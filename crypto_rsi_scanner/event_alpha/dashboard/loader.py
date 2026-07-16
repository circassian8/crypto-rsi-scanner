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
from ..radar import source_independence_store as event_source_independence_store
from .history import load_dashboard_history, read_unverified_json_object_bytes
from .models import DashboardLoadError, DashboardSnapshot, build_dashboard_snapshot
from .secure_reader import (
    AnchoredNamespaceReader,
    _DashboardNamespaceReadError,
    compare_fingerprint_values,
    open_anchored_namespace,
    verify_run_ledger_bytes,
)


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
    return _operator_state_from_bytes(path, data=data, read_error=read_error)


def _operator_state_from_bytes(
    path: Path,
    *,
    data: bytes | None,
    read_error: str | None,
) -> event_alpha_operator_state.EventAlphaOperatorStateReadResult:
    """Parse one already-read operator-state buffer."""

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


def _read_operator_state(
    reader: AnchoredNamespaceReader,
    *,
    state_loader: StateLoader,
) -> event_alpha_operator_state.EventAlphaOperatorStateReadResult:
    """Read production state through the namespace fd; keep test loaders injectable."""

    if state_loader is _load_dashboard_operator_state:
        path = event_alpha_operator_state.operator_state_path(reader.namespace_dir)
        data, read_error = reader.read_bytes(path.name)
        return _operator_state_from_bytes(path, data=data, read_error=read_error)
    reader.assert_current()
    result = state_loader(reader.namespace_dir)
    reader.assert_current()
    return result


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
            with open_anchored_namespace(namespace_dir) as reader:
                return _load_once(
                    namespace_dir,
                    reader=reader,
                    state_loader=state_loader,
                    now=checked_at,
                    max_generation_age_hours=generation_age_limit,
                    max_doctor_age_hours=doctor_age_limit,
                )
        except _GenerationChanged as exc:
            last_error = str(exc)
        except _DashboardNamespaceReadError as exc:
            raise DashboardLoadError(str(exc)) from exc
    raise DashboardLoadError(last_error)


def _load_once(
    namespace_dir: Path,
    *,
    reader: AnchoredNamespaceReader,
    state_loader: StateLoader,
    now: datetime,
    max_generation_age_hours: float,
    max_doctor_age_hours: float,
) -> DashboardSnapshot:
    before = _read_operator_state(reader, state_loader=state_loader)
    state = _require_valid_state(before)
    run_id, profile, namespace, revision = _state_identity(state, namespace_dir)
    _require_zero_side_effects(state)
    state_digest = _operator_state_digest(state)
    blobs, manifest_reasons = _read_current_manifest_once(
        state,
        namespace_dir,
        reader=reader,
    )
    authority_reasons = [*_manifest_structure_reasons(state), *manifest_reasons]

    current_rows = _load_current_rows(
        state,
        blobs=blobs,
        reader=reader,
        identity=(run_id, profile, namespace),
        read_at=now,
        authority_reasons=authority_reasons,
    )
    current_candidates, current_anomalies, current_market_observations, current_calendar = (
        current_rows
    )

    exact_artifacts = {
        name: {
            "data": blob.data,
            "fingerprint_kind": blob.fingerprint_kind,
            "path_name": blob.path.name,
        }
        for name in ("market_history", "integrated_outcomes", "market_no_send_request_ledger")
        if (blob := blobs.get(name)) is not None
    }
    history = load_dashboard_history(
        namespace_dir,
        integrated_outcomes_data=None,
        now=now,
        namespace_reader=lambda path: _read_namespace_path(
            path,
            namespace_dir=namespace_dir,
            reader=reader,
            blobs=blobs,
        ),
        exact_artifacts=exact_artifacts,
        identity=(run_id, profile, namespace),
        current_artifact_names=_current_manifest_artifact_names(state),
    )
    authority_reasons.extend(history["exact_support_authority_reasons"])
    for artifact_name, metadata_name in (
        ("market_history", "exact_market_history_metadata"),
        ("integrated_outcomes", "current_outcomes_metadata"),
        ("market_no_send_request_ledger", "current_request_ledger_metadata"),
    ):
        _check_optional_artifact_count(
            state,
            blobs=blobs,
            artifact_name=artifact_name,
            actual=int(history[metadata_name].get("source_row_count") or 0),
            authority_reasons=authority_reasons,
        )

    source_coverage = _current_manifest_json(
        blobs.get("source_coverage_json"),
        "source_coverage_json",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    market_generation = _current_manifest_json(
        blobs.get("market_no_send_generation"),
        "market_no_send_generation",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    provider_readiness = _current_manifest_json(
        blobs.get("provider_readiness_json"),
        "provider_readiness_json",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    provider_health_data, provider_health_read_error = _read_namespace_path(
        namespace_dir / "event_provider_health.json",
        namespace_dir=namespace_dir,
        reader=reader,
        blobs=blobs,
    )
    provider_health, provider_health_digest, provider_health_error = (
        read_unverified_json_object_bytes(
            provider_health_data,
            read_error=provider_health_read_error,
        )
    )

    after = _read_operator_state(reader, state_loader=state_loader)
    after_state = _require_valid_state(after)
    _state_identity(after_state, namespace_dir)
    if state_digest != _operator_state_digest(after_state):
        raise _GenerationChanged("operator state changed while dashboard artifacts were read")

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
    return build_dashboard_snapshot(
        namespace_dir,
        identity=(run_id, profile, namespace, revision),
        state=state,
        state_digest=state_digest,
        now=now,
        authority_reasons=authority_reasons,
        current_rows=current_rows,
        current_metadata=(source_coverage, market_generation, provider_readiness),
        exact_supporting_data=history,
        history=history,
        provider_health=(provider_health, provider_health_digest, provider_health_error),
    )


def _load_current_rows(
    state: Mapping[str, Any],
    *,
    blobs: Mapping[str, _VerifiedArtifactBlob],
    reader: AnchoredNamespaceReader,
    identity: tuple[str, str, str],
    read_at: datetime,
    authority_reasons: list[str],
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    """Load and count-check the exact current trader-facing row artifacts."""

    run_id, profile, namespace = identity
    candidates = _current_core_rows(
        blobs.get("core_opportunities"),
        reader=reader,
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        read_at=read_at,
        authority_reasons=authority_reasons,
    )
    expected_core = _expected_current_core_count(state)
    if expected_core is not None and len(candidates) != expected_core:
        authority_reasons.append("core_opportunities:current_count_mismatch")
    anomalies = _current_generation_jsonl_rows(
        blobs.get("market_anomalies"),
        "market_anomalies",
        row_type="event_market_anomaly",
        schema_name="market_anomaly_v1",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    _check_optional_artifact_count(
        state,
        blobs=blobs,
        artifact_name="market_anomalies",
        actual=len(anomalies),
        authority_reasons=authority_reasons,
    )
    snapshot_blob = blobs.get("market_state_snapshots")
    if snapshot_blob is not None:
        observations = _current_generation_jsonl_rows(
            snapshot_blob,
            "market_state_snapshots",
            row_type="event_market_state_snapshot",
            schema_name="market_state_snapshot_v1",
            run_id=run_id,
            profile=profile,
            namespace=namespace,
            authority_reasons=authority_reasons,
        )
    else:
        source_cache = _current_manifest_json(
            blobs.get("market_no_send_source_cache"),
            "market_no_send_source_cache",
            run_id=run_id,
            profile=profile,
            namespace=namespace,
            authority_reasons=authority_reasons,
        )
        observations = _current_market_observation_rows(
            source_cache,
            authority_reasons=authority_reasons,
        )
    _check_optional_artifact_count(
        state,
        blobs=blobs,
        artifact_name="market_state_snapshots",
        actual=len(observations),
        authority_reasons=authority_reasons,
    )
    calendar = _current_calendar_rows(
        blobs.get("unified_calendar"),
        run_id=run_id,
        profile=profile,
        namespace=namespace,
        authority_reasons=authority_reasons,
    )
    expected_calendar = _manifest_count(state, "unified_calendar")
    if expected_calendar is not None and len(calendar) != expected_calendar:
        authority_reasons.append("unified_calendar:current_count_mismatch")
    return candidates, anomalies, observations, calendar


def _check_optional_artifact_count(
    state: Mapping[str, Any],
    *,
    blobs: Mapping[str, _VerifiedArtifactBlob],
    artifact_name: str,
    actual: int,
    authority_reasons: list[str],
) -> None:
    if blobs.get(artifact_name) is None:
        return
    expected = _manifest_count(state, artifact_name)
    if expected is not None and actual != expected:
        authority_reasons.append(f"{artifact_name}:current_count_mismatch")


def _current_manifest_artifact_names(state: Mapping[str, Any]) -> frozenset[str]:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return frozenset()
    return frozenset(
        str(name)
        for name, entry in artifacts.items()
        if isinstance(entry, Mapping) and entry.get("status") == "current"
    )


def _read_namespace_path(
    path: Path,
    *,
    namespace_dir: Path,
    reader: AnchoredNamespaceReader,
    blobs: Mapping[str, _VerifiedArtifactBlob],
) -> tuple[bytes | None, str | None]:
    """Reuse a verified buffer or read one non-manifest namespace file safely."""

    for blob in blobs.values():
        if blob.path == path:
            return blob.data, None
    try:
        relative = path.relative_to(namespace_dir)
    except ValueError:
        return None, "artifact_path_escape"
    data, error = reader.read_bytes(relative)
    if error == "artifact_symlink_not_allowed":
        return None, "artifact_unreadable_or_symlink"
    return data, error


def _namespace_dir(artifact_base_dir: str | Path, artifact_namespace: str) -> Path:
    namespace = str(artifact_namespace or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise DashboardLoadError("invalid dashboard artifact namespace")
    base = Path(artifact_base_dir).expanduser().resolve()
    return base / namespace


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
    *,
    reader: AnchoredNamespaceReader,
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
        if target is None:
            reasons.append(f"{name}:artifact_missing")
            continue
        relative = target.relative_to(namespace_dir)
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
            data, read_error = reader.read_bytes(relative)
            if read_error or data is None:
                reasons.append(f"{name}:{read_error or 'artifact_unreadable'}")
                continue
            valid, reason = verify_run_ledger_bytes(data, entry)
            if not valid:
                reasons.append(f"{name}:{reason or 'fingerprint_mismatch'}")
            continue
        if kind == "directory_tree_v1":
            actual, read_error = reader.fingerprint_directory(relative)
            if read_error or actual is None:
                reasons.append(f"{name}:{read_error or 'artifact_unreadable'}")
                continue
            valid, reason = compare_fingerprint_values(actual, entry)
            if not valid:
                reasons.append(f"{name}:{reason or 'fingerprint_mismatch'}")
            continue
        if kind not in {"file_bytes", "jsonl_lines"}:
            reasons.append(f"{name}:fingerprint_kind_unsupported")
            continue
        data, read_error = reader.read_bytes(relative)
        if read_error or data is None:
            reasons.append(f"{name}:{read_error or 'artifact_unreadable'}")
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
    if artifact_name in {
        "research_cards",
        "source_independence_contract_store",
    }:
        return "directory_tree_v1"
    if artifact_name in {
        "core_opportunities",
        "unified_calendar",
        "market_history",
        "market_state_snapshots",
        "market_anomalies",
        "market_anomaly_catalyst_search_queue",
        "integrated_candidates",
        "integrated_outcomes",
    }:
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
    return target, None


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


def _current_market_observation_rows(
    payload: Mapping[str, Any],
    *,
    authority_reasons: list[str],
) -> tuple[dict[str, Any], ...]:
    """Return exact-generation market rows from the fingerprinted source cache."""

    if not payload:
        return ()
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        authority_reasons.append("market_no_send_source_cache:rows_invalid")
        return ()
    if any(not isinstance(row, Mapping) for row in raw_rows):
        authority_reasons.append("market_no_send_source_cache:row_not_object")
        return ()
    rows = tuple(dict(row) for row in raw_rows)
    expected = _optional_int(payload.get("selected_market_row_count"))
    if expected is None or expected < 0:
        authority_reasons.append("market_no_send_source_cache:selected_count_invalid")
    elif expected != len(rows):
        authority_reasons.append("market_no_send_source_cache:selected_count_mismatch")
    return rows


def _current_generation_jsonl_rows(
    blob: _VerifiedArtifactBlob | None,
    artifact_name: str,
    *,
    row_type: str,
    schema_name: str,
    run_id: str,
    profile: str,
    namespace: str,
    authority_reasons: list[str],
) -> tuple[dict[str, Any], ...]:
    """Return one exact, schema-valid generation from a fingerprinted JSONL artifact."""

    if blob is None:
        return ()
    try:
        rows = _jsonl_rows_from_blob(blob)
    except DashboardLoadError:
        authority_reasons.append(f"{artifact_name}:invalid_jsonl")
        return ()
    if any(str(row.get("row_type") or "") != row_type for row in rows):
        authority_reasons.append(f"{artifact_name}:row_type_mismatch")
        return ()
    if any(
        not _matches_generation(row, run_id=run_id, profile=profile, namespace=namespace)
        for row in rows
    ):
        authority_reasons.append(f"{artifact_name}:generation_lineage_mismatch")
        return ()
    if any(schema_v1.validate_row_against_schema(row, schema_name) for row in rows):
        authority_reasons.append(f"{artifact_name}:schema_validation_failed")
        return ()
    return tuple(dict(row) for row in rows)


def _current_core_rows(
    blob: _VerifiedArtifactBlob | None,
    *,
    reader: AnchoredNamespaceReader,
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
    contract_cache: dict[bytes, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("row_type") or "") != "event_core_opportunity":
            continue
        if not _matches_generation(row, run_id=run_id, profile=profile, namespace=namespace):
            continue
        if schema_v1.validate_row_against_schema(row, "core_opportunity_v1"):
            authority_reasons.append("core_opportunities:schema_validation_failed")
            continue
        try:
            hydrated = _hydrate_source_independence_references(
                row,
                reader=reader,
                cache=contract_cache,
            )
        except event_source_independence_store.SourceIndependenceStoreError as exc:
            authority_reasons.append(
                "core_opportunities:source_independence_reference_invalid:"
                + str(exc)[:200]
            )
            continue
        current.append(_dashboard_decision_row(hydrated, read_at=read_at))
    return tuple(current)


def _hydrate_source_independence_references(
    value: Any,
    *,
    reader: AnchoredNamespaceReader,
    cache: dict[bytes, dict[str, Any]],
    max_nodes: int = 100_000,
) -> Any:
    """Resolve exact store references through the already-anchored namespace."""

    visited = 0

    def _hydrate(current: Any) -> Any:
        nonlocal visited
        visited += 1
        if visited > max_nodes:
            raise event_source_independence_store.SourceIndependenceStoreError(
                "source_independence_dashboard_node_limit_exceeded"
            )
        if isinstance(current, Mapping):
            if (
                current.get("schema_id")
                == event_source_independence_store.REFERENCE_SCHEMA_ID
            ):
                errors = event_source_independence_store.validate_reference(current)
                if errors:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_reference_invalid:" + ",".join(errors)
                    )
                try:
                    key = event_alpha_fingerprints.canonical_json_bytes(
                        dict(current)
                    )
                except event_alpha_fingerprints.FingerprintError as exc:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_reference_canonicalization_failed"
                    ) from exc
                cached = cache.get(key)
                if cached is not None:
                    return dict(cached)
                raw, read_error = reader.read_bytes(current["artifact_relative_path"])
                if read_error or raw is None:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_store_blob_unreadable:"
                        + str(read_error or "missing")
                    )
                contract = event_source_independence_store.resolve_bytes(current, raw)
                cache[key] = contract
                return dict(contract)
            return {key: _hydrate(item) for key, item in current.items()}
        if isinstance(current, list):
            return [_hydrate(item) for item in current]
        return current

    return _hydrate(value)


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
    Expiry applies to every complete Decision v2 row independently of canonical
    actionability: a watch/review idea with a closed research window is no more
    current than an actionable idea with the same closed window.
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
        return event_alpha_operator_state.operator_authority_digest(state)
    except (TypeError, ValueError) as exc:
        raise DashboardLoadError("operator state cannot be canonically digested") from exc


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
