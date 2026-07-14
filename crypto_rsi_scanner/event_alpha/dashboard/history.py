"""Fail-soft, non-authoritative history reads for the local dashboard."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from ..artifacts import schema_v1
from ..operations import market_no_send_io
from ..operations.market_no_send_models import MarketNoSendError


_CAMPAIGN_LEDGER = "event_decision_radar_campaign_outcomes.jsonl"
_CAMPAIGN_ATTEMPT_LEDGER = "event_market_no_send_attempts.jsonl"
_CAMPAIGN_LATEST_ATTEMPT = "event_market_no_send_latest_attempt.json"
_CAMPAIGN_RESERVATION = "event_decision_radar_campaign_reservation.json"
_SAFE_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]{0,80}$")

DASHBOARD_CAMPAIGN_ATTEMPT_LIMIT = 128
DASHBOARD_CAMPAIGN_OUTCOME_LIMIT = 512
DASHBOARD_EXACT_MARKET_HISTORY_LIMIT = 8_192
_REQUEST_LEDGER_SIDE_EFFECT_COUNTERS = (
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)
_REQUEST_LEDGER_FIELDS = (
    "artifact_namespace",
    "burn_in_counted",
    "burn_in_eligible",
    "burn_in_reason",
    "cache_behavior",
    "cache_status",
    "candidate_source_mode",
    "contract_counted_status",
    "contract_version",
    "data_acquisition_mode",
    "data_mode",
    "decision_radar_campaign_counted",
    "decision_radar_campaign_eligible",
    "decision_radar_campaign_reason",
    "duration_ms",
    "endpoint_path",
    "error_class",
    "fixture_mode",
    "http_status",
    "live_provider_authorized",
    "market_history_artifact",
    "market_history_sha256",
    "measurement_program",
    "no_send",
    "no_send_status",
    "normal_rsi_signal_rows_written",
    "observed_at",
    "paper_trades_created",
    "profile",
    "provenance_contract_valid",
    "provider",
    "provider_call_attempted",
    "provider_request_succeeded",
    "provider_source_artifact",
    "provider_source_artifact_sha256",
    "raw_market_row_count",
    "request_ended_at",
    "request_started_at",
    "research_only",
    "result_count",
    "retry_count",
    "row_type",
    "run_id",
    "run_mode",
    "selected_market_row_count",
    "telegram_sends",
    "trades_created",
    "triggered_fade_created",
)


def load_dashboard_history(
    namespace_dir: Path,
    *,
    integrated_outcomes_data: bytes | None,
    now: datetime,
    namespace_reader: Callable[[Path], tuple[bytes | None, str | None]] | None = None,
    exact_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    identity: tuple[str, str, str] | None = None,
    current_artifact_names: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Load namespace-local and shared history without granting generation authority."""

    exact_support = _load_exact_generation_support(exact_artifacts or {}, identity=identity)
    exact_outcomes_present = "integrated_outcomes" in (exact_artifacts or {})
    exact_outcomes_quarantined = (
        "integrated_outcomes" in current_artifact_names and not exact_outcomes_present
    )
    feedback_path = namespace_dir / "event_alpha_feedback.jsonl"
    integrated_path = namespace_dir / "event_integrated_radar_outcomes.jsonl"
    legacy_path = namespace_dir / "event_alpha_outcomes.jsonl"
    feedback, feedback_digest, feedback_error = _read_namespace_jsonl(
        feedback_path,
        namespace_reader=namespace_reader,
    )
    integrated, integrated_digest, integrated_error, integrated_authority = (
        _select_current_outcomes(
            integrated_path,
            integrated_outcomes_data=integrated_outcomes_data,
            namespace_reader=namespace_reader,
            exact_support=exact_support,
            exact_outcomes_present=exact_outcomes_present,
            exact_outcomes_quarantined=exact_outcomes_quarantined,
        )
    )
    legacy, legacy_digest, legacy_error = _read_namespace_jsonl(
        legacy_path,
        namespace_reader=namespace_reader,
    )
    campaign, campaign_digest, campaign_error, campaign_stats = _read_shared_jsonl(
        namespace_dir.parent,
        Path("radar_market_history_cache") / _CAMPAIGN_LEDGER,
        limit=DASHBOARD_CAMPAIGN_OUTCOME_LIMIT,
    )
    attempts, attempts_digest, attempts_error, attempt_stats = _read_shared_jsonl(
        namespace_dir.parent,
        Path(_CAMPAIGN_ATTEMPT_LEDGER),
        limit=DASHBOARD_CAMPAIGN_ATTEMPT_LIMIT,
    )
    projected_attempts, rejected_attempts = _project_campaign_attempts(attempts)
    attempt_stats = _bounded_stats(
        int(attempt_stats["source_row_count"]),
        len(projected_attempts),
        DASHBOARD_CAMPAIGN_ATTEMPT_LIMIT,
    )
    if rejected_attempts:
        attempts_error = attempts_error or "invalid_contract_rows"
    latest_attempt, latest_digest, latest_error = _read_shared_json_object(
        namespace_dir.parent,
        Path(_CAMPAIGN_LATEST_ATTEMPT),
    )
    latest_attempt = _project_campaign_attempt(latest_attempt, latest=True)
    if latest_digest and not latest_attempt and latest_error is None:
        latest_error = "invalid_contract"
    reservation, reservation_digest, reservation_error = _read_shared_json_object(
        namespace_dir.parent,
        Path(_CAMPAIGN_RESERVATION),
    )
    reservation = _project_campaign_reservation(reservation)
    if reservation_digest and not reservation and reservation_error is None:
        reservation_error = "invalid_contract"
    metadata = {
        feedback_path.name: _history_metadata(now, feedback_digest, feedback_error),
        integrated_path.name: _history_metadata(
            now,
            integrated_digest,
            integrated_error,
            authority=integrated_authority,
        ),
        legacy_path.name: _history_metadata(now, legacy_digest, legacy_error),
        f"radar_market_history_cache/{_CAMPAIGN_LEDGER}": _history_metadata(
            now,
            campaign_digest,
            campaign_error,
            authority="shared_campaign_non_authoritative",
            **campaign_stats,
        ),
    }
    campaign_metadata = {
        f"radar_market_history_cache/{_CAMPAIGN_LEDGER}": _history_metadata(
            now,
            campaign_digest,
            campaign_error,
            authority="historical_non_authoritative",
            **campaign_stats,
        ),
        _CAMPAIGN_ATTEMPT_LEDGER: _history_metadata(
            now,
            attempts_digest,
            attempts_error,
            authority="historical_non_authoritative",
            rejected_row_count=rejected_attempts,
            **attempt_stats,
        ),
        _CAMPAIGN_LATEST_ATTEMPT: _history_metadata(
            now,
            latest_digest,
            latest_error,
            authority="historical_non_authoritative",
            source_row_count=1 if latest_digest else 0,
            returned_row_count=1 if latest_attempt else 0,
            truncated=False,
        ),
        _CAMPAIGN_RESERVATION: _history_metadata(
            now,
            reservation_digest,
            reservation_error,
            authority="historical_non_authoritative",
            source_row_count=1 if reservation_digest else 0,
            returned_row_count=1 if reservation else 0,
            truncated=False,
        ),
    }
    return {
        **exact_support,
        "feedback": feedback,
        "current_outcomes": (
            integrated
            if exact_outcomes_present or integrated_outcomes_data is not None
            else ()
        ),
        "outcomes": (
            legacy
            if exact_outcomes_present or integrated_outcomes_data is not None
            else legacy if exact_outcomes_quarantined else (*integrated, *legacy)
        ),
        "campaign_outcomes": campaign,
        "campaign_attempts": projected_attempts,
        "campaign_latest_attempt": latest_attempt,
        "campaign_reservation": reservation,
        "campaign_metadata": campaign_metadata,
        "metadata": metadata,
    }


def _select_current_outcomes(
    integrated_path: Path,
    *,
    integrated_outcomes_data: bytes | None,
    namespace_reader: Callable[[Path], tuple[bytes | None, str | None]] | None,
    exact_support: dict[str, Any],
    exact_outcomes_present: bool,
    exact_outcomes_quarantined: bool,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None, str]:
    """Select exact current outcomes or quarantine them without fallback leakage."""

    if exact_outcomes_present:
        integrated = exact_support["current_outcomes"]
        integrated_metadata = exact_support["current_outcomes_metadata"]
        return (
            integrated,
            integrated_metadata["sha256"],
            integrated_metadata["error"],
            "current_generation_fingerprint_verified",
        )
    if exact_outcomes_quarantined:
        error = "current_artifact_quarantined"
        authority = "current_generation_invalid"
        exact_support["current_outcomes_metadata"] = {
            "authority": authority,
            "artifact_name": "integrated_outcomes",
            "sha256": None,
            "fingerprint_kind": None,
            "source_row_count": 0,
            "returned_row_count": 0,
            "truncated": False,
            "error": error,
        }
        return (), None, error, authority
    if integrated_outcomes_data is not None:
        integrated, digest, error = _read_jsonl_bytes(integrated_outcomes_data)
        authority = (
            "current_generation_fingerprint_verified"
            if error is None
            else "current_generation_invalid"
        )
        return (
            integrated,
            digest,
            "invalid_verified_jsonl" if error is not None else None,
            authority,
        )
    integrated, digest, error = _read_namespace_jsonl(
        integrated_path,
        namespace_reader=namespace_reader,
    )
    return integrated, digest, error, "cumulative_non_authoritative"


def _load_exact_generation_support(
    artifacts: Mapping[str, Mapping[str, Any]],
    *,
    identity: tuple[str, str, str] | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    market_rows, market_metadata = _exact_market_history(
        artifacts.get("market_history"),
        reasons=reasons,
    )
    outcome_rows, outcome_metadata = _exact_current_outcomes(
        artifacts.get("integrated_outcomes"),
        identity=identity,
        reasons=reasons,
    )
    request_ledger, request_metadata = _exact_request_ledger(
        artifacts.get("market_no_send_request_ledger"),
        identity=identity,
        market_history_artifact=artifacts.get("market_history"),
        reasons=reasons,
    )
    return {
        "exact_market_history": market_rows,
        "exact_market_history_metadata": market_metadata,
        "current_outcomes": outcome_rows,
        "current_outcomes_metadata": outcome_metadata,
        "current_request_ledger": request_ledger,
        "current_request_ledger_metadata": request_metadata,
        "exact_support_authority_reasons": tuple(dict.fromkeys(reasons)),
    }


def _exact_market_history(
    artifact: Mapping[str, Any] | None,
    *,
    reasons: list[str],
) -> tuple[tuple[dict[str, Any], ...], Mapping[str, Any]]:
    data, fingerprint_kind, _path_name = _exact_artifact_values(artifact)
    if data is None:
        return (), _exact_artifact_metadata(
            "market_history",
            data=None,
            fingerprint_kind=None,
            source_row_count=0,
            returned_row_count=0,
        )
    rows, _digest, error = _read_jsonl_bytes(data)
    if error:
        reasons.append(f"market_history:{error}")
        return (), _exact_artifact_metadata(
            "market_history",
            data=data,
            fingerprint_kind=fingerprint_kind,
            source_row_count=0,
            returned_row_count=0,
            error=error,
            row_limit=DASHBOARD_EXACT_MARKET_HISTORY_LIMIT,
        )
    invalid = any(
        row.get("schema_id") != "event_alpha.market_history_observation"
        or row.get("schema_version") != 1
        or row.get("research_only") is not True
        or _aware_timestamp(row.get("observed_at")) is None
        for row in rows
    )
    if invalid:
        reasons.append("market_history:contract_validation_failed")
        return (), _exact_artifact_metadata(
            "market_history",
            data=data,
            fingerprint_kind=fingerprint_kind,
            source_row_count=len(rows),
            returned_row_count=0,
            error="contract_validation_failed",
            row_limit=DASHBOARD_EXACT_MARKET_HISTORY_LIMIT,
        )
    bounded = rows[-DASHBOARD_EXACT_MARKET_HISTORY_LIMIT:]
    return tuple(dict(row) for row in bounded), _exact_artifact_metadata(
        "market_history",
        data=data,
        fingerprint_kind=fingerprint_kind,
        source_row_count=len(rows),
        returned_row_count=len(bounded),
        row_limit=DASHBOARD_EXACT_MARKET_HISTORY_LIMIT,
    )


def _exact_current_outcomes(
    artifact: Mapping[str, Any] | None,
    *,
    identity: tuple[str, str, str] | None,
    reasons: list[str],
) -> tuple[tuple[dict[str, Any], ...], Mapping[str, Any]]:
    data, fingerprint_kind, _path_name = _exact_artifact_values(artifact)
    if data is None:
        return (), _exact_artifact_metadata(
            "integrated_outcomes",
            data=None,
            fingerprint_kind=None,
            source_row_count=0,
            returned_row_count=0,
        )
    rows, _digest, error = _read_jsonl_bytes(data)
    if error:
        reasons.append(f"integrated_outcomes:{error}")
        return (), _exact_artifact_metadata(
            "integrated_outcomes",
            data=data,
            fingerprint_kind=fingerprint_kind,
            source_row_count=0,
            returned_row_count=0,
            error=error,
        )
    validation_error = _current_outcome_error(rows, identity=identity)
    if validation_error:
        reasons.append(f"integrated_outcomes:{validation_error}")
        return (), _exact_artifact_metadata(
            "integrated_outcomes",
            data=data,
            fingerprint_kind=fingerprint_kind,
            source_row_count=len(rows),
            returned_row_count=0,
            error=validation_error,
        )
    return tuple(dict(row) for row in rows), _exact_artifact_metadata(
        "integrated_outcomes",
        data=data,
        fingerprint_kind=fingerprint_kind,
        source_row_count=len(rows),
        returned_row_count=len(rows),
    )


def _current_outcome_error(
    rows: tuple[dict[str, Any], ...],
    *,
    identity: tuple[str, str, str] | None,
) -> str | None:
    if identity is None:
        return "generation_identity_missing"
    run_id, profile, namespace = identity
    if any(row.get("row_type") != "event_integrated_radar_outcome" for row in rows):
        return "row_type_mismatch"
    if any(
        str(row.get("run_id") or "") != run_id
        or str(row.get("profile") or "") != profile
        or str(row.get("artifact_namespace") or "") != namespace
        for row in rows
    ):
        return "generation_lineage_mismatch"
    if any(schema_v1.validate_row_against_schema(row, "outcome_row_v1") for row in rows):
        return "schema_validation_failed"
    if any(row.get("research_only") is not True for row in rows):
        return "research_only_missing"
    return None


def _exact_request_ledger(
    artifact: Mapping[str, Any] | None,
    *,
    identity: tuple[str, str, str] | None,
    market_history_artifact: Mapping[str, Any] | None,
    reasons: list[str],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    data, fingerprint_kind, _path_name = _exact_artifact_values(artifact)
    if data is None:
        return {}, _exact_artifact_metadata(
            "market_no_send_request_ledger",
            data=None,
            fingerprint_kind=None,
            source_row_count=0,
            returned_row_count=0,
        )
    payload, _digest, parse_error = read_unverified_json_object_bytes(data, read_error=None)
    errors: list[str] = []
    if parse_error:
        errors.append(parse_error)
    if payload.get("row_type") != "event_market_no_send_request_ledger":
        errors.append("row_type_mismatch")
    if identity is None:
        errors.append("generation_identity_missing")
    elif any(
        str(payload.get(field) or "") != expected
        for field, expected in zip(("run_id", "profile", "artifact_namespace"), identity)
    ):
        errors.append("generation_lineage_mismatch")
    if payload.get("research_only") is not True:
        errors.append("research_only_missing")
    if payload.get("no_send") is not True:
        errors.append("no_send_missing")
    for field in _REQUEST_LEDGER_SIDE_EFFECT_COUNTERS:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            errors.append(f"safety_counter_invalid:{field}")
    endpoint = str(payload.get("endpoint_path") or "")
    if (
        not endpoint.startswith("/")
        or "?" in endpoint
        or "#" in endpoint
        or len(endpoint) > 240
        or any(ord(character) < 32 for character in endpoint)
    ):
        errors.append("endpoint_path_invalid")
    history_data, _kind, history_name = _exact_artifact_values(market_history_artifact)
    if history_data is not None:
        if payload.get("market_history_sha256") != hashlib.sha256(history_data).hexdigest():
            errors.append("market_history_sha256_mismatch")
        if payload.get("market_history_artifact") != history_name:
            errors.append("market_history_artifact_mismatch")
    if errors:
        reasons.extend(f"market_no_send_request_ledger:{error}" for error in errors)
        return {}, _exact_artifact_metadata(
            "market_no_send_request_ledger",
            data=data,
            fingerprint_kind=fingerprint_kind,
            source_row_count=1,
            returned_row_count=0,
            error=errors[0],
        )
    projected = {field: payload.get(field) for field in _REQUEST_LEDGER_FIELDS}
    return projected, _exact_artifact_metadata(
        "market_no_send_request_ledger",
        data=data,
        fingerprint_kind=fingerprint_kind,
        source_row_count=1,
        returned_row_count=1,
    )


def _exact_artifact_values(
    artifact: Mapping[str, Any] | None,
) -> tuple[bytes | None, str | None, str | None]:
    if not isinstance(artifact, Mapping):
        return None, None, None
    data = artifact.get("data")
    return (
        bytes(data) if isinstance(data, (bytes, bytearray)) else None,
        str(artifact.get("fingerprint_kind") or "") or None,
        str(artifact.get("path_name") or "") or None,
    )


def _exact_artifact_metadata(
    artifact_name: str,
    *,
    data: bytes | None,
    fingerprint_kind: str | None,
    source_row_count: int,
    returned_row_count: int,
    error: str | None = None,
    row_limit: int | None = None,
) -> Mapping[str, Any]:
    metadata: dict[str, Any] = {
        "authority": "current_generation_fingerprint_verified" if data is not None else "not_available",
        "artifact_name": artifact_name if data is not None else None,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "fingerprint_kind": fingerprint_kind,
        "source_row_count": source_row_count,
        "returned_row_count": returned_row_count,
        "truncated": source_row_count > returned_row_count and error is None,
        "error": error,
    }
    if row_limit is not None:
        metadata["row_limit"] = row_limit
    return metadata


def read_unverified_json_object(
    path: Path,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    data, read_error = _read_regular_file_once(path)
    return read_unverified_json_object_bytes(data, read_error=read_error)


def read_unverified_json_object_bytes(
    data: bytes | None,
    *,
    read_error: str | None,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    """Parse one already-read non-authoritative JSON object."""

    if read_error == "artifact_missing":
        return {}, None, None
    if read_error or data is None:
        return {}, None, read_error or "unreadable"
    digest = hashlib.sha256(data).hexdigest()
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}, digest, "invalid_json"
    if not isinstance(payload, Mapping):
        return {}, digest, "json_not_object"
    return dict(payload), digest, None


def _read_namespace_jsonl(
    path: Path,
    *,
    namespace_reader: Callable[[Path], tuple[bytes | None, str | None]] | None,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    if namespace_reader is None:
        return read_unverified_jsonl(path)
    data, read_error = namespace_reader(path)
    if read_error == "artifact_missing":
        return (), None, None
    if read_error or data is None:
        return (), None, read_error or "unreadable"
    return _read_jsonl_bytes(data)


def read_unverified_jsonl(
    path: Path,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        return (), None, None
    if read_error or data is None:
        return (), None, read_error or "unreadable"
    return _read_jsonl_bytes(data)


def _read_shared_jsonl(
    artifact_base: Path,
    relative_path: Path,
    *,
    limit: int,
) -> tuple[
    tuple[dict[str, Any], ...],
    str | None,
    str | None,
    dict[str, Any],
]:
    path = artifact_base / relative_path
    if path_error := _path_symlink_error(artifact_base, path):
        return (), None, path_error, _bounded_stats(0, 0, limit)
    try:
        parent_info = path.parent.lstat()
    except FileNotFoundError:
        return (), None, None, _bounded_stats(0, 0, limit)
    except OSError:
        return (
            (),
            None,
            "artifact_parent_unreadable_or_unsafe",
            _bounded_stats(0, 0, limit),
        )
    if not stat.S_ISDIR(parent_info.st_mode):
        return (
            (),
            None,
            "artifact_parent_unreadable_or_unsafe",
            _bounded_stats(0, 0, limit),
        )
    try:
        data = market_no_send_io.read_regular_bytes(path, missing_ok=True)
    except MarketNoSendError:
        return (), None, "artifact_unreadable_or_symlink", _bounded_stats(0, 0, limit)
    return _read_bounded_jsonl_bytes(data, limit=limit)


def _read_shared_json_object(
    artifact_base: Path,
    relative_path: Path,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    path = artifact_base / relative_path
    if path_error := _path_symlink_error(artifact_base, path):
        return {}, None, path_error
    try:
        data = market_no_send_io.read_regular_bytes(path, missing_ok=True)
    except MarketNoSendError:
        return {}, None, "artifact_unreadable_or_symlink"
    return read_unverified_json_object_bytes(data, read_error=None)


def _read_regular_file_once(path: Path) -> tuple[bytes | None, str | None]:
    """Reuse the no-follow leaf reader without importing dashboard loader internals."""

    try:
        return market_no_send_io.read_regular_bytes(path, missing_ok=True), None
    except MarketNoSendError:
        return None, "artifact_unreadable_or_symlink"


def _read_jsonl_bytes(
    data: bytes | None,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    if data is None:
        return (), None, None
    digest = hashlib.sha256(data).hexdigest()
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return (), digest, "invalid_utf8"
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, ValueError):
            return (), digest, f"invalid_jsonl:{line_number}"
        if not isinstance(payload, Mapping):
            return (), digest, f"non_object_jsonl:{line_number}"
        rows.append(dict(payload))
    return tuple(rows), digest, None


def _read_bounded_jsonl_bytes(
    data: bytes | None,
    *,
    limit: int,
) -> tuple[
    tuple[dict[str, Any], ...],
    str | None,
    str | None,
    dict[str, Any],
]:
    if data is None:
        return (), None, None, _bounded_stats(0, 0, limit)
    digest = hashlib.sha256(data).hexdigest()
    try:
        lines = [line for line in data.decode("utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError:
        return (), digest, "invalid_utf8", _bounded_stats(0, 0, limit)
    source_count = len(lines)
    selected = lines[-limit:]
    rows: list[dict[str, Any]] = []
    first_selected_line = source_count - len(selected) + 1
    for offset, line in enumerate(selected):
        line_number = first_selected_line + offset
        try:
            payload = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, ValueError):
            return (
                (),
                digest,
                f"invalid_jsonl:{line_number}",
                _bounded_stats(source_count, 0, limit),
            )
        if not isinstance(payload, Mapping):
            return (
                (),
                digest,
                f"non_object_jsonl:{line_number}",
                _bounded_stats(source_count, 0, limit),
            )
        rows.append(dict(payload))
    return (
        tuple(rows),
        digest,
        None,
        _bounded_stats(source_count, len(rows), limit),
    )


def _history_metadata(
    now: datetime,
    digest: str | None,
    error: str | None,
    *,
    authority: str = "cumulative_non_authoritative",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "authority": authority,
        "read_at": now.isoformat() if digest else None,
        "sha256": digest,
        "error": error,
        **extra,
    }


def _bounded_stats(source_count: int, returned_count: int, limit: int) -> dict[str, Any]:
    return {
        "source_row_count": source_count,
        "returned_row_count": returned_count,
        "row_limit": limit,
        "truncated": source_count > returned_count,
    }


def _project_campaign_attempts(
    rows: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], int]:
    projected: list[dict[str, Any]] = []
    rejected = 0
    for row in rows:
        value = _project_campaign_attempt(row, latest=False)
        if value:
            projected.append(value)
        else:
            rejected += 1
    return tuple(projected), rejected


def _project_campaign_attempt(
    row: Mapping[str, Any],
    *,
    latest: bool,
) -> dict[str, Any]:
    expected_type = (
        "event_market_no_send_latest_attempt"
        if latest
        else "event_market_no_send_attempt"
    )
    namespace = str(row.get("artifact_namespace") or "").strip()
    if (
        row.get("contract_version") != 1
        or row.get("row_type") != expected_type
        or row.get("research_only") is not True
        or row.get("no_send") is not True
        or not _SAFE_NAMESPACE_RE.fullmatch(namespace)
        or namespace in {".", ".."}
        or not _safe_token_fields(
            row,
            (
                "attempt_id",
                "status",
                "provider",
                "data_mode",
                "data_acquisition_mode",
                "candidate_source_mode",
                "failure_class",
                "measurement_program",
            ),
        )
        or not _required_safe_tokens(row, ("attempt_id", "status", "provider"))
        or not _boolean_fields(
            row,
            (
                "provider_call_attempted",
                "provider_request_succeeded",
                "decision_radar_campaign_counted",
                "burn_in_counted",
            ),
        )
        or not _safe_identity_fields(
            row,
            ("recorded_at", "observed_at", "run_id"),
        )
        or not _required_aware_timestamps(row, ("recorded_at", "observed_at"))
    ):
        return {}
    fields = (
        "contract_version",
        "row_type",
        "attempt_id",
        "recorded_at",
        "artifact_namespace",
        "status",
        "observed_at",
        "run_id",
        "provider",
        "data_mode",
        "data_acquisition_mode",
        "provider_call_attempted",
        "provider_request_succeeded",
        "candidate_source_mode",
        "failure_class",
        "measurement_program",
        "decision_radar_campaign_counted",
        "burn_in_counted",
        "no_send",
        "research_only",
    )
    return {field: row.get(field) for field in fields}


def _project_campaign_reservation(row: Mapping[str, Any]) -> dict[str, Any]:
    namespace = str(row.get("artifact_namespace") or "").strip()
    if (
        row.get("contract_version") != 1
        or row.get("row_type") != "decision_radar_campaign_reservation"
        or row.get("status") not in {"active", "released"}
        or row.get("research_only") is not True
        or row.get("no_send") is not True
        or not _SAFE_NAMESPACE_RE.fullmatch(namespace)
        or namespace in {".", ".."}
        or not _safe_token_fields(row, ("previous_reservation_status",))
        or not _safe_identity_fields(
            row,
            (
                "acquired_at",
                "expires_at",
                "next_provider_call_at",
                "provider_call_reserved_at",
                "released_at",
            ),
        )
        or not _required_aware_timestamps(row, ("acquired_at", "expires_at"))
        or not _optional_aware_timestamps(
            row,
            (
                "next_provider_call_at",
                "provider_call_reserved_at",
                "released_at",
            ),
        )
    ):
        return {}
    acquired_at = _aware_timestamp(row["acquired_at"])
    expires_at = _aware_timestamp(row["expires_at"])
    reserved_at = _aware_timestamp(row.get("provider_call_reserved_at"))
    next_call_at = _aware_timestamp(row.get("next_provider_call_at"))
    if acquired_at is None or expires_at is None or expires_at <= acquired_at:
        return {}
    if reserved_at is not None and (next_call_at is None or next_call_at <= reserved_at):
        return {}
    fields = (
        "contract_version",
        "row_type",
        "artifact_namespace",
        "status",
        "acquired_at",
        "expires_at",
        "next_provider_call_at",
        "provider_call_reserved_at",
        "released_at",
        "previous_reservation_status",
        "no_send",
        "research_only",
    )
    return {field: row.get(field) for field in fields}


def _safe_token_fields(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = row.get(field)
        if value in (None, ""):
            continue
        if not _SAFE_TOKEN_RE.fullmatch(str(value).strip()):
            return False
    return True


def _safe_identity_fields(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = row.get(field)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if not text or len(text) > 240 or any(ord(character) < 32 for character in text):
            return False
    return True


def _required_safe_tokens(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(
        bool(str(row.get(field) or "").strip())
        and bool(_SAFE_TOKEN_RE.fullmatch(str(row.get(field)).strip()))
        for field in fields
    )


def _boolean_fields(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(isinstance(row.get(field), bool) for field in fields)


def _required_aware_timestamps(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(_aware_timestamp(row.get(field)) is not None for field in fields)


def _optional_aware_timestamps(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(
        row.get(field) in (None, "") or _aware_timestamp(row.get(field)) is not None
        for field in fields
    )


def _aware_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _path_symlink_error(base: Path, target: Path) -> str | None:
    try:
        relative = target.relative_to(base)
    except ValueError:
        return "artifact_path_escape"
    current = base
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


__all__ = (
    "DASHBOARD_CAMPAIGN_ATTEMPT_LIMIT",
    "DASHBOARD_CAMPAIGN_OUTCOME_LIMIT",
    "load_dashboard_history",
    "read_unverified_json_object",
    "read_unverified_json_object_bytes",
    "read_unverified_jsonl",
)
