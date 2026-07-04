"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (ledger)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_providers.cryptopanic import CryptoPanicProvider, normalize_cryptopanic_currency_code
from ....event_providers.gdelt import GdeltProvider
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ..resolver import clean_text
from .models import *  # noqa: F403

def _catalyst_search_skip_reasons(
    market_anomalies: tuple[RawDiscoveredEvent, ...],
    eligible_anomalies: tuple[RawDiscoveredEvent, ...],
    queries: tuple[SearchQuery, ...],
    cfg: EventCatalystSearchConfig,
) -> dict[str, int]:
    reasons: dict[str, int] = {}
    if not cfg.enabled:
        reasons["profile_disabled"] = 1
        return reasons
    if not market_anomalies:
        return reasons
    if not eligible_anomalies:
        reasons["no_anomalies_over_threshold"] = len(market_anomalies)
        return reasons
    if cfg.max_queries_per_anomaly <= 0:
        reasons["query_limit_zero"] = len(eligible_anomalies)
        return reasons
    if not queries:
        missing_identity = sum(1 for anomaly in eligible_anomalies if not _identity_for_raw_event(anomaly).symbol)
        reasons["anomaly_identity_missing" if missing_identity else "unknown"] = missing_identity or len(eligible_anomalies)
    return reasons
def _skip_reasons_from_warnings(warnings: Iterable[str]) -> dict[str, int]:
    reasons: dict[str, int] = {}
    for warning in warnings:
        text = str(warning or "").casefold()
        if not text:
            continue
        if "backoff" in text:
            reasons["provider_backoff"] = reasons.get("provider_backoff", 0) + 1
        elif any(token in text for token in ("unavailable", "timeout", "failed", "failure", "dns", "429")):
            reasons["provider_unavailable"] = reasons.get("provider_unavailable", 0) + 1
    return reasons
def _merge_reason_counts(*items: Mapping[str, int] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for mapping in items:
        if not mapping:
            continue
        for key, value in mapping.items():
            clean = str(key or "").strip()
            if not clean:
                continue
            try:
                count = int(value)
            except (TypeError, ValueError):
                count = 1
            out[clean] = out.get(clean, 0) + max(1, count)
    return out
def _hypothesis_search_skip_reasons(
    all_hypotheses: tuple[object, ...],
    eligible: tuple[object, ...],
    queries: tuple[SearchQuery, ...],
    cfg: EventImpactHypothesisSearchConfig,
) -> dict[str, int]:
    reasons: dict[str, int] = {}
    if not cfg.enabled:
        reasons["profile_disabled"] = 1
        return reasons
    if not all_hypotheses:
        reasons["no_hypotheses"] = 1
        return reasons
    if not eligible:
        low_confidence = 0
        missing_assets = 0
        already_validated = 0
        for hypothesis in all_hypotheses:
            status = str(getattr(hypothesis, "status", "") or "")
            if status == "validated":
                already_validated += 1
                continue
            try:
                confidence = float(getattr(hypothesis, "confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence < cfg.min_confidence:
                low_confidence += 1
            elif not tuple(getattr(hypothesis, "candidate_symbols", ()) or ()):
                missing_assets += 1
        if low_confidence:
            reasons["low_confidence"] = low_confidence
        if missing_assets:
            reasons["no_candidate_assets"] = missing_assets
        if already_validated:
            reasons["already_validated"] = already_validated
        return reasons
    if not queries:
        reasons["no_candidate_assets"] = len(eligible)
    return reasons
