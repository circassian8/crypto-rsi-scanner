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
        "partition": "development",
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led", "technical_led"],
        "market_regime": "bull",
        "liquidity_tier": "high",
        "liquidity_usd": 5_000_000.0,
        "trailing_quote_volume": 4_000_000.0,
        "data_quality_mode": "historical_ohlcv",
        "point_in_time_universe_member": True,
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
    original_rows = deepcopy([first, dependent, exact_boundary])
    asset_frame = _frame([100.0] * 15, start=_START + timedelta(hours=12))
    original_frame = asset_frame.copy(deep=True)

    result = empirical_replay_outcomes.build_empirical_replay_outcomes(
        [exact_boundary, dependent, first],
        {"AAA": asset_frame},
        evaluated_at=_START + timedelta(days=14),
    )

    assert result["episode_count"] == 2
    assert result["dependent_repeat_count"] == 1
    episode = result["episodes"][0]
    assert episode["representative_idea_id"] == "first"
    assert episode["representative_reselected"] is False
    assert episode["representative_outcome"]["status"] == "missing_data"
    assert episode["member_count"] == 2
    assert [row["radar_route"] for row in episode["member_progression"]] == [
        "dashboard_watch",
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
    assert episode["representative"]["episode_id"] == episode["episode_id"]
    assert episode["representative_outcome"]["episode_id"] == episode["episode_id"]
    assert episode["representative"]["partition"] == "development"
    assert episode["representative"]["primary_thesis_origin"] == "market_led"
    assert episode["representative"]["market_regime"] == "bull"
    assert episode["representative"]["liquidity_tier"] == "high"
    assert episode["representative"]["data_quality_mode"] == "historical_ohlcv"
    assert episode["representative"]["point_in_time_membership"] is True
    assert [first, dependent, exact_boundary] == original_rows
    assert_frame_equal(asset_frame, original_frame)
    assert set(result["safety"].values()) <= {True, False, 0}
    assert result["safety"]["provider_calls"] == 0
    assert result["safety"]["writes"] == 0


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
