"""Pure shadow-only robust temporal surprise for direct market features.

This module deliberately does not feed routing, priority, or scores. It surveys
already-supplied observations and emits a bounded, closed, JSON-safe research
value for later calibration work.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from numbers import Real
from typing import Any


SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID = "event_alpha.shadow_temporal_surprise"
SHADOW_TEMPORAL_SURPRISE_SCHEMA_VERSION = 2
SUPPORTED_FEATURES = ("volume_24h", "turnover_24h")
RETURN_HORIZONS_HOURS = (1, 4, 24)
RETURN_BENCHMARKS = ("btc", "eth")
SUPPORTED_RETURN_FEATURES = (
    *(f"return_{hours}h" for hours in RETURN_HORIZONS_HOURS),
    *(
        f"relative_return_vs_{benchmark}_{hours}h"
        for benchmark in RETURN_BENCHMARKS
        for hours in RETURN_HORIZONS_HOURS
    ),
)
BENCHMARK_ASSET_IDS = {
    "btc": ("bitcoin", "btc"),
    "eth": ("ethereum", "eth"),
}
ELIGIBLE_FEATURE_BASES = frozenset(("provider_observed", "derived_provider_ratio"))
ELIGIBLE_PRICE_BASIS = "provider_observed"
DIRECT_RETURN_BASIS = "provider_observed_price_ratio"
RELATIVE_RETURN_BASIS = "provider_observed_asset_return_minus_provider_observed_benchmark_return"
RETURN_UNIT = "percent_points"
MAD_NORMAL_CONSISTENCY_FACTOR = 1.482602218505602
MAD_DEGENERATE_THRESHOLD = 1e-12
DERIVED_FLOAT_DECIMAL_PLACES = 12
DERIVED_RATIO_REL_TOLERANCE = 1e-9
DERIVED_RATIO_ABS_TOLERANCE = 1e-12
RETURN_ANCHOR_TOLERANCE_RATIO = 0.25
RETURN_MIN_ANCHOR_TOLERANCE_SECONDS = 300
BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS = 300

_TOP_LEVEL_VALUE_KEYS = frozenset(
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
        "return_status",
        "return_method",
        "return_features",
        "routing_eligible",
        "priority_eligible",
        "score_adjustment_eligible",
        "decision_score_eligible",
        "auto_apply",
        "research_only",
    )
)
_RETURN_METHOD_VALUE_KEYS = frozenset(
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
_METHOD_VALUE_KEYS = frozenset(
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
_RETURN_FEATURE_VALUE_KEYS = frozenset(
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
_RETURN_SAMPLE_VALUE_KEYS = frozenset(
    (
        "asset_endpoint",
        "asset_anchor",
        "benchmark_endpoint",
        "benchmark_anchor",
    )
)


@dataclass(frozen=True)
class _DirectReturnSample:
    value: float
    endpoint: Mapping[str, Any]
    anchor: Mapping[str, Any]


@dataclass(frozen=True)
class _RelativeReturnSample:
    value: float
    asset_endpoint: Mapping[str, Any]
    asset_anchor: Mapping[str, Any]
    benchmark_endpoint: Mapping[str, Any]
    benchmark_anchor: Mapping[str, Any]


_FEATURE_VALUE_KEYS = frozenset(
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


def evaluate_shadow_temporal_surprise(
    current_observation: Mapping[str, Any],
    prior_observations: Iterable[Mapping[str, Any]],
    *,
    minimum_sample_count: int,
    history_artifact: str,
    history_sha256: str,
    benchmark_observations: Mapping[
        str, Iterable[Mapping[str, Any]]
    ] | None = None,
) -> dict[str, Any]:
    """Return the closed v2 robust shadow value for activity and return tails.

    Inputs are only read. Proxy, cross-sectional, missing, and otherwise
    unapproved feature bases are explicitly excluded. Non-positive and
    non-finite activity values are never transformed. Signed returns are
    independently rederived from provider-observed prices and preserve their
    exact horizon and benchmark family.
    """

    _validate_inputs(
        current_observation,
        minimum_sample_count,
        history_artifact=history_artifact,
        history_sha256=history_sha256,
    )
    priors = tuple(prior_observations)
    if any(not isinstance(observation, Mapping) for observation in priors):
        raise TypeError("prior_observations must contain only mappings")
    _validate_observation_sequence(current_observation, priors)
    benchmarks = _validated_benchmark_observations(
        current_observation,
        benchmark_observations,
    )

    surveyed_references = sorted(
        (_observation_reference(observation) for observation in priors),
        key=_reference_sort_key,
    )
    features = {
        feature: _evaluate_feature(
            feature,
            current_observation,
            priors,
            minimum_sample_count=minimum_sample_count,
        )
        for feature in SUPPORTED_FEATURES
    }
    return_features = _evaluate_return_features(
        current_observation,
        priors,
        benchmarks,
        minimum_sample_count=minimum_sample_count,
    )
    return_status = _feature_collection_status(
        return_features.values(),
        ignore_statuses={"not_applicable"},
    )
    status = _feature_collection_status(
        (*features.values(), *return_features.values()),
        ignore_statuses={"not_applicable"},
    )

    value = {
        "schema_id": SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID,
        "schema_version": SHADOW_TEMPORAL_SURPRISE_SCHEMA_VERSION,
        "status": status,
        "history_artifact": history_artifact,
        "history_artifact_sha256": history_sha256,
        "current_observation": _observation_reference(current_observation),
        "surveyed_prior_first_observation": surveyed_references[0] if surveyed_references else None,
        "surveyed_prior_last_observation": surveyed_references[-1] if surveyed_references else None,
        "supplied_prior_observation_count": len(priors),
        "minimum_sample_count": minimum_sample_count,
        "method": {
            "transform": "natural_log",
            "location_estimator": "median",
            "scale_estimator": "median_absolute_deviation",
            "normal_consistency_factor": MAD_NORMAL_CONSISTENCY_FACTOR,
            "degenerate_mad_threshold": MAD_DEGENERATE_THRESHOLD,
            "derived_float_decimal_places": DERIVED_FLOAT_DECIMAL_PLACES,
            "derived_ratio_rel_tolerance": DERIVED_RATIO_REL_TOLERANCE,
            "derived_ratio_abs_tolerance": DERIVED_RATIO_ABS_TOLERANCE,
            "upper_tail_rank_definition": (
                "(count(baseline_log >= current_log)+1)/(sample_count+1)"
            ),
            "upper_tail_rank_is_p_value": False,
        },
        "features": features,
        "return_status": return_status,
        "return_method": {
            "transform": "identity_signed",
            "return_unit": RETURN_UNIT,
            "location_estimator": "median",
            "scale_estimator": "median_absolute_deviation",
            "normal_consistency_factor": MAD_NORMAL_CONSISTENCY_FACTOR,
            "degenerate_mad_threshold": MAD_DEGENERATE_THRESHOLD,
            "derived_float_decimal_places": DERIVED_FLOAT_DECIMAL_PLACES,
            "anchor_tolerance_ratio": RETURN_ANCHOR_TOLERANCE_RATIO,
            "minimum_anchor_tolerance_seconds": RETURN_MIN_ANCHOR_TOLERANCE_SECONDS,
            "benchmark_alignment_tolerance_seconds": (
                BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS
            ),
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
        },
        "return_features": return_features,
        "routing_eligible": False,
        "priority_eligible": False,
        "score_adjustment_eligible": False,
        "decision_score_eligible": False,
        "auto_apply": False,
        "research_only": True,
    }
    return _assert_closed_value(value)


def build_shadow_temporal_surprise(
    current_observation: Mapping[str, Any],
    prior_observations: Iterable[Mapping[str, Any]],
    *,
    minimum_sample_count: int,
    history_artifact: str,
    history_sha256: str,
    benchmark_observations: Mapping[
        str, Iterable[Mapping[str, Any]]
    ] | None = None,
) -> dict[str, Any]:
    """Return the namespaced projection used when integration is desired."""

    return {
        "shadow_temporal_surprise": evaluate_shadow_temporal_surprise(
            current_observation,
            prior_observations,
            minimum_sample_count=minimum_sample_count,
            history_artifact=history_artifact,
            history_sha256=history_sha256,
            benchmark_observations=benchmark_observations,
        )
    }


def _feature_collection_status(
    values: Iterable[Mapping[str, Any]],
    *,
    ignore_statuses: set[str],
) -> str:
    relevant = [
        value for value in values
        if str(value.get("status") or "") not in ignore_statuses
    ]
    ready_count = sum(value.get("status") == "ready" for value in relevant)
    if relevant and ready_count == len(relevant):
        return "ready"
    if ready_count:
        return "partial"
    return "unavailable"


def _evaluate_return_features(
    current: Mapping[str, Any],
    priors: tuple[Mapping[str, Any], ...],
    benchmarks: Mapping[str, tuple[Mapping[str, Any], ...]],
    *,
    minimum_sample_count: int,
) -> dict[str, dict[str, Any]]:
    asset_observations = tuple(sorted(
        (*priors, current),
        key=lambda observation: _reference_sort_key(
            _observation_reference(observation)
        ),
    ))
    features: dict[str, dict[str, Any]] = {}
    for hours in RETURN_HORIZONS_HOURS:
        feature = f"return_{hours}h"
        features[feature] = _evaluate_signed_return_feature(
            feature=feature,
            family="direct_return",
            horizon_hours=hours,
            benchmark=None,
            current_result=_direct_return_sample(
                current,
                asset_observations,
                horizon_hours=hours,
            ),
            baseline_results=tuple(
                _direct_return_sample(
                    endpoint,
                    asset_observations,
                    horizon_hours=hours,
                )
                for endpoint in priors
            ),
            minimum_sample_count=minimum_sample_count,
            feature_basis=DIRECT_RETURN_BASIS,
        )
    current_asset = _required_identity(
        current.get("canonical_asset_id"),
        "current canonical_asset_id",
    )
    for benchmark in RETURN_BENCHMARKS:
        benchmark_rows = benchmarks.get(benchmark, ())
        for hours in RETURN_HORIZONS_HOURS:
            feature = f"relative_return_vs_{benchmark}_{hours}h"
            if current_asset.casefold() in {
                asset_id.casefold()
                for asset_id in BENCHMARK_ASSET_IDS[benchmark]
            }:
                features[feature] = _empty_return_feature_value(
                    feature=feature,
                    family=f"relative_return_{benchmark}",
                    horizon_hours=hours,
                    benchmark=benchmark,
                    minimum_sample_count=minimum_sample_count,
                    status="not_applicable",
                    reason="same_asset_benchmark_not_applicable",
                )
                continue
            if not benchmark_rows:
                features[feature] = _empty_return_feature_value(
                    feature=feature,
                    family=f"relative_return_{benchmark}",
                    horizon_hours=hours,
                    benchmark=benchmark,
                    minimum_sample_count=minimum_sample_count,
                    status="benchmark_unavailable",
                    reason="benchmark_history_unavailable",
                    invalid_baseline_count=len(priors),
                )
                continue
            features[feature] = _evaluate_signed_return_feature(
                feature=feature,
                family=f"relative_return_{benchmark}",
                horizon_hours=hours,
                benchmark=benchmark,
                current_result=_relative_return_sample(
                    current,
                    asset_observations,
                    benchmark_rows,
                    horizon_hours=hours,
                ),
                baseline_results=tuple(
                    _relative_return_sample(
                        endpoint,
                        asset_observations,
                        benchmark_rows,
                        horizon_hours=hours,
                    )
                    for endpoint in priors
                ),
                minimum_sample_count=minimum_sample_count,
                feature_basis=RELATIVE_RETURN_BASIS,
            )
    if frozenset(features) != frozenset(SUPPORTED_RETURN_FEATURES):
        raise AssertionError("shadow signed-return feature set drifted from v2")
    return features


def _evaluate_signed_return_feature(
    *,
    feature: str,
    family: str,
    horizon_hours: int,
    benchmark: str | None,
    current_result: tuple[_DirectReturnSample | _RelativeReturnSample | None, str],
    baseline_results: tuple[
        tuple[_DirectReturnSample | _RelativeReturnSample | None, str], ...
    ],
    minimum_sample_count: int,
    feature_basis: str,
) -> dict[str, Any]:
    eligible = [sample for sample, state in baseline_results if state == "eligible" and sample]
    basis_ineligible_count = sum(state == "basis_ineligible" for _, state in baseline_results)
    invalid_count = sum(state == "invalid" for _, state in baseline_results)
    eligible.sort(key=lambda sample: _reference_sort_key(
        _return_sample_endpoint_reference(sample)
    ))
    identities = [
        _return_sample_identity(sample, feature=feature, feature_basis=feature_basis)
        for sample in eligible
    ]
    references = [_return_sample_endpoint_reference(sample) for sample in eligible]
    current_sample, current_state = current_result
    value = _empty_return_feature_value(
        feature=feature,
        family=family,
        horizon_hours=horizon_hours,
        benchmark=benchmark,
        minimum_sample_count=minimum_sample_count,
        sample_count=len(eligible),
        basis_ineligible_baseline_count=basis_ineligible_count,
        invalid_baseline_count=invalid_count,
        eligible_baseline_first_observation=references[0] if references else None,
        eligible_baseline_last_observation=references[-1] if references else None,
        eligible_sample_sha256=_sha256_json(identities),
    )
    if current_state == "basis_ineligible":
        value.update(
            status="basis_ineligible",
            reason="current_price_basis_not_eligible",
        )
        return _assert_closed_return_feature_value(value)
    if current_state != "eligible" or current_sample is None:
        value.update(
            status="current_unavailable",
            reason="current_return_sample_unavailable",
        )
        return _assert_closed_return_feature_value(value)
    value.update(
        current_value=_round_derived(current_sample.value),
        current_sample=_return_sample_projection(current_sample),
        feature_basis=feature_basis,
    )
    if len(eligible) < minimum_sample_count:
        value.update(
            status="insufficient_history",
            reason="minimum_sample_count_not_met",
        )
        return _assert_closed_return_feature_value(value)

    baseline = [sample.value for sample in eligible]
    median = float(statistics.median(baseline))
    mad = float(statistics.median(abs(item - median) for item in baseline))
    consistent_mad = float(mad * MAD_NORMAL_CONSISTENCY_FACTOR)
    current_value = current_sample.value
    lower_tail = (sum(item <= current_value for item in baseline) + 1) / (
        len(baseline) + 1
    )
    upper_tail = (sum(item >= current_value for item in baseline) + 1) / (
        len(baseline) + 1
    )
    two_sided_tail = min(1.0, 2.0 * min(lower_tail, upper_tail))
    value.update(
        median=_round_derived(median),
        mad=_round_derived(mad),
        normal_consistent_mad=_round_derived(consistent_mad),
        lower_tail_rank=_round_derived(lower_tail),
        upper_tail_rank=_round_derived(upper_tail),
        two_sided_tail_rank=_round_derived(two_sided_tail),
    )
    if mad <= MAD_DEGENERATE_THRESHOLD:
        value.update(
            status="degenerate_scale",
            reason="mad_at_or_below_degenerate_threshold",
        )
        return _assert_closed_return_feature_value(value)
    robust_z = float((current_value - median) / consistent_mad)
    if not math.isfinite(robust_z):
        value.update(status="unavailable", reason="non_finite_robust_z")
        return _assert_closed_return_feature_value(value)
    value.update(status="ready", reason=None, robust_z=_round_derived(robust_z))
    return _assert_closed_return_feature_value(value)


def _empty_return_feature_value(
    *,
    feature: str,
    family: str,
    horizon_hours: int,
    benchmark: str | None,
    minimum_sample_count: int,
    status: str = "unavailable",
    reason: str | None = None,
    sample_count: int = 0,
    basis_ineligible_baseline_count: int = 0,
    invalid_baseline_count: int = 0,
    eligible_baseline_first_observation: Mapping[str, str | None] | None = None,
    eligible_baseline_last_observation: Mapping[str, str | None] | None = None,
    eligible_sample_sha256: str | None = None,
) -> dict[str, Any]:
    return _assert_closed_return_feature_value({
        "feature": feature,
        "family": family,
        "horizon_hours": horizon_hours,
        "benchmark": benchmark,
        "status": status,
        "reason": reason,
        "return_unit": RETURN_UNIT,
        "current_value": None,
        "current_sample": None,
        "feature_basis": None,
        "sample_count": sample_count,
        "minimum_sample_count": minimum_sample_count,
        "basis_ineligible_baseline_count": basis_ineligible_baseline_count,
        "invalid_baseline_count": invalid_baseline_count,
        "eligible_baseline_first_observation": eligible_baseline_first_observation,
        "eligible_baseline_last_observation": eligible_baseline_last_observation,
        "eligible_sample_sha256": eligible_sample_sha256 or _sha256_json([]),
        "median": None,
        "mad": None,
        "normal_consistent_mad": None,
        "robust_z": None,
        "lower_tail_rank": None,
        "upper_tail_rank": None,
        "two_sided_tail_rank": None,
        "tail_ranks_are_p_values": False,
    })


def _direct_return_sample(
    endpoint: Mapping[str, Any],
    observations: tuple[Mapping[str, Any], ...],
    *,
    horizon_hours: int,
) -> tuple[_DirectReturnSample | None, str]:
    endpoint_price = _positive_finite_number(endpoint.get("price"))
    if endpoint_price is None:
        return None, "invalid"
    if _feature_basis(endpoint, "price") != ELIGIBLE_PRICE_BASIS:
        return None, "basis_ineligible"
    endpoint_at = _required_aware_time(endpoint.get("observed_at"), "endpoint observed_at")
    target = endpoint_at - timedelta(hours=horizon_hours)
    tolerance = max(
        timedelta(seconds=RETURN_MIN_ANCHOR_TOLERANCE_SECONDS),
        timedelta(hours=horizon_hours * RETURN_ANCHOR_TOLERANCE_RATIO),
    )
    candidates = [
        observation
        for observation in observations
        if (observed_at := _required_aware_time(
            observation.get("observed_at"),
            "anchor observed_at",
        )) <= target
        and target - observed_at <= tolerance
        and _positive_finite_number(observation.get("price")) is not None
    ]
    if not candidates:
        return None, "invalid"
    anchor = max(
        candidates,
        key=lambda observation: _reference_sort_key(
            _observation_reference(observation)
        ),
    )
    if _feature_basis(anchor, "price") != ELIGIBLE_PRICE_BASIS:
        return None, "basis_ineligible"
    anchor_price = _positive_finite_number(anchor.get("price"))
    if anchor_price is None:
        return None, "invalid"
    value = (endpoint_price / anchor_price - 1.0) * 100.0
    if not math.isfinite(value):
        return None, "invalid"
    return _DirectReturnSample(
        value=_round_derived(value),
        endpoint=endpoint,
        anchor=anchor,
    ), "eligible"


def _relative_return_sample(
    asset_endpoint: Mapping[str, Any],
    asset_observations: tuple[Mapping[str, Any], ...],
    benchmark_observations: tuple[Mapping[str, Any], ...],
    *,
    horizon_hours: int,
) -> tuple[_RelativeReturnSample | None, str]:
    asset_sample, asset_state = _direct_return_sample(
        asset_endpoint,
        asset_observations,
        horizon_hours=horizon_hours,
    )
    asset_at = _required_aware_time(
        asset_endpoint.get("observed_at"),
        "asset endpoint observed_at",
    )
    alignment_tolerance = timedelta(
        seconds=BENCHMARK_ALIGNMENT_TOLERANCE_SECONDS
    )
    benchmark_candidates = [
        observation
        for observation in benchmark_observations
        if (observed_at := _required_aware_time(
            observation.get("observed_at"),
            "benchmark observed_at",
        )) <= asset_at
        and asset_at - observed_at <= alignment_tolerance
    ]
    if not benchmark_candidates:
        return None, "invalid"
    benchmark_endpoint = max(
        benchmark_candidates,
        key=lambda observation: _reference_sort_key(
            _observation_reference(observation)
        ),
    )
    benchmark_sample, benchmark_state = _direct_return_sample(
        benchmark_endpoint,
        benchmark_observations,
        horizon_hours=horizon_hours,
    )
    if "basis_ineligible" in {asset_state, benchmark_state}:
        return None, "basis_ineligible"
    if (
        asset_state != "eligible"
        or benchmark_state != "eligible"
        or asset_sample is None
        or benchmark_sample is None
    ):
        return None, "invalid"
    value = asset_sample.value - benchmark_sample.value
    if not math.isfinite(value):
        return None, "invalid"
    return _RelativeReturnSample(
        value=_round_derived(value),
        asset_endpoint=asset_sample.endpoint,
        asset_anchor=asset_sample.anchor,
        benchmark_endpoint=benchmark_sample.endpoint,
        benchmark_anchor=benchmark_sample.anchor,
    ), "eligible"


def _return_sample_endpoint_reference(
    sample: _DirectReturnSample | _RelativeReturnSample,
) -> dict[str, str | None]:
    endpoint = (
        sample.endpoint
        if isinstance(sample, _DirectReturnSample)
        else sample.asset_endpoint
    )
    return _observation_reference(endpoint)


def _return_sample_projection(
    sample: _DirectReturnSample | _RelativeReturnSample,
) -> dict[str, dict[str, str | None] | None]:
    if isinstance(sample, _DirectReturnSample):
        return {
            "asset_endpoint": _observation_reference(sample.endpoint),
            "asset_anchor": _observation_reference(sample.anchor),
            "benchmark_endpoint": None,
            "benchmark_anchor": None,
        }
    return {
        "asset_endpoint": _observation_reference(sample.asset_endpoint),
        "asset_anchor": _observation_reference(sample.asset_anchor),
        "benchmark_endpoint": _observation_reference(sample.benchmark_endpoint),
        "benchmark_anchor": _observation_reference(sample.benchmark_anchor),
    }


def _return_sample_identity(
    sample: _DirectReturnSample | _RelativeReturnSample,
    *,
    feature: str,
    feature_basis: str,
) -> dict[str, Any]:
    projection = _return_sample_projection(sample)
    rows = (
        (sample.endpoint, sample.anchor)
        if isinstance(sample, _DirectReturnSample)
        else (
            sample.asset_endpoint,
            sample.asset_anchor,
            sample.benchmark_endpoint,
            sample.benchmark_anchor,
        )
    )
    return {
        "feature": feature,
        "value": format(sample.value, ".17g"),
        "feature_basis": feature_basis,
        "sample": projection,
        "source_prices": [
            _return_source_price_identity(row)
            for row in rows
        ],
    }


def _return_source_price_identity(row: Mapping[str, Any]) -> dict[str, str | None]:
    price = _positive_finite_number(row.get("price"))
    if price is None:
        raise AssertionError("eligible shadow return sample lost its source price")
    return {
        "observation_id": _observation_reference(row)["observation_id"],
        "canonical_asset_id": _required_identity(
            row.get("canonical_asset_id"),
            "eligible return sample canonical_asset_id",
        ),
        "price": format(price, ".17g"),
        "price_basis": _feature_basis(row, "price"),
    }


def _validated_benchmark_observations(
    current: Mapping[str, Any],
    supplied: Mapping[str, Iterable[Mapping[str, Any]]] | None,
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    if supplied is None:
        return {name: () for name in RETURN_BENCHMARKS}
    if not isinstance(supplied, Mapping):
        raise TypeError("benchmark_observations must be a mapping")
    unknown = set(supplied) - set(RETURN_BENCHMARKS)
    if unknown:
        raise ValueError("benchmark_observations contains an unknown benchmark")
    current_at = _required_aware_time(current.get("observed_at"), "current observed_at")
    result: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for benchmark in RETURN_BENCHMARKS:
        observations = tuple(supplied.get(benchmark, ()))
        if any(not isinstance(observation, Mapping) for observation in observations):
            raise TypeError("benchmark observations must contain only mappings")
        seen_ids: set[str] = set()
        seen_times: set[datetime] = set()
        asset_ids: set[str] = set()
        for observation in observations:
            observation_id = _required_identity(
                observation.get("observation_id"),
                f"{benchmark} benchmark observation_id",
            )
            asset_ids.add(_required_identity(
                observation.get("canonical_asset_id"),
                f"{benchmark} benchmark canonical_asset_id",
            ))
            observed_at = _required_aware_time(
                observation.get("observed_at"),
                f"{benchmark} benchmark observed_at",
            )
            if observation.get("baseline_counted") is not True:
                raise ValueError("benchmark observation must be cadence-counted")
            if observed_at > current_at:
                raise ValueError("benchmark observation cannot be later than current")
            if observation_id in seen_ids or observed_at in seen_times:
                raise ValueError(
                    "benchmark observation identity or timestamp is not unique"
                )
            seen_ids.add(observation_id)
            seen_times.add(observed_at)
        if len(asset_ids) > 1:
            raise ValueError("benchmark observations mix canonical assets")
        expected_asset_ids = {
            asset_id.casefold() for asset_id in BENCHMARK_ASSET_IDS[benchmark]
        }
        normalized_asset_ids = {asset_id.casefold() for asset_id in asset_ids}
        if normalized_asset_ids and not normalized_asset_ids <= expected_asset_ids:
            raise ValueError(
                f"{benchmark} benchmark canonical asset identity is invalid"
            )
        result[benchmark] = tuple(sorted(
            observations,
            key=lambda observation: _reference_sort_key(
                _observation_reference(observation)
            ),
        ))
    return result


def _evaluate_feature(
    feature: str,
    current: Mapping[str, Any],
    priors: tuple[Mapping[str, Any], ...],
    *,
    minimum_sample_count: int,
) -> dict[str, Any]:
    current_value = _positive_finite_number(current.get(feature))
    current_basis = _feature_basis(current, feature)
    eligible: list[tuple[float, dict[str, str | None], dict[str, str | None]]] = []
    basis_ineligible_count = 0
    invalid_value_count = 0
    for observation in priors:
        if not _feature_basis_is_eligible(observation, feature):
            basis_ineligible_count += 1
            continue
        baseline_value = _positive_finite_number(observation.get(feature))
        if baseline_value is None:
            invalid_value_count += 1
            continue
        reference = _observation_reference(observation)
        eligible.append(
            (
                baseline_value,
                reference,
                _sample_identity(observation, feature, baseline_value, reference),
            )
        )
    eligible.sort(key=lambda item: (_reference_sort_key(item[1]), _canonical_json(item[2])))
    references = [reference for _, reference, _ in eligible]
    sample_digest = _sha256_json([identity for _, _, identity in eligible])

    value = _empty_feature_value(
        feature=feature,
        current_value=current_value,
        current_basis=current_basis,
        eligible_references=references,
        eligible_sample_sha256=sample_digest,
        minimum_sample_count=minimum_sample_count,
        basis_ineligible_count=basis_ineligible_count,
        invalid_value_count=invalid_value_count,
    )
    if not _feature_basis_is_eligible(current, feature):
        value.update(status="basis_ineligible", reason="current_feature_basis_not_eligible")
        return _assert_closed_feature_value(value)
    if current_value is None:
        value.update(status="current_unavailable", reason="current_value_not_strictly_positive_finite")
        return _assert_closed_feature_value(value)

    current_log = math.log(current_value)
    value["current_log"] = _round_derived(current_log)
    if len(eligible) < minimum_sample_count:
        value.update(status="insufficient_history", reason="minimum_sample_count_not_met")
        return _assert_closed_feature_value(value)

    baseline_logs = [math.log(item) for item, _, _ in eligible]
    median_log = float(statistics.median(baseline_logs))
    mad_log = float(statistics.median(abs(item - median_log) for item in baseline_logs))
    consistent_mad = float(mad_log * MAD_NORMAL_CONSISTENCY_FACTOR)
    tail_rank = (
        sum(item >= current_log for item in baseline_logs) + 1
    ) / (len(baseline_logs) + 1)
    value.update(
        median_log=_round_derived(median_log),
        mad_log=_round_derived(mad_log),
        normal_consistent_mad_log=_round_derived(consistent_mad),
        upper_tail_rank=_round_derived(tail_rank),
    )
    if mad_log <= MAD_DEGENERATE_THRESHOLD:
        value.update(status="degenerate_scale", reason="mad_at_or_below_degenerate_threshold")
        return _assert_closed_feature_value(value)

    robust_z = float((current_log - median_log) / consistent_mad)
    if not math.isfinite(robust_z):
        value.update(status="unavailable", reason="non_finite_robust_z")
        return _assert_closed_feature_value(value)
    value.update(status="ready", reason=None, robust_z=_round_derived(robust_z))
    return _assert_closed_feature_value(value)


def _empty_feature_value(
    *,
    feature: str,
    current_value: float | None,
    current_basis: str | None,
    eligible_references: list[dict[str, str | None]],
    eligible_sample_sha256: str,
    minimum_sample_count: int,
    basis_ineligible_count: int,
    invalid_value_count: int,
) -> dict[str, Any]:
    return {
        "feature": feature,
        "status": "unavailable",
        "reason": None,
        "current_value": current_value,
        "current_log": None,
        "feature_basis": current_basis,
        "sample_count": len(eligible_references),
        "minimum_sample_count": minimum_sample_count,
        "basis_ineligible_baseline_count": basis_ineligible_count,
        "invalid_baseline_count": invalid_value_count,
        "eligible_baseline_first_observation": (
            eligible_references[0] if eligible_references else None
        ),
        "eligible_baseline_last_observation": (
            eligible_references[-1] if eligible_references else None
        ),
        "eligible_sample_sha256": eligible_sample_sha256,
        "median_log": None,
        "mad_log": None,
        "normal_consistent_mad_log": None,
        "robust_z": None,
        "upper_tail_rank": None,
        "upper_tail_rank_is_p_value": False,
    }


def _feature_basis_is_eligible(observation: Mapping[str, Any], feature: str) -> bool:
    basis = _feature_basis(observation, feature)
    if feature == "volume_24h":
        return basis == "provider_observed"
    if feature == "turnover_24h":
        if basis == "provider_observed":
            return True
        if (
            basis != "derived_provider_ratio"
            or _feature_basis(observation, "volume_24h") != "provider_observed"
            or _feature_basis(observation, "market_cap") != "provider_observed"
        ):
            return False
        turnover = _positive_finite_number(observation.get("turnover_24h"))
        volume = _positive_finite_number(observation.get("volume_24h"))
        market_cap = _positive_finite_number(observation.get("market_cap"))
        return (
            turnover is not None
            and volume is not None
            and market_cap is not None
            and math.isclose(
                turnover,
                volume / market_cap,
                rel_tol=DERIVED_RATIO_REL_TOLERANCE,
                abs_tol=DERIVED_RATIO_ABS_TOLERANCE,
            )
        )
    return False


def _feature_basis(observation: Mapping[str, Any], feature: str) -> str | None:
    feature_basis = observation.get("feature_basis")
    if isinstance(feature_basis, Mapping):
        raw_basis = feature_basis.get(feature)
    else:
        raw_basis = observation.get(f"{feature}_basis")
    if not isinstance(raw_basis, str) or not raw_basis.strip():
        return None
    return raw_basis.strip().casefold()


def _sample_identity(
    observation: Mapping[str, Any],
    feature: str,
    value: float,
    reference: Mapping[str, str | None],
) -> dict[str, str | None]:
    identity = {
        "observation_id": reference.get("observation_id"),
        "observed_at": reference.get("observed_at"),
        "value": format(value, ".17g"),
        "feature_basis": _feature_basis(observation, feature),
    }
    if feature == "turnover_24h":
        identity["volume_24h_basis"] = _feature_basis(observation, "volume_24h")
        identity["market_cap_basis"] = _feature_basis(observation, "market_cap")
        volume = _positive_finite_number(observation.get("volume_24h"))
        market_cap = _positive_finite_number(observation.get("market_cap"))
        identity["volume_24h_value"] = (
            format(volume, ".17g") if volume is not None else None
        )
        identity["market_cap_value"] = (
            format(market_cap, ".17g") if market_cap is not None else None
        )
    return identity


def _positive_finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        return None
    return converted


def _round_derived(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("derived shadow value must be finite")
    rounded = round(float(value), DERIVED_FLOAT_DECIMAL_PLACES)
    return 0.0 if rounded == 0 else rounded


def _observation_reference(observation: Mapping[str, Any]) -> dict[str, str | None]:
    return {
        "observation_id": _optional_string(observation.get("observation_id")),
        "observed_at": _optional_string(observation.get("observed_at")),
    }


def _optional_string(value: object) -> str | None:
    if value in (None, ""):
        return None
    rendered = str(value).strip()
    return rendered or None


def _reference_sort_key(reference: Mapping[str, str | None]) -> tuple[str, str]:
    return (
        reference.get("observed_at") or "",
        reference.get("observation_id") or "",
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_inputs(
    current_observation: object,
    minimum_sample_count: object,
    *,
    history_artifact: object,
    history_sha256: object,
) -> None:
    if (
        isinstance(minimum_sample_count, bool)
        or not isinstance(minimum_sample_count, int)
        or minimum_sample_count < 1
    ):
        raise ValueError("minimum_sample_count must be a positive integer")
    if not isinstance(current_observation, Mapping):
        raise TypeError("current_observation must be a mapping")
    if (
        not isinstance(history_artifact, str)
        or not history_artifact
        or history_artifact in {".", ".."}
        or "/" in history_artifact
        or "\\" in history_artifact
    ):
        raise ValueError("history_artifact must be a safe basename")
    if (
        not isinstance(history_sha256, str)
        or len(history_sha256) != 64
        or any(character not in "0123456789abcdef" for character in history_sha256)
    ):
        raise ValueError("history_sha256 must be a lowercase SHA-256 digest")


def _validate_observation_sequence(
    current: Mapping[str, Any],
    priors: tuple[Mapping[str, Any], ...],
) -> None:
    current_id = _required_identity(current.get("observation_id"), "current observation_id")
    current_asset = _required_identity(
        current.get("canonical_asset_id"),
        "current canonical_asset_id",
    )
    current_at = _required_aware_time(current.get("observed_at"), "current observed_at")
    seen_ids = {current_id}
    seen_times: set[datetime] = set()
    for prior in priors:
        prior_id = _required_identity(prior.get("observation_id"), "prior observation_id")
        prior_asset = _required_identity(
            prior.get("canonical_asset_id"),
            "prior canonical_asset_id",
        )
        prior_at = _required_aware_time(prior.get("observed_at"), "prior observed_at")
        if prior.get("baseline_counted") is not True:
            raise ValueError("prior observation must be cadence-counted")
        if prior_asset != current_asset:
            raise ValueError("prior observation canonical asset does not match current")
        if prior_at >= current_at:
            raise ValueError("prior observation must be strictly earlier than current")
        if prior_id in seen_ids or prior_at in seen_times:
            raise ValueError("prior observation identity or timestamp is not unique")
        seen_ids.add(prior_id)
        seen_times.add(prior_at)


def _required_identity(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_aware_time(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be an aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an aware timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be an aware timestamp")
    return parsed.astimezone(timezone.utc)


def _assert_closed_value(value: dict[str, Any]) -> dict[str, Any]:
    if frozenset(value) != _TOP_LEVEL_VALUE_KEYS:
        raise AssertionError("shadow temporal surprise drifted from its closed v2 schema")
    if frozenset(value["method"]) != _METHOD_VALUE_KEYS:
        raise AssertionError("shadow temporal surprise method drifted from its closed v2 schema")
    if frozenset(value["features"]) != frozenset(SUPPORTED_FEATURES):
        raise AssertionError("shadow temporal surprise feature set drifted from v2")
    if frozenset(value["return_method"]) != _RETURN_METHOD_VALUE_KEYS:
        raise AssertionError("shadow signed-return method drifted from its closed v2 schema")
    if frozenset(value["return_features"]) != frozenset(SUPPORTED_RETURN_FEATURES):
        raise AssertionError("shadow signed-return feature set drifted from v2")
    return value


def _assert_closed_feature_value(value: dict[str, Any]) -> dict[str, Any]:
    if frozenset(value) != _FEATURE_VALUE_KEYS:
        raise AssertionError("shadow feature value drifted from its closed v1 schema")
    return value


def _assert_closed_return_feature_value(value: dict[str, Any]) -> dict[str, Any]:
    if frozenset(value) != _RETURN_FEATURE_VALUE_KEYS:
        raise AssertionError("shadow signed-return value drifted from its closed v2 schema")
    current_sample = value.get("current_sample")
    if current_sample is not None and frozenset(current_sample) != _RETURN_SAMPLE_VALUE_KEYS:
        raise AssertionError("shadow signed-return sample drifted from its closed v2 schema")
    return value
