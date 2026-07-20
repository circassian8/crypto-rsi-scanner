"""Pure decision-price latency projection for one modeled Bybit round trip.

Implementation shortfall compares an execution result with the price available
when the decision was made.  The existing visible-book primitive instead uses
the midpoint of each later execution book.  This module keeps those concepts
separate: it measures signed midpoint drift from two supplied decision-book
references to the corresponding later Bybit matching-engine book timestamps,
then proves the exact decomposition from decision-reference return through
latency drift and visible-book impact.

The references remain unsealed research inputs.  This module observes no order
submission or fill, chooses no latency allowance, calls no provider, reads no
credential, writes no artifact, and does not bind the Protocol-v2 annex.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re

from .bybit_execution_quality import (
    ROUND_TRIP_SCHEMA_VERSION,
    BybitVisibleBookRoundTrip,
)


SCHEMA_VERSION = "crypto_radar.bybit_decision_price_latency_scenario.v1"
OFFICIAL_ORDERBOOK_URL = (
    "https://bybit-exchange.github.io/docs/v5/market/orderbook"
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESEARCH_REFERENCE_RE = re.compile(
    r"^research-assumption:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class BybitExecutionLatencyError(ValueError):
    """Raised when a supplied decision-price latency scenario is invalid."""


@dataclass(frozen=True)
class _BybitDecisionBookReferenceInput:
    """One exact operator-supplied best-bid/ask decision reference."""

    instrument_id: str
    best_bid: str
    best_ask: str
    provider_observed_at: str
    acquired_at: str
    decision_at: str
    source_reference: str
    request_lineage_id: str


BybitDecisionBookReferenceInput = _BybitDecisionBookReferenceInput


@dataclass(frozen=True)
class _BybitDecisionBookReference:
    """Canonical decision-book reference bound to one later execution leg."""

    snapshot_role: str
    instrument_id: str
    best_bid: str
    best_ask: str
    mid_price: str
    provider_observed_at: str
    acquired_at: str
    decision_at: str
    execution_book_provider_observed_at: str
    execution_book_acquired_at: str
    market_drift_window_microseconds: int
    decision_to_execution_book_observation_microseconds: int
    decision_to_execution_book_acquisition_microseconds: int
    source_status: str
    source_reference: str
    request_lineage_id: str
    source_sealed: bool
    matching_engine_timestamp_basis: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


BybitDecisionBookReference = _BybitDecisionBookReference


@dataclass(frozen=True)
class _BybitDecisionPriceLatencyScenario:
    """Signed decision-mid drift plus visible-book cost for one round trip."""

    schema_version: str
    source_round_trip_schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    position_side: str
    base_quantity: str
    entry_reference: BybitDecisionBookReferenceInput
    exit_reference: BybitDecisionBookReferenceInput
    entry_reference_projection: BybitDecisionBookReference
    exit_reference_projection: BybitDecisionBookReference
    round_trip: BybitVisibleBookRoundTrip
    decision_reference_identity_reconciled: bool
    reference_lineages_distinct: bool
    reference_and_execution_lineages_distinct: bool
    reference_timeline_reconciled: bool
    entry_decision_mid_price_usdt: str
    entry_execution_mid_price_usdt: str
    exit_decision_mid_price_usdt: str
    exit_execution_mid_price_usdt: str
    entry_reference_mid_notional_usdt: float
    decision_reference_gross_return_usdt: float
    execution_book_gross_mid_mark_return_usdt: float
    entry_latency_cost_usdt: float
    exit_latency_cost_usdt: float
    total_latency_cost_usdt: float
    total_latency_cashflow_usdt: float
    total_latency_cost_bps_of_entry_reference_notional: float
    total_visible_book_cost_usdt: float
    net_visible_book_return_usdt: float
    net_from_decision_reference_after_latency_and_visible_book_usdt: float
    decision_reference_to_execution_mid_identity_reconciled: bool
    decision_reference_to_visible_book_identity_reconciled: bool
    latency_cost_sign_convention: str
    latency_measurement_basis: str
    cost_benchmark: str
    arithmetic_exact_for_supplied_inputs: bool
    latency_reference_set_complete_for_supplied_scenario: bool
    actual_order_submission_observed: bool
    actual_fill_observed: bool
    realized_execution_latency_observed: bool
    decision_reference_sources_sealed: bool
    latency_cost_policy_sealed: bool
    fees_included: bool
    funding_included: bool
    spread_added_separately: bool
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
        value["entry_reference_projection"] = (
            self.entry_reference_projection.to_dict()
        )
        value["exit_reference_projection"] = (
            self.exit_reference_projection.to_dict()
        )
        value["round_trip"] = self.round_trip.to_dict()
        return value


BybitDecisionPriceLatencyScenario = _BybitDecisionPriceLatencyScenario


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BybitExecutionLatencyError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionLatencyError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionLatencyError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _decimal_text(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise BybitExecutionLatencyError(f"{field}_must_be_decimal_text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise BybitExecutionLatencyError(
            f"{field}_must_be_decimal_text"
        ) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise BybitExecutionLatencyError(f"{field}_invalid")
    return parsed


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionLatencyError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionLatencyError(f"{field}_invalid") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionLatencyError(f"{field}_invalid")
    return parsed


def _canonical(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionLatencyError("calculated_value_non_finite")
    return round(parsed, 12)


def _microseconds(value: object) -> int:
    if not hasattr(value, "days"):
        raise BybitExecutionLatencyError("latency_duration_invalid")
    return (
        int(value.days) * 86_400_000_000
        + int(value.seconds) * 1_000_000
        + int(value.microseconds)
    )


def _source_reference(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BybitExecutionLatencyError(f"{field}_invalid")
    if value == OFFICIAL_ORDERBOOK_URL or _RESEARCH_REFERENCE_RE.fullmatch(value):
        return value
    raise BybitExecutionLatencyError(f"{field}_invalid")


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise BybitExecutionLatencyError(f"{field}_invalid")
    return value


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _validate_round_trip(round_trip: object) -> BybitVisibleBookRoundTrip:
    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionLatencyError("round_trip_type_invalid")
    if (
        round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION
        or round_trip.venue_id != "bybit"
        or round_trip.execution_mode != "perpetual"
        or round_trip.quote_asset != "USDT"
        or round_trip.position_side not in {"long", "short"}
        or round_trip.realized_execution
        or round_trip.latency_cost_included
        or round_trip.fees_included
        or round_trip.funding_included
        or not round_trip.research_only
    ):
        raise BybitExecutionLatencyError("round_trip_contract_invalid")
    if (
        not round_trip.same_base_quantity_reconciled
        or not round_trip.entry_exit_snapshots_distinct
        or round_trip.spread_added_separately
        or not round_trip.entry.visible_depth_complete
        or not round_trip.exit.visible_depth_complete
        or round_trip.entry.base_quantity != round_trip.base_quantity
        or round_trip.exit.base_quantity != round_trip.base_quantity
        or round_trip.entry.request_lineage_id == round_trip.exit.request_lineage_id
    ):
        raise BybitExecutionLatencyError("round_trip_identity_invalid")
    expected_actions = (
        ("buy", "sell")
        if round_trip.position_side == "long"
        else ("sell", "buy")
    )
    if (round_trip.entry.action, round_trip.exit.action) != expected_actions:
        raise BybitExecutionLatencyError("round_trip_action_identity_invalid")
    return round_trip


def _reference_projection(
    value: object,
    *,
    role: str,
    round_trip: BybitVisibleBookRoundTrip,
) -> tuple[BybitDecisionBookReferenceInput, BybitDecisionBookReference]:
    if not isinstance(value, BybitDecisionBookReferenceInput):
        raise BybitExecutionLatencyError(f"{role}_reference_type_invalid")
    if value.instrument_id != round_trip.instrument_id:
        raise BybitExecutionLatencyError(f"{role}_reference_instrument_mismatch")
    bid = _decimal_text(value.best_bid, f"{role}_reference_best_bid")
    ask = _decimal_text(value.best_ask, f"{role}_reference_best_ask")
    if bid >= ask:
        raise BybitExecutionLatencyError(f"{role}_reference_book_crossed")
    observed = _utc(value.provider_observed_at, f"{role}_reference_observed_at")
    acquired = _utc(value.acquired_at, f"{role}_reference_acquired_at")
    decision = _utc(value.decision_at, f"{role}_decision_at")
    if not observed <= acquired <= decision:
        raise BybitExecutionLatencyError(f"{role}_reference_timeline_invalid")
    leg = round_trip.entry if role == "entry" else round_trip.exit
    execution_observed = _utc(
        leg.provider_observed_at,
        f"{role}_execution_provider_observed_at",
    )
    execution_acquired = _utc(
        leg.acquired_at,
        f"{role}_execution_acquired_at",
    )
    if not decision < execution_observed <= execution_acquired:
        raise BybitExecutionLatencyError(
            f"{role}_decision_not_before_execution_book"
        )
    source_reference = _source_reference(
        value.source_reference,
        f"{role}_reference_source_reference",
    )
    lineage = _token(
        value.request_lineage_id,
        f"{role}_reference_lineage_id",
    )
    if lineage == leg.request_lineage_id:
        raise BybitExecutionLatencyError(
            f"{role}_reference_reuses_execution_lineage"
        )
    normalized = BybitDecisionBookReferenceInput(
        instrument_id=round_trip.instrument_id,
        best_bid=_canonical(bid),
        best_ask=_canonical(ask),
        provider_observed_at=value.provider_observed_at,
        acquired_at=value.acquired_at,
        decision_at=value.decision_at,
        source_reference=source_reference,
        request_lineage_id=lineage,
    )
    projection = BybitDecisionBookReference(
        snapshot_role=role,
        instrument_id=round_trip.instrument_id,
        best_bid=normalized.best_bid,
        best_ask=normalized.best_ask,
        mid_price=_canonical((bid + ask) / Decimal("2")),
        provider_observed_at=normalized.provider_observed_at,
        acquired_at=normalized.acquired_at,
        decision_at=normalized.decision_at,
        execution_book_provider_observed_at=leg.provider_observed_at,
        execution_book_acquired_at=leg.acquired_at,
        market_drift_window_microseconds=_microseconds(
            execution_observed - observed
        ),
        decision_to_execution_book_observation_microseconds=_microseconds(
            execution_observed - decision
        ),
        decision_to_execution_book_acquisition_microseconds=_microseconds(
            execution_acquired - decision
        ),
        source_status="operator_supplied_unsealed_decision_book",
        source_reference=source_reference,
        request_lineage_id=lineage,
        source_sealed=False,
        matching_engine_timestamp_basis=True,
    )
    return normalized, projection


def model_bybit_decision_price_latency_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    entry_reference: BybitDecisionBookReferenceInput,
    exit_reference: BybitDecisionBookReferenceInput,
) -> BybitDecisionPriceLatencyScenario:
    """Decompose decision-price drift from already-modeled visible-book cost."""

    validated = _validate_round_trip(round_trip)
    entry_input, entry = _reference_projection(
        entry_reference,
        role="entry",
        round_trip=validated,
    )
    exit_input, exit = _reference_projection(
        exit_reference,
        role="exit",
        round_trip=validated,
    )
    if entry_input.request_lineage_id == exit_input.request_lineage_id:
        raise BybitExecutionLatencyError("reference_lineages_not_distinct")
    execution_lineages = {
        validated.entry.request_lineage_id,
        validated.exit.request_lineage_id,
    }
    if {
        entry_input.request_lineage_id,
        exit_input.request_lineage_id,
    } & execution_lineages:
        raise BybitExecutionLatencyError(
            "reference_and_execution_lineages_not_distinct"
        )
    entry_execution_acquired = _utc(
        validated.entry.acquired_at,
        "entry_execution_acquired_at",
    )
    exit_reference_acquired = _utc(
        exit_input.acquired_at,
        "exit_reference_acquired_at",
    )
    if exit_reference_acquired <= entry_execution_acquired:
        raise BybitExecutionLatencyError(
            "exit_reference_not_after_modeled_position_open"
        )

    quantity = _decimal(validated.base_quantity, "base_quantity", positive=True)
    entry_reference_mid = _decimal(
        entry.mid_price,
        "entry_reference_mid_price",
        positive=True,
    )
    exit_reference_mid = _decimal(
        exit.mid_price,
        "exit_reference_mid_price",
        positive=True,
    )
    entry_execution_mid = _decimal(
        validated.entry.mid_price,
        "entry_execution_mid_price",
        positive=True,
    )
    exit_execution_mid = _decimal(
        validated.exit.mid_price,
        "exit_execution_mid_price",
        positive=True,
    )
    if validated.position_side == "long":
        reference_gross = quantity * (exit_reference_mid - entry_reference_mid)
        execution_gross = quantity * (exit_execution_mid - entry_execution_mid)
        entry_latency_cost = quantity * (
            entry_execution_mid - entry_reference_mid
        )
        exit_latency_cost = quantity * (
            exit_reference_mid - exit_execution_mid
        )
    else:
        reference_gross = quantity * (entry_reference_mid - exit_reference_mid)
        execution_gross = quantity * (entry_execution_mid - exit_execution_mid)
        entry_latency_cost = quantity * (
            entry_reference_mid - entry_execution_mid
        )
        exit_latency_cost = quantity * (
            exit_execution_mid - exit_reference_mid
        )
    total_latency_cost = entry_latency_cost + exit_latency_cost
    if not _close(reference_gross - total_latency_cost, execution_gross):
        raise BybitExecutionLatencyError("decision_to_execution_mid_identity_invalid")
    supplied_execution_gross = _decimal(
        validated.gross_mid_mark_return_usdt,
        "gross_mid_mark_return_usdt",
    )
    if not _close(execution_gross, supplied_execution_gross):
        raise BybitExecutionLatencyError("round_trip_gross_return_identity_invalid")
    visible_cost = _decimal(
        validated.total_visible_book_cost_usdt,
        "total_visible_book_cost_usdt",
    )
    net_visible = _decimal(
        validated.net_visible_book_return_usdt,
        "net_visible_book_return_usdt",
    )
    net_from_reference = reference_gross - total_latency_cost - visible_cost
    if visible_cost < 0 or not _close(net_from_reference, net_visible):
        raise BybitExecutionLatencyError(
            "decision_reference_to_visible_book_identity_invalid"
        )
    entry_reference_notional = quantity * entry_reference_mid

    return BybitDecisionPriceLatencyScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=validated.schema_version,
        venue_id=validated.venue_id,
        execution_mode=validated.execution_mode,
        instrument_id=validated.instrument_id,
        canonical_asset_id=validated.canonical_asset_id,
        base_asset=validated.base_asset,
        quote_asset=validated.quote_asset,
        position_side=validated.position_side,
        base_quantity=validated.base_quantity,
        entry_reference=entry_input,
        exit_reference=exit_input,
        entry_reference_projection=entry,
        exit_reference_projection=exit,
        round_trip=validated,
        decision_reference_identity_reconciled=True,
        reference_lineages_distinct=True,
        reference_and_execution_lineages_distinct=True,
        reference_timeline_reconciled=True,
        entry_decision_mid_price_usdt=_canonical(entry_reference_mid),
        entry_execution_mid_price_usdt=_canonical(entry_execution_mid),
        exit_decision_mid_price_usdt=_canonical(exit_reference_mid),
        exit_execution_mid_price_usdt=_canonical(exit_execution_mid),
        entry_reference_mid_notional_usdt=_float(entry_reference_notional),
        decision_reference_gross_return_usdt=_float(reference_gross),
        execution_book_gross_mid_mark_return_usdt=_float(execution_gross),
        entry_latency_cost_usdt=_float(entry_latency_cost),
        exit_latency_cost_usdt=_float(exit_latency_cost),
        total_latency_cost_usdt=_float(total_latency_cost),
        total_latency_cashflow_usdt=_float(-total_latency_cost),
        total_latency_cost_bps_of_entry_reference_notional=_float(
            total_latency_cost / entry_reference_notional * Decimal("10000")
        ),
        total_visible_book_cost_usdt=_float(visible_cost),
        net_visible_book_return_usdt=_float(net_visible),
        net_from_decision_reference_after_latency_and_visible_book_usdt=(
            _float(net_from_reference)
        ),
        decision_reference_to_execution_mid_identity_reconciled=True,
        decision_reference_to_visible_book_identity_reconciled=True,
        latency_cost_sign_convention=(
            "positive_adverse_negative_favorable_relative_to_decision_mid"
        ),
        latency_measurement_basis=(
            "supplied_decision_book_mid_to_later_matching_engine_book_mid"
        ),
        cost_benchmark="decision_book_mid_price",
        arithmetic_exact_for_supplied_inputs=True,
        latency_reference_set_complete_for_supplied_scenario=True,
        actual_order_submission_observed=False,
        actual_fill_observed=False,
        realized_execution_latency_observed=False,
        decision_reference_sources_sealed=False,
        latency_cost_policy_sealed=False,
        fees_included=False,
        funding_included=False,
        spread_added_separately=False,
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
    "OFFICIAL_ORDERBOOK_URL",
    "BybitDecisionBookReference",
    "BybitDecisionBookReferenceInput",
    "BybitDecisionPriceLatencyScenario",
    "BybitExecutionLatencyError",
    "model_bybit_decision_price_latency_scenario",
)
