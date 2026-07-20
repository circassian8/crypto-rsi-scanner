"""Pure residual-cost sensitivity for a modeled Bybit perpetual round trip.

The decision-reference composite already rederives visible-book impact, taker
fees, funding, and decision-price latency.  A backtest still needs an explicit
answer for execution drag that is not proved by those public snapshots.  This
module keeps that uncertainty honest:

* without an explicit assumption, the all-in numeric result is unavailable;
* with an explicit per-leg basis-point assumption, the module computes a
  sensitivity result against each leg's exact executed quote value;
* the assumption remains unobserved, source-unsealed, policy-unsealed, and
  ineligible for Protocol-v2 evidence.

It selects no final slippage or unavailable-cost policy, observes no order or
fill, calls no provider, reads no credential, writes no artifact, and does not
bind the Protocol-v2 annex.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re

from .bybit_execution_cost_latency import (
    SCHEMA_VERSION as DECISION_REFERENCE_COMPOSITE_SCHEMA_VERSION,
    BybitDecisionReferenceCompositeExecutionCostScenario,
    model_bybit_decision_reference_composite_execution_cost_scenario,
)
from .bybit_execution_quality import (
    ROUND_TRIP_SCHEMA_VERSION,
    BybitVisibleBookRoundTrip,
)


SCHEMA_VERSION = (
    "crypto_radar.bybit_residual_execution_cost_sensitivity_scenario.v1"
)
SLIPPAGE_UNIT = "basis_points_of_executed_quote_value"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESEARCH_REFERENCE_RE = re.compile(
    r"^research-assumption:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class BybitExecutionResidualCostError(ValueError):
    """Raised when a residual-cost sensitivity is ambiguous or inconsistent."""


@dataclass(frozen=True)
class _BybitResidualSlippageAssumptionInput:
    """One explicit, unsealed adverse-cost sensitivity for both book legs."""

    entry_slippage_bps: str
    exit_slippage_bps: str
    unit: str
    assumption_id: str
    source_reference: str
    source_observed_at: str
    effective_from: str
    effective_until: str
    lineage_id: str


BybitResidualSlippageAssumptionInput = _BybitResidualSlippageAssumptionInput


@dataclass(frozen=True)
class _BybitResidualExecutionCostSensitivityScenario:
    """Known composite costs plus optional unsealed residual-cost sensitivity."""

    schema_version: str
    source_round_trip_schema_version: str
    source_decision_reference_composite_schema_version: str
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
    decision_reference_composite_scenario: (
        BybitDecisionReferenceCompositeExecutionCostScenario
    )
    residual_slippage_assumption: BybitResidualSlippageAssumptionInput | None
    component_identity_reconciled: bool
    component_values_fully_rederived: bool
    cost_result_status: str
    cost_result_available: bool
    unavailable_cost_behavior: str
    unavailable_cost_behavior_applied: bool
    missing_numeric_cost_components: tuple[str, ...]
    decision_reference_gross_return_usdt: float
    known_decision_reference_implementation_cost_usdt: float
    known_net_after_latency_visible_book_fees_and_funding_usdt: float
    slippage_unit: str
    slippage_reference_basis: str
    slippage_sign_convention: str
    entry_executed_quote_value_usdt: float
    exit_executed_quote_value_usdt: float
    entry_residual_slippage_bps: float | None
    exit_residual_slippage_bps: float | None
    entry_residual_slippage_cost_usdt: float | None
    exit_residual_slippage_cost_usdt: float | None
    total_residual_slippage_cost_usdt: float | None
    total_sensitivity_implementation_cost_usdt: float | None
    total_sensitivity_implementation_cost_bps: float | None
    net_after_all_supplied_costs_usdt: float | None
    known_net_minus_residual_identity_reconciled: bool
    sensitivity_arithmetic_complete_for_supplied_inputs: bool
    modeled_component_scope: str
    beyond_visible_book_slippage_status: str
    beyond_visible_book_slippage_included: bool
    beyond_visible_book_slippage_observed: bool
    beyond_visible_book_slippage_source_sealed: bool
    unavailable_cost_fail_closed_implemented: bool
    unavailable_cost_policy_sealed: bool
    complete_protocol_v2_cost_model: bool
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
        value["decision_reference_composite_scenario"] = (
            self.decision_reference_composite_scenario.to_dict()
        )
        value["missing_numeric_cost_components"] = list(
            self.missing_numeric_cost_components
        )
        return value


BybitResidualExecutionCostSensitivityScenario = (
    _BybitResidualExecutionCostSensitivityScenario
)


def _decimal_text(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise BybitExecutionResidualCostError(f"{field}_must_be_decimal_text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise BybitExecutionResidualCostError(
            f"{field}_must_be_decimal_text"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise BybitExecutionResidualCostError(
            f"{field}_must_be_non_negative_finite_decimal_text"
        )
    return parsed


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionResidualCostError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionResidualCostError(f"{field}_invalid") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionResidualCostError(f"{field}_invalid")
    return parsed


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionResidualCostError("calculated_value_non_finite")
    return round(parsed, 12)


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BybitExecutionResidualCostError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionResidualCostError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionResidualCostError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise BybitExecutionResidualCostError(f"{field}_invalid")
    return value


def _source_reference(value: object) -> str:
    if not isinstance(value, str) or not _RESEARCH_REFERENCE_RE.fullmatch(value):
        raise BybitExecutionResidualCostError("source_reference_invalid")
    return value


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _rederive_composite(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: object,
) -> BybitDecisionReferenceCompositeExecutionCostScenario:
    if not isinstance(
        scenario,
        BybitDecisionReferenceCompositeExecutionCostScenario,
    ):
        raise BybitExecutionResidualCostError(
            "decision_reference_composite_scenario_type_invalid"
        )
    if scenario.schema_version != DECISION_REFERENCE_COMPOSITE_SCHEMA_VERSION:
        raise BybitExecutionResidualCostError(
            "decision_reference_composite_scenario_schema_invalid"
        )
    try:
        rebuilt = (
            model_bybit_decision_reference_composite_execution_cost_scenario(
                round_trip,
                base_composite_scenario=scenario.base_composite_scenario,
                latency_scenario=scenario.latency_scenario,
            )
        )
    except ValueError as exc:
        raise BybitExecutionResidualCostError(
            "decision_reference_composite_scenario_rederivation_failed"
        ) from exc
    if rebuilt != scenario:
        raise BybitExecutionResidualCostError(
            "decision_reference_composite_scenario_rederivation_mismatch"
        )
    return rebuilt


def _reserved_lineages(
    scenario: BybitDecisionReferenceCompositeExecutionCostScenario,
) -> set[str]:
    funding = scenario.base_composite_scenario.funding_interval_scenario
    values = {
        scenario.round_trip.entry.request_lineage_id,
        scenario.round_trip.exit.request_lineage_id,
        scenario.round_trip.entry_instrument_constraints.lineage_id,
        scenario.round_trip.exit_instrument_constraints.lineage_id,
        scenario.latency_scenario.entry_reference.request_lineage_id,
        scenario.latency_scenario.exit_reference.request_lineage_id,
        scenario.base_composite_scenario.fee_scenario.fee_rate_lineage_id,
        funding.funding_schedule_lineage_id,
    }
    for settlement in funding.settlements:
        values.add(settlement.funding_rate_lineage_id)
        values.add(settlement.settlement_mark_lineage_id)
    return values


def _validated_assumption(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: BybitDecisionReferenceCompositeExecutionCostScenario,
    value: object,
) -> tuple[BybitResidualSlippageAssumptionInput, Decimal, Decimal]:
    if not isinstance(value, BybitResidualSlippageAssumptionInput):
        raise BybitExecutionResidualCostError(
            "residual_slippage_assumption_type_invalid"
        )
    if value.unit != SLIPPAGE_UNIT:
        raise BybitExecutionResidualCostError("slippage_unit_invalid")
    entry_bps = _decimal_text(value.entry_slippage_bps, "entry_slippage_bps")
    exit_bps = _decimal_text(value.exit_slippage_bps, "exit_slippage_bps")
    _token(value.assumption_id, "assumption_id")
    _source_reference(value.source_reference)
    observed = _utc(value.source_observed_at, "source_observed_at")
    effective_from = _utc(value.effective_from, "effective_from")
    effective_until = _utc(value.effective_until, "effective_until")
    entry_observed = _utc(
        round_trip.entry.provider_observed_at,
        "entry_provider_observed_at",
    )
    exit_observed = _utc(
        round_trip.exit.provider_observed_at,
        "exit_provider_observed_at",
    )
    if not (
        observed <= entry_observed
        and effective_from <= entry_observed < exit_observed <= effective_until
    ):
        raise BybitExecutionResidualCostError(
            "slippage_assumption_effective_window_incomplete"
        )
    lineage = _token(value.lineage_id, "lineage_id")
    if lineage in _reserved_lineages(scenario):
        raise BybitExecutionResidualCostError("slippage_lineage_reused")
    return value, entry_bps, exit_bps


def _base_result_values(
    round_trip: BybitVisibleBookRoundTrip,
    scenario: BybitDecisionReferenceCompositeExecutionCostScenario,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    gross = _decimal(
        scenario.decision_reference_gross_return_usdt,
        "decision_reference_gross_return_usdt",
    )
    known_cost = _decimal(
        scenario.total_decision_reference_implementation_cost_usdt,
        "known_decision_reference_implementation_cost_usdt",
    )
    known_net = _decimal(
        scenario.net_after_latency_visible_book_fees_and_funding_usdt,
        "known_net_after_latency_visible_book_fees_and_funding_usdt",
    )
    entry_reference_notional = _decimal(
        scenario.latency_scenario.entry_reference_mid_notional_usdt,
        "entry_reference_mid_notional_usdt",
        positive=True,
    )
    entry_quote = _decimal(
        round_trip.entry.quote_value_usdt,
        "entry_executed_quote_value_usdt",
        positive=True,
    )
    exit_quote = _decimal(
        round_trip.exit.quote_value_usdt,
        "exit_executed_quote_value_usdt",
        positive=True,
    )
    if not _close(gross - known_cost, known_net):
        raise BybitExecutionResidualCostError("known_cost_identity_invalid")
    return (
        gross,
        known_cost,
        known_net,
        entry_reference_notional,
        entry_quote,
        exit_quote,
    )


def model_bybit_residual_execution_cost_sensitivity_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    decision_reference_composite_scenario: (
        BybitDecisionReferenceCompositeExecutionCostScenario
    ),
    residual_slippage_assumption: (
        BybitResidualSlippageAssumptionInput | None
    ) = None,
) -> BybitResidualExecutionCostSensitivityScenario:
    """Rederive known costs and fail closed or add one explicit sensitivity."""

    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionResidualCostError("round_trip_type_invalid")
    if (
        round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION
        or round_trip.venue_id != "bybit"
        or round_trip.execution_mode != "perpetual"
        or round_trip.quote_asset != "USDT"
        or round_trip.realized_execution
        or not round_trip.research_only
    ):
        raise BybitExecutionResidualCostError("round_trip_contract_invalid")
    scenario = _rederive_composite(
        round_trip,
        decision_reference_composite_scenario,
    )
    (
        gross,
        known_cost,
        known_net,
        entry_reference_notional,
        entry_quote,
        exit_quote,
    ) = _base_result_values(round_trip, scenario)

    if residual_slippage_assumption is None:
        return BybitResidualExecutionCostSensitivityScenario(
            schema_version=SCHEMA_VERSION,
            source_round_trip_schema_version=round_trip.schema_version,
            source_decision_reference_composite_schema_version=(
                scenario.schema_version
            ),
            venue_id=round_trip.venue_id,
            execution_mode=round_trip.execution_mode,
            instrument_id=round_trip.instrument_id,
            canonical_asset_id=round_trip.canonical_asset_id,
            base_asset=round_trip.base_asset,
            quote_asset=round_trip.quote_asset,
            position_side=round_trip.position_side,
            base_quantity=round_trip.base_quantity,
            modeled_position_opened_at=scenario.modeled_position_opened_at,
            modeled_position_closed_at=scenario.modeled_position_closed_at,
            round_trip=round_trip,
            decision_reference_composite_scenario=scenario,
            residual_slippage_assumption=None,
            component_identity_reconciled=True,
            component_values_fully_rederived=True,
            cost_result_status=(
                "unavailable_fail_closed_missing_residual_slippage_assumption"
            ),
            cost_result_available=False,
            unavailable_cost_behavior=(
                "missing_required_residual_cost_produces_no_numeric_all_in_result"
            ),
            unavailable_cost_behavior_applied=True,
            missing_numeric_cost_components=(
                "beyond_visible_book_residual_slippage",
            ),
            decision_reference_gross_return_usdt=_float(gross),
            known_decision_reference_implementation_cost_usdt=_float(known_cost),
            known_net_after_latency_visible_book_fees_and_funding_usdt=(
                _float(known_net)
            ),
            slippage_unit=SLIPPAGE_UNIT,
            slippage_reference_basis="each_leg_exact_executed_quote_value_usdt",
            slippage_sign_convention="non_negative_adverse_cost",
            entry_executed_quote_value_usdt=_float(entry_quote),
            exit_executed_quote_value_usdt=_float(exit_quote),
            entry_residual_slippage_bps=None,
            exit_residual_slippage_bps=None,
            entry_residual_slippage_cost_usdt=None,
            exit_residual_slippage_cost_usdt=None,
            total_residual_slippage_cost_usdt=None,
            total_sensitivity_implementation_cost_usdt=None,
            total_sensitivity_implementation_cost_bps=None,
            net_after_all_supplied_costs_usdt=None,
            known_net_minus_residual_identity_reconciled=False,
            sensitivity_arithmetic_complete_for_supplied_inputs=False,
            modeled_component_scope=(
                "known_decision_reference_composite_with_required_residual_cost_"
                "unavailable"
            ),
            beyond_visible_book_slippage_status="unavailable",
            beyond_visible_book_slippage_included=False,
            beyond_visible_book_slippage_observed=False,
            beyond_visible_book_slippage_source_sealed=False,
            unavailable_cost_fail_closed_implemented=True,
            unavailable_cost_policy_sealed=False,
            complete_protocol_v2_cost_model=False,
            protocol_v2_annex_bound=False,
            protocol_v2_evidence_eligible=False,
            realized_execution=False,
            provider_calls=0,
            credentials_read=False,
            private_data_read=False,
            writes_performed=False,
            research_only=True,
        )

    assumption, entry_bps, exit_bps = _validated_assumption(
        round_trip,
        scenario,
        residual_slippage_assumption,
    )
    entry_residual = entry_quote * entry_bps / Decimal(10_000)
    exit_residual = exit_quote * exit_bps / Decimal(10_000)
    total_residual = entry_residual + exit_residual
    total_cost = known_cost + total_residual
    net = known_net - total_residual
    if not _close(gross - total_cost, net):
        raise BybitExecutionResidualCostError(
            "residual_sensitivity_cost_identity_invalid"
        )

    return BybitResidualExecutionCostSensitivityScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=round_trip.schema_version,
        source_decision_reference_composite_schema_version=scenario.schema_version,
        venue_id=round_trip.venue_id,
        execution_mode=round_trip.execution_mode,
        instrument_id=round_trip.instrument_id,
        canonical_asset_id=round_trip.canonical_asset_id,
        base_asset=round_trip.base_asset,
        quote_asset=round_trip.quote_asset,
        position_side=round_trip.position_side,
        base_quantity=round_trip.base_quantity,
        modeled_position_opened_at=scenario.modeled_position_opened_at,
        modeled_position_closed_at=scenario.modeled_position_closed_at,
        round_trip=round_trip,
        decision_reference_composite_scenario=scenario,
        residual_slippage_assumption=assumption,
        component_identity_reconciled=True,
        component_values_fully_rederived=True,
        cost_result_status="available_supplied_unsealed_research_sensitivity",
        cost_result_available=True,
        unavailable_cost_behavior=(
            "missing_required_residual_cost_produces_no_numeric_all_in_result"
        ),
        unavailable_cost_behavior_applied=False,
        missing_numeric_cost_components=(),
        decision_reference_gross_return_usdt=_float(gross),
        known_decision_reference_implementation_cost_usdt=_float(known_cost),
        known_net_after_latency_visible_book_fees_and_funding_usdt=(
            _float(known_net)
        ),
        slippage_unit=SLIPPAGE_UNIT,
        slippage_reference_basis="each_leg_exact_executed_quote_value_usdt",
        slippage_sign_convention="non_negative_adverse_cost",
        entry_executed_quote_value_usdt=_float(entry_quote),
        exit_executed_quote_value_usdt=_float(exit_quote),
        entry_residual_slippage_bps=_float(entry_bps),
        exit_residual_slippage_bps=_float(exit_bps),
        entry_residual_slippage_cost_usdt=_float(entry_residual),
        exit_residual_slippage_cost_usdt=_float(exit_residual),
        total_residual_slippage_cost_usdt=_float(total_residual),
        total_sensitivity_implementation_cost_usdt=_float(total_cost),
        total_sensitivity_implementation_cost_bps=_float(
            total_cost / entry_reference_notional * Decimal(10_000)
        ),
        net_after_all_supplied_costs_usdt=_float(net),
        known_net_minus_residual_identity_reconciled=True,
        sensitivity_arithmetic_complete_for_supplied_inputs=True,
        modeled_component_scope=(
            "decision_reference_composite_plus_supplied_unsealed_per_leg_"
            "residual_slippage_sensitivity"
        ),
        beyond_visible_book_slippage_status=(
            "supplied_unsealed_research_sensitivity_not_observed"
        ),
        beyond_visible_book_slippage_included=True,
        beyond_visible_book_slippage_observed=False,
        beyond_visible_book_slippage_source_sealed=False,
        unavailable_cost_fail_closed_implemented=True,
        unavailable_cost_policy_sealed=False,
        complete_protocol_v2_cost_model=False,
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
    "SLIPPAGE_UNIT",
    "BybitExecutionResidualCostError",
    "BybitResidualExecutionCostSensitivityScenario",
    "BybitResidualSlippageAssumptionInput",
    "model_bybit_residual_execution_cost_sensitivity_scenario",
)
