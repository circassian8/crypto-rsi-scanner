"""Composite Bybit visible-book, taker-fee, and funding cost regressions."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_cost import (
    SCHEMA_VERSION,
    BybitExecutionCostError,
    model_bybit_composite_execution_cost_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_fee import (
    OFFICIAL_FEE_STRUCTURE_URL,
    model_bybit_visible_book_taker_fee_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_funding import (
    OFFICIAL_FUNDING_HISTORY_URL,
    OFFICIAL_INSTRUMENT_INFO_URL,
    OFFICIAL_MARK_PRICE_KLINE_URL,
    BybitFundingSettlementInput,
    model_bybit_funding_interval_scenario,
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
        entry_request_lineage_id=f"test.cost.{position_side}.entry",
        exit_request_lineage_id=f"test.cost.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id=f"test.cost.{position_side}.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id=f"test.cost.{position_side}.catalog.exit",
    )


def _fee(round_trip: object, *, zero: bool = False) -> object:
    rate = "0" if zero else "0.00055"
    return model_bybit_visible_book_taker_fee_scenario(
        round_trip,
        entry_fee_rate_fraction=rate,
        exit_fee_rate_fraction=rate,
        assumption_id="fixture-composite-taker-fee",
        fee_rate_source_reference=OFFICIAL_FEE_STRUCTURE_URL,
        fee_rate_source_observed_at="2026-07-17T11:50:00Z",
        fee_rate_effective_from="2026-07-17T00:00:00Z",
        fee_rate_effective_until="2026-07-18T00:00:00Z",
        fee_rate_lineage_id="fixture.composite.fee.20260717",
    )


def _settlement(
    settled_at: str,
    *,
    rate: str,
    mark: str,
    suffix: str,
) -> BybitFundingSettlementInput:
    return BybitFundingSettlementInput(
        funding_rate_fraction=rate,
        settlement_mark_price_usdt=mark,
        funding_settled_at=settled_at,
        assumption_id=f"fixture-composite-settlement-{suffix}",
        funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
        funding_rate_source_observed_at="2026-07-17T13:05:00Z",
        funding_rate_lineage_id=f"fixture.composite.funding.{suffix}",
        settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
        settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
        settlement_mark_lineage_id=f"fixture.composite.mark.{suffix}",
    )


def _funding(round_trip: object, *, empty: bool = False) -> object:
    times = () if empty else (
        "2026-07-17T12:20:00Z",
        "2026-07-17T12:40:00Z",
    )
    settlements = () if empty else (
        _settlement(times[0], rate="0.0001", mark="105", suffix="one"),
        _settlement(times[1], rate="-0.0002", mark="106", suffix="two"),
    )
    return model_bybit_funding_interval_scenario(
        round_trip,
        settlements=settlements,
        expected_funding_settlement_times=times,
        funding_schedule_assumption_id="fixture-composite-funding-schedule",
        funding_schedule_source_reference=OFFICIAL_INSTRUMENT_INFO_URL,
        funding_schedule_source_observed_at="2026-07-17T11:50:00Z",
        funding_schedule_effective_from="2026-07-17T11:00:00Z",
        funding_schedule_effective_until="2026-07-17T14:00:00Z",
        funding_schedule_lineage_id="fixture.composite.schedule.20260717",
    )


def _composite(position_side: str = "long") -> object:
    round_trip = _round_trip(position_side)
    return model_bybit_composite_execution_cost_scenario(
        round_trip,
        fee_scenario=_fee(round_trip),
        funding_interval_scenario=_funding(round_trip),
    )


def test_composite_rederives_and_reconciles_every_modeled_component() -> None:
    result = _composite().to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["venue_id"] == "bybit"
    assert result["execution_mode"] == "perpetual"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == "long"
    assert result["base_quantity"] == "15"
    assert result["component_identity_reconciled"] is True
    assert result["component_values_fully_rederived"] is True
    assert result["total_visible_book_cost_usdt"] == 2.25
    assert result["total_taker_fee_usdt"] == pytest.approx(1.7331875)
    assert result["total_position_funding_cashflow_usdt"] == pytest.approx(0.1605)
    assert result["total_position_funding_cost_usdt"] == pytest.approx(-0.1605)
    assert result["total_visible_book_fee_and_funding_cost_usdt"] == pytest.approx(
        3.8226875
    )
    assert result["net_after_visible_book_fees_and_funding_usdt"] == pytest.approx(
        146.1773125
    )
    assert result["gross_mid_mark_return_usdt"] - result[
        "net_after_visible_book_fees_and_funding_usdt"
    ] == pytest.approx(result["total_visible_book_fee_and_funding_cost_usdt"])
    assert result["round_trip"]["schema_version"].endswith(".v3")
    assert result["fee_scenario"]["schema_version"].endswith(".v1")
    assert result["funding_interval_scenario"]["schema_version"].endswith(".v1")
    assert result["arithmetic_exact_for_supplied_inputs"] is True
    assert result["modeled_component_set_complete"] is True
    assert result["modeled_component_scope"] == (
        "visible_book_plus_unsealed_taker_fee_plus_operator_supplied_funding_schedule"
    )
    assert result["complete_protocol_v2_cost_model"] is False
    assert result["funding_interval_coverage_complete"] is False
    assert result["fee_rate_source_sealed"] is False
    assert result["funding_schedule_source_sealed"] is False
    assert result["funding_rate_sources_sealed"] is False
    assert result["settlement_mark_sources_sealed"] is False
    assert result["latency_cost_included"] is False
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["unavailable_cost_policy_sealed"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["provider_calls"] == 0
    assert result["writes_performed"] is False
    assert result["research_only"] is True
    json.dumps(result, allow_nan=False)


def test_short_position_preserves_the_inverse_funding_transfer() -> None:
    long = _composite("long").to_dict()
    short = _composite("short").to_dict()

    assert short["total_taker_fee_usdt"] == pytest.approx(1.7334625)
    assert short["total_taker_fee_usdt"] != long["total_taker_fee_usdt"]
    assert short["total_position_funding_cashflow_usdt"] == pytest.approx(
        -long["total_position_funding_cashflow_usdt"]
    )
    assert short["net_after_visible_book_fees_and_funding_usdt"] == pytest.approx(
        short["gross_mid_mark_return_usdt"]
        - short["total_visible_book_fee_and_funding_cost_usdt"]
    )


def test_zero_fee_and_empty_funding_reduce_to_visible_book_return() -> None:
    round_trip = _round_trip()
    result = model_bybit_composite_execution_cost_scenario(
        round_trip,
        fee_scenario=_fee(round_trip, zero=True),
        funding_interval_scenario=_funding(round_trip, empty=True),
    ).to_dict()

    assert result["total_taker_fee_usdt"] == 0.0
    assert result["total_position_funding_cashflow_usdt"] == 0.0
    assert result["total_visible_book_fee_and_funding_cost_usdt"] == (
        result["total_visible_book_cost_usdt"]
    )
    assert result["net_after_visible_book_fees_and_funding_usdt"] == (
        result["round_trip"]["net_visible_book_return_usdt"]
    )
    assert result["complete_protocol_v2_cost_model"] is False


@pytest.mark.parametrize(
    ("component", "field", "value", "error"),
    (
        ("fee", "total_trading_fee_usdt", 999.0, "fee_scenario_rederivation_mismatch"),
        (
            "funding",
            "total_position_funding_cashflow_usdt",
            999.0,
            "funding_interval_scenario_rederivation_mismatch",
        ),
    ),
)
def test_tampered_component_projection_fails_closed(
    component: str,
    field: str,
    value: object,
    error: str,
) -> None:
    round_trip = _round_trip()
    fee = _fee(round_trip)
    funding = _funding(round_trip)
    if component == "fee":
        fee = replace(fee, **{field: value})
    else:
        funding = replace(funding, **{field: value})

    with pytest.raises(BybitExecutionCostError, match=error):
        model_bybit_composite_execution_cost_scenario(
            round_trip,
            fee_scenario=fee,
            funding_interval_scenario=funding,
        )


def test_components_from_a_different_round_trip_fail_closed() -> None:
    long = _round_trip("long")
    short = _round_trip("short")

    with pytest.raises(
        BybitExecutionCostError,
        match="funding_interval_scenario_rederivation_mismatch",
    ):
        model_bybit_composite_execution_cost_scenario(
            long,
            fee_scenario=_fee(long),
            funding_interval_scenario=_funding(short),
        )


@pytest.mark.parametrize(
    ("fee", "funding", "error"),
    (
        (None, "valid", "fee_scenario_type_invalid"),
        ("valid", None, "funding_interval_scenario_type_invalid"),
    ),
)
def test_component_types_fail_closed(
    fee: object,
    funding: object,
    error: str,
) -> None:
    round_trip = _round_trip()
    fee_value = _fee(round_trip) if fee == "valid" else fee
    funding_value = _funding(round_trip) if funding == "valid" else funding

    with pytest.raises(BybitExecutionCostError, match=error):
        model_bybit_composite_execution_cost_scenario(
            round_trip,
            fee_scenario=fee_value,
            funding_interval_scenario=funding_value,
        )


def test_composite_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip = _round_trip()
    fee = _fee(round_trip)
    funding = _funding(round_trip)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("composite projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)

    result = model_bybit_composite_execution_cost_scenario(
        round_trip,
        fee_scenario=fee,
        funding_interval_scenario=funding,
    )

    assert result.provider_calls == 0
    assert result.credentials_read is False
    assert result.private_data_read is False
    assert result.writes_performed is False
