"""Coherent, read-only dashboard snapshot loading.

The operator state is the only generation authority.  This loader never falls
back to a timestamp-derived "latest" run and never writes or repairs artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from ... import config
from ..artifacts import fingerprints as event_alpha_fingerprints
from ..artifacts import operator_state as event_alpha_operator_state
from ..artifacts import schema_v1
from ..radar.calendar import CalendarValidationError, UnifiedCalendarEvent
from ..radar.decision_model import DECISION_MODEL_VERSION
from ..radar.decision_model_surfaces import decision_model_values
from .models import DashboardLoadError, DashboardSnapshot


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SUPPORTED_DECISION_MODEL_VERSION = DECISION_MODEL_VERSION
_ROUTES = {
    "dashboard_watch",
    "actionable_watch",
    "high_confidence_watch",
    "rapid_market_anomaly",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
    "diagnostic",
}
_SIDE_EFFECT_COUNTERS = (
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)


StateLoader = Callable[[str | Path], event_alpha_operator_state.EventAlphaOperatorStateReadResult]


@dataclass(frozen=True)
class _VerifiedArtifactBlob:
    artifact_name: str
    path: Path
    fingerprint_kind: str
    data: bytes


def _load_dashboard_operator_state(
    namespace_dir: str | Path,
) -> event_alpha_operator_state.EventAlphaOperatorStateReadResult:
    """Read operator state without reopening any manifest-referenced artifact."""

    path = event_alpha_operator_state.operator_state_path(namespace_dir)
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        return event_alpha_operator_state.EventAlphaOperatorStateReadResult(
            path=path,
            exists=False,
            valid=False,
            error="missing",
        )
    if read_error or data is None:
        return event_alpha_operator_state.EventAlphaOperatorStateReadResult(
            path=path,
            exists=True,
            valid=False,
            error=read_error or "unreadable",
        )
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return event_alpha_operator_state.EventAlphaOperatorStateReadResult(
            path=path,
            exists=True,
            valid=False,
            error=type(exc).__name__,
        )
    if not isinstance(parsed, Mapping):
        return event_alpha_operator_state.EventAlphaOperatorStateReadResult(
            path=path,
            exists=True,
            valid=False,
            error="not_object",
        )
    state = dict(parsed)
    schema_errors = schema_v1.validate_row_against_schema(
        state,
        event_alpha_operator_state.OPERATOR_STATE_SCHEMA_ID,
    )
    fatal_schema_errors = tuple(
        error
        for error in schema_errors
        if not error.startswith(
            (
                "operator_state_current_artifact_",
                "operator_state_run_ledger_",
            )
        )
    )
    return event_alpha_operator_state.EventAlphaOperatorStateReadResult(
        path=path,
        exists=True,
        valid=not fatal_schema_errors,
        state=state,
        error=f"schema_error:{fatal_schema_errors[0]}" if fatal_schema_errors else None,
    )


def load_dashboard_snapshot(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    *,
    state_loader: StateLoader = _load_dashboard_operator_state,
    max_attempts: int = 2,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> DashboardSnapshot:
    """Load one exact operator generation, retrying only a concurrent revision."""

    namespace_dir = _namespace_dir(artifact_base_dir, artifact_namespace)
    checked_at = _coerce_now(now)
    generation_age_limit = _age_limit(
        max_generation_age_hours,
        default=float(config.EVENT_ALPHA_MAX_RUN_AGE_HOURS),
        label="generation",
    )
    doctor_age_limit = _age_limit(
        max_doctor_age_hours,
        default=float(config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS),
        label="doctor",
    )
    attempts = max(1, int(max_attempts))
    last_error = "operator generation changed while dashboard artifacts were read"
    for _attempt in range(attempts):
        try:
            return _load_once(
                namespace_dir,
                state_loader=state_loader,
                now=checked_at,
                max_generation_age_hours=generation_age_limit,
                max_doctor_age_hours=doctor_age_limit,
            )
        except _GenerationChanged as exc:
            last_error = str(exc)
    raise DashboardLoadError(last_error)


def _load_once(
    namespace_dir: Path,
    *,
    state_loader: StateLoader,
    now: datetime,
    max_generation_age_hours: float,
    max_doctor_age_hours: float,
) -> DashboardSnapshot:
    before = state_loader(namespace_dir)
    state = _require_valid_state(before)
    run_id, profile, namespace, revision = _state_identity(state, namespace_dir)
    _require_zero_side_effects(state)
    state_digest = _operator_state_digest(state)
    blobs, manifest_reasons = _read_current_manifest_once(state, namespace_dir)
    authority_reasons = [*_manifest_structure_reasons(state), *manifest_reasons]

    current_candidates = _current_core_rows(
        blobs.get("core_opportunities"),
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        read_at=now,
        authority_reasons=authority_reasons,
    )
    expected_core_count = _expected_current_core_count(state)
    if expected_core_count is not None and len(current_candidates) != expected_core_count:
        authority_reasons.append("core_opportunities:current_count_mismatch")

    current_anomalies: tuple[dict[str, Any], ...] = ()
    current_calendar = _current_calendar_rows(
        blobs.get("unified_calendar"),
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    expected_calendar_count = _manifest_count(state, "unified_calendar")
    if expected_calendar_count is not None and len(current_calendar) != expected_calendar_count:
        authority_reasons.append("unified_calendar:current_count_mismatch")

    feedback_path = namespace_dir / "event_alpha_feedback.jsonl"
    integrated_outcomes_path = namespace_dir / "event_integrated_radar_outcomes.jsonl"
    legacy_outcomes_path = namespace_dir / "event_alpha_outcomes.jsonl"
    cumulative_feedback, feedback_digest, feedback_error = _read_unverified_jsonl(feedback_path)
    integrated_outcomes, integrated_outcomes_digest, integrated_outcomes_error = (
        _read_unverified_jsonl(integrated_outcomes_path)
    )
    legacy_outcomes, legacy_outcomes_digest, legacy_outcomes_error = _read_unverified_jsonl(
        legacy_outcomes_path
    )
    cumulative_outcomes = (*integrated_outcomes, *legacy_outcomes)
    cumulative_history_metadata = {
        feedback_path.name: _unverified_history_metadata(
            now,
            feedback_digest,
            feedback_error,
        ),
        integrated_outcomes_path.name: _unverified_history_metadata(
            now,
            integrated_outcomes_digest,
            integrated_outcomes_error,
        ),
        legacy_outcomes_path.name: _unverified_history_metadata(
            now,
            legacy_outcomes_digest,
            legacy_outcomes_error,
        ),
    }
    provider_readiness = _current_manifest_json(
        blobs.get("provider_readiness_json"),
        "provider_readiness_json",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    provider_health, provider_health_digest, provider_health_error = _read_unverified_json_object(
        namespace_dir / "event_provider_health.json"
    )

    after = state_loader(namespace_dir)
    after_state = _require_valid_state(after)
    _state_identity(after_state, namespace_dir)
    if state_digest != _operator_state_digest(after_state):
        raise _GenerationChanged("operator state changed while dashboard artifacts were read")

    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    authority_reasons.extend(
        _generation_authority_reasons(
            state,
            run_id=run_id,
            revision=revision,
            now=now,
            max_generation_age_hours=max_generation_age_hours,
            max_doctor_age_hours=max_doctor_age_hours,
        )
    )
    authority_reasons = list(dict.fromkeys(authority_reasons))
    authority_status = "authoritative" if not authority_reasons else "untrusted"
    return DashboardSnapshot(
        namespace_dir=namespace_dir,
        run_id=run_id,
        profile=profile,
        artifact_namespace=namespace,
        revision=revision,
        manifest_status=str(state.get("manifest_status") or "unknown"),
        doctor_status=str(doctor.get("status") or "not_run"),
        doctor_verified_revision=_optional_int(doctor.get("verified_revision")),
        generation_authority_status=authority_status,
        generation_authority_reasons=tuple(authority_reasons),
        generation_authority_checked_at=now.isoformat(),
        operator_state_sha256=state_digest,
        operator_state=state,
        current_candidates=current_candidates,
        current_market_anomalies=current_anomalies,
        current_calendar_events=tuple(dict(row) for row in current_calendar),
        cumulative_feedback=tuple(dict(row) for row in cumulative_feedback),
        cumulative_outcomes=tuple(dict(row) for row in cumulative_outcomes),
        cumulative_history_metadata=cumulative_history_metadata,
        provider_readiness=provider_readiness,
        provider_health=provider_health,
        provider_health_read_at=now.isoformat() if provider_health_digest else None,
        provider_health_sha256=provider_health_digest,
        provider_health_error=provider_health_error,
    )


def _namespace_dir(artifact_base_dir: str | Path, artifact_namespace: str) -> Path:
    namespace = str(artifact_namespace or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise DashboardLoadError("invalid dashboard artifact namespace")
    base = Path(artifact_base_dir).expanduser().resolve()
    candidate = (base / namespace).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise DashboardLoadError("dashboard namespace escapes artifact base") from exc
    return candidate


def _require_valid_state(
    result: event_alpha_operator_state.EventAlphaOperatorStateReadResult,
) -> dict[str, Any]:
    if not result.exists:
        raise DashboardLoadError("operator state is missing; dashboard will not guess the latest run")
    if not result.valid or not isinstance(result.state, Mapping):
        raise DashboardLoadError(f"operator state is invalid: {result.error or 'unknown'}")
    return dict(result.state)


def _state_identity(state: Mapping[str, Any], namespace_dir: Path) -> tuple[str, str, str, int]:
    run_id = str(state.get("run_id") or "").strip()
    profile = str(state.get("profile") or "").strip()
    namespace = str(state.get("artifact_namespace") or "").strip()
    revision = _optional_int(state.get("revision"))
    if not run_id or not profile or namespace != namespace_dir.name or revision is None:
        raise DashboardLoadError("operator state has incomplete or mismatched generation identity")
    return run_id, profile, namespace, revision


def _require_zero_side_effects(state: Mapping[str, Any]) -> None:
    if state.get("research_only") is not True:
        raise DashboardLoadError("operator generation is not marked research_only")
    for field in _SIDE_EFFECT_COUNTERS:
        value = _optional_int(state.get(field))
        if value is None:
            raise DashboardLoadError(f"operator safety counter is invalid: {field}")
        if value != 0:
            raise DashboardLoadError(f"operator safety invariant violated: {field}")


def _read_current_manifest_once(
    state: Mapping[str, Any],
    namespace_dir: Path,
) -> tuple[dict[str, _VerifiedArtifactBlob], tuple[str, ...]]:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return {}, ("manifest:artifacts_missing",)
    blobs: dict[str, _VerifiedArtifactBlob] = {}
    reasons: list[str] = []
    state_run_id = str(state.get("run_id") or "").strip()
    expected_run_identity = {
        "run_id": state_run_id,
        "profile": str(state.get("profile") or "").strip(),
        "artifact_namespace": str(state.get("artifact_namespace") or "").strip(),
    }
    for raw_name, raw_entry in sorted(artifacts.items(), key=lambda item: str(item[0])):
        name = str(raw_name)
        if not isinstance(raw_entry, Mapping):
            reasons.append(f"{name}:manifest_entry_invalid")
            continue
        if str(raw_entry.get("status") or "") != "current":
            continue
        entry = dict(raw_entry)
        if str(entry.get("run_id") or "").strip() != state_run_id:
            reasons.append(f"{name}:run_id_mismatch")
            continue
        metadata_error = event_alpha_fingerprints.fingerprint_metadata_error(entry)
        if metadata_error:
            reasons.append(f"{name}:{metadata_error}")
            continue
        target, path_error = _manifest_target(namespace_dir, entry, artifact_name=name)
        if path_error:
            reasons.append(f"{name}:{path_error}")
            continue
        if target is None or not target.exists():
            reasons.append(f"{name}:artifact_missing")
            continue
        kind = str(entry.get("fingerprint_kind") or "")
        expected_kind = _expected_fingerprint_kind(name)
        if kind != expected_kind:
            reasons.append(f"{name}:fingerprint_kind_mismatch")
            continue
        if kind == "canonical_run_row":
            raw_identity = entry.get("run_row_identity")
            run_identity = (
                {
                    field: str(raw_identity.get(field) or "").strip()
                    for field in expected_run_identity
                }
                if isinstance(raw_identity, Mapping)
                else {}
            )
            if run_identity != expected_run_identity:
                reasons.append(f"{name}:run_row_identity_mismatch")
                continue
            if not target.is_file():
                reasons.append(f"{name}:artifact_kind_mismatch")
            else:
                valid, reason = event_alpha_fingerprints.verify_run_ledger_row_fingerprint(
                    target,
                    entry,
                )
                if not valid:
                    reasons.append(f"{name}:{reason or 'fingerprint_mismatch'}")
                elif post_error := _path_symlink_error(namespace_dir, target):
                    reasons.append(f"{name}:{post_error}")
            continue
        if kind == "directory_tree_v1":
            if not target.is_dir():
                reasons.append(f"{name}:artifact_kind_mismatch")
            else:
                valid, reason = event_alpha_fingerprints.verify_path_fingerprint(target, entry)
                if not valid:
                    reasons.append(f"{name}:{reason or 'fingerprint_mismatch'}")
                elif post_error := _path_symlink_error(namespace_dir, target):
                    reasons.append(f"{name}:{post_error}")
            continue
        if kind not in {"file_bytes", "jsonl_lines"}:
            reasons.append(f"{name}:fingerprint_kind_unsupported")
            continue
        if not target.is_file():
            reasons.append(f"{name}:artifact_kind_mismatch")
            continue
        data, read_error = _read_regular_file_once(target)
        if read_error or data is None:
            reasons.append(f"{name}:{read_error or 'artifact_unreadable'}")
            continue
        if post_error := _path_symlink_error(namespace_dir, target):
            reasons.append(f"{name}:{post_error}")
            continue
        valid, reason = event_alpha_fingerprints.verify_bytes_fingerprint(data, entry)
        if not valid:
            reasons.append(f"{name}:{reason or 'fingerprint_mismatch'}")
            continue
        blobs[name] = _VerifiedArtifactBlob(
            artifact_name=name,
            path=target,
            fingerprint_kind=kind,
            data=data,
        )
    return blobs, tuple(reasons)


def _expected_fingerprint_kind(artifact_name: str) -> str:
    if artifact_name == "run_ledger":
        return "canonical_run_row"
    if artifact_name == "research_cards":
        return "directory_tree_v1"
    if artifact_name in {"core_opportunities", "unified_calendar"}:
        return "jsonl_lines"
    return "file_bytes"


def _manifest_structure_reasons(state: Mapping[str, Any]) -> tuple[str, ...]:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return ("manifest:artifacts_missing",)
    reasons: list[str] = []
    required = set(event_alpha_operator_state.KNOWN_ARTIFACTS)
    allowed = required | set(event_alpha_operator_state.OPTIONAL_ARTIFACTS)
    for missing in sorted(required - set(artifacts)):
        reasons.append(f"manifest:missing_artifact_entry:{missing}")
    statuses: set[str] = set()
    state_run_id = str(state.get("run_id") or "")
    for raw_name, raw_entry in artifacts.items():
        name = str(raw_name)
        if name not in allowed:
            reasons.append(f"manifest:unknown_artifact_entry:{name}")
        if not isinstance(raw_entry, Mapping):
            reasons.append(f"{name}:manifest_entry_invalid")
            continue
        status = str(raw_entry.get("status") or "")
        statuses.add(status)
        if status not in event_alpha_operator_state.ARTIFACT_STATUSES:
            reasons.append(f"{name}:artifact_status_invalid")
        if str(raw_entry.get("run_id") or "") != state_run_id:
            reasons.append(f"{name}:run_id_mismatch")
        if status == event_alpha_operator_state.STATUS_CURRENT:
            if not str(raw_entry.get("path") or "").strip():
                reasons.append(f"{name}:current_path_missing")
        elif not str(raw_entry.get("reason") or "").strip():
            reasons.append(f"{name}:noncurrent_reason_missing")
    incoherent = {
        event_alpha_operator_state.STATUS_FAILED,
        event_alpha_operator_state.STATUS_MISSING,
        event_alpha_operator_state.STATUS_STALE,
    }
    if statuses & incoherent:
        computed_status = "incoherent"
    elif event_alpha_operator_state.STATUS_PENDING in statuses:
        computed_status = "partial"
    else:
        computed_status = "complete"
    if str(state.get("manifest_status") or "") != computed_status:
        reasons.append("manifest:status_mismatch")
    return tuple(dict.fromkeys(reasons))


def _manifest_target(
    namespace_dir: Path,
    entry: Mapping[str, Any],
    *,
    artifact_name: str,
) -> tuple[Path | None, str | None]:
    raw = str(entry.get("path") or "").strip()
    if not raw:
        return None, None
    raw_path = Path(raw).expanduser()
    if raw_path.is_absolute():
        raise DashboardLoadError(f"operator artifact path must be relative: {artifact_name}")
    if any(part == ".." for part in raw_path.parts):
        raise DashboardLoadError(f"operator artifact escapes namespace: {artifact_name}")
    target = namespace_dir.joinpath(*raw_path.parts)
    symlink_error = _path_symlink_error(namespace_dir, target)
    return target, symlink_error


def _path_symlink_error(namespace_dir: Path, target: Path) -> str | None:
    try:
        relative = target.relative_to(namespace_dir)
    except ValueError:
        return "artifact_path_escape"
    current = namespace_dir
    for part in relative.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            return "artifact_path_unreadable"
        if stat.S_ISLNK(info.st_mode):
            return "artifact_symlink_not_allowed"
    return None


def _read_regular_file_once(path: Path) -> tuple[bytes | None, str | None]:
    """Read one regular file through a no-follow descriptor exactly once."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None, "artifact_missing"
    except OSError:
        return None, "artifact_unreadable_or_symlink"
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None, "artifact_not_regular_file"
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    except OSError:
        return None, "artifact_unreadable"
    finally:
        os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        return None, "artifact_changed_during_read"
    data = b"".join(chunks)
    if len(data) != after.st_size:
        return None, "artifact_changed_during_read"
    try:
        current = path.lstat()
    except OSError:
        return None, "artifact_changed_during_read"
    if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != (
        after.st_dev,
        after.st_ino,
    ):
        return None, "artifact_changed_during_read"
    return data, None


def _expected_current_core_count(state: Mapping[str, Any]) -> int | None:
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    entry = artifacts.get("core_opportunities") if isinstance(artifacts, Mapping) else None
    raw = entry.get("count") if isinstance(entry, Mapping) else None
    if raw in (None, ""):
        raw = state.get("current_generation_core_rows")
    if raw in (None, ""):
        return None
    count = _optional_int(raw)
    if count is None or count < 0:
        raise DashboardLoadError("current core artifact count is invalid")
    return count


def _manifest_count(state: Mapping[str, Any], artifact_name: str) -> int | None:
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    entry = artifacts.get(artifact_name) if isinstance(artifacts, Mapping) else None
    raw = entry.get("count") if isinstance(entry, Mapping) else None
    if raw in (None, ""):
        return None
    count = _optional_int(raw)
    if count is None or count < 0:
        raise DashboardLoadError(f"current {artifact_name} artifact count is invalid")
    return count


def _current_manifest_json(
    blob: _VerifiedArtifactBlob | None,
    artifact_name: str,
    *,
    run_id: str,
    profile: str,
    namespace: str,
    authority_reasons: list[str],
) -> Mapping[str, Any]:
    if blob is None:
        return {}
    try:
        parsed = json.loads(blob.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        authority_reasons.append(f"{artifact_name}:invalid_json")
        return {}
    if not isinstance(parsed, Mapping):
        authority_reasons.append(f"{artifact_name}:json_not_object")
        return {}
    payload = dict(parsed)
    for field, expected in (
        ("run_id", run_id),
        ("profile", profile),
        ("artifact_namespace", namespace),
    ):
        actual = str(payload.get(field) or "").strip()
        if actual != expected:
            authority_reasons.append(f"{artifact_name}:{field}_mismatch")
            return {}
    return payload


def _current_core_rows(
    blob: _VerifiedArtifactBlob | None,
    *,
    run_id: str,
    profile: str,
    namespace: str,
    read_at: datetime,
    authority_reasons: list[str],
) -> tuple[dict[str, Any], ...]:
    if blob is None:
        return ()
    try:
        rows = _jsonl_rows_from_blob(blob)
    except DashboardLoadError:
        authority_reasons.append("core_opportunities:invalid_jsonl")
        return ()
    current: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("row_type") or "") != "event_core_opportunity":
            continue
        if not _matches_generation(row, run_id=run_id, profile=profile, namespace=namespace):
            continue
        if schema_v1.validate_row_against_schema(row, "core_opportunity_v1"):
            authority_reasons.append("core_opportunities:schema_validation_failed")
            continue
        current.append(_dashboard_decision_row(row, read_at=read_at))
    return tuple(current)


def _current_calendar_rows(
    blob: _VerifiedArtifactBlob | None,
    *,
    run_id: str,
    profile: str,
    namespace: str,
    authority_reasons: list[str],
) -> tuple[dict[str, Any], ...]:
    if blob is None:
        return ()
    try:
        rows = _jsonl_rows_from_blob(blob)
    except DashboardLoadError:
        authority_reasons.append("unified_calendar:invalid_jsonl")
        return ()
    current: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("row_type") or "") != "event_unified_calendar_event":
            continue
        if not _matches_generation(row, run_id=run_id, profile=profile, namespace=namespace):
            continue
        if schema_v1.validate_row_against_schema(row, "unified_calendar_event_v1"):
            authority_reasons.append("unified_calendar:schema_validation_failed")
            continue
        try:
            current.append(UnifiedCalendarEvent.from_mapping(row).to_dict())
        except (CalendarValidationError, TypeError, ValueError):
            authority_reasons.append("unified_calendar:model_validation_failed")
    return tuple(current)


def _jsonl_rows_from_blob(blob: _VerifiedArtifactBlob) -> tuple[dict[str, Any], ...]:
    try:
        lines = blob.data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise DashboardLoadError(f"invalid UTF-8 in {blob.path.name}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DashboardLoadError(f"invalid JSONL in {blob.path.name}:{line_number}") from exc
        if not isinstance(payload, Mapping):
            raise DashboardLoadError(f"non-object JSONL row in {blob.path.name}:{line_number}")
        rows.append(dict(payload))
    return tuple(rows)


def _read_unverified_json_object(
    path: Path,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        return {}, None, None
    if read_error or data is None:
        return {}, None, read_error or "unreadable"
    digest = hashlib.sha256(data).hexdigest()
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, digest, "invalid_json"
    if not isinstance(payload, Mapping):
        return {}, digest, "json_not_object"
    return dict(payload), digest, None


def _read_unverified_jsonl(
    path: Path,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    rows: list[dict[str, Any]] = []
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        return (), None, None
    if read_error or data is None:
        return (), None, read_error or "unreadable"
    digest = hashlib.sha256(data).hexdigest()
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return (), digest, "invalid_utf8"
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return (), digest, f"invalid_jsonl:{line_number}"
        if not isinstance(payload, Mapping):
            return (), digest, f"non_object_jsonl:{line_number}"
        rows.append(dict(payload))
    return tuple(rows), digest, None


def _unverified_history_metadata(
    now: datetime,
    digest: str | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "authority": "cumulative_non_authoritative",
        "read_at": now.isoformat() if digest else None,
        "sha256": digest,
        "error": error,
    }


def _matches_generation(
    row: Mapping[str, Any],
    *,
    run_id: str,
    profile: str,
    namespace: str,
) -> bool:
    return (
        str(row.get("run_id") or "") == run_id
        and str(row.get("profile") or "") == profile
        and str(row.get("artifact_namespace") or "") == namespace
    )


def _dashboard_decision_row(
    row: Mapping[str, Any],
    *,
    read_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build a read-only dashboard view over the stored canonical projection.

    Expiry is a read-time safety overlay only.  The canonical route and
    ``radar_actionable`` value remain untouched so historical artifacts are not
    silently reinterpreted, while the dashboard's effective route fails closed.
    """

    out = dict(row)
    projection = decision_model_values(row)
    if projection:
        out.update(projection)
    route = str(projection.get("radar_route") or "").strip().casefold()
    complete = bool(projection) and (
        str(projection.get("decision_model_version") or "").strip()
        == SUPPORTED_DECISION_MODEL_VERSION
    )
    if route not in _ROUTES:
        complete = False
    out["_decision_model_status"] = "v2" if complete else "legacy_unclassified"
    out["_dashboard_route"] = route if complete else "diagnostic"
    checked_at = _strict_timestamp(read_at)
    expiry = _strict_timestamp(projection.get("expires_at")) if projection else None
    expired = bool(
        complete
        and projection.get("radar_actionable") is True
        and checked_at is not None
        and expiry is not None
        and expiry <= checked_at
    )
    out["_decision_expired_at_read_time"] = expired
    out["_decision_read_time_checked_at"] = (
        checked_at.isoformat() if checked_at is not None else None
    )
    out["_decision_read_time_reason"] = (
        "canonical_expiry_at_or_before_dashboard_read_time" if expired else None
    )
    if expired:
        out["_dashboard_route"] = "diagnostic"
    return out


def candidate_identifier(row: Mapping[str, Any]) -> str:
    for field in (
        "core_opportunity_id",
        "candidate_id",
        "integrated_candidate_id",
        "market_anomaly_id",
        "anomaly_id",
    ):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _generation_authority_reasons(
    state: Mapping[str, Any],
    *,
    run_id: str,
    revision: int,
    now: datetime,
    max_generation_age_hours: float,
    max_doctor_age_hours: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if str(state.get("manifest_status") or "") != "complete":
        reasons.append("manifest:not_complete")
    run_started_at = state.get("run_started_at")
    generation_time = _strict_timestamp(
        run_started_at if str(run_started_at or "").strip() else state.get("generated_at")
    )
    reasons.extend(
        _timestamp_authority_reasons(
            "generation",
            generation_time,
            now=now,
            max_age_hours=max_generation_age_hours,
        )
    )
    doctor = state.get("doctor")
    if not isinstance(doctor, Mapping):
        return tuple((*reasons, "doctor:missing"))
    if doctor.get("authoritative") is not True:
        reasons.append("doctor:not_authoritative")
    if doctor.get("strict") is not True:
        reasons.append("doctor:not_strict")
    if doctor.get("schema_only") is not False:
        reasons.append("doctor:schema_only_or_missing")
    if doctor.get("skip_api_checks") is not False:
        reasons.append("doctor:api_checks_skipped_or_missing")
    if str(doctor.get("run_id") or "") != run_id:
        reasons.append("doctor:run_id_mismatch")
    verified_revision = doctor.get("verified_revision")
    if (
        isinstance(verified_revision, bool)
        or not isinstance(verified_revision, int)
        or verified_revision != revision
    ):
        reasons.append("doctor:revision_mismatch")
    if doctor.get("status") not in {"OK", "WARN"}:
        reasons.append("doctor:status_not_authoritative")
    blocker_count = doctor.get("blocker_count")
    if isinstance(blocker_count, bool) or not isinstance(blocker_count, int):
        reasons.append("doctor:blocker_count_invalid")
    elif blocker_count != 0:
        reasons.append("doctor:blockers_present")
    warning_count = doctor.get("warning_count")
    if (
        isinstance(warning_count, bool)
        or not isinstance(warning_count, int)
        or warning_count < 0
    ):
        reasons.append("doctor:warning_count_invalid")
    if "blockers" in doctor:
        blockers = doctor.get("blockers")
        if not isinstance(blockers, (list, tuple)):
            reasons.append("doctor:blockers_invalid")
        elif blockers:
            reasons.append("doctor:blockers_present")
    doctor_time = _strict_timestamp(doctor.get("verified_at"))
    reasons.extend(
        _timestamp_authority_reasons(
            "doctor",
            doctor_time,
            now=now,
            max_age_hours=max_doctor_age_hours,
        )
    )
    return tuple(dict.fromkeys(reasons))


def _timestamp_authority_reasons(
    label: str,
    value: datetime | None,
    *,
    now: datetime,
    max_age_hours: float,
) -> tuple[str, ...]:
    if value is None:
        return (f"{label}:timestamp_invalid_or_missing",)
    age_hours = (now - value).total_seconds() / 3600.0
    if age_hours < 0:
        return (f"{label}:timestamp_in_future",)
    if age_hours > max_age_hours:
        return (f"{label}:stale",)
    return ()


def _strict_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _operator_state_digest(state: Mapping[str, Any]) -> str:
    try:
        data = json.dumps(
            state,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DashboardLoadError("operator state cannot be canonically digested") from exc
    return hashlib.sha256(data).hexdigest()


def _coerce_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise DashboardLoadError("dashboard now must include a timezone")
        return value.astimezone(timezone.utc)
    parsed = _strict_timestamp(value)
    if parsed is None:
        raise DashboardLoadError("dashboard now is invalid")
    return parsed


def _age_limit(value: float | None, *, default: float, label: str) -> float:
    try:
        limit = float(default if value is None else value)
    except (TypeError, ValueError) as exc:
        raise DashboardLoadError(f"dashboard {label} age limit is invalid") from exc
    if not math.isfinite(limit) or limit <= 0:
        raise DashboardLoadError(f"dashboard {label} age limit is invalid")
    return limit


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class _GenerationChanged(RuntimeError):
    pass


__all__ = (
    "SUPPORTED_DECISION_MODEL_VERSION",
    "candidate_identifier",
    "load_dashboard_snapshot",
)
