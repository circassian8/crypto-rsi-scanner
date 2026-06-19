"""Day-1 notification helpers for Event Alpha research alerts.

This module owns delivery state only. It does not rank alerts, mutate
watchlist state, create trades, paper trade, or write normal RSI signal rows.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import event_alpha_pipeline, event_alpha_router

LANE_DAILY_DIGEST = "daily_digest"
LANE_INSTANT_ESCALATION = "instant_escalation"
LANE_TRIGGERED_FADE = "triggered_fade"
LANE_HEALTH_HEARTBEAT = "health_heartbeat"

LANES = (
    LANE_DAILY_DIGEST,
    LANE_INSTANT_ESCALATION,
    LANE_TRIGGERED_FADE,
    LANE_HEALTH_HEARTBEAT,
)

LAST_SENT_META_KEYS = {
    LANE_DAILY_DIGEST: "event_alpha_last_sent_daily_digest_at",
    LANE_INSTANT_ESCALATION: "event_alpha_last_sent_instant_escalation_at",
    LANE_TRIGGERED_FADE: "event_alpha_last_sent_triggered_fade_at",
    LANE_HEALTH_HEARTBEAT: "event_alpha_last_sent_health_heartbeat_at",
}


@dataclass(frozen=True)
class EventAlphaNotificationConfig:
    enabled: bool = False
    mode: str = "research_only"
    daily_digest_cooldown_hours: float = 12.0
    instant_escalation_cooldown_hours: float = 1.0
    max_instant_per_day: int = 3
    health_heartbeat_enabled: bool = True
    health_heartbeat_cooldown_hours: float = 24.0
    triggered_fade_dedupe: bool = True


@dataclass(frozen=True)
class EventAlphaNotificationPlan:
    decisions_by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = field(default_factory=dict)
    blocked_by_lane: dict[str, str] = field(default_factory=dict)
    heartbeat_due: bool = False
    heartbeat_reason: str = "heartbeat disabled"
    cooldown_status: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def decision_count(self) -> int:
        return sum(len(items) for items in self.decisions_by_lane.values())

    @property
    def would_send_count(self) -> int:
        return self.decision_count + (1 if self.heartbeat_due else 0)

    @property
    def lane_counts(self) -> dict[str, int]:
        counts = {lane: len(self.decisions_by_lane.get(lane, ())) for lane in LANES}
        counts[LANE_HEALTH_HEARTBEAT] = 1 if self.heartbeat_due else 0
        return counts


SendFn = Callable[[str], bool]


def build_notification_plan(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    storage: Any,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    include_health_heartbeat: bool = False,
) -> EventAlphaNotificationPlan:
    """Return lane-specific due decisions without mutating storage."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    alertable = [decision for decision in decisions if decision.alertable]
    by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = {lane: [] for lane in LANES}
    blocked: dict[str, str] = {}

    daily = [decision for decision in alertable if _lane_for_decision(decision) == LANE_DAILY_DIGEST]
    if daily:
        due, reason = lane_due(storage, LANE_DAILY_DIGEST, cfg=cfg, now=observed)
        if due:
            by_lane[LANE_DAILY_DIGEST] = daily
        else:
            blocked[LANE_DAILY_DIGEST] = reason

    instant = [decision for decision in alertable if _lane_for_decision(decision) == LANE_INSTANT_ESCALATION]
    if instant:
        due, reason = lane_due(storage, LANE_INSTANT_ESCALATION, cfg=cfg, now=observed)
        if due:
            remaining = max(0, cfg.max_instant_per_day - _sent_count_today(storage, LANE_INSTANT_ESCALATION, observed))
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

    heartbeat_due = False
    heartbeat_reason = "heartbeat disabled"
    if include_health_heartbeat and cfg.health_heartbeat_enabled:
        heartbeat_due, heartbeat_reason = lane_due(storage, LANE_HEALTH_HEARTBEAT, cfg=cfg, now=observed)
    elif include_health_heartbeat:
        heartbeat_reason = "health heartbeat disabled"

    by_lane = {lane: items for lane, items in by_lane.items() if items}
    return EventAlphaNotificationPlan(
        decisions_by_lane=by_lane,
        blocked_by_lane=blocked,
        heartbeat_due=heartbeat_due,
        heartbeat_reason=heartbeat_reason,
        cooldown_status=cooldown_status_by_lane(storage, cfg=cfg, now=observed),
    )


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
        if storage.get_meta(_triggered_alert_meta_key(alert_id)):
            return False, f"triggered fade already sent for {alert_id}"
        return True, "due"
    if lane_key == LANE_INSTANT_ESCALATION:
        sent_today = _sent_count_today(storage, lane_key, now)
        if cfg.max_instant_per_day >= 0 and sent_today >= cfg.max_instant_per_day:
            return False, f"daily instant cap reached ({cfg.max_instant_per_day})"
    cooldown = _cooldown_hours(lane_key, cfg)
    if cooldown <= 0:
        return True, "due"
    last_raw = storage.get_meta(LAST_SENT_META_KEYS[lane_key])
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
        rows[lane] = {
            "due": due,
            "reason": reason,
            "last_sent_at": storage.get_meta(LAST_SENT_META_KEYS[lane]),
            "sent_today": _sent_count_today(storage, lane, observed),
            "meta_key": LAST_SENT_META_KEYS[lane],
        }
    return rows


def record_lane_sent(
    storage: Any,
    lane: str,
    *,
    item_count: int,
    now: datetime,
    alert_ids: Iterable[str] = (),
) -> None:
    lane_key = _clean_lane(lane)
    storage.set_meta(LAST_SENT_META_KEYS[lane_key], now.isoformat())
    count_key = _count_meta_key(lane_key, now)
    storage.set_meta(count_key, str(_sent_count_today(storage, lane_key, now) + max(0, int(item_count or 0))))
    if lane_key == LANE_TRIGGERED_FADE:
        for alert_id in alert_ids:
            storage.set_meta(_triggered_alert_meta_key(alert_id), now.isoformat())


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
    include_health_heartbeat: bool = False,
) -> event_alpha_pipeline.EventAlphaSendResult:
    """Send lane-specific Event Alpha notifications when guards are satisfied."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    plan = build_notification_plan(
        decisions,
        storage=storage,
        cfg=cfg,
        now=observed,
        include_health_heartbeat=include_health_heartbeat,
    )
    lane_attempts = plan.lane_counts
    would_send = plan.would_send_count
    if not cfg.enabled:
        return event_alpha_pipeline.EventAlphaSendResult(
            requested=True,
            attempted=False,
            items_attempted=would_send,
            items_delivered=0,
            block_reason="event alerts disabled",
            lane_items_attempted=lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=would_send,
        )
    if cfg.mode != "research_only":
        return event_alpha_pipeline.EventAlphaSendResult(
            requested=True,
            attempted=False,
            items_attempted=would_send,
            items_delivered=0,
            block_reason="event alert mode is not research_only",
            lane_items_attempted=lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=would_send,
        )
    if would_send <= 0:
        reason = "; ".join(plan.blocked_by_lane.values()) or plan.heartbeat_reason or "no due notifications"
        return event_alpha_pipeline.EventAlphaSendResult(
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
    card_map = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST):
        items = plan.decisions_by_lane.get(lane, [])
        if not items:
            continue
        attempted = True
        message = event_alpha_router.format_routed_telegram_digest(
            items,
            profile=profile,
            card_path_by_alert_id=card_map,
        )
        if send_fn(message):
            delivered_by_lane[lane] = len(items)
            record_lane_sent(
                storage,
                lane,
                item_count=len(items),
                now=observed,
                alert_ids=[decision.alert_id for decision in items],
            )
        else:
            block_reasons.append(f"{lane}: no channel delivered")
    if plan.heartbeat_due:
        attempted = True
        if send_fn(format_health_heartbeat(profile=profile, result=pipeline_result, now=observed)):
            delivered_by_lane[LANE_HEALTH_HEARTBEAT] = 1
            record_lane_sent(storage, LANE_HEALTH_HEARTBEAT, item_count=1, now=observed)
        else:
            block_reasons.append("health_heartbeat: no channel delivered")

    delivered = sum(delivered_by_lane.values())
    return event_alpha_pipeline.EventAlphaSendResult(
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


def format_health_heartbeat(
    *,
    profile: str | None,
    result: Any | None = None,
    now: datetime | None = None,
) -> str:
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings = tuple(str(item) for item in getattr(result, "warnings", ()) or () if str(item))
    lines = [
        "<b>Event Alpha notification heartbeat</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"profile={_esc(profile or getattr(result, 'profile', None) or 'default')}",
        f"generated_at={_esc(observed.isoformat())}",
        (
            "run_stats: "
            f"raw_events={_num(result, 'raw_events')} "
            f"anomalies={_num(result, 'anomaly_lifecycle_entries')} "
            f"candidates={_num(result, 'candidates')} "
            f"watchlist={_num(result, 'watchlist_entries')} "
            f"alertable={_num(result, 'alertable')}"
        ),
        (
            "llm_budget: "
            f"extractions={_num(result, 'extractions')}/{len(getattr(result, 'extraction_rows', ()) or ())} "
            f"relationship_rows={len(getattr(result, 'relationship_rows', ()) or ())}"
        ),
    ]
    if warnings:
        lines.append("provider_warnings=" + _esc("; ".join(warnings[:5])))
    else:
        lines.append("provider_warnings=none")
    lines.append("next=make event-alpha-notify-preview PROFILE=" + _esc(profile or "notify_no_key"))
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
) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION PREVIEW (research-only / unvalidated)",
        "=" * 76,
        f"profile: {profile}",
        f"artifact_namespace: {artifact_namespace}",
        f"telegram_ready: {'yes' if telegram_ready else 'no'}",
        (
            "event_source_readiness: "
            f"event_sources={provider_ready_event_sources} enrichment_sources={provider_ready_enrichment_sources}"
        ),
        f"LLM budget status: {llm_budget_status}",
        f"routed alertable decisions due: {plan.decision_count}",
        f"would_send_daily_digest: {'yes' if plan.lane_counts.get(LANE_DAILY_DIGEST, 0) else 'no'}",
        f"would_send_instant_alerts: {plan.lane_counts.get(LANE_INSTANT_ESCALATION, 0)}",
        f"would_send_triggered_fade: {plan.lane_counts.get(LANE_TRIGGERED_FADE, 0)}",
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
            f"reason={status.get('reason') or 'unknown'}"
        )
    if plan.blocked_by_lane:
        lines.append("")
        lines.append("blocked lanes:")
        lines.extend(f"- {lane}: {reason}" for lane, reason in sorted(plan.blocked_by_lane.items()))
    lines.append("Preview does not send, trade, paper trade, write normal RSI signals, or alter tiers.")
    return "\n".join(lines).rstrip()


def _lane_for_decision(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    lane = decision.lane
    if lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE:
        return LANE_TRIGGERED_FADE
    if lane == event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION:
        return LANE_INSTANT_ESCALATION
    if lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST:
        return LANE_DAILY_DIGEST
    route = getattr(decision, "route", None)
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH:
        return LANE_TRIGGERED_FADE
    if route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH:
        return LANE_INSTANT_ESCALATION
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST:
        return LANE_DAILY_DIGEST
    return LANE_DAILY_DIGEST


def _cooldown_hours(lane: str, cfg: EventAlphaNotificationConfig) -> float:
    if lane == LANE_DAILY_DIGEST:
        return cfg.daily_digest_cooldown_hours
    if lane == LANE_INSTANT_ESCALATION:
        return cfg.instant_escalation_cooldown_hours
    if lane == LANE_HEALTH_HEARTBEAT:
        return cfg.health_heartbeat_cooldown_hours
    return 0.0


def _sent_count_today(storage: Any, lane: str, now: datetime) -> int:
    try:
        return int(storage.get_meta(_count_meta_key(lane, now)) or "0")
    except (TypeError, ValueError):
        return 0


def _count_meta_key(lane: str, now: datetime) -> str:
    suffix = {
        LANE_DAILY_DIGEST: "daily_digest",
        LANE_INSTANT_ESCALATION: "instant",
        LANE_TRIGGERED_FADE: "triggered",
        LANE_HEALTH_HEARTBEAT: "health_heartbeat",
    }[_clean_lane(lane)]
    return f"event_alpha_sent_count_{suffix}_{now.date().isoformat()}"


def _triggered_alert_meta_key(alert_id: str) -> str:
    digest = hashlib.sha1(str(alert_id).encode("utf-8")).hexdigest()[:20]
    return f"event_alpha_sent_triggered_fade_alert_{digest}"


def _clean_lane(lane: str) -> str:
    value = str(lane or "").strip().lower()
    if value not in LAST_SENT_META_KEYS:
        raise ValueError(f"unknown Event Alpha notification lane: {lane!r}")
    return value


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


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _num(result: Any | None, attr: str) -> int:
    try:
        return int(getattr(result, attr, 0) or 0)
    except (TypeError, ValueError):
        return 0
