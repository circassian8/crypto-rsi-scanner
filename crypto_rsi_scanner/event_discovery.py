"""Research-only event discovery pipeline for event-fade candidates."""

from __future__ import annotations

import hashlib
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
from .event_providers.gdelt import GdeltProvider
from .event_providers.manual_json import ManualJsonEventProvider, parse_datetime
from .event_providers.prediction_market_events import PredictionMarketEventsProvider
from .event_providers.project_blog_rss import ProjectBlogRssProvider
from .event_providers.sports_fixtures import SportsFixturesProvider
from .event_providers.tokenomist import TokenomistProvider
from .event_resolver import clean_text, load_asset_aliases, resolve_event_assets

log = logging.getLogger(__name__)


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
    bybit_announcements_path: str | Path | None = None,
    coinmarketcal_path: str | Path | None = None,
    tokenomist_path: str | Path | None = None,
    cryptopanic_path: str | Path | None = None,
    gdelt_path: str | Path | None = None,
    project_blog_rss_path: str | Path | None = None,
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
    coinalyze_derivatives_path: str | Path | None = None,
    universe_path: str | Path | None = None,
    universe_limit: int | None = None,
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
        bybit_announcements_path=bybit_announcements_path,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
        cryptopanic_path=cryptopanic_path,
        gdelt_path=gdelt_path,
        project_blog_rss_path=project_blog_rss_path,
        external_ipo_path=external_ipo_path,
        sports_fixtures_path=sports_fixtures_path,
        prediction_market_events_path=prediction_market_events_path,
    )
    derivatives = load_derivatives_snapshots(coinalyze_derivatives_path)
    assets = load_discovery_assets(alias_path, universe_path=universe_path, universe_limit=universe_limit)
    return run_discovery(raw_events, assets, cfg=cfg, fade_cfg=fade_cfg, now=now, derivatives_by_asset=derivatives)


def load_discovery_events(
    event_path: str | Path | None,
    start: datetime,
    end: datetime,
    *,
    binance_announcements_path: str | Path | None = None,
    bybit_announcements_path: str | Path | None = None,
    coinmarketcal_path: str | Path | None = None,
    tokenomist_path: str | Path | None = None,
    cryptopanic_path: str | Path | None = None,
    gdelt_path: str | Path | None = None,
    project_blog_rss_path: str | Path | None = None,
    external_ipo_path: str | Path | None = None,
    sports_fixtures_path: str | Path | None = None,
    prediction_market_events_path: str | Path | None = None,
) -> list[RawDiscoveredEvent]:
    """Load local event fixtures from every configured research source."""
    events: list[RawDiscoveredEvent] = []
    if event_path:
        events.extend(ManualJsonEventProvider(event_path).fetch_events(start, end))
    if binance_announcements_path:
        events.extend(BinanceAnnouncementProvider(binance_announcements_path).fetch_events(start, end))
    if bybit_announcements_path:
        events.extend(BybitAnnouncementProvider(bybit_announcements_path).fetch_events(start, end))
    if coinmarketcal_path:
        events.extend(CoinMarketCalProvider(coinmarketcal_path).fetch_events(start, end))
    if tokenomist_path:
        events.extend(TokenomistProvider(tokenomist_path).fetch_events(start, end))
    if cryptopanic_path:
        events.extend(CryptoPanicProvider(cryptopanic_path).fetch_events(start, end))
    if gdelt_path:
        events.extend(GdeltProvider(gdelt_path).fetch_events(start, end))
    if project_blog_rss_path:
        events.extend(ProjectBlogRssProvider(project_blog_rss_path).fetch_events(start, end))
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
) -> list[DiscoveredAsset]:
    """Load manual aliases plus an optional cleaned CoinGecko-style universe."""
    assets: list[DiscoveredAsset] = []
    assets.extend(load_asset_aliases(alias_path))
    if universe_path:
        assets.extend(CoinGeckoUniverseProvider(universe_path, limit=universe_limit).fetch_assets())
    return merge_discovered_assets(assets)


def load_derivatives_snapshots(
    coinalyze_derivatives_path: str | Path | None,
) -> dict[str, dict[str, Any]]:
    """Load optional local derivatives snapshots for event-candidate enrichment."""
    if not coinalyze_derivatives_path:
        return {}
    return CoinalyzeDerivativesProvider(coinalyze_derivatives_path).fetch_snapshots()


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
        supply=_supply_snapshot(asset, payload.get("supply"), now),
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
        rows.append(
            f"  {candidate.asset.symbol:<12} {relation:<22} {proxy:<9} "
            f"link={candidate.link.link_confidence:.2f} cls={cls.confidence:.2f} "
            f"score={score:<3} deriv={derivatives:<3} signal={signal}/{state}"
        )
        rows.append(f"    event: {candidate.event.event_name}")
        rows.append(f"    reason: {cls.reason}")
    return "\n".join(rows)


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
