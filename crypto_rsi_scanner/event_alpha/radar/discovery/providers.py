"""Event discovery provider and enrichment helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .... import event_anomaly_scanner, event_fade, event_market_enrichment, event_provider_health
from ....derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
from ....event_classification import classify_event_asset
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
from ....event_resolver import clean_text, load_asset_aliases, resolve_event_assets
from ....supply_providers.arkham import ArkhamSupplyProvider
from ....supply_providers.dune import DuneSupplyProvider
from ....supply_providers.etherscan import EtherscanSupplyProvider
from ....supply_providers.tokenomist import TokenomistSupplyProvider
from .models import *  # noqa: F403 - split modules share legacy model names


def _coinalyze_base_symbols(assets: Iterable[DiscoveredAsset]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for asset in assets:
        for value in (asset.symbol, *asset.aliases):
            symbol = _coinalyze_base_symbol(value)
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            out.append(symbol)
            break
    return tuple(out)


def _coinalyze_base_symbol(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    compact = text.replace("-", "").replace("_", "").replace("/", "")
    for suffix in ("USDT", "USD"):
        if compact.endswith(suffix) and len(compact) > len(suffix):
            compact = compact[: -len(suffix)]
    if compact.isalnum() and any(ch.isalpha() for ch in compact):
        return compact
    return ""


def load_derivatives_snapshots(
    coinalyze_derivatives_path: str | Path | None,
    *,
    coinalyze_live: bool = False,
    coinalyze_api_key: str = "",
    coinalyze_symbols: Iterable[str] = (),
    coinalyze_auto_symbols: bool = True,
    coinalyze_base_symbols: Iterable[str] = (),
    coinalyze_base_url: str = "https://api.coinalyze.net/v1/",
    coinalyze_timeout: float = 10.0,
    coinalyze_history_interval: str = "1hour",
    coinalyze_lookback_hours: int = 24,
    coinalyze_convert_to_usd: bool = True,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
    provider_warnings: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load optional local and/or live derivatives snapshots for event-candidate enrichment."""
    snapshots: dict[str, dict[str, Any]] = {}
    if coinalyze_derivatives_path:
        snapshots.update(CoinalyzeDerivativesProvider(coinalyze_derivatives_path).fetch_snapshots())
    if coinalyze_live:
        provider = CoinalyzeDerivativesProvider(
            None,
            live_enabled=True,
            api_key=coinalyze_api_key,
            symbols=coinalyze_symbols,
            base_symbols=coinalyze_base_symbols,
            auto_symbols=coinalyze_auto_symbols,
            base_url=coinalyze_base_url,
            timeout=coinalyze_timeout,
            history_interval=coinalyze_history_interval,
            lookback_hours=coinalyze_lookback_hours,
            convert_to_usd=coinalyze_convert_to_usd,
        )
        if provider_health_cfg is not None:
            provider = event_provider_health.HealthCheckedDerivativesProvider(
                provider,
                cfg=provider_health_cfg,
                provider_kind="enrichment",
            )
        snapshots.update(provider.fetch_snapshots())
        _extend_warnings(provider_warnings, getattr(provider, "last_warnings", ()))
    return snapshots


def _fetch_provider_events(
    provider: Any,
    start: datetime,
    end: datetime,
    *,
    live: bool,
    health_cfg: event_provider_health.EventProviderHealthConfig | None,
    warnings: list[str] | None,
) -> list[RawDiscoveredEvent]:
    wrapped = provider
    if live and health_cfg is not None:
        wrapped = event_provider_health.HealthCheckedEventProvider(
            provider,
            cfg=health_cfg,
            provider_kind="event_source",
        )
    rows = list(wrapped.fetch_events(start, end))
    _extend_warnings(warnings, getattr(wrapped, "last_warnings", ()))
    return rows


def _extend_warnings(target: list[str] | None, warnings: Iterable[str]) -> None:
    if target is None:
        return
    for warning in warnings:
        text = str(warning or "").strip()
        if text:
            target.append(text)


def load_supply_snapshots(
    *,
    tokenomist_supply_path: str | Path | None = None,
    etherscan_supply_path: str | Path | None = None,
    arkham_supply_path: str | Path | None = None,
    dune_supply_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load optional local supply/on-chain snapshots for event-candidate enrichment."""
    out: dict[str, dict[str, Any]] = {}
    for provider in (
        TokenomistSupplyProvider(tokenomist_supply_path),
        EtherscanSupplyProvider(etherscan_supply_path),
        ArkhamSupplyProvider(arkham_supply_path),
        DuneSupplyProvider(dune_supply_path),
    ):
        out.update(provider.fetch_snapshots())
    return out


def merge_discovered_assets(assets: Iterable[DiscoveredAsset]) -> list[DiscoveredAsset]:
    by_id: dict[str, DiscoveredAsset] = {}
    order: list[str] = []
    for asset in assets:
        if not asset.coin_id:
            continue
        if asset.coin_id not in by_id:
            by_id[asset.coin_id] = asset
            order.append(asset.coin_id)
            continue
        by_id[asset.coin_id] = _merge_asset(by_id[asset.coin_id], asset)
    return [by_id[coin_id] for coin_id in order]


def build_fade_candidate(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    classification: EventClassification,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    now: datetime,
    *,
    market_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    derivatives_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    supply_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
) -> event_fade.FadeCandidate:
    payload = _merged_event_payload(event, asset, raw_by_id, now)
    catalyst_confidence = min(
        event.confidence,
        classification.confidence,
        event.event_time_confidence if event.event_time else 1.0,
    )
    catalyst = event_fade.CatalystEvent(
        event_id=event.event_id,
        coin_id=asset.coin_id,
        symbol=asset.symbol,
        event_name=event.event_name,
        event_type=event.event_type,
        event_time=event.event_time,
        first_seen_time=event.first_seen_time,
        source=event.source,
        source_url=event.source_urls[0] if event.source_urls else None,
        confidence=catalyst_confidence,
        external_asset=event.external_asset,
        is_proxy_narrative=classification.is_proxy_narrative,
        is_direct_beneficiary=classification.is_direct_beneficiary,
        notes=classification.reason,
    )
    market = _market_snapshot(asset, payload.get("market") or _market_for_asset(market_by_asset, asset), now)
    return event_fade.FadeCandidate(
        symbol=asset.symbol,
        coin_id=asset.coin_id,
        event=catalyst,
        market=market,
        derivatives=_derivatives_snapshot(asset, payload.get("derivatives") or _derivatives_for_asset(
            derivatives_by_asset,
            asset,
        ), now),
        supply=_supply_snapshot(asset, payload.get("supply") or _supply_for_asset(supply_by_asset, asset), now),
        rsi=_rsi_snapshot(asset, payload.get("rsi"), now),
        technical=_technical_snapshot(asset, payload.get("technical"), now),
    )


def _merged_event_payload(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    decision_time: datetime,
) -> dict[str, Any]:
    payloads: list[Mapping[str, Any]] = []
    for raw_id in event.raw_ids:
        raw = raw_by_id.get(raw_id)
        if raw is None or not isinstance(raw.raw_json, Mapping):
            continue
        if not _raw_available_as_of(raw, decision_time):
            continue
        payloads.append(raw.raw_json)
    out: dict[str, Any] = {}
    for section in ("market", "derivatives", "supply", "rsi", "technical"):
        best = _richest_payload_section(payloads, section, asset)
        if best:
            out[section] = best
    return out


def _raw_available_as_of(raw: RawDiscoveredEvent, decision_time: datetime) -> bool:
    decision = _as_utc(decision_time)
    if raw.fetched_at and _as_utc(raw.fetched_at) > decision:
        return False
    if raw.published_at and _as_utc(raw.published_at) > decision:
        return False
    return True


def _richest_payload_section(
    payloads: Iterable[Mapping[str, Any]],
    section: str,
    asset: DiscoveredAsset,
) -> Mapping[str, Any] | None:
    best: Mapping[str, Any] | None = None
    best_score = -1
    for payload in payloads:
        raw_section = payload.get(section)
        if not isinstance(raw_section, Mapping):
            continue
        if not _section_matches_asset(raw_section, asset):
            continue
        score = _payload_richness(raw_section)
        if score > best_score:
            best = raw_section
            best_score = score
    return best


def _section_matches_asset(section: Mapping[str, Any], asset: DiscoveredAsset) -> bool:
    symbol = clean_text(section.get("symbol"))
    coin_id = clean_text(section.get("coin_id"))
    if coin_id and coin_id != clean_text(asset.coin_id):
        return False
    if symbol:
        expected = {clean_text(asset.symbol), clean_text(f"{asset.symbol}usdt")}
        if symbol not in expected:
            return False
    return True


def _payload_richness(payload: Mapping[str, Any]) -> int:
    score = 0
    for value in payload.values():
        if value in (None, "", [], {}):
            continue
        score += 1
    return score
