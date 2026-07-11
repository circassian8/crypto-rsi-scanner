"""Atomic current-generation state for Event Alpha operator artifacts.

The state file is deliberately small and bounded: every completed cycle replaces
the prior generation, then later local report commands update only that same
generation.  It is research metadata only and cannot route or send anything.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from . import schema_v1


OPERATOR_STATE_FILENAME = "event_alpha_operator_state.json"
_LOCK_FILENAME = ".event_alpha_operator_state.lock"
OPERATOR_STATE_SCHEMA_ID = "operator_state_v1"
OPERATOR_STATE_ROW_TYPE = "event_alpha_operator_state"

STATUS_CURRENT = "current"
STATUS_SKIPPED = "skipped"
STATUS_MISSING = "missing"
STATUS_STALE = "stale"
STATUS_FAILED = "failed"
STATUS_PENDING = "pending"
ARTIFACT_STATUSES = {
    STATUS_CURRENT,
    STATUS_SKIPPED,
    STATUS_MISSING,
    STATUS_STALE,
    STATUS_FAILED,
    STATUS_PENDING,
}
DOCTOR_COMPLETED_STATUSES = {"OK", "WARN", "BLOCKED"}
DOCTOR_STATUSES = {"not_run", "stale", "STALE", *DOCTOR_COMPLETED_STATUSES}

KNOWN_ARTIFACTS = (
    "run_ledger",
    "core_opportunities",
    "research_cards",
    "daily_brief",
    "notification_preview",
    "source_coverage_json",
    "source_coverage_md",
    "provider_readiness_json",
    "provider_readiness_md",
)

_RUN_PATH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "core_opportunities": ("core_opportunity_store_path",),
    "daily_brief": ("daily_brief_path",),
    "notification_preview": ("notification_preview_path",),
    "source_coverage_json": (
        "integrated_source_coverage_json_path",
        "source_coverage_json_path_rel",
    ),
    "source_coverage_md": ("source_coverage_md_path_rel", "source_coverage_path"),
    "provider_readiness_json": ("live_provider_readiness_json_path", "provider_readiness_json_path"),
    "provider_readiness_md": ("live_provider_readiness_report_path", "provider_readiness_md_path"),
}


@dataclass(frozen=True)
class EventAlphaOperatorStateReadResult:
    path: Path
    exists: bool
    valid: bool
    state: Mapping[str, Any] | None = None
    error: str | None = None


def operator_state_path(namespace_dir: str | Path) -> Path:
    return Path(namespace_dir).expanduser() / OPERATOR_STATE_FILENAME


def text_has_exact_run_id(text: str, run_id: object) -> bool:
    """Return whether operator text contains one exact top-level run_id line."""

    expected = str(run_id or "").strip()
    if not expected:
        return False
    return bool(re.search(rf"(?m)^run_id:\s*{re.escape(expected)}\s*$", str(text)))


def write_json_atomic(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Durably replace one JSON document with a same-directory temporary file."""

    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(_json_ready(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, target)
        temp_path = None
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return target


def _write_text_atomic(path: Path, text_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text_value)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, path)
        temp_path = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_operator_state(namespace_dir: str | Path) -> EventAlphaOperatorStateReadResult:
    path = operator_state_path(namespace_dir)
    if not path.exists():
        return EventAlphaOperatorStateReadResult(path=path, exists=False, valid=False, error="missing")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return EventAlphaOperatorStateReadResult(path=path, exists=True, valid=False, error=type(exc).__name__)
    if not isinstance(parsed, Mapping):
        return EventAlphaOperatorStateReadResult(path=path, exists=True, valid=False, error="not_object")
    state = dict(parsed)
    error = _state_validation_error(state, base=path.parent)
    return EventAlphaOperatorStateReadResult(
        path=path,
        exists=True,
        valid=error is None,
        state=state,
        error=error,
    )


def begin_run(
    namespace_dir: str | Path,
    run_row: Mapping[str, Any],
    *,
    run_ledger_path: str | Path | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """Atomically start a new current generation from one persisted run row."""

    base = Path(namespace_dir).expanduser()
    state = _build_run_state(
        base,
        run_row,
        run_ledger_path=run_ledger_path,
        updated_at=updated_at,
    )
    with _state_lock(base):
        write_json_atomic(operator_state_path(base), state)
    return state


def begin_run_if_newer(
    namespace_dir: str | Path,
    run_row: Mapping[str, Any],
    *,
    run_ledger_path: str | Path | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Atomically advance state, refusing a candidate not proven newer."""

    base = Path(namespace_dir).expanduser()
    candidate = _build_run_state(
        base,
        run_row,
        run_ledger_path=run_ledger_path,
        updated_at=updated_at,
    )
    with _state_lock(base):
        loaded = load_operator_state(base)
        if loaded.valid and loaded.state is not None:
            current = dict(loaded.state)
            if state_matches_run(
                current,
                run_row,
                profile=str(candidate["profile"]),
                artifact_namespace=str(candidate["artifact_namespace"]),
            ):
                return current
            if not run_is_newer_than_state(run_row, current):
                return None
        write_json_atomic(operator_state_path(base), candidate)
    return candidate


def _build_run_state(
    base: Path,
    run_row: Mapping[str, Any],
    *,
    run_ledger_path: str | Path | None,
    updated_at: datetime | None,
) -> dict[str, Any]:
    run_id = str(run_row.get("run_id") or "").strip()
    profile = str(run_row.get("profile") or "default").strip() or "default"
    namespace = str(run_row.get("artifact_namespace") or base.name).strip() or base.name
    if not run_id:
        raise ValueError("operator state requires run_id")
    now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
    send_requested = run_row.get("send_requested") is True
    send_attempted = run_row.get("send_attempted") is True
    send_success = run_row.get("send_success") is True
    send_items_delivered = _nonnegative_int(run_row.get("send_items_delivered"))
    sent = send_items_delivered > 0
    artifact_run_row = dict(run_row)
    if run_ledger_path is not None:
        artifact_run_row["_operator_run_ledger_path"] = run_ledger_path
    artifacts = {
        name: _initial_artifact_entry(name, base=base, run_id=run_id, run_row=artifact_run_row, now=now)
        for name in KNOWN_ARTIFACTS
    }
    state = {
        "schema_id": OPERATOR_STATE_SCHEMA_ID,
        "schema_version": schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
        "row_type": OPERATOR_STATE_ROW_TYPE,
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": namespace,
        "run_mode": str(run_row.get("run_mode") or "unknown"),
        "run_started_at": str(
            run_row.get("started_at")
            or run_row.get("observed_at")
            or run_row.get("generated_at")
            or now
        ),
        "generated_at": now,
        "updated_at": now,
        "revision": 1,
        "manifest_status": _manifest_status(artifacts),
        "research_only": True,
        "no_send_rehearsal": not send_attempted,
        "sent": sent,
        "send_requested": send_requested,
        "send_attempted": send_attempted,
        "send_success": send_success,
        "send_items_delivered": send_items_delivered,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "artifacts": artifacts,
        "doctor": {
            "status": "not_run",
            "run_id": run_id,
            "authoritative": False,
            "strict": False,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": None,
            "verified_revision": None,
            "blocker_count": 0,
            "warning_count": 0,
        },
    }
    return state


def invalidate_operator_state(
    namespace_dir: str | Path,
    *,
    reason: str,
    updated_at: datetime | None = None,
    expected_run_id: str | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Invalidate a completed doctor stamp after an out-of-band artifact mutation."""

    invalidation_reason = str(reason or "").strip()
    if not invalidation_reason:
        raise ValueError("operator-state invalidation requires reason")
    base = Path(namespace_dir).expanduser()
    with _state_lock(base):
        loaded = load_operator_state(base)
        if not loaded.valid or loaded.state is None:
            raise ValueError(f"operator state unavailable: {loaded.error or 'invalid'}")
        state = dict(loaded.state)
        if expected_run_id is not None and str(state.get("run_id") or "") != str(expected_run_id):
            raise ValueError("operator state changed before invalidation: run_id mismatch")
        if expected_revision is not None and int(state.get("revision") or 0) != int(expected_revision):
            raise ValueError("operator state changed before invalidation: revision mismatch")
        now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
        state["revision"] = int(state.get("revision") or 0) + 1
        state["updated_at"] = now
        state["invalidation_reason"] = invalidation_reason
        state["doctor"] = {
            "status": "stale",
            "run_id": str(state.get("run_id") or ""),
            "authoritative": False,
            "strict": False,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": None,
            "verified_revision": None,
            "blocker_count": 0,
            "warning_count": 0,
        }
        write_json_atomic(operator_state_path(base), state)
    return state


def latest_matching_run(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str,
    artifact_namespace: str,
) -> dict[str, Any] | None:
    """Return the newest run whose complete identity exactly matches a context."""

    expected_profile = str(profile or "default")
    expected_namespace = str(artifact_namespace or "")
    matching = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("profile") or "default") == expected_profile
        and str(row.get("artifact_namespace") or "") == expected_namespace
        and str(row.get("run_id") or "").strip()
    ]
    if not matching:
        return None
    return max(
        matching,
        key=lambda row: (
            str(row.get("started_at") or row.get("observed_at") or row.get("generated_at") or ""),
            str(row.get("run_id") or ""),
        ),
    )


def state_matches_run(
    state: Mapping[str, Any] | None,
    run_row: Mapping[str, Any] | None,
    *,
    profile: str,
    artifact_namespace: str,
) -> bool:
    """Return whether state, latest run, and requested context share one identity."""

    if not isinstance(state, Mapping) or not isinstance(run_row, Mapping):
        return False
    expected = (
        str(run_row.get("run_id") or ""),
        str(profile or "default"),
        str(artifact_namespace or ""),
    )
    if not all(expected):
        return False
    run_identity = (
        str(run_row.get("run_id") or ""),
        str(run_row.get("profile") or "default"),
        str(run_row.get("artifact_namespace") or ""),
    )
    state_identity = (
        str(state.get("run_id") or ""),
        str(state.get("profile") or ""),
        str(state.get("artifact_namespace") or ""),
    )
    return run_identity == expected and state_identity == expected


def run_is_newer_than_state(
    run_row: Mapping[str, Any],
    state: Mapping[str, Any],
) -> bool:
    """Return true only when timestamps prove a candidate run supersedes state."""

    run_timestamp = _first_timestamp(
        run_row,
        ("started_at", "observed_at", "generated_at", "finished_at"),
    )
    state_timestamp = _first_timestamp(state, ("run_started_at", "generated_at"))
    if not run_timestamp or not state_timestamp:
        return False
    if run_timestamp != state_timestamp:
        return run_timestamp > state_timestamp
    return str(run_row.get("run_id") or "") > str(state.get("run_id") or "")


def record_artifact(
    namespace_dir: str | Path,
    *,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    name: str,
    path: str | Path | None = None,
    status: str = STATUS_CURRENT,
    skip_reason: str | None = None,
    count: int | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """Update one artifact for the exact current generation."""

    if name not in KNOWN_ARTIFACTS:
        raise ValueError(f"unknown operator artifact: {name}")
    if status not in ARTIFACT_STATUSES:
        raise ValueError(f"invalid operator artifact status: {status}")
    reason = str(skip_reason or "").strip()
    if status != STATUS_CURRENT and not reason:
        raise ValueError("non-current operator artifact status requires skip_reason")
    if status == STATUS_CURRENT and path is None:
        raise ValueError("current operator artifact requires path")
    base = Path(namespace_dir).expanduser()
    with _state_lock(base):
        state = _require_matching_state(base, run_id, profile, artifact_namespace)
        now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
        state = _updated_artifact_state(
            state,
            base=base,
            run_id=run_id,
            name=name,
            path=path,
            status=status,
            reason=reason,
            count=count,
            now=now,
        )
        write_json_atomic(operator_state_path(base), state)
    return state


def write_text_artifact(
    namespace_dir: str | Path,
    *,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    name: str,
    path: str | Path,
    text: str,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """Write text and record it while holding exact-generation ownership."""

    if name not in KNOWN_ARTIFACTS:
        raise ValueError(f"unknown operator artifact: {name}")
    base = Path(namespace_dir).expanduser()
    target = Path(path).expanduser()
    with _state_lock(base):
        state = _require_matching_state(base, run_id, profile, artifact_namespace)
        _portable_path(target, base=base)
        _write_text_atomic(target, text)
        now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
        state = _updated_artifact_state(
            state,
            base=base,
            run_id=run_id,
            name=name,
            path=target,
            status=STATUS_CURRENT,
            reason="",
            count=None,
            now=now,
        )
        write_json_atomic(operator_state_path(base), state)
    return state


def _updated_artifact_state(
    state: dict[str, Any],
    *,
    base: Path,
    run_id: str,
    name: str,
    path: str | Path | None,
    status: str,
    reason: str,
    count: int | None,
    now: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "status": status,
        "run_id": str(run_id),
        "path": _portable_path(path, base=base) if path is not None else None,
        "generated_at": now,
        "reason": None if status == STATUS_CURRENT else reason,
    }
    if count is not None:
        entry["count"] = max(0, int(count))
    artifacts = dict(state.get("artifacts") or {})
    artifacts[name] = entry
    state["artifacts"] = artifacts
    state["revision"] = int(state.get("revision") or 0) + 1
    state["updated_at"] = now
    state["manifest_status"] = _manifest_status(artifacts)
    state["doctor"] = {
        "status": "stale",
        "run_id": str(run_id),
        "authoritative": False,
        "strict": False,
        "schema_only": False,
        "skip_api_checks": False,
        "verified_at": None,
        "verified_revision": None,
        "blocker_count": 0,
        "warning_count": 0,
    }
    return state


def record_doctor_status(
    namespace_dir: str | Path,
    *,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    expected_revision: int,
    strict: bool,
    schema_only: bool,
    skip_api_checks: bool,
    status: str,
    blocker_count: int = 0,
    warning_count: int = 0,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    """Stamp doctor status against the exact manifest revision it inspected."""

    if status not in DOCTOR_COMPLETED_STATUSES:
        raise ValueError(f"invalid completed doctor status: {status}")
    if not strict or schema_only or skip_api_checks:
        raise ValueError("only a full strict doctor can verify operator state")
    base = Path(namespace_dir).expanduser()
    with _state_lock(base):
        state = _require_matching_state(base, run_id, profile, artifact_namespace)
        current_revision = int(state.get("revision") or 0)
        if current_revision != int(expected_revision):
            raise ValueError(
                "operator state revision mismatch: "
                f"expected={int(expected_revision)} actual={current_revision}"
            )
        checked = _as_utc(checked_at or datetime.now(timezone.utc)).isoformat()
        state["doctor"] = {
            "status": status,
            "run_id": str(run_id),
            "authoritative": True,
            "strict": True,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": checked,
            "verified_revision": current_revision,
            "blocker_count": max(0, int(blocker_count)),
            "warning_count": max(0, int(warning_count)),
        }
        state.pop("invalidation_reason", None)
        state["updated_at"] = checked
        write_json_atomic(operator_state_path(base), state)
    return state


def _initial_artifact_entry(
    name: str,
    *,
    base: Path,
    run_id: str,
    run_row: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    if name == "run_ledger":
        path: str | Path | None = run_row.get("_operator_run_ledger_path") or base / "event_alpha_runs.jsonl"
    elif name == "core_opportunities":
        path = run_row.get("core_opportunity_store_path")
        if path and run_row.get("core_opportunity_write_success") is not True:
            return {
                "status": STATUS_FAILED,
                "run_id": run_id,
                "path": _portable_path(path, base=base),
                "generated_at": now,
                "reason": "core_opportunity_write_not_successful",
            }
    elif name == "research_cards":
        paths = tuple(str(item) for item in run_row.get("research_card_paths") or () if str(item))
        cards_written = _nonnegative_int(run_row.get("research_cards_written"))
        path = run_row.get("research_cards_dir") if paths or cards_written else None
        if path is None and (paths or cards_written):
            path = base / "research_cards"
    else:
        path = next(
            (run_row.get(field) for field in _RUN_PATH_FIELDS.get(name, ()) if run_row.get(field)),
            None,
        )
    if path:
        return {
            "status": STATUS_CURRENT,
            "run_id": run_id,
            "path": _portable_path(path, base=base),
            "generated_at": now,
            "reason": None,
        }
    return {
        "status": STATUS_SKIPPED,
        "run_id": run_id,
        "path": None,
        "generated_at": now,
        "reason": "not_written_by_cycle",
    }


def _require_matching_state(base: Path, run_id: str, profile: str, namespace: str) -> dict[str, Any]:
    loaded = load_operator_state(base)
    if not loaded.valid or loaded.state is None:
        raise ValueError(f"operator state unavailable: {loaded.error or 'invalid'}")
    state = dict(loaded.state)
    expected = (str(run_id), str(profile or "default"), str(namespace or base.name))
    actual = (
        str(state.get("run_id") or ""),
        str(state.get("profile") or ""),
        str(state.get("artifact_namespace") or ""),
    )
    if actual != expected:
        raise ValueError(f"operator state identity mismatch: expected={expected!r} actual={actual!r}")
    return state


def _state_validation_error(state: Mapping[str, Any], *, base: Path) -> str | None:
    schema_errors = schema_v1.validate_row_against_schema(state, OPERATOR_STATE_SCHEMA_ID)
    if schema_errors:
        return f"schema_error:{schema_errors[0]}"
    delivered = _nonnegative_int(state.get("send_items_delivered"))
    send_requested = state.get("send_requested") is True
    send_attempted = state.get("send_attempted") is True
    send_success = state.get("send_success") is True
    if (state.get("sent") is True) != (delivered > 0):
        return "send_delivery_fact_mismatch"
    if send_attempted and not send_requested:
        return "send_attempt_without_request"
    if delivered > 0 and not (send_requested and send_attempted):
        return "send_delivery_without_request_attempt"
    if send_success and not (send_requested and send_attempted and delivered > 0):
        return "send_success_fact_mismatch"
    if (state.get("no_send_rehearsal") is True) != (not send_attempted):
        return "no_send_fact_mismatch"
    for key in ("run_id", "profile", "artifact_namespace", "revision", "manifest_status", "artifacts", "doctor"):
        if state.get(key) in (None, "", {}):
            return f"missing_{key}"
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return "artifacts_not_object"
    missing_artifacts = set(KNOWN_ARTIFACTS) - set(artifacts)
    if missing_artifacts:
        return f"missing_artifact_entry:{sorted(missing_artifacts)[0]}"
    state_run_id = str(state.get("run_id") or "")
    for name, entry in artifacts.items():
        if name not in KNOWN_ARTIFACTS or not isinstance(entry, Mapping):
            return "invalid_artifact_entry"
        status = str(entry.get("status") or "")
        if status not in ARTIFACT_STATUSES:
            return f"invalid_artifact_status:{name}"
        if str(entry.get("run_id") or "") != state_run_id:
            return f"artifact_run_mismatch:{name}"
        if status != STATUS_CURRENT and not str(entry.get("reason") or "").strip():
            return f"missing_artifact_reason:{name}"
        path_text = str(entry.get("path") or "").strip()
        if status == STATUS_CURRENT and not path_text:
            return f"missing_current_artifact_path:{name}"
        if path_text:
            raw = Path(path_text).expanduser()
            if raw.is_absolute():
                return f"absolute_artifact_path:{name}"
            try:
                (base / raw).resolve().relative_to(base.resolve())
            except (OSError, ValueError):
                return f"artifact_path_outside_namespace:{name}"
    if str(state.get("manifest_status") or "") != _manifest_status(artifacts):
        return "manifest_status_mismatch"
    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    doctor_status = str(doctor.get("status") or "")
    if doctor_status not in DOCTOR_STATUSES:
        return "invalid_doctor_status"
    if doctor.get("authoritative") is True and not (
        doctor_status in DOCTOR_COMPLETED_STATUSES
        and doctor.get("strict") is True
        and doctor.get("schema_only") is False
        and doctor.get("skip_api_checks") is False
    ):
        return "doctor_authority_mode_mismatch"
    if doctor.get("authoritative") is True:
        if str(doctor.get("run_id") or "") != str(state.get("run_id") or ""):
            return "doctor_authority_run_mismatch"
        if _nonnegative_int(doctor.get("verified_revision")) != _nonnegative_int(state.get("revision")):
            return "doctor_authority_revision_mismatch"
        if not str(doctor.get("verified_at") or "").strip():
            return "doctor_authority_missing_verified_at"
    return None


def _manifest_status(artifacts: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = {str(entry.get("status") or "") for entry in artifacts.values()}
    if statuses & {STATUS_FAILED, STATUS_MISSING, STATUS_STALE}:
        return "incoherent"
    if STATUS_PENDING in statuses:
        return "partial"
    return "complete"


def _portable_path(path: str | Path, *, base: Path) -> str:
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raw = (Path.cwd() / raw).resolve()
    try:
        return raw.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError(f"operator artifact path outside namespace: {raw}") from exc


@contextmanager
def _state_lock(base: Path) -> Iterator[None]:
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / _LOCK_FILENAME
    with lock_path.open("a+", encoding="utf-8") as lock:
        lock_path.chmod(0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return value


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _first_timestamp(row: Mapping[str, Any], fields: Iterable[str]) -> datetime | None:
    for field in fields:
        text = str(row.get(field) or "").strip()
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        return _as_utc(parsed)
    return None


__all__ = (
    "ARTIFACT_STATUSES",
    "DOCTOR_STATUSES",
    "EventAlphaOperatorStateReadResult",
    "KNOWN_ARTIFACTS",
    "OPERATOR_STATE_FILENAME",
    "begin_run",
    "begin_run_if_newer",
    "invalidate_operator_state",
    "latest_matching_run",
    "load_operator_state",
    "operator_state_path",
    "record_artifact",
    "record_doctor_status",
    "run_is_newer_than_state",
    "state_matches_run",
    "text_has_exact_run_id",
    "write_text_artifact",
    "write_json_atomic",
)
