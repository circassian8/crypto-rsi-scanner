"""Bybit announcement provider for event discovery.

The default path is fixture-only for deterministic tests. Live HTTP ingestion is
explicit opt-in and research-only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ..event_models import RawDiscoveredEvent
from ._announcement_common import fetch_announcement_events, _announcement_items, _raw_event_from_item

log = logging.getLogger(__name__)

UrlOpen = Callable[[Request, float], Any]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class BybitAnnouncementProvider:
    name = "bybit_announcements"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        base_url: str = "https://api.bybit.com",
        locale: str = "en-US",
        announcement_type: str = "new_crypto",
        tag: str = "",
        page: int = 1,
        limit: int = 20,
        timeout: float = 10.0,
        opener: UrlOpen | None = None,
    ) -> None:
        self.path = path
        self.required = required
        self.live_enabled = live_enabled
        self.base_url = base_url.rstrip("/") + "/"
        self.locale = locale
        self.announcement_type = announcement_type
        self.tag = tag
        self.page = page
        self.limit = limit
        self.timeout = timeout
        self.opener = opener or _urlopen_with_timeout

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        if self.path is None and self.live_enabled:
            return self._fetch_live_events(start, end)
        return fetch_announcement_events(
            self.path,
            provider=self.name,
            start=start,
            end=end,
            required=self.required,
        )

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        url = self._request_url()
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"})
            with self.opener(request, self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
            items = _announcement_items(raw)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Bybit live announcement fetch failed: %s", exc)
            return []

        # Reuse the same parser/filter path as fixtures so live ingestion cannot
        # bypass the direct-event and no-trade safety rules.
        events: list[RawDiscoveredEvent] = []
        for item in items:
            event = _raw_event_from_item(item, self.name)
            if event is None:
                continue
            reference = _as_utc(event.published_at or event.fetched_at)
            if start_utc <= reference <= end_utc:
                events.append(event)
        return events

    def _request_url(self) -> str:
        query = {
            "locale": self.locale,
            "page": max(1, self.page),
            "limit": max(1, self.limit),
        }
        if self.announcement_type:
            query["type"] = self.announcement_type
        if self.tag:
            query["tag"] = self.tag
        return urljoin(self.base_url, "v5/announcements/index") + "?" + urlencode(query)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
