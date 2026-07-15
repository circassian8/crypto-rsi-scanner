"""Closed source-binding helpers for the Decision episode scorecard."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from . import outcome_eligibility
from ..radar.decision_model_surfaces import decision_model_values
from ..radar.decision_models import decision_score_cohort_values


SOURCE_ARTIFACT_BINDING_KEYS = {
    "source_role",
    "artifact_namespace",
    "run_id",
    "artifact_name",
    "artifact_sha256",
    "artifact_size_bytes",
    "row_count",
    "binding_source",
}
SOURCE_ROLES = ("candidate", "core", "outcome")
OUTCOME_VALIDATION_BINDING_KEYS = {
    "schema_id",
    "schema_version",
    "artifact_namespace",
    "candidate_id",
    "outcome_identity_key",
    "outcome_row_digest",
    "valid",
    "reasons",
    "score_cohort_status",
    "score_cohort_reason",
    "canonical_score_cohorts",
}
OUTCOME_VALIDATION_SCHEMA_ID = (
    "event_alpha.campaign_ledger_outcome_validation_binding"
)


def primary_outcome_state(
    outcome: Mapping[str, Any],
    *,
    evaluated_at: datetime,
) -> tuple[str, str | None, str | None, float | None]:
    """Classify only the declared primary horizon against an external clock."""

    primary = outcome.get("primary_horizon")
    metadata = outcome.get("horizon_metadata")
    if type(primary) is not str or not isinstance(metadata, Mapping):
        return "contract_excluded", None, None, None
    item = metadata.get(primary)
    if not isinstance(item, Mapping):
        return "contract_excluded", None, None, None
    due = outcome_eligibility.parse_aware_time(item.get("due_at"))
    if due is None:
        return "contract_excluded", None, None, None
    due_text = due.isoformat()
    maturity = item.get("maturity_status")
    if maturity == "matured":
        primary_return = outcome_eligibility.finite_number(
            outcome.get("primary_horizon_return")
        )
        returns = outcome.get("return_by_horizon")
        mapped = (
            outcome_eligibility.finite_number(returns.get(primary))
            if isinstance(returns, Mapping)
            else None
        )
        price_time = outcome_eligibility.parse_aware_time(
            item.get("price_observed_at")
        )
        if (
            primary_return is None
            or mapped != primary_return
            or due > evaluated_at
            or price_time is None
            or price_time > evaluated_at
        ):
            return "contract_excluded", primary, due_text, None
        return "matured", primary, due_text, primary_return
    if due > evaluated_at:
        return "not_due", primary, due_text, None
    if maturity in {"pending", "missing_data"}:
        return "due_missing_price", primary, due_text, None
    return "contract_excluded", primary, due_text, None


def materialize_source_artifact_bindings(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    materialized = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("source_artifact_binding_not_mapping")
        materialized.append(dict(row))
    return sorted(materialized, key=_source_binding_sort_key)


def materialize_outcome_validation_bindings(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    materialized = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("outcome_validation_binding_not_mapping")
        materialized.append(dict(row))
    return sorted(materialized, key=_validation_binding_sort_key)


def source_artifact_binding_errors(
    rows: Sequence[Mapping[str, Any]],
    *,
    row_counts: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    observed_counts: Counter[str] = Counter()
    sort_keys: list[tuple[str, ...]] = []
    for index, row in enumerate(rows):
        prefix = f"source_artifact_binding_{index}"
        if type(row) is not dict:
            errors.append(f"{prefix}:not_object")
            continue
        _check_exact_keys(row, SOURCE_ARTIFACT_BINDING_KEYS, prefix, errors)
        role = row.get("source_role")
        if role not in SOURCE_ROLES:
            errors.append(f"{prefix}:invalid_source_role")
        for field in ("artifact_namespace", "run_id"):
            if not _exact_text(row.get(field)):
                errors.append(f"{prefix}:invalid_{field}")
        artifact = row.get("artifact_name")
        if (
            not _exact_text(artifact)
            or "/" in str(artifact)
            or "\\" in str(artifact)
            or artifact in {".", ".."}
        ):
            errors.append(f"{prefix}:invalid_artifact_name")
        if not _is_digest(row.get("artifact_sha256")):
            errors.append(f"{prefix}:invalid_artifact_sha256")
        for field in ("artifact_size_bytes", "row_count"):
            if type(row.get(field)) is not int or row.get(field) < 0:
                errors.append(f"{prefix}:invalid_{field}")
        if not _exact_text(row.get("binding_source")):
            errors.append(f"{prefix}:invalid_binding_source")
        if role in SOURCE_ROLES and type(row.get("row_count")) is int:
            observed_counts[str(role)] += row["row_count"]
        sort_keys.append(_source_binding_sort_key(row))
    if sort_keys != sorted(sort_keys) or len(sort_keys) != len(set(sort_keys)):
        errors.append("source_artifact_bindings_not_unique_sorted")
    for role in SOURCE_ROLES:
        expected = row_counts.get(role)
        if type(expected) is not int or isinstance(expected, bool) or expected < 0:
            errors.append(f"source_artifact_binding_{role}_expected_count_invalid")
            continue
        if observed_counts[role] != row_counts.get(role):
            errors.append(f"source_artifact_binding_{role}_row_count_mismatch")
    return sorted(set(errors))


def outcome_validation_binding_errors(
    rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    sort_keys: list[tuple[str, ...]] = []
    for index, row in enumerate(rows):
        prefix = f"outcome_validation_binding_{index}"
        if type(row) is not dict:
            errors.append(f"{prefix}:not_object")
            continue
        _check_exact_keys(row, OUTCOME_VALIDATION_BINDING_KEYS, prefix, errors)
        if row.get("schema_id") != OUTCOME_VALIDATION_SCHEMA_ID:
            errors.append(f"{prefix}:invalid_schema_id")
        if row.get("schema_version") != 1:
            errors.append(f"{prefix}:invalid_schema_version")
        valid = row.get("valid")
        if type(valid) is not bool:
            errors.append(f"{prefix}:invalid_valid")
        for field in ("artifact_namespace", "candidate_id"):
            value = row.get(field)
            if not _exact_text(value) and not (valid is False and value is None):
                errors.append(f"{prefix}:invalid_{field}")
        identity_key = row.get("outcome_identity_key")
        if not _is_digest(identity_key) and not (
            valid is False and identity_key is None
        ):
            errors.append(f"{prefix}:invalid_outcome_identity_key")
        if not _is_digest(row.get("outcome_row_digest")):
            errors.append(f"{prefix}:invalid_outcome_row_digest")
        reasons = row.get("reasons")
        if (
            type(reasons) is not list
            or reasons != sorted(set(reasons))
            or not all(_exact_text(reason) for reason in reasons)
        ):
            errors.append(f"{prefix}:invalid_reasons")
        elif valid is False and not reasons:
            errors.append(f"{prefix}:invalid_binding_requires_reason")
        cohort_status = row.get("score_cohort_status")
        if cohort_status not in {
            "canonical_exact",
            "legacy_unversioned_exact",
            "legacy_null_derived_from_canonical_scores",
            "invalid",
        }:
            errors.append(f"{prefix}:invalid_score_cohort_status")
        reason = row.get("score_cohort_reason")
        if reason is not None and not _exact_text(reason):
            errors.append(f"{prefix}:invalid_score_cohort_reason")
        cohorts = row.get("canonical_score_cohorts")
        if (
            not isinstance(cohorts, Mapping)
            or set(cohorts) != {
                "actionability_score_cohort",
                "evidence_confidence_score_cohort",
                "risk_score_cohort",
            }
            or not all(_exact_text(value) for value in cohorts.values())
        ):
            errors.append(f"{prefix}:invalid_canonical_score_cohorts")
        sort_keys.append(_validation_binding_sort_key(row))
    if sort_keys != sorted(sort_keys):
        errors.append("outcome_validation_bindings_not_sorted")
    return sorted(set(errors))


def representative_candidate_binding_errors(
    payload: Mapping[str, Any],
    candidate_rows: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Recheck representative Decision values against exact supplied candidates."""

    candidates = [dict(row) for row in candidate_rows if isinstance(row, Mapping)]
    errors: list[str] = []
    if payload.get("candidate_input_digest") != _digest(
        sorted(_digest(row) for row in candidates)
    ):
        errors.append("candidate_input_rows_digest_mismatch")
    for index, representative in enumerate(payload.get("representatives") or ()):
        matches = [
            row for row in candidates
            if all(row.get(field) == representative.get(field) for field in (
                "artifact_namespace", "run_id", "candidate_id", "observed_at",
                "canonical_asset_id",
            ))
        ]
        if len(matches) != 1:
            errors.append(f"representative_{index}:candidate_binding_count_invalid")
            continue
        candidate = matches[0]
        projection = decision_model_values(candidate)
        cohorts = decision_score_cohort_values(projection)
        expected = {
            "primary_thesis_origin": projection.get("primary_thesis_origin"),
            "thesis_origins": list(projection.get("thesis_origins") or ()),
            "radar_route": projection.get("radar_route"),
            "directional_bias": projection.get("directional_bias"),
            "actionability_score": projection.get("actionability_score"),
            "evidence_confidence_score": projection.get("evidence_confidence_score"),
            "risk_score": projection.get("risk_score"),
            "catalyst_status": projection.get("catalyst_status"),
            "timing_state": projection.get("timing_state"),
            "market_phase": projection.get("market_phase"),
            **(cohorts or {}),
        }
        if any(representative.get(field) != value for field, value in expected.items()):
            errors.append(f"representative_{index}:candidate_decision_values_mismatch")
        if representative.get("candidate_row_digest") != _digest(candidate):
            errors.append(f"representative_{index}:candidate_row_digest_mismatch")
        if representative.get("decision_projection_digest") != _digest(projection):
            errors.append(f"representative_{index}:decision_projection_digest_mismatch")
    return sorted(set(errors))


def _source_binding_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("source_role") or ""),
        str(row.get("artifact_namespace") or ""),
        str(row.get("run_id") or ""),
        str(row.get("artifact_name") or ""),
        str(row.get("artifact_sha256") or ""),
    )


def _validation_binding_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("artifact_namespace") or ""),
        str(row.get("candidate_id") or ""),
        str(row.get("outcome_identity_key") or ""),
        str(row.get("outcome_row_digest") or ""),
    )


def _exact_text(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _is_digest(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _check_exact_keys(
    row: Mapping[str, Any], expected: set[str], prefix: str, errors: list[str]
) -> None:
    errors.extend(f"{prefix}:missing_key:{key}" for key in sorted(expected - set(row)))
    errors.extend(f"{prefix}:unknown_key:{key}" for key in sorted(set(row) - expected))


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


__all__ = (
    "OUTCOME_VALIDATION_SCHEMA_ID",
    "materialize_outcome_validation_bindings",
    "materialize_source_artifact_bindings",
    "outcome_validation_binding_errors",
    "primary_outcome_state",
    "representative_candidate_binding_errors",
    "source_artifact_binding_errors",
)
