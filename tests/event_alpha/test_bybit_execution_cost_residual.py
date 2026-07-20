"""Residual Bybit execution-cost sensitivity and fail-closed availability."""

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
    model_bybit_decision_reference_composite_execution_cost_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_cost_residual import (
    SCHEMA_VERSION,
    SLIPPAGE_UNIT,
    BybitExecutionResidualCostError,
    BybitResidualSlippageAssumptionInput,
    model_bybit_residual_execution_cost_sensitivity_scenario,
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
        entry_request_lineage_id=f"test.residual.{position_side}.execution.entry",
        exit_request_lineage_id=f"test.residual.{position_side}.execution.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id=(
            f"test.residual.{position_side}.catalog.entry"
        ),
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id=(
            f"test.residual.{position_side}.catalog.exit"
        ),
    )


def _reference(role: str, position_side: str) -> BybitDecisionBookReferenceInput:
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
        request_lineage_id=f"test.residual.{position_side}.reference.{role}",
    )


def _decision_reference_composite(position_side: str = "long") -> tuple[object, object]:
    round_trip = _round_trip(position_side)
    fee = model_bybit_visible_book_taker_fee_scenario(
        round_trip,
        entry_fee_rate_fraction="0.00055",
        exit_fee_rate_fraction="0.00055",
        assumption_id="fixture-residual-taker-fee",
        fee_rate_source_reference=OFFICIAL_FEE_STRUCTURE_URL,
        fee_rate_source_observed_at="2026-07-17T11:50:00Z",
        fee_rate_effective_from="2026-07-17T00:00:00Z",
        fee_rate_effective_until="2026-07-18T00:00:00Z",
        fee_rate_lineage_id=f"fixture.residual.{position_side}.fee",
    )
    settlement_times = (
        "2026-07-17T12:20:00Z",
        "2026-07-17T12:40:00Z",
    )
    settlements = tuple(
        BybitFundingSettlementInput(
            funding_rate_fraction=rate,
            settlement_mark_price_usdt=mark,
            funding_settled_at=settled_at,
            assumption_id=f"fixture-residual-settlement-{index}",
            funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
            funding_rate_source_observed_at="2026-07-17T13:05:00Z",
            funding_rate_lineage_id=(
                f"fixture.residual.{position_side}.funding.{index}"
            ),
            settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
            settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
            settlement_mark_lineage_id=(
                f"fixture.residual.{position_side}.mark.{index}"
            ),
        )
        for index, (rate, mark, settled_at) in enumerate(
            (
                ("0.0001", "105", settlement_times[0]),
                ("-0.0002", "106", settlement_times[1]),
            ),
            start=1,
        )
    )
    funding = model_bybit_funding_interval_scenario(
        round_trip,
        settlements=settlements,
        expected_funding_settlement_times=settlement_times,
        funding_schedule_assumption_id="fixture-residual-schedule",
        funding_schedule_source_reference=OFFICIAL_INSTRUMENT_INFO_URL,
        funding_schedule_source_observed_at="2026-07-17T11:50:00Z",
        funding_schedule_effective_from="2026-07-17T11:00:00Z",
        funding_schedule_effective_until="2026-07-17T14:00:00Z",
        funding_schedule_lineage_id=(
            f"fixture.residual.{position_side}.schedule"
        ),
    )
    base = model_bybit_composite_execution_cost_scenario(
        round_trip,
        fee_scenario=fee,
        funding_interval_scenario=funding,
    )
    latency = model_bybit_decision_price_latency_scenario(
        round_trip,
        entry_reference=_reference("entry", position_side),
        exit_reference=_reference("exit", position_side),
    )
    composite = model_bybit_decision_reference_composite_execution_cost_scenario(
        round_trip,
        base_composite_scenario=base,
        latency_scenario=latency,
    )
    return round_trip, composite


def _assumption(
    *,
    entry_bps: object = "10",
    exit_bps: object = "20",
    unit: str = SLIPPAGE_UNIT,
    source_reference: str = "research-assumption:protocol-v2-residual-sensitivity",
    source_observed_at: str = "2026-07-17T11:50:00Z",
    effective_until: str = "2026-07-17T14:00:00Z",
    lineage_id: str = "fixture.residual.slippage.v1",
) -> BybitResidualSlippageAssumptionInput:
    return BybitResidualSlippageAssumptionInput(
        entry_slippage_bps=entry_bps,  # type: ignore[arg-type]
        exit_slippage_bps=exit_bps,  # type: ignore[arg-type]
        unit=unit,
        assumption_id="fixture-residual-slippage",
        source_reference=source_reference,
        source_observed_at=source_observed_at,
        effective_from="2026-07-17T11:00:00Z",
        effective_until=effective_until,
        lineage_id=lineage_id,
    )


def _scenario(
    position_side: str = "long",
    assumption: object = ...,
) -> object:
    round_trip, composite = _decision_reference_composite(position_side)
    supplied = _assumption() if assumption is ... else assumption
    return model_bybit_residual_execution_cost_sensitivity_scenario(
        round_trip,
        decision_reference_composite_scenario=composite,
        residual_slippage_assumption=supplied,  # type: ignore[arg-type]
    )


def test_missing_residual_cost_fails_closed_without_treating_it_as_zero() -> None:
    result = _scenario(assumption=None).to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["cost_result_status"] == (
        "unavailable_fail_closed_missing_residual_slippage_assumption"
    )
    assert result["cost_result_available"] is False
    assert result["unavailable_cost_behavior_applied"] is True
    assert result["missing_numeric_cost_components"] == [
        "beyond_visible_book_residual_slippage"
    ]
    assert result["known_decision_reference_implementation_cost_usdt"] == (
        pytest.approx(9.8226875)
    )
    assert result[
        "known_net_after_latency_visible_book_fees_and_funding_usdt"
    ] == pytest.approx(146.1773125)
    assert result["total_residual_slippage_cost_usdt"] is None
    assert result["total_sensitivity_implementation_cost_usdt"] is None
    assert result["net_after_all_supplied_costs_usdt"] is None
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["beyond_visible_book_slippage_observed"] is False
    assert result["unavailable_cost_fail_closed_implemented"] is True
    assert result["unavailable_cost_policy_sealed"] is False
    assert result["complete_protocol_v2_cost_model"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["research_only"] is True
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("position_side", "expected_total_residual", "expected_total", "expected_net"),
    (
        ("long", 4.80075, 14.6234375, 141.3765625),
        ("short", 4.80375, 2.9477125, -158.9477125),
    ),
)
def test_supplied_sensitivity_uses_each_exact_executed_leg_value(
    position_side: str,
    expected_total_residual: float,
    expected_total: float,
    expected_net: float,
) -> None:
    result = _scenario(position_side).to_dict()

    assert result["cost_result_status"] == (
        "available_supplied_unsealed_research_sensitivity"
    )
    assert result["cost_result_available"] is True
    assert result["unavailable_cost_behavior_applied"] is False
    assert result["missing_numeric_cost_components"] == []
    assert result["entry_residual_slippage_bps"] == 10.0
    assert result["exit_residual_slippage_bps"] == 20.0
    assert result["total_residual_slippage_cost_usdt"] == pytest.approx(
        expected_total_residual
    )
    assert result["total_sensitivity_implementation_cost_usdt"] == pytest.approx(
        expected_total
    )
    assert result["net_after_all_supplied_costs_usdt"] == pytest.approx(expected_net)
    assert result["known_net_minus_residual_identity_reconciled"] is True
    assert result["sensitivity_arithmetic_complete_for_supplied_inputs"] is True
    assert result["beyond_visible_book_slippage_included"] is True
    assert result["beyond_visible_book_slippage_observed"] is False
    assert result["beyond_visible_book_slippage_source_sealed"] is False
    assert result["unavailable_cost_policy_sealed"] is False
    assert result["complete_protocol_v2_cost_model"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["realized_execution"] is False
    assert result["provider_calls"] == 0
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["writes_performed"] is False


def test_explicit_zero_sensitivity_remains_unsealed_and_not_observed() -> None:
    result = _scenario(assumption=_assumption(entry_bps="0", exit_bps="0"))

    assert result.cost_result_available is True
    assert result.total_residual_slippage_cost_usdt == 0.0
    assert result.beyond_visible_book_slippage_included is True
    assert result.beyond_visible_book_slippage_observed is False
    assert result.beyond_visible_book_slippage_source_sealed is False
    assert result.complete_protocol_v2_cost_model is False


def test_tampered_composite_fails_closed_on_full_rederivation() -> None:
    round_trip, composite = _decision_reference_composite()
    tampered = replace(
        composite,
        net_after_latency_visible_book_fees_and_funding_usdt=999.0,
    )

    with pytest.raises(
        BybitExecutionResidualCostError,
        match="decision_reference_composite_scenario_rederivation_mismatch",
    ):
        model_bybit_residual_execution_cost_sensitivity_scenario(
            round_trip,
            decision_reference_composite_scenario=tampered,
            residual_slippage_assumption=_assumption(),
        )


@pytest.mark.parametrize(
    ("assumption", "error"),
    (
        (_assumption(entry_bps=True), "entry_slippage_bps_must_be_decimal_text"),
        (
            _assumption(entry_bps="-0.1"),
            "entry_slippage_bps_must_be_non_negative_finite_decimal_text",
        ),
        (
            _assumption(exit_bps="NaN"),
            "exit_slippage_bps_must_be_non_negative_finite_decimal_text",
        ),
        (_assumption(unit="percent_points"), "slippage_unit_invalid"),
        (
            _assumption(source_reference="https://example.com/slippage"),
            "source_reference_invalid",
        ),
        (
            _assumption(source_observed_at="2026-07-17T12:30:00Z"),
            "slippage_assumption_effective_window_incomplete",
        ),
        (
            _assumption(effective_until="2026-07-17T12:30:00Z"),
            "slippage_assumption_effective_window_incomplete",
        ),
        (
            _assumption(lineage_id="test.residual.long.execution.entry"),
            "slippage_lineage_reused",
        ),
        (
            _assumption(lineage_id="test.residual.long.catalog.entry"),
            "slippage_lineage_reused",
        ),
    ),
)
def test_invalid_or_ambiguous_assumptions_fail_closed(
    assumption: BybitResidualSlippageAssumptionInput,
    error: str,
) -> None:
    round_trip, composite = _decision_reference_composite()

    with pytest.raises(BybitExecutionResidualCostError, match=error):
        model_bybit_residual_execution_cost_sensitivity_scenario(
            round_trip,
            decision_reference_composite_scenario=composite,
            residual_slippage_assumption=assumption,
        )


def test_assumption_mapping_is_not_implicitly_coerced() -> None:
    round_trip, composite = _decision_reference_composite()

    with pytest.raises(
        BybitExecutionResidualCostError,
        match="residual_slippage_assumption_type_invalid",
    ):
        model_bybit_residual_execution_cost_sensitivity_scenario(
            round_trip,
            decision_reference_composite_scenario=composite,
            residual_slippage_assumption={"entry_slippage_bps": "10"},  # type: ignore[arg-type]
        )


def test_residual_cost_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip, composite = _decision_reference_composite()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("residual cost projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)

    result = model_bybit_residual_execution_cost_sensitivity_scenario(
        round_trip,
        decision_reference_composite_scenario=composite,
        residual_slippage_assumption=_assumption(),
    )
    assert result.provider_calls == 0
    assert result.writes_performed is False
