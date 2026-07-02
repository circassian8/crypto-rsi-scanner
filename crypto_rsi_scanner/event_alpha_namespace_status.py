"""Namespace status markers for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import event_artifact_paths


NAMESPACE_STATUS_FILENAME = "event_alpha_namespace_status.json"
STATUS_ACTIVE = "active"
STATUS_STALE_DEPRECATED = "stale_deprecated"


@dataclass(frozen=True)
class EventAlphaNamespaceStatus:
    namespace: str
    status: str
    reason: str | None = None
    superseded_by: str | None = None
    safe_for_send_readiness: bool = True
    marked_at: str | None = None
    marker_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        superseded: Any
        if self.superseded_by and "," in self.superseded_by:
            superseded = [item.strip() for item in self.superseded_by.split(",") if item.strip()]
        else:
            superseded = self.superseded_by
        return {
            "schema_version": 1,
            "row_type": "event_alpha_namespace_status",
            "namespace": self.namespace,
            "status": self.status,
            "reason": self.reason,
            "superseded_by": superseded,
            "safe_for_send_readiness": bool(self.safe_for_send_readiness),
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
        marked_at=ts,
        marker_path=event_artifact_paths.artifact_display_path(marker),
    )
    marker.write_text(json.dumps(status.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            marker_path=event_artifact_paths.artifact_display_path(marker),
        )
    if not isinstance(payload, Mapping):
        return EventAlphaNamespaceStatus(
            namespace=Path(namespace_dir).name,
            status="invalid",
            reason="marker_not_object",
            marker_path=event_artifact_paths.artifact_display_path(marker),
        )
    superseded = payload.get("superseded_by")
    if isinstance(superseded, list):
        superseded_text = ", ".join(str(item) for item in superseded if str(item))
    else:
        superseded_text = str(superseded or "")
    safe_value = payload.get("safe_for_send_readiness")
    safe_for_send_readiness = bool(safe_value) if safe_value is not None else str(payload.get("status") or "") != STATUS_STALE_DEPRECATED
    return EventAlphaNamespaceStatus(
        namespace=str(payload.get("namespace") or Path(namespace_dir).name),
        status=str(payload.get("status") or STATUS_ACTIVE),
        reason=str(payload.get("reason") or "") or None,
        superseded_by=superseded_text or None,
        safe_for_send_readiness=safe_for_send_readiness,
        marked_at=str(payload.get("marked_at") or "") or None,
        marker_path=event_artifact_paths.artifact_display_path(marker),
    )


def is_stale_deprecated(status: EventAlphaNamespaceStatus | None) -> bool:
    return bool(status and status.status == STATUS_STALE_DEPRECATED)


def format_namespace_status(status: EventAlphaNamespaceStatus | None) -> str:
    if status is None:
        return "namespace_status: active (no marker)"
    lines = [
        f"namespace_status: {status.status}",
        f"namespace: {status.namespace}",
        f"reason: {status.reason or 'none'}",
        f"superseded_by: {status.superseded_by or 'none'}",
        f"safe_for_send_readiness: {str(status.safe_for_send_readiness).lower()}",
        f"marked_at: {status.marked_at or 'unknown'}",
        f"marker_path: {status.marker_path or 'none'}",
    ]
    if status.status == STATUS_STALE_DEPRECATED:
        lines.append("operator_note: stale/deprecated namespaces are ignored by default artifact doctor reports and blocked for send-readiness.")
    return "\n".join(lines)


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
