"""Authoritative namespace selection for the local read-only radar dashboard."""

from __future__ import annotations

import json
import os
import re
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..artifacts import fingerprints as event_alpha_fingerprints
from .loader import _read_regular_file_once, load_dashboard_snapshot
from .models import DashboardLoadError, DashboardSnapshot


CURRENT_NAMESPACE_POINTER = "radar_current_namespace.json"
POINTER_CONTRACT_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_POINTER_FIELDS = frozenset(
    {
        "contract_version",
        "artifact_namespace",
        "profile",
        "run_id",
        "revision",
        "operator_state_sha256",
        "generation_authority_status",
        "authority_checked_at",
    }
)
_REQUIRED_PRODUCT_ARTIFACTS = (
    "run_ledger",
    "core_opportunities",
    "research_cards",
    "daily_brief",
    "notification_preview",
    "decision_v2_notification_preview",
    "source_coverage_json",
    "source_coverage_md",
    "provider_readiness_json",
    "provider_readiness_md",
    "unified_calendar",
)


class DashboardReadinessError(RuntimeError):
    """Raised when no exact authoritative dashboard generation is available."""


@dataclass(frozen=True)
class _DashboardReadinessResult:
    snapshot: DashboardSnapshot
    namespace_source: str
    pointer_path: Path


def resolve_authoritative_dashboard(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Resolve an explicit namespace or the exact persisted pointer, then revalidate it."""

    base = _artifact_base(artifact_base_dir)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    explicit = str(artifact_namespace or "").strip()
    pointer: Mapping[str, Any] | None = None
    if explicit:
        namespace = explicit
        source = "explicit"
    else:
        pointer = read_current_namespace_pointer(base)
        namespace = str(pointer["artifact_namespace"])
        source = "pointer"
    try:
        snapshot = load_dashboard_snapshot(
            base,
            namespace,
            now=now,
            max_generation_age_hours=max_generation_age_hours,
            max_doctor_age_hours=max_doctor_age_hours,
        )
    except DashboardLoadError as exc:
        raise DashboardReadinessError(str(exc)) from exc
    _require_authoritative(snapshot)
    _require_complete_product_artifacts(snapshot)
    _require_current_counts(snapshot)
    if pointer is not None:
        _require_pointer_matches_snapshot(pointer, snapshot)
    return _DashboardReadinessResult(
        snapshot=snapshot,
        namespace_source=source,
        pointer_path=pointer_path,
    )


def publish_current_namespace_pointer(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Publish the fixed pointer only after the dashboard loader proves authority."""

    result = resolve_authoritative_dashboard(
        artifact_base_dir,
        artifact_namespace,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
    )
    snapshot = result.snapshot
    payload = {
        "contract_version": POINTER_CONTRACT_VERSION,
        "artifact_namespace": snapshot.artifact_namespace,
        "profile": snapshot.profile,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
        "generation_authority_status": "authoritative",
        "authority_checked_at": snapshot.generation_authority_checked_at,
    }
    _write_pointer_atomic(result.pointer_path, payload)
    return _DashboardReadinessResult(
        snapshot=snapshot,
        namespace_source=result.namespace_source,
        pointer_path=result.pointer_path,
    )


def read_current_namespace_pointer(artifact_base_dir: str | Path) -> dict[str, Any]:
    """Read and validate the fixed pointer without following a leaf symlink."""

    path = _artifact_base(artifact_base_dir) / CURRENT_NAMESPACE_POINTER
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        raise DashboardReadinessError(
            "current namespace pointer is missing; run radar-dashboard-readiness with an explicit namespace"
        )
    if read_error or data is None:
        raise DashboardReadinessError("current namespace pointer is unreadable or unsafe")
    try:
        parsed = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise DashboardReadinessError("current namespace pointer is invalid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise DashboardReadinessError("current namespace pointer is not an object")
    pointer = dict(parsed)
    if set(pointer) != _POINTER_FIELDS:
        raise DashboardReadinessError("current namespace pointer fields do not match contract v1")
    if pointer.get("contract_version") != POINTER_CONTRACT_VERSION:
        raise DashboardReadinessError("current namespace pointer contract version is unsupported")
    for field in ("artifact_namespace", "profile", "run_id"):
        value = pointer.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            raise DashboardReadinessError(f"current namespace pointer has invalid {field}")
    revision = pointer.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise DashboardReadinessError("current namespace pointer has invalid revision")
    digest = pointer.get("operator_state_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise DashboardReadinessError("current namespace pointer has invalid operator-state fingerprint")
    if pointer.get("generation_authority_status") != "authoritative":
        raise DashboardReadinessError("current namespace pointer is not authoritative")
    checked_at = pointer.get("authority_checked_at")
    if not isinstance(checked_at, str) or _aware_timestamp(checked_at) is None:
        raise DashboardReadinessError("current namespace pointer has invalid authority timestamp")
    return pointer


def _require_authoritative(snapshot: DashboardSnapshot) -> None:
    if snapshot.generation_authoritative:
        return
    reasons = ",".join(snapshot.generation_authority_reasons[:6]) or "unknown"
    raise DashboardReadinessError(f"dashboard generation is not authoritative ({reasons})")


def _require_current_counts(snapshot: DashboardSnapshot) -> None:
    artifacts = snapshot.operator_state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise DashboardReadinessError("dashboard generation has no exact artifact counts")
    expected = {
        "core_opportunities": len(snapshot.current_candidates),
        "unified_calendar": len(snapshot.current_calendar_events),
    }
    for artifact_name, observed in expected.items():
        entry = artifacts.get(artifact_name)
        if not isinstance(entry, Mapping) or entry.get("status") != "current":
            raise DashboardReadinessError(
                f"dashboard generation lacks current {artifact_name} artifact"
            )
        count = entry.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DashboardReadinessError(
                f"dashboard generation has invalid current count for {artifact_name}"
            )
        if count != observed:
            raise DashboardReadinessError(
                f"dashboard generation current count does not match {artifact_name}"
            )


def _require_complete_product_artifacts(snapshot: DashboardSnapshot) -> None:
    artifacts = snapshot.operator_state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise DashboardReadinessError("dashboard generation has no exact artifact manifest")
    for artifact_name in _REQUIRED_PRODUCT_ARTIFACTS:
        entry = artifacts.get(artifact_name)
        if not isinstance(entry, Mapping) or entry.get("status") != "current":
            raise DashboardReadinessError(
                f"dashboard generation lacks current {artifact_name} artifact"
            )
        metadata_error = event_alpha_fingerprints.fingerprint_metadata_error(entry)
        if metadata_error:
            raise DashboardReadinessError(
                f"dashboard generation {artifact_name} fingerprint is invalid ({metadata_error})"
            )


def _require_pointer_matches_snapshot(
    pointer: Mapping[str, Any],
    snapshot: DashboardSnapshot,
) -> None:
    expected = {
        "artifact_namespace": snapshot.artifact_namespace,
        "profile": snapshot.profile,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
    }
    if any(pointer.get(field) != value for field, value in expected.items()):
        raise DashboardReadinessError("current namespace pointer does not match the exact operator generation")


def _artifact_base(value: str | Path) -> Path:
    base = Path(value).expanduser().resolve()
    try:
        info = base.lstat()
    except OSError as exc:
        raise DashboardReadinessError("dashboard artifact base is missing or unreadable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise DashboardReadinessError("dashboard artifact base is not a directory")
    return base


def _write_pointer_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        raise DashboardReadinessError("current namespace pointer cannot be inspected") from exc
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise DashboardReadinessError("current namespace pointer target is not a regular file")
    data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise DashboardReadinessError("current namespace pointer update failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _aware_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


__all__ = (
    "CURRENT_NAMESPACE_POINTER",
    "DashboardReadinessError",
    "publish_current_namespace_pointer",
    "read_current_namespace_pointer",
    "resolve_authoritative_dashboard",
)
