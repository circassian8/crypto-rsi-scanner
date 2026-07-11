"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (models)."""

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

log = logging.getLogger(__name__)
QUERY_TEMPLATES = (
    "{symbol} crypto why up",
    "{symbol} Binance listing",
    "{symbol} perp listing",
    "{symbol} token unlock",
    "{symbol} airdrop",
    "{symbol} OpenAI exposure",
    "{symbol} SpaceX exposure",
    "{symbol} exploit",
    "{symbol} DWF Labs",
)
CATALYST_TERM_WEIGHTS = {
    "binance": 12,
    "listing": 10,
    "perp": 10,
    "futures": 8,
    "unlock": 10,
    "airdrop": 8,
    "tge": 8,
    "exploit": 12,
    "hack": 10,
    "pre ipo": 12,
    "pre-ipo": 12,
    "tokenized stock": 12,
    "synthetic exposure": 12,
    "prediction market": 10,
    "spacex": 12,
    "openai": 12,
    "anthropic": 12,
    "world cup": 8,
    "fan token": 8,
}
LOW_QUALITY_PHRASES = (
    "market recap",
    "market roundup",
    "daily recap",
    "weekly recap",
    "crypto prices today",
    "price prediction",
)
SOURCE_NOISE_PHRASES = (
    "bitcoin world",
    "kucoin source",
    "ripple effects",
    "ipo hype",
)
HIGH_CONFIDENCE_SOURCE_HINTS = (
    "binance",
    "bybit",
    "coinbase",
    "okx",
    "kucoin",
    "polymarket",
    "gdelt",
    "official",
)
COMMON_WORD_SYMBOLS = {
    "HYPE",
    "PRIME",
    "OPEN",
    "BEAT",
    "BILL",
    "CASH",
    "REAL",
    "JUST",
    "HUMAN",
    "HUMANITY",
    "AI",
}
@dataclass(frozen=True)
class EventCatalystSearchConfig:
    enabled: bool = False
    provider: str = "fixture"
    providers: tuple[str, ...] = ()
    max_anomalies: int = 10
    max_queries_per_anomaly: int = 6
    max_results_per_query: int = 5
    min_anomaly_score: int = 60
    require_live_source: bool = False
    min_result_confidence: float = 0.50
@dataclass(frozen=True)
class EventImpactHypothesisSearchConfig:
    enabled: bool = False
    max_hypotheses: int = 10
    max_queries_per_hypothesis: int = 4
    max_results_per_query: int = 5
    min_confidence: float = 0.55
    min_result_confidence: float = 0.50
    require_validated_identity: bool = True
    candidate_discovery_enabled: bool = True
    max_candidate_discovery_queries: int = 10
    max_candidate_discovery_results: int = 5
@dataclass(frozen=True)
class CatalystSearchScore:
    score: int
    reason_codes: tuple[str, ...] = ()
@dataclass(frozen=True)
class SearchQuery:
    anomaly_raw_id: str
    query: str
    symbol: str
    rank: int
    query_type: str = "candidate_validation"
    score: int = 0
    score_reasons: tuple[str, ...] = ()
    coin_id: str | None = None
    project_name: str | None = None
    aliases: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()
    is_common_word_symbol: bool = False
    identity_terms: tuple[str, ...] = ()
@dataclass(frozen=True)
class SearchResultEvent:
    query: SearchQuery
    raw_event: RawDiscoveredEvent
    result_score: int = 0
    result_score_reasons: tuple[str, ...] = ()
    accepted: bool = True
@dataclass(frozen=True)
class CatalystSearchRunResult:
    provider: str
    queries: tuple[SearchQuery, ...] = ()
    result_events: tuple[SearchResultEvent, ...] = ()
    rejected_result_events: tuple[SearchResultEvent, ...] = ()
    attached_raw_events: tuple[RawDiscoveredEvent, ...] = ()
    warnings: tuple[str, ...] = ()
    provider_fetch_count: int = 0
    provider_cache_hits: int = 0
    provider_cache_misses: int = 0
    query_count: int = 0
    result_count: int = 0
    rejected_count: int = 0
    skip_reasons: Mapping[str, int] = field(default_factory=dict)

    @property
    def attached_result_count(self) -> int:
        return len(self.result_events)

    @property
    def rejected_result_count(self) -> int:
        return len(self.rejected_result_events)
@dataclass(frozen=True)
class _AnomalyIdentity:
    symbol: str
    coin_id: str | None = None
    project_name: str | None = None
    aliases: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()

    @property
    def is_common_word_symbol(self) -> bool:
        return bool(self.symbol and (len(self.symbol.strip()) <= 1 or self.symbol.upper() in COMMON_WORD_SYMBOLS))

    @property
    def identity_terms(self) -> tuple[str, ...]:
        terms: list[str] = []
        for value in (self.project_name, self.coin_id, *self.aliases):
            text = str(value or "").strip()
            if not text:
                continue
            terms.append(text)
            terms.append(text.replace("-", " "))
        return tuple(dict.fromkeys(term for term in terms if len(term) >= 3))
@dataclass(frozen=True)
class HypothesisSearchQuerySpec:
    query: str
    query_type: str = "candidate_validation"
@dataclass(frozen=True)
class _HypothesisIdentity:
    symbol: str
    coin_id: str | None = None
    project_name: str | None = None
    aliases: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()

    @property
    def identity_terms(self) -> tuple[str, ...]:
        terms = [self.project_name, self.coin_id, self.coin_id.replace("-", " ") if self.coin_id else None, *self.aliases]
        return tuple(dict.fromkeys(str(term).strip() for term in terms if str(term or "").strip()))
