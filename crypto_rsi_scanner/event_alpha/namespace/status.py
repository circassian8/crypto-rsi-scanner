"""Namespace status markers for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..artifacts import paths as event_artifact_paths
from ..artifacts import operator_state as event_alpha_operator_state
from ..artifacts import schema_v1


NAMESPACE_STATUS_FILENAME = "event_alpha_namespace_status.json"
STATUS_ACTIVE = "active"
STATUS_ACTIVE_LIVE_REHEARSAL = "active_live_rehearsal"
STATUS_ACTIVE_FIXTURE_SMOKE = "active_fixture_smoke"
STATUS_ACTIVE_PROVIDER_PREFLIGHT = "active_provider_preflight"
STATUS_ACTIVE_PROVIDER_REHEARSAL = "active_provider_rehearsal"
STATUS_ACTIVE_INTEGRATED_SMOKE = "active_integrated_smoke"
STATUS_ACTIVE_ARCHITECTURE_REPORT = "active_architecture_report"
STATUS_MANUAL_REVIEW = "manual_review"
STATUS_STALE_DEPRECATED = "stale_deprecated"
STATUS_ARCHIVED = "archived"
STATUS_QUARANTINE = "quarantine"
STATUS_UNKNOWN = "unknown"

INACTIVE_STATUSES = {STATUS_STALE_DEPRECATED, STATUS_ARCHIVED, STATUS_QUARANTINE, STATUS_MANUAL_REVIEW}


@dataclass(frozen=True)
class EventAlphaNamespaceStatus:
    namespace: str
    status: str
    profile: str | None = None
    reason: str | None = None
    superseded_by: str | None = None
    safe_for_send_readiness: bool = False
    safe_for_burn_in_measurement: bool = False
    safe_for_calibration: bool = False
    created_at: str | None = None
    last_updated_at: str | None = None
    last_verified_at: str | None = None
    retention_policy: str | None = None
    archive_after_days: int | None = None
    prune_after_days: int | None = None
    current_doctor_status: str | None = None
    latest_run_id: str | None = None
    artifact_counts: Mapping[str, Any] | None = None
    key_artifacts_present: tuple[str, ...] = ()
    missing_key_artifacts: tuple[str, ...] = ()
    readiness_required: bool = False
    readiness_present: bool = False
    operator_state_path: str | None = None
    operator_state_run_id: str | None = None
    operator_state_revision: int | None = None
    operator_state_status: str | None = None
    doctor_run_id: str | None = None
    doctor_state_revision: int | None = None
    marked_at: str | None = None
    marker_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        superseded: Any
        if self.superseded_by and "," in self.superseded_by:
            superseded = [item.strip() for item in self.superseded_by.split(",") if item.strip()]
        else:
            superseded = self.superseded_by
        return {
            "schema_id": "namespace_status_v1",
            "schema_version": schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
            "row_type": "event_alpha_namespace_status",
            "namespace": self.namespace,
            "status": self.status,
            "profile": self.profile,
            "reason": self.reason,
            "superseded_by": superseded,
            "safe_for_send_readiness": bool(self.safe_for_send_readiness),
            "safe_for_burn_in_measurement": bool(self.safe_for_burn_in_measurement),
            "safe_for_calibration": bool(self.safe_for_calibration),
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
            "last_verified_at": self.last_verified_at,
            "retention_policy": self.retention_policy,
            "archive_after_days": self.archive_after_days,
            "prune_after_days": self.prune_after_days,
            "current_doctor_status": self.current_doctor_status,
            "latest_run_id": self.latest_run_id,
            "artifact_counts": dict(self.artifact_counts or {}),
            "key_artifacts_present": list(self.key_artifacts_present),
            "missing_key_artifacts": list(self.missing_key_artifacts),
            "readiness_required": bool(self.readiness_required),
            "readiness_present": bool(self.readiness_present),
            "operator_state_path": self.operator_state_path,
            "operator_state_run_id": self.operator_state_run_id,
            "operator_state_revision": self.operator_state_revision,
            "operator_state_status": self.operator_state_status,
            "doctor_run_id": self.doctor_run_id,
            "doctor_state_revision": self.doctor_state_revision,
            "marked_at": self.marked_at,
            "marker_path": self.marker_path,
        }


def mark_namespace_stale(
    namespace_dir: str | Path,
    *,
    namespace: str,
    reason: str,
    superseded_by: str | None = None,
    safe_for_send_readiness: bool = False,
    now: datetime | None = None,
) -> Path:
    """Write a stale/deprecated marker in a namespace directory."""

    base = Path(namespace_dir)
    base.mkdir(parents=True, exist_ok=True)
    marker = base / NAMESPACE_STATUS_FILENAME
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    status = EventAlphaNamespaceStatus(
        namespace=namespace,
        status=STATUS_STALE_DEPRECATED,
        reason=reason,
        superseded_by=superseded_by,
        safe_for_send_readiness=bool(safe_for_send_readiness),
        safe_for_burn_in_measurement=False,
        safe_for_calibration=False,
        retention_policy="audit_then_archive",
        archive_after_days=30,
        prune_after_days=180,
        current_doctor_status="not_run",
        marked_at=ts,
        marker_path=event_artifact_paths.artifact_display_path(marker),
    )
    event_alpha_operator_state.write_json_atomic(marker, status.to_dict())
    return marker


def write_namespace_status(
    namespace_dir: str | Path,
    payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> Path:
    """Write a full lifecycle status marker for one namespace."""

    base = Path(namespace_dir)
    base.mkdir(parents=True, exist_ok=True)
    marker = base / NAMESPACE_STATUS_FILENAME
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    row = dict(payload)
    row.setdefault("schema_id", "namespace_status_v1")
    row.setdefault("schema_version", schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION)
    row.setdefault("row_type", "event_alpha_namespace_status")
    row.setdefault("namespace", base.name)
    row.setdefault("status", STATUS_UNKNOWN)
    row.setdefault("safe_for_send_readiness", False)
    row.setdefault("safe_for_burn_in_measurement", False)
    row.setdefault("safe_for_calibration", False)
    row.setdefault("marked_at", ts)
    row["marker_path"] = event_artifact_paths.artifact_display_path(marker)
    event_alpha_operator_state.write_json_atomic(marker, row)
    return marker


def refresh_namespace_status(
    namespace_dir: str | Path,
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Refresh factual state for one namespace without changing safety policy."""

    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    marker = base / NAMESPACE_STATUS_FILENAME
    existing = _load_marker_mapping(marker)
    loaded = event_alpha_operator_state.load_operator_state(base)
    state = dict(loaded.state or {}) if loaded.valid else {}
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    namespace = str(state.get("artifact_namespace") or artifact_namespace or existing.get("namespace") or base.name)
    selected_profile = str(state.get("profile") or profile or existing.get("profile") or "") or None
    status = str(existing.get("status") or _status_for_run(selected_profile, run_mode or state.get("run_mode")))
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    if state:
        current_artifacts = sorted(
            str(name)
            for name, entry in artifacts.items()
            if isinstance(entry, Mapping)
            and str(entry.get("status") or "") == event_alpha_operator_state.STATUS_CURRENT
            and _operator_artifact_exists(base, entry.get("path"))
        )
        non_current_artifacts = sorted(str(name) for name in artifacts if str(name) not in current_artifacts)
    else:
        current_artifacts = [str(name) for name in existing.get("key_artifacts_present") or ()]
        non_current_artifacts = [str(name) for name in existing.get("missing_key_artifacts") or ()]
    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    revision = _int_or_none(state.get("revision"))
    doctor_current = bool(
        state
        and str(doctor.get("run_id") or "") == str(state.get("run_id") or "")
        and _int_or_none(doctor.get("verified_revision")) == revision
        and doctor.get("authoritative") is True
        and doctor.get("strict") is True
        and doctor.get("schema_only") is False
        and doctor.get("skip_api_checks") is False
        and str(doctor.get("status") or "") in {"OK", "WARN", "BLOCKED"}
    )
    if doctor_current:
        doctor_status = str(doctor.get("status") or "not_run")
    elif state and str(doctor.get("status") or "") in {"not_run", "stale", "STALE"}:
        doctor_status = str(doctor.get("status"))
    else:
        doctor_status = "stale" if state else "not_run"
    files = [path for path in base.rglob("*") if path.is_file() and path.suffix != ".lock"]
    row = dict(existing)
    row.update(
        {
            "schema_id": "namespace_status_v1",
            "schema_version": schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
            "row_type": "event_alpha_namespace_status",
            "namespace": namespace,
            "profile": selected_profile,
            "status": status,
            "latest_run_id": str(state.get("run_id") or existing.get("latest_run_id") or "") or None,
            "last_updated_at": timestamp,
            "current_doctor_status": doctor_status,
            "last_verified_at": str(doctor.get("verified_at") or "") if doctor_current else None,
            "artifact_counts": {
                "files": len(files),
                "json": sum(path.suffix == ".json" for path in files),
                "jsonl": sum(path.suffix == ".jsonl" for path in files),
                "md": sum(path.suffix == ".md" for path in files),
                "research_cards": sum(
                    "research_cards" in path.parts and path.suffix == ".md" and path.name != "index.md"
                    for path in files
                ),
            },
            "key_artifacts_present": current_artifacts,
            "missing_key_artifacts": non_current_artifacts,
            "readiness_present": (
                "provider_readiness_json" in current_artifacts
                if state
                else bool(
                    existing.get("readiness_present")
                    or (base / "event_live_provider_activation_readiness.json").exists()
                )
            ),
            "operator_state_path": (
                event_artifact_paths.artifact_display_path(loaded.path, base=base) if loaded.exists else None
            ),
            "operator_state_run_id": str(state.get("run_id") or "") or None,
            "operator_state_revision": revision,
            "operator_state_status": str(state.get("manifest_status") or ("invalid" if loaded.exists else "missing")),
            "doctor_run_id": str(doctor.get("run_id") or "") or None,
            "doctor_state_revision": _int_or_none(doctor.get("verified_revision")),
            "marked_at": str(existing.get("marked_at") or timestamp),
            "marker_path": event_artifact_paths.artifact_display_path(marker),
        }
    )
    # Policy is explicit and never inferred from artifact presence.
    for key in ("safe_for_send_readiness", "safe_for_burn_in_measurement", "safe_for_calibration"):
        row[key] = existing.get(key) is True
    row.setdefault("readiness_required", status in {STATUS_ACTIVE_LIVE_REHEARSAL, STATUS_ACTIVE_PROVIDER_REHEARSAL})
    event_alpha_operator_state.write_json_atomic(marker, row)
    return marker


def load_namespace_status(namespace_dir: str | Path | None) -> EventAlphaNamespaceStatus | None:
    if namespace_dir is None:
        return None
    marker = Path(namespace_dir) / NAMESPACE_STATUS_FILENAME
    if not marker.exists():
        return None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EventAlphaNamespaceStatus(
            namespace=Path(namespace_dir).name,
            status="invalid",
            reason="marker_unreadable",
            safe_for_send_readiness=False,
            marker_path=event_artifact_paths.artifact_display_path(marker),
        )
    if not isinstance(payload, Mapping):
        return EventAlphaNamespaceStatus(
            namespace=Path(namespace_dir).name,
            status="invalid",
            reason="marker_not_object",
            safe_for_send_readiness=False,
            marker_path=event_artifact_paths.artifact_display_path(marker),
        )
    expected_namespace = Path(namespace_dir).name
    schema_errors = schema_v1.validate_row_against_schema(payload, "namespace_status_v1")
    schema_identity_valid = bool(
        str(payload.get("schema_id") or "") == "namespace_status_v1"
        and str(payload.get("schema_version") or "") == schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION
    )
    row_type_valid = str(payload.get("row_type") or "") == "event_alpha_namespace_status"
    namespace_identity_valid = str(payload.get("namespace") or "") == expected_namespace
    superseded = payload.get("superseded_by")
    if isinstance(superseded, list):
        superseded_text = ", ".join(str(item) for item in superseded if str(item))
    else:
        superseded_text = str(superseded or "")
    status = str(payload.get("status") or STATUS_UNKNOWN)
    status_allows_send_readiness = status not in {"invalid", STATUS_UNKNOWN}
    safe_for_send_readiness = bool(
        not schema_errors
        and schema_identity_valid
        and row_type_valid
        and namespace_identity_valid
        and status_allows_send_readiness
        and payload.get("safe_for_send_readiness") is True
    )
    return EventAlphaNamespaceStatus(
        namespace=str(payload.get("namespace") or Path(namespace_dir).name),
        status=status,
        profile=str(payload.get("profile") or "") or None,
        reason=(
            str(payload.get("reason") or "")
            or (
                "marker_schema_invalid"
                if schema_errors or not schema_identity_valid or not row_type_valid or not namespace_identity_valid
                else ""
            )
            or None
        ),
        superseded_by=superseded_text or None,
        safe_for_send_readiness=safe_for_send_readiness,
        safe_for_burn_in_measurement=payload.get("safe_for_burn_in_measurement") is True,
        safe_for_calibration=payload.get("safe_for_calibration") is True,
        created_at=str(payload.get("created_at") or "") or None,
        last_updated_at=str(payload.get("last_updated_at") or "") or None,
        last_verified_at=str(payload.get("last_verified_at") or "") or None,
        retention_policy=str(payload.get("retention_policy") or "") or None,
        archive_after_days=_int_or_none(payload.get("archive_after_days")),
        prune_after_days=_int_or_none(payload.get("prune_after_days")),
        current_doctor_status=str(payload.get("current_doctor_status") or "") or None,
        latest_run_id=str(payload.get("latest_run_id") or "") or None,
        artifact_counts=payload.get("artifact_counts") if isinstance(payload.get("artifact_counts"), Mapping) else None,
        key_artifacts_present=tuple(str(item) for item in payload.get("key_artifacts_present") or ()),
        missing_key_artifacts=tuple(str(item) for item in payload.get("missing_key_artifacts") or ()),
        readiness_required=bool(payload.get("readiness_required", False)),
        readiness_present=bool(payload.get("readiness_present", False)),
        operator_state_path=str(payload.get("operator_state_path") or "") or None,
        operator_state_run_id=str(payload.get("operator_state_run_id") or "") or None,
        operator_state_revision=_int_or_none(payload.get("operator_state_revision")),
        operator_state_status=str(payload.get("operator_state_status") or "") or None,
        doctor_run_id=str(payload.get("doctor_run_id") or "") or None,
        doctor_state_revision=_int_or_none(payload.get("doctor_state_revision")),
        marked_at=str(payload.get("marked_at") or "") or None,
        marker_path=event_artifact_paths.artifact_display_path(marker),
    )


def is_stale_deprecated(status: EventAlphaNamespaceStatus | None) -> bool:
    return bool(status and status.status == STATUS_STALE_DEPRECATED)


def is_inactive(status: EventAlphaNamespaceStatus | None) -> bool:
    return bool(status and status.status in INACTIVE_STATUSES)


def format_namespace_status(status: EventAlphaNamespaceStatus | None) -> str:
    if status is None:
        return "namespace_status: active (no marker)"
    lines = [
        f"namespace_status: {status.status}",
        f"namespace: {status.namespace}",
        f"profile: {status.profile or 'unknown'}",
        f"reason: {status.reason or 'none'}",
        f"superseded_by: {status.superseded_by or 'none'}",
        f"safe_for_send_readiness: {str(status.safe_for_send_readiness).lower()}",
        f"safe_for_burn_in_measurement: {str(status.safe_for_burn_in_measurement).lower()}",
        f"safe_for_calibration: {str(status.safe_for_calibration).lower()}",
        f"current_doctor_status: {status.current_doctor_status or 'unknown'}",
        f"last_verified_at: {status.last_verified_at or 'unknown'}",
        f"marked_at: {status.marked_at or 'unknown'}",
        f"marker_path: {status.marker_path or 'none'}",
    ]
    if status.status == STATUS_STALE_DEPRECATED:
        lines.append("operator_note: stale/deprecated namespaces are ignored by default artifact doctor reports and blocked for send-readiness.")
    return "\n".join(lines)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _operator_artifact_exists(base: Path, value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    raw = Path(text).expanduser()
    return (raw if raw.is_absolute() else base / raw).exists()


def _load_marker_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _status_for_run(profile: str | None, run_mode: object) -> str:
    mode = str(run_mode or "")
    selected = str(profile or "")
    if mode == "notification_burn_in" or selected.startswith("notify_"):
        return STATUS_ACTIVE_LIVE_REHEARSAL
    if mode in {"fixture", "test", "replay"} or selected == "fixture":
        return STATUS_ACTIVE_FIXTURE_SMOKE
    if mode in {"burn_in", "operational"}:
        return STATUS_ACTIVE
    return STATUS_UNKNOWN


def stale_namespace_plan(namespace_dir: str | Path, *, archive: bool = False) -> dict[str, Any]:
    base = Path(namespace_dir)
    files = sorted(path for path in base.rglob("*") if path.is_file()) if base.exists() else []
    return {
        "namespace_dir": event_artifact_paths.artifact_display_path(base),
        "exists": base.exists(),
        "file_count": len(files),
        "archive": bool(archive),
        "dry_run_only": True,
        "files_sample": [event_artifact_paths.artifact_display_path(path) for path in files[:20]],
    }
