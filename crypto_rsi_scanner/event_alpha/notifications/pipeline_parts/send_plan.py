"""Send-plan helpers for the notification pipeline."""

from __future__ import annotations

from .runtime import *

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

@dataclass
class _SendContext:
    storage: Any
    cfg: EventAlphaNotificationConfig
    send_fn: SendFn
    observed: datetime
    profile: str | None
    pipeline_result: Any | None
    card_map: dict[str, str | Path]
    plan: EventAlphaNotificationPlan
    writer: _DeliveryWriter | None

    @property
    def lane_attempts(self) -> dict[str, int]:
        return self.plan.lane_counts

    @property
    def would_send(self) -> int:
        return self.plan.would_send_count


@dataclass(frozen=True)
class _PreparedLaneSend:
    lane: str
    items: list[Any]
    message: str
    identity: DeliveryIdentity
    alert_ids: list[str]
    route_label: str


@dataclass
class _SendExecutionState:
    delivered_by_lane: dict[str, int] = field(default_factory=lambda: {lane: 0 for lane in LANES})
    attempted: bool = False
    block_reasons: list[str] = field(default_factory=list)

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
    context = _build_send_context(
        decisions,
        storage=storage,
        cfg=cfg,
        send_fn=send_fn,
        now=observed,
        profile=profile,
        pipeline_result=pipeline_result,
        card_path_by_alert_id=card_path_by_alert_id,
        include_health_heartbeat=include_health_heartbeat,
        core_opportunity_rows=core_opportunity_rows,
        delivery_cfg=delivery_cfg,
        run_id=run_id,
        namespace=namespace,
    )
    blocked = _blocked_send_result(context, pause_state=pause_state)
    if blocked is not None:
        return blocked
    if context.would_send <= 0:
        return _no_due_send_result(context)

    state = _SendExecutionState()
    _send_due_digest_lanes(context, state)
    _send_health_heartbeat(context, state)
    delivered = sum(state.delivered_by_lane.values())
    return _send_result(
        context,
        requested=True,
        attempted=state.attempted,
        success=delivered > 0 and not state.block_reasons,
        items_attempted=context.would_send,
        items_delivered=delivered,
        block_reason="; ".join(state.block_reasons) or None,
        lane_items_attempted=context.lane_attempts,
        lane_items_delivered=state.delivered_by_lane,
        would_send_items=context.would_send,
        heartbeat_sent=state.delivered_by_lane[LANE_HEALTH_HEARTBEAT] > 0,
    )


def _build_send_context(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    storage: Any,
    cfg: EventAlphaNotificationConfig,
    send_fn: SendFn,
    now: datetime,
    profile: str | None,
    pipeline_result: Any | None,
    card_path_by_alert_id: Mapping[str, str | Path] | None,
    include_health_heartbeat: bool,
    core_opportunity_rows: Iterable[Mapping[str, Any] | object],
    delivery_cfg: delivery.NotificationDeliveryConfig | None,
    run_id: str | None,
    namespace: str | None,
) -> _SendContext:
    plan = build_notification_plan(
        decisions,
        storage=storage,
        cfg=cfg,
        now=now,
        include_health_heartbeat=include_health_heartbeat,
        core_opportunity_rows=core_opportunity_rows,
    )
    writer = (
        _DeliveryWriter(delivery_cfg, run_id=run_id, profile=profile, namespace=namespace, now=now)
        if delivery_cfg is not None
        else None
    )
    return _SendContext(
        storage=storage,
        cfg=cfg,
        send_fn=send_fn,
        observed=now,
        profile=profile,
        pipeline_result=pipeline_result,
        card_map={str(key): value for key, value in (card_path_by_alert_id or {}).items()},
        plan=plan,
        writer=writer,
    )


def _send_result(context: _SendContext, **kwargs: Any) -> event_alpha_pipeline.EventAlphaSendResult:
    counts = context.writer.counts if context.writer else {}
    preview_rendered_items = sum(
        len(getattr(section.get("identity"), "notification_item_ids", ()) or ())
        for section in (context.writer.preview_sections if context.writer else ())
    )
    research_review_sent = kwargs.pop(
        "research_review_digest_sent",
        int((kwargs.get("lane_items_delivered") or {}).get(LANE_RESEARCH_REVIEW_DIGEST, 0)),
    )
    return event_alpha_pipeline.EventAlphaSendResult(
        heartbeat_due=context.plan.heartbeat_due,
        cooldown_blocks=dict(context.plan.blocked_by_lane),
        notification_scope=context.plan.notification_scope,
        notification_scope_value=context.plan.scope_value,
        delivery_records_written=int(counts.get("records", 0)),
        deliveries_delivered=int(counts.get(delivery.STATE_DELIVERED, 0)),
        deliveries_partial_delivered=int(counts.get(delivery.STATE_PARTIAL_DELIVERED, 0)),
        deliveries_failed=int(counts.get(delivery.STATE_FAILED, 0)),
        deliveries_skipped_duplicate=int(counts.get(delivery.STATE_SKIPPED_DUPLICATE, 0)),
        deliveries_skipped_in_flight=int(counts.get(delivery.STATE_SKIPPED_IN_FLIGHT, 0)),
        deliveries_blocked=int(counts.get(delivery.STATE_BLOCKED, 0)),
        research_review_digest_enabled=bool(context.cfg.research_review_digest_enabled),
        research_review_digest_candidates=len(context.plan.research_review_items),
        research_review_digest_would_send=int(context.lane_attempts.get(LANE_RESEARCH_REVIEW_DIGEST, 0)),
        research_review_digest_sent=int(research_review_sent or 0),
        research_review_digest_block_reason=context.plan.blocked_by_lane.get(LANE_RESEARCH_REVIEW_DIGEST),
        preview_rendered_items=preview_rendered_items,
        **kwargs,
    )


def _blocked_send_result(
    context: _SendContext,
    *,
    pause_state: Any | None,
) -> event_alpha_pipeline.EventAlphaSendResult | None:
    if not context.cfg.enabled or context.cfg.mode != "research_only":
        block_reason = "event alerts disabled" if not context.cfg.enabled else "event alert mode is not research_only"
        _record_blocked_send(context, block_reason=block_reason)
        return _send_result(
            context,
            requested=True,
            attempted=False,
            items_attempted=context.would_send,
            items_delivered=0,
            block_reason=block_reason,
            lane_items_attempted=context.lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=context.would_send,
        )
    if bool(getattr(pause_state, "paused", False)):
        reason = str(getattr(pause_state, "reason", "") or "notifications paused")
        block_reason = f"notifications paused: {reason}"
        _record_blocked_send(context, block_reason=block_reason, error_class="notifications_paused")
        return _send_result(
            context,
            requested=True,
            attempted=False,
            items_attempted=context.would_send,
            items_delivered=0,
            block_reason=block_reason,
            lane_items_attempted=context.lane_attempts,
            lane_items_delivered={lane: 0 for lane in LANES},
            would_send_items=context.would_send,
        )
    return None


def _record_blocked_send(
    context: _SendContext,
    *,
    block_reason: str,
    error_class: str | None = None,
) -> None:
    if not context.writer:
        return
    kwargs = {
        "profile": context.profile,
        "card_map": context.card_map,
        "reason": block_reason,
        "pipeline_result": _notification_preview_result(
            context.pipeline_result,
            plan=context.plan,
            block_reason=block_reason,
        ),
    }
    if error_class is not None:
        kwargs["error_class"] = error_class
    context.writer.record_blocked(context.plan, **kwargs)
    if not context.writer.preview_sections:
        context.writer.write_no_digest_preview(
            profile=context.profile,
            pipeline_result=_notification_preview_result(
                context.pipeline_result,
                plan=context.plan,
                block_reason=block_reason,
            ),
            reason=block_reason,
        )


def _no_due_send_result(context: _SendContext) -> event_alpha_pipeline.EventAlphaSendResult:
    reason = "; ".join(context.plan.blocked_by_lane.values()) or context.plan.heartbeat_reason or "no due notifications"
    if context.writer:
        context.writer.write_no_digest_preview(
            profile=context.profile,
            pipeline_result=_notification_preview_result(context.pipeline_result, plan=context.plan, block_reason=reason),
            reason=reason,
        )
    return _send_result(
        context,
        requested=True,
        attempted=False,
        items_attempted=0,
        items_delivered=0,
        block_reason=reason,
        lane_items_attempted=context.lane_attempts,
        lane_items_delivered={lane: 0 for lane in LANES},
        would_send_items=0,
    )


def _send_due_digest_lanes(context: _SendContext, state: _SendExecutionState) -> None:
    for lane in (
        LANE_TRIGGERED_FADE,
        LANE_INSTANT_ESCALATION,
        LANE_DAILY_DIGEST,
        LANE_RESEARCH_REVIEW_DIGEST,
        LANE_EXPLORATORY_DIGEST,
    ):
        prepared = _prepare_lane_send(context, lane)
        if prepared is None:
            continue
        _write_lane_preview(context, prepared)
        if _skip_duplicate_lane(context, prepared):
            continue
        state.attempted = True
        _record_lane_sending(context, prepared)
        attempt = _call_send_fn(context.send_fn, prepared.message)
        _handle_lane_attempt_result(context, state, prepared, attempt, block_label=prepared.lane)


def _prepare_lane_send(context: _SendContext, lane: str) -> _PreparedLaneSend | None:
    research_review = lane == LANE_RESEARCH_REVIEW_DIGEST
    exploratory = lane == LANE_EXPLORATORY_DIGEST
    if research_review:
        items = list(context.plan.research_review_items)
    else:
        items = list(context.plan.exploratory_items if exploratory else context.plan.decisions_by_lane.get(lane, []))
    if not items:
        return None
    if research_review:
        message = format_research_review_telegram_digest(
            items,
            profile=context.profile,
            card_path_by_alert_id=context.card_map,
            core_row_by_alert_id=context.plan.core_row_by_alert_id,
            cfg=context.cfg,
            eligible_count=context.plan.research_review_eligible_count,
            skipped_items=context.plan.research_review_skipped_items,
        )
        decisions = [item.decision for item in items]
        route_label = "RESEARCH_REVIEW_DIGEST"
    elif exploratory:
        message = format_exploratory_telegram_digest(
            items,
            profile=context.profile,
            card_path_by_alert_id=context.card_map,
            cfg=context.cfg,
        )
        decisions = [item.decision for item in items]
        route_label = "EXPLORATORY_DIGEST"
    else:
        message = format_core_opportunity_telegram_digest(
            items,
            profile=context.profile,
            card_path_by_alert_id=context.card_map,
            core_row_by_alert_id=context.plan.core_row_by_alert_id,
            pipeline_result=context.pipeline_result,
            max_items=context.cfg.daily_digest_max_items if lane == LANE_DAILY_DIGEST else None,
        )
        decisions = items
        route_label = _route_label(items)
    identity = _delivery_identity_for_decisions(
        decisions,
        core_row_by_alert_id=context.plan.core_row_by_alert_id,
        card_path_by_alert_id=context.card_map,
        lane=lane,
        preview_path=context.writer.preview_path if context.writer else None,
    )
    return _PreparedLaneSend(
        lane=lane,
        items=items,
        message=message,
        identity=identity,
        alert_ids=list(identity.notification_item_ids),
        route_label=route_label,
    )


def _write_lane_preview(context: _SendContext, prepared: _PreparedLaneSend) -> None:
    if context.writer:
        context.writer.write_preview(
            message=prepared.message,
            lane=prepared.lane,
            route=prepared.route_label,
            identity=prepared.identity,
            would_send=True,
            sent=False,
        )


def _skip_duplicate_lane(context: _SendContext, prepared: _PreparedLaneSend) -> bool:
    return bool(
        context.writer
        and context.writer.skip_as_duplicate(
            message=prepared.message,
            lane=prepared.lane,
            alert_ids=prepared.alert_ids,
            route=prepared.route_label,
            identity=prepared.identity,
        )
    )


def _record_lane_sending(context: _SendContext, prepared: _PreparedLaneSend) -> None:
    if not context.writer:
        return
    context.writer.record_planned(
        message=prepared.message,
        lane=prepared.lane,
        alert_ids=prepared.alert_ids,
        route=prepared.route_label,
        identity=prepared.identity,
    )
    context.writer.record_sending(
        message=prepared.message,
        lane=prepared.lane,
        alert_ids=prepared.alert_ids,
        route=prepared.route_label,
        identity=prepared.identity,
    )


def _send_health_heartbeat(context: _SendContext, state: _SendExecutionState) -> None:
    if not context.plan.heartbeat_due:
        return
    prepared = _prepare_heartbeat_send(context, state.delivered_by_lane)
    _write_lane_preview(context, prepared)
    # Same delivery-ledger dedupe as the digest lanes for idempotency. In
    # practice the heartbeat carries a timestamp so its content hash differs
    # each run, but this keeps every lane consistently deduped.
    if _skip_duplicate_lane(context, prepared):
        return
    state.attempted = True
    _record_lane_sending(context, prepared)
    attempt = _call_send_fn(context.send_fn, prepared.message)
    _handle_lane_attempt_result(context, state, prepared, attempt, block_label="health_heartbeat")


def _prepare_heartbeat_send(
    context: _SendContext,
    delivered_by_lane: Mapping[str, int],
) -> _PreparedLaneSend:
    heartbeat_message = format_health_heartbeat(
        profile=context.profile,
        result=_notification_preview_result(
            context.pipeline_result,
            plan=context.plan,
            delivered_by_lane=delivered_by_lane,
        ),
        now=context.observed,
    )
    heartbeat_identity = DeliveryIdentity(
        notification_item_ids=("heartbeat",),
        source_alert_ids=("heartbeat",),
        requested_alert_id="heartbeat",
        alert_id="heartbeat",
        identity_reconciled=False,
        identity_reconciliation_reason="heartbeat",
        notification_preview_path=str(context.writer.preview_path) if context.writer else None,
        notification_preview_relpath=delivery.notification_preview_relpath_for_path(
            context.writer.preview_path if context.writer else None
        ),
    )
    return _PreparedLaneSend(
        lane=LANE_HEALTH_HEARTBEAT,
        items=["heartbeat"],
        message=heartbeat_message,
        identity=heartbeat_identity,
        alert_ids=["heartbeat"],
        route_label="HEALTH_HEARTBEAT",
    )


def _handle_lane_attempt_result(
    context: _SendContext,
    state: _SendExecutionState,
    prepared: _PreparedLaneSend,
    attempt: sender.NotificationSendAttemptResult,
    *,
    block_label: str,
) -> None:
    terminal_state = delivery.state_for_send_counts(
        delivered_count=attempt.delivered_count,
        failed_count=attempt.failed_count,
    )
    partial_marks_cooldown = bool(context.writer.cfg.partial_marks_cooldown) if context.writer else True
    if terminal_state == delivery.STATE_DELIVERED:
        state.delivered_by_lane[prepared.lane] = len(prepared.items)
        _record_lane_sent_for_attempt(context, prepared)
    elif terminal_state == delivery.STATE_PARTIAL_DELIVERED:
        state.block_reasons.append(
            f"{block_label}: partial delivery ({attempt.delivered_count}/{attempt.recipient_count} recipient(s))"
        )
        if partial_marks_cooldown:
            _record_lane_sent_for_attempt(context, prepared)
    else:
        state.block_reasons.append(f"{block_label}: {attempt.error_message_safe or 'no channel delivered'}")
    if context.writer:
        context.writer.record_attempt_result(
            message=prepared.message,
            lane=prepared.lane,
            alert_ids=prepared.alert_ids,
            route=prepared.route_label,
            attempt=attempt,
            identity=prepared.identity,
        )
        context.writer.mark_preview_attempt(
            lane=prepared.lane,
            identity=prepared.identity,
            attempt=attempt,
        )


def _record_lane_sent_for_attempt(context: _SendContext, prepared: _PreparedLaneSend) -> None:
    record_lane_sent(
        context.storage,
        prepared.lane,
        item_count=len(prepared.items),
        now=context.observed,
        alert_ids=prepared.alert_ids,
        cfg=context.cfg,
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

__all__ = (
    'lane_due',
    'cooldown_status_by_lane',
    'record_lane_sent',
    'send_notifications',
    '_call_send_fn',
    '_delivery_identity_for_decisions',
    '_identity_record_fields',
)
