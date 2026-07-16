from __future__ import annotations

from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.operations import empirical_survivability


def _idea(
    episode_id: str,
    *,
    observed_at: str = "2022-02-01T00:00:00Z",
    route: str = "actionable_watch",
    volume_usd: float | None = 10_000_000.0,
    **overrides,
) -> dict:
    row = {
        "episode_id": episode_id,
        "partition": "development",
        "observed_at": observed_at,
        "canonical_asset_id": episode_id,
        "directional_bias": "long",
        "radar_route": route,
        "trailing_quote_volume_usd": volume_usd,
        "research_only": True,
    }
    row.update(overrides)
    return row


def _outcome(
    episode_id: str,
    *,
    returns: dict[int, float] | None = None,
    mae_3d: float = -0.08,
) -> dict:
    values = returns or {1: 0.10, 3: 0.21, 7: 0.30, 14: 0.40}
    return {
        "episode_id": episode_id,
        "partition": "development",
        "status": "matured",
        "primary_horizon": "3d",
        "horizons": {
            f"{days}d": {
                "horizon": f"{days}d",
                "horizon_days": days,
                "maturity_status": "matured",
                "raw_return_fraction": value,
                "direction_adjusted_return_fraction": value,
                "max_favorable_excursion_fraction": max(value, 0.02),
                "max_adverse_excursion_fraction": (
                    mae_3d if days == 3 else min(-0.01, mae_3d)
                ),
                "return_unit": "fraction",
            }
            for days, value in values.items()
        },
        "research_only": True,
        "auto_apply": False,
    }


def _build(ideas, outcomes):
    return empirical_survivability.build_empirical_survivability(
        ideas,
        outcomes,
        partition="development",
        evidence_mode="historical_replay",
    )


def test_cost_delay_capacity_stop_and_holding_sensitivities_are_explicit() -> None:
    result = _build([_idea("a")], [_outcome("a")])

    actionable = result["route_cost_survivability"]["routes"][1]
    assert actionable["route"] == "actionable_watch"
    assert actionable["episode_count"] == 1
    assert actionable["sample_status"] == "insufficient_sample"
    by_cost = {
        row["round_trip_cost_bps"]: row
        for row in actionable["assumed_cost_scenarios"]
    }
    assert by_cost[100]["metrics"][
        "mean_direction_adjusted_return_fraction"
    ] == pytest.approx(0.20)
    assert by_cost[100]["historical_cost_observed"] is False

    delays = {
        row["review_delay_days"]: row
        for row in result["review_delay_sensitivity"]["scenarios"]
    }
    assert delays[0]["metrics"][
        "mean_direction_adjusted_return_fraction"
    ] == pytest.approx(0.21)
    assert delays[1]["metrics"][
        "mean_direction_adjusted_return_fraction"
    ] == pytest.approx(0.10)
    assert delays[1]["entry_basis"] == "1d_close"
    assert delays[1]["selection_uses_outcomes"] is False

    capacity = result["position_liquidity_capacity"]["scenarios"][1]
    assert capacity["position_liquidity_fraction"] == pytest.approx(0.001)
    assert capacity["overall"]["mean_capacity_usd"] == pytest.approx(10_000.0)
    assert result["position_liquidity_capacity"][
        "capacity_is_not_executable_size"
    ] is True

    stops = {
        row["stop_loss_fraction"]: row
        for row in result["fixed_stop_loss_sensitivity"]["scenarios"]
    }
    assert stops[0.05]["overall"][
        "mean_direction_adjusted_return_fraction"
    ] == pytest.approx(-0.05)
    assert stops[0.05]["overall"]["assumed_stop_trigger_count"] == 1
    assert result["fixed_stop_loss_sensitivity"]["assumptions"][
        "gap_through_stop"
    ] == "not_observable_and_assumed_absent"

    holding = result["maximum_holding_time_sensitivity"]
    assert [row["maximum_holding_days"] for row in holding["scenarios"]] == [
        1,
        3,
        7,
        14,
    ]
    assert holding["scenarios"][2]["overall"][
        "mean_direction_adjusted_return_fraction"
    ] == pytest.approx(0.30)


def test_component_profiles_are_assumed_and_trailing_stop_is_unavailable() -> None:
    result = _build([_idea("a")], [_outcome("a")])

    profiles = result["component_cost_profiles"]["profiles"]
    stressed = next(
        row for row in profiles if row["name"] == "stressed_adverse_selection"
    )
    assert stressed["components_bps"] == {
        "fee_bps": 20,
        "spread_bps": 30,
        "slippage_bps": 50,
        "adverse_selection_bps": 100,
    }
    assert stressed["total_round_trip_cost_bps"] == 200
    assert set(stressed["component_observation_status"].values()) == {
        "assumed_not_observed"
    }
    assert result["component_cost_profiles"][
        "execution_cost_measurement_claim"
    ] is False

    trailing = result["trailing_stop_sensitivity"]
    assert trailing["status"] == "unavailable"
    assert trailing["reason"] == "intraday_high_low_order_absent"
    assert trailing["fabricated_path_order"] is False
    assert len(trailing["scenarios"]) == 3
    assert all(row["metrics"] is None for row in trailing["scenarios"])


def test_daily_and_simultaneous_cap_selection_is_outcome_blind() -> None:
    ideas = [
        _idea("a", observed_at="2022-02-01T00:00:00Z"),
        _idea("b", observed_at="2022-02-01T01:00:00Z"),
        _idea("c", observed_at="2022-02-02T00:00:00Z"),
        _idea("d", observed_at="2022-02-05T00:00:00Z"),
    ]
    first_outcomes = [
        _outcome("a", returns={1: 0.01, 3: 0.20, 7: 0.20, 14: 0.20}),
        _outcome("b", returns={1: 0.01, 3: -0.20, 7: -0.20, 14: -0.20}),
        _outcome("c", returns={1: 0.01, 3: 0.10, 7: 0.10, 14: 0.10}),
        _outcome("d", returns={1: 0.01, 3: 0.05, 7: 0.05, 14: 0.05}),
    ]
    second_outcomes = deepcopy(first_outcomes)
    second_outcomes[0], second_outcomes[1] = (
        _outcome("a", returns={1: 0.01, 3: -0.90, 7: -0.90, 14: -0.90}),
        _outcome("b", returns={1: 0.01, 3: 0.90, 7: 0.90, 14: 0.90}),
    )
    first = _build(ideas, first_outcomes)
    second = _build(ideas, second_outcomes)

    first_daily = first["daily_idea_caps"]["scenarios"][0]
    second_daily = second["daily_idea_caps"]["scenarios"][0]
    assert first_daily["maximum_daily_ideas"] == 1
    assert first_daily["selected_episode_ids"] == ["a", "c", "d"]
    assert first_daily["selected_episode_ids"] == second_daily[
        "selected_episode_ids"
    ]
    assert first_daily["selected_episode_id_digest"] == second_daily[
        "selected_episode_id_digest"
    ]

    first_simultaneous = first["simultaneous_position_caps"]["scenarios"][0]
    second_simultaneous = second["simultaneous_position_caps"]["scenarios"][0]
    assert first_simultaneous["maximum_simultaneous_ideas"] == 1
    assert first_simultaneous["selected_episode_ids"] == ["a", "d"]
    assert first_simultaneous["selected_episode_ids"] == second_simultaneous[
        "selected_episode_ids"
    ]
    assert first_simultaneous["selection_uses_outcomes"] is False
    assert result_safety(first) is True


def test_missing_outcomes_liquidity_and_mae_remain_explicit() -> None:
    missing_mae = _outcome("b")
    missing_mae["horizons"]["3d"]["max_adverse_excursion_fraction"] = None
    result = _build(
        [_idea("a", volume_usd=None), _idea("b", volume_usd=None)],
        [missing_mae],
    )

    actionable = result["route_cost_survivability"]["routes"][1]
    gross = actionable["gross_metrics"]
    assert gross["selection_count"] == 2
    assert gross["sample_size"] == 1
    assert gross["unavailable_reason_counts"] == {"outcome_missing": 1}

    capacity = result["position_liquidity_capacity"]
    assert capacity["status"] == "unavailable"
    assert capacity["scenarios"][0]["overall"]["sample_status"] == "no_sample"
    assert capacity["scenarios"][0]["overall"]["missing_liquidity_count"] == 2

    stop = result["fixed_stop_loss_sensitivity"]["scenarios"][0]["overall"]
    assert stop["sample_size"] == 0
    assert stop["unavailable_reason_counts"] == {
        "mae_unavailable": 1,
        "outcome_missing": 1,
    }
    assert stop["sample_status"] == "no_sample"


def test_zero_sample_routes_and_global_safety_are_closed() -> None:
    result = _build([], [])

    routes = result["route_cost_survivability"]["routes"]
    assert [row["route"] for row in routes] == list(empirical_survivability.ROUTES)
    assert len(routes) == 8
    for row in routes:
        assert row["episode_count"] == 0
        assert row["sample_status"] == "no_sample"
        assert row["evidence_status"] == "no_evidence"
        assert row["gross_metrics"]["sample_size"] == 0
        assert row["break_even_mean_round_trip_cost_bps"] is None
    assert result["sample_status"] == "no_sample"
    assert result["evidence_status"] == "no_evidence"
    assert result["outcomes_used_for_selection"] == 0
    assert result["causal_claim"] is False
    assert result["execution_claim"] is False
    assert result["production_policy_claim"] is False
    assert result["policy_eligible"] is False
    assert result["research_only"] is True
    assert result["auto_apply"] is False
    assert result_safety(result) is True


def test_partition_mixing_is_rejected() -> None:
    with pytest.raises(ValueError, match="representative_partition_mismatch"):
        _build([_idea("a", partition="validation")], [_outcome("a")])

    with pytest.raises(ValueError, match="outcome_partition_mismatch"):
        _build([_idea("a")], [{**_outcome("a"), "partition": "validation"}])


def result_safety(result: dict) -> bool:
    return set(result["safety"].values()) == {0}
