"""Robust summary coverage for outcome-joined replay baselines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_replay_benchmark_metrics,
    empirical_replay_controls,
)


_START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _horizon(
    days: int,
    value: float | None,
    *,
    status: str = "matured",
    unit: str = "fraction",
    mfe: float | None = 0.08,
    mae: float | None = -0.04,
) -> dict[str, object]:
    return {
        "horizon": f"{days}d",
        "horizon_days": days,
        "maturity_status": status,
        "due_at": (_START + timedelta(days=days)).isoformat(),
        "raw_return_fraction": value,
        "direction_adjusted_return_fraction": value,
        "max_favorable_excursion_fraction": mfe,
        "max_adverse_excursion_fraction": mae,
        "time_to_mfe_hours": 24,
        "time_to_mae_hours": 48,
        "time_to_invalidation_hours": None,
        "path_status": "complete" if status == "matured" else status,
        "path_missing_reasons": [],
        "missing_reasons": [] if status == "matured" else ["horizon_not_due"],
        "return_unit": unit,
    }


def _selection(index: int, primary_return: float) -> dict[str, object]:
    observed = _START + timedelta(days=index)
    return {
        "selection_id": f"selection-{index:02d}",
        "policy": "matched_non_signal",
        "observation": {
            "symbol": f"T{index:02d}",
            "observed_at": observed.isoformat(),
        },
        "outcome": {
            "status": "matured",
            "primary_horizon": "3d",
            "return_unit": "fraction",
            "horizons": {
                "1d": _horizon(1, primary_return / 2.0),
                "3d": _horizon(3, primary_return),
                "7d": _horizon(7, primary_return * 2.0),
                "14d": _horizon(14, None, status="pending", mfe=None, mae=None),
            },
        },
    }


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value * 1.02 for value in closes],
            "low": [value * 0.98 for value in closes],
            "close": closes,
            "volume": [1_000.0] * len(closes),
        },
        index=pd.date_range(_START, periods=len(closes), freq="1D", tz="UTC"),
    )


def test_benchmark_metrics_cover_robust_risk_cost_and_holding_summaries() -> None:
    returns = [-0.05, -0.04, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.04, 0.10]
    row = empirical_replay_benchmark_metrics.build_benchmark_row(
        "matched_non_signal",
        [_selection(index, value) for index, value in enumerate(returns)],
        {},
        eligible_group_count=10,
        detail_row_limit=4,
    )

    assert row["status"] == "available"
    assert row["sample_size"] == 10
    assert row["hit_rate"] == pytest.approx(0.5)
    assert row["mean_primary_direction_adjusted_return_fraction"] == pytest.approx(
        0.005
    )
    assert row["median_primary_direction_adjusted_return_fraction"] == 0.0
    assert row[
        "trimmed_mean_10pct_primary_direction_adjusted_return_fraction"
    ] == pytest.approx(0.0)
    assert row[
        "downside_5pct_primary_direction_adjusted_return_fraction"
    ] == pytest.approx(-0.0455)
    assert row["worst_primary_direction_adjusted_return_fraction"] == -0.05
    assert row["chronological_drawdown_proxy_fraction"] == pytest.approx(-0.15)
    assert row["mean_primary_mfe_fraction"] == pytest.approx(0.08)
    assert row["mean_primary_mae_fraction"] == pytest.approx(-0.04)
    assert row["break_even_mean_round_trip_cost_bps"] == pytest.approx(50.0)
    assert [
        item["round_trip_cost_bps"] for item in row["cost_sensitivity"]["scenarios"]
    ] == [0, 20, 50, 100, 200]
    assert row["cost_sensitivity"]["scenarios"][1][
        "mean_net_direction_adjusted_return_fraction"
    ] == pytest.approx(0.003)
    holding = row["holding_period_sensitivity"]
    assert holding["horizon_order"] == ["1d", "3d", "7d", "14d"]
    assert [item["sample_size"] for item in holding["horizons"]] == [10, 10, 10, 0]
    assert holding["horizons"][3]["pending_outcome_count"] == 10
    assert row["selections_truncated"] is True
    assert len(row["selections"]) == 4
    assert row["selection_uses_outcomes"] is False
    assert row["causal_claim"] is False
    assert row["policy_eligible"] is False
    assert row["return_unit"] == "fraction"


def test_empty_benchmark_keeps_every_metric_and_sensitivity_explicit() -> None:
    row = empirical_replay_benchmark_metrics.build_benchmark_row(
        "rsi_only",
        [],
        {"rsi_unavailable": 4},
        eligible_group_count=4,
        detail_row_limit=256,
    )

    assert row["status"] == "unavailable"
    assert row["metric_status"] == "unavailable"
    assert row["sample_size"] == 0
    assert row["hit_rate"] is None
    assert row["mean_primary_mfe_fraction"] is None
    assert row["mean_primary_mae_fraction"] is None
    assert row["chronological_drawdown_proxy_fraction"] is None
    assert row["break_even_mean_round_trip_cost_bps"] is None
    assert row["unavailable_reason_counts"] == {"rsi_unavailable": 4}
    assert all(
        item["mean_net_direction_adjusted_return_fraction"] is None
        for item in row["cost_sensitivity"]["scenarios"]
    )
    assert all(
        item["status"] == "unavailable"
        for item in row["holding_period_sensitivity"]["horizons"]
    )


def test_non_fraction_outcome_is_not_silently_converted() -> None:
    selection = _selection(0, 10.0)
    selection["outcome"]["horizons"]["3d"]["return_unit"] = "percent_points"

    row = empirical_replay_benchmark_metrics.build_benchmark_row(
        "matched_non_signal",
        [selection],
        {},
        eligible_group_count=1,
        detail_row_limit=256,
    )

    assert row["matured_outcome_count"] == 1
    assert row["metric_status"] == "unavailable"
    assert row["sample_size"] == 0
    assert row["mean_primary_direction_adjusted_return_fraction"] is None
    assert row["primary_outcome_metrics"]["unavailable_reason_counts"] == {
        "return_unit_not_fraction": 1
    }
    assert row["cost_sensitivity"]["status"] == "unavailable"
    assert row["break_even_mean_round_trip_cost_bps"] is None


def test_compact_joined_outcome_retains_all_horizon_path_fields() -> None:
    raw = {
        "idea_id": "idea-1",
        "canonical_asset_id": "asset-1",
        "symbol": "AAA",
        "observed_at": _START.isoformat(),
        "directional_bias": "long",
        "status": "matured",
        "primary_horizon": "3d",
        "primary_horizon_return": 0.03,
        "primary_direction_adjusted_return": 0.03,
        "max_favorable_excursion": 0.08,
        "max_adverse_excursion": -0.04,
        "return_unit": "fraction",
        "research_only": True,
        "auto_apply": False,
        "horizons": {
            f"{days}d": _horizon(days, days / 100.0)
            for days in (14, 3, 1, 7)
        },
    }

    compact = empirical_replay_benchmark_metrics.compact_joined_path_outcome(raw)

    assert list(compact["horizons"]) == ["1d", "3d", "7d", "14d"]
    assert compact["preserved_horizon_order"] == ["1d", "3d", "7d", "14d"]
    assert compact["primary_horizon_preserved"] is True
    assert compact["horizons"]["14d"]["max_favorable_excursion_fraction"] == 0.08
    assert compact["horizons"]["14d"]["max_adverse_excursion_fraction"] == -0.04
    assert compact["horizons"]["14d"]["return_unit"] == "fraction"


def test_controls_integrate_all_baseline_metrics_after_outcome_join() -> None:
    observation = {
        "canonical_asset_id": "asset-aaa",
        "symbol": "AAA",
        "observed_at": _START.isoformat(),
        "partition": "validation",
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
    frames = {
        "AAA": _frame([100.0 + index for index in range(15)]),
        "BTC": _frame([200.0 + index for index in range(15)]),
        "ETH": _frame([300.0 + index for index in range(15)]),
    }
    result = empirical_replay_controls.build_empirical_replay_controls(
        [observation],
        [],
        [],
        frames,
        evaluated_at=_START + timedelta(days=14),
    )

    assert len(result["benchmark_rows"]) == 8
    for row in result["benchmark_rows"]:
        assert row["metric_schema_id"] == (
            "decision_radar.empirical_benchmark_metrics"
        )
        assert "primary_outcome_metrics" in row
        assert "cost_sensitivity" in row
        assert "holding_period_sensitivity" in row
        assert row["return_unit"] == "fraction"
        assert row["selection_uses_outcomes"] is False
        assert row["causal_claim"] is False
    raw_mover = next(
        row
        for row in result["benchmark_rows"]
        if row["policy"] == "same_day_top_raw_mover"
    )
    outcome = raw_mover["selections"][0]["outcome"]
    assert list(outcome["horizons"]) == ["1d", "3d", "7d", "14d"]
    assert raw_mover["sample_size"] == 1
    assert raw_mover["primary_outcome_metrics"]["mfe_sample_size"] == 1
    assert raw_mover["primary_outcome_metrics"]["mae_sample_size"] == 1
