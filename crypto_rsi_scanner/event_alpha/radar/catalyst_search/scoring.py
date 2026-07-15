"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (scoring)."""

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

def score_search_result(
    raw_event: RawDiscoveredEvent,
    query: SearchQuery,
    anomaly: RawDiscoveredEvent | None = None,
    *,
    now: datetime | None = None,
) -> CatalystSearchScore:
    """Score returned source evidence before attaching it to an anomaly."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    text = clean_text(" ".join(str(part or "") for part in (
        raw_event.title,
        raw_event.body,
        raw_event.source_url,
        event_payload.get("event_name"),
        event_payload.get("event_type"),
        event_payload.get("external_asset"),
        event_payload.get("description"),
    )))
    score = max(0.0, min(1.0, float(raw_event.source_confidence or 0.0))) * 35
    reasons = [f"source_confidence_{int(round(float(raw_event.source_confidence or 0.0) * 100))}"]
    identity_reason = _identity_match_reason(raw_event, query, anomaly)
    identity_missing = identity_reason is None
    rejected_identity_reasons = {
        "common_word_identity_rejected",
        "identity_url_only_rejected",
        "identity_source_origin_rejected",
    }
    common_word_rejected = identity_reason == "common_word_identity_rejected"
    rejected_identity = identity_reason in rejected_identity_reasons
    candidate_discovery_asset = (
        str(getattr(query, "query_type", "") or "") == "candidate_discovery"
        and _candidate_discovery_asset_present(raw_event)
    )
    if identity_reason and not rejected_identity:
        score += {
            "identity_match_strong": 26,
            "identity_match_pair": 24,
            "identity_match_contract": 28,
            "identity_match_alias": 22,
            "identity_match_project": 22,
            "identity_match_token_context": 20,
            "identity_match_llm_resolver_validated": 20,
            "identity_quote_validated": 20,
        }.get(identity_reason, 18)
        reasons.append(identity_reason)
    elif candidate_discovery_asset:
        score += 18
        reasons.append("candidate_discovery_asset_hint")
    elif query.symbol in {"BTC", "ETH"} and _looks_generic_major_market_article(text):
        score -= 25
        reasons.append("generic_major_market_penalty")
    if anomaly is not None:
        identity = _identity_for_raw_event(anomaly)
        anomaly_name = clean_text(identity.project_name or _event_name(anomaly))
        if identity_reason and anomaly_name and anomaly_name in text:
            score += 6
            reasons.append("anomaly_project_match")
    catalyst_hits = _weighted_term_hits(text, CATALYST_TERM_WEIGHTS)
    if catalyst_hits:
        score += min(30, sum(CATALYST_TERM_WEIGHTS[hit] for hit in catalyst_hits))
        reasons.append("catalyst_terms:" + ",".join(catalyst_hits[:4]))
    if event_payload.get("event_time"):
        score += 10
        reasons.append("explicit_event_time")
    if any(hint in text for hint in HIGH_CONFIDENCE_SOURCE_HINTS):
        score += 8
        reasons.append("high_confidence_source_hint")
    future_timestamp_fields = _future_source_timestamp_fields(raw_event, observed)
    published = raw_event.published_at or raw_event.fetched_at
    if published is not None and not future_timestamp_fields:
        age_hours = (observed - _as_utc(published)).total_seconds() / 3600.0
        if age_hours <= 24:
            score += 8
            reasons.append("fresh_24h")
        elif age_hours > 24 * 14:
            score -= 22
            reasons.append("stale_result_penalty")
    if future_timestamp_fields:
        reasons.append("source_timestamp_in_future")
        reasons.extend(f"source_{field}_in_future" for field in future_timestamp_fields)
    if any(phrase in text for phrase in LOW_QUALITY_PHRASES):
        score -= 28
        reasons.append("market_recap_penalty")
    if any(phrase in text for phrase in SOURCE_NOISE_PHRASES):
        score -= 22
        reasons.append("source_noise_penalty")
    if not raw_event.source_url and raw_event.provider not in {"fixture_search_result", "manual_json"}:
        score -= 8
        reasons.append("missing_source_url_penalty")
    if common_word_rejected:
        score = min(score, 35)
        reasons.append("common_word_identity_rejected")
    elif identity_reason in {"identity_url_only_rejected", "identity_source_origin_rejected"}:
        score = min(score, 40)
        reasons.append(identity_reason)
    elif identity_missing and not candidate_discovery_asset:
        score = min(score, 45)
        reasons.append("identity_missing_cap")
    if future_timestamp_fields:
        score = 0
    return CatalystSearchScore(max(0, min(100, int(round(score)))), tuple(dict.fromkeys(reasons)))


def _future_source_timestamp_fields(
    raw_event: RawDiscoveredEvent,
    observed: datetime,
) -> tuple[str, ...]:
    """Return impossible source-clock fields without confusing them with event time.

    A future scheduled ``event_time`` is valid catalyst content.  A source's
    publication or fetch timestamp beyond the bounded clock-skew tolerance is
    not valid freshness evidence and must fail closed before attachment.
    """

    cutoff = observed + SOURCE_TIMESTAMP_FUTURE_TOLERANCE
    fields: list[str] = []
    for field_name, value in (
        ("published_at", raw_event.published_at),
        ("fetched_at", raw_event.fetched_at),
    ):
        if value is not None and _as_utc(value) > cutoff:
            fields.append(field_name)
    return tuple(fields)


def _weighted_term_hits(text: str, weights: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(term for term in weights if term in text)
def _looks_generic_major_market_article(text: str) -> bool:
    return any(phrase in text for phrase in (
        "bitcoin price",
        "ethereum price",
        "crypto market",
        "market update",
        "market recap",
    ))
def _annotate_scored_result(
    raw: RawDiscoveredEvent,
    score: int,
    reasons: Iterable[str],
) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    source_payload = dict(payload.get("market_anomaly_catalyst_search_source") or {})
    source_payload.update({
        "result_score": score,
        "result_score_reasons": list(dict.fromkeys(str(reason) for reason in reasons)),
        "research_only": True,
    })
    payload["market_anomaly_catalyst_search_source"] = source_payload
    return replace(raw, raw_json=payload, content_hash=_content_hash(payload))
