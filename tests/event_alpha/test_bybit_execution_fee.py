"""Exact taker-fee application over Bybit visible-book round trips."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_fee import (
    OFFICIAL_FEE_STRUCTURE_URL,
    OFFICIAL_MAKER_TAKER_URL,
    SCHEMA_VERSION,
    BybitExecutionFeeError,
    model_bybit_visible_book_taker_fee_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    model_bybit_visible_book_round_trip,
    select_bybit_usdt_perpetual_instruments,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures/bybit_execution_quality"


def _json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _round_trip(position_side: str = "long") -> object:
    instrument = select_bybit_usdt_perpetual_instruments(
        _json("radar_assets.json"),
        _json("instruments_info.json"),
    )[0]
    return model_bybit_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=instrument,
        exit_instrument=instrument,
        position_side=position_side,
        base_quantity="15.000",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id=f"test.fee.{position_side}.entry",
        exit_request_lineage_id=f"test.fee.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.fee.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.fee.catalog.exit",
    )


def _scenario(position_side: str = "long", **changes: object) -> object:
    kwargs: dict[str, object] = {
        "entry_fee_rate_fraction": "0.00055",
        "exit_fee_rate_fraction": "0.00055",
        "assumption_id": "fixture-non-vip-taker",
        "fee_rate_source_reference": OFFICIAL_FEE_STRUCTURE_URL,
        "fee_rate_source_observed_at": "2026-07-20T00:00:00Z",
        "fee_rate_effective_from": "2026-07-17T00:00:00Z",
        "fee_rate_effective_until": "2026-07-18T00:00:00Z",
        "fee_rate_lineage_id": "fixture.bybit.fee.20260717",
    }
    kwargs.update(changes)
    return model_bybit_visible_book_taker_fee_scenario(
        _round_trip(position_side),
        **kwargs,
    )


@pytest.mark.parametrize(
    ("position_side", "entry_quote", "exit_quote", "fee", "net", "fee_bps"),
    (
        (
            "long",
            1501.75,
            1649.5,
            1.7331875,
            146.0168125,
            11.548808928869,
        ),
        (
            "short",
            1499.75,
            1652.0,
            1.7334625,
            -153.9834625,
            11.550641345994,
        ),
    ),
)
def test_taker_fee_scenario_uses_each_exact_executed_leg_value(
    position_side: str,
    entry_quote: float,
    exit_quote: float,
    fee: float,
    net: float,
    fee_bps: float,
) -> None:
    result = _scenario(position_side).to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source_round_trip_schema_version"].endswith("round_trip.v3")
    assert result["venue_id"] == "bybit"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == position_side
    assert result["base_quantity"] == "15"
    assert result["fee_liquidity_role"] == "taker"
    assert result["immediately_marketable_book_walk"] is True
    assert result["marketable_limit_immediate_fill_is_taker"] is True
    assert result["maker_liquidity_modeled"] is False
    assert result["maker_taker_semantics_source_url"] == OFFICIAL_MAKER_TAKER_URL
    assert result["fee_rate_unit"] == "fraction"
    assert result["entry_fee_rate_fraction"] == "0.00055"
    assert result["exit_fee_rate_fraction"] == "0.00055"
    assert result["entry_fee_rate_bps"] == 5.5
    assert result["exit_fee_rate_bps"] == 5.5
    assert result["entry_executed_quote_value_usdt"] == entry_quote
    assert result["exit_executed_quote_value_usdt"] == exit_quote
    assert result["total_trading_fee_usdt"] == pytest.approx(fee)
    assert result["net_after_visible_book_and_fees_usdt"] == pytest.approx(net)
    assert result["total_trading_fee_bps_of_entry_mid_notional"] == (
        pytest.approx(fee_bps)
    )
    assert result["total_visible_book_and_fee_cost_usdt"] == pytest.approx(
        result["gross_mid_mark_return_usdt"]
        - result["net_after_visible_book_and_fees_usdt"]
    )
    assert result["fee_rate_source_status"] == (
        "operator_supplied_unsealed_research_assumption"
    )
    assert result["account_specific_fee_rate"] is False
    assert result["fee_rate_source_sealed"] is False
    assert result["spread_added_separately"] is False
    assert result["funding_included"] is False
    assert result["latency_cost_included"] is False
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["realized_execution"] is False
    assert result["provider_calls"] == 0
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["writes_performed"] is False
    assert result["research_only"] is True


def test_entry_and_exit_fee_rates_remain_distinct() -> None:
    result = _scenario(
        entry_fee_rate_fraction="0.00055",
        exit_fee_rate_fraction="0.0002",
        fee_rate_source_reference="research-assumption:mixed-taker-window",
    ).to_dict()

    assert result["entry_trading_fee_usdt"] == pytest.approx(0.8259625)
    assert result["exit_trading_fee_usdt"] == pytest.approx(0.3299)
    assert result["total_trading_fee_usdt"] == pytest.approx(1.1558625)
    assert result["fee_rate_source_reference"] == (
        "research-assumption:mixed-taker-window"
    )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("entry_fee_rate_fraction", 0.00055, "must_be_decimal_text"),
        ("entry_fee_rate_fraction", "NaN", "outside_plausible"),
        ("entry_fee_rate_fraction", "-0.0001", "outside_plausible"),
        ("entry_fee_rate_fraction", "0.055", "outside_plausible"),
        ("exit_fee_rate_fraction", "Infinity", "outside_plausible"),
    ),
)
def test_fee_units_and_plausible_fraction_bounds_fail_closed(
    field: str,
    value: object,
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFeeError, match=error):
        _scenario(**{field: value})


@pytest.mark.parametrize(
    ("changes", "error"),
    (
        (
            {"fee_rate_effective_from": "2026-07-17T12:00:00.001Z"},
            "effective_window_incomplete",
        ),
        (
            {"fee_rate_effective_until": "2026-07-17T12:59:59Z"},
            "effective_window_incomplete",
        ),
        (
            {"fee_rate_effective_from": "2026-07-17T00:00:00"},
            "timezone_missing",
        ),
        (
            {"fee_rate_source_reference": "https://example.com/?token=secret"},
            "source_reference_invalid",
        ),
        ({"assumption_id": "bad assumption"}, "assumption_id_invalid"),
        ({"fee_rate_lineage_id": "bad lineage"}, "lineage_id_invalid"),
    ),
)
def test_fee_source_and_effective_window_fail_closed(
    changes: dict[str, object],
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFeeError, match=error):
        _scenario(**changes)


@pytest.mark.parametrize(
    "round_trip_change",
    (
        {"fees_included": True},
        {"realized_execution": True},
        {"spread_added_separately": True},
        {"same_base_quantity_reconciled": False},
    ),
)
def test_tampered_source_round_trip_fails_closed(
    round_trip_change: dict[str, object],
) -> None:
    round_trip = replace(_round_trip(), **round_trip_change)

    with pytest.raises(BybitExecutionFeeError, match="round_trip_"):
        model_bybit_visible_book_taker_fee_scenario(
            round_trip,
            entry_fee_rate_fraction="0.00055",
            exit_fee_rate_fraction="0.00055",
            assumption_id="fixture-non-vip-taker",
            fee_rate_source_reference=OFFICIAL_FEE_STRUCTURE_URL,
            fee_rate_source_observed_at="2026-07-20T00:00:00Z",
            fee_rate_effective_from="2026-07-17T00:00:00Z",
            fee_rate_effective_until="2026-07-18T00:00:00Z",
            fee_rate_lineage_id="fixture.bybit.fee.20260717",
        )


def test_fee_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip = _round_trip()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("fee projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    result = model_bybit_visible_book_taker_fee_scenario(
        round_trip,
        entry_fee_rate_fraction="0.00055",
        exit_fee_rate_fraction="0.00055",
        assumption_id="fixture-non-vip-taker",
        fee_rate_source_reference=OFFICIAL_FEE_STRUCTURE_URL,
        fee_rate_source_observed_at="2026-07-20T00:00:00Z",
        fee_rate_effective_from="2026-07-17T00:00:00Z",
        fee_rate_effective_until="2026-07-18T00:00:00Z",
        fee_rate_lineage_id="fixture.bybit.fee.20260717",
    )

    assert result.provider_calls == 0
    assert result.writes_performed is False
