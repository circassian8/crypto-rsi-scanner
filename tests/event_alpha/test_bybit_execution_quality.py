"""Bybit USDT-perpetual offline execution-quality contract regressions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    CONTRACT_VERSION,
    MAX_PLANNED_REQUESTS,
    OFFICIAL_USDT_CONTRACT_ORDER_COST_DOC,
    ROUND_TRIP_SCHEMA_VERSION,
    TARGET_NOTIONAL_ROUND_TRIP_SCHEMA_VERSION,
    TARGET_NOTIONAL_SIZING_SCHEMA_VERSION,
    BybitExecutionQualityError,
    build_bybit_public_request_plan,
    main,
    model_bybit_target_notional_visible_book_round_trip,
    model_bybit_visible_book_round_trip,
    normalize_bybit_orderbook,
    run_fixture_smoke,
    select_bybit_usdt_perpetual_instruments,
    size_bybit_target_entry_mid_notional,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"


def _json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _selected() -> tuple[object, ...]:
    return select_bybit_usdt_perpetual_instruments(
        _json("radar_assets.json"),
        _json("instruments_info.json"),
    )


def test_universe_intersection_accepts_only_exact_active_usdt_perpetuals() -> None:
    selected = _selected()

    assert [row.instrument_id for row in selected] == ["BTCUSDT", "ETHUSDT"]
    assert [row.canonical_asset_id for row in selected] == ["bitcoin", "ethereum"]
    assert [row.liquidity_rank for row in selected] == [1, 2]
    assert all(row.contract_type == "LinearPerpetual" for row in selected)
    assert all(row.status == "Trading" for row in selected)
    assert all(row.quote_asset == row.settle_asset == "USDT" for row in selected)
    assert selected[0].quantity_step == "0.001"
    assert selected[0].minimum_order_quantity == "0.001"
    assert selected[0].maximum_limit_order_quantity == "1190"
    assert selected[0].maximum_market_order_quantity == "500"
    assert selected[0].minimum_notional_value_usdt == "5"


def test_universe_intersection_never_guesses_multiplier_or_partial_pages() -> None:
    radar = _json("radar_assets.json")
    payload = _json("instruments_info.json")
    selected = select_bybit_usdt_perpetual_instruments(radar, payload)

    assert "1000PEPEUSDT" not in {row.instrument_id for row in selected}
    partial = deepcopy(payload)
    partial["result"]["nextPageCursor"] = "next"
    with pytest.raises(BybitExecutionQualityError, match="page_incomplete"):
        select_bybit_usdt_perpetual_instruments(radar, partial)
    missing = deepcopy(payload)
    missing["result"].pop("nextPageCursor")
    with pytest.raises(BybitExecutionQualityError, match="page_incomplete"):
        select_bybit_usdt_perpetual_instruments(radar, missing)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        (
            "minOrderQty",
            "0.0015",
            "quantity_constraints_not_aligned_to_quantity_step",
        ),
        (
            "maxMktOrderQty",
            "0",
            "maxMktOrderQty_must_be_positive_and_finite",
        ),
        (
            "minOrderQty",
            "501",
            "quantity_constraints_inconsistent",
        ),
    ),
)
def test_instrument_quantity_constraints_fail_closed(
    field: str,
    value: str,
    error: str,
) -> None:
    payload = deepcopy(_json("instruments_info.json"))
    payload["result"]["list"][0]["lotSizeFilter"][field] = value

    with pytest.raises(BybitExecutionQualityError, match=error):
        select_bybit_usdt_perpetual_instruments(
            _json("radar_assets.json"), payload
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda rows: rows + [dict(rows[0])], "identity_not_unique"),
        (lambda rows: rows * 8, "exceeds_30"),
        (
            lambda rows: [dict(rows[0], liquidity_rank=31), *rows[1:]],
            "rank_exceeds_30",
        ),
    ),
)
def test_universe_identity_and_bound_fail_closed(mutation: object, error: str) -> None:
    radar = _json("radar_assets.json")
    with pytest.raises(BybitExecutionQualityError, match=error):
        select_bybit_usdt_perpetual_instruments(
            mutation(radar),
            _json("instruments_info.json"),
        )


def test_request_plan_is_bounded_public_get_only_and_non_executable() -> None:
    plan = build_bybit_public_request_plan(_selected())
    payload = plan.to_dict()

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["venue_id"] == "bybit"
    assert payload["execution_mode"] == "perpetual"
    assert payload["quote_asset"] == "USDT"
    assert payload["request_count"] == 3
    assert payload["request_count"] <= MAX_PLANNED_REQUESTS
    assert {row["method"] for row in payload["requests"]} == {"GET"}
    assert {row["path"] for row in payload["requests"]} == {
        "/v5/market/instruments-info",
        "/v5/market/orderbook",
    }
    assert payload["requests"][0]["query"] == {
        "category": "linear",
        "status": "Trading",
        "limit": "1000",
    }
    assert sum(
        row["path"] == "/v5/market/instruments-info"
        for row in payload["requests"]
    ) == 1
    assert all(row["credentials_required"] is False for row in payload["requests"])
    assert all(row["private_data"] is False for row in payload["requests"])
    assert payload["provider_call_authorized"] is False
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["order_operations_available"] is False
    assert payload["research_only"] is True


def test_orderbook_normalizes_quote_units_freshness_lineage_and_sequences() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:00:01Z",
        request_lineage_id="test.bybit.btcusdt.1",
    )
    payload = snapshot.to_dict()

    assert payload["venue_id"] == "bybit"
    assert payload["execution_mode"] == "perpetual"
    assert payload["instrument_id"] == "BTCUSDT"
    assert payload["canonical_asset_id"] == "bitcoin"
    assert payload["quote_asset"] == payload["notional_currency"] == "USDT"
    assert payload["provider_observed_at"] == "2026-07-17T12:00:00Z"
    assert payload["snapshot_generated_at"] == "2026-07-17T12:00:00.100000Z"
    assert payload["acquired_at"] == "2026-07-17T12:00:01Z"
    assert payload["age_seconds"] == 1.0
    assert payload["freshness_status"] == "fresh"
    assert payload["best_bid"] == 100.0
    assert payload["best_ask"] == 100.1
    assert payload["mid_price"] == 100.05
    assert payload["spread_bps"] == pytest.approx(9.995002498751)
    assert payload["schema_version"] == "crypto_radar.bybit_execution_quality.v2"
    assert payload["orderbook_level_limit"] == 200
    assert payload["liquidity_scope"] == "bybit_public_rest_visible_levels_only"
    assert payload["rpi_orders_included"] is False
    assert payload["bid_depth_usdt_by_band"] == {
        5: 1_000.0,
        10: 2_999.0,
        25: 7_994.0,
        50: 7_994.0,
    }
    assert payload["ask_depth_usdt_by_band"] == {
        5: 1_001.0,
        10: 3_004.0,
        25: 8_014.0,
        50: 18_064.0,
    }
    assert payload["buy_price_impact_bps_by_notional_usdt"][500.0] is not None
    assert payload["sell_price_impact_bps_by_notional_usdt"][500.0] is not None
    assert payload["buy_price_impact_bps_by_notional_usdt"][10_000.0] is not None
    buy_top = payload["buy_price_impact_bps_by_notional_usdt"][500.0]
    sell_top = payload["sell_price_impact_bps_by_notional_usdt"][500.0]
    assert buy_top == pytest.approx(payload["spread_bps"] / 2.0)
    assert sell_top == pytest.approx(payload["spread_bps"] / 2.0)
    assert buy_top + sell_top == pytest.approx(payload["spread_bps"])
    assert payload["impact_reference"] == "mid_price"
    assert payload["impact_method"] == (
        "deterministic_visible_book_walk_not_realized_execution"
    )
    assert payload["impact_size_definition"] == (
        "exact_usdt_spend_for_buy_and_exact_usdt_proceeds_for_sell"
    )
    assert payload["order_book_update_id"] == 230704
    assert payload["order_book_cross_sequence"] == 1432604333
    assert payload["request_lineage_id"] == "test.bybit.btcusdt.1"
    assert payload["research_only"] is True


def test_insufficient_book_depth_is_explicit_not_extrapolated() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:00:01Z",
        request_lineage_id="test.bybit.btcusdt.depth",
        notionals_usdt=(100_000.0,),
    )

    assert snapshot.buy_price_impact_bps_by_notional_usdt == ((100_000.0, None),)
    assert snapshot.sell_price_impact_bps_by_notional_usdt == ((100_000.0, None),)


@pytest.mark.parametrize(
    ("position_side", "entry_action", "exit_action", "gross_return", "net_return"),
    (
        ("long", "buy", "sell", 150.0, 147.75),
        ("short", "sell", "buy", -150.0, -152.25),
    ),
)
def test_round_trip_reconciles_one_exact_base_quantity_across_distinct_books(
    position_side: str,
    entry_action: str,
    exit_action: str,
    gross_return: float,
    net_return: float,
) -> None:
    result = model_bybit_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=_selected()[0],
        exit_instrument=_selected()[0],
        position_side=position_side,
        base_quantity="15.000",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id=f"test.{position_side}.entry",
        exit_request_lineage_id=f"test.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.linear.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.linear.catalog.exit",
    ).to_dict()

    assert result["schema_version"] == ROUND_TRIP_SCHEMA_VERSION
    assert result["instrument_id"] == "BTCUSDT"
    assert result["base_asset"] == "BTC"
    assert result["quote_asset"] == "USDT"
    assert result["base_quantity"] == "15"
    entry_constraints = result["entry_instrument_constraints"]
    exit_constraints = result["exit_instrument_constraints"]
    assert entry_constraints["quantity_step"] == "0.001"
    assert exit_constraints["quantity_step"] == "0.001"
    assert entry_constraints["minimum_order_quantity"] == "0.001"
    assert exit_constraints["minimum_order_quantity"] == "0.001"
    assert entry_constraints["maximum_limit_order_quantity"] == "1190"
    assert exit_constraints["maximum_limit_order_quantity"] == "1190"
    assert entry_constraints["maximum_market_order_quantity"] == "500"
    assert exit_constraints["maximum_market_order_quantity"] == "500"
    assert entry_constraints["minimum_notional_value_usdt"] == "5"
    assert exit_constraints["minimum_notional_value_usdt"] == "5"
    assert entry_constraints["visible_quote_value_meets_minimum_notional"] is True
    assert exit_constraints["visible_quote_value_meets_minimum_notional"] is True
    assert entry_constraints["quantity_aligned_to_step"] is True
    assert exit_constraints["quantity_aligned_to_step"] is True
    assert entry_constraints["quantity_eligible_order_styles"] == [
        "market",
        "marketable_limit",
    ]
    assert exit_constraints["quantity_eligible_order_styles"] == [
        "market",
        "marketable_limit",
    ]
    assert result["round_trip_quantity_eligible_order_styles"] == [
        "market",
        "marketable_limit",
    ]
    assert result["order_style_available_on_both_legs"] is True
    assert result["order_style_selected"] is False
    assert entry_constraints["observed_at"] == (
        "2026-07-17T11:59:59Z"
    )
    assert exit_constraints["observed_at"] == "2026-07-17T12:59:59Z"
    assert entry_constraints["lineage_id"] == "test.linear.catalog.entry"
    assert exit_constraints["lineage_id"] == "test.linear.catalog.exit"
    assert entry_constraints["causal_to_leg"] is True
    assert exit_constraints["causal_to_leg"] is True
    assert result["instrument_identity_reconciled"] is True
    assert result["constraint_lineages_distinct"] is True
    assert result["constraint_snapshots_ordered"] is True
    assert result["dynamic_constraints_revalidated_per_leg"] is True
    assert result["constraint_values_changed_between_legs"] is False
    assert result["quantity_aligned_to_entry_and_exit_steps"] is True
    assert result["instrument_constraints_freshness_policy_sealed"] is False
    assert result["instrument_maximums_dynamic"] is True
    assert result["quantity_unit"] == "base_asset"
    assert result["quantity_semantics"] == (
        "bybit_USDT_linear_contract_quantity_in_underlying_token"
    )
    assert result["quantity_source_url"] == OFFICIAL_USDT_CONTRACT_ORDER_COST_DOC
    assert result["entry"]["action"] == entry_action
    assert result["exit"]["action"] == exit_action
    assert result["entry"]["base_quantity"] == result["exit"]["base_quantity"] == "15"
    assert result["entry"]["visible_depth_complete"] is True
    assert result["exit"]["visible_depth_complete"] is True
    assert result["gross_mid_mark_return_usdt"] == pytest.approx(gross_return)
    assert result["net_visible_book_return_usdt"] == pytest.approx(net_return)
    assert result["total_visible_book_cost_usdt"] == pytest.approx(2.25)
    assert result["total_visible_book_cost_usdt"] == pytest.approx(
        result["gross_mid_mark_return_usdt"]
        - result["net_visible_book_return_usdt"]
    )
    assert result["total_visible_book_cost_bps_of_entry_mid_notional"] == (
        pytest.approx(14.992503748126)
    )
    assert result["same_base_quantity_reconciled"] is True
    assert result["entry_exit_snapshots_distinct"] is True
    assert result["spread_added_separately"] is False
    assert result["realized_execution"] is False
    assert result["fees_included"] is False
    assert result["funding_included"] is False
    assert result["latency_cost_included"] is False
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["research_only"] is True


def test_target_mid_notional_floors_to_exact_venue_quantity_without_policy_claim() -> None:
    result = size_bybit_target_entry_mid_notional(
        _json("orderbook_btcusdt.json"),
        instrument=_selected()[0],
        target_entry_mid_notional_usdt="1500.74",
        entry_acquired_at="2026-07-17T12:00:01Z",
        entry_request_lineage_id="test.sizing.entry",
        instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        instrument_constraints_lineage_id="test.sizing.catalog",
    ).to_dict()

    assert result["schema_version"] == TARGET_NOTIONAL_SIZING_SCHEMA_VERSION
    assert result["target_entry_mid_notional_usdt"] == "1500.74"
    assert result["entry_mid_price"] == 100.05
    assert result["sized_base_quantity"] == "14.999"
    assert result["sized_entry_mid_notional_usdt"] == "1500.64995"
    assert result["notional_shortfall_usdt"] == "0.09005"
    assert result["one_quantity_step_mid_notional_usdt"] == "0.10005"
    assert result["rounding_mode"] == "floor_to_quantity_step"
    assert result["does_not_exceed_target"] is True
    assert result["shortfall_less_than_one_quantity_step_notional"] is True
    assert result["sized_mid_notional_meets_minimum"] is True
    assert result["quantity_eligible_order_styles"] == [
        "market",
        "marketable_limit",
    ]
    assert result["order_style_selected"] is False
    assert result["target_notional_tier_set_sealed"] is False
    assert result["base_quantity_selection_policy_sealed"] is False
    assert result["target_is_reference_mid_notional_not_quote_budget"] is True
    assert (
        result["marketable_quote_value_may_exceed_target_due_spread_and_impact"]
        is True
    )
    assert result["realized_execution"] is False
    assert result["research_only"] is True


@pytest.mark.parametrize("position_side", ("long", "short"))
def test_target_notional_sizing_reconciles_into_exact_round_trip(
    position_side: str,
) -> None:
    result = model_bybit_target_notional_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=_selected()[0],
        exit_instrument=_selected()[0],
        position_side=position_side,
        target_entry_mid_notional_usdt="1500.75",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id=f"test.target.{position_side}.entry",
        exit_request_lineage_id=f"test.target.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.target.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.target.catalog.exit",
    ).to_dict()

    assert result["schema_version"] == TARGET_NOTIONAL_ROUND_TRIP_SCHEMA_VERSION
    assert result["sizing"]["sized_base_quantity"] == "15"
    assert result["sizing"]["sized_entry_mid_notional_usdt"] == "1500.75"
    assert result["sizing"]["notional_shortfall_usdt"] == "0"
    assert result["round_trip"]["base_quantity"] == "15"
    assert result["round_trip"]["entry_mid_notional_usdt"] == 1500.75
    assert result["sizing_and_round_trip_identity_reconciled"] is True
    assert result["same_entry_book_reconciled"] is True
    assert result["same_base_quantity_reconciled"] is True
    assert result["target_notional_tier_set_sealed"] is False
    assert result["base_quantity_selection_policy_sealed"] is False
    assert result["order_style_selected"] is False
    assert result["realized_execution"] is False
    if position_side == "long":
        assert result["round_trip"]["entry"]["quote_value_usdt"] > 1500.75
    else:
        assert result["round_trip"]["entry"]["quote_value_usdt"] < 1500.75


def test_target_notional_sizing_reports_order_style_eligibility_without_choice() -> None:
    result = size_bybit_target_entry_mid_notional(
        _json("orderbook_btcusdt.json"),
        instrument=replace(
            _selected()[0],
            maximum_market_order_quantity="10",
        ),
        target_entry_mid_notional_usdt="1500.75",
        entry_acquired_at="2026-07-17T12:00:01Z",
        entry_request_lineage_id="test.sizing.limitonly.entry",
        instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        instrument_constraints_lineage_id="test.sizing.limitonly.catalog",
    ).to_dict()

    assert result["market_order_quantity_eligible"] is False
    assert result["limit_order_quantity_eligible"] is True
    assert result["quantity_eligible_order_styles"] == ["marketable_limit"]
    assert result["order_style_selected"] is False


@pytest.mark.parametrize(
    ("target", "instrument_changes", "acquired_at", "constraints_at", "error"),
    (
        (True, {}, "2026-07-17T12:00:01Z", "2026-07-17T11:59:59Z", "must_be_decimal_text"),
        ("0", {}, "2026-07-17T12:00:01Z", "2026-07-17T11:59:59Z", "positive_and_finite"),
        ("NaN", {}, "2026-07-17T12:00:01Z", "2026-07-17T11:59:59Z", "positive_and_finite"),
        ("0.05", {}, "2026-07-17T12:00:01Z", "2026-07-17T11:59:59Z", "below_minimum_order_quantity"),
        ("0.20", {}, "2026-07-17T12:00:01Z", "2026-07-17T11:59:59Z", "below_instrument_minimum_notional"),
        (
            "1500.75",
            {"maximum_limit_order_quantity": "10", "maximum_market_order_quantity": "10"},
            "2026-07-17T12:00:01Z",
            "2026-07-17T11:59:59Z",
            "exceeds_all_order_style_maximums",
        ),
        ("1500.75", {}, "2026-07-17T12:01:00Z", "2026-07-17T11:59:59Z", "snapshot_not_fresh"),
        ("1500.75", {}, "2026-07-17T12:00:01Z", "2026-07-17T12:00:00.001Z", "constraints_observed_after_entry"),
    ),
)
def test_target_notional_sizing_fails_closed(
    target: object,
    instrument_changes: dict[str, str],
    acquired_at: str,
    constraints_at: str,
    error: str,
) -> None:
    with pytest.raises(BybitExecutionQualityError, match=error):
        size_bybit_target_entry_mid_notional(
            _json("orderbook_btcusdt.json"),
            instrument=replace(_selected()[0], **instrument_changes),
            target_entry_mid_notional_usdt=target,
            entry_acquired_at=acquired_at,
            entry_request_lineage_id="test.sizing.invalid.entry",
            instrument_constraints_observed_at=constraints_at,
            instrument_constraints_lineage_id="test.sizing.invalid.catalog",
        )


@pytest.mark.parametrize(
    ("kwargs", "error"),
    (
        ({"position_side": "flat"}, "position_side_invalid"),
        ({"base_quantity": "15.0005"}, "not_aligned_to_quantity_step"),
        (
            {
                "entry_request_lineage_id": "same.lineage",
                "exit_request_lineage_id": "same.lineage",
            },
            "request_lineage_not_distinct",
        ),
        (
            {
                "entry_instrument_constraints_lineage_id": "same.catalog",
                "exit_instrument_constraints_lineage_id": "same.catalog",
            },
            "constraints_lineage_not_distinct",
        ),
        (
            {
                "exit_instrument": replace(
                    _selected()[0],
                    canonical_asset_id="not-bitcoin",
                )
            },
            "instrument_identity_mismatch",
        ),
        (
            {"exit_acquired_at": "2026-07-17T13:01:00Z"},
            "round_trip_snapshot_not_fresh",
        ),
        ({"base_quantity": "1000"}, "entry_visible_depth_insufficient"),
    ),
)
def test_round_trip_invalid_quantity_identity_freshness_and_depth_fail_closed(
    kwargs: dict[str, object],
    error: str,
) -> None:
    arguments: dict[str, object] = {
        "instrument": _selected()[0],
        "exit_instrument": _selected()[0],
        "position_side": "long",
        "base_quantity": "15",
        "entry_acquired_at": "2026-07-17T12:00:01Z",
        "exit_acquired_at": "2026-07-17T13:00:01Z",
        "entry_request_lineage_id": "test.roundtrip.entry",
        "exit_request_lineage_id": "test.roundtrip.exit",
        "entry_instrument_constraints_observed_at": "2026-07-17T11:59:59Z",
        "entry_instrument_constraints_lineage_id": "test.linear.catalog.entry",
        "exit_instrument_constraints_observed_at": "2026-07-17T12:59:59Z",
        "exit_instrument_constraints_lineage_id": "test.linear.catalog.exit",
    }
    arguments.update(kwargs)
    with pytest.raises(BybitExecutionQualityError, match=error):
        model_bybit_visible_book_round_trip(
            _json("orderbook_btcusdt.json"),
            _json("orderbook_btcusdt_exit.json"),
            **arguments,
        )


def test_round_trip_rejects_reused_or_reversed_provider_snapshot_order() -> None:
    with pytest.raises(BybitExecutionQualityError, match="snapshot_order_invalid"):
        model_bybit_visible_book_round_trip(
            _json("orderbook_btcusdt_exit.json"),
            _json("orderbook_btcusdt.json"),
            instrument=_selected()[0],
            exit_instrument=_selected()[0],
            position_side="long",
            base_quantity="15",
            entry_acquired_at="2026-07-17T13:00:01Z",
            exit_acquired_at="2026-07-17T12:00:01Z",
            entry_request_lineage_id="test.reversed.entry",
            exit_request_lineage_id="test.reversed.exit",
            entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
            entry_instrument_constraints_lineage_id="test.linear.catalog.entry",
            exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
            exit_instrument_constraints_lineage_id="test.linear.catalog.exit",
        )


def test_round_trip_reports_quantity_eligibility_without_selecting_order_style() -> None:
    exit_instrument = replace(
        _selected()[0],
        quantity_step="0.002",
        minimum_order_quantity="0.002",
        maximum_market_order_quantity="10",
    )

    result = model_bybit_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=_selected()[0],
        exit_instrument=exit_instrument,
        position_side="long",
        base_quantity="15",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id="test.limitonly.entry",
        exit_request_lineage_id="test.limitonly.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.limitonly.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.limitonly.catalog.exit",
    ).to_dict()

    assert result["entry_instrument_constraints"][
        "market_order_quantity_eligible"
    ] is True
    assert result["exit_instrument_constraints"][
        "market_order_quantity_eligible"
    ] is False
    assert result["exit_instrument_constraints"][
        "limit_order_quantity_eligible"
    ] is True
    assert result["entry_instrument_constraints"]["quantity_step"] == "0.001"
    assert result["exit_instrument_constraints"]["quantity_step"] == "0.002"
    assert result["quantity_aligned_to_entry_and_exit_steps"] is True
    assert result["round_trip_quantity_eligible_order_styles"] == [
        "marketable_limit"
    ]
    assert result["order_style_available_on_both_legs"] is True
    assert result["constraint_values_changed_between_legs"] is True
    assert result["order_style_selected"] is False


def test_round_trip_keeps_per_leg_styles_when_no_single_style_spans_both() -> None:
    entry_instrument = replace(
        _selected()[0],
        maximum_limit_order_quantity="10",
    )
    exit_instrument = replace(
        _selected()[0],
        maximum_market_order_quantity="10",
    )

    result = model_bybit_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=entry_instrument,
        exit_instrument=exit_instrument,
        position_side="long",
        base_quantity="15",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id="test.splitstyles.entry",
        exit_request_lineage_id="test.splitstyles.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id=(
            "test.splitstyles.catalog.entry"
        ),
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id=(
            "test.splitstyles.catalog.exit"
        ),
    ).to_dict()

    assert result["entry_instrument_constraints"][
        "quantity_eligible_order_styles"
    ] == ["market"]
    assert result["exit_instrument_constraints"][
        "quantity_eligible_order_styles"
    ] == ["marketable_limit"]
    assert result["round_trip_quantity_eligible_order_styles"] == []
    assert result["order_style_available_on_both_legs"] is False
    assert result["order_style_selected"] is False


@pytest.mark.parametrize(
    (
        "entry_changes",
        "exit_changes",
        "quantity",
        "entry_constraints_at",
        "exit_constraints_at",
        "error",
    ),
    (
        (
            {"minimum_order_quantity": "0.01"},
            {},
            "0.001",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "entry_base_quantity_below_minimum_order_quantity",
        ),
        (
            {},
            {"minimum_order_quantity": "0.01"},
            "0.001",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "exit_base_quantity_below_minimum_order_quantity",
        ),
        (
            {
                "quantity_step": "0.002",
                "minimum_order_quantity": "0.002",
            },
            {},
            "15.001",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "entry_base_quantity_not_aligned_to_quantity_step",
        ),
        (
            {},
            {
                "quantity_step": "0.002",
                "minimum_order_quantity": "0.002",
            },
            "15.001",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "exit_base_quantity_not_aligned_to_quantity_step",
        ),
        (
            {
                "maximum_limit_order_quantity": "10",
                "maximum_market_order_quantity": "10",
            },
            {},
            "15",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "entry_base_quantity_exceeds_all_order_style_maximums",
        ),
        (
            {},
            {
                "maximum_limit_order_quantity": "10",
                "maximum_market_order_quantity": "10",
            },
            "15",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "exit_base_quantity_exceeds_all_order_style_maximums",
        ),
        (
            {},
            {},
            "0.001",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "entry_notional_below_instrument_minimum",
        ),
        (
            {},
            {"minimum_notional_value_usdt": "2000"},
            "15",
            "2026-07-17T11:59:59Z",
            "2026-07-17T12:59:59Z",
            "exit_notional_below_instrument_minimum",
        ),
        (
            {},
            {},
            "15",
            "2026-07-17T12:00:00.001Z",
            "2026-07-17T12:59:59Z",
            "entry_instrument_constraints_observed_after_entry",
        ),
        (
            {},
            {},
            "15",
            "2026-07-17T11:59:59Z",
            "2026-07-17T13:00:00.001Z",
            "exit_instrument_constraints_observed_after_exit",
        ),
        (
            {},
            {},
            "15",
            "2026-07-17T11:59:59Z",
            "2026-07-17T11:59:59.500000Z",
            "exit_instrument_constraints_not_revalidated_after_entry",
        ),
    ),
)
def test_round_trip_instrument_constraints_fail_closed(
    entry_changes: dict[str, str],
    exit_changes: dict[str, str],
    quantity: str,
    entry_constraints_at: str,
    exit_constraints_at: str,
    error: str,
) -> None:
    with pytest.raises(BybitExecutionQualityError, match=error):
        model_bybit_visible_book_round_trip(
            _json("orderbook_btcusdt.json"),
            _json("orderbook_btcusdt_exit.json"),
            instrument=replace(_selected()[0], **entry_changes),
            exit_instrument=replace(_selected()[0], **exit_changes),
            position_side="long",
            base_quantity=quantity,
            entry_acquired_at="2026-07-17T12:00:01Z",
            exit_acquired_at="2026-07-17T13:00:01Z",
            entry_request_lineage_id="test.constraints.entry",
            exit_request_lineage_id="test.constraints.exit",
            entry_instrument_constraints_observed_at=entry_constraints_at,
            entry_instrument_constraints_lineage_id=(
                "test.constraints.catalog.entry"
            ),
            exit_instrument_constraints_observed_at=exit_constraints_at,
            exit_instrument_constraints_lineage_id=(
                "test.constraints.catalog.exit"
            ),
        )


def test_stale_snapshot_stays_stale_without_weakening_freshness_gate() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:01:00Z",
        request_lineage_id="test.bybit.btcusdt.stale",
    )

    assert snapshot.age_seconds == 60.0
    assert snapshot.freshness_status == "stale"


@pytest.mark.parametrize(
    "freshness_seconds",
    (True, False, float("nan"), float("inf"), float("-inf"), 14.0, 16.0),
)
def test_orderbook_rejects_unbound_or_nonfinite_freshness_policy(
    freshness_seconds: object,
) -> None:
    with pytest.raises(BybitExecutionQualityError, match="freshness_seconds_invalid"):
        normalize_bybit_orderbook(
            _json("orderbook_btcusdt.json"),
            instrument=_selected()[0],
            acquired_at="2026-07-17T12:01:00Z",
            request_lineage_id="test.bybit.btcusdt.invalid_freshness",
            freshness_seconds=freshness_seconds,
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda row: row["result"].update(s="ETHUSDT"), "instrument_mismatch"),
        (lambda row: row["result"]["b"].__setitem__(0, ["100.20", "10"]), "locked_or_crossed"),
        (lambda row: row["result"]["a"].reverse(), "asks_sort_invalid"),
        (lambda row: row.update(retCode=10001), "response_not_ok"),
        (lambda row: row.update(retCode=False), "response_not_ok"),
        (
            lambda row: row["result"].update(ts=row["result"]["cts"] - 1),
            "snapshot_clock_precedes",
        ),
    ),
)
def test_invalid_orderbook_identity_shape_and_status_fail_closed(
    mutation: object,
    error: str,
) -> None:
    payload = _json("orderbook_btcusdt.json")
    mutation(payload)
    with pytest.raises(BybitExecutionQualityError, match=error):
        normalize_bybit_orderbook(
            payload,
            instrument=_selected()[0],
            acquired_at="2026-07-17T12:00:01Z",
            request_lineage_id="test.bybit.invalid",
        )


def test_fixture_smoke_and_cli_are_offline_secret_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline Bybit fixture smoke must not open a connection")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setenv("BYBIT_API_KEY", "must-not-print")
    monkeypatch.setenv("BYBIT_API_SECRET", "must-not-print")

    result = run_fixture_smoke(FIXTURE_DIR)
    assert result["provider_calls"] == 0
    assert result["network_called"] is False
    assert result["credentials_read"] is False
    assert result["orders_available"] is False
    assert result["research_only"] is True
    assert result["quantity_reconciled_round_trip"]["same_base_quantity_reconciled"] is True
    assert result["quantity_reconciled_round_trip"]["spread_added_separately"] is False
    assert result["target_notional_round_trip"]["same_base_quantity_reconciled"] is True
    assert result["target_notional_round_trip"]["target_notional_tier_set_sealed"] is False

    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["selected_instrument_ids"] == ["BTCUSDT", "ETHUSDT"]
    assert payload["provider_calls"] == 0
    assert "must-not-print" not in output.out


def test_make_smoke_exposes_fixture_normalizer_not_provider_or_order_command() -> None:
    completed = subprocess.run(
        ["make", "-n", "radar-execution-quality-bybit-smoke", "PYTHON=python3"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "operations.bybit_execution_quality" in completed.stdout
    assert "--fixture-dir fixtures/bybit_execution_quality" in completed.stdout
    lowered = completed.stdout.casefold()
    assert "curl" not in lowered
    assert "place-order" not in lowered
    assert "execute-order" not in lowered
