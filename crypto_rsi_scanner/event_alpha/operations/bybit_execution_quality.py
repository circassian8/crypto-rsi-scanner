"""Offline Bybit USDT-perpetual execution-quality contract and normalizer.

The owner selected Bybit USDT-linear perpetuals as the intended execution
surface for Decision Radar research.  This module implements only the safe
first slice: strict parsing of already-supplied public V5 instrument and order
book payloads, deterministic universe intersection, and a bounded request plan.
It contains no HTTP client, credential handling, private endpoint, or order
operation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


CONTRACT_VERSION = "crypto_radar_bybit_usdt_perpetual_execution_quality_v5"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.bybit_execution_quality.v2"
ROUND_TRIP_SCHEMA_VERSION = "crypto_radar.bybit_visible_book_round_trip.v3"
TARGET_NOTIONAL_SIZING_SCHEMA_VERSION = (
    "crypto_radar.bybit_target_entry_mid_notional_sizing.v1"
)
TARGET_NOTIONAL_ROUND_TRIP_SCHEMA_VERSION = (
    "crypto_radar.bybit_target_notional_visible_book_round_trip.v2"
)
VENUE_ID = "bybit"
EXECUTION_MODE = "perpetual"
BYBIT_CATEGORY = "linear"
QUOTE_ASSET = "USDT"
CONTRACT_TYPE = "LinearPerpetual"
INSTRUMENT_STATUS = "Trading"
MAX_RADAR_ASSETS = 30
INSTRUMENT_CATALOG_LIMIT = 1000
ORDERBOOK_LEVEL_LIMIT = 200
MAX_PLANNED_REQUESTS = MAX_RADAR_ASSETS + 1
REQUEST_STRATEGY = (
    "one_complete_trading_linear_catalog_then_one_orderbook_per_eligible_instrument"
)
DEFAULT_DEPTH_BANDS_BPS = (5, 10, 25, 50)
DEFAULT_NOTIONALS_USDT = (500.0, 2_000.0, 10_000.0)
DEFAULT_FRESHNESS_SECONDS = 15.0
PUBLIC_API_BASE = "https://api.bybit.com"
INSTRUMENTS_PATH = "/v5/market/instruments-info"
ORDERBOOK_PATH = "/v5/market/orderbook"
OFFICIAL_INSTRUMENT_DOC = "https://bybit-exchange.github.io/docs/v5/market/instrument"
OFFICIAL_ORDERBOOK_DOC = "https://bybit-exchange.github.io/docs/v5/market/orderbook"
OFFICIAL_USDT_CONTRACT_ORDER_COST_DOC = (
    "https://www.bybit.com/en/help-center/article/Order-Cost-USDT-Contract"
)

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CANONICAL_ASSET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ASSET_RE = re.compile(r"^[A-Z0-9]{2,24}$")
_INSTRUMENT_RE = re.compile(r"^[A-Z0-9]{4,32}$")


class BybitExecutionQualityError(ValueError):
    """Raised when public payloads violate the sealed offline contract."""


@dataclass(frozen=True)
class _BybitEligibleInstrument:
    """One exact Radar asset to active Bybit USDT-perpetual mapping."""

    canonical_asset_id: str
    radar_symbol: str
    liquidity_rank: int
    instrument_id: str
    base_asset: str
    quote_asset: str
    settle_asset: str
    contract_type: str
    status: str
    tick_size: str
    quantity_step: str
    minimum_order_quantity: str
    maximum_limit_order_quantity: str
    maximum_market_order_quantity: str
    minimum_notional_value_usdt: str
    launch_time_ms: int
    delivery_time_ms: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _BybitPublicRequest:
    """One future public GET request description; it performs no request."""

    method: str
    path: str
    query: tuple[tuple[str, str], ...]
    credentials_required: bool = False
    private_data: bool = False
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "path": self.path,
            "query": dict(self.query),
            "credentials_required": self.credentials_required,
            "private_data": self.private_data,
            "research_only": self.research_only,
        }


@dataclass(frozen=True)
class _BybitPublicRequestPlan:
    """Bounded, non-executable plan for a later separately authorized read."""

    contract_version: str
    venue_id: str
    execution_mode: str
    quote_asset: str
    requests: tuple[BybitPublicRequest, ...]
    provider_call_authorized: bool
    provider_call_planned: bool
    provider_call_attempted: bool
    credentials_required: bool
    order_operations_available: bool
    research_only: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "venue_id": self.venue_id,
            "execution_mode": self.execution_mode,
            "quote_asset": self.quote_asset,
            "requests": [request.to_dict() for request in self.requests],
            "request_count": len(self.requests),
            "provider_call_authorized": self.provider_call_authorized,
            "provider_call_planned": self.provider_call_planned,
            "provider_call_attempted": self.provider_call_attempted,
            "credentials_required": self.credentials_required,
            "order_operations_available": self.order_operations_available,
            "research_only": self.research_only,
        }


@dataclass(frozen=True)
class _BybitExecutionQualitySnapshot:
    """Closed quote-denominated projection of one Bybit order-book snapshot."""

    schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    notional_currency: str
    provider_observed_at: str
    snapshot_generated_at: str
    acquired_at: str
    age_seconds: float
    freshness_status: str
    best_bid: float
    best_ask: float
    mid_price: float
    spread_bps: float
    orderbook_level_limit: int
    liquidity_scope: str
    rpi_orders_included: bool
    bid_depth_usdt_by_band: tuple[tuple[int, float], ...]
    ask_depth_usdt_by_band: tuple[tuple[int, float], ...]
    buy_price_impact_bps_by_notional_usdt: tuple[tuple[float, float | None], ...]
    sell_price_impact_bps_by_notional_usdt: tuple[tuple[float, float | None], ...]
    impact_reference: str
    impact_method: str
    impact_size_definition: str
    order_book_update_id: int
    order_book_cross_sequence: int
    source_url: str
    request_lineage_id: str
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "venue_id": self.venue_id,
            "execution_mode": self.execution_mode,
            "instrument_id": self.instrument_id,
            "canonical_asset_id": self.canonical_asset_id,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "notional_currency": self.notional_currency,
            "provider_observed_at": self.provider_observed_at,
            "snapshot_generated_at": self.snapshot_generated_at,
            "acquired_at": self.acquired_at,
            "age_seconds": self.age_seconds,
            "freshness_status": self.freshness_status,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread_bps": self.spread_bps,
            "orderbook_level_limit": self.orderbook_level_limit,
            "liquidity_scope": self.liquidity_scope,
            "rpi_orders_included": self.rpi_orders_included,
            "bid_depth_usdt_by_band": dict(self.bid_depth_usdt_by_band),
            "ask_depth_usdt_by_band": dict(self.ask_depth_usdt_by_band),
            "buy_price_impact_bps_by_notional_usdt": dict(
                self.buy_price_impact_bps_by_notional_usdt
            ),
            "sell_price_impact_bps_by_notional_usdt": dict(
                self.sell_price_impact_bps_by_notional_usdt
            ),
            "impact_reference": self.impact_reference,
            "impact_method": self.impact_method,
            "impact_size_definition": self.impact_size_definition,
            "order_book_update_id": self.order_book_update_id,
            "order_book_cross_sequence": self.order_book_cross_sequence,
            "source_url": self.source_url,
            "request_lineage_id": self.request_lineage_id,
            "research_only": self.research_only,
        }


@dataclass(frozen=True)
class _BybitVisibleBookLeg:
    """One quantity-complete marketable walk through one supplied public book."""

    snapshot_role: str
    action: str
    provider_observed_at: str
    snapshot_generated_at: str
    acquired_at: str
    request_lineage_id: str
    order_book_update_id: int
    order_book_cross_sequence: int
    mid_price: float
    base_quantity: str
    quote_value_usdt: float
    vwap: float
    mid_reference_notional_usdt: float
    visible_book_cost_usdt: float
    impact_bps_from_mid: float
    visible_depth_complete: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _BybitLegInstrumentConstraints:
    """Dynamic venue order constraints revalidated for one exact book leg."""

    snapshot_role: str
    instrument_id: str
    quantity_step: str
    minimum_order_quantity: str
    maximum_limit_order_quantity: str
    maximum_market_order_quantity: str
    minimum_notional_value_usdt: str
    base_quantity: str
    visible_quote_value_usdt: float
    quantity_aligned_to_step: bool
    quantity_meets_minimum: bool
    visible_quote_value_meets_minimum_notional: bool
    limit_order_quantity_eligible: bool
    market_order_quantity_eligible: bool
    quantity_eligible_order_styles: tuple[str, ...]
    observed_at: str
    lineage_id: str
    causal_to_leg: bool
    maximums_dynamic: bool
    source_url: str

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["quantity_eligible_order_styles"] = list(
            self.quantity_eligible_order_styles
        )
        return value


@dataclass(frozen=True)
class _BybitVisibleBookRoundTrip:
    """Quantity-reconciled long/short entry and exit visible-book projection."""

    schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    position_side: str
    base_quantity: str
    entry_instrument_constraints: _BybitLegInstrumentConstraints
    exit_instrument_constraints: _BybitLegInstrumentConstraints
    instrument_identity_reconciled: bool
    constraint_lineages_distinct: bool
    constraint_snapshots_ordered: bool
    dynamic_constraints_revalidated_per_leg: bool
    constraint_values_changed_between_legs: bool
    quantity_aligned_to_entry_and_exit_steps: bool
    round_trip_quantity_eligible_order_styles: tuple[str, ...]
    order_style_available_on_both_legs: bool
    order_style_selected: bool
    instrument_constraints_freshness_policy_sealed: bool
    instrument_maximums_dynamic: bool
    instrument_constraints_source_url: str
    quantity_unit: str
    quantity_semantics: str
    entry: _BybitVisibleBookLeg
    exit: _BybitVisibleBookLeg
    entry_mid_notional_usdt: float
    gross_mid_mark_return_usdt: float
    net_visible_book_return_usdt: float
    total_visible_book_cost_usdt: float
    total_visible_book_cost_bps_of_entry_mid_notional: float
    same_base_quantity_reconciled: bool
    entry_exit_snapshots_distinct: bool
    spread_added_separately: bool
    realized_execution: bool
    fees_included: bool
    funding_included: bool
    latency_cost_included: bool
    beyond_visible_book_slippage_included: bool
    liquidity_scope: str
    quantity_source_url: str
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["entry"] = self.entry.to_dict()
        value["exit"] = self.exit.to_dict()
        value["entry_instrument_constraints"] = (
            self.entry_instrument_constraints.to_dict()
        )
        value["exit_instrument_constraints"] = (
            self.exit_instrument_constraints.to_dict()
        )
        value["round_trip_quantity_eligible_order_styles"] = list(
            self.round_trip_quantity_eligible_order_styles
        )
        return value


@dataclass(frozen=True)
class _BybitTargetNotionalSizing:
    """One conservative target-mid-notional to venue quantity projection."""

    schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    target_entry_mid_notional_usdt: str
    entry_mid_price: float
    sized_base_quantity: str
    sized_entry_mid_notional_usdt: str
    notional_shortfall_usdt: str
    notional_shortfall_bps: float
    one_quantity_step_mid_notional_usdt: str
    rounding_mode: str
    does_not_exceed_target: bool
    shortfall_less_than_one_quantity_step_notional: bool
    quantity_step: str
    minimum_order_quantity: str
    maximum_limit_order_quantity: str
    maximum_market_order_quantity: str
    minimum_notional_value_usdt: str
    sized_mid_notional_meets_minimum: bool
    limit_order_quantity_eligible: bool
    market_order_quantity_eligible: bool
    quantity_eligible_order_styles: tuple[str, ...]
    order_style_selected: bool
    entry_provider_observed_at: str
    entry_snapshot_generated_at: str
    entry_acquired_at: str
    entry_request_lineage_id: str
    instrument_constraints_observed_at: str
    instrument_constraints_lineage_id: str
    instrument_constraints_causal_to_entry: bool
    instrument_constraints_freshness_policy_sealed: bool
    instrument_maximums_dynamic: bool
    target_notional_tier_set_sealed: bool
    base_quantity_selection_policy_sealed: bool
    target_is_reference_mid_notional_not_quote_budget: bool
    marketable_quote_value_may_exceed_target_due_spread_and_impact: bool
    realized_execution: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["quantity_eligible_order_styles"] = list(
            self.quantity_eligible_order_styles
        )
        return value


@dataclass(frozen=True)
class _BybitTargetNotionalRoundTrip:
    """One target-notional sizing projection joined to its exact round trip."""

    schema_version: str
    sizing: _BybitTargetNotionalSizing
    round_trip: _BybitVisibleBookRoundTrip
    sizing_and_round_trip_identity_reconciled: bool
    same_entry_book_reconciled: bool
    same_base_quantity_reconciled: bool
    target_notional_tier_set_sealed: bool
    base_quantity_selection_policy_sealed: bool
    order_style_selected: bool
    realized_execution: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sizing": self.sizing.to_dict(),
            "round_trip": self.round_trip.to_dict(),
            "sizing_and_round_trip_identity_reconciled": (
                self.sizing_and_round_trip_identity_reconciled
            ),
            "same_entry_book_reconciled": self.same_entry_book_reconciled,
            "same_base_quantity_reconciled": self.same_base_quantity_reconciled,
            "target_notional_tier_set_sealed": self.target_notional_tier_set_sealed,
            "base_quantity_selection_policy_sealed": (
                self.base_quantity_selection_policy_sealed
            ),
            "order_style_selected": self.order_style_selected,
            "realized_execution": self.realized_execution,
            "research_only": self.research_only,
        }


# Stable public names expose a closed model bundle without declaring multiple
# public ownership classes in this behavior module.
BybitEligibleInstrument = _BybitEligibleInstrument
BybitPublicRequest = _BybitPublicRequest
BybitPublicRequestPlan = _BybitPublicRequestPlan
BybitExecutionQualitySnapshot = _BybitExecutionQualitySnapshot
BybitVisibleBookLeg = _BybitVisibleBookLeg
BybitLegInstrumentConstraints = _BybitLegInstrumentConstraints
BybitVisibleBookRoundTrip = _BybitVisibleBookRoundTrip
BybitTargetNotionalSizing = _BybitTargetNotionalSizing
BybitTargetNotionalRoundTrip = _BybitTargetNotionalRoundTrip


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BybitExecutionQualityError(f"{label}_must_be_an_object")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise BybitExecutionQualityError(f"{label}_must_be_an_array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BybitExecutionQualityError(f"{label}_must_be_nonempty_text")
    return value.strip()


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise BybitExecutionQualityError(f"{label}_must_be_an_integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BybitExecutionQualityError(f"{label}_must_be_an_integer") from exc
    if str(value).strip() != str(parsed) and not isinstance(value, int):
        raise BybitExecutionQualityError(f"{label}_must_be_an_integer")
    if parsed < minimum:
        raise BybitExecutionQualityError(f"{label}_below_minimum")
    return parsed


def _decimal(value: object, label: str, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool):
        raise BybitExecutionQualityError(f"{label}_must_be_decimal_text")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitExecutionQualityError(f"{label}_must_be_decimal_text") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise BybitExecutionQualityError(f"{label}_must_be_positive_and_finite")
    return parsed


def _utc_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionQualityError(f"{label}_must_be_iso8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionQualityError(f"{label}_must_include_timezone")
    return parsed.astimezone(timezone.utc)


def _iso_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _float(value: Decimal) -> float:
    return round(float(value), 12)


def bybit_base_symbol_requestable(value: object) -> bool:
    """Return whether a Radar symbol can form one exact Bybit base contract ID."""

    return isinstance(value, str) and bool(_ASSET_RE.fullmatch(value.strip().upper()))


def bybit_eligible_instrument_from_values(
    value: object,
) -> BybitEligibleInstrument:
    """Validate one persisted venue instrument without coercing evidence types."""

    expected = {
        "base_asset",
        "canonical_asset_id",
        "contract_type",
        "delivery_time_ms",
        "instrument_id",
        "launch_time_ms",
        "liquidity_rank",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
        "minimum_order_quantity",
        "quantity_step",
        "quote_asset",
        "radar_symbol",
        "settle_asset",
        "status",
        "tick_size",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise BybitExecutionQualityError("eligible_instrument_schema_invalid")
    text_fields = (
        "canonical_asset_id",
        "radar_symbol",
        "instrument_id",
        "base_asset",
        "quote_asset",
        "settle_asset",
        "contract_type",
        "status",
        "tick_size",
        "quantity_step",
        "minimum_order_quantity",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
    )
    if any(
        not isinstance(value.get(field), str)
        or value.get(field) != str(value.get(field)).strip()
        or not value.get(field)
        for field in text_fields
    ):
        raise BybitExecutionQualityError("eligible_instrument_text_invalid")
    if (
        type(value.get("liquidity_rank")) is not int
        or type(value.get("launch_time_ms")) is not int
        or type(value.get("delivery_time_ms")) is not int
    ):
        raise BybitExecutionQualityError("eligible_instrument_integer_invalid")

    instrument = BybitEligibleInstrument(
        canonical_asset_id=value["canonical_asset_id"],
        radar_symbol=value["radar_symbol"],
        liquidity_rank=value["liquidity_rank"],
        instrument_id=value["instrument_id"],
        base_asset=value["base_asset"],
        quote_asset=value["quote_asset"],
        settle_asset=value["settle_asset"],
        contract_type=value["contract_type"],
        status=value["status"],
        tick_size=value["tick_size"],
        quantity_step=value["quantity_step"],
        minimum_order_quantity=value["minimum_order_quantity"],
        maximum_limit_order_quantity=value["maximum_limit_order_quantity"],
        maximum_market_order_quantity=value["maximum_market_order_quantity"],
        minimum_notional_value_usdt=value["minimum_notional_value_usdt"],
        launch_time_ms=value["launch_time_ms"],
        delivery_time_ms=value["delivery_time_ms"],
    )
    if (
        not _CANONICAL_ASSET_RE.fullmatch(instrument.canonical_asset_id)
        or not _ASSET_RE.fullmatch(instrument.radar_symbol)
        or not _ASSET_RE.fullmatch(instrument.base_asset)
        or not _INSTRUMENT_RE.fullmatch(instrument.instrument_id)
        or instrument.radar_symbol != instrument.base_asset
        or instrument.instrument_id != f"{instrument.base_asset}{QUOTE_ASSET}"
        or instrument.quote_asset != QUOTE_ASSET
        or instrument.settle_asset != QUOTE_ASSET
        or instrument.contract_type != CONTRACT_TYPE
        or instrument.status != INSTRUMENT_STATUS
        or not 1 <= instrument.liquidity_rank <= MAX_RADAR_ASSETS
        or instrument.launch_time_ms < 0
        or instrument.delivery_time_ms < 0
    ):
        raise BybitExecutionQualityError("eligible_instrument_contract_invalid")
    decimal_fields = (
        "tick_size",
        "quantity_step",
        "minimum_order_quantity",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
    )
    for field in decimal_fields:
        parsed = _decimal(getattr(instrument, field), field)
        if _canonical_decimal_text(parsed) != getattr(instrument, field):
            raise BybitExecutionQualityError(
                "eligible_instrument_decimal_not_canonical"
            )
    _instrument_order_constraints(instrument)
    return instrument


def select_bybit_usdt_perpetual_instruments(
    radar_assets: Sequence[Mapping[str, object]],
    payload: Mapping[str, object],
) -> tuple[BybitEligibleInstrument, ...]:
    """Intersect at most 30 exact Radar symbols with active USDT perps.

    `radar_assets` must already be the point-in-time, liquidity-ranked Radar
    universe.  This function does not rank assets, guess multiplier contracts,
    or silently accept a paginated partial instrument response.
    """

    if not radar_assets:
        raise BybitExecutionQualityError("radar_asset_universe_empty")
    if len(radar_assets) > MAX_RADAR_ASSETS:
        raise BybitExecutionQualityError("radar_asset_universe_exceeds_30")

    radar_by_symbol: dict[str, tuple[str, int]] = {}
    canonical_ids: set[str] = set()
    ranks: set[int] = set()
    for index, raw in enumerate(radar_assets):
        row = _mapping(raw, f"radar_asset_{index}")
        canonical_id = _text(row.get("canonical_asset_id"), "canonical_asset_id")
        if not _CANONICAL_ASSET_RE.fullmatch(canonical_id):
            raise BybitExecutionQualityError("canonical_asset_id_invalid")
        symbol = _text(row.get("symbol"), "radar_symbol").upper()
        rank = _integer(row.get("liquidity_rank"), "liquidity_rank", minimum=1)
        if rank > MAX_RADAR_ASSETS:
            raise BybitExecutionQualityError("liquidity_rank_exceeds_30")
        if not _ASSET_RE.fullmatch(symbol):
            raise BybitExecutionQualityError("radar_symbol_invalid")
        if canonical_id in canonical_ids or rank in ranks or symbol in radar_by_symbol:
            raise BybitExecutionQualityError("radar_asset_identity_not_unique")
        canonical_ids.add(canonical_id)
        ranks.add(rank)
        radar_by_symbol[symbol] = (canonical_id, rank)

    if isinstance(payload.get("retCode"), bool) or payload.get("retCode") != 0:
        raise BybitExecutionQualityError("bybit_instruments_response_not_ok")
    result = _mapping(payload.get("result"), "bybit_instruments_result")
    if result.get("category") != BYBIT_CATEGORY:
        raise BybitExecutionQualityError("bybit_instruments_category_not_linear")
    cursor = result.get("nextPageCursor")
    if cursor != "":
        raise BybitExecutionQualityError("bybit_instruments_page_incomplete")
    rows = _sequence(result.get("list"), "bybit_instruments_list")

    selected_by_base: dict[str, BybitEligibleInstrument] = {}
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"bybit_instrument_{index}")
        base = _text(row.get("baseCoin"), "baseCoin").upper()
        if base not in radar_by_symbol:
            continue
        if (
            row.get("contractType") != CONTRACT_TYPE
            or row.get("status") != INSTRUMENT_STATUS
            or row.get("quoteCoin") != QUOTE_ASSET
            or row.get("settleCoin") != QUOTE_ASSET
            or row.get("isPreListing") is not False
        ):
            continue
        instrument_id = _text(row.get("symbol"), "instrument_symbol").upper()
        if not _INSTRUMENT_RE.fullmatch(instrument_id):
            raise BybitExecutionQualityError("instrument_symbol_invalid")
        if instrument_id != f"{base}{QUOTE_ASSET}":
            raise BybitExecutionQualityError("instrument_identity_not_exact_base_quote")
        price_filter = _mapping(row.get("priceFilter"), "priceFilter")
        lot_filter = _mapping(row.get("lotSizeFilter"), "lotSizeFilter")
        tick = _decimal(price_filter.get("tickSize"), "tickSize")
        quantity_step = _decimal(lot_filter.get("qtyStep"), "qtyStep")
        minimum_order_quantity = _decimal(
            lot_filter.get("minOrderQty"), "minOrderQty"
        )
        maximum_limit_order_quantity = _decimal(
            lot_filter.get("maxOrderQty"), "maxOrderQty"
        )
        maximum_market_order_quantity = _decimal(
            lot_filter.get("maxMktOrderQty"), "maxMktOrderQty"
        )
        minimum_notional_value_usdt = _decimal(
            lot_filter.get("minNotionalValue"), "minNotionalValue"
        )
        if any(
            value % quantity_step != 0
            for value in (
                minimum_order_quantity,
                maximum_limit_order_quantity,
                maximum_market_order_quantity,
            )
        ):
            raise BybitExecutionQualityError(
                "instrument_quantity_constraints_not_aligned_to_quantity_step"
            )
        if (
            minimum_order_quantity > maximum_limit_order_quantity
            or minimum_order_quantity > maximum_market_order_quantity
        ):
            raise BybitExecutionQualityError(
                "instrument_quantity_constraints_inconsistent"
            )
        canonical_id, rank = radar_by_symbol[base]
        selected = BybitEligibleInstrument(
            canonical_asset_id=canonical_id,
            radar_symbol=base,
            liquidity_rank=rank,
            instrument_id=instrument_id,
            base_asset=base,
            quote_asset=QUOTE_ASSET,
            settle_asset=QUOTE_ASSET,
            contract_type=CONTRACT_TYPE,
            status=INSTRUMENT_STATUS,
            tick_size=_canonical_decimal_text(tick),
            quantity_step=_canonical_decimal_text(quantity_step),
            minimum_order_quantity=_canonical_decimal_text(
                minimum_order_quantity
            ),
            maximum_limit_order_quantity=_canonical_decimal_text(
                maximum_limit_order_quantity
            ),
            maximum_market_order_quantity=_canonical_decimal_text(
                maximum_market_order_quantity
            ),
            minimum_notional_value_usdt=_canonical_decimal_text(
                minimum_notional_value_usdt
            ),
            launch_time_ms=_integer(row.get("launchTime"), "launchTime"),
            delivery_time_ms=_integer(row.get("deliveryTime"), "deliveryTime"),
        )
        if base in selected_by_base:
            raise BybitExecutionQualityError("bybit_instrument_mapping_ambiguous")
        selected_by_base[base] = selected

    return tuple(
        sorted(selected_by_base.values(), key=lambda row: (row.liquidity_rank, row.instrument_id))
    )


def build_bybit_instrument_catalog_request() -> BybitPublicRequest:
    """Build the one complete active-linear catalog request used by capture v5."""

    return BybitPublicRequest(
        method="GET",
        path=INSTRUMENTS_PATH,
        query=(
            ("category", BYBIT_CATEGORY),
            ("status", INSTRUMENT_STATUS),
            ("limit", str(INSTRUMENT_CATALOG_LIMIT)),
        ),
    )


def build_bybit_orderbook_request(
    instrument: BybitEligibleInstrument,
) -> BybitPublicRequest:
    """Build one exact 200-level public order-book request."""

    if type(instrument) is not BybitEligibleInstrument:
        raise BybitExecutionQualityError("eligible_instrument_schema_invalid")
    instrument = bybit_eligible_instrument_from_values(instrument.to_dict())
    return BybitPublicRequest(
        method="GET",
        path=ORDERBOOK_PATH,
        query=(
            ("category", BYBIT_CATEGORY),
            ("symbol", instrument.instrument_id),
            ("limit", str(ORDERBOOK_LEVEL_LIMIT)),
        ),
    )


def build_bybit_public_request_plan(
    instruments: Sequence[BybitEligibleInstrument],
) -> BybitPublicRequestPlan:
    """Build but never execute one catalog plus exact public book GETs."""

    if not instruments:
        raise BybitExecutionQualityError("eligible_instrument_set_empty")
    if len(instruments) > MAX_RADAR_ASSETS:
        raise BybitExecutionQualityError("eligible_instrument_set_exceeds_30")
    seen_instruments: set[str] = set()
    seen_assets: set[str] = set()
    seen_bases: set[str] = set()
    seen_ranks: set[int] = set()
    requests: list[BybitPublicRequest] = [build_bybit_instrument_catalog_request()]
    for supplied in instruments:
        if type(supplied) is not BybitEligibleInstrument:
            raise BybitExecutionQualityError("eligible_instrument_schema_invalid")
        instrument = bybit_eligible_instrument_from_values(supplied.to_dict())
        if (
            instrument.instrument_id in seen_instruments
            or instrument.canonical_asset_id in seen_assets
            or instrument.base_asset in seen_bases
            or instrument.liquidity_rank in seen_ranks
        ):
            raise BybitExecutionQualityError("eligible_instrument_identity_not_unique")
        seen_instruments.add(instrument.instrument_id)
        seen_assets.add(instrument.canonical_asset_id)
        seen_bases.add(instrument.base_asset)
        seen_ranks.add(instrument.liquidity_rank)
        requests.append(build_bybit_orderbook_request(instrument))
    if len(requests) > MAX_PLANNED_REQUESTS:
        raise BybitExecutionQualityError("request_plan_exceeds_bound")
    return BybitPublicRequestPlan(
        contract_version=CONTRACT_VERSION,
        venue_id=VENUE_ID,
        execution_mode=EXECUTION_MODE,
        quote_asset=QUOTE_ASSET,
        requests=tuple(requests),
        provider_call_authorized=False,
        provider_call_planned=False,
        provider_call_attempted=False,
        credentials_required=False,
        order_operations_available=False,
        research_only=True,
    )


def _book_levels(value: object, side: str) -> tuple[tuple[Decimal, Decimal], ...]:
    rows = _sequence(value, f"orderbook_{side}")
    if not rows:
        raise BybitExecutionQualityError(f"orderbook_{side}_empty")
    levels: list[tuple[Decimal, Decimal]] = []
    for index, raw in enumerate(rows):
        pair = _sequence(raw, f"orderbook_{side}_{index}")
        if len(pair) != 2:
            raise BybitExecutionQualityError(f"orderbook_{side}_level_shape_invalid")
        levels.append(
            (
                _decimal(pair[0], f"orderbook_{side}_price"),
                _decimal(pair[1], f"orderbook_{side}_quantity"),
            )
        )
    prices = [price for price, _quantity in levels]
    if len(set(prices)) != len(prices):
        raise BybitExecutionQualityError(f"orderbook_{side}_duplicate_price")
    expected = sorted(prices, reverse=side == "bids")
    if prices != expected:
        raise BybitExecutionQualityError(f"orderbook_{side}_sort_invalid")
    return tuple(levels)


def _depth_by_band(
    levels: Sequence[tuple[Decimal, Decimal]],
    *,
    mid: Decimal,
    bands_bps: Sequence[int],
    side: str,
) -> tuple[tuple[int, float], ...]:
    values: list[tuple[int, float]] = []
    for band in bands_bps:
        fraction = Decimal(band) / Decimal(10_000)
        boundary = mid * (Decimal(1) - fraction if side == "bids" else Decimal(1) + fraction)
        depth = sum(
            price * quantity
            for price, quantity in levels
            if (price >= boundary if side == "bids" else price <= boundary)
        )
        values.append((band, _float(depth)))
    return tuple(values)


def _price_impact(
    levels: Sequence[tuple[Decimal, Decimal]],
    *,
    mid: Decimal,
    notionals: Sequence[float],
    side: str,
) -> tuple[tuple[float, float | None], ...]:
    values: list[tuple[float, float | None]] = []
    for raw_notional in notionals:
        notional = _decimal(raw_notional, "notional_usdt")
        remaining = notional
        base_quantity = Decimal(0)
        for price, available_quantity in levels:
            available_quote = price * available_quantity
            consumed_quote = min(remaining, available_quote)
            base_quantity += consumed_quote / price
            remaining -= consumed_quote
            if remaining == 0:
                break
        if remaining > 0 or base_quantity <= 0:
            values.append((float(raw_notional), None))
            continue
        vwap = notional / base_quantity
        impact = (
            (vwap - mid) / mid * Decimal(10_000)
            if side == "asks"
            else (mid - vwap) / mid * Decimal(10_000)
        )
        values.append((float(raw_notional), _float(impact)))
    return tuple(values)


def _canonical_decimal_text(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return "0" if rendered == "-0" else rendered


def _walk_base_quantity(
    levels: Sequence[tuple[Decimal, Decimal]],
    *,
    quantity: Decimal,
    mid: Decimal,
    action: str,
    snapshot_role: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    remaining = quantity
    quote_value = Decimal(0)
    for price, available_quantity in levels:
        consumed_quantity = min(remaining, available_quantity)
        quote_value += consumed_quantity * price
        remaining -= consumed_quantity
        if remaining == 0:
            break
    if remaining > 0:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_visible_depth_insufficient_for_base_quantity"
        )
    vwap = quote_value / quantity
    mid_notional = quantity * mid
    if action == "buy":
        cost = quote_value - mid_notional
        impact = (vwap - mid) / mid * Decimal(10_000)
    elif action == "sell":
        cost = mid_notional - quote_value
        impact = (mid - vwap) / mid * Decimal(10_000)
    else:  # pragma: no cover - internal caller owns the closed action set
        raise BybitExecutionQualityError("visible_book_action_invalid")
    if cost < 0 or impact < 0:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_visible_book_cost_negative"
        )
    return quote_value, vwap, mid_notional, cost


def _visible_book_leg(
    *,
    snapshot: BybitExecutionQualitySnapshot,
    payload: Mapping[str, object],
    quantity: Decimal,
    action: str,
    snapshot_role: str,
) -> tuple[BybitVisibleBookLeg, Decimal, Decimal, Decimal]:
    result = _mapping(payload.get("result"), f"{snapshot_role}_orderbook_result")
    bids = _book_levels(result.get("b"), "bids")
    asks = _book_levels(result.get("a"), "asks")
    mid = (bids[0][0] + asks[0][0]) / Decimal(2)
    if _float(mid) != snapshot.mid_price:
        raise BybitExecutionQualityError(f"{snapshot_role}_mid_price_drift")
    levels = asks if action == "buy" else bids
    quote_value, vwap, mid_notional, cost = _walk_base_quantity(
        levels,
        quantity=quantity,
        mid=mid,
        action=action,
        snapshot_role=snapshot_role,
    )
    impact = cost / mid_notional * Decimal(10_000)
    leg = BybitVisibleBookLeg(
        snapshot_role=snapshot_role,
        action=action,
        provider_observed_at=snapshot.provider_observed_at,
        snapshot_generated_at=snapshot.snapshot_generated_at,
        acquired_at=snapshot.acquired_at,
        request_lineage_id=snapshot.request_lineage_id,
        order_book_update_id=snapshot.order_book_update_id,
        order_book_cross_sequence=snapshot.order_book_cross_sequence,
        mid_price=snapshot.mid_price,
        base_quantity=_canonical_decimal_text(quantity),
        quote_value_usdt=_float(quote_value),
        vwap=_float(vwap),
        mid_reference_notional_usdt=_float(mid_notional),
        visible_book_cost_usdt=_float(cost),
        impact_bps_from_mid=_float(impact),
    )
    return leg, quote_value, mid, cost


def _instrument_order_constraints(
    instrument: BybitEligibleInstrument,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    quantity_step = _decimal(instrument.quantity_step, "quantity_step")
    minimum_order_quantity = _decimal(
        instrument.minimum_order_quantity, "minimum_order_quantity"
    )
    maximum_limit_order_quantity = _decimal(
        instrument.maximum_limit_order_quantity, "maximum_limit_order_quantity"
    )
    maximum_market_order_quantity = _decimal(
        instrument.maximum_market_order_quantity, "maximum_market_order_quantity"
    )
    minimum_notional_value_usdt = _decimal(
        instrument.minimum_notional_value_usdt, "minimum_notional_value_usdt"
    )
    if any(
        value % quantity_step != 0
        for value in (
            minimum_order_quantity,
            maximum_limit_order_quantity,
            maximum_market_order_quantity,
        )
    ):
        raise BybitExecutionQualityError(
            "instrument_quantity_constraints_not_aligned_to_quantity_step"
        )
    if (
        minimum_order_quantity > maximum_limit_order_quantity
        or minimum_order_quantity > maximum_market_order_quantity
    ):
        raise BybitExecutionQualityError(
            "instrument_quantity_constraints_inconsistent"
        )
    return (
        quantity_step,
        minimum_order_quantity,
        maximum_limit_order_quantity,
        maximum_market_order_quantity,
        minimum_notional_value_usdt,
    )


def _venue_instrument_identity(
    instrument: BybitEligibleInstrument,
) -> tuple[object, ...]:
    return (
        instrument.canonical_asset_id,
        instrument.radar_symbol,
        instrument.instrument_id,
        instrument.base_asset,
        instrument.quote_asset,
        instrument.settle_asset,
        instrument.contract_type,
        instrument.status,
        instrument.launch_time_ms,
        instrument.delivery_time_ms,
    )


def _quantity_eligible_order_styles(
    *,
    quantity: Decimal,
    constraints: tuple[Decimal, Decimal, Decimal, Decimal, Decimal],
    snapshot_role: str,
) -> tuple[str, ...]:
    (
        quantity_step,
        minimum_order_quantity,
        maximum_limit_order_quantity,
        maximum_market_order_quantity,
        _minimum_notional_value_usdt,
    ) = constraints
    if quantity % quantity_step != 0:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_base_quantity_not_aligned_to_quantity_step"
        )
    if quantity < minimum_order_quantity:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_base_quantity_below_minimum_order_quantity"
        )
    eligible = tuple(
        style
        for style, maximum in (
            ("market", maximum_market_order_quantity),
            ("marketable_limit", maximum_limit_order_quantity),
        )
        if quantity <= maximum
    )
    if not eligible:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_base_quantity_exceeds_all_order_style_maximums"
        )
    return eligible


def _leg_instrument_constraints(
    *,
    instrument: BybitEligibleInstrument,
    constraints: tuple[Decimal, Decimal, Decimal, Decimal, Decimal],
    quantity: Decimal,
    visible_quote_value: Decimal,
    eligible_order_styles: tuple[str, ...],
    snapshot_role: str,
    observed_at: datetime,
    lineage_id: str,
) -> BybitLegInstrumentConstraints:
    (
        quantity_step,
        minimum_order_quantity,
        maximum_limit_order_quantity,
        maximum_market_order_quantity,
        minimum_notional_value_usdt,
    ) = constraints
    if visible_quote_value < minimum_notional_value_usdt:
        raise BybitExecutionQualityError(
            f"{snapshot_role}_notional_below_instrument_minimum"
        )
    return BybitLegInstrumentConstraints(
        snapshot_role=snapshot_role,
        instrument_id=instrument.instrument_id,
        quantity_step=_canonical_decimal_text(quantity_step),
        minimum_order_quantity=_canonical_decimal_text(minimum_order_quantity),
        maximum_limit_order_quantity=_canonical_decimal_text(
            maximum_limit_order_quantity
        ),
        maximum_market_order_quantity=_canonical_decimal_text(
            maximum_market_order_quantity
        ),
        minimum_notional_value_usdt=_canonical_decimal_text(
            minimum_notional_value_usdt
        ),
        base_quantity=_canonical_decimal_text(quantity),
        visible_quote_value_usdt=_float(visible_quote_value),
        quantity_aligned_to_step=True,
        quantity_meets_minimum=True,
        visible_quote_value_meets_minimum_notional=True,
        limit_order_quantity_eligible=(
            "marketable_limit" in eligible_order_styles
        ),
        market_order_quantity_eligible="market" in eligible_order_styles,
        quantity_eligible_order_styles=eligible_order_styles,
        observed_at=observed_at.isoformat().replace("+00:00", "Z"),
        lineage_id=lineage_id,
        causal_to_leg=True,
        maximums_dynamic=True,
        source_url=OFFICIAL_INSTRUMENT_DOC,
    )


def size_bybit_target_entry_mid_notional(
    entry_payload: Mapping[str, object],
    *,
    instrument: BybitEligibleInstrument,
    target_entry_mid_notional_usdt: object,
    entry_acquired_at: str,
    entry_request_lineage_id: str,
    instrument_constraints_observed_at: str,
    instrument_constraints_lineage_id: str,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> BybitTargetNotionalSizing:
    """Floor one supplied target mid-notional to an exact venue quantity.

    The target is an entry-mid reference for research cost normalization, not a
    maximum quote spend or minimum sale proceeds.  The caller still owns the
    eventual tier set and order-style policy; this projection adopts neither.
    """

    if not _TOKEN_RE.fullmatch(instrument_constraints_lineage_id):
        raise BybitExecutionQualityError(
            "instrument_constraints_lineage_id_invalid"
        )
    target = _decimal(
        target_entry_mid_notional_usdt,
        "target_entry_mid_notional_usdt",
    )
    (
        quantity_step,
        minimum_order_quantity,
        maximum_limit_order_quantity,
        maximum_market_order_quantity,
        minimum_notional_value_usdt,
    ) = _instrument_order_constraints(instrument)
    entry_snapshot = normalize_bybit_orderbook(
        entry_payload,
        instrument=instrument,
        acquired_at=entry_acquired_at,
        request_lineage_id=entry_request_lineage_id,
        freshness_seconds=freshness_seconds,
    )
    if entry_snapshot.freshness_status != "fresh":
        raise BybitExecutionQualityError("target_notional_entry_snapshot_not_fresh")
    entry_observed = _utc_datetime(
        entry_snapshot.provider_observed_at,
        "entry_provider_observed_at",
    )
    constraints_observed = _utc_datetime(
        instrument_constraints_observed_at,
        "instrument_constraints_observed_at",
    )
    if constraints_observed > entry_observed:
        raise BybitExecutionQualityError(
            "instrument_constraints_observed_after_entry"
        )
    result = _mapping(entry_payload.get("result"), "entry_orderbook_result")
    bids = _book_levels(result.get("b"), "bids")
    asks = _book_levels(result.get("a"), "asks")
    entry_mid = (bids[0][0] + asks[0][0]) / Decimal(2)
    if _float(entry_mid) != entry_snapshot.mid_price:
        raise BybitExecutionQualityError("target_notional_entry_mid_price_drift")
    step_count = (target / entry_mid / quantity_step).to_integral_value(
        rounding=ROUND_FLOOR
    )
    quantity = step_count * quantity_step
    if quantity < minimum_order_quantity:
        raise BybitExecutionQualityError(
            "target_notional_rounds_below_minimum_order_quantity"
        )
    limit_order_quantity_eligible = quantity <= maximum_limit_order_quantity
    market_order_quantity_eligible = quantity <= maximum_market_order_quantity
    if not (limit_order_quantity_eligible or market_order_quantity_eligible):
        raise BybitExecutionQualityError(
            "target_notional_quantity_exceeds_all_order_style_maximums"
        )
    sized_mid_notional = quantity * entry_mid
    if sized_mid_notional < minimum_notional_value_usdt:
        raise BybitExecutionQualityError(
            "target_notional_rounds_below_instrument_minimum_notional"
        )
    shortfall = target - sized_mid_notional
    one_step_notional = quantity_step * entry_mid
    if shortfall < 0 or shortfall >= one_step_notional:
        raise BybitExecutionQualityError(
            "target_notional_floor_rounding_identity_mismatch"
        )
    return BybitTargetNotionalSizing(
        schema_version=TARGET_NOTIONAL_SIZING_SCHEMA_VERSION,
        venue_id=VENUE_ID,
        execution_mode=EXECUTION_MODE,
        instrument_id=instrument.instrument_id,
        canonical_asset_id=instrument.canonical_asset_id,
        base_asset=instrument.base_asset,
        quote_asset=instrument.quote_asset,
        target_entry_mid_notional_usdt=_canonical_decimal_text(target),
        entry_mid_price=_float(entry_mid),
        sized_base_quantity=_canonical_decimal_text(quantity),
        sized_entry_mid_notional_usdt=_canonical_decimal_text(
            sized_mid_notional
        ),
        notional_shortfall_usdt=_canonical_decimal_text(shortfall),
        notional_shortfall_bps=_float(shortfall / target * Decimal(10_000)),
        one_quantity_step_mid_notional_usdt=_canonical_decimal_text(
            one_step_notional
        ),
        rounding_mode="floor_to_quantity_step",
        does_not_exceed_target=True,
        shortfall_less_than_one_quantity_step_notional=True,
        quantity_step=_canonical_decimal_text(quantity_step),
        minimum_order_quantity=_canonical_decimal_text(minimum_order_quantity),
        maximum_limit_order_quantity=_canonical_decimal_text(
            maximum_limit_order_quantity
        ),
        maximum_market_order_quantity=_canonical_decimal_text(
            maximum_market_order_quantity
        ),
        minimum_notional_value_usdt=_canonical_decimal_text(
            minimum_notional_value_usdt
        ),
        sized_mid_notional_meets_minimum=True,
        limit_order_quantity_eligible=limit_order_quantity_eligible,
        market_order_quantity_eligible=market_order_quantity_eligible,
        quantity_eligible_order_styles=tuple(
            style
            for style, eligible in (
                ("market", market_order_quantity_eligible),
                ("marketable_limit", limit_order_quantity_eligible),
            )
            if eligible
        ),
        order_style_selected=False,
        entry_provider_observed_at=entry_snapshot.provider_observed_at,
        entry_snapshot_generated_at=entry_snapshot.snapshot_generated_at,
        entry_acquired_at=entry_snapshot.acquired_at,
        entry_request_lineage_id=entry_snapshot.request_lineage_id,
        instrument_constraints_observed_at=(
            constraints_observed.isoformat().replace("+00:00", "Z")
        ),
        instrument_constraints_lineage_id=instrument_constraints_lineage_id,
        instrument_constraints_causal_to_entry=True,
        instrument_constraints_freshness_policy_sealed=False,
        instrument_maximums_dynamic=True,
        target_notional_tier_set_sealed=False,
        base_quantity_selection_policy_sealed=False,
        target_is_reference_mid_notional_not_quote_budget=True,
        marketable_quote_value_may_exceed_target_due_spread_and_impact=True,
        realized_execution=False,
    )


def model_bybit_visible_book_round_trip(
    entry_payload: Mapping[str, object],
    exit_payload: Mapping[str, object],
    *,
    instrument: BybitEligibleInstrument,
    exit_instrument: BybitEligibleInstrument,
    position_side: str,
    base_quantity: object,
    entry_acquired_at: str,
    exit_acquired_at: str,
    entry_request_lineage_id: str,
    exit_request_lineage_id: str,
    entry_instrument_constraints_observed_at: str,
    entry_instrument_constraints_lineage_id: str,
    exit_instrument_constraints_observed_at: str,
    exit_instrument_constraints_lineage_id: str,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> BybitVisibleBookRoundTrip:
    """Model one quantity-identical visible-book round trip without execution.

    This consumes two already-supplied Bybit public snapshots.  It models only
    an immediately marketable walk through the visible REST levels and never
    adds the standalone spread because each side's mid-referenced impact already
    includes its crossing half-spread.  Fees, funding, latency, and liquidity
    beyond the returned book remain deliberately unavailable.
    """

    if position_side not in {"long", "short"}:
        raise BybitExecutionQualityError("position_side_invalid")
    if entry_request_lineage_id == exit_request_lineage_id:
        raise BybitExecutionQualityError("entry_exit_request_lineage_not_distinct")
    if (
        not _TOKEN_RE.fullmatch(entry_instrument_constraints_lineage_id)
        or not _TOKEN_RE.fullmatch(exit_instrument_constraints_lineage_id)
    ):
        raise BybitExecutionQualityError(
            "instrument_constraints_lineage_id_invalid"
        )
    if (
        entry_instrument_constraints_lineage_id
        == exit_instrument_constraints_lineage_id
    ):
        raise BybitExecutionQualityError(
            "entry_exit_instrument_constraints_lineage_not_distinct"
        )
    if _venue_instrument_identity(instrument) != _venue_instrument_identity(
        exit_instrument
    ):
        raise BybitExecutionQualityError("entry_exit_instrument_identity_mismatch")
    quantity = _decimal(base_quantity, "base_quantity")
    entry_constraint_values = _instrument_order_constraints(instrument)
    exit_constraint_values = _instrument_order_constraints(exit_instrument)
    entry_eligible_styles = _quantity_eligible_order_styles(
        quantity=quantity,
        constraints=entry_constraint_values,
        snapshot_role="entry",
    )
    exit_eligible_styles = _quantity_eligible_order_styles(
        quantity=quantity,
        constraints=exit_constraint_values,
        snapshot_role="exit",
    )

    entry_snapshot = normalize_bybit_orderbook(
        entry_payload,
        instrument=instrument,
        acquired_at=entry_acquired_at,
        request_lineage_id=entry_request_lineage_id,
        freshness_seconds=freshness_seconds,
    )
    exit_snapshot = normalize_bybit_orderbook(
        exit_payload,
        instrument=exit_instrument,
        acquired_at=exit_acquired_at,
        request_lineage_id=exit_request_lineage_id,
        freshness_seconds=freshness_seconds,
    )
    if (
        entry_snapshot.freshness_status != "fresh"
        or exit_snapshot.freshness_status != "fresh"
    ):
        raise BybitExecutionQualityError("round_trip_snapshot_not_fresh")
    entry_observed = _utc_datetime(
        entry_snapshot.provider_observed_at, "entry_provider_observed_at"
    )
    exit_observed = _utc_datetime(
        exit_snapshot.provider_observed_at, "exit_provider_observed_at"
    )
    entry_generated = _utc_datetime(
        entry_snapshot.snapshot_generated_at, "entry_snapshot_generated_at"
    )
    exit_generated = _utc_datetime(
        exit_snapshot.snapshot_generated_at, "exit_snapshot_generated_at"
    )
    entry_acquired = _utc_datetime(entry_snapshot.acquired_at, "entry_acquired_at")
    exit_acquired = _utc_datetime(exit_snapshot.acquired_at, "exit_acquired_at")
    entry_constraints_observed = _utc_datetime(
        entry_instrument_constraints_observed_at,
        "entry_instrument_constraints_observed_at",
    )
    exit_constraints_observed = _utc_datetime(
        exit_instrument_constraints_observed_at,
        "exit_instrument_constraints_observed_at",
    )
    if not (
        exit_observed > entry_observed
        and exit_generated > entry_generated
        and exit_acquired > entry_acquired
    ):
        raise BybitExecutionQualityError("entry_exit_snapshot_order_invalid")
    if entry_constraints_observed > entry_observed:
        raise BybitExecutionQualityError(
            "entry_instrument_constraints_observed_after_entry"
        )
    if exit_constraints_observed > exit_observed:
        raise BybitExecutionQualityError(
            "exit_instrument_constraints_observed_after_exit"
        )
    if not (
        exit_constraints_observed > entry_observed
        and exit_constraints_observed > entry_constraints_observed
    ):
        raise BybitExecutionQualityError(
            "exit_instrument_constraints_not_revalidated_after_entry"
        )

    entry_action = "buy" if position_side == "long" else "sell"
    exit_action = "sell" if position_side == "long" else "buy"
    entry, entry_quote, entry_mid, entry_cost = _visible_book_leg(
        snapshot=entry_snapshot,
        payload=entry_payload,
        quantity=quantity,
        action=entry_action,
        snapshot_role="entry",
    )
    exit, exit_quote, exit_mid, exit_cost = _visible_book_leg(
        snapshot=exit_snapshot,
        payload=exit_payload,
        quantity=quantity,
        action=exit_action,
        snapshot_role="exit",
    )
    entry_mid_notional = quantity * entry_mid
    if position_side == "long":
        gross_return = quantity * (exit_mid - entry_mid)
        net_return = exit_quote - entry_quote
    else:
        gross_return = quantity * (entry_mid - exit_mid)
        net_return = entry_quote - exit_quote
    total_cost = entry_cost + exit_cost
    entry_constraints = _leg_instrument_constraints(
        instrument=instrument,
        constraints=entry_constraint_values,
        quantity=quantity,
        visible_quote_value=entry_quote,
        eligible_order_styles=entry_eligible_styles,
        snapshot_role="entry",
        observed_at=entry_constraints_observed,
        lineage_id=entry_instrument_constraints_lineage_id,
    )
    exit_constraints = _leg_instrument_constraints(
        instrument=exit_instrument,
        constraints=exit_constraint_values,
        quantity=quantity,
        visible_quote_value=exit_quote,
        eligible_order_styles=exit_eligible_styles,
        snapshot_role="exit",
        observed_at=exit_constraints_observed,
        lineage_id=exit_instrument_constraints_lineage_id,
    )
    if (gross_return - net_return) != total_cost:
        raise BybitExecutionQualityError("round_trip_cost_identity_mismatch")
    total_cost_bps = total_cost / entry_mid_notional * Decimal(10_000)
    round_trip_eligible_styles = tuple(
        style
        for style in ("market", "marketable_limit")
        if style in entry_eligible_styles and style in exit_eligible_styles
    )
    return BybitVisibleBookRoundTrip(
        schema_version=ROUND_TRIP_SCHEMA_VERSION,
        venue_id=VENUE_ID,
        execution_mode=EXECUTION_MODE,
        instrument_id=instrument.instrument_id,
        canonical_asset_id=instrument.canonical_asset_id,
        base_asset=instrument.base_asset,
        quote_asset=instrument.quote_asset,
        position_side=position_side,
        base_quantity=_canonical_decimal_text(quantity),
        entry_instrument_constraints=entry_constraints,
        exit_instrument_constraints=exit_constraints,
        instrument_identity_reconciled=True,
        constraint_lineages_distinct=True,
        constraint_snapshots_ordered=True,
        dynamic_constraints_revalidated_per_leg=True,
        constraint_values_changed_between_legs=(
            entry_constraint_values != exit_constraint_values
        ),
        quantity_aligned_to_entry_and_exit_steps=True,
        round_trip_quantity_eligible_order_styles=round_trip_eligible_styles,
        order_style_available_on_both_legs=bool(round_trip_eligible_styles),
        order_style_selected=False,
        instrument_constraints_freshness_policy_sealed=False,
        instrument_maximums_dynamic=True,
        instrument_constraints_source_url=OFFICIAL_INSTRUMENT_DOC,
        quantity_unit="base_asset",
        quantity_semantics=(
            "bybit_USDT_linear_contract_quantity_in_underlying_token"
        ),
        entry=entry,
        exit=exit,
        entry_mid_notional_usdt=_float(entry_mid_notional),
        gross_mid_mark_return_usdt=_float(gross_return),
        net_visible_book_return_usdt=_float(net_return),
        total_visible_book_cost_usdt=_float(total_cost),
        total_visible_book_cost_bps_of_entry_mid_notional=_float(total_cost_bps),
        same_base_quantity_reconciled=True,
        entry_exit_snapshots_distinct=True,
        spread_added_separately=False,
        realized_execution=False,
        fees_included=False,
        funding_included=False,
        latency_cost_included=False,
        beyond_visible_book_slippage_included=False,
        liquidity_scope="bybit_public_REST_visible_levels_excluding_RPI",
        quantity_source_url=OFFICIAL_USDT_CONTRACT_ORDER_COST_DOC,
    )


def model_bybit_target_notional_visible_book_round_trip(
    entry_payload: Mapping[str, object],
    exit_payload: Mapping[str, object],
    *,
    instrument: BybitEligibleInstrument,
    exit_instrument: BybitEligibleInstrument,
    position_side: str,
    target_entry_mid_notional_usdt: object,
    entry_acquired_at: str,
    exit_acquired_at: str,
    entry_request_lineage_id: str,
    exit_request_lineage_id: str,
    entry_instrument_constraints_observed_at: str,
    entry_instrument_constraints_lineage_id: str,
    exit_instrument_constraints_observed_at: str,
    exit_instrument_constraints_lineage_id: str,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> BybitTargetNotionalRoundTrip:
    """Join conservative target-mid sizing to the exact quantity round trip."""

    sizing = size_bybit_target_entry_mid_notional(
        entry_payload,
        instrument=instrument,
        target_entry_mid_notional_usdt=target_entry_mid_notional_usdt,
        entry_acquired_at=entry_acquired_at,
        entry_request_lineage_id=entry_request_lineage_id,
        instrument_constraints_observed_at=(
            entry_instrument_constraints_observed_at
        ),
        instrument_constraints_lineage_id=(
            entry_instrument_constraints_lineage_id
        ),
        freshness_seconds=freshness_seconds,
    )
    round_trip = model_bybit_visible_book_round_trip(
        entry_payload,
        exit_payload,
        instrument=instrument,
        exit_instrument=exit_instrument,
        position_side=position_side,
        base_quantity=sizing.sized_base_quantity,
        entry_acquired_at=entry_acquired_at,
        exit_acquired_at=exit_acquired_at,
        entry_request_lineage_id=entry_request_lineage_id,
        exit_request_lineage_id=exit_request_lineage_id,
        entry_instrument_constraints_observed_at=(
            entry_instrument_constraints_observed_at
        ),
        entry_instrument_constraints_lineage_id=(
            entry_instrument_constraints_lineage_id
        ),
        exit_instrument_constraints_observed_at=(
            exit_instrument_constraints_observed_at
        ),
        exit_instrument_constraints_lineage_id=(
            exit_instrument_constraints_lineage_id
        ),
        freshness_seconds=freshness_seconds,
    )
    identity_reconciled = (
        sizing.instrument_id == round_trip.instrument_id
        and sizing.canonical_asset_id == round_trip.canonical_asset_id
        and sizing.base_asset == round_trip.base_asset
        and sizing.quote_asset == round_trip.quote_asset
        and sizing.sized_base_quantity == round_trip.base_quantity
        and sizing.quantity_step
        == round_trip.entry_instrument_constraints.quantity_step
        and sizing.instrument_constraints_observed_at
        == round_trip.entry_instrument_constraints.observed_at
        and sizing.instrument_constraints_lineage_id
        == round_trip.entry_instrument_constraints.lineage_id
    )
    same_entry_book = (
        sizing.entry_provider_observed_at == round_trip.entry.provider_observed_at
        and sizing.entry_snapshot_generated_at
        == round_trip.entry.snapshot_generated_at
        and sizing.entry_acquired_at == round_trip.entry.acquired_at
        and sizing.entry_request_lineage_id == round_trip.entry.request_lineage_id
        and sizing.entry_mid_price == round_trip.entry.mid_price
        and _float(Decimal(sizing.sized_entry_mid_notional_usdt))
        == round_trip.entry_mid_notional_usdt
    )
    if not identity_reconciled:
        raise BybitExecutionQualityError(
            "target_notional_round_trip_identity_mismatch"
        )
    if not same_entry_book:
        raise BybitExecutionQualityError(
            "target_notional_round_trip_entry_book_mismatch"
        )
    return BybitTargetNotionalRoundTrip(
        schema_version=TARGET_NOTIONAL_ROUND_TRIP_SCHEMA_VERSION,
        sizing=sizing,
        round_trip=round_trip,
        sizing_and_round_trip_identity_reconciled=True,
        same_entry_book_reconciled=True,
        same_base_quantity_reconciled=True,
        target_notional_tier_set_sealed=False,
        base_quantity_selection_policy_sealed=False,
        order_style_selected=False,
        realized_execution=False,
    )


def normalize_bybit_orderbook(
    payload: Mapping[str, object],
    *,
    instrument: BybitEligibleInstrument,
    acquired_at: str,
    request_lineage_id: str,
    depth_bands_bps: Sequence[int] = DEFAULT_DEPTH_BANDS_BPS,
    notionals_usdt: Sequence[float] = DEFAULT_NOTIONALS_USDT,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> BybitExecutionQualitySnapshot:
    """Normalize one supplied Bybit V5 snapshot without any provider access."""

    if not _TOKEN_RE.fullmatch(request_lineage_id):
        raise BybitExecutionQualityError("request_lineage_id_invalid")
    bands = tuple(depth_bands_bps)
    if (
        not bands
        or any(isinstance(value, bool) or not isinstance(value, int) for value in bands)
        or any(value <= 0 or value > 1_000 for value in bands)
        or tuple(sorted(set(bands))) != bands
    ):
        raise BybitExecutionQualityError("depth_bands_bps_invalid")
    notionals = tuple(notionals_usdt)
    if not notionals or tuple(sorted(set(notionals))) != notionals:
        raise BybitExecutionQualityError("notionals_usdt_invalid")
    for value in notionals:
        _decimal(value, "notional_usdt")
    if (
        type(freshness_seconds) not in {int, float}
        or not math.isfinite(float(freshness_seconds))
        or float(freshness_seconds) != DEFAULT_FRESHNESS_SECONDS
    ):
        raise BybitExecutionQualityError("freshness_seconds_invalid")
    if isinstance(payload.get("retCode"), bool) or payload.get("retCode") != 0:
        raise BybitExecutionQualityError("bybit_orderbook_response_not_ok")
    result = _mapping(payload.get("result"), "bybit_orderbook_result")
    if result.get("s") != instrument.instrument_id:
        raise BybitExecutionQualityError("bybit_orderbook_instrument_mismatch")

    bids = _book_levels(result.get("b"), "bids")
    asks = _book_levels(result.get("a"), "asks")
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    if best_bid >= best_ask:
        raise BybitExecutionQualityError("bybit_orderbook_locked_or_crossed")
    mid = (best_bid + best_ask) / Decimal(2)
    spread_bps = (best_ask - best_bid) / mid * Decimal(10_000)

    snapshot_ms = _integer(result.get("ts"), "orderbook_ts", minimum=1)
    observed_ms = _integer(result.get("cts"), "orderbook_cts", minimum=1)
    if snapshot_ms < observed_ms:
        raise BybitExecutionQualityError("snapshot_clock_precedes_matching_engine_clock")
    update_id = _integer(result.get("u"), "orderbook_update_id", minimum=0)
    sequence = _integer(result.get("seq"), "orderbook_sequence", minimum=0)
    acquired = _utc_datetime(acquired_at, "acquired_at")
    observed = datetime.fromtimestamp(observed_ms / 1000, tz=timezone.utc)
    age_seconds = (acquired - observed).total_seconds()
    if age_seconds < -5:
        raise BybitExecutionQualityError("provider_observed_at_too_far_in_future")
    snapshot_age_seconds = acquired.timestamp() - (snapshot_ms / 1000)
    if snapshot_age_seconds < -5:
        raise BybitExecutionQualityError("snapshot_generated_at_too_far_in_future")
    freshness_status = "fresh" if age_seconds <= freshness_seconds else "stale"

    return BybitExecutionQualitySnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        venue_id=VENUE_ID,
        execution_mode=EXECUTION_MODE,
        instrument_id=instrument.instrument_id,
        canonical_asset_id=instrument.canonical_asset_id,
        base_asset=instrument.base_asset,
        quote_asset=instrument.quote_asset,
        notional_currency=QUOTE_ASSET,
        provider_observed_at=_iso_from_ms(observed_ms),
        snapshot_generated_at=_iso_from_ms(snapshot_ms),
        acquired_at=acquired.isoformat().replace("+00:00", "Z"),
        age_seconds=round(age_seconds, 6),
        freshness_status=freshness_status,
        best_bid=_float(best_bid),
        best_ask=_float(best_ask),
        mid_price=_float(mid),
        spread_bps=_float(spread_bps),
        orderbook_level_limit=ORDERBOOK_LEVEL_LIMIT,
        liquidity_scope="bybit_public_rest_visible_levels_only",
        rpi_orders_included=False,
        bid_depth_usdt_by_band=_depth_by_band(
            bids, mid=mid, bands_bps=bands, side="bids"
        ),
        ask_depth_usdt_by_band=_depth_by_band(
            asks, mid=mid, bands_bps=bands, side="asks"
        ),
        buy_price_impact_bps_by_notional_usdt=_price_impact(
            asks, mid=mid, notionals=notionals, side="asks"
        ),
        sell_price_impact_bps_by_notional_usdt=_price_impact(
            bids, mid=mid, notionals=notionals, side="bids"
        ),
        impact_reference="mid_price",
        impact_method="deterministic_visible_book_walk_not_realized_execution",
        impact_size_definition=(
            "exact_usdt_spend_for_buy_and_exact_usdt_proceeds_for_sell"
        ),
        order_book_update_id=update_id,
        order_book_cross_sequence=sequence,
        source_url=(
            f"{PUBLIC_API_BASE}{ORDERBOOK_PATH}?category={BYBIT_CATEGORY}"
            f"&symbol={instrument.instrument_id}&limit={ORDERBOOK_LEVEL_LIMIT}"
        ),
        request_lineage_id=request_lineage_id,
        research_only=True,
    )


def run_fixture_smoke(fixture_directory: Path) -> dict[str, object]:
    """Run the checked offline example and return a credential-free summary."""

    radar_assets = json.loads((fixture_directory / "radar_assets.json").read_text(encoding="utf-8"))
    instruments_payload = json.loads(
        (fixture_directory / "instruments_info.json").read_text(encoding="utf-8")
    )
    orderbook_payload = json.loads(
        (fixture_directory / "orderbook_btcusdt.json").read_text(encoding="utf-8")
    )
    exit_orderbook_payload = json.loads(
        (fixture_directory / "orderbook_btcusdt_exit.json").read_text(
            encoding="utf-8"
        )
    )
    selected = select_bybit_usdt_perpetual_instruments(radar_assets, instruments_payload)
    if not selected:
        raise BybitExecutionQualityError("fixture_selected_no_instruments")
    btc = next((row for row in selected if row.instrument_id == "BTCUSDT"), None)
    if btc is None:
        raise BybitExecutionQualityError("fixture_missing_btcusdt")
    snapshot = normalize_bybit_orderbook(
        orderbook_payload,
        instrument=btc,
        acquired_at="2026-07-17T12:00:01Z",
        request_lineage_id="fixture.bybit.btcusdt.20260717",
    )
    target_notional_round_trip = (
        model_bybit_target_notional_visible_book_round_trip(
            orderbook_payload,
            exit_orderbook_payload,
            instrument=btc,
            exit_instrument=btc,
            position_side="long",
            target_entry_mid_notional_usdt="1500.75",
            entry_acquired_at="2026-07-17T12:00:01Z",
            exit_acquired_at="2026-07-17T13:00:01Z",
            entry_request_lineage_id="fixture.bybit.btcusdt.entry.20260717",
            exit_request_lineage_id="fixture.bybit.btcusdt.exit.20260717",
            entry_instrument_constraints_observed_at=(
                "2026-07-17T11:59:59Z"
            ),
            entry_instrument_constraints_lineage_id=(
                "fixture.bybit.linear.catalog.20260717"
            ),
            exit_instrument_constraints_observed_at=(
                "2026-07-17T12:59:59Z"
            ),
            exit_instrument_constraints_lineage_id=(
                "fixture.bybit.linear.catalog.exit.20260717"
            ),
        )
    )
    round_trip = target_notional_round_trip.round_trip
    plan = build_bybit_public_request_plan(selected)
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": "offline_fixture",
        "selected_instrument_ids": [row.instrument_id for row in selected],
        "selected_count": len(selected),
        "snapshot": snapshot.to_dict(),
        "target_notional_round_trip": target_notional_round_trip.to_dict(),
        "quantity_reconciled_round_trip": round_trip.to_dict(),
        "request_plan": plan.to_dict(),
        "provider_calls": 0,
        "network_called": False,
        "credentials_read": False,
        "orders_available": False,
        "research_only": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize checked Bybit public fixtures without provider access."
    )
    parser.add_argument("--fixture-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(json.dumps(run_fixture_smoke(args.fixture_dir), indent=2, sort_keys=True))
    return 0


__all__ = (
    "BYBIT_CATEGORY",
    "CONTRACT_TYPE",
    "CONTRACT_VERSION",
    "DEFAULT_DEPTH_BANDS_BPS",
    "DEFAULT_FRESHNESS_SECONDS",
    "DEFAULT_NOTIONALS_USDT",
    "EXECUTION_MODE",
    "INSTRUMENT_STATUS",
    "INSTRUMENT_CATALOG_LIMIT",
    "MAX_PLANNED_REQUESTS",
    "MAX_RADAR_ASSETS",
    "OFFICIAL_INSTRUMENT_DOC",
    "OFFICIAL_ORDERBOOK_DOC",
    "OFFICIAL_USDT_CONTRACT_ORDER_COST_DOC",
    "ORDERBOOK_LEVEL_LIMIT",
    "QUOTE_ASSET",
    "ROUND_TRIP_SCHEMA_VERSION",
    "REQUEST_STRATEGY",
    "SNAPSHOT_SCHEMA_VERSION",
    "TARGET_NOTIONAL_ROUND_TRIP_SCHEMA_VERSION",
    "TARGET_NOTIONAL_SIZING_SCHEMA_VERSION",
    "VENUE_ID",
    "BybitEligibleInstrument",
    "BybitExecutionQualityError",
    "BybitExecutionQualitySnapshot",
    "BybitLegInstrumentConstraints",
    "BybitPublicRequest",
    "BybitPublicRequestPlan",
    "BybitVisibleBookLeg",
    "BybitVisibleBookRoundTrip",
    "BybitTargetNotionalRoundTrip",
    "BybitTargetNotionalSizing",
    "bybit_base_symbol_requestable",
    "bybit_eligible_instrument_from_values",
    "build_bybit_instrument_catalog_request",
    "build_bybit_orderbook_request",
    "build_bybit_public_request_plan",
    "main",
    "model_bybit_visible_book_round_trip",
    "model_bybit_target_notional_visible_book_round_trip",
    "normalize_bybit_orderbook",
    "run_fixture_smoke",
    "select_bybit_usdt_perpetual_instruments",
    "size_bybit_target_entry_mid_notional",
)


if __name__ == "__main__":
    raise SystemExit(main())
