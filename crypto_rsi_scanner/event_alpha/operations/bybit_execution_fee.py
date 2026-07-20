"""Pure taker-fee projection for one modeled Bybit visible-book round trip.

The existing round-trip primitive models an immediate walk through two public
books.  Bybit classifies any immediately executing order as a taker, including
an immediately marketable limit order.  This module applies caller-supplied
fractional taker-fee assumptions to the exact executed quote value of each leg.

It deliberately does not select fee rates, read private account data, call a
provider, write an artifact, model maker fills, or seal the Protocol-v2 cost
annex.
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


SCHEMA_VERSION = "crypto_radar.bybit_visible_book_taker_fee_scenario.v1"
OFFICIAL_FEE_STRUCTURE_URL = (
    "https://www.bybit.com/en/help-center/article/Trading-Fee-Structure"
)
OFFICIAL_MAKER_TAKER_URL = (
    "https://www.bybit.com/en/help-center/article/"
    "Comparison-Between-Maker-Orders-and-Taker-Orders"
)
MAX_PLAUSIBLE_FEE_RATE_FRACTION = Decimal("0.01")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESEARCH_REFERENCE_RE = re.compile(
    r"^research-assumption:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class BybitExecutionFeeError(ValueError):
    """Raised when a fee scenario is incomplete, ambiguous, or inconsistent."""


@dataclass(frozen=True)
class _BybitVisibleBookTakerFeeScenario:
    """One unsealed fee scenario applied to an exact visible-book round trip."""

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
    fee_liquidity_role: str
    immediately_marketable_book_walk: bool
    marketable_limit_immediate_fill_is_taker: bool
    maker_liquidity_modeled: bool
    maker_taker_semantics_source_url: str
    fee_rate_unit: str
    entry_fee_rate_fraction: str
    exit_fee_rate_fraction: str
    entry_fee_rate_bps: float
    exit_fee_rate_bps: float
    entry_executed_quote_value_usdt: float
    exit_executed_quote_value_usdt: float
    entry_trading_fee_usdt: float
    exit_trading_fee_usdt: float
    total_trading_fee_usdt: float
    gross_mid_mark_return_usdt: float
    net_visible_book_return_usdt: float
    net_after_visible_book_and_fees_usdt: float
    total_visible_book_cost_usdt: float
    total_visible_book_and_fee_cost_usdt: float
    total_trading_fee_bps_of_entry_mid_notional: float
    total_visible_book_and_fee_cost_bps_of_entry_mid_notional: float
    assumption_id: str
    fee_rate_source_status: str
    fee_rate_source_reference: str
    fee_rate_source_observed_at: str
    fee_rate_effective_from: str
    fee_rate_effective_until: str
    fee_rate_lineage_id: str
    account_specific_fee_rate: bool
    fee_rate_source_sealed: bool
    spread_added_separately: bool
    funding_included: bool
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


BybitVisibleBookTakerFeeScenario = _BybitVisibleBookTakerFeeScenario


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BybitExecutionFeeError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionFeeError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionFeeError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _rate(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise BybitExecutionFeeError(f"{field}_must_be_decimal_text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise BybitExecutionFeeError(f"{field}_must_be_decimal_text") from exc
    if (
        not parsed.is_finite()
        or parsed < 0
        or parsed > MAX_PLAUSIBLE_FEE_RATE_FRACTION
    ):
        raise BybitExecutionFeeError(
            f"{field}_outside_plausible_fraction_bounds"
        )
    return parsed


def _positive_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionFeeError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionFeeError(f"{field}_invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise BybitExecutionFeeError(f"{field}_invalid")
    return parsed


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionFeeError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitExecutionFeeError(f"{field}_invalid") from exc
    if not parsed.is_finite():
        raise BybitExecutionFeeError(f"{field}_invalid")
    return parsed


def _canonical(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _float(value: Decimal) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitExecutionFeeError("calculated_value_non_finite")
    return round(parsed, 12)


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise BybitExecutionFeeError(f"{field}_invalid")
    return value


def _source_reference(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise BybitExecutionFeeError("fee_rate_source_reference_invalid")
    if value == OFFICIAL_FEE_STRUCTURE_URL or _RESEARCH_REFERENCE_RE.fullmatch(
        value
    ):
        return value
    raise BybitExecutionFeeError("fee_rate_source_reference_invalid")


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")


def model_bybit_visible_book_taker_fee_scenario(
    round_trip: BybitVisibleBookRoundTrip,
    *,
    entry_fee_rate_fraction: object,
    exit_fee_rate_fraction: object,
    assumption_id: str,
    fee_rate_source_reference: str,
    fee_rate_source_observed_at: str,
    fee_rate_effective_from: str,
    fee_rate_effective_until: str,
    fee_rate_lineage_id: str,
) -> BybitVisibleBookTakerFeeScenario:
    """Apply unsealed taker-fee assumptions to each exact executed leg value."""

    if not isinstance(round_trip, BybitVisibleBookRoundTrip):
        raise BybitExecutionFeeError("round_trip_type_invalid")
    if (
        round_trip.schema_version != ROUND_TRIP_SCHEMA_VERSION
        or round_trip.venue_id != "bybit"
        or round_trip.execution_mode != "perpetual"
        or round_trip.quote_asset != "USDT"
        or round_trip.realized_execution
        or round_trip.fees_included
        or not round_trip.research_only
    ):
        raise BybitExecutionFeeError("round_trip_contract_invalid")
    if (
        not round_trip.same_base_quantity_reconciled
        or not round_trip.entry_exit_snapshots_distinct
        or round_trip.spread_added_separately
        or not round_trip.entry.visible_depth_complete
        or not round_trip.exit.visible_depth_complete
        or round_trip.entry.base_quantity != round_trip.base_quantity
        or round_trip.exit.base_quantity != round_trip.base_quantity
    ):
        raise BybitExecutionFeeError("round_trip_identity_invalid")
    expected_actions = (
        ("buy", "sell")
        if round_trip.position_side == "long"
        else ("sell", "buy")
    )
    if (round_trip.entry.action, round_trip.exit.action) != expected_actions:
        raise BybitExecutionFeeError("round_trip_action_identity_invalid")

    entry_rate = _rate(entry_fee_rate_fraction, "entry_fee_rate_fraction")
    exit_rate = _rate(exit_fee_rate_fraction, "exit_fee_rate_fraction")
    source_reference = _source_reference(fee_rate_source_reference)
    observed_at = _utc(
        fee_rate_source_observed_at,
        "fee_rate_source_observed_at",
    )
    effective_from = _utc(fee_rate_effective_from, "fee_rate_effective_from")
    effective_until = _utc(fee_rate_effective_until, "fee_rate_effective_until")
    entry_observed = _utc(
        round_trip.entry.provider_observed_at,
        "entry_provider_observed_at",
    )
    exit_observed = _utc(
        round_trip.exit.provider_observed_at,
        "exit_provider_observed_at",
    )
    if not (effective_from <= entry_observed < exit_observed <= effective_until):
        raise BybitExecutionFeeError("fee_rate_effective_window_incomplete")

    entry_quote = _positive_decimal(
        round_trip.entry.quote_value_usdt,
        "entry_quote_value_usdt",
    )
    exit_quote = _positive_decimal(
        round_trip.exit.quote_value_usdt,
        "exit_quote_value_usdt",
    )
    entry_mid_notional = _positive_decimal(
        round_trip.entry_mid_notional_usdt,
        "entry_mid_notional_usdt",
    )
    visible_cost = _decimal(
        round_trip.total_visible_book_cost_usdt,
        "total_visible_book_cost_usdt",
    )
    gross_return = _decimal(
        round_trip.gross_mid_mark_return_usdt,
        "gross_mid_mark_return_usdt",
    )
    net_visible = _decimal(
        round_trip.net_visible_book_return_usdt,
        "net_visible_book_return_usdt",
    )
    if visible_cost < 0 or not _close(gross_return - net_visible, visible_cost):
        raise BybitExecutionFeeError("round_trip_visible_cost_identity_invalid")

    entry_fee = entry_quote * entry_rate
    exit_fee = exit_quote * exit_rate
    total_fee = entry_fee + exit_fee
    net_after_fees = net_visible - total_fee
    total_cost = visible_cost + total_fee
    if not _close(gross_return - net_after_fees, total_cost):
        raise BybitExecutionFeeError("fee_adjusted_cost_identity_invalid")

    return BybitVisibleBookTakerFeeScenario(
        schema_version=SCHEMA_VERSION,
        source_round_trip_schema_version=round_trip.schema_version,
        venue_id=round_trip.venue_id,
        execution_mode=round_trip.execution_mode,
        instrument_id=round_trip.instrument_id,
        canonical_asset_id=round_trip.canonical_asset_id,
        base_asset=round_trip.base_asset,
        quote_asset=round_trip.quote_asset,
        position_side=round_trip.position_side,
        base_quantity=round_trip.base_quantity,
        fee_liquidity_role="taker",
        immediately_marketable_book_walk=True,
        marketable_limit_immediate_fill_is_taker=True,
        maker_liquidity_modeled=False,
        maker_taker_semantics_source_url=OFFICIAL_MAKER_TAKER_URL,
        fee_rate_unit="fraction",
        entry_fee_rate_fraction=_canonical(entry_rate),
        exit_fee_rate_fraction=_canonical(exit_rate),
        entry_fee_rate_bps=_float(entry_rate * Decimal(10_000)),
        exit_fee_rate_bps=_float(exit_rate * Decimal(10_000)),
        entry_executed_quote_value_usdt=_float(entry_quote),
        exit_executed_quote_value_usdt=_float(exit_quote),
        entry_trading_fee_usdt=_float(entry_fee),
        exit_trading_fee_usdt=_float(exit_fee),
        total_trading_fee_usdt=_float(total_fee),
        gross_mid_mark_return_usdt=_float(gross_return),
        net_visible_book_return_usdt=_float(net_visible),
        net_after_visible_book_and_fees_usdt=_float(net_after_fees),
        total_visible_book_cost_usdt=_float(visible_cost),
        total_visible_book_and_fee_cost_usdt=_float(total_cost),
        total_trading_fee_bps_of_entry_mid_notional=_float(
            total_fee / entry_mid_notional * Decimal(10_000)
        ),
        total_visible_book_and_fee_cost_bps_of_entry_mid_notional=_float(
            total_cost / entry_mid_notional * Decimal(10_000)
        ),
        assumption_id=_token(assumption_id, "assumption_id"),
        fee_rate_source_status=(
            "operator_supplied_unsealed_research_assumption"
        ),
        fee_rate_source_reference=source_reference,
        fee_rate_source_observed_at=observed_at.isoformat().replace(
            "+00:00", "Z"
        ),
        fee_rate_effective_from=effective_from.isoformat().replace(
            "+00:00", "Z"
        ),
        fee_rate_effective_until=effective_until.isoformat().replace(
            "+00:00", "Z"
        ),
        fee_rate_lineage_id=_token(fee_rate_lineage_id, "fee_rate_lineage_id"),
        account_specific_fee_rate=False,
        fee_rate_source_sealed=False,
        spread_added_separately=False,
        funding_included=False,
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
    "MAX_PLAUSIBLE_FEE_RATE_FRACTION",
    "OFFICIAL_FEE_STRUCTURE_URL",
    "OFFICIAL_MAKER_TAKER_URL",
    "SCHEMA_VERSION",
    "BybitExecutionFeeError",
    "BybitVisibleBookTakerFeeScenario",
    "model_bybit_visible_book_taker_fee_scenario",
)
