"""Offline catalyst-search scaffolding for market-anomaly research rows.

This module does not fetch search results or create alerts. It only generates
review queries and attaches externally supplied source events to a market
anomaly so the normal discovery/resolver/classifier pipeline can validate them.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .event_models import RawDiscoveredEvent

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


@dataclass(frozen=True)
class EventCatalystSearchConfig:
    enabled: bool = False
    provider: str = "fixture"
    max_anomalies: int = 10
    max_queries_per_anomaly: int = 6
    max_results_per_query: int = 5
    min_anomaly_score: int = 60


@dataclass(frozen=True)
class SearchQuery:
    anomaly_raw_id: str
    query: str
    symbol: str
    rank: int


@dataclass(frozen=True)
class SearchResultEvent:
    query: SearchQuery
    raw_event: RawDiscoveredEvent


@dataclass(frozen=True)
class CatalystSearchRunResult:
    provider: str
    queries: tuple[SearchQuery, ...] = ()
    result_events: tuple[SearchResultEvent, ...] = ()
    attached_raw_events: tuple[RawDiscoveredEvent, ...] = ()
    warnings: tuple[str, ...] = ()


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
        query_rows = self._load_rows()
        result_events: list[SearchResultEvent] = []
        warnings: list[str] = []
        for query in queries:
            matches = _fixture_matches(query_rows, query.query)
            for raw in matches[: max(0, max_results_per_query)]:
                result_events.append(SearchResultEvent(query=query, raw_event=raw))
        return CatalystSearchRunResult(
            provider=self.name,
            queries=tuple(queries),
            result_events=tuple(result_events),
            warnings=tuple(warnings),
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
    warnings: list[str] = []
    try:
        provider_result = provider.search(
            queries,
            max_results_per_query=cfg.max_results_per_query,
            now=observed,
        )
        warnings.extend(provider_result.warnings)
        result_events = provider_result.result_events
    except Exception as exc:  # noqa: BLE001
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            queries=queries,
            warnings=(f"catalyst search provider failed: {exc}",),
        )
    grouped: dict[str, list[RawDiscoveredEvent]] = {}
    for result in result_events:
        grouped.setdefault(result.query.anomaly_raw_id, []).append(result.raw_event)
    attached: list[RawDiscoveredEvent] = []
    for anomaly in anomalies:
        attached.extend(attach_search_results_to_anomaly(anomaly, grouped.get(anomaly.raw_id, ())))
    return CatalystSearchRunResult(
        provider=getattr(provider, "name", cfg.provider),
        queries=queries,
        result_events=tuple(result_events),
        attached_raw_events=tuple(attached),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def generate_search_queries_for_anomaly(raw_market_anomaly_event: RawDiscoveredEvent) -> tuple[str, ...]:
    """Return deterministic review queries for a market-anomaly raw event."""
    symbol = _event_symbol(raw_market_anomaly_event)
    if not symbol:
        return ()
    return tuple(template.format(symbol=symbol) for template in QUERY_TEMPLATES)


def generate_search_query_objects_for_anomaly(
    raw_market_anomaly_event: RawDiscoveredEvent,
    *,
    max_queries: int | None = None,
) -> tuple[SearchQuery, ...]:
    symbol = _event_symbol(raw_market_anomaly_event)
    queries = generate_search_queries_for_anomaly(raw_market_anomaly_event)
    if max_queries is not None:
        queries = queries[: max(0, max_queries)]
    return tuple(
        SearchQuery(
            anomaly_raw_id=raw_market_anomaly_event.raw_id,
            query=query,
            symbol=symbol,
            rank=idx + 1,
        )
        for idx, query in enumerate(queries)
    )


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
        f"results={len(result.result_events)} · attached_raw_events={len(result.attached_raw_events)}"
    )
    if result.warnings:
        rows.append("warnings: " + "; ".join(result.warnings))
    if result.queries:
        rows.append("")
        rows.append("Queries:")
        for query in result.queries[:20]:
            rows.append(f"- {query.symbol} #{query.rank}: {query.query}")
    if result.result_events:
        rows.append("")
        rows.append("Result evidence:")
        for event in result.result_events[:20]:
            rows.append(f"- {event.query.symbol}: {event.raw_event.title} [{event.raw_event.provider}]")
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
