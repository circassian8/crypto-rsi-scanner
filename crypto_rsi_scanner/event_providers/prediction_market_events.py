"""Prediction-market catalyst provider for event discovery.

Fixtures remain the default for deterministic tests. Live Polymarket Gamma
ingestion is explicit opt-in, no-auth, fail-soft, and research-only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..event_models import RawDiscoveredEvent
from ._external_common import fetch_external_events
from ._news_common import infer_external_asset
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)

DEFAULT_POLYMARKET_GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

UrlOpen = Callable[[Request, float], Any]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class PredictionMarketEventsProvider:
    name = "prediction_market_events"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        base_url: str = DEFAULT_POLYMARKET_GAMMA_EVENTS_URL,
        limit: int = 100,
        timeout: float = 10.0,
        opener: UrlOpen | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        self.path = path
        self.required = required
        self.live_enabled = live_enabled
        self.base_url = base_url
        self.limit = limit
        self.timeout = timeout
        self.opener = opener or _urlopen_with_timeout
        self.fetched_at = fetched_at

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        if self.path is None and self.live_enabled:
            return self._fetch_live_events(start, end)
        return fetch_external_events(
            self.path,
            provider=self.name,
            default_event_type="external_proxy_event",
            start=start,
            end=end,
            required=self.required,
        )

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        try:
            request = Request(
                self._request_url(),
                headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"},
            )
            with self.opener(request, self.timeout) as response:
                status = getattr(response, "status", getattr(response, "code", 200))
                if int(status) >= 400:
                    raise RuntimeError(f"HTTP {status}")
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Prediction-market live event fetch failed: %s", exc)
            return []

        fetched_at = _as_utc(self.fetched_at or datetime.now(timezone.utc))
        rows = _polymarket_event_rows(payload)
        events: list[RawDiscoveredEvent] = []
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        for row in rows:
            event = _raw_polymarket_event(row, fetched_at)
            if event is None:
                continue
            event_time = _parse_time(event.raw_json.get("event", {}).get("event_time")) if event.raw_json else None
            reference_time = event_time or event.published_at or event.fetched_at
            if start_utc <= reference_time <= end_utc:
                events.append(event)
        return events

    def _request_url(self) -> str:
        query = {
            "active": "true",
            "closed": "false",
            "limit": str(max(1, min(500, int(self.limit or 100)))),
            "order": "volume_24hr",
            "ascending": "false",
        }
        separator = "&" if "?" in self.base_url else "?"
        return self.base_url + separator + urlencode(query)


def _polymarket_event_rows(payload: object) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("events", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
        if payload.get("title") or payload.get("question"):
            return [payload]
    return []


def _raw_polymarket_event(row: Mapping[str, Any], fetched_at: datetime) -> RawDiscoveredEvent | None:
    title = str(row.get("title") or row.get("question") or "").strip()
    if not title:
        return None
    body = str(row.get("description") or row.get("subtitle") or "")
    event_time = _polymarket_event_time(row)
    event_type = _polymarket_event_type(title, body, row)
    event_time_confidence = _event_time_confidence(row, event_time)
    published_at = _parse_time(
        row.get("createdAt")
        or row.get("creationDate")
        or row.get("startDate")
        or row.get("published_at")
    )
    slug = str(row.get("slug") or row.get("ticker") or "").strip()
    source_url = str(row.get("url") or row.get("market_url") or _polymarket_event_url(slug) or "").strip() or None
    raw_id = str(row.get("id") or slug or f"polymarket:{content_hash(dict(row))[:16]}")
    payload = dict(row)
    payload["event"] = {
        "event_name": title,
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": event_time_confidence,
        "external_asset": row.get("external_asset") or row.get("externalAsset") or _external_asset_hint(title, body),
        "confidence": float(row.get("source_confidence") or 0.78),
        "description": body or title,
    }
    payload["provider_source"] = "polymarket_gamma"
    return RawDiscoveredEvent(
        raw_id=f"{PredictionMarketEventsProvider.name}:polymarket:{raw_id}",
        provider=PredictionMarketEventsProvider.name,
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=source_url,
        title=title,
        body=body or None,
        raw_json=payload,
        source_confidence=float(row.get("source_confidence") or 0.78),
        content_hash=content_hash(payload),
    )


def _polymarket_event_time(row: Mapping[str, Any]) -> datetime | None:
    markets = row.get("markets")
    if isinstance(markets, list):
        market_times = [
            parsed
            for market in markets
            if isinstance(market, Mapping) and _market_is_usable_for_event_time(market)
            for parsed in (_parse_time(market.get("endDate") or market.get("end_date")),)
            if parsed is not None
        ]
        if market_times:
            return min(market_times)
    for key in ("event_time", "eventTime", "endDate", "end_date", "closedTime", "close_time"):
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _market_is_usable_for_event_time(market: Mapping[str, Any]) -> bool:
    if market.get("closed") is True or market.get("archived") is True:
        return False
    if market.get("active") is False:
        return False
    return True


def _polymarket_event_type(title: str, body: str, row: Mapping[str, Any]) -> str:
    configured = row.get("event_type") or row.get("eventType")
    if configured:
        return str(configured)
    text = f"{title} {body} {row.get('category') or ''} {row.get('subcategory') or ''}".casefold()
    if "ipo" in text or "pre-ipo" in text or "pre ipo" in text:
        return "ipo_proxy"
    if "election" in text or "inauguration" in text or "president" in text:
        return "political_event"
    if any(token in text for token in ("world cup", "match", "game", "league", "nba", "nfl", "mlb", "soccer")):
        return "sports_event"
    return "external_proxy_event"


def _event_time_confidence(row: Mapping[str, Any], event_time: datetime | None) -> float:
    if event_time is None:
        return 0.0
    raw = row.get("event_time") or row.get("eventTime") or row.get("endDate") or row.get("end_date")
    if isinstance(raw, str) and len(raw.strip()) <= 10:
        return 0.45
    return 0.90


def _external_asset_hint(title: str, body: str) -> str | None:
    text = f"{title} {body}".casefold()
    for name, aliases in (
        ("SpaceX", ("spacex",)),
        ("OpenAI", ("openai", "open ai", "chatgpt")),
        ("Anthropic", ("anthropic", "claude")),
        ("Kraken", ("kraken",)),
        ("World Cup", ("world cup",)),
        ("US election", ("us election", "presidential election", "election")),
    ):
        if any(alias in text for alias in aliases):
            return name
    return infer_external_asset(f"{title} {body}")


def _polymarket_event_url(slug: str) -> str | None:
    return f"https://polymarket.com/event/{slug}" if slug else None


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
