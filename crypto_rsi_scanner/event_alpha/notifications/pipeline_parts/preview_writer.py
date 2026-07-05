"""Preview writer for the notification pipeline."""

from __future__ import annotations

from .runtime import *

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
    record_delivery_rows: bool = False,
    delivery_row_not_written_reason: str | None = "preview_command",
) -> None:
    """Write a full read-only preview for every due lane in ``plan``."""

    card_map = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    wrote_section = False
    section_status = status or "would_send"
    for lane in _notification_preview_lanes():
        wrote_section = _write_plan_lane_preview(
            plan,
            lane=lane,
            writer=writer,
            profile=profile,
            cfg=cfg,
            pipeline_result=pipeline_result,
            card_map=card_map,
            section_status=section_status,
            record_delivery_rows=record_delivery_rows,
            delivery_row_not_written_reason=delivery_row_not_written_reason,
        ) or wrote_section

    if plan.heartbeat_due:
        _write_heartbeat_preview(
            plan,
            writer=writer,
            profile=profile,
            pipeline_result=pipeline_result,
            send_guard_status=send_guard_status,
            section_status=section_status,
            record_delivery_rows=record_delivery_rows,
            delivery_row_not_written_reason=delivery_row_not_written_reason,
        )
        wrote_section = True

    if not wrote_section:
        reason = "; ".join(plan.blocked_by_lane.values()) or plan.heartbeat_reason or "no due notifications"
        writer.write_no_digest_preview(
            profile=profile,
            pipeline_result=_notification_preview_result(pipeline_result, plan=plan, block_reason=reason),
            reason=reason,
        )


def _notification_preview_lanes() -> tuple[str, ...]:
    return (
        LANE_TRIGGERED_FADE,
        LANE_INSTANT_ESCALATION,
        LANE_DAILY_DIGEST,
        LANE_RESEARCH_REVIEW_DIGEST,
        LANE_EXPLORATORY_DIGEST,
    )


def _plan_items_for_preview_lane(
    plan: EventAlphaNotificationPlan,
    lane: str,
) -> tuple[list[Any], bool, bool]:
    research_review = lane == LANE_RESEARCH_REVIEW_DIGEST
    exploratory = lane == LANE_EXPLORATORY_DIGEST
    if research_review:
        return list(plan.research_review_items), research_review, exploratory
    if exploratory:
        return list(plan.exploratory_items), research_review, exploratory
    return list(plan.decisions_by_lane.get(lane, [])), research_review, exploratory


def _preview_lane_payload(
    plan: EventAlphaNotificationPlan,
    lane: str,
    *,
    items: list[Any],
    research_review: bool,
    exploratory: bool,
    writer: "_DeliveryWriter",
    profile: str | None,
    cfg: EventAlphaNotificationConfig,
    pipeline_result: Any | None,
    card_map: Mapping[str, str | Path],
) -> tuple[str, DeliveryIdentity, str]:
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
        identity_items = [item.decision for item in items]
        route_label = "RESEARCH_REVIEW_DIGEST"
    elif exploratory:
        message = format_exploratory_telegram_digest(
            items,
            profile=profile,
            card_path_by_alert_id=card_map,
            cfg=cfg,
        )
        identity_items = [item.decision for item in items]
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
        identity_items = items
        route_label = _route_label(items)
    identity = _delivery_identity_for_decisions(
        identity_items,
        core_row_by_alert_id=plan.core_row_by_alert_id,
        card_path_by_alert_id=card_map,
        lane=lane,
        preview_path=writer.preview_path,
    )
    return message, identity, route_label


def _append_preview_delivery_row(
    *,
    writer: "_DeliveryWriter",
    message: str,
    lane: str,
    route: str,
    identity: DeliveryIdentity,
    error_message: str | None,
    channel_summary: Mapping[str, Any] | None = None,
) -> None:
    alert_ids = list(identity.notification_item_ids)
    dedupe_key, dedupe_bucket = writer._dedupe_key(message, lane, alert_ids)
    writer._append(
        alert_ids=alert_ids,
        lane=lane,
        route=route,
        content_hash=writer._hash(message, lane, alert_ids),
        dedupe_key=dedupe_key,
        dedupe_bucket=dedupe_bucket,
        state=delivery.STATE_BLOCKED,
        identity=identity,
        error_class="preview_only",
        error_message=error_message or "preview_command",
        delivery_mode=delivery.DELIVERY_MODE_PREVIEW_ONLY,
        delivery_state=delivery.DELIVERY_STATE_PREVIEW,
        status_detail=delivery.STATUS_DETAIL_PREVIEW_ONLY,
        send_guard_enabled=False,
        would_send=True,
        sent=False,
        failed=False,
        channel_summary=channel_summary,
    )


def _write_plan_lane_preview(
    plan: EventAlphaNotificationPlan,
    *,
    lane: str,
    writer: "_DeliveryWriter",
    profile: str | None,
    cfg: EventAlphaNotificationConfig,
    pipeline_result: Any | None,
    card_map: Mapping[str, str | Path],
    section_status: str,
    record_delivery_rows: bool,
    delivery_row_not_written_reason: str | None,
) -> bool:
    items, research_review, exploratory = _plan_items_for_preview_lane(plan, lane)
    if not items:
        return False
    message, identity, route_label = _preview_lane_payload(
        plan,
        lane,
        items=items,
        research_review=research_review,
        exploratory=exploratory,
        writer=writer,
        profile=profile,
        cfg=cfg,
        pipeline_result=pipeline_result,
        card_map=card_map,
    )
    writer.write_preview(
        message=message,
        lane=lane,
        route=route_label,
        identity=identity,
        would_send=True,
        sent=False,
        status=section_status,
        preview_only=not record_delivery_rows,
        delivery_row_not_written_reason=delivery_row_not_written_reason if not record_delivery_rows else None,
    )
    if record_delivery_rows:
        _append_preview_delivery_row(
            writer=writer,
            message=message,
            lane=lane,
            route=route_label,
            identity=identity,
            error_message=delivery_row_not_written_reason,
            channel_summary=_research_review_channel_summary(plan) if research_review else None,
        )
    return True


def _heartbeat_identity(writer: "_DeliveryWriter") -> DeliveryIdentity:
    return DeliveryIdentity(
        notification_item_ids=("heartbeat",),
        source_alert_ids=("heartbeat",),
        requested_alert_id="heartbeat",
        alert_id="heartbeat",
        identity_reconciled=False,
        identity_reconciliation_reason="heartbeat",
        notification_preview_path=str(writer.preview_path),
        notification_preview_relpath=delivery.notification_preview_relpath_for_path(writer.preview_path),
    )


def _heartbeat_preview_message(
    plan: EventAlphaNotificationPlan,
    *,
    profile: str | None,
    pipeline_result: Any | None,
    writer: "_DeliveryWriter",
    send_guard_status: str | None,
) -> str:
    return format_health_heartbeat(
        profile=profile,
        result=_notification_preview_result(
            pipeline_result,
            plan=plan,
            delivered_by_lane={lane: 0 for lane in LANES},
        ),
        now=writer.now,
        send_guard_status=send_guard_status,
    )


def _write_heartbeat_preview(
    plan: EventAlphaNotificationPlan,
    *,
    writer: "_DeliveryWriter",
    profile: str | None,
    pipeline_result: Any | None,
    send_guard_status: str | None,
    section_status: str,
    record_delivery_rows: bool,
    delivery_row_not_written_reason: str | None,
) -> None:
    heartbeat_identity = _heartbeat_identity(writer)
    message = _heartbeat_preview_message(
        plan,
        profile=profile,
        pipeline_result=pipeline_result,
        writer=writer,
        send_guard_status=send_guard_status,
    )
    writer.write_preview(
        message=message,
        lane=LANE_HEALTH_HEARTBEAT,
        route="HEALTH_HEARTBEAT",
        identity=heartbeat_identity,
        would_send=True,
        sent=False,
        status=section_status,
        preview_only=not record_delivery_rows,
        delivery_row_not_written_reason=delivery_row_not_written_reason if not record_delivery_rows else None,
    )
    if record_delivery_rows:
        _append_preview_delivery_row(
            writer=writer,
            message=message,
            lane=LANE_HEALTH_HEARTBEAT,
            route="HEALTH_HEARTBEAT",
            identity=heartbeat_identity,
            error_message=delivery_row_not_written_reason,
        )

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

__all__ = (
    'write_notification_plan_preview',
    '_preview_summary_lines',
    '_preview_path_label',
    'format_preview',
    '_notification_preview_result',
    '_llm_stats_from_result',
    '_delivery_lane_status',
    '_send_guard_status_line',
    '_blocked_preview_status_detail',
    '_yes_no',
)
