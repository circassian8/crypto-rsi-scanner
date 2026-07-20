"""Exact funding-settlement arithmetic for modeled Bybit positions."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_funding import (
    OFFICIAL_FUNDING_FEE_URL,
    OFFICIAL_FUNDING_HISTORY_URL,
    OFFICIAL_MARK_PRICE_KLINE_URL,
    SCHEMA_VERSION,
    BybitExecutionFundingError,
    model_bybit_funding_settlement_scenario,
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
        entry_request_lineage_id=f"test.funding.{position_side}.entry",
        exit_request_lineage_id=f"test.funding.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.funding.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.funding.catalog.exit",
    )


def _scenario(position_side: str = "long", **changes: object) -> object:
    kwargs: dict[str, object] = {
        "funding_rate_fraction": "0.0001",
        "settlement_mark_price_usdt": "105.00",
        "funding_settled_at": "2026-07-17T12:30:00Z",
        "assumption_id": "fixture-one-settlement",
        "funding_rate_source_reference": OFFICIAL_FUNDING_HISTORY_URL,
        "funding_rate_source_observed_at": "2026-07-17T13:05:00Z",
        "funding_rate_lineage_id": "fixture.bybit.funding.20260717",
        "settlement_mark_source_reference": OFFICIAL_MARK_PRICE_KLINE_URL,
        "settlement_mark_source_observed_at": "2026-07-17T13:05:01Z",
        "settlement_mark_lineage_id": "fixture.bybit.mark.20260717",
    }
    kwargs.update(changes)
    return model_bybit_funding_settlement_scenario(
        _round_trip(position_side),
        **kwargs,
    )


@pytest.mark.parametrize(
    (
        "position_side",
        "rate",
        "direction",
        "payer",
        "receiver",
        "cashflow",
        "cost",
        "net",
    ),
    (
        (
            "long",
            "0.0001",
            "positive_long_pays_short",
            "long",
            "short",
            -0.1575,
            0.1575,
            147.5925,
        ),
        (
            "short",
            "0.0001",
            "positive_long_pays_short",
            "long",
            "short",
            0.1575,
            -0.1575,
            -152.0925,
        ),
        (
            "long",
            "-0.0002",
            "negative_short_pays_long",
            "short",
            "long",
            0.315,
            -0.315,
            148.065,
        ),
        (
            "short",
            "-0.0002",
            "negative_short_pays_long",
            "short",
            "long",
            -0.315,
            0.315,
            -152.565,
        ),
        (
            "long",
            "0",
            "zero_no_transfer",
            "none",
            "none",
            0.0,
            0.0,
            147.75,
        ),
    ),
)
def test_funding_settlement_sign_and_cost_identity(
    position_side: str,
    rate: str,
    direction: str,
    payer: str,
    receiver: str,
    cashflow: float,
    cost: float,
    net: float,
) -> None:
    result = _scenario(
        position_side,
        funding_rate_fraction=rate,
    ).to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source_round_trip_schema_version"].endswith("round_trip.v3")
    assert result["venue_id"] == "bybit"
    assert result["execution_mode"] == "perpetual"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == position_side
    assert result["base_quantity"] == "15"
    assert result["modeled_position_opened_at"] == "2026-07-17T12:00:01Z"
    assert result["modeled_position_closed_at"] == "2026-07-17T13:00:01Z"
    assert result["funding_settled_at"] == "2026-07-17T12:30:00Z"
    assert result["funding_rate_unit"] == "fraction"
    assert result["funding_rate_fraction"] == rate
    assert result["funding_rate_percent_points"] == pytest.approx(
        float(rate) * 100
    )
    assert result["settlement_mark_price_usdt"] == "105"
    assert result["position_value_at_settlement_usdt"] == 1575.0
    assert result["funding_formula"] == (
        "base_quantity_times_settlement_mark_price_times_rate"
    )
    assert result["funding_formula_source_url"] == OFFICIAL_FUNDING_FEE_URL
    assert result["funding_direction"] == direction
    assert result["payer_side"] == payer
    assert result["receiver_side"] == receiver
    assert result["position_cashflow_sign_convention"] == (
        "positive_received_negative_paid"
    )
    assert result["position_funding_cashflow_usdt"] == pytest.approx(cashflow)
    assert result["position_funding_cost_usdt"] == pytest.approx(cost)
    assert result["net_after_visible_book_and_funding_usdt"] == pytest.approx(net)
    assert result["total_visible_book_and_funding_cost_usdt"] == pytest.approx(
        result["gross_mid_mark_return_usdt"]
        - result["net_after_visible_book_and_funding_usdt"]
    )
    assert result["arithmetic_exact_for_supplied_inputs"] is True
    assert result["funding_event_count"] == 1
    assert result["holding_interval_funding_coverage_complete"] is False
    assert result["settlement_mark_source_sealed"] is False
    assert result["funding_rate_source_sealed"] is False
    assert result["fees_included"] is False
    assert result["spread_added_separately"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["realized_execution"] is False
    assert result["provider_calls"] == 0
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["writes_performed"] is False
    assert result["research_only"] is True


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("funding_rate_fraction", 0.0001, "must_be_decimal_text"),
        ("funding_rate_fraction", "NaN", "invalid"),
        ("funding_rate_fraction", "10.0", "outside_plausible"),
        ("funding_rate_fraction", "-0.11", "outside_plausible"),
        ("settlement_mark_price_usdt", 105, "must_be_decimal_text"),
        ("settlement_mark_price_usdt", "0", "invalid"),
        ("settlement_mark_price_usdt", "Infinity", "invalid"),
    ),
)
def test_funding_units_and_numeric_bounds_fail_closed(
    field: str,
    value: object,
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFundingError, match=error):
        _scenario(**{field: value})


@pytest.mark.parametrize(
    ("changes", "error"),
    (
        (
            {"funding_settled_at": "2026-07-17T12:00:01Z"},
            "outside_modeled_holding_interval",
        ),
        (
            {"funding_settled_at": "2026-07-17T13:00:01Z"},
            "outside_modeled_holding_interval",
        ),
        (
            {"funding_settled_at": "2026-07-17T12:30:00"},
            "timezone_missing",
        ),
        (
            {"funding_rate_source_observed_at": "2026-07-17T12:29:59Z"},
            "source_precedes_settlement",
        ),
        (
            {"settlement_mark_source_observed_at": "2026-07-17T12:29:59Z"},
            "source_precedes_settlement",
        ),
        (
            {"funding_rate_source_reference": "https://example.com/?key=secret"},
            "source_reference_invalid",
        ),
        (
            {"settlement_mark_source_reference": "https://example.com/mark"},
            "source_reference_invalid",
        ),
        ({"assumption_id": "bad assumption"}, "assumption_id_invalid"),
        (
            {"funding_rate_lineage_id": "bad lineage"},
            "funding_rate_lineage_id_invalid",
        ),
        (
            {"settlement_mark_lineage_id": "bad lineage"},
            "settlement_mark_lineage_id_invalid",
        ),
    ),
)
def test_funding_sources_and_holding_window_fail_closed(
    changes: dict[str, object],
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFundingError, match=error):
        _scenario(**changes)


def test_explicit_research_assumption_references_remain_unsealed() -> None:
    result = _scenario(
        funding_rate_source_reference="research-assumption:settled-rate",
        settlement_mark_source_reference="research-assumption:settlement-mark",
    ).to_dict()

    assert result["funding_rate_source_reference"] == (
        "research-assumption:settled-rate"
    )
    assert result["settlement_mark_source_reference"] == (
        "research-assumption:settlement-mark"
    )
    assert result["funding_rate_source_status"] == (
        "operator_supplied_unsealed_scenario"
    )
    assert result["settlement_mark_source_status"] == (
        "operator_supplied_unsealed_scenario"
    )


@pytest.mark.parametrize(
    "round_trip_change",
    (
        {"fees_included": True},
        {"funding_included": True},
        {"realized_execution": True},
        {"spread_added_separately": True},
        {"same_base_quantity_reconciled": False},
    ),
)
def test_tampered_source_round_trip_fails_closed(
    round_trip_change: dict[str, object],
) -> None:
    round_trip = replace(_round_trip(), **round_trip_change)

    with pytest.raises(BybitExecutionFundingError, match="round_trip_"):
        model_bybit_funding_settlement_scenario(
            round_trip,
            funding_rate_fraction="0.0001",
            settlement_mark_price_usdt="105",
            funding_settled_at="2026-07-17T12:30:00Z",
            assumption_id="fixture-one-settlement",
            funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
            funding_rate_source_observed_at="2026-07-17T13:05:00Z",
            funding_rate_lineage_id="fixture.bybit.funding.20260717",
            settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
            settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
            settlement_mark_lineage_id="fixture.bybit.mark.20260717",
        )


def test_funding_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip = _round_trip()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("funding projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    result = model_bybit_funding_settlement_scenario(
        round_trip,
        funding_rate_fraction="0.0001",
        settlement_mark_price_usdt="105",
        funding_settled_at="2026-07-17T12:30:00Z",
        assumption_id="fixture-one-settlement",
        funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
        funding_rate_source_observed_at="2026-07-17T13:05:00Z",
        funding_rate_lineage_id="fixture.bybit.funding.20260717",
        settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
        settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
        settlement_mark_lineage_id="fixture.bybit.mark.20260717",
    )

    assert result.provider_calls == 0
    assert result.writes_performed is False
