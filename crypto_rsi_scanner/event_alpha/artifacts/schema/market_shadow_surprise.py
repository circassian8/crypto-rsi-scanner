"""Closed nested schema checks for shadow temporal market surprise v1-v5."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from numbers import Real
from typing import Any


SCHEMA_ID = "event_alpha.shadow_temporal_surprise"
SCHEMA_VERSION = 5
LEGACY_SCHEMA_VERSIONS = frozenset((1, 2, 3, 4))
FEATURES = ("volume_24h", "turnover_24h")
RETURN_HORIZONS_HOURS = (1, 4, 24)
RETURN_BENCHMARKS = ("btc", "eth")
RETURN_FEATURES = (
    *(f"return_{hours}h" for hours in RETURN_HORIZONS_HOURS),
    *(
        f"relative_return_vs_{benchmark}_{hours}h"
        for benchmark in RETURN_BENCHMARKS
        for hours in RETURN_HORIZONS_HOURS
    ),
)
RETURN_ANCHOR_TOLERANCE_RATIO = 0.25
RETURN_MIN_ANCHOR_TOLERANCE_SECONDS = 300
BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS = 300

_TOP_LEVEL_KEYS_V1 = frozenset(
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
_TOP_LEVEL_KEYS = frozenset(
    (
        *_TOP_LEVEL_KEYS_V1,
        "return_status",
        "return_method",
        "return_features",
    )
)
_METHOD_KEYS_V1_V2 = frozenset(
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
_METHOD_KEYS_V3 = frozenset(
    (
        *_METHOD_KEYS_V1_V2,
        "baseline_value_identity",
        "minimum_distinct_baseline_value_count",
        "variation_diagnostics_are_policy",
    )
)
_METHOD_KEYS = frozenset(
    (
        *_METHOD_KEYS_V3,
        "source_value_tuple_identity",
        "input_trace_diagnostics_are_policy",
        "provider_causation_claimed",
    )
)
_FEATURE_KEYS_V1_V2 = frozenset(
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
_FEATURE_KEYS_V3 = frozenset(
    (
        *_FEATURE_KEYS_V1_V2,
        "distinct_baseline_value_count",
        "maximum_baseline_value_tie_count",
        "current_value_baseline_tie_count",
        "distinct_baseline_value_ratio",
        "nominal_one_sided_tail_rank_floor",
    )
)
_INPUT_TRACE_KEYS = frozenset(
    (
        "source_value_tuple_kind",
        "source_value_tuple_count",
        "distinct_source_value_tuple_count",
        "maximum_source_value_tuple_tie_count",
        "source_value_tuple_sha256",
        "source_value_tuple_repeat_excess_count",
        "derived_value_repeat_excess_count",
        "transform_collision_distinct_value_loss_count",
        "maximum_consecutive_source_value_tuple_count",
        "maximum_consecutive_derived_value_count",
        "input_trace_status",
        "input_trace_diagnostics_are_policy",
        "provider_causation_claimed",
    )
)
_FEATURE_KEYS = frozenset((*_FEATURE_KEYS_V3, *_INPUT_TRACE_KEYS))
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
_METHOD_VALUES_V1_V2 = {
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
_METHOD_VALUES_V3 = {
    **_METHOD_VALUES_V1_V2,
    "baseline_value_identity": (
        "transformed_values_rounded_to_12_decimal_places"
    ),
    "minimum_distinct_baseline_value_count": None,
    "variation_diagnostics_are_policy": False,
}
_METHOD_VALUES = {
    **_METHOD_VALUES_V3,
    "source_value_tuple_identity": (
        "ordered_value_only_source_components_formatted_to_17_significant_digits"
    ),
    "input_trace_diagnostics_are_policy": False,
    "provider_causation_claimed": False,
}
_RETURN_METHOD_KEYS_V2 = frozenset(
    (
        "transform",
        "return_unit",
        "location_estimator",
        "scale_estimator",
        "normal_consistency_factor",
        "degenerate_mad_threshold",
        "derived_float_decimal_places",
        "anchor_tolerance_ratio",
        "minimum_anchor_tolerance_seconds",
        "benchmark_alignment_tolerance_seconds",
        "lower_tail_rank_definition",
        "upper_tail_rank_definition",
        "two_sided_tail_rank_definition",
        "tail_ranks_are_p_values",
        "overlapping_samples_are_independent",
    )
)
_RETURN_METHOD_KEYS_V3 = frozenset(
    (
        *_RETURN_METHOD_KEYS_V2,
        "baseline_value_identity",
        "minimum_distinct_baseline_value_count",
        "variation_diagnostics_are_policy",
    )
)
_RETURN_METHOD_KEYS_V4 = frozenset(
    (
        *_RETURN_METHOD_KEYS_V3,
        "source_value_tuple_identity",
        "input_trace_diagnostics_are_policy",
        "provider_causation_claimed",
    )
)
_RETURN_METHOD_KEYS = frozenset(
    (
        *_RETURN_METHOD_KEYS_V4,
        "return_sampling_trace_identity",
        "return_sampling_timing_diagnostics_are_policy",
    )
)
_RETURN_METHOD_VALUES_V2 = {
    "transform": "identity_signed",
    "return_unit": "percent_points",
    "location_estimator": "median",
    "scale_estimator": "median_absolute_deviation",
    "normal_consistency_factor": 1.482602218505602,
    "degenerate_mad_threshold": 1e-12,
    "derived_float_decimal_places": 12,
    "anchor_tolerance_ratio": 0.25,
    "minimum_anchor_tolerance_seconds": 300,
    "benchmark_alignment_tolerance_seconds": 300,
    "lower_tail_rank_definition": (
        "(count(baseline_return <= current_return)+1)/(sample_count+1)"
    ),
    "upper_tail_rank_definition": (
        "(count(baseline_return >= current_return)+1)/(sample_count+1)"
    ),
    "two_sided_tail_rank_definition": (
        "min(1,2*min(lower_tail_rank,upper_tail_rank))"
    ),
    "tail_ranks_are_p_values": False,
    "overlapping_samples_are_independent": False,
}
_RETURN_METHOD_VALUES_V3 = {
    **_RETURN_METHOD_VALUES_V2,
    "baseline_value_identity": (
        "derived_return_values_rounded_to_12_decimal_places"
    ),
    "minimum_distinct_baseline_value_count": None,
    "variation_diagnostics_are_policy": False,
}
_RETURN_METHOD_VALUES_V4 = {
    **_RETURN_METHOD_VALUES_V3,
    "source_value_tuple_identity": (
        "ordered_value_only_source_price_tuples_formatted_to_17_significant_digits"
    ),
    "input_trace_diagnostics_are_policy": False,
    "provider_causation_claimed": False,
}
_RETURN_METHOD_VALUES = {
    **_RETURN_METHOD_VALUES_V4,
    "return_sampling_trace_identity": (
        "ordered_exact_endpoint_anchor_observation_identity_and_timing"
    ),
    "return_sampling_timing_diagnostics_are_policy": False,
}
_RETURN_FEATURE_KEYS_V2 = frozenset(
    (
        "feature",
        "family",
        "horizon_hours",
        "benchmark",
        "status",
        "reason",
        "return_unit",
        "current_value",
        "current_sample",
        "feature_basis",
        "sample_count",
        "minimum_sample_count",
        "basis_ineligible_baseline_count",
        "invalid_baseline_count",
        "eligible_baseline_first_observation",
        "eligible_baseline_last_observation",
        "eligible_sample_sha256",
        "median",
        "mad",
        "normal_consistent_mad",
        "robust_z",
        "lower_tail_rank",
        "upper_tail_rank",
        "two_sided_tail_rank",
        "tail_ranks_are_p_values",
    )
)
_RETURN_FEATURE_KEYS_V3 = frozenset(
    (
        *_RETURN_FEATURE_KEYS_V2,
        "distinct_baseline_value_count",
        "maximum_baseline_value_tie_count",
        "current_value_baseline_tie_count",
        "distinct_baseline_value_ratio",
        "nominal_one_sided_tail_rank_floor",
        "nominal_two_sided_tail_rank_floor",
    )
)
_RETURN_FEATURE_KEYS_V4 = frozenset(
    (*_RETURN_FEATURE_KEYS_V3, *_INPUT_TRACE_KEYS)
)
_RETURN_FEATURE_KEYS = frozenset(
    (*_RETURN_FEATURE_KEYS_V4, "return_sampling_trace")
)
_RETURN_SAMPLE_KEYS = frozenset(
    ("asset_endpoint", "asset_anchor", "benchmark_endpoint", "benchmark_anchor")
)
_RETURN_SAMPLING_TRACE_KEYS = frozenset(
    (
        "status",
        "sample_count",
        "horizon_hours",
        "nominal_horizon_seconds",
        "sample_identity_sha256",
        "asset_leg",
        "benchmark_leg",
        "benchmark_endpoint_alignment",
        "anchor_reuse_detected",
        "benchmark_endpoint_reuse_detected",
        "nonzero_anchor_selection_error_detected",
        "nonzero_benchmark_alignment_lag_detected",
        "timing_diagnostics_are_policy",
        "provider_causation_claimed",
        "statistical_independence_claimed",
    )
)
_RETURN_SAMPLING_LEG_KEYS = frozenset(
    (
        "endpoint_observation_count",
        "distinct_endpoint_observation_count",
        "endpoint_reuse_excess_count",
        "maximum_endpoint_reuse_count",
        "maximum_consecutive_endpoint_reuse_count",
        "anchor_observation_count",
        "distinct_anchor_observation_count",
        "anchor_reuse_excess_count",
        "maximum_anchor_reuse_count",
        "maximum_consecutive_anchor_reuse_count",
        "realized_horizon_seconds",
        "anchor_selection_error_seconds",
        "maximum_endpoint_reuse_reference",
        "maximum_anchor_reuse_reference",
        "maximum_anchor_selection_error_reference",
    )
)
_RETURN_SAMPLING_RANGE_KEYS = frozenset(("minimum", "median", "maximum"))
_RETURN_SAMPLING_REUSE_REFERENCE_KEYS = frozenset(
    (
        "observation",
        "reuse_count",
        "first_asset_endpoint",
        "last_asset_endpoint",
    )
)
_RETURN_SAMPLING_ERROR_REFERENCE_KEYS = frozenset(
    (
        "asset_endpoint",
        "endpoint",
        "anchor",
        "realized_horizon_seconds",
        "anchor_selection_error_seconds",
    )
)
_RETURN_SAMPLING_ALIGNMENT_KEYS = frozenset(
    ("sample_count", "lag_seconds", "maximum_lag_reference")
)
_RETURN_SAMPLING_ALIGNMENT_REFERENCE_KEYS = frozenset(
    ("asset_endpoint", "benchmark_endpoint", "lag_seconds")
)
_RETURN_FEATURE_STATUSES = frozenset(
    (
        "ready",
        "not_applicable",
        "benchmark_unavailable",
        "basis_ineligible",
        "current_unavailable",
        "insufficient_history",
        "degenerate_scale",
        "unavailable",
    )
)
_RETURN_FEATURE_REASONS = frozenset(
    (
        "same_asset_benchmark_not_applicable",
        "benchmark_history_unavailable",
        "current_price_basis_not_eligible",
        "current_return_sample_unavailable",
        "minimum_sample_count_not_met",
        "mad_at_or_below_degenerate_threshold",
        "non_finite_robust_z",
    )
)
_RETURN_REASON_BY_STATUS = {
    "ready": None,
    "not_applicable": "same_asset_benchmark_not_applicable",
    "benchmark_unavailable": "benchmark_history_unavailable",
    "basis_ineligible": "current_price_basis_not_eligible",
    "current_unavailable": "current_return_sample_unavailable",
    "insufficient_history": "minimum_sample_count_not_met",
    "degenerate_scale": "mad_at_or_below_degenerate_threshold",
    "unavailable": "non_finite_robust_z",
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
    current_reference = value.get("current_observation")
    outer_observation_id = row.get("market_history_observation_id")
    if (
        outer_observation_id not in (None, "")
        and isinstance(current_reference, Mapping)
        and current_reference.get("observation_id") != outer_observation_id
    ):
        errors.append(
            "shadow_temporal_surprise_reference_inconsistent:outer_market_history_observation_id"
        )
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
    schema_version = value.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version not in {*LEGACY_SCHEMA_VERSIONS, SCHEMA_VERSION}
    ):
        return [
            "shadow_temporal_surprise_fixed_value_mismatch:value.schema_version"
        ]
    expected_keys = (
        _TOP_LEVEL_KEYS_V1
        if schema_version == 1
        else _TOP_LEVEL_KEYS
    )
    errors = _closed_keys(value, expected_keys, "value")
    if errors:
        return errors

    _expect_exact(value, "schema_id", SCHEMA_ID, "value", errors)
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
    _validate_method(value.get("method"), schema_version=schema_version, errors=errors)
    _validate_features(value.get("features"), schema_version=schema_version, errors=errors)
    if schema_version >= 2:
        _expect_enum(value, "return_status", _TOP_LEVEL_STATUSES, "value", errors)
        _validate_return_method(
            value.get("return_method"),
            schema_version=schema_version,
            errors=errors,
        )
        _validate_return_features(
            value.get("return_features"),
            schema_version=schema_version,
            errors=errors,
        )
    _validate_cross_field_consistency(
        value,
        schema_version=schema_version,
        errors=errors,
    )
    return errors


def _validate_method(
    value: object,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:method:dict")
        return
    expected_keys = (
        _METHOD_KEYS
        if schema_version >= 4
        else _METHOD_KEYS_V3
        if schema_version == 3
        else _METHOD_KEYS_V1_V2
    )
    expected_values = (
        _METHOD_VALUES
        if schema_version >= 4
        else _METHOD_VALUES_V3
        if schema_version == 3
        else _METHOD_VALUES_V1_V2
    )
    key_errors = _closed_keys(value, expected_keys, "method")
    errors.extend(key_errors)
    if key_errors:
        return
    for field, expected in expected_values.items():
        _expect_exact(value, field, expected, "method", errors)


def _validate_return_method(
    value: object,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:return_method:dict")
        return
    expected_keys = (
        _RETURN_METHOD_KEYS
        if schema_version >= 5
        else _RETURN_METHOD_KEYS_V4
        if schema_version == 4
        else _RETURN_METHOD_KEYS_V3
        if schema_version == 3
        else _RETURN_METHOD_KEYS_V2
    )
    expected_values = (
        _RETURN_METHOD_VALUES
        if schema_version >= 5
        else _RETURN_METHOD_VALUES_V4
        if schema_version == 4
        else _RETURN_METHOD_VALUES_V3
        if schema_version == 3
        else _RETURN_METHOD_VALUES_V2
    )
    key_errors = _closed_keys(value, expected_keys, "return_method")
    errors.extend(key_errors)
    if key_errors:
        return
    for field, expected in expected_values.items():
        _expect_exact(value, field, expected, "return_method", errors)


def _validate_features(
    value: object,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:features:dict")
        return
    key_errors = _closed_keys(value, frozenset(FEATURES), "features")
    errors.extend(key_errors)
    if key_errors:
        return
    for feature in FEATURES:
        _validate_feature(
            value.get(feature),
            feature,
            schema_version=schema_version,
            errors=errors,
        )


def _validate_feature(
    value: object,
    feature: str,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    path = f"features.{feature}"
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    expected_keys = (
        _FEATURE_KEYS
        if schema_version >= 4
        else _FEATURE_KEYS_V3
        if schema_version == 3
        else _FEATURE_KEYS_V1_V2
    )
    key_errors = _closed_keys(value, expected_keys, path)
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
    if schema_version >= 3:
        _validate_variation_diagnostics(
            value,
            path=path,
            current_value_present=value.get("current_log") is not None,
            include_two_sided=False,
            errors=errors,
        )
    if schema_version >= 4:
        _validate_input_trace(
            value,
            path=path,
            expected_tuple_kind=(
                "provider_volume_value"
                if feature == "volume_24h"
                else "turnover_source_component_tuple"
            ),
            errors=errors,
        )
def _validate_return_features(
    value: object,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append("shadow_temporal_surprise_invalid_type:return_features:dict")
        return
    key_errors = _closed_keys(
        value,
        frozenset(RETURN_FEATURES),
        "return_features",
    )
    errors.extend(key_errors)
    if key_errors:
        return
    for feature in RETURN_FEATURES:
        _validate_return_feature(
            value.get(feature),
            feature,
            schema_version=schema_version,
            errors=errors,
        )


def _validate_return_feature(
    value: object,
    feature: str,
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    path = f"return_features.{feature}"
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    expected_keys = (
        _RETURN_FEATURE_KEYS
        if schema_version >= 5
        else _RETURN_FEATURE_KEYS_V4
        if schema_version == 4
        else _RETURN_FEATURE_KEYS_V3
        if schema_version == 3
        else _RETURN_FEATURE_KEYS_V2
    )
    key_errors = _closed_keys(value, expected_keys, path)
    errors.extend(key_errors)
    if key_errors:
        return
    family, horizon, benchmark = _return_feature_spec(feature)
    _expect_exact(value, "feature", feature, path, errors)
    _expect_exact(value, "family", family, path, errors)
    _expect_exact(value, "horizon_hours", horizon, path, errors)
    if benchmark is None:
        if value.get("benchmark") is not None:
            errors.append(
                f"shadow_temporal_surprise_fixed_value_mismatch:{path}.benchmark"
            )
    else:
        _expect_exact(value, "benchmark", benchmark, path, errors)
    _expect_enum(value, "status", _RETURN_FEATURE_STATUSES, path, errors)
    reason = value.get("reason")
    if reason is not None and (
        not isinstance(reason, str) or reason not in _RETURN_FEATURE_REASONS
    ):
        errors.append(f"shadow_temporal_surprise_invalid_enum:{path}.reason")
    _expect_exact(value, "return_unit", "percent_points", path, errors)
    basis = value.get("feature_basis")
    if basis is not None and (not isinstance(basis, str) or not basis.strip()):
        errors.append(
            f"shadow_temporal_surprise_invalid_type:{path}.feature_basis:str_or_null"
        )
    for field in (
        "current_value",
        "median",
        "mad",
        "normal_consistent_mad",
        "robust_z",
        "lower_tail_rank",
        "upper_tail_rank",
        "two_sided_tail_rank",
    ):
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
    if not _is_sha256(value.get("eligible_sample_sha256")):
        errors.append(
            f"shadow_temporal_surprise_invalid_type:{path}.eligible_sample_sha256:sha256"
        )
    _validate_return_sample(
        value.get("current_sample"),
        path=f"{path}.current_sample",
        benchmark=benchmark,
        errors=errors,
    )
    _expect_exact(value, "tail_ranks_are_p_values", False, path, errors)
    if schema_version >= 3:
        _validate_variation_diagnostics(
            value,
            path=path,
            current_value_present=value.get("current_sample") is not None,
            include_two_sided=True,
            errors=errors,
        )
    if schema_version >= 4:
        _validate_input_trace(
            value,
            path=path,
            expected_tuple_kind=(
                "asset_endpoint_anchor_price_tuple"
                if benchmark is None
                else "asset_benchmark_endpoint_anchor_price_tuple"
            ),
            errors=errors,
        )
    if schema_version >= 5:
        _validate_return_sampling_trace(
            value.get("return_sampling_trace"),
            path=f"{path}.return_sampling_trace",
            horizon_hours=horizon,
            benchmark=benchmark,
            feature_sample_count=value.get("sample_count"),
            errors=errors,
        )


def _validate_return_sample(
    value: object,
    *,
    path: str,
    benchmark: str | None,
    errors: list[str],
) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict_or_null")
        return
    key_errors = _closed_keys(value, _RETURN_SAMPLE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return
    _validate_reference(value.get("asset_endpoint"), f"{path}.asset_endpoint", errors)
    _validate_reference(value.get("asset_anchor"), f"{path}.asset_anchor", errors)
    for field in ("benchmark_endpoint", "benchmark_anchor"):
        item = value.get(field)
        if benchmark is None:
            if item is not None:
                errors.append(
                    f"shadow_temporal_surprise_reference_inconsistent:{path}.{field}"
                )
        else:
            _validate_reference(item, f"{path}.{field}", errors)


def _validate_return_sampling_trace(
    value: object,
    *,
    path: str,
    horizon_hours: int,
    benchmark: str | None,
    feature_sample_count: object,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    key_errors = _closed_keys(value, _RETURN_SAMPLING_TRACE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return
    sample_count = value.get("sample_count")
    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
        or sample_count < 0
        or sample_count != feature_sample_count
    ):
        errors.append(f"shadow_temporal_surprise_sampling_count_inconsistent:{path}")
        return
    expected_status = "observed" if sample_count else "no_samples"
    if value.get("status") != expected_status:
        errors.append(f"shadow_temporal_surprise_sampling_status_inconsistent:{path}")
    if value.get("horizon_hours") != horizon_hours:
        errors.append(f"shadow_temporal_surprise_sampling_horizon_inconsistent:{path}")
    nominal_seconds = horizon_hours * 3600
    if value.get("nominal_horizon_seconds") != nominal_seconds:
        errors.append(f"shadow_temporal_surprise_sampling_nominal_inconsistent:{path}")
    if not _is_sha256(value.get("sample_identity_sha256")):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}.sample_identity_sha256:sha256")
    for field in (
        "timing_diagnostics_are_policy",
        "provider_causation_claimed",
        "statistical_independence_claimed",
    ):
        if value.get(field) is not False:
            errors.append(f"shadow_temporal_surprise_sampling_safety_inconsistent:{path}.{field}")

    tolerance_seconds = max(
        RETURN_MIN_ANCHOR_TOLERANCE_SECONDS,
        nominal_seconds * RETURN_ANCHOR_TOLERANCE_RATIO,
    )
    asset_metrics = _validate_return_sampling_leg(
        value.get("asset_leg"),
        path=f"{path}.asset_leg",
        sample_count=sample_count,
        nominal_horizon_seconds=nominal_seconds,
        tolerance_seconds=tolerance_seconds,
        errors=errors,
    )
    benchmark_metrics = None
    alignment_metrics = None
    if benchmark is None:
        if value.get("benchmark_leg") is not None:
            errors.append(f"shadow_temporal_surprise_sampling_benchmark_inconsistent:{path}.benchmark_leg")
        if value.get("benchmark_endpoint_alignment") is not None:
            errors.append(f"shadow_temporal_surprise_sampling_benchmark_inconsistent:{path}.benchmark_endpoint_alignment")
    else:
        benchmark_metrics = _validate_return_sampling_leg(
            value.get("benchmark_leg"),
            path=f"{path}.benchmark_leg",
            sample_count=sample_count,
            nominal_horizon_seconds=nominal_seconds,
            tolerance_seconds=tolerance_seconds,
            errors=errors,
        )
        alignment_metrics = _validate_return_sampling_alignment(
            value.get("benchmark_endpoint_alignment"),
            path=f"{path}.benchmark_endpoint_alignment",
            sample_count=sample_count,
            errors=errors,
        )
    leg_metrics = tuple(
        item for item in (asset_metrics, benchmark_metrics) if item is not None
    )
    expected_anchor_reuse = any(item["anchor_reuse"] for item in leg_metrics)
    expected_error = any(item["nonzero_error"] for item in leg_metrics)
    expected_endpoint_reuse = bool(
        benchmark_metrics and benchmark_metrics["endpoint_reuse"]
    )
    expected_alignment_lag = bool(
        alignment_metrics and alignment_metrics["nonzero_lag"]
    )
    for field, expected in (
        ("anchor_reuse_detected", expected_anchor_reuse),
        ("benchmark_endpoint_reuse_detected", expected_endpoint_reuse),
        ("nonzero_anchor_selection_error_detected", expected_error),
        ("nonzero_benchmark_alignment_lag_detected", expected_alignment_lag),
    ):
        if value.get(field) is not expected:
            errors.append(f"shadow_temporal_surprise_sampling_flag_inconsistent:{path}.{field}")


def _validate_return_sampling_leg(
    value: object,
    *,
    path: str,
    sample_count: int,
    nominal_horizon_seconds: int,
    tolerance_seconds: float,
    errors: list[str],
) -> dict[str, bool] | None:
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return None
    key_errors = _closed_keys(value, _RETURN_SAMPLING_LEG_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return None
    count_fields = (
        "endpoint_observation_count",
        "distinct_endpoint_observation_count",
        "endpoint_reuse_excess_count",
        "maximum_endpoint_reuse_count",
        "maximum_consecutive_endpoint_reuse_count",
        "anchor_observation_count",
        "distinct_anchor_observation_count",
        "anchor_reuse_excess_count",
        "maximum_anchor_reuse_count",
        "maximum_consecutive_anchor_reuse_count",
    )
    counts = {field: value.get(field) for field in count_fields}
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in counts.values()
    ):
        errors.append(f"shadow_temporal_surprise_sampling_counts_invalid:{path}")
        return None
    if (
        counts["endpoint_observation_count"] != sample_count
        or counts["anchor_observation_count"] != sample_count
    ):
        errors.append(f"shadow_temporal_surprise_sampling_counts_inconsistent:{path}")
    _validate_sampling_reuse_counts(
        sample_count=sample_count,
        distinct_count=counts["distinct_endpoint_observation_count"],
        reuse_excess=counts["endpoint_reuse_excess_count"],
        maximum_reuse=counts["maximum_endpoint_reuse_count"],
        maximum_consecutive=counts["maximum_consecutive_endpoint_reuse_count"],
        path=f"{path}.endpoint",
        errors=errors,
    )
    _validate_sampling_reuse_counts(
        sample_count=sample_count,
        distinct_count=counts["distinct_anchor_observation_count"],
        reuse_excess=counts["anchor_reuse_excess_count"],
        maximum_reuse=counts["maximum_anchor_reuse_count"],
        maximum_consecutive=counts["maximum_consecutive_anchor_reuse_count"],
        path=f"{path}.anchor",
        errors=errors,
    )
    realized = _validate_sampling_range(
        value.get("realized_horizon_seconds"),
        path=f"{path}.realized_horizon_seconds",
        sample_count=sample_count,
        minimum=nominal_horizon_seconds,
        maximum=nominal_horizon_seconds + tolerance_seconds,
        errors=errors,
    )
    selection_error = _validate_sampling_range(
        value.get("anchor_selection_error_seconds"),
        path=f"{path}.anchor_selection_error_seconds",
        sample_count=sample_count,
        minimum=0.0,
        maximum=tolerance_seconds,
        errors=errors,
    )
    if realized and selection_error and any(
        not math.isclose(
            realized[field] - nominal_horizon_seconds,
            selection_error[field],
            abs_tol=1e-6,
        )
        for field in _RETURN_SAMPLING_RANGE_KEYS
    ):
        errors.append(f"shadow_temporal_surprise_sampling_error_range_inconsistent:{path}")
    _validate_sampling_reuse_reference(
        value.get("maximum_endpoint_reuse_reference"),
        path=f"{path}.maximum_endpoint_reuse_reference",
        sample_count=sample_count,
        expected_reuse_count=counts["maximum_endpoint_reuse_count"],
        errors=errors,
    )
    _validate_sampling_reuse_reference(
        value.get("maximum_anchor_reuse_reference"),
        path=f"{path}.maximum_anchor_reuse_reference",
        sample_count=sample_count,
        expected_reuse_count=counts["maximum_anchor_reuse_count"],
        errors=errors,
    )
    _validate_sampling_error_reference(
        value.get("maximum_anchor_selection_error_reference"),
        path=f"{path}.maximum_anchor_selection_error_reference",
        sample_count=sample_count,
        nominal_horizon_seconds=nominal_horizon_seconds,
        expected_maximum=(selection_error or {}).get("maximum"),
        errors=errors,
    )
    return {
        "endpoint_reuse": counts["endpoint_reuse_excess_count"] > 0,
        "anchor_reuse": counts["anchor_reuse_excess_count"] > 0,
        "nonzero_error": bool(
            selection_error and selection_error["maximum"] > 0
        ),
    }


def _validate_sampling_reuse_counts(
    *,
    sample_count: int,
    distinct_count: int,
    reuse_excess: int,
    maximum_reuse: int,
    maximum_consecutive: int,
    path: str,
    errors: list[str],
) -> None:
    if sample_count == 0:
        if any((distinct_count, reuse_excess, maximum_reuse, maximum_consecutive)):
            errors.append(f"shadow_temporal_surprise_sampling_empty_counts_invalid:{path}")
        return
    if not 1 <= distinct_count <= sample_count:
        errors.append(f"shadow_temporal_surprise_sampling_distinct_count_invalid:{path}")
        return
    if reuse_excess != sample_count - distinct_count:
        errors.append(f"shadow_temporal_surprise_sampling_reuse_excess_invalid:{path}")
    if not (
        math.ceil(sample_count / distinct_count)
        <= maximum_reuse
        <= sample_count - distinct_count + 1
    ):
        errors.append(f"shadow_temporal_surprise_sampling_maximum_reuse_invalid:{path}")
    if not 1 <= maximum_consecutive <= maximum_reuse:
        errors.append(f"shadow_temporal_surprise_sampling_consecutive_reuse_invalid:{path}")


def _validate_sampling_range(
    value: object,
    *,
    path: str,
    sample_count: int,
    minimum: float,
    maximum: float,
    errors: list[str],
) -> dict[str, float] | None:
    if sample_count == 0:
        if value is not None:
            errors.append(f"shadow_temporal_surprise_sampling_empty_range_invalid:{path}")
        return None
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return None
    key_errors = _closed_keys(value, _RETURN_SAMPLING_RANGE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return None
    values = {field: value.get(field) for field in _RETURN_SAMPLING_RANGE_KEYS}
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(float(item))
        for item in values.values()
    ):
        errors.append(f"shadow_temporal_surprise_sampling_range_invalid:{path}")
        return None
    result = {field: float(item) for field, item in values.items()}
    if not (
        minimum - 1e-6
        <= result["minimum"]
        <= result["median"]
        <= result["maximum"]
        <= maximum + 1e-6
    ):
        errors.append(f"shadow_temporal_surprise_sampling_range_out_of_bounds:{path}")
    return result


def _validate_sampling_reuse_reference(
    value: object,
    *,
    path: str,
    sample_count: int,
    expected_reuse_count: int,
    errors: list[str],
) -> None:
    if sample_count == 0:
        if value is not None:
            errors.append(f"shadow_temporal_surprise_sampling_empty_reference_invalid:{path}")
        return
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    key_errors = _closed_keys(value, _RETURN_SAMPLING_REUSE_REFERENCE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return
    for field in ("observation", "first_asset_endpoint", "last_asset_endpoint"):
        _validate_reference(value.get(field), f"{path}.{field}", errors)
    if value.get("reuse_count") != expected_reuse_count:
        errors.append(f"shadow_temporal_surprise_sampling_reuse_reference_count_invalid:{path}")
    first = _reference_time(value.get("first_asset_endpoint"))
    last = _reference_time(value.get("last_asset_endpoint"))
    if first is not None and last is not None and first > last:
        errors.append(f"shadow_temporal_surprise_sampling_reuse_reference_order_invalid:{path}")


def _validate_sampling_error_reference(
    value: object,
    *,
    path: str,
    sample_count: int,
    nominal_horizon_seconds: int,
    expected_maximum: float | None,
    errors: list[str],
) -> None:
    if sample_count == 0:
        if value is not None:
            errors.append(f"shadow_temporal_surprise_sampling_empty_reference_invalid:{path}")
        return
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return
    key_errors = _closed_keys(value, _RETURN_SAMPLING_ERROR_REFERENCE_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return
    for field in ("asset_endpoint", "endpoint", "anchor"):
        _validate_reference(value.get(field), f"{path}.{field}", errors)
    endpoint = _reference_time(value.get("endpoint"))
    anchor = _reference_time(value.get("anchor"))
    realized = value.get("realized_horizon_seconds")
    selection_error = value.get("anchor_selection_error_seconds")
    if (
        endpoint is None
        or anchor is None
        or not _sampling_number(realized)
        or not _sampling_number(selection_error)
    ):
        return
    expected_realized = round((endpoint - anchor).total_seconds(), 6)
    if not math.isclose(float(realized), expected_realized, abs_tol=1e-6):
        errors.append(f"shadow_temporal_surprise_sampling_reference_realized_invalid:{path}")
    if not math.isclose(
        float(selection_error),
        expected_realized - nominal_horizon_seconds,
        abs_tol=1e-6,
    ):
        errors.append(f"shadow_temporal_surprise_sampling_reference_error_invalid:{path}")
    if expected_maximum is not None and not math.isclose(
        float(selection_error), expected_maximum, abs_tol=1e-6
    ):
        errors.append(f"shadow_temporal_surprise_sampling_reference_not_maximum:{path}")


def _validate_return_sampling_alignment(
    value: object,
    *,
    path: str,
    sample_count: int,
    errors: list[str],
) -> dict[str, bool] | None:
    if not isinstance(value, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}:dict")
        return None
    key_errors = _closed_keys(value, _RETURN_SAMPLING_ALIGNMENT_KEYS, path)
    errors.extend(key_errors)
    if key_errors:
        return None
    if value.get("sample_count") != sample_count:
        errors.append(f"shadow_temporal_surprise_sampling_alignment_count_invalid:{path}")
    lag = _validate_sampling_range(
        value.get("lag_seconds"),
        path=f"{path}.lag_seconds",
        sample_count=sample_count,
        minimum=0.0,
        maximum=BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS,
        errors=errors,
    )
    reference = value.get("maximum_lag_reference")
    if sample_count == 0:
        if reference is not None:
            errors.append(f"shadow_temporal_surprise_sampling_empty_reference_invalid:{path}.maximum_lag_reference")
    elif not isinstance(reference, Mapping):
        errors.append(f"shadow_temporal_surprise_invalid_type:{path}.maximum_lag_reference:dict")
    else:
        reference_path = f"{path}.maximum_lag_reference"
        key_errors = _closed_keys(
            reference,
            _RETURN_SAMPLING_ALIGNMENT_REFERENCE_KEYS,
            reference_path,
        )
        errors.extend(key_errors)
        if not key_errors:
            _validate_reference(reference.get("asset_endpoint"), f"{reference_path}.asset_endpoint", errors)
            _validate_reference(reference.get("benchmark_endpoint"), f"{reference_path}.benchmark_endpoint", errors)
            asset_at = _reference_time(reference.get("asset_endpoint"))
            benchmark_at = _reference_time(reference.get("benchmark_endpoint"))
            reference_lag = reference.get("lag_seconds")
            if asset_at is not None and benchmark_at is not None and _sampling_number(reference_lag):
                expected = round((asset_at - benchmark_at).total_seconds(), 6)
                if not math.isclose(float(reference_lag), expected, abs_tol=1e-6):
                    errors.append(f"shadow_temporal_surprise_sampling_alignment_reference_invalid:{reference_path}")
                if lag and not math.isclose(float(reference_lag), lag["maximum"], abs_tol=1e-6):
                    errors.append(f"shadow_temporal_surprise_sampling_alignment_reference_not_maximum:{reference_path}")
    return {"nonzero_lag": bool(lag and lag["maximum"] > 0)}


def _sampling_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _return_feature_spec(feature: str) -> tuple[str, int, str | None]:
    if feature.startswith("return_"):
        hours = int(feature.removeprefix("return_").removesuffix("h"))
        return "direct_return", hours, None
    for benchmark in RETURN_BENCHMARKS:
        prefix = f"relative_return_vs_{benchmark}_"
        if feature.startswith(prefix):
            hours = int(feature.removeprefix(prefix).removesuffix("h"))
            return f"relative_return_{benchmark}", hours, benchmark
    raise AssertionError(f"unknown shadow return feature: {feature}")


def _validate_cross_field_consistency(
    value: Mapping[str, Any],
    *,
    schema_version: int,
    errors: list[str],
) -> None:
    features = value.get("features")
    if not isinstance(features, Mapping) or frozenset(features) != frozenset(FEATURES):
        return
    supplied = value.get("supplied_prior_observation_count")
    minimum = value.get("minimum_sample_count")
    magnitude_values = [
        features[feature]
        for feature in FEATURES
        if isinstance(features.get(feature), Mapping)
    ]
    status_values = list(magnitude_values)
    if schema_version >= 2:
        return_features = value.get("return_features")
        if (
            isinstance(return_features, Mapping)
            and frozenset(return_features) == frozenset(RETURN_FEATURES)
        ):
            return_values = [
                return_features[feature]
                for feature in RETURN_FEATURES
                if isinstance(return_features.get(feature), Mapping)
            ]
            applicable_return_values = [
                item
                for item in return_values
                if item.get("status") != "not_applicable"
            ]
            expected_return_status = _collection_status(applicable_return_values)
            if value.get("return_status") != expected_return_status:
                errors.append(
                    "shadow_temporal_surprise_status_inconsistent:value.return_status"
                )
            status_values.extend(applicable_return_values)
            for feature in RETURN_FEATURES:
                feature_value = return_features.get(feature)
                if (
                    isinstance(feature_value, Mapping)
                    and frozenset(feature_value) == (
                        _RETURN_FEATURE_KEYS
                        if schema_version >= 5
                        else _RETURN_FEATURE_KEYS_V4
                        if schema_version == 4
                        else _RETURN_FEATURE_KEYS_V3
                        if schema_version == 3
                        else _RETURN_FEATURE_KEYS_V2
                    )
                ):
                    _validate_return_feature_consistency(
                        feature_value,
                        feature=feature,
                        supplied=supplied,
                        top_level_minimum=minimum,
                        current_reference=value.get("current_observation"),
                        errors=errors,
                    )
    expected_status = _collection_status(status_values)
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
        expected_feature_keys = (
            _FEATURE_KEYS
            if schema_version >= 4
            else _FEATURE_KEYS_V3
            if schema_version == 3
            else _FEATURE_KEYS_V1_V2
        )
        if (
            not isinstance(feature_value, Mapping)
            or frozenset(feature_value) != expected_feature_keys
        ):
            continue
        _validate_feature_consistency(
            feature_value,
            feature=feature,
            supplied=supplied,
            top_level_minimum=minimum,
            errors=errors,
        )


def _collection_status(values: list[Mapping[str, Any]]) -> str:
    ready_count = sum(value.get("status") == "ready" for value in values)
    if values and ready_count == len(values):
        return "ready"
    if ready_count:
        return "partial"
    return "unavailable"


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


def _validate_return_feature_consistency(
    value: Mapping[str, Any],
    *,
    feature: str,
    supplied: object,
    top_level_minimum: object,
    current_reference: object,
    errors: list[str],
) -> None:
    path = f"return_features.{feature}"
    status = value.get("status")
    if (
        status in _RETURN_REASON_BY_STATUS
        and value.get("reason") != _RETURN_REASON_BY_STATUS[status]
    ):
        errors.append(f"shadow_temporal_surprise_reason_inconsistent:{path}")
    if value.get("minimum_sample_count") != top_level_minimum:
        errors.append(f"shadow_temporal_surprise_minimum_inconsistent:{path}")
    sample_count = value.get("sample_count")
    minimum = value.get("minimum_sample_count")
    if (
        isinstance(sample_count, int)
        and not isinstance(sample_count, bool)
        and isinstance(minimum, int)
        and not isinstance(minimum, bool)
    ):
        if status in {"ready", "degenerate_scale", "unavailable"} and (
            sample_count < minimum
        ):
            errors.append(f"shadow_temporal_surprise_sample_status_mismatch:{path}")
        if status == "insufficient_history" and sample_count >= minimum:
            errors.append(f"shadow_temporal_surprise_sample_status_mismatch:{path}")
    counts = (
        value.get("sample_count"),
        value.get("basis_ineligible_baseline_count"),
        value.get("invalid_baseline_count"),
    )
    if (
        status != "not_applicable"
        and isinstance(supplied, int)
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
    family, hours, benchmark = _return_feature_spec(feature)
    expected_basis = (
        "provider_observed_price_ratio"
        if family == "direct_return"
        else (
            "provider_observed_asset_return_minus_provider_observed_"
            "benchmark_return"
        )
    )
    derived_statuses = {
        "ready", "insufficient_history", "degenerate_scale", "unavailable"
    }
    if status in derived_statuses and value.get("feature_basis") != expected_basis:
        errors.append(f"shadow_temporal_surprise_basis_inconsistent:{path}")
    required_statistics = {
        "ready": {
            "current_value", "current_sample", "feature_basis", "median", "mad",
            "normal_consistent_mad", "robust_z", "lower_tail_rank",
            "upper_tail_rank", "two_sided_tail_rank",
        },
        "degenerate_scale": {
            "current_value", "current_sample", "feature_basis", "median", "mad",
            "normal_consistent_mad", "lower_tail_rank", "upper_tail_rank",
            "two_sided_tail_rank",
        },
        "unavailable": {
            "current_value", "current_sample", "feature_basis", "median", "mad",
            "normal_consistent_mad", "lower_tail_rank", "upper_tail_rank",
            "two_sided_tail_rank",
        },
        "insufficient_history": {
            "current_value", "current_sample", "feature_basis",
        },
    }.get(status, set())
    nullable_fields = (
        "current_value", "current_sample", "feature_basis", "median", "mad",
        "normal_consistent_mad", "robust_z", "lower_tail_rank",
        "upper_tail_rank", "two_sided_tail_rank",
    )
    for field in nullable_fields:
        should_exist = field in required_statistics
        if should_exist != (value.get(field) is not None):
            errors.append(
                f"shadow_temporal_surprise_statistic_inconsistent:{path}.{field}"
            )
    for field in ("lower_tail_rank", "upper_tail_rank", "two_sided_tail_rank"):
        tail = value.get(field)
        if (
            _is_finite_number_or_none(tail)
            and tail is not None
            and not 0 <= float(tail) <= 1
        ):
            errors.append(
                f"shadow_temporal_surprise_tail_out_of_range:{path}.{field}"
            )
    mad = value.get("mad")
    consistent_mad = value.get("normal_consistent_mad")
    if _is_finite_number_or_none(mad) and mad is not None and float(mad) < 0:
        errors.append(f"shadow_temporal_surprise_scale_inconsistent:{path}.mad")
    if (
        _is_finite_number_or_none(consistent_mad)
        and consistent_mad is not None
        and float(consistent_mad) < 0
    ):
        errors.append(
            f"shadow_temporal_surprise_scale_inconsistent:{path}.normal_consistent_mad"
        )
    if (
        _is_finite_number_or_none(mad)
        and mad is not None
        and _is_finite_number_or_none(consistent_mad)
        and consistent_mad is not None
        and not math.isclose(
            float(consistent_mad),
            float(mad) * _RETURN_METHOD_VALUES["normal_consistency_factor"],
            rel_tol=1e-10,
            abs_tol=2e-12,
        )
    ):
        errors.append(
            f"shadow_temporal_surprise_scale_inconsistent:{path}.normal_consistent_mad"
        )
    lower_tail = value.get("lower_tail_rank")
    upper_tail = value.get("upper_tail_rank")
    two_sided_tail = value.get("two_sided_tail_rank")
    if all(
        _is_finite_number_or_none(item) and item is not None
        for item in (lower_tail, upper_tail, two_sided_tail)
    ):
        expected_two_sided = min(
            1.0,
            2.0 * min(float(lower_tail), float(upper_tail)),
        )
        if not math.isclose(
            float(two_sided_tail),
            expected_two_sided,
            rel_tol=1e-10,
            abs_tol=2e-12,
        ):
            errors.append(
                f"shadow_temporal_surprise_tail_inconsistent:{path}.two_sided_tail_rank"
            )
    current_value = value.get("current_value")
    median = value.get("median")
    robust_z = value.get("robust_z")
    if all(
        _is_finite_number_or_none(item) and item is not None
        for item in (current_value, median, consistent_mad, robust_z)
    ) and float(consistent_mad) > 0:
        expected_robust_z = (
            float(current_value) - float(median)
        ) / float(consistent_mad)
        if not math.isclose(
            float(robust_z),
            expected_robust_z,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            errors.append(
                f"shadow_temporal_surprise_statistic_inconsistent:{path}.robust_z"
            )
    sample = value.get("current_sample")
    if isinstance(sample, Mapping) and frozenset(sample) == _RETURN_SAMPLE_KEYS:
        _validate_return_sample_clocks(
            sample,
            path=path,
            benchmark=benchmark,
            horizon_hours=hours,
            current_reference=current_reference,
            errors=errors,
        )


def _validate_variation_diagnostics(
    value: Mapping[str, Any],
    *,
    path: str,
    current_value_present: bool,
    include_two_sided: bool,
    errors: list[str],
) -> None:
    count_fields = (
        "distinct_baseline_value_count",
        "maximum_baseline_value_tie_count",
    )
    for field in count_fields:
        _expect_nonnegative_int(value, field, path, errors)

    current_ties = value.get("current_value_baseline_tie_count")
    if current_value_present:
        if not _is_nonnegative_int(current_ties):
            errors.append(
                "shadow_temporal_surprise_invalid_type:"
                f"{path}.current_value_baseline_tie_count:nonnegative_int"
            )
    elif current_ties is not None:
        errors.append(
            "shadow_temporal_surprise_variation_inconsistent:"
            f"{path}.current_value_baseline_tie_count"
        )

    numeric_fields = [
        "distinct_baseline_value_ratio",
        "nominal_one_sided_tail_rank_floor",
    ]
    if include_two_sided:
        numeric_fields.append("nominal_two_sided_tail_rank_floor")
    for field in numeric_fields:
        if not _is_finite_number_or_none(value.get(field)):
            errors.append(
                "shadow_temporal_surprise_invalid_type:"
                f"{path}.{field}:finite_number_or_null"
            )

    sample_count = value.get("sample_count")
    distinct_count = value.get("distinct_baseline_value_count")
    maximum_ties = value.get("maximum_baseline_value_tie_count")
    if not all(
        _is_nonnegative_int(item)
        for item in (sample_count, distinct_count, maximum_ties)
    ):
        return

    expected_ratio: float | None = None
    expected_one_sided: float | None = None
    expected_two_sided: float | None = None
    if sample_count == 0:
        if distinct_count != 0:
            _append_variation_error(
                errors,
                path,
                "distinct_baseline_value_count",
            )
        if maximum_ties != 0:
            _append_variation_error(
                errors,
                path,
                "maximum_baseline_value_tie_count",
            )
    else:
        if not 1 <= distinct_count <= sample_count:
            _append_variation_error(
                errors,
                path,
                "distinct_baseline_value_count",
            )
        elif not (
            math.ceil(sample_count / distinct_count)
            <= maximum_ties
            <= sample_count - distinct_count + 1
        ):
            _append_variation_error(
                errors,
                path,
                "maximum_baseline_value_tie_count",
            )
        expected_ratio = distinct_count / sample_count
        expected_one_sided = 1.0 / (sample_count + 1)
        expected_two_sided = min(1.0, 2.0 / (sample_count + 1))

    if _is_nonnegative_int(current_ties) and current_ties > maximum_ties:
        _append_variation_error(
            errors,
            path,
            "current_value_baseline_tie_count",
        )
    _expect_optional_close(
        value.get("distinct_baseline_value_ratio"),
        expected_ratio,
        path=path,
        field="distinct_baseline_value_ratio",
        errors=errors,
    )
    _expect_optional_close(
        value.get("nominal_one_sided_tail_rank_floor"),
        expected_one_sided,
        path=path,
        field="nominal_one_sided_tail_rank_floor",
        errors=errors,
    )
    if include_two_sided:
        _expect_optional_close(
            value.get("nominal_two_sided_tail_rank_floor"),
            expected_two_sided,
            path=path,
            field="nominal_two_sided_tail_rank_floor",
            errors=errors,
        )


def _validate_input_trace(
    value: Mapping[str, Any],
    *,
    path: str,
    expected_tuple_kind: str,
    errors: list[str],
) -> None:
    _expect_exact(
        value,
        "source_value_tuple_kind",
        expected_tuple_kind,
        path,
        errors,
    )
    count_fields = (
        "source_value_tuple_count",
        "distinct_source_value_tuple_count",
        "maximum_source_value_tuple_tie_count",
        "source_value_tuple_repeat_excess_count",
        "derived_value_repeat_excess_count",
        "transform_collision_distinct_value_loss_count",
        "maximum_consecutive_source_value_tuple_count",
        "maximum_consecutive_derived_value_count",
    )
    for field in count_fields:
        _expect_nonnegative_int(value, field, path, errors)
    if not _is_sha256(value.get("source_value_tuple_sha256")):
        errors.append(
            "shadow_temporal_surprise_invalid_type:"
            f"{path}.source_value_tuple_sha256:sha256"
        )
    _expect_enum(
        value,
        "input_trace_status",
        frozenset((
            "no_samples",
            "all_distinct",
            "source_tuple_repetition",
            "transform_collision",
            "mixed_source_repetition_and_transform_collision",
        )),
        path,
        errors,
    )
    _expect_exact(
        value,
        "input_trace_diagnostics_are_policy",
        False,
        path,
        errors,
    )
    _expect_exact(
        value,
        "provider_causation_claimed",
        False,
        path,
        errors,
    )

    fields = (
        "sample_count",
        "distinct_baseline_value_count",
        "maximum_baseline_value_tie_count",
        *count_fields,
    )
    if not all(_is_nonnegative_int(value.get(field)) for field in fields):
        return
    sample_count = int(value["sample_count"])
    derived_distinct = int(value["distinct_baseline_value_count"])
    derived_maximum_tie = int(value["maximum_baseline_value_tie_count"])
    source_count = int(value["source_value_tuple_count"])
    source_distinct = int(value["distinct_source_value_tuple_count"])
    source_maximum_tie = int(value["maximum_source_value_tuple_tie_count"])
    source_repeat_excess = int(value["source_value_tuple_repeat_excess_count"])
    derived_repeat_excess = int(value["derived_value_repeat_excess_count"])
    collision_loss = int(
        value["transform_collision_distinct_value_loss_count"]
    )
    source_consecutive = int(
        value["maximum_consecutive_source_value_tuple_count"]
    )
    derived_consecutive = int(
        value["maximum_consecutive_derived_value_count"]
    )
    if source_count != sample_count:
        _append_input_trace_error(errors, path, "source_value_tuple_count")
    if sample_count == 0:
        if any(
            count != 0
            for count in (
                source_distinct,
                source_maximum_tie,
                source_repeat_excess,
                derived_repeat_excess,
                collision_loss,
                source_consecutive,
                derived_consecutive,
            )
        ):
            _append_input_trace_error(errors, path, "empty_counts")
        expected_status = "no_samples"
    else:
        if not 1 <= source_distinct <= sample_count:
            _append_input_trace_error(
                errors,
                path,
                "distinct_source_value_tuple_count",
            )
        elif not (
            math.ceil(sample_count / source_distinct)
            <= source_maximum_tie
            <= sample_count - source_distinct + 1
        ):
            _append_input_trace_error(
                errors,
                path,
                "maximum_source_value_tuple_tie_count",
            )
        if not 1 <= source_consecutive <= source_maximum_tie:
            _append_input_trace_error(
                errors,
                path,
                "maximum_consecutive_source_value_tuple_count",
            )
        if not 1 <= derived_consecutive <= derived_maximum_tie:
            _append_input_trace_error(
                errors,
                path,
                "maximum_consecutive_derived_value_count",
            )
        if source_repeat_excess != sample_count - source_distinct:
            _append_input_trace_error(
                errors,
                path,
                "source_value_tuple_repeat_excess_count",
            )
        if derived_repeat_excess != sample_count - derived_distinct:
            _append_input_trace_error(
                errors,
                path,
                "derived_value_repeat_excess_count",
            )
        if collision_loss != source_distinct - derived_distinct:
            _append_input_trace_error(
                errors,
                path,
                "transform_collision_distinct_value_loss_count",
            )
        if derived_distinct > source_distinct:
            _append_input_trace_error(
                errors,
                path,
                "deterministic_distinctness_order",
            )
        if source_repeat_excess == 0 and collision_loss == 0:
            expected_status = "all_distinct"
        elif source_repeat_excess > 0 and collision_loss == 0:
            expected_status = "source_tuple_repetition"
        elif source_repeat_excess == 0 and collision_loss > 0:
            expected_status = "transform_collision"
        else:
            expected_status = (
                "mixed_source_repetition_and_transform_collision"
            )
    if value.get("input_trace_status") != expected_status:
        _append_input_trace_error(errors, path, "input_trace_status")


def _append_input_trace_error(
    errors: list[str],
    path: str,
    field: str,
) -> None:
    errors.append(
        f"shadow_temporal_surprise_input_trace_inconsistent:{path}.{field}"
    )


def _expect_optional_close(
    actual: object,
    expected: float | None,
    *,
    path: str,
    field: str,
    errors: list[str],
) -> None:
    if expected is None:
        if actual is not None:
            _append_variation_error(errors, path, field)
        return
    if (
        not _is_finite_number_or_none(actual)
        or actual is None
        or not math.isclose(
            float(actual),
            expected,
            rel_tol=1e-10,
            abs_tol=2e-12,
        )
    ):
        _append_variation_error(errors, path, field)


def _append_variation_error(
    errors: list[str],
    path: str,
    field: str,
) -> None:
    errors.append(
        f"shadow_temporal_surprise_variation_inconsistent:{path}.{field}"
    )


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_return_sample_clocks(
    sample: Mapping[str, Any],
    *,
    path: str,
    benchmark: str | None,
    horizon_hours: int,
    current_reference: object,
    errors: list[str],
) -> None:
    asset_endpoint = sample.get("asset_endpoint")
    asset_anchor = sample.get("asset_anchor")
    if (
        isinstance(current_reference, Mapping)
        and isinstance(asset_endpoint, Mapping)
        and dict(asset_endpoint) != dict(current_reference)
    ):
        errors.append(
            f"shadow_temporal_surprise_reference_inconsistent:{path}.asset_endpoint"
        )
    endpoint_at = _reference_time(asset_endpoint)
    anchor_at = _reference_time(asset_anchor)
    if (
        isinstance(asset_endpoint, Mapping)
        and isinstance(asset_anchor, Mapping)
        and asset_endpoint.get("observation_id") == asset_anchor.get("observation_id")
    ):
        errors.append(
            f"shadow_temporal_surprise_reference_inconsistent:{path}.asset_anchor"
        )
    if endpoint_at is None or anchor_at is None:
        return
    target_at = endpoint_at - timedelta(hours=horizon_hours)
    tolerance = max(
        timedelta(seconds=RETURN_MIN_ANCHOR_TOLERANCE_SECONDS),
        timedelta(hours=horizon_hours * RETURN_ANCHOR_TOLERANCE_RATIO),
    )
    if anchor_at > target_at or target_at - anchor_at > tolerance:
        errors.append(
            f"shadow_temporal_surprise_return_clock_inconsistent:{path}.asset"
        )
    if benchmark is None:
        return
    benchmark_endpoint_at = _reference_time(sample.get("benchmark_endpoint"))
    benchmark_anchor_at = _reference_time(sample.get("benchmark_anchor"))
    benchmark_endpoint = sample.get("benchmark_endpoint")
    benchmark_anchor = sample.get("benchmark_anchor")
    if (
        isinstance(benchmark_endpoint, Mapping)
        and isinstance(benchmark_anchor, Mapping)
        and benchmark_endpoint.get("observation_id")
        == benchmark_anchor.get("observation_id")
    ):
        errors.append(
            f"shadow_temporal_surprise_reference_inconsistent:{path}.benchmark_anchor"
        )
    if benchmark_endpoint_at is None or benchmark_anchor_at is None:
        return
    alignment_tolerance = timedelta(
        seconds=BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS
    )
    if (
        benchmark_endpoint_at > endpoint_at
        or endpoint_at - benchmark_endpoint_at > alignment_tolerance
    ):
        errors.append(
            f"shadow_temporal_surprise_return_clock_inconsistent:{path}.benchmark_alignment"
        )
    benchmark_target_at = benchmark_endpoint_at - timedelta(hours=horizon_hours)
    if (
        benchmark_anchor_at > benchmark_target_at
        or benchmark_target_at - benchmark_anchor_at > tolerance
    ):
        errors.append(
            f"shadow_temporal_surprise_return_clock_inconsistent:{path}.benchmark"
        )


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
    if _reference_time(value) is None:
        errors.append(
            f"shadow_temporal_surprise_invalid_type:{path}.observed_at:aware_timestamp"
        )


def _validate_nullable_reference(value: object, path: str, errors: list[str]) -> None:
    if value is None:
        return
    _validate_reference(value, path, errors)


def _reference_time(value: object) -> datetime | None:
    if not isinstance(value, Mapping):
        return None
    raw = value.get("observed_at")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


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
