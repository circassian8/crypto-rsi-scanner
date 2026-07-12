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
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..event_core.models import RawDiscoveredEvent
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initialize_gdelt_provider(self, *args, **kwargs)

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_gdelt_events(self, start, end)

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_gdelt_live_events(self, start, end)

    def _request_url(self, start: datetime, end: datetime) -> str:
        return build_gdelt_request_url(self, start, end)


def initialize_gdelt_provider(
    self: Any,
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
    self.last_warnings: tuple[str, ...] = ()
    self.last_status_code: int | None = None
    self.last_error_class: str | None = None
    self.last_retry_after: str | None = None


def fetch_gdelt_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    self.last_warnings = ()
    self.last_status_code = None
    self.last_error_class = None
    self.last_retry_after = None
    if self.path is None and self.live_enabled:
        return self._fetch_live_events(start, end)
    return fetch_news_events(
        self.path,
        provider=self.name,
        start=start,
        end=end,
        required=self.required,
    )


def fetch_gdelt_live_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    url = self._request_url(start, end)
    status_code: int | None = None
    try:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"})
        with self.opener(request, self.timeout) as response:
            status = getattr(response, "status", getattr(response, "code", 200))
            status_code = int(status)
            if status_code >= 400:
                raise HTTPError(url, status_code, f"HTTP {status_code}", getattr(response, "headers", None), None)
            raw = json.loads(response.read().decode("utf-8"))
        rows = _news_items(raw, allow_empty=True)
    except Exception as exc:  # noqa: BLE001
        status_code = status_code or _status_code_from_exception(exc)
        error_class = _gdelt_error_class(exc, status_code=status_code)
        retry_after = _retry_after_from_exception(exc)
        self.last_status_code = status_code
        self.last_error_class = error_class
        self.last_retry_after = retry_after
        warning = _gdelt_failure_warning(
            exc,
            error_class=error_class,
            status_code=status_code,
            retry_after=retry_after,
        )
        self.last_warnings = (warning,)
        if self.required:
            raise
        log.warning(warning)
        return []

    # Live rows reuse the fixture parser/filter path so they inherit the same
    # event-type inference, point-in-time timestamps, and no-trade safety.
    self.last_status_code = status_code
    self.last_error_class = None
    self.last_retry_after = None
    self.last_warnings = ()
    return news_events_from_items(
        rows,
        provider=self.name,
        start=start,
        end=end,
        fetched_at=self.fetched_at or datetime.now(timezone.utc),
    )


def build_gdelt_request_url(self: Any, start: datetime, end: datetime) -> str:
    start_utc = _as_utc(start)
    research_now = _as_utc(self.fetched_at or datetime.now(timezone.utc))
    end_utc = min(_as_utc(end), research_now)
    if start_utc > end_utc:
        start_utc = end_utc
    query = {
        "query": self.query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": min(250, max(1, self.max_records)),
        "sort": "datedesc",
        "startdatetime": start_utc.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end_utc.strftime("%Y%m%d%H%M%S"),
    }
    separator = "&" if "?" in self.base_url else "?"
    return self.base_url + separator + urlencode(query)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _status_code_from_exception(exc: BaseException) -> int | None:
    value = getattr(exc, "status", getattr(exc, "code", None))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _retry_after_from_exception(exc: BaseException) -> str | None:
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    value = headers.get("Retry-After") if hasattr(headers, "get") else None
    clean = str(value or "").strip()
    return clean or None


def _gdelt_error_class(exc: BaseException, *, status_code: int | None) -> str:
    if status_code in {403, 429}:
        # This is the existing provider-health taxonomy. Preserve the exact
        # status separately so operators can distinguish quota from access.
        return "rate_limited_or_forbidden"
    if status_code is not None and status_code >= 500:
        return "server_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_parse_error"
    if isinstance(exc, (TimeoutError, OSError)):
        return "network_error"
    return type(exc).__name__


def _gdelt_failure_warning(
    exc: BaseException,
    *,
    error_class: str,
    status_code: int | None,
    retry_after: str | None,
) -> str:
    parts = [f"GDELT live news fetch failed: {error_class}"]
    if status_code is not None:
        parts.append(f"status={status_code}")
    if retry_after:
        parts.append(f"retry_after={retry_after}")
    if status_code is None:
        detail = str(exc).strip()
        if detail:
            parts.append(detail)
    return " ".join(parts)
