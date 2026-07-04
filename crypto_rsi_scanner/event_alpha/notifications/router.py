"""Research-only routing decisions for Event Alpha Radar watchlist rows."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from ... import event_alpha_quality_fields, event_opportunity_verdict, event_playbooks, event_watchlist
from . import router_rendering


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
    requested_route_before_quality_gate: str | None = None
    final_route_after_quality_gate: str | None = None
    quality_gate_block_reason: str | None = None
    opportunity_level: str | None = None
    opportunity_score_final: float | None = None
    routing_score_used: float | None = None
    routing_score_source: str | None = None
    routing_verdict_used: str | None = None

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
        return [decision for decision in self.decisions if alertable_after_quality_gate(decision)]


ALERTABLE_ROUTE_VALUES = {
    EventAlphaRoute.RESEARCH_DIGEST.value,
    EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
    EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
}


def route_value_is_alertable(route_value: object) -> bool:
    return str(getattr(route_value, "value", route_value) or "") in ALERTABLE_ROUTE_VALUES


def lane_value_for_route_value(route_value: object) -> str:
    route = str(getattr(route_value, "value", route_value) or "")
    if route == EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return EventAlphaRouteLane.TRIGGERED_FADE.value
    if route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value:
        return EventAlphaRouteLane.INSTANT_ESCALATION.value
    if route == EventAlphaRoute.RESEARCH_DIGEST.value:
        return EventAlphaRouteLane.DAILY_DIGEST.value
    return EventAlphaRouteLane.LOCAL_ONLY.value


def final_route_value(decision: object) -> str:
    explicit = getattr(decision, "final_route_after_quality_gate", None)
    if explicit:
        return str(explicit)
    route = getattr(decision, "route", None)
    route_value = str(getattr(route, "value", route) or "")
    if route_value:
        return route_value
    lane = getattr(decision, "lane", None)
    lane_value = str(getattr(lane, "value", lane) or "")
    if lane_value == EventAlphaRouteLane.TRIGGERED_FADE.value:
        return EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value
    if lane_value == EventAlphaRouteLane.INSTANT_ESCALATION.value:
        return EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if lane_value == EventAlphaRouteLane.DAILY_DIGEST.value:
        return EventAlphaRoute.RESEARCH_DIGEST.value
    return EventAlphaRoute.STORE_ONLY.value


def final_lane_value(decision: object) -> str:
    return lane_value_for_route_value(final_route_value(decision))


def alertable_after_quality_gate(decision: object) -> bool:
    return bool(getattr(decision, "alertable", False)) and route_value_is_alertable(final_route_value(decision))


def quality_gate_route_for_row(
    row: Mapping[str, object],
    *,
    components: Mapping[str, object] | None = None,
    requested_route: str | None = None,
    require_quality: bool = False,
) -> tuple[str, str | None]:
    """Return the final quality-gated route for persisted artifact rows.

    This is intentionally conservative for modern rows carrying quality fields,
    while preserving legacy rows that lack quality metadata unless callers opt in
    to recomputing missing-quality defaults.
    """
    data = dict(row or {})
    nested = components
    if nested is None:
        raw_nested = data.get("score_components")
        if not isinstance(raw_nested, Mapping):
            raw_nested = data.get("latest_score_components")
        nested = raw_nested if isinstance(raw_nested, Mapping) else {}
    has_quality = event_alpha_quality_fields.has_any_quality_field(data, components_key="score_components")
    if not has_quality and not require_quality:
        final = str(
            data.get("final_route_after_quality_gate")
            or requested_route
            or data.get("route")
            or EventAlphaRoute.STORE_ONLY.value
        )
        return final, _optional_str(data.get("quality_gate_block_reason"))
    stored_reason = _optional_str(data.get("quality_gate_block_reason"))
    stored_final_route = str(data.get("final_route_after_quality_gate") or "").strip()
    use_reconciled_final_route = (
        not requested_route
        and stored_final_route
        and _is_core_route_derivation_reason(stored_reason)
    )
    requested = str(
        (stored_final_route if use_reconciled_final_route else None)
        or requested_route
        or data.get("requested_route_before_quality_gate")
        or data.get("route")
        or data.get("final_route_after_quality_gate")
        or EventAlphaRoute.STORE_ONLY.value
    )
    if requested == EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return requested, None
    quality = event_alpha_quality_fields.ensure_quality_fields(data, components=nested)
    level = str(quality.get("opportunity_level") or "").strip()
    block = _quality_gate_block_reason(quality)
    if block:
        if level == event_opportunity_verdict.OpportunityLevel.EXPLORATORY.value:
            return EventAlphaRoute.LOCAL_REPORT.value, block
        return EventAlphaRoute.STORE_ONLY.value, block
    if (
        requested == EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
        and level in {
            event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
            event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
        }
    ):
        return (
            EventAlphaRoute.RESEARCH_DIGEST.value,
            f"opportunity_level_caps_high_priority:{level}",
        )
    return requested, stored_reason


def alertable_after_quality_gate_for_row(
    row: Mapping[str, object],
    *,
    components: Mapping[str, object] | None = None,
    require_quality: bool = False,
) -> bool:
    final, _ = quality_gate_route_for_row(row, components=components, require_quality=require_quality)
    return route_value_is_alertable(final)


def _is_core_route_derivation_reason(reason: str | None) -> bool:
    return str(reason or "").startswith("core_route_derived_from_opportunity_level:")


def route_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    cfg: EventAlphaRouterConfig | None = None,
) -> EventAlphaRouterResult:
    """Convert latest watchlist state into artifact-only research route decisions."""
    cfg = cfg or EventAlphaRouterConfig()
    requested = [_route_entry(entry, cfg=cfg) for entry in read_result.entries]
    decisions = _apply_route_caps([_apply_quality_gate(decision) for decision in requested], cfg)
    if not cfg.include_suppressed:
        decisions = [decision for decision in decisions if decision.alertable]
    return EventAlphaRouterResult(
        state_path=read_result.state_path,
        rows_read=read_result.rows_read,
        decisions=sorted(decisions, key=_decision_sort_key),
        enabled=cfg.enabled,
    )


def format_router_report(result: EventAlphaRouterResult) -> str:
    return router_rendering.format_router_report(result)


def format_routed_telegram_digest(
    decisions: Iterable[EventAlphaRouteDecision],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, object] | None = None,
) -> str:
    return router_rendering.format_routed_telegram_digest(
        decisions,
        profile=profile,
        card_path_by_alert_id=card_path_by_alert_id,
        alertable_after_quality_gate=alertable_after_quality_gate,
        final_route_value=final_route_value,
        is_validated_hypothesis_digest_entry=_is_validated_hypothesis_digest_entry,
    )


def _route_entry(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
) -> EventAlphaRouteDecision:
    playbook = entry.latest_playbook_type or ""
    state = event_watchlist.final_state_value(entry)
    warnings = list(entry.warnings)

    if not cfg.enabled:
        return _disabled_route_decision(entry, warnings)

    quality_capped = _quality_capped_route_decision(
        entry,
        playbook=playbook,
        state=state,
        warnings=warnings,
    )
    if quality_capped is not None:
        return quality_capped

    if _is_raw_or_terminal(state):
        return _raw_or_terminal_route_decision(entry, warnings)

    if state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return _triggered_fade_route_decision(entry, playbook=playbook, warnings=warnings)

    material_allowed, material_reason = _material_change_allowed(entry, cfg)
    if not entry.should_alert or not material_allowed:
        return _suppressed_route_decision(entry, warnings, material_reason=material_reason)

    if _looks_like_validated_hypothesis(entry):
        return _validated_hypothesis_route_decision(entry, cfg=cfg, warnings=warnings)

    if entry.relationship_type == "impact_hypothesis":
        return _unvalidated_impact_hypothesis_route_decision(entry, warnings)

    playbook_decision = _playbook_route_decision(entry, cfg=cfg, playbook=playbook, state=state, warnings=warnings)
    if playbook_decision is not None:
        return playbook_decision

    return _unrecognized_route_decision(entry, warnings)


def _disabled_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.STORE_ONLY,
        False,
        "Event Alpha router is disabled; retaining watchlist row as research evidence only.",
        warnings=warnings,
    )


def _quality_capped_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    playbook: str,
    state: str,
    warnings: list[str],
) -> EventAlphaRouteDecision | None:
    if not event_watchlist.state_is_quality_capped(entry):
        return None
    requested_state = event_watchlist.requested_state_value(entry)
    requested_route = _route_value_for_requested_state(requested_state, playbook)
    _, state_block = event_watchlist.quality_cap_watchlist_state(
        requested_state,
        _quality_for_entry(entry),
    )
    state_block = entry.quality_state_block_reason or state_block or "quality_state_capped"
    if state != event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value:
        warnings.append(f"quality_state_capped:{state_block}")
        return None
    route_block = _quality_gate_block_reason(_quality_for_entry(entry)) or state_block
    return _decision(
        entry,
        EventAlphaRoute.STORE_ONLY,
        False,
        "Quality route gate kept lifecycle-blocked row local-only: "
        f"{route_block}.",
        warnings=tuple(dict.fromkeys((*warnings, f"quality_gate_blocked:{route_block}"))),
        requested_route_before_quality_gate=requested_route,
        final_route_after_quality_gate=EventAlphaRoute.STORE_ONLY.value,
        quality_gate_block_reason=route_block,
        opportunity_level=entry.opportunity_level,
        opportunity_score_final=entry.opportunity_score_final,
        routing_score_used=entry.opportunity_score_final,
        routing_score_source="opportunity_score_final",
        routing_verdict_used=entry.opportunity_level,
    )


def _raw_or_terminal_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.STORE_ONLY,
        False,
        "Raw, expired, or invalidated watchlist state is stored only.",
        warnings=warnings,
    )


def _triggered_fade_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    playbook: str,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value:
        return _decision(
            entry,
            EventAlphaRoute.TRIGGERED_FADE_RESEARCH,
            True,
            "Proxy-fade playbook reached TRIGGERED_FADE from the deterministic event_fade engine.",
            lane=EventAlphaRouteLane.TRIGGERED_FADE,
            warnings=warnings,
        )
    warnings.append("non-proxy playbook cannot route triggered fade")
    return _decision(
        entry,
        EventAlphaRoute.LOCAL_REPORT,
        False,
        "Triggered state is retained for local review because the playbook is not proxy_fade.",
        warnings=warnings,
    )


def _suppressed_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
    *,
    material_reason: str | None,
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.SUPPRESS_DUPLICATE,
        False,
        material_reason or entry.suppressed_reason or "No meaningful state escalation since the previous observation.",
        warnings=warnings,
    )


def _validated_hypothesis_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    quality_block = _validated_hypothesis_digest_block_reason(entry, cfg)
    if quality_block:
        warnings.append(f"validated_hypothesis_digest_blocked:{quality_block}")
        return _decision(
            entry,
            EventAlphaRoute.STORE_ONLY,
            False,
            f"Validated impact hypothesis kept local-only: {quality_block}.",
            warnings=warnings,
        )
    route = _validated_hypothesis_route(entry)
    high_priority = route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    return _decision(
        entry,
        route,
        (
            cfg.instant_enabled
            if high_priority
            else cfg.daily_digest_enabled and cfg.validated_hypothesis_digest_enabled
        ),
        _validated_hypothesis_route_reason(entry),
        lane=EventAlphaRouteLane.INSTANT_ESCALATION
        if high_priority
        else EventAlphaRouteLane.DAILY_DIGEST,
        warnings=warnings,
    )


def _unvalidated_impact_hypothesis_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.STORE_ONLY,
        False,
        "Impact hypothesis rows require catalyst-link validation and a validated token identity before digest routing.",
        warnings=warnings,
    )


def _playbook_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
    playbook: str,
    state: str,
    warnings: list[str],
) -> EventAlphaRouteDecision | None:
    if _is_control_or_anomaly_playbook(playbook):
        return _control_or_anomaly_route_decision(entry, warnings)
    if playbook == event_playbooks.EventPlaybookType.INFRASTRUCTURE_MENTION.value:
        return _infrastructure_route_decision(entry, warnings)
    if playbook in _NON_FADE_RESEARCH_PLAYBOOKS:
        return _non_fade_research_route_decision(entry, cfg=cfg, state=state, warnings=warnings)
    if _is_higher_watchlist_state(state):
        return _higher_proxy_state_route_decision(entry, cfg=cfg, playbook=playbook, warnings=warnings)
    if _is_proxy_digest_state(state, playbook):
        return _proxy_digest_route_decision(entry, cfg=cfg, warnings=warnings)
    return None


def _control_or_anomaly_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.STORE_ONLY,
        False,
        "Control/anomaly playbooks are evidence only until catalyst and asset identity are validated.",
        warnings=warnings,
    )


def _infrastructure_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.LOCAL_REPORT,
        False,
        "Infrastructure playbooks may be reviewed locally but cannot enter research digest routing.",
        warnings=warnings,
    )


def _non_fade_research_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
    state: str,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    route = (
        EventAlphaRoute.HIGH_PRIORITY_RESEARCH
        if _is_higher_watchlist_state(state)
        else EventAlphaRoute.RESEARCH_DIGEST
    )
    high_priority = route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    return _decision(
        entry,
        route,
        cfg.instant_enabled if high_priority else cfg.daily_digest_enabled,
        "Non-fade event playbook produced a research-only state escalation.",
        lane=EventAlphaRouteLane.INSTANT_ESCALATION if high_priority else EventAlphaRouteLane.DAILY_DIGEST,
        warnings=warnings,
    )


def _higher_proxy_state_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
    playbook: str,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    route = (
        EventAlphaRoute.HIGH_PRIORITY_RESEARCH
        if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value
        else EventAlphaRoute.RESEARCH_DIGEST
    )
    high_priority = route == EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    return _decision(
        entry,
        route,
        cfg.instant_enabled if high_priority else cfg.daily_digest_enabled,
        "Proxy candidate escalated to a higher watchlist state.",
        lane=EventAlphaRouteLane.INSTANT_ESCALATION if high_priority else EventAlphaRouteLane.DAILY_DIGEST,
        warnings=warnings,
    )


def _proxy_digest_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.RESEARCH_DIGEST,
        cfg.daily_digest_enabled,
        "Proxy candidate produced a meaningful radar/watchlist escalation.",
        lane=EventAlphaRouteLane.DAILY_DIGEST,
        warnings=warnings,
    )


def _unrecognized_route_decision(
    entry: event_watchlist.EventWatchlistEntry,
    warnings: list[str],
) -> EventAlphaRouteDecision:
    return _decision(
        entry,
        EventAlphaRoute.LOCAL_REPORT,
        False,
        "Unrecognized playbook/state combination is kept in local research output only.",
        warnings=warnings,
    )


def _decision(
    entry: event_watchlist.EventWatchlistEntry,
    route: EventAlphaRoute,
    alertable: bool,
    reason: str,
    *,
    lane: EventAlphaRouteLane = EventAlphaRouteLane.LOCAL_ONLY,
    warnings: Iterable[str] = (),
    **kwargs: object,
) -> EventAlphaRouteDecision:
    return EventAlphaRouteDecision(
        entry=entry,
        route=route,
        alertable=alertable,
        reason=reason,
        lane=lane,
        warnings=tuple(warnings),
        **kwargs,
    )


def _is_control_or_anomaly_playbook(playbook: str) -> bool:
    return playbook in {
        event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
        event_playbooks.EventPlaybookType.AMBIGUOUS_CONTROL.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value,
    }


def _is_higher_watchlist_state(state: str) -> bool:
    return state in {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.ARMED.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
    }


def _is_proxy_digest_state(state: str, playbook: str) -> bool:
    return state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.RADAR.value,
    } and playbook in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }


def _apply_quality_gate(decision: EventAlphaRouteDecision) -> EventAlphaRouteDecision:
    """Downgrade alertable routes that conflict with final quality verdicts."""
    quality = _quality_for_entry(decision.entry)
    requested = decision.requested_route_before_quality_gate or decision.route.value
    score = _float_or_none(quality.get("opportunity_score_final"))
    level = str(quality.get("opportunity_level") or "").strip()
    base = replace(
        decision,
        requested_route_before_quality_gate=requested,
        final_route_after_quality_gate=decision.route.value,
        opportunity_level=level or None,
        opportunity_score_final=score,
        routing_score_used=score,
        routing_score_source="opportunity_score_final",
        routing_verdict_used=level or None,
    )
    if decision.route == EventAlphaRoute.TRIGGERED_FADE_RESEARCH:
        return base
    if not decision.alertable:
        return base
    block = _quality_gate_block_reason(quality)
    if block:
        return _quality_downgrade(base, block, level=level)
    capped = _quality_route_cap(base, level)
    if capped is not None:
        return capped
    return base


def _quality_downgrade(
    decision: EventAlphaRouteDecision,
    block: str,
    *,
    level: str,
) -> EventAlphaRouteDecision:
    route = EventAlphaRoute.LOCAL_REPORT if level == event_opportunity_verdict.OpportunityLevel.EXPLORATORY.value else EventAlphaRoute.STORE_ONLY
    return replace(
        decision,
        route=route,
        alertable=False,
        lane=EventAlphaRouteLane.LOCAL_ONLY,
        reason=f"Quality gate kept route local-only: {block}.",
        final_route_after_quality_gate=route.value,
        quality_gate_block_reason=block,
        warnings=tuple(dict.fromkeys((*decision.warnings, f"quality_gate_blocked:{block}"))),
    )


def _quality_route_cap(decision: EventAlphaRouteDecision, level: str) -> EventAlphaRouteDecision | None:
    requested = decision.route
    if level == event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value:
        if requested == EventAlphaRoute.HIGH_PRIORITY_RESEARCH:
            return replace(
                decision,
                route=EventAlphaRoute.RESEARCH_DIGEST,
                alertable=True,
                lane=EventAlphaRouteLane.DAILY_DIGEST,
                reason=decision.reason + " Quality gate capped route at validated digest.",
                final_route_after_quality_gate=EventAlphaRoute.RESEARCH_DIGEST.value,
                quality_gate_block_reason="opportunity_level_caps_high_priority:validated_digest",
                warnings=tuple(dict.fromkeys((*decision.warnings, "quality_gate_capped:validated_digest"))),
            )
        return None
    if level == event_opportunity_verdict.OpportunityLevel.WATCHLIST.value:
        if requested == EventAlphaRoute.HIGH_PRIORITY_RESEARCH:
            return replace(
                decision,
                route=EventAlphaRoute.RESEARCH_DIGEST,
                alertable=True,
                lane=EventAlphaRouteLane.DAILY_DIGEST,
                reason=decision.reason + " Quality gate capped route at watchlist/digest.",
                final_route_after_quality_gate=EventAlphaRoute.RESEARCH_DIGEST.value,
                quality_gate_block_reason="opportunity_level_caps_high_priority:watchlist",
                warnings=tuple(dict.fromkeys((*decision.warnings, "quality_gate_capped:watchlist"))),
            )
        return None
    if level == event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value:
        return None
    return None


def _quality_gate_block_reason(quality: Mapping[str, object]) -> str | None:
    level = str(quality.get("opportunity_level") or "").strip()
    score = _float_or_none(quality.get("opportunity_score_final"))
    text = _quality_gate_text(quality)
    if "source_noise" in text:
        return "source_noise_hard_gate"
    if "ticker_collision" in text or "word_collision" in text or "ticker_word_collision" in text:
        return "ticker_collision_hard_gate"
    if "publisher_source_name_not_asset_identity" in text or "identity_source_origin_rejected" in text:
        return "publisher_source_origin_identity_rejected"
    if str(quality.get("impact_path_type") or "") == "insufficient_data":
        return "impact_path_type_insufficient_data"
    if score is None or score <= 0:
        return "opportunity_score_final_zero"
    if str(quality.get("evidence_specificity") or "") == "insufficient_data":
        return "evidence_specificity_insufficient_data"
    if str(quality.get("source_class") or "") == "insufficient_data":
        return "source_class_insufficient_data"
    if str(quality.get("candidate_role") or "") == "unknown_with_reason":
        return "candidate_role_unknown_with_reason"
    if level == event_opportunity_verdict.OpportunityLevel.LOCAL_ONLY.value:
        return _normalize_quality_gate_block_reason(
            str(quality.get("why_local_only") or "opportunity_level_local_only"),
            quality,
        )
    if level == event_opportunity_verdict.OpportunityLevel.EXPLORATORY.value:
        return _normalize_quality_gate_block_reason(
            str(quality.get("why_not_watchlist") or "opportunity_level_exploratory"),
            quality,
        )
    if not level:
        return "opportunity_level_missing"
    return None


def _normalize_quality_gate_block_reason(reason: str, quality: Mapping[str, object]) -> str:
    if reason.strip().casefold() != "strong_market_confirmation":
        if reason.strip().casefold() == "impact_path":
            return "impact_path_not_strong_enough"
        if reason.strip().casefold() == "explained_token_impact_path":
            return "missing_direct_impact_path"
        return reason
    impact = str(quality.get("impact_path_type") or "").strip()
    strength = str(quality.get("impact_path_strength") or "").strip()
    role = str(quality.get("candidate_role") or "").strip()
    market_level = str(quality.get("market_confirmation_level") or "").strip()
    market_score = _float_or_none(quality.get("market_confirmation_score"))
    market_is_strong = market_level in {"strong", "confirmed"} or (market_score is not None and market_score >= 75)
    weak_context = (
        strength not in {"strong", "medium"}
        or impact in {"generic_cooccurrence_only", "macro_attention_only", "technology_risk", "market_structure_policy", "unknown", ""}
        or role in {"generic_mention", "macro_affected_asset", "unknown_with_reason", ""}
    )
    if market_is_strong and weak_context:
        return "weak_impact_path_despite_market_confirmation"
    if market_is_strong:
        return "impact_path_not_strong_enough"
    return "needs_strong_market_confirmation"


def _quality_for_entry(entry: event_watchlist.EventWatchlistEntry) -> dict[str, object]:
    row: dict[str, object] = {}
    for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
        value = getattr(entry, key, None)
        if value not in (None, "", [], {}, ()):
            row[key] = value
    components = dict(entry.latest_score_components or {})
    return event_alpha_quality_fields.ensure_quality_fields(row, components=components)


def _quality_gate_text(quality: Mapping[str, object]) -> str:
    values: list[object] = []
    for key in (
        "impact_path_type",
        "candidate_role",
        "evidence_specificity",
        "source_class",
        "why_local_only",
        "why_not_watchlist",
        "opportunity_verdict_reasons",
        "manual_verification_items",
        "upgrade_requirements",
        "downgrade_warnings",
        "warnings",
        "rejection_reasons",
    ):
        value = quality.get(key)
        if isinstance(value, (list, tuple, set)):
            values.extend(value)
        else:
            values.append(value)
    return " ".join(str(value or "") for value in values).casefold()


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
        "quality_state_upgraded",
        "cause_status_changed",
        "claim_confirmed",
        "claim_ruled_out",
        "incident_confidence_changed",
        "affected_asset_role_changed",
    }:
        allowed = True
    if "independent_source_confirmation" in reasons:
        if cfg.alert_on_new_independent_source:
            allowed = True
        else:
            blocked.append("independent source alerts disabled")
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
                requested_route_before_quality_gate=decision.requested_route_before_quality_gate,
                final_route_after_quality_gate=EventAlphaRoute.SUPPRESS_DUPLICATE.value,
                quality_gate_block_reason=decision.quality_gate_block_reason,
                opportunity_level=decision.opportunity_level,
                opportunity_score_final=decision.opportunity_score_final,
                routing_score_used=decision.routing_score_used,
                routing_score_source=decision.routing_score_source,
                routing_verdict_used=decision.routing_verdict_used,
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
                    requested_route_before_quality_gate=decision.requested_route_before_quality_gate,
                    final_route_after_quality_gate=EventAlphaRoute.SUPPRESS_DUPLICATE.value,
                    quality_gate_block_reason=decision.quality_gate_block_reason,
                    opportunity_level=decision.opportunity_level,
                    opportunity_score_final=decision.opportunity_score_final,
                    routing_score_used=decision.routing_score_used,
                    routing_score_source=decision.routing_score_source,
                    routing_verdict_used=decision.routing_verdict_used,
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
                        requested_route_before_quality_gate=decision.requested_route_before_quality_gate,
                        final_route_after_quality_gate=EventAlphaRoute.SUPPRESS_DUPLICATE.value,
                        quality_gate_block_reason=decision.quality_gate_block_reason,
                        opportunity_level=decision.opportunity_level,
                        opportunity_score_final=decision.opportunity_score_final,
                        routing_score_used=decision.routing_score_used,
                        routing_score_source=decision.routing_score_source,
                        routing_verdict_used=decision.routing_verdict_used,
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
                    requested_route_before_quality_gate=decision.requested_route_before_quality_gate,
                    final_route_after_quality_gate=EventAlphaRoute.SUPPRESS_DUPLICATE.value,
                    quality_gate_block_reason=decision.quality_gate_block_reason,
                    opportunity_level=decision.opportunity_level,
                    opportunity_score_final=decision.opportunity_score_final,
                    routing_score_used=decision.routing_score_used,
                    routing_score_source=decision.routing_score_source,
                    routing_verdict_used=decision.routing_verdict_used,
                ))
                continue
        out.append(decision)
    return out


def _is_validated_hypothesis_digest_entry(entry: event_watchlist.EventWatchlistEntry) -> bool:
    return _validated_hypothesis_digest_block_reason(entry, EventAlphaRouterConfig()) is None


def _looks_like_validated_hypothesis(entry: event_watchlist.EventWatchlistEntry) -> bool:
    if entry.relationship_type != "impact_hypothesis":
        return False
    if event_watchlist.final_state_value(entry) not in {
        event_watchlist.EventWatchlistState.RADAR.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
    }:
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
    if event_watchlist.final_state_value(entry) not in {
        event_watchlist.EventWatchlistState.RADAR.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
    }:
        return "not_validated_hypothesis_route_state"
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
            direct_override_score = max(75.0, float(cfg.validated_hypothesis_min_final_score) + 10.0)
            if not (_has_clear_direct_token_event(entry, components) and final_score >= direct_override_score):
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
    try:
        num = float(components.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        num = 0.0
    if num > 0:
        return num
    try:
        entry_num = float(entry.opportunity_score_final or 0.0)
    except (TypeError, ValueError):
        entry_num = 0.0
    if entry_num > 0:
        return entry_num
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
        event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value,
        event_watchlist.EventWatchlistState.INVALIDATED.value,
        event_watchlist.EventWatchlistState.EXPIRED.value,
    }


def _route_value_for_requested_state(state: str, playbook: str) -> str:
    if state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value
    if state in {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.ARMED.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
    }:
        return (
            EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
            if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value
            else EventAlphaRoute.RESEARCH_DIGEST.value
        )
    if state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.RADAR.value,
    }:
        return EventAlphaRoute.RESEARCH_DIGEST.value
    return EventAlphaRoute.STORE_ONLY.value


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


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value in (None, "", [], {}, ()):
        return None
    return str(value)


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
