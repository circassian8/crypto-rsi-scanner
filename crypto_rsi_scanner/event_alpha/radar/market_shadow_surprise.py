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
from datetime import datetime, timezone
from numbers import Real
from typing import Any


SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID = "event_alpha.shadow_temporal_surprise"
SHADOW_TEMPORAL_SURPRISE_SCHEMA_VERSION = 1
SUPPORTED_FEATURES = ("volume_24h", "turnover_24h")
ELIGIBLE_FEATURE_BASES = frozenset(("provider_observed", "derived_provider_ratio"))
MAD_NORMAL_CONSISTENCY_FACTOR = 1.482602218505602
MAD_DEGENERATE_THRESHOLD = 1e-12
DERIVED_FLOAT_DECIMAL_PLACES = 12
DERIVED_RATIO_REL_TOLERANCE = 1e-9
DERIVED_RATIO_ABS_TOLERANCE = 1e-12

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
        "routing_eligible",
        "priority_eligible",
        "score_adjustment_eligible",
        "decision_score_eligible",
        "auto_apply",
        "research_only",
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
) -> dict[str, Any]:
    """Return the closed v1 shadow value for two direct market features.

    Inputs are only read. Proxy, cross-sectional, missing, and otherwise
    unapproved feature bases are explicitly excluded. Non-positive and
    non-finite values are never transformed.
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
    ready_count = sum(value["status"] == "ready" for value in features.values())
    if ready_count == len(SUPPORTED_FEATURES):
        status = "ready"
    elif ready_count:
        status = "partial"
    else:
        status = "unavailable"

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
) -> dict[str, Any]:
    """Return the namespaced projection used when integration is desired."""

    return {
        "shadow_temporal_surprise": evaluate_shadow_temporal_surprise(
            current_observation,
            prior_observations,
            minimum_sample_count=minimum_sample_count,
            history_artifact=history_artifact,
            history_sha256=history_sha256,
        )
    }


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
        raise AssertionError("shadow temporal surprise drifted from its closed v1 schema")
    if frozenset(value["method"]) != _METHOD_VALUE_KEYS:
        raise AssertionError("shadow temporal surprise method drifted from its closed v1 schema")
    if frozenset(value["features"]) != frozenset(SUPPORTED_FEATURES):
        raise AssertionError("shadow temporal surprise feature set drifted from v1")
    return value


def _assert_closed_feature_value(value: dict[str, Any]) -> dict[str, Any]:
    if frozenset(value) != _FEATURE_VALUE_KEYS:
        raise AssertionError("shadow feature value drifted from its closed v1 schema")
    return value
