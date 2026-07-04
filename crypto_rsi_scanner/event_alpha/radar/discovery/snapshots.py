"""Event discovery market/derivatives/supply snapshot helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
from ....derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
from ..classification import classify_event_asset
from crypto_rsi_scanner.event_core.models import (
    DiscoveredAsset,
    DiscoveredEventFadeCandidate,
    EventAssetLink,
    EventClassification,
    EventDiscoveryResult,
    NormalizedEvent,
    RawDiscoveredEvent,
)
from ....event_providers.binance_announcements import BinanceAnnouncementProvider
from ....event_providers.bybit_announcements import BybitAnnouncementProvider
from ....event_providers.coinmarketcal import CoinMarketCalProvider
from ....event_providers.coingecko_universe import CoinGeckoUniverseProvider
from ....event_providers.cryptopanic import CryptoPanicProvider
from ....event_providers.external_ipo import ExternalIpoProvider
from ....event_providers.gdelt import DEFAULT_GDELT_QUERY, GdeltProvider
from ....event_providers.manual_json import ManualJsonEventProvider, parse_datetime
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ....event_providers.sports_fixtures import SportsFixturesProvider
from ....event_providers.tokenomist import TokenomistProvider
from ..resolver import clean_text, load_asset_aliases, resolve_event_assets
from ....supply_providers.arkham import ArkhamSupplyProvider
from ....supply_providers.dune import DuneSupplyProvider
from ....supply_providers.etherscan import EtherscanSupplyProvider
from ....supply_providers.tokenomist import TokenomistSupplyProvider
from .models import *  # noqa: F403 - split modules share legacy model names


def _infer_event_type(title: str, body: str | None) -> str:
    text = clean_text(f"{title} {body or ''}")
    if "unlock" in text:
        return "token_unlock"
    if "binance" in text and "listing" in text:
        return "exchange_listing"
    if "listing" in text:
        return "exchange_listing"
    if "perp" in text or "futures" in text:
        return "perp_listing"
    if "airdrop" in text:
        return "airdrop"
    if "mainnet" in text:
        return "mainnet_launch"
    if "etf" in text:
        return "etf_approval"
    if "ipo" in text or "pre-ipo" in text or "pre ipo" in text:
        return "ipo_proxy"
    if "election" in text or "inauguration" in text:
        return "political_event"
    if "world cup" in text or "match" in text:
        return "sports_event"
    return "other"


def _merge_asset(base: DiscoveredAsset, other: DiscoveredAsset) -> DiscoveredAsset:
    return DiscoveredAsset(
        coin_id=base.coin_id or other.coin_id,
        symbol=base.symbol or other.symbol,
        name=base.name or other.name,
        market_cap=base.market_cap if base.market_cap is not None else other.market_cap,
        volume_24h=base.volume_24h if base.volume_24h is not None else other.volume_24h,
        price=base.price if base.price is not None else other.price,
        categories=_unique((*base.categories, *other.categories)),
        contract_addresses={**other.contract_addresses, **base.contract_addresses},
        source=base.source if base.source == other.source else f"{base.source}+{other.source}",
        aliases=_unique((*base.aliases, *other.aliases)),
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        key = clean_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return tuple(out)


def _derivatives_for_asset(
    snapshots: Mapping[str, Mapping[str, Any]] | None,
    asset: DiscoveredAsset,
) -> Mapping[str, Any] | None:
    if not snapshots:
        return None
    for key in _asset_derivatives_keys(asset):
        if key in snapshots:
            return snapshots[key]
    return None


def _supply_for_asset(
    snapshots: Mapping[str, Mapping[str, Any]] | None,
    asset: DiscoveredAsset,
) -> Mapping[str, Any] | None:
    if not snapshots:
        return None
    for key in _asset_supply_keys(asset):
        if key in snapshots:
            return snapshots[key]
    return None


def _market_for_asset(
    snapshots: Mapping[str, Mapping[str, Any]] | None,
    asset: DiscoveredAsset,
) -> Mapping[str, Any] | None:
    if not snapshots:
        return None
    for key in _asset_market_keys(asset):
        if key in snapshots:
            return snapshots[key]
    return None


def _asset_market_keys(asset: DiscoveredAsset) -> tuple[str, ...]:
    raw_values = (
        asset.coin_id,
        asset.symbol,
        asset.name,
        *asset.aliases,
        *asset.contract_addresses.values(),
    )
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        for key in (clean_text(value), str(value or "").upper()):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _asset_derivatives_keys(asset: DiscoveredAsset) -> tuple[str, ...]:
    raw_values = (asset.coin_id, asset.symbol, *asset.aliases)
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        for key in (clean_text(value), str(value).upper()):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _asset_supply_keys(asset: DiscoveredAsset) -> tuple[str, ...]:
    raw_values = (
        asset.coin_id,
        asset.symbol,
        *asset.aliases,
        *asset.contract_addresses.values(),
    )
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        for key in (clean_text(value), str(value).upper()):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _event_id(*parts: object) -> str:
    encoded = "|".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return "evt_" + hashlib.sha1(encoded).hexdigest()[:16]


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _dt(value: object, fallback: datetime) -> datetime:
    return parse_datetime(value) or fallback


def _payload(data: object) -> dict[str, Any]:
    return dict(data) if isinstance(data, Mapping) else {}


def _market_snapshot(asset: DiscoveredAsset, data: object, now: datetime) -> event_fade.EventMarketSnapshot:
    p = _payload(data)
    return event_fade.EventMarketSnapshot(
        symbol=str(p.get("symbol") or asset.symbol).upper(),
        coin_id=p.get("coin_id", asset.coin_id),
        timestamp=_dt(p.get("timestamp"), now),
        price=float(p.get("price") or asset.price or 0.0),
        volume_24h=p.get("volume_24h", asset.volume_24h),
        spot_volume_24h=p.get("spot_volume_24h"),
        market_cap=p.get("market_cap", asset.market_cap),
        fdv=p.get("fdv"),
        circulating_supply=p.get("circulating_supply"),
        total_supply=p.get("total_supply"),
        max_supply=p.get("max_supply"),
        return_1h=p.get("return_1h"),
        return_4h=p.get("return_4h"),
        return_24h=p.get("return_24h"),
        return_72h=p.get("return_72h"),
        return_7d=p.get("return_7d"),
        distance_from_20d_ma=p.get("distance_from_20d_ma"),
        volume_zscore_24h=p.get("volume_zscore_24h"),
        order_book_depth_1pct=p.get("order_book_depth_1pct"),
        order_book_depth_2pct=p.get("order_book_depth_2pct"),
        spread_bps=p.get("spread_bps"),
    )


def _derivatives_snapshot(
    asset: DiscoveredAsset,
    data: object,
    now: datetime,
) -> event_fade.EventDerivativesSnapshot | None:
    p = _payload(data)
    if not p:
        return None
    return event_fade.EventDerivativesSnapshot(
        symbol=str(p.get("symbol") or asset.symbol).upper(),
        timestamp=_dt(p.get("timestamp"), now),
        perp_available=bool(p.get("perp_available")),
        open_interest=p.get("open_interest"),
        open_interest_24h_change_pct=p.get("open_interest_24h_change_pct"),
        open_interest_to_market_cap=p.get("open_interest_to_market_cap"),
        funding_rate_8h=p.get("funding_rate_8h"),
        funding_rate_percentile=p.get("funding_rate_percentile"),
        futures_volume_24h=p.get("futures_volume_24h"),
        perp_spot_volume_ratio=p.get("perp_spot_volume_ratio"),
        liquidations_24h=p.get("liquidations_24h"),
        long_short_ratio=p.get("long_short_ratio"),
        basis=p.get("basis"),
    )


def _supply_snapshot(asset: DiscoveredAsset, data: object, now: datetime) -> event_fade.EventSupplyPressureSnapshot | None:
    p = _payload(data)
    if not p:
        return None
    return event_fade.EventSupplyPressureSnapshot(
        symbol=str(p.get("symbol") or asset.symbol).upper(),
        timestamp=_dt(p.get("timestamp"), now),
        large_holder_exchange_inflow=p.get("large_holder_exchange_inflow"),
        cex_inflow_amount=p.get("cex_inflow_amount"),
        cex_inflow_pct_supply=p.get("cex_inflow_pct_supply"),
        unlock_amount=p.get("unlock_amount"),
        unlock_pct_circulating=p.get("unlock_pct_circulating"),
        top_holder_concentration=p.get("top_holder_concentration"),
        team_or_mm_wallet_activity=p.get("team_or_mm_wallet_activity"),
        admin_or_mint_risk=p.get("admin_or_mint_risk"),
        notes=p.get("notes"),
    )


def _rsi_snapshot(asset: DiscoveredAsset, data: object, now: datetime) -> event_fade.EventRSISnapshot | None:
    p = _payload(data)
    if not p:
        return None
    return event_fade.EventRSISnapshot(
        symbol=str(p.get("symbol") or asset.symbol).upper(),
        timestamp=_dt(p.get("timestamp"), now),
        rsi_daily=p.get("rsi_daily"),
        rsi_4h=p.get("rsi_4h"),
        rsi_weekly=p.get("rsi_weekly"),
        rsi_5m=p.get("rsi_5m"),
        rsi_15m=p.get("rsi_15m"),
        rsi_1h=p.get("rsi_1h"),
        btc_rsi_daily=p.get("btc_rsi_daily"),
        btc_rsi_4h=p.get("btc_rsi_4h"),
        btc_rsi_1h=p.get("btc_rsi_1h"),
        target_overbought_score=float(p.get("target_overbought_score") or 0.0),
        target_oversold_score=float(p.get("target_oversold_score") or 0.0),
        btc_risk_on_score=float(p.get("btc_risk_on_score") or 0.0),
        btc_risk_off_score=float(p.get("btc_risk_off_score") or 0.0),
        rsi_rollover_confirmed=bool(p.get("rsi_rollover_confirmed")),
        bearish_rsi_divergence=p.get("bearish_rsi_divergence"),
    )


def _technical_snapshot(asset: DiscoveredAsset, data: object, now: datetime) -> event_fade.EventTechnicalSnapshot | None:
    p = _payload(data)
    if not p:
        return None
    return event_fade.EventTechnicalSnapshot(
        symbol=str(p.get("symbol") or asset.symbol).upper(),
        timestamp=_dt(p.get("timestamp"), now),
        event_vwap=p.get("event_vwap"),
        price_below_event_vwap=p.get("price_below_event_vwap"),
        failed_reclaim_event_vwap=p.get("failed_reclaim_event_vwap"),
        lower_high_confirmed=p.get("lower_high_confirmed"),
        first_support_broken=p.get("first_support_broken"),
        post_event_high=p.get("post_event_high"),
        post_event_lower_high=p.get("post_event_lower_high"),
        invalidation_level=p.get("invalidation_level"),
        entry_reference_price=p.get("entry_reference_price"),
    )
