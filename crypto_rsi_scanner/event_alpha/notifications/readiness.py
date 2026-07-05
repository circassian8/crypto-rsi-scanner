"""Final send-readiness checks for Event Alpha notification rehearsals.

This module is read-only. It inspects local research artifacts before an
operator enables real Telegram delivery, and it never sends, trades, paper
trades, or writes normal RSI signal rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
from ..artifacts import context as event_alpha_artifacts
from ..namespace import status as event_alpha_namespace_status
from . import delivery


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
    preview_path_source: str
    latest_run_completed: bool
    artifact_doctor_status: str
    alertable_items: int
    delivery_rows_checked: int
    core_rows_checked: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SendReadinessRows:
    runs: list[dict[str, Any]]
    core_rows: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    deliveries: list[dict[str, Any]]


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
    include_api_artifacts: bool = False,
) -> EventAlphaSendReadinessResult:
    """Return a final read-only readiness verdict for a profile namespace."""
    rows = _filtered_send_readiness_rows(
        run_rows=run_rows,
        core_opportunity_rows=core_opportunity_rows,
        alert_rows=alert_rows,
        delivery_rows=delivery_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    latest_run = _latest_run(rows.runs)
    latest_run_id = str(latest_run.get("run_id") or "") if latest_run else None
    latest_deliveries = [
        row for row in delivery.latest_rows_by_delivery(rows.deliveries)
        if not latest_run_id or str(row.get("run_id") or "") == latest_run_id
    ]
    resolved_preview_path, preview_source = _resolve_preview_path(
        latest_deliveries,
        explicit_path=preview_path,
        artifact_namespace=artifact_namespace,
    )
    resolved_preview = str(resolved_preview_path) if resolved_preview_path else None
    blockers = [
        *_namespace_send_readiness_blockers(
            resolved_preview_path=resolved_preview_path,
            preview_path=preview_path,
            artifact_namespace=artifact_namespace,
        ),
        *_latest_run_blockers(latest_run),
        *_artifact_doctor_send_readiness_blockers(artifact_doctor, preview_source=preview_source),
        *_preview_path_blockers(resolved_preview),
        *_send_guard_blockers(send_guard_enabled=send_guard_enabled, telegram_ready=telegram_ready),
    ]
    warnings = _send_readiness_warnings(send_guard_enabled=send_guard_enabled)
    latest_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in rows.core_rows
        if not latest_run_id or str(row.get("run_id") or "") == latest_run_id
    }
    blockers.extend(_delivery_send_readiness_blockers(
        latest_deliveries,
        latest_core_ids=latest_core_ids,
        send_guard_enabled=send_guard_enabled,
    ))
    would_send_cores = [
        row for row in rows.core_rows
        if (not latest_run_id or str(row.get("run_id") or "") == latest_run_id)
        and _route_is_alertable(row)
    ]
    blockers.extend(_core_send_readiness_blockers(would_send_cores))

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
        preview_path_source=preview_source,
        latest_run_completed=completed,
        artifact_doctor_status=str(artifact_doctor.status or "unknown"),
        alertable_items=sum(1 for row in would_send_cores),
        delivery_rows_checked=len(latest_deliveries),
        core_rows_checked=len(rows.core_rows),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _filtered_send_readiness_rows(
    *,
    run_rows: Iterable[Mapping[str, Any]],
    core_opportunity_rows: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> _SendReadinessRows:
    filter_kwargs = {
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "include_test_artifacts": include_test_artifacts,
        "include_api_artifacts": include_api_artifacts,
    }
    return _SendReadinessRows(
        runs=event_alpha_artifacts.filter_artifact_rows(
            [dict(row) for row in run_rows if isinstance(row, Mapping)],
            **filter_kwargs,
        ),
        core_rows=event_alpha_artifacts.filter_artifact_rows(
            [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)],
            **filter_kwargs,
        ),
        alerts=event_alpha_artifacts.filter_artifact_rows(
            [dict(row) for row in alert_rows if isinstance(row, Mapping)],
            **filter_kwargs,
        ),
        deliveries=_filter_delivery_rows(
            [dict(row) for row in delivery_rows if isinstance(row, Mapping)],
            **filter_kwargs,
        ),
    )


def _namespace_send_readiness_blockers(
    *,
    resolved_preview_path: Path | None,
    preview_path: str | Path | None,
    artifact_namespace: str | None,
) -> list[str]:
    namespace_dir = None
    if resolved_preview_path is not None:
        namespace_dir = resolved_preview_path.expanduser().parent
    elif preview_path:
        namespace_dir = Path(preview_path).expanduser().parent
    elif artifact_namespace:
        namespace_dir = Path("event_fade_cache") / str(artifact_namespace)
    namespace_status = event_alpha_namespace_status.load_namespace_status(namespace_dir)
    if event_alpha_namespace_status.is_inactive(namespace_status):
        return ["artifact namespace is stale/deprecated and blocked for send-readiness"]
    if namespace_status and not namespace_status.safe_for_send_readiness:
        return ["artifact namespace is marked unsafe for send-readiness"]
    return []


def _latest_run_blockers(latest_run: Mapping[str, Any] | None) -> list[str]:
    if latest_run is None:
        return ["no latest Event Alpha run found for this profile/namespace"]
    blockers: list[str] = []
    if not bool(latest_run.get("cycle_completed", latest_run.get("success", True))):
        blockers.append("latest run did not complete")
    if not bool(latest_run.get("success", True)):
        blockers.append("latest run is marked unsuccessful")
    return blockers


def _artifact_doctor_send_readiness_blockers(
    artifact_doctor: event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult,
    *,
    preview_source: str,
) -> list[str]:
    blockers: list[str] = []
    if str(artifact_doctor.status or "").upper() == "BLOCKED" or artifact_doctor.blockers:
        blockers.append("strict artifact doctor has blockers")
    if artifact_doctor.notification_preview_missing and preview_source == "missing":
        blockers.append("notification preview is missing")
    if artifact_doctor.notification_preview_path_unresolvable and preview_source == "missing":
        blockers.append("notification preview path is unresolvable")
    if (
        artifact_doctor.notification_preview_run_summary_mismatch
        or artifact_doctor.notification_preview_core_count_mismatch
        or artifact_doctor.notification_preview_alertable_count_mismatch
        or artifact_doctor.notification_preview_llm_summary_mismatch
        or artifact_doctor.notification_preview_lane_counts_mismatch
    ):
        blockers.append("notification preview summary does not match latest run artifacts")
    if artifact_doctor.notification_preview_missing_send_guard_status:
        blockers.append("notification preview is missing send/no-send guard status")
    if artifact_doctor.notification_preview_no_send_status_unclear:
        blockers.append("notification preview no-send/blocked wording is unclear")
    if getattr(artifact_doctor, "delivery_status_missing", 0):
        blockers.append("delivery rows are missing explicit delivery_state")
    if getattr(artifact_doctor, "delivery_status_detail_missing", 0):
        blockers.append("delivery rows are missing explicit status_detail")
    if getattr(artifact_doctor, "delivery_mode_missing", 0):
        blockers.append("delivery rows are missing explicit delivery_mode")
    if getattr(artifact_doctor, "delivery_state_inconsistent", 0):
        blockers.append("delivery rows have inconsistent delivery_state")
    if getattr(artifact_doctor, "delivery_would_send_sent_failed_inconsistent", 0):
        blockers.append("delivery rows have inconsistent would_send/sent/failed flags")
    return blockers


def _preview_path_blockers(resolved_preview: str | None) -> list[str]:
    if not resolved_preview:
        return ["notification preview path was not recorded"]
    if not Path(resolved_preview).expanduser().exists():
        return ["notification preview path does not exist"]
    return []


def _send_guard_blockers(*, send_guard_enabled: bool, telegram_ready: bool) -> list[str]:
    if send_guard_enabled and not telegram_ready:
        return ["Telegram token/chat id missing while send guard is enabled"]
    return []


def _send_readiness_warnings(*, send_guard_enabled: bool) -> list[str]:
    if not send_guard_enabled:
        return ["no-send rehearsal: send guard disabled; real Telegram sends remain blocked"]
    return []


def _delivery_send_readiness_blockers(
    latest_deliveries: Iterable[Mapping[str, Any]],
    *,
    latest_core_ids: set[str],
    send_guard_enabled: bool,
) -> list[str]:
    blockers: list[str] = []
    for row in latest_deliveries:
        status_detail = str(row.get("status_detail") or "").strip()
        delivery_state = str(row.get("delivery_state") or "").strip()
        delivery_mode = str(row.get("delivery_mode") or "").strip()
        if not delivery_state:
            blockers.append("delivery row missing explicit delivery_state")
        if not status_detail:
            blockers.append("delivery row missing explicit status_detail")
        if not delivery_mode:
            blockers.append("delivery row missing explicit delivery_mode")
        if bool(row.get("sent")) and not send_guard_enabled:
            blockers.append("delivery row says sent while send guard is disabled")
        if status_detail == delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED and bool(row.get("send_guard_enabled")):
            blockers.append("no-send rehearsal delivery row has send_guard_enabled=true")
        blockers.extend(_delivery_core_identity_blockers(row, latest_core_ids=latest_core_ids))
    return blockers


def _delivery_core_identity_blockers(row: Mapping[str, Any], *, latest_core_ids: set[str]) -> list[str]:
    lane = str(row.get("lane") or "")
    if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
        return []
    state = str(row.get("state") or "")
    if state not in {
        delivery.STATE_DELIVERED,
        delivery.STATE_PARTIAL_DELIVERED,
        delivery.STATE_BLOCKED,
        delivery.STATE_SKIPPED_DUPLICATE,
        delivery.STATE_SKIPPED_IN_FLIGHT,
    }:
        return []
    core_id = str(row.get("core_opportunity_id") or "").strip()
    if not core_id:
        return ["delivery row missing canonical core opportunity identity"]
    if latest_core_ids and core_id not in latest_core_ids:
        return ["delivery row references core opportunity missing from core store"]
    return []


def _core_send_readiness_blockers(would_send_cores: Iterable[Mapping[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for row in would_send_cores:
        if _core_is_rejected_or_unconfirmed(row):
            blockers.append(
                "alertable core lacks accepted/live confirmation: "
                + str(row.get("core_opportunity_id") or row.get("symbol") or "unknown")
            )
        if _route_value(row) == "TRIGGERED_FADE" and str(row.get("effective_playbook_type") or row.get("playbook_type") or "") != "proxy_fade":
            blockers.append("TRIGGERED_FADE core is not proxy_fade")
    return blockers


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
        f"notification_preview_path_resolved: {result.preview_path or 'missing'}",
        f"notification_preview_path_source: {result.preview_path_source}",
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
    include_api_artifacts: bool,
) -> list[dict[str, Any]]:
    """Filter delivery rows without requiring run_mode on historical rows."""
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        if not include_test_artifacts and event_alpha_artifacts.is_non_operational_row(data):
            continue
        if not include_api_artifacts and _delivery_is_api(data):
            continue
        if profile_key is not None and _clean_optional(data.get("profile")) not in (None, profile_key):
            continue
        if namespace_key is not None:
            row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
            if row_ns != namespace_key:
                continue
        out.append(data)
    return out


def _delivery_is_api(row: Mapping[str, Any]) -> bool:
    namespace = _clean_optional(row.get("artifact_namespace") or row.get("namespace"))
    if namespace in (None, event_alpha_artifacts.LEGACY_NAMESPACE):
        return True
    return str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}


def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _resolve_preview_path(
    rows: Iterable[Mapping[str, Any]],
    *,
    explicit_path: str | Path | None,
    artifact_namespace: str | None,
) -> tuple[Path | None, str]:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.exists():
            return path, "explicit"
    candidates: list[tuple[str, Path, str]] = []
    for row in rows:
        path, source = delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=artifact_namespace,
        )
        if path is None:
            continue
        stamp = str(row.get("attempted_at") or row.get("delivered_at") or "")
        candidates.append((stamp, path, source))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1], candidates[-1][2]
    default_path, default_source = delivery.resolve_notification_preview_path(
        {},
        artifact_namespace=artifact_namespace,
    )
    return default_path, default_source


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
