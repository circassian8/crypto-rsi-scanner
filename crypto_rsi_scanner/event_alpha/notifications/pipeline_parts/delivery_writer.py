"""Delivery writer for the notification pipeline."""

from __future__ import annotations

from .runtime import *
from ...artifacts import operator_state as event_alpha_operator_state
from ...namespace import status as event_alpha_namespace_status

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
        self.preview_write_succeeded = False
        self.require_current_operator_generation = False
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
    extra_delivery_fields: dict[str, Any] = {}
    channel_summary = kwargs.get("channel_summary")
    if lane == LANE_RESEARCH_REVIEW_DIGEST and isinstance(channel_summary, Mapping):
        for key in (
            "eligible_candidate_count",
            "rendered_candidate_count",
            "skipped_candidate_count",
            "skip_reason_counts",
            "skipped_candidates_sample",
            "skipped_family_summary",
            "skipped_reason_counts",
            "skipped_family_count",
            "selection_policy",
            "max_items",
            "ranking_policy",
            "cooldown_policy",
            "rendered_candidate_ids",
            "rendered_core_opportunity_ids",
        ):
            if key in channel_summary:
                extra_delivery_fields[key] = channel_summary.get(key)
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
    if extra_delivery_fields:
        row = record.to_row()
        row.update(extra_delivery_fields)
        row = delivery.append_delivery_record(row, path=self.cfg.path)
    else:
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
    preview_only: bool = False,
    delivery_row_not_written_reason: str | None = None,
    send_requested: bool | None = None,
    send_attempted: bool | None = None,
    no_send_rehearsal: bool | None = None,
) -> None:
    """Write operator-visible Telegram bodies for all lanes in this run."""
    section_status = str(status or ("sent" if sent else "would_send"))
    if send_requested is None:
        send_requested = False if preview_only else bool(would_send)
    if send_attempted is None:
        if sent:
            send_attempted = True
        elif preview_only or section_status in {
            delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED,
            "blocked_by_send_guard",
            "no_digest_candidates",
            "not_due",
        }:
            send_attempted = False
    if no_send_rehearsal is None and send_attempted is not None:
        no_send_rehearsal = not send_attempted
    self.preview_sections.append(
        {
            "lane": lane,
            "route": route,
            "would_send": bool(would_send),
            "sent": bool(sent),
            "status": section_status,
            "identity": identity,
            "message": message,
            "preview_only": bool(preview_only),
            "delivery_row_not_written_reason": delivery_row_not_written_reason,
            "send_requested": send_requested,
            "send_attempted": send_attempted,
            "no_send_rehearsal": no_send_rehearsal,
        }
    )
    _persist_preview_sections(self)


def mark_preview_attempt(
    self,
    *,
    lane: str,
    identity: DeliveryIdentity,
    attempt: Any,
) -> None:
    """Rewrite one preview section with terminal delivery-attempt facts."""

    expected_ids = tuple(identity.notification_item_ids or ())
    for section in reversed(self.preview_sections):
        section_identity = section.get("identity")
        if str(section.get("lane") or "") != str(lane):
            continue
        if tuple(getattr(section_identity, "notification_item_ids", ()) or ()) != expected_ids:
            continue
        delivered = _safe_int(getattr(attempt, "delivered_count", 0))
        failed = _safe_int(getattr(attempt, "failed_count", 0))
        section["send_requested"] = True
        section["send_attempted"] = bool(getattr(attempt, "attempted", True))
        section["no_send_rehearsal"] = False
        section["sent"] = delivered > 0
        section["failed"] = failed > 0
        if delivered > 0 and failed > 0:
            section["status"] = "partial_delivery"
        elif delivered > 0:
            section["status"] = "sent"
        else:
            section["status"] = "delivery_failed"
        _persist_preview_sections(self)
        return


def _persist_preview_sections(self) -> None:
    body = [
        "# Event Alpha Notification Preview",
        "",
        f"generated_at: {self.now.isoformat()}",
        f"run_id: {self.run_id}",
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
                f"send_requested: {_preview_bool(section.get('send_requested'))}",
                f"send_attempted: {_preview_bool(section.get('send_attempted'))}",
                f"no_send_rehearsal: {_preview_bool(section.get('no_send_rehearsal'))}",
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
                f"preview_only: {str(bool(section.get('preview_only'))).lower()}",
                f"delivery_row_not_written_reason: {section.get('delivery_row_not_written_reason') or 'none'}",
                "",
                "### Telegram Body",
                "",
                "```html",
                str(section["message"]),
                "```",
            ]
        )
    preview_text = "\n".join(body) + "\n"
    if self.require_current_operator_generation:
        try:
            event_alpha_operator_state.write_text_artifact(
                self.preview_path.parent,
                run_id=self.run_id,
                profile=str(self.profile or "default"),
                artifact_namespace=str(self.namespace or self.preview_path.parent.name),
                name="notification_preview",
                path=self.preview_path,
                text=preview_text,
                updated_at=self.now,
            )
            self.preview_write_succeeded = True
        except (OSError, ValueError):
            self.preview_write_succeeded = False
        return
    try:
        self.preview_path.parent.mkdir(parents=True, exist_ok=True)
        self.preview_path.write_text(preview_text, encoding="utf-8")
        self.preview_write_succeeded = True
        _record_preview_operator_state(self)
    except OSError:
        self.preview_write_succeeded = False
        return


def _preview_bool(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else "unknown"


def _record_preview_operator_state(writer: _DeliveryWriter) -> None:
    loaded = event_alpha_operator_state.load_operator_state(writer.preview_path.parent)
    state = dict(loaded.state or {}) if loaded.valid else {}
    expected_profile = str(writer.profile or "default")
    expected_namespace = str(writer.namespace or writer.preview_path.parent.name)
    run_identity = {
        "run_id": writer.run_id,
        "profile": expected_profile,
        "artifact_namespace": expected_namespace,
    }
    if not event_alpha_operator_state.state_matches_run(
        state,
        run_identity,
        profile=expected_profile,
        artifact_namespace=expected_namespace,
    ):
        return
    try:
        event_alpha_operator_state.record_artifact(
            writer.preview_path.parent,
            run_id=writer.run_id,
            profile=expected_profile,
            artifact_namespace=expected_namespace,
            name="notification_preview",
            path=writer.preview_path,
            updated_at=writer.now,
        )
        event_alpha_namespace_status.refresh_namespace_status(
            writer.preview_path.parent,
            profile=expected_profile,
            artifact_namespace=expected_namespace,
            run_mode=str(state.get("run_mode") or ""),
            now=writer.now,
        )
    except (OSError, ValueError):
        return

def write_no_digest_preview(
    self,
    *,
    profile: str | None,
    pipeline_result: Any | None,
    reason: str,
    preview_only: bool = False,
) -> None:
    warnings = tuple(str(item) for item in _value(pipeline_result, "warnings") or () if str(item))
    counters = event_alpha_run_counters.canonical_run_counters(pipeline_result)
    send_state = event_alpha_run_counters.canonical_send_state(pipeline_result)
    lane_due = _mapping_value(pipeline_result, "send_lane_items_attempted")
    lane_sent = _mapping_value(pipeline_result, "send_lane_items_delivered")
    lanes_due = sum(_safe_int(value) for value in lane_due.values())
    lanes_sent = sum(_safe_int(value) for value in lane_sent.values())
    lines = [
        "<b>Event Alpha Notification Rehearsal</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"Profile: {_esc(profile or _value(pipeline_result, 'profile') or 'default')}",
        f"Burn-in mode: {_esc(send_state['burn_in_mode'])}",
        "Status: no digest candidates would be sent",
        f"Reason: {_esc(reason or 'no due notifications')}",
        f"Completed: {_yes_no(bool(_value(pipeline_result, 'cycle_completed', pipeline_result is not None)))}",
        (
            f"Raw events: {counters['raw_events']} · "
            f"Candidate events: {counters['candidate_events']} · "
            f"Research candidates: {counters['research_candidates']}"
        ),
        (
            f"Source alert snapshots: {counters['source_alert_snapshots']} · "
            f"Current-generation core rows: {counters['current_generation_core_rows']} · "
            f"Current-generation visible core rows: {counters['current_generation_visible_core_rows']} · "
            f"Cumulative store rows: {counters['cumulative_store_rows']}"
        ),
        f"Extraction rows: {_num(pipeline_result, 'extraction_rows')}",
        (
            f"Alertable decisions: {counters['alertable_decisions']} · "
            f"Strict alerts: {counters['strict_alerts']} · "
            f"Preview-rendered items: {counters['preview_rendered_items']}"
        ),
        f"Delivery lanes: due={lanes_due} · sent={lanes_sent} · blocked={max(0, _num(pipeline_result, 'send_would_send_items') - lanes_sent)}",
        f"Provider issues: {_provider_failure_count(warnings)}",
        f"LLM calls/skips: {_num(pipeline_result, 'llm_calls_attempted')}/{_num(pipeline_result, 'llm_skipped_due_budget')}",
        f"Send guard: {_send_guard_status_line(reason)}",
        (
            f"Send requested: {_yes_no(send_state['send_requested'])} · "
            f"attempted: {_yes_no(send_state['send_attempted'])} · "
            f"no-send rehearsal: {_yes_no(send_state['no_send_rehearsal'])}"
        ),
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
        preview_only=preview_only,
        send_requested=not preview_only,
        send_attempted=False,
        no_send_rehearsal=True,
    )


_DeliveryWriter._joined = _joined
_DeliveryWriter._hash = _hash
_DeliveryWriter._dedupe_bucket = _dedupe_bucket
_DeliveryWriter._dedupe_key = _dedupe_key
_DeliveryWriter._append = _append
_DeliveryWriter.skip_as_duplicate = skip_as_duplicate
_DeliveryWriter.record_planned = record_planned
_DeliveryWriter.record_sending = record_sending
_DeliveryWriter.record_attempt_result = record_attempt_result
_DeliveryWriter.record_blocked = record_blocked
_DeliveryWriter.write_preview = write_preview
_DeliveryWriter.mark_preview_attempt = mark_preview_attempt
_DeliveryWriter.write_no_digest_preview = write_no_digest_preview

__all__ = (
    '_DeliveryWriter',
)
