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
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


CONTRACT_VERSION = "crypto_radar_bybit_usdt_perpetual_execution_quality_v1"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.bybit_execution_quality.v2"
VENUE_ID = "bybit"
EXECUTION_MODE = "perpetual"
BYBIT_CATEGORY = "linear"
QUOTE_ASSET = "USDT"
CONTRACT_TYPE = "LinearPerpetual"
INSTRUMENT_STATUS = "Trading"
MAX_RADAR_ASSETS = 30
MAX_PLANNED_REQUESTS = MAX_RADAR_ASSETS * 2
DEFAULT_DEPTH_BANDS_BPS = (5, 10, 25, 50)
DEFAULT_NOTIONALS_USDT = (500.0, 2_000.0, 10_000.0)
DEFAULT_FRESHNESS_SECONDS = 15.0
PUBLIC_API_BASE = "https://api.bybit.com"
INSTRUMENTS_PATH = "/v5/market/instruments-info"
ORDERBOOK_PATH = "/v5/market/orderbook"
OFFICIAL_INSTRUMENT_DOC = "https://bybit-exchange.github.io/docs/v5/market/instrument"
OFFICIAL_ORDERBOOK_DOC = "https://bybit-exchange.github.io/docs/v5/market/orderbook"

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


# Stable public names expose a closed model bundle without declaring multiple
# public ownership classes in this behavior module.
BybitEligibleInstrument = _BybitEligibleInstrument
BybitPublicRequest = _BybitPublicRequest
BybitPublicRequestPlan = _BybitPublicRequestPlan
BybitExecutionQualitySnapshot = _BybitExecutionQualitySnapshot


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
    if cursor not in (None, ""):
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
            tick_size=str(tick),
            quantity_step=str(quantity_step),
            launch_time_ms=_integer(row.get("launchTime"), "launchTime"),
            delivery_time_ms=_integer(row.get("deliveryTime"), "deliveryTime"),
        )
        if base in selected_by_base:
            raise BybitExecutionQualityError("bybit_instrument_mapping_ambiguous")
        selected_by_base[base] = selected

    return tuple(
        sorted(selected_by_base.values(), key=lambda row: (row.liquidity_rank, row.instrument_id))
    )


def build_bybit_public_request_plan(
    instruments: Sequence[BybitEligibleInstrument],
) -> BybitPublicRequestPlan:
    """Build but never execute exact public metadata/book GET descriptions."""

    if not instruments:
        raise BybitExecutionQualityError("eligible_instrument_set_empty")
    if len(instruments) > MAX_RADAR_ASSETS:
        raise BybitExecutionQualityError("eligible_instrument_set_exceeds_30")
    seen: set[str] = set()
    requests: list[BybitPublicRequest] = []
    for instrument in instruments:
        if (
            instrument.instrument_id in seen
            or instrument.quote_asset != QUOTE_ASSET
            or instrument.settle_asset != QUOTE_ASSET
            or instrument.contract_type != CONTRACT_TYPE
            or instrument.status != INSTRUMENT_STATUS
        ):
            raise BybitExecutionQualityError("eligible_instrument_contract_invalid")
        seen.add(instrument.instrument_id)
        requests.extend(
            (
                BybitPublicRequest(
                    method="GET",
                    path=INSTRUMENTS_PATH,
                    query=(
                        ("category", BYBIT_CATEGORY),
                        ("symbol", instrument.instrument_id),
                    ),
                ),
                BybitPublicRequest(
                    method="GET",
                    path=ORDERBOOK_PATH,
                    query=(
                        ("category", BYBIT_CATEGORY),
                        ("symbol", instrument.instrument_id),
                        ("limit", "200"),
                    ),
                ),
            )
        )
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
    if freshness_seconds <= 0:
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
        orderbook_level_limit=200,
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
            f"&symbol={instrument.instrument_id}&limit=200"
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
    plan = build_bybit_public_request_plan(selected)
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": "offline_fixture",
        "selected_instrument_ids": [row.instrument_id for row in selected],
        "selected_count": len(selected),
        "snapshot": snapshot.to_dict(),
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
    "MAX_PLANNED_REQUESTS",
    "MAX_RADAR_ASSETS",
    "OFFICIAL_INSTRUMENT_DOC",
    "OFFICIAL_ORDERBOOK_DOC",
    "QUOTE_ASSET",
    "SNAPSHOT_SCHEMA_VERSION",
    "VENUE_ID",
    "BybitEligibleInstrument",
    "BybitExecutionQualityError",
    "BybitExecutionQualitySnapshot",
    "BybitPublicRequest",
    "BybitPublicRequestPlan",
    "bybit_base_symbol_requestable",
    "build_bybit_public_request_plan",
    "main",
    "normalize_bybit_orderbook",
    "run_fixture_smoke",
    "select_bybit_usdt_perpetual_instruments",
)


if __name__ == "__main__":
    raise SystemExit(main())
