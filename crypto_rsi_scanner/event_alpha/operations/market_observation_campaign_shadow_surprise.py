"""Causal campaign audit for the existing shadow temporal-surprise model.

The audit replays retained, cadence-counted market observations against only
strictly earlier same-asset history.  It is a deterministic report projection:
it never rewrites historical rows, calls a provider, or grants policy authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..radar import market_shadow_surprise


SCHEMA_ID = "decision_radar.shadow_temporal_surprise_campaign_audit"
SCHEMA_VERSION = 4
LEGACY_SCHEMA_VERSIONS = (1, 2, 3)
DESCRIPTIVE_QUANTILE_METHOD = "linear_interpolation_sorted_ready_values"
VARIATION_QUANTILE_METHOD = (
    "linear_interpolation_sorted_sample_eligible_values"
)
VARIATION_OBSERVATION_BASIS = (
    "closed_shadow_v3_projection_meeting_existing_minimum_sample_count"
)
_SOURCE_STATUSES = {"missing", "observed_empty", "observed", "unavailable"}
_AUDIT_STATUSES = {"unavailable", "empty", "warming", "partial", "ready"}
_INPUT_REJECTION_REASONS = {
    "baseline_counted_invalid",
    "observation_id_invalid",
    "canonical_asset_id_invalid",
    "observed_at_invalid",
    "duplicate_observation_id",
    "duplicate_asset_observed_at",
}
_EVALUATION_ERROR_REASONS = {
    "shadow_projection_type_error",
    "shadow_projection_value_error",
    "shadow_projection_assertion_error",
}
_FEATURES = (
    *market_shadow_surprise.SUPPORTED_FEATURES,
    *market_shadow_surprise.SUPPORTED_RETURN_FEATURES,
)
_FEATURE_FAMILIES = {
    **{
        feature: "activity"
        for feature in market_shadow_surprise.SUPPORTED_FEATURES
    },
    **{
        feature: (
            "direct_return"
            if feature.startswith("return_")
            else "relative_return_btc"
            if "_vs_btc_" in feature
            else "relative_return_eth"
        )
        for feature in market_shadow_surprise.SUPPORTED_RETURN_FEATURES
    },
}
_AUDIT_KEYS_V1_TO_V3 = {
    "schema_id",
    "schema_version",
    "status",
    "source_history",
    "shadow_schema_id",
    "shadow_schema_version",
    "minimum_sample_count",
    "input_row_count",
    "excluded_not_baseline_counted_count",
    "input_rejected_count",
    "input_rejection_reason_counts",
    "valid_baseline_counted_row_count",
    "evaluated_observation_count",
    "evaluation_error_count",
    "evaluation_error_reason_counts",
    "projection_status_counts",
    "return_status_counts",
    "feature_coverage",
    "asset_projection_summaries",
    "asset_count",
    "source_bound_projection_digest",
    "causal_projection_digest",
    "all_features_have_ready_evidence",
    "statistical_independence_claimed",
    "routing_eligible",
    "priority_eligible",
    "score_adjustment_eligible",
    "decision_score_eligible",
    "threshold_change_eligible",
    "publication_authority",
    "protocol_v2_evidence_eligible",
    "auto_apply",
    "historical_rows_rewritten",
    "provider_calls",
    "writes",
    "research_only",
}
_AUDIT_KEYS = _AUDIT_KEYS_V1_TO_V3 | {
    "asset_variation_summaries",
}
_SOURCE_KEYS = {
    "status",
    "artifact",
    "sha256",
    "size_bytes",
    "row_count",
    "binding_source",
}
_FEATURE_COVERAGE_KEYS_V1 = {
    "feature",
    "family",
    "evaluated_observation_count",
    "ready_count",
    "status_counts",
    "minimum_sample_count",
    "minimum_eligible_sample_count",
    "maximum_eligible_sample_count",
    "first_ready_observation",
    "last_ready_observation",
    "projection_digest",
}
_FEATURE_COVERAGE_KEYS_V2 = _FEATURE_COVERAGE_KEYS_V1 | {
    "descriptive_quantile_method",
    "descriptive_tail_rank_kind",
    "tail_ranks_are_p_values",
    "overlapping_samples_are_independent",
    "distribution_ready_count",
    "robust_z_minimum",
    "robust_z_p05",
    "robust_z_median",
    "robust_z_p95",
    "robust_z_maximum",
    "minimum_robust_z_observation",
    "maximum_robust_z_observation",
    "descriptive_tail_rank_minimum",
    "descriptive_tail_rank_p05",
    "descriptive_tail_rank_median",
    "descriptive_tail_rank_p95",
    "descriptive_tail_rank_maximum",
    "minimum_descriptive_tail_rank_observation",
    "maximum_descriptive_tail_rank_observation",
}
_FEATURE_COVERAGE_KEYS = _FEATURE_COVERAGE_KEYS_V2 | {
    "variation_observation_basis",
    "variation_quantile_method",
    "variation_observation_count",
    "minimum_distinct_baseline_value_count",
    "variation_diagnostics_are_policy",
    "effective_sample_size_claimed",
    "distinct_baseline_value_count_minimum",
    "distinct_baseline_value_count_median",
    "distinct_baseline_value_count_maximum",
    "distinct_baseline_value_ratio_minimum",
    "distinct_baseline_value_ratio_p05",
    "distinct_baseline_value_ratio_median",
    "distinct_baseline_value_ratio_p95",
    "distinct_baseline_value_ratio_maximum",
    "maximum_baseline_value_tie_count_maximum",
    "maximum_baseline_value_tie_ratio_minimum",
    "maximum_baseline_value_tie_ratio_p05",
    "maximum_baseline_value_tie_ratio_median",
    "maximum_baseline_value_tie_ratio_p95",
    "maximum_baseline_value_tie_ratio_maximum",
    "minimum_distinct_baseline_value_ratio_observation",
    "maximum_baseline_value_tie_ratio_observation",
}
_ASSET_SUMMARY_KEYS = {
    "canonical_asset_id",
    "evaluated_observation_count",
    "first_observation",
    "last_observation",
    "first_source_bound_projection_sha256",
    "last_source_bound_projection_sha256",
    "first_causal_projection_sha256",
    "last_causal_projection_sha256",
    "projection_status_counts",
    "source_bound_projection_digest",
    "causal_projection_digest",
}
_ASSET_VARIATION_SUMMARY_KEYS = {
    "canonical_asset_id",
    "evaluated_observation_count",
    "retained_context_observation_count",
    "first_evaluated_observation",
    "last_evaluated_observation",
    "retained_symbol_counts",
    "retained_provider_counts",
    "retained_data_mode_counts",
    "retained_feature_basis_counts",
    "source_context_is_causal_attribution",
    "features_with_repeated_baseline_values",
    "feature_with_repeated_baseline_value_count",
    "feature_variation",
    "projection_digest",
    "routing_eligible",
    "score_adjustment_eligible",
    "threshold_change_eligible",
    "protocol_v2_evidence_eligible",
    "research_only",
}
_ASSET_FEATURE_VARIATION_KEYS = {
    "feature",
    "family",
    "evaluated_observation_count",
    "minimum_sample_count",
    "variation_observation_count",
    "repeated_baseline_value_observation_count",
    "all_distinct_baseline_value_observation_count",
    "descriptive_repetition_observation_share",
    "distinct_baseline_value_ratio_minimum",
    "distinct_baseline_value_ratio_median",
    "maximum_baseline_value_tie_ratio_median",
    "maximum_baseline_value_tie_ratio_maximum",
    "latest_variation_observation",
    "minimum_distinct_baseline_value_ratio_observation",
    "maximum_baseline_value_tie_ratio_observation",
    "minimum_distinct_baseline_value_count",
    "variation_diagnostics_are_policy",
    "effective_sample_size_claimed",
    "overlapping_reference_sets_are_independent",
    "projection_digest",
}
_RETAINED_FEATURE_BASIS_KEYS = {
    "price",
    "volume_24h",
    "market_cap",
    "turnover_24h",
}
_REFERENCE_KEYS = {"observation_id", "observed_at"}
_EXTREME_REFERENCE_KEYS = {
    "canonical_asset_id",
    "observation_id",
    "observed_at",
}
_VARIATION_REFERENCE_KEYS = _EXTREME_REFERENCE_KEYS | {
    "sample_count",
    "distinct_baseline_value_count",
    "distinct_baseline_value_ratio",
    "maximum_baseline_value_tie_count",
    "maximum_baseline_value_tie_ratio",
}
_ZERO_FALSE_FIELDS = (
    "statistical_independence_claimed",
    "routing_eligible",
    "priority_eligible",
    "score_adjustment_eligible",
    "decision_score_eligible",
    "threshold_change_eligible",
    "publication_authority",
    "protocol_v2_evidence_eligible",
    "auto_apply",
    "historical_rows_rewritten",
)
_ZERO_COUNT_FIELDS = ("provider_calls", "writes")


def build_campaign_shadow_surprise_audit(
    history_snapshot: Mapping[str, Any],
    *,
    minimum_sample_count: int,
) -> dict[str, Any]:
    """Replay the current closed shadow diagnostics over one history snapshot."""

    if (
        isinstance(minimum_sample_count, bool)
        or not isinstance(minimum_sample_count, int)
        or minimum_sample_count < 1
    ):
        raise ValueError("minimum_sample_count must be a positive integer")
    source = _source_projection(history_snapshot)
    raw_rows = history_snapshot.get("rows")
    rows = list(raw_rows) if isinstance(raw_rows, (tuple, list)) else []
    if source["status"] not in {"observed", "observed_empty"}:
        audit = _empty_audit(
            source,
            minimum_sample_count=minimum_sample_count,
            status="unavailable",
        )
        _assert_valid(audit)
        return audit
    if source["row_count"] != len(rows) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        audit = _empty_audit(
            source,
            minimum_sample_count=minimum_sample_count,
            status="unavailable",
            input_row_count=len(rows),
            input_rejected_count=len(rows),
            input_rejection_reason_counts={
                "baseline_counted_invalid": len(rows)
            } if rows else {},
        )
        _assert_valid(audit)
        return audit

    prepared, excluded_count, rejection_counts = _prepare_rows(rows)
    projections: list[dict[str, Any]] = []
    evaluation_errors: Counter[str] = Counter()
    feature_records: dict[str, list[dict[str, Any]]] = {
        feature: [] for feature in _FEATURES
    }
    asset_feature_records: dict[str, dict[str, list[dict[str, Any]]]] = (
        defaultdict(lambda: {feature: [] for feature in _FEATURES})
    )
    by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_rows: dict[str, tuple[dict[str, Any], ...]] = {}
    for row in prepared:
        grouped_rows.setdefault(row["canonical_asset_id"], ())
    for asset_id in grouped_rows:
        grouped_rows[asset_id] = tuple(
            item
            for item in prepared
            if item["canonical_asset_id"] == asset_id
        )
    benchmark_rows = {
        benchmark: tuple(
            row
            for row in prepared
            if row["canonical_asset_id"].casefold()
            in {asset_id.casefold() for asset_id in asset_ids}
        )
        for benchmark, asset_ids in market_shadow_surprise.BENCHMARK_ASSET_IDS.items()
    }

    for current in prepared:
        current_at = _parse_aware_utc(current["observed_at"])
        same_asset = grouped_rows[current["canonical_asset_id"]]
        priors = tuple(
            row
            for row in same_asset
            if _parse_aware_utc(row["observed_at"]) < current_at
        )
        current_benchmarks = {
            benchmark: tuple(
                row
                for row in candidates
                if _parse_aware_utc(row["observed_at"]) <= current_at
            )
            for benchmark, candidates in benchmark_rows.items()
        }
        try:
            projection = market_shadow_surprise.evaluate_shadow_temporal_surprise(
                current,
                priors,
                minimum_sample_count=minimum_sample_count,
                history_artifact=source["artifact"],
                history_sha256=source["sha256"],
                benchmark_observations=current_benchmarks,
            )
        except TypeError:
            evaluation_errors["shadow_projection_type_error"] += 1
            continue
        except ValueError:
            evaluation_errors["shadow_projection_value_error"] += 1
            continue
        except AssertionError:
            evaluation_errors["shadow_projection_assertion_error"] += 1
            continue
        compact = _compact_projection(current, projection)
        projections.append(compact)
        by_asset[current["canonical_asset_id"]].append(compact)
        _append_feature_records(
            current,
            projection,
            feature_records=feature_records,
            asset_feature_records=asset_feature_records,
        )

    feature_coverage = {
        feature: _feature_coverage(
            feature,
            feature_records[feature],
            minimum_sample_count=minimum_sample_count,
        )
        for feature in _FEATURES
    }
    asset_summaries = [
        _asset_summary(asset_id, by_asset[asset_id])
        for asset_id in sorted(by_asset)
        if by_asset[asset_id]
    ]
    asset_variation_summaries = [
        _asset_variation_summary(
            asset_id,
            evaluated_records=by_asset[asset_id],
            retained_context_rows=grouped_rows[asset_id],
            feature_records=asset_feature_records[asset_id],
            minimum_sample_count=minimum_sample_count,
        )
        for asset_id in sorted(by_asset)
        if by_asset[asset_id]
    ]
    projection_status_counts = Counter(
        str(row["status"]) for row in projections
    )
    return_status_counts = Counter(
        str(row["return_status"]) for row in projections
    )
    rejected_count = sum(rejection_counts.values())
    evaluated_count = len(projections)
    all_features_ready = bool(feature_coverage) and all(
        coverage["ready_count"] > 0
        for coverage in feature_coverage.values()
    )
    status = _audit_status(
        source_status=source["status"],
        input_row_count=len(rows),
        evaluated_count=evaluated_count,
        rejected_count=rejected_count,
        evaluation_error_count=sum(evaluation_errors.values()),
        all_features_ready=all_features_ready,
    )
    audit = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_history": source,
        "shadow_schema_id": (
            market_shadow_surprise.SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID
        ),
        "shadow_schema_version": (
            market_shadow_surprise.SHADOW_TEMPORAL_SURPRISE_SCHEMA_VERSION
        ),
        "minimum_sample_count": minimum_sample_count,
        "input_row_count": len(rows),
        "excluded_not_baseline_counted_count": excluded_count,
        "input_rejected_count": rejected_count,
        "input_rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "valid_baseline_counted_row_count": len(prepared),
        "evaluated_observation_count": evaluated_count,
        "evaluation_error_count": sum(evaluation_errors.values()),
        "evaluation_error_reason_counts": dict(sorted(evaluation_errors.items())),
        "projection_status_counts": dict(sorted(projection_status_counts.items())),
        "return_status_counts": dict(sorted(return_status_counts.items())),
        "feature_coverage": feature_coverage,
        "asset_projection_summaries": asset_summaries,
        "asset_variation_summaries": asset_variation_summaries,
        "asset_count": len(asset_summaries),
        "source_bound_projection_digest": _sha256_json(projections),
        "causal_projection_digest": _sha256_json([
            {
                key: value
                for key, value in projection.items()
                if key != "source_bound_projection_sha256"
            }
            for projection in projections
        ]),
        "all_features_have_ready_evidence": all_features_ready,
        "statistical_independence_claimed": False,
        "routing_eligible": False,
        "priority_eligible": False,
        "score_adjustment_eligible": False,
        "decision_score_eligible": False,
        "threshold_change_eligible": False,
        "publication_authority": False,
        "protocol_v2_evidence_eligible": False,
        "auto_apply": False,
        "historical_rows_rewritten": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    _assert_valid(audit)
    return audit


def validate_campaign_shadow_surprise_audit(
    value: Mapping[str, Any],
) -> list[str]:
    """Validate the closed report projection and its accounting equations."""

    if not isinstance(value, Mapping):
        return ["audit_not_mapping"]
    errors: list[str] = []
    raw_schema_version = value.get("schema_version")
    expected_audit_keys = (
        _AUDIT_KEYS
        if raw_schema_version == SCHEMA_VERSION
        else _AUDIT_KEYS_V1_TO_V3
    )
    _exact_keys(value, expected_audit_keys, "audit", errors)
    if value.get("schema_id") != SCHEMA_ID:
        errors.append("schema_id_invalid")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int or schema_version not in {
        *LEGACY_SCHEMA_VERSIONS,
        SCHEMA_VERSION,
    }:
        errors.append("schema_version_invalid")
    if value.get("status") not in _AUDIT_STATUSES:
        errors.append("status_invalid")
    if value.get("shadow_schema_id") != (
        market_shadow_surprise.SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID
    ):
        errors.append("shadow_schema_id_invalid")
    accepted_shadow_versions = {
        1: {2},
        2: {2, 3},
        3: {3},
        4: {3},
    }.get(schema_version, set())
    if value.get("shadow_schema_version") not in accepted_shadow_versions:
        errors.append("shadow_schema_version_invalid")
    minimum = value.get("minimum_sample_count")
    if type(minimum) is not int or minimum < 1:
        errors.append("minimum_sample_count_invalid")

    source = value.get("source_history")
    if not isinstance(source, Mapping):
        errors.append("source_history_invalid")
        source = {}
    _validate_source(source, errors=errors)
    counts = _validated_counts(value, errors=errors)
    rejection_counts = _reason_counts(
        value.get("input_rejection_reason_counts"),
        allowed=_INPUT_REJECTION_REASONS,
        label="input_rejection",
        errors=errors,
    )
    evaluation_reason_counts = _reason_counts(
        value.get("evaluation_error_reason_counts"),
        allowed=_EVALUATION_ERROR_REASONS,
        label="evaluation_error",
        errors=errors,
    )
    if counts:
        if counts["input_row_count"] != (
            counts["excluded_not_baseline_counted_count"]
            + counts["input_rejected_count"]
            + counts["valid_baseline_counted_row_count"]
        ):
            errors.append("input_row_count_not_closed")
        if counts["valid_baseline_counted_row_count"] != (
            counts["evaluated_observation_count"]
            + counts["evaluation_error_count"]
        ):
            errors.append("evaluation_count_not_closed")
        if counts["input_rejected_count"] != sum(rejection_counts.values()):
            errors.append("input_rejection_count_mismatch")
        if counts["evaluation_error_count"] != sum(
            evaluation_reason_counts.values()
        ):
            errors.append("evaluation_error_count_mismatch")

    feature_coverage = value.get("feature_coverage")
    if not isinstance(feature_coverage, Mapping) or set(feature_coverage) != set(
        _FEATURES
    ):
        errors.append("feature_coverage_keys_invalid")
        feature_coverage = {}
    evaluated_count = counts.get("evaluated_observation_count", 0)
    for feature in _FEATURES:
        coverage = feature_coverage.get(feature)
        _validate_feature_coverage(
            feature,
            coverage,
            schema_version=(
                schema_version if type(schema_version) is int else SCHEMA_VERSION
            ),
            evaluated_count=evaluated_count,
            minimum_sample_count=minimum if type(minimum) is int else None,
            errors=errors,
        )

    asset_summaries = value.get("asset_projection_summaries")
    if not isinstance(asset_summaries, list):
        errors.append("asset_projection_summaries_invalid")
        asset_summaries = []
    _validate_asset_summaries(
        asset_summaries,
        evaluated_count=evaluated_count,
        errors=errors,
    )
    if schema_version >= 4:
        _validate_asset_variation_summaries(
            value.get("asset_variation_summaries"),
            asset_summaries=asset_summaries,
            minimum_sample_count=(minimum if type(minimum) is int else None),
            errors=errors,
        )
    if type(value.get("asset_count")) is not int or value.get("asset_count") != len(
        asset_summaries
    ):
        errors.append("asset_count_invalid")
    _validate_status_counts(
        value.get("projection_status_counts"),
        expected_total=evaluated_count,
        label="projection_status",
        errors=errors,
    )
    _validate_status_counts(
        value.get("return_status_counts"),
        expected_total=evaluated_count,
        label="return_status",
        errors=errors,
    )
    all_features_ready = bool(feature_coverage) and all(
        isinstance(coverage, Mapping)
        and type(coverage.get("ready_count")) is int
        and coverage.get("ready_count") > 0
        for coverage in feature_coverage.values()
    )
    if value.get("all_features_have_ready_evidence") is not all_features_ready:
        errors.append("all_features_ready_mismatch")
    expected_status = _audit_status(
        source_status=str(source.get("status") or "unavailable"),
        input_row_count=counts.get("input_row_count", 0),
        evaluated_count=evaluated_count,
        rejected_count=counts.get("input_rejected_count", 0),
        evaluation_error_count=counts.get("evaluation_error_count", 0),
        all_features_ready=all_features_ready,
    )
    if value.get("status") != expected_status:
        errors.append("status_derivation_mismatch")
    for field in (
        "source_bound_projection_digest",
        "causal_projection_digest",
    ):
        if not _sha256(value.get(field)):
            errors.append(f"{field}_invalid")
    for field in _ZERO_FALSE_FIELDS:
        if value.get(field) is not False:
            errors.append(f"{field}_must_be_false")
    for field in _ZERO_COUNT_FIELDS:
        if value.get(field) != 0:
            errors.append(f"{field}_must_be_zero")
    if value.get("research_only") is not True:
        errors.append("research_only_must_be_true")
    return sorted(set(errors))


def _prepare_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, Counter[str]]:
    excluded = 0
    rejected: dict[int, str] = {}
    basic: list[tuple[int, dict[str, Any], datetime]] = []
    for index, raw in enumerate(rows):
        row = dict(raw)
        baseline_counted = row.get("baseline_counted")
        if baseline_counted is False:
            excluded += 1
            continue
        if baseline_counted is not True:
            rejected[index] = "baseline_counted_invalid"
            continue
        if not _identity(row.get("observation_id")):
            rejected[index] = "observation_id_invalid"
            continue
        if not _identity(row.get("canonical_asset_id")):
            rejected[index] = "canonical_asset_id_invalid"
            continue
        try:
            observed_at = _parse_aware_utc(row.get("observed_at"))
        except (TypeError, ValueError):
            rejected[index] = "observed_at_invalid"
            continue
        row["observation_id"] = _identity(row["observation_id"])
        row["canonical_asset_id"] = _identity(row["canonical_asset_id"])
        row["observed_at"] = observed_at.isoformat()
        basic.append((index, row, observed_at))

    by_id: dict[str, list[int]] = defaultdict(list)
    by_asset_time: dict[tuple[str, datetime], list[int]] = defaultdict(list)
    for index, row, observed_at in basic:
        by_id[row["observation_id"]].append(index)
        by_asset_time[(row["canonical_asset_id"], observed_at)].append(index)
    for indexes in by_id.values():
        if len(indexes) > 1:
            for index in indexes:
                rejected.setdefault(index, "duplicate_observation_id")
    for indexes in by_asset_time.values():
        if len(indexes) > 1:
            for index in indexes:
                rejected.setdefault(index, "duplicate_asset_observed_at")

    prepared = [
        row
        for index, row, _ in basic
        if index not in rejected
    ]
    prepared.sort(
        key=lambda row: (
            _parse_aware_utc(row["observed_at"]),
            row["canonical_asset_id"],
            row["observation_id"],
        )
    )
    return prepared, excluded, Counter(rejected.values())


def _append_feature_records(
    current: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    feature_records: dict[str, list[dict[str, Any]]],
    asset_feature_records: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    reference = _reference(current)
    activity = projection.get("features")
    returns = projection.get("return_features")
    if not isinstance(activity, Mapping) or not isinstance(returns, Mapping):
        raise AssertionError("closed shadow projection lost feature mappings")
    for feature in _FEATURES:
        feature_value = (
            activity.get(feature)
            if feature in market_shadow_surprise.SUPPORTED_FEATURES
            else returns.get(feature)
        )
        if not isinstance(feature_value, Mapping):
            raise AssertionError("closed shadow projection lost a feature value")
        sample_count = feature_value.get("sample_count")
        if type(sample_count) is not int or sample_count < 0:
            raise AssertionError("closed shadow projection has invalid sample count")
        distinct_count = feature_value.get("distinct_baseline_value_count")
        maximum_tie_count = feature_value.get(
            "maximum_baseline_value_tie_count"
        )
        current_tie_count = feature_value.get(
            "current_value_baseline_tie_count"
        )
        distinct_ratio = _finite_float_or_none(
            feature_value.get("distinct_baseline_value_ratio")
        )
        if sample_count == 0:
            if (
                distinct_count != 0
                or maximum_tie_count != 0
                or current_tie_count not in (0, None)
                or distinct_ratio is not None
            ):
                raise AssertionError(
                    "empty shadow baseline has inconsistent variation diagnostics"
                )
        elif (
            type(distinct_count) is not int
            or not 1 <= distinct_count <= sample_count
            or type(maximum_tie_count) is not int
            or not 1 <= maximum_tie_count <= sample_count
            or (
                current_tie_count is not None
                and (
                    type(current_tie_count) is not int
                    or not 0 <= current_tie_count <= sample_count
                )
            )
            or distinct_ratio != _rounded_ratio(distinct_count, sample_count)
        ):
            raise AssertionError(
                "shadow baseline variation diagnostics are inconsistent"
            )
        status = str(feature_value.get("status") or "unavailable")
        robust_z = _finite_float_or_none(feature_value.get("robust_z"))
        tail_rank_field = (
            "upper_tail_rank"
            if feature in market_shadow_surprise.SUPPORTED_FEATURES
            else "two_sided_tail_rank"
        )
        descriptive_tail_rank = _finite_float_or_none(
            feature_value.get(tail_rank_field)
        )
        if status == "ready" and (
            robust_z is None
            or descriptive_tail_rank is None
            or not 0.0 < descriptive_tail_rank <= 1.0
        ):
            raise AssertionError(
                "ready shadow projection lost robust-z or descriptive-tail truth"
            )
        if status != "ready":
            robust_z = None
            descriptive_tail_rank = None
        record = {
            "reference": reference,
            "canonical_asset_id": str(current["canonical_asset_id"]),
            "status": status,
            "sample_count": sample_count,
            "distinct_baseline_value_count": distinct_count,
            "maximum_baseline_value_tie_count": maximum_tie_count,
            "current_value_baseline_tie_count": current_tie_count,
            "distinct_baseline_value_ratio": distinct_ratio,
            "robust_z": robust_z,
            "descriptive_tail_rank": descriptive_tail_rank,
            "projection_sha256": _sha256_json(feature_value),
        }
        feature_records[feature].append(record)
        asset_feature_records[str(current["canonical_asset_id"])][feature].append(
            record
        )


def _compact_projection(
    current: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "canonical_asset_id": current["canonical_asset_id"],
        **_reference(current),
        "status": str(projection.get("status") or "unavailable"),
        "return_status": str(projection.get("return_status") or "unavailable"),
        "source_bound_projection_sha256": _sha256_json(projection),
        "causal_projection_sha256": _sha256_json({
            key: value
            for key, value in projection.items()
            if key != "history_artifact_sha256"
        }),
    }


def _feature_coverage(
    feature: str,
    records: Sequence[Mapping[str, Any]],
    *,
    minimum_sample_count: int,
) -> dict[str, Any]:
    status_counts = Counter(str(row["status"]) for row in records)
    ready = [row for row in records if row["status"] == "ready"]
    samples = [int(row["sample_count"]) for row in records]
    variation = [
        row
        for row in records
        if int(row["sample_count"]) >= minimum_sample_count
    ]
    robust_z_values = [float(row["robust_z"]) for row in ready]
    tail_rank_values = [float(row["descriptive_tail_rank"]) for row in ready]
    distinct_counts = [
        float(row["distinct_baseline_value_count"])
        for row in variation
    ]
    distinct_ratios = [
        float(row["distinct_baseline_value_ratio"])
        for row in variation
    ]
    maximum_tie_ratios = [
        _maximum_baseline_tie_ratio(row)
        for row in variation
    ]
    minimum_robust_z_row = (
        min(ready, key=lambda row: float(row["robust_z"])) if ready else None
    )
    maximum_robust_z_row = (
        max(ready, key=lambda row: float(row["robust_z"])) if ready else None
    )
    minimum_tail_rank_row = (
        min(ready, key=lambda row: float(row["descriptive_tail_rank"]))
        if ready
        else None
    )
    maximum_tail_rank_row = (
        max(ready, key=lambda row: float(row["descriptive_tail_rank"]))
        if ready
        else None
    )
    minimum_distinct_ratio_row = (
        min(
            variation,
            key=lambda row: (
                float(row["distinct_baseline_value_ratio"]),
                _feature_record_sort_key(row),
            ),
        )
        if variation
        else None
    )
    maximum_tie_ratio_row = (
        min(
            variation,
            key=lambda row: (
                -_maximum_baseline_tie_ratio(row),
                _feature_record_sort_key(row),
            ),
        )
        if variation
        else None
    )
    return {
        "feature": feature,
        "family": _FEATURE_FAMILIES[feature],
        "evaluated_observation_count": len(records),
        "ready_count": len(ready),
        "status_counts": dict(sorted(status_counts.items())),
        "minimum_sample_count": minimum_sample_count,
        "minimum_eligible_sample_count": min(samples) if samples else None,
        "maximum_eligible_sample_count": max(samples) if samples else None,
        "first_ready_observation": (
            dict(ready[0]["reference"]) if ready else None
        ),
        "last_ready_observation": (
            dict(ready[-1]["reference"]) if ready else None
        ),
        "descriptive_quantile_method": DESCRIPTIVE_QUANTILE_METHOD,
        "descriptive_tail_rank_kind": (
            "upper"
            if feature in market_shadow_surprise.SUPPORTED_FEATURES
            else "two_sided"
        ),
        "tail_ranks_are_p_values": False,
        "overlapping_samples_are_independent": False,
        "distribution_ready_count": len(ready),
        "robust_z_minimum": _descriptive_quantile(robust_z_values, 0.0),
        "robust_z_p05": _descriptive_quantile(robust_z_values, 0.05),
        "robust_z_median": _descriptive_quantile(robust_z_values, 0.5),
        "robust_z_p95": _descriptive_quantile(robust_z_values, 0.95),
        "robust_z_maximum": _descriptive_quantile(robust_z_values, 1.0),
        "minimum_robust_z_observation": (
            _extreme_reference(minimum_robust_z_row)
            if minimum_robust_z_row is not None
            else None
        ),
        "maximum_robust_z_observation": (
            _extreme_reference(maximum_robust_z_row)
            if maximum_robust_z_row is not None
            else None
        ),
        "descriptive_tail_rank_minimum": _descriptive_quantile(
            tail_rank_values, 0.0
        ),
        "descriptive_tail_rank_p05": _descriptive_quantile(
            tail_rank_values, 0.05
        ),
        "descriptive_tail_rank_median": _descriptive_quantile(
            tail_rank_values, 0.5
        ),
        "descriptive_tail_rank_p95": _descriptive_quantile(
            tail_rank_values, 0.95
        ),
        "descriptive_tail_rank_maximum": _descriptive_quantile(
            tail_rank_values, 1.0
        ),
        "minimum_descriptive_tail_rank_observation": (
            _extreme_reference(minimum_tail_rank_row)
            if minimum_tail_rank_row is not None
            else None
        ),
        "maximum_descriptive_tail_rank_observation": (
            _extreme_reference(maximum_tail_rank_row)
            if maximum_tail_rank_row is not None
            else None
        ),
        "variation_observation_basis": VARIATION_OBSERVATION_BASIS,
        "variation_quantile_method": VARIATION_QUANTILE_METHOD,
        "variation_observation_count": len(variation),
        "minimum_distinct_baseline_value_count": None,
        "variation_diagnostics_are_policy": False,
        "effective_sample_size_claimed": False,
        "distinct_baseline_value_count_minimum": _descriptive_quantile(
            distinct_counts, 0.0
        ),
        "distinct_baseline_value_count_median": _descriptive_quantile(
            distinct_counts, 0.5
        ),
        "distinct_baseline_value_count_maximum": _descriptive_quantile(
            distinct_counts, 1.0
        ),
        "distinct_baseline_value_ratio_minimum": _descriptive_quantile(
            distinct_ratios, 0.0
        ),
        "distinct_baseline_value_ratio_p05": _descriptive_quantile(
            distinct_ratios, 0.05
        ),
        "distinct_baseline_value_ratio_median": _descriptive_quantile(
            distinct_ratios, 0.5
        ),
        "distinct_baseline_value_ratio_p95": _descriptive_quantile(
            distinct_ratios, 0.95
        ),
        "distinct_baseline_value_ratio_maximum": _descriptive_quantile(
            distinct_ratios, 1.0
        ),
        "maximum_baseline_value_tie_count_maximum": (
            max(
                int(row["maximum_baseline_value_tie_count"])
                for row in variation
            )
            if variation
            else None
        ),
        "maximum_baseline_value_tie_ratio_minimum": _descriptive_quantile(
            maximum_tie_ratios, 0.0
        ),
        "maximum_baseline_value_tie_ratio_p05": _descriptive_quantile(
            maximum_tie_ratios, 0.05
        ),
        "maximum_baseline_value_tie_ratio_median": _descriptive_quantile(
            maximum_tie_ratios, 0.5
        ),
        "maximum_baseline_value_tie_ratio_p95": _descriptive_quantile(
            maximum_tie_ratios, 0.95
        ),
        "maximum_baseline_value_tie_ratio_maximum": _descriptive_quantile(
            maximum_tie_ratios, 1.0
        ),
        "minimum_distinct_baseline_value_ratio_observation": (
            _variation_reference(minimum_distinct_ratio_row)
            if minimum_distinct_ratio_row is not None
            else None
        ),
        "maximum_baseline_value_tie_ratio_observation": (
            _variation_reference(maximum_tie_ratio_row)
            if maximum_tie_ratio_row is not None
            else None
        ),
        "projection_digest": _sha256_json(list(records)),
    }


def _descriptive_quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        value = ordered[lower_index]
    else:
        weight = position - lower_index
        value = ordered[lower_index] + (
            ordered[upper_index] - ordered[lower_index]
        ) * weight
    rounded = round(float(value), 12)
    return 0.0 if rounded == 0.0 else rounded


def _extreme_reference(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "canonical_asset_id": str(row["canonical_asset_id"]),
        **dict(row["reference"]),
    }


def _maximum_baseline_tie_ratio(row: Mapping[str, Any]) -> float:
    return _rounded_ratio(
        int(row["maximum_baseline_value_tie_count"]),
        int(row["sample_count"]),
    )


def _variation_reference(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_extreme_reference(row),
        "sample_count": int(row["sample_count"]),
        "distinct_baseline_value_count": int(
            row["distinct_baseline_value_count"]
        ),
        "distinct_baseline_value_ratio": float(
            row["distinct_baseline_value_ratio"]
        ),
        "maximum_baseline_value_tie_count": int(
            row["maximum_baseline_value_tie_count"]
        ),
        "maximum_baseline_value_tie_ratio": _maximum_baseline_tie_ratio(row),
    }


def _feature_record_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    reference = row["reference"]
    return (
        str(reference["observed_at"]),
        str(row["canonical_asset_id"]),
        str(reference["observation_id"]),
    )


def _rounded_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise AssertionError("ratio denominator must be positive")
    value = round(numerator / denominator, 12)
    return 0.0 if value == 0.0 else value


def _asset_variation_summary(
    asset_id: str,
    *,
    evaluated_records: Sequence[Mapping[str, Any]],
    retained_context_rows: Sequence[Mapping[str, Any]],
    feature_records: Mapping[str, Sequence[Mapping[str, Any]]],
    minimum_sample_count: int,
) -> dict[str, Any]:
    feature_variation = {
        feature: _asset_feature_variation(
            feature,
            feature_records[feature],
            minimum_sample_count=minimum_sample_count,
        )
        for feature in _FEATURES
    }
    repeated_features = sorted(
        feature
        for feature, summary in feature_variation.items()
        if summary["repeated_baseline_value_observation_count"] > 0
    )
    retained_feature_basis_counts = {
        feature: _retained_feature_basis_counts(
            retained_context_rows,
            feature=feature,
        )
        for feature in sorted(_RETAINED_FEATURE_BASIS_KEYS)
    }
    return {
        "canonical_asset_id": asset_id,
        "evaluated_observation_count": len(evaluated_records),
        "retained_context_observation_count": len(retained_context_rows),
        "first_evaluated_observation": {
            key: evaluated_records[0][key] for key in _REFERENCE_KEYS
        },
        "last_evaluated_observation": {
            key: evaluated_records[-1][key] for key in _REFERENCE_KEYS
        },
        "retained_symbol_counts": _retained_context_counts(
            retained_context_rows,
            fields=("symbol",),
            normalize=False,
        ),
        "retained_provider_counts": _retained_context_counts(
            retained_context_rows,
            fields=("provider", "market_data_source", "source"),
            normalize=True,
        ),
        "retained_data_mode_counts": _retained_context_counts(
            retained_context_rows,
            fields=("data_mode", "data_acquisition_mode"),
            normalize=True,
        ),
        "retained_feature_basis_counts": retained_feature_basis_counts,
        "source_context_is_causal_attribution": False,
        "features_with_repeated_baseline_values": repeated_features,
        "feature_with_repeated_baseline_value_count": len(repeated_features),
        "feature_variation": feature_variation,
        "projection_digest": _sha256_json({
            feature: list(feature_records[feature])
            for feature in _FEATURES
        }),
        "routing_eligible": False,
        "score_adjustment_eligible": False,
        "threshold_change_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def _asset_feature_variation(
    feature: str,
    records: Sequence[Mapping[str, Any]],
    *,
    minimum_sample_count: int,
) -> dict[str, Any]:
    variation = [
        row
        for row in records
        if int(row["sample_count"]) >= minimum_sample_count
    ]
    repeated = [
        row
        for row in variation
        if int(row["distinct_baseline_value_count"])
        < int(row["sample_count"])
    ]
    distinct_ratios = [
        float(row["distinct_baseline_value_ratio"])
        for row in variation
    ]
    maximum_tie_ratios = [
        _maximum_baseline_tie_ratio(row)
        for row in variation
    ]
    minimum_distinct_ratio_row = (
        min(
            variation,
            key=lambda row: (
                float(row["distinct_baseline_value_ratio"]),
                _feature_record_sort_key(row),
            ),
        )
        if variation
        else None
    )
    maximum_tie_ratio_row = (
        min(
            variation,
            key=lambda row: (
                -_maximum_baseline_tie_ratio(row),
                _feature_record_sort_key(row),
            ),
        )
        if variation
        else None
    )
    return {
        "feature": feature,
        "family": _FEATURE_FAMILIES[feature],
        "evaluated_observation_count": len(records),
        "minimum_sample_count": minimum_sample_count,
        "variation_observation_count": len(variation),
        "repeated_baseline_value_observation_count": len(repeated),
        "all_distinct_baseline_value_observation_count": (
            len(variation) - len(repeated)
        ),
        "descriptive_repetition_observation_share": (
            _rounded_ratio(len(repeated), len(variation))
            if variation
            else None
        ),
        "distinct_baseline_value_ratio_minimum": _descriptive_quantile(
            distinct_ratios, 0.0
        ),
        "distinct_baseline_value_ratio_median": _descriptive_quantile(
            distinct_ratios, 0.5
        ),
        "maximum_baseline_value_tie_ratio_median": _descriptive_quantile(
            maximum_tie_ratios, 0.5
        ),
        "maximum_baseline_value_tie_ratio_maximum": _descriptive_quantile(
            maximum_tie_ratios, 1.0
        ),
        "latest_variation_observation": (
            _variation_reference(variation[-1]) if variation else None
        ),
        "minimum_distinct_baseline_value_ratio_observation": (
            _variation_reference(minimum_distinct_ratio_row)
            if minimum_distinct_ratio_row is not None
            else None
        ),
        "maximum_baseline_value_tie_ratio_observation": (
            _variation_reference(maximum_tie_ratio_row)
            if maximum_tie_ratio_row is not None
            else None
        ),
        "minimum_distinct_baseline_value_count": None,
        "variation_diagnostics_are_policy": False,
        "effective_sample_size_claimed": False,
        "overlapping_reference_sets_are_independent": False,
        "projection_digest": _sha256_json(list(records)),
    }


def _retained_context_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    fields: tuple[str, ...],
    normalize: bool,
) -> dict[str, int]:
    return dict(sorted(Counter(
        _retained_context_identity(
            row,
            fields=fields,
            normalize=normalize,
        )
        for row in rows
    ).items()))


def _retained_context_identity(
    row: Mapping[str, Any],
    *,
    fields: tuple[str, ...],
    normalize: bool,
) -> str:
    for field in fields:
        if field not in row:
            continue
        value = row.get(field)
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value.strip()) > 200
            or any(ord(character) < 32 for character in value.strip())
        ):
            return "invalid"
        identity = value.strip()
        return identity.casefold() if normalize else identity
    return "unavailable"


def _retained_feature_basis_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    feature: str,
) -> dict[str, int]:
    return dict(sorted(Counter(
        _retained_feature_basis(row, feature=feature)
        for row in rows
    ).items()))


def _retained_feature_basis(row: Mapping[str, Any], *, feature: str) -> str:
    if "feature_basis" in row:
        container = row.get("feature_basis")
        if not isinstance(container, Mapping):
            return "invalid"
        if feature not in container:
            return "unavailable"
        value = container.get(feature)
    elif f"{feature}_basis" in row:
        value = row.get(f"{feature}_basis")
    else:
        return "unavailable"
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 200
        or any(ord(character) < 32 for character in value.strip())
    ):
        return "invalid"
    return value.strip().casefold()


def _asset_summary(
    asset_id: str,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "canonical_asset_id": asset_id,
        "evaluated_observation_count": len(records),
        "first_observation": {
            key: records[0][key] for key in _REFERENCE_KEYS
        },
        "last_observation": {
            key: records[-1][key] for key in _REFERENCE_KEYS
        },
        "first_source_bound_projection_sha256": records[0][
            "source_bound_projection_sha256"
        ],
        "last_source_bound_projection_sha256": records[-1][
            "source_bound_projection_sha256"
        ],
        "first_causal_projection_sha256": records[0][
            "causal_projection_sha256"
        ],
        "last_causal_projection_sha256": records[-1][
            "causal_projection_sha256"
        ],
        "projection_status_counts": dict(sorted(Counter(
            str(row["status"]) for row in records
        ).items())),
        "source_bound_projection_digest": _sha256_json(list(records)),
        "causal_projection_digest": _sha256_json([
            {
                key: value
                for key, value in record.items()
                if key != "source_bound_projection_sha256"
            }
            for record in records
        ]),
    }


def _empty_audit(
    source: Mapping[str, Any],
    *,
    minimum_sample_count: int,
    status: str,
    input_row_count: int = 0,
    input_rejected_count: int = 0,
    input_rejection_reason_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    feature_coverage = {
        feature: _feature_coverage(
            feature,
            (),
            minimum_sample_count=minimum_sample_count,
        )
        for feature in _FEATURES
    }
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_history": dict(source),
        "shadow_schema_id": market_shadow_surprise.SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID,
        "shadow_schema_version": market_shadow_surprise.SHADOW_TEMPORAL_SURPRISE_SCHEMA_VERSION,
        "minimum_sample_count": minimum_sample_count,
        "input_row_count": input_row_count,
        "excluded_not_baseline_counted_count": 0,
        "input_rejected_count": input_rejected_count,
        "input_rejection_reason_counts": dict(
            sorted((input_rejection_reason_counts or {}).items())
        ),
        "valid_baseline_counted_row_count": 0,
        "evaluated_observation_count": 0,
        "evaluation_error_count": 0,
        "evaluation_error_reason_counts": {},
        "projection_status_counts": {},
        "return_status_counts": {},
        "feature_coverage": feature_coverage,
        "asset_projection_summaries": [],
        "asset_variation_summaries": [],
        "asset_count": 0,
        "source_bound_projection_digest": _sha256_json([]),
        "causal_projection_digest": _sha256_json([]),
        "all_features_have_ready_evidence": False,
        "statistical_independence_claimed": False,
        "routing_eligible": False,
        "priority_eligible": False,
        "score_adjustment_eligible": False,
        "decision_score_eligible": False,
        "threshold_change_eligible": False,
        "publication_authority": False,
        "protocol_v2_evidence_eligible": False,
        "auto_apply": False,
        "historical_rows_rewritten": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _source_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    status = snapshot.get("status")
    return {
        "status": status if status in _SOURCE_STATUSES else "unavailable",
        "artifact": snapshot.get("artifact") if _identity(snapshot.get("artifact")) else None,
        "sha256": snapshot.get("sha256") if _sha256(snapshot.get("sha256")) else None,
        "size_bytes": snapshot.get("size_bytes") if _nonnegative_int(snapshot.get("size_bytes")) else 0,
        "row_count": snapshot.get("row_count") if _nonnegative_int(snapshot.get("row_count")) else 0,
        "binding_source": (
            snapshot.get("binding_source")
            if _identity(snapshot.get("binding_source"))
            else "campaign_market_history_path"
        ),
    }


def _audit_status(
    *,
    source_status: str,
    input_row_count: int,
    evaluated_count: int,
    rejected_count: int,
    evaluation_error_count: int,
    all_features_ready: bool,
) -> str:
    if source_status not in {"observed", "observed_empty"}:
        return "unavailable"
    if input_row_count == 0:
        return "empty"
    if evaluated_count == 0:
        return "unavailable"
    if rejected_count or evaluation_error_count:
        return "partial"
    return "ready" if all_features_ready else "warming"


def _validate_source(source: Mapping[str, Any], *, errors: list[str]) -> None:
    _exact_keys(source, _SOURCE_KEYS, "source_history", errors)
    if source.get("status") not in _SOURCE_STATUSES:
        errors.append("source_history_status_invalid")
    if source.get("artifact") is not None and not _identity(source.get("artifact")):
        errors.append("source_history_artifact_invalid")
    if source.get("sha256") is not None and not _sha256(source.get("sha256")):
        errors.append("source_history_sha256_invalid")
    for field in ("size_bytes", "row_count"):
        if not _nonnegative_int(source.get(field)):
            errors.append(f"source_history_{field}_invalid")
    if not _identity(source.get("binding_source")):
        errors.append("source_history_binding_source_invalid")
    if source.get("status") in {"observed", "observed_empty"}:
        if source.get("artifact") is None:
            errors.append("observed_source_artifact_missing")
        if source.get("sha256") is None:
            errors.append("observed_source_sha256_missing")


def _validated_counts(
    value: Mapping[str, Any],
    *,
    errors: list[str],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for field in (
        "input_row_count",
        "excluded_not_baseline_counted_count",
        "input_rejected_count",
        "valid_baseline_counted_row_count",
        "evaluated_observation_count",
        "evaluation_error_count",
    ):
        raw = value.get(field)
        if not _nonnegative_int(raw):
            errors.append(f"{field}_invalid")
        else:
            result[field] = raw
    return result


def _reason_counts(
    raw: Any,
    *,
    allowed: set[str],
    label: str,
    errors: list[str],
) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        errors.append(f"{label}_reason_counts_invalid")
        return {}
    result: dict[str, int] = {}
    for reason, count in raw.items():
        if reason not in allowed:
            errors.append(f"{label}_reason_invalid")
        if not _positive_int(count):
            errors.append(f"{label}_reason_count_invalid")
        else:
            result[str(reason)] = count
    return result


def _validate_feature_coverage(
    feature: str,
    coverage: Any,
    *,
    schema_version: int,
    evaluated_count: int,
    minimum_sample_count: int | None,
    errors: list[str],
) -> None:
    if not isinstance(coverage, Mapping):
        errors.append(f"feature_coverage_{feature}_invalid")
        return
    expected_keys = (
        _FEATURE_COVERAGE_KEYS_V1
        if schema_version == 1
        else _FEATURE_COVERAGE_KEYS_V2
        if schema_version == 2
        else _FEATURE_COVERAGE_KEYS
    )
    _exact_keys(coverage, expected_keys, f"feature_{feature}", errors)
    if coverage.get("feature") != feature:
        errors.append(f"feature_coverage_{feature}_identity_invalid")
    if coverage.get("family") != _FEATURE_FAMILIES[feature]:
        errors.append(f"feature_coverage_{feature}_family_invalid")
    if coverage.get("evaluated_observation_count") != evaluated_count:
        errors.append(f"feature_coverage_{feature}_evaluation_count_mismatch")
    if coverage.get("minimum_sample_count") != minimum_sample_count:
        errors.append(f"feature_coverage_{feature}_minimum_mismatch")
    ready_count = coverage.get("ready_count")
    if not _nonnegative_int(ready_count) or ready_count > evaluated_count:
        errors.append(f"feature_coverage_{feature}_ready_count_invalid")
    _validate_status_counts(
        coverage.get("status_counts"),
        expected_total=evaluated_count,
        label=f"feature_{feature}",
        errors=errors,
    )
    status_counts = coverage.get("status_counts")
    if isinstance(status_counts, Mapping) and ready_count != status_counts.get(
        "ready", 0
    ):
        errors.append(f"feature_coverage_{feature}_ready_count_mismatch")
    minimum = coverage.get("minimum_eligible_sample_count")
    maximum = coverage.get("maximum_eligible_sample_count")
    if evaluated_count == 0:
        if minimum is not None or maximum is not None:
            errors.append(f"feature_coverage_{feature}_sample_range_invalid")
    elif (
        not _nonnegative_int(minimum)
        or not _nonnegative_int(maximum)
        or minimum > maximum
    ):
        errors.append(f"feature_coverage_{feature}_sample_range_invalid")
    first = coverage.get("first_ready_observation")
    last = coverage.get("last_ready_observation")
    if (ready_count == 0) != (first is None and last is None):
        errors.append(f"feature_coverage_{feature}_ready_reference_mismatch")
    for label, reference in (("first", first), ("last", last)):
        if reference is not None and not _valid_reference(reference):
            errors.append(f"feature_coverage_{feature}_{label}_reference_invalid")
    if schema_version >= 2:
        _validate_feature_distribution(
            feature,
            coverage,
            ready_count=ready_count if _nonnegative_int(ready_count) else 0,
            errors=errors,
        )
    if schema_version >= 3:
        _validate_feature_variation(
            feature,
            coverage,
            evaluated_count=evaluated_count,
            minimum_sample_count=minimum_sample_count,
            maximum_sample_count=(
                maximum if _nonnegative_int(maximum) else None
            ),
            errors=errors,
        )
    if not _sha256(coverage.get("projection_digest")):
        errors.append(f"feature_coverage_{feature}_projection_digest_invalid")


def _validate_feature_distribution(
    feature: str,
    coverage: Mapping[str, Any],
    *,
    ready_count: int,
    errors: list[str],
) -> None:
    prefix = f"feature_coverage_{feature}"
    expected_tail_kind = (
        "upper"
        if feature in market_shadow_surprise.SUPPORTED_FEATURES
        else "two_sided"
    )
    if coverage.get("descriptive_quantile_method") != DESCRIPTIVE_QUANTILE_METHOD:
        errors.append(f"{prefix}_quantile_method_invalid")
    if coverage.get("descriptive_tail_rank_kind") != expected_tail_kind:
        errors.append(f"{prefix}_tail_rank_kind_invalid")
    if coverage.get("tail_ranks_are_p_values") is not False:
        errors.append(f"{prefix}_tail_rank_p_value_claim_invalid")
    if coverage.get("overlapping_samples_are_independent") is not False:
        errors.append(f"{prefix}_independence_claim_invalid")
    if coverage.get("distribution_ready_count") != ready_count:
        errors.append(f"{prefix}_distribution_ready_count_mismatch")

    robust_fields = (
        "robust_z_minimum",
        "robust_z_p05",
        "robust_z_median",
        "robust_z_p95",
        "robust_z_maximum",
    )
    tail_fields = (
        "descriptive_tail_rank_minimum",
        "descriptive_tail_rank_p05",
        "descriptive_tail_rank_median",
        "descriptive_tail_rank_p95",
        "descriptive_tail_rank_maximum",
    )
    reference_fields = (
        "minimum_robust_z_observation",
        "maximum_robust_z_observation",
        "minimum_descriptive_tail_rank_observation",
        "maximum_descriptive_tail_rank_observation",
    )
    if ready_count == 0:
        if any(
            coverage.get(field) is not None
            for field in (*robust_fields, *tail_fields, *reference_fields)
        ):
            errors.append(f"{prefix}_empty_distribution_not_null")
        return

    robust_values = [_finite_float_or_none(coverage.get(field)) for field in robust_fields]
    if any(value is None for value in robust_values):
        errors.append(f"{prefix}_robust_z_distribution_invalid")
    elif robust_values != sorted(robust_values):
        errors.append(f"{prefix}_robust_z_distribution_order_invalid")
    tail_values = [_finite_float_or_none(coverage.get(field)) for field in tail_fields]
    if any(
        value is None or not 0.0 < value <= 1.0
        for value in tail_values
    ):
        errors.append(f"{prefix}_tail_rank_distribution_invalid")
    elif tail_values != sorted(tail_values):
        errors.append(f"{prefix}_tail_rank_distribution_order_invalid")
    for field in reference_fields:
        if not _valid_extreme_reference(coverage.get(field)):
            errors.append(f"{prefix}_{field}_invalid")


def _validate_feature_variation(
    feature: str,
    coverage: Mapping[str, Any],
    *,
    evaluated_count: int,
    minimum_sample_count: int | None,
    maximum_sample_count: int | None,
    errors: list[str],
) -> None:
    prefix = f"feature_coverage_{feature}"
    if coverage.get("variation_observation_basis") != VARIATION_OBSERVATION_BASIS:
        errors.append(f"{prefix}_variation_basis_invalid")
    if coverage.get("variation_quantile_method") != VARIATION_QUANTILE_METHOD:
        errors.append(f"{prefix}_variation_quantile_method_invalid")
    if coverage.get("minimum_distinct_baseline_value_count") is not None:
        errors.append(f"{prefix}_minimum_distinct_policy_must_be_null")
    if coverage.get("variation_diagnostics_are_policy") is not False:
        errors.append(f"{prefix}_variation_policy_claim_invalid")
    if coverage.get("effective_sample_size_claimed") is not False:
        errors.append(f"{prefix}_effective_sample_claim_invalid")

    count = coverage.get("variation_observation_count")
    if not _nonnegative_int(count) or count > evaluated_count:
        errors.append(f"{prefix}_variation_observation_count_invalid")
        count = 0
    distinct_count_fields = (
        "distinct_baseline_value_count_minimum",
        "distinct_baseline_value_count_median",
        "distinct_baseline_value_count_maximum",
    )
    distinct_ratio_fields = (
        "distinct_baseline_value_ratio_minimum",
        "distinct_baseline_value_ratio_p05",
        "distinct_baseline_value_ratio_median",
        "distinct_baseline_value_ratio_p95",
        "distinct_baseline_value_ratio_maximum",
    )
    maximum_tie_ratio_fields = (
        "maximum_baseline_value_tie_ratio_minimum",
        "maximum_baseline_value_tie_ratio_p05",
        "maximum_baseline_value_tie_ratio_median",
        "maximum_baseline_value_tie_ratio_p95",
        "maximum_baseline_value_tie_ratio_maximum",
    )
    reference_fields = (
        "minimum_distinct_baseline_value_ratio_observation",
        "maximum_baseline_value_tie_ratio_observation",
    )
    maximum_tie_count = coverage.get(
        "maximum_baseline_value_tie_count_maximum"
    )
    if count == 0:
        if any(
            coverage.get(field) is not None
            for field in (
                *distinct_count_fields,
                *distinct_ratio_fields,
                *maximum_tie_ratio_fields,
                *reference_fields,
                "maximum_baseline_value_tie_count_maximum",
            )
        ):
            errors.append(f"{prefix}_empty_variation_distribution_not_null")
        return

    distinct_count_values = [
        _finite_float_or_none(coverage.get(field))
        for field in distinct_count_fields
    ]
    if any(
        value is None or value < 1.0
        for value in distinct_count_values
    ):
        errors.append(f"{prefix}_distinct_count_distribution_invalid")
    elif distinct_count_values != sorted(distinct_count_values):
        errors.append(f"{prefix}_distinct_count_distribution_order_invalid")
    elif (
        maximum_sample_count is not None
        and distinct_count_values[-1] > maximum_sample_count
    ):
        errors.append(f"{prefix}_distinct_count_exceeds_sample_count")

    distinct_ratio_values = [
        _finite_float_or_none(coverage.get(field))
        for field in distinct_ratio_fields
    ]
    if any(
        value is None or not 0.0 < value <= 1.0
        for value in distinct_ratio_values
    ):
        errors.append(f"{prefix}_distinct_ratio_distribution_invalid")
    elif distinct_ratio_values != sorted(distinct_ratio_values):
        errors.append(f"{prefix}_distinct_ratio_distribution_order_invalid")

    maximum_tie_ratio_values = [
        _finite_float_or_none(coverage.get(field))
        for field in maximum_tie_ratio_fields
    ]
    if any(
        value is None or not 0.0 < value <= 1.0
        for value in maximum_tie_ratio_values
    ):
        errors.append(f"{prefix}_maximum_tie_ratio_distribution_invalid")
    elif maximum_tie_ratio_values != sorted(maximum_tie_ratio_values):
        errors.append(f"{prefix}_maximum_tie_ratio_distribution_order_invalid")

    if (
        not _positive_int(maximum_tie_count)
        or (
            maximum_sample_count is not None
            and maximum_tie_count > maximum_sample_count
        )
    ):
        errors.append(f"{prefix}_maximum_tie_count_invalid")

    minimum_distinct_reference = coverage.get(reference_fields[0])
    maximum_tie_reference = coverage.get(reference_fields[1])
    for label, reference in (
        ("minimum_distinct_ratio", minimum_distinct_reference),
        ("maximum_tie_ratio", maximum_tie_reference),
    ):
        if not _valid_variation_reference(reference):
            errors.append(f"{prefix}_{label}_reference_invalid")
        elif (
            minimum_sample_count is not None
            and reference.get("sample_count") < minimum_sample_count
        ):
            errors.append(f"{prefix}_{label}_reference_below_minimum_sample")
    if (
        _valid_variation_reference(minimum_distinct_reference)
        and distinct_ratio_values
        and distinct_ratio_values[0] is not None
        and minimum_distinct_reference.get("distinct_baseline_value_ratio")
        != distinct_ratio_values[0]
    ):
        errors.append(f"{prefix}_minimum_distinct_ratio_reference_mismatch")
    if (
        _valid_variation_reference(maximum_tie_reference)
        and maximum_tie_ratio_values
        and maximum_tie_ratio_values[-1] is not None
        and maximum_tie_reference.get("maximum_baseline_value_tie_ratio")
        != maximum_tie_ratio_values[-1]
    ):
        errors.append(f"{prefix}_maximum_tie_ratio_reference_mismatch")


def _validate_asset_summaries(
    summaries: Sequence[Any],
    *,
    evaluated_count: int,
    errors: list[str],
) -> None:
    asset_ids: list[str] = []
    total = 0
    for index, summary in enumerate(summaries):
        if not isinstance(summary, Mapping):
            errors.append("asset_projection_summary_invalid")
            continue
        _exact_keys(summary, _ASSET_SUMMARY_KEYS, f"asset_summary_{index}", errors)
        asset_id = _identity(summary.get("canonical_asset_id"))
        if not asset_id:
            errors.append("asset_projection_summary_identity_invalid")
        else:
            asset_ids.append(asset_id)
        count = summary.get("evaluated_observation_count")
        if not _positive_int(count):
            errors.append("asset_projection_summary_count_invalid")
            count = 0
        total += count
        for field in ("first_observation", "last_observation"):
            if not _valid_reference(summary.get(field)):
                errors.append(f"asset_projection_summary_{field}_invalid")
        for field in (
            "first_source_bound_projection_sha256",
            "last_source_bound_projection_sha256",
            "first_causal_projection_sha256",
            "last_causal_projection_sha256",
            "source_bound_projection_digest",
            "causal_projection_digest",
        ):
            if not _sha256(summary.get(field)):
                errors.append(f"asset_projection_summary_{field}_invalid")
        _validate_status_counts(
            summary.get("projection_status_counts"),
            expected_total=count,
            label="asset_projection",
            errors=errors,
        )
    if asset_ids != sorted(set(asset_ids)):
        errors.append("asset_projection_summary_order_or_uniqueness_invalid")
    if total != evaluated_count:
        errors.append("asset_projection_summary_count_mismatch")


def _validate_asset_variation_summaries(
    summaries: Any,
    *,
    asset_summaries: Sequence[Any],
    minimum_sample_count: int | None,
    errors: list[str],
) -> None:
    if not isinstance(summaries, list):
        errors.append("asset_variation_summaries_invalid")
        return
    expected_assets = {
        str(summary.get("canonical_asset_id")): summary
        for summary in asset_summaries
        if isinstance(summary, Mapping)
        and _identity(summary.get("canonical_asset_id"))
    }
    observed_asset_ids: list[str] = []
    for index, summary in enumerate(summaries):
        if not isinstance(summary, Mapping):
            errors.append("asset_variation_summary_invalid")
            continue
        prefix = f"asset_variation_{index}"
        _exact_keys(summary, _ASSET_VARIATION_SUMMARY_KEYS, prefix, errors)
        asset_id = _identity(summary.get("canonical_asset_id"))
        if not asset_id:
            errors.append(f"{prefix}_identity_invalid")
        else:
            observed_asset_ids.append(asset_id)
        expected = expected_assets.get(asset_id)
        evaluated_count = summary.get("evaluated_observation_count")
        if (
            not _positive_int(evaluated_count)
            or not isinstance(expected, Mapping)
            or evaluated_count != expected.get("evaluated_observation_count")
        ):
            errors.append(f"{prefix}_evaluated_count_invalid")
            evaluated_count = 0
        retained_count = summary.get("retained_context_observation_count")
        if (
            not _positive_int(retained_count)
            or retained_count < evaluated_count
        ):
            errors.append(f"{prefix}_retained_context_count_invalid")
            retained_count = 0
        for field, expected_field in (
            ("first_evaluated_observation", "first_observation"),
            ("last_evaluated_observation", "last_observation"),
        ):
            reference = summary.get(field)
            if (
                not _valid_reference(reference)
                or not isinstance(expected, Mapping)
                or reference != expected.get(expected_field)
            ):
                errors.append(f"{prefix}_{field}_invalid")
        for field in (
            "retained_symbol_counts",
            "retained_provider_counts",
            "retained_data_mode_counts",
        ):
            _validate_bounded_context_counts(
                summary.get(field),
                expected_total=retained_count,
                label=f"{prefix}_{field}",
                errors=errors,
            )
        basis_counts = summary.get("retained_feature_basis_counts")
        if (
            not isinstance(basis_counts, Mapping)
            or set(basis_counts) != _RETAINED_FEATURE_BASIS_KEYS
        ):
            errors.append(f"{prefix}_feature_basis_keys_invalid")
            basis_counts = {}
        for feature in sorted(_RETAINED_FEATURE_BASIS_KEYS):
            _validate_bounded_context_counts(
                basis_counts.get(feature),
                expected_total=retained_count,
                label=f"{prefix}_{feature}_basis",
                errors=errors,
            )
        if summary.get("source_context_is_causal_attribution") is not False:
            errors.append(f"{prefix}_source_attribution_claim_invalid")

        feature_variation = summary.get("feature_variation")
        if (
            not isinstance(feature_variation, Mapping)
            or set(feature_variation) != set(_FEATURES)
        ):
            errors.append(f"{prefix}_feature_variation_keys_invalid")
            feature_variation = {}
        repeated_features: list[str] = []
        for feature in _FEATURES:
            feature_summary = feature_variation.get(feature)
            _validate_asset_feature_variation(
                asset_id,
                feature,
                feature_summary,
                evaluated_count=evaluated_count,
                minimum_sample_count=minimum_sample_count,
                errors=errors,
            )
            if (
                isinstance(feature_summary, Mapping)
                and _positive_int(
                    feature_summary.get(
                        "repeated_baseline_value_observation_count"
                    )
                )
            ):
                repeated_features.append(feature)
        declared_repeated = summary.get(
            "features_with_repeated_baseline_values"
        )
        if declared_repeated != sorted(repeated_features):
            errors.append(f"{prefix}_repeated_feature_names_invalid")
        if summary.get("feature_with_repeated_baseline_value_count") != len(
            repeated_features
        ):
            errors.append(f"{prefix}_repeated_feature_count_invalid")
        if not _sha256(summary.get("projection_digest")):
            errors.append(f"{prefix}_projection_digest_invalid")
        for field in (
            "routing_eligible",
            "score_adjustment_eligible",
            "threshold_change_eligible",
            "protocol_v2_evidence_eligible",
        ):
            if summary.get(field) is not False:
                errors.append(f"{prefix}_{field}_must_be_false")
        if summary.get("research_only") is not True:
            errors.append(f"{prefix}_research_only_must_be_true")
    if observed_asset_ids != sorted(expected_assets):
        errors.append("asset_variation_summary_order_or_identity_invalid")


def _validate_asset_feature_variation(
    asset_id: str,
    feature: str,
    summary: Any,
    *,
    evaluated_count: int,
    minimum_sample_count: int | None,
    errors: list[str],
) -> None:
    prefix = f"asset_variation_{asset_id}_{feature}"
    if not isinstance(summary, Mapping):
        errors.append(f"{prefix}_invalid")
        return
    _exact_keys(summary, _ASSET_FEATURE_VARIATION_KEYS, prefix, errors)
    if summary.get("feature") != feature:
        errors.append(f"{prefix}_identity_invalid")
    if summary.get("family") != _FEATURE_FAMILIES[feature]:
        errors.append(f"{prefix}_family_invalid")
    if summary.get("evaluated_observation_count") != evaluated_count:
        errors.append(f"{prefix}_evaluated_count_invalid")
    if summary.get("minimum_sample_count") != minimum_sample_count:
        errors.append(f"{prefix}_minimum_sample_count_invalid")
    variation_count = summary.get("variation_observation_count")
    repeated_count = summary.get("repeated_baseline_value_observation_count")
    all_distinct_count = summary.get(
        "all_distinct_baseline_value_observation_count"
    )
    if (
        not _nonnegative_int(variation_count)
        or variation_count > evaluated_count
        or not _nonnegative_int(repeated_count)
        or not _nonnegative_int(all_distinct_count)
        or repeated_count + all_distinct_count != variation_count
    ):
        errors.append(f"{prefix}_counts_invalid")
        variation_count = 0
        repeated_count = 0
    expected_share = (
        _rounded_ratio(repeated_count, variation_count)
        if variation_count
        else None
    )
    if summary.get("descriptive_repetition_observation_share") != expected_share:
        errors.append(f"{prefix}_repetition_share_invalid")

    distribution_fields = (
        "distinct_baseline_value_ratio_minimum",
        "distinct_baseline_value_ratio_median",
        "maximum_baseline_value_tie_ratio_median",
        "maximum_baseline_value_tie_ratio_maximum",
    )
    reference_fields = (
        "latest_variation_observation",
        "minimum_distinct_baseline_value_ratio_observation",
        "maximum_baseline_value_tie_ratio_observation",
    )
    if variation_count == 0:
        if any(
            summary.get(field) is not None
            for field in (*distribution_fields, *reference_fields)
        ):
            errors.append(f"{prefix}_empty_distribution_not_null")
    else:
        minimum_distinct = _finite_float_or_none(
            summary.get("distinct_baseline_value_ratio_minimum")
        )
        median_distinct = _finite_float_or_none(
            summary.get("distinct_baseline_value_ratio_median")
        )
        median_tie = _finite_float_or_none(
            summary.get("maximum_baseline_value_tie_ratio_median")
        )
        maximum_tie = _finite_float_or_none(
            summary.get("maximum_baseline_value_tie_ratio_maximum")
        )
        if (
            minimum_distinct is None
            or median_distinct is None
            or not 0.0 < minimum_distinct <= median_distinct <= 1.0
        ):
            errors.append(f"{prefix}_distinct_distribution_invalid")
        if (
            median_tie is None
            or maximum_tie is None
            or not 0.0 < median_tie <= maximum_tie <= 1.0
        ):
            errors.append(f"{prefix}_tie_distribution_invalid")
        for field in reference_fields:
            reference = summary.get(field)
            if not _valid_variation_reference(reference):
                errors.append(f"{prefix}_{field}_invalid")
            elif (
                minimum_sample_count is not None
                and reference.get("sample_count") < minimum_sample_count
            ):
                errors.append(f"{prefix}_{field}_below_minimum_sample")
        minimum_reference = summary.get(reference_fields[1])
        maximum_reference = summary.get(reference_fields[2])
        if (
            _valid_variation_reference(minimum_reference)
            and minimum_reference.get("distinct_baseline_value_ratio")
            != minimum_distinct
        ):
            errors.append(f"{prefix}_minimum_reference_mismatch")
        if (
            _valid_variation_reference(maximum_reference)
            and maximum_reference.get("maximum_baseline_value_tie_ratio")
            != maximum_tie
        ):
            errors.append(f"{prefix}_maximum_reference_mismatch")
    if summary.get("minimum_distinct_baseline_value_count") is not None:
        errors.append(f"{prefix}_minimum_distinct_policy_must_be_null")
    for field in (
        "variation_diagnostics_are_policy",
        "effective_sample_size_claimed",
        "overlapping_reference_sets_are_independent",
    ):
        if summary.get(field) is not False:
            errors.append(f"{prefix}_{field}_must_be_false")
    if not _sha256(summary.get("projection_digest")):
        errors.append(f"{prefix}_projection_digest_invalid")


def _validate_bounded_context_counts(
    raw: Any,
    *,
    expected_total: int,
    label: str,
    errors: list[str],
) -> None:
    if (
        not isinstance(raw, Mapping)
        or len(raw) > 64
        or any(
            not isinstance(key, str)
            or not key
            or len(key) > 200
            or any(ord(character) < 32 for character in key)
            for key in raw
        )
    ):
        errors.append(f"{label}_bounded_identity_invalid")
    _validate_status_counts(
        raw,
        expected_total=expected_total,
        label=label,
        errors=errors,
    )


def _validate_status_counts(
    raw: Any,
    *,
    expected_total: int,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(raw, Mapping):
        errors.append(f"{label}_counts_invalid")
        return
    total = 0
    for status, count in raw.items():
        if not _identity(status) or not _positive_int(count):
            errors.append(f"{label}_count_invalid")
            continue
        total += count
    if total != expected_total:
        errors.append(f"{label}_count_total_mismatch")


def _reference(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "observation_id": str(row["observation_id"]),
        "observed_at": str(row["observed_at"]),
    }


def _valid_reference(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == _REFERENCE_KEYS
        and bool(_identity(value.get("observation_id")))
        and _aware_time_or_none(value.get("observed_at")) is not None
    )


def _valid_extreme_reference(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == _EXTREME_REFERENCE_KEYS
        and bool(_identity(value.get("canonical_asset_id")))
        and bool(_identity(value.get("observation_id")))
        and _aware_time_or_none(value.get("observed_at")) is not None
    )


def _valid_variation_reference(value: Any) -> bool:
    if (
        not isinstance(value, Mapping)
        or set(value) != _VARIATION_REFERENCE_KEYS
        or not _valid_extreme_reference({
            key: value.get(key) for key in _EXTREME_REFERENCE_KEYS
        })
    ):
        return False
    sample_count = value.get("sample_count")
    distinct_count = value.get("distinct_baseline_value_count")
    maximum_tie_count = value.get("maximum_baseline_value_tie_count")
    distinct_ratio = _finite_float_or_none(
        value.get("distinct_baseline_value_ratio")
    )
    maximum_tie_ratio = _finite_float_or_none(
        value.get("maximum_baseline_value_tie_ratio")
    )
    return bool(
        _positive_int(sample_count)
        and _positive_int(distinct_count)
        and distinct_count <= sample_count
        and _positive_int(maximum_tie_count)
        and maximum_tie_count <= sample_count
        and distinct_ratio == _rounded_ratio(distinct_count, sample_count)
        and maximum_tie_ratio == _rounded_ratio(
            maximum_tie_count, sample_count
        )
    )


def _parse_aware_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TypeError("timestamp must be a non-empty string")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _aware_time_or_none(value: Any) -> datetime | None:
    try:
        return _parse_aware_utc(value)
    except (TypeError, ValueError):
        return None


def _identity(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _finite_float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
    errors: list[str],
) -> None:
    if set(value) != expected:
        errors.append(f"{label}_keys_invalid")


def _assert_valid(value: Mapping[str, Any]) -> None:
    errors = validate_campaign_shadow_surprise_audit(value)
    if errors:
        raise AssertionError(
            "campaign shadow-surprise audit invalid: " + ";".join(errors)
        )


__all__ = (
    "LEGACY_SCHEMA_VERSIONS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "VARIATION_OBSERVATION_BASIS",
    "VARIATION_QUANTILE_METHOD",
    "build_campaign_shadow_surprise_audit",
    "validate_campaign_shadow_surprise_audit",
)
