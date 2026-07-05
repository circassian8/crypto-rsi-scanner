"""Namespace lifecycle phase for Event Alpha artifact doctor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import check_registry
from ..namespace import status as event_alpha_namespace_status


@dataclass(frozen=True)
class NamespaceDoctorResult:
    namespace_dir: Path | None
    namespace_status: str | None = None
    namespace_stale_deprecated: int = 0
    namespace_superseded_by: Any | None = None
    short_circuit: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def inspect_namespace(
    namespace_dir: str | Path | None,
    *,
    include_stale_artifacts: bool = False,
) -> NamespaceDoctorResult:
    """Read namespace lifecycle status before artifact content checks run."""
    if namespace_dir is None:
        return NamespaceDoctorResult(namespace_dir=None, namespace_status=event_alpha_namespace_status.STATUS_ACTIVE)
    base = Path(namespace_dir)
    marker = event_alpha_namespace_status.load_namespace_status(base)
    is_stale = event_alpha_namespace_status.is_stale_deprecated(marker)
    blockers, warnings = _namespace_policy_messages(marker)
    if is_stale and marker:
        warnings.append(event_alpha_namespace_status.format_namespace_status(marker))
    return NamespaceDoctorResult(
        namespace_dir=base,
        namespace_status=marker.status if marker else event_alpha_namespace_status.STATUS_ACTIVE,
        namespace_stale_deprecated=1 if is_stale else 0,
        namespace_superseded_by=marker.superseded_by if marker else None,
        short_circuit=bool(is_stale and not include_stale_artifacts),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _namespace_policy_messages(
    marker: event_alpha_namespace_status.EventAlphaNamespaceStatus | None,
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if marker is None:
        return blockers, warnings
    status = str(marker.status or event_alpha_namespace_status.STATUS_UNKNOWN)
    if status in {"invalid", event_alpha_namespace_status.STATUS_UNKNOWN}:
        warnings.append(
            check_registry.format_check_message(
                "namespace.lifecycle_marker",
                f"unknown_namespace_status={status} namespace={marker.namespace}",
            )
        )
    if event_alpha_namespace_status.is_inactive(marker) and marker.safe_for_send_readiness:
        blockers.append(
            check_registry.format_check_message(
                "namespace.stale_send_readiness",
                f"namespace={marker.namespace} status={status} safe_for_send_readiness=true",
            )
        )
    active_statuses = {
        event_alpha_namespace_status.STATUS_ACTIVE,
        event_alpha_namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
        event_alpha_namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE,
        event_alpha_namespace_status.STATUS_ACTIVE_PROVIDER_PREFLIGHT,
        event_alpha_namespace_status.STATUS_ACTIVE_PROVIDER_REHEARSAL,
        event_alpha_namespace_status.STATUS_ACTIVE_INTEGRATED_SMOKE,
        event_alpha_namespace_status.STATUS_ACTIVE_ARCHITECTURE_REPORT,
        event_alpha_namespace_status.STATUS_MANUAL_REVIEW,
    }
    if status in active_statuses:
        doctor_status = str(marker.current_doctor_status or "not_run").upper()
        if marker.safe_for_send_readiness and doctor_status == "BLOCKED":
            blockers.append(
                check_registry.format_check_message(
                    "namespace.stale_send_readiness",
                    f"namespace={marker.namespace} current_doctor_status=BLOCKED safe_for_send_readiness=true",
                )
            )
        elif marker.safe_for_send_readiness and doctor_status not in {"OK", "WARN"}:
            warnings.append(
                check_registry.format_check_message(
                    "namespace.lifecycle_marker",
                    f"namespace={marker.namespace} safe_for_send_readiness_without_recent_doctor={doctor_status.lower()}",
                )
            )
        if _older_than_retention(marker):
            warnings.append(
                check_registry.format_check_message(
                    "namespace.include_stale_artifacts_guard",
                    f"active_namespace_older_than_retention={marker.namespace}",
                )
            )
    return blockers, warnings


def _older_than_retention(marker: event_alpha_namespace_status.EventAlphaNamespaceStatus) -> bool:
    if not marker.last_updated_at or not marker.archive_after_days:
        return False
    try:
        last_updated = datetime.fromisoformat(marker.last_updated_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - last_updated.astimezone(timezone.utc)).days
    return age_days > int(marker.archive_after_days)
