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
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse

from . import event_identity
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
        max_fetches_per_search: int | None = None,
    ) -> None:
        self.event_provider_factory = event_provider_factory
        self.name = name
        self.lookback_hours = lookback_hours
        self.horizon_days = horizon_days
        self.filter_by_query = filter_by_query
        self.max_fetches_per_search = max_fetches_per_search

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
                if self.max_fetches_per_search is not None and fetch_count >= self.max_fetches_per_search:
                    warnings.append(
                        f"{self.name} search fetch cap reached after {fetch_count} fetch(es)"
                    )
                    break
                cache_misses += 1
                fetch_count += 1
                events = ()
                try:
                    provider = self.event_provider_factory(query)
                    events = tuple(provider.fetch_events(start, end))  # type: ignore[attr-defined]
                    provider_warnings = tuple(str(item) for item in getattr(provider, "last_warnings", ()) if str(item))
                    warnings.extend(provider_warnings)
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

        super().__init__(factory, name=self.name, max_fetches_per_search=int(kwargs.get("max_fetches_per_search") or 1))


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
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            skip_reasons={"profile_disabled": 1},
        )
    observed = _as_utc(now or datetime.now(timezone.utc))
    raw_event_rows = tuple(raw_events)
    all_anomalies = _market_anomaly_events(raw_event_rows)
    anomalies = _eligible_anomalies(raw_event_rows, cfg)
    queries = _queries_for_anomalies(anomalies, cfg)
    skip_reasons = _catalyst_search_skip_reasons(all_anomalies, anomalies, queries, cfg)
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
        skip_reasons = _merge_reason_counts(
            skip_reasons,
            getattr(provider_result, "skip_reasons", {}) or {},
            _skip_reasons_from_warnings(provider_result.warnings),
        )
    except Exception as exc:  # noqa: BLE001
        provider_reason = "provider_backoff" if "backoff" in str(exc).casefold() else "provider_unavailable"
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            queries=queries,
            warnings=(f"catalyst search provider failed: {exc}",),
            query_count=len(queries),
            skip_reasons=_merge_reason_counts(skip_reasons, {provider_reason: 1}),
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
        skip_reasons=skip_reasons,
    )


def run_hypothesis_search(
    hypotheses: Iterable[object],
    provider: CatalystSearchProvider,
    *,
    cfg: EventImpactHypothesisSearchConfig | None = None,
    now: datetime | None = None,
) -> CatalystSearchRunResult:
    """Search for asset-validation evidence around impact hypotheses.

    This is separate from market-anomaly catalyst search: accepted rows are
    source evidence for validating sector/venue/infrastructure hypotheses, not
    attachments to market anomaly parents.
    """
    cfg = cfg or EventImpactHypothesisSearchConfig()
    provider_name = getattr(provider, "name", "hypothesis_search")
    if not cfg.enabled:
        return CatalystSearchRunResult(provider=provider_name, skip_reasons={"profile_disabled": 1})
    observed = _as_utc(now or datetime.now(timezone.utc))
    eligible = _eligible_hypotheses(hypotheses, cfg)
    queries = _queries_for_hypotheses(eligible, cfg)
    hypothesis_by_id = {str(getattr(item, "hypothesis_id", "") or ""): item for item in tuple(hypotheses)}
    skip_reasons = _hypothesis_search_skip_reasons(tuple(hypotheses), eligible, queries, cfg)
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
        skip_reasons = _merge_reason_counts(
            skip_reasons,
            getattr(provider_result, "skip_reasons", {}) or {},
            _skip_reasons_from_warnings(provider_result.warnings),
        )
    except Exception as exc:  # noqa: BLE001 - research providers must fail soft.
        provider_reason = "provider_backoff" if "backoff" in str(exc).casefold() else "provider_unavailable"
        return CatalystSearchRunResult(
            provider=provider_name,
            queries=queries,
            warnings=(f"hypothesis search provider failed: {exc}",),
            query_count=len(queries),
            skip_reasons=_merge_reason_counts(skip_reasons, {provider_reason: 1}),
        )

    accepted_results: list[SearchResultEvent] = []
    rejected_results: list[SearchResultEvent] = list(provider_rejected)
    result_skip_reasons: dict[str, int] = {}
    threshold = _confidence_threshold(cfg.min_result_confidence)
    seen_content: set[str] = set()
    for result in provider_events:
        score = score_search_result(result.raw_event, result.query, None, now=observed)
        reasons = list(score.reason_codes)
        content_key = result.raw_event.content_hash or _content_hash(result.raw_event.raw_json or {})
        if content_key in seen_content:
            score = CatalystSearchScore(max(0, score.score - 25), (*score.reason_codes, "duplicate_content_penalty"))
            reasons = list(score.reason_codes)
        else:
            seen_content.add(content_key)
        hypothesis = hypothesis_by_id.get(result.query.anomaly_raw_id)
        query_type = str(getattr(result.query, "query_type", "") or "candidate_validation")
        catalyst_ok = _result_mentions_hypothesis_catalyst(result.raw_event, hypothesis)
        if not catalyst_ok:
            reasons.append("result_catalyst_missing")
            result_skip_reasons["result_catalyst_missing"] = result_skip_reasons.get("result_catalyst_missing", 0) + 1
            rejected_results.append(replace(
                result,
                result_score=min(score.score, 45),
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        identity_ok = result_mentions_anomaly_identity(result.raw_event, result.query, None)
        if query_type == "candidate_discovery":
            asset_ok = _candidate_discovery_asset_present(result.raw_event)
            if not asset_ok:
                reasons.append("candidate_discovery_asset_missing")
                result_skip_reasons["candidate_discovery_asset_missing"] = result_skip_reasons.get("candidate_discovery_asset_missing", 0) + 1
                rejected_results.append(replace(
                    result,
                    result_score=min(score.score, 45),
                    result_score_reasons=tuple(dict.fromkeys(reasons)),
                    accepted=False,
                ))
                continue
        elif cfg.require_validated_identity and not identity_ok:
            reasons.append("result_identity_rejected")
            result_skip_reasons["result_identity_rejected"] = result_skip_reasons.get("result_identity_rejected", 0) + 1
            rejected_results.append(replace(
                result,
                result_score=min(score.score, 45),
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        scored = replace(
            result,
            raw_event=_annotate_hypothesis_search_result(result.raw_event, score.score, reasons, result.query),
            result_score=score.score,
            result_score_reasons=tuple(dict.fromkeys(reasons)),
            accepted=score.score >= threshold,
        )
        if scored.accepted:
            accepted_results.append(scored)
        else:
            result_skip_reasons["result_score_below_threshold"] = result_skip_reasons.get("result_score_below_threshold", 0) + 1
            rejected_results.append(scored)
    return CatalystSearchRunResult(
        provider=provider_name,
        queries=queries,
        result_events=tuple(accepted_results),
        rejected_result_events=tuple(rejected_results),
        warnings=tuple(dict.fromkeys(warnings)),
        provider_fetch_count=provider_result.provider_fetch_count,
        provider_cache_hits=provider_result.provider_cache_hits,
        provider_cache_misses=provider_result.provider_cache_misses,
        query_count=len(queries),
        result_count=len(accepted_results),
        rejected_count=len(rejected_results),
        skip_reasons=_merge_reason_counts(skip_reasons, result_skip_reasons),
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


def generate_search_queries_for_hypothesis(hypothesis: object) -> tuple[str, ...]:
    """Return targeted validation queries for an Event Alpha impact hypothesis.

    The hypothesis object is intentionally duck-typed to avoid making catalyst
    search depend on hypothesis generation. Results still need resolver and
    identity validation before they can promote anything beyond review evidence.
    """
    return tuple(item.query for item in generate_search_query_specs_for_hypothesis(hypothesis))


@dataclass(frozen=True)
class HypothesisSearchQuerySpec:
    query: str
    query_type: str = "candidate_validation"


def generate_search_query_specs_for_hypothesis(hypothesis: object) -> tuple[HypothesisSearchQuerySpec, ...]:
    """Return typed validation/discovery query specs for an impact hypothesis."""
    category = str(getattr(hypothesis, "impact_category", "") or "")
    external = str(getattr(hypothesis, "external_asset", "") or "").strip()
    symbols = tuple(str(symbol).strip().upper() for symbol in getattr(hypothesis, "candidate_symbols", ()) or () if str(symbol).strip())
    sectors = tuple(str(sector) for sector in getattr(hypothesis, "candidate_sectors", ()) or ())
    out: list[HypothesisSearchQuerySpec] = []
    for symbol in symbols[:8]:
        if external and category in {"rwa_preipo_proxy", "tokenized_stock_venue"}:
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} {external} exposure"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO exposure"),
                HypothesisSearchQuerySpec(f"{symbol} tokenized stock {external}"),
                HypothesisSearchQuerySpec(f"{symbol} {external} prediction market"),
            ))
        elif external and category == "ai_ipo_proxy":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} {external} exposure"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO exposure"),
                HypothesisSearchQuerySpec(f"{symbol} tokenized stock {external}"),
                HypothesisSearchQuerySpec(f"{symbol} {external} perp"),
                HypothesisSearchQuerySpec(f"{symbol} AI IPO proxy"),
            ))
        elif category == "sports_fan_proxy":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} World Cup fan token"),
                HypothesisSearchQuerySpec(f"{symbol} sports event prediction market"),
            ))
        elif category == "stablecoin_regulatory":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} GENIUS Act stablecoin"),
                HypothesisSearchQuerySpec(f"{symbol} stablecoin reserve regulation"),
            ))
        elif category == "listing_liquidity_event":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} listing"), HypothesisSearchQuerySpec(f"{symbol} Binance listing")))
        elif category == "unlock_supply_pressure":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} unlock"), HypothesisSearchQuerySpec(f"{symbol} token vesting unlock")))
        elif category == "perp_venue_attention":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} perp listing"), HypothesisSearchQuerySpec(f"{symbol} futures listing")))
        elif category == "prediction_market_infra":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} prediction market oracle"), HypothesisSearchQuerySpec(f"{symbol} polymarket infrastructure")))
        elif category == "security_or_regulatory_shock":
            out.append(HypothesisSearchQuerySpec(f"{symbol} exploit hack regulatory"))
        else:
            qtype = "market_confirmation" if category == "market_anomaly_unknown" else "candidate_validation"
            out.append(HypothesisSearchQuerySpec(f"{symbol} crypto catalyst", qtype))
    if external and category in {
        "rwa_preipo_proxy",
        "ai_ipo_proxy",
        "tokenized_stock_venue",
        "sports_fan_proxy",
        "political_meme_proxy",
        "prediction_market_infra",
        "perp_venue_attention",
    }:
        out.extend(HypothesisSearchQuerySpec(query, "candidate_discovery") for query in _candidate_discovery_queries(external, sectors, category))
    elif not out:
        discovery_terms: list[str] = []
        for sector in sectors[:4]:
            clean = sector.replace("_", " ")
            if external:
                discovery_terms.append(f"{external} {clean} crypto")
            else:
                discovery_terms.append(f"{clean} crypto catalyst candidates")
        out.extend(HypothesisSearchQuerySpec(query, "candidate_discovery") for query in discovery_terms)
    deduped: dict[str, HypothesisSearchQuerySpec] = {}
    for item in out:
        query = str(item.query or "").strip()
        if query:
            deduped.setdefault(query, HypothesisSearchQuerySpec(query, item.query_type))
    return tuple(deduped.values())


def _candidate_discovery_queries(external: str, sectors: Iterable[str], category: str) -> tuple[str, ...]:
    sector_rows = tuple(sectors)
    discovery_terms: list[str] = [
        f"{external} crypto exposure",
        f"{external} tokenized stock crypto",
        f"{external} pre-IPO crypto",
        f"{external} prediction market token",
        f"{external} perp crypto",
        f"{external} synthetic exposure crypto",
        f"{external} crypto venue",
    ]
    for sector in sector_rows[:4]:
        clean = str(sector).replace("_", " ").strip()
        if clean:
            discovery_terms.append(f"{external} {clean} crypto")
    if not sector_rows:
        discovery_terms.append(f"{external} {category.replace('_', ' ')} crypto")
    return tuple(discovery_terms)


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
            query_type="market_confirmation",
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
    elif identity_missing and not candidate_discovery_asset:
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
    if result.skip_reasons:
        rows.append(
            "skip_reasons: "
            + ", ".join(f"{key}={value}" for key, value in sorted(result.skip_reasons.items()))
        )
    if result.warnings:
        rows.append("warnings: " + "; ".join(result.warnings))
    if result.queries:
        rows.append("")
        rows.append("Queries:")
        for query in result.queries[:20]:
            reason_text = f" ({', '.join(query.score_reasons)})" if query.score_reasons else ""
            rows.append(f"- {query.symbol} #{query.rank} {query.query_type}: score={query.score} {query.query}{reason_text}")
    if result.result_events:
        rows.append("")
        rows.append("Accepted result evidence:")
        for event in result.result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol} {event.query.query_type}: score={event.result_score} "
                f"{event.raw_event.title} [{event.raw_event.provider}]{reason_text}"
            )
    if result.rejected_result_events:
        rows.append("")
        rows.append("Rejected result evidence:")
        for event in result.rejected_result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol} {event.query.query_type}: score={event.result_score} "
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


def _market_anomaly_events(raw_events: Iterable[RawDiscoveredEvent]) -> tuple[RawDiscoveredEvent, ...]:
    out: list[RawDiscoveredEvent] = []
    for raw in raw_events:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        if raw.provider == "market_anomaly" or isinstance(payload.get("anomaly"), Mapping):
            out.append(raw)
    return tuple(out)


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


def _eligible_hypotheses(
    hypotheses: Iterable[object],
    cfg: EventImpactHypothesisSearchConfig,
) -> tuple[object, ...]:
    candidates: list[tuple[float, str, object]] = []
    for hypothesis in hypotheses:
        try:
            confidence = float(getattr(hypothesis, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        status = str(getattr(hypothesis, "status", "") or "")
        if status == "validated":
            continue
        if confidence < cfg.min_confidence:
            continue
        if not tuple(getattr(hypothesis, "candidate_symbols", ()) or ()) and not (
            str(getattr(hypothesis, "external_asset", "") or "").strip()
            or tuple(getattr(hypothesis, "candidate_sectors", ()) or ())
        ):
            continue
        candidates.append((confidence, str(getattr(hypothesis, "hypothesis_id", "") or ""), hypothesis))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(item[2] for item in candidates[: max(0, cfg.max_hypotheses)])


def _queries_for_hypotheses(
    hypotheses: Iterable[object],
    cfg: EventImpactHypothesisSearchConfig,
) -> tuple[SearchQuery, ...]:
    out: list[SearchQuery] = []
    discovery_count = 0
    for hypothesis in hypotheses:
        all_specs = generate_search_query_specs_for_hypothesis(hypothesis)
        validation_specs = [spec for spec in all_specs if spec.query_type != "candidate_discovery"]
        discovery_specs = [spec for spec in all_specs if spec.query_type == "candidate_discovery"]
        specs = validation_specs[: max(0, cfg.max_queries_per_hypothesis)]
        if cfg.candidate_discovery_enabled and discovery_count < max(0, cfg.max_candidate_discovery_queries):
            room = max(0, cfg.max_candidate_discovery_queries - discovery_count)
            selected = discovery_specs[:room]
            specs = [*specs, *selected]
            discovery_count += len(selected)
        base_queries = tuple(spec.query for spec in specs)
        identity_by_query = _hypothesis_query_identities(hypothesis, base_queries)
        for idx, spec in enumerate(specs):
            query_text = spec.query
            identity = identity_by_query.get(query_text) or _HypothesisIdentity(symbol="SECTOR")
            base = SearchQuery(
                anomaly_raw_id=str(getattr(hypothesis, "hypothesis_id", "") or "hypothesis"),
                query=query_text,
                symbol=identity.symbol,
                rank=idx + 1,
                query_type=spec.query_type,
                coin_id=identity.coin_id,
                project_name=identity.project_name,
                aliases=identity.aliases,
                contract_addresses=identity.contract_addresses,
                is_common_word_symbol=identity.symbol.upper() in COMMON_WORD_SYMBOLS,
                identity_terms=identity.identity_terms,
            )
            score = score_search_query(base, None)
            out.append(replace(base, score=score.score, score_reasons=score.reason_codes))
    return tuple(out)


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


def _hypothesis_query_identities(hypothesis: object, query_texts: Iterable[str]) -> dict[str, _HypothesisIdentity]:
    symbols = tuple(str(symbol).strip().upper() for symbol in getattr(hypothesis, "candidate_symbols", ()) or () if str(symbol).strip())
    coin_ids = tuple(str(coin_id).strip() for coin_id in getattr(hypothesis, "candidate_coin_ids", ()) or () if str(coin_id).strip())
    out: dict[str, _HypothesisIdentity] = {}
    for query in query_texts:
        query_clean = clean_text(query)
        for idx, symbol in enumerate(symbols):
            if not symbol:
                continue
            coin_id = coin_ids[idx] if idx < len(coin_ids) else None
            symbol_pattern = rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])"
            coin_text = clean_text(coin_id or "")
            if re.search(symbol_pattern, query_clean) or (coin_text and coin_text in query_clean):
                out[query] = _HypothesisIdentity(
                    symbol=symbol,
                    coin_id=coin_id,
                    project_name=coin_id.replace("-", " ").title() if coin_id else None,
                    aliases=(coin_id.replace("-", " ") if coin_id else ""),
                )
                break
    return out


def _candidate_discovery_asset_present(raw_event: RawDiscoveredEvent) -> bool:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    for key in ("candidate_asset", "asset", "market"):
        value = payload.get(key)
        if not isinstance(value, Mapping):
            continue
        if any(str(value.get(field) or "").strip() for field in ("symbol", "asset_symbol", "coin_id", "id", "name", "project_name", "contract_address", "address")):
            return True
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        mention_type = clean_text(mention.get("mention_type"))
        if mention_type in {"publisher or source", "publisher_or_source", "ordinary word", "ordinary_word", "false positive"}:
            continue
        try:
            confidence = float(mention.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.70:
            continue
        if any(str(mention.get(field) or "").strip() for field in ("symbol", "coin_id", "name", "contract_address")):
            return True
    return False


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


def _result_mentions_hypothesis_catalyst(raw_event: RawDiscoveredEvent, hypothesis: object | None) -> bool:
    """Return true when a hypothesis-search result still mentions the catalyst context."""
    if hypothesis is None:
        return True
    text = clean_text(" ".join(str(part or "") for part in (
        raw_event.title,
        raw_event.body,
        _event_payload_value(raw_event, "event_name"),
        _event_payload_value(raw_event, "event_type"),
        _event_payload_value(raw_event, "external_asset"),
        _event_payload_value(raw_event, "description"),
    )))
    if not text:
        return False
    external = clean_text(getattr(hypothesis, "external_asset", "") or "")
    if external and _text_contains_term(text, external):
        return True
    category = str(getattr(hypothesis, "impact_category", "") or "")
    terms_by_category = {
        "rwa_preipo_proxy": ("pre ipo", "pre-ipo", "spacex", "tokenized stock", "synthetic exposure"),
        "ai_ipo_proxy": ("openai", "anthropic", "pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure"),
        "tokenized_stock_venue": ("tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo"),
        "sports_fan_proxy": ("world cup", "champions league", "fan token", "sports", "fixture", "kickoff"),
        "political_meme_proxy": ("election", "inauguration", "campaign", "debate", "political"),
        "stablecoin_regulatory": ("genius act", "stablecoin", "reserve", "regulation", "regulatory"),
        "prediction_market_infra": ("prediction market", "polymarket", "oracle", "resolution"),
        "perp_venue_attention": ("perp", "perpetual", "futures listing"),
        "unlock_supply_pressure": ("unlock", "vesting", "airdrop", "tge"),
        "listing_liquidity_event": ("listing", "listed on", "binance", "coinbase", "bybit"),
        "security_or_regulatory_shock": ("exploit", "hack", "lawsuit", "regulatory", "sec", "cftc"),
        "market_anomaly_unknown": ("catalyst", "listing", "unlock", "airdrop", "exploit", "partnership"),
    }.get(category, tuple(CATALYST_TERM_WEIGHTS))
    return any(_text_contains_term(text, term) for term in terms_by_category)


def _event_payload_value(raw_event: RawDiscoveredEvent, key: str) -> str:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event_payload.get(key) or payload.get(key) or "")


def _text_contains_term(text: str, term: str) -> bool:
    source = clean_text(text)
    needle = clean_text(term)
    if not source or not needle:
        return False
    escaped = re.escape(needle).replace("\\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", source) is not None


def _annotate_hypothesis_search_result(
    raw_event: RawDiscoveredEvent,
    score: int,
    reasons: Iterable[str],
    query: SearchQuery,
) -> RawDiscoveredEvent:
    return _annotate_raw_event(
        raw_event,
        {
            "impact_hypothesis_search": {
                "role": "validation_source_evidence",
                "hypothesis_id": query.anomaly_raw_id,
                "query": query.query,
                "query_type": query.query_type,
                "symbol": query.symbol,
                "score": score,
                "reasons": list(reasons),
                "research_only": True,
            }
        },
    )


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
    strong_fields = (
        raw_event.title,
        raw_event.body,
        _event_name(raw_event),
        event_payload.get("description"),
    )
    result = event_identity.match_asset_identity(
        _shared_identity(identity),
        event_identity.IdentityEvidence(
            strong_content=tuple(str(field or "") for field in strong_fields),
            llm_quotes=(
                event_identity.validated_llm_identity_quotes(payload, strong_fields)
                or ((identity.symbol,) if _llm_extraction_mentions_identity(raw_event, identity) else ())
            ),
            url=str(raw_event.source_url or ""),
            source_origin=(_source_origin_text(raw_event),),
        ),
    )
    return result.reason


def _shared_identity(identity: _AnomalyIdentity) -> event_identity.AssetIdentity:
    return event_identity.AssetIdentity(
        symbol=identity.symbol.upper(),
        coin_id=identity.coin_id,
        project_name=identity.project_name,
        aliases=tuple(identity.aliases),
        contract_addresses=tuple(identity.contract_addresses),
        is_common_word_symbol=identity.is_common_word_symbol,
        identity_terms=tuple(identity.identity_terms),
    )


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
        "query_type": query.query_type,
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
