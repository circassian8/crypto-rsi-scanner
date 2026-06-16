"""Research-only event discovery pipeline for event-fade candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_fade
from .derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
from .event_classification import classify_event_asset
from .event_models import (
    DiscoveredAsset,
    DiscoveredEventFadeCandidate,
    EventAssetLink,
    EventClassification,
    EventDiscoveryResult,
    NormalizedEvent,
    RawDiscoveredEvent,
)
from .event_providers.binance_announcements import BinanceAnnouncementProvider
from .event_providers.bybit_announcements import BybitAnnouncementProvider
from .event_providers.coinmarketcal import CoinMarketCalProvider
from .event_providers.coingecko_universe import CoinGeckoUniverseProvider
from .event_providers.cryptopanic import CryptoPanicProvider
from .event_providers.external_ipo import ExternalIpoProvider
from .event_providers.gdelt import DEFAULT_GDELT_QUERY, GdeltProvider
from .event_providers.manual_json import ManualJsonEventProvider, parse_datetime
from .event_providers.prediction_market_events import PredictionMarketEventsProvider
from .event_providers.project_blog_rss import ProjectBlogRssProvider
from .event_providers.sports_fixtures import SportsFixturesProvider
from .event_providers.tokenomist import TokenomistProvider
from .event_resolver import clean_text, load_asset_aliases, resolve_event_assets
from .supply_providers.arkham import ArkhamSupplyProvider
from .supply_providers.dune import DuneSupplyProvider
from .supply_providers.etherscan import EtherscanSupplyProvider
from .supply_providers.tokenomist import TokenomistSupplyProvider

log = logging.getLogger(__name__)

VALIDATION_SAMPLE_SCHEMA_VERSION = "event_fade_validation_sample_v1"
VALIDATION_SAMPLE_FIELDS = (
    "schema_version",
    "exported_at",
    "row_type",
    "event_id",
    "raw_ids",
    "raw_providers",
    "raw_titles",
    "raw_content_hashes",
    "event_name",
    "event_type",
    "external_asset",
    "event_time",
    "event_time_confidence",
    "first_seen_time",
    "raw_published_at",
    "raw_fetched_at",
    "published_at_min",
    "published_at_max",
    "fetched_at_min",
    "fetched_at_max",
    "source",
    "source_urls",
    "source_count",
    "asset_coin_id",
    "asset_symbol",
    "asset_name",
    "link_confidence",
    "match_reason",
    "link_evidence",
    "relationship_type",
    "is_proxy_narrative",
    "is_direct_beneficiary",
    "classifier_confidence",
    "classifier_version",
    "classification_reason",
    "classification_evidence",
    "fade_state",
    "signal_type",
    "fade_score",
    "signal_confidence",
    "eligible",
    "reason_codes",
    "warnings",
    "component_scores",
    "data_quality",
    "missing_data",
    "price",
    "market_cap",
    "volume_24h",
    "spot_volume_24h",
    "return_24h",
    "return_72h",
    "return_7d",
    "volume_zscore_24h",
    "spread_bps",
    "order_book_depth_2pct",
    "perp_available",
    "open_interest",
    "open_interest_24h_change_pct",
    "open_interest_to_market_cap",
    "funding_rate_8h",
    "funding_rate_percentile",
    "futures_volume_24h",
    "perp_spot_volume_ratio",
    "liquidations_24h",
    "long_short_ratio",
    "basis",
    "large_holder_exchange_inflow",
    "cex_inflow_amount",
    "cex_inflow_pct_supply",
    "unlock_amount",
    "unlock_pct_circulating",
    "top_holder_concentration",
    "team_or_mm_wallet_activity",
    "admin_or_mint_risk",
    "rsi_daily",
    "rsi_4h",
    "rsi_weekly",
    "target_overbought_score",
    "btc_risk_on_score",
    "rsi_rollover_confirmed",
    "bearish_rsi_divergence",
    "event_vwap",
    "price_below_event_vwap",
    "failed_reclaim_event_vwap",
    "lower_high_confirmed",
    "first_support_broken",
    "post_event_high",
    "post_event_lower_high",
    "entry_reference_price",
    "invalidation_level",
    "trigger_observed_at",
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_24h",
    "post_event_return_72h",
    "post_event_return_7d",
    "event_time_entry_price",
    "event_time_max_adverse_excursion",
    "event_time_max_favorable_excursion",
    "event_time_post_event_return_24h",
    "event_time_post_event_return_72h",
    "event_time_post_event_return_7d",
    "review_status",
    "human_label",
    "human_notes",
)


@dataclass(frozen=True)
class EventDiscoveryConfig:
    min_link_confidence: float = 0.80
    min_classifier_confidence: float = 0.80
    lookback_hours: int = 72
    horizon_days: int = 14


def normalize_raw_event(raw: RawDiscoveredEvent) -> NormalizedEvent:
    payload = raw.raw_json or {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    title = raw.title.strip()
    body = raw.body or ""
    event_name = str(event_payload.get("event_name") or payload.get("event_name") or title)
    event_type = str(event_payload.get("event_type") or payload.get("event_type") or _infer_event_type(title, body))
    event_time = parse_datetime(event_payload.get("event_time") or payload.get("event_time"))
    event_time_confidence_raw = event_payload.get("event_time_confidence", payload.get("event_time_confidence"))
    event_time_confidence = (
        float(event_time_confidence_raw) if event_time_confidence_raw is not None else (1.0 if event_time else 0.0)
    )
    first_seen = raw.published_at or raw.fetched_at
    external_asset = event_payload.get("external_asset", payload.get("external_asset"))
    confidence_raw = event_payload.get("confidence", payload.get("confidence"))
    confidence = float(confidence_raw) if confidence_raw is not None else raw.source_confidence
    description = str(event_payload.get("description") or payload.get("description") or body or "")
    event_id = str(event_payload.get("event_id") or payload.get("event_id") or _event_id(
        event_name,
        event_type,
        event_time,
        external_asset,
    ))
    return NormalizedEvent(
        event_id=event_id,
        raw_ids=(raw.raw_id,),
        event_name=event_name,
        event_type=event_type,
        event_time=event_time,
        event_time_confidence=event_time_confidence,
        first_seen_time=first_seen,
        source=raw.provider,
        source_urls=tuple(u for u in (raw.source_url,) if u),
        external_asset=str(external_asset) if external_asset else None,
        description=description or None,
        confidence=max(0.0, min(1.0, confidence)),
    )


def dedupe_events(events: Iterable[NormalizedEvent]) -> list[NormalizedEvent]:
    grouped: dict[tuple[str, str, str, str], list[NormalizedEvent]] = {}
    for event in events:
        key = (
            clean_text(event.event_name),
            event.event_type,
            event.event_time.isoformat() if event.event_time else "",
            clean_text(event.external_asset),
        )
        grouped.setdefault(key, []).append(event)

    out: list[NormalizedEvent] = []
    for key, group in grouped.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        first = min(group, key=lambda e: e.first_seen_time)
        raw_ids = tuple(sorted({raw_id for event in group for raw_id in event.raw_ids}))
        urls = tuple(sorted({url for event in group for url in event.source_urls}))
        confidence = min(1.0, max(event.confidence for event in group) + 0.05 * (len(group) - 1))
        out.append(NormalizedEvent(
            event_id=_event_id(*key),
            raw_ids=raw_ids,
            event_name=first.event_name,
            event_type=first.event_type,
            event_time=first.event_time,
            event_time_confidence=max(event.event_time_confidence for event in group),
            first_seen_time=first.first_seen_time,
            source="+".join(sorted({event.source for event in group})),
            source_urls=urls,
            external_asset=first.external_asset,
            description=first.description,
            confidence=confidence,
        ))
    return sorted(out, key=lambda e: (e.event_time or e.first_seen_time, e.event_name))


def run_discovery(
    raw_events: Iterable[RawDiscoveredEvent],
    assets: Iterable[DiscoveredAsset],
    *,
    cfg: EventDiscoveryConfig | None = None,
    fade_cfg: event_fade.EventFadeConfig | None = None,
    now: datetime | None = None,
    derivatives_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    supply_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
) -> EventDiscoveryResult:
    cfg = cfg or EventDiscoveryConfig()
    fade_cfg = fade_cfg or event_fade.EventFadeConfig()
    now = _as_utc(now or datetime.now(timezone.utc))
    raw_tuple = tuple(raw_events)
    assets_tuple = tuple(assets)
    raw_by_id = {raw.raw_id: raw for raw in raw_tuple}
    normalized = tuple(dedupe_events(normalize_raw_event(raw) for raw in raw_tuple))
    links: list[EventAssetLink] = []
    classifications: list[EventClassification] = []
    candidates: list[DiscoveredEventFadeCandidate] = []

    by_coin = {asset.coin_id: asset for asset in assets_tuple}
    for event in normalized:
        event_links = resolve_event_assets(event, assets_tuple, min_confidence=cfg.min_link_confidence)
        links.extend(event_links)
        for link in event_links:
            asset = by_coin.get(link.coin_id)
            if asset is None:
                continue
            classification = classify_event_asset(event, asset, link)
            classifications.append(classification)
            fade_candidate = build_fade_candidate(
                event,
                asset,
                classification,
                raw_by_id,
                now,
                derivatives_by_asset=derivatives_by_asset,
                supply_by_asset=supply_by_asset,
            )
            fade_signal = event_fade.generate_fade_signal(fade_candidate, fade_cfg, now) if fade_candidate else None
            candidates.append(DiscoveredEventFadeCandidate(
                event=event,
                asset=asset,
                link=link,
                classification=classification,
                fade_candidate=fade_candidate,
                fade_signal=fade_signal,
                data_quality={
                    "source_count": len(event.raw_ids),
                    "has_event_time": event.event_time is not None,
                    "link_confidence": link.link_confidence,
                    "classifier_confidence": classification.confidence,
                    "classifier_pass": classification.confidence >= cfg.min_classifier_confidence,
                    "has_market_snapshot": fade_candidate is not None and fade_candidate.market.price > 0,
                    "has_derivatives_snapshot": fade_candidate is not None and fade_candidate.derivatives is not None,
                    "has_supply_snapshot": fade_candidate is not None and fade_candidate.supply is not None,
                    "has_technical_snapshot": fade_candidate is not None and fade_candidate.technical is not None,
                },
            ))
    return EventDiscoveryResult(
        raw_events=raw_tuple,
        normalized_events=normalized,
        links=tuple(links),
        classifications=tuple(classifications),
        candidates=tuple(candidates),
    )


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
    cryptopanic_base_url: str = "https://cryptopanic.com/api/v1/posts/",
    cryptopanic_public: bool = True,
    cryptopanic_filter: str = "",
    cryptopanic_currencies: str = "",
    cryptopanic_regions: str = "",
    cryptopanic_kind: str = "",
    cryptopanic_search: str = "",
    cryptopanic_timeout: float = 10.0,
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
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
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
) -> EventDiscoveryResult:
    cfg = cfg or EventDiscoveryConfig()
    now = _as_utc(now or datetime.now(timezone.utc))
    start = now - timedelta(hours=cfg.lookback_hours)
    end = now + timedelta(days=cfg.horizon_days)
    raw_events = load_discovery_events(
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
        cryptopanic_path=cryptopanic_path,
        cryptopanic_live=cryptopanic_live,
        cryptopanic_api_token=cryptopanic_api_token,
        cryptopanic_base_url=cryptopanic_base_url,
        cryptopanic_public=cryptopanic_public,
        cryptopanic_filter=cryptopanic_filter,
        cryptopanic_currencies=cryptopanic_currencies,
        cryptopanic_regions=cryptopanic_regions,
        cryptopanic_kind=cryptopanic_kind,
        cryptopanic_search=cryptopanic_search,
        cryptopanic_timeout=cryptopanic_timeout,
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
        external_ipo_path=external_ipo_path,
        sports_fixtures_path=sports_fixtures_path,
        prediction_market_events_path=prediction_market_events_path,
    )
    assets = load_discovery_assets(
        alias_path,
        universe_path=universe_path,
        universe_limit=universe_limit,
        universe_live=universe_live,
        universe_fetch_limit=universe_fetch_limit,
    )
    derivatives = load_derivatives_snapshots(
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
    )
    supply = load_supply_snapshots(
        tokenomist_supply_path=tokenomist_supply_path,
        etherscan_supply_path=etherscan_supply_path,
        arkham_supply_path=arkham_supply_path,
        dune_supply_path=dune_supply_path,
    )
    return run_discovery(
        raw_events,
        assets,
        cfg=cfg,
        fade_cfg=fade_cfg,
        now=now,
        derivatives_by_asset=derivatives,
        supply_by_asset=supply,
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
    cryptopanic_base_url: str = "https://cryptopanic.com/api/v1/posts/",
    cryptopanic_public: bool = True,
    cryptopanic_filter: str = "",
    cryptopanic_currencies: str = "",
    cryptopanic_regions: str = "",
    cryptopanic_kind: str = "",
    cryptopanic_search: str = "",
    cryptopanic_timeout: float = 10.0,
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
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
) -> list[RawDiscoveredEvent]:
    """Load local event fixtures from every configured research source."""
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
    if cryptopanic_path or cryptopanic_live:
        events.extend(CryptoPanicProvider(
            cryptopanic_path,
            live_enabled=cryptopanic_live,
            api_token=cryptopanic_api_token,
            base_url=cryptopanic_base_url,
            public=cryptopanic_public,
            filter_name=cryptopanic_filter,
            currencies=cryptopanic_currencies,
            regions=cryptopanic_regions,
            kind=cryptopanic_kind,
            search=cryptopanic_search,
            timeout=cryptopanic_timeout,
        ).fetch_events(start, end))
    if gdelt_path or gdelt_live:
        events.extend(GdeltProvider(
            gdelt_path,
            live_enabled=gdelt_live,
            base_url=gdelt_base_url,
            query=gdelt_query or DEFAULT_GDELT_QUERY,
            max_records=gdelt_max_records,
            timeout=gdelt_timeout,
        ).fetch_events(start, end))
    if project_blog_rss_path or project_blog_rss_live:
        events.extend(ProjectBlogRssProvider(
            project_blog_rss_path,
            live_enabled=project_blog_rss_live,
            feed_urls=project_blog_rss_urls,
            timeout=project_blog_rss_timeout,
        ).fetch_events(start, end))
    if external_ipo_path:
        events.extend(ExternalIpoProvider(external_ipo_path).fetch_events(start, end))
    if sports_fixtures_path:
        events.extend(SportsFixturesProvider(sports_fixtures_path).fetch_events(start, end))
    if prediction_market_events_path:
        events.extend(PredictionMarketEventsProvider(prediction_market_events_path).fetch_events(start, end))
    return events


def load_discovery_assets(
    alias_path: str | Path | None,
    *,
    universe_path: str | Path | None = None,
    universe_limit: int | None = None,
    universe_live: bool = False,
    universe_fetch_limit: int | None = None,
) -> list[DiscoveredAsset]:
    """Load manual aliases plus an optional cleaned CoinGecko-style universe."""
    assets: list[DiscoveredAsset] = []
    assets.extend(load_asset_aliases(alias_path))
    if universe_path:
        assets.extend(CoinGeckoUniverseProvider(universe_path, limit=universe_limit).fetch_assets())
    if universe_live:
        assets.extend(CoinGeckoUniverseProvider(
            None,
            limit=universe_limit,
            live_enabled=True,
            live_fetch_limit=universe_fetch_limit,
        ).fetch_assets())
    return merge_discovered_assets(assets)


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
) -> dict[str, dict[str, Any]]:
    """Load optional local and/or live derivatives snapshots for event-candidate enrichment."""
    snapshots: dict[str, dict[str, Any]] = {}
    if coinalyze_derivatives_path:
        snapshots.update(CoinalyzeDerivativesProvider(coinalyze_derivatives_path).fetch_snapshots())
    if coinalyze_live:
        snapshots.update(CoinalyzeDerivativesProvider(
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
        ).fetch_snapshots())
    return snapshots


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
    derivatives_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    supply_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
) -> event_fade.FadeCandidate:
    raw = raw_by_id.get(event.raw_ids[0]) if event.raw_ids else None
    payload = raw.raw_json if raw and raw.raw_json else {}
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
        confidence=min(event.confidence, classification.confidence),
        external_asset=event.external_asset,
        is_proxy_narrative=classification.is_proxy_narrative,
        is_direct_beneficiary=classification.is_direct_beneficiary,
        notes=classification.reason,
    )
    market = _market_snapshot(asset, payload.get("market"), now)
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


def format_discovery_report(result: EventDiscoveryResult) -> str:
    rows = [
        "=" * 72,
        "EVENT DISCOVERY REPORT (research-only; no alerts, DB writes, or trades)",
        "=" * 72,
        f"Raw events: {len(result.raw_events)} · normalized: {len(result.normalized_events)} · "
        f"links: {len(result.links)} · candidates: {len(result.candidates)}",
        "",
        "EVENT RADAR",
    ]
    if not result.normalized_events:
        rows.append("  No discovered events.")
    for event in result.normalized_events:
        event_time = event.event_time.isoformat() if event.event_time else "unknown"
        rows.append(
            f"  {event.event_type:<18} {event_time:<25} {event.event_name} "
            f"(conf={event.confidence:.2f}, sources={len(event.raw_ids)})"
        )

    rows.append("")
    rows.append("ASSET CLASSIFICATIONS")
    if not result.candidates:
        rows.append("  No high-confidence asset links.")
    for candidate in result.candidates:
        cls = candidate.classification
        signal = candidate.fade_signal.signal_type.value if candidate.fade_signal else "NO_TRADE"
        state = candidate.fade_signal.state.value if candidate.fade_signal else "DISCOVERED"
        score = candidate.fade_signal.fade_score if candidate.fade_signal else 0
        relation = cls.relationship_type
        proxy = "proxy" if cls.is_proxy_narrative else "direct" if cls.is_direct_beneficiary else "ambiguous"
        derivatives = "yes" if candidate.data_quality.get("has_derivatives_snapshot") else "no"
        supply = "yes" if candidate.data_quality.get("has_supply_snapshot") else "no"
        rows.append(
            f"  {candidate.asset.symbol:<12} {relation:<22} {proxy:<9} "
            f"link={candidate.link.link_confidence:.2f} cls={cls.confidence:.2f} "
            f"score={score:<3} deriv={derivatives:<3} supply={supply:<3} signal={signal}/{state}"
        )
        rows.append(f"    event: {candidate.event.event_name}")
        rows.append(f"    reason: {cls.reason}")
    return "\n".join(rows)


def format_event_fade_auto_report(result: EventDiscoveryResult) -> str:
    """Format a research-only event-fade report grouped by candidate lifecycle."""
    buckets: dict[str, list[DiscoveredEventFadeCandidate]] = {
        "PROXY WATCHLIST": [],
        "BLOWOFF RISK": [],
        "EVENT PASSED": [],
        "ARMED": [],
        "TRIGGERED": [],
        "REJECTED / NO TRADE": [],
        "AMBIGUOUS": [],
    }
    for candidate in result.candidates:
        buckets[_auto_report_bucket(candidate)].append(candidate)

    rows = [
        "=" * 76,
        "EVENT FADE AUTO REPORT (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 76,
        f"Raw events: {len(result.raw_events)} · normalized: {len(result.normalized_events)} · "
        f"links: {len(result.links)} · candidates: {len(result.candidates)}",
        "",
        "EVENT RADAR",
    ]
    if not result.normalized_events:
        rows.append("  No discovered events.")
    for event in result.normalized_events:
        event_time = event.event_time.isoformat() if event.event_time else "unknown"
        first_seen = event.first_seen_time.isoformat()
        rows.append(
            f"  {event.event_type:<22} time={event_time:<25} first_seen={first_seen:<25} "
            f"conf={event.confidence:.2f} sources={len(event.raw_ids)}"
        )
        rows.append(f"    event: {event.event_name}")
        if event.source_urls:
            rows.append(f"    sources: {', '.join(event.source_urls[:3])}")

    for section in (
        "PROXY WATCHLIST",
        "BLOWOFF RISK",
        "EVENT PASSED",
        "ARMED",
        "TRIGGERED",
        "REJECTED / NO TRADE",
        "AMBIGUOUS",
    ):
        rows.append("")
        rows.append(section)
        candidates = sorted(buckets[section], key=_auto_report_sort_key)
        if not candidates:
            rows.append("  None.")
            continue
        for candidate in candidates:
            rows.extend(_format_auto_candidate(candidate))
    return "\n".join(rows)


def _auto_report_bucket(candidate: DiscoveredEventFadeCandidate) -> str:
    cls = candidate.classification
    signal = candidate.fade_signal
    signal_type = signal.signal_type if signal else event_fade.FadeSignalType.NO_TRADE
    state = signal.state if signal else event_fade.FadeState.DISCOVERED
    if signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED or state == event_fade.FadeState.TRIGGERED_SHORT:
        return "TRIGGERED"
    if signal_type == event_fade.FadeSignalType.ARMED or state == event_fade.FadeState.ARMED:
        return "ARMED"
    if state == event_fade.FadeState.EVENT_PASSED:
        return "EVENT PASSED"
    if state == event_fade.FadeState.BLOWOFF_RISK:
        return "BLOWOFF RISK"
    if _is_ambiguous_candidate(candidate):
        return "AMBIGUOUS"
    if (
        cls.is_proxy_narrative
        and not cls.is_direct_beneficiary
        and state in {
            event_fade.FadeState.WATCHLISTED,
            event_fade.FadeState.PRE_EVENT_HYPE,
        }
    ):
        return "PROXY WATCHLIST"
    return "REJECTED / NO TRADE"


def _is_ambiguous_candidate(candidate: DiscoveredEventFadeCandidate) -> bool:
    cls = candidate.classification
    return cls.relationship_type == "ambiguous" or (
        not cls.is_proxy_narrative and not cls.is_direct_beneficiary
    )


def _auto_report_sort_key(candidate: DiscoveredEventFadeCandidate) -> tuple[int, str, str]:
    signal = candidate.fade_signal
    score = signal.fade_score if signal else 0
    event_time = candidate.event.event_time.isoformat() if candidate.event.event_time else "9999"
    return (-score, event_time, candidate.asset.symbol)


def _format_auto_candidate(candidate: DiscoveredEventFadeCandidate) -> list[str]:
    cls = candidate.classification
    signal = candidate.fade_signal
    fade_candidate = candidate.fade_candidate
    signal_type = signal.signal_type.value if signal else event_fade.FadeSignalType.NO_TRADE.value
    state = signal.state.value if signal else event_fade.FadeState.DISCOVERED.value
    score = signal.fade_score if signal else 0
    event_time = candidate.event.event_time.isoformat() if candidate.event.event_time else "unknown"
    first_seen = candidate.event.first_seen_time.isoformat()
    relation = cls.relationship_type
    relationship = "proxy" if cls.is_proxy_narrative else "direct" if cls.is_direct_beneficiary else "ambiguous"
    rows = [
        (
            f"  {candidate.asset.symbol:<12} coin={candidate.asset.coin_id:<18} "
            f"signal={signal_type}/{state} score={score:>3}/100 rel={relationship}/{relation}"
        ),
        f"    event: {candidate.event.event_name}",
        f"    time: {event_time} · first_seen: {first_seen}",
        f"    confidence: link={candidate.link.link_confidence:.2f} classifier={cls.confidence:.2f}",
    ]
    missing = _missing_data(candidate)
    if missing:
        rows.append("    missing: " + ", ".join(missing))
    if signal and signal.reason_codes:
        rows.append("    reasons: " + ", ".join(signal.reason_codes))
    if signal and signal.invalidation_level is not None:
        rows.append(f"    invalidation: {signal.invalidation_level:g}")
    elif fade_candidate and fade_candidate.invalidation_level is not None:
        rows.append(f"    invalidation: {fade_candidate.invalidation_level:g}")
    if signal and signal.warnings:
        rows.append("    warnings: " + ", ".join(signal.warnings))
    if candidate.event.source_urls:
        rows.append("    sources: " + ", ".join(candidate.event.source_urls[:3]))
    rows.append("    classification: " + cls.reason)
    return rows


def _missing_data(candidate: DiscoveredEventFadeCandidate) -> list[str]:
    checks = (
        ("event_time", candidate.data_quality.get("has_event_time")),
        ("market", candidate.data_quality.get("has_market_snapshot")),
        ("derivatives", candidate.data_quality.get("has_derivatives_snapshot")),
        ("supply", candidate.data_quality.get("has_supply_snapshot")),
        ("technical", candidate.data_quality.get("has_technical_snapshot")),
    )
    return [name for name, present in checks if not present]


def event_fade_validation_sample_rows(
    result: EventDiscoveryResult,
    *,
    exported_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build point-in-time review rows for the event-fade validation sample."""
    exported = _as_utc(exported_at or datetime.now(timezone.utc))
    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    rows: list[dict[str, Any]] = []
    for candidate in result.candidates:
        rows.append(_validation_sample_row(candidate, raw_by_id, exported))
    return rows


def format_validation_sample_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")) for row in rows)


def format_validation_sample_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    from io import StringIO

    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(VALIDATION_SAMPLE_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_cell(row.get(field)) for field in VALIDATION_SAMPLE_FIELDS})
    return out.getvalue()


def write_validation_sample(rows: Iterable[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path).expanduser()
    data = list(rows)
    if out.suffix.casefold() == ".csv":
        text = format_validation_sample_csv(data)
    else:
        text = format_validation_sample_jsonl(data)
        if text:
            text += "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def _validation_sample_row(
    candidate: DiscoveredEventFadeCandidate,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    exported_at: datetime,
) -> dict[str, Any]:
    raw_events = [raw_by_id[raw_id] for raw_id in candidate.event.raw_ids if raw_id in raw_by_id]
    signal = candidate.fade_signal
    fade_candidate = candidate.fade_candidate
    market = fade_candidate.market if fade_candidate else None
    derivatives = fade_candidate.derivatives if fade_candidate else None
    supply = fade_candidate.supply if fade_candidate else None
    rsi = fade_candidate.rsi if fade_candidate else None
    technical = fade_candidate.technical if fade_candidate else None
    vector = (
        event_fade.event_fade_feature_vector(fade_candidate, now=signal.timestamp if signal else None)
        if fade_candidate
        else {}
    )
    row = {
        "schema_version": VALIDATION_SAMPLE_SCHEMA_VERSION,
        "exported_at": _iso(exported_at),
        "row_type": "candidate",
        "event_id": candidate.event.event_id,
        "raw_ids": list(candidate.event.raw_ids),
        "raw_providers": _unique(raw.provider for raw in raw_events),
        "raw_titles": [raw.title for raw in raw_events],
        "raw_content_hashes": [raw.content_hash for raw in raw_events],
        "event_name": candidate.event.event_name,
        "event_type": candidate.event.event_type,
        "external_asset": candidate.event.external_asset,
        "event_time": _iso(candidate.event.event_time),
        "event_time_confidence": candidate.event.event_time_confidence,
        "first_seen_time": _iso(candidate.event.first_seen_time),
        "raw_published_at": [_iso(raw.published_at) for raw in raw_events],
        "raw_fetched_at": [_iso(raw.fetched_at) for raw in raw_events],
        "published_at_min": _iso(_min_dt(raw.published_at for raw in raw_events)),
        "published_at_max": _iso(_max_dt(raw.published_at for raw in raw_events)),
        "fetched_at_min": _iso(_min_dt(raw.fetched_at for raw in raw_events)),
        "fetched_at_max": _iso(_max_dt(raw.fetched_at for raw in raw_events)),
        "source": candidate.event.source,
        "source_urls": list(candidate.event.source_urls),
        "source_count": candidate.data_quality.get("source_count"),
        "asset_coin_id": candidate.asset.coin_id,
        "asset_symbol": candidate.asset.symbol,
        "asset_name": candidate.asset.name,
        "link_confidence": candidate.link.link_confidence,
        "match_reason": candidate.link.match_reason,
        "link_evidence": list(candidate.link.evidence),
        "relationship_type": candidate.classification.relationship_type,
        "is_proxy_narrative": candidate.classification.is_proxy_narrative,
        "is_direct_beneficiary": candidate.classification.is_direct_beneficiary,
        "classifier_confidence": candidate.classification.confidence,
        "classifier_version": candidate.classification.classifier_version,
        "classification_reason": candidate.classification.reason,
        "classification_evidence": list(candidate.classification.evidence),
        "fade_state": signal.state.value if signal else None,
        "signal_type": signal.signal_type.value if signal else event_fade.FadeSignalType.NO_TRADE.value,
        "fade_score": signal.fade_score if signal else (fade_candidate.fade_score if fade_candidate else None),
        "signal_confidence": signal.confidence if signal else None,
        "eligible": vector.get("eligible"),
        "reason_codes": list(signal.reason_codes) if signal else [],
        "warnings": list(signal.warnings) if signal else [],
        "component_scores": dict(fade_candidate.component_scores) if fade_candidate else {},
        "data_quality": dict(candidate.data_quality),
        "missing_data": _missing_data(candidate),
        "price": market.price if market else None,
        "market_cap": market.market_cap if market else None,
        "volume_24h": market.volume_24h if market else None,
        "spot_volume_24h": market.spot_volume_24h if market else None,
        "return_24h": market.return_24h if market else None,
        "return_72h": market.return_72h if market else None,
        "return_7d": market.return_7d if market else None,
        "volume_zscore_24h": market.volume_zscore_24h if market else None,
        "spread_bps": market.spread_bps if market else None,
        "order_book_depth_2pct": market.order_book_depth_2pct if market else None,
        "perp_available": derivatives.perp_available if derivatives else None,
        "open_interest": derivatives.open_interest if derivatives else None,
        "open_interest_24h_change_pct": derivatives.open_interest_24h_change_pct if derivatives else None,
        "open_interest_to_market_cap": derivatives.open_interest_to_market_cap if derivatives else None,
        "funding_rate_8h": derivatives.funding_rate_8h if derivatives else None,
        "funding_rate_percentile": derivatives.funding_rate_percentile if derivatives else None,
        "futures_volume_24h": derivatives.futures_volume_24h if derivatives else None,
        "perp_spot_volume_ratio": derivatives.perp_spot_volume_ratio if derivatives else None,
        "liquidations_24h": derivatives.liquidations_24h if derivatives else None,
        "long_short_ratio": derivatives.long_short_ratio if derivatives else None,
        "basis": derivatives.basis if derivatives else None,
        "large_holder_exchange_inflow": supply.large_holder_exchange_inflow if supply else None,
        "cex_inflow_amount": supply.cex_inflow_amount if supply else None,
        "cex_inflow_pct_supply": supply.cex_inflow_pct_supply if supply else None,
        "unlock_amount": supply.unlock_amount if supply else None,
        "unlock_pct_circulating": supply.unlock_pct_circulating if supply else None,
        "top_holder_concentration": supply.top_holder_concentration if supply else None,
        "team_or_mm_wallet_activity": supply.team_or_mm_wallet_activity if supply else None,
        "admin_or_mint_risk": supply.admin_or_mint_risk if supply else None,
        "rsi_daily": rsi.rsi_daily if rsi else None,
        "rsi_4h": rsi.rsi_4h if rsi else None,
        "rsi_weekly": rsi.rsi_weekly if rsi else None,
        "target_overbought_score": rsi.target_overbought_score if rsi else None,
        "btc_risk_on_score": rsi.btc_risk_on_score if rsi else None,
        "rsi_rollover_confirmed": rsi.rsi_rollover_confirmed if rsi else None,
        "bearish_rsi_divergence": rsi.bearish_rsi_divergence if rsi else None,
        "event_vwap": technical.event_vwap if technical else None,
        "price_below_event_vwap": technical.price_below_event_vwap if technical else None,
        "failed_reclaim_event_vwap": technical.failed_reclaim_event_vwap if technical else None,
        "lower_high_confirmed": technical.lower_high_confirmed if technical else None,
        "first_support_broken": technical.first_support_broken if technical else None,
        "post_event_high": technical.post_event_high if technical else None,
        "post_event_lower_high": technical.post_event_lower_high if technical else None,
        "entry_reference_price": signal.entry_reference_price if signal else (technical.entry_reference_price if technical else None),
        "invalidation_level": signal.invalidation_level if signal else (technical.invalidation_level if technical else None),
        "trigger_observed_at": _iso(signal.timestamp) if signal and signal.signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED else None,
        "max_adverse_excursion": None,
        "max_favorable_excursion": None,
        "post_event_return_24h": None,
        "post_event_return_72h": None,
        "post_event_return_7d": None,
        "event_time_entry_price": None,
        "event_time_max_adverse_excursion": None,
        "event_time_max_favorable_excursion": None,
        "event_time_post_event_return_24h": None,
        "event_time_post_event_return_72h": None,
        "event_time_post_event_return_7d": None,
        "review_status": "",
        "human_label": "",
        "human_notes": "",
    }
    return {field: row.get(field) for field in VALIDATION_SAMPLE_FIELDS}


def _min_dt(values: Iterable[datetime | None]) -> datetime | None:
    present = [_as_utc(value) for value in values if value is not None]
    return min(present) if present else None


def _max_dt(values: Iterable[datetime | None]) -> datetime | None:
    present = [_as_utc(value) for value in values if value is not None]
    return max(present) if present else None


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return str(value)


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def _csv_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, datetime):
        return _iso(value)
    return value


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
