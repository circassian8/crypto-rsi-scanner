"""Compact final pre-send check for Event Alpha Telegram rehearsals.

This module is read-only. It inspects existing notification rehearsal artifacts
and never sends Telegram messages, trades, paper trades, writes normal RSI rows,
or creates Event Alpha trigger state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import event_artifact_paths
from . import event_alpha_notification_delivery as delivery
from . import event_alpha_notification_go_no_go as go_no_go


@dataclass(frozen=True)
class EventAlphaTelegramFinalCheckResult:
    profile: str
    artifact_namespace: str
    status: str
    preview_path: str | None
    doctor_status: str
    would_send_lanes: tuple[str, ...]
    core_ids: tuple[str, ...]
    sends_performed: int
    provider_summary: str
    telegram_ready: bool
    send_guard_enabled: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    inspect_preview_command: str = ""
    real_send_command: str = ""


def build_final_check(
    *,
    go_no_go_result: go_no_go.EventAlphaNotificationGoNoGoResult,
    doctor_status: str,
    doctor_blockers: Iterable[str] = (),
    doctor_warnings: Iterable[str] = (),
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
) -> EventAlphaTelegramFinalCheckResult:
    """Build a compact final check from already-loaded local artifacts."""
    deliveries = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    latest_run_id = go_no_go_result.latest_run_id
    latest_deliveries = [
        row for row in delivery.latest_rows_by_delivery(deliveries)
        if not latest_run_id or str(row.get("run_id") or "") == latest_run_id
    ]
    blockers = list(go_no_go_result.blockers)
    warnings = [*go_no_go_result.warnings, *(str(item) for item in doctor_warnings)]
    blockers.extend(str(item) for item in doctor_blockers)
    stale_warning = any("pre-canonical notification delivery rows" in str(item) for item in warnings)
    if stale_warning:
        blockers.append("stale pre-canonical delivery rows detected; do not use this namespace for send-readiness")
    if str(doctor_status or "").upper() == "BLOCKED":
        blockers.append("strict artifact doctor status is BLOCKED")
    if not go_no_go_result.notification_preview_exists:
        blockers.append("notification preview is missing")
    if not go_no_go_result.delivery_rows_have_explicit_status:
        blockers.append("delivery rows are missing explicit delivery status")
    if go_no_go_result.canonical_delivery_identity is False:
        blockers.append("delivery rows are missing canonical core identity")
    if go_no_go_result.rejected_or_unconfirmed_selected:
        blockers.append("rejected-only or unconfirmed candidate selected")

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    status = go_no_go.RECOMMEND_NOT_READY if blockers else go_no_go_result.final_recommendation
    preview_path = go_no_go_result.notification_preview_path_resolved
    core_ids = _core_ids_from_deliveries(latest_deliveries) or _core_ids_from_rows(cores, latest_run_id=latest_run_id)
    sends_performed = sum(1 for row in latest_deliveries if bool(row.get("sent")))
    lanes = go_no_go_result.would_send_lanes or _would_send_lanes(latest_deliveries)
    provider_summary = (
        f"event_sources={go_no_go_result.provider_ready_event_sources} "
        f"enrichment={go_no_go_result.provider_ready_enrichment_sources} "
        f"backoff={go_no_go_result.provider_backoff_count}"
    )
    preview_label = event_artifact_paths.artifact_display_path(preview_path) if preview_path else ""
    inspect = f"sed -n '1,180p' {preview_label}" if preview_label else "run the fixture final check to create a preview"
    real_send = _real_send_command(go_no_go_result.profile)
    return EventAlphaTelegramFinalCheckResult(
        profile=go_no_go_result.profile,
        artifact_namespace=go_no_go_result.artifact_namespace,
        status=status,
        preview_path=preview_path,
        doctor_status=str(doctor_status or "unknown"),
        would_send_lanes=lanes,
        core_ids=core_ids,
        sends_performed=sends_performed,
        provider_summary=provider_summary,
        telegram_ready=go_no_go_result.telegram_ready,
        send_guard_enabled=go_no_go_result.send_guard_enabled,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        inspect_preview_command=inspect,
        real_send_command=real_send,
    )


def format_final_check(result: EventAlphaTelegramFinalCheckResult) -> str:
    """Return the compact operator-facing final-check summary."""
    lines = [
        "Final Telegram no-send check:",
        f"- status: {result.status}",
        f"- profile: {result.profile}",
        f"- artifact namespace: {result.artifact_namespace}",
        f"- preview: {event_artifact_paths.artifact_display_path(result.preview_path) if result.preview_path else 'missing'}",
        f"- doctor: {result.doctor_status}",
        f"- candidate count: {len(result.core_ids)}",
        f"- would-send lanes: {_join(result.would_send_lanes)}",
        f"- core IDs: {_join(result.core_ids)}",
        f"- sends performed: {result.sends_performed}",
        f"- providers: {result.provider_summary}",
        f"- provider warnings: {_provider_warning_summary(result.warnings)}",
        f"- telegram configured: {'yes' if result.telegram_ready else 'no'}",
        f"- send guard enabled: {'yes' if result.send_guard_enabled else 'no'}",
        f"- next command to inspect preview: {result.inspect_preview_command}",
        f"- next command to enable real send, if desired: {result.real_send_command}",
        "",
        "Blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("Warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append("Research-only check: no Telegram sends, trades, paper rows, normal RSI rows, or trigger creation.")
    return "\n".join(lines)


def _core_ids_from_deliveries(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    ids = []
    for row in rows:
        if _is_alert_lane(row) and bool(row.get("would_send")):
            ids.append(str(row.get("core_opportunity_id") or "").strip())
    return tuple(item for item in _dedupe(ids) if item)


def _core_ids_from_rows(rows: Iterable[Mapping[str, Any]], *, latest_run_id: str | None) -> tuple[str, ...]:
    ids = []
    for row in rows:
        if latest_run_id and str(row.get("run_id") or "") != latest_run_id:
            continue
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if route in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE"}:
            ids.append(str(row.get("core_opportunity_id") or "").strip())
    return tuple(item for item in _dedupe(ids) if item)


def _would_send_lanes(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    lanes = [
        str(row.get("lane") or "").strip()
        for row in rows
        if _is_alert_lane(row) and bool(row.get("would_send"))
    ]
    return tuple(item for item in _dedupe(lanes) if item)


def _is_alert_lane(row: Mapping[str, Any]) -> bool:
    return str(row.get("lane") or "") in {
        "daily_digest",
        "instant_escalation",
        "triggered_fade",
        "research_review_digest",
    }


def _real_send_command(profile: str) -> str:
    clean = str(profile or "notify_llm_deep")
    return f"RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 make event-alpha-telegram-send-one-cycle PROFILE={clean} PYTHON=python3"


def _provider_warning_summary(warnings: Iterable[str]) -> str:
    items = [
        str(item)
        for item in warnings
        if any(token in str(item).lower() for token in ("provider", "backoff", "source", "enrichment"))
    ]
    return f"{len(items)} warning(s)" if items else "none"


def _join(values: Iterable[str]) -> str:
    items = [str(value) for value in values if str(value or "").strip()]
    return ", ".join(items) if items else "none"


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value or "").strip()))
