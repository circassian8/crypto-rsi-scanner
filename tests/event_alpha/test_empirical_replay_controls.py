"""Point-in-time control, benchmark, and missed-move contract tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from crypto_rsi_scanner.event_alpha.operations import empirical_replay_controls


_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
_BENCHMARK_POLICIES = [
    "matched_non_signal",
    "same_day_top_raw_mover",
    "volume_anomaly_only",
    "rsi_only",
    "btc_buy_and_hold_context",
    "eth_buy_and_hold_context",
    "top_relative_strength",
    "late_momentum_fade",
]


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
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000.0] * len(closes),
        },
        index=pd.date_range(start=start, periods=len(closes), freq="1D", tz="UTC"),
    )


def _observation(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "canonical_asset_id": f"asset-{symbol.casefold()}",
        "symbol": symbol,
        "observed_at": _START.isoformat(),
        "partition": "final_test",
        "market_regime": "bull",
        "liquidity_tier": "high",
        "liquidity_usd": 8_000_000.0,
        "trailing_quote_volume_usd": 5_000_000.0,
        "point_in_time_universe_member": True,
        "baseline_status": "warm",
        "data_quality_mode": "historical_ohlcv",
        "return_unit": "percent_points",
        "return_24h": 4.0,
        "return_72h": 6.0,
        "return_7d": 8.0,
        "relative_return_vs_btc_24h": 3.0,
        "volume_zscore_24h": 2.0,
        "rsi": 65.0,
    }
    row.update(overrides)
    return row


def _idea(symbol: str = "AAA", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "idea_id": f"idea-{symbol.casefold()}",
        "canonical_asset_id": f"asset-{symbol.casefold()}",
        "symbol": symbol,
        "observed_at": _START.isoformat(),
        "partition": "final_test",
        "market_regime": "bull",
        "liquidity_tier": "high",
        "directional_bias": "long",
        "anomaly_family": "market_breakout",
        "radar_route": "actionable_watch",
        "operator_visible": True,
        "decision_projection": {
            "radar_route": "actionable_watch",
            "directional_bias": "long",
            "research_only": True,
        },
    }
    row.update(overrides)
    return row


def _trace(
    symbol: str,
    *,
    failure_stage: str = "no_anomaly_generated",
    trace_status: str = "no_anomaly",
) -> dict[str, object]:
    return {
        "canonical_asset_id": f"asset-{symbol.casefold()}",
        "symbol": symbol,
        "observed_at": _START.isoformat(),
        "trace_status": trace_status,
        "failure_stage": failure_stage,
        "operator_visible": False,
        "radar_route": "diagnostic",
        "hard_blockers": [],
    }


def _price_frames() -> dict[str, pd.DataFrame]:
    return {
        "AAA": _frame([100.0, 103.0, 107.0, 115.0] + [115.0] * 11),
        "BBB": _frame([100.0, 101.0, 103.0, 108.0] + [108.0] * 11),
        "CCC": _frame([100.0, 102.0, 105.0, 109.0] + [109.0] * 11),
        "DDD": _frame([100.0, 104.0, 108.0, 116.0] + [116.0] * 11),
        "BTC": _frame([100.0, 101.0, 102.0, 103.0] + [103.0] * 11),
        "ETH": _frame([200.0, 202.0, 204.0, 206.0] + [206.0] * 11),
    }


def test_matched_control_selection_is_deterministic_outcome_blind_and_excludes_signals() -> None:
    observations = [
        _observation("AAA"),
        _observation("BBB"),
        _observation("CCC"),
        _observation("DDD"),
    ]
    ideas = [_idea("AAA"), _idea("DDD")]

    original = empirical_replay_controls.select_matched_non_signal_controls(
        observations, ideas
    )
    polluted = deepcopy(observations)
    for index, row in enumerate(polluted):
        row["future_return_3d"] = 99_999.0 - index
        row["outcome"] = {"primary_horizon_return": -99_999.0 + index}
        row["future_high"] = 1_000_000.0 + index
    repeated = empirical_replay_controls.select_matched_non_signal_controls(
        list(reversed(polluted)), list(reversed(ideas))
    )

    assert original["selection_digest"] == repeated["selection_digest"]
    assert original["selection_uses_outcomes"] is False
    assert original["selected_control_count"] == 2
    selected_assets = {
        row["control_observation"]["canonical_asset_id"]
        for row in original["rows"]
        if row["status"] == "selected"
    }
    assert selected_assets <= {"asset-bbb", "asset-ccc"}
    assert selected_assets.isdisjoint({"asset-aaa", "asset-ddd"})


def test_future_price_append_cannot_change_selection_or_matured_three_day_outcome() -> None:
    observations = [_observation("AAA"), _observation("BBB"), _observation("CCC")]
    ideas = [_idea("AAA")]
    initial_frames = {
        key: frame.iloc[:4].copy() for key, frame in _price_frames().items()
    }
    initial = empirical_replay_controls.build_empirical_replay_controls(
        observations,
        [],
        ideas,
        initial_frames,
        evaluated_at=_START + timedelta(days=3),
    )

    extended_frames: dict[str, pd.DataFrame] = {}
    for symbol, frame in initial_frames.items():
        future = _frame(
            [1_000.0, 1.0, 2_000.0, 0.5] + [500.0] * 7,
            highs=[5_000.0] * 11,
            lows=[0.01] * 11,
            start=_START + timedelta(days=4),
        )
        extended_frames[symbol] = pd.concat([frame, future])
    extended = empirical_replay_controls.build_empirical_replay_controls(
        observations,
        [],
        ideas,
        extended_frames,
        evaluated_at=_START + timedelta(days=14),
    )

    initial_controls = initial["matched_non_signal_controls"]
    extended_controls = extended["matched_non_signal_controls"]
    assert initial_controls["selection_digest"] == extended_controls["selection_digest"]
    first = initial_controls["rows"][0]
    second = extended_controls["rows"][0]
    assert first["control_id"] == second["control_id"]
    assert first["outcome"]["horizons"]["3d"] == second["outcome"]["horizons"]["3d"]


def test_missed_moves_require_primary_endpoint_and_retain_trace_failure_stage() -> None:
    observations = [
        _observation("MFE"),
        _observation("WIN"),
        _observation("ILLIQ", trailing_quote_volume_usd=1_000_000.0),
        _observation("DROP"),
    ]
    frames = {
        # Intrahorizon high is large, but the predeclared 3d endpoint is only +5%.
        "MFE": _frame(
            [100.0, 102.0, 103.0, 105.0],
            highs=[101.0, 160.0, 150.0, 140.0],
        ),
        "WIN": _frame([100.0, 104.0, 110.0, 115.0]),
        "ILLIQ": _frame([100.0, 105.0, 110.0, 120.0]),
        "DROP": _frame([100.0, 96.0, 92.0, 85.0]),
    }
    result = empirical_replay_controls.build_empirical_replay_controls(
        observations,
        [
            _trace("MFE"),
            _trace("WIN", failure_stage="hard_gate_blocked"),
            _trace("ILLIQ"),
            _trace("DROP", failure_stage="decision_not_operator_visible"),
        ],
        [],
        frames,
        evaluated_at=_START + timedelta(days=3),
    )
    missed = result["missed_move_evaluation"]

    assert missed["maximum_future_excursion_alone_sufficient"] is False
    assert missed["evaluation_state_counts"] == {
        "endpoint_below_threshold": 1,
        "endpoint_threshold_crossed": 3,
        "matured": 4,
    }
    assert missed["endpoint_candidate_count"] == 3
    assert missed["missed_opportunity_count"] == 2
    by_symbol = {
        row["observation"]["symbol"]: row
        for row in missed["endpoint_candidates"]
    }
    assert "MFE" not in by_symbol
    assert by_symbol["WIN"]["failure_stage"] == "hard_gate_blocked"
    assert by_symbol["WIN"]["qualifies_as_missed_opportunity"] is True
    assert by_symbol["DROP"]["directional_bias"] == "risk"
    assert by_symbol["DROP"]["qualifies_as_missed_opportunity"] is True
    assert by_symbol["ILLIQ"]["qualifies_as_missed_opportunity"] is False
    assert by_symbol["ILLIQ"]["qualification_failure_reasons"] == [
        "minimum_point_in_time_liquidity_not_met"
    ]


def test_closed_benchmark_contract_emits_every_policy_even_when_unavailable() -> None:
    observations = [
        _observation(
            "AAA",
            return_24h=None,
            return_7d=None,
            relative_return_vs_btc_24h=None,
            volume_zscore_24h=None,
            rsi=None,
        )
    ]
    result = empirical_replay_controls.build_empirical_replay_controls(
        observations,
        [_trace("AAA")],
        [],
        {"AAA": _frame([100.0, 101.0, 102.0, 103.0])},
        evaluated_at=_START + timedelta(days=3),
    )

    rows = result["benchmark_rows"]
    assert result["benchmark_policy_order"] == _BENCHMARK_POLICIES
    assert [row["policy"] for row in rows] == _BENCHMARK_POLICIES
    assert len(rows) == len(_BENCHMARK_POLICIES)
    by_policy = {row["policy"]: row for row in rows}
    assert by_policy["matched_non_signal"]["status"] == "unavailable"
    assert by_policy["same_day_top_raw_mover"]["status"] == "unavailable"
    assert by_policy["volume_anomaly_only"]["status"] == "unavailable"
    assert by_policy["rsi_only"]["status"] == "unavailable"
    assert by_policy["btc_buy_and_hold_context"]["status"] == "unavailable"
    assert by_policy["eth_buy_and_hold_context"]["status"] == "unavailable"
    assert by_policy["top_relative_strength"]["status"] == "unavailable"
    assert by_policy["late_momentum_fade"]["status"] == "unavailable"
    assert all(row["selection_uses_outcomes"] is False for row in rows)
    assert all(row["causal_claim"] is False for row in rows)
    assert result["final_test_used_for_tuning"] is False
    assert result["policy_eligible"] is False
    assert result["research_only"] is True
    assert result["auto_apply"] is False
    assert all(value == 0 for value in result["safety"].values())


def test_percent_point_benchmark_features_are_normalized_without_changing_selection() -> None:
    observations = [
        _observation("AAA", return_24h=4.0, relative_return_vs_btc_24h=2.0),
        _observation("BBB", return_24h=10.0, relative_return_vs_btc_24h=7.0),
    ]
    result = empirical_replay_controls.build_empirical_replay_controls(
        observations,
        [_trace("AAA"), _trace("BBB")],
        [],
        {
            "AAA": _frame([100.0, 101.0, 102.0, 103.0]),
            "BBB": _frame([100.0, 103.0, 106.0, 110.0]),
        },
        evaluated_at=_START + timedelta(days=3),
    )
    by_policy = {row["policy"]: row for row in result["benchmark_rows"]}

    raw = by_policy["same_day_top_raw_mover"]["selections"][0]
    relative = by_policy["top_relative_strength"]["selections"][0]
    assert raw["observation"]["symbol"] == "BBB"
    assert raw["selection_metric_value"] == pytest.approx(0.10)
    assert relative["observation"]["symbol"] == "BBB"
    assert relative["selection_metric_value"] == pytest.approx(0.07)
