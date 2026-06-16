"""GDELT-style news provider for event discovery.

The default path is fixture-only for deterministic tests. Live HTTP ingestion is
explicit opt-in and research-only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..event_models import RawDiscoveredEvent
from ._news_common import _news_items, fetch_news_events, news_events_from_items

log = logging.getLogger(__name__)

DEFAULT_GDELT_QUERY = (
    '("pre-ipo" OR "pre ipo" OR "synthetic exposure" OR "tokenized stock" '
    'OR "prediction market" OR "fan token")'
)

UrlOpen = Callable[[Request, float], Any]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class GdeltProvider:
    name = "gdelt"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc",
        query: str = DEFAULT_GDELT_QUERY,
        max_records: int = 50,
        timeout: float = 10.0,
        opener: UrlOpen | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        self.path = path
        self.required = required
        self.live_enabled = live_enabled
        self.base_url = base_url
        self.query = query
        self.max_records = max_records
        self.timeout = timeout
        self.opener = opener or _urlopen_with_timeout
        self.fetched_at = fetched_at

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        if self.path is None and self.live_enabled:
            return self._fetch_live_events(start, end)
        return fetch_news_events(
            self.path,
            provider=self.name,
            start=start,
            end=end,
            required=self.required,
        )

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        url = self._request_url(start, end)
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"})
            with self.opener(request, self.timeout) as response:
                status = getattr(response, "status", getattr(response, "code", 200))
                if int(status) >= 400:
                    raise RuntimeError(f"HTTP {status}")
                raw = json.loads(response.read().decode("utf-8"))
            rows = _news_items(raw, allow_empty=True)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("GDELT live news fetch failed: %s", exc)
            return []

        # Live rows reuse the fixture parser/filter path so they inherit the same
        # event-type inference, point-in-time timestamps, and no-trade safety.
        return news_events_from_items(
            rows,
            provider=self.name,
            start=start,
            end=end,
            fetched_at=self.fetched_at or datetime.now(timezone.utc),
        )

    def _request_url(self, start: datetime, end: datetime) -> str:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        query = {
            "query": self.query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max(1, self.max_records),
            "sort": "datedesc",
            "startdatetime": start_utc.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_utc.strftime("%Y%m%d%H%M%S"),
        }
        separator = "&" if "?" in self.base_url else "?"
        return self.base_url + separator + urlencode(query)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
