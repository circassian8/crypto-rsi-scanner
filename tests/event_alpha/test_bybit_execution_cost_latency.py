"""Decision-reference Bybit latency, book, fee, and funding composition."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_cost import (
    model_bybit_composite_execution_cost_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_cost_latency import (
    SCHEMA_VERSION,
    BybitExecutionCostLatencyError,
    model_bybit_decision_reference_composite_execution_cost_scenario,
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
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_latency import (
    OFFICIAL_ORDERBOOK_URL,
    BybitDecisionBookReferenceInput,
    model_bybit_decision_price_latency_scenario,
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
        entry_request_lineage_id=f"test.cost.latency.{position_side}.execution.entry",
        exit_request_lineage_id=f"test.cost.latency.{position_side}.execution.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id=(
            f"test.cost.latency.{position_side}.catalog.entry"
        ),
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id=(
            f"test.cost.latency.{position_side}.catalog.exit"
        ),
    )


def _fee(round_trip: object) -> object:
    return model_bybit_visible_book_taker_fee_scenario(
        round_trip,
        entry_fee_rate_fraction="0.00055",
        exit_fee_rate_fraction="0.00055",
        assumption_id="fixture-latency-composite-taker-fee",
        fee_rate_source_reference=OFFICIAL_FEE_STRUCTURE_URL,
        fee_rate_source_observed_at="2026-07-17T11:50:00Z",
        fee_rate_effective_from="2026-07-17T00:00:00Z",
        fee_rate_effective_until="2026-07-18T00:00:00Z",
        fee_rate_lineage_id="fixture.latency.composite.fee.20260717",
    )


def _funding(round_trip: object) -> object:
    times = (
        "2026-07-17T12:20:00Z",
        "2026-07-17T12:40:00Z",
    )
    settlements = (
        BybitFundingSettlementInput(
            funding_rate_fraction="0.0001",
            settlement_mark_price_usdt="105",
            funding_settled_at=times[0],
            assumption_id="fixture-latency-composite-settlement-one",
            funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
            funding_rate_source_observed_at="2026-07-17T13:05:00Z",
            funding_rate_lineage_id="fixture.latency.composite.funding.one",
            settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
            settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
            settlement_mark_lineage_id="fixture.latency.composite.mark.one",
        ),
        BybitFundingSettlementInput(
            funding_rate_fraction="-0.0002",
            settlement_mark_price_usdt="106",
            funding_settled_at=times[1],
            assumption_id="fixture-latency-composite-settlement-two",
            funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
            funding_rate_source_observed_at="2026-07-17T13:05:00Z",
            funding_rate_lineage_id="fixture.latency.composite.funding.two",
            settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
            settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
            settlement_mark_lineage_id="fixture.latency.composite.mark.two",
        ),
    )
    return model_bybit_funding_interval_scenario(
        round_trip,
        settlements=settlements,
        expected_funding_settlement_times=times,
        funding_schedule_assumption_id="fixture-latency-composite-schedule",
        funding_schedule_source_reference=OFFICIAL_INSTRUMENT_INFO_URL,
        funding_schedule_source_observed_at="2026-07-17T11:50:00Z",
        funding_schedule_effective_from="2026-07-17T11:00:00Z",
        funding_schedule_effective_until="2026-07-17T14:00:00Z",
        funding_schedule_lineage_id="fixture.latency.composite.schedule.20260717",
    )


def _reference(role: str, position_side: str) -> object:
    if role == "entry":
        bid, ask = "99.80", "99.90"
        observed = "2026-07-17T11:59:59Z"
        acquired = "2026-07-17T11:59:59.100Z"
        decision = "2026-07-17T11:59:59.200Z"
    else:
        bid, ask = "110.20", "110.30"
        observed = "2026-07-17T12:59:59Z"
        acquired = "2026-07-17T12:59:59.100Z"
        decision = "2026-07-17T12:59:59.200Z"
    return BybitDecisionBookReferenceInput(
        instrument_id="BTCUSDT",
        best_bid=bid,
        best_ask=ask,
        provider_observed_at=observed,
        acquired_at=acquired,
        decision_at=decision,
        source_reference=OFFICIAL_ORDERBOOK_URL,
        request_lineage_id=(
            f"test.cost.latency.{position_side}.reference.{role}"
        ),
    )


def _components(position_side: str = "long") -> tuple[object, object, object]:
    round_trip = _round_trip(position_side)
    base = model_bybit_composite_execution_cost_scenario(
        round_trip,
        fee_scenario=_fee(round_trip),
        funding_interval_scenario=_funding(round_trip),
    )
    latency = model_bybit_decision_price_latency_scenario(
        round_trip,
        entry_reference=_reference("entry", position_side),
        exit_reference=_reference("exit", position_side),
    )
    return round_trip, base, latency


def _scenario(position_side: str = "long") -> object:
    round_trip, base, latency = _components(position_side)
    return model_bybit_decision_reference_composite_execution_cost_scenario(
        round_trip,
        base_composite_scenario=base,
        latency_scenario=latency,
    )


def test_decision_reference_composite_rederives_every_component() -> None:
    result = _scenario().to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source_round_trip_schema_version"].endswith("round_trip.v3")
    assert result["source_base_composite_schema_version"].endswith("scenario.v1")
    assert result["source_latency_schema_version"].endswith("scenario.v1")
    assert result["venue_id"] == "bybit"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == "long"
    assert result["base_quantity"] == "15"
    assert result["component_identity_reconciled"] is True
    assert result["component_values_fully_rederived"] is True
    assert result["decision_reference_gross_return_usdt"] == 156.0
    assert result["execution_book_gross_mid_mark_return_usdt"] == 150.0
    assert result["total_latency_cost_usdt"] == 6.0
    assert result["total_visible_book_cost_usdt"] == 2.25
    assert result["total_taker_fee_usdt"] == pytest.approx(1.7331875)
    assert result["total_position_funding_cashflow_usdt"] == pytest.approx(0.1605)
    assert result["total_position_funding_cost_usdt"] == pytest.approx(-0.1605)
    assert result["total_decision_reference_implementation_cost_usdt"] == (
        pytest.approx(9.8226875)
    )
    assert result[
        "net_after_latency_visible_book_fees_and_funding_usdt"
    ] == pytest.approx(146.1773125)
    assert result["net_equals_execution_mid_composite_result"] is True
    assert result["decision_reference_cost_identity_reconciled"] is True
    assert result["arithmetic_exact_for_supplied_inputs"] is True
    assert result["modeled_component_set_complete"] is True
    assert result["modeled_component_scope"] == (
        "decision_reference_latency_plus_visible_book_plus_unsealed_taker_fee_"
        "plus_operator_supplied_funding_schedule"
    )
    assert result["complete_protocol_v2_cost_model"] is False
    assert result["latency_reference_set_complete_for_supplied_scenario"] is True
    assert result["realized_execution_latency_observed"] is False
    assert result["latency_cost_policy_sealed"] is False
    assert result["funding_interval_coverage_complete"] is False
    assert result["decision_reference_sources_sealed"] is False
    assert result["spread_added_separately"] is False
    assert result["latency_cost_included"] is True
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["unavailable_cost_policy_sealed"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["realized_execution"] is False
    assert result["provider_calls"] == 0
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["writes_performed"] is False
    assert result["research_only"] is True
    json.dumps(result, allow_nan=False)


def test_short_favorable_latency_preserves_signed_cost_identity() -> None:
    result = _scenario("short").to_dict()

    assert result["decision_reference_gross_return_usdt"] == -156.0
    assert result["execution_book_gross_mid_mark_return_usdt"] == -150.0
    assert result["total_latency_cost_usdt"] == -6.0
    assert result["total_latency_cashflow_usdt"] == 6.0
    assert result["total_taker_fee_usdt"] == pytest.approx(1.7334625)
    assert result["total_position_funding_cost_usdt"] == pytest.approx(0.1605)
    assert result["total_decision_reference_implementation_cost_usdt"] == (
        pytest.approx(-1.8560375)
    )
    assert result[
        "net_after_latency_visible_book_fees_and_funding_usdt"
    ] == pytest.approx(-154.1439625)


@pytest.mark.parametrize(
    ("component", "field", "error"),
    (
        (
            "base",
            "total_taker_fee_usdt",
            "base_composite_scenario_rederivation_mismatch",
        ),
        (
            "latency",
            "total_latency_cost_usdt",
            "latency_scenario_rederivation_mismatch",
        ),
    ),
)
def test_tampered_components_fail_closed(
    component: str,
    field: str,
    error: str,
) -> None:
    round_trip, base, latency = _components()
    if component == "base":
        base = replace(base, **{field: 999.0})
    else:
        latency = replace(latency, **{field: 999.0})

    with pytest.raises(BybitExecutionCostLatencyError, match=error):
        model_bybit_decision_reference_composite_execution_cost_scenario(
            round_trip,
            base_composite_scenario=base,
            latency_scenario=latency,
        )


def test_components_from_a_different_round_trip_fail_closed() -> None:
    long, base, _latency = _components("long")
    _short, _short_base, short_latency = _components("short")

    with pytest.raises(
        BybitExecutionCostLatencyError,
        match="latency_scenario_rederivation_mismatch",
    ):
        model_bybit_decision_reference_composite_execution_cost_scenario(
            long,
            base_composite_scenario=base,
            latency_scenario=short_latency,
        )


@pytest.mark.parametrize(
    ("base", "latency", "error"),
    (
        (None, "valid", "base_composite_scenario_type_invalid"),
        ("valid", None, "latency_scenario_type_invalid"),
    ),
)
def test_component_types_fail_closed(
    base: object,
    latency: object,
    error: str,
) -> None:
    round_trip, valid_base, valid_latency = _components()

    with pytest.raises(BybitExecutionCostLatencyError, match=error):
        model_bybit_decision_reference_composite_execution_cost_scenario(
            round_trip,
            base_composite_scenario=valid_base if base == "valid" else base,
            latency_scenario=(valid_latency if latency == "valid" else latency),
        )


def test_decision_reference_composite_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip, base, latency = _components()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("decision-reference composite must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)

    result = model_bybit_decision_reference_composite_execution_cost_scenario(
        round_trip,
        base_composite_scenario=base,
        latency_scenario=latency,
    )
    assert result.provider_calls == 0
    assert result.writes_performed is False
