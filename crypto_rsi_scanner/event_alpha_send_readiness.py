"""Final send-readiness checks for Event Alpha notification rehearsals.

This module is read-only. It inspects local research artifacts before an
operator enables real Telegram delivery, and it never sends, trades, paper
trades, or writes normal RSI signal rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_artifact_doctor, event_alpha_artifacts, event_alpha_notification_delivery as delivery


@dataclass(frozen=True)
class EventAlphaSendReadinessResult:
    profile: str | None
    artifact_namespace: str | None
    latest_run_id: str | None
    ready: bool
    no_send_rehearsal: bool
    send_guard_enabled: bool
    telegram_ready: bool
    preview_path: str | None
    latest_run_completed: bool
    artifact_doctor_status: str
    alertable_items: int
    delivery_rows_checked: int
    core_rows_checked: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def build_send_readiness(
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_rows: Iterable[Mapping[str, Any]],
    core_opportunity_rows: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    artifact_doctor: event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult,
    send_guard_enabled: bool,
    telegram_ready: bool,
    preview_path: str | Path | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> EventAlphaSendReadinessResult:
    """Return a final read-only readiness verdict for a profile namespace."""
    runs = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in run_rows if isinstance(row, Mapping)],
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    core_rows = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)],
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in alert_rows if isinstance(row, Mapping)],
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    deliveries = _filter_delivery_rows(
        [dict(row) for row in delivery_rows if isinstance(row, Mapping)],
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    latest_run = _latest_run(runs)
    latest_run_id = str(latest_run.get("run_id") or "") if latest_run else None
    latest_deliveries = [
        row for row in delivery.latest_rows_by_delivery(deliveries)
        if not latest_run_id or str(row.get("run_id") or "") == latest_run_id
    ]
    resolved_preview = str(preview_path or _latest_preview_path(latest_deliveries) or "").strip() or None
    blockers: list[str] = []
    warnings: list[str] = []

    if latest_run is None:
        blockers.append("no latest Event Alpha run found for this profile/namespace")
    else:
        if not bool(latest_run.get("cycle_completed", latest_run.get("success", True))):
            blockers.append("latest run did not complete")
        if not bool(latest_run.get("success", True)):
            blockers.append("latest run is marked unsuccessful")

    if str(artifact_doctor.status or "").upper() == "BLOCKED" or artifact_doctor.blockers:
        blockers.append("strict artifact doctor has blockers")
    if artifact_doctor.notification_preview_missing:
        blockers.append("notification preview is missing")
    if (
        artifact_doctor.notification_preview_run_summary_mismatch
        or artifact_doctor.notification_preview_core_count_mismatch
        or artifact_doctor.notification_preview_alertable_count_mismatch
    ):
        blockers.append("notification preview summary does not match latest run artifacts")
    if artifact_doctor.notification_preview_missing_send_guard_status:
        blockers.append("notification preview is missing send/no-send guard status")
    if artifact_doctor.notification_preview_no_send_status_unclear:
        blockers.append("notification preview no-send/blocked wording is unclear")

    if not resolved_preview:
        blockers.append("notification preview path was not recorded")
    elif not Path(resolved_preview).expanduser().exists():
        blockers.append("notification preview path does not exist")

    if send_guard_enabled and not telegram_ready:
        blockers.append("Telegram token/chat id missing while send guard is enabled")
    if not send_guard_enabled:
        warnings.append("no-send rehearsal: send guard disabled; real Telegram sends remain blocked")

    latest_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows
        if not latest_run_id or str(row.get("run_id") or "") == latest_run_id
    }
    for row in latest_deliveries:
        lane = str(row.get("lane") or "")
        if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
            continue
        state = str(row.get("state") or "")
        if state not in {
            delivery.STATE_DELIVERED,
            delivery.STATE_PARTIAL_DELIVERED,
            delivery.STATE_BLOCKED,
            delivery.STATE_SKIPPED_DUPLICATE,
            delivery.STATE_SKIPPED_IN_FLIGHT,
        }:
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if not core_id:
            blockers.append("delivery row missing canonical core opportunity identity")
        elif latest_core_ids and core_id not in latest_core_ids:
            blockers.append("delivery row references core opportunity missing from core store")

    would_send_cores = [
        row for row in core_rows
        if (not latest_run_id or str(row.get("run_id") or "") == latest_run_id)
        and _route_is_alertable(row)
    ]
    for row in would_send_cores:
        if _core_is_rejected_or_unconfirmed(row):
            blockers.append(
                "alertable core lacks accepted/live confirmation: "
                + str(row.get("core_opportunity_id") or row.get("symbol") or "unknown")
            )
        if _route_value(row) == "TRIGGERED_FADE" and str(row.get("effective_playbook_type") or row.get("playbook_type") or "") != "proxy_fade":
            blockers.append("TRIGGERED_FADE core is not proxy_fade")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    completed = bool(latest_run.get("cycle_completed", latest_run is not None)) if latest_run else False
    return EventAlphaSendReadinessResult(
        profile=profile,
        artifact_namespace=artifact_namespace,
        latest_run_id=latest_run_id,
        ready=not blockers,
        no_send_rehearsal=not send_guard_enabled,
        send_guard_enabled=bool(send_guard_enabled),
        telegram_ready=bool(telegram_ready),
        preview_path=resolved_preview,
        latest_run_completed=completed,
        artifact_doctor_status=str(artifact_doctor.status or "unknown"),
        alertable_items=sum(1 for row in would_send_cores),
        delivery_rows_checked=len(latest_deliveries),
        core_rows_checked=len(core_rows),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def format_send_readiness(result: EventAlphaSendReadinessResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SEND READINESS (research artifact only)",
        "=" * 76,
        f"profile: {result.profile or 'default'}",
        f"namespace: {result.artifact_namespace or 'default'}",
        f"latest_run_id: {result.latest_run_id or 'none'}",
        f"READY_FOR_EVENT_ALPHA_SEND: {'yes' if result.ready and result.send_guard_enabled else 'no'}",
        f"READY_FOR_NO_SEND_REHEARSAL_REVIEW: {'yes' if result.ready and result.no_send_rehearsal else 'no'}",
        f"latest_run_completed: {'yes' if result.latest_run_completed else 'no'}",
        f"artifact_doctor_status: {result.artifact_doctor_status}",
        f"send_guard_enabled: {'yes' if result.send_guard_enabled else 'no'}",
        f"telegram_ready: {'yes' if result.telegram_ready else 'no'}",
        f"notification_preview_path: {result.preview_path or 'missing'}",
        f"alertable_items_checked: {result.alertable_items}",
        f"delivery_rows_checked: {result.delivery_rows_checked}",
        f"core_rows_checked: {result.core_rows_checked}",
        "",
        "Blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("Warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.extend([
        "",
        "Next:",
        "- If this is a rehearsal, inspect the notification preview, inbox, and daily brief.",
        "- Only enable RSI_EVENT_ALERTS_ENABLED=1 after the preview content is acceptable.",
    ])
    return "\n".join(lines)


def _latest_run(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted((dict(row) for row in rows), key=lambda row: str(row.get("started_at") or ""), reverse=True)
    return ordered[0] if ordered else None


def _filter_delivery_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    """Filter delivery rows without requiring run_mode on historical rows."""
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        if not include_test_artifacts and event_alpha_artifacts.is_non_operational_row(data):
            continue
        if not include_legacy_artifacts and _delivery_is_legacy(data):
            continue
        if profile_key is not None and _clean_optional(data.get("profile")) not in (None, profile_key):
            continue
        if namespace_key is not None:
            row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
            if row_ns != namespace_key:
                continue
        out.append(data)
    return out


def _delivery_is_legacy(row: Mapping[str, Any]) -> bool:
    namespace = _clean_optional(row.get("artifact_namespace") or row.get("namespace"))
    if namespace in (None, event_alpha_artifacts.LEGACY_NAMESPACE):
        return True
    return str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}


def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _latest_preview_path(rows: Iterable[Mapping[str, Any]]) -> str | None:
    candidates = [
        (str(row.get("attempted_at") or row.get("delivered_at") or ""), str(row.get("notification_preview_path") or ""))
        for row in rows
        if str(row.get("notification_preview_path") or "").strip()
    ]
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _route_value(row: Mapping[str, Any]) -> str:
    return str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()


def _route_is_alertable(row: Mapping[str, Any]) -> bool:
    return _route_value(row) in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE"}


def _core_is_rejected_or_unconfirmed(row: Mapping[str, Any]) -> bool:
    status = str(row.get("evidence_acquisition_status") or "")
    confirmation = str(row.get("acquisition_confirmation_status") or "")
    market = str(row.get("market_confirmation_level") or "").casefold()
    accepted = _as_int(row.get("accepted_evidence_count") or row.get("evidence_acquisition_accepted_count"))
    source_class = str(row.get("source_class") or "").casefold()
    if accepted > 0 or confirmation == "confirms":
        return False
    if source_class in {"official_project", "official_exchange", "structured_calendar", "cryptopanic_tagged"}:
        return False
    if market in {"fresh", "strong", "confirmed"}:
        return False
    return status in {"rejected_results_only", "no_results", "skipped_budget", "provider_unavailable", "skipped_config", "not_configured"}


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
