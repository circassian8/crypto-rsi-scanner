"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (providers)."""

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
        self._loaded_rows = _load_fixture_search_rows(
            self.rows_by_query,
            self.path,
            required=self.required,
        )
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
        return _search_event_provider_queries(
            self,
            queries,
            max_results_per_query=max_results_per_query,
            now=now,
        )

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        return (self.name, query.query)


def _load_fixture_search_rows(
    rows_by_query: Mapping[str, tuple[RawDiscoveredEvent, ...]],
    path: Path | None,
    *,
    required: bool,
) -> dict[str, tuple[RawDiscoveredEvent, ...]]:
    if rows_by_query:
        return dict(rows_by_query)
    if path is None:
        return {}
    if not path.exists():
        if required:
            raise FileNotFoundError(f"fixture catalyst-search rows not found: {path}")
        log.warning("Fixture catalyst-search rows missing: %s", path)
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("search_results", raw) if isinstance(raw, Mapping) else raw
        if not isinstance(rows, list):
            raise ValueError("fixture catalyst-search file must be a list or {'search_results': [...]}")
        loaded: dict[str, list[RawDiscoveredEvent]] = {}
        for item in rows:
            if not isinstance(item, Mapping):
                raise ValueError("fixture catalyst-search rows must be objects")
            query = str(item.get("query") or item.get("query_contains") or "").strip()
            event_obj = item.get("raw_event") if isinstance(item.get("raw_event"), Mapping) else item
            loaded.setdefault(query, []).append(_raw_event_from_fixture(event_obj))
        return {key: tuple(value) for key, value in loaded.items()}
    except Exception as exc:  # noqa: BLE001
        if required:
            raise
        log.warning("Fixture catalyst-search rows failed to load: %s", exc)
        return {}


def _search_event_provider_queries(
    provider_adapter: EventProviderCatalystSearchProvider,
    queries: Iterable[SearchQuery],
    *,
    max_results_per_query: int,
    now: datetime | None = None,
) -> CatalystSearchRunResult:
    observed = _as_utc(now or datetime.now(timezone.utc))
    start = observed - timedelta(hours=max(0.0, provider_adapter.lookback_hours))
    end = observed + timedelta(days=max(0.0, provider_adapter.horizon_days))
    query_rows = tuple(queries)
    result_events: list[SearchResultEvent] = []
    warnings: list[str] = []
    cache: dict[tuple[str, ...], tuple[RawDiscoveredEvent, ...]] = {}
    fetch_count = 0
    cache_hits = 0
    cache_misses = 0
    for query in query_rows:
        cache_key = provider_adapter.cache_key_for_query(query)
        if cache_key in cache:
            events = cache[cache_key]
            cache_hits += 1
        else:
            if provider_adapter.max_fetches_per_search is not None and fetch_count >= provider_adapter.max_fetches_per_search:
                warnings.append(f"{provider_adapter.name} search fetch cap reached after {fetch_count} fetch(es)")
                break
            cache_misses += 1
            fetch_count += 1
            events = _fetch_provider_search_events(provider_adapter, query, start=start, end=end, warnings=warnings)
            cache[cache_key] = events
        matched = _filter_provider_search_events(
            provider_adapter,
            query,
            events,
            max_results_per_query=max_results_per_query,
            warnings=warnings,
        )
        for raw in matched:
            result_events.append(SearchResultEvent(
                query=query,
                raw_event=_annotate_search_source(raw, provider_adapter.name, query),
            ))
    return CatalystSearchRunResult(
        provider=provider_adapter.name,
        queries=query_rows,
        result_events=tuple(result_events),
        warnings=tuple(dict.fromkeys(warnings)),
        provider_fetch_count=fetch_count,
        provider_cache_hits=cache_hits,
        provider_cache_misses=cache_misses,
        query_count=len(query_rows),
        result_count=len(result_events),
    )


def _fetch_provider_search_events(
    provider_adapter: EventProviderCatalystSearchProvider,
    query: SearchQuery,
    *,
    start: datetime,
    end: datetime,
    warnings: list[str],
) -> tuple[RawDiscoveredEvent, ...]:
    try:
        provider = provider_adapter.event_provider_factory(query)
        events = tuple(provider.fetch_events(start, end))  # type: ignore[attr-defined]
        provider_warnings = tuple(str(item) for item in getattr(provider, "last_warnings", ()) if str(item))
        warnings.extend(provider_warnings)
        return events
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{provider_adapter.name} search failed for {query.query!r}: {exc}")
        return ()


def _filter_provider_search_events(
    provider_adapter: EventProviderCatalystSearchProvider,
    query: SearchQuery,
    events: tuple[RawDiscoveredEvent, ...],
    *,
    max_results_per_query: int,
    warnings: list[str],
) -> list[RawDiscoveredEvent]:
    try:
        return [
            raw for raw in events
            if not provider_adapter.filter_by_query or _raw_event_matches_query(raw, query)
        ][: max(0, max_results_per_query)]
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{provider_adapter.name} filter failed for {query.query!r}: {exc}")
        return []
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
        self._configured_currencies = kwargs.get("currencies")
        self._filter_name = str(kwargs.get("filter_name") or "")
        self._kind = str(kwargs.get("kind") or "news")
        self._public = bool(kwargs.get("public", True))
        self._following = bool(kwargs.get("following", False))

        def factory(query: SearchQuery) -> CryptoPanicProvider:
            return CryptoPanicProvider(
                kwargs.get("path"),
                required=bool(kwargs.get("required", False)),
                live_enabled=bool(kwargs.get("live_enabled", False)),
                api_token=str(kwargs.get("api_token") or ""),
                base_url=str(kwargs.get("base_url") or "https://cryptopanic.com/api/growth_weekly/v2"),
                plan=str(kwargs.get("plan") or "growth_weekly"),
                public=bool(kwargs.get("public", True)),
                following=bool(kwargs.get("following", False)),
                filter_name=str(kwargs.get("filter_name") or ""),
                currencies=_cryptopanic_currencies_for_query(query, kwargs.get("currencies")),
                regions=str(kwargs.get("regions") or "en"),
                kind=str(kwargs.get("kind") or "news"),
                search=query.query,
                timeout=float(kwargs.get("timeout") or 10.0),
                opener=kwargs.get("opener"),
                fetched_at=kwargs.get("fetched_at"),
                request_ledger_path=kwargs.get("request_ledger_path"),
                profile=str(kwargs.get("profile") or ""),
                artifact_namespace=str(kwargs.get("artifact_namespace") or ""),
                weekly_request_limit=int(kwargs.get("weekly_request_limit") or 600),
                requests_per_run_limit=int(kwargs.get("requests_per_run_limit") or 20),
                requests_per_day_soft_limit=int(kwargs.get("requests_per_day_soft_limit") or 80),
                min_seconds_between_requests=float(kwargs.get("min_seconds_between_requests") or 1.0),
                max_pages_per_query=int(kwargs.get("max_pages_per_query") or 1),
                max_currencies_per_request=int(kwargs.get("max_currencies_per_request") or 10),
            )

        super().__init__(factory, name=self.name)

    def cache_key_for_query(self, query: SearchQuery) -> tuple[str, ...]:
        currencies = _cryptopanic_currencies_for_query(query, self._configured_currencies)
        return (
            self.name,
            currencies,
            self._filter_name.strip().lower(),
            self._kind.strip().lower(),
            "following" if self._following else ("public" if self._public else "private"),
        )
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
