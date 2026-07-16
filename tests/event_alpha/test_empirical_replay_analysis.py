from __future__ import annotations

from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.operations import empirical_replay_analysis as analysis


def _representative(episode_id: str, **overrides):
    row = {
        "episode_id": episode_id,
        "partition": "development",
        "observed_at": "2022-02-01T00:00:00Z",
        "expires_at": "2022-02-04T00:00:00Z",
        "canonical_asset_id": episode_id,
        "radar_route": "actionable_watch",
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led"],
        "directional_bias": "long",
        "actionability_score": 70.0,
        "evidence_confidence_score": 65.0,
        "risk_score": 35.0,
        "urgency_score": 55.0,
        "chase_risk_score": 30.0,
        "market_regime": "bull",
        "liquidity_tier": "large",
        "data_quality_mode": "historical_ohlcv",
        "catalyst_known_at_observation": False,
        "catalyst_status_at_observation": "unknown",
        "anomaly_family": "volume_breakout",
        "operator_visible_idea": True,
    }
    row.update(overrides)
    return row


def _outcome(episode_id: str, primary_return: float, **overrides):
    row = {
        "episode_id": episode_id,
        "partition": "development",
        "status": "matured",
        "primary_horizon": "3d",
        "primary_horizon_return": primary_return,
        "primary_direction_adjusted_return": primary_return,
        "max_favorable_excursion": max(primary_return, 0.02),
        "max_adverse_excursion": 0.03,
        "horizons": {
            "1d": {
                "maturity_status": "matured",
                "raw_return_fraction": primary_return / 2.0,
                "direction_adjusted_return_fraction": primary_return / 2.0,
            },
            "3d": {
                "maturity_status": "matured",
                "raw_return_fraction": primary_return,
                "direction_adjusted_return_fraction": primary_return,
                "mfe_fraction": max(primary_return, 0.02),
                "mae_fraction": 0.03,
            },
        },
    }
    row.update(overrides)
    return row


def _build(representatives, outcomes, *, resamples=100):
    return analysis.build_empirical_replay_analysis(
        representatives,
        outcomes,
        partition="development",
        evidence_mode="historical_replay",
        bootstrap_resamples=resamples,
    )


def test_zero_input_closes_all_routes_and_primary_origins() -> None:
    result = _build([], [])

    assert [row["cohort"] for row in result["route_cohorts"]] == list(
        analysis.ROUTES
    )
    assert [row["cohort"] for row in result["primary_origin_cohorts"]] == list(
        analysis.PRIMARY_ORIGINS
    )
    assert len(result["route_cohorts"]) == 8
    assert len(result["primary_origin_cohorts"]) == 7
    for row in result["route_cohorts"] + result["primary_origin_cohorts"]:
        assert row["partition"] == "development"
        assert row["evidence_mode"] == "historical_replay"
        assert row["sample_size"] == 0
        assert row["sample_status"] == "no_sample"
        assert row["evidence_strength"] == "no_evidence"
        assert row["result_direction"] == "no_result"
        assert row["uncertainty"]["status"] == "not_estimable_no_sample"
        assert row["policy_eligible"] is False
        assert row["auto_apply"] is False
    assert set(result["safety"].values()) == {0}
    assert result["causal_claim"] is False
    assert result["production_policy_claim"] is False


def test_insufficient_sample_is_distinct_from_negative_descriptive_result() -> None:
    representatives = [_representative("a"), _representative("b")]
    outcomes = [_outcome("a", -0.10), _outcome("b", -0.04)]

    row = _build(representatives, outcomes)["route_cohorts"][1]

    assert row["cohort"] == "actionable_watch"
    assert row["sample_status"] == "insufficient_sample"
    assert row["evidence_strength"] == "insufficient"
    assert row["result_direction"] == "negative_descriptive"
    assert row["mean_directional_return_fraction"] == pytest.approx(-0.07)
    assert row["hit_rate"] == 0.0
    assert row["policy_eligible"] is False


def test_bootstrap_ci_and_analysis_are_deterministic_and_order_independent() -> None:
    representatives = [_representative(f"e{index}") for index in range(8)]
    outcomes = [
        _outcome(f"e{index}", value)
        for index, value in enumerate((-0.09, -0.03, 0.01, 0.02, 0.04, 0.07, 0.11, 0.16))
    ]

    first = _build(representatives, outcomes, resamples=250)
    second = _build(list(reversed(representatives)), list(reversed(outcomes)), resamples=250)
    first_row = first["route_cohorts"][1]
    second_row = second["route_cohorts"][1]

    assert first_row["uncertainty"] == second_row["uncertainty"]
    assert first["analysis_digest"] == second["analysis_digest"]
    assert first_row["uncertainty"]["status"] == "estimated_exploratory"
    assert first_row["uncertainty"]["lower_fraction"] <= first_row[
        "mean_directional_return_fraction"
    ]
    assert first_row["uncertainty"]["upper_fraction"] >= first_row[
        "mean_directional_return_fraction"
    ]


def test_robust_metrics_trim_outliers_and_keep_mfe_mae_as_fractions() -> None:
    values = [0.01] * 9 + [1.0]
    representatives = [_representative(f"r{index}") for index in range(10)]
    outcomes = [
        _outcome(
            f"r{index}",
            value,
            max_favorable_excursion=0.20 + index / 100.0,
            max_adverse_excursion=0.05,
        )
        for index, value in enumerate(values)
    ]

    row = _build(representatives, outcomes)["route_cohorts"][1]

    assert row["mean_directional_return_fraction"] == pytest.approx(0.109)
    assert row["median_directional_return_fraction"] == pytest.approx(0.01)
    assert row["trimmed_mean_10pct_directional_return_fraction"] == pytest.approx(
        0.01
    )
    assert row["mean_mae_fraction"] == pytest.approx(0.05)
    assert row["mfe_to_mae_ratio_of_means"] is not None
    assert row["return_unit"] == "fraction"


def test_score_bucket_monotonicity_reports_violations_without_model_change() -> None:
    low_score_winner = _representative(
        "winner",
        actionability_score=10.0,
        evidence_confidence_score=10.0,
        urgency_score=10.0,
        risk_score=90.0,
        chase_risk_score=90.0,
    )
    high_score_loser = _representative(
        "loser",
        actionability_score=90.0,
        evidence_confidence_score=90.0,
        urgency_score=90.0,
        risk_score=10.0,
        chase_risk_score=10.0,
    )

    result = _build(
        [low_score_winner, high_score_loser],
        [_outcome("winner", 0.20), _outcome("loser", -0.20)],
    )
    by_field = {row["score_field"]: row for row in result["score_monotonicity"]}

    for field in analysis.SCORE_FIELDS:
        assert by_field[field]["violation_count"] == 1
        assert by_field[field]["comparisons"][0]["violation"] is True
        assert by_field[field]["model_changed"] is False
        assert by_field[field]["auto_apply"] is False
    assert len(by_field["urgency_score"]["buckets"]) == 5


def test_units_and_cost_scenarios_are_explicit_and_not_silently_scaled() -> None:
    representatives = [_representative("fraction"), _representative("points")]
    outcomes = [
        _outcome("fraction", 0.10),
        _outcome(
            "points",
            10.0,
            primary_horizon_return_unit="percent_points",
            primary_direction_adjusted_return=10.0,
            primary_direction_adjusted_return_unit="percent_points",
        ),
    ]

    result = _build(representatives, outcomes)
    row = result["route_cohorts"][1]
    cost = result["cost_sensitivity"]

    assert row["mean_directional_return_fraction"] == pytest.approx(0.10)
    assert [item["round_trip_cost_bps"] for item in cost["scenarios"]] == [
        0,
        20,
        50,
        100,
        200,
    ]
    assert cost["scenarios"][1]["round_trip_cost_fraction"] == pytest.approx(0.002)
    assert cost["scenarios"][1]["mean_net_directional_return_fraction"] == pytest.approx(
        0.098
    )
    assert cost["break_even_mean_round_trip_cost_bps"] == pytest.approx(1000.0)
    assert cost["cost_basis"] == "assumed_sensitivity_not_observed"
    assert cost["historical_spread_observed"] is False

    invalid = deepcopy(outcomes[0])
    invalid["episode_id"] = "invalid"
    invalid["return_unit"] = "mystery"
    invalid["horizons"] = {}
    invalid_rep = _representative("invalid")
    invalid_result = _build([invalid_rep], [invalid])
    assert invalid_result["invalid_declared_return_unit_count"] == 1
    assert invalid_result["directional_return_sample_size"] == 0


def test_market_catalyst_categories_use_only_supplied_point_in_time_timing() -> None:
    later = analysis.classify_market_catalyst_category(
        _representative(
            "later",
            catalyst_attribution_timing="discovered_after_observation",
        )
    )
    before = analysis.classify_market_catalyst_category(
        _representative(
            "before",
            primary_thesis_origin="catalyst_led",
            thesis_origins=["catalyst_led"],
            catalyst_timing_vs_market_reaction="before_market_reaction",
        )
    )
    missing = analysis.classify_market_catalyst_category(
        _representative(
            "missing",
            primary_thesis_origin="catalyst_led",
            thesis_origins=["catalyst_led"],
        )
    )

    assert later["category"] == "market_led_later_catalyst_discovery"
    assert before["category"] == "catalyst_led_before_market_reaction"
    assert missing["category"] == "unclassified"
    assert missing["timing_basis"] == "exact_timing_unavailable"
    assert all(row["retrospective_attribution_used"] is False for row in (later, before, missing))

    canonical_unknown = analysis.classify_market_catalyst_category(
        _representative(
            "canonical-unknown",
            catalyst_status_at_observation=None,
            catalyst_status="unknown",
        )
    )
    assert canonical_unknown["category"] == "market_led_unknown_catalyst"
    assert canonical_unknown["timing_basis"] == "canonical_projection_at_observation"


def test_missed_opportunity_requires_endpoint_liquidity_membership_and_warmth() -> None:
    representative = _representative(
        "missed",
        analysis_role="missed_candidate",
        operator_visible_idea=False,
        trailing_quote_volume_usd=3_000_000.0,
        point_in_time_membership=True,
        baseline_status="warm",
        anomaly_generated=False,
    )
    classified = analysis.classify_missed_opportunity(
        representative,
        _outcome("missed", 0.15),
    )

    assert classified["qualifies"] is True
    assert classified["classification"] == "missed_opportunity"
    assert classified["primary_reason"] == "no_anomaly_generated"
    assert classified["maximum_future_excursion_alone_is_sufficient"] is False
    assert classified["auto_apply"] is False

    only_mfe = deepcopy(_outcome("missed", 0.05))
    only_mfe["max_favorable_excursion"] = 0.50
    not_missed = analysis.classify_missed_opportunity(representative, only_mfe)
    assert not_missed["qualifies"] is False
    assert "primary_endpoint_below_frozen_threshold" in not_missed[
        "qualification_failure_reasons"
    ]


def test_false_positive_and_late_classifier_uses_frozen_thresholds() -> None:
    representative = _representative(
        "failure",
        chase_risk_score=75.0,
        pre_signal_move_7d=0.25,
        timing_state="extended",
        proxy_only=True,
        spread_status="unavailable",
        episode_member_count=3,
    )
    outcome = _outcome(
        "failure",
        -0.08,
        max_favorable_excursion=0.02,
        max_adverse_excursion=0.08,
        horizons={
            "1d": {
                "maturity_status": "matured",
                "raw_return_fraction": -0.06,
                "direction_adjusted_return_fraction": -0.06,
            },
            "3d": {
                "maturity_status": "matured",
                "raw_return_fraction": -0.08,
                "direction_adjusted_return_fraction": -0.08,
                "mfe_fraction": 0.02,
                "mae_fraction": 0.08,
            },
        },
    )

    classified = analysis.classify_false_positive_and_late(representative, outcome)

    assert classified["classification_status"] == "evaluated"
    assert classified["false_positive"] is True
    assert classified["late_idea"] is True
    assert {
        "failed_quickly",
        "poor_mfe_to_mae_asymmetry",
        "late_pre_signal_move",
        "high_chase_risk",
        "too_extended",
        "proxy_data_dependency",
        "liquidity_or_spread_limited",
        "repeated_episode_noise",
    } <= set(classified["symptom_codes"])
    assert classified["causal_claim"] is False
    assert classified["policy_eligible"] is False


def test_operator_burden_is_closed_per_day_and_family_without_notification_inference() -> None:
    rows = [
        _representative(
            "a",
            observed_at="2022-02-01T01:00:00Z",
            anomaly_family="volume",
            radar_route="rapid_market_anomaly",
            digest_eligible=True,
            episode_member_count=3,
            review_required=True,
        ),
        _representative(
            "b",
            observed_at="2022-02-01T05:00:00Z",
            anomaly_family="volume",
            digest_eligible=False,
            system_warning=True,
        ),
        _representative(
            "c",
            observed_at="2022-02-02T05:00:00Z",
            anomaly_family="calendar",
            calendar_reminder=True,
        ),
    ]

    burden = analysis.operator_burden(
        rows,
        partition="development",
        evidence_mode="historical_replay",
    )

    assert burden["episode_count"] == 3
    assert burden["observed_day_count"] == 2
    assert burden["family_count"] == 2
    assert burden["mean_ideas_per_observed_day"] == pytest.approx(1.5)
    first_day = burden["daily"][0]
    assert first_day["idea_count"] == 2
    assert first_day["urgent_item_count"] == 1
    assert first_day["digest_item_count"] == 1
    assert first_day["dependent_repeat_item_count"] == 2
    assert first_day["repeated_family_item_count"] == 3
    volume = next(row for row in burden["families"] if row["name"] == "volume")
    assert volume["repeated_family_item_count"] == 3
    assert volume["median_observation_interval_hours"] == pytest.approx(4.0)
    assert volume["material_change_interval_status"] == (
        "unavailable_incomplete_progression_evidence"
    )
    assert volume["median_material_change_interval_hours"] is None
    assert burden["notification_state_inferred"] is False
    assert burden["auto_apply"] is False


def test_nested_decision_projection_and_cohort_dimensions_are_supported() -> None:
    representative = _representative("nested")
    projection = {
        key: representative.pop(key)
        for key in (
            "radar_route",
            "primary_thesis_origin",
            "thesis_origins",
            "directional_bias",
            "actionability_score",
            "evidence_confidence_score",
            "risk_score",
            "urgency_score",
            "chase_risk_score",
        )
    }
    representative["decision_projection"] = projection
    representative["market_regime"] = "bear"
    representative["liquidity_tier"] = "mid"
    representative["data_quality_mode"] = "cross_sectional_proxy"

    result = _build([representative], [_outcome("nested", 0.04)])

    assert result["route_cohorts"][1]["episode_count"] == 1
    assert {row["cohort"] for row in result["market_regime_cohorts"]} == {
        "bear",
        "unknown",
    }
    assert {row["cohort"] for row in result["liquidity_tier_cohorts"]} == {
        "mid",
        "unknown",
    }
    assert {
        row["cohort"] for row in result["data_quality_cohorts"]
    } == {"cross_sectional_proxy", "unknown"}


def test_generic_outcome_completion_status_defers_to_primary_horizon_maturity() -> None:
    outcome = {
        "episode_id": "nested-outcome",
        "partition": "development",
        "status": "complete",
        "primary_horizon": "3d",
        "horizons": {
            "3d": {
                "maturity_status": "matured",
                "raw_return_fraction": 0.08,
                "direction_adjusted_return_fraction": 0.08,
                "mfe_fraction": 0.12,
                "mae_fraction": 0.04,
            }
        },
    }

    result = _build([_representative("nested-outcome")], [outcome])
    row = result["route_cohorts"][1]

    assert result["matured_episode_count"] == 1
    assert row["mean_directional_return_fraction"] == pytest.approx(0.08)
    assert row["mean_mfe_fraction"] == pytest.approx(0.12)
    assert row["mean_mae_fraction"] == pytest.approx(0.04)


def test_episode_adapter_binds_representative_outcome_by_episode_identity() -> None:
    representative = _representative("discarded-id")
    representative.pop("episode_id")
    outcome = _outcome("discarded-id", -0.08)
    outcome.pop("episode_id")
    outcome["pre_signal_move_7d"] = {
        "status": "available",
        "raw_return_fraction": 0.25,
        "direction_adjusted_return_fraction": 0.25,
        "return_unit": "fraction",
    }
    episode = {
        "episode_id": "episode-bound",
        "episode_start_at": representative["observed_at"],
        "canonical_asset_id": representative["canonical_asset_id"],
        "directional_bias": "long",
        "anomaly_family": "volume_breakout",
        "representative": representative,
        "member_count": 3,
        "dependent_repeat_count": 2,
        "representative_outcome": outcome,
    }

    result = analysis.build_empirical_replay_analysis_from_episodes(
        {"episodes": [episode]},
        partition="development",
        evidence_mode="historical_replay",
        bootstrap_resamples=25,
    )

    assert result["episode_count"] == 1
    assert result["route_cohorts"][1]["mean_directional_return_fraction"] == pytest.approx(
        -0.08
    )
    classification = result["false_positive_and_late_classifications"][0]
    assert classification["episode_id"] == "episode-bound"
    assert classification["late_idea"] is True
    assert "late_pre_signal_move" in classification["symptom_codes"]
    family = result["operator_burden"]["families"][0]
    assert family["dependent_repeat_item_count"] == 2


def test_input_identity_and_partition_ambiguity_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate_representative_episode_id"):
        _build([_representative("dup"), _representative("dup")], [])
    with pytest.raises(ValueError, match="orphan_outcome_episode_id"):
        _build([], [_outcome("orphan", 0.1)])
    with pytest.raises(ValueError, match="representative_partition_mismatch"):
        _build([_representative("wrong", partition="validation")], [])


def test_fixture_partition_is_explicit_mechanics_evidence_and_never_policy() -> None:
    representative = _representative(
        "fixture",
        partition=None,
        replay_partition="fixture",
        operator_visible=False,
    )
    representative.pop("operator_visible_idea")
    outcome = _outcome("fixture", 0.20, partition=None)

    result = analysis.build_empirical_replay_analysis(
        [representative],
        [outcome],
        partition="fixture",
        evidence_mode="synthetic_fixture",
        bootstrap_resamples=25,
    )

    assert result["partition"] == "fixture"
    assert result["evidence_mode"] == "synthetic_fixture"
    assert result["policy_eligible"] is False
    assert len(result["missed_opportunity_classifications"]) == 1
    with pytest.raises(ValueError, match="partition_not_frozen"):
        analysis.build_empirical_replay_analysis(
            [],
            [],
            partition="fixture",
            evidence_mode="historical_replay",
            bootstrap_resamples=25,
        )


def test_closed_decision_dimensions_include_multi_origin_and_unknown_rows() -> None:
    representative = _representative(
        "dimensions",
        thesis_origins=["market_led", "technical_led"],
        directional_bias="risk",
        catalyst_status="plausible",
        market_phase="emerging",
        timing_state="early",
        preferred_horizon="3d_7d",
        tradability_status="good",
        spread_status="verified_good",
        baseline_status="warm",
        point_in_time_volume_rank=2,
        decision_projection={
            "source_provider_lineage": {
                "providers": ["binance_historical_ohlcv"],
                "origins": ["market_anomaly"],
                "source_packs": ["integrated_radar_pack"],
            }
        },
    )

    dimensions = _build(
        [representative],
        [_outcome("dimensions", 0.08)],
        resamples=25,
    )["dimension_analysis"]
    cohorts = dimensions["cohorts"]

    contributing = {
        row["cohort"]: row for row in cohorts["contributing_origin_cohorts"]
    }
    assert contributing["market_led"]["episode_count"] == 1
    assert contributing["technical_led"]["episode_count"] == 1
    assert contributing["unknown"]["episode_count"] == 0
    assert contributing["catalyst_led"]["sample_status"] == "no_sample"
    assert contributing["market_led"]["membership_is_multi_valued"] is True

    expected = {
        "directional_bias_cohorts": ("risk", "long"),
        "catalyst_status_cohorts": ("plausible", "confirmed"),
        "market_phase_cohorts": ("emerging", "breakout"),
        "timing_state_cohorts": ("early", "active"),
        "preferred_horizon_cohorts": ("3d_7d", "intraday"),
        "tradability_status_cohorts": ("good", "blocked"),
        "spread_status_cohorts": ("verified_good", "unavailable"),
        "baseline_maturity_cohorts": ("warm", "cold"),
        "asset_tier_cohorts": ("top_1_3", "rank_4_30"),
    }
    for name, (populated, empty) in expected.items():
        by_name = {row["cohort"]: row for row in cohorts[name]}
        assert by_name[populated]["episode_count"] == 1
        assert by_name[populated]["sample_status"] == "insufficient_sample"
        assert by_name[empty]["sample_status"] == "no_sample"
        assert by_name["unknown"]["episode_count"] == 0

    provider = cohorts["provider_source_combination_cohorts"]
    observed = next(row for row in provider if row["episode_count"] == 1)
    assert observed["cohort"] == (
        "providers=binance_historical_ohlcv|sources=market_anomaly"
    )
    assert dimensions["provider_source_combination_definitions"][0][
        "source_packs"
    ] == ["integrated_radar_pack"]
    assert dimensions["return_unit"] == "fraction"
    assert dimensions["research_only"] is True
    assert dimensions["auto_apply"] is False


def test_horizon_timing_classification_and_expiry_summaries_are_closed() -> None:
    outcome = _outcome(
        "timing",
        -0.01,
        horizons={
            "1d": {
                "maturity_status": "matured",
                "path_status": "complete",
                "raw_return_fraction": 0.02,
                "direction_adjusted_return_fraction": 0.02,
                "direction_adjusted_relative_returns_fraction": {
                    "BTC": 0.01,
                    "ETH": 0.015,
                },
                "max_favorable_excursion_fraction": 0.04,
                "max_adverse_excursion_fraction": -0.03,
                "time_to_mfe_hours": 24.0,
                "time_to_mae_hours": 24.0,
                "time_to_invalidation_hours": None,
                "return_unit": "fraction",
            },
            "3d": {
                "maturity_status": "matured",
                "path_status": "complete",
                "raw_return_fraction": -0.01,
                "direction_adjusted_return_fraction": -0.01,
                "direction_adjusted_relative_returns_fraction": {
                    "BTC": -0.02,
                    "ETH": -0.015,
                },
                "max_favorable_excursion_fraction": 0.06,
                "max_adverse_excursion_fraction": -0.08,
                "time_to_mfe_hours": 24.0,
                "time_to_mae_hours": 72.0,
                "time_to_invalidation_hours": 48.0,
                "return_unit": "fraction",
            },
            "7d": {
                "maturity_status": "matured",
                "path_status": "complete",
                "raw_return_fraction": 0.12,
                "direction_adjusted_return_fraction": 0.12,
                "direction_adjusted_relative_returns_fraction": {
                    "BTC": 0.08,
                    "ETH": 0.07,
                },
                "max_favorable_excursion_fraction": 0.18,
                "max_adverse_excursion_fraction": -0.08,
                "time_to_mfe_hours": 144.0,
                "time_to_mae_hours": 72.0,
                "time_to_invalidation_hours": 48.0,
                "return_unit": "fraction",
            },
            "14d": {
                "maturity_status": "matured",
                "path_status": "complete",
                "raw_return_fraction": 0.15,
                "direction_adjusted_return_fraction": 0.15,
                "direction_adjusted_relative_returns_fraction": {
                    "BTC": 0.09,
                    "ETH": 0.08,
                },
                "max_favorable_excursion_fraction": 0.22,
                "max_adverse_excursion_fraction": -0.10,
                "time_to_mfe_hours": 240.0,
                "time_to_mae_hours": 72.0,
                "time_to_invalidation_hours": 48.0,
                "return_unit": "fraction",
            },
        },
        classifications={
            "status": "available",
            "continuation": False,
            "reversal": True,
            "breakout_failure": True,
            "fade_success": None,
            "risk_event_validation": None,
        },
        expiry={
            "status": "expired_with_directional_resolution",
            "time_to_expiry_observation_hours": 72.0,
            "post_expiry_behavior": "continuation",
            "post_expiry_direction_adjusted_return_fraction": 0.04,
            "return_unit": "fraction",
        },
    )

    dimensions = _build(
        [_representative("timing", directional_bias="long")],
        [outcome],
        resamples=25,
    )["dimension_analysis"]
    horizon_rows = {row["horizon"]: row for row in dimensions["horizon_sensitivity"]}

    assert tuple(horizon_rows) == ("1d", "3d", "7d", "14d")
    assert horizon_rows["14d"]["mean_directional_return_fraction"] == pytest.approx(
        0.15
    )
    assert horizon_rows["3d"]["mean_mae_fraction"] == pytest.approx(0.08)
    assert horizon_rows["3d"]["time_to_invalidation"]["mean_hours"] == 48.0
    assert horizon_rows["3d"]["classification_counts"]["reversal"] == 1
    assert horizon_rows["3d"]["classification_counts"]["breakout_failure"] == 1
    horizon_classes = {
        row["classification"]: row
        for row in horizon_rows["3d"]["classification_summary"]
    }
    assert horizon_classes["reversal"]["sample_status"] == "insufficient_sample"
    assert horizon_classes["reversal"]["uncertainty"]["status"] == (
        "degenerate_single_episode"
    )
    assert horizon_classes["fade_success"]["sample_status"] == "no_sample"
    assert all(row["return_unit"] == "fraction" for row in horizon_rows.values())

    timing = {row["metric"]: row for row in dimensions["timing_metrics"]}
    assert timing["time_to_mfe_hours"]["mean_hours"] == 24.0
    assert timing["time_to_mae_hours"]["mean_hours"] == 72.0
    assert timing["time_to_invalidation_hours"]["mean_hours"] == 48.0
    assert timing["time_to_expiry_observation_hours"]["mean_hours"] == 72.0
    assert timing["time_to_mfe_hours"]["uncertainty"]["timing_unit"] == "hours"

    classifications = {
        row["classification"]: row
        for row in dimensions["outcome_classification_summary"]
    }
    assert classifications["continuation"]["rate_fraction"] == 0.0
    assert classifications["reversal"]["rate_fraction"] == 1.0
    assert classifications["breakout_failure"]["rate_fraction"] == 1.0
    assert classifications["fade_success"]["sample_status"] == "no_sample"
    assert classifications["risk_event_validation"]["sample_status"] == "no_sample"

    expiry = {row["cohort"]: row for row in dimensions["expiry_status_cohorts"]}
    assert expiry["expired_with_directional_resolution"]["episode_count"] == 1
    assert expiry["expired_without_resolution"]["sample_status"] == "no_sample"
    post_expiry = {
        row["cohort"]: row for row in dimensions["post_expiry_status_cohorts"]
    }
    assert post_expiry["continuation"][
        "mean_post_expiry_directional_return_fraction"
    ] == pytest.approx(0.04)
    assert post_expiry["reversal"]["sample_status"] == "no_sample"
    assert dimensions["policy_eligible"] is False
