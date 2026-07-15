"""Pure tests for shadow-only robust temporal market surprise."""

from __future__ import annotations

import copy
import json
import math
import statistics

import pytest

from crypto_rsi_scanner.event_alpha.radar.market_shadow_surprise import (
    ELIGIBLE_FEATURE_BASES,
    MAD_NORMAL_CONSISTENCY_FACTOR,
    SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID,
    build_shadow_temporal_surprise as _build_shadow_temporal_surprise,
    evaluate_shadow_temporal_surprise as _evaluate_shadow_temporal_surprise,
)

_HISTORY_ARTIFACT = "event_market_history.jsonl"
_HISTORY_SHA256 = "a" * 64


def evaluate_shadow_temporal_surprise(current, priors, *, minimum_sample_count):
    return _evaluate_shadow_temporal_surprise(
        current,
        priors,
        minimum_sample_count=minimum_sample_count,
        history_artifact=_HISTORY_ARTIFACT,
        history_sha256=_HISTORY_SHA256,
    )


def build_shadow_temporal_surprise(current, priors, *, minimum_sample_count):
    return _build_shadow_temporal_surprise(
        current,
        priors,
        minimum_sample_count=minimum_sample_count,
        history_artifact=_HISTORY_ARTIFACT,
        history_sha256=_HISTORY_SHA256,
    )


def _observation(
    index: int,
    *,
    volume: float | None,
    turnover: float | None,
    volume_basis: str = "provider_observed",
    turnover_basis: str = "derived_provider_ratio",
    market_cap_basis: str = "provider_observed",
) -> dict:
    return {
        "observation_id": f"obs-{index}",
        "observed_at": f"2026-07-15T{index:02d}:00:00+00:00",
        "canonical_asset_id": "asset-a",
        "baseline_counted": True,
        "volume_24h": volume,
        "turnover_24h": turnover,
        "market_cap": 1_000.0,
        "price": 100 + index,
        "feature_basis": {
            "volume_24h": volume_basis,
            "turnover_24h": turnover_basis,
            "market_cap": market_cap_basis,
            "price": "provider_observed",
        },
    }


def test_ready_shadow_value_uses_log_median_mad_and_descriptive_tail_rank():
    priors = [
        _observation(index, volume=volume, turnover=turnover)
        for index, (volume, turnover) in enumerate(
            zip((80, 90, 100, 110, 120), (0.08, 0.09, 0.10, 0.11, 0.12)),
            start=1,
        )
    ]
    current = _observation(9, volume=160, turnover=0.16)

    result = evaluate_shadow_temporal_surprise(
        current,
        priors,
        minimum_sample_count=5,
    )
    volume = result["features"]["volume_24h"]
    expected_logs = [math.log(value) for value in (80, 90, 100, 110, 120)]
    expected_median = statistics.median(expected_logs)
    expected_mad = statistics.median(abs(value - expected_median) for value in expected_logs)

    assert SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID == "event_alpha.shadow_temporal_surprise"
    assert result["schema_id"] == SHADOW_TEMPORAL_SURPRISE_SCHEMA_ID
    assert result["schema_version"] == 1
    assert result["status"] == "ready"
    assert volume["status"] == "ready"
    assert volume["current_log"] == round(math.log(160), 12)
    assert volume["median_log"] == round(expected_median, 12)
    assert volume["mad_log"] == round(expected_mad, 12)
    assert volume["normal_consistent_mad_log"] == round(
        expected_mad * MAD_NORMAL_CONSISTENCY_FACTOR, 12
    )
    assert volume["robust_z"] == round(
        (math.log(160) - expected_median) / (expected_mad * MAD_NORMAL_CONSISTENCY_FACTOR),
        12,
    )
    assert volume["upper_tail_rank"] == round(1 / 6, 12)
    assert volume["upper_tail_rank_is_p_value"] is False
    assert result["method"]["upper_tail_rank_is_p_value"] is False
    assert result["method"]["transform"] == "natural_log"
    assert set(result["method"]) == {
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
    }
    assert set(result) == {
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
    }
    assert set(result["features"]) == {"volume_24h", "turnover_24h"}
    assert "price" not in result["features"]
    assert result["routing_eligible"] is False
    assert result["priority_eligible"] is False
    assert result["score_adjustment_eligible"] is False
    assert result["decision_score_eligible"] is False
    assert result["auto_apply"] is False
    assert result["research_only"] is True
    assert result["history_artifact"] == _HISTORY_ARTIFACT
    assert result["history_artifact_sha256"] == _HISTORY_SHA256
    assert len(volume["eligible_sample_sha256"]) == 64
    assert volume["eligible_baseline_first_observation"]["observation_id"] == "obs-1"
    assert volume["eligible_baseline_last_observation"]["observation_id"] == "obs-5"
    json.dumps(result, allow_nan=False)


def test_insufficient_history_is_explicit_and_does_not_compute_statistics():
    result = evaluate_shadow_temporal_surprise(
        _observation(9, volume=140, turnover=0.14),
        [
            _observation(1, volume=90, turnover=0.09),
            _observation(2, volume=100, turnover=0.10),
        ],
        minimum_sample_count=3,
    )

    assert result["status"] == "unavailable"
    for feature in ("volume_24h", "turnover_24h"):
        value = result["features"][feature]
        assert value["status"] == "insufficient_history"
        assert value["reason"] == "minimum_sample_count_not_met"
        assert value["sample_count"] == 2
        assert value["median_log"] is None
        assert value["robust_z"] is None
        assert value["upper_tail_rank"] is None


@pytest.mark.parametrize("bad_value", [None, 0, -1, float("nan"), float("inf"), True])
def test_missing_nonpositive_or_nonfinite_current_is_never_transformed(bad_value):
    current = _observation(
        9,
        volume=bad_value,
        turnover=0.15,
        turnover_basis="provider_observed",
    )
    priors = [
        _observation(index, volume=80 + index * 10, turnover=0.08 + index / 100)
        for index in range(1, 5)
    ]

    result = evaluate_shadow_temporal_surprise(current, priors, minimum_sample_count=3)

    volume = result["features"]["volume_24h"]
    assert result["status"] == "partial"
    assert volume["status"] == "current_unavailable"
    assert volume["reason"] == "current_value_not_strictly_positive_finite"
    assert volume["current_value"] is None
    assert volume["robust_z"] is None
    json.dumps(result, allow_nan=False)


def test_degenerate_mad_returns_null_robust_z_without_fallback():
    priors = [
        _observation(index, volume=100, turnover=0.1)
        for index in range(1, 6)
    ]
    result = evaluate_shadow_temporal_surprise(
        _observation(9, volume=200, turnover=0.2),
        priors,
        minimum_sample_count=5,
    )

    assert result["status"] == "unavailable"
    for feature in ("volume_24h", "turnover_24h"):
        value = result["features"][feature]
        assert value["status"] == "degenerate_scale"
        assert value["mad_log"] <= 1e-12
        assert value["normal_consistent_mad_log"] <= 1.482602218505602e-12
        assert value["robust_z"] is None
        assert value["upper_tail_rank"] == pytest.approx(1 / 6)


def test_median_and_mad_resist_one_extreme_baseline_outlier():
    ordinary = (80, 90, 100, 110, 120, 130)
    contaminated = (80, 90, 100, 110, 120, 1_000_000_000_000)
    current = _observation(9, volume=160, turnover=0.16)

    def volume_value(values):
        priors = [
            _observation(index, volume=volume, turnover=0.08 + index / 100)
            for index, volume in enumerate(values, start=1)
        ]
        return evaluate_shadow_temporal_surprise(
            current,
            priors,
            minimum_sample_count=6,
        )["features"]["volume_24h"]

    clean = volume_value(ordinary)
    with_outlier = volume_value(contaminated)

    assert clean["median_log"] == pytest.approx(with_outlier["median_log"])
    assert clean["mad_log"] == pytest.approx(with_outlier["mad_log"])
    assert clean["robust_z"] == pytest.approx(with_outlier["robust_z"])


def test_basis_filter_allows_direct_inputs_and_excludes_proxy_or_cross_sectional_rows():
    assert ELIGIBLE_FEATURE_BASES == {"provider_observed", "derived_provider_ratio"}
    priors = [
        _observation(1, volume=80, turnover=0.08),
        _observation(
            2,
            volume=90,
            turnover=0.09,
            volume_basis="cross_sectional_log_turnover_proxy",
            turnover_basis="proxy_market_cap_ratio",
        ),
        _observation(3, volume=100, turnover=0.10),
        _observation(4, volume=110, turnover=0.11),
    ]
    current = _observation(
        9,
        volume=150,
        turnover=0.15,
        volume_basis="cross_sectional_volume_proxy",
        turnover_basis="provider_observed",
    )

    result = evaluate_shadow_temporal_surprise(current, priors, minimum_sample_count=3)

    volume = result["features"]["volume_24h"]
    turnover = result["features"]["turnover_24h"]
    assert result["status"] == "partial"
    assert volume["status"] == "basis_ineligible"
    assert volume["reason"] == "current_feature_basis_not_eligible"
    assert volume["basis_ineligible_baseline_count"] == 1
    assert turnover["status"] == "ready"
    assert turnover["basis_ineligible_baseline_count"] == 1
    assert turnover["sample_count"] == 3


def test_derived_turnover_requires_provider_observed_volume_and_market_cap_bases():
    priors = [
        _observation(1, volume=80, turnover=0.08),
        _observation(2, volume=90, turnover=0.09, market_cap_basis="provider_proxy"),
        _observation(3, volume=100, turnover=0.10),
        _observation(4, volume=110, turnover=0.11),
    ]
    current = _observation(
        9,
        volume=150,
        turnover=0.15,
        market_cap_basis="cross_sectional_proxy",
    )

    result = evaluate_shadow_temporal_surprise(current, priors, minimum_sample_count=3)

    volume = result["features"]["volume_24h"]
    turnover = result["features"]["turnover_24h"]
    assert result["status"] == "partial"
    assert volume["status"] == "ready"
    assert turnover["status"] == "basis_ineligible"
    assert turnover["basis_ineligible_baseline_count"] == 1
    assert turnover["sample_count"] == 3


def test_derived_turnover_requires_value_to_match_provider_ratio():
    priors = [
        _observation(1, volume=80, turnover=0.08),
        _observation(2, volume=90, turnover=0.90),
        _observation(3, volume=100, turnover=0.10),
        _observation(4, volume=110, turnover=0.11),
    ]
    current = _observation(9, volume=150, turnover=0.90)

    result = evaluate_shadow_temporal_surprise(current, priors, minimum_sample_count=3)

    turnover = result["features"]["turnover_24h"]
    assert result["status"] == "partial"
    assert turnover["status"] == "basis_ineligible"
    assert turnover["basis_ineligible_baseline_count"] == 1
    assert turnover["sample_count"] == 3


def test_invalid_baselines_are_excluded_and_reported_without_fabricating_sample_size():
    priors = [
        _observation(1, volume=80, turnover=0.08),
        _observation(2, volume=0, turnover=-0.01),
        _observation(3, volume=float("nan"), turnover=float("inf")),
        _observation(4, volume=110, turnover=0.11),
    ]
    result = evaluate_shadow_temporal_surprise(
        _observation(9, volume=150, turnover=0.15),
        priors,
        minimum_sample_count=3,
    )

    volume = result["features"]["volume_24h"]
    turnover = result["features"]["turnover_24h"]
    assert volume["status"] == turnover["status"] == "insufficient_history"
    assert volume["sample_count"] == turnover["sample_count"] == 2
    assert volume["invalid_baseline_count"] == 2
    assert turnover["invalid_baseline_count"] == 0
    assert turnover["basis_ineligible_baseline_count"] == 2
    json.dumps(result, allow_nan=False)


def test_inputs_are_immutable_output_is_deterministic_and_wrapper_is_namespaced():
    current = _observation(9, volume=160, turnover=0.16)
    priors = [
        _observation(index, volume=70 + index * 10, turnover=0.07 + index / 100)
        for index in range(1, 6)
    ]
    current_before = copy.deepcopy(current)
    priors_before = copy.deepcopy(priors)

    forward = evaluate_shadow_temporal_surprise(current, priors, minimum_sample_count=5)
    reverse = evaluate_shadow_temporal_surprise(current, reversed(priors), minimum_sample_count=5)
    wrapped = build_shadow_temporal_surprise(current, priors, minimum_sample_count=5)

    assert current == current_before
    assert priors == priors_before
    assert forward == reverse
    assert wrapped == {"shadow_temporal_surprise": forward}
    assert forward["surveyed_prior_first_observation"]["observation_id"] == "obs-1"
    assert forward["surveyed_prior_last_observation"]["observation_id"] == "obs-5"
    assert forward["current_observation"] == {
        "observation_id": "obs-9",
        "observed_at": "2026-07-15T09:00:00+00:00",
    }
    json.dumps(wrapped, sort_keys=True, allow_nan=False)


def test_eligible_sample_digest_binds_identity_value_and_basis_without_copying_samples():
    current = _observation(9, volume=160, turnover=0.16)
    priors = [
        _observation(index, volume=70 + index * 10, turnover=0.07 + index / 100)
        for index in range(1, 6)
    ]
    original = evaluate_shadow_temporal_surprise(
        current,
        priors,
        minimum_sample_count=5,
    )["features"]["volume_24h"]
    changed_priors = copy.deepcopy(priors)
    changed_priors[2]["volume_24h"] += 0.5
    changed = evaluate_shadow_temporal_surprise(
        current,
        changed_priors,
        minimum_sample_count=5,
    )["features"]["volume_24h"]

    assert original["eligible_sample_sha256"] != changed["eligible_sample_sha256"]
    assert "eligible_baseline_observations" not in original
    assert set(original) == {
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
    }


def test_derived_turnover_sample_digest_binds_ratio_dependencies():
    current = _observation(9, volume=160, turnover=0.16)
    priors = [
        _observation(index, volume=70 + index * 10, turnover=0.07 + index / 100)
        for index in range(1, 6)
    ]
    original = evaluate_shadow_temporal_surprise(
        current,
        priors,
        minimum_sample_count=5,
    )["features"]["turnover_24h"]
    changed_priors = copy.deepcopy(priors)
    changed_priors[2]["volume_24h"] *= 2
    changed_priors[2]["market_cap"] *= 2
    changed = evaluate_shadow_temporal_surprise(
        current,
        changed_priors,
        minimum_sample_count=5,
    )["features"]["turnover_24h"]

    assert original["eligible_sample_sha256"] != changed["eligible_sample_sha256"]
    assert original["robust_z"] == changed["robust_z"]


@pytest.mark.parametrize("minimum", [0, -1, True, 1.5])
def test_minimum_sample_count_must_be_a_positive_integer(minimum):
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_shadow_temporal_surprise(
            _observation(9, volume=160, turnover=0.16),
            [],
            minimum_sample_count=minimum,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda row: row.update(baseline_counted=False), "cadence-counted"),
        (
            lambda row: row.update(canonical_asset_id="asset-b"),
            "canonical asset does not match",
        ),
        (
            lambda row: row.update(observed_at="2026-07-15T10:00:00+00:00"),
            "strictly earlier",
        ),
        (lambda row: row.update(observation_id="obs-9"), "not unique"),
    ),
)
def test_evaluator_rejects_unfiltered_or_ambiguous_prior_history(mutation, message):
    current = _observation(9, volume=160, turnover=0.16)
    priors = [
        _observation(index, volume=70 + index * 10, turnover=0.07 + index / 100)
        for index in range(1, 6)
    ]
    mutation(priors[-1])

    with pytest.raises(ValueError, match=message):
        evaluate_shadow_temporal_surprise(
            current,
            priors,
            minimum_sample_count=5,
        )


@pytest.mark.parametrize(
    ("history_artifact", "history_sha256", "message"),
    (
        ("../history.jsonl", "a" * 64, "safe basename"),
        ("history.jsonl", "A" * 64, "lowercase SHA-256"),
        ("history.jsonl", "a" * 63, "lowercase SHA-256"),
    ),
)
def test_evaluator_requires_closed_history_artifact_binding(
    history_artifact,
    history_sha256,
    message,
):
    with pytest.raises(ValueError, match=message):
        _evaluate_shadow_temporal_surprise(
            _observation(9, volume=160, turnover=0.16),
            [],
            minimum_sample_count=5,
            history_artifact=history_artifact,
            history_sha256=history_sha256,
        )


def test_north_star_keeps_robust_surprise_shadow_only_and_threshold_free():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.project_health import radar_north_star

    payload = radar_north_star.build_north_star()
    policy = payload["shadow_temporal_surprise_policy"]

    assert policy["schema_id"] == "event_alpha.shadow_temporal_surprise"
    assert policy["features"] == ["volume_24h", "turnover_24h"]
    assert policy["derived_ratio_validation"] == (
        "volume_div_market_cap_rel_tol_1e-9_abs_tol_1e-12"
    )
    assert policy["routing_eligible"] is False
    assert policy["priority_eligible"] is False
    assert policy["decision_score_eligible"] is False
    assert policy["score_adjustment_eligible"] is False
    assert policy["auto_apply"] is False
    assert policy["descriptive_tail_is_p_value"] is False
    for schema_id in ("market_state_snapshot_v1", "market_anomaly_v1"):
        schema = schema_v1.get_schema(schema_id)
        assert "shadow_temporal_surprise" in schema.optional_fields
        assert schema.field_types["shadow_temporal_surprise"] == "dict"
    assert "## Shadow Robust Temporal Surprise" in radar_north_star.format_north_star(
        payload
    )


def _valid_schema_shadow() -> dict:
    priors = [
        _observation(index, volume=70 + index * 10, turnover=0.07 + index / 100)
        for index in range(1, 6)
    ]
    return evaluate_shadow_temporal_surprise(
        _observation(9, volume=160, turnover=0.16),
        priors,
        minimum_sample_count=5,
    )


def _shadow_artifact_row(schema_id: str, shadow: object) -> dict:
    if schema_id == "market_state_snapshot_v1":
        return {
            "row_type": "event_market_state_snapshot",
            "symbol": "TEST",
            "shadow_temporal_surprise": shadow,
        }
    return {
        "row_type": "event_market_anomaly",
        "symbol": "TEST",
        "market_state_class": "high_volume_expansion",
        "market_state_snapshot": {"symbol": "TEST"},
        "shadow_temporal_surprise": shadow,
    }


@pytest.mark.parametrize(
    "schema_id", ("market_state_snapshot_v1", "market_anomaly_v1")
)
def test_artifact_schema_accepts_closed_shadow_temporal_surprise(schema_id):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    row = _shadow_artifact_row(schema_id, _valid_schema_shadow())

    assert schema_v1.validate_row_against_schema(row, schema_id) == []


def test_artifact_schema_accepts_unavailable_shadow_with_null_references_and_statistics():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    shadow = evaluate_shadow_temporal_surprise(
        _observation(9, volume=160, turnover=0.16),
        [],
        minimum_sample_count=5,
    )
    row = _shadow_artifact_row("market_state_snapshot_v1", shadow)

    assert shadow["status"] == "unavailable"
    assert shadow["surveyed_prior_first_observation"] is None
    assert schema_v1.validate_row_against_schema(
        row, "market_state_snapshot_v1"
    ) == []


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        (
            lambda value: value.update(unexpected=True),
            "shadow_temporal_surprise_closed_keys:value",
        ),
        (
            lambda value: value.__setitem__("method", []),
            "shadow_temporal_surprise_invalid_type:method:dict",
        ),
        (
            lambda value: value["method"].update(unexpected=True),
            "shadow_temporal_surprise_closed_keys:method",
        ),
        (
            lambda value: value.__setitem__("features", []),
            "shadow_temporal_surprise_invalid_type:features:dict",
        ),
        (
            lambda value: value["features"].pop("turnover_24h"),
            "shadow_temporal_surprise_closed_keys:features",
        ),
        (
            lambda value: value["features"].__setitem__("volume_24h", []),
            "shadow_temporal_surprise_invalid_type:features.volume_24h:dict",
        ),
        (
            lambda value: value["features"]["volume_24h"].update(unexpected=True),
            "shadow_temporal_surprise_closed_keys:features.volume_24h",
        ),
        (
            lambda value: value.__setitem__("status", {}),
            "shadow_temporal_surprise_invalid_enum:value.status",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "status", "not_a_status"
            ),
            "shadow_temporal_surprise_invalid_enum:features.volume_24h.status",
        ),
        (
            lambda value: value.__setitem__("routing_eligible", True),
            "shadow_temporal_surprise_fixed_value_mismatch:value.routing_eligible",
        ),
        (
            lambda value: value.__setitem__("research_only", False),
            "shadow_temporal_surprise_fixed_value_mismatch:value.research_only",
        ),
        (
            lambda value: value["method"].__setitem__(
                "upper_tail_rank_is_p_value", True
            ),
            "shadow_temporal_surprise_fixed_value_mismatch:method.upper_tail_rank_is_p_value",
        ),
        (
            lambda value: value["features"]["turnover_24h"].__setitem__(
                "upper_tail_rank_is_p_value", True
            ),
            "shadow_temporal_surprise_fixed_value_mismatch:features.turnover_24h.upper_tail_rank_is_p_value",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "sample_count", []
            ),
            "shadow_temporal_surprise_invalid_type:features.volume_24h.sample_count:nonnegative_int",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "robust_z", {}
            ),
            "shadow_temporal_surprise_invalid_type:features.volume_24h.robust_z:finite_number_or_null",
        ),
        (
            lambda value: value.__setitem__("current_observation", []),
            "shadow_temporal_surprise_invalid_type:current_observation:dict",
        ),
        (
            lambda value: value.__setitem__("history_artifact", "../history.jsonl"),
            "shadow_temporal_surprise_invalid_type:value.history_artifact:safe_basename",
        ),
        (
            lambda value: value.__setitem__("history_artifact_sha256", "A" * 64),
            "shadow_temporal_surprise_invalid_type:value.history_artifact_sha256:sha256",
        ),
        (
            lambda value: value.__setitem__("status", "partial"),
            "shadow_temporal_surprise_status_inconsistent:value.status",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "reason", "minimum_sample_count_not_met"
            ),
            "shadow_temporal_surprise_reason_inconsistent:features.volume_24h",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "sample_count", 4
            ),
            "shadow_temporal_surprise_sample_accounting_mismatch:features.volume_24h",
        ),
        (
            lambda value: value["features"]["volume_24h"].__setitem__(
                "robust_z", None
            ),
            "shadow_temporal_surprise_statistic_inconsistent:features.volume_24h.robust_z",
        ),
    ),
)
def test_artifact_schema_rejects_malformed_closed_shadow_values(
    mutation, expected_error
):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    shadow = _valid_schema_shadow()
    mutation(shadow)
    row = _shadow_artifact_row("market_state_snapshot_v1", shadow)

    errors = schema_v1.validate_row_against_schema(row, "market_state_snapshot_v1")

    assert any(error.startswith(expected_error) for error in errors), errors


def test_artifact_schema_rejects_non_mapping_shadow_value():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    row = _shadow_artifact_row("market_state_snapshot_v1", [])

    errors = schema_v1.validate_row_against_schema(row, "market_state_snapshot_v1")

    assert "invalid_type:shadow_temporal_surprise:dict" in errors
    assert "shadow_temporal_surprise_invalid_type:value:dict" in errors


def test_artifact_schema_rejects_sample_count_status_contradictions():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    ready = _valid_schema_shadow()
    ready_volume = ready["features"]["volume_24h"]
    ready_volume["sample_count"] = ready_volume["minimum_sample_count"] - 1
    ready_volume["invalid_baseline_count"] += 1
    ready_errors = schema_v1.validate_row_against_schema(
        _shadow_artifact_row("market_state_snapshot_v1", ready),
        "market_state_snapshot_v1",
    )

    insufficient = evaluate_shadow_temporal_surprise(
        _observation(9, volume=160, turnover=0.16),
        [
            _observation(1, volume=80, turnover=0.08),
            _observation(2, volume=90, turnover=0.09),
        ],
        minimum_sample_count=5,
    )
    insufficient["features"]["volume_24h"]["sample_count"] = 5
    insufficient_errors = schema_v1.validate_row_against_schema(
        _shadow_artifact_row("market_state_snapshot_v1", insufficient),
        "market_state_snapshot_v1",
    )

    expected = (
        "shadow_temporal_surprise_sample_status_mismatch:features.volume_24h"
    )
    assert expected in ready_errors
    assert expected in insufficient_errors


def test_market_anomaly_schema_rejects_nested_shadow_placement_and_bad_snapshot_type():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    shadow = _valid_schema_shadow()
    nested = _shadow_artifact_row("market_anomaly_v1", shadow)
    nested["market_state_snapshot"]["shadow_temporal_surprise"] = copy.deepcopy(shadow)
    malformed = _shadow_artifact_row("market_anomaly_v1", shadow)
    malformed["market_state_snapshot"] = []

    nested_errors = schema_v1.validate_row_against_schema(nested, "market_anomaly_v1")
    malformed_errors = schema_v1.validate_row_against_schema(
        malformed, "market_anomaly_v1"
    )

    assert (
        "shadow_temporal_surprise_forbidden_placement:market_state_snapshot"
        in nested_errors
    )
    assert (
        "shadow_temporal_surprise_invalid_type:market_state_snapshot:dict"
        in malformed_errors
    )


@pytest.mark.parametrize(
    ("schema_id", "row"),
    (
        (
            "integrated_radar_candidate_v1",
            {
                "row_type": "event_integrated_radar_candidate",
                "candidate_id": "candidate-1",
                "symbol": "AAA",
                "opportunity_type": "DIAGNOSTIC",
            },
        ),
        (
            "core_opportunity_v1",
            {
                "row_type": "event_core_opportunity",
                "core_opportunity_id": "core-1",
                "symbol": "AAA",
                "opportunity_type": "DIAGNOSTIC",
            },
        ),
        (
            "outcome_row_v1",
            {
                "row_type": "event_integrated_radar_outcome",
                "symbol": "AAA",
                "opportunity_type": "DIAGNOSTIC",
            },
        ),
    ),
)
def test_schema_rejects_shadow_anywhere_outside_raw_market_evidence(schema_id, row):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    row["container"] = {"shadow_temporal_surprise": _valid_schema_shadow()}

    errors = schema_v1.validate_row_against_schema(row, schema_id)

    assert (
        "shadow_temporal_surprise_forbidden_placement:outside_market_evidence"
        in errors
    )
