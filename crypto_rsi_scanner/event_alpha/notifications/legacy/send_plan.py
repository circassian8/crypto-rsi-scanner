"""Send Plan for the legacy notification pipeline."""

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

__all__ = (
    'lane_due',
    'cooldown_status_by_lane',
    'record_lane_sent',
    'send_notifications',
    '_call_send_fn',
    '_delivery_identity_for_decisions',
    '_identity_record_fields',
)
