"""Bybit announcement provider for event discovery.

The default path is fixture-only for deterministic tests. Live HTTP ingestion is
explicit opt-in and research-only.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ...event_core.models import RawDiscoveredEvent
from .._announcement_common import (
    _announcement_items,
    _announcement_items_with_acquisition_time,
    _raw_event_from_item,
    fetch_announcement_events,
)

log = logging.getLogger(__name__)

UrlOpen = Callable[[Request, float], Any]
BYBIT_ERROR_SUMMARY_MAX_CHARS = 320
_MAX_ERROR_RESPONSE_BYTES = 2_048
_SAFE_RESPONSE_HEADERS = frozenset({
    "cdn-request-id",
    "cf-ray",
    "content-type",
    "retry-after",
    "server",
    "x-amz-cf-id",
    "x-bapi-limit",
    "x-bapi-limit-reset-timestamp",
    "x-bapi-limit-status",
    "x-cache",
})
_RATE_LIMIT_MARKERS = (
    "access too frequent",
    "too many visits",
    "too many requests",
    "rate limit",
    "frequency protection",
)
_REGION_RESTRICTION_MARKERS = (
    "retcode 10009",
    '"retcode":10009',
    '"retcode": 10009',
    "block access from your country",
    "blocked access from your country",
    "service restricted",
    "unavailable for your region",
    "region is restricted",
    "restricted jurisdiction",
)


class BybitAPIResponseError(RuntimeError):
    """A successful HTTP response containing a non-zero Bybit return code."""

    def __init__(self, ret_code: int | str, ret_msg: str) -> None:
        self.ret_code = ret_code
        self.ret_msg = ret_msg
        super().__init__(f"Bybit retCode {ret_code}: {ret_msg or 'request rejected'}")


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


def build_bybit_public_request(url: str, *, request_id: str | None = None) -> Request:
    """Build a public Bybit request with a unique CDN diagnostic identifier."""
    diagnostic_id = str(request_id or uuid.uuid4().hex).strip()
    return Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "crypto-rsi-scanner/1.0",
            "cdn-request-id": diagnostic_id,
        },
    )


def raise_for_bybit_api_error(payload: object) -> None:
    """Raise when Bybit encodes an API failure in an otherwise successful HTTP response."""
    if not isinstance(payload, Mapping):
        return
    raw_code = payload.get("retCode")
    if raw_code in (None, "", 0, "0"):
        return
    raise BybitAPIResponseError(raw_code, str(payload.get("retMsg") or ""))


def classify_bybit_failure(status_codes: Iterable[int], diagnostic_text: str) -> str | None:
    """Classify public Bybit failures without treating every 403 as authentication."""
    codes = set(status_codes)
    text = str(diagnostic_text or "").casefold()
    if 429 in codes:
        return "rate_limited"
    if any(marker in text for marker in _REGION_RESTRICTION_MARKERS):
        return "region_restricted"
    if any(marker in text for marker in _RATE_LIMIT_MARKERS):
        return "rate_limited"
    if 401 in codes:
        return "auth_or_access_error"
    if 403 in codes:
        return "edge_forbidden"
    return None


def bybit_failure_message(row: Mapping[str, Any]) -> str:
    message = str(row.get("error_message_safe") or "").strip()
    summary = str(row.get("response_body_summary_redacted") or "").strip()
    if summary and summary.casefold() not in message.casefold():
        return f"{message}; response: {summary}"[:BYBIT_ERROR_SUMMARY_MAX_CHARS]
    return message[:BYBIT_ERROR_SUMMARY_MAX_CHARS]


def bybit_request_id(request: Request) -> str | None:
    for key, value in request.header_items():
        if str(key).casefold() == "cdn-request-id":
            return str(value).strip() or None
    return None


def bybit_response_diagnostics(
    *,
    response: Any | None,
    payload: bytes | None,
    error: Exception | None,
) -> dict[str, Any]:
    """Return a bounded, redacted diagnostic view of a Bybit HTTP response."""
    source = error if isinstance(error, HTTPError) else response
    headers = _safe_response_headers(source)
    raw = payload
    truncated = False
    if raw is None and isinstance(error, HTTPError):
        try:
            raw = error.read(_MAX_ERROR_RESPONSE_BYTES + 1)
        except Exception:  # noqa: BLE001 - diagnostics must never mask the provider error
            raw = None
    if raw is not None and len(raw) > _MAX_ERROR_RESPONSE_BYTES:
        raw = raw[:_MAX_ERROR_RESPONSE_BYTES]
        truncated = True
    summary = _redacted_response_summary(raw) if error is not None else None
    return {
        "response_headers_safe": headers,
        "response_body_summary_redacted": summary,
        "response_body_truncated": truncated,
        "response_bytes_captured": len(raw) if raw is not None and error is not None else 0,
    }


def _safe_response_headers(source: Any | None) -> dict[str, str]:
    if source is None:
        return {}
    headers = getattr(source, "headers", None) or getattr(source, "hdrs", None)
    if headers is None:
        return {}
    try:
        items = headers.items()
    except AttributeError:
        return {}
    return {
        str(key).casefold(): str(value)[:240]
        for key, value in items
        if str(key).casefold() in _SAFE_RESPONSE_HEADERS
    }


def _redacted_response_summary(raw: bytes | None) -> str | None:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip-redacted>", text)
    text = re.sub(r"(?i)\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f:]{1,4}\b", "<ip-redacted>", text)
    text = re.sub(
        r'''(?ix)(["']?(?:api[_-]?key|secret|token|authorization|cookie)["']?\s*[:=]\s*)
        (["']?)[^\s,;"'<>]+\2''',
        r"\1<redacted>",
        text,
    )
    text = " ".join(text.split())
    return text[:BYBIT_ERROR_SUMMARY_MAX_CHARS] or None


def initialize_bybit_announcement_provider(
    self: Any,
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
    acquisition_clock: Callable[[], datetime] | None = None,
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
    self.acquisition_clock = acquisition_clock or (lambda: datetime.now(timezone.utc))


def fetch_bybit_announcement_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    if self.path is None and self.live_enabled:
        return self._fetch_live_events(start, end)
    return fetch_announcement_events(
        self.path,
        provider=self.name,
        start=start,
        end=end,
        required=self.required,
    )


def fetch_bybit_live_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    url = self._request_url()
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    try:
        request = build_bybit_public_request(url)
        with self.opener(request, self.timeout) as response:
            response_bytes = response.read()
            acquired_at = self.acquisition_clock()
            raw = json.loads(response_bytes.decode("utf-8"))
        raise_for_bybit_api_error(raw)
        items = _announcement_items_with_acquisition_time(
            _announcement_items(raw),
            acquired_at=acquired_at,
        )
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


def build_bybit_request_url(self: Any) -> str:
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
