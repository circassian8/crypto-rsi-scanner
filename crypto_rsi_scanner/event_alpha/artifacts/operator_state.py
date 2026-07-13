"""Atomic current-generation state for Event Alpha operator artifacts.

The state file is deliberately small and bounded: every completed cycle replaces
the prior generation, then later local report commands update only that same
generation.  It is research metadata only and cannot route or send anything.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from . import fingerprints as artifact_fingerprints
from . import operator_state_fingerprints as operator_fingerprint_helpers
from . import run_counters, schema_v1


_resolve_namespace_artifact_path = operator_fingerprint_helpers.resolve_namespace_artifact_path
_portable_path = operator_fingerprint_helpers.portable_path


OPERATOR_STATE_FILENAME = "event_alpha_operator_state.json"
_LOCK_FILENAME = ".event_alpha_operator_state.lock"
OPERATOR_STATE_SCHEMA_ID = "operator_state_v1"
OPERATOR_STATE_ROW_TYPE = "event_alpha_operator_state"
DECISION_MODEL_V2_VERSION = "crypto_radar_decision_model_v2"

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
OPTIONAL_ARTIFACTS = (
    "unified_calendar",
    "decision_v2_notification_preview",
    "market_no_send_source_cache",
    "market_no_send_request_ledger",
    "market_no_send_generation",
    "market_no_send_calendar_source",
    "market_history",
    "market_state_snapshots",
    "market_anomalies",
    "market_anomaly_catalyst_search_queue",
    "integrated_candidates",
    "integrated_outcomes",
    "provider_health",
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
    "unified_calendar": ("unified_calendar_path",),
    "decision_v2_notification_preview": ("decision_v2_notification_preview_path",),
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


def operator_authority_digest(state: Mapping[str, Any]) -> str:
    """Return the stable fingerprint for one exact operator authority.

    A full strict doctor may be rerun against an unchanged revision.  Its
    verification clock is freshness evidence, not generation identity, so the
    two clock-only fields written by :func:`record_doctor_status` are excluded.
    Every substantive doctor value and the complete artifact manifest remain
    bound into the digest.
    """

    stable = dict(state)
    stable.pop("updated_at", None)
    doctor = stable.get("doctor")
    if isinstance(doctor, Mapping):
        stable_doctor = dict(doctor)
        stable_doctor.pop("verified_at", None)
        stable["doctor"] = stable_doctor
    data = json.dumps(
        stable,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
    try:
        raw = artifact_fingerprints.read_regular_file_bytes(path)
    except artifact_fingerprints.FingerprintError as exc:
        exists = os.path.lexists(path)
        return EventAlphaOperatorStateReadResult(
            path=path,
            exists=exists,
            valid=False,
            error=str(exc) if exists else "missing",
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return EventAlphaOperatorStateReadResult(path=path, exists=True, valid=False, error=type(exc).__name__)
    if not isinstance(parsed, Mapping):
        return EventAlphaOperatorStateReadResult(path=path, exists=True, valid=False, error="not_object")
    state = _downgrade_legacy_doctor_authority(dict(parsed), base=path.parent)
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
    authoritative_row = enrich_run_row_from_core_store(base, run_row)
    state = _build_run_state(
        base,
        authoritative_row,
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
    authoritative_row = enrich_run_row_from_core_store(base, run_row)
    candidate = _build_run_state(
        base,
        authoritative_row,
        run_ledger_path=run_ledger_path,
        updated_at=updated_at,
    )
    with _state_lock(base):
        loaded = load_operator_state(base)
        if loaded.valid and loaded.state is not None:
            current = dict(loaded.state)
            if state_matches_run(
                current,
                authoritative_row,
                profile=str(candidate["profile"]),
                artifact_namespace=str(candidate["artifact_namespace"]),
            ):
                return _backfill_same_run_state(
                    base,
                    current,
                    authoritative_row,
                    updated_at=updated_at,
                )
            if not run_is_newer_than_state(authoritative_row, current):
                return None
        write_json_atomic(operator_state_path(base), candidate)
    return candidate


def enrich_run_row_from_core_store(
    namespace_dir: str | Path,
    run_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an exact-run counter projection enriched by its canonical store.

    Legacy run rows predate visible-generation and cumulative-store counters.
    The core JSONL is safe read-only evidence for those scopes, but only when
    its path stays inside the requested namespace and rows match the exact
    persisted run id.
    """

    base = Path(namespace_dir).expanduser()
    enriched = dict(run_row)
    raw_path = str(run_row.get("core_opportunity_store_path") or "").strip()
    run_id = str(run_row.get("run_id") or "").strip()
    if not raw_path or not run_id:
        return enriched
    resolved = _resolve_namespace_artifact_path(base, raw_path)
    if resolved is None:
        return enriched
    try:
        from ..radar import core_opportunities as event_core_opportunities
        from ..radar import core_opportunity_store as event_core_opportunity_store

        current = event_core_opportunity_store.load_core_opportunities(
            resolved,
            run_id=run_id,
            include_api=True,
        )
        visible = event_core_opportunities.visible_core_opportunities(current.rows)
    except (OSError, ValueError, TypeError):
        return enriched
    enriched.update(
        {
            "current_generation_core_rows": int(current.rows_read),
            "current_generation_visible_core_rows": len(visible),
            "cumulative_store_rows": int(current.total_rows_read),
            **_decision_model_summary(
                current.rows,
                configured_enabled=run_row.get("decision_model_v2_enabled") is True,
            ),
        }
    )
    preview_path = _resolve_namespace_artifact_path(
        base,
        str(run_row.get("notification_preview_path") or OPERATOR_STATE_FILENAME).replace(
            OPERATOR_STATE_FILENAME,
            "event_alpha_notification_preview.md",
        ),
    )
    if preview_path is not None:
        try:
            preview_text = preview_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            preview_text = ""
        if text_has_exact_run_id(preview_text, run_id):
            rendered = re.search(
                r"(?im)^(?:-\s*)?(?:preview_rendered_items|Rendered candidate items):\s*(\d+)\b",
                preview_text,
            )
            if rendered:
                enriched["preview_rendered_items"] = int(rendered.group(1))
    return enriched


def _build_run_state(
    base: Path,
    run_row: Mapping[str, Any],
    *,
    run_ledger_path: str | Path | None,
    updated_at: datetime | None,
) -> dict[str, Any]:
    run_id = _require_identity_string(run_row, "run_id")
    profile = _require_identity_string(run_row, "profile", default="default")
    namespace = _require_identity_string(run_row, "artifact_namespace", default=base.name)
    now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
    counters = run_counters.canonical_run_counters(run_row)
    decision_summary = _decision_model_summary_from_run(run_row)
    send_state = run_counters.canonical_send_state(run_row)
    send_requested = send_state["send_requested"] is True
    send_attempted = send_state["send_attempted"] is True
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
    for name in OPTIONAL_ARTIFACTS:
        entry = _initial_artifact_entry(name, base=base, run_id=run_id, run_row=artifact_run_row, now=now)
        if entry["status"] != STATUS_SKIPPED:
            artifacts[name] = entry
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
        "counter_schema_version": run_counters.COUNTER_SCHEMA_VERSION,
        **counters,
        **decision_summary,
        "burn_in_mode": send_state["burn_in_mode"],
        "send_guard_status": send_state["send_guard_status"],
        "no_send_rehearsal": send_state["no_send_rehearsal"],
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


def _backfill_same_run_state(
    base: Path,
    state: dict[str, Any],
    run_row: Mapping[str, Any],
    *,
    updated_at: datetime | None,
) -> dict[str, Any]:
    """Backfill exact-run semantics without replacing its artifact manifest.

    Report and preview regeneration frequently revisit an already-created
    generation.  Adding new run-scoped fields must preserve every artifact
    status/path while making the exact persisted run row authoritative for the
    canonical counters and factual no-send state.
    """

    counters = run_counters.canonical_run_counters(run_row)
    send_state = run_counters.canonical_send_state(run_row)
    projection: dict[str, Any] = {
        "counter_schema_version": run_counters.COUNTER_SCHEMA_VERSION,
        **counters,
        **_decision_model_summary_from_run(run_row),
        "burn_in_mode": send_state["burn_in_mode"],
        "send_guard_status": send_state["send_guard_status"],
        "send_requested": send_state["send_requested"],
        "send_attempted": send_state["send_attempted"],
        "no_send_rehearsal": send_state["no_send_rehearsal"],
    }
    if all(state.get(key) == value for key, value in projection.items()):
        return state

    now = _as_utc(updated_at or datetime.now(timezone.utc)).isoformat()
    state.update(projection)
    state["revision"] = int(state.get("revision") or 0) + 1
    state["updated_at"] = now
    state["invalidation_reason"] = "exact_run_semantics_backfilled"
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


def _decision_model_summary(
    rows: Iterable[Mapping[str, Any]],
    *,
    configured_enabled: bool | None = None,
) -> dict[str, Any]:
    """Summarize only explicitly versioned v2 rows from one exact generation."""

    versioned = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("decision_model_version") or "").strip()
        == DECISION_MODEL_V2_VERSION
        and row.get("decision_model_enabled") is True
        and str(row.get("radar_route") or "").strip()
        and str(row.get("confidence_band") or "").strip()
    ]
    route_counts = Counter(str(row.get("radar_route")) for row in versioned)
    confidence_counts = Counter(str(row.get("confidence_band")) for row in versioned)
    thesis_counts = Counter(str(row.get("thesis_origin") or "unknown") for row in versioned)
    catalyst_counts = Counter(str(row.get("catalyst_status") or "unknown") for row in versioned)
    bias_counts = Counter(str(row.get("directional_bias") or "neutral") for row in versioned)
    timing_counts = Counter(str(row.get("timing_state") or "unknown") for row in versioned)
    tradability_counts = Counter(str(row.get("tradability_status") or "unknown") for row in versioned)
    enabled = bool(versioned) if configured_enabled is None else configured_enabled
    return {
        "decision_model_version": DECISION_MODEL_V2_VERSION if enabled else None,
        "decision_model_v2_enabled": enabled,
        "decision_model_v2_row_count": len(versioned),
        "radar_route_counts": dict(sorted(route_counts.items())),
        "confidence_band_counts": dict(sorted(confidence_counts.items())),
        "thesis_origin_counts": dict(sorted(thesis_counts.items())),
        "directional_bias_counts": dict(sorted(bias_counts.items())),
        "catalyst_status_counts": dict(sorted(catalyst_counts.items())),
        "timing_state_counts": dict(sorted(timing_counts.items())),
        "tradability_status_counts": dict(sorted(tradability_counts.items())),
        "actionable_research_ideas": sum(
            1
            for row in versioned
            if row.get("radar_actionable") is True
        ),
        "high_confidence_research_ideas": confidence_counts.get("high_confidence", 0),
    }


def _decision_model_summary_from_run(run_row: Mapping[str, Any]) -> dict[str, Any]:
    """Project persisted v2 summary fields without inferring them for old runs."""

    enabled = run_row.get("decision_model_v2_enabled") is True
    return {
        "decision_model_version": run_row.get("decision_model_version") if enabled else None,
        "decision_model_v2_enabled": enabled,
        "decision_model_v2_row_count": _nonnegative_int(run_row.get("decision_model_v2_row_count")) if enabled else 0,
        "radar_route_counts": dict(run_row.get("radar_route_counts") or {}) if enabled else {},
        "confidence_band_counts": dict(run_row.get("confidence_band_counts") or {}) if enabled else {},
        "thesis_origin_counts": dict(run_row.get("thesis_origin_counts") or {}) if enabled else {},
        "directional_bias_counts": dict(run_row.get("directional_bias_counts") or {}) if enabled else {},
        "catalyst_status_counts": dict(run_row.get("catalyst_status_counts") or {}) if enabled else {},
        "timing_state_counts": dict(run_row.get("timing_state_counts") or {}) if enabled else {},
        "tradability_status_counts": dict(run_row.get("tradability_status_counts") or {}) if enabled else {},
        "actionable_research_ideas": _nonnegative_int(run_row.get("actionable_research_ideas")) if enabled else 0,
        "high_confidence_research_ideas": _nonnegative_int(run_row.get("high_confidence_research_ideas")) if enabled else 0,
    }


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

    if name not in {*KNOWN_ARTIFACTS, *OPTIONAL_ARTIFACTS}:
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

    if name not in {*KNOWN_ARTIFACTS, *OPTIONAL_ARTIFACTS}:
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
    if status == STATUS_CURRENT and path is not None:
        entry = _fingerprinted_artifact_entry(
            name,
            base=base,
            run_id=run_id,
            profile=str(state.get("profile") or "default"),
            artifact_namespace=str(state.get("artifact_namespace") or base.name),
            path=path,
            now=now,
            count=count,
        )
    else:
        entry = {
            "status": status,
            "run_id": str(run_id),
            "path": _portable_path(path, base=base) if path is not None else None,
            "generated_at": now,
            "reason": reason,
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

    verified_revision = _require_nonnegative_int(expected_revision, field="expected_revision")
    verified_blocker_count = _require_nonnegative_int(blocker_count, field="blocker_count")
    verified_warning_count = _require_nonnegative_int(warning_count, field="warning_count")
    if status not in DOCTOR_COMPLETED_STATUSES:
        raise ValueError(f"invalid completed doctor status: {status}")
    if not strict or schema_only or skip_api_checks:
        raise ValueError("only a full strict doctor can verify operator state")
    base = Path(namespace_dir).expanduser()
    with _state_lock(base):
        state = _require_matching_state(base, run_id, profile, artifact_namespace)
        current_revision = int(state.get("revision") or 0)
        if current_revision != verified_revision:
            raise ValueError(
                "operator state revision mismatch: "
                f"expected={verified_revision} actual={current_revision}"
            )
        if str(state.get("manifest_status") or "") != "complete":
            raise ValueError("operator state manifest is not complete")
        fingerprint_error = operator_artifact_fingerprint_error(
            state,
            base=base,
            require_complete=True,
        )
        if fingerprint_error:
            raise ValueError(f"operator artifact fingerprint authority unavailable: {fingerprint_error}")
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
            "blocker_count": verified_blocker_count,
            "warning_count": verified_warning_count,
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
        if path is None and run_row.get("research_cards_dir"):
            candidate = run_row.get("research_cards_dir")
            resolved = _resolve_namespace_artifact_path(base, candidate)
            if resolved is not None and (resolved / "index.md").is_file():
                # A Decision generation with no visible ideas still renders an
                # exact-run empty index. Keep that canonical zero distinct from
                # a cycle that never wrote the card surface.
                path = candidate
        if path is None and (paths or cards_written):
            path = base / "research_cards"
    else:
        path = next(
            (run_row.get(field) for field in _RUN_PATH_FIELDS.get(name, ()) if run_row.get(field)),
            None,
        )
    if path:
        return _fingerprinted_artifact_entry(
            name,
            base=base,
            run_id=run_id,
            profile=str(run_row.get("profile") or "default"),
            artifact_namespace=str(run_row.get("artifact_namespace") or base.name),
            path=path,
            now=now,
            count=(
                _nonnegative_int(run_row.get("current_generation_core_rows"))
                if name == "core_opportunities"
                else _nonnegative_int(run_row.get("unified_calendar_rows"))
                if name == "unified_calendar"
                else None
            ),
        )
    return {
        "status": STATUS_SKIPPED,
        "run_id": run_id,
        "path": None,
        "generated_at": now,
        "reason": "not_written_by_cycle",
    }


def _fingerprinted_artifact_entry(
    name: str,
    *,
    base: Path,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    path: str | Path,
    now: str,
    count: int | None,
) -> dict[str, Any]:
    return operator_fingerprint_helpers.fingerprinted_artifact_entry(
        name,
        base=base,
        run_id=run_id,
        profile=profile,
        artifact_namespace=artifact_namespace,
        path=path,
        now=now,
        count=count,
        current_status=STATUS_CURRENT,
        missing_status=STATUS_MISSING,
        failed_status=STATUS_FAILED,
    )


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


def operator_artifact_fingerprint_error(
    state: Mapping[str, Any],
    *,
    base: str | Path,
    require_complete: bool,
) -> str | None:
    """Validate current artifact fingerprints without upgrading legacy entries.

    Missing v1 metadata remains readable when ``require_complete`` is false so
    historical operator states can still power status/Health surfaces.  Any
    present v1 contract is validated strictly, and authority callers require a
    complete verified contract for every current artifact.
    """

    return operator_fingerprint_helpers.operator_artifact_fingerprint_error(
        state,
        base=base,
        require_complete=require_complete,
        current_status=STATUS_CURRENT,
    )


def state_has_complete_artifact_fingerprints(
    state: Mapping[str, Any],
    *,
    base: str | Path,
) -> bool:
    """Return whether every current artifact has a verified v1 contract."""

    return operator_artifact_fingerprint_error(
        state,
        base=base,
        require_complete=True,
    ) is None


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
    for key in ("run_id", "profile", "artifact_namespace"):
        value = state.get(key)
        if not isinstance(value, str) or value != value.strip():
            return f"invalid_identity:{key}"
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return "artifacts_not_object"
    missing_artifacts = set(KNOWN_ARTIFACTS) - set(artifacts)
    if missing_artifacts:
        return f"missing_artifact_entry:{sorted(missing_artifacts)[0]}"
    state_run_id = str(state.get("run_id") or "")
    for name, entry in artifacts.items():
        if name not in {*KNOWN_ARTIFACTS, *OPTIONAL_ARTIFACTS} or not isinstance(entry, Mapping):
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
    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    doctor_status_value = doctor.get("status")
    if not isinstance(doctor_status_value, str) or doctor_status_value not in DOCTOR_STATUSES:
        return "invalid_doctor_status"
    doctor_authoritative = doctor.get("authoritative") is True
    if doctor_authoritative:
        revision = state.get("revision")
        verified_revision = doctor.get("verified_revision")
        if not _is_nonnegative_int(revision):
            return "doctor_authority_invalid_revision"
        if not _is_nonnegative_int(verified_revision):
            return "doctor_authority_invalid_verified_revision"
        if verified_revision != revision:
            return "doctor_authority_revision_mismatch"
        for field in ("blocker_count", "warning_count"):
            if not _is_nonnegative_int(doctor.get(field)):
                return f"doctor_authority_invalid_{field}"
    fingerprint_error = operator_artifact_fingerprint_error(
        state,
        base=base,
        require_complete=doctor_authoritative,
    )
    if fingerprint_error:
        return fingerprint_error
    if str(state.get("manifest_status") or "") != _manifest_status(artifacts):
        return "manifest_status_mismatch"
    doctor_status = doctor_status_value
    if doctor_authoritative and not (
        doctor_status in DOCTOR_COMPLETED_STATUSES
        and doctor.get("strict") is True
        and doctor.get("schema_only") is False
        and doctor.get("skip_api_checks") is False
    ):
        return "doctor_authority_mode_mismatch"
    if doctor_authoritative:
        if str(doctor.get("run_id") or "") != str(state.get("run_id") or ""):
            return "doctor_authority_run_mismatch"
        if not str(doctor.get("verified_at") or "").strip():
            return "doctor_authority_missing_verified_at"
    return None


def _downgrade_legacy_doctor_authority(
    state: dict[str, Any],
    *,
    base: Path,
) -> dict[str, Any]:
    return operator_fingerprint_helpers.downgrade_legacy_doctor_authority(
        state,
        base=base,
        completed_statuses=DOCTOR_COMPLETED_STATUSES,
        current_status=STATUS_CURRENT,
    )


def _manifest_status(artifacts: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = {str(entry.get("status") or "") for entry in artifacts.values()}
    if statuses & {STATUS_FAILED, STATUS_MISSING, STATUS_STALE}:
        return "incoherent"
    if STATUS_PENDING in statuses:
        return "partial"
    return "complete"


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


def _require_nonnegative_int(value: Any, *, field: str) -> int:
    if not _is_nonnegative_int(value):
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_identity_string(
    row: Mapping[str, Any],
    field: str,
    *,
    default: str | None = None,
) -> str:
    raw = default if field not in row and default is not None else row.get(field)
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ValueError(f"operator state requires string {field}")
    return raw


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
    "enrich_run_row_from_core_store",
    "invalidate_operator_state",
    "latest_matching_run",
    "load_operator_state",
    "operator_artifact_fingerprint_error",
    "operator_authority_digest",
    "operator_state_path",
    "record_artifact",
    "record_doctor_status",
    "run_is_newer_than_state",
    "state_matches_run",
    "state_has_complete_artifact_fingerprints",
    "text_has_exact_run_id",
    "write_text_artifact",
    "write_json_atomic",
)
