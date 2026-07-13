"""Pure, fail-closed provenance values for market-led research candidates.

This module deliberately performs no file or provider I/O.  It validates the
lineage assertions supplied by an upstream market-data operation, recomputes
the applicable measurement-program eligibility from those assertions, and
exposes one JSON-shaped value that downstream artifacts can copy without
reinterpreting acquisition mode.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from pathlib import PurePosixPath
import re
from typing import Any


MARKET_PROVENANCE_CONTRACT_VERSION = 2
MARKET_PROVENANCE_SCHEMA_VERSION = "crypto_radar_market_provenance_v2"
DECISION_RADAR_MEASUREMENT_PROGRAM = "decision_radar_live_observation_campaign_v2"

CANDIDATE_SOURCE_MODES = (
    "live_no_send",
    "mocked_fixture",
    "artifact_replay",
    "preflight_only",
)

DATA_ACQUISITION_MODES = (
    "live_provider",
    "mocked_fixture",
    "artifact_replay",
    "preflight_only",
    "cache_replay",
)

CACHE_STATUSES = (
    "not_applicable",
    "miss",
    "hit",
    "refreshed",
    "write_through",
    "unknown",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_ACQUISITION_ALIASES = {
    "live": "live_provider",
    "live_no_send": "live_provider",
    "live_provider": "live_provider",
    "real": "live_provider",
    "mock": "mocked_fixture",
    "fixture": "mocked_fixture",
    "mock_fixture": "mocked_fixture",
    "mocked_fixture": "mocked_fixture",
    "replay": "artifact_replay",
    "artifact_replay": "artifact_replay",
    "preflight": "preflight_only",
    "preflight_only": "preflight_only",
    "cache": "cache_replay",
    "cached": "cache_replay",
    "cache_hit": "cache_replay",
    "cache_replay": "cache_replay",
}
_SOURCE_MODE_ALIASES = {
    "live": "live_no_send",
    "live_no_send": "live_no_send",
    "mock": "mocked_fixture",
    "fixture": "mocked_fixture",
    "mocked_fixture": "mocked_fixture",
    "replay": "artifact_replay",
    "cached": "artifact_replay",
    "artifact_replay": "artifact_replay",
    "preflight": "preflight_only",
    "preflight_only": "preflight_only",
}
_CACHE_ALIASES = {
    "": "unknown",
    "none": "not_applicable",
    "not_used": "not_applicable",
    "not_applicable": "not_applicable",
    "miss": "miss",
    "cache_miss": "miss",
    "hit": "hit",
    "cache_hit": "hit",
    "cached": "hit",
    "refreshed": "refreshed",
    "refresh": "refreshed",
    "write_through": "write_through",
    "written": "write_through",
    "fresh_request_artifact": "write_through",
    "unknown": "unknown",
}
_MODE_COMPATIBILITY = {
    "live_provider": "live_no_send",
    "mocked_fixture": "mocked_fixture",
    "artifact_replay": "artifact_replay",
    "preflight_only": "preflight_only",
    "cache_replay": "artifact_replay",
}


def normalize_market_provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a closed provenance value and recompute every trust decision.

    Caller-supplied ``provenance_contract_valid`` and burn-in flags are never
    trusted.  A live candidate counts only when its explicit authorization,
    provider attempt, source artifact, request ledger, hashes, generation id,
    feature basis, and data-quality evidence form a complete compatible value.
    """

    if not isinstance(value, Mapping) or not value:
        return {}
    raw = dict(value)
    normalized = _normalized_provenance_fields(raw)
    errors = _provenance_validation_errors(raw, normalized)
    return _closed_provenance_value(normalized, errors)


def _normalized_provenance_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    declared_schema = _text(raw.get("schema_version"))
    declared_contract = _integer(raw.get("contract_version"))
    schema_version = (
        MARKET_PROVENANCE_SCHEMA_VERSION
        if declared_schema == MARKET_PROVENANCE_SCHEMA_VERSION
        or declared_contract == MARKET_PROVENANCE_CONTRACT_VERSION
        else declared_schema
    )
    acquisition_declared = _text(
        raw.get("data_acquisition_mode") or raw.get("data_mode")
    )
    source_mode_declared = _text(raw.get("candidate_source_mode"))
    request_path_raw = (
        raw.get("request_ledger_path")
        or raw.get("provider_request_ledger_path")
    )
    request_digest_raw = (
        raw.get("request_ledger_sha256")
        or raw.get("provider_request_ledger_sha256")
    )
    source_path_raw = (
        raw.get("provider_source_artifact")
        or raw.get("source_artifact_path")
    )
    source_digest_raw = (
        raw.get("provider_source_artifact_sha256")
        or raw.get("provider_source_sha256")
        or raw.get("source_artifact_sha256")
    )
    cache_declared = _text(raw.get("cache_status"))
    return {
        "declared_schema": declared_schema,
        "declared_contract": declared_contract,
        "schema_version": schema_version,
        "acquisition_declared": acquisition_declared,
        "source_mode_declared": source_mode_declared,
        "acquisition_mode": _ACQUISITION_ALIASES.get(
            acquisition_declared.casefold(),
            "",
        ),
        "source_mode": _SOURCE_MODE_ALIASES.get(
            source_mode_declared.casefold(),
            "",
        ),
        "provider": _text(raw.get("provider") or raw.get("source_provider")),
        "attempted": _strict_bool(raw.get("provider_call_attempted")),
        "succeeded": _strict_bool(
            raw.get("provider_call_succeeded")
            if "provider_call_succeeded" in raw
            else raw.get("provider_request_succeeded")
        ),
        "authorized": _strict_bool(raw.get("live_provider_authorized")),
        "request_path_raw": request_path_raw,
        "request_ledger_path": _portable_artifact_path(request_path_raw),
        "request_digest_raw": request_digest_raw,
        "request_ledger_sha256": _sha256(request_digest_raw),
        "source_path_raw": source_path_raw,
        "source_artifact_path": _portable_artifact_path(source_path_raw),
        "source_digest_raw": source_digest_raw,
        "source_artifact_sha256": _sha256(source_digest_raw),
        "generation_id": _text(
            raw.get("provider_generation_id") or raw.get("generation_id")
        ),
        "cache_declared": cache_declared,
        "cache_status": _CACHE_ALIASES.get(cache_declared.casefold(), ""),
        "feature_basis": _mapping(raw.get("feature_basis")),
        "data_quality": _data_quality(raw.get("data_quality")),
        "measurement_program": _text(raw.get("measurement_program")),
    }


def _provenance_validation_errors(
    raw: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    _validate_contract_and_modes(errors, normalized)
    _validate_provider_and_cache(errors, normalized)
    _validate_lineage(errors, normalized)
    _validate_candidate_inputs(errors, normalized)
    _validate_live_claim(errors, raw, normalized)
    if normalized.get("measurement_program") not in {
        "",
        DECISION_RADAR_MEASUREMENT_PROGRAM,
    }:
        errors.append("measurement_program_unsupported")
    return list(dict.fromkeys(errors))


def _validate_contract_and_modes(
    errors: list[str],
    normalized: Mapping[str, Any],
) -> None:
    if normalized["schema_version"] != MARKET_PROVENANCE_SCHEMA_VERSION:
        errors.append("schema_version_unsupported")
    declared_schema = normalized["declared_schema"]
    if declared_schema and declared_schema != MARKET_PROVENANCE_SCHEMA_VERSION:
        errors.append("schema_version_conflict")
    if normalized["declared_contract"] not in (
        None,
        MARKET_PROVENANCE_CONTRACT_VERSION,
    ):
        errors.append("contract_version_unsupported")
    acquisition_declared = normalized["acquisition_declared"]
    acquisition_mode = normalized["acquisition_mode"]
    if not acquisition_declared:
        errors.append("data_acquisition_mode_missing")
    elif acquisition_mode not in DATA_ACQUISITION_MODES:
        errors.append("data_acquisition_mode_invalid")
    source_mode_declared = normalized["source_mode_declared"]
    source_mode = normalized["source_mode"]
    if not source_mode_declared:
        errors.append("candidate_source_mode_missing")
    elif source_mode not in CANDIDATE_SOURCE_MODES:
        errors.append("candidate_source_mode_invalid")
    if (
        acquisition_mode
        and source_mode
        and _MODE_COMPATIBILITY.get(acquisition_mode) != source_mode
    ):
        errors.append("acquisition_source_mode_mismatch")


def _validate_provider_and_cache(
    errors: list[str],
    normalized: Mapping[str, Any],
) -> None:
    if not normalized["provider"]:
        errors.append("provider_missing")
    if normalized["attempted"] is None:
        errors.append("provider_call_attempted_invalid")
    if normalized["succeeded"] is None:
        errors.append("provider_call_succeeded_invalid")
    if normalized["authorized"] is None:
        errors.append("live_provider_authorized_invalid")
    if normalized["succeeded"] is True and normalized["attempted"] is not True:
        errors.append("provider_success_without_attempt")
    cache_declared = normalized["cache_declared"]
    cache_status = normalized["cache_status"]
    if not cache_declared:
        errors.append("cache_status_missing")
    elif cache_status not in CACHE_STATUSES:
        errors.append("cache_status_invalid")
    if normalized["acquisition_mode"] == "cache_replay" and cache_status != "hit":
        errors.append("cache_replay_without_cache_hit")
    if normalized["acquisition_mode"] == "live_provider" and cache_status == "hit":
        errors.append("live_provider_cannot_be_cache_hit")


def _validate_lineage(
    errors: list[str],
    normalized: Mapping[str, Any],
) -> None:
    _validate_optional_lineage_pair(
        errors,
        path=normalized["request_ledger_path"],
        digest=normalized["request_ledger_sha256"],
        path_name="request_ledger_path",
        digest_name="request_ledger_sha256",
        raw_path=normalized["request_path_raw"],
        raw_digest=normalized["request_digest_raw"],
    )
    _validate_optional_lineage_pair(
        errors,
        path=normalized["source_artifact_path"],
        digest=normalized["source_artifact_sha256"],
        path_name="provider_source_artifact",
        digest_name="provider_source_artifact_sha256",
        raw_path=normalized["source_path_raw"],
        raw_digest=normalized["source_digest_raw"],
    )
    request_path = normalized["request_ledger_path"]
    source_path = normalized["source_artifact_path"]
    if request_path and source_path and request_path == source_path:
        errors.append("request_ledger_source_artifact_not_distinct")


def _validate_candidate_inputs(
    errors: list[str],
    normalized: Mapping[str, Any],
) -> None:
    if not normalized["generation_id"]:
        errors.append("provider_generation_id_missing")
    if normalized["source_mode"] not in {
        "live_no_send",
        "mocked_fixture",
        "artifact_replay",
    }:
        return
    required_fields = (
        ("request_ledger_path", "request_ledger_path_missing"),
        ("request_ledger_sha256", "request_ledger_sha256_missing"),
        ("source_artifact_path", "provider_source_artifact_missing"),
        ("source_artifact_sha256", "provider_source_artifact_sha256_missing"),
        ("feature_basis", "feature_basis_missing"),
        ("data_quality", "data_quality_missing"),
    )
    for field, error in required_fields:
        if not normalized[field]:
            errors.append(error)


def _validate_live_claim(
    errors: list[str],
    raw: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> None:
    live_claim = (
        normalized["source_mode"] == "live_no_send"
        or normalized["acquisition_mode"] == "live_provider"
    )
    if not live_claim:
        return
    if normalized["attempted"] is not True:
        errors.append("live_provider_call_not_attempted")
    if normalized["succeeded"] is not True:
        errors.append("live_provider_call_not_successful")
    if normalized["authorized"] is not True:
        errors.append("live_provider_not_authorized")
    if raw.get("fixture_mode") is True:
        errors.append("live_provider_fixture_mode")


def _closed_provenance_value(
    normalized: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    contract_valid = not errors
    source_mode = normalized["source_mode"]
    decision_campaign = (
        normalized.get("measurement_program") == DECISION_RADAR_MEASUREMENT_PROGRAM
    )
    live_lineage_eligible = bool(contract_valid and source_mode == "live_no_send")
    campaign_eligible = bool(decision_campaign and live_lineage_eligible)
    burn_in_eligible = bool(not decision_campaign and live_lineage_eligible)
    if decision_campaign:
        burn_in_reason = "not_counted_separate_decision_radar_campaign"
    elif burn_in_eligible:
        burn_in_reason = "counted_live_no_send_exact_lineage"
    elif errors:
        burn_in_reason = "not_counted_invalid_provenance:" + ",".join(errors)
    else:
        burn_in_reason = f"not_counted_non_live_mode:{source_mode}"
    if campaign_eligible:
        campaign_reason = "counted_live_no_send_exact_lineage"
    elif errors:
        campaign_reason = "not_counted_invalid_provenance:" + ",".join(errors)
    else:
        campaign_reason = f"not_counted_non_live_mode:{source_mode}"
    out = {
        "schema_version": normalized["schema_version"] or None,
        "contract_version": MARKET_PROVENANCE_CONTRACT_VERSION,
        "data_acquisition_mode": (
            normalized["acquisition_mode"]
            or normalized["acquisition_declared"]
            or "unknown"
        ),
        "candidate_source_mode": (
            source_mode or normalized["source_mode_declared"] or "unknown"
        ),
        "provider": normalized["provider"] or None,
        "provider_call_attempted": normalized["attempted"] is True,
        "provider_call_succeeded": normalized["succeeded"] is True,
        "live_provider_authorized": normalized["authorized"] is True,
        "request_ledger_path": normalized["request_ledger_path"],
        "request_ledger_sha256": normalized["request_ledger_sha256"],
        "provider_source_artifact": normalized["source_artifact_path"],
        "provider_source_artifact_sha256": normalized["source_artifact_sha256"],
        "provider_generation_id": normalized["generation_id"] or None,
        "cache_status": (
            normalized["cache_status"] or normalized["cache_declared"] or "unknown"
        ),
        "provenance_contract_valid": contract_valid,
        "burn_in_eligible": burn_in_eligible,
        "burn_in_counted": burn_in_eligible,
        "burn_in_reason": burn_in_reason,
        "feature_basis": normalized["feature_basis"],
        "data_quality": normalized["data_quality"],
        "validation_errors": errors,
    }
    if decision_campaign:
        out.update({
            "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
            "decision_radar_campaign_eligible": campaign_eligible,
            "decision_radar_campaign_counted": campaign_eligible,
            "decision_radar_campaign_reason": campaign_reason,
        })
    return out


def market_provenance_values(source: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract and normalize provenance from a row or closed projection.

    Historical flat rows are left alone unless they declare the new provenance
    schema/acquisition field.  This avoids silently reclassifying older burn-in
    artifacts that only carried ``candidate_source_mode``.
    """

    if not isinstance(source, Mapping) or not source:
        return {}
    direct = source.get("market_provenance")
    if isinstance(direct, Mapping) and direct:
        return normalize_market_provenance(_with_source_context(direct, source))
    if (
        source.get("schema_version") == MARKET_PROVENANCE_SCHEMA_VERSION
        or source.get("contract_version") == MARKET_PROVENANCE_CONTRACT_VERSION
    ):
        return normalize_market_provenance(source)
    for container_name in (
        "source_provider_lineage",
        "decision_projection",
        "market_state_snapshot",
        "market_snapshot",
        "latest_market_snapshot",
    ):
        container = source.get(container_name)
        if not isinstance(container, Mapping):
            continue
        nested = container.get("market_provenance")
        if isinstance(nested, Mapping) and nested:
            return normalize_market_provenance(_with_source_context(nested, source, container))
        lineage = container.get("source_provider_lineage")
        if isinstance(lineage, Mapping):
            nested = lineage.get("market_provenance")
            if isinstance(nested, Mapping) and nested:
                return normalize_market_provenance(_with_source_context(nested, source, container))
    for container_name in ("score_components", "latest_score_components"):
        container = source.get(container_name)
        if isinstance(container, Mapping):
            nested = container.get("market_provenance")
            if isinstance(nested, Mapping) and nested:
                return normalize_market_provenance(_with_source_context(nested, source, container))
    if (
        source.get("market_provenance_schema_version")
        or source.get("market_provenance_contract_version")
        or source.get("data_acquisition_mode")
    ):
        flat = dict(source)
        flat["schema_version"] = source.get("market_provenance_schema_version")
        flat["contract_version"] = source.get("market_provenance_contract_version")
        return normalize_market_provenance(flat)
    return {}


def merge_market_provenance(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return one exact shared provenance value or a fail-closed conflict."""

    values = [
        value
        for row in rows
        if isinstance(row, Mapping)
        and (value := market_provenance_values(row))
    ]
    if not values:
        return {}
    first = values[0]
    if all(value == first for value in values[1:]):
        return deepcopy(first)
    invalid = deepcopy(first)
    errors = list(invalid.get("validation_errors") or ())
    errors.append("market_provenance_conflict")
    invalid["validation_errors"] = list(dict.fromkeys(str(item) for item in errors))
    invalid["provenance_contract_valid"] = False
    if invalid.get("measurement_program") == DECISION_RADAR_MEASUREMENT_PROGRAM:
        invalid["decision_radar_campaign_eligible"] = False
        invalid["decision_radar_campaign_counted"] = False
        invalid["decision_radar_campaign_reason"] = (
            "not_counted_invalid_provenance:market_provenance_conflict"
        )
    invalid["burn_in_eligible"] = False
    invalid["burn_in_counted"] = False
    invalid["burn_in_reason"] = "not_counted_invalid_provenance:market_provenance_conflict"
    return invalid


def market_provenance_flat_fields(source: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return compatibility fields derived only from canonical provenance."""

    provenance = market_provenance_values(source)
    if not provenance:
        return {}
    return {
        "market_provenance_schema_version": provenance["schema_version"],
        "market_provenance_contract_version": provenance["contract_version"],
        "data_acquisition_mode": provenance["data_acquisition_mode"],
        "candidate_source_mode": provenance["candidate_source_mode"],
        "provider": provenance["provider"],
        "provider_call_attempted": provenance["provider_call_attempted"],
        "provider_call_succeeded": provenance["provider_call_succeeded"],
        "provider_request_succeeded": provenance["provider_call_succeeded"],
        "live_provider_authorized": provenance["live_provider_authorized"],
        "request_ledger_path": provenance["request_ledger_path"],
        "request_ledger_sha256": provenance["request_ledger_sha256"],
        "provider_source_artifact": provenance["provider_source_artifact"],
        "provider_source_artifact_sha256": provenance["provider_source_artifact_sha256"],
        "provider_generation_id": provenance["provider_generation_id"],
        "cache_status": provenance["cache_status"],
        "provenance_contract_valid": provenance["provenance_contract_valid"],
        **({
            "measurement_program": provenance.get("measurement_program"),
            "decision_radar_campaign_eligible": provenance.get("decision_radar_campaign_eligible"),
            "decision_radar_campaign_counted": provenance.get("decision_radar_campaign_counted"),
            "decision_radar_campaign_reason": provenance.get("decision_radar_campaign_reason"),
        } if provenance.get("measurement_program") else {}),
        "burn_in_eligible": provenance["burn_in_eligible"],
        "burn_in_counted": provenance["burn_in_counted"],
        "burn_in_reason": provenance["burn_in_reason"],
        "feature_basis": deepcopy(provenance["feature_basis"]),
        "data_quality": deepcopy(provenance["data_quality"]),
        "contract_counted_candidate": (
            provenance.get("decision_radar_campaign_counted") is True
            if provenance.get("measurement_program") == DECISION_RADAR_MEASUREMENT_PROGRAM
            else provenance["burn_in_counted"]
        ),
    }


def _validate_optional_lineage_pair(
    errors: list[str],
    *,
    path: str | None,
    digest: str | None,
    path_name: str,
    digest_name: str,
    raw_path: Any,
    raw_digest: Any,
) -> None:
    if raw_path not in (None, "") and path is None:
        errors.append(f"{path_name}_invalid")
    if raw_digest not in (None, "") and digest is None:
        errors.append(f"{digest_name}_invalid")
    if path and not digest:
        errors.append(f"{digest_name}_missing")
    if digest and not path:
        errors.append(f"{path_name}_missing")


def _with_source_context(
    provenance: Mapping[str, Any],
    *sources: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(provenance)
    if not isinstance(payload.get("feature_basis"), Mapping) or not payload.get("feature_basis"):
        payload["feature_basis"] = _first_context_mapping(
            sources,
            "feature_basis",
            "market_feature_basis",
        )
    if not isinstance(payload.get("data_quality"), Mapping) or not payload.get("data_quality"):
        payload["data_quality"] = _first_context_mapping(
            sources,
            "data_quality",
            "market_data_quality",
        )
    return payload


def _first_context_mapping(
    sources: Iterable[Mapping[str, Any]],
    *fields: str,
) -> dict[str, Any]:
    for source in sources:
        for field in fields:
            value = source.get(field)
            if isinstance(value, Mapping) and value:
                return _mapping(value)
        for snapshot_field in ("market_state_snapshot", "market_snapshot", "latest_market_snapshot"):
            snapshot = source.get(snapshot_field)
            if not isinstance(snapshot, Mapping):
                continue
            for field in fields:
                value = snapshot.get(field)
                if isinstance(value, Mapping) and value:
                    return _mapping(value)
    return {}


def _portable_artifact_path(value: Any) -> str | None:
    text = _text(value).replace("\\", "/")
    if not text or text.startswith("/") or _WINDOWS_ABSOLUTE_RE.match(text):
        return None
    path = PurePosixPath(text)
    if ".." in path.parts or any(part in {"", "."} for part in path.parts):
        return None
    return path.as_posix()


def _sha256(value: Any) -> str | None:
    text = _text(value).casefold()
    if text.startswith("sha256:"):
        text = text[7:]
    return text if _SHA256_RE.fullmatch(text) else None


def _strict_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): deepcopy(item)
        for key, item in value.items()
        if str(key or "").strip()
    }


def _data_quality(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return _mapping(value)
    text = _text(value)
    return {"status": text} if text else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = (
    "CACHE_STATUSES",
    "CANDIDATE_SOURCE_MODES",
    "DATA_ACQUISITION_MODES",
    "MARKET_PROVENANCE_CONTRACT_VERSION",
    "MARKET_PROVENANCE_SCHEMA_VERSION",
    "market_provenance_flat_fields",
    "market_provenance_values",
    "merge_market_provenance",
    "normalize_market_provenance",
)
