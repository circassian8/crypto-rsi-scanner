"""CryptoPanic-style news provider for event discovery.

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

UrlOpen = Callable[[Request, float], Any]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class CryptoPanicProvider:
    name = "cryptopanic"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        api_token: str = "",
        base_url: str = "https://cryptopanic.com/api/v1/posts/",
        public: bool = True,
        filter_name: str = "",
        currencies: str = "",
        regions: str = "",
        kind: str = "",
        search: str = "",
        timeout: float = 10.0,
        opener: UrlOpen | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        self.path = path
        self.required = required
        self.live_enabled = live_enabled
        self.api_token = api_token
        self.base_url = base_url
        self.public = public
        self.filter_name = filter_name
        self.currencies = currencies
        self.regions = regions
        self.kind = kind
        self.search = search
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
        token = self.api_token.strip()
        if not token:
            if self.required:
                raise ValueError("CryptoPanic live fetch requires RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN")
            log.warning("CryptoPanic live news fetch skipped: missing API token")
            return []
        url = self._request_url(token)
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
            log.warning("CryptoPanic live news fetch failed: %s", exc)
            return []

        return news_events_from_items(
            rows,
            provider=self.name,
            start=start,
            end=end,
            fetched_at=self.fetched_at or datetime.now(timezone.utc),
        )

    def _request_url(self, token: str) -> str:
        query = {
            "auth_token": token,
            "public": "true" if self.public else "false",
        }
        optional = {
            "filter": self.filter_name,
            "currencies": self.currencies,
            "regions": self.regions,
            "kind": self.kind,
            "search": self.search,
        }
        query.update({key: value for key, value in optional.items() if value})
        separator = "&" if "?" in self.base_url else "?"
        return self.base_url + separator + urlencode(query)
