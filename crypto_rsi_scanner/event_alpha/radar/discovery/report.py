"""Event discovery report renderers."""

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
            f"  {candidate.asset.symbol:<12} {relation:<22} {proxy:<9} role={cls.asset_role:<18} "
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
    rows.append("    asset role: " + cls.asset_role_reason)
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
