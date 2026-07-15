"""Bounded, report-only view of cumulative Event Alpha artifact roots.

Static project-health checks must not recursively walk years of operational
artifacts. This inventory samples only bounded top-level metadata, never reads
artifact payloads, and deliberately has no delete/compact implementation.
"""

from __future__ import annotations

import os
import stat
from collections import Counter
from pathlib import Path
from typing import Any

from ..event_alpha.namespace import lifecycle as namespace_lifecycle
from ..event_alpha.namespace import status as namespace_status


REPORT_SCHEMA_VERSION = "bounded_artifact_retention_report_v1"
DEFAULT_NAMESPACE_SCAN_LIMIT = 128
DEFAULT_ENTRY_SCAN_LIMIT = 128
DEFAULT_CANDIDATE_LIMIT = 50
_COMPACTION_STATUSES = frozenset(
    {
        namespace_lifecycle.STATUS_STALE_DEPRECATED,
        namespace_lifecycle.STATUS_QUARANTINE,
        namespace_lifecycle.STATUS_ACTIVE_FIXTURE_SMOKE,
        namespace_lifecycle.STATUS_ACTIVE_INTEGRATED_SMOKE,
    }
)


def build_bounded_retention_report(
    base_dir: str | Path,
    *,
    display_base_dir: str | None = None,
    namespace_scan_limit: int = DEFAULT_NAMESPACE_SCAN_LIMIT,
    entry_scan_limit: int = DEFAULT_ENTRY_SCAN_LIMIT,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> dict[str, Any]:
    """Describe retention pressure without recursive scans or mutations."""

    base = Path(base_dir).expanduser()
    namespace_limit = max(1, int(namespace_scan_limit))
    entry_limit = max(1, int(entry_scan_limit))
    namespaces, namespaces_truncated, namespace_scan_error = _bounded_child_directories(
        base,
        limit=namespace_limit,
    )
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    control_metadata_files_read = 0
    namespace_entry_scan_error_count = 0
    for namespace_dir in namespaces:
        marker_path = namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME
        marker_present = marker_path.exists() or marker_path.is_symlink()
        marker_regular = marker_present and not marker_path.is_symlink() and marker_path.is_file()
        if marker_regular:
            marker = namespace_status.load_namespace_status(namespace_dir)
            control_metadata_files_read += 1
        elif marker_present:
            marker = namespace_status.EventAlphaNamespaceStatus(
                namespace=namespace_dir.name,
                status="invalid",
                reason="marker_not_regular",
                safe_for_send_readiness=False,
            )
        else:
            marker = None
        if marker and marker.status in {"invalid", namespace_lifecycle.STATUS_UNKNOWN}:
            status = namespace_lifecycle.STATUS_UNKNOWN
            reason = marker.reason or "namespace marker is invalid or unknown"
            _superseded_by = marker.superseded_by
        else:
            status, reason, _superseded_by = namespace_lifecycle._classify_namespace(  # noqa: SLF001
                namespace_dir.name,
                marker,
            )
        entry_counts, entries_truncated, entry_scan_error = _bounded_direct_entry_counts(
            namespace_dir,
            limit=entry_limit,
        )
        if entry_scan_error:
            namespace_entry_scan_error_count += 1
        stale = status in {
            namespace_lifecycle.STATUS_STALE_DEPRECATED,
            namespace_lifecycle.STATUS_ARCHIVED,
            namespace_lifecycle.STATUS_QUARANTINE,
        }
        safe_for_send_readiness = bool(
            marker
            and marker.safe_for_send_readiness
            and status == namespace_lifecycle.STATUS_ACTIVE_LIVE_REHEARSAL
            and marker.current_doctor_status in {"OK", "WARN"}
        )
        row = {
            "namespace": namespace_dir.name,
            "status": status,
            "reason": reason,
            "profile": marker.profile if marker else None,
            "marker_present": marker_present,
            "marker_regular": marker_regular,
            "marker_valid": bool(marker and marker.status not in {"invalid", namespace_lifecycle.STATUS_UNKNOWN}),
            "marker_status": marker.status if marker else None,
            "safe_for_send_readiness": safe_for_send_readiness,
            "safe_for_burn_in_measurement": bool(
                marker and marker.safe_for_burn_in_measurement and safe_for_send_readiness
            ),
            "safe_for_calibration": bool(marker and marker.safe_for_calibration and safe_for_send_readiness),
            "superseded_by": (marker.superseded_by if marker else None) or _superseded_by,
            "current_doctor_status": marker.current_doctor_status if marker else None,
            "stale": stale,
            "file_count": entry_counts["files"],
            "file_count_exact": not entries_truncated and entry_scan_error is None,
            "direct_entry_count": entry_counts["entries"],
            "direct_entry_scan_truncated": entries_truncated,
            "direct_entry_scan_error": entry_scan_error,
            "nested_entries_scanned": False,
            "artifact_counts": {
                "json": entry_counts["json"],
                "jsonl": entry_counts["jsonl"],
                "md": entry_counts["md"],
            },
            "retention_policy": (
                marker.retention_policy if marker and marker.retention_policy else namespace_lifecycle._retention_policy(status)  # noqa: SLF001
            ),
        }
        rows.append(row)
        status_counts[status] += 1
    rows.sort(key=lambda row: str(row["namespace"]))
    candidate_rows = _compaction_candidates(rows, limit=candidate_limit)
    gate_blockers: list[str] = []
    if namespace_scan_error:
        gate_blockers.append("namespace_scan_failed")
    if namespaces_truncated:
        gate_blockers.append("namespace_scan_truncated")
    if namespace_entry_scan_error_count:
        gate_blockers.append("namespace_entry_scan_failed")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "bounded_artifact_retention_report",
        "base_dir": display_base_dir or base.as_posix(),
        "scan_mode": "bounded_top_level_metadata_only",
        "deep_scan_performed": False,
        "artifact_payloads_read": 0,
        "control_metadata_files_read": control_metadata_files_read,
        "namespace_scan_limit": namespace_limit,
        "direct_entry_scan_limit_per_namespace": entry_limit,
        "namespace_count": len(rows),
        "namespace_count_exact": not namespaces_truncated and namespace_scan_error is None,
        "namespace_scan_truncated": namespaces_truncated,
        "namespace_scan_error": namespace_scan_error,
        "namespace_entry_scan_error_count": namespace_entry_scan_error_count,
        "gate_status": "blocked" if gate_blockers else "pass",
        "gate_blockers": gate_blockers,
        "status_counts": dict(sorted(status_counts.items())),
        "known_stale_namespaces": [str(row["namespace"]) for row in rows if row["stale"]],
        "namespaces": rows,
        "compaction_candidate_count_observed": sum(
            1 for row in rows if row["status"] in _COMPACTION_STATUSES
        ),
        "compaction_candidates": candidate_rows,
        "candidate_report_limit": max(0, int(candidate_limit)),
        "retention_policy_authorized": False,
        "compaction_performed": False,
        "deletion_performed": False,
        "next_action": "configure and explicitly authorize a separate retention policy before any mutation",
    }


def _compaction_candidates(
    rows: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, str]]:
    candidates = [
        {
            "namespace": str(row["namespace"]),
            "status": str(row["status"]),
            "retention_policy": str(row["retention_policy"]),
            "reason": "candidate for explicit operator retention review; no action authorized",
        }
        for row in rows
        if row["status"] in _COMPACTION_STATUSES
    ]
    return candidates[: max(0, int(limit))]


def _bounded_child_directories(
    base: Path,
    *,
    limit: int,
) -> tuple[list[Path], bool, str | None]:
    try:
        base_identity = os.lstat(base)
    except FileNotFoundError:
        return [], False, None
    except OSError:
        return [], False, "base_directory_status_failed"
    if stat.S_ISLNK(base_identity.st_mode):
        return [], False, "base_directory_symlink"
    if not stat.S_ISDIR(base_identity.st_mode):
        return [], False, "base_path_not_directory"

    descriptor = _open_verified_directory(base, expected=base_identity)
    if descriptor is None:
        return [], False, "base_directory_identity_failed"

    rows: list[Path] = []
    truncated = False
    entry_status_failed = False
    try:
        with os.scandir(descriptor) as iterator:
            for entry in iterator:
                try:
                    entry_identity = entry.stat(follow_symlinks=False)
                except OSError:
                    entry_status_failed = True
                    continue
                if not stat.S_ISDIR(entry_identity.st_mode):
                    continue
                if len(rows) >= limit:
                    truncated = True
                    break
                rows.append(base / entry.name)
    except OSError:
        return rows, False, "base_directory_scan_failed"
    finally:
        os.close(descriptor)
    rows.sort(key=lambda path: path.name)
    return rows, truncated, "base_entry_status_failed" if entry_status_failed else None


def _bounded_direct_entry_counts(
    namespace_dir: Path,
    *,
    limit: int,
) -> tuple[Counter[str], bool, str | None]:
    counts: Counter[str] = Counter()
    truncated = False
    try:
        namespace_identity = os.lstat(namespace_dir)
    except OSError:
        return counts, False, "namespace_directory_identity_failed"
    if stat.S_ISLNK(namespace_identity.st_mode) or not stat.S_ISDIR(namespace_identity.st_mode):
        return counts, False, "namespace_directory_identity_failed"

    descriptor = _open_verified_directory(namespace_dir, expected=namespace_identity)
    if descriptor is None:
        return counts, False, "namespace_directory_identity_failed"

    entry_status_failed = False
    try:
        with os.scandir(descriptor) as iterator:
            for entry in iterator:
                if counts["entries"] >= limit:
                    truncated = True
                    break
                counts["entries"] += 1
                try:
                    entry_identity = entry.stat(follow_symlinks=False)
                except OSError:
                    entry_status_failed = True
                    continue
                if not stat.S_ISREG(entry_identity.st_mode):
                    continue
                counts["files"] += 1
                suffix = Path(entry.name).suffix.lstrip(".").lower()
                if suffix in {"json", "jsonl", "md"}:
                    counts[suffix] += 1
    except OSError:
        return counts, False, "namespace_directory_scan_failed"
    finally:
        os.close(descriptor)
    return counts, truncated, "namespace_entry_status_failed" if entry_status_failed else None


def _open_verified_directory(path: Path, *, expected: os.stat_result) -> int | None:
    """Open ``path`` without following links and retain only its exact inode."""

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        opened = os.fstat(descriptor)
    except OSError:
        os.close(descriptor)
        return None
    if (
        not stat.S_ISDIR(opened.st_mode)
        or opened.st_dev != expected.st_dev
        or opened.st_ino != expected.st_ino
    ):
        os.close(descriptor)
        return None
    return descriptor


__all__ = ["build_bounded_retention_report"]
