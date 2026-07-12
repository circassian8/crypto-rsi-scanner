"""Nested operator-state fingerprint contract validation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

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
_JSONL_ARTIFACTS = {"core_opportunities", "unified_calendar"}
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


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate fingerprints on every artifact claiming current authority."""

    artifacts = row.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return []
    errors: list[str] = []
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
