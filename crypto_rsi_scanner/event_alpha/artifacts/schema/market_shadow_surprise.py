"""Closed nested schema checks for shadow temporal market surprise v1."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import Any


SCHEMA_ID = "event_alpha.shadow_temporal_surprise"
SCHEMA_VERSION = 1
FEATURES = ("volume_24h", "turnover_24h")

_TOP_LEVEL_KEYS = frozenset(
    (
        "schema_id",
        "schema_version",
        "status",
        "history_artifact",
        "history_artifact_sha256",
        "current_observation",
        "surveyed_prior_first_observation",
        "surveyed_prior_last_observation",
        "supplied_prior_observation_count",
        "minimum_sample_count",
        "method",
        "features",
        "routing_eligible",
        "priority_eligible",
        "score_adjustment_eligible",
        "decision_score_eligible",
        "auto_apply",
        "research_only",
    )
)
_METHOD_KEYS = frozenset(
    (
        "transform",
        "location_estimator",
        "scale_estimator",
        "normal_consistency_factor",
        "degenerate_mad_threshold",
        "derived_float_decimal_places",
        "derived_ratio_rel_tolerance",
        "derived_ratio_abs_tolerance",
        "upper_tail_rank_definition",
        "upper_tail_rank_is_p_value",
    )
)
_FEATURE_KEYS = frozenset(
    (
        "feature",
        "status",
        "reason",
        "current_value",
        "current_log",
        "feature_basis",
        "sample_count",
        "minimum_sample_count",
        "basis_ineligible_baseline_count",
        "invalid_baseline_count",
        "eligible_baseline_first_observation",
        "eligible_baseline_last_observation",
        "eligible_sample_sha256",
        "median_log",
        "mad_log",
        "normal_consistent_mad_log",
        "robust_z",
        "upper_tail_rank",
        "upper_tail_rank_is_p_value",
    )
)
_REFERENCE_KEYS = frozenset(("observation_id", "observed_at"))
_TOP_LEVEL_STATUSES = frozenset(("ready", "partial", "unavailable"))
_FEATURE_STATUSES = frozenset(
    (
        "ready",
        "basis_ineligible",
        "current_unavailable",
        "insufficient_history",
        "degenerate_scale",
        "unavailable",
    )
)
_FEATURE_REASONS = frozenset(
    (
        "current_feature_basis_not_eligible",
        "current_value_not_strictly_positive_finite",
        "minimum_sample_count_not_met",
        "mad_at_or_below_degenerate_threshold",
        "non_finite_robust_z",
    )
)
_METHOD_VALUES = {
    "transform": "natural_log",
    "location_estimator": "median",
    "scale_estimator": "median_absolute_deviation",
    "normal_consistency_factor": 1.482602218505602,
    "degenerate_mad_threshold": 1e-12,
    "derived_float_decimal_places": 12,
    "derived_ratio_rel_tolerance": 1e-9,
    "derived_ratio_abs_tolerance": 1e-12,
    "upper_tail_rank_definition": (
        "(count(baseline_log >= current_log)+1)/(sample_count+1)"
    ),
    "upper_tail_rank_is_p_value": False,
}
_FALSE_ISOLATION_FLAGS = (
    "routing_eligible",
    "priority_eligible",
    "score_adjustment_eligible",
    "decision_score_eligible",
    "auto_apply",
)
_NULLABLE_NUMBERS = (
    "current_value",
    "current_log",
    "median_log",
    "mad_log",
    "normal_consistent_mad_log",
    "robust_z",
    "upper_tail_rank",
)
_NONNEGATIVE_COUNTS = (
    "sample_count",
    "basis_ineligible_baseline_count",
    "invalid_baseline_count",
)
_REASON_BY_STATUS = {
    "ready": None,
    "basis_ineligible": "current_feature_basis_not_eligible",
    "current_unavailable": "current_value_not_strictly_positive_finite",
    "insufficient_history": "minimum_sample_count_not_met",
    "degenerate_scale": "mad_at_or_below_degenerate_threshold",
    "unavailable": "non_finite_robust_z",
}
_DERIVED_STAT_FIELDS = (
    "median_log",
    "mad_log",
    "normal_consistent_mad_log",
    "robust_z",
    "upper_tail_rank",
)


def validate_contract(
    row: Mapping[str, Any],
    *,
    reject_anomaly_snapshot_placement: bool = False,
) -> list[str]:
    """Validate an optional shadow value and its artifact placement."""

    errors: list[str] = []
    if any(
        _contains_shadow_key(nested)
        for key, nested in row.items()
        if key != "shadow_temporal_surprise"
    ):
        errors.append(
            "shadow_temporal_surprise_forbidden_placement:nested_market_evidence"
        )
    if reject_anomaly_snapshot_placement and "market_state_snapshot" in row:
        snapshot = row.get("market_state_snapshot")
        if not isinstance(snapshot, Mapping):
            errors.append(
                "shadow_temporal_surprise_invalid_type:market_state_snapshot:dict"
            )
        elif "shadow_temporal_surprise" in snapshot:
            errors.append(
                "shadow_temporal_surprise_forbidden_placement:market_state_snapshot"
            )

    if "shadow_temporal_surprise" not in row:
        return errors
    value = row.get("shadow_temporal_surprise")
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:value:dict")
        return errors
    errors.extend(_validate_value(value))
    return errors


def validate_absence_contract(row: Mapping[str, Any]) -> list[str]:
    """Reject shadow metadata on every non-market-evidence artifact."""

    if _contains_shadow_key(row):
        return [
            "shadow_temporal_surprise_forbidden_placement:outside_market_evidence"
        ]
    return []


def _contains_shadow_key(value: object) -> bool:
    pending = [value]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        if isinstance(current, Mapping):
            if "shadow_temporal_surprise" in current:
                return True
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return False


def _validate_value(value: Mapping[str, Any]) -> list[str]:
    errors = _closed_keys(value, _TOP_LEVEL_KEYS, "value")
    if errors:
        return errors

    _expect_exact(value, "schema_id", SCHEMA_ID, "value", errors)
    _expect_exact(value, "schema_version", SCHEMA_VERSION, "value", errors)
    _expect_enum(value, "status", _TOP_LEVEL_STATUSES, "value", errors)
    history_artifact = value.get("history_artifact")
    if (
        not isinstance(history_artifact, str)
        or not history_artifact
        or history_artifact in {".", ".."}
        or "/" in history_artifact
        or "\\" in history_artifact
    ):
        errors.append(
            "shadow_temporal_surprise_invalid_type:value.history_artifact:safe_basename"
        )
    if not _is_sha256(value.get("history_artifact_sha256")):
        errors.append(
            "shadow_temporal_surprise_invalid_type:value.history_artifact_sha256:sha256"
        )
    _expect_nonnegative_int(
        value, "supplied_prior_observation_count", "value", errors
    )
    _expect_positive_int(value, "minimum_sample_count", "value", errors)
    for field in _FALSE_ISOLATION_FLAGS:
        _expect_exact(value, field, False, "value", errors)
    _expect_exact(value, "research_only", True, "value", errors)

    _validate_reference(value.get("current_observation"), "current_observation", errors)
    _validate_nullable_reference(
        value.get("surveyed_prior_first_observation"),
        "surveyed_prior_first_observation",
        errors,
    )
    _validate_nullable_reference(
        value.get("surveyed_prior_last_observation"),
        "surveyed_prior_last_observation",
        errors,
    )
    _validate_method(value.get("method"), errors)
    _validate_features(value.get("features"), errors)
    _validate_cross_field_consistency(value, errors)
    return errors


def _validate_method(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:method:dict")
        return
    key_errors = _closed_keys(value, _METHOD_KEYS, "method")
    errors.extend(key_errors)
    if key_errors:
        return
    for field, expected in _METHOD_VALUES.items():
        _expect_exact(value, field, expected, "method", errors)


def _validate_features(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:features:dict")
        return
    key_errors = _closed_keys(value, frozenset(FEATURES), "features")
    errors.extend(key_errors)
    if key_errors:
        return
    for feature in FEATURES:
        _validate_feature(value.get(feature), feature, errors)


def _validate_feature(value: object, feature: str, errors: list[str]) -> None:
    path = f"features.{feature}"
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    key_errors = _closed_keys(value, _FEATURE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return

    _expect_exact(value, "feature", feature, path, errors)
    _expect_enum(value, "status", _FEATURE_STATUSES, path, errors)
    reason = value.get("reason")
    if reason is not None and (
        not isinstance(reason, str) or reason not in _FEATURE_REASONS
    ):
        errors.append(f"shadow_temporal_surprise_invalid_enum:{path}.reason")
    basis = value.get("feature_basis")
    if basis is not None and (not isinstance(basis, str) or not basis.strip()):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}.feature_basis:str_or_null")
    for field in _NULLABLE_NUMBERS:
        if not _is_finite_number_or_none(value.get(field)):
            errors.append(
                f"shadow_temporal_surprise_invalid_type:{path}.{field}:finite_number_or_null"
            )
    for field in _NONNEGATIVE_COUNTS:
        _expect_nonnegative_int(value, field, path, errors)
    _expect_positive_int(value, "minimum_sample_count", path, errors)
    _validate_nullable_reference(
        value.get("eligible_baseline_first_observation"),
        f"{path}.eligible_baseline_first_observation",
        errors,
    )
    _validate_nullable_reference(
        value.get("eligible_baseline_last_observation"),
        f"{path}.eligible_baseline_last_observation",
        errors,
    )
    digest = value.get("eligible_sample_sha256")
    if not _is_sha256(digest):
        errors.append(
            f"shadow_temporal_surprise_invalid_type:{path}.eligible_sample_sha256:sha256"
        )
    _expect_exact(value, "upper_tail_rank_is_p_value", False, path, errors)


def _validate_cross_field_consistency(
    value: Mapping[str, Any],
    errors: list[str],
) -> None:
    features = value.get("features")
    if not isinstance(features, Mapping) or frozenset(features) != frozenset(FEATURES):
        return
    supplied = value.get("supplied_prior_observation_count")
    minimum = value.get("minimum_sample_count")
    ready_count = sum(
        isinstance(features.get(feature), Mapping)
        and features[feature].get("status") == "ready"
        for feature in FEATURES
    )
    expected_status = "ready" if ready_count == len(FEATURES) else (
        "partial" if ready_count else "unavailable"
    )
    if value.get("status") != expected_status:
        errors.append("shadow_temporal_surprise_status_inconsistent:value.status")
    _validate_reference_presence(
        count=supplied,
        first=value.get("surveyed_prior_first_observation"),
        last=value.get("surveyed_prior_last_observation"),
        path="surveyed_prior",
        errors=errors,
    )
    for feature in FEATURES:
        feature_value = features.get(feature)
        if not isinstance(feature_value, Mapping) or frozenset(feature_value) != _FEATURE_KEYS:
            continue
        _validate_feature_consistency(
            feature_value,
            feature=feature,
            supplied=supplied,
            top_level_minimum=minimum,
            errors=errors,
        )


def _validate_feature_consistency(
    value: Mapping[str, Any],
    *,
    feature: str,
    supplied: object,
    top_level_minimum: object,
    errors: list[str],
) -> None:
    path = f"features.{feature}"
    status = value.get("status")
    if status in _REASON_BY_STATUS and value.get("reason") != _REASON_BY_STATUS[status]:
        errors.append(f"shadow_temporal_surprise_reason_inconsistent:{path}")
    if value.get("minimum_sample_count") != top_level_minimum:
        errors.append(f"shadow_temporal_surprise_minimum_inconsistent:{path}")
    sample_count = value.get("sample_count")
    feature_minimum = value.get("minimum_sample_count")
    if (
        isinstance(sample_count, int)
        and not isinstance(sample_count, bool)
        and isinstance(feature_minimum, int)
        and not isinstance(feature_minimum, bool)
    ):
        if status in {"ready", "degenerate_scale", "unavailable"} and (
            sample_count < feature_minimum
        ):
            errors.append(f"shadow_temporal_surprise_sample_status_mismatch:{path}")
        if status == "insufficient_history" and sample_count >= feature_minimum:
            errors.append(f"shadow_temporal_surprise_sample_status_mismatch:{path}")
    counts = (
        value.get("sample_count"),
        value.get("basis_ineligible_baseline_count"),
        value.get("invalid_baseline_count"),
    )
    if (
        isinstance(supplied, int)
        and not isinstance(supplied, bool)
        and all(isinstance(item, int) and not isinstance(item, bool) for item in counts)
        and sum(counts) != supplied
    ):
        errors.append(f"shadow_temporal_surprise_sample_accounting_mismatch:{path}")
    _validate_reference_presence(
        count=value.get("sample_count"),
        first=value.get("eligible_baseline_first_observation"),
        last=value.get("eligible_baseline_last_observation"),
        path=f"{path}.eligible_baseline",
        errors=errors,
    )
    basis = value.get("feature_basis")
    if status in {"ready", "insufficient_history", "degenerate_scale", "unavailable"}:
        eligible_basis = basis == "provider_observed" or (
            feature == "turnover_24h" and basis == "derived_provider_ratio"
        )
        if not eligible_basis:
            errors.append(f"shadow_temporal_surprise_basis_inconsistent:{path}")
    required_statistics = {
        "ready": {
            "current_value", "current_log", "median_log", "mad_log",
            "normal_consistent_mad_log", "robust_z", "upper_tail_rank",
        },
        "degenerate_scale": {
            "current_value", "current_log", "median_log", "mad_log",
            "normal_consistent_mad_log", "upper_tail_rank",
        },
        "unavailable": {
            "current_value", "current_log", "median_log", "mad_log",
            "normal_consistent_mad_log", "upper_tail_rank",
        },
        "insufficient_history": {"current_value", "current_log"},
    }.get(status, set())
    for field in (*_DERIVED_STAT_FIELDS, "current_log"):
        should_exist = field in required_statistics
        if should_exist != (value.get(field) is not None):
            errors.append(
                f"shadow_temporal_surprise_statistic_inconsistent:{path}.{field}"
            )
    if status != "basis_ineligible":
        current_should_exist = "current_value" in required_statistics
        if current_should_exist != (value.get("current_value") is not None):
            errors.append(
                f"shadow_temporal_surprise_statistic_inconsistent:{path}.current_value"
            )
    tail = value.get("upper_tail_rank")
    if _is_finite_number_or_none(tail) and tail is not None and not 0 <= float(tail) <= 1:
        errors.append(f"shadow_temporal_surprise_tail_out_of_range:{path}")


def _validate_reference_presence(
    *,
    count: object,
    first: object,
    last: object,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return
    should_exist = count > 0
    if should_exist != (first is not None) or should_exist != (last is not None):
        errors.append(f"shadow_temporal_surprise_reference_inconsistent:{path}")


def _validate_reference(value: object, path: str, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    key_errors = _closed_keys(value, _REFERENCE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return
    for field in _REFERENCE_KEYS:
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            errors.append(
                f"shadow_temporal_surprise_invalid_type:{path}.{field}:str"
            )


def _validate_nullable_reference(value: object, path: str, errors: list[str]) -> None:
    if value is None:
        return
    _validate_reference(value, path, errors)


def _closed_keys(
    value: Mapping[str, Any], expected: frozenset[str], path: str
) -> list[str]:
    actual = frozenset(value)
    if actual == expected:
        return []
    missing = ",".join(sorted(expected - actual)) or "-"
    unexpected = ",".join(sorted(actual - expected)) or "-"
    return [
        "shadow_temporal_surprise_closed_keys:"
        f"{path}:missing={missing}:unexpected={unexpected}"
    ]


def _expect_exact(
    value: Mapping[str, Any],
    field: str,
    expected: object,
    path: str,
    errors: list[str],
) -> None:
    actual = value.get(field)
    if type(actual) is not type(expected) or actual != expected:
        errors.append(f"shadow_temporal_surprise_fixed_value_mismatch:{path}.{field}")


def _expect_enum(
    value: Mapping[str, Any],
    field: str,
    allowed: frozenset[str],
    path: str,
    errors: list[str],
) -> None:
    actual = value.get(field)
    if not isinstance(actual, str) or actual not in allowed:
        errors.append(f"shadow_temporal_surprise_invalid_enum:{path}.{field}")


def _expect_nonnegative_int(
    value: Mapping[str, Any], field: str, path: str, errors: list[str]
) -> None:
    actual = value.get(field)
    if isinstance(actual, bool) or not isinstance(actual, int) or actual < 0:
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}.{field}:nonnegative_int")


def _expect_positive_int(
    value: Mapping[str, Any], field: str, path: str, errors: list[str]
) -> None:
    actual = value.get(field)
    if isinstance(actual, bool) or not isinstance(actual, int) or actual < 1:
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}.{field}:positive_int")


def _is_finite_number_or_none(value: object) -> bool:
    return value is None or (
        not isinstance(value, bool)
        and isinstance(value, Real)
        and math.isfinite(float(value))
    )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
