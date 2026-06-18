"""Catalyst-search scaffolding for market-anomaly research rows.

This module does not create alerts. It generates review queries, optionally
collects source evidence from research providers, scores the evidence, and
attaches accepted raw events to a market anomaly so the normal
discovery/resolver/classifier pipeline can validate them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse

from .event_models import RawDiscoveredEvent
from .event_providers.cryptopanic import CryptoPanicProvider
from .event_providers.gdelt import GdeltProvider
from .event_providers.prediction_market_events import PredictionMarketEventsProvider
from .event_providers.project_blog_rss import ProjectBlogRssProvider
from .event_resolver import clean_text

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
class CatalystSearchScore:
    score: int
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchQuery:
    anomaly_raw_id: str
    query: str
    symbol: str
    rank: int
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
        return bool(self.symbol and self.symbol.upper() in COMMON_WORD_SYMBOLS)

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


class CatalystSearchProvider(Protocol):
    name: str

    def search(
        self,
        queries: Iterable[SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> CatalystSearchRunResult:
        ...


class FixtureCatalystSearchProvider:
    """Fixture-backed catalyst search provider for offline tests/reports."""

    name = "fixture"

    def __init__(
        self,
        rows_by_query: Mapping[str, Iterable[RawDiscoveredEvent]] | None = None,
        path: str | Path | None = None,
        *,
        required: bool = False,
    ) -> None:
        self.rows_by_query = {str(key): tuple(value) for key, value in (rows_by_query or {}).items()}
        self.path = Path(path).expanduser() if path else None
        self.required = required
        self._loaded_rows: dict[str, tuple[RawDiscoveredEvent, ...]] | None = None

    def search(
        self,
        queries: Iterable[SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> CatalystSearchRunResult:
        queries_tuple = tuple(queries)
        rows_by_query = self._load_rows()
        result_events: list[SearchResultEvent] = []
        warnings: list[str] = []
        for query in queries_tuple:
            matches = _fixture_matches(rows_by_query, query.query)
            for raw in matches[: max(0, max_results_per_query)]:
                result_events.append(SearchResultEvent(query=query, raw_event=raw))
        return CatalystSearchRunResult(
            provider=self.name,
            queries=queries_tuple,
            result_events=tuple(result_events),
            warnings=tuple(warnings),
            provider_fetch_count=1 if queries_tuple else 0,
            provider_cache_misses=1 if queries_tuple else 0,
            query_count=len(queries_tuple),
            result_count=len(result_events),
        )

    def _load_rows(self) -> dict[str, tuple[RawDiscoveredEvent, ...]]:
        if self._loaded_rows is not None:
            return self._loaded_rows
        if self.rows_by_query:
            self._loaded_rows = dict(self.rows_by_query)
            return self._loaded_rows
        if self.path is None:
            self._loaded_rows = {}
            return self._loaded_rows
        if not self.path.exists():
            if self.required:
                raise FileNotFoundError(f"fixture catalyst-search rows not found: {self.path}")
            log.warning("Fixture catalyst-search rows missing: %s", self.path)
            self._loaded_rows = {}
            return self._loaded_rows
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            rows = raw.get("search_results", raw) if isinstance(raw, Mapping) else raw
            if not isinstance(rows, list):
                raise ValueError("fixture catalyst-search file must be a list or {'search_results': [...]}")
            loaded: dict[str, list[RawDiscoveredEvent]] = {}
            for item in rows:
                if not isinstance(item, Mapping):
                    raise ValueError("fixture catalyst-search rows must be objects")
                query = str(item.get("query") or item.get("query_contains") or "").strip()
                event_obj = item.get("raw_event") if isinstance(item.get("raw_event"), Mapping) else item
                raw_event = _raw_event_from_fixture(event_obj)
                loaded.setdefault(query, []).append(raw_event)
            self._loaded_rows = {key: tuple(value) for key, value in loaded.items()}
            return self._loaded_rows
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Fixture catalyst-search rows failed to load: %s", exc)
            self._loaded_rows = {}
            return self._loaded_rows


class CompositeCatalystSearchProvider:
    """Fan out catalyst-search queries to multiple evidence providers."""

    def __init__(self, providers: Iterable[CatalystSearchProvider]) -> None:
        self.providers = tuple(providers)
        self.name = ",".join(provider.name for provider in self.providers) or "none"

    def search(
        self,
        queries: Iterable[SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> CatalystSearchRunResult:
        query_rows = tuple(queries)
        result_events: list[SearchResultEvent] = []
        rejected: list[SearchResultEvent] = []
        warnings: list[str] = []
        fetch_count = 0
        cache_hits = 0
        cache_misses = 0
        for provider in self.providers:
            try:
                result = provider.search(query_rows, max_results_per_query=max_results_per_query, now=now)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{provider.name} failed: {exc}")
                continue
            result_events.extend(result.result_events)
            rejected.extend(result.rejected_result_events)
            warnings.extend(result.warnings)
            fetch_count += result.provider_fetch_count
            cache_hits += result.provider_cache_hits
            cache_misses += result.provider_cache_misses
        return CatalystSearchRunResult(
            provider=self.name,
            queries=query_rows,
            result_events=tuple(result_events),
            rejected_result_events=tuple(rejected),
            warnings=tuple(dict.fromkeys(warnings)),
            provider_fetch_count=fetch_count,
            provider_cache_hits=cache_hits,
            provider_cache_misses=cache_misses,
            query_count=len(query_rows),
            result_count=len(result_events),
            rejected_count=len(rejected),
        )


class EventProviderCatalystSearchProvider:
    """Adapter from broad event providers to anomaly-specific search results."""

    name = "event_provider"

    def __init__(
        self,
        event_provider_factory: Callable[[SearchQuery], object],
        *,
        name: str,
        lookback_hours: float = 168.0,
        horizon_days: float = 30.0,
        filter_by_query: bool = True,
    ) -> None:
        self.event_provider_factory = event_provider_factory
        self.name = name
        self.lookback_hours = lookback_hours
        self.horizon_days = horizon_days
        self.filter_by_query = filter_by_query

    def search(
        self,
        queries: Iterable[SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> CatalystSearchRunResult:
        observed = _as_utc(now or datetime.now(timezone.utc))
        start = observed - timedelta(hours=max(0.0, self.lookback_hours))
        end = observed + timedelta(days=max(0.0, self.horizon_days))
        query_rows = tuple(queries)
        result_events: list[SearchResultEvent] = []
        warnings: list[str] = []
        cache: dict[tuple[str, ...], tuple[RawDiscoveredEvent, ...]] = {}
        fetch_count = 0
        cache_hits = 0
        cache_misses = 0
        for query in query_rows:
            cache_key = self.cache_key_for_query(query)
            if cache_key in cache:
                events = cache[cache_key]
                cache_hits += 1
            else:
                cache_misses += 1
                fetch_count += 1
                events = ()
                try:
                    provider = self.event_provider_factory(query)
                    events = tuple(provider.fetch_events(start, end))  # type: ignore[attr-defined]
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{self.name} search failed for {query.query!r}: {exc}")
                cache[cache_key] = events
            try:
                matched = [
                    raw for raw in events
                    if not self.filter_by_query or _raw_event_matches_query(raw, query)
                ][: max(0, max_results_per_query)]
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{self.name} filter failed for {query.query!r}: {exc}")
                matched = []
            for raw in matched:
                result_events.append(SearchResultEvent(
                    query=query,
                    raw_event=_annotate_search_source(raw, self.name, query),
                ))
        return CatalystSearchRunResult(
            provider=self.name,
            queries=query_rows,
            result_events=tuple(result_events),
            warnings=tuple(dict.fromkeys(warnings)),
            provider_fetch_count=fetch_count,
            provider_cache_hits=cache_hits,
            provider_cache_misses=cache_misses,
            query_count=len(query_rows),
            result_count=len(result_events),
        )

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        return (self.name, query.query)


class GdeltCatalystSearchProvider(EventProviderCatalystSearchProvider):
    name = "gdelt"

    def __init__(self, **kwargs: Any) -> None:
        def factory(query: SearchQuery) -> GdeltProvider:
            return GdeltProvider(
                kwargs.get("path"),
                required=bool(kwargs.get("required", False)),
                live_enabled=bool(kwargs.get("live_enabled", False)),
                base_url=str(kwargs.get("base_url") or "https://api.gdeltproject.org/api/v2/doc/doc"),
                query=query.query,
                max_records=int(kwargs.get("max_records") or 50),
                timeout=float(kwargs.get("timeout") or 10.0),
                opener=kwargs.get("opener"),
                fetched_at=kwargs.get("fetched_at"),
            )

        super().__init__(factory, name=self.name)


class ProjectRssCatalystSearchProvider(EventProviderCatalystSearchProvider):
    name = "rss"

    def __init__(self, **kwargs: Any) -> None:
        def factory(query: SearchQuery) -> ProjectBlogRssProvider:
            del query
            return ProjectBlogRssProvider(
                kwargs.get("path"),
                required=bool(kwargs.get("required", False)),
                live_enabled=bool(kwargs.get("live_enabled", False)),
                feed_urls=kwargs.get("feed_urls"),
                timeout=float(kwargs.get("timeout") or 10.0),
                opener=kwargs.get("opener"),
                fetched_at=kwargs.get("fetched_at"),
            )

        super().__init__(factory, name=self.name)

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        del query
        return (self.name, "feed_bundle")


class CryptoPanicCatalystSearchProvider(EventProviderCatalystSearchProvider):
    name = "cryptopanic"

    def __init__(self, **kwargs: Any) -> None:
        def factory(query: SearchQuery) -> CryptoPanicProvider:
            return CryptoPanicProvider(
                kwargs.get("path"),
                required=bool(kwargs.get("required", False)),
                live_enabled=bool(kwargs.get("live_enabled", False)),
                api_token=str(kwargs.get("api_token") or ""),
                base_url=str(kwargs.get("base_url") or "https://cryptopanic.com/api/v1/posts/"),
                public=bool(kwargs.get("public", True)),
                filter_name=str(kwargs.get("filter_name") or ""),
                currencies=str(kwargs.get("currencies") or query.symbol),
                regions=str(kwargs.get("regions") or ""),
                kind=str(kwargs.get("kind") or ""),
                search=query.query,
                timeout=float(kwargs.get("timeout") or 10.0),
                opener=kwargs.get("opener"),
                fetched_at=kwargs.get("fetched_at"),
            )

        super().__init__(factory, name=self.name)

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        return (self.name, query.symbol, query.query)


class PolymarketCatalystSearchProvider(EventProviderCatalystSearchProvider):
    name = "polymarket"

    def __init__(self, **kwargs: Any) -> None:
        def factory(query: SearchQuery) -> PredictionMarketEventsProvider:
            del query
            return PredictionMarketEventsProvider(
                kwargs.get("path"),
                required=bool(kwargs.get("required", False)),
                live_enabled=bool(kwargs.get("live_enabled", False)),
                base_url=str(kwargs.get("base_url") or "https://gamma-api.polymarket.com/events"),
                limit=int(kwargs.get("limit") or 100),
                timeout=float(kwargs.get("timeout") or 10.0),
                opener=kwargs.get("opener"),
                fetched_at=kwargs.get("fetched_at"),
            )

        super().__init__(factory, name=self.name, filter_by_query=True)

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        del query
        return (self.name, "gamma_events")


def run_catalyst_search(
    raw_events: Iterable[RawDiscoveredEvent],
    provider: CatalystSearchProvider,
    *,
    cfg: EventCatalystSearchConfig | None = None,
    now: datetime | None = None,
) -> CatalystSearchRunResult:
    """Search for source evidence around market anomalies and attach results."""
    cfg = cfg or EventCatalystSearchConfig()
    if not cfg.enabled:
        return CatalystSearchRunResult(provider=getattr(provider, "name", cfg.provider))
    observed = _as_utc(now or datetime.now(timezone.utc))
    anomalies = _eligible_anomalies(raw_events, cfg)
    queries = _queries_for_anomalies(anomalies, cfg)
    anomaly_by_id = {raw.raw_id: raw for raw in anomalies}
    warnings: list[str] = []
    try:
        provider_result = provider.search(
            queries,
            max_results_per_query=cfg.max_results_per_query,
            now=observed,
        )
        warnings.extend(provider_result.warnings)
        provider_events = provider_result.result_events
        provider_rejected = list(provider_result.rejected_result_events)
    except Exception as exc:  # noqa: BLE001
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            queries=queries,
            warnings=(f"catalyst search provider failed: {exc}",),
            query_count=len(queries),
        )
    accepted_results: list[SearchResultEvent] = []
    rejected_results: list[SearchResultEvent] = list(provider_rejected)
    seen_content: set[str] = set()
    threshold = _confidence_threshold(cfg.min_result_confidence)
    for result in provider_events:
        anomaly = anomaly_by_id.get(result.query.anomaly_raw_id)
        score = score_search_result(result.raw_event, result.query, anomaly, now=observed)
        reasons = list(score.reason_codes)
        content_key = result.raw_event.content_hash or _content_hash(result.raw_event.raw_json or {})
        if content_key in seen_content:
            score = CatalystSearchScore(max(0, score.score - 25), (*score.reason_codes, "duplicate_content_penalty"))
            reasons = list(score.reason_codes)
        else:
            seen_content.add(content_key)
        if cfg.require_live_source and _is_fixture_source(result.raw_event, provider_name=getattr(provider, "name", "")):
            reasons.append("fixture_source_rejected")
            rejected_results.append(replace(
                result,
                result_score=score.score,
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        scored = replace(
            result,
            raw_event=_annotate_scored_result(result.raw_event, score.score, reasons),
            result_score=score.score,
            result_score_reasons=tuple(dict.fromkeys(reasons)),
            accepted=score.score >= threshold,
        )
        if scored.accepted:
            accepted_results.append(scored)
        else:
            rejected_results.append(scored)
    grouped: dict[str, list[RawDiscoveredEvent]] = {}
    for result in accepted_results:
        grouped.setdefault(result.query.anomaly_raw_id, []).append(result.raw_event)
    attached: list[RawDiscoveredEvent] = []
    for anomaly in anomalies:
        attached.extend(attach_search_results_to_anomaly(anomaly, grouped.get(anomaly.raw_id, ())))
    return CatalystSearchRunResult(
        provider=getattr(provider, "name", cfg.provider),
        queries=queries,
        result_events=tuple(accepted_results),
        rejected_result_events=tuple(rejected_results),
        attached_raw_events=tuple(attached),
        warnings=tuple(dict.fromkeys(warnings)),
        provider_fetch_count=provider_result.provider_fetch_count,
        provider_cache_hits=provider_result.provider_cache_hits,
        provider_cache_misses=provider_result.provider_cache_misses,
        query_count=len(queries),
        result_count=len(accepted_results),
        rejected_count=len(rejected_results),
    )


def generate_search_queries_for_anomaly(raw_market_anomaly_event: RawDiscoveredEvent) -> tuple[str, ...]:
    """Return deterministic review queries for a market-anomaly raw event."""
    identity = _identity_for_raw_event(raw_market_anomaly_event)
    symbol = identity.symbol
    if not symbol:
        return ()
    queries: list[str] = [template.format(symbol=symbol) for template in QUERY_TEMPLATES]
    if identity.project_name:
        queries.extend((
            f"{identity.project_name} crypto catalyst",
            f"{identity.project_name} Binance listing",
            f"{identity.project_name} token unlock",
            f"{identity.project_name} synthetic exposure",
        ))
    for alias in identity.aliases[:4]:
        if alias and alias.casefold() not in {symbol.casefold(), (identity.project_name or "").casefold()}:
            queries.append(f"{alias} crypto catalyst")
    queries.extend((
        f"{symbol}USDT Binance listing",
        f"{symbol}-USDT perp listing",
    ))
    for address in identity.contract_addresses[:2]:
        queries.append(f"{address} crypto catalyst")
    return tuple(dict.fromkeys(query for query in queries if query.strip()))


def generate_search_query_objects_for_anomaly(
    raw_market_anomaly_event: RawDiscoveredEvent,
    *,
    max_queries: int | None = None,
) -> tuple[SearchQuery, ...]:
    identity = _identity_for_raw_event(raw_market_anomaly_event)
    symbol = identity.symbol
    queries = generate_search_queries_for_anomaly(raw_market_anomaly_event)
    if max_queries is not None:
        queries = queries[: max(0, max_queries)]
    out: list[SearchQuery] = []
    for idx, query in enumerate(queries):
        base = SearchQuery(
            anomaly_raw_id=raw_market_anomaly_event.raw_id,
            query=query,
            symbol=symbol,
            rank=idx + 1,
            coin_id=identity.coin_id,
            project_name=identity.project_name,
            aliases=identity.aliases,
            contract_addresses=identity.contract_addresses,
            is_common_word_symbol=identity.is_common_word_symbol,
            identity_terms=identity.identity_terms,
        )
        score = score_search_query(base, raw_market_anomaly_event)
        out.append(replace(base, score=score.score, score_reasons=score.reason_codes))
    return tuple(out)


def score_search_query(query: SearchQuery, anomaly: RawDiscoveredEvent | None = None) -> CatalystSearchScore:
    """Score a generated search query before using provider budget."""
    payload = anomaly.raw_json if anomaly is not None and isinstance(anomaly.raw_json, Mapping) else {}
    anomaly_payload = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    try:
        anomaly_score = float(anomaly_payload.get("score") or 0.0)
    except (TypeError, ValueError):
        anomaly_score = 0.0
    text = clean_text(query.query)
    score = 15 + min(35, anomaly_score * 0.35)
    reasons = [f"anomaly_score_{int(round(anomaly_score))}"] if anomaly_score else []
    if query.symbol and query.symbol.casefold() in text:
        score += 10
        reasons.append("symbol_in_query")
    catalyst_hits = _weighted_term_hits(text, CATALYST_TERM_WEIGHTS)
    if catalyst_hits:
        score += min(35, sum(CATALYST_TERM_WEIGHTS[hit] for hit in catalyst_hits))
        reasons.append("catalyst_terms:" + ",".join(catalyst_hits[:4]))
    if "why up" in text:
        score -= 8
        reasons.append("generic_why_up_penalty")
    return CatalystSearchScore(max(0, min(100, int(round(score)))), tuple(dict.fromkeys(reasons)))


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
    published = raw_event.published_at or raw_event.fetched_at
    if published is not None:
        age_hours = max(0.0, (observed - _as_utc(published)).total_seconds() / 3600.0)
        if age_hours <= 24:
            score += 8
            reasons.append("fresh_24h")
        elif age_hours > 24 * 14:
            score -= 22
            reasons.append("stale_result_penalty")
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
    elif identity_missing:
        score = min(score, 45)
        reasons.append("identity_missing_cap")
    return CatalystSearchScore(max(0, min(100, int(round(score)))), tuple(dict.fromkeys(reasons)))


def attach_search_results_to_anomaly(
    raw_event: RawDiscoveredEvent,
    result_events: Iterable[RawDiscoveredEvent],
) -> tuple[RawDiscoveredEvent, ...]:
    """Attach manually supplied source events to an anomaly with provenance.

    The returned rows are still raw event evidence. They must pass normal
    normalization, asset resolution, classification, and playbook tiering before
    they can become research alerts.
    """
    queries = generate_search_queries_for_anomaly(raw_event)
    annotated_parent = _annotate_raw_event(
        raw_event,
        {
            "market_anomaly_catalyst_search": {
                "role": "parent_anomaly",
                "queries": list(queries),
                "research_only": True,
                "live_fetch": False,
            }
        },
    )
    parent_ref = {
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "title": raw_event.title,
        "symbol": _event_symbol(raw_event),
    }
    attached = [
        _annotate_raw_event(
            event,
            {
                "market_anomaly_catalyst_search": {
                    "role": "attached_source_evidence",
                    "parent": parent_ref,
                    "queries": list(queries),
                    "research_only": True,
                    "live_fetch": False,
                }
            },
        )
        for event in result_events
    ]
    return (annotated_parent, *attached)


def format_catalyst_search_report(result: CatalystSearchRunResult | None) -> str:
    rows = [
        "=" * 76,
        "EVENT CATALYST SEARCH REPORT (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 76,
    ]
    if result is None:
        rows.append("No catalyst search run.")
        return "\n".join(rows)
    rows.append(
        f"provider={result.provider} · queries={len(result.queries)} · "
        f"accepted_results={len(result.result_events)} · rejected_results={len(result.rejected_result_events)} · "
        f"attached_raw_events={len(result.attached_raw_events)}"
    )
    rows.append(
        f"provider_fetches={result.provider_fetch_count} · cache_hits={result.provider_cache_hits} · "
        f"cache_misses={result.provider_cache_misses} · query_count={result.query_count or len(result.queries)} · "
        f"result_count={result.result_count or len(result.result_events)} · "
        f"rejected_count={result.rejected_count or len(result.rejected_result_events)}"
    )
    if result.warnings:
        rows.append("warnings: " + "; ".join(result.warnings))
    if result.queries:
        rows.append("")
        rows.append("Queries:")
        for query in result.queries[:20]:
            reason_text = f" ({', '.join(query.score_reasons)})" if query.score_reasons else ""
            rows.append(f"- {query.symbol} #{query.rank}: score={query.score} {query.query}{reason_text}")
    if result.result_events:
        rows.append("")
        rows.append("Accepted result evidence:")
        for event in result.result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol}: score={event.result_score} "
                f"{event.raw_event.title} [{event.raw_event.provider}]{reason_text}"
            )
    if result.rejected_result_events:
        rows.append("")
        rows.append("Rejected result evidence:")
        for event in result.rejected_result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol}: score={event.result_score} "
                f"{event.raw_event.title} [{event.raw_event.provider}]{reason_text}"
            )
    return "\n".join(rows).rstrip()


def _eligible_anomalies(
    raw_events: Iterable[RawDiscoveredEvent],
    cfg: EventCatalystSearchConfig,
) -> tuple[RawDiscoveredEvent, ...]:
    candidates: list[tuple[float, RawDiscoveredEvent]] = []
    for raw in raw_events:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
        try:
            score = float(anomaly.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if raw.provider == "market_anomaly" and score >= cfg.min_anomaly_score:
            candidates.append((score, raw))
    candidates.sort(key=lambda item: (item[0], item[1].raw_id), reverse=True)
    return tuple(raw for _, raw in candidates[: max(0, cfg.max_anomalies)])


def _queries_for_anomalies(
    anomalies: Iterable[RawDiscoveredEvent],
    cfg: EventCatalystSearchConfig,
) -> tuple[SearchQuery, ...]:
    out: list[SearchQuery] = []
    for anomaly in anomalies:
        out.extend(generate_search_query_objects_for_anomaly(
            anomaly,
            max_queries=cfg.max_queries_per_anomaly,
        ))
    return tuple(out)


def _confidence_threshold(value: float) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.50
    if number <= 1.0:
        number *= 100.0
    return max(0, min(100, int(round(number))))


def _fixture_matches(
    rows_by_query: Mapping[str, tuple[RawDiscoveredEvent, ...]],
    query: str,
) -> tuple[RawDiscoveredEvent, ...]:
    exact = rows_by_query.get(query)
    if exact is not None:
        return exact
    query_lower = query.lower()
    matches: list[RawDiscoveredEvent] = []
    for key, rows in rows_by_query.items():
        key_lower = key.lower()
        if key_lower and (key_lower in query_lower or query_lower in key_lower):
            matches.extend(rows)
    return tuple(matches)


def _raw_event_matches_query(raw: RawDiscoveredEvent, query: SearchQuery) -> bool:
    if result_mentions_anomaly_identity(raw, query, None):
        return True
    text = clean_text(" ".join(str(part or "") for part in (raw.title, raw.body, raw.source_url)))
    if not text:
        return False
    symbol = query.symbol.casefold()
    if symbol and not query.is_common_word_symbol and _case_sensitive_symbol_in_source(raw, query.symbol):
        return True
    query_terms = [
        term for term in clean_text(query.query).split()
        if len(term) >= 4 and term not in {"crypto", "token", "why"}
    ]
    return any(term in text for term in query_terms)


def result_mentions_anomaly_identity(
    raw_event: RawDiscoveredEvent,
    query: SearchQuery,
    anomaly: RawDiscoveredEvent | None,
) -> bool:
    """Return true when a search result names the anomaly asset, not just a catalyst."""
    return _identity_match_reason(raw_event, query, anomaly) not in {
        None,
        "common_word_identity_rejected",
        "identity_url_only_rejected",
        "identity_source_origin_rejected",
    }


def _identity_match_reason(
    raw_event: RawDiscoveredEvent,
    query: SearchQuery,
    anomaly: RawDiscoveredEvent | None = None,
) -> str | None:
    identity = _query_identity(query, anomaly)
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    strong_source = " ".join(str(part or "") for part in (
        raw_event.title,
        raw_event.body,
        _event_name(raw_event),
        event_payload.get("description"),
    ))
    strong_lower = strong_source.casefold()
    text = clean_text(strong_source)
    source_url = str(raw_event.source_url or "")
    source_origin = _source_origin_text(raw_event)
    symbol = identity.symbol.upper()
    if not symbol:
        return None

    for address in identity.contract_addresses:
        if address and address.casefold() in strong_lower:
            return "identity_match_contract"
        if _contract_in_url_path(source_url, address):
            return "identity_match_contract"

    if _pair_symbol_in_source(strong_source, symbol):
        return "identity_match_pair"
    if _dollar_symbol_in_source(strong_source, symbol):
        return "identity_match_strong"
    if _case_sensitive_symbol_in_source(raw_event, symbol):
        if identity.is_common_word_symbol:
            return "identity_match_strong"
        return "identity_match_strong"
    if _token_context_in_text(text, symbol):
        return "identity_match_token_context"

    for term in identity.identity_terms:
        normalized = clean_text(term)
        if not normalized or len(normalized) < 3:
            continue
        if normalized in text:
            if identity.project_name and normalized == clean_text(identity.project_name):
                return "identity_match_project"
            return "identity_match_alias"

    if _llm_extraction_mentions_identity(raw_event, identity):
        return "identity_quote_validated"

    if identity.is_common_word_symbol and symbol.casefold() in text:
        return "common_word_identity_rejected"
    url_text = clean_text(source_url)
    origin_text = clean_text(source_origin)
    if _identity_in_source_origin(identity, origin_text):
        return "identity_source_origin_rejected"
    if _identity_in_url_only(identity, source_url, url_text):
        return "identity_url_only_rejected"
    return None


def _query_identity(query: SearchQuery, anomaly: RawDiscoveredEvent | None = None) -> _AnomalyIdentity:
    if query.identity_terms or query.coin_id or query.project_name or query.aliases or query.contract_addresses:
        return _AnomalyIdentity(
            symbol=query.symbol.upper(),
            coin_id=query.coin_id,
            project_name=query.project_name,
            aliases=tuple(query.aliases),
            contract_addresses=tuple(query.contract_addresses),
        )
    if anomaly is not None:
        return _identity_for_raw_event(anomaly)
    return _AnomalyIdentity(symbol=query.symbol.upper(), coin_id=query.coin_id)


def _identity_for_raw_event(raw: RawDiscoveredEvent) -> _AnomalyIdentity:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    asset = payload.get("asset") if isinstance(payload.get("asset"), Mapping) else {}
    anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    symbol = _event_symbol(raw)
    coin_id = _first_text(
        market.get("coin_id"),
        asset.get("coin_id"),
        payload.get("coin_id"),
        market.get("id"),
        asset.get("id"),
    )
    project_name = _first_text(
        market.get("name"),
        asset.get("name"),
        payload.get("name"),
        anomaly.get("name"),
    )
    aliases = _tuple_texts(
        market.get("aliases"),
        asset.get("aliases"),
        payload.get("aliases"),
        project_name,
        coin_id.replace("-", " ") if coin_id else None,
    )
    contracts = _contract_addresses(
        market.get("contract_addresses"),
        asset.get("contract_addresses"),
        payload.get("contract_addresses"),
        market.get("contract_address"),
        asset.get("contract_address"),
        payload.get("contract_address"),
    )
    return _AnomalyIdentity(
        symbol=symbol,
        coin_id=coin_id,
        project_name=project_name,
        aliases=aliases,
        contract_addresses=contracts,
    )


def _first_text(*values: object) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"none", "null"}:
            return text
    return None


def _tuple_texts(*values: object) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            iterable = value.values()
        elif isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = (value,)
        for item in iterable:
            text = str(item or "").strip()
            if text:
                out.append(text)
    return tuple(dict.fromkeys(out))


def _contract_addresses(*values: object) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            iterable = value.values()
        elif isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = (value,)
        for item in iterable:
            text = str(item or "").strip()
            if text:
                out.append(text.casefold())
    return tuple(dict.fromkeys(out))


def _pair_symbol_in_source(raw_source: str, symbol: str) -> bool:
    if not symbol:
        return False
    pattern = rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?:[-_/]?)USDT(?![A-Za-z0-9])"
    return re.search(pattern, raw_source, flags=re.IGNORECASE) is not None


def _dollar_symbol_in_source(raw_source: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9])\${re.escape(symbol)}(?![A-Za-z0-9])", raw_source, flags=re.IGNORECASE) is not None


def _case_sensitive_symbol_in_source(raw_event: RawDiscoveredEvent, symbol: str) -> bool:
    if not symbol:
        return False
    source = " ".join(str(part or "") for part in (raw_event.title, raw_event.body, _event_name(raw_event)))
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])", source) is not None


def _token_context_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    lower = symbol.casefold()
    return any(
        phrase in text
        for phrase in (
            f"{lower} token",
            f"{lower} coin",
            f"{lower} crypto",
            f"token {lower}",
            f"coin {lower}",
        )
    )


def _contract_in_url_path(source_url: str, address: str) -> bool:
    if not source_url or not address or not _looks_contract_address(address):
        return False
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return False
    path = parsed.path or ""
    query = parsed.query or ""
    address_l = address.casefold()
    if address_l in query.casefold():
        return False
    return address_l in path.casefold()


def _looks_contract_address(address: str) -> bool:
    text = str(address or "").strip()
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", text))


def _source_origin_text(raw_event: RawDiscoveredEvent) -> str:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    values = [
        payload.get("source_origin"),
        payload.get("publisher"),
        payload.get("source_name"),
        payload.get("provider_name"),
        raw_event.provider,
    ]
    if raw_event.source_url:
        try:
            values.append(urlparse(raw_event.source_url).netloc)
        except ValueError:
            pass
    return " ".join(str(value or "") for value in values)


def _identity_in_source_origin(identity: _AnomalyIdentity, origin_text: str) -> bool:
    if not origin_text:
        return False
    symbol = identity.symbol.casefold()
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?![a-z0-9])", origin_text):
        return True
    for term in identity.identity_terms:
        normalized = clean_text(term)
        if normalized and normalized in origin_text:
            return True
    return False


def _identity_in_url_only(identity: _AnomalyIdentity, source_url: str, url_text: str) -> bool:
    if not source_url or not url_text:
        return False
    symbol = identity.symbol.casefold()
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?:usdt)?(?![a-z0-9])", url_text):
        return True
    for term in identity.identity_terms:
        normalized = clean_text(term)
        if normalized and normalized in url_text:
            return True
    for address in identity.contract_addresses:
        if address and address.casefold() in source_url.casefold() and not _contract_in_url_path(source_url, address):
            return True
    return False


def _llm_extraction_mentions_identity(raw_event: RawDiscoveredEvent, identity: _AnomalyIdentity) -> bool:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    symbol = identity.symbol.casefold()
    coin_id = (identity.coin_id or "").casefold()
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        try:
            confidence = float(mention.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.70:
            continue
        mention_type = clean_text(mention.get("mention_type"))
        if mention_type in {"publisher", "source noise", "ordinary word", "false positive"}:
            continue
        mention_coin = str(
            mention.get("resolved_coin_id")
            or mention.get("coin_id")
            or mention.get("asset_coin_id")
            or ""
        ).casefold()
        mention_symbol = str(mention.get("symbol") or "").casefold()
        resolver_validated = bool(
            mention.get("resolver_validated")
            or (coin_id and mention_coin == coin_id)
            or (symbol and mention_symbol == symbol)
        )
        if not (resolver_validated and ((coin_id and mention_coin == coin_id) or (symbol and mention_symbol == symbol))):
            continue
        quotes = mention.get("evidence_quotes")
        if isinstance(quotes, list) and quotes:
            source_text = " ".join(str(part or "") for part in (raw_event.title, raw_event.body, _event_name(raw_event)))
            if not any(
                isinstance(quote, Mapping)
                and str(quote.get("text") or "").strip()
                and str(quote.get("text") or "").strip() in source_text
                for quote in quotes
            ):
                continue
        return True
    return False


def _weighted_term_hits(text: str, weights: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(term for term in weights if term in text)


def _event_name(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event.get("event_name") or raw.title or "")


def _looks_generic_major_market_article(text: str) -> bool:
    return any(phrase in text for phrase in (
        "bitcoin price",
        "ethereum price",
        "crypto market",
        "market update",
        "market recap",
    ))


def _is_fixture_source(raw: RawDiscoveredEvent, *, provider_name: str) -> bool:
    provider = raw.provider.casefold()
    search_provider = provider_name.casefold()
    return (
        search_provider == "fixture"
        or "fixture" in provider
        or provider in {"manual_json", "manual"}
    )


def _annotate_search_source(
    raw: RawDiscoveredEvent,
    provider_name: str,
    query: SearchQuery,
) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    search_payload = dict(payload.get("market_anomaly_catalyst_search_source") or {})
    search_payload.update({
        "provider": provider_name,
        "query": query.query,
        "symbol": query.symbol,
        "coin_id": query.coin_id,
        "project_name": query.project_name,
        "aliases": list(query.aliases),
        "contract_addresses": list(query.contract_addresses),
        "is_common_word_symbol": query.is_common_word_symbol,
        "identity_terms": list(query.identity_terms),
        "query_score": query.score,
        "query_score_reasons": list(query.score_reasons),
        "research_only": True,
    })
    payload["market_anomaly_catalyst_search_source"] = search_payload
    return replace(raw, raw_json=payload, content_hash=_content_hash(payload))


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


def _raw_event_from_fixture(item: Mapping[str, Any]) -> RawDiscoveredEvent:
    fetched = _parse_dt(item.get("fetched_at")) or datetime.now(timezone.utc)
    published = _parse_dt(item.get("published_at")) or fetched
    payload = item.get("raw_json") if isinstance(item.get("raw_json"), Mapping) else dict(item)
    raw_id = str(item.get("raw_id") or payload.get("raw_id") or _content_hash(payload))
    return RawDiscoveredEvent(
        raw_id=raw_id,
        provider=str(item.get("provider") or "fixture_catalyst_search"),
        fetched_at=fetched,
        published_at=published,
        source_url=str(item.get("source_url") or "") or None,
        title=str(item.get("title") or ""),
        body=str(item.get("body") or "") or None,
        raw_json=dict(payload),
        source_confidence=float(item.get("source_confidence") or payload.get("source_confidence") or 0.75),
        content_hash=str(item.get("content_hash") or _content_hash(payload)),
    )


def _annotate_raw_event(raw: RawDiscoveredEvent, extra: Mapping[str, Any]) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    payload.update(extra)
    return replace(raw, raw_json=payload, content_hash=_content_hash(payload))


def _event_symbol(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
    asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else {}
    candidates = (
        market.get("symbol"),
        asset.get("symbol"),
        payload.get("symbol"),
    )
    for value in candidates:
        symbol = str(value or "").strip().upper()
        if symbol:
            return symbol
    title = raw.title.strip().split()
    if title:
        token = title[0].strip("():,").upper()
        if token and len(token) <= 12:
            return token
    return ""


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _content_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
