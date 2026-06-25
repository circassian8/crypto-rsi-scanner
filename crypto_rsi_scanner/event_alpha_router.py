"""Research-only routing decisions for Event Alpha Radar watchlist rows."""

from __future__ import annotations

import html
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from . import event_playbooks, event_watchlist


class EventAlphaRoute(str, Enum):
    SUPPRESS_DUPLICATE = "SUPPRESS_DUPLICATE"
    STORE_ONLY = "STORE_ONLY"
    LOCAL_REPORT = "LOCAL_REPORT"
    RESEARCH_DIGEST = "RESEARCH_DIGEST"
    HIGH_PRIORITY_RESEARCH = "HIGH_PRIORITY_RESEARCH"
    TRIGGERED_FADE_RESEARCH = "TRIGGERED_FADE_RESEARCH"


class EventAlphaRouteLane(str, Enum):
    DAILY_DIGEST = "DAILY_DIGEST"
    INSTANT_ESCALATION = "INSTANT_ESCALATION"
    TRIGGERED_FADE = "TRIGGERED_FADE"
    LOCAL_ONLY = "LOCAL_ONLY"


@dataclass(frozen=True)
class EventAlphaRouterConfig:
    enabled: bool = False
    include_suppressed: bool = True
    daily_digest_enabled: bool = True
    instant_enabled: bool = True
    max_digest_items: int = 20
    validated_hypothesis_digest_enabled: bool = False
    max_validated_hypothesis_digest_items: int = 5
    validated_hypothesis_min_score: float = 65.0
    validated_hypothesis_min_opportunity_score: float = 65.0
    validated_hypothesis_min_final_score: float = 65.0
    validated_hypothesis_require_external_or_direct_event: bool = True
    validated_hypothesis_require_impact_path: bool = True
    weak_validated_local_only: bool = True
    allow_weak_path_with_market_confirmation: bool = True
    block_generic_cooccurrence_digest: bool = True
    max_high_priority_per_day: int = 3
    per_key_cooldown_hours: float = 12.0
    alert_on_score_jump: bool = True
    score_jump_threshold: int = 10
    alert_on_new_independent_source: bool = True
    alert_on_event_time_upgrade: bool = True
    alert_on_derivatives_crowding_upgrade: bool = True
    alert_on_cluster_confidence_upgrade: bool = True


@dataclass(frozen=True)
class EventAlphaRouteDecision:
    entry: event_watchlist.EventWatchlistEntry
    route: EventAlphaRoute
    alertable: bool
    reason: str
    lane: EventAlphaRouteLane = EventAlphaRouteLane.LOCAL_ONLY
    warnings: tuple[str, ...] = ()

    @property
    def alert_id(self) -> str:
        return alert_id_for_entry(self.entry)

    @property
    def card_id(self) -> str:
        return card_id_for_entry(self.entry)


@dataclass(frozen=True)
class EventAlphaRouterResult:
    state_path: Path
    rows_read: int
    decisions: list[EventAlphaRouteDecision]
    enabled: bool

    @property
    def alertable_decisions(self) -> list[EventAlphaRouteDecision]:
        return [decision for decision in self.decisions if decision.alertable]


def route_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    cfg: EventAlphaRouterConfig | None = None,
) -> EventAlphaRouterResult:
    """Convert latest watchlist state into artifact-only research route decisions."""
    cfg = cfg or EventAlphaRouterConfig()
    decisions = _apply_route_caps([_route_entry(entry, cfg=cfg) for entry in read_result.entries], cfg)
    if not cfg.include_suppressed:
        decisions = [decision for decision in decisions if decision.alertable]
    return EventAlphaRouterResult(
        state_path=read_result.state_path,
        rows_read=read_result.rows_read,
        decisions=sorted(decisions, key=_decision_sort_key),
        enabled=cfg.enabled,
    )


def format_router_report(result: EventAlphaRouterResult) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA ROUTER REPORT (research-only; no sends, trades, or paper rows)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"router_enabled: {str(result.enabled).lower()}",
        f"rows_read: {result.rows_read} · decisions: {len(result.decisions)} · alertable: {len(result.alertable_decisions)}",
    ]
    if not result.enabled:
        rows.append("disabled: set RSI_EVENT_ALPHA_ROUTER_ENABLED=1 for route decisions.")
    if not result.decisions:
        rows.append("")
        rows.append("No watchlist rows to route.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for decision in result.decisions:
        counts[decision.route.value] = counts.get(decision.route.value, 0) + 1
    rows.append("routes: " + ", ".join(f"{route}={count}" for route, count in sorted(counts.items())))
    lane_counts: dict[str, int] = {}
    for decision in result.decisions:
        lane_counts[decision.lane.value] = lane_counts.get(decision.lane.value, 0) + 1
    rows.append("lanes: " + ", ".join(f"{lane}={count}" for lane, count in sorted(lane_counts.items())))
    rows.append("")
    for decision in result.decisions:
        entry = decision.entry
        rows.append(
            f"{decision.route.value:<24} score={entry.latest_score:>3} high={entry.highest_score:>3} "
            f"{entry.symbol}/{entry.coin_id}"
        )
        rows.append(f"  alert_id: {decision.alert_id} · card_id: {decision.card_id}")
        rows.append(f"  event: {entry.latest_event_name}")
        rows.append(
            f"  state: {entry.previous_state or 'new'} -> {entry.state} · "
            f"watchlist_alertable={str(entry.should_alert).lower()}"
        )
        rows.append(
            f"  playbook: {entry.latest_playbook_type or 'unknown'} "
            f"action={entry.latest_playbook_action or 'store_only'}"
        )
        components = entry.latest_score_components or {}
        if entry.relationship_type == "impact_hypothesis" and (
            components.get("opportunity_level") or components.get("opportunity_score_final")
        ):
            rows.append(
                "  opportunity: "
                f"level={components.get('opportunity_level') or 'unknown'} "
                f"score={components.get('opportunity_score_final') if components.get('opportunity_score_final') is not None else 'n/a'} "
                f"market={components.get('market_confirmation_level') or 'unknown'} "
                f"evidence={components.get('source_class') or 'unknown'}/{components.get('evidence_specificity') or 'unknown'}"
            )
        rows.append(f"  route reason: {decision.reason}")
        rows.append(f"  lane: {decision.lane.value}")
        rows.append(f"  card: {decision.card_id}.md")
        rows.append(f"  feedback: make event-feedback-useful FEEDBACK_TARGET={decision.alert_id}")
        if entry.latest_llm_asset_role:
            rows.append(
                f"  llm: role={entry.latest_llm_asset_role} "
                f"conf={entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0:.2f}"
            )
        warnings = (*entry.warnings, *decision.warnings)
        if warnings:
            rows.append("  warnings: " + "; ".join(dict.fromkeys(warnings)))
        if entry.suppressed_reason:
            rows.append(f"  watchlist suppressed: {entry.suppressed_reason}")
        rows.append("")
    return "\n".join(rows).rstrip()


def format_routed_telegram_digest(
    decisions: Iterable[EventAlphaRouteDecision],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, object] | None = None,
) -> str:
    """Render router-approved Event Alpha escalations for Telegram."""
    keep = [decision for decision in decisions if decision.alertable]
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    lines = [
        "<b>Event Alpha routed research alerts</b>",
        "<i>Research-only / DAY-1 UNVALIDATED. Not a trade signal, paper trade, or execution.</i>",
        "Validation status: DAY-1 UNVALIDATED",
        "Trading action: NONE",
        "Review before acting.",
    ]
    if profile:
        lines.append(f"profile={_esc(profile)}")
    if not keep:
        lines.append("No router-approved escalations.")
        return "\n".join(lines)
    for decision in keep:
        entry = decision.entry
        is_validated_hypothesis = _is_validated_hypothesis_digest_entry(entry)
        lines.append("")
        lines.append(
            f"<b>{_esc(decision.route.value)}</b> score={entry.latest_score} "
            f"<b>{_esc(entry.symbol)}</b>"
        )
        if is_validated_hypothesis:
            lines.append("<b>Validated impact hypothesis</b>")
            lines.append("Catalyst link validated, but this is not a calibrated strategy.")
        lines.append(_esc(entry.latest_event_name or "unknown event"))
        lines.append(
            f"tier={_esc(entry.latest_tier or 'unknown')} route={_esc(decision.route.value)} "
            f"lane={_esc(decision.lane.value)}"
        )
        if profile:
            lines.append(f"profile={_esc(profile)} notification_lane={_esc(decision.lane.value)}")
        lines.append(
            f"state={_esc(entry.state)} playbook={_esc(entry.latest_playbook_type or 'unknown')} "
            f"external_catalyst={_esc(entry.external_asset or 'unknown')}"
        )
        lines.append(_event_time_line(entry))
        lines.append("market=" + _esc(_market_summary(entry.latest_market_snapshot)))
        if entry.latest_rule_playbook_type and entry.latest_rule_playbook_type != entry.latest_playbook_type:
            lines.append(f"rule_playbook={_esc(entry.latest_rule_playbook_type)}")
        if entry.latest_llm_asset_role:
            conf = entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0
            lines.append(f"llm_role={_esc(entry.latest_llm_asset_role)} llm_confidence={conf:.2f}")
        else:
            lines.append("llm_role=none llm_confidence=n/a")
        lines.append(f"route_reason={_esc(decision.reason)}")
        if is_validated_hypothesis:
            lines.append("operator_note=Research-only. Not a trade signal. Review the local card before acting.")
        lines.append(f"alert_id={_esc(decision.alert_id)}")
        lines.append(f"card_id={_esc(decision.card_id)}")
        card_path = card_paths.get(decision.alert_id)
        if card_path:
            lines.append(f"research_card={_esc(card_path)}")
        else:
            lines.append("research_card=not_written")
        lines.append(f"feedback=make event-feedback-useful FEEDBACK_TARGET={_esc(decision.alert_id)}")
        warnings = tuple(dict.fromkeys((*entry.warnings, *decision.warnings)))
        if warnings:
            lines.append("warnings=" + _esc("; ".join(warnings[:3])))
    return "\n".join(lines)


def _route_entry(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
) -> EventAlphaRouteDecision:
    playbook = entry.latest_playbook_type or ""
    state = entry.state
    warnings = list(entry.warnings)

    if not cfg.enabled:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Event Alpha router is disabled; retaining watchlist row as research evidence only.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if _is_raw_or_terminal(state):
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Raw, expired, or invalidated watchlist state is stored only.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value:
            return EventAlphaRouteDecision(
                entry=entry,
                route=EventAlphaRoute.TRIGGERED_FADE_RESEARCH,
                alertable=True,
                reason="Proxy-fade playbook reached TRIGGERED_FADE from the deterministic event_fade engine.",
                lane=EventAlphaRouteLane.TRIGGERED_FADE,
                warnings=tuple(warnings),
            )
        warnings.append("non-proxy playbook cannot route triggered fade")
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.LOCAL_REPORT,
            alertable=False,
            reason="Triggered state is retained for local review because the playbook is not proxy_fade.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    material_allowed, material_reason = _material_change_allowed(entry, cfg)
    if not entry.should_alert or not material_allowed:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.SUPPRESS_DUPLICATE,
            alertable=False,
            reason=material_reason or entry.suppressed_reason or "No meaningful state escalation since the previous observation.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if _looks_like_validated_hypothesis(entry):
        quality_block = _validated_hypothesis_digest_block_reason(entry, cfg)
        if quality_block:
            warnings.append(f"validated_hypothesis_digest_blocked:{quality_block}")
            return EventAlphaRouteDecision(
                entry=entry,
                route=EventAlphaRoute.STORE_ONLY,
                alertable=False,
                reason=f"Validated impact hypothesis kept local-only: {quality_block}.",
                lane=EventAlphaRouteLane.LOCAL_ONLY,
                warnings=tuple(warnings),
            )
        route = _validated_hypothesis_route(entry)
        return EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=(
                cfg.instant_enabled
                if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
                else cfg.daily_digest_enabled and cfg.validated_hypothesis_digest_enabled
            ),
            reason=_validated_hypothesis_route_reason(entry),
            lane=EventAlphaRouteLane.INSTANT_ESCALATION
            if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            else EventAlphaRouteLane.DAILY_DIGEST,
            warnings=tuple(warnings),
        )

    if entry.relationship_type == "impact_hypothesis":
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Impact hypothesis rows require catalyst-link validation and a validated token identity before digest routing.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if playbook in {
        event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
        event_playbooks.EventPlaybookType.AMBIGUOUS_CONTROL.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value,
    }:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Control/anomaly playbooks are evidence only until catalyst and asset identity are validated.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if playbook == event_playbooks.EventPlaybookType.INFRASTRUCTURE_MENTION.value:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.LOCAL_REPORT,
            alertable=False,
            reason="Infrastructure playbooks may be reviewed locally but cannot enter research digest routing.",
            lane=EventAlphaRouteLane.LOCAL_ONLY,
            warnings=tuple(warnings),
        )

    if playbook in _NON_FADE_RESEARCH_PLAYBOOKS:
        route = (
            EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            if state in {
                event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                event_watchlist.EventWatchlistState.ARMED.value,
                event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            }
            else EventAlphaRoute.RESEARCH_DIGEST
        )
        return EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=cfg.instant_enabled if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH else cfg.daily_digest_enabled,
            reason="Non-fade event playbook produced a research-only state escalation.",
            lane=EventAlphaRouteLane.INSTANT_ESCALATION
            if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            else EventAlphaRouteLane.DAILY_DIGEST,
            warnings=tuple(warnings),
        )

    if state in {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.ARMED.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
    }:
        route = (
            EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value
            else EventAlphaRoute.RESEARCH_DIGEST
        )
        return EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=cfg.instant_enabled if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH else cfg.daily_digest_enabled,
            reason="Proxy candidate escalated to a higher watchlist state.",
            lane=EventAlphaRouteLane.INSTANT_ESCALATION
            if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            else EventAlphaRouteLane.DAILY_DIGEST,
            warnings=tuple(warnings),
        )

    if state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.RADAR.value,
    } and playbook in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.RESEARCH_DIGEST,
            alertable=cfg.daily_digest_enabled,
            reason="Proxy candidate produced a meaningful radar/watchlist escalation.",
            lane=EventAlphaRouteLane.DAILY_DIGEST,
            warnings=tuple(warnings),
        )

    return EventAlphaRouteDecision(
        entry=entry,
        route=EventAlphaRoute.LOCAL_REPORT,
        alertable=False,
        reason="Unrecognized playbook/state combination is kept in local research output only.",
        lane=EventAlphaRouteLane.LOCAL_ONLY,
        warnings=tuple(warnings),
    )


def alert_id_for_entry(entry: event_watchlist.EventWatchlistEntry) -> str:
    return f"ea:{entry.key}"


def card_id_for_entry(entry: event_watchlist.EventWatchlistEntry) -> str:
    return "card_" + "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in entry.key)[:180]


def validated_hypothesis_digest_block_reason(
    entry: event_watchlist.EventWatchlistEntry,
    cfg: EventAlphaRouterConfig | None = None,
) -> str | None:
    """Return why a validated impact hypothesis is local-only, or None if digest-eligible."""
    return _validated_hypothesis_digest_block_reason(entry, cfg or EventAlphaRouterConfig())


def _material_change_allowed(
    entry: event_watchlist.EventWatchlistEntry,
    cfg: EventAlphaRouterConfig,
) -> tuple[bool, str | None]:
    reasons = set(entry.material_change_reasons)
    if not reasons:
        return True, None
    allowed = False
    blocked: list[str] = []
    if reasons & {
        "initial_validated_hypothesis",
        "hypothesis_validated",
        "impact_path_confirmed",
        "market_confirmation_upgraded",
        "evidence_quality_upgraded",
        "opportunity_score_upgraded",
    }:
        allowed = True
    if "score_jump" in reasons:
        if cfg.alert_on_score_jump and entry.score_jump >= cfg.score_jump_threshold:
            allowed = True
        else:
            blocked.append("score jump alerts disabled or below threshold")
    if "new_independent_source" in reasons:
        if cfg.alert_on_new_independent_source:
            allowed = True
        else:
            blocked.append("new source alerts disabled")
    if "event_time_upgrade" in reasons:
        if cfg.alert_on_event_time_upgrade:
            allowed = True
        else:
            blocked.append("event-time upgrade alerts disabled")
    if "derivatives_crowding_upgrade" in reasons:
        if cfg.alert_on_derivatives_crowding_upgrade:
            allowed = True
        else:
            blocked.append("derivatives upgrade alerts disabled")
    if "supply_pressure_upgrade" in reasons:
        allowed = True
    if "cluster_confidence_upgrade" in reasons:
        if cfg.alert_on_cluster_confidence_upgrade:
            allowed = True
        else:
            blocked.append("cluster-confidence upgrade alerts disabled")
    if "hypothesis_validated" in reasons:
        allowed = True
    if not allowed:
        return False, "; ".join(blocked) or "material-change alerts disabled"
    return True, None


def _apply_route_caps(
    decisions: list[EventAlphaRouteDecision],
    cfg: EventAlphaRouterConfig,
) -> list[EventAlphaRouteDecision]:
    digest_seen = 0
    validated_hypothesis_seen = 0
    high_seen = 0
    out: list[EventAlphaRouteDecision] = []
    for decision in sorted(decisions, key=_decision_sort_key):
        if not decision.alertable:
            out.append(decision)
            continue
        if decision.lane == EventAlphaRouteLane.TRIGGERED_FADE:
            out.append(decision)
            continue
        if _cooldown_active(decision.entry, cfg):
            out.append(EventAlphaRouteDecision(
                entry=decision.entry,
                route=EventAlphaRoute.SUPPRESS_DUPLICATE,
                alertable=False,
                reason=f"Per-key cooldown active ({cfg.per_key_cooldown_hours:g}h).",
                lane=EventAlphaRouteLane.LOCAL_ONLY,
                warnings=decision.warnings,
            ))
            continue
        if decision.lane == EventAlphaRouteLane.INSTANT_ESCALATION:
            high_seen += 1
            if cfg.max_high_priority_per_day and high_seen > cfg.max_high_priority_per_day:
                out.append(EventAlphaRouteDecision(
                    entry=decision.entry,
                    route=EventAlphaRoute.SUPPRESS_DUPLICATE,
                    alertable=False,
                    reason="High-priority route cap reached for this run.",
                    lane=EventAlphaRouteLane.LOCAL_ONLY,
                    warnings=decision.warnings,
                ))
                continue
        if decision.lane == EventAlphaRouteLane.DAILY_DIGEST:
            if _looks_like_validated_hypothesis(decision.entry):
                validated_hypothesis_seen += 1
                if (
                    cfg.max_validated_hypothesis_digest_items
                    and validated_hypothesis_seen > cfg.max_validated_hypothesis_digest_items
                ):
                    out.append(EventAlphaRouteDecision(
                        entry=decision.entry,
                        route=EventAlphaRoute.SUPPRESS_DUPLICATE,
                        alertable=False,
                        reason="Validated impact hypothesis digest cap reached for this run.",
                        lane=EventAlphaRouteLane.LOCAL_ONLY,
                        warnings=decision.warnings,
                    ))
                    continue
            digest_seen += 1
            if cfg.max_digest_items and digest_seen > cfg.max_digest_items:
                out.append(EventAlphaRouteDecision(
                    entry=decision.entry,
                    route=EventAlphaRoute.SUPPRESS_DUPLICATE,
                    alertable=False,
                    reason="Daily digest item cap reached for this run.",
                    lane=EventAlphaRouteLane.LOCAL_ONLY,
                    warnings=decision.warnings,
                ))
                continue
        out.append(decision)
    return out


def _is_validated_hypothesis_digest_entry(entry: event_watchlist.EventWatchlistEntry) -> bool:
    return _validated_hypothesis_digest_block_reason(entry, EventAlphaRouterConfig()) is None


def _looks_like_validated_hypothesis(entry: event_watchlist.EventWatchlistEntry) -> bool:
    if entry.relationship_type != "impact_hypothesis":
        return False
    if entry.state != event_watchlist.EventWatchlistState.RADAR.value:
        return False
    if (entry.symbol or "").upper() == "SECTOR":
        return False
    components = entry.latest_score_components or {}
    if str(components.get("validation_stage") or "") not in {
        "catalyst_link_validated",
        "impact_path_validated",
        "market_confirmed",
        "promoted_to_radar",
    }:
        return False
    if not (components.get("validated_symbol") or components.get("validated_coin_id") or components.get("validated_asset")):
        return False
    return True


def _validated_hypothesis_route(entry: event_watchlist.EventWatchlistEntry) -> EventAlphaRoute:
    level = str((entry.latest_score_components or {}).get("opportunity_level") or "").strip()
    if level == "high_priority":
        return EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    return EventAlphaRoute.RESEARCH_DIGEST


def _validated_hypothesis_route_reason(entry: event_watchlist.EventWatchlistEntry) -> str:
    components = entry.latest_score_components or {}
    level = str(components.get("opportunity_level") or "validated_digest").strip()
    score = _hypothesis_opportunity_score_final(entry, components)
    if level == "high_priority":
        return f"Validated impact hypothesis reached high-priority opportunity verdict ({score:.0f})."
    if level == "watchlist":
        return f"Validated impact hypothesis reached watchlist opportunity verdict ({score:.0f})."
    return f"Validated impact hypothesis reached digest opportunity verdict ({score:.0f})."


def _validated_hypothesis_digest_block_reason(
    entry: event_watchlist.EventWatchlistEntry,
    cfg: EventAlphaRouterConfig,
) -> str | None:
    if entry.relationship_type != "impact_hypothesis":
        return "not_impact_hypothesis"
    if entry.state != event_watchlist.EventWatchlistState.RADAR.value:
        return "not_radar_state"
    if (entry.symbol or "").upper() == "SECTOR":
        return "missing_validated_token_identity"
    components = dict(entry.latest_score_components or {})
    stage = str(components.get("validation_stage") or "").strip()
    if stage not in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
        return "catalyst_link_not_validated"
    if not (components.get("validated_symbol") or components.get("validated_coin_id") or components.get("validated_asset")):
        return "missing_validated_token_identity"
    playbook = str(entry.latest_effective_playbook_type or entry.latest_playbook_type or "").strip()
    category = str(components.get("impact_category") or playbook or "").strip()
    if playbook in {
        "",
        "impact_hypothesis",
        event_playbooks.EventPlaybookType.AMBIGUOUS_CONTROL.value,
        event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value,
    }:
        return "ambiguous_playbook"
    gate_text = " ".join(
        str(value or "")
        for value in (
            playbook,
            category,
            entry.latest_llm_asset_role,
            *entry.warnings,
            *(components.get("warnings") or ()),
            *(components.get("rejection_reasons") or ()),
            *(components.get("why_not_promoted") or ()),
        )
    ).casefold()
    if "source_noise" in gate_text or "ticker_collision" in gate_text or "word_collision" in gate_text:
        return "source_noise_or_ticker_collision"
    score = _hypothesis_score(entry, components)
    if score < float(cfg.validated_hypothesis_min_score):
        return f"score_below_threshold:{score:.0f}<{cfg.validated_hypothesis_min_score:.0f}"
    opportunity_score = _hypothesis_opportunity_score_v2(entry, components)
    if opportunity_score < float(cfg.validated_hypothesis_min_opportunity_score):
        return (
            "opportunity_score_v2_below_threshold:"
            f"{opportunity_score:.0f}<{cfg.validated_hypothesis_min_opportunity_score:.0f}"
        )
    final_score = _hypothesis_opportunity_score_final(entry, components)
    if final_score < float(cfg.validated_hypothesis_min_final_score):
        return (
            "opportunity_score_final_below_threshold:"
            f"{final_score:.0f}<{cfg.validated_hypothesis_min_final_score:.0f}"
        )
    opportunity_level = str(components.get("opportunity_level") or "").strip()
    if opportunity_level in {"local_only", "exploratory"}:
        reason = str(components.get("why_local_only") or components.get("why_not_watchlist") or opportunity_level)
        return f"opportunity_level_not_digest_eligible:{reason}"
    path_type = str(components.get("impact_path_type") or "").strip()
    path_strength = str(components.get("impact_path_strength") or "").strip()
    digest_eligible = _boolish(components.get("digest_eligible_by_impact_path"))
    why_digest_ineligible = str(components.get("why_digest_ineligible") or "").strip()
    if cfg.block_generic_cooccurrence_digest and path_type == "generic_cooccurrence_only":
        return "generic_cooccurrence_only"
    if cfg.validated_hypothesis_require_impact_path:
        if path_strength:
            market_score = _market_confirmation_component(components)
            if path_strength == "strong" and (digest_eligible is not False):
                pass
            elif path_strength == "medium" and cfg.allow_weak_path_with_market_confirmation and market_score >= 40.0:
                pass
            elif (
                path_strength == "weak"
                and cfg.allow_weak_path_with_market_confirmation
                and market_score >= 75.0
                and path_type not in {"generic_cooccurrence_only", "macro_attention_only", "technology_risk", "market_structure_policy"}
            ):
                pass
            else:
                reason = why_digest_ineligible or components.get("impact_path_reason") or path_strength
                return f"impact_path_not_digest_eligible:{reason}"
        if stage not in {"impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            direct_override_score = max(75.0, float(cfg.validated_hypothesis_min_score) + 10.0)
            if not (_has_clear_direct_token_event(entry, components) and score >= direct_override_score):
                reason = str(components.get("impact_path_reason") or "no_value_capture_explained")
                return f"impact_path_not_validated:{reason}"
            if cfg.weak_validated_local_only:
                reason = str(components.get("impact_path_reason") or "weak_cooccurrence_only")
                return f"weak_validated_local_only:{reason}"
    if cfg.validated_hypothesis_require_external_or_direct_event and _missing_external(entry.external_asset):
        if not _has_clear_direct_token_event(entry, components):
            return "missing_external_asset_or_clear_direct_token_event"
    return None


def _hypothesis_score(entry: event_watchlist.EventWatchlistEntry, components: Mapping[str, object]) -> float:
    for value in (
        components.get("hypothesis_score"),
        components.get("score"),
        entry.latest_score,
        components.get("hypothesis_confidence"),
    ):
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            continue
        if num > 0:
            return num
    return 0.0


def _hypothesis_opportunity_score_v2(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, object],
) -> float:
    for value in (
        components.get("opportunity_score_v2"),
        entry.latest_score,
        components.get("hypothesis_score"),
        components.get("score"),
    ):
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            continue
        if num > 0:
            return num
    return 0.0


def _hypothesis_opportunity_score_final(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, object],
) -> float:
    for value in (
        components.get("opportunity_score_final"),
        components.get("opportunity_score_v2"),
        entry.latest_score,
        components.get("hypothesis_score"),
    ):
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            continue
        if num > 0:
            return num
    return 0.0


def _market_confirmation_component(components: Mapping[str, object]) -> float:
    for value in (
        components.get("market_confirmation"),
        (components.get("opportunity_score_components") or {}).get("market_confirmation")
        if isinstance(components.get("opportunity_score_components"), Mapping)
        else None,
        components.get("market_move_volume"),
    ):
        if value in (None, ""):
            continue
        try:
            return max(0.0, min(100.0, float(value or 0.0)))
        except (TypeError, ValueError):
            continue
    return 0.0


def _boolish(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _missing_external(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return text in {"", "unknown", "none", "null", "n/a", "na", "sector"}


def _has_clear_direct_token_event(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, object],
) -> bool:
    category = str(components.get("impact_category") or entry.latest_playbook_type or "").strip()
    evidence_text = _direct_event_evidence_text(entry, components)
    asset_terms = _asset_identity_terms(entry, components)
    mentions_asset = any(_term_in_text(term, evidence_text) for term in asset_terms)
    if not mentions_asset:
        return False
    if category == event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value:
        return any(
            _term_in_text(term, evidence_text)
            for term in ("exploit", "hack", "lawsuit", "sec", "cftc", "regulatory", "security incident", "attack")
        )
    if category == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value or category == "listing_liquidity_event":
        return any(
            _term_in_text(term, evidence_text)
            for term in ("listing", "listed on", "nasdaq", "public listing", "merger", "coinbase", "binance")
        )
    if category == event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE.value:
        return any(_term_in_text(term, evidence_text) for term in ("unlock", "vesting", "airdrop", "tge", "emission"))
    return False


def _direct_event_evidence_text(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, object],
) -> str:
    parts: list[str] = [
        entry.latest_event_name,
        entry.latest_source,
        str(components.get("impact_category") or ""),
    ]
    for field in ("validation_reasons", "evidence_quotes", "why_not_promoted"):
        values = components.get(field) or ()
        if isinstance(values, str):
            parts.append(values)
        elif isinstance(values, Iterable):
            parts.extend(str(value) for value in values)
    asset = components.get("validated_asset")
    if isinstance(asset, Mapping):
        parts.extend(str(value) for value in asset.values())
    return " ".join(part for part in parts if part).casefold()


def _asset_identity_terms(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, object],
) -> tuple[str, ...]:
    terms = [entry.symbol, entry.coin_id, components.get("validated_symbol"), components.get("validated_coin_id")]
    asset = components.get("validated_asset")
    if isinstance(asset, Mapping):
        terms.extend(asset.get(key) for key in ("symbol", "coin_id", "name"))
    out = [
        str(term).strip().casefold()
        for term in terms
        if str(term or "").strip() and str(term or "").strip().casefold() not in {"sector", "unknown", "none"}
    ]
    return tuple(dict.fromkeys(out))


def _term_in_text(term: str, text: str) -> bool:
    clean = str(term or "").strip().casefold()
    if not clean:
        return False
    return clean in text


def _cooldown_active(
    entry: event_watchlist.EventWatchlistEntry,
    cfg: EventAlphaRouterConfig,
) -> bool:
    if entry.escalation:
        return False
    if cfg.per_key_cooldown_hours <= 0 or not entry.alert_history:
        return False
    latest = entry.alert_history[-1]
    latest_ts = _parse_iso(latest.get("observed_at"))
    if latest_ts is None:
        return False
    for prior in entry.alert_history[:-1]:
        if not bool(prior.get("should_alert")):
            continue
        prior_ts = _parse_iso(prior.get("observed_at"))
        if prior_ts is None:
            continue
        age_hours = (latest_ts - prior_ts).total_seconds() / 3600.0
        if 0 <= age_hours < cfg.per_key_cooldown_hours:
            return True
    return False


def _parse_iso(value: object):
    from datetime import datetime, timezone

    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _is_raw_or_terminal(state: str) -> bool:
    return state in {
        event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        event_watchlist.EventWatchlistState.INVALIDATED.value,
        event_watchlist.EventWatchlistState.EXPIRED.value,
    }


def _decision_sort_key(decision: EventAlphaRouteDecision) -> tuple[int, int, str]:
    rank = {
        EventAlphaRoute.TRIGGERED_FADE_RESEARCH: 0,
        EventAlphaRoute.HIGH_PRIORITY_RESEARCH: 1,
        EventAlphaRoute.RESEARCH_DIGEST: 2,
        EventAlphaRoute.LOCAL_REPORT: 3,
        EventAlphaRoute.SUPPRESS_DUPLICATE: 4,
        EventAlphaRoute.STORE_ONLY: 5,
    }
    entry = decision.entry
    return (rank[decision.route], -entry.highest_score, entry.symbol)


_NON_FADE_RESEARCH_PLAYBOOKS = {
    event_playbooks.EventPlaybookType.DIRECT_EVENT.value,
    event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value,
    event_playbooks.EventPlaybookType.PERP_LISTING_SQUEEZE.value,
    event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE.value,
    event_playbooks.EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE.value,
    event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
    event_playbooks.EventPlaybookType.POLITICAL_MEME_EVENT.value,
    event_playbooks.EventPlaybookType.RWA_PREIPO_PROXY.value,
    event_playbooks.EventPlaybookType.AI_IPO_PROXY.value,
    event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _event_time_line(entry: event_watchlist.EventWatchlistEntry) -> str:
    event_time = entry.event_time or "unknown"
    parsed = _parse_iso(event_time)
    if parsed is None:
        return f"event_time={_esc(event_time)} countdown=unknown"
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    hours = (parsed - now).total_seconds() / 3600.0
    if hours >= 0:
        countdown = f"T-{hours:.1f}h"
    else:
        countdown = f"T+{abs(hours):.1f}h"
    return f"event_time={_esc(event_time)} countdown={_esc(countdown)}"


def _market_summary(snapshot: Mapping[str, object] | None) -> str:
    if not snapshot:
        return "no market confirmation snapshot"
    bits: list[str] = []
    for key in ("price", "return_24h", "return_72h", "volume_zscore_24h", "rsi_1d", "rsi_4h"):
        value = snapshot.get(key)
        if value not in (None, ""):
            bits.append(f"{key}={value}")
    return ", ".join(bits[:5]) if bits else "market snapshot present"
