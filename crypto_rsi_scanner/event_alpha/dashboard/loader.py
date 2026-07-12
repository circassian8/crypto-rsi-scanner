"""Coherent, read-only dashboard snapshot loading.

The operator state is the only generation authority.  This loader never falls
back to a timestamp-derived "latest" run and never writes or repairs artifacts.
"""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..artifacts import operator_state as event_alpha_operator_state
from ..artifacts.schema import decision_model as decision_model_schema
from ..radar.calendar import load_unified_calendar_artifact
from ..radar.decision_model import DECISION_MODEL_VERSION
from .models import DashboardLoadError, DashboardSnapshot


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SUPPORTED_DECISION_MODEL_VERSION = DECISION_MODEL_VERSION
_ROUTE_FIELDS = ("radar_route", "decision_route", "actionability_route", "research_route")
_ROUTES = {
    "actionable_watch",
    "high_confidence_watch",
    "rapid_market_anomaly",
    "fade_exhaustion_review",
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


def load_dashboard_snapshot(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    *,
    state_loader: StateLoader = event_alpha_operator_state.load_operator_state,
    max_attempts: int = 2,
) -> DashboardSnapshot:
    """Load one exact operator generation, retrying only a concurrent revision."""

    namespace_dir = _namespace_dir(artifact_base_dir, artifact_namespace)
    attempts = max(1, int(max_attempts))
    last_error = "operator generation changed while dashboard artifacts were read"
    for _attempt in range(attempts):
        try:
            return _load_once(namespace_dir, state_loader=state_loader)
        except _GenerationChanged as exc:
            last_error = str(exc)
    raise DashboardLoadError(last_error)


def _load_once(namespace_dir: Path, *, state_loader: StateLoader) -> DashboardSnapshot:
    before = state_loader(namespace_dir)
    state = _require_valid_state(before)
    run_id, profile, namespace, revision = _state_identity(state, namespace_dir)
    _require_zero_side_effects(state)

    core_path = _current_manifest_path(state, namespace_dir, "core_opportunities")
    core_rows = _read_jsonl(core_path) if core_path is not None else ()
    current_candidates = tuple(
        _dashboard_decision_row(row)
        for row in core_rows
        if str(row.get("row_type") or "") == "event_core_opportunity"
        and _matches_generation(row, run_id=run_id, profile=profile, namespace=namespace)
    )
    expected_core_count = _expected_current_core_count(state)
    if expected_core_count is not None and len(current_candidates) != expected_core_count:
        raise DashboardLoadError(
            "current core artifact count does not match the exact operator generation"
        )

    current_anomalies: tuple[dict[str, Any], ...] = ()
    calendar_path = _current_manifest_path(state, namespace_dir, "unified_calendar")
    try:
        current_calendar = (
            load_unified_calendar_artifact(
                calendar_path,
                run_id=run_id,
                profile=profile,
                artifact_namespace=namespace,
            )
            if calendar_path is not None
            else ()
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise DashboardLoadError(f"invalid current calendar artifact: {type(exc).__name__}") from exc
    expected_calendar_count = _manifest_count(state, "unified_calendar")
    if expected_calendar_count is not None and len(current_calendar) != expected_calendar_count:
        raise DashboardLoadError("current calendar artifact count does not match the exact operator generation")

    cumulative_feedback = _read_jsonl(namespace_dir / "event_alpha_feedback.jsonl")
    cumulative_outcomes = (
        *_read_jsonl(namespace_dir / "event_integrated_radar_outcomes.jsonl"),
        *_read_jsonl(namespace_dir / "event_alpha_outcomes.jsonl"),
    )
    provider_readiness = _read_manifest_json(
        state,
        namespace_dir,
        "provider_readiness_json",
        run_id=run_id,
        profile=profile,
        namespace=namespace,
    )
    provider_health = _read_json_object(namespace_dir / "event_provider_health.json")

    after = state_loader(namespace_dir)
    after_state = _require_valid_state(after)
    after_identity = _state_identity(after_state, namespace_dir)
    if (run_id, profile, namespace, revision) != after_identity:
        raise _GenerationChanged("operator run or revision changed while dashboard artifacts were read")

    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    return DashboardSnapshot(
        namespace_dir=namespace_dir,
        run_id=run_id,
        profile=profile,
        artifact_namespace=namespace,
        revision=revision,
        manifest_status=str(state.get("manifest_status") or "unknown"),
        doctor_status=str(doctor.get("status") or "not_run"),
        doctor_verified_revision=_optional_int(doctor.get("verified_revision")),
        operator_state=state,
        current_candidates=current_candidates,
        current_market_anomalies=current_anomalies,
        current_calendar_events=tuple(dict(row) for row in current_calendar),
        cumulative_feedback=tuple(dict(row) for row in cumulative_feedback),
        cumulative_outcomes=tuple(dict(row) for row in cumulative_outcomes),
        provider_readiness=provider_readiness,
        provider_health=provider_health,
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
        try:
            value = int(state.get(field) or 0)
        except (TypeError, ValueError) as exc:
            raise DashboardLoadError(f"operator safety counter is invalid: {field}") from exc
        if value != 0:
            raise DashboardLoadError(f"operator safety invariant violated: {field}")


def _current_manifest_path(
    state: Mapping[str, Any],
    namespace_dir: Path,
    artifact_name: str,
) -> Path | None:
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    entry = artifacts.get(artifact_name) if isinstance(artifacts, Mapping) else None
    if not isinstance(entry, Mapping) or str(entry.get("status") or "") != "current":
        return None
    entry_run_id = str(entry.get("run_id") or "").strip()
    state_run_id = str(state.get("run_id") or "").strip()
    if entry_run_id and entry_run_id != state_run_id:
        raise DashboardLoadError(f"current operator artifact has mismatched run_id: {artifact_name}")
    raw = str(entry.get("path") or "").strip()
    if not raw:
        raise DashboardLoadError(f"current operator artifact has no path: {artifact_name}")
    target = (namespace_dir / raw).resolve()
    try:
        target.relative_to(namespace_dir.resolve())
    except ValueError as exc:
        raise DashboardLoadError(f"operator artifact escapes namespace: {artifact_name}") from exc
    if not target.exists() or not target.is_file():
        raise DashboardLoadError(f"current operator artifact is missing: {artifact_name}")
    expected_digest = str(entry.get("sha256") or "").strip().casefold()
    if expected_digest and hashlib.sha256(target.read_bytes()).hexdigest() != expected_digest:
        raise DashboardLoadError(f"current operator artifact digest does not match: {artifact_name}")
    return target


def _expected_current_core_count(state: Mapping[str, Any]) -> int | None:
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    entry = artifacts.get("core_opportunities") if isinstance(artifacts, Mapping) else None
    raw = entry.get("count") if isinstance(entry, Mapping) else None
    if raw in (None, ""):
        raw = state.get("current_generation_core_rows")
    if raw in (None, ""):
        return None
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise DashboardLoadError("current core artifact count is invalid") from exc
    if count < 0:
        raise DashboardLoadError("current core artifact count is invalid")
    return count


def _manifest_count(state: Mapping[str, Any], artifact_name: str) -> int | None:
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    entry = artifacts.get(artifact_name) if isinstance(artifacts, Mapping) else None
    raw = entry.get("count") if isinstance(entry, Mapping) else None
    if raw in (None, ""):
        return None
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise DashboardLoadError(f"current {artifact_name} artifact count is invalid") from exc
    if count < 0:
        raise DashboardLoadError(f"current {artifact_name} artifact count is invalid")
    return count


def _read_manifest_json(
    state: Mapping[str, Any],
    namespace_dir: Path,
    artifact_name: str,
    *,
    run_id: str,
    profile: str,
    namespace: str,
) -> Mapping[str, Any]:
    path = _current_manifest_path(state, namespace_dir, artifact_name)
    payload = _read_json_object(path) if path is not None else {}
    for field, expected in (
        ("run_id", run_id),
        ("profile", profile),
        ("artifact_namespace", namespace),
    ):
        actual = str(payload.get(field) or "").strip()
        if actual and actual != expected:
            raise DashboardLoadError(f"current {artifact_name} has mismatched {field}")
    return payload


def _read_json_object(path: Path | None) -> Mapping[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardLoadError(f"invalid dashboard JSON artifact: {path.name}") from exc
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_jsonl(path: Path | None) -> tuple[dict[str, Any], ...]:
    if path is None or not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise DashboardLoadError(f"dashboard artifact is unreadable: {path.name}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DashboardLoadError(f"invalid JSONL in {path.name}:{line_number}") from exc
        if isinstance(payload, Mapping):
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


def _dashboard_decision_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    route = next(
        (str(row.get(field) or "").strip().casefold() for field in _ROUTE_FIELDS if row.get(field)),
        "",
    )
    complete = (
        str(row.get("decision_model_version") or "").strip() == SUPPORTED_DECISION_MODEL_VERSION
        and row.get("decision_model_enabled") is True
        and not decision_model_schema.validate_contract(row)
    )
    if route not in _ROUTES:
        complete = False
    out["_decision_model_status"] = "v2" if complete else "legacy_unclassified"
    out["_dashboard_route"] = route if complete else "diagnostic"
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


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class _GenerationChanged(RuntimeError):
    pass


__all__ = (
    "SUPPORTED_DECISION_MODEL_VERSION",
    "candidate_identifier",
    "load_dashboard_snapshot",
)
