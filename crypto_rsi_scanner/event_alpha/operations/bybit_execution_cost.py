"""Pure composite cost projection for one modeled Bybit perpetual round trip.

The visible-book, taker-fee, and funding-interval primitives deliberately stay
separate because their evidence and policy boundaries differ.  This module
combines exact instances of those projections only after fully rederiving both
cost add-ons from the supplied round trip.  It selects no rate, schedule, order
style, latency rule, slippage rule, provider, or Protocol-v2 policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import math

from .bybit_execution_fee import (
    SCHEMA_VERSION as FEE_SCHEMA_VERSION,
    BybitVisibleBookTakerFeeScenario,
    model_bybit_visible_book_taker_fee_scenario,
)
from .bybit_execution_funding import (
    INTERVAL_SCHEMA_VERSION as FUNDING_INTERVAL_SCHEMA_VERSION,
    BybitFundingIntervalScenario,
    BybitFundingSettlementInput,
    model_bybit_funding_interval_scenario,
)
from .bybit_execution_quality import (
    ROUND_TRIP_SCHEMA_VERSION,
    BybitVisibleBookRoundTrip,
)


SCHEMA_VERSION = "crypto_radar.bybit_composite_execution_cost_scenario.v1"


class BybitExecutionCostError(ValueError):
    """Raised when supplied component projections do not share one identity."""


@dataclass(frozen=True)
class _BybitCompositeExecutionCostScenario:
    """One exact composite of visible-book, fee, and funding scenario costs."""

    schema_version: str
    source_round_trip_schema_version: str
    source_fee_schema_version: str
    source_funding_interval_schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    position_side: str
    base_quantity: str
    modeled_position_opened_at: str
    modeled_position_closed_at: str
    round_trip: BybitVisibleBookRoundTrip
    fee_scenario: BybitVisibleBookTakerFeeScenario
    funding_interval_scenario: BybitFundingIntervalScenario
    component_identity_reconciled: bool
    component_values_fully_rederived: bool
    gross_mid_mark_return_usdt: float
    total_visible_book_cost_usdt: float
    total_taker_fee_usdt: float
    total_position_funding_cashflow_usdt: float
    total_position_funding_cost_usdt: float
    net_after_visible_book_fees_and_funding_usdt: float
    total_visible_book_fee_and_funding_cost_usdt: float
    total_visible_book_fee_and_funding_cost_bps_of_entry_mid_notional: float
    arithmetic_exact_for_supplied_inputs: bool
    modeled_component_set_complete: bool
    modeled_component_scope: str
    complete_protocol_v2_cost_model: bool
    funding_interval_coverage_complete: bool
    fee_rate_source_sealed: bool
    funding_schedule_source_sealed: bool
    funding_rate_sources_sealed: bool
    settlement_mark_sources_sealed: bool
    spread_added_separately: bool
    latency_cost_included: bool
    beyond_visible_book_slippage_included: bool
    unavailable_cost_policy_sealed: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    realized_execution: bool
    provider_calls: int
    credentials_read: bool
    private_data_read: bool
    writes_performed: bool
    research_only: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


BybitCompositeExecutionCostScenario = _BybitCompositeExecutionCostScenario


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionCostError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionCostError(f"{field}_invalid") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionCostError(f"{field}_invalid")
    return parsed


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionCostError("calculated_value_non_finite")
    return round(parsed, 12)


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _funding_inputs(
    scenario: BybitFundingIntervalScenario,
) -> tuple[BybitFundingSettlementInput, ...]:
    return tuple(
        BybitFundingSettlementInput(
            funding_rate_fraction=row.funding_rate_fraction,
            settlement_mark_price_usdt=row.settlement_mark_price_usdt,
            funding_settled_at=row.funding_settled_at,
            assumption_id=row.assumption_id,
            funding_rate_source_reference=row.funding_rate_source_reference,
            funding_rate_source_observed_at=row.funding_rate_source_observed_at,
            funding_rate_lineage_id=row.funding_rate_lineage_id,
            settlement_mark_source_reference=row.settlement_mark_source_reference,
            settlement_mark_source_observed_at=(
                row.settlement_mark_source_observed_at
            ),
            settlement_mark_lineage_id=row.settlement_mark_lineage_id,
        )
        for row in scenario.settlements
    )


def _rederive_fee(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: BybitVisibleBookTakerFeeScenario,
) -> BybitVisibleBookTakerFeeScenario:
    if not isinstance(scenario, BybitVisibleBookTakerFeeScenario):
        raise BybitExecutionCostError("fee_scenario_type_invalid")
    if scenario.schema_version != FEE_SCHEMA_VERSION:
        raise BybitExecutionCostError("fee_scenario_schema_invalid")
    try:
        rebuilt = model_bybit_visible_book_taker_fee_scenario(
            round_trip,
            entry_fee_rate_fraction=scenario.entry_fee_rate_fraction,
            exit_fee_rate_fraction=scenario.exit_fee_rate_fraction,
            assumption_id=scenario.assumption_id,
            fee_rate_source_reference=scenario.fee_rate_source_reference,
            fee_rate_source_observed_at=scenario.fee_rate_source_observed_at,
            fee_rate_effective_from=scenario.fee_rate_effective_from,
            fee_rate_effective_until=scenario.fee_rate_effective_until,
            fee_rate_lineage_id=scenario.fee_rate_lineage_id,
        )
    except ValueError as exc:
        raise BybitExecutionCostError("fee_scenario_rederivation_failed") from exc
    if rebuilt != scenario:
        raise BybitExecutionCostError("fee_scenario_rederivation_mismatch")
    return rebuilt


def _rederive_funding(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: BybitFundingIntervalScenario,
) -> BybitFundingIntervalScenario:
    if not isinstance(scenario, BybitFundingIntervalScenario):
        raise BybitExecutionCostError("funding_interval_scenario_type_invalid")
    if scenario.schema_version != FUNDING_INTERVAL_SCHEMA_VERSION:
        raise BybitExecutionCostError("funding_interval_scenario_schema_invalid")
    try:
        rebuilt = model_bybit_funding_interval_scenario(
            round_trip,
            settlements=_funding_inputs(scenario),
            expected_funding_settlement_times=(
                scenario.expected_funding_settlement_times
            ),
            funding_schedule_assumption_id=(
                scenario.funding_schedule_assumption_id
            ),
            funding_schedule_source_reference=(
                scenario.funding_schedule_source_reference
            ),
            funding_schedule_source_observed_at=(
                scenario.funding_schedule_source_observed_at
            ),
            funding_schedule_effective_from=(
                scenario.funding_schedule_effective_from
            ),
            funding_schedule_effective_until=(
                scenario.funding_schedule_effective_until
            ),
            funding_schedule_lineage_id=scenario.funding_schedule_lineage_id,
        )
    except ValueError as exc:
        raise BybitExecutionCostError(
            "funding_interval_scenario_rederivation_failed"
        ) from exc
    if rebuilt != scenario:
        raise BybitExecutionCostError(
            "funding_interval_scenario_rederivation_mismatch"
        )
    return rebuilt


def model_bybit_composite_execution_cost_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    fee_scenario: BybitVisibleBookTakerFeeScenario,
    funding_interval_scenario: BybitFundingIntervalScenario,
) -> BybitCompositeExecutionCostScenario:
    """Fully rederive and combine three unsealed modeled cost components."""

    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionCostError("round_trip_type_invalid")
    if round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION:
        raise BybitExecutionCostError("round_trip_schema_invalid")
    fee = _rederive_fee(round_trip, fee_scenario)
    funding = _rederive_funding(round_trip, funding_interval_scenario)

    gross_return = _decimal(
        round_trip.gross_mid_mark_return_usdt,
        "gross_mid_mark_return_usdt",
    )
    net_visible = _decimal(
        round_trip.net_visible_book_return_usdt,
        "net_visible_book_return_usdt",
    )
    visible_cost = _decimal(
        round_trip.total_visible_book_cost_usdt,
        "total_visible_book_cost_usdt",
    )
    entry_mid_notional = _decimal(
        round_trip.entry_mid_notional_usdt,
        "entry_mid_notional_usdt",
        positive=True,
    )
    if visible_cost < 0 or not _close(
        gross_return - net_visible,
        visible_cost,
    ):
        raise BybitExecutionCostError("round_trip_visible_cost_identity_invalid")

    entry_quote = _decimal(
        round_trip.entry.quote_value_usdt,
        "entry_quote_value_usdt",
        positive=True,
    )
    exit_quote = _decimal(
        round_trip.exit.quote_value_usdt,
        "exit_quote_value_usdt",
        positive=True,
    )
    entry_rate = _decimal(
        fee.entry_fee_rate_fraction,
        "entry_fee_rate_fraction",
    )
    exit_rate = _decimal(
        fee.exit_fee_rate_fraction,
        "exit_fee_rate_fraction",
    )
    total_fee = entry_quote * entry_rate + exit_quote * exit_rate

    base_quantity = _decimal(
        round_trip.base_quantity,
        "base_quantity",
        positive=True,
    )
    funding_cashflow = Decimal("0")
    for row in funding.settlements:
        mark = _decimal(
            row.settlement_mark_price_usdt,
            "settlement_mark_price_usdt",
            positive=True,
        )
        rate = _decimal(row.funding_rate_fraction, "funding_rate_fraction")
        transfer = base_quantity * mark * rate
        funding_cashflow += (
            -transfer if round_trip.position_side == "long" else transfer
        )

    funding_cost = -funding_cashflow
    total_cost = visible_cost + total_fee + funding_cost
    net_after_all = gross_return - total_cost
    if not _close(
        net_after_all,
        net_visible - total_fee + funding_cashflow,
    ):
        raise BybitExecutionCostError("composite_cost_identity_invalid")

    return BybitCompositeExecutionCostScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=round_trip.schema_version,
        source_fee_schema_version=fee.schema_version,
        source_funding_interval_schema_version=funding.schema_version,
        venue_id=round_trip.venue_id,
        execution_mode=round_trip.execution_mode,
        instrument_id=round_trip.instrument_id,
        canonical_asset_id=round_trip.canonical_asset_id,
        base_asset=round_trip.base_asset,
        quote_asset=round_trip.quote_asset,
        position_side=round_trip.position_side,
        base_quantity=round_trip.base_quantity,
        modeled_position_opened_at=funding.modeled_position_opened_at,
        modeled_position_closed_at=funding.modeled_position_closed_at,
        round_trip=round_trip,
        fee_scenario=fee,
        funding_interval_scenario=funding,
        component_identity_reconciled=True,
        component_values_fully_rederived=True,
        gross_mid_mark_return_usdt=_float(gross_return),
        total_visible_book_cost_usdt=_float(visible_cost),
        total_taker_fee_usdt=_float(total_fee),
        total_position_funding_cashflow_usdt=_float(funding_cashflow),
        total_position_funding_cost_usdt=_float(funding_cost),
        net_after_visible_book_fees_and_funding_usdt=_float(net_after_all),
        total_visible_book_fee_and_funding_cost_usdt=_float(total_cost),
        total_visible_book_fee_and_funding_cost_bps_of_entry_mid_notional=(
            _float(total_cost / entry_mid_notional * Decimal("10000"))
        ),
        arithmetic_exact_for_supplied_inputs=True,
        modeled_component_set_complete=True,
        modeled_component_scope=(
            "visible_book_plus_unsealed_taker_fee_plus_operator_supplied_"
            "funding_schedule"
        ),
        complete_protocol_v2_cost_model=False,
        funding_interval_coverage_complete=False,
        fee_rate_source_sealed=False,
        funding_schedule_source_sealed=False,
        funding_rate_sources_sealed=False,
        settlement_mark_sources_sealed=False,
        spread_added_separately=False,
        latency_cost_included=False,
        beyond_visible_book_slippage_included=False,
        unavailable_cost_policy_sealed=False,
        protocol_v2_annex_bound=False,
        protocol_v2_evidence_eligible=False,
        realized_execution=False,
        provider_calls=0,
        credentials_read=False,
        private_data_read=False,
        writes_performed=False,
        research_only=True,
    )


__all__ = (
    "SCHEMA_VERSION",
    "BybitCompositeExecutionCostScenario",
    "BybitExecutionCostError",
    "model_bybit_composite_execution_cost_scenario",
)
