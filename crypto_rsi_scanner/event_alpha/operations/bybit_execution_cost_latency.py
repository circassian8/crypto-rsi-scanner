"""Decision-reference composite cost for one modeled Bybit round trip.

This projection joins the exact identity-rederived visible-book/fee/funding
composite with the supplied decision-price latency decomposition.  It treats
latency as implementation shortfall relative to decision-book midpoints, not as
another charge on the already modeled execution-mid return.  Every component is
fully rederived before the final native-USDT identity is accepted.

The result remains an unsealed research scenario.  It does not observe orders
or fills, model liquidity beyond the visible book, choose an unavailable-cost
rule, seal any source, call a provider, or bind Protocol v2.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import math

from .bybit_execution_cost import (
    SCHEMA_VERSION as BASE_COMPOSITE_SCHEMA_VERSION,
    BybitCompositeExecutionCostScenario,
    model_bybit_composite_execution_cost_scenario,
)
from .bybit_execution_latency import (
    SCHEMA_VERSION as LATENCY_SCHEMA_VERSION,
    BybitDecisionPriceLatencyScenario,
    model_bybit_decision_price_latency_scenario,
)
from .bybit_execution_quality import (
    ROUND_TRIP_SCHEMA_VERSION,
    BybitVisibleBookRoundTrip,
)


SCHEMA_VERSION = (
    "crypto_radar.bybit_decision_reference_composite_execution_cost_scenario.v1"
)


class BybitExecutionCostLatencyError(ValueError):
    """Raised when latency and base cost projections do not share identity."""


@dataclass(frozen=True)
class _BybitDecisionReferenceCompositeExecutionCostScenario:
    """One exact decision-reference cost decomposition over supplied inputs."""

    schema_version: str
    source_round_trip_schema_version: str
    source_base_composite_schema_version: str
    source_latency_schema_version: str
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
    base_composite_scenario: BybitCompositeExecutionCostScenario
    latency_scenario: BybitDecisionPriceLatencyScenario
    component_identity_reconciled: bool
    component_values_fully_rederived: bool
    decision_reference_gross_return_usdt: float
    execution_book_gross_mid_mark_return_usdt: float
    total_latency_cost_usdt: float
    total_latency_cashflow_usdt: float
    total_visible_book_cost_usdt: float
    total_taker_fee_usdt: float
    total_position_funding_cashflow_usdt: float
    total_position_funding_cost_usdt: float
    total_decision_reference_implementation_cost_usdt: float
    total_decision_reference_implementation_cost_bps: float
    net_after_latency_visible_book_fees_and_funding_usdt: float
    net_equals_execution_mid_composite_result: bool
    decision_reference_cost_identity_reconciled: bool
    arithmetic_exact_for_supplied_inputs: bool
    modeled_component_set_complete: bool
    modeled_component_scope: str
    complete_protocol_v2_cost_model: bool
    latency_reference_set_complete_for_supplied_scenario: bool
    realized_execution_latency_observed: bool
    latency_cost_policy_sealed: bool
    funding_interval_coverage_complete: bool
    fee_rate_source_sealed: bool
    funding_schedule_source_sealed: bool
    funding_rate_sources_sealed: bool
    settlement_mark_sources_sealed: bool
    decision_reference_sources_sealed: bool
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
        value = asdict(self)
        value["round_trip"] = self.round_trip.to_dict()
        value["base_composite_scenario"] = self.base_composite_scenario.to_dict()
        value["latency_scenario"] = self.latency_scenario.to_dict()
        return value


BybitDecisionReferenceCompositeExecutionCostScenario = (
    _BybitDecisionReferenceCompositeExecutionCostScenario
)


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionCostLatencyError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionCostLatencyError(f"{field}_invalid") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionCostLatencyError(f"{field}_invalid")
    return parsed


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionCostLatencyError("calculated_value_non_finite")
    return round(parsed, 12)


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _rederive_base_composite(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: object,
) -> BybitCompositeExecutionCostScenario:
    if not isinstance(scenario, BybitCompositeExecutionCostScenario):
        raise BybitExecutionCostLatencyError("base_composite_scenario_type_invalid")
    if scenario.schema_version != BASE_COMPOSITE_SCHEMA_VERSION:
        raise BybitExecutionCostLatencyError(
            "base_composite_scenario_schema_invalid"
        )
    try:
        rebuilt = model_bybit_composite_execution_cost_scenario(
            round_trip,
            fee_scenario=scenario.fee_scenario,
            funding_interval_scenario=scenario.funding_interval_scenario,
        )
    except ValueError as exc:
        raise BybitExecutionCostLatencyError(
            "base_composite_scenario_rederivation_failed"
        ) from exc
    if rebuilt != scenario:
        raise BybitExecutionCostLatencyError(
            "base_composite_scenario_rederivation_mismatch"
        )
    return rebuilt


def _rederive_latency(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: object,
) -> BybitDecisionPriceLatencyScenario:
    if not isinstance(scenario, BybitDecisionPriceLatencyScenario):
        raise BybitExecutionCostLatencyError("latency_scenario_type_invalid")
    if scenario.schema_version != LATENCY_SCHEMA_VERSION:
        raise BybitExecutionCostLatencyError("latency_scenario_schema_invalid")
    try:
        rebuilt = model_bybit_decision_price_latency_scenario(
            round_trip,
            entry_reference=scenario.entry_reference,
            exit_reference=scenario.exit_reference,
        )
    except ValueError as exc:
        raise BybitExecutionCostLatencyError(
            "latency_scenario_rederivation_failed"
        ) from exc
    if rebuilt != scenario:
        raise BybitExecutionCostLatencyError(
            "latency_scenario_rederivation_mismatch"
        )
    return rebuilt


def model_bybit_decision_reference_composite_execution_cost_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    base_composite_scenario: BybitCompositeExecutionCostScenario,
    latency_scenario: BybitDecisionPriceLatencyScenario,
) -> BybitDecisionReferenceCompositeExecutionCostScenario:
    """Fully rederive and combine the supplied decision-reference components."""

    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionCostLatencyError("round_trip_type_invalid")
    if round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION:
        raise BybitExecutionCostLatencyError("round_trip_schema_invalid")
    base = _rederive_base_composite(round_trip, base_composite_scenario)
    latency = _rederive_latency(round_trip, latency_scenario)

    reference_gross = _decimal(
        latency.decision_reference_gross_return_usdt,
        "decision_reference_gross_return_usdt",
    )
    execution_gross = _decimal(
        latency.execution_book_gross_mid_mark_return_usdt,
        "execution_book_gross_mid_mark_return_usdt",
    )
    latency_cost = _decimal(latency.total_latency_cost_usdt, "total_latency_cost_usdt")
    visible_cost = _decimal(
        base.total_visible_book_cost_usdt,
        "total_visible_book_cost_usdt",
    )
    fee = _decimal(base.total_taker_fee_usdt, "total_taker_fee_usdt")
    funding_cashflow = _decimal(
        base.total_position_funding_cashflow_usdt,
        "total_position_funding_cashflow_usdt",
    )
    funding_cost = _decimal(
        base.total_position_funding_cost_usdt,
        "total_position_funding_cost_usdt",
    )
    entry_reference_notional = _decimal(
        latency.entry_reference_mid_notional_usdt,
        "entry_reference_mid_notional_usdt",
        positive=True,
    )
    base_net = _decimal(
        base.net_after_visible_book_fees_and_funding_usdt,
        "base_composite_net_usdt",
    )
    if not _close(reference_gross - latency_cost, execution_gross):
        raise BybitExecutionCostLatencyError(
            "decision_reference_latency_identity_invalid"
        )
    total_cost = latency_cost + visible_cost + fee + funding_cost
    net = reference_gross - total_cost
    if not _close(net, base_net):
        raise BybitExecutionCostLatencyError(
            "decision_reference_composite_cost_identity_invalid"
        )
    if not _close(
        net,
        execution_gross - visible_cost - fee + funding_cashflow,
    ):
        raise BybitExecutionCostLatencyError(
            "execution_mid_composite_cost_identity_invalid"
        )

    return BybitDecisionReferenceCompositeExecutionCostScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=round_trip.schema_version,
        source_base_composite_schema_version=base.schema_version,
        source_latency_schema_version=latency.schema_version,
        venue_id=round_trip.venue_id,
        execution_mode=round_trip.execution_mode,
        instrument_id=round_trip.instrument_id,
        canonical_asset_id=round_trip.canonical_asset_id,
        base_asset=round_trip.base_asset,
        quote_asset=round_trip.quote_asset,
        position_side=round_trip.position_side,
        base_quantity=round_trip.base_quantity,
        modeled_position_opened_at=base.modeled_position_opened_at,
        modeled_position_closed_at=base.modeled_position_closed_at,
        round_trip=round_trip,
        base_composite_scenario=base,
        latency_scenario=latency,
        component_identity_reconciled=True,
        component_values_fully_rederived=True,
        decision_reference_gross_return_usdt=_float(reference_gross),
        execution_book_gross_mid_mark_return_usdt=_float(execution_gross),
        total_latency_cost_usdt=_float(latency_cost),
        total_latency_cashflow_usdt=_float(-latency_cost),
        total_visible_book_cost_usdt=_float(visible_cost),
        total_taker_fee_usdt=_float(fee),
        total_position_funding_cashflow_usdt=_float(funding_cashflow),
        total_position_funding_cost_usdt=_float(funding_cost),
        total_decision_reference_implementation_cost_usdt=_float(total_cost),
        total_decision_reference_implementation_cost_bps=_float(
            total_cost / entry_reference_notional * Decimal("10000")
        ),
        net_after_latency_visible_book_fees_and_funding_usdt=_float(net),
        net_equals_execution_mid_composite_result=True,
        decision_reference_cost_identity_reconciled=True,
        arithmetic_exact_for_supplied_inputs=True,
        modeled_component_set_complete=True,
        modeled_component_scope=(
            "decision_reference_latency_plus_visible_book_plus_unsealed_taker_"
            "fee_plus_operator_supplied_funding_schedule"
        ),
        complete_protocol_v2_cost_model=False,
        latency_reference_set_complete_for_supplied_scenario=True,
        realized_execution_latency_observed=False,
        latency_cost_policy_sealed=False,
        funding_interval_coverage_complete=False,
        fee_rate_source_sealed=False,
        funding_schedule_source_sealed=False,
        funding_rate_sources_sealed=False,
        settlement_mark_sources_sealed=False,
        decision_reference_sources_sealed=False,
        spread_added_separately=False,
        latency_cost_included=True,
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
    "BybitDecisionReferenceCompositeExecutionCostScenario",
    "BybitExecutionCostLatencyError",
    "model_bybit_decision_reference_composite_execution_cost_scenario",
)
