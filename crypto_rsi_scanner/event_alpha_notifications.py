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
import re

from . import event_alpha_notification_delivery as delivery
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
    notification_scope: str = NOTIFICATION_SCOPE_GLOBAL
    scope_value: str = NOTIFICATION_SCOPE_GLOBAL
    migration_warnings: tuple[str, ...] = ()

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
        notification_scope=_clean_scope(cfg.notification_scope),
        scope_value=_scope_value(cfg),
        migration_warnings=legacy_meta_warnings(storage, cfg),
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
    include_health_heartbeat: bool = False,
    delivery_cfg: delivery.NotificationDeliveryConfig | None = None,
    run_id: str | None = None,
    namespace: str | None = None,
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
        return event_alpha_pipeline.EventAlphaSendResult(
            heartbeat_due=plan.heartbeat_due,
            cooldown_blocks=dict(plan.blocked_by_lane),
            notification_scope=plan.notification_scope,
            notification_scope_value=plan.scope_value,
            delivery_records_written=int(counts.get("records", 0)),
            deliveries_delivered=int(counts.get(delivery.STATE_DELIVERED, 0)),
            deliveries_failed=int(counts.get(delivery.STATE_FAILED, 0)),
            deliveries_skipped_duplicate=int(counts.get(delivery.STATE_SKIPPED_DUPLICATE, 0)),
            deliveries_blocked=int(counts.get(delivery.STATE_BLOCKED, 0)),
            **kwargs,
        )

    if not cfg.enabled or cfg.mode != "research_only":
        block_reason = "event alerts disabled" if not cfg.enabled else "event alert mode is not research_only"
        if writer:
            writer.record_blocked(plan, profile=profile, card_map=card_map, reason=block_reason)
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
    for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST):
        items = plan.decisions_by_lane.get(lane, [])
        if not items:
            continue
        message = event_alpha_router.format_routed_telegram_digest(
            items,
            profile=profile,
            card_path_by_alert_id=card_map,
        )
        alert_ids = [decision.alert_id for decision in items]
        if writer and writer.skip_as_duplicate(message=message, lane=lane, alert_ids=alert_ids, route=_route_label(items)):
            continue
        attempted = True
        if writer:
            writer.record_sending(message=message, lane=lane, alert_ids=alert_ids, route=_route_label(items))
        if send_fn(message):
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
                writer.record_delivered(message=message, lane=lane, alert_ids=alert_ids, route=_route_label(items), delivered_count=len(items))
        else:
            block_reasons.append(f"{lane}: no channel delivered")
            if writer:
                writer.record_failed(message=message, lane=lane, alert_ids=alert_ids, route=_route_label(items), error_message="no channel delivered")
    if plan.heartbeat_due:
        attempted = True
        heartbeat_message = format_health_heartbeat(profile=profile, result=pipeline_result, now=observed)
        if send_fn(heartbeat_message):
            delivered_by_lane[LANE_HEALTH_HEARTBEAT] = 1
            record_lane_sent(storage, LANE_HEALTH_HEARTBEAT, item_count=1, now=observed, cfg=cfg)
            if writer:
                writer.record_delivered(message=heartbeat_message, lane=LANE_HEALTH_HEARTBEAT, alert_ids=["heartbeat"], route="HEALTH_HEARTBEAT", delivered_count=1)
        else:
            block_reasons.append("health_heartbeat: no channel delivered")
            if writer:
                writer.record_failed(message=heartbeat_message, lane=LANE_HEALTH_HEARTBEAT, alert_ids=["heartbeat"], route="HEALTH_HEARTBEAT", error_message="no channel delivered")

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
        self.counts: dict[str, int] = {
            delivery.STATE_DELIVERED: 0,
            delivery.STATE_FAILED: 0,
            delivery.STATE_SKIPPED_DUPLICATE: 0,
            delivery.STATE_BLOCKED: 0,
            "records": 0,
        }

    def _joined(self, alert_ids: Iterable[str]) -> str:
        return ",".join(sorted(str(item) for item in alert_ids))

    def _hash(self, message: str, lane: str, alert_ids: Iterable[str]) -> str:
        return delivery.compute_content_hash(message, alert_id=self._joined(alert_ids), lane=lane, profile=self.profile)

    def _append(self, *, alert_ids: Iterable[str], lane: str, route: str, content_hash: str, state: str, **kwargs: Any) -> None:
        record = delivery.build_record(
            run_id=self.run_id,
            alert_id=self._joined(alert_ids),
            profile=self.profile,
            namespace=self.namespace,
            lane=lane,
            route=route,
            content_hash=content_hash,
            state=state,
            now=self.now,
            **kwargs,
        )
        row = delivery.append_delivery_record(record, path=self.cfg.path)
        self.existing.append(row)
        if state in self.counts:
            self.counts[state] += 1
        if state in delivery.TERMINAL_STATES:
            self.counts["records"] += 1

    def skip_as_duplicate(self, *, message: str, lane: str, alert_ids: list[str], route: str) -> bool:
        if not self.cfg.dedupe_by_content:
            return False
        content_hash = self._hash(message, lane, alert_ids)
        dup = delivery.find_recent_delivered(
            self.existing,
            content_hash=content_hash,
            namespace=self.namespace,
            now=self.now,
            window_hours=self.cfg.dedupe_window_hours,
        )
        if dup is None:
            return False
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=content_hash,
            state=delivery.STATE_SKIPPED_DUPLICATE,
            error_class="duplicate_content",
            error_message=f"duplicate within {self.cfg.dedupe_window_hours:g}h (prior delivered_at={dup.get('delivered_at')})",
        )
        return True

    def record_sending(self, *, message: str, lane: str, alert_ids: list[str], route: str) -> None:
        self._append(alert_ids=alert_ids, lane=lane, route=route, content_hash=self._hash(message, lane, alert_ids), state=delivery.STATE_SENDING)

    def record_delivered(self, *, message: str, lane: str, alert_ids: list[str], route: str, delivered_count: int) -> None:
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=self._hash(message, lane, alert_ids),
            state=delivery.STATE_DELIVERED,
            delivered_at=self.now,
            delivered_count=delivered_count,
            channel_summary={"channel": "telegram", "delivered_count": int(delivered_count)},
        )

    def record_failed(self, *, message: str, lane: str, alert_ids: list[str], route: str, error_message: str) -> None:
        self._append(
            alert_ids=alert_ids,
            lane=lane,
            route=route,
            content_hash=self._hash(message, lane, alert_ids),
            state=delivery.STATE_FAILED,
            error_class="send_failed",
            error_message=error_message,
        )

    def record_blocked(self, plan: "EventAlphaNotificationPlan", *, profile: str | None, card_map: dict[str, Any], reason: str) -> None:
        for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST):
            items = plan.decisions_by_lane.get(lane, [])
            if not items:
                continue
            message = event_alpha_router.format_routed_telegram_digest(items, profile=profile, card_path_by_alert_id=card_map)
            alert_ids = [decision.alert_id for decision in items]
            self._append(
                alert_ids=alert_ids,
                lane=lane,
                route=_route_label(items),
                content_hash=self._hash(message, lane, alert_ids),
                state=delivery.STATE_BLOCKED,
                error_class="guard_blocked",
                error_message=reason,
            )
        if plan.heartbeat_due:
            message = format_health_heartbeat(profile=profile)
            self._append(
                alert_ids=["heartbeat"],
                lane=LANE_HEALTH_HEARTBEAT,
                route="HEALTH_HEARTBEAT",
                content_hash=self._hash(message, LANE_HEALTH_HEARTBEAT, ["heartbeat"]),
                state=delivery.STATE_BLOCKED,
                error_class="guard_blocked",
                error_message=reason,
            )


def _route_label(items: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    for decision in items:
        route = getattr(decision, "route", None)
        if route is not None:
            return getattr(route, "value", str(route))
    return ""


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
) -> str:
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings = tuple(str(item) for item in getattr(result, "warnings", ()) or () if str(item))
    partial = bool(getattr(result, "partial_results", False) or _provider_failure_count(warnings) > 0)
    lines = [
        "<b>Event Alpha notification heartbeat</b>",
        "<i>Research-only / DAY-1 UNVALIDATED. Not a trade signal.</i>",
        "Validation status: DAY-1 UNVALIDATED",
        "Trading action: NONE",
        "Review before acting.",
        f"profile={_esc(profile or getattr(result, 'profile', None) or 'default')}",
        f"namespace={_esc(getattr(result, 'artifact_namespace', None) or 'default')}",
        f"generated_at={_esc(observed.isoformat())}",
        f"cycle_completed={_yes_no(bool(getattr(result, 'cycle_completed', result is not None)))}",
        f"degraded={_yes_no(partial)}",
        f"partial_results={_yes_no(partial)}",
        f"provider_failure_count={_provider_failure_count(warnings)}",
        f"runtime_budget_status={'exhausted' if _runtime_budget_exhausted(warnings) else 'ok'}",
        f"alertable_count={_num(result, 'alertable')}",
        f"artifact_doctor_status={_esc(getattr(result, 'artifact_doctor_status', 'not_run') if result is not None else 'not_run')}",
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
        lines.append("warnings_summary=" + _esc("; ".join(warnings[:5])))
    else:
        lines.append("warnings_summary=none")
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


def _num(result: Any | None, attr: str) -> int:
    try:
        return int(getattr(result, attr, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _provider_failure_count(warnings: Iterable[str]) -> int:
    tokens = ("failed", "failure", "backoff", "rate limit", "timeout", "dns", "429")
    return sum(1 for warning in warnings if any(token in warning.casefold() for token in tokens))


def _runtime_budget_exhausted(warnings: Iterable[str]) -> bool:
    return any("notification_runtime_budget_exhausted" in warning for warning in warnings)
