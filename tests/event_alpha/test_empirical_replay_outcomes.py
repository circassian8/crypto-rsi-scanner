"""Pure daily path and fixed-start episode tests for empirical replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from crypto_rsi_scanner.event_alpha.operations import empirical_replay_outcomes


_START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _frame(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    start: datetime = _START,
) -> pd.DataFrame:
    highs = highs or [value * 1.01 for value in closes]
    lows = lows or [value * 0.99 for value in closes]
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes, "volume": 1_000.0},
        index=pd.date_range(start=start, periods=len(closes), freq="1D", tz="UTC"),
    )


def _idea(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "idea_id": "idea-alpha",
        "candidate_id": "candidate-alpha",
        "core_opportunity_id": "core-alpha",
        "canonical_asset_id": "asset-alpha",
        "symbol": "AAA",
        "observed_at": _START.isoformat(),
        "directional_bias": "long",
        "anomaly_family": "breakout",
        "radar_route": "actionable_watch",
        "actionability_score": 70.0,
        "evidence_confidence_score": 65.0,
        "risk_score": 40.0,
        "urgency_score": 60.0,
        "chase_risk_score": 25.0,
        "market_phase": "expansion",
        "catalyst_status": "unknown",
        "spread_status": "unavailable",
        "derivatives_status": "unavailable",
        "expires_at": (_START + timedelta(days=2)).isoformat(),
        "partition": "fixture",
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led", "technical_led"],
        "market_regime": "bull",
        "liquidity_tier": "high",
        "liquidity_usd": 5_000_000.0,
        "trailing_quote_volume": 4_000_000.0,
        "data_quality_mode": "historical_ohlcv",
        "point_in_time_universe_member": True,
        "point_in_time_volume_rank": 17,
        "baseline_status": "complete",
        "operator_visible_idea": True,
        "catalyst_evidence_timing": "unavailable",
        "decision_projection": {
            "radar_route": "actionable_watch",
            "actionability_score": 70.0,
            "directional_bias": "long",
            "research_only": True,
        },
    }
    row.update(overrides)
    return row


def _benchmarks() -> dict[str, pd.DataFrame]:
    return {
        "BTC": _frame([100.0, 102.0, 105.0, 110.0] + [110.0] * 11),
        "ETH": _frame([200.0, 202.0, 210.0, 220.0] + [220.0] * 11),
    }


def test_primary_and_sensitivity_returns_are_fractional_and_same_bar_is_excluded() -> None:
    asset = _frame(
        [100.0, 110.0, 120.0, 130.0] + [130.0] * 11,
        highs=[1_000.0, 112.0, 125.0, 135.0] + [135.0] * 11,
        lows=[1.0, 94.0, 90.0, 85.0] + [85.0] * 11,
    )
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(),
        {"AAA": asset, **_benchmarks()},
        evaluated_at=_START + timedelta(days=14),
    )

    assert list(outcome["horizons"]) == ["1d", "3d", "7d", "14d"]
    primary = outcome["horizons"]["3d"]
    assert primary["maturity_status"] == "matured"
    assert primary["raw_return_fraction"] == pytest.approx(0.30)
    assert primary["direction_adjusted_return_fraction"] == pytest.approx(0.30)
    assert primary["benchmark_returns_fraction"] == pytest.approx(
        {"BTC": 0.10, "ETH": 0.10}
    )
    assert primary["relative_returns_fraction"] == pytest.approx(
        {"BTC": 0.20, "ETH": 0.20}
    )
    assert primary["max_favorable_excursion_fraction"] == pytest.approx(0.35)
    assert primary["max_adverse_excursion_fraction"] == pytest.approx(-0.15)
    assert primary["time_to_mfe_hours"] == 72.0
    assert primary["time_to_mae_hours"] == 72.0
    assert primary["time_to_invalidation_hours"] == 24.0
    assert primary["path_bar_count"] == 3
    assert primary["same_idea_bar_excluded"] is True
    assert outcome["max_favorable_excursion"] != pytest.approx(9.0)
    assert outcome["max_adverse_excursion"] != pytest.approx(-0.99)
    assert outcome["return_unit"] == "fraction"
    assert outcome["timing_resolution"] == {
        "basis": "daily_ohlcv",
        "minimum_increment_hours": 24,
        "intraday_timing_available": False,
        "same_idea_bar_extremes_included": False,
    }


@pytest.mark.parametrize(
    ("direction", "classification"),
    [
        ("fade_short_review", "fade_success"),
        ("risk", "risk_event_validation"),
    ],
)
def test_short_and_risk_direction_adjustment_and_classification(
    direction: str,
    classification: str,
) -> None:
    asset = _frame(
        [100.0, 95.0, 85.0, 80.0] + [80.0] * 11,
        highs=[101.0, 105.0, 98.0, 90.0] + [90.0] * 11,
        lows=[99.0, 90.0, 80.0, 75.0] + [75.0] * 11,
    )
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(directional_bias=direction),
        {"AAA": asset, **_benchmarks()},
        evaluated_at=_START + timedelta(days=14),
    )

    primary = outcome["horizons"]["3d"]
    assert outcome["primary_horizon_return"] == pytest.approx(-0.20)
    assert outcome["primary_direction_adjusted_return"] == pytest.approx(0.20)
    assert outcome["primary_relative_return_vs_btc"] == pytest.approx(-0.30)
    assert primary["direction_adjusted_relative_returns_fraction"]["BTC"] == (
        pytest.approx(0.30)
    )
    assert outcome["max_favorable_excursion"] == pytest.approx(0.25)
    assert outcome["max_adverse_excursion"] == pytest.approx(-0.05)
    assert outcome["classifications"]["continuation"] is True
    assert outcome["classifications"][classification] is True


def test_breakout_failure_and_expiry_behavior_are_descriptive() -> None:
    failed = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {
            "AAA": _frame(
                [100.0, 110.0, 105.0, 90.0] + [90.0] * 11,
                highs=[101.0, 115.0, 112.0, 105.0] + [105.0] * 11,
                lows=[99.0, 98.0, 95.0, 85.0] + [85.0] * 11,
            ),
            **_benchmarks(),
        },
        evaluated_at=_START + timedelta(days=14),
    )

    assert failed["classifications"]["reversal"] is True
    assert failed["classifications"]["breakout_failure"] is True
    assert failed["classifications"]["descriptive_only"] is True

    expiry = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=(_START + timedelta(days=1)).isoformat()),
        {
            "AAA": _frame([100.0, 95.0, 110.0, 120.0] + [120.0] * 11),
            **_benchmarks(),
        },
        evaluated_at=_START + timedelta(days=14),
    )
    assert expiry["expiry"]["status"] == "expired_without_resolution"
    assert expiry["expiry"]["expired_without_resolution"] is True
    assert expiry["expiry"]["post_expiry_assessment_horizon"] == "3d"
    assert expiry["expiry"]["post_expiry_continuation"] is True
    assert expiry["expiry"]["post_expiry_reversal"] is False
    assert expiry["classifications"]["post_expiry_continuation"] is True


def test_appending_future_bars_cannot_change_matured_earlier_horizons() -> None:
    initial_asset = _frame([100.0, 110.0, 120.0, 130.0])
    initial = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": initial_asset},
        evaluated_at=_START + timedelta(days=3),
    )
    future = _frame(
        [50.0, 200.0] + [140.0] * 9,
        highs=[250.0] * 11,
        lows=[10.0] * 11,
        start=_START + timedelta(days=4),
    )
    extended_asset = pd.concat([initial_asset, future])
    extended = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": extended_asset},
        evaluated_at=_START + timedelta(days=14),
    )

    assert initial["horizons"]["1d"] == extended["horizons"]["1d"]
    assert initial["horizons"]["3d"] == extended["horizons"]["3d"]
    assert initial["horizons"]["7d"]["maturity_status"] == "pending"
    assert extended["horizons"]["7d"]["maturity_status"] == "matured"


def test_fixed_start_episode_freezes_first_representative_and_retains_progression() -> None:
    first = _idea(
        idea_id="first",
        symbol="MISSING",
        observed_at=_START.isoformat(),
        radar_route="dashboard_watch",
        actionability_score=45.0,
        market_phase="emerging",
        catalyst_status="unknown",
        spread_status="unavailable",
        derivatives_status="unavailable",
        expires_at=(_START + timedelta(days=1)).isoformat(),
        decision_projection={"radar_route": "dashboard_watch", "marker": "first"},
    )
    dependent = _idea(
        idea_id="dependent",
        symbol="AAA",
        observed_at=(_START + timedelta(hours=12)).isoformat(),
        radar_route="actionable_watch",
        actionability_score=75.0,
        evidence_confidence_score=80.0,
        risk_score=30.0,
        urgency_score=85.0,
        chase_risk_score=40.0,
        market_phase="expansion",
        catalyst_status="confirmed",
        spread_status="verified_good",
        derivatives_status="observed",
        expires_at=(_START + timedelta(days=3)).isoformat(),
        decision_projection={"radar_route": "actionable_watch", "marker": "dependent"},
    )
    exact_boundary = _idea(
        idea_id="boundary",
        observed_at=(_START + timedelta(hours=24)).isoformat(),
    )
    outside_boundary = _idea(
        idea_id="outside-boundary",
        observed_at=(_START + timedelta(hours=24, seconds=1)).isoformat(),
    )
    original_rows = deepcopy([first, dependent, exact_boundary, outside_boundary])
    asset_frame = _frame([100.0] * 15, start=_START + timedelta(hours=12))
    original_frame = asset_frame.copy(deep=True)

    result = empirical_replay_outcomes.build_empirical_replay_outcomes(
        [outside_boundary, exact_boundary, dependent, first],
        {"AAA": asset_frame},
        evaluated_at=_START + timedelta(days=14),
    )

    assert result["episode_count"] == 2
    assert result["dependent_repeat_count"] == 2
    assert result["episode_boundary_rule"] == (
        "member_observed_at_lte_episode_start_plus_window"
    )
    assert result["schema_version"] == 3
    assert result["episodes"][0]["window_end_inclusive_at"] == (
        "2025-01-02T00:00:00+00:00"
    )
    assert "window_end_exclusive_at" not in result["episodes"][0]
    episode = result["episodes"][0]
    assert episode["representative_idea_id"] == "first"
    assert episode["representative_reselected"] is False
    assert episode["representative_outcome"]["status"] == "missing_data"
    assert episode["member_count"] == 3
    assert [row["radar_route"] for row in episode["member_progression"]] == [
        "dashboard_watch",
        "actionable_watch",
        "actionable_watch",
    ]
    assert episode["member_progression"][1]["actionability_score"] == 75.0
    assert episode["member_progression"][1]["market_phase"] == "expansion"
    assert episode["member_progression"][1]["catalyst_status"] == "confirmed"
    assert episode["member_progression"][1]["spread_status"] == "verified_good"
    assert episode["member_progression"][1]["derivatives_status"] == "observed"
    assert episode["member_progression"][1]["decision_projection"]["marker"] == (
        "dependent"
    )
    assert episode["representative"]["point_in_time_volume_rank"] == 17.0
    assert episode["candidate_family_id"] == "asset-alpha|breakout"
    assert episode["representative"]["candidate_family_id"] == (
        "asset-alpha|breakout"
    )
    assert episode["representative_outcome"]["candidate_family_id"] == (
        "asset-alpha|breakout"
    )
    assert episode["representative"]["episode_id"] == episode["episode_id"]
    assert episode["representative_outcome"]["episode_id"] == episode["episode_id"]
    assert episode["representative"]["partition"] == "fixture"
    assert episode["representative"]["primary_thesis_origin"] == "market_led"
    assert episode["representative"]["market_regime"] == "bull"
    assert episode["representative"]["liquidity_tier"] == "high"
    assert episode["representative"]["data_quality_mode"] == "historical_ohlcv"
    assert episode["representative"]["point_in_time_membership"] is True
    assert result["episodes"][1]["representative_idea_id"] == "outside-boundary"
    assert [first, dependent, exact_boundary, outside_boundary] == original_rows
    assert_frame_equal(asset_frame, original_frame)
    assert set(result["safety"].values()) <= {True, False, 0}
    assert result["safety"]["provider_calls"] == 0
    assert result["safety"]["writes"] == 0
    sensitivity = result["episode_window_sensitivity"]
    assert sensitivity["outcomes_used"] is False
    assert [row["window_hours"] for row in sensitivity["windows"]] == [12, 24, 48]
    assert [row["episode_count"] for row in sensitivity["windows"]] == [2, 2, 1]
    assert [row["dependent_repeat_count"] for row in sensitivity["windows"]] == [2, 2, 3]
    assert all(
        row["representative_reselection"] is False
        and row["outcomes_used_for_grouping"] is False
        and row["outcomes_computed_for_sensitivity"] is False
        and row["representative_count"] == row["episode_count"]
        and len(row["representative_idea_ids_digest"]) == 64
        for row in sensitivity["windows"]
    )


def test_pending_missing_exit_and_missing_benchmarks_remain_distinct() -> None:
    complete_asset = _frame([100.0, 105.0, 110.0, 115.0])
    pending = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": complete_asset},
        evaluated_at=_START + timedelta(days=2),
    )
    assert pending["status"] == "pending"
    assert pending["horizons"]["3d"]["missing_reasons"] == ["horizon_not_due"]

    missing_exit = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": complete_asset.iloc[:3]},
        evaluated_at=_START + timedelta(days=3),
    )
    assert missing_exit["status"] == "missing_data"
    assert "exit_bar_missing_or_invalid" in missing_exit["missing_reasons"]

    missing_benchmarks = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": complete_asset},
        evaluated_at=_START + timedelta(days=3),
    )
    primary = missing_benchmarks["horizons"]["3d"]
    assert missing_benchmarks["status"] == "matured"
    assert primary["benchmark_status"] == {
        "BTC": "missing_data",
        "ETH": "missing_data",
    }
    assert primary["relative_returns_fraction"] == {"BTC": None, "ETH": None}
    assert primary["benchmark_missing_reasons"]["BTC"] == [
        "benchmark_price_frame_missing"
    ]


def test_neutral_direction_keeps_raw_return_but_not_directional_claims() -> None:
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(directional_bias="neutral", expires_at=None),
        {"AAA": _frame([100.0, 110.0, 120.0, 130.0])},
        evaluated_at=_START + timedelta(days=3),
    )

    assert outcome["primary_horizon_return"] == pytest.approx(0.30)
    assert outcome["primary_direction_adjusted_return"] is None
    assert outcome["direction_status"] == "not_scoreable"
    assert "directional_bias_not_scoreable" in outcome["missing_reasons"]
    assert outcome["classifications"]["continuation"] is None


def test_binance_quote_pair_names_are_valid_benchmark_aliases() -> None:
    benchmark_frames = _benchmarks()
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {
            "AAA": _frame([100.0, 110.0, 120.0, 130.0]),
            "BTCUSDT": benchmark_frames["BTC"],
            "ETHUSDT": benchmark_frames["ETH"],
        },
        evaluated_at=_START + timedelta(days=3),
    )

    primary = outcome["horizons"]["3d"]
    assert primary["benchmark_status"] == {"BTC": "matured", "ETH": "matured"}
    assert outcome["primary_relative_return_vs_btc"] == pytest.approx(0.20)
    assert outcome["primary_relative_return_vs_eth"] == pytest.approx(0.20)


def test_bounded_row_sequences_from_replay_dataset_are_accepted() -> None:
    frame = _frame([100.0, 110.0, 120.0, 130.0])
    rows = [
        {
            "observed_at": timestamp.isoformat(),
            "close": float(row.close),
            "high": float(row.high),
            "low": float(row.low),
        }
        for timestamp, row in frame.iterrows()
    ]
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": tuple(rows)},
        evaluated_at=_START + timedelta(days=3),
    )

    assert outcome["status"] == "matured"
    assert outcome["primary_horizon_return"] == pytest.approx(0.30)


def test_flat_path_iterator_normalizes_frames_once_for_many_independent_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = empirical_replay_outcomes._normalize_price_frames
    calls = 0

    def counted(frames):
        nonlocal calls
        calls += 1
        return original(frames)

    monkeypatch.setattr(empirical_replay_outcomes, "_normalize_price_frames", counted)
    outcomes = list(
        empirical_replay_outcomes.iter_empirical_path_outcomes(
            (
                _idea(idea_id="idea-one", candidate_id="candidate-one"),
                _idea(idea_id="idea-two", candidate_id="candidate-two"),
            ),
            {"AAA": _frame([100.0, 110.0, 120.0, 130.0])},
            evaluated_at=_START + timedelta(days=3),
        )
    )

    assert calls == 1
    assert [row["idea_id"] for row in outcomes] == ["idea-one", "idea-two"]
    assert all(row["status"] == "matured" for row in outcomes)


def test_partition_embargo_keeps_valid_horizons_within_boundary() -> None:
    observed = datetime(2022, 12, 31, tzinfo=timezone.utc)
    cutoff = "2023-01-15T00:00:00+00:00"
    outcome = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(
            observed_at=observed.isoformat(),
            partition="development",
            replay_partition="development",
            expires_at="2023-01-15T00:00:00Z",
        ),
        {
            "AAA": _frame([100.0] + [500.0] * 19, start=observed),
            "BTC": _frame([100.0] + [400.0] * 19, start=observed),
            "ETH": _frame([100.0] + [300.0] * 19, start=observed),
        },
        evaluated_at=observed + timedelta(days=19),
    )

    assert outcome["outcome_end_exclusive"] == cutoff
    assert outcome["partition_outcome_boundary"]["status"] == "enforced"
    for label in ("1d", "3d", "7d", "14d"):
        horizon = outcome["horizons"][label]
        assert horizon["maturity_status"] == "matured"
        assert horizon["missing_reasons"] == []
        assert horizon["exit_price"] == pytest.approx(500.0)
        assert horizon["raw_return_fraction"] == pytest.approx(4.0)
        assert horizon["path_status"] == "complete"
        assert horizon["benchmark_status"] == {
            "BTC": "matured",
            "ETH": "matured",
        }
    assert outcome["horizons"]["14d"]["due_at"] < cutoff
    assert outcome["status"] == "matured"
    assert outcome["expiry"]["status"] == "withheld_partition_boundary"
    assert outcome["expiry"]["expiry_price"] is None
    assert outcome["expiry"]["missing_reasons"] == [
        "horizon_crosses_partition_outcome_boundary"
    ]


def test_values_at_or_after_partition_cutoff_cannot_change_outcome() -> None:
    observed = datetime(2022, 12, 31, tzinfo=timezone.utc)
    before_cutoff = [100.0, 110.0] + [120.0] * 13
    baseline = before_cutoff + [130.0] * 5
    changed = before_cutoff + [9_999.0, 0.01, 8_888.0, 0.02, 7_777.0]
    idea = _idea(
        observed_at=observed.isoformat(),
        partition="development",
        replay_partition="development",
        expires_at="2023-01-15T00:00:00Z",
    )

    first = empirical_replay_outcomes.build_empirical_path_outcome(
        idea,
        {
            "AAA": _frame(baseline, start=observed),
            "BTC": _frame(baseline, start=observed),
            "ETH": _frame(baseline, start=observed),
        },
        evaluated_at=observed + timedelta(days=19),
    )
    replaced = empirical_replay_outcomes.build_empirical_path_outcome(
        idea,
        {
            "AAA": _frame(changed, start=observed),
            "BTC": _frame(changed, start=observed),
            "ETH": _frame(changed, start=observed),
        },
        evaluated_at=observed + timedelta(days=19),
    )

    assert first == replaced
    assert first["horizons"]["1d"]["raw_return_fraction"] == pytest.approx(0.10)
    assert first["horizons"]["3d"]["maturity_status"] == "matured"
    assert first["expiry"]["status"] == "withheld_partition_boundary"
    assert first["expiry"]["expiry_price_observed_at"] is None


def test_in_boundary_outcome_and_fixture_without_cutoff_remain_unchanged() -> None:
    observed = datetime(2022, 12, 29, tzinfo=timezone.utc)
    production = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(
            observed_at=observed.isoformat(),
            partition="development",
            replay_partition="development",
            candidate_family_id="asset-alpha|custom-breakout",
            expires_at=None,
        ),
        {"AAA": _frame([100.0, 110.0, 120.0, 130.0], start=observed)},
        evaluated_at=observed + timedelta(days=3),
    )
    fixture = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(expires_at=None),
        {"AAA": _frame([100.0, 110.0, 120.0, 130.0])},
        evaluated_at=_START + timedelta(days=3),
    )

    assert production["horizons"]["3d"]["maturity_status"] == "matured"
    assert production["primary_horizon_return"] == pytest.approx(0.30)
    assert production["candidate_family_id"] == "asset-alpha|custom-breakout"
    assert production["horizons"]["3d"]["path_status"] == "complete"
    assert production["horizons"]["3d"]["partition_outcome_boundary_status"] == (
        "within_boundary"
    )
    assert fixture["partition_outcome_boundary"]["status"] == "not_applicable"
    assert fixture["outcome_end_exclusive"] is None
    assert fixture["primary_horizon_return"] == pytest.approx(0.30)


def test_claimed_frozen_partition_enforces_start_and_end_bounds() -> None:
    start = datetime(2021, 6, 12, tzinfo=timezone.utc)
    accepted = empirical_replay_outcomes.build_empirical_path_outcome(
        _idea(
            observed_at=start.isoformat(),
            partition="development",
            replay_partition="development",
            expires_at=None,
        ),
        {"AAA": _frame([100.0, 110.0, 120.0, 130.0], start=start)},
        evaluated_at=start + timedelta(days=3),
    )
    assert accepted["partition"] == "development"

    for observed in (
        datetime(2023, 1, 1, tzinfo=timezone.utc),
        datetime(2023, 1, 10, tzinfo=timezone.utc),
    ):
        with pytest.raises(
            ValueError, match="observed_at outside claimed frozen partition"
        ):
            empirical_replay_outcomes.build_empirical_path_outcome(
                _idea(
                    observed_at=observed.isoformat(),
                    partition="development",
                    replay_partition="development",
                    expires_at=None,
                ),
                {"AAA": _frame([100.0], start=observed)},
                evaluated_at=observed,
            )


def test_unknown_nonfixture_partition_is_rejected() -> None:
    with pytest.raises(ValueError, match="claimed replay partition unknown"):
        empirical_replay_outcomes.build_empirical_path_outcome(
            _idea(partition="invented", expires_at=None),
            {"AAA": _frame([100.0])},
            evaluated_at=_START,
        )


def test_bundle_exposes_exact_partition_boundary_contract() -> None:
    observed = datetime(2022, 12, 31, tzinfo=timezone.utc)
    result = empirical_replay_outcomes.build_empirical_replay_outcomes(
        [
            _idea(
                observed_at=observed.isoformat(),
                partition="development",
                replay_partition="development",
                expires_at=None,
            )
        ],
        {"AAA": _frame([100.0] * 20, start=observed)},
        evaluated_at=observed + timedelta(days=19),
    )

    assert result["partition_outcome_boundary_rule"] == {
        "partition_field_precedence": ["replay_partition", "partition"],
        "protocol_cutoff_field": "outcome_end_exclusive",
        "rule": "horizon_due_at_lt_outcome_end_exclusive",
        "observation_read_rule": (
            "outcome_observation_at_lt_partition_outcome_end_exclusive"
        ),
        "due_at_equal_cutoff": "withheld_partition_boundary",
        "withheld_reason": "horizon_crosses_partition_outcome_boundary",
        "fixture_without_cutoff": "not_applicable",
    }
    assert result["partition_outcome_boundaries"] == [
        {
            "partition": "development",
            "status": "enforced",
            "outcome_end_exclusive": "2023-01-15T00:00:00+00:00",
            "cutoff_source": "frozen_protocol_partition.outcome_end_exclusive",
            "rule": "horizon_due_at_lt_outcome_end_exclusive",
            "observation_read_rule": (
                "outcome_observation_at_lt_partition_outcome_end_exclusive"
            ),
            "due_at_equal_cutoff": "withheld_partition_boundary",
            "withheld_reason": "horizon_crosses_partition_outcome_boundary",
        }
    ]
    episode = result["episodes"][0]
    assert episode["replay_partition"] == "development"
    assert episode["outcome_end_exclusive"] == "2023-01-15T00:00:00+00:00"
    assert episode["representative"]["outcome_end_exclusive"] == (
        "2023-01-15T00:00:00+00:00"
    )
