"""Event discovery normalization and resolver orchestration."""

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
import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as event_catalyst_attribution
import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
import crypto_rsi_scanner.event_alpha.radar.source_independence as event_source_independence
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
from .models import *  # noqa: F403 - split modules share historical model names


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
    event_time_source_raw = event_payload.get("event_time_source", payload.get("event_time_source"))
    event_time_source = str(event_time_source_raw) if event_time_source_raw else ("explicit" if event_time else None)
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
        event_time_source=event_time_source,
        first_seen_time=first_seen,
        source=raw.provider,
        source_urls=tuple(u for u in (raw.source_url,) if u),
        external_asset=str(external_asset) if external_asset else None,
        description=description or None,
        confidence=max(0.0, min(1.0, confidence)),
    )


def dedupe_events(events: Iterable[NormalizedEvent]) -> list[NormalizedEvent]:
    exact_merged = _merge_event_groups(events, key_func=_exact_dedupe_key)
    canonical_groups: dict[tuple[str, str, str, str], list[NormalizedEvent]] = {}
    passthrough: list[NormalizedEvent] = []
    for event in exact_merged:
        key = _canonical_dedupe_key(event)
        if key is None:
            passthrough.append(event)
        else:
            canonical_groups.setdefault(key, []).append(event)
    out = [*passthrough]
    out.extend(_merge_event_group(key, group) for key, group in canonical_groups.items())
    return sorted(out, key=lambda e: (e.event_time or e.first_seen_time, e.event_name))


def _merge_event_groups(
    events: Iterable[NormalizedEvent],
    *,
    key_func,
) -> list[NormalizedEvent]:
    grouped: dict[tuple[str, str, str, str], list[NormalizedEvent]] = {}
    for event in events:
        key = key_func(event)
        grouped.setdefault(key, []).append(event)
    return [_merge_event_group(key, group) for key, group in grouped.items()]


def _merge_event_group(key: tuple[str, str, str, str], group: list[NormalizedEvent]) -> NormalizedEvent:
    if len(group) == 1:
        return group[0]
    first = min(group, key=lambda e: e.first_seen_time)
    raw_ids = tuple(sorted({raw_id for event in group for raw_id in event.raw_ids}))
    urls = tuple(sorted({url for event in group for url in event.source_urls}))
    confidence = max(event.confidence for event in group)
    best_time = _best_event_time_event(group) or first
    description = " ".join(_unique(
        value
        for event in group
        for value in (event.event_name, event.description)
        if value
    )) or None
    return NormalizedEvent(
        event_id=_event_id(*key),
        raw_ids=raw_ids,
        event_name=first.event_name,
        event_type=first.event_type,
        event_time=best_time.event_time,
        event_time_confidence=max(event.event_time_confidence for event in group),
        event_time_source=_best_event_time_source(group),
        first_seen_time=first.first_seen_time,
        source="+".join(sorted({event.source for event in group})),
        source_urls=urls,
        external_asset=first.external_asset or next((event.external_asset for event in group if event.external_asset), None),
        description=description,
        confidence=confidence,
    )


def _exact_dedupe_key(event: NormalizedEvent) -> tuple[str, str, str, str]:
    return (
        clean_text(event.event_name),
        event.event_type,
        event.event_time.isoformat() if event.event_time else "",
        clean_text(event.external_asset),
    )


def _canonical_dedupe_key(event: NormalizedEvent) -> tuple[str, str, str, str] | None:
    if event.event_time is None or not event.external_asset:
        return None
    terms = _catalyst_terms(event)
    if not terms:
        return None
    return (
        event.event_type,
        clean_text(event.external_asset),
        event.event_time.date().isoformat(),
        "+".join(terms),
    )


def _catalyst_terms(event: NormalizedEvent) -> tuple[str, ...]:
    text = clean_text(" ".join((event.event_name, event.description or "", event.event_type)))
    groups = {
        "ipo": (
            "ipo",
            "pre ipo",
            "pre-ipo",
            "nasdaq",
            "public offering",
            "debut",
            "trading start",
            "trading starts",
            "opens trading",
        ),
        "listing": ("listing", "listed", "exchange listing", "perp", "futures"),
        "unlock": ("unlock", "vesting", "emission"),
        "etf": ("etf", "approval", "launch"),
        "sports": ("match", "world cup", "champions league", "fixture", "kickoff"),
        "political": ("election", "inauguration", "vote", "certification"),
        "product": ("launch", "release", "product event", "model event"),
    }
    hits = [name for name, markers in groups.items() if any(marker in text for marker in markers)]
    return tuple(sorted(set(hits)))


def _best_event_time_event(events: Iterable[NormalizedEvent]) -> NormalizedEvent | None:
    best: NormalizedEvent | None = None
    for event in events:
        if event.event_time is None:
            continue
        if best is None or event.event_time_confidence > best.event_time_confidence:
            best = event
    return best


def _best_event_time_source(events: Iterable[NormalizedEvent]) -> str | None:
    best: NormalizedEvent | None = None
    for event in events:
        if event.event_time_source is None:
            continue
        if best is None or event.event_time_confidence > best.event_time_confidence:
            best = event
    return best.event_time_source if best else None


def run_discovery(
    raw_events: Iterable[RawDiscoveredEvent],
    assets: Iterable[DiscoveredAsset],
    *,
    cfg: EventDiscoveryConfig | None = None,
    fade_cfg: event_fade.EventFadeConfig | None = None,
    now: datetime | None = None,
    market_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    derivatives_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    supply_by_asset: Mapping[str, Mapping[str, Any]] | None = None,
    warnings: Iterable[str] = (),
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
        source_independence_contract, source_independence_errors = event_source_independence.assess_source_independence_safe([
            _source_independence_row(raw_by_id[raw_id])
            for raw_id in event.raw_ids
            if raw_id in raw_by_id
        ], expected_document_count=len(event.raw_ids))
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
                market_by_asset=market_by_asset,
                derivatives_by_asset=derivatives_by_asset,
                supply_by_asset=supply_by_asset,
            )
            forced_no_trade_reasons = _forced_no_trade_reasons(event, classification, cfg)
            if fade_candidate and forced_no_trade_reasons:
                fade_signal = _forced_no_trade_signal(fade_candidate, fade_cfg, now, forced_no_trade_reasons)
            else:
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
                    "source_update_count": len(event.raw_ids),
                    "independent_source_count": int(source_independence_contract.get("independent_evidence_count") or 0),
                    "independent_corroboration_count": int(source_independence_contract.get("independent_corroboration_count") or 0),
                    "source_content_cluster_count": int(source_independence_contract.get("content_cluster_count") or 0),
                    "source_independence": source_independence_contract,
                    "source_independence_errors": list(source_independence_errors),
                    "source_independence_status": (
                        "assessed"
                        if source_independence_contract
                        else "rejected"
                        if source_independence_errors
                        else "unassessed"
                    ),
                    "has_event_time": event.event_time is not None,
                    "link_confidence": link.link_confidence,
                    "classifier_confidence": classification.confidence,
                    "classifier_pass": classification.confidence >= cfg.min_classifier_confidence,
                    "event_time_confidence_pass": (
                        event.event_time is None
                        or event.event_time_confidence >= cfg.min_event_time_confidence
                    ),
                    "proxy_venue_trigger_allowed": cfg.allow_proxy_venue_trigger,
                    "forced_no_trade_reason": forced_no_trade_reasons[0] if forced_no_trade_reasons else None,
                    "forced_no_trade_reasons": list(forced_no_trade_reasons),
                    "asset_role": classification.asset_role,
                    "asset_role_confidence": classification.asset_role_confidence,
                    "has_market_snapshot": fade_candidate is not None and fade_candidate.market.price > 0,
                    "has_derivatives_snapshot": fade_candidate is not None and fade_candidate.derivatives is not None,
                    "has_supply_snapshot": fade_candidate is not None and fade_candidate.supply is not None,
                    "has_technical_snapshot": fade_candidate is not None and fade_candidate.technical is not None,
                    "catalyst_attributions": list(
                        _validated_candidate_catalyst_attributions(event, raw_by_id)
                    ),
                },
            ))
    return EventDiscoveryResult(
        raw_events=raw_tuple,
        normalized_events=normalized,
        links=tuple(links),
        classifications=tuple(classifications),
        candidates=tuple(candidates),
        warnings=tuple(dict.fromkeys(str(warning) for warning in warnings if str(warning))),
    )


def _source_independence_row(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
    return {
        "source_id": raw.raw_id,
        "source_url": raw.source_url,
        "title": raw.title,
        "body": raw.body,
        "provider": raw.provider,
        "source_class": payload.get("source_class") or provenance.get("source_class"),
        "published_at": raw.published_at,
        "fetched_at": raw.fetched_at,
    }


def _validated_candidate_catalyst_attributions(
    event: NormalizedEvent,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
) -> tuple[dict[str, Any], ...]:
    """Copy only contracts bound to an exact raw source and parent anomaly."""

    values: dict[str, dict[str, Any]] = {}
    for raw_id in event.raw_ids:
        source = raw_by_id.get(raw_id)
        payload = source.raw_json if source is not None and isinstance(source.raw_json, Mapping) else {}
        value = payload.get("catalyst_attribution")
        if not isinstance(value, Mapping):
            continue
        anomaly = raw_by_id.get(str(value.get("anomaly_id") or ""))
        if anomaly is None or source is None:
            continue
        if event_catalyst_attribution.validate_source_binding(value, anomaly, source):
            continue
        copied = dict(value)
        values[str(copied["attribution_digest"])] = copied
    return tuple(
        values[key]
        for key in sorted(values)
    )


def _forced_no_trade_reasons(
    event: NormalizedEvent,
    classification: EventClassification,
    cfg: EventDiscoveryConfig,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if classification.confidence < cfg.min_classifier_confidence:
        reasons.append("low_classifier_confidence")
    if event.event_time is not None and event.event_time_confidence < cfg.min_event_time_confidence:
        reasons.append("low_event_time_confidence")
    if classification.asset_role == "proxy_venue" and not cfg.allow_proxy_venue_trigger:
        reasons.append("proxy_venue_review_only")
    return tuple(reasons)


def _forced_no_trade_signal(
    candidate: event_fade.FadeCandidate,
    cfg: event_fade.EventFadeConfig,
    now: datetime,
    reasons: tuple[str, ...],
) -> event_fade.FadeSignal:
    event_fade.calculate_fade_score(candidate, cfg, now)
    warnings = [
        *candidate.warnings,
        *(_forced_no_trade_warning(reason) for reason in reasons),
    ]
    return event_fade.FadeSignal(
        symbol=candidate.symbol,
        timestamp=now,
        signal_type=event_fade.FadeSignalType.NO_TRADE,
        state=event_fade.FadeState.DISCOVERED,
        fade_score=candidate.fade_score,
        confidence=0.0,
        reason_codes=list(_unique((*candidate.reason_codes, *(f"forced no trade: {reason}" for reason in reasons)))),
        warnings=list(_unique(warnings)),
        entry_reference_price=None,
        invalidation_level=None,
        take_profit_zones=None,
        position_size_suggestion=None,
    )


def _forced_no_trade_warning(reason: str) -> str:
    return {
        "low_classifier_confidence": "classifier confidence below discovery trigger threshold; review-only",
        "low_event_time_confidence": "event time confidence below discovery trigger threshold; review-only",
        "proxy_venue_review_only": "proxy venue candidates are watchlist-only by default",
    }.get(reason, f"{reason}; review-only")
