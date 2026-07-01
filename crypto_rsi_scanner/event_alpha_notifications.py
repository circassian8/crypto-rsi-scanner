"""Day-1 notification helpers for Event Alpha research alerts.

This module owns delivery state only. It does not rank alerts, mutate
watchlist state, create trades, paper trade, or write normal RSI signal rows.
"""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
import re

from . import event_alpha_notification_delivery as delivery
from . import event_alpha_notification_sender as sender
from . import event_alpha_pipeline, event_alpha_router, event_artifact_paths, event_watchlist

LANE_DAILY_DIGEST = "daily_digest"
LANE_INSTANT_ESCALATION = "instant_escalation"
LANE_TRIGGERED_FADE = "triggered_fade"
LANE_RESEARCH_REVIEW_DIGEST = "research_review_digest"
LANE_EXPLORATORY_DIGEST = "exploratory_digest"
LANE_HEALTH_HEARTBEAT = "health_heartbeat"

LANES = (
    LANE_DAILY_DIGEST,
    LANE_INSTANT_ESCALATION,
    LANE_TRIGGERED_FADE,
    LANE_RESEARCH_REVIEW_DIGEST,
    LANE_EXPLORATORY_DIGEST,
    LANE_HEALTH_HEARTBEAT,
)

LAST_SENT_META_KEYS = {
    LANE_DAILY_DIGEST: "event_alpha_last_sent_daily_digest_at",
    LANE_INSTANT_ESCALATION: "event_alpha_last_sent_instant_escalation_at",
    LANE_TRIGGERED_FADE: "event_alpha_last_sent_triggered_fade_at",
    LANE_RESEARCH_REVIEW_DIGEST: "event_alpha_last_sent_research_review_digest_at",
    LANE_EXPLORATORY_DIGEST: "event_alpha_last_sent_exploratory_digest_at",
    LANE_HEALTH_HEARTBEAT: "event_alpha_last_sent_health_heartbeat_at",
}

NOTIFICATION_SCOPE_GLOBAL = "global"
NOTIFICATION_SCOPE_NAMESPACE = "namespace"
NOTIFICATION_SCOPE_PROFILE = "profile"
NOTIFICATION_SCOPES = (
    NOTIFICATION_SCOPE_GLOBAL,
    NOTIFICATION_SCOPE_NAMESPACE,
    NOTIFICATION_SCOPE_PROFILE,
)


@dataclass(frozen=True)
class EventAlphaNotificationConfig:
    enabled: bool = False
    mode: str = "research_only"
    notification_scope: str = NOTIFICATION_SCOPE_GLOBAL
    profile_name: str | None = None
    artifact_namespace: str | None = None
    daily_digest_cooldown_hours: float = 12.0
    daily_digest_max_items: int = 5
    instant_escalation_cooldown_hours: float = 1.0
    max_instant_per_day: int = 3
    health_heartbeat_enabled: bool = True
    health_heartbeat_cooldown_hours: float = 24.0
    triggered_fade_dedupe: bool = True
    exploratory_digest_enabled: bool = False
    exploratory_digest_max_items: int = 10
    exploratory_digest_min_score: int = 0
    exploratory_digest_cooldown_hours: float = 24.0
    exploratory_digest_include_rejection_reasons: bool = True
    exploratory_digest_include_raw_evidence: bool = True
    exploratory_digest_include_controls: bool = False
    research_review_digest_enabled: bool = False
    research_review_digest_max_items: int = 3
    research_review_digest_min_score: float = 60.0
    research_review_digest_cooldown_hours: float = 12.0
    research_review_digest_include_local_only: bool = False
    research_review_digest_include_sector: bool = False
    research_review_digest_send_with_alerts: bool = False
    allow_source_only_narrative_digest: bool = False
    quality_mode: str = "validated_digest"


@dataclass(frozen=True)
class EventAlphaExploratoryDigestItem:
    decision: event_alpha_router.EventAlphaRouteDecision
    rank_score: float
    why_included: tuple[str, ...] = ()
    what_to_verify: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaResearchReviewDigestItem:
    decision: event_alpha_router.EventAlphaRouteDecision
    rank_score: float
    why_included: tuple[str, ...] = ()
    why_not_alertable: tuple[str, ...] = ()
    what_would_upgrade: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaResearchReviewSkippedItem:
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    score: float
    rank_score: float
    skip_reason: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "coin_id": self.coin_id,
            "core_opportunity_id": self.core_opportunity_id,
            "score": self.score,
            "rank_score": self.rank_score,
            "skip_reason": self.skip_reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EventAlphaNotificationPlan:
    all_decisions: tuple[event_alpha_router.EventAlphaRouteDecision, ...] = ()
    decisions_by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = field(default_factory=dict)
    blocked_by_lane: dict[str, str] = field(default_factory=dict)
    heartbeat_due: bool = False
    heartbeat_reason: str = "heartbeat disabled"
    exploratory_items: tuple[EventAlphaExploratoryDigestItem, ...] = ()
    research_review_items: tuple[EventAlphaResearchReviewDigestItem, ...] = ()
    research_review_eligible_count: int = 0
    research_review_skipped_items: tuple[EventAlphaResearchReviewSkippedItem, ...] = ()
    cooldown_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    notification_scope: str = NOTIFICATION_SCOPE_GLOBAL
    scope_value: str = NOTIFICATION_SCOPE_GLOBAL
    migration_warnings: tuple[str, ...] = ()
    core_row_by_alert_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    canonicalization_warnings: tuple[str, ...] = ()

    @property
    def decision_count(self) -> int:
        return sum(len(items) for items in self.decisions_by_lane.values())

    @property
    def would_send_count(self) -> int:
        return (
            self.decision_count
            + len(self.research_review_items)
            + len(self.exploratory_items)
            + (1 if self.heartbeat_due else 0)
        )

    @property
    def lane_counts(self) -> dict[str, int]:
        counts = {lane: len(self.decisions_by_lane.get(lane, ())) for lane in LANES}
        counts[LANE_RESEARCH_REVIEW_DIGEST] = len(self.research_review_items)
        counts[LANE_EXPLORATORY_DIGEST] = len(self.exploratory_items)
        counts[LANE_HEALTH_HEARTBEAT] = 1 if self.heartbeat_due else 0
        return counts


@dataclass(frozen=True)
class DeliveryIdentity:
    notification_item_ids: tuple[str, ...]
    source_alert_ids: tuple[str, ...]
    core_opportunity_ids: tuple[str, ...] = ()
    canonical_symbols: tuple[str, ...] = ()
    canonical_coin_ids: tuple[str, ...] = ()
    canonical_card_paths: tuple[str, ...] = ()
    feedback_targets: tuple[str, ...] = ()
    requested_alert_id: str | None = None
    alert_id: str | None = None
    core_opportunity_id: str | None = None
    canonical_symbol: str | None = None
    canonical_coin_id: str | None = None
    canonical_card_path: str | None = None
    feedback_target: str | None = None
    identity_reconciled: bool = False
    identity_reconciliation_reason: str | None = None
    notification_preview_path: str | None = None
    notification_preview_relpath: str | None = None


SendFn = Callable[[str], bool | sender.NotificationSendAttemptResult | Mapping[str, Any]]


def build_notification_plan(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    storage: Any,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    include_health_heartbeat: bool = False,
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
) -> EventAlphaNotificationPlan:
    """Return lane-specific due decisions without mutating storage."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    raw_decisions = list(decisions)
    core_index = _core_index_for_decisions(raw_decisions, core_opportunity_rows)
    all_decisions, canonical_warnings = _canonicalize_decisions_for_notification(raw_decisions, core_index)
    quality_mode = _quality_mode(cfg.quality_mode)
    alertable = _filter_alertable_by_quality_mode(
        [decision for decision in all_decisions if event_alpha_router.alertable_after_quality_gate(decision)],
        quality_mode,
    )
    by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = {lane: [] for lane in LANES}
    blocked: dict[str, str] = {}

    daily_candidates = [decision for decision in alertable if _lane_for_decision(decision) == LANE_DAILY_DIGEST]
    daily_unconfirmed: list[event_alpha_router.EventAlphaRouteDecision] = []
    daily = _confirmed_daily_digest_decisions(
        daily_candidates,
        core_row_by_alert_id=core_index,
        cfg=cfg,
        unconfirmed=daily_unconfirmed,
    )
    daily = _dedupe_daily_digest_decisions(
        daily,
        core_row_by_alert_id=core_index,
        max_items=cfg.daily_digest_max_items,
    )
    if daily:
        due, reason = lane_due(storage, LANE_DAILY_DIGEST, cfg=cfg, now=observed)
        if due:
            by_lane[LANE_DAILY_DIGEST] = daily
        else:
            blocked[LANE_DAILY_DIGEST] = reason
    if daily_unconfirmed:
        blocked[LANE_DAILY_DIGEST] = (
            f"{len(daily_unconfirmed)} candidate(s) excluded from daily_digest: live confirmation missing"
        )

    instant = [decision for decision in alertable if _lane_for_decision(decision) == LANE_INSTANT_ESCALATION]
    if instant:
        due, reason = lane_due(storage, LANE_INSTANT_ESCALATION, cfg=cfg, now=observed)
        if due:
            remaining = max(
                0,
                cfg.max_instant_per_day - _sent_count_today(storage, LANE_INSTANT_ESCALATION, observed, cfg),
            )
            by_lane[LANE_INSTANT_ESCALATION] = instant[:remaining]
            if len(instant) > remaining:
                blocked[LANE_INSTANT_ESCALATION] = f"daily instant cap reached after {remaining} item(s)"
        else:
            blocked[LANE_INSTANT_ESCALATION] = reason

    triggered = [decision for decision in alertable if _lane_for_decision(decision) == LANE_TRIGGERED_FADE]
    if triggered:
        due_triggered: list[event_alpha_router.EventAlphaRouteDecision] = []
        blocked_count = 0
        for decision in triggered:
            due, reason = lane_due(
                storage,
                LANE_TRIGGERED_FADE,
                cfg=cfg,
                now=observed,
                alert_id=decision.alert_id,
            )
            if due:
                due_triggered.append(decision)
            else:
                blocked_count += 1
                blocked[LANE_TRIGGERED_FADE] = reason
        by_lane[LANE_TRIGGERED_FADE] = due_triggered
        if blocked_count and LANE_TRIGGERED_FADE not in blocked:
            blocked[LANE_TRIGGERED_FADE] = f"{blocked_count} triggered fade item(s) already sent"

    exploratory_items: tuple[EventAlphaExploratoryDigestItem, ...] = ()
    research_review_items: tuple[EventAlphaResearchReviewDigestItem, ...] = ()
    strict_due_count = sum(
        len(by_lane.get(lane, ()))
        for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST)
    )
    strict_core_ids = _strict_lane_core_ids(by_lane, core_index)
    if cfg.research_review_digest_enabled:
        selected, eligible_count, skipped_items = select_research_review_candidates_with_diagnostics(
            all_decisions,
            cfg=cfg,
            now=observed,
            excluded_core_ids=strict_core_ids,
            core_row_by_alert_id=core_index,
        )
        selected = _with_unconfirmed_daily_review_items(
            selected,
            daily_unconfirmed,
            cfg=cfg,
            excluded_core_ids=strict_core_ids,
            core_row_by_alert_id=core_index,
        )
        if selected:
            if strict_due_count and not cfg.research_review_digest_send_with_alerts:
                blocked[LANE_RESEARCH_REVIEW_DIGEST] = "strict alert lane has due candidates"
            else:
                due, reason = lane_due(storage, LANE_RESEARCH_REVIEW_DIGEST, cfg=cfg, now=observed)
                if due:
                    research_review_items = selected
                else:
                    blocked[LANE_RESEARCH_REVIEW_DIGEST] = reason
    else:
        eligible_count = 0
        skipped_items = ()

    if cfg.exploratory_digest_enabled and quality_mode == "exploratory_only":
        selected = select_exploratory_candidates(all_decisions, cfg=cfg, now=observed)
        if selected:
            due, reason = lane_due(storage, LANE_EXPLORATORY_DIGEST, cfg=cfg, now=observed)
            if due:
                exploratory_items = selected
            else:
                blocked[LANE_EXPLORATORY_DIGEST] = reason

    heartbeat_due = False
    heartbeat_reason = "heartbeat disabled"
    if include_health_heartbeat and cfg.health_heartbeat_enabled:
        heartbeat_due, heartbeat_reason = lane_due(storage, LANE_HEALTH_HEARTBEAT, cfg=cfg, now=observed)
    elif include_health_heartbeat:
        heartbeat_reason = "health heartbeat disabled"

    by_lane = {lane: items for lane, items in by_lane.items() if items}
    return EventAlphaNotificationPlan(
        all_decisions=tuple(all_decisions),
        decisions_by_lane=by_lane,
        blocked_by_lane=blocked,
        heartbeat_due=heartbeat_due,
        heartbeat_reason=heartbeat_reason,
        exploratory_items=exploratory_items,
        research_review_items=research_review_items,
        research_review_eligible_count=eligible_count,
        research_review_skipped_items=skipped_items,
        cooldown_status=cooldown_status_by_lane(storage, cfg=cfg, now=observed),
        notification_scope=_clean_scope(cfg.notification_scope),
        scope_value=_scope_value(cfg),
        migration_warnings=legacy_meta_warnings(storage, cfg),
        core_row_by_alert_id=core_index,
        canonicalization_warnings=canonical_warnings,
    )


def _confirmed_daily_digest_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
    cfg: EventAlphaNotificationConfig,
    unconfirmed: list[event_alpha_router.EventAlphaRouteDecision],
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    confirmed: list[event_alpha_router.EventAlphaRouteDecision] = []
    live_strict = _daily_digest_requires_live_confirmation(cfg)
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
        if not live_strict or _daily_digest_has_confirmation(decision, core, cfg=cfg):
            confirmed.append(decision)
        else:
            unconfirmed.append(decision)
    return confirmed


def _daily_digest_requires_live_confirmation(cfg: EventAlphaNotificationConfig) -> bool:
    scope = " ".join(
        str(value or "").casefold()
        for value in (cfg.profile_name, cfg.artifact_namespace, cfg.notification_scope)
    )
    if any(token in scope for token in ("fixture", "smoke", "e2e", "test")):
        return False
    if not str(cfg.artifact_namespace or "").strip() and "deep" not in scope and "rehearsal" not in scope:
        return False
    return any(token in scope for token in ("notify_llm_deep", "cryptopanic", "live", "burn_in", "rehearsal", "send"))


def _daily_digest_has_confirmation(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core: Mapping[str, Any],
    *,
    cfg: EventAlphaNotificationConfig | None = None,
) -> bool:
    cfg = cfg or EventAlphaNotificationConfig()
    entry = _decision_entry(decision)
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    merged: dict[str, Any] = {**components, **dict(core)}
    symbol = str(merged.get("symbol") or merged.get("validated_symbol") or getattr(entry, "symbol", "") or "").strip().upper()
    coin_id = str(merged.get("coin_id") or merged.get("validated_coin_id") or getattr(entry, "coin_id", "") or "").strip()
    if _research_review_is_sector(symbol, coin_id):
        return False
    accepted = _accepted_evidence_count(merged)
    acquisition_status = str(merged.get("evidence_acquisition_status") or "").strip()
    acquisition_confirmation = str(merged.get("acquisition_confirmation_status") or "").strip()
    source_class = str(merged.get("source_class") or merged.get("source_origin_class") or "").casefold()
    reason_values = (
        *_iter_values(merged.get("accepted_reason_codes") or merged.get("reason_codes")),
        *_iter_values(merged.get("accepted_reason_code_counts")),
    )
    reason_codes = " ".join(str(item) for item in reason_values)
    source_pack = str(merged.get("source_pack") or "").casefold()
    market_confirmation = str(
        merged.get("market_confirmation_level")
        or merged.get("market_confirmation")
        or merged.get("market_reaction_confirmation")
        or ""
    ).casefold()
    market_freshness = str(
        merged.get("market_context_freshness_status")
        or merged.get("core_market_freshness_status")
        or merged.get("market_freshness_status")
        or ""
    ).casefold()
    impact = str(merged.get("impact_path_type") or merged.get("effective_playbook_type") or "").casefold()
    official_or_structured = source_class in {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    provider_counts = _mapping_counts(merged.get("accepted_provider_counts"))
    cryptopanic_accepted = provider_counts.get("cryptopanic", 0)
    cryptopanic_tagged = "cryptopanic_currency_tag_match" in reason_codes.casefold()
    fresh_market = _has_digest_market_confirmation(merged)
    narrative_source_pack = source_pack in {
        "fan_sports_pack",
        "proxy_preipo_rwa_pack",
        "political_meme_pack",
    }
    if narrative_source_pack:
        if bool(getattr(cfg, "allow_source_only_narrative_digest", False)):
            return (accepted > 0 and acquisition_status == "accepted_evidence_found") or acquisition_confirmation == "confirms"
        if official_or_structured:
            return True
        if accepted >= 2:
            return True
        if cryptopanic_tagged and cryptopanic_accepted > 0 and fresh_market:
            return True
        return False
    if accepted > 0 and acquisition_status == "accepted_evidence_found":
        return True
    if acquisition_confirmation == "confirms":
        return True
    if official_or_structured:
        return True
    if "cryptopanic_currency_tag_match" in reason_codes.casefold() and source_class in {"cryptopanic_tagged", "crypto_news"}:
        return True
    if source_pack in {"listing_liquidity_pack", "perp_listing_squeeze_pack", "unlock_supply_pack"} and source_class.startswith("official"):
        return True
    fresh_market = market_confirmation not in {"", "none", "missing", "unknown", "insufficient_data"}
    fresh_context = market_freshness not in {"", "missing", "stale", "unknown"}
    generic = impact in {"", "insufficient_data", "generic_cooccurrence", "source_noise_control", "ambiguous_control"}
    return fresh_market and fresh_context and not generic


def _has_digest_market_confirmation(row: Mapping[str, Any]) -> bool:
    market = str(
        row.get("market_confirmation_level")
        or row.get("market_confirmation")
        or row.get("market_reaction_confirmation")
        or ""
    ).casefold()
    freshness = str(
        row.get("market_context_freshness_status")
        or row.get("core_market_freshness_status")
        or row.get("market_freshness_status")
        or ""
    ).casefold()
    if market in {"moderate", "strong", "confirmed", "fresh"} and freshness not in {"missing", "stale", "unknown"}:
        return True
    score = _float_or_none(row.get("market_confirmation_score") or row.get("market_move_volume") or row.get("market_score"))
    return score is not None and score >= 40 and freshness not in {"missing", "stale", "unknown"}


def _mapping_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw or 0)
        except (TypeError, ValueError):
            continue
        out[str(key).strip().casefold()] = max(0, count)
    return out


def _dedupe_daily_digest_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
    max_items: int,
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    grouped: list[event_alpha_router.EventAlphaRouteDecision] = []
    seen: set[tuple[str, str, str]] = set()
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
        key = _daily_digest_group_key(decision, core)
        if key in seen:
            continue
        seen.add(key)
        grouped.append(decision)
    limit = max(0, int(max_items or 0))
    return grouped[:limit] if limit else []


def _strict_lane_core_ids(
    by_lane: Mapping[str, Iterable[event_alpha_router.EventAlphaRouteDecision]],
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    out: set[str] = set()
    for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST):
        for decision in by_lane.get(lane, ()):
            core_id = _core_id_for_decision(decision, core_row_by_alert_id)
            if core_id:
                out.add(core_id)
    return out


def _core_id_for_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> str:
    core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
    entry = _decision_entry(decision)
    return str(
        core.get("core_opportunity_id")
        or getattr(entry, "core_opportunity_id", None)
        or ""
    ).strip()


def _core_row_is_research_alertable(core: Mapping[str, Any]) -> bool:
    if not core:
        return False
    route = str(core.get("final_route_after_quality_gate") or core.get("route") or "").strip()
    if event_alpha_router.route_value_is_alertable(route):
        return True
    level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
    return level in {"validated_digest", "watchlist", "high_priority"}


def _daily_digest_group_key(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core: Mapping[str, Any],
) -> tuple[str, str, str]:
    entry = _decision_entry(decision)
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or getattr(entry, "coin_id", "") or "").strip().casefold()
    if not coin_id:
        coin_id = str(core.get("symbol") or core.get("validated_symbol") or getattr(entry, "symbol", "") or "").strip().casefold()
    incident = str(
        core.get("incident_id")
        or core.get("canonical_incident_name")
        or core.get("event_family")
        or getattr(entry, "latest_event_name", "")
        or ""
    ).strip().casefold()
    impact = str(core.get("impact_path_type") or getattr(entry, "impact_path_type", "") or getattr(entry, "latest_effective_playbook_type", "") or "").strip().casefold()
    return (coin_id, incident, _impact_family(impact))


def _decision_entry(decision: object) -> object:
    return getattr(decision, "entry", decision)


def _impact_family(value: str) -> str:
    text = str(value or "").casefold()
    if "fan" in text or "sports" in text:
        return "fan_sports"
    if "proxy" in text or "rwa" in text or "preipo" in text or "pre_ipo" in text:
        return "proxy"
    if "listing" in text or "perp" in text:
        return "listing"
    if "unlock" in text or "supply" in text:
        return "supply"
    if "security" in text or "exploit" in text:
        return "security"
    return text or "unknown"


def _with_unconfirmed_daily_review_items(
    selected: tuple[EventAlphaResearchReviewDigestItem, ...],
    unconfirmed: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[EventAlphaResearchReviewDigestItem, ...]:
    if not unconfirmed:
        return selected
    items = list(selected)
    core_index = core_row_by_alert_id or {}
    seen = {item.decision.alert_id for item in items}
    seen_core_ids = {
        core_id
        for item in items
        for core_id in (_core_id_for_decision(item.decision, core_index),)
        if core_id
    }
    excluded = {str(item).strip() for item in excluded_core_ids if str(item).strip()}
    for decision in unconfirmed:
        if decision.alert_id in seen:
            continue
        core_id = _core_id_for_decision(decision, core_index)
        core = _core_row_for_decision(decision, core_index) or {}
        if core_id and (core_id in excluded or core_id in seen_core_ids):
            continue
        entry = _decision_entry(decision)
        components = dict(getattr(entry, "latest_score_components", {}) or {})
        score = _research_review_score(decision)
        if score < float(cfg.research_review_digest_min_score or 0.0):
            continue
        items.append(EventAlphaResearchReviewDigestItem(
            decision=decision,
            rank_score=score,
            why_included=("would be daily digest except live confirmation is missing",),
            why_not_alertable=tuple(_research_review_not_alertable_reasons(decision, components)) or (
                "live_confirmation_missing",
            ),
            what_would_upgrade=("accepted source-pack evidence or fresh market confirmation",),
        ))
        seen.add(decision.alert_id)
        if core_id:
            seen_core_ids.add(core_id)
    items.sort(
        key=lambda item: (
            item.rank_score,
            _research_review_score(item.decision),
            getattr(_decision_entry(item.decision), "last_seen_at", ""),
            getattr(_decision_entry(item.decision), "symbol", ""),
        ),
        reverse=True,
    )
    return tuple(items[: max(0, int(cfg.research_review_digest_max_items or 0))])


def _iter_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(value.values())
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def select_exploratory_candidates(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
) -> tuple[EventAlphaExploratoryDigestItem, ...]:
    """Pick low-confidence/suppressed rows for a separate operator-learning digest.

    This deliberately does not make the rows alertable. It only surfaces stored
    evidence for manual review during notification burn-in.
    """
    _ = now  # currently reserved for freshness/ranking extensions.
    if not cfg.exploratory_digest_enabled or cfg.exploratory_digest_max_items <= 0:
        return ()
    items: list[EventAlphaExploratoryDigestItem] = []
    for decision in decisions:
        if bool(getattr(decision, "alertable", False)) or event_alpha_router.alertable_after_quality_gate(decision):
            continue
        entry = decision.entry
        if _is_promoted_or_validated_exploratory(entry, decision):
            continue
        if (entry.symbol or entry.coin_id) == "":
            continue
        if not (entry.latest_source or entry.source_count):
            continue
        reason = _suppression_reason(decision)
        if not reason:
            continue
        if entry.latest_score < int(cfg.exploratory_digest_min_score or 0):
            continue
        if _is_exploratory_control(entry) and not cfg.exploratory_digest_include_controls:
            continue
        if _is_ambiguous_exploratory(entry) and not _ambiguous_has_learning_value(entry):
            continue
        rank, why = _exploratory_rank(entry)
        verify = _exploratory_verify_steps(entry, reason)
        items.append(EventAlphaExploratoryDigestItem(
            decision=decision,
            rank_score=rank,
            why_included=tuple(why),
            what_to_verify=tuple(verify),
        ))
    items.sort(
        key=lambda item: (
            item.rank_score,
            item.decision.entry.latest_score,
            item.decision.entry.last_seen_at,
            item.decision.entry.symbol,
        ),
        reverse=True,
    )
    return tuple(items[: max(0, int(cfg.exploratory_digest_max_items or 0))])


def select_research_review_candidates(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[EventAlphaResearchReviewDigestItem, ...]:
    """Pick near-miss/local research candidates without making them alertable."""
    selected, _eligible_count, _skipped = select_research_review_candidates_with_diagnostics(
        decisions,
        cfg=cfg,
        now=now,
        excluded_core_ids=excluded_core_ids,
        core_row_by_alert_id=core_row_by_alert_id,
    )
    return selected


def select_research_review_candidates_with_diagnostics(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[
    tuple[EventAlphaResearchReviewDigestItem, ...],
    int,
    tuple[EventAlphaResearchReviewSkippedItem, ...],
]:
    """Pick research-review rows plus explicit non-rendered candidate reasons."""
    _ = now
    if not cfg.research_review_digest_enabled or cfg.research_review_digest_max_items <= 0:
        return (), 0, ()
    min_score = float(cfg.research_review_digest_min_score or 0.0)
    items: list[EventAlphaResearchReviewDigestItem] = []
    skipped: list[EventAlphaResearchReviewSkippedItem] = []
    excluded = {str(item).strip() for item in excluded_core_ids if str(item).strip()}
    core_index = core_row_by_alert_id or {}
    seen_core_ids: set[str] = set()

    def add_skipped(
        decision: event_alpha_router.EventAlphaRouteDecision,
        reason: str,
        *,
        detail: str | None = None,
        rank_score: float | None = None,
    ) -> None:
        entry = decision.entry
        core = _core_row_for_decision(decision, core_index) or {}
        components = dict(getattr(entry, "latest_score_components", {}) or {})
        symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or components.get("validated_symbol") or "UNKNOWN")
        coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or components.get("validated_coin_id") or "unknown")
        skipped.append(EventAlphaResearchReviewSkippedItem(
            symbol=symbol,
            coin_id=coin_id,
            core_opportunity_id=_core_id_for_decision(decision, core_index),
            score=_research_review_score(decision),
            rank_score=float(rank_score if rank_score is not None else _research_review_score(decision)),
            skip_reason=reason,
            detail=detail,
        ))

    for decision in decisions:
        if bool(getattr(decision, "alertable", False)) or event_alpha_router.alertable_after_quality_gate(decision):
            continue
        core_id = _core_id_for_decision(decision, core_index)
        core = _core_row_for_decision(decision, core_index) or {}
        if core_id and (core_id in excluded or core_id in seen_core_ids):
            add_skipped(decision, "already_represented" if core_id in excluded else "duplicate_family")
            continue
        if _core_row_is_research_alertable(core):
            add_skipped(decision, "already_represented", detail="core opportunity already has a promoted route")
            continue
        entry = decision.entry
        components = dict(getattr(entry, "latest_score_components", {}) or {})
        symbol = str(getattr(entry, "symbol", "") or components.get("validated_symbol") or "").strip()
        coin_id = str(getattr(entry, "coin_id", "") or components.get("validated_coin_id") or "").strip()
        if not symbol or not coin_id:
            add_skipped(decision, "hard_gated", detail="missing validated asset identity")
            continue
        if _research_review_is_sector(symbol, coin_id) and not cfg.research_review_digest_include_sector:
            add_skipped(decision, "hard_gated", detail="sector-only candidate excluded from review digest")
            continue
        level = _research_review_level(decision)
        if level == "local_only" and not cfg.research_review_digest_include_local_only:
            add_skipped(decision, "quality_blocked", detail="local-only candidates are hidden by digest config")
            continue
        if level not in {"exploratory", "local_only"}:
            add_skipped(decision, "quality_blocked", detail=f"level={level or 'unknown'}")
            continue
        score = _research_review_score(decision)
        if score < min_score:
            add_skipped(decision, "lower_rank", detail=f"score below min {min_score:g}")
            continue
        hard_gate = _research_review_hard_gate_reason(decision)
        if hard_gate:
            add_skipped(decision, "hard_gated", detail=hard_gate)
            continue
        rank, why = _research_review_rank(entry, components, score)
        why_not = _research_review_not_alertable_reasons(decision, components)
        upgrade = _research_review_upgrade_steps(entry, decision, components)
        items.append(
            EventAlphaResearchReviewDigestItem(
                decision=decision,
                rank_score=rank,
                why_included=tuple(why),
                why_not_alertable=tuple(why_not),
                what_would_upgrade=tuple(upgrade),
            )
        )
        if core_id:
            seen_core_ids.add(core_id)
    items.sort(
        key=lambda item: (
            item.rank_score,
            _research_review_score(item.decision),
            item.decision.entry.last_seen_at,
            item.decision.entry.symbol,
        ),
        reverse=True,
    )
    max_items = max(0, int(cfg.research_review_digest_max_items or 0))
    selected = tuple(items[:max_items])
    for item in items[max_items:]:
        skipped.append(EventAlphaResearchReviewSkippedItem(
            symbol=str(item.decision.entry.symbol or "UNKNOWN"),
            coin_id=str(item.decision.entry.coin_id or "unknown"),
            core_opportunity_id=_core_id_for_decision(item.decision, core_index),
            score=_research_review_score(item.decision),
            rank_score=item.rank_score,
            skip_reason="max_items",
            detail=f"ranked below top {max_items}",
        ))
    return selected, len(items), tuple(skipped)


def _is_promoted_or_validated_exploratory(
    entry: event_watchlist.EventWatchlistEntry,
    decision: event_alpha_router.EventAlphaRouteDecision,
) -> bool:
    components = dict(entry.latest_score_components or {})
    level = str(components.get("opportunity_level") or getattr(decision, "opportunity_level", None) or "")
    route = event_alpha_router.final_route_value(decision)
    state = event_watchlist.final_state_value(entry)
    validation_stage = str(components.get("validation_stage") or "")
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    if route and event_alpha_router.route_value_is_alertable(route):
        return True
    if state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }:
        return True
    return validation_stage in {"impact_path_validated", "market_confirmed", "promoted_to_radar"} and level not in {
        "local_only",
        "exploratory",
        "",
    }


def _quality_mode(value: str | None) -> str:
    mode = str(value or "validated_digest").strip().lower()
    if mode in {"exploratory_only", "validated_digest", "high_quality_only"}:
        return mode
    return "validated_digest"


def _filter_alertable_by_quality_mode(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    mode: str,
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    """Apply notification-level quality gates without changing routing decisions."""
    if mode == "exploratory_only":
        return [
            decision for decision in decisions
            if _route_value(decision) in {"", event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value}
        ]
    if mode == "high_quality_only":
        return [
            decision for decision in decisions
            if _route_value(decision) in {
                "",
                event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
                event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
            }
        ]
    return [
        decision for decision in decisions
        if _route_value(decision) in {
            "",
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }
    ]


def _route_value(decision: object) -> str:
    return event_alpha_router.final_route_value(decision)


def _research_review_level(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    for key in ("final_opportunity_level", "opportunity_level", "opportunity_verdict"):
        value = str(components.get(key) or "").strip()
        if value:
            return value
    return str(
        getattr(decision, "opportunity_level", None)
        or getattr(entry, "opportunity_level", None)
        or ""
    ).strip()


def _research_review_score(decision: event_alpha_router.EventAlphaRouteDecision) -> float:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    for value in (
        getattr(decision, "opportunity_score_final", None),
        components.get("final_opportunity_score"),
        components.get("opportunity_score_final"),
        getattr(entry, "opportunity_score_final", None),
        getattr(entry, "latest_score", None),
    ):
        parsed = _float_or_none(value)
        if parsed is not None:
            return parsed
    return 0.0


def _research_review_is_sector(symbol: object, coin_id: object) -> bool:
    symbol_text = str(symbol or "").strip().upper()
    coin_text = str(coin_id or "").strip().casefold()
    return symbol_text == "SECTOR" or coin_text.startswith("sector") or coin_text in {
        "sports_fan_proxy",
        "rwa_preipo_proxy",
        "ai_ipo_proxy",
        "market_anomaly",
    }


def _research_review_hard_gate_reason(decision: event_alpha_router.EventAlphaRouteDecision) -> str | None:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            getattr(entry, "latest_playbook_type", None),
            getattr(entry, "latest_rule_playbook_type", None),
            getattr(entry, "latest_effective_playbook_type", None),
            getattr(entry, "relationship_type", None),
            getattr(entry, "latest_llm_asset_role", None),
            getattr(entry, "candidate_role", None),
            getattr(entry, "impact_path_type", None),
            components.get("candidate_role"),
            components.get("asset_role"),
            components.get("llm_asset_role"),
            components.get("relationship_type"),
            components.get("impact_path_type"),
            components.get("impact_path_reason"),
            components.get("snapshot_class"),
            components.get("row_classification"),
            getattr(decision, "quality_gate_block_reason", None),
            getattr(decision, "reason", None),
            getattr(entry, "suppressed_reason", None),
        )
    )
    blockers = {
        "source_noise": "source_noise",
        "ticker_word_collision": "ticker_collision",
        "ticker_collision": "ticker_collision",
        "word_collision": "ticker_collision",
        "generic_cooccurrence_only": "generic_cooccurrence_only",
        "source_noise_control": "source_noise_control",
        "ambiguous_control": "ambiguous_control",
        "diagnostic_support": "diagnostic_support",
        "support_row": "support_row",
    }
    for token, reason in blockers.items():
        if token in fields:
            return reason
    if str(components.get("is_diagnostic_snapshot") or "").strip().casefold() in {"1", "true", "yes"}:
        return "diagnostic_snapshot"
    return None


def _research_review_rank(
    entry: Any,
    components: Mapping[str, Any],
    score: float,
) -> tuple[float, list[str]]:
    market = max(
        _component_score(components, "market_confirmation_score"),
        _component_score(components, "market_move_volume"),
    )
    source_quality = max(
        _component_score(components, "evidence_quality_score"),
        _component_score(components, "source_quality"),
    )
    freshness = _component_score(components, "novelty_freshness")
    cluster = _component_score(components, "cluster_confidence")
    rank = score + 0.35 * market + 0.25 * source_quality + 0.15 * freshness + 0.15 * cluster
    reasons: list[str] = []
    if score:
        reasons.append(f"near-miss score {score:g}")
    if market >= 25:
        reasons.append(f"market confirmation {market:g}")
    if source_quality >= 40:
        reasons.append(f"source quality {source_quality:g}")
    if getattr(entry, "external_asset", None) or getattr(entry, "event_time", None):
        reasons.append("has catalyst context")
    if cluster >= 40:
        reasons.append(f"cluster confidence {cluster:g}")
    if freshness >= 40:
        reasons.append("fresh opportunity")
    if not reasons:
        reasons.append("selected for manual research review")
    return rank, reasons


def _research_review_not_alertable_reasons(
    decision: event_alpha_router.EventAlphaRouteDecision,
    components: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for key in (
        "why_not_promoted",
        "quality_gate_block_reason",
        "why_not_watchlist",
        "why_local_only",
        "live_confirmation_reason",
        "no_upgrade_reason",
    ):
        value = components.get(key)
        if value:
            reasons.extend(_as_list(value))
    if getattr(decision, "quality_gate_block_reason", None):
        reasons.append(str(decision.quality_gate_block_reason))
    if getattr(decision.entry, "suppressed_reason", None):
        reasons.append(str(decision.entry.suppressed_reason))
    if getattr(decision, "reason", None):
        reasons.append(str(decision.reason))
    cleaned = [_human_reason(item) for item in reasons if str(item or "").strip()]
    if not cleaned:
        cleaned.append("missing confirmation for strict alert lanes")
    return list(dict.fromkeys(cleaned))[:3]


def _research_review_upgrade_steps(
    entry: Any,
    decision: event_alpha_router.EventAlphaRouteDecision,
    components: Mapping[str, Any],
) -> list[str]:
    steps: list[str] = []
    for key in ("what_would_upgrade", "upgrade_requirements", "manual_verification_items"):
        steps.extend(str(item) for item in _as_list(components.get(key)) if str(item or "").strip())
    if not steps:
        steps.extend(_exploratory_verify_steps(entry, _suppression_reason(decision)))
    return list(dict.fromkeys(step.replace("_", " ") for step in steps if step))[:3]


def format_research_review_telegram_digest(
    items: Iterable[EventAlphaResearchReviewDigestItem],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
    cfg: EventAlphaNotificationConfig | None = None,
    eligible_count: int | None = None,
    skipped_items: Iterable[EventAlphaResearchReviewSkippedItem] = (),
) -> str:
    """Render near-miss research-review candidates for Telegram burn-in."""
    cfg = cfg or EventAlphaNotificationConfig()
    _ = cfg  # Kept for API compatibility; all review items are rendered.
    keep = list(items)
    skipped = list(skipped_items)
    lines = [
        "<b>Event Alpha Research Review</b>",
        "<i>Not alertable. Missing confirmation. Not a trade signal.</i>",
        f"Profile: {_esc(profile or 'unknown')}",
        f"Items: {len(keep)}",
        f"Eligible candidates: {int(eligible_count if eligible_count is not None else len(keep))}",
        f"Skipped candidates: {len(skipped)}",
    ]
    if not keep:
        lines.append("No research-review candidates.")
        return "\n".join(lines)
    displayed = 0
    for item in keep:
        decision = item.decision
        entry = decision.entry
        core = _core_row_for_decision(decision, core_row_by_alert_id or {}) or {}
        level = _human_level(_research_review_level(decision))
        score = _research_review_score(decision)
        card_label = _telegram_card_basename(decision, card_path_by_alert_id, core=core)
        feedback_target = _telegram_feedback_target(decision, core=core)
        symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or "UNKNOWN")
        coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or "unknown")
        lane = str(core.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
        market_state = str(core.get("market_state_class") or core.get("market_state") or "unknown")
        block = [
            "",
            f"{displayed + 1}. <b>{_esc(symbol)} / {_esc(coin_id)}</b>",
            f"   Level: {_esc(level)} · Score: {_esc(f'{score:g}')}",
            f"   Opportunity: {_esc(_human_reason(lane))} · Market: {_esc(_human_reason(market_state))}",
            f"   Catalyst: {_esc(_candidate_catalyst_text(entry))}",
            f"   Impact path: {_esc(_human_playbook(entry.impact_path_type or entry.latest_effective_playbook_type or entry.latest_playbook_type or entry.relationship_type))}",
            f"   Why surfaced: {_esc(_human_why(item.why_included))}",
            f"   Why not alertable: {_esc(_human_why_not_alertable(item.why_not_alertable))}",
            f"   What would upgrade: {_esc(_human_check_next(item.what_would_upgrade))}",
            f"   Card: {_esc(card_label)}",
            f"   Feedback target: {_esc(feedback_target)}",
        ]
        lines.extend(block)
        displayed += 1
    lines.append("")
    if skipped:
        lines.append("<b>Skipped candidates</b>")
        for row in skipped[:10]:
            label = f"{row.symbol} / {row.coin_id}"
            detail = f" · {row.detail}" if row.detail else ""
            lines.append(
                f"- {_esc(label)}: {_esc(row.skip_reason)}{_esc(detail)}"
            )
        if len(skipped) > 10:
            lines.append(f"- +{len(skipped) - 10} more skipped candidates in local artifacts/inbox.")
        lines.append("")
    lines.append("Research cards and feedback commands are available in local artifacts/inbox.")
    return "\n".join(lines)


def _research_review_channel_summary(plan: EventAlphaNotificationPlan) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for item in plan.research_review_skipped_items:
        reason = str(item.skip_reason or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "rendered_candidate_count": len(plan.research_review_items),
        "eligible_candidate_count": int(plan.research_review_eligible_count or 0),
        "skipped_candidate_count": len(plan.research_review_skipped_items),
        "skip_reason_counts": dict(sorted(reason_counts.items())),
        "skipped_candidates": [item.to_dict() for item in plan.research_review_skipped_items[:20]],
    }


def write_notification_plan_preview(
    plan: EventAlphaNotificationPlan,
    *,
    writer: "_DeliveryWriter",
    profile: str | None,
    cfg: EventAlphaNotificationConfig,
    pipeline_result: Any | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    status: str | None = None,
    send_guard_status: str | None = None,
) -> None:
    """Write a full read-only preview for every due lane in ``plan``."""

    card_map = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    wrote_section = False
    section_status = status or "would_send"
    for lane in (
        LANE_TRIGGERED_FADE,
        LANE_INSTANT_ESCALATION,
        LANE_DAILY_DIGEST,
        LANE_RESEARCH_REVIEW_DIGEST,
        LANE_EXPLORATORY_DIGEST,
    ):
        research_review = lane == LANE_RESEARCH_REVIEW_DIGEST
        exploratory = lane == LANE_EXPLORATORY_DIGEST
        if research_review:
            items = list(plan.research_review_items)
        else:
            items = list(plan.exploratory_items if exploratory else plan.decisions_by_lane.get(lane, []))
        if not items:
            continue
        if research_review:
            message = format_research_review_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                cfg=cfg,
                eligible_count=plan.research_review_eligible_count,
                skipped_items=plan.research_review_skipped_items,
            )
            identity = _delivery_identity_for_decisions(
                [item.decision for item in items],
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path,
            )
            route_label = "RESEARCH_REVIEW_DIGEST"
        elif exploratory:
            message = format_exploratory_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                cfg=cfg,
            )
            identity = _delivery_identity_for_decisions(
                [item.decision for item in items],
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path,
            )
            route_label = "EXPLORATORY_DIGEST"
        else:
            message = format_core_opportunity_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                pipeline_result=pipeline_result,
                max_items=cfg.daily_digest_max_items if lane == LANE_DAILY_DIGEST else None,
            )
            identity = _delivery_identity_for_decisions(
                items,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path,
            )
            route_label = _route_label(items)
        writer.write_preview(
            message=message,
            lane=lane,
            route=route_label,
            identity=identity,
            would_send=True,
            sent=False,
            status=section_status,
        )
        wrote_section = True

    if plan.heartbeat_due:
        heartbeat_identity = DeliveryIdentity(
            notification_item_ids=("heartbeat",),
            source_alert_ids=("heartbeat",),
            requested_alert_id="heartbeat",
            alert_id="heartbeat",
            identity_reconciled=False,
            identity_reconciliation_reason="heartbeat",
            notification_preview_path=str(writer.preview_path),
            notification_preview_relpath=delivery.notification_preview_relpath_for_path(writer.preview_path),
        )
        writer.write_preview(
            message=format_health_heartbeat(
                profile=profile,
                result=_notification_preview_result(
                    pipeline_result,
                    plan=plan,
                    delivered_by_lane={lane: 0 for lane in LANES},
                ),
                now=writer.now,
                send_guard_status=send_guard_status,
            ),
            lane=LANE_HEALTH_HEARTBEAT,
            route="HEALTH_HEARTBEAT",
            identity=heartbeat_identity,
            would_send=True,
            sent=False,
            status=section_status,
        )
        wrote_section = True

    if not wrote_section:
        reason = "; ".join(plan.blocked_by_lane.values()) or plan.heartbeat_reason or "no due notifications"
        writer.write_no_digest_preview(
            profile=profile,
            pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=reason),
            reason=reason,
        )


def format_exploratory_telegram_digest(
    items: Iterable[EventAlphaExploratoryDigestItem],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    cfg: EventAlphaNotificationConfig | None = None,
) -> str:
    """Render low-confidence Event Alpha evidence for Telegram burn-in review."""
    cfg = cfg or EventAlphaNotificationConfig()
    _ = card_path_by_alert_id  # internal paths stay in artifacts/inbox, not Telegram.
    _ = cfg  # Kept for API compatibility; all exploratory items are rendered.
    keep = list(items)
    lines = [
        "<b>🟡 Exploratory Event Alpha Digest</b>",
        "<i>Low-confidence research leads — not trade signals</i>",
        f"Profile: {_esc(profile or 'unknown')}",
        f"Items: {len(keep)}",
        "Research-only / DAY-1 UNVALIDATED. No trades, paper trades, live RSI rows, execution, or TRIGGERED_FADE changes.",
    ]
    if not keep:
        lines.append("No exploratory candidates.")
        return "\n".join(lines)
    footer = "Research cards and feedback commands are available in local artifacts/inbox."
    displayed = 0
    for item in keep:
        decision = item.decision
        entry = decision.entry
        block = [
            "",
            f"{displayed + 1}. <b>{_esc(entry.symbol or entry.coin_id or 'UNKNOWN')} / {_esc(_human_asset_name(entry.coin_id))}</b>",
            f"   Move: {_esc(_move_summary(entry.latest_market_snapshot))}",
            f"   Volume/Mcap: {_esc(_volume_mcap_summary(entry.latest_market_snapshot))}",
            f"   Playbook: {_esc(_human_playbook(entry.latest_playbook_type or entry.latest_effective_playbook_type or entry.relationship_type))}",
            f"   Why surfaced: {_esc(_human_why(item.why_included))}",
            f"   Status: {_esc(_human_status(entry.state, entry.latest_tier, _suppression_reason(decision)))}",
            f"   Check next: {_esc(_human_check_next(item.what_to_verify))}",
            f"   Risk: {_esc(_human_risk(entry, decision))}",
        ]
        lines.extend(block)
        displayed += 1
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def lane_due(
    storage: Any,
    lane: str,
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime,
    alert_id: str | None = None,
) -> tuple[bool, str]:
    """Check one lane's send state using lane-specific meta keys."""
    lane_key = _clean_lane(lane)
    if lane_key == LANE_TRIGGERED_FADE and cfg.triggered_fade_dedupe and alert_id:
        if storage.get_meta(_triggered_alert_meta_key(alert_id, cfg)):
            return False, f"triggered fade already sent for {alert_id}"
        return True, "due"
    if lane_key == LANE_INSTANT_ESCALATION:
        sent_today = _sent_count_today(storage, lane_key, now, cfg)
        if cfg.max_instant_per_day >= 0 and sent_today >= cfg.max_instant_per_day:
            return False, f"daily instant cap reached ({cfg.max_instant_per_day})"
    cooldown = _cooldown_hours(lane_key, cfg)
    if cooldown <= 0:
        return True, "due"
    last_raw = storage.get_meta(_last_sent_meta_key(lane_key, cfg))
    last = _parse_iso(last_raw)
    if last is None:
        return True, "due"
    elapsed = (now - last).total_seconds() / 3600.0
    if elapsed < cooldown:
        return False, f"{lane_key} cooldown active for {cooldown:g}h"
    return True, "due"


def cooldown_status_by_lane(
    storage: Any,
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    observed = _as_utc(now or datetime.now(timezone.utc))
    rows: dict[str, dict[str, Any]] = {}
    for lane in LANES:
        due, reason = lane_due(storage, lane, cfg=cfg, now=observed)
        legacy_key = LAST_SENT_META_KEYS[lane]
        rows[lane] = {
            "due": due,
            "reason": reason,
            "last_sent_at": storage.get_meta(_last_sent_meta_key(lane, cfg)),
            "sent_today": _sent_count_today(storage, lane, observed, cfg),
            "meta_key": _last_sent_meta_key(lane, cfg),
            "count_meta_key": _count_meta_key(lane, observed, cfg),
            "legacy_meta_key": legacy_key,
            "legacy_last_sent_at": storage.get_meta(legacy_key),
        }
    return rows


def record_lane_sent(
    storage: Any,
    lane: str,
    *,
    item_count: int,
    now: datetime,
    alert_ids: Iterable[str] = (),
    cfg: EventAlphaNotificationConfig | None = None,
) -> None:
    cfg = cfg or EventAlphaNotificationConfig()
    lane_key = _clean_lane(lane)
    storage.set_meta(_last_sent_meta_key(lane_key, cfg), now.isoformat())
    count_key = _count_meta_key(lane_key, now, cfg)
    storage.set_meta(count_key, str(_sent_count_today(storage, lane_key, now, cfg) + max(0, int(item_count or 0))))
    if lane_key == LANE_TRIGGERED_FADE:
        for alert_id in alert_ids:
            storage.set_meta(_triggered_alert_meta_key(alert_id, cfg), now.isoformat())


def send_notifications(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    storage: Any,
    cfg: EventAlphaNotificationConfig,
    send_fn: SendFn,
    now: datetime | None = None,
    profile: str | None = None,
    pipeline_result: Any | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
    include_health_heartbeat: bool = False,
    delivery_cfg: delivery.NotificationDeliveryConfig | None = None,
    run_id: str | None = None,
    namespace: str | None = None,
    pause_state: Any | None = None,
) -> event_alpha_pipeline.EventAlphaSendResult:
    """Send lane-specific Event Alpha notifications when guards are satisfied.

    When ``delivery_cfg`` is provided, each lane send is recorded in the
    idempotent delivery ledger and skipped if identical content was already
    delivered within the dedupe window. Cooldown is only marked after a real
    delivery, never after a dedupe-skip or a failed send.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    plan = build_notification_plan(
        decisions,
        storage=storage,
        cfg=cfg,
        now=observed,
        include_health_heartbeat=include_health_heartbeat,
        core_opportunity_rows=core_opportunity_rows,
    )
    lane_attempts = plan.lane_counts
    would_send = plan.would_send_count
    card_map = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    writer = (
        _DeliveryWriter(delivery_cfg, run_id=run_id, profile=profile, namespace=namespace, now=observed)
        if delivery_cfg is not None
        else None
    )

    def _result(**kwargs: Any) -> event_alpha_pipeline.EventAlphaSendResult:
        counts = writer.counts if writer else {}
        research_review_sent = kwargs.pop(
            "research_review_digest_sent",
            int((kwargs.get("lane_items_delivered") or {}).get(LANE_RESEARCH_REVIEW_DIGEST, 0)),
        )
        return event_alpha_pipeline.EventAlphaSendResult(
            heartbeat_due=plan.heartbeat_due,
            cooldown_blocks=dict(plan.blocked_by_lane),
            notification_scope=plan.notification_scope,
            notification_scope_value=plan.scope_value,
            delivery_records_written=int(counts.get("records", 0)),
            deliveries_delivered=int(counts.get(delivery.STATE_DELIVERED, 0)),
            deliveries_partial_delivered=int(counts.get(delivery.STATE_PARTIAL_DELIVERED, 0)),
            deliveries_failed=int(counts.get(delivery.STATE_FAILED, 0)),
            deliveries_skipped_duplicate=int(counts.get(delivery.STATE_SKIPPED_DUPLICATE, 0)),
            deliveries_skipped_in_flight=int(counts.get(delivery.STATE_SKIPPED_IN_FLIGHT, 0)),
            deliveries_blocked=int(counts.get(delivery.STATE_BLOCKED, 0)),
            research_review_digest_enabled=bool(cfg.research_review_digest_enabled),
            research_review_digest_candidates=len(plan.research_review_items),
            research_review_digest_would_send=int(lane_attempts.get(LANE_RESEARCH_REVIEW_DIGEST, 0)),
            research_review_digest_sent=int(research_review_sent or 0),
            research_review_digest_block_reason=plan.blocked_by_lane.get(LANE_RESEARCH_REVIEW_DIGEST),
            **kwargs,
        )

    if not cfg.enabled or cfg.mode != "research_only":
        block_reason = "event alerts disabled" if not cfg.enabled else "event alert mode is not research_only"
        if writer:
            writer.record_blocked(
                plan,
                profile=profile,
                card_map=card_map,
                reason=block_reason,
                pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=block_reason),
            )
            if not writer.preview_sections:
                writer.write_no_digest_preview(
                    profile=profile,
                    pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=block_reason),
                    reason=block_reason,
                )
        return _result(
            requested=True,
            attempted=False,
            items_attempted=would_send,
            items_delivered=0,
            block_reason=block_reason,
            lane_items_attempted=lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=would_send,
        )
    if bool(getattr(pause_state, "paused", False)):
        reason = str(getattr(pause_state, "reason", "") or "notifications paused")
        block_reason = f"notifications paused: {reason}"
        if writer:
            writer.record_blocked(
                plan,
                profile=profile,
                card_map=card_map,
                reason=block_reason,
                error_class="notifications_paused",
                pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=block_reason),
            )
            if not writer.preview_sections:
                writer.write_no_digest_preview(
                    profile=profile,
                    pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=block_reason),
                    reason=block_reason,
                )
        return _result(
            requested=True,
            attempted=False,
            items_attempted=would_send,
            items_delivered=0,
            block_reason=block_reason,
            lane_items_attempted=lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=would_send,
        )
    if would_send <= 0:
        reason = "; ".join(plan.blocked_by_lane.values()) or plan.heartbeat_reason or "no due notifications"
        if writer:
            writer.write_no_digest_preview(
                profile=profile,
                pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=reason),
                reason=reason,
            )
        return _result(
            requested=True,
            attempted=False,
            items_attempted=0,
            items_delivered=0,
            block_reason=reason,
            lane_items_attempted=lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=0,
        )

    delivered_by_lane = {lane: 0 for lane in LANES}
    attempted = False
    block_reasons: list[str] = []
    for lane in (
        LANE_TRIGGERED_FADE,
        LANE_INSTANT_ESCALATION,
        LANE_DAILY_DIGEST,
        LANE_RESEARCH_REVIEW_DIGEST,
        LANE_EXPLORATORY_DIGEST,
    ):
        research_review = lane == LANE_RESEARCH_REVIEW_DIGEST
        exploratory = lane == LANE_EXPLORATORY_DIGEST
        if research_review:
            items = list(plan.research_review_items)
        else:
            items = list(plan.exploratory_items if exploratory else plan.decisions_by_lane.get(lane, []))
        if not items:
            continue
        if research_review:
            message = format_research_review_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                cfg=cfg,
                eligible_count=plan.research_review_eligible_count,
                skipped_items=plan.research_review_skipped_items,
            )
            identity = _delivery_identity_for_decisions(
                [item.decision for item in items],
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path if writer else None,
            )
            alert_ids = list(identity.notification_item_ids)
            route_label = "RESEARCH_REVIEW_DIGEST"
        elif exploratory:
            message = format_exploratory_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                cfg=cfg,
            )
            identity = _delivery_identity_for_decisions(
                [item.decision for item in items],
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path if writer else None,
            )
            alert_ids = list(identity.notification_item_ids)
            route_label = "EXPLORATORY_DIGEST"
        else:
            message = format_core_opportunity_telegram_digest(
                items,
                profile=profile,
                card_path_by_alert_id=card_map,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                pipeline_result=pipeline_result,
                max_items=cfg.daily_digest_max_items if lane == LANE_DAILY_DIGEST else None,
            )
            identity = _delivery_identity_for_decisions(
                items,
                core_row_by_alert_id=plan.core_row_by_alert_id,
                card_path_by_alert_id=card_map,
                lane=lane,
                preview_path=writer.preview_path if writer else None,
            )
            alert_ids = list(identity.notification_item_ids)
            route_label = _route_label(items)
        if writer:
            writer.write_preview(
                message=message,
                lane=lane,
                route=route_label,
                identity=identity,
                would_send=True,
                sent=False,
            )
        if writer and writer.skip_as_duplicate(
            message=message,
            lane=lane,
            alert_ids=alert_ids,
            route=route_label,
            identity=identity,
        ):
            continue
        attempted = True
        if writer:
            writer.record_planned(message=message, lane=lane, alert_ids=alert_ids, route=route_label, identity=identity)
            writer.record_sending(message=message, lane=lane, alert_ids=alert_ids, route=route_label, identity=identity)
        attempt = _call_send_fn(send_fn, message)
        terminal_state = delivery.state_for_send_counts(
            delivered_count=attempt.delivered_count,
            failed_count=attempt.failed_count,
        )
        partial_marks_cooldown = bool(writer.cfg.partial_marks_cooldown) if writer else True
        if terminal_state == delivery.STATE_DELIVERED:
            delivered_by_lane[lane] = len(items)
            record_lane_sent(
                storage,
                lane,
                item_count=len(items),
                now=observed,
                alert_ids=alert_ids,
                cfg=cfg,
            )
            if writer:
                writer.record_attempt_result(
                    message=message,
                    lane=lane,
                    alert_ids=alert_ids,
                    route=route_label,
                    attempt=attempt,
                    identity=identity,
                )
        elif terminal_state == delivery.STATE_PARTIAL_DELIVERED:
            block_reasons.append(f"{lane}: partial delivery ({attempt.delivered_count}/{attempt.recipient_count} recipient(s))")
            if partial_marks_cooldown:
                record_lane_sent(
                    storage,
                    lane,
                    item_count=len(items),
                    now=observed,
                    alert_ids=alert_ids,
                    cfg=cfg,
                )
            if writer:
                writer.record_attempt_result(
                    message=message,
                    lane=lane,
                    alert_ids=alert_ids,
                    route=route_label,
                    attempt=attempt,
                    identity=identity,
                )
        else:
            block_reasons.append(f"{lane}: {attempt.error_message_safe or 'no channel delivered'}")
            if writer:
                writer.record_attempt_result(
                    message=message,
                    lane=lane,
                    alert_ids=alert_ids,
                    route=route_label,
                    attempt=attempt,
                    identity=identity,
                )
    if plan.heartbeat_due:
        heartbeat_message = format_health_heartbeat(
            profile=profile,
            result=_notification_preview_result(
                pipeline_result,
                plan=plan,
                delivered_by_lane=delivered_by_lane,
            ),
            now=observed,
        )
        heartbeat_identity = DeliveryIdentity(
            notification_item_ids=("heartbeat",),
            source_alert_ids=("heartbeat",),
            requested_alert_id="heartbeat",
            alert_id="heartbeat",
            identity_reconciled=False,
            identity_reconciliation_reason="heartbeat",
            notification_preview_path=str(writer.preview_path) if writer else None,
            notification_preview_relpath=delivery.notification_preview_relpath_for_path(writer.preview_path if writer else None),
        )
        if writer:
            writer.write_preview(
                message=heartbeat_message,
                lane=LANE_HEALTH_HEARTBEAT,
                route="HEALTH_HEARTBEAT",
                identity=heartbeat_identity,
                would_send=True,
                sent=False,
            )
        # Same delivery-ledger dedupe as the digest lanes for idempotency. In
        # practice the heartbeat carries a timestamp so its content hash differs
        # each run, but this keeps every lane consistently deduped.
        heartbeat_dup = bool(
            writer
            and writer.skip_as_duplicate(
                message=heartbeat_message,
                lane=LANE_HEALTH_HEARTBEAT,
                alert_ids=["heartbeat"],
                route="HEALTH_HEARTBEAT",
                identity=heartbeat_identity,
            )
        )
        if not heartbeat_dup:
            attempted = True
            if writer:
                writer.record_planned(
                    message=heartbeat_message,
                    lane=LANE_HEALTH_HEARTBEAT,
                    alert_ids=["heartbeat"],
                    route="HEALTH_HEARTBEAT",
                    identity=heartbeat_identity,
                )
                writer.record_sending(
                    message=heartbeat_message,
                    lane=LANE_HEALTH_HEARTBEAT,
                    alert_ids=["heartbeat"],
                    route="HEALTH_HEARTBEAT",
                    identity=heartbeat_identity,
                )
            attempt = _call_send_fn(send_fn, heartbeat_message)
            terminal_state = delivery.state_for_send_counts(
                delivered_count=attempt.delivered_count,
                failed_count=attempt.failed_count,
            )
            partial_marks_cooldown = bool(writer.cfg.partial_marks_cooldown) if writer else True
            if terminal_state == delivery.STATE_DELIVERED:
                delivered_by_lane[LANE_HEALTH_HEARTBEAT] = 1
                record_lane_sent(storage, LANE_HEALTH_HEARTBEAT, item_count=1, now=observed, cfg=cfg)
                if writer:
                    writer.record_attempt_result(
                        message=heartbeat_message,
                        lane=LANE_HEALTH_HEARTBEAT,
                        alert_ids=["heartbeat"],
                        route="HEALTH_HEARTBEAT",
                        attempt=attempt,
                        identity=heartbeat_identity,
                    )
            elif terminal_state == delivery.STATE_PARTIAL_DELIVERED:
                block_reasons.append(
                    f"health_heartbeat: partial delivery ({attempt.delivered_count}/{attempt.recipient_count} recipient(s))"
                )
                if partial_marks_cooldown:
                    record_lane_sent(storage, LANE_HEALTH_HEARTBEAT, item_count=1, now=observed, cfg=cfg)
                if writer:
                    writer.record_attempt_result(
                        message=heartbeat_message,
                        lane=LANE_HEALTH_HEARTBEAT,
                        alert_ids=["heartbeat"],
                        route="HEALTH_HEARTBEAT",
                        attempt=attempt,
                        identity=heartbeat_identity,
                    )
            else:
                block_reasons.append(f"health_heartbeat: {attempt.error_message_safe or 'no channel delivered'}")
                if writer:
                    writer.record_attempt_result(
                        message=heartbeat_message,
                        lane=LANE_HEALTH_HEARTBEAT,
                        alert_ids=["heartbeat"],
                        route="HEALTH_HEARTBEAT",
                        attempt=attempt,
                        identity=heartbeat_identity,
                    )

    delivered = sum(delivered_by_lane.values())
    return _result(
        requested=True,
        attempted=attempted,
        success=delivered > 0 and not block_reasons,
        items_attempted=would_send,
        items_delivered=delivered,
        block_reason="; ".join(block_reasons) or None,
        lane_items_attempted=lane_attempts,
        lane_items_delivered=delivered_by_lane,
        would_send_items=would_send,
        heartbeat_sent=delivered_by_lane[LANE_HEALTH_HEARTBEAT] > 0,
    )


def _call_send_fn(send_fn: SendFn, message: str) -> sender.NotificationSendAttemptResult:
    try:
        raw = send_fn(message)
    except Exception as exc:  # noqa: BLE001 - notification delivery must fail soft
        return sender.NotificationSendAttemptResult(
            attempted=True,
            success=False,
            recipient_count=0,
            delivered_count=0,
            failed_count=1,
            chunk_count=sender.telegram_chunk_count(message),
            delivered_chunks=0,
            failed_chunks=sender.telegram_chunk_count(message),
            error_class=type(exc).__name__,
            error_message_safe=sender.safe_error(exc),
            channel_summary={"channel": "unknown", "exception": type(exc).__name__},
        )
    return sender.normalize_send_result(raw, message=message, recipient_count=0)


def _delivery_identity_for_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
    card_path_by_alert_id: Mapping[str, str | Path],
    lane: str,
    preview_path: str | Path | None = None,
) -> DeliveryIdentity:
    source_ids = tuple(dict.fromkeys(decision.alert_id for decision in decisions if decision.alert_id))
    cores = [_core_row_for_decision(decision, core_row_by_alert_id) for decision in decisions]
    core_rows = [row for row in cores if row]
    core_ids = tuple(dict.fromkeys(str(row.get("core_opportunity_id") or "").strip() for row in core_rows if str(row.get("core_opportunity_id") or "").strip()))
    notification_ids = core_ids or source_ids or (lane,)
    first_core = core_rows[0] if core_rows else {}
    card_path = (
        first_core.get("card_path")
        or first_core.get("research_card_path")
        or first_core.get("canonical_card_path")
        or _first_card_path(card_path_by_alert_id, (*core_ids, *source_ids))
    )
    card_paths = tuple(dict.fromkeys(
        event_artifact_paths.artifact_display_path(
            row.get("card_path")
            or row.get("research_card_path")
            or row.get("canonical_card_path")
            or ""
        )
        for row in core_rows
        if str(row.get("card_path") or row.get("research_card_path") or row.get("canonical_card_path") or "").strip()
    ))
    symbols = tuple(dict.fromkeys(
        str(row.get("symbol") or row.get("validated_symbol") or "").strip()
        for row in core_rows
        if str(row.get("symbol") or row.get("validated_symbol") or "").strip()
    ))
    coin_ids = tuple(dict.fromkeys(
        str(row.get("coin_id") or row.get("validated_coin_id") or "").strip()
        for row in core_rows
        if str(row.get("coin_id") or row.get("validated_coin_id") or "").strip()
    ))
    feedback_targets = core_ids or source_ids or notification_ids
    alert_id = notification_ids[0] if notification_ids else None
    requested = source_ids[0] if source_ids else alert_id
    reconciled = bool(core_ids)
    return DeliveryIdentity(
        notification_item_ids=notification_ids,
        source_alert_ids=source_ids,
        core_opportunity_ids=core_ids,
        canonical_symbols=symbols,
        canonical_coin_ids=coin_ids,
        canonical_card_paths=card_paths,
        feedback_targets=feedback_targets,
        requested_alert_id=requested or alert_id,
        alert_id=alert_id,
        core_opportunity_id=core_ids[0] if core_ids else None,
        canonical_symbol=symbols[0] if symbols else None,
        canonical_coin_id=coin_ids[0] if coin_ids else None,
        canonical_card_path=event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        feedback_target=feedback_targets[0] if feedback_targets else (requested or alert_id),
        identity_reconciled=reconciled,
        identity_reconciliation_reason="canonical_core_opportunity" if reconciled else "source_alert_identity",
        notification_preview_path=str(preview_path) if preview_path else None,
        notification_preview_relpath=delivery.notification_preview_relpath_for_path(preview_path),
    )


def _identity_record_fields(identity: DeliveryIdentity | None) -> dict[str, Any]:
    if identity is None:
        return {}
    return {
        "requested_alert_id": identity.requested_alert_id,
        "core_opportunity_id": identity.core_opportunity_id,
        "core_opportunity_ids": identity.core_opportunity_ids,
        "canonical_symbol": identity.canonical_symbol,
        "canonical_symbols": identity.canonical_symbols,
        "canonical_coin_id": identity.canonical_coin_id,
        "canonical_coin_ids": identity.canonical_coin_ids,
        "canonical_card_path": identity.canonical_card_path,
        "canonical_card_paths": identity.canonical_card_paths,
        "feedback_target": identity.feedback_target,
        "feedback_targets": identity.feedback_targets,
        "source_alert_ids": identity.source_alert_ids,
        "notification_item_ids": identity.notification_item_ids,
        "identity_reconciled": identity.identity_reconciled,
        "identity_reconciliation_reason": identity.identity_reconciliation_reason,
        "notification_preview_path": identity.notification_preview_path,
        "notification_preview_relpath": identity.notification_preview_relpath,
    }


def format_core_opportunity_telegram_digest(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, object] | None = None,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
    pipeline_result: Any | None = None,
    max_items: int | None = None,
) -> str:
    """Render a compact human-facing digest keyed by canonical core opportunities."""
    unique_keep: list[event_alpha_router.EventAlphaRouteDecision] = []
    seen_for_count: set[str] = set()
    for decision in decisions:
        if not event_alpha_router.alertable_after_quality_gate(decision):
            continue
        key = decision.alert_id
        if key in seen_for_count:
            continue
        seen_for_count.add(key)
        unique_keep.append(decision)
    total_items = len(unique_keep)
    limit = max(1, int(max_items or 0)) if max_items is not None else None
    keep = unique_keep[:limit] if limit is not None else unique_keep
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    core_map = core_row_by_alert_id or {}
    title = "Event Alpha Research Digest"
    if any(event_alpha_router.final_route_value(item) == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value for item in keep):
        title = "Event Alpha High-Priority Research"
    if any(
        str((_core_row_for_decision(item, core_map) or {}).get("opportunity_type") or "").upper() == "FADE_SHORT_REVIEW"
        for item in keep
    ):
        title = "Event Alpha Fade / Short-Review Research"
    if any(event_alpha_router.final_route_value(item) == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value for item in keep):
        title = "Event Alpha Triggered Fade Research"
    lines = [
        f"<b>{_esc(title)}</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"Profile: {_esc(profile or 'default')}",
        f"Items: {len(keep)}",
    ]
    provider_summary = _provider_degradation_summary(pipeline_result)
    if provider_summary:
        lines.append(f"Provider status: {_esc(provider_summary)}")
    if not keep:
        lines.append("No router-approved escalations.")
        return "\n".join(lines)
    displayed = 0
    seen_core: set[str] = set()
    for decision in keep:
        core = _core_row_for_decision(decision, core_map) or {}
        core_id = str(core.get("core_opportunity_id") or "").strip()
        if core_id and core_id in seen_core:
            continue
        if core_id:
            seen_core.add(core_id)
        if max_items is not None and displayed >= max(1, int(max_items or 1)):
            break
        entry = decision.entry
        symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or "UNKNOWN")
        coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or "unknown")
        catalyst = str(
            core.get("canonical_incident_name")
            or core.get("incident_canonical_name")
            or core.get("event_name")
            or entry.latest_event_name
            or "unknown catalyst"
        )
        route = _human_route(event_alpha_router.final_route_value(decision))
        level = _human_reason(core.get("final_opportunity_level") or decision.opportunity_level or entry.opportunity_level or route)
        lane = _human_reason(core.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
        market_state = _human_reason(core.get("market_state_class") or core.get("market_state") or "unknown")
        impact = _human_reason(core.get("impact_path_type") or entry.impact_path_type or entry.latest_effective_playbook_type)
        role = _human_reason(core.get("candidate_role") or entry.candidate_role or entry.relationship_type)
        evidence = _evidence_line(core)
        market = _market_line_for_core(core, entry)
        why = _truncate_text(
            core.get("why_opportunity_visible")
            or core.get("final_verdict_reason")
            or decision.reason
            or "quality-gated research lead",
            140,
        )
        verify = _truncate_text(_verification_line(core, entry), 130)
        displayed += 1
        lines.extend(
            [
                "",
                f"<b>{displayed}. {_esc(symbol)} / {_esc(coin_id)}</b>",
                f"Catalyst: {_esc(catalyst)}",
                f"Level: {_esc(level)} · Route: {_esc(route)}",
                f"Opportunity: {_esc(lane)} · Market: {_esc(market_state)}",
                f"Impact: {_esc(impact)} · Role: {_esc(role)}",
                f"Why surfaced: {_esc(why)}",
                f"Evidence: {_esc(evidence)}",
                f"Market: {_esc(market)}",
                f"Check next: {_esc(verify)}",
            ]
        )
        if str(core.get("opportunity_type") or "").upper() == "FADE_SHORT_REVIEW":
            lines.extend([
                "Fade review: move already happened; crowding/exhaustion evidence is present.",
                "Risk: review invalidation and liquidity manually. Research-only. Not a trade signal.",
            ])
        card = core.get("card_path") or core.get("research_card_path") or _first_card_path(card_paths, (core_id, decision.alert_id))
        if card:
            lines.append(f"Card: {_esc(Path(str(card)).name)}")
        if core_id:
            lines.append(f"Feedback target: {_esc(core_id)}")
    lines.append("")
    if total_items > len(keep):
        lines.append(f"+{total_items - len(keep)} more in local brief.")
    lines.append("Research cards and feedback commands are available in local artifacts/inbox.")
    return "\n".join(lines)


def _evidence_line(core: Mapping[str, Any]) -> str:
    accepted = _accepted_evidence_count(core)
    status = str(core.get("evidence_acquisition_status") or "unknown").strip()
    confirm = str(core.get("acquisition_confirmation_status") or "").strip()
    pack = str(core.get("source_pack") or "source pack unknown").strip()
    if accepted > 0:
        return f"{accepted} accepted evidence item(s) from {pack}"
    if status == "rejected_results_only" or confirm == "does_not_confirm":
        return f"not confirmed; acquisition found rejected-only evidence via {pack}"
    if status in {"no_results", "skipped_budget", "provider_unavailable", "skipped_config"}:
        return f"not confirmed; acquisition status {status} via {pack}"
    return f"{status or 'unknown'} via {pack}"


def _market_line_for_core(core: Mapping[str, Any], entry: Any) -> str:
    level = str(core.get("market_confirmation_level") or getattr(entry, "market_confirmation_level", None) or "unknown")
    freshness = str(core.get("market_context_freshness_status") or getattr(entry, "market_context_freshness_status", None) or "unknown")
    score = core.get("market_confirmation_score")
    if score is None:
        score = getattr(entry, "market_confirmation_score", None)
    if score is not None:
        return f"{_human_reason(level)}; freshness {_human_reason(freshness)}; score {_fmt_num(score)}"
    return f"{_human_reason(level)}; freshness {_human_reason(freshness)}"


def _verification_line(core: Mapping[str, Any], entry: Any) -> str:
    items = _as_list(core.get("upgrade_requirements")) or _as_list(core.get("manual_verification_items"))
    if not items:
        items = list(getattr(entry, "upgrade_requirements", ()) or getattr(entry, "manual_verification_items", ()) or ())
    if not items:
        return "review the local card and source evidence before acting"
    return "; ".join(str(item).replace("_", " ") for item in items[:2])


def _provider_degradation_summary(result: Any | None) -> str:
    warnings = [str(item) for item in getattr(result, "warnings", ()) or () if str(item)]
    if not warnings:
        return ""
    provider_warnings = [item for item in warnings if any(token in item.lower() for token in ("provider", "gdelt", "rss", "cryptopanic", "timeout", "429", "403"))]
    selected = provider_warnings[:3] or warnings[:2]
    return "; ".join(_truncate_text(item, 80) for item in selected)


def _first_card_path(card_paths: Mapping[str, object], keys: Iterable[str]) -> str | None:
    for key in keys:
        if not key:
            continue
        path = card_paths.get(str(key))
        if path:
            return str(path)
    return None


def _joined_unique(values: Iterable[Any]) -> str | None:
    clean = tuple(dict.fromkeys(str(item).strip() for item in values if str(item or "").strip()))
    return ",".join(clean) if clean else None


def _human_route(value: object) -> str:
    raw = str(getattr(value, "value", value) or "").strip()
    mapping = {
        "RESEARCH_DIGEST": "research digest",
        "HIGH_PRIORITY_RESEARCH": "high-priority research",
        "TRIGGERED_FADE_RESEARCH": "triggered fade research",
        "STORE_ONLY": "stored locally",
        "LOCAL_REPORT": "local report",
    }
    return mapping.get(raw, _human_reason(raw))


def _fmt_num(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return "n/a"
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _truncate_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _canonicalize_decisions_for_notification(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[event_alpha_router.EventAlphaRouteDecision], tuple[str, ...]]:
    canonical: list[event_alpha_router.EventAlphaRouteDecision] = []
    warnings: list[str] = []
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id)
        if not core:
            canonical.append(decision)
            continue
        final_route = _core_final_route(core)
        block_reason = _core_notification_block_reason(core)
        if block_reason:
            final_route = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            warnings.append(f"{decision.alert_id}:notification_core_gate:{block_reason}")
        alertable = event_alpha_router.route_value_is_alertable(final_route)
        route = _route_enum_for_value(final_route)
        lane = _lane_enum_for_route(final_route)
        reason = str(
            block_reason
            or core.get("why_opportunity_visible")
            or core.get("final_verdict_reason")
            or core.get("quality_gate_block_reason")
            or decision.reason
        )
        canonical.append(
            replace(
                decision,
                route=route,
                lane=lane,
                alertable=alertable,
                reason=reason,
                final_route_after_quality_gate=final_route,
                quality_gate_block_reason=block_reason or decision.quality_gate_block_reason,
                opportunity_level=str(core.get("final_opportunity_level") or core.get("opportunity_level") or decision.opportunity_level or ""),
                opportunity_score_final=_float_or_none(
                    core.get("opportunity_score_final")
                    or core.get("final_opportunity_score")
                    or decision.opportunity_score_final
                ),
            )
        )
    return canonical, tuple(dict.fromkeys(warnings))


def _core_index_for_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    core_rows: Iterable[Mapping[str, Any] | object],
) -> dict[str, dict[str, Any]]:
    _ = decisions
    index: dict[str, dict[str, Any]] = {}
    for raw in core_rows or ():
        row = _as_mapping(raw)
        if not row:
            continue
        for key in _core_identity_keys(row):
            index.setdefault(key, row)
            index.setdefault(f"ea:{key}", row)
    return index


def _core_row_for_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not core_row_by_alert_id:
        return None
    for key in _decision_identity_keys(decision):
        row = core_row_by_alert_id.get(key)
        if row:
            return dict(row)
    return None


def _decision_identity_keys(decision: event_alpha_router.EventAlphaRouteDecision) -> tuple[str, ...]:
    entry = decision.entry
    components = getattr(entry, "latest_score_components", None) or {}
    values: list[Any] = [
        decision.alert_id,
        decision.card_id,
        getattr(entry, "key", None),
        getattr(entry, "hypothesis_id", None),
        getattr(entry, "incident_id", None),
        components.get("core_opportunity_id") if isinstance(components, Mapping) else None,
        components.get("canonical_core_opportunity_id") if isinstance(components, Mapping) else None,
        components.get("primary_hypothesis_id") if isinstance(components, Mapping) else None,
        components.get("hypothesis_id") if isinstance(components, Mapping) else None,
        components.get("watchlist_key") if isinstance(components, Mapping) else None,
        components.get("alert_id") if isinstance(components, Mapping) else None,
    ]
    if isinstance(components, Mapping):
        for name in ("supporting_hypothesis_ids", "diagnostic_row_ids", "supporting_row_ids"):
            values.extend(_as_list(components.get(name)))
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item or "").strip()))


def _core_identity_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[Any] = [
        row.get("core_opportunity_id"),
        row.get("aggregated_candidate_id"),
        row.get("primary_hypothesis_id"),
        row.get("hypothesis_id"),
        row.get("watchlist_key"),
        row.get("alert_id"),
        row.get("key"),
    ]
    for name in ("supporting_hypothesis_ids", "diagnostic_row_ids", "supporting_row_ids", "source_alert_ids"):
        values.extend(_as_list(row.get(name)))
    clean = [str(item).strip() for item in values if str(item or "").strip()]
    return tuple(dict.fromkeys(clean))


def _core_final_route(core: Mapping[str, Any]) -> str:
    value = str(
        core.get("final_route_after_quality_gate")
        or core.get("route")
        or core.get("final_route")
        or event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    )
    if value in {"WATCHLIST", "RADAR", "VALIDATED_DIGEST"}:
        return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    if value == "HIGH_PRIORITY":
        return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if value in {"LOCAL_ONLY", "QUALITY_BLOCKED", "RAW_EVIDENCE", "HYPOTHESIS"}:
        return event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    return value


def _core_notification_block_reason(core: Mapping[str, Any]) -> str | None:
    route = _core_final_route(core)
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return None
    if not event_alpha_router.route_value_is_alertable(route):
        return "canonical_core_not_alertable"
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip()
    if symbol.upper() == "SECTOR" or coin_id.startswith("sector") or not coin_id:
        return "sector_or_missing_validated_asset_not_digest_eligible"
    status = str(core.get("evidence_acquisition_status") or "").strip()
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    accepted = _accepted_evidence_count(core)
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    source_class = str(core.get("source_class") or "").strip().casefold()
    impact_path = str(core.get("impact_path_type") or "").strip().casefold()
    has_market_confirmation = market not in {"", "none", "missing", "unknown", "insufficient_data"} and freshness not in {"missing", "stale"}
    has_strong_source = source_class in {
        "official_project",
        "official_exchange",
        "structured_event_calendar",
        "cryptopanic_tagged",
        "project_blog",
        "exchange_announcement",
    }
    has_accepted_confirmation = accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate"))
    direct_event = impact_path in {
        "direct_token_event",
        "listing_liquidity_event",
        "unlock_supply_event",
        "exploit_security_event",
        "venue_value_capture",
        "fan_token_event",
    }
    if _core_is_unconfirmed_broad_strategic_asset(core):
        return "delivery_blocked_broad_strategic_asset_unconfirmed"
    if has_accepted_confirmation or has_strong_source or (has_market_confirmation and direct_event):
        return None
    if status == "rejected_results_only" or confirmation == "does_not_confirm":
        return "rejected_results_only_not_confirmation"
    if status == "skipped_budget":
        return "skipped_budget_not_confirmation"
    if status == "no_results":
        return "no_results_not_confirmation"
    if status in {"provider_unavailable", "backoff", "skipped_config", "not_configured"}:
        return f"{status}_not_confirmation"
    return "live_confirmation_missing"


def _accepted_evidence_count(core: Mapping[str, Any]) -> int:
    for key in ("accepted_evidence_count", "evidence_acquisition_accepted_count", "accepted_count"):
        value = _float_or_none(core.get(key))
        if value is not None:
            return max(0, int(value))
    return 0


def _core_is_unconfirmed_broad_strategic_asset(core: Mapping[str, Any]) -> bool:
    """Block broad treasury/equity valuation context from digest delivery.

    BTC/ETH/SOL can be valid Event Alpha candidates, but live-style notification
    delivery should not promote broad Strategy/MSTR/treasury/equity valuation
    articles unless the token impact was independently confirmed.
    """
    accepted = _accepted_evidence_count(core)
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    if accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate")):
        return False
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol not in {"BTC", "ETH", "SOL"} and coin_id not in {"bitcoin", "ethereum", "solana"}:
        return False
    impact = str(core.get("impact_path_type") or core.get("primary_impact_path") or "").strip().casefold()
    reason = str(core.get("impact_path_reason") or core.get("primary_impact_path_reason") or "").strip().casefold()
    if impact not in {"strategic_investment", "strategic_investment_or_valuation", "valuation_event"} and reason not in {
        "strategic_investment",
        "treasury_context",
        "external_equity_proxy_context",
    }:
        return False
    text = " ".join(
        str(core.get(key) or "")
        for key in (
            "canonical_incident_name",
            "incident_canonical_name",
            "latest_event_name",
            "event_name",
            "latest_source_title",
            "source_title",
            "latest_source",
            "source",
            "why_opportunity_visible",
            "final_verdict_reason",
        )
    ).casefold()
    broad_terms = (
        "strategy",
        "microstrategy",
        "mstr",
        "treasury",
        "holdings",
        "valuation",
        "discount",
        "premium",
        "public company",
        "market structure",
        "equity valuation",
        "shares",
        "stock",
    )
    direct_terms = (
        "protocol upgrade",
        "network upgrade",
        "spot etf approved",
        "listing",
        "unlock",
        "exploit",
    )
    return any(term in text for term in broad_terms) and not any(term in text for term in direct_terms)


def _route_enum_for_value(value: object) -> event_alpha_router.EventAlphaRoute:
    raw = str(getattr(value, "value", value) or "")
    try:
        return event_alpha_router.EventAlphaRoute(raw)
    except ValueError:
        if raw == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value:
            return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
        if raw == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
            return event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
        if raw == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
            return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
        return event_alpha_router.EventAlphaRoute.STORE_ONLY


def _lane_enum_for_route(value: object) -> event_alpha_router.EventAlphaRouteLane:
    lane = event_alpha_router.lane_value_for_route_value(value)
    try:
        return event_alpha_router.EventAlphaRouteLane(lane)
    except ValueError:
        return event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY


def _as_mapping(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_row"):
        try:
            row = value.to_row()
            if isinstance(row, Mapping):
                return dict(row)
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        return dict(getattr(value, "__dict__", {}) or {})
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
    return [value]


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _preview_summary_lines(sections: Iterable[Mapping[str, Any]]) -> list[str]:
    rows = [dict(section) for section in sections]
    would_send = [row for row in rows if bool(row.get("would_send"))]
    sent = [row for row in rows if bool(row.get("sent"))]
    guard_blocked = [
        row for row in would_send
        if str(row.get("status") or "") == delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED
    ]
    quality_blocked = [
        row for row in rows
        if "quality" in str(row.get("status") or "").casefold()
    ]
    cooldown_blocked = [
        row for row in rows
        if "cooldown" in str(row.get("status") or "").casefold()
    ]
    not_due = [row for row in rows if not bool(row.get("would_send")) and not bool(row.get("sent"))]
    core_ids = {
        str(item).strip()
        for row in rows
        for item in (getattr(row.get("identity"), "core_opportunity_ids", ()) or ())
        if str(item).strip()
    }
    rendered_items = sum(len(getattr(row.get("identity"), "notification_item_ids", ()) or ()) for row in rows)
    source_alert_count = sum(len(getattr(row.get("identity"), "source_alert_ids", ()) or ()) for row in rows)
    blocked_confirmation = [
        row for row in rows
        if any(
            token in " ".join(str(row.get(field) or "") for field in ("status", "route", "message")).casefold()
            for token in ("rejected", "unconfirmed", "no_market", "no-market", "confirmation")
        )
    ]
    lane_parts = []
    for row in rows:
        lane = str(row.get("lane") or "unknown")
        status = str(row.get("status") or "unknown")
        if bool(row.get("sent")):
            label = "sent"
        elif bool(row.get("would_send")) and status == delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED:
            label = "would_send_but_guard_disabled"
        elif bool(row.get("would_send")):
            label = status or "would_send"
        else:
            label = "not_due"
        lane_parts.append(f"{lane}={label}")
    send_guard = (
        "disabled (no-send rehearsal)"
        if guard_blocked
        else ("enabled" if sent else "not observed")
    )
    mode = "no-send rehearsal" if guard_blocked else ("send attempt" if sent else "preview")
    lines = [
        f"- Mode: {mode}",
        f"- Would send: {'yes' if would_send else 'no'}",
        f"- Lanes: {', '.join(lane_parts) if lane_parts else 'none'}",
        f"- Lane counts: due={len(would_send)} · sent={len(sent)} · would_send_but_guard_disabled={len(guard_blocked)} · blocked_by_quality={len(quality_blocked)} · blocked_by_cooldown={len(cooldown_blocked)} · not_due={len(not_due)}",
        f"- Rendered candidate items: {rendered_items}",
        f"- Core opportunity items: {len(core_ids)}",
        f"- Source alert IDs: {source_alert_count}",
        f"- Candidates blocked by confirmation: {len(blocked_confirmation)}",
        "- Provider issues: see Telegram body/run ledger",
        f"- Send guard: {send_guard}",
    ]
    if guard_blocked:
        lines.append("- No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode.")
    lines.append("- Recommendation: inspect this preview, inbox, and strict doctor before enabling Telegram sends.")
    return lines


def _preview_path_label(path: str | None) -> str:
    text = str(path or "").strip()
    if not text:
        return "none"
    return event_artifact_paths.artifact_display_path(text)


class _DeliveryWriter:
    """Append-only delivery recorder used by ``send_notifications``.

    Tracks rows written this run and dedupes against prior delivered content so a
    retried/overlapping cycle cannot re-send an identical research digest.
    """

    def __init__(
        self,
        cfg: delivery.NotificationDeliveryConfig,
        *,
        run_id: str | None,
        profile: str | None,
        namespace: str | None,
        now: datetime,
    ) -> None:
        self.cfg = cfg
        self.run_id = str(run_id or "unknown")
        self.profile = profile
        self.namespace = namespace
        self.now = now
        self.existing = delivery.load_delivery_records(cfg.path)
        self.preview_path = Path(cfg.path).expanduser().parent / "event_alpha_notification_preview.md"
        self.preview_sections: list[dict[str, Any]] = []
        self.counts: dict[str, int] = {
            delivery.STATE_DELIVERED: 0,
            delivery.STATE_PARTIAL_DELIVERED: 0,
            delivery.STATE_FAILED: 0,
            delivery.STATE_SKIPPED_DUPLICATE: 0,
            delivery.STATE_SKIPPED_IN_FLIGHT: 0,
            delivery.STATE_BLOCKED: 0,
            "records": 0,
        }

    def _joined(self, alert_ids: Iterable[str]) -> str:
        return ",".join(sorted(str(item) for item in alert_ids))

    def _hash(self, message: str, lane: str, alert_ids: Iterable[str]) -> str:
        return delivery.compute_content_hash(message, alert_id=self._joined(alert_ids), lane=lane, profile=self.profile)

    def _dedupe_bucket(self, message: str, lane: str, alert_ids: Iterable[str]) -> str:
        joined = self._joined(alert_ids)
        day = self.now.date().isoformat()
        lane_key = _clean_lane(lane)
        if lane_key == LANE_HEALTH_HEARTBEAT:
            status = "degraded" if _heartbeat_degraded(message) else "healthy"
            return f"{day}|{status}"
        if lane_key in {LANE_DAILY_DIGEST, LANE_RESEARCH_REVIEW_DIGEST, LANE_EXPLORATORY_DIGEST}:
            digest_bucket = joined or "digest"
            return f"{day}|{digest_bucket}"
        return joined or lane_key

    def _dedupe_key(self, message: str, lane: str, alert_ids: Iterable[str]) -> tuple[str, str]:
        bucket = self._dedupe_bucket(message, lane, alert_ids)
        return delivery.compute_dedupe_key(namespace=self.namespace, lane=lane, dedupe_bucket=bucket), bucket

    def _append(
        self,
        *,
        alert_ids: Iterable[str],
        lane: str,
        route: str,
        content_hash: str,
        state: str,
        dedupe_key: str | None = None,
        dedupe_bucket: str | None = None,
        **kwargs: Any,
    ) -> None:
        identity = kwargs.pop("identity", None)
        identity_fields = _identity_record_fields(identity)
        record = delivery.build_record(
            run_id=self.run_id,
            alert_id=self._joined(alert_ids),
            profile=self.profile,
            namespace=self.namespace,
            lane=lane,
            route=route,
            content_hash=content_hash,
            dedupe_key=dedupe_key,
            dedupe_bucket=dedupe_bucket,
            state=state,
            **identity_fields,
            now=self.now,
            **kwargs,
        )
        row = delivery.append_delivery_record(record, path=self.cfg.path)
        self.existing.append(row)
        if state in self.counts:
            self.counts[state] += 1
        if state in delivery.TERMINAL_STATES:
            self.counts["records"] += 1

    def skip_as_duplicate(
        self,
        *,
        message: str,
        lane: str,
        alert_ids: list[str],
        route: str,
        identity: DeliveryIdentity | None = None,
    ) -> bool:
        if not self.cfg.dedupe_by_content:
            return False
        content_hash = self._hash(message, lane, alert_ids)
        dedupe_key, dedupe_bucket = self._dedupe_key(message, lane, alert_ids)
        dup = delivery.find_recent_delivered(
            self.existing,
            content_hash=content_hash,
            dedupe_key=dedupe_key,
            namespace=self.namespace,
            now=self.now,
            window_hours=self.cfg.dedupe_window_hours,
            include_partial=self.cfg.partial_marks_cooldown,
        )
        if dup is None:
            in_flight = delivery.find_recent_in_flight(
                self.existing,
                content_hash=content_hash,
                dedupe_key=dedupe_key,
                namespace=self.namespace,
                now=self.now,
                grace_minutes=self.cfg.in_flight_grace_minutes,
            )
            if in_flight is None:
                return False
            self._append(
                alert_ids=alert_ids,
                lane=lane,
                route=route,
                content_hash=content_hash,
                dedupe_key=dedupe_key,
                dedupe_bucket=dedupe_bucket,
                state=delivery.STATE_SKIPPED_IN_FLIGHT,
                identity=identity,
                error_class="in_flight_content",
                error_message=(
                    f"in-flight duplicate within {self.cfg.in_flight_grace_minutes:g}m "
                    f"(prior attempted_at={in_flight.get('attempted_at')})"
                ),
            )
            return True
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=content_hash,
            dedupe_key=dedupe_key,
            dedupe_bucket=dedupe_bucket,
            state=delivery.STATE_SKIPPED_DUPLICATE,
            identity=identity,
            error_class="duplicate_content",
            error_message=f"duplicate within {self.cfg.dedupe_window_hours:g}h (prior delivered_at={dup.get('delivered_at')})",
        )
        return True

    def record_planned(
        self,
        *,
        message: str,
        lane: str,
        alert_ids: list[str],
        route: str,
        identity: DeliveryIdentity | None = None,
    ) -> None:
        dedupe_key, dedupe_bucket = self._dedupe_key(message, lane, alert_ids)
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=self._hash(message, lane, alert_ids),
            dedupe_key=dedupe_key,
            dedupe_bucket=dedupe_bucket,
            state=delivery.STATE_PLANNED,
            identity=identity,
        )

    def record_sending(
        self,
        *,
        message: str,
        lane: str,
        alert_ids: list[str],
        route: str,
        identity: DeliveryIdentity | None = None,
    ) -> None:
        dedupe_key, dedupe_bucket = self._dedupe_key(message, lane, alert_ids)
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=self._hash(message, lane, alert_ids),
            dedupe_key=dedupe_key,
            dedupe_bucket=dedupe_bucket,
            state=delivery.STATE_SENDING,
            identity=identity,
        )

    def record_attempt_result(
        self,
        *,
        message: str,
        lane: str,
        alert_ids: list[str],
        route: str,
        attempt: sender.NotificationSendAttemptResult,
        identity: DeliveryIdentity | None = None,
    ) -> None:
        state = delivery.state_for_send_counts(
            delivered_count=attempt.delivered_count,
            failed_count=attempt.failed_count,
        )
        dedupe_key, dedupe_bucket = self._dedupe_key(message, lane, alert_ids)
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=self._hash(message, lane, alert_ids),
            dedupe_key=dedupe_key,
            dedupe_bucket=dedupe_bucket,
            state=state,
            delivered_at=self.now if attempt.delivered_count > 0 else None,
            error_class=None if state == delivery.STATE_DELIVERED else (attempt.error_class or "send_failed"),
            error_message=None if state == delivery.STATE_DELIVERED else (attempt.error_message_safe or "no channel delivered"),
            recipient_count=attempt.recipient_count,
            delivered_count=attempt.delivered_count,
            failed_count=attempt.failed_count,
            chunk_count=attempt.chunk_count,
            delivered_chunks=attempt.delivered_chunks,
            failed_chunks=attempt.failed_chunks,
            channel_summary=attempt.channel_summary,
            identity=identity,
        )

    def record_blocked(
        self,
        plan: "EventAlphaNotificationPlan",
        *,
        profile: str | None,
        card_map: dict[str, Any],
        reason: str,
        error_class: str = "guard_blocked",
        pipeline_result: Any | None = None,
    ) -> None:
        status_detail = _blocked_preview_status_detail(reason, error_class=error_class)
        for lane in (
            LANE_TRIGGERED_FADE,
            LANE_INSTANT_ESCALATION,
            LANE_DAILY_DIGEST,
            LANE_RESEARCH_REVIEW_DIGEST,
            LANE_EXPLORATORY_DIGEST,
        ):
            research_review = lane == LANE_RESEARCH_REVIEW_DIGEST
            exploratory = lane == LANE_EXPLORATORY_DIGEST
            if research_review:
                items = list(plan.research_review_items)
            else:
                items = list(plan.exploratory_items if exploratory else plan.decisions_by_lane.get(lane, []))
            if not items:
                continue
            if research_review:
                message = format_research_review_telegram_digest(
                    items,
                    profile=profile,
                    card_path_by_alert_id=card_map,
                    core_row_by_alert_id=plan.core_row_by_alert_id,
                    cfg=EventAlphaNotificationConfig(),
                    eligible_count=plan.research_review_eligible_count,
                    skipped_items=plan.research_review_skipped_items,
                )
                identity = _delivery_identity_for_decisions(
                    [item.decision for item in items],
                    core_row_by_alert_id=plan.core_row_by_alert_id,
                    card_path_by_alert_id=card_map,
                    lane=lane,
                    preview_path=self.preview_path,
                )
                alert_ids = list(identity.notification_item_ids)
                route_label = "RESEARCH_REVIEW_DIGEST"
            elif exploratory:
                message = format_exploratory_telegram_digest(items, profile=profile, card_path_by_alert_id=card_map)
                identity = _delivery_identity_for_decisions(
                    [item.decision for item in items],
                    core_row_by_alert_id=plan.core_row_by_alert_id,
                    card_path_by_alert_id=card_map,
                    lane=lane,
                    preview_path=self.preview_path,
                )
                alert_ids = list(identity.notification_item_ids)
                route_label = "EXPLORATORY_DIGEST"
            else:
                message = format_core_opportunity_telegram_digest(
                    items,
                    profile=profile,
                    card_path_by_alert_id=card_map,
                    core_row_by_alert_id=plan.core_row_by_alert_id,
                    max_items=getattr(self.cfg, "daily_digest_max_items", None) if lane == LANE_DAILY_DIGEST else None,
                )
                identity = _delivery_identity_for_decisions(
                    items,
                    core_row_by_alert_id=plan.core_row_by_alert_id,
                    card_path_by_alert_id=card_map,
                    lane=lane,
                    preview_path=self.preview_path,
                )
                alert_ids = list(identity.notification_item_ids)
                route_label = _route_label(items)
            self.write_preview(
                message=message,
                lane=lane,
                route=route_label,
                identity=identity,
                would_send=True,
                sent=False,
                status=status_detail,
            )
            self._append(
                alert_ids=alert_ids,
                lane=lane,
                route=route_label,
                content_hash=self._hash(message, lane, alert_ids),
                dedupe_key=self._dedupe_key(message, lane, alert_ids)[0],
                dedupe_bucket=self._dedupe_key(message, lane, alert_ids)[1],
                state=delivery.STATE_BLOCKED,
                identity=identity,
                error_class=error_class,
                error_message=reason,
                channel_summary=_research_review_channel_summary(plan) if research_review else None,
            )
        if plan.heartbeat_due:
            message = format_health_heartbeat(
                profile=profile,
                result=pipeline_result,
                now=self.now,
                send_guard_status=_send_guard_status_line(reason, error_class=error_class),
            )
            identity = DeliveryIdentity(
                notification_item_ids=("heartbeat",),
                source_alert_ids=("heartbeat",),
                requested_alert_id="heartbeat",
                alert_id="heartbeat",
                identity_reconciled=False,
                identity_reconciliation_reason="heartbeat",
                notification_preview_path=str(self.preview_path),
                notification_preview_relpath=delivery.notification_preview_relpath_for_path(self.preview_path),
            )
            self.write_preview(
                message=message,
                lane=LANE_HEALTH_HEARTBEAT,
                route="HEALTH_HEARTBEAT",
                identity=identity,
                would_send=True,
                sent=False,
                status=status_detail,
            )
            self._append(
                alert_ids=["heartbeat"],
                lane=LANE_HEALTH_HEARTBEAT,
                route="HEALTH_HEARTBEAT",
                content_hash=self._hash(message, LANE_HEALTH_HEARTBEAT, ["heartbeat"]),
                dedupe_key=self._dedupe_key(message, LANE_HEALTH_HEARTBEAT, ["heartbeat"])[0],
                dedupe_bucket=self._dedupe_key(message, LANE_HEALTH_HEARTBEAT, ["heartbeat"])[1],
                state=delivery.STATE_BLOCKED,
                identity=identity,
                error_class=error_class,
                error_message=reason,
            )

    def write_preview(
        self,
        *,
        message: str,
        lane: str,
        route: str,
        identity: DeliveryIdentity,
        would_send: bool,
        sent: bool,
        status: str | None = None,
    ) -> None:
        """Write operator-visible Telegram bodies for all lanes in this run."""
        section_status = str(status or ("sent" if sent else "would_send"))
        self.preview_sections.append(
            {
                "lane": lane,
                "route": route,
                "would_send": bool(would_send),
                "sent": bool(sent),
                "status": section_status,
                "identity": identity,
                "message": message,
            }
        )
        body = [
            "# Event Alpha Notification Preview",
            "",
            f"generated_at: {self.now.isoformat()}",
            f"profile: {self.profile or 'default'}",
            f"namespace: {self.namespace or 'default'}",
            "",
            "## Preview Summary",
            "",
            *_preview_summary_lines(self.preview_sections),
            "",
            f"sections: {len(self.preview_sections)}",
        ]
        for idx, section in enumerate(self.preview_sections, start=1):
            item_identity = section["identity"]
            body.extend(
                [
                    "",
                    f"## Lane {idx}: {section['lane']}",
                    "",
                    f"lane: {section['lane']}",
                    f"route: {section['route']}",
                    f"status: {section['status']}",
                    f"would_send: {str(bool(section['would_send'])).lower()}",
                    f"sent: {str(bool(section['sent'])).lower()}",
                    f"alert_id: {item_identity.alert_id or self._joined(item_identity.notification_item_ids)}",
                    f"core_opportunity_id: {item_identity.core_opportunity_id or 'none'}",
                    "core_opportunity_ids: " + ", ".join(item_identity.core_opportunity_ids or ("none",)),
                    f"canonical_symbol: {item_identity.canonical_symbol or 'unknown'}",
                    "canonical_symbols: " + ", ".join(item_identity.canonical_symbols or ("none",)),
                    f"canonical_coin_id: {item_identity.canonical_coin_id or 'unknown'}",
                    "canonical_coin_ids: " + ", ".join(item_identity.canonical_coin_ids or ("none",)),
                    f"canonical_card_path: {_preview_path_label(item_identity.canonical_card_path)}",
                    "canonical_card_paths: " + ", ".join(_preview_path_label(path) for path in (item_identity.canonical_card_paths or ("none",))),
                    f"feedback_target: {item_identity.feedback_target or item_identity.core_opportunity_id or item_identity.alert_id or 'none'}",
                    "feedback_targets: " + ", ".join(item_identity.feedback_targets or ("none",)),
                    "source_alert_ids: " + ", ".join(item_identity.source_alert_ids or ("none",)),
                    "notification_item_ids: " + ", ".join(item_identity.notification_item_ids or ("none",)),
                    f"identity_reconciled: {str(item_identity.identity_reconciled).lower()}",
                    f"identity_reconciliation_reason: {item_identity.identity_reconciliation_reason or 'none'}",
                    "",
                    "### Telegram Body",
                    "",
                    "```html",
                    str(section["message"]),
                    "```",
                ]
            )
        try:
            self.preview_path.parent.mkdir(parents=True, exist_ok=True)
            self.preview_path.write_text("\n".join(body) + "\n", encoding="utf-8")
        except OSError:
            return

    def write_no_digest_preview(
        self,
        *,
        profile: str | None,
        pipeline_result: Any | None,
        reason: str,
    ) -> None:
        warnings = tuple(str(item) for item in _value(pipeline_result, "warnings") or () if str(item))
        lane_due = _mapping_value(pipeline_result, "send_lane_items_attempted")
        lane_sent = _mapping_value(pipeline_result, "send_lane_items_delivered")
        lanes_due = sum(_safe_int(value) for value in lane_due.values())
        lanes_sent = sum(_safe_int(value) for value in lane_sent.values())
        lines = [
            "<b>Event Alpha Notification Rehearsal</b>",
            "<i>Research-only / unvalidated. Not a trade signal.</i>",
            f"Profile: {_esc(profile or _value(pipeline_result, 'profile') or 'default')}",
            "Mode: no-send rehearsal / preview only",
            "Status: no digest candidates would be sent",
            f"Reason: {_esc(reason or 'no due notifications')}",
            f"Completed: {_yes_no(bool(_value(pipeline_result, 'cycle_completed', pipeline_result is not None)))}",
            f"Raw events: {_num(pipeline_result, 'raw_events')} · Core opportunities: {_num(pipeline_result, 'core_opportunities')}",
            f"Extraction rows: {_num(pipeline_result, 'extraction_rows')}",
            (
                f"Alertable decisions: {_num(pipeline_result, 'alertable')} · "
                f"Strict alerts: {_num(pipeline_result, 'alerts')} · "
                f"Research candidates: {_num(pipeline_result, 'candidates')} · "
                f"Raw source candidates: {_raw_source_candidate_count(pipeline_result)}"
            ),
            f"Delivery lanes: due={lanes_due} · sent={lanes_sent} · blocked={max(0, _num(pipeline_result, 'send_would_send_items') - lanes_sent)}",
            f"Provider issues: {_provider_failure_count(warnings)}",
            f"LLM calls/skips: {_num(pipeline_result, 'llm_calls_attempted')}/{_num(pipeline_result, 'llm_skipped_due_budget')}",
            f"Send guard: {_send_guard_status_line(reason)}",
        ]
        if warnings:
            lines.append("Top issues: " + _esc("; ".join(_truncate_text(item, 90) for item in warnings[:3])))
        else:
            lines.append("Top issues: none")
        lines.append("Next: inspect daily brief, inbox, and strict artifact doctor before enabling Telegram.")
        identity = DeliveryIdentity(
            notification_item_ids=("no_digest_candidates",),
            source_alert_ids=("none",),
            requested_alert_id="no_digest_candidates",
            alert_id="no_digest_candidates",
            identity_reconciled=False,
            identity_reconciliation_reason="no_digest_candidates",
            notification_preview_path=str(self.preview_path),
            notification_preview_relpath=delivery.notification_preview_relpath_for_path(self.preview_path),
        )
        self.write_preview(
            message="\n".join(lines),
            lane=LANE_DAILY_DIGEST,
            route="NO_DIGEST_CANDIDATES",
            identity=identity,
            would_send=False,
            sent=False,
            status="no_digest_candidates",
        )


def _route_label(items: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    for decision in items:
        route = getattr(decision, "route", None)
        if route is not None:
            return getattr(route, "value", str(route))
    return ""


def _suppression_reason(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    entry = decision.entry
    return str(
        entry.suppressed_reason
        or decision.reason
        or ("; ".join(entry.warnings) if entry.warnings else "")
    ).strip()


def _is_exploratory_control(entry: Any) -> bool:
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            entry.latest_playbook_type,
            entry.latest_effective_playbook_type,
            entry.relationship_type,
            entry.latest_llm_asset_role,
            entry.latest_event_name,
        )
    )
    return any(token in fields for token in ("source_noise", "ticker_word_collision", "word_collision"))


def _is_ambiguous_exploratory(entry: Any) -> bool:
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            entry.latest_playbook_type,
            entry.latest_effective_playbook_type,
            entry.relationship_type,
            entry.latest_llm_asset_role,
        )
    )
    return "ambiguous" in fields


def _ambiguous_has_learning_value(entry: Any) -> bool:
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    return bool(
        entry.external_asset
        or entry.event_time
        or _component_score(components, "market_move_volume") >= 25
        or _component_score(components, "source_quality") >= 40
        or _component_score(components, "cluster_confidence") >= 40
        or int(getattr(entry, "source_count", 0) or 0) > 1
    )


def _exploratory_rank(entry: Any) -> tuple[float, list[str]]:
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    market = _component_score(components, "market_move_volume")
    source_quality = _component_score(components, "source_quality")
    extraction = max(
        _component_score(components, "llm_extraction_confidence"),
        _component_score(components, "extraction_confidence"),
        float(getattr(entry, "latest_llm_confidence", 0.0) or 0.0) * 100.0,
    )
    cluster = _component_score(components, "cluster_confidence")
    freshness = _component_score(components, "novelty_freshness")
    catalyst = 20.0 if (entry.external_asset or entry.event_time) else _component_score(components, "catalyst_presence")
    hypothesis = _component_score(components, "hypothesis_confidence")
    rank = (
        float(getattr(entry, "latest_score", 0) or 0)
        + 0.45 * market
        + 0.30 * source_quality
        + 0.25 * extraction
        + 0.20 * cluster
        + 0.15 * freshness
        + catalyst
        + 0.30 * hypothesis
    )
    reasons: list[str] = []
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        reasons.append("impact hypothesis awaiting validation")
    if market >= 25:
        reasons.append(f"market anomaly score {market:g}")
    if source_quality >= 40:
        reasons.append(f"source quality {source_quality:g}")
    if extraction >= 50:
        reasons.append(f"LLM/extraction confidence {extraction:g}")
    if catalyst:
        reasons.append("has catalyst/external-asset evidence")
    if hypothesis >= 40:
        reasons.append(f"hypothesis confidence {hypothesis:g}")
    if cluster >= 40:
        reasons.append(f"cluster confidence {cluster:g}")
    if freshness >= 40:
        reasons.append(f"freshness {freshness:g}")
    if not reasons:
        reasons.append("suppressed row retained for burn-in review")
    return rank, reasons


def _exploratory_verify_steps(entry: Any, reason: str) -> list[str]:
    playbook = str(entry.latest_playbook_type or entry.latest_effective_playbook_type or "").casefold()
    steps = []
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        steps.append("validate candidate asset link to catalyst")
        steps.append("run targeted source search for candidate/catalyst")
    elif "market_anomaly" in playbook:
        steps.append("find independent catalyst/source evidence for the move")
        steps.append("check whether the move is liquidity noise or organic volume")
    elif "direct" in playbook or "listing" in playbook or "unlock" in playbook:
        steps.append("verify the direct event mechanics and timing")
        steps.append("check whether this belongs outside proxy-fade research")
    elif entry.external_asset:
        steps.append("confirm the crypto asset is actually linked to the external catalyst")
        steps.append("verify the catalyst timestamp and source provenance")
    else:
        steps.append("verify asset identity from source title/body, not publisher or URL noise")
        steps.append("look for a dated catalyst before escalating")
    if "duplicate" in str(reason).casefold():
        steps.append("check whether this is a repeated row rather than a new escalation")
    return steps


def _component_score(components: Mapping[str, Any], key: str) -> float:
    try:
        return float(components.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _compact_market(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    if not data:
        return "missing"
    fields = []
    for key in ("price", "return_24h", "return_72h", "volume_zscore_24h", "volume_mcap"):
        if key in data and data.get(key) not in (None, ""):
            value = data.get(key)
            if isinstance(value, float):
                fields.append(f"{key}={value:.4g}")
            else:
                fields.append(f"{key}={value}")
    return " ".join(fields) if fields else "present"


def _human_asset_name(coin_id: object) -> str:
    text = str(coin_id or "unknown").strip()
    if not text:
        return "Unknown"
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", text) if part) or text


def _human_playbook(value: object) -> str:
    text = str(value or "unknown").strip()
    mapping = {
        "market_anomaly_unknown": "market anomaly / unknown catalyst",
        "market_anomaly": "market anomaly",
        "proxy_fade": "proxy fade",
        "proxy_attention": "proxy attention",
        "direct_event": "direct event",
        "infrastructure_mention": "infrastructure mention",
        "source_noise_control": "source/noise control",
        "ambiguous_control": "relationship unclear",
        "ambiguous": "relationship unclear",
        "impact_hypothesis": "impact hypothesis",
        "rwa_preipo_proxy": "RWA/pre-IPO proxy",
        "ai_ipo_proxy": "AI IPO proxy",
        "sports_fan_proxy": "sports/fan-token proxy",
        "stablecoin_regulatory": "stablecoin regulatory",
    }
    return mapping.get(text, text.replace("_", " "))


def _human_state(value: object) -> str:
    text = str(value or "").strip()
    mapping = {
        "RAW_EVIDENCE": "raw evidence only",
        "HYPOTHESIS": "impact hypothesis awaiting validation",
        "STORE_ONLY": "stored for research only",
        "RADAR": "radar",
        "WATCHLIST": "watchlist",
        "HIGH_PRIORITY": "high priority",
        "EVENT_PASSED": "event passed",
        "ARMED": "armed",
        "TRIGGERED_FADE": "triggered fade",
        "INVALIDATED": "invalidated",
        "EXPIRED": "expired",
    }
    return mapping.get(text, text.replace("_", " ").lower() if text else "stored for research only")


def _human_reason(value: object) -> str:
    text = str(value or "").strip()
    normalized = text.casefold()
    mapping = {
        "raw/store-only evidence, no alertable watchlist state": "not alertable yet",
        "raw, expired, or invalidated watchlist state is stored only.": "not alertable yet",
        "event alpha router is disabled; retaining watchlist row as research evidence only.": "router disabled",
        "impact hypothesis awaiting asset validation": "not alertable yet",
        "impact hypothesis awaiting validation": "not alertable yet",
    }
    if normalized in mapping:
        return mapping[normalized]
    if "duplicate" in normalized:
        return "duplicate or repeated evidence"
    if "cooldown" in normalized:
        return "cooldown active"
    if "alertable" in normalized:
        return "not alertable yet"
    return text.replace("_", " ") if text else "not alertable yet"


def _human_level(value: object) -> str:
    text = str(value or "").strip()
    mapping = {
        "local_only": "local-only research",
        "exploratory": "exploratory research",
        "validated_digest": "validated digest",
        "watchlist": "watchlist",
        "high_priority": "high priority",
    }
    return mapping.get(text, text.replace("_", " ") if text else "research review")


def _candidate_catalyst_text(entry: Any) -> str:
    for value in (
        getattr(entry, "latest_event_name", None),
        getattr(entry, "external_asset", None),
        getattr(entry, "event_id", None),
    ):
        text = str(value or "").strip()
        if text:
            return _truncate_text(text.replace("|", " / "), 96)
    return "catalyst not confirmed"


def _human_why_not_alertable(reasons: Iterable[str]) -> str:
    output: list[str] = []
    for reason in reasons:
        text = _human_reason(reason)
        lower = text.casefold()
        if "confirmation" in lower and "missing" in lower:
            output.append("missing confirmation")
        elif "rejected results only" in lower:
            output.append("evidence search rejected the link")
        elif "skipped budget" in lower:
            output.append("evidence search unresolved")
        elif "local only" in lower:
            output.append("quality gate kept it local-only")
        elif "watchlist" in lower and "not" in lower:
            output.append("watchlist requirements not met")
        elif text:
            output.append(text)
    if not output:
        output.append("missing confirmation")
    return "; ".join(dict.fromkeys(output[:3]))


def _telegram_card_basename(
    decision: event_alpha_router.EventAlphaRouteDecision,
    card_path_by_alert_id: Mapping[str, str | Path] | None,
    *,
    core: Mapping[str, Any] | None = None,
) -> str:
    core = core or {}
    for value in (
        core.get("card_path"),
        core.get("research_card_path"),
        core.get("canonical_card_path"),
    ):
        text = str(value or "").strip()
        if text:
            return event_artifact_paths.artifact_display_path(text)
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    for key in _decision_identity_keys(decision):
        path = card_paths.get(key)
        if path:
            return event_artifact_paths.artifact_display_path(path)
    return "local artifacts"


def _telegram_feedback_target(
    decision: event_alpha_router.EventAlphaRouteDecision,
    *,
    core: Mapping[str, Any] | None = None,
) -> str:
    core = core or {}
    for value in (
        core.get("feedback_target"),
        core.get("core_opportunity_id"),
        core.get("canonical_core_opportunity_id"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    components = dict(getattr(decision.entry, "latest_score_components", {}) or {})
    for value in (
        components.get("core_opportunity_id"),
        components.get("canonical_core_opportunity_id"),
        getattr(decision.entry, "hypothesis_id", None),
        decision.alert_id,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "local inbox"


def _human_status(state: object, tier: object, reason: object) -> str:
    state_text = _human_state(state or tier)
    reason_text = _human_reason(reason)
    if reason_text and reason_text != state_text:
        return f"{state_text} — {reason_text}"
    return state_text


def _move_summary(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    parts = []
    for key, label in (("return_24h", "24h"), ("return_72h", "72h"), ("return_7d", "7d")):
        value = _float_or_none(data.get(key))
        if value is not None:
            parts.append(f"{_format_pct_return(value)} {label}")
    return ", ".join(parts) if parts else "n/a"


def _volume_mcap_summary(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    value = _float_or_none(data.get("volume_mcap"))
    if value is None:
        volume = _float_or_none(data.get("volume_24h") or data.get("spot_volume_24h"))
        market_cap = _float_or_none(data.get("market_cap"))
        if volume is not None and market_cap and market_cap > 0:
            value = volume / market_cap
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _format_pct_return(value: float) -> str:
    percent = value if abs(value) > 10 else value * 100.0
    sign = "+" if percent > 0 else ""
    return f"{sign}{percent:.1f}%"


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _human_why(reasons: Iterable[str]) -> str:
    output: list[str] = []
    for reason in reasons:
        text = str(reason or "").strip()
        lower = text.casefold()
        if lower.startswith("market anomaly score"):
            output.append("unusual market move")
        elif "impact hypothesis" in lower:
            output.append("impact hypothesis")
        elif lower.startswith("hypothesis confidence"):
            output.append(text)
        elif lower.startswith("source quality"):
            output.append(text)
        elif lower.startswith("freshness"):
            output.append("fresh anomaly")
        elif lower.startswith("cluster confidence"):
            output.append(text)
        elif "catalyst" in lower or "external-asset" in lower:
            output.append("possible catalyst clue")
        elif "extraction confidence" in lower or "llm" in lower:
            output.append(text.replace("LLM/extraction", "extraction"))
        elif text:
            output.append(text.replace("_", " "))
    if not output:
        output.append("suppressed row retained for review")
    return "; ".join(dict.fromkeys(output[:4]))


def _human_check_next(steps: Iterable[str]) -> str:
    output: list[str] = []
    for step in steps:
        text = str(step or "").strip()
        lower = text.casefold()
        if "independent catalyst" in lower:
            output.append("find independent catalyst")
        elif "candidate asset link" in lower:
            output.append("validate asset-catalyst link")
        elif "targeted source search" in lower:
            output.append("run targeted source search")
        elif "liquidity noise" in lower or "organic volume" in lower:
            output.append("verify liquidity/organic volume")
        elif "direct event mechanics" in lower:
            output.append("verify event mechanics/timing")
        elif "proxy-fade" in lower:
            output.append("confirm outside proxy-fade path")
        elif "asset is actually linked" in lower:
            output.append("verify asset-catalyst link")
        elif "timestamp" in lower or "provenance" in lower:
            output.append("verify event time/source")
        elif "asset identity" in lower:
            output.append("verify asset identity")
        elif "dated catalyst" in lower:
            output.append("look for dated catalyst")
        elif text:
            output.append(text)
    if not output:
        output.append("review source evidence")
    return "; ".join(dict.fromkeys(output[:3]))


def _human_risk(entry: Any, decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    risks: list[str] = []
    playbook = str(entry.latest_playbook_type or entry.latest_effective_playbook_type or "").casefold()
    relationship = str(entry.relationship_type or "").casefold()
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    classifier = _component_score(components, "classifier")
    if "market_anomaly" in playbook:
        risks.append("no confirmed narrative")
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        risks.append("asset impact not validated")
    if "ambiguous" in relationship or "ambiguous" in playbook:
        risks.append("relationship unclear")
    if classifier and classifier < 60:
        risks.append("low classifier confidence")
    if not getattr(entry, "event_time", None):
        risks.append("no dated catalyst")
    if int(getattr(entry, "source_count", 0) or 0) <= 1:
        risks.append("single-source evidence")
    warnings = tuple(dict.fromkeys((*getattr(entry, "warnings", ()), *getattr(decision, "warnings", ()))))
    if warnings and len(risks) < 3:
        risks.append(str(warnings[0]).replace("_", " "))
    return "; ".join(dict.fromkeys(risks[:3])) if risks else "needs manual confirmation"


def legacy_meta_warnings(storage: Any, cfg: EventAlphaNotificationConfig) -> tuple[str, ...]:
    """Return migration warnings for old unscoped notification keys."""
    if _clean_scope(cfg.notification_scope) == NOTIFICATION_SCOPE_GLOBAL:
        return ()
    warnings: list[str] = []
    for lane, key in LAST_SENT_META_KEYS.items():
        if storage.get_meta(key):
            warnings.append(f"legacy unscoped key present for {lane}: {key}")
    return tuple(warnings)


def format_health_heartbeat(
    *,
    profile: str | None,
    result: Any | None = None,
    now: datetime | None = None,
    send_guard_status: str | None = None,
) -> str:
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings = tuple(str(item) for item in _value(result, "warnings") or () if str(item))
    partial = bool(_value(result, "partial_results", False) or _provider_failure_count(warnings) > 0)
    lane_due = _mapping_value(result, "send_lane_items_attempted")
    lane_sent = _mapping_value(result, "send_lane_items_delivered")
    lanes_due = sum(_safe_int(value) for value in lane_due.values())
    lanes_sent = sum(_safe_int(value) for value in lane_sent.values())
    lane_status = _delivery_lane_status(result, send_guard_status=send_guard_status)
    llm_calls = _num(result, "llm_calls_attempted")
    llm_skipped = _num(result, "llm_skipped_due_budget")
    lines = [
        "<b>Event Alpha Heartbeat</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"Profile: {_esc(profile or _value(result, 'profile') or 'default')}",
        f"Generated: {_esc(observed.isoformat())}",
        f"Status: {_esc('degraded' if partial else 'ok')}",
        f"Completed: {_yes_no(bool(_value(result, 'cycle_completed', result is not None)))}",
        f"Raw events: {_num(result, 'raw_events')} · Core opportunities: {_num(result, 'core_opportunities')}",
        f"Extraction rows: {_num(result, 'extraction_rows')}",
        (
            f"Alertable decisions: {_num(result, 'alertable')} · "
            f"Strict alerts: {_num(result, 'alerts')} · "
            f"Research candidates: {_num(result, 'candidates')} · "
            f"Raw source candidates: {_raw_source_candidate_count(result)}"
        ),
        (
            "Delivery lanes: "
            f"due={lanes_due} · sent={lanes_sent} · "
            f"would_send_but_guard_disabled={lane_status['would_send_but_guard_disabled']} · "
            f"blocked_by_quality={lane_status['blocked_by_quality']} · "
            f"blocked_by_cooldown={lane_status['blocked_by_cooldown']} · "
            f"not_due={lane_status['not_due']}"
        ),
        f"Heartbeat: due={_yes_no(bool(_value(result, 'send_heartbeat_due', False)))} · sent={_yes_no(bool(_value(result, 'send_heartbeat_sent', False)))}",
        f"Provider issues: {_provider_failure_count(warnings)}",
        f"LLM calls/skips: {llm_calls}/{llm_skipped}",
        f"LLM budget: {'exhausted' if _runtime_budget_exhausted(warnings) else 'ok'}",
        f"Artifact doctor: {_esc(_value(result, 'artifact_doctor_status', 'not_run') if result is not None else 'not_run')}",
    ]
    if send_guard_status:
        lines.append(f"Send guard: {_esc(send_guard_status)}")
    if warnings:
        lines.append("Top issues: " + _esc("; ".join(_truncate_text(item, 90) for item in warnings[:3])))
    else:
        lines.append("Top issues: none")
    lines.append("Next: make event-alpha-notify-preview PROFILE=" + _esc(profile or "notify_no_key"))
    return "\n".join(lines)


def format_preview(
    *,
    profile: str,
    artifact_namespace: str,
    telegram_ready: bool,
    provider_ready_event_sources: int,
    provider_ready_enrichment_sources: int,
    llm_budget_status: str,
    plan: EventAlphaNotificationPlan,
    card_auto_write: bool,
    send_guard_enabled: bool = False,
    partial_results_allowed: bool = True,
    max_runtime_seconds: float = 120.0,
    provider_timeout_seconds: float = 5.0,
    fail_fast_on_dns: bool = True,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    clock_status: Mapping[str, Any] | None = None,
) -> str:
    provider_health_rows = provider_health_rows or {}
    clock_status = clock_status or {}
    disabled_rows = [
        f"{row.get('provider_key') or key} disabled_until={row.get('disabled_until')}"
        for key, row in provider_health_rows.items()
        if row.get("disabled_until")
    ]
    failure_count = sum(int(row.get("consecutive_failures") or 0) for row in provider_health_rows.values())
    fixed_clock_blocked = _fixed_clock_send_blocked(clock_status)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION PREVIEW (research-only / unvalidated)",
        "=" * 76,
        f"profile: {profile}",
        f"artifact_namespace: {artifact_namespace}",
        f"notification_scope: {plan.notification_scope}",
        f"notification_scope_value: {plan.scope_value}",
        f"telegram_ready: {'yes' if telegram_ready else 'no'}",
        "ready_to_preview: yes",
        f"ready_to_send_now: {'yes' if (telegram_ready and send_guard_enabled and not fixed_clock_blocked) else 'no'}",
        _format_clock_status(clock_status),
        f"partial_results_allowed: {'yes' if partial_results_allowed else 'no'}",
        f"max_runtime_seconds: {float(max_runtime_seconds or 0):g}",
        f"provider_timeout_seconds: {float(provider_timeout_seconds or 0):g}",
        f"fail_fast_on_dns: {'yes' if fail_fast_on_dns else 'no'}",
        f"provider_health_failures: {failure_count}",
        f"provider_health_backoff_count: {len(disabled_rows)}",
        (
            "event_source_readiness: "
            f"event_sources={provider_ready_event_sources} enrichment_sources={provider_ready_enrichment_sources}"
        ),
        f"LLM budget status: {llm_budget_status}",
        f"routed alertable decisions due: {plan.decision_count}",
        f"would_send_daily_digest: {'yes' if plan.lane_counts.get(LANE_DAILY_DIGEST, 0) else 'no'}",
        f"would_send_instant_alerts: {plan.lane_counts.get(LANE_INSTANT_ESCALATION, 0)}",
        f"would_send_triggered_fade: {plan.lane_counts.get(LANE_TRIGGERED_FADE, 0)}",
        f"would_send_research_review_digest: {plan.lane_counts.get(LANE_RESEARCH_REVIEW_DIGEST, 0)}",
        f"would_send_exploratory_digest: {plan.lane_counts.get(LANE_EXPLORATORY_DIGEST, 0)}",
        f"would_send_health_heartbeat: {'yes' if plan.heartbeat_due else 'no'}",
        f"research_card_auto_write: {'yes' if card_auto_write else 'no'}",
        "",
        "cooldowns:",
    ]
    for lane in LANES:
        status = plan.cooldown_status.get(lane, {})
        lines.append(
            f"- {lane}: due={'yes' if status.get('due') else 'no'} "
            f"sent_today={status.get('sent_today', 0)} "
            f"last={status.get('last_sent_at') or 'never'} "
            f"reason={status.get('reason') or 'unknown'} "
            f"meta_key={status.get('meta_key') or 'unknown'} "
            f"count_key={status.get('count_meta_key') or 'unknown'}"
        )
    if plan.migration_warnings:
        lines.append("")
        lines.append("migration warnings:")
        lines.extend(f"- {warning}" for warning in plan.migration_warnings)
    if plan.blocked_by_lane:
        lines.append("")
        lines.append("blocked lanes:")
        lines.extend(f"- {lane}: {reason}" for lane, reason in sorted(plan.blocked_by_lane.items()))
    if disabled_rows:
        lines.append("")
        lines.append("provider backoff:")
        lines.extend(f"- {row}" for row in disabled_rows[:10])
    clock_warnings = tuple(str(item) for item in clock_status.get("warnings", ()) or () if str(item))
    if clock_warnings:
        lines.append("")
        lines.append("clock warnings:")
        lines.extend(f"- {warning}" for warning in clock_warnings)
    lines.append("Preview does not send, trade, paper trade, write normal RSI signals, or alter tiers.")
    return "\n".join(lines).rstrip()


def _lane_for_decision(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    final_lane = event_alpha_router.final_lane_value(decision)
    if final_lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE.value:
        return LANE_TRIGGERED_FADE
    if final_lane == event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION.value:
        return LANE_INSTANT_ESCALATION
    if final_lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST.value:
        return LANE_DAILY_DIGEST
    return LANE_DAILY_DIGEST


def _cooldown_hours(lane: str, cfg: EventAlphaNotificationConfig) -> float:
    if lane == LANE_DAILY_DIGEST:
        return cfg.daily_digest_cooldown_hours
    if lane == LANE_INSTANT_ESCALATION:
        return cfg.instant_escalation_cooldown_hours
    if lane == LANE_RESEARCH_REVIEW_DIGEST:
        return cfg.research_review_digest_cooldown_hours
    if lane == LANE_EXPLORATORY_DIGEST:
        return cfg.exploratory_digest_cooldown_hours
    if lane == LANE_HEALTH_HEARTBEAT:
        return cfg.health_heartbeat_cooldown_hours
    return 0.0


def _sent_count_today(
    storage: Any,
    lane: str,
    now: datetime,
    cfg: EventAlphaNotificationConfig | None = None,
) -> int:
    try:
        return int(storage.get_meta(_count_meta_key(lane, now, cfg)) or "0")
    except (TypeError, ValueError):
        return 0


def _count_meta_key(lane: str, now: datetime, cfg: EventAlphaNotificationConfig | None = None) -> str:
    suffix = {
        LANE_DAILY_DIGEST: "daily_digest",
        LANE_INSTANT_ESCALATION: "instant",
        LANE_TRIGGERED_FADE: "triggered",
        LANE_RESEARCH_REVIEW_DIGEST: "research_review",
        LANE_EXPLORATORY_DIGEST: "exploratory",
        LANE_HEALTH_HEARTBEAT: "health_heartbeat",
    }[_clean_lane(lane)]
    if cfg is not None and _clean_scope(cfg.notification_scope) != NOTIFICATION_SCOPE_GLOBAL:
        return f"event_alpha_notify:{_scope_value(cfg)}:sent_count:{suffix}:{now.date().isoformat()}"
    return f"event_alpha_sent_count_{suffix}_{now.date().isoformat()}"


def _triggered_alert_meta_key(alert_id: str, cfg: EventAlphaNotificationConfig | None = None) -> str:
    digest = hashlib.sha1(str(alert_id).encode("utf-8")).hexdigest()[:20]
    if cfg is not None and _clean_scope(cfg.notification_scope) != NOTIFICATION_SCOPE_GLOBAL:
        return f"event_alpha_notify:{_scope_value(cfg)}:triggered:{digest}"
    return f"event_alpha_sent_triggered_fade_alert_{digest}"


def _heartbeat_degraded(message: str) -> bool:
    text = str(message or "").casefold()
    return (
        "degraded=yes" in text
        or "partial_results=yes" in text
        or "runtime_budget_status=exhausted" in text
    )


def _last_sent_meta_key(lane: str, cfg: EventAlphaNotificationConfig) -> str:
    lane_key = _clean_lane(lane)
    if _clean_scope(cfg.notification_scope) == NOTIFICATION_SCOPE_GLOBAL:
        return LAST_SENT_META_KEYS[lane_key]
    return f"event_alpha_notify:{_scope_value(cfg)}:last_sent:{lane_key}"


def _clean_lane(lane: str) -> str:
    value = str(lane or "").strip().lower()
    if value not in LAST_SENT_META_KEYS:
        raise ValueError(f"unknown Event Alpha notification lane: {lane!r}")
    return value


def _clean_scope(scope: str) -> str:
    value = str(scope or "").strip().lower()
    return value if value in NOTIFICATION_SCOPES else NOTIFICATION_SCOPE_GLOBAL


def _scope_value(cfg: EventAlphaNotificationConfig) -> str:
    scope = _clean_scope(cfg.notification_scope)
    if scope == NOTIFICATION_SCOPE_GLOBAL:
        return NOTIFICATION_SCOPE_GLOBAL
    if scope == NOTIFICATION_SCOPE_PROFILE:
        return _clean_token(cfg.profile_name or cfg.artifact_namespace or "default")
    return _clean_token(cfg.artifact_namespace or cfg.profile_name or "default")


def _clean_token(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text).strip("._-")
    return text or "default"


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "clock: "
        f"mode={status.get('clock_mode') or 'unknown'} "
        f"research_now={status.get('research_now') or 'unknown'} "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'} "
        f"fixed_clock_age={age_text}"
    )


def _fixed_clock_send_blocked(status: Mapping[str, Any]) -> bool:
    if str(status.get("clock_mode") or "") != "fixed":
        return False
    age = status.get("fixed_clock_age_hours")
    try:
        hours = float(age)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return hours > 24.0 or hours < -1.0


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _value(result: Any | None, attr: str, default: Any = None) -> Any:
    if result is None:
        return default
    if isinstance(result, Mapping):
        return result.get(attr, default)
    return getattr(result, attr, default)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mapping_value(result: Any | None, attr: str) -> dict[str, Any]:
    value = _value(result, attr, {})
    return dict(value) if isinstance(value, Mapping) else {}


def _num(result: Any | None, attr: str) -> int:
    if attr == "llm_calls_attempted":
        explicit = _value(result, attr, None)
        if explicit is not None:
            return _safe_int(explicit)
        return _llm_stats_from_result(result)["calls_attempted"]
    if attr == "llm_skipped_due_budget":
        explicit = _value(result, attr, None)
        if explicit is not None:
            return _safe_int(explicit)
        return _llm_stats_from_result(result)["skipped_due_budget"]
    if attr == "core_opportunities":
        value = _value(result, "core_opportunities", None)
        if value is None:
            value = _value(result, "core_opportunity_rows_written", 0)
        return _safe_int(value)
    value = _value(result, attr, 0)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return _safe_int(_value(result, attr, 0))


def _raw_source_candidate_count(result: Any | None) -> int:
    for attr in ("raw_source_candidates", "source_candidates", "candidate_rows", "candidates"):
        value = _num(result, attr)
        if value:
            return value
    return 0


def _notification_preview_result(
    result: Any | None,
    *,
    plan: EventAlphaNotificationPlan,
    delivered_by_lane: Mapping[str, int] | None = None,
    block_reason: str | None = None,
) -> dict[str, Any]:
    delivered = dict(delivered_by_lane or {lane: 0 for lane in LANES})
    llm_stats = _llm_stats_from_result(result)
    warnings = tuple(str(item) for item in _value(result, "warnings") or () if str(item))
    return {
        "profile": _value(result, "profile"),
        "cycle_completed": bool(_value(result, "cycle_completed", result is not None)),
        "partial_results": bool(_value(result, "partial_results", False)),
        "warnings": warnings,
        "raw_events": _num(result, "raw_events"),
        "extraction_rows": _num(result, "extraction_rows"),
        "core_opportunity_rows_written": _num(result, "core_opportunities") or _num(result, "core_opportunity_rows_written"),
        "alertable": _num(result, "alertable"),
        "alerts": _num(result, "alerts"),
        "candidates": _num(result, "candidates") or _num(result, "research_candidates"),
        "raw_source_candidates": _raw_source_candidate_count(result),
        "send_lane_items_attempted": dict(plan.lane_counts),
        "send_lane_items_delivered": delivered,
        "send_would_send_items": int(plan.would_send_count or 0),
        "send_heartbeat_due": bool(plan.heartbeat_due),
        "send_heartbeat_sent": bool(delivered.get(LANE_HEALTH_HEARTBEAT, 0)),
        "send_block_reason": block_reason,
        "llm_calls_attempted": llm_stats["calls_attempted"],
        "llm_skipped_due_budget": llm_stats["skipped_due_budget"],
        "artifact_doctor_status": _value(result, "artifact_doctor_status", "not_run"),
    }


def _llm_stats_from_result(result: Any | None) -> dict[str, int]:
    explicit_calls = _value(result, "llm_calls_attempted", None)
    explicit_skips = _value(result, "llm_skipped_due_budget", None)
    if explicit_calls is not None or explicit_skips is not None:
        return {
            "calls_attempted": _safe_int(explicit_calls),
            "skipped_due_budget": _safe_int(explicit_skips),
        }
    stats = {"calls_attempted": 0, "skipped_due_budget": 0}
    rows: list[Any] = []
    for attr in ("extraction_rows", "catalyst_frame_rows", "relationship_rows"):
        value = _value(result, attr, ())
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            rows.extend(list(value))
    for row in rows:
        status = str(getattr(row, "cache_status", "") or "")
        if status == "miss":
            stats["calls_attempted"] += 1
        elif status == "skipped_budget":
            stats["skipped_due_budget"] += 1
        warnings = tuple(getattr(row, "warnings", ()) or ())
        if any("budget exhausted" in str(warning).casefold() for warning in warnings):
            stats["skipped_due_budget"] += 1
    return stats


def _delivery_lane_status(result: Any | None, *, send_guard_status: str | None) -> dict[str, int]:
    due = sum(_safe_int(value) for value in _mapping_value(result, "send_lane_items_attempted").values())
    sent = sum(_safe_int(value) for value in _mapping_value(result, "send_lane_items_delivered").values())
    remaining = max(0, max(_num(result, "send_would_send_items"), due) - sent)
    reason = " ".join(
        str(value or "")
        for value in (
            send_guard_status,
            _value(result, "send_block_reason"),
        )
    ).casefold()
    out = {
        "would_send_but_guard_disabled": 0,
        "blocked_by_quality": 0,
        "blocked_by_cooldown": 0,
        "not_due": 0,
    }
    if remaining <= 0:
        return out
    if "send guard is disabled" in reason or "event alerts disabled" in reason or "rsi_event_alerts_enabled" in reason:
        out["would_send_but_guard_disabled"] = remaining
    elif "quality" in reason:
        out["blocked_by_quality"] = remaining
    elif "cooldown" in reason or "duplicate" in reason:
        out["blocked_by_cooldown"] = remaining
    elif due <= 0:
        out["not_due"] = remaining
    return out


def _send_guard_status_line(reason: str, *, error_class: str = "guard_blocked") -> str:
    lower = str(reason or "").casefold()
    if error_class == "notifications_paused":
        return "Notifications paused: would send only after the local pause is cleared."
    if "no due notifications" in lower or "no digest candidates" in lower:
        return "No due notification lanes."
    if "event alerts disabled" in lower or "rsi_event_alerts_enabled" in lower:
        return "No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode."
    if "quality" in lower:
        return "Blocked by quality gate."
    if "cooldown" in lower or "duplicate" in lower:
        return "Blocked by cooldown or duplicate guard."
    return "Blocked by send guard."


def _blocked_preview_status_detail(reason: str, *, error_class: str = "guard_blocked") -> str:
    lower = str(reason or "").casefold()
    if error_class == "notifications_paused":
        return "blocked_by_send_guard"
    if "no due notifications" in lower or "no digest candidates" in lower:
        return "not_due"
    if "event alerts disabled" in lower or "rsi_event_alerts_enabled" in lower:
        return "would_send_but_guard_disabled"
    if "quality" in lower:
        return "blocked_by_quality_gate"
    if "cooldown" in lower or "duplicate" in lower:
        return "blocked_by_cooldown"
    return "blocked_by_send_guard"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _provider_failure_count(warnings: Iterable[str]) -> int:
    tokens = ("failed", "failure", "backoff", "rate limit", "timeout", "dns", "429")
    return sum(1 for warning in warnings if any(token in warning.casefold() for token in tokens))


def _runtime_budget_exhausted(warnings: Iterable[str]) -> bool:
    return any("notification_runtime_budget_exhausted" in warning for warning in warnings)
