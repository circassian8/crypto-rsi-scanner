"""Pure funding-settlement projection for a modeled Bybit round trip.

Bybit USDT perpetual funding is a transfer between long and short positions at
the funding timestamp.  This module applies one caller-supplied settled rate
and settlement mark price to the exact base quantity already carried by the
visible-book round-trip model.

The arithmetic is exact for the supplied decimal inputs.  The inputs remain an
unsealed research scenario: this module does not obtain a settlement mark,
prove that every funding event in a holding interval is present, call Bybit,
read credentials, write artifacts, or bind the Protocol-v2 cost annex.
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


SCHEMA_VERSION = "crypto_radar.bybit_funding_settlement_scenario.v1"
OFFICIAL_FUNDING_HISTORY_URL = (
    "https://bybit-exchange.github.io/docs/v5/market/history-fund-rate"
)
OFFICIAL_MARK_PRICE_KLINE_URL = (
    "https://bybit-exchange.github.io/docs/v5/market/mark-kline"
)
OFFICIAL_FUNDING_FEE_URL = (
    "https://www.bybit.com/en/help-center/article/"
    "Funding-fee-calculation/%3Fcategory%3Dcd60af6303161fd598"
)
MAX_ABSOLUTE_FUNDING_RATE_FRACTION = Decimal("0.1")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESEARCH_REFERENCE_RE = re.compile(
    r"^research-assumption:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class BybitExecutionFundingError(ValueError):
    """Raised when a funding scenario is incomplete or inconsistent."""


@dataclass(frozen=True)
class _BybitFundingSettlementScenario:
    """One unsealed settlement transfer applied to a modeled position."""

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
    modeled_position_opened_at: str
    modeled_position_closed_at: str
    funding_settled_at: str
    funding_rate_unit: str
    funding_rate_fraction: str
    funding_rate_percent_points: float
    settlement_mark_price_usdt: str
    position_value_at_settlement_usdt: float
    funding_formula: str
    funding_formula_source_url: str
    funding_direction: str
    payer_side: str
    receiver_side: str
    position_cashflow_sign_convention: str
    position_funding_cashflow_usdt: float
    position_funding_cost_usdt: float
    position_funding_cost_bps_of_entry_mid_notional: float
    gross_mid_mark_return_usdt: float
    net_visible_book_return_usdt: float
    net_after_visible_book_and_funding_usdt: float
    total_visible_book_cost_usdt: float
    total_visible_book_and_funding_cost_usdt: float
    assumption_id: str
    funding_rate_source_status: str
    funding_rate_source_reference: str
    funding_rate_source_observed_at: str
    funding_rate_lineage_id: str
    settlement_mark_source_status: str
    settlement_mark_source_reference: str
    settlement_mark_source_observed_at: str
    settlement_mark_lineage_id: str
    arithmetic_exact_for_supplied_inputs: bool
    funding_event_count: int
    holding_interval_funding_coverage_complete: bool
    settlement_mark_source_sealed: bool
    funding_rate_source_sealed: bool
    fees_included: bool
    spread_added_separately: bool
    latency_cost_included: bool
    beyond_visible_book_slippage_included: bool
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


BybitFundingSettlementScenario = _BybitFundingSettlementScenario


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BybitExecutionFundingError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionFundingError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionFundingError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _decimal_text(
    value: object,
    field: str,
    *,
    positive: bool = False,
    maximum_abs: Decimal | None = None,
) -> Decimal:
    if not isinstance(value, str):
        raise BybitExecutionFundingError(f"{field}_must_be_decimal_text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise BybitExecutionFundingError(
            f"{field}_must_be_decimal_text"
        ) from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionFundingError(f"{field}_invalid")
    if maximum_abs is not None and abs(parsed) > maximum_abs:
        raise BybitExecutionFundingError(f"{field}_outside_plausible_bounds")
    return parsed


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionFundingError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionFundingError(f"{field}_invalid") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionFundingError(f"{field}_invalid")
    return parsed


def _canonical(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionFundingError("calculated_value_non_finite")
    return round(parsed, 12)


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise BybitExecutionFundingError(f"{field}_invalid")
    return value


def _source_reference(value: object, field: str, official_url: str) -> str:
    if not isinstance(value, str) or not value:
        raise BybitExecutionFundingError(f"{field}_invalid")
    if value == official_url or _RESEARCH_REFERENCE_RE.fullmatch(value):
        return value
    raise BybitExecutionFundingError(f"{field}_invalid")


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def _validate_round_trip(round_trip: object) -> BybitVisibleBookRoundTrip:
    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionFundingError("round_trip_type_invalid")
    if (
        round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION
        or round_trip.venue_id != "bybit"
        or round_trip.execution_mode != "perpetual"
        or round_trip.quote_asset != "USDT"
        or round_trip.realized_execution
        or round_trip.fees_included
        or round_trip.funding_included
        or not round_trip.research_only
    ):
        raise BybitExecutionFundingError("round_trip_contract_invalid")
    if (
        not round_trip.same_base_quantity_reconciled
        or not round_trip.entry_exit_snapshots_distinct
        or round_trip.spread_added_separately
        or not round_trip.entry.visible_depth_complete
        or not round_trip.exit.visible_depth_complete
        or round_trip.entry.base_quantity != round_trip.base_quantity
        or round_trip.exit.base_quantity != round_trip.base_quantity
    ):
        raise BybitExecutionFundingError("round_trip_identity_invalid")
    expected_actions = (
        ("buy", "sell")
        if round_trip.position_side == "long"
        else ("sell", "buy")
    )
    if (round_trip.entry.action, round_trip.exit.action) != expected_actions:
        raise BybitExecutionFundingError("round_trip_action_identity_invalid")
    return round_trip


def _funding_direction(rate: Decimal) -> tuple[str, str, str]:
    if rate > 0:
        return "positive_long_pays_short", "long", "short"
    if rate < 0:
        return "negative_short_pays_long", "short", "long"
    return "zero_no_transfer", "none", "none"


def model_bybit_funding_settlement_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    funding_rate_fraction: object,
    settlement_mark_price_usdt: object,
    funding_settled_at: str,
    assumption_id: str,
    funding_rate_source_reference: str,
    funding_rate_source_observed_at: str,
    funding_rate_lineage_id: str,
    settlement_mark_source_reference: str,
    settlement_mark_source_observed_at: str,
    settlement_mark_lineage_id: str,
) -> BybitFundingSettlementScenario:
    """Apply one unsealed funding settlement to a modeled position."""

    source = _validate_round_trip(round_trip)
    rate = _decimal_text(
        funding_rate_fraction,
        "funding_rate_fraction",
        maximum_abs=MAX_ABSOLUTE_FUNDING_RATE_FRACTION,
    )
    mark_price = _decimal_text(
        settlement_mark_price_usdt,
        "settlement_mark_price_usdt",
        positive=True,
    )
    settled_at = _utc(funding_settled_at, "funding_settled_at")
    opened_at = _utc(source.entry.acquired_at, "entry_acquired_at")
    closed_at = _utc(source.exit.acquired_at, "exit_acquired_at")
    if not opened_at < settled_at < closed_at:
        raise BybitExecutionFundingError(
            "funding_settlement_outside_modeled_holding_interval"
        )

    funding_observed = _utc(
        funding_rate_source_observed_at,
        "funding_rate_source_observed_at",
    )
    mark_observed = _utc(
        settlement_mark_source_observed_at,
        "settlement_mark_source_observed_at",
    )
    if funding_observed < settled_at:
        raise BybitExecutionFundingError("funding_rate_source_precedes_settlement")
    if mark_observed < settled_at:
        raise BybitExecutionFundingError("settlement_mark_source_precedes_settlement")

    funding_reference = _source_reference(
        funding_rate_source_reference,
        "funding_rate_source_reference",
        OFFICIAL_FUNDING_HISTORY_URL,
    )
    mark_reference = _source_reference(
        settlement_mark_source_reference,
        "settlement_mark_source_reference",
        OFFICIAL_MARK_PRICE_KLINE_URL,
    )
    base_quantity = _decimal(source.base_quantity, "base_quantity", positive=True)
    entry_mid_notional = _decimal(
        source.entry_mid_notional_usdt,
        "entry_mid_notional_usdt",
        positive=True,
    )
    visible_cost = _decimal(
        source.total_visible_book_cost_usdt,
        "total_visible_book_cost_usdt",
    )
    gross_return = _decimal(
        source.gross_mid_mark_return_usdt,
        "gross_mid_mark_return_usdt",
    )
    net_visible = _decimal(
        source.net_visible_book_return_usdt,
        "net_visible_book_return_usdt",
    )
    if visible_cost < 0 or not _close(gross_return - net_visible, visible_cost):
        raise BybitExecutionFundingError(
            "round_trip_visible_cost_identity_invalid"
        )

    position_value = base_quantity * mark_price
    unsigned_transfer = position_value * abs(rate)
    if rate == 0:
        cashflow = Decimal("0")
    elif source.position_side == "long":
        cashflow = -position_value * rate
    else:
        cashflow = position_value * rate
    funding_cost = -cashflow
    net_after_funding = net_visible + cashflow
    combined_cost = visible_cost + funding_cost
    if not _close(gross_return - net_after_funding, combined_cost):
        raise BybitExecutionFundingError("funding_adjusted_cost_identity_invalid")
    if not _close(abs(cashflow), unsigned_transfer):
        raise BybitExecutionFundingError("funding_cashflow_identity_invalid")

    direction, payer_side, receiver_side = _funding_direction(rate)
    return BybitFundingSettlementScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=source.schema_version,
        venue_id=source.venue_id,
        execution_mode=source.execution_mode,
        instrument_id=source.instrument_id,
        canonical_asset_id=source.canonical_asset_id,
        base_asset=source.base_asset,
        quote_asset=source.quote_asset,
        position_side=source.position_side,
        base_quantity=source.base_quantity,
        modeled_position_opened_at=opened_at.isoformat().replace("+00:00", "Z"),
        modeled_position_closed_at=closed_at.isoformat().replace("+00:00", "Z"),
        funding_settled_at=settled_at.isoformat().replace("+00:00", "Z"),
        funding_rate_unit="fraction",
        funding_rate_fraction=_canonical(rate),
        funding_rate_percent_points=_float(rate * Decimal("100")),
        settlement_mark_price_usdt=_canonical(mark_price),
        position_value_at_settlement_usdt=_float(position_value),
        funding_formula="base_quantity_times_settlement_mark_price_times_rate",
        funding_formula_source_url=OFFICIAL_FUNDING_FEE_URL,
        funding_direction=direction,
        payer_side=payer_side,
        receiver_side=receiver_side,
        position_cashflow_sign_convention="positive_received_negative_paid",
        position_funding_cashflow_usdt=_float(cashflow),
        position_funding_cost_usdt=_float(funding_cost),
        position_funding_cost_bps_of_entry_mid_notional=_float(
            funding_cost / entry_mid_notional * Decimal("10000")
        ),
        gross_mid_mark_return_usdt=_float(gross_return),
        net_visible_book_return_usdt=_float(net_visible),
        net_after_visible_book_and_funding_usdt=_float(net_after_funding),
        total_visible_book_cost_usdt=_float(visible_cost),
        total_visible_book_and_funding_cost_usdt=_float(combined_cost),
        assumption_id=_token(assumption_id, "assumption_id"),
        funding_rate_source_status="operator_supplied_unsealed_scenario",
        funding_rate_source_reference=funding_reference,
        funding_rate_source_observed_at=funding_observed.isoformat().replace(
            "+00:00", "Z"
        ),
        funding_rate_lineage_id=_token(
            funding_rate_lineage_id,
            "funding_rate_lineage_id",
        ),
        settlement_mark_source_status="operator_supplied_unsealed_scenario",
        settlement_mark_source_reference=mark_reference,
        settlement_mark_source_observed_at=mark_observed.isoformat().replace(
            "+00:00", "Z"
        ),
        settlement_mark_lineage_id=_token(
            settlement_mark_lineage_id,
            "settlement_mark_lineage_id",
        ),
        arithmetic_exact_for_supplied_inputs=True,
        funding_event_count=1,
        holding_interval_funding_coverage_complete=False,
        settlement_mark_source_sealed=False,
        funding_rate_source_sealed=False,
        fees_included=False,
        spread_added_separately=False,
        latency_cost_included=False,
        beyond_visible_book_slippage_included=False,
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
    "MAX_ABSOLUTE_FUNDING_RATE_FRACTION",
    "OFFICIAL_FUNDING_FEE_URL",
    "OFFICIAL_FUNDING_HISTORY_URL",
    "OFFICIAL_MARK_PRICE_KLINE_URL",
    "SCHEMA_VERSION",
    "BybitExecutionFundingError",
    "BybitFundingSettlementScenario",
    "model_bybit_funding_settlement_scenario",
)
