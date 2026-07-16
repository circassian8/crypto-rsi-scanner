from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_report_diagnostics as diagnostics,
)
from crypto_rsi_scanner.event_alpha.operations import (
    empirical_replay_persistence,
    empirical_replay_store,
)


_RUN = "a" * 64


def _digest_record(row: dict, field: str) -> dict:
    value = deepcopy(row)
    value[field] = hashlib.sha256(
        empirical_replay_store.canonical_json_bytes(value)
    ).hexdigest()
    return value


def _reseal_diagnostic(row: dict) -> dict:
    value = deepcopy(row)
    value.pop("diagnostic_digest", None)
    return _digest_record(value, "diagnostic_digest")


def _idea(
    candidate_id: str,
    *,
    asset: str | None = None,
    observed_at: str = "2024-02-01T00:00:00Z",
    partition: str = "development",
    route: str = "actionable_watch",
    directional_bias: str = "long",
    market_regime: str = "bull",
    liquidity_tier: str = "high",
    data_quality_mode: str = "historical_ohlcv",
    actionability_score: float = 10.0,
    evidence_confidence_score: float = 10.0,
    risk_score: float = 10.0,
    urgency_score: float = 10.0,
    chase_risk_score: float = 10.0,
    return_24h: float | None = -5.0,
    return_unit: str = "percent_points",
    volume_zscore_24h: float | None = 2.0,
    liquidity_usd: float | None = 10_000_000.0,
) -> dict:
    canonical_asset_id = asset or candidate_id
    row = {
        "schema_id": empirical_replay_persistence.IDEA_RECORD_SCHEMA_ID,
        "schema_version": 1,
        "identity": {
            "candidate_id": candidate_id,
            "canonical_asset_id": canonical_asset_id,
        },
        "replay": {
            "observed_at": observed_at,
            "replay_partition": partition,
        },
        "point_in_time_context": {
            "market_regime": market_regime,
            "liquidity_tier": liquidity_tier,
            "data_quality_mode": data_quality_mode,
            "liquidity_usd": liquidity_usd,
        },
        "market_features": {
            "return_24h": return_24h,
            "return_unit": return_unit,
            "volume_zscore_24h": volume_zscore_24h,
            "liquidity_usd": liquidity_usd,
        },
        "decision_projection": {
            "radar_route": route,
            "directional_bias": directional_bias,
            "actionability_score": actionability_score,
            "evidence_confidence_score": evidence_confidence_score,
            "risk_score": risk_score,
            "urgency_score": urgency_score,
            "chase_risk_score": chase_risk_score,
        },
    }
    return _digest_record(row, "snapshot_sha256")


def _episode(
    idea: dict,
    *,
    episode_id: str | None = None,
    directional_return: float = 0.05,
) -> dict:
    candidate_id = idea["identity"]["candidate_id"]
    episode_id = episode_id or f"episode-{candidate_id}"
    row = {
        "schema_id": empirical_replay_persistence.EPISODE_RECORD_SCHEMA_ID,
        "schema_version": 1,
        "episode_id": episode_id,
        "canonical_asset_id": idea["identity"]["canonical_asset_id"],
        "directional_bias": idea["decision_projection"]["directional_bias"],
        "episode_start_at": idea["replay"]["observed_at"],
        "representative_idea_id": candidate_id,
        "member_count": 1,
        "dependent_repeat_count": 0,
        "members": [
            {
                "idea_id": candidate_id,
                "candidate_id": candidate_id,
                "observed_at": idea["replay"]["observed_at"],
                "idea_snapshot_sha256": idea["snapshot_sha256"],
                "is_representative": True,
            }
        ],
        "representative_outcome": {
            "episode_id": episode_id,
            "idea_id": candidate_id,
            "partition": idea["replay"]["replay_partition"],
            "status": "matured",
            "primary_direction_adjusted_return": directional_return,
            "primary_direction_adjusted_return_unit": "fraction",
        },
    }
    return _digest_record(row, "archive_episode_sha256")


def _episode_with_dependent(representative: dict, dependent: dict) -> dict:
    row = _episode(representative)
    row.pop("archive_episode_sha256")
    row["members"].append(
        {
            "idea_id": dependent["identity"]["candidate_id"],
            "candidate_id": dependent["identity"]["candidate_id"],
            "observed_at": dependent["replay"]["observed_at"],
            "idea_snapshot_sha256": dependent["snapshot_sha256"],
            "is_representative": False,
        }
    )
    row["member_count"] = 2
    row["dependent_repeat_count"] = 1
    return _digest_record(row, "archive_episode_sha256")


def _archive(rows: list[tuple[dict, float]]) -> tuple[list[dict], list[dict]]:
    ideas = [idea for idea, _return in rows]
    episodes = [
        _episode(idea, directional_return=directional_return)
        for idea, directional_return in rows
    ]
    return ideas, episodes


def _route_row(result: dict, route: str) -> dict:
    return next(
        row for row in result["route_score_diagnostics"] if row["route"] == route
    )


def _score_row(route_row: dict, field: str) -> dict:
    return next(
        row for row in route_row["score_diagnostics"] if row["score_field"] == field
    )


def _partition_route_row(result: dict, partition: str, route: str) -> dict:
    return next(
        row
        for row in result["partition_route_score_diagnostics"]
        if row["partition"] == partition and row["route"] == route
    )


def test_route_conditioned_calibration_uses_fixed_buckets_and_minimums() -> None:
    rows = [
        (
            _idea(f"low-{index}", actionability_score=10.0),
            0.10,
        )
        for index in range(5)
    ] + [
        (
            _idea(f"high-{index}", actionability_score=30.0),
            -0.10,
        )
        for index in range(5)
    ]
    ideas, episodes = _archive(rows)

    result = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    actionability = _score_row(
        _route_row(result, "actionable_watch"), "actionability_score"
    )
    comparison = actionability["adjacent_comparisons"][0]

    assert result["schema_id"] == diagnostics.ROUTE_CALIBRATION_SCHEMA_ID
    assert result["source_run_fingerprint"] == _RUN
    assert result["score_fields"] == list(diagnostics.SCORE_FIELDS)
    assert [row["name"] for row in result["score_buckets"]] == [
        "0_19",
        "20_39",
        "40_59",
        "60_79",
        "80_100",
    ]
    assert comparison["evaluation_status"] == "evaluated"
    assert comparison["lower_matured_sample_size"] == 5
    assert comparison["higher_matured_sample_size"] == 5
    assert comparison["observed_delta_fraction"] == pytest.approx(-0.20)
    assert comparison["violation"] is True
    assert actionability["buckets"][0]["sample_status"] == (
        "insufficient_exploratory"
    )
    assert actionability["buckets"][0]["cohort_directional_minimum_met"] is False
    assert result["minimum_samples"] == {
        "adjacent_bucket_comparison_each_bucket": 5,
        "cohort_directional": 30,
        "below_cohort_directional_status": "insufficient_exploratory",
    }
    assert result["policy_eligible"] is False
    assert set(result["safety"].values()) == {0}


def test_each_route_conditioning_dimension_is_reported_without_cross_route_pooling() -> None:
    rows = [
        (
            _idea(
                "action",
                route="actionable_watch",
                directional_bias="long",
                market_regime="bull",
                liquidity_tier="high",
                data_quality_mode="historical_ohlcv",
            ),
            0.04,
        ),
        (
            _idea(
                "risk",
                route="risk_watch",
                directional_bias="risk",
                market_regime="bear",
                liquidity_tier="mid",
                data_quality_mode="cross_sectional_proxy",
            ),
            -0.04,
        ),
    ]
    ideas, episodes = _archive(rows)

    result = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    cohorts = result["route_conditioned_dimension_cohorts"]

    assert set(diagnostics.CONDITIONING_DIMENSIONS) == {
        "directional_bias",
        "market_regime",
        "liquidity_tier",
        "data_quality_mode",
    }
    bull_action = next(
        row
        for row in cohorts
        if row["route"] == "actionable_watch"
        and row["conditioning_dimension"] == "market_regime"
        and row["conditioning_value"] == "bull"
    )
    bear_action = next(
        row
        for row in cohorts
        if row["route"] == "actionable_watch"
        and row["conditioning_dimension"] == "market_regime"
        and row["conditioning_value"] == "bear"
    )
    assert bull_action["episode_count"] == 1
    assert bear_action["episode_count"] == 0
    assert all(row["policy_eligible"] is False for row in cohorts)


def test_partition_route_diagnostics_keep_development_and_validation_isolated() -> None:
    rows = [
        (
            _idea(
                f"development-low-{index}",
                partition="development",
                actionability_score=10.0,
            ),
            0.10,
        )
        for index in range(5)
    ] + [
        (
            _idea(
                f"development-high-{index}",
                partition="development",
                actionability_score=30.0,
            ),
            0.20,
        )
        for index in range(5)
    ] + [
        (
            _idea(
                f"validation-low-{index}",
                partition="validation",
                actionability_score=10.0,
            ),
            0.20,
        )
        for index in range(5)
    ] + [
        (
            _idea(
                f"validation-high-{index}",
                partition="validation",
                actionability_score=30.0,
            ),
            -0.10,
        )
        for index in range(5)
    ]
    ideas, episodes = _archive(rows)

    result = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    development = _score_row(
        _partition_route_row(result, "development", "actionable_watch"),
        "actionability_score",
    )["adjacent_comparisons"][0]
    validation = _score_row(
        _partition_route_row(result, "validation", "actionable_watch"),
        "actionability_score",
    )["adjacent_comparisons"][0]

    assert result["partition_route_score_diagnostic_count"] == 16
    assert len(result["partition_route_score_diagnostics"]) == 16
    assert result["partition_route_score_diagnostics_closed"] is True
    assert development["evaluation_status"] == "evaluated"
    assert development["observed_delta_fraction"] == pytest.approx(0.10)
    assert development["violation"] is False
    assert validation["evaluation_status"] == "evaluated"
    assert validation["observed_delta_fraction"] == pytest.approx(-0.30)
    assert validation["violation"] is True
    assert _partition_route_row(
        result, "development", "actionable_watch"
    )["episode_count"] == 10
    assert _partition_route_row(
        result, "validation", "actionable_watch"
    )["episode_count"] == 10


def test_between_route_composition_counts_and_both_shares_reconcile() -> None:
    rows = [
        (_idea(f"action-{index}", actionability_score=10.0), 0.01)
        for index in range(3)
    ] + [
        (
            _idea(
                f"risk-{index}",
                route="risk_watch",
                directional_bias="risk",
                actionability_score=10.0,
            ),
            -0.01,
        )
        for index in range(2)
    ]
    ideas, episodes = _archive(rows)

    result = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    bucket = next(
        row
        for row in result["between_route_bucket_composition"]
        if row["score_field"] == "actionability_score"
        and row["score_bucket"] == "0_19"
    )
    by_route = {row["route"]: row for row in bucket["routes"]}

    assert bucket["episode_count"] == 5
    assert by_route["actionable_watch"]["episode_count"] == 3
    assert by_route["actionable_watch"]["share_of_score_bucket"] == pytest.approx(
        0.6
    )
    assert by_route["actionable_watch"]["share_of_route"] == 1.0
    assert by_route["risk_watch"]["share_of_score_bucket"] == pytest.approx(0.4)
    assert result["composition_reconciliation"][
        "all_score_fields_reconcile"
    ] is True
    assert result["composition_reconciliation"][
        "all_route_counts_reconcile"
    ] is True


def test_adjacent_comparison_requires_five_matured_in_each_bucket() -> None:
    rows = [
        (_idea(f"low-{index}", actionability_score=10.0), 0.10)
        for index in range(4)
    ] + [
        (_idea(f"high-{index}", actionability_score=30.0), -0.10)
        for index in range(5)
    ]
    ideas, episodes = _archive(rows)

    result = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    comparison = _score_row(
        _route_row(result, "actionable_watch"), "actionability_score"
    )["adjacent_comparisons"][0]

    assert comparison["evaluation_status"] == "insufficient_sample"
    assert comparison["observed_delta_fraction"] is None
    assert comparison["violation"] is None


def test_exact_representative_snapshot_and_outcome_joins_fail_closed() -> None:
    idea = _idea("joined")
    episode = _episode(idea)
    bad_snapshot = deepcopy(episode)
    bad_snapshot["members"][0]["idea_snapshot_sha256"] = "f" * 64
    bad_snapshot = _digest_record(
        {key: value for key, value in bad_snapshot.items() if key != "archive_episode_sha256"},
        "archive_episode_sha256",
    )

    with pytest.raises(ValueError, match="snapshot_reference_mismatch"):
        diagnostics.build_route_conditioned_calibration(
            [idea], [bad_snapshot], source_run_fingerprint=_RUN
        )

    bad_outcome = deepcopy(episode)
    bad_outcome["representative_outcome"]["idea_id"] = "substituted"
    bad_outcome = _digest_record(
        {key: value for key, value in bad_outcome.items() if key != "archive_episode_sha256"},
        "archive_episode_sha256",
    )
    with pytest.raises(ValueError, match="outcome_reference_mismatch"):
        diagnostics.build_route_conditioned_calibration(
            [idea], [bad_outcome], source_run_fingerprint=_RUN
        )


class _OutcomePoison(dict):
    def get(self, key, default=None):
        if key == "representative_outcome":
            raise AssertionError("outcome accessed")
        return super().get(key, default)


def test_final_test_is_rejected_before_any_outcome_access() -> None:
    idea = _idea("holdout", partition="final_test")
    episode = _OutcomePoison(_episode(idea))

    with pytest.raises(ValueError, match="nonselection_partition_rejected"):
        diagnostics.build_route_conditioned_calibration(
            [idea], [episode], source_run_fingerprint=_RUN
        )
    with pytest.raises(ValueError, match="nonselection_partition_rejected"):
        diagnostics.build_market_wide_risk_diagnostics(
            [idea], [episode], source_run_fingerprint=_RUN
        )


def test_market_risk_grouping_is_outcome_blind_and_uses_exact_utc_day() -> None:
    ideas: list[dict] = []
    episodes: list[dict] = []
    values = [
        ("deep", -20.0, 1.0, 1_000_000.0),
        ("tie-z", -10.0, 5.0, 1_000_000.0),
        ("tie-liq", -10.0, 5.0, 9_000_000.0),
        *[(f"asset-{index:02d}", float(-9 + index), 2.0, 2_000_000.0) for index in range(8)],
    ]
    for index, (asset, return_24h, volume_z, liquidity) in enumerate(values):
        idea = _idea(
            f"risk-{index}",
            asset=asset,
            observed_at=(
                "2024-02-02T01:00:00+03:00"
                if index % 2 == 0
                else "2024-02-01T23:30:00Z"
            ),
            route="risk_watch",
            directional_bias="risk",
            market_regime="bear" if index < 8 else "sideways",
            return_24h=return_24h,
            volume_zscore_24h=volume_z,
            liquidity_usd=liquidity,
        )
        ideas.append(idea)
        episodes.append(_OutcomePoison(_episode(idea, directional_return=999.0)))

    result = diagnostics.build_market_wide_risk_diagnostics(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    group = result["daily_risk_groups"][0]
    lists = {row["limit"]: row for row in group["affected_asset_lists"]}

    assert result["schema_id"] == diagnostics.MARKET_RISK_SCHEMA_ID
    assert result["risk_observed_day_count"] == 1
    assert group["utc_day"] == "2024-02-01"
    assert group["market_wide_episode_status"] == "formed"
    assert lists[3]["assets"] == ["deep", "tie-liq", "tie-z"]
    assert len(lists[5]["assets"]) == 5
    assert len(lists[10]["assets"]) == 10
    assert lists[10]["truncated"] is True
    assert group["ranked_asset_evidence"][0]["return_24h_fraction"] == pytest.approx(
        -0.20
    )
    assert group["market_regime_status"] == "mixed"
    assert group["correlated_family_suppression_status"] == (
        diagnostics.CORRELATED_FAMILY_STATUS
    )
    assert result["correlated_family_suppression_status"] == (
        "not_evaluable_missing_correlation_and_family_lineage"
    )
    assert result["outcomes_used_for_group_formation"] is False
    assert result["outcome_fields_read_for_group_formation"] is False
    assert result["policy_eligible"] is False
    assert set(result["safety"].values()) == {0}


def test_market_risk_grouping_deduplicates_assets_and_puts_missing_rank_last() -> None:
    better = _idea(
        "repeat-better",
        asset="repeat",
        observed_at="2024-02-01T01:00:00Z",
        route="risk_watch",
        directional_bias="risk",
        return_24h=-12.0,
    )
    worse = _idea(
        "repeat-worse",
        asset="repeat",
        observed_at="2024-02-01T02:00:00Z",
        route="risk_watch",
        directional_bias="risk",
        return_24h=-2.0,
    )
    missing = _idea(
        "missing",
        observed_at="2024-02-01T03:00:00Z",
        route="risk_watch",
        directional_bias="risk",
        return_24h=None,
    )
    known = _idea(
        "known",
        observed_at="2024-02-01T04:00:00Z",
        route="risk_watch",
        directional_bias="risk",
        return_24h=5.0,
    )
    ideas = [better, worse, missing, known]
    episodes = [_OutcomePoison(_episode(idea)) for idea in ideas]

    result = diagnostics.build_market_wide_risk_diagnostics(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    group = result["daily_risk_groups"][0]

    assert group["risk_item_count"] == 4
    assert group["distinct_asset_count"] == 3
    assert group["dependent_same_asset_item_count"] == 1
    assert group["affected_asset_lists"][0]["assets"] == [
        "repeat",
        "known",
        "missing",
    ]
    repeat = group["ranked_asset_evidence"][0]
    assert repeat["candidate_id"] == "repeat-better"
    assert repeat["return_24h_fraction"] == pytest.approx(-0.12)


def test_diagnostics_are_deterministic_and_require_bound_source_run() -> None:
    rows = [(_idea("a"), 0.03), (_idea("b"), -0.02)]
    ideas, episodes = _archive(rows)
    first = diagnostics.build_route_conditioned_calibration(
        ideas, episodes, source_run_fingerprint=_RUN
    )
    second = diagnostics.build_route_conditioned_calibration(
        list(reversed(ideas)),
        list(reversed(episodes)),
        source_run_fingerprint=_RUN,
    )

    assert first == second
    assert first["diagnostic_digest"] == second["diagnostic_digest"]
    with pytest.raises(ValueError, match="source_run_fingerprint_invalid"):
        diagnostics.build_route_conditioned_calibration(
            ideas, episodes, source_run_fingerprint="unbound"
        )


def test_zero_row_diagnostics_keep_fixed_selection_partition_inventory() -> None:
    calibration = diagnostics.build_route_conditioned_calibration(
        [], [], source_run_fingerprint=_RUN
    )
    risk = diagnostics.build_market_wide_risk_diagnostics(
        [], [], source_run_fingerprint=_RUN
    )

    assert calibration["partitions"] == ["development", "validation"]
    assert risk["partitions"] == ["development", "validation"]
    assert len(calibration["partition_route_score_diagnostics"]) == 16
    assert risk["daily_risk_groups"] == []
    assert diagnostics.validate_route_conditioned_calibration(
        calibration, source_run_fingerprint=_RUN
    ) == calibration
    assert diagnostics.validate_market_wide_risk_diagnostics(
        risk, source_run_fingerprint=_RUN
    ) == risk


def test_market_risk_daily_groups_never_pool_selection_partitions() -> None:
    ideas = [
        _idea(
            f"{partition}-{index}",
            partition=partition,
            route="risk_watch",
            directional_bias="risk",
            observed_at="2024-02-01T12:00:00Z",
        )
        for partition in ("development", "validation")
        for index in range(2)
    ]
    episodes = [_OutcomePoison(_episode(idea)) for idea in ideas]

    result = diagnostics.build_market_wide_risk_diagnostics(
        ideas, episodes, source_run_fingerprint=_RUN
    )

    assert result["risk_observed_day_count"] == 2
    assert result["market_wide_group_count"] == 0
    assert [
        (row["partition"], row["utc_day"], row["risk_item_count"])
        for row in result["daily_risk_groups"]
    ] == [
        ("development", "2024-02-01", 2),
        ("validation", "2024-02-01", 2),
    ]
    assert all(
        row["market_wide_episode_status"] == "insufficient_distinct_assets"
        for row in result["daily_risk_groups"]
    )
    bull_visibility = next(
        row
        for row in result["regime_conditioned_visibility"]
        if row["market_regime"] == "bull"
    )
    assert bull_visibility["observed_day_count"] == 2
    diagnostics.validate_market_wide_risk_diagnostics(
        result, source_run_fingerprint=_RUN
    )


@pytest.mark.parametrize(
    ("mismatch", "error"),
    [
        ("partition", "member_partition_mismatch"),
        ("asset", "member_asset_mismatch"),
        ("direction", "member_direction_mismatch"),
    ],
)
def test_every_dependent_episode_member_must_match_episode_identity(
    mismatch: str, error: str
) -> None:
    representative = _idea("representative", asset="shared")
    dependent = _idea(
        "dependent",
        asset="other" if mismatch == "asset" else "shared",
        partition="validation" if mismatch == "partition" else "development",
        directional_bias="short" if mismatch == "direction" else "long",
        observed_at="2024-02-01T01:00:00Z",
    )
    episode = _episode_with_dependent(representative, dependent)

    with pytest.raises(ValueError, match=error):
        diagnostics.build_route_conditioned_calibration(
            [representative, dependent], [episode], source_run_fingerprint=_RUN
        )


def test_return_24h_units_are_explicit_and_normalize_without_100x_drift() -> None:
    fraction = _idea(
        "fraction",
        route="risk_watch",
        directional_bias="risk",
        return_24h=0.10,
        return_unit="fraction",
    )
    percent_points = _idea(
        "percent-points",
        route="risk_watch",
        directional_bias="risk",
        return_24h=10.0,
        return_unit="percent_points",
    )
    field_level = _idea(
        "field-level",
        route="risk_watch",
        directional_bias="risk",
        return_24h=10.0,
    )
    field_level.pop("snapshot_sha256")
    field_level["market_features"].pop("return_unit")
    field_level["market_features"]["return_units"] = {
        "return_24h": "percent_points"
    }
    field_level = _digest_record(field_level, "snapshot_sha256")
    ideas = [fraction, percent_points, field_level]
    result = diagnostics.build_market_wide_risk_diagnostics(
        ideas,
        [_OutcomePoison(_episode(idea)) for idea in ideas],
        source_run_fingerprint=_RUN,
    )
    normalized = {
        row["canonical_asset_id"]: row["return_24h_fraction"]
        for row in result["daily_risk_groups"][0]["ranked_asset_evidence"]
    }

    assert normalized == {
        "field-level": 0.10,
        "fraction": 0.10,
        "percent-points": 0.10,
    }


@pytest.mark.parametrize("unit", ["fraction", "unknown", None, "empty_override"])
def test_invalid_or_missing_present_return_unit_fails_closed(unit: str | None) -> None:
    idea = _idea(
        "bad-unit",
        route="risk_watch",
        directional_bias="risk",
        return_24h=10.0 if unit == "fraction" else 0.10,
        return_unit=unit if unit in {"fraction", "unknown"} else "percent_points",
    )
    idea.pop("snapshot_sha256")
    if unit is None:
        idea["market_features"].pop("return_unit")
    elif unit == "empty_override":
        idea["market_features"]["return_units"] = {"return_24h": ""}
    else:
        idea["market_features"]["return_unit"] = unit
    idea = _digest_record(idea, "snapshot_sha256")

    with pytest.raises(
        ValueError,
        match=(
            "fraction_implausible"
            if unit == "fraction"
            else "unit_missing_or_unknown"
        ),
    ):
        diagnostics.build_market_wide_risk_diagnostics(
            [idea], [_episode(idea)], source_run_fingerprint=_RUN
        )


def test_route_calibration_validator_is_closed_and_reconciles_nested_counts() -> None:
    idea = _idea("validated")
    result = diagnostics.build_route_conditioned_calibration(
        [idea], [_episode(idea)], source_run_fingerprint=_RUN
    )
    assert diagnostics.validate_route_conditioned_calibration(
        result, source_run_fingerprint=_RUN
    ) == result

    mutants: list[dict] = []
    missing = deepcopy(result)
    missing.pop("outcome_unit")
    mutants.append(_reseal_diagnostic(missing))
    extra = deepcopy(result)
    extra["unexpected"] = True
    mutants.append(_reseal_diagnostic(extra))
    nested_extra = deepcopy(result)
    nested_extra["route_score_diagnostics"][0]["unexpected"] = True
    mutants.append(_reseal_diagnostic(nested_extra))
    count_drift = deepcopy(result)
    count_drift["route_score_diagnostics"][1]["episode_count"] += 1
    mutants.append(_reseal_diagnostic(count_drift))
    partition_drift = deepcopy(result)
    partition_drift["partitions"] = ["development"]
    mutants.append(_reseal_diagnostic(partition_drift))
    unsafe_shape = deepcopy(result)
    unsafe_shape["safety"]["trades"] = False
    mutants.append(_reseal_diagnostic(unsafe_shape))

    for mutant in mutants:
        with pytest.raises(ValueError):
            diagnostics.validate_route_conditioned_calibration(
                mutant, source_run_fingerprint=_RUN
            )
    digest_drift = deepcopy(result)
    digest_drift["episode_count"] = 2
    with pytest.raises(ValueError, match="diagnostic_digest_mismatch"):
        diagnostics.validate_route_conditioned_calibration(digest_drift)


def test_market_risk_validator_is_closed_and_reconciles_nested_counts() -> None:
    idea = _idea(
        "validated-risk", route="risk_watch", directional_bias="risk"
    )
    result = diagnostics.build_market_wide_risk_diagnostics(
        [idea], [_episode(idea)], source_run_fingerprint=_RUN
    )
    assert diagnostics.validate_market_wide_risk_diagnostics(
        result, source_run_fingerprint=_RUN
    ) == result

    mutants: list[dict] = []
    missing = deepcopy(result)
    missing.pop("risk_item_rule")
    mutants.append(_reseal_diagnostic(missing))
    extra = deepcopy(result)
    extra["daily_risk_groups"][0]["unexpected"] = True
    mutants.append(_reseal_diagnostic(extra))
    count_drift = deepcopy(result)
    count_drift["daily_risk_groups"][0]["risk_item_count"] = 2
    mutants.append(_reseal_diagnostic(count_drift))
    list_drift = deepcopy(result)
    list_drift["daily_risk_groups"][0]["affected_asset_lists"][0]["assets"] = []
    mutants.append(_reseal_diagnostic(list_drift))
    regime_drift = deepcopy(result)
    regime_drift["regime_conditioned_visibility"][0]["risk_item_count"] = 2
    mutants.append(_reseal_diagnostic(regime_drift))

    for mutant in mutants:
        with pytest.raises(ValueError):
            diagnostics.validate_market_wide_risk_diagnostics(
                mutant, source_run_fingerprint=_RUN
            )
    with pytest.raises(ValueError, match="source_run_fingerprint_mismatch"):
        diagnostics.validate_market_wide_risk_diagnostics(
            result, source_run_fingerprint="b" * 64
        )
