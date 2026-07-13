"""Nested operator-state fingerprint contract validation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from ...operations import market_provenance
from ..fingerprints import (
    ALL_FINGERPRINT_KINDS,
    CANONICAL_RUN_ROW_KIND as FINGERPRINT_KIND_CANONICAL_RUN_ROW,
    DIRECTORY_TREE_KIND as FINGERPRINT_KIND_DIRECTORY_TREE,
    FILE_BYTES_KIND as FINGERPRINT_KIND_FILE_BYTES,
    FINGERPRINT_CONTRACT_VERSION,
    FINGERPRINT_FIELDS,
    JSONL_LINES_KIND as FINGERPRINT_KIND_JSONL_LINES,
)

FINGERPRINT_KINDS = frozenset(ALL_FINGERPRINT_KINDS)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_JSONL_ARTIFACTS = {
    "core_opportunities",
    "unified_calendar",
    "market_history",
    "integrated_candidates",
    "integrated_outcomes",
}
_DIRECTORY_ARTIFACTS = {"research_cards"}
_RUN_ROW_IDENTITY_FIELDS = ("run_id", "profile", "artifact_namespace")
_COMMON_FINGERPRINT_FIELDS = FINGERPRINT_FIELDS
_RUN_ROW_FINGERPRINT_FIELDS = ("run_row_identity", "run_row_match_count")
_INVALID_LEGACY_FINGERPRINT_FIELDS = ("run_row_sha256",)
_LEGACY_SHA_ONLY_OTHER_FIELDS = tuple(
    field
    for field in (
        *_COMMON_FINGERPRINT_FIELDS,
        *_RUN_ROW_FINGERPRINT_FIELDS,
        *_INVALID_LEGACY_FINGERPRINT_FIELDS,
    )
    if field != "sha256"
)
_MARKET_NO_SEND_PROVENANCE_V1_FIELDS = frozenset(
    {
        "contract_version",
        "data_mode",
        "provider",
        "observed_at",
        "request_cache_artifact",
        "contract_counted_status",
        "provider_call_attempted",
        "provider_request_succeeded",
        "no_send_status",
        "no_send",
        "research_only",
        "trades_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
        "telegram_sends",
    }
)
_MARKET_NO_SEND_PROVENANCE_V2_FIELDS = frozenset(
    {
        "schema_version",
        "contract_version",
        "data_acquisition_mode",
        "candidate_source_mode",
        "provider",
        "provider_call_attempted",
        "provider_call_succeeded",
        "live_provider_authorized",
        "request_ledger_path",
        "request_ledger_sha256",
        "provider_source_artifact",
        "provider_source_artifact_sha256",
        "provider_generation_id",
        "cache_status",
        "provenance_contract_valid",
        "burn_in_eligible",
        "burn_in_counted",
        "burn_in_reason",
        "feature_basis",
        "data_quality",
        "validation_errors",
    }
)


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate fingerprints on every artifact claiming current authority."""

    errors = _validate_market_no_send_provenance(row.get("market_no_send_provenance"))
    artifacts = row.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return errors
    for raw_name, raw_entry in artifacts.items():
        name = str(raw_name)
        if not isinstance(raw_entry, Mapping):
            continue
        if str(raw_entry.get("status") or "") != "current":
            continue
        if _is_valid_legacy_sha_only(raw_entry):
            continue
        if not _has_fingerprint_contract(raw_entry):
            continue
        errors.extend(_validate_current_entry(name, raw_entry, state=row))
    return errors


def _validate_market_no_send_provenance(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return ["operator_state_market_no_send_provenance_not_object"]
    errors: list[str] = []
    version = value.get("contract_version")
    if version == 1:
        return _validate_market_no_send_provenance_v1(value)
    if version != 2:
        errors.append("operator_state_market_no_send_provenance_version_invalid")
        return errors
    if set(value) != _MARKET_NO_SEND_PROVENANCE_V2_FIELDS:
        errors.append("operator_state_market_no_send_provenance_fields_invalid")
    if value.get("schema_version") != "crypto_radar_market_provenance_v2":
        errors.append("operator_state_market_no_send_schema_version_invalid")
    normalized = market_provenance.normalize_market_provenance(value)
    if dict(value) != normalized:
        errors.append("operator_state_market_no_send_provenance_not_canonical")
    acquisition_mode = value.get("data_acquisition_mode")
    source_mode = value.get("candidate_source_mode")
    provider = value.get("provider")
    mode_pairs = {
        "live_provider": "live_no_send",
        "mocked_fixture": "mocked_fixture",
        "artifact_replay": "artifact_replay",
        "preflight_only": "preflight_only",
        "cache_replay": "artifact_replay",
    }
    if acquisition_mode not in mode_pairs:
        errors.append("operator_state_market_no_send_acquisition_mode_invalid")
    if mode_pairs.get(acquisition_mode) != source_mode:
        errors.append("operator_state_market_no_send_candidate_source_mode_invalid")
    if not isinstance(provider, str) or not provider.strip():
        errors.append("operator_state_market_no_send_provider_invalid")
    request_artifact = value.get("provider_source_artifact")
    request_path = Path(str(request_artifact or ""))
    if (
        request_artifact != "event_market_no_send_market_rows.json"
        or request_path.is_absolute()
        or len(request_path.parts) != 1
    ):
        errors.append("operator_state_market_no_send_request_artifact_invalid")
    ledger = value.get("request_ledger_path")
    ledger_path = Path(str(ledger or ""))
    if (
        ledger != "event_market_no_send_request_ledger.json"
        or ledger_path.is_absolute()
        or len(ledger_path.parts) != 1
    ):
        errors.append("operator_state_market_no_send_request_ledger_invalid")
    for field in ("provider_source_artifact_sha256", "request_ledger_sha256"):
        if not _valid_sha256(value.get(field)):
            errors.append(f"operator_state_market_no_send_{field}_invalid")
    live = source_mode == "live_no_send"
    validation_errors = value.get("validation_errors")
    if not isinstance(validation_errors, list) or any(not isinstance(item, str) for item in validation_errors):
        errors.append("operator_state_market_no_send_validation_errors_invalid")
        validation_errors = []
    elif validation_errors:
        errors.append("operator_state_market_no_send_provenance_contract_invalid")
    eligible = bool(
        live
        and value.get("live_provider_authorized") is True
        and value.get("provider_call_attempted") is True
        and value.get("provider_call_succeeded") is True
        and not validation_errors
    )
    contract_valid = not validation_errors
    if value.get("provenance_contract_valid") is not contract_valid:
        errors.append("invalid_market_no_send_provenance:provenance_contract_valid")
    for field in ("burn_in_eligible", "burn_in_counted"):
        if value.get(field) is not eligible:
            errors.append(f"invalid_market_no_send_provenance:{field}")
    if not str(value.get("provider_generation_id") or "").strip():
        errors.append("operator_state_market_no_send_generation_id_invalid")
    if value.get("cache_status") not in {
        "not_applicable", "miss", "hit", "refreshed", "write_through", "unknown"
    }:
        errors.append("operator_state_market_no_send_cache_status_invalid")
    if not str(value.get("burn_in_reason") or "").strip():
        errors.append("operator_state_market_no_send_burn_in_reason_invalid")
    for field in ("feature_basis", "data_quality"):
        if not isinstance(value.get(field), Mapping):
            errors.append(f"operator_state_market_no_send_{field}_invalid")
    return errors


def _validate_market_no_send_provenance_v1(value: Mapping[str, Any]) -> list[str]:
    """Keep already-published historical v1 operator states readable."""

    errors: list[str] = []
    if set(value) != _MARKET_NO_SEND_PROVENANCE_V1_FIELDS:
        errors.append("operator_state_market_no_send_provenance_fields_invalid")
    data_mode = value.get("data_mode")
    if data_mode not in {"live", "mock"}:
        errors.append("operator_state_market_no_send_data_mode_invalid")
    if value.get("provider") != ("coingecko" if data_mode == "live" else "mock_coingecko"):
        errors.append("operator_state_market_no_send_provider_invalid")
    request_artifact = value.get("request_cache_artifact")
    request_path = Path(str(request_artifact or ""))
    if (
        request_artifact != "event_market_no_send_market_rows.json"
        or request_path.is_absolute()
        or len(request_path.parts) != 1
    ):
        errors.append("operator_state_market_no_send_request_artifact_invalid")
    expected = {
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "no_send": True,
        "research_only": True,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "telegram_sends": 0,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            errors.append(f"invalid_safety_market_no_send_provenance:{field}")
    return errors


def _validate_current_entry(
    name: str,
    entry: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
) -> list[str]:
    errors = [
        f"operator_state_current_artifact_missing_fingerprint:{name}:{field}"
        for field in _COMMON_FINGERPRINT_FIELDS
        if field not in entry or entry.get(field) is None
    ]
    if "run_row_sha256" in entry:
        errors.append(
            f"operator_state_current_artifact_deprecated_run_row_sha256:{name}"
        )
    if name != "run_ledger" and any(
        field in entry for field in _RUN_ROW_FINGERPRINT_FIELDS
    ):
        errors.append(
            f"operator_state_current_artifact_invalid_run_row_fields:{name}"
        )
    version = entry.get("fingerprint_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FINGERPRINT_CONTRACT_VERSION:
        errors.append(f"operator_state_current_artifact_invalid_fingerprint_version:{name}")
    kind = str(entry.get("fingerprint_kind") or "")
    expected_kind = _expected_kind(name)
    if kind not in FINGERPRINT_KINDS or kind != expected_kind:
        errors.append(f"operator_state_current_artifact_invalid_fingerprint_kind:{name}")
    if not _valid_sha256(entry.get("sha256")):
        errors.append(f"operator_state_current_artifact_invalid_sha256:{name}")
    for field in ("size_bytes", "item_count"):
        if not _nonnegative_int(entry.get(field)):
            errors.append(f"operator_state_current_artifact_invalid_{field}:{name}")
    if name == "run_ledger":
        errors.extend(_validate_run_row_fingerprint(entry, state=state))
    return list(dict.fromkeys(errors))


def _validate_run_row_fingerprint(
    entry: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    identity = entry.get("run_row_identity")
    if not isinstance(identity, Mapping):
        errors.append("operator_state_run_ledger_invalid_run_row_identity")
    else:
        for field in _RUN_ROW_IDENTITY_FIELDS:
            expected = state.get(field)
            if not isinstance(expected, str) or not expected or identity.get(field) != expected:
                errors.append(f"operator_state_run_ledger_identity_mismatch:{field}")
    match_count = entry.get("run_row_match_count")
    if not isinstance(match_count, int) or isinstance(match_count, bool) or match_count != 1:
        errors.append("operator_state_run_ledger_match_count_not_one")
    item_count = entry.get("item_count")
    if not isinstance(item_count, int) or isinstance(item_count, bool) or item_count != 1:
        errors.append("operator_state_run_ledger_item_count_not_one")
    return errors


def _expected_kind(name: str) -> str:
    if name == "run_ledger":
        return FINGERPRINT_KIND_CANONICAL_RUN_ROW
    if name in _DIRECTORY_ARTIFACTS:
        return FINGERPRINT_KIND_DIRECTORY_TREE
    if name in _JSONL_ARTIFACTS:
        return FINGERPRINT_KIND_JSONL_LINES
    return FINGERPRINT_KIND_FILE_BYTES


def _has_fingerprint_contract(entry: Mapping[str, Any]) -> bool:
    return any(
        field in entry
        for field in (
            *_COMMON_FINGERPRINT_FIELDS,
            *_RUN_ROW_FINGERPRINT_FIELDS,
            *_INVALID_LEGACY_FINGERPRINT_FIELDS,
        )
    )


def _is_valid_legacy_sha_only(entry: Mapping[str, Any]) -> bool:
    if not _valid_sha256(entry.get("sha256")):
        return False
    return not any(field in entry for field in _LEGACY_SHA_ONLY_OTHER_FIELDS)


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = (
    "FINGERPRINT_CONTRACT_VERSION",
    "FINGERPRINT_KIND_CANONICAL_RUN_ROW",
    "FINGERPRINT_KIND_DIRECTORY_TREE",
    "FINGERPRINT_KIND_FILE_BYTES",
    "FINGERPRINT_KIND_JSONL_LINES",
    "FINGERPRINT_KINDS",
    "validate_contract",
)
