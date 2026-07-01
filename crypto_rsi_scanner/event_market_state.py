"""Normalized market-state snapshots for Event Alpha research artifacts.

This module is pure: it reads already-collected market rows and produces a
stable snapshot schema. It does not create alerts, routes, paper rows, or
event-fade triggers.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class MarketStateSnapshot:
    symbol: str
    coin_id: str
    canonical_asset_id: str
    observed_at: str
    price: float | None = None
    return_5m: float | None = None
    return_15m: float | None = None
    return_1h: float | None = None
    return_4h: float | None = None
    return_24h: float | None = None
    relative_return_vs_btc_1h: float | None = None
    relative_return_vs_btc_4h: float | None = None
    relative_return_vs_btc_24h: float | None = None
    relative_return_vs_eth_1h: float | None = None
    relative_return_vs_eth_4h: float | None = None
    relative_return_vs_eth_24h: float | None = None
    volume_24h: float | None = None
    volume_zscore_24h: float | None = None
    turnover_zscore: float | None = None
    volume_to_market_cap: float | None = None
    liquidity_usd: float | None = None
    spread_bps: float | None = None
    open_interest_delta: float | None = None
    funding_level: float | None = None
    funding_zscore: float | None = None
    liquidation_imbalance: float | None = None
    dex_volume_change: float | None = None
    dex_liquidity_change: float | None = None
    event_age_hours: float | None = None
    market_data_source: str = "unknown"
    freshness_status: str = "unknown"
    observed_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["observed_fields"] = list(self.observed_fields)
        data["warnings"] = list(self.warnings)
        return data


def snapshot_from_market_row(
    row: Mapping[str, Any],
    *,
    observed_at: datetime | str | None = None,
    btc_benchmark: Mapping[str, Any] | None = None,
    eth_benchmark: Mapping[str, Any] | None = None,
) -> MarketStateSnapshot:
    """Build a stable market-state snapshot from a CoinGecko-style row."""
    observed = _observed_at(row, observed_at)
    symbol = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
    coin_id = str(row.get("coin_id") or row.get("id") or "").strip()
    canonical_asset_id = str(row.get("canonical_asset_id") or coin_id or symbol).strip()
    warnings: list[str] = []
    fields: list[str] = []

    def capture(name: str, value: float | None) -> float | None:
        if value is not None:
            fields.append(name)
        return value

    market_cap = _float(row.get("market_cap") or row.get("mcap"))
    volume_24h = _float(row.get("volume_24h") or row.get("total_volume") or row.get("spot_volume_24h"))
    volume_mcap = _float(row.get("volume_to_market_cap") or row.get("volume_mcap") or row.get("volume_mcap_ratio"))
    if volume_mcap is None and volume_24h is not None and market_cap and market_cap > 0:
        volume_mcap = volume_24h / market_cap
    if not symbol and not coin_id:
        warnings.append("missing_asset_identity")

    r1h = _percent_value(row.get("return_1h") or row.get("price_change_percentage_1h_in_currency"))
    r4h = _percent_value(row.get("return_4h") or row.get("price_change_percentage_4h_in_currency"))
    r24h = _percent_value(row.get("return_24h") or row.get("price_change_24h") or row.get("price_change_percentage_24h_in_currency"))
    btc = btc_benchmark or {}
    eth = eth_benchmark or {}
    rel_btc_1h = _percent_value(row.get("relative_return_vs_btc_1h") or row.get("rel_btc_1h"))
    rel_btc_4h = _percent_value(row.get("relative_return_vs_btc_4h") or row.get("rel_btc_4h"))
    rel_btc_24h = _percent_value(row.get("relative_return_vs_btc_24h") or row.get("relative_strength_vs_btc") or row.get("btc_relative_return"))
    rel_eth_1h = _percent_value(row.get("relative_return_vs_eth_1h") or row.get("rel_eth_1h"))
    rel_eth_4h = _percent_value(row.get("relative_return_vs_eth_4h") or row.get("rel_eth_4h"))
    rel_eth_24h = _percent_value(row.get("relative_return_vs_eth_24h") or row.get("rel_eth_24h"))
    if rel_btc_1h is None and r1h is not None:
        btc_r1h = _percent_value(btc.get("return_1h") or btc.get("price_change_percentage_1h_in_currency"))
        if btc_r1h is not None:
            rel_btc_1h = r1h - btc_r1h
    if rel_btc_4h is None and r4h is not None:
        btc_r4h = _percent_value(btc.get("return_4h") or btc.get("price_change_percentage_4h_in_currency"))
        if btc_r4h is not None:
            rel_btc_4h = r4h - btc_r4h
    if rel_btc_24h is None and r24h is not None:
        btc_r24h = _percent_value(btc.get("return_24h") or btc.get("price_change_percentage_24h_in_currency"))
        if btc_r24h is not None:
            rel_btc_24h = r24h - btc_r24h
    if rel_eth_1h is None and r1h is not None:
        eth_r1h = _percent_value(eth.get("return_1h") or eth.get("price_change_percentage_1h_in_currency"))
        if eth_r1h is not None:
            rel_eth_1h = r1h - eth_r1h
    if rel_eth_4h is None and r4h is not None:
        eth_r4h = _percent_value(eth.get("return_4h") or eth.get("price_change_percentage_4h_in_currency"))
        if eth_r4h is not None:
            rel_eth_4h = r4h - eth_r4h
    if rel_eth_24h is None and r24h is not None:
        eth_r24h = _percent_value(eth.get("return_24h") or eth.get("price_change_percentage_24h_in_currency"))
        if eth_r24h is not None:
            rel_eth_24h = r24h - eth_r24h

    freshness = str(
        row.get("market_context_freshness_status")
        or row.get("freshness_status")
        or ("fresh" if row.get("observed_at") or row.get("timestamp") else "unknown")
    )
    source = str(row.get("market_data_source") or row.get("source") or "fixture")
    snapshot = MarketStateSnapshot(
        symbol=symbol,
        coin_id=coin_id,
        canonical_asset_id=canonical_asset_id,
        observed_at=observed.isoformat(),
        price=capture("price", _float(row.get("price") or row.get("current_price"))),
        return_5m=capture("return_5m", _percent_value(row.get("return_5m"))),
        return_15m=capture("return_15m", _percent_value(row.get("return_15m"))),
        return_1h=capture("return_1h", r1h),
        return_4h=capture("return_4h", r4h),
        return_24h=capture("return_24h", r24h),
        relative_return_vs_btc_1h=capture("relative_return_vs_btc_1h", rel_btc_1h),
        relative_return_vs_btc_4h=capture("relative_return_vs_btc_4h", rel_btc_4h),
        relative_return_vs_btc_24h=capture("relative_return_vs_btc_24h", rel_btc_24h),
        relative_return_vs_eth_1h=capture("relative_return_vs_eth_1h", rel_eth_1h),
        relative_return_vs_eth_4h=capture("relative_return_vs_eth_4h", rel_eth_4h),
        relative_return_vs_eth_24h=capture("relative_return_vs_eth_24h", rel_eth_24h),
        volume_24h=capture("volume_24h", volume_24h),
        volume_zscore_24h=capture("volume_zscore_24h", _float(row.get("volume_zscore_24h") or row.get("volume_zscore"))),
        turnover_zscore=capture("turnover_zscore", _float(row.get("turnover_zscore"))),
        volume_to_market_cap=capture("volume_to_market_cap", volume_mcap),
        liquidity_usd=capture("liquidity_usd", _float(row.get("liquidity_usd") or row.get("order_book_liquidity_usd"))),
        spread_bps=capture("spread_bps", _float(row.get("spread_bps"))),
        open_interest_delta=capture("open_interest_delta", _percent_value(row.get("open_interest_delta") or row.get("open_interest_delta_24h"))),
        funding_level=capture("funding_level", _float(row.get("funding_level") or row.get("funding_rate"))),
        funding_zscore=capture("funding_zscore", _float(row.get("funding_zscore"))),
        liquidation_imbalance=capture("liquidation_imbalance", _float(row.get("liquidation_imbalance"))),
        dex_volume_change=capture("dex_volume_change", _percent_value(row.get("dex_volume_change"))),
        dex_liquidity_change=capture("dex_liquidity_change", _percent_value(row.get("dex_liquidity_change"))),
        event_age_hours=capture("event_age_hours", _float(row.get("event_age_hours"))),
        market_data_source=source,
        freshness_status=freshness,
        observed_fields=tuple(dict.fromkeys(fields)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return snapshot


def benchmark_rows(market_rows: list[Mapping[str, Any]]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Return BTC and ETH benchmark rows when present."""
    btc: Mapping[str, Any] = {}
    eth: Mapping[str, Any] = {}
    for row in market_rows:
        symbol = str(row.get("symbol") or "").upper()
        coin_id = str(row.get("coin_id") or row.get("id") or "").casefold()
        if symbol == "BTC" or coin_id == "bitcoin":
            btc = row
        elif symbol == "ETH" or coin_id == "ethereum":
            eth = row
    return btc, eth


def _observed_at(row: Mapping[str, Any], observed_at: datetime | str | None) -> datetime:
    value = observed_at or row.get("observed_at") or row.get("timestamp")
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str) and value.strip():
        try:
            return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _percent_value(value: object) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    # Existing market-enrichment snapshots use fractions. User-facing market
    # state artifacts use percentage points to match threshold language.
    if abs(parsed) <= 3.0:
        return parsed * 100.0
    return parsed


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
