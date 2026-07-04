"""Event discovery fixture/manual source loading."""

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


def run_manual_discovery(
    event_path: str | Path | None,
    alias_path: str | Path | None,
    *,
    binance_announcements_path: str | Path | None = None,
    binance_announcements_live: bool = False,
    binance_announcements_api_key: str = "",
    binance_announcements_api_secret: str = "",
    binance_announcements_ws_url: str = "wss://api.binance.com/sapi/wss",
    binance_announcements_topic: str = "com_announcement_en",
    binance_announcements_recv_window_ms: int = 30000,
    binance_announcements_listen_seconds: float = 5.0,
    binance_announcements_max_messages: int = 20,
    bybit_announcements_path: str | Path | None = None,
    bybit_announcements_live: bool = False,
    bybit_announcements_base_url: str = "https://api.bybit.com",
    bybit_announcements_locale: str = "en-US",
    bybit_announcements_type: str = "new_crypto",
    bybit_announcements_limit: int = 20,
    bybit_announcements_timeout: float = 10.0,
    coinmarketcal_path: str | Path | None = None,
    tokenomist_path: str | Path | None = None,
    cryptopanic_path: str | Path | None = None,
    cryptopanic_live: bool = False,
    cryptopanic_api_token: str = "",
    cryptopanic_base_url: str = "https://cryptopanic.com/api/growth_weekly/v2",
    cryptopanic_plan: str = "growth_weekly",
    cryptopanic_public: bool = True,
    cryptopanic_following: bool = False,
    cryptopanic_filter: str = "",
    cryptopanic_currencies: str = "",
    cryptopanic_regions: str = "en",
    cryptopanic_kind: str = "news",
    cryptopanic_search: str = "",
    cryptopanic_timeout: float = 10.0,
    cryptopanic_request_ledger_path: str | Path | None = None,
    cryptopanic_profile: str = "",
    cryptopanic_artifact_namespace: str = "",
    cryptopanic_weekly_request_limit: int = 600,
    cryptopanic_requests_per_run_limit: int = 20,
    cryptopanic_requests_per_day_soft_limit: int = 80,
    cryptopanic_min_seconds_between_requests: float = 1.0,
    cryptopanic_max_pages_per_query: int = 1,
    cryptopanic_max_currencies_per_request: int = 10,
    gdelt_path: str | Path | None = None,
    gdelt_live: bool = False,
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc",
    gdelt_query: str = "",
    gdelt_max_records: int = 50,
    gdelt_timeout: float = 10.0,
    project_blog_rss_path: str | Path | None = None,
    project_blog_rss_live: bool = False,
    project_blog_rss_urls: Iterable[str] | None = None,
    project_blog_rss_timeout: float = 10.0,
    project_blog_rss_fail_fast_on_error: bool = False,
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
    prediction_market_events_live: bool = False,
    prediction_market_events_base_url: str = "https://gamma-api.polymarket.com/events",
    prediction_market_events_limit: int = 100,
    prediction_market_events_timeout: float = 10.0,
    coinalyze_derivatives_path: str | Path | None = None,
    coinalyze_live: bool = False,
    coinalyze_api_key: str = "",
    coinalyze_symbols: Iterable[str] = (),
    coinalyze_auto_symbols: bool = True,
    coinalyze_base_url: str = "https://api.coinalyze.net/v1/",
    coinalyze_timeout: float = 10.0,
    coinalyze_history_interval: str = "1hour",
    coinalyze_lookback_hours: int = 24,
    coinalyze_convert_to_usd: bool = True,
    market_enrichment_enabled: bool = False,
    market_enrichment_path: str | Path | None = None,
    market_enrichment_live: bool = False,
    market_enrichment_fetch_limit: int = 0,
    market_enrichment_fail_soft: bool = False,
    anomaly_scanner_enabled: bool = False,
    anomaly_min_return_24h: float = 0.30,
    anomaly_min_volume_mcap: float = 0.25,
    anomaly_min_volume_zscore: float = 3.0,
    anomaly_max_assets: int = 50,
    tokenomist_supply_path: str | Path | None = None,
    etherscan_supply_path: str | Path | None = None,
    arkham_supply_path: str | Path | None = None,
    dune_supply_path: str | Path | None = None,
    universe_path: str | Path | None = None,
    universe_limit: int | None = None,
    universe_live: bool = False,
    universe_fetch_limit: int | None = None,
    cfg: EventDiscoveryConfig | None = None,
    fade_cfg: event_fade.EventFadeConfig | None = None,
    now: datetime | None = None,
    raw_event_transform: Callable[[tuple[RawDiscoveredEvent]], Iterable[RawDiscoveredEvent]] | None = None,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
) -> EventDiscoveryResult:
    return _run_manual_discovery_from_options(locals())


def _run_manual_discovery_from_options(options: Mapping[str, Any]) -> EventDiscoveryResult:
    cfg = options["cfg"] or EventDiscoveryConfig()
    now = _as_utc(options["now"] or datetime.now(timezone.utc))
    start = now - timedelta(hours=cfg.lookback_hours)
    end = now + timedelta(days=cfg.horizon_days)
    provider_warnings: list[str] = []
    raw_events = _load_manual_discovery_raw_events(
        options["event_path"],
        start,
        end,
        provider_health_cfg=options["provider_health_cfg"],
        provider_warnings=provider_warnings,
        local_options=options,
    )
    market_rows = _load_manual_discovery_market_rows(
        now=now,
        market_enrichment_enabled=options["market_enrichment_enabled"],
        anomaly_scanner_enabled=options["anomaly_scanner_enabled"],
        market_enrichment_path=options["market_enrichment_path"],
        market_enrichment_live=options["market_enrichment_live"],
        market_enrichment_fetch_limit=options["market_enrichment_fetch_limit"],
        market_enrichment_fail_soft=options["market_enrichment_fail_soft"],
        universe_path=options["universe_path"],
        universe_fetch_limit=options["universe_fetch_limit"],
        universe_limit=options["universe_limit"],
        provider_health_cfg=options["provider_health_cfg"],
        provider_warnings=provider_warnings,
    )
    raw_events = _apply_manual_discovery_market_and_transform(
        raw_events,
        market_rows,
        now=now,
        anomaly_scanner_enabled=options["anomaly_scanner_enabled"],
        anomaly_min_return_24h=options["anomaly_min_return_24h"],
        anomaly_min_volume_mcap=options["anomaly_min_volume_mcap"],
        anomaly_min_volume_zscore=options["anomaly_min_volume_zscore"],
        anomaly_max_assets=options["anomaly_max_assets"],
        raw_event_transform=options["raw_event_transform"],
    )
    assets = _load_manual_discovery_assets(
        options["alias_path"],
        universe_path=options["universe_path"],
        universe_limit=options["universe_limit"],
        universe_live=options["universe_live"],
        universe_fetch_limit=options["universe_fetch_limit"],
        provider_health_cfg=options["provider_health_cfg"],
        provider_warnings=provider_warnings,
    )
    derivatives = _load_manual_discovery_derivatives(
        assets,
        coinalyze_derivatives_path=options["coinalyze_derivatives_path"],
        coinalyze_live=options["coinalyze_live"],
        coinalyze_api_key=options["coinalyze_api_key"],
        coinalyze_symbols=options["coinalyze_symbols"],
        coinalyze_auto_symbols=options["coinalyze_auto_symbols"],
        coinalyze_base_url=options["coinalyze_base_url"],
        coinalyze_timeout=options["coinalyze_timeout"],
        coinalyze_history_interval=options["coinalyze_history_interval"],
        coinalyze_lookback_hours=options["coinalyze_lookback_hours"],
        coinalyze_convert_to_usd=options["coinalyze_convert_to_usd"],
        provider_health_cfg=options["provider_health_cfg"],
        provider_warnings=provider_warnings,
    )
    supply = _load_manual_discovery_supply(
        tokenomist_supply_path=options["tokenomist_supply_path"],
        etherscan_supply_path=options["etherscan_supply_path"],
        arkham_supply_path=options["arkham_supply_path"],
        dune_supply_path=options["dune_supply_path"],
    )
    return _run_manual_discovery_core(
        raw_events,
        assets,
        cfg=cfg,
        fade_cfg=options["fade_cfg"],
        now=now,
        market_rows=market_rows,
        market_enrichment_enabled=options["market_enrichment_enabled"],
        derivatives_by_asset=derivatives,
        supply_by_asset=supply,
        warnings=provider_warnings,
    )


def _load_manual_discovery_raw_events(
    event_path: str | Path | None,
    start: datetime,
    end: datetime,
    *,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str],
    local_options: Mapping[str, Any],
) -> list[RawDiscoveredEvent]:
    option_keys = (
        "binance_announcements_path", "binance_announcements_live", "binance_announcements_api_key",
        "binance_announcements_api_secret", "binance_announcements_ws_url", "binance_announcements_topic",
        "binance_announcements_recv_window_ms", "binance_announcements_listen_seconds",
        "binance_announcements_max_messages", "bybit_announcements_path", "bybit_announcements_live",
        "bybit_announcements_base_url", "bybit_announcements_locale", "bybit_announcements_type",
        "bybit_announcements_limit", "bybit_announcements_timeout", "coinmarketcal_path", "tokenomist_path",
        "cryptopanic_path", "cryptopanic_live", "cryptopanic_api_token", "cryptopanic_base_url",
        "cryptopanic_plan", "cryptopanic_public", "cryptopanic_following", "cryptopanic_filter",
        "cryptopanic_currencies", "cryptopanic_regions", "cryptopanic_kind", "cryptopanic_search",
        "cryptopanic_timeout", "cryptopanic_request_ledger_path", "cryptopanic_profile",
        "cryptopanic_artifact_namespace", "cryptopanic_weekly_request_limit",
        "cryptopanic_requests_per_run_limit", "cryptopanic_requests_per_day_soft_limit",
        "cryptopanic_min_seconds_between_requests", "cryptopanic_max_pages_per_query",
        "cryptopanic_max_currencies_per_request", "gdelt_path", "gdelt_live", "gdelt_base_url",
        "gdelt_query", "gdelt_max_records", "gdelt_timeout", "project_blog_rss_path",
        "project_blog_rss_live", "project_blog_rss_urls", "project_blog_rss_timeout",
        "project_blog_rss_fail_fast_on_error", "external_ipo_path", "sports_fixtures_path",
        "prediction_market_events_path", "prediction_market_events_live",
        "prediction_market_events_base_url", "prediction_market_events_limit",
        "prediction_market_events_timeout",
    )
    options = {key: local_options[key] for key in option_keys}
    return load_discovery_events(
        event_path,
        start,
        end,
        provider_health_cfg=provider_health_cfg,
        provider_warnings=provider_warnings,
        **options,
    )


def _load_manual_discovery_market_rows(
    *,
    now: datetime,
    market_enrichment_enabled: bool,
    anomaly_scanner_enabled: bool,
    market_enrichment_path: str | Path | None,
    market_enrichment_live: bool,
    market_enrichment_fetch_limit: int,
    market_enrichment_fail_soft: bool,
    universe_path: str | Path | None,
    universe_fetch_limit: int | None,
    universe_limit: int | None,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str],
) -> list[Mapping[str, Any]]:
    if not (market_enrichment_enabled or anomaly_scanner_enabled):
        return []
    market_rows, market_warnings = event_market_enrichment.load_market_enrichment_rows_safe(
        market_enrichment_path if market_enrichment_path is not None else universe_path,
        live=market_enrichment_live,
        fetch_limit=market_enrichment_fetch_limit or universe_fetch_limit or 0,
        limit=universe_limit,
        fail_soft=market_enrichment_fail_soft,
        provider_health_cfg=provider_health_cfg if market_enrichment_fail_soft else None,
        now=now,
    )
    provider_warnings.extend(market_warnings)
    return market_rows


def _apply_manual_discovery_market_and_transform(
    raw_events: list[RawDiscoveredEvent],
    market_rows: list[Mapping[str, Any]],
    *,
    now: datetime,
    anomaly_scanner_enabled: bool,
    anomaly_min_return_24h: float,
    anomaly_min_volume_mcap: float,
    anomaly_min_volume_zscore: float,
    anomaly_max_assets: int,
    raw_event_transform: Callable[[tuple[RawDiscoveredEvent]], Iterable[RawDiscoveredEvent]] | None,
) -> list[RawDiscoveredEvent]:
    if anomaly_scanner_enabled:
        raw_events.extend(event_anomaly_scanner.discover_market_anomalies(
            market_rows,
            cfg=event_anomaly_scanner.EventAnomalyScannerConfig(
                enabled=True,
                min_return_24h=anomaly_min_return_24h,
                min_volume_mcap=anomaly_min_volume_mcap,
                min_volume_zscore=anomaly_min_volume_zscore,
                max_assets=anomaly_max_assets,
            ),
            now=now,
        ))
    if raw_event_transform is None:
        return raw_events
    original_raw_events = tuple(raw_events)
    try:
        return list(raw_event_transform(original_raw_events))
    except Exception as exc:  # noqa: BLE001
        log.warning("Event raw evidence transform failed; continuing without transformed hints: %s", exc)
        return list(original_raw_events)


def _load_manual_discovery_assets(
    alias_path: str | Path | None,
    *,
    universe_path: str | Path | None,
    universe_limit: int | None,
    universe_live: bool,
    universe_fetch_limit: int | None,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str],
) -> list[DiscoveredAsset]:
    return load_discovery_assets(
        alias_path,
        universe_path=universe_path,
        universe_limit=universe_limit,
        universe_live=universe_live,
        universe_fetch_limit=universe_fetch_limit,
        provider_health_cfg=provider_health_cfg,
        provider_warnings=provider_warnings,
    )


def _load_manual_discovery_derivatives(
    assets: list[DiscoveredAsset],
    *,
    coinalyze_derivatives_path: str | Path | None,
    coinalyze_live: bool,
    coinalyze_api_key: str,
    coinalyze_symbols: Iterable[str],
    coinalyze_auto_symbols: bool,
    coinalyze_base_url: str,
    coinalyze_timeout: float,
    coinalyze_history_interval: str,
    coinalyze_lookback_hours: int,
    coinalyze_convert_to_usd: bool,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str],
) -> dict[str, Mapping[str, Any]]:
    return load_derivatives_snapshots(
        coinalyze_derivatives_path,
        coinalyze_live=coinalyze_live,
        coinalyze_api_key=coinalyze_api_key,
        coinalyze_symbols=coinalyze_symbols,
        coinalyze_auto_symbols=coinalyze_auto_symbols,
        coinalyze_base_symbols=_coinalyze_base_symbols(assets),
        coinalyze_base_url=coinalyze_base_url,
        coinalyze_timeout=coinalyze_timeout,
        coinalyze_history_interval=coinalyze_history_interval,
        coinalyze_lookback_hours=coinalyze_lookback_hours,
        coinalyze_convert_to_usd=coinalyze_convert_to_usd,
        provider_health_cfg=provider_health_cfg,
        provider_warnings=provider_warnings,
    )


def _load_manual_discovery_supply(
    *,
    tokenomist_supply_path: str | Path | None,
    etherscan_supply_path: str | Path | None,
    arkham_supply_path: str | Path | None,
    dune_supply_path: str | Path | None,
) -> dict[str, Mapping[str, Any]]:
    return load_supply_snapshots(
        tokenomist_supply_path=tokenomist_supply_path,
        etherscan_supply_path=etherscan_supply_path,
        arkham_supply_path=arkham_supply_path,
        dune_supply_path=dune_supply_path,
    )


def _run_manual_discovery_core(
    raw_events: list[RawDiscoveredEvent],
    assets: list[DiscoveredAsset],
    *,
    cfg: EventDiscoveryConfig,
    fade_cfg: event_fade.EventFadeConfig | None,
    now: datetime,
    market_rows: list[Mapping[str, Any]],
    market_enrichment_enabled: bool,
    derivatives_by_asset: Mapping[str, Mapping[str, Any]],
    supply_by_asset: Mapping[str, Mapping[str, Any]],
    warnings: list[str],
) -> EventDiscoveryResult:
    market = (
        event_market_enrichment.market_snapshots_from_rows(market_rows, now=now)
        if market_enrichment_enabled and market_rows
        else {}
    )
    return run_discovery(
        raw_events,
        assets,
        cfg=cfg,
        fade_cfg=fade_cfg,
        now=now,
        market_by_asset=market,
        derivatives_by_asset=derivatives_by_asset,
        supply_by_asset=supply_by_asset,
        warnings=warnings,
    )


def load_discovery_events(
    event_path: str | Path | None,
    start: datetime,
    end: datetime,
    *,
    binance_announcements_path: str | Path | None = None,
    binance_announcements_live: bool = False,
    binance_announcements_api_key: str = "",
    binance_announcements_api_secret: str = "",
    binance_announcements_ws_url: str = "wss://api.binance.com/sapi/wss",
    binance_announcements_topic: str = "com_announcement_en",
    binance_announcements_recv_window_ms: int = 30000,
    binance_announcements_listen_seconds: float = 5.0,
    binance_announcements_max_messages: int = 20,
    bybit_announcements_path: str | Path | None = None,
    bybit_announcements_live: bool = False,
    bybit_announcements_base_url: str = "https://api.bybit.com",
    bybit_announcements_locale: str = "en-US",
    bybit_announcements_type: str = "new_crypto",
    bybit_announcements_limit: int = 20,
    bybit_announcements_timeout: float = 10.0,
    coinmarketcal_path: str | Path | None = None,
    tokenomist_path: str | Path | None = None,
    cryptopanic_path: str | Path | None = None,
    cryptopanic_live: bool = False,
    cryptopanic_api_token: str = "",
    cryptopanic_base_url: str = "https://cryptopanic.com/api/growth_weekly/v2",
    cryptopanic_plan: str = "growth_weekly",
    cryptopanic_public: bool = True,
    cryptopanic_following: bool = False,
    cryptopanic_filter: str = "",
    cryptopanic_currencies: str = "",
    cryptopanic_regions: str = "en",
    cryptopanic_kind: str = "news",
    cryptopanic_search: str = "",
    cryptopanic_timeout: float = 10.0,
    cryptopanic_request_ledger_path: str | Path | None = None,
    cryptopanic_profile: str = "",
    cryptopanic_artifact_namespace: str = "",
    cryptopanic_weekly_request_limit: int = 600,
    cryptopanic_requests_per_run_limit: int = 20,
    cryptopanic_requests_per_day_soft_limit: int = 80,
    cryptopanic_min_seconds_between_requests: float = 1.0,
    cryptopanic_max_pages_per_query: int = 1,
    cryptopanic_max_currencies_per_request: int = 10,
    gdelt_path: str | Path | None = None,
    gdelt_live: bool = False,
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc",
    gdelt_query: str = "",
    gdelt_max_records: int = 50,
    gdelt_timeout: float = 10.0,
    project_blog_rss_path: str | Path | None = None,
    project_blog_rss_live: bool = False,
    project_blog_rss_urls: Iterable[str] | None = None,
    project_blog_rss_timeout: float = 10.0,
    project_blog_rss_fail_fast_on_error: bool = False,
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
    prediction_market_events_live: bool = False,
    prediction_market_events_base_url: str = "https://gamma-api.polymarket.com/events",
    prediction_market_events_limit: int = 100,
    prediction_market_events_timeout: float = 10.0,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
    provider_warnings: list[str] | None = None,
) -> list[RawDiscoveredEvent]:
    """Load local event fixtures from every configured research source."""
    events: list[RawDiscoveredEvent] = []
    events.extend(_load_core_discovery_events(
        event_path,
        start,
        end,
        binance_announcements_path=binance_announcements_path,
        binance_announcements_live=binance_announcements_live,
        binance_announcements_api_key=binance_announcements_api_key,
        binance_announcements_api_secret=binance_announcements_api_secret,
        binance_announcements_ws_url=binance_announcements_ws_url,
        binance_announcements_topic=binance_announcements_topic,
        binance_announcements_recv_window_ms=binance_announcements_recv_window_ms,
        binance_announcements_listen_seconds=binance_announcements_listen_seconds,
        binance_announcements_max_messages=binance_announcements_max_messages,
        bybit_announcements_path=bybit_announcements_path,
        bybit_announcements_live=bybit_announcements_live,
        bybit_announcements_base_url=bybit_announcements_base_url,
        bybit_announcements_locale=bybit_announcements_locale,
        bybit_announcements_type=bybit_announcements_type,
        bybit_announcements_limit=bybit_announcements_limit,
        bybit_announcements_timeout=bybit_announcements_timeout,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
    ))
    events.extend(_load_news_discovery_events(
        start,
        end,
        cryptopanic_path=cryptopanic_path,
        cryptopanic_live=cryptopanic_live,
        cryptopanic_api_token=cryptopanic_api_token,
        cryptopanic_base_url=cryptopanic_base_url,
        cryptopanic_plan=cryptopanic_plan,
        cryptopanic_public=cryptopanic_public,
        cryptopanic_following=cryptopanic_following,
        cryptopanic_filter=cryptopanic_filter,
        cryptopanic_currencies=cryptopanic_currencies,
        cryptopanic_regions=cryptopanic_regions,
        cryptopanic_kind=cryptopanic_kind,
        cryptopanic_search=cryptopanic_search,
        cryptopanic_timeout=cryptopanic_timeout,
        cryptopanic_request_ledger_path=cryptopanic_request_ledger_path,
        cryptopanic_profile=cryptopanic_profile,
        cryptopanic_artifact_namespace=cryptopanic_artifact_namespace,
        cryptopanic_weekly_request_limit=cryptopanic_weekly_request_limit,
        cryptopanic_requests_per_run_limit=cryptopanic_requests_per_run_limit,
        cryptopanic_requests_per_day_soft_limit=cryptopanic_requests_per_day_soft_limit,
        cryptopanic_min_seconds_between_requests=cryptopanic_min_seconds_between_requests,
        cryptopanic_max_pages_per_query=cryptopanic_max_pages_per_query,
        cryptopanic_max_currencies_per_request=cryptopanic_max_currencies_per_request,
        gdelt_path=gdelt_path,
        gdelt_live=gdelt_live,
        gdelt_base_url=gdelt_base_url,
        gdelt_query=gdelt_query,
        gdelt_max_records=gdelt_max_records,
        gdelt_timeout=gdelt_timeout,
        project_blog_rss_path=project_blog_rss_path,
        project_blog_rss_live=project_blog_rss_live,
        project_blog_rss_urls=project_blog_rss_urls,
        project_blog_rss_timeout=project_blog_rss_timeout,
        project_blog_rss_fail_fast_on_error=project_blog_rss_fail_fast_on_error,
        provider_health_cfg=provider_health_cfg,
        provider_warnings=provider_warnings,
    ))
    events.extend(_load_external_discovery_events(
        start,
        end,
        external_ipo_path=external_ipo_path,
        sports_fixtures_path=sports_fixtures_path,
        prediction_market_events_path=prediction_market_events_path,
        prediction_market_events_live=prediction_market_events_live,
        prediction_market_events_base_url=prediction_market_events_base_url,
        prediction_market_events_limit=prediction_market_events_limit,
        prediction_market_events_timeout=prediction_market_events_timeout,
        provider_health_cfg=provider_health_cfg,
        provider_warnings=provider_warnings,
    ))
    return events


def _load_core_discovery_events(
    event_path: str | Path | None,
    start: datetime,
    end: datetime,
    *,
    binance_announcements_path: str | Path | None,
    binance_announcements_live: bool,
    binance_announcements_api_key: str,
    binance_announcements_api_secret: str,
    binance_announcements_ws_url: str,
    binance_announcements_topic: str,
    binance_announcements_recv_window_ms: int,
    binance_announcements_listen_seconds: float,
    binance_announcements_max_messages: int,
    bybit_announcements_path: str | Path | None,
    bybit_announcements_live: bool,
    bybit_announcements_base_url: str,
    bybit_announcements_locale: str,
    bybit_announcements_type: str,
    bybit_announcements_limit: int,
    bybit_announcements_timeout: float,
    coinmarketcal_path: str | Path | None,
    tokenomist_path: str | Path | None,
) -> list[RawDiscoveredEvent]:
    events: list[RawDiscoveredEvent] = []
    if event_path:
        events.extend(ManualJsonEventProvider(event_path).fetch_events(start, end))
    if binance_announcements_path or binance_announcements_live:
        events.extend(BinanceAnnouncementProvider(
            binance_announcements_path,
            live_enabled=binance_announcements_live,
            api_key=binance_announcements_api_key,
            api_secret=binance_announcements_api_secret,
            ws_url=binance_announcements_ws_url,
            topic=binance_announcements_topic,
            recv_window_ms=binance_announcements_recv_window_ms,
            listen_seconds=binance_announcements_listen_seconds,
            max_messages=binance_announcements_max_messages,
        ).fetch_events(start, end))
    if bybit_announcements_path or bybit_announcements_live:
        events.extend(BybitAnnouncementProvider(
            bybit_announcements_path,
            live_enabled=bybit_announcements_live,
            base_url=bybit_announcements_base_url,
            locale=bybit_announcements_locale,
            announcement_type=bybit_announcements_type,
            limit=bybit_announcements_limit,
            timeout=bybit_announcements_timeout,
        ).fetch_events(start, end))
    if coinmarketcal_path:
        events.extend(CoinMarketCalProvider(coinmarketcal_path).fetch_events(start, end))
    if tokenomist_path:
        events.extend(TokenomistProvider(tokenomist_path).fetch_events(start, end))
    return events


def _load_news_discovery_events(
    start: datetime,
    end: datetime,
    *,
    cryptopanic_path: str | Path | None,
    cryptopanic_live: bool,
    cryptopanic_api_token: str,
    cryptopanic_base_url: str,
    cryptopanic_plan: str,
    cryptopanic_public: bool,
    cryptopanic_following: bool,
    cryptopanic_filter: str,
    cryptopanic_currencies: str,
    cryptopanic_regions: str,
    cryptopanic_kind: str,
    cryptopanic_search: str,
    cryptopanic_timeout: float,
    cryptopanic_request_ledger_path: str | Path | None,
    cryptopanic_profile: str,
    cryptopanic_artifact_namespace: str,
    cryptopanic_weekly_request_limit: int,
    cryptopanic_requests_per_run_limit: int,
    cryptopanic_requests_per_day_soft_limit: int,
    cryptopanic_min_seconds_between_requests: float,
    cryptopanic_max_pages_per_query: int,
    cryptopanic_max_currencies_per_request: int,
    gdelt_path: str | Path | None,
    gdelt_live: bool,
    gdelt_base_url: str,
    gdelt_query: str,
    gdelt_max_records: int,
    gdelt_timeout: float,
    project_blog_rss_path: str | Path | None,
    project_blog_rss_live: bool,
    project_blog_rss_urls: Iterable[str] | None,
    project_blog_rss_timeout: float,
    project_blog_rss_fail_fast_on_error: bool,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str] | None,
) -> list[RawDiscoveredEvent]:
    events: list[RawDiscoveredEvent] = []
    if cryptopanic_path or cryptopanic_live:
        provider = CryptoPanicProvider(
            cryptopanic_path,
            live_enabled=cryptopanic_live,
            api_token=cryptopanic_api_token,
            base_url=cryptopanic_base_url,
            plan=cryptopanic_plan,
            public=cryptopanic_public,
            following=cryptopanic_following,
            filter_name=cryptopanic_filter,
            currencies=cryptopanic_currencies,
            regions=cryptopanic_regions,
            kind=cryptopanic_kind,
            search=cryptopanic_search,
            timeout=cryptopanic_timeout,
            request_ledger_path=cryptopanic_request_ledger_path,
            profile=cryptopanic_profile,
            artifact_namespace=cryptopanic_artifact_namespace,
            weekly_request_limit=cryptopanic_weekly_request_limit,
            requests_per_run_limit=cryptopanic_requests_per_run_limit,
            requests_per_day_soft_limit=cryptopanic_requests_per_day_soft_limit,
            min_seconds_between_requests=cryptopanic_min_seconds_between_requests,
            max_pages_per_query=cryptopanic_max_pages_per_query,
            max_currencies_per_request=cryptopanic_max_currencies_per_request,
        )
        events.extend(_fetch_provider_events(
            provider,
            start,
            end,
            live=cryptopanic_live,
            health_cfg=provider_health_cfg,
            warnings=provider_warnings,
        ))
    if gdelt_path or gdelt_live:
        provider = GdeltProvider(
            gdelt_path,
            live_enabled=gdelt_live,
            base_url=gdelt_base_url,
            query=gdelt_query or DEFAULT_GDELT_QUERY,
            max_records=gdelt_max_records,
            timeout=gdelt_timeout,
        )
        events.extend(_fetch_provider_events(
            provider,
            start,
            end,
            live=gdelt_live,
            health_cfg=provider_health_cfg,
            warnings=provider_warnings,
        ))
    if project_blog_rss_path or project_blog_rss_live:
        provider = ProjectBlogRssProvider(
            project_blog_rss_path,
            live_enabled=project_blog_rss_live,
            feed_urls=project_blog_rss_urls,
            timeout=project_blog_rss_timeout,
            fail_fast_on_error=project_blog_rss_fail_fast_on_error,
        )
        events.extend(_fetch_provider_events(
            provider,
            start,
            end,
            live=project_blog_rss_live,
            health_cfg=provider_health_cfg,
            warnings=provider_warnings,
        ))
    return events


def _load_external_discovery_events(
    start: datetime,
    end: datetime,
    *,
    external_ipo_path: str | Path | None,
    sports_fixtures_path: str | Path | None,
    prediction_market_events_path: str | Path | None,
    prediction_market_events_live: bool,
    prediction_market_events_base_url: str,
    prediction_market_events_limit: int,
    prediction_market_events_timeout: float,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None,
    provider_warnings: list[str] | None,
) -> list[RawDiscoveredEvent]:
    events: list[RawDiscoveredEvent] = []
    if external_ipo_path:
        events.extend(ExternalIpoProvider(external_ipo_path).fetch_events(start, end))
    if sports_fixtures_path:
        events.extend(SportsFixturesProvider(sports_fixtures_path).fetch_events(start, end))
    if prediction_market_events_path or prediction_market_events_live:
        provider = PredictionMarketEventsProvider(
            prediction_market_events_path,
            live_enabled=prediction_market_events_live,
            base_url=prediction_market_events_base_url,
            limit=prediction_market_events_limit,
            timeout=prediction_market_events_timeout,
        )
        events.extend(_fetch_provider_events(
            provider,
            start,
            end,
            live=prediction_market_events_live,
            health_cfg=provider_health_cfg,
            warnings=provider_warnings,
        ))
    return events


def load_discovery_assets(
    alias_path: str | Path | None,
    *,
    universe_path: str | Path | None = None,
    universe_limit: int | None = None,
    universe_live: bool = False,
    universe_fetch_limit: int | None = None,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
    provider_warnings: list[str] | None = None,
) -> list[DiscoveredAsset]:
    """Load manual aliases plus an optional cleaned CoinGecko-style universe."""
    assets: list[DiscoveredAsset] = []
    assets.extend(load_asset_aliases(alias_path))
    if universe_path:
        assets.extend(CoinGeckoUniverseProvider(universe_path, limit=universe_limit).fetch_assets())
    if universe_live:
        provider = CoinGeckoUniverseProvider(
            None,
            limit=universe_limit,
            live_enabled=True,
            live_fetch_limit=universe_fetch_limit,
        )
        if provider_health_cfg is not None:
            provider = event_provider_health.HealthCheckedUniverseProvider(
                provider,
                cfg=provider_health_cfg,
                provider_kind="enrichment",
            )
        fetched = provider.fetch_assets()
        assets.extend(fetched)
        _extend_warnings(provider_warnings, getattr(provider, "last_warnings", ()))
    return merge_discovered_assets(assets)
