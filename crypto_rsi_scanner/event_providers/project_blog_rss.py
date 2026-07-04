"""Project blog/RSS news provider for event discovery.

The default path is fixture-only for deterministic tests. Live RSS/Atom
ingestion is explicit opt-in and research-only.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
from ..event_core.models import RawDiscoveredEvent
from ._news_common import fetch_news_events, news_events_from_items

log = logging.getLogger(__name__)

UrlOpen = Callable[[Request, float], Any]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class ProjectBlogRssProvider:
    name = "project_blog_rss"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initialize_project_blog_rss_provider(self, *args, **kwargs)

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_project_blog_rss_events(self, start, end)

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_project_blog_rss_live_events(self, start, end)


def initialize_project_blog_rss_provider(
    self: Any,
    path: str | Path | None,
    *,
    required: bool = False,
    live_enabled: bool = False,
    feed_urls: Iterable[str] | None = None,
    timeout: float = 10.0,
    fail_fast_on_error: bool = False,
    opener: UrlOpen | None = None,
    fetched_at: datetime | None = None,
) -> None:
    self.path = path
    self.required = required
    self.live_enabled = live_enabled
    self.feed_urls = tuple(url.strip() for url in (feed_urls or ()) if url.strip())
    self.timeout = timeout
    self.fail_fast_on_error = fail_fast_on_error
    self.opener = opener or _urlopen_with_timeout
    self.fetched_at = fetched_at
    self.last_warnings: tuple[str, ...] = ()
    self.last_feed_health: tuple[event_source_registry.FeedHealth, ...] = ()


def fetch_project_blog_rss_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    self.last_warnings = ()
    self.last_feed_health = ()
    if self.path is None and self.live_enabled:
        return self._fetch_live_events(start, end)
    return fetch_news_events(
        self.path,
        provider=self.name,
        start=start,
        end=end,
        required=self.required,
    )


def fetch_project_blog_rss_live_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    fetched_at = self.fetched_at or datetime.now(timezone.utc)
    events: list[RawDiscoveredEvent] = []
    warnings: list[str] = []
    feed_health: list[event_source_registry.FeedHealth] = []
    for feed_url in self.feed_urls:
        try:
            request = Request(
                feed_url,
                headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
            )
            with self.opener(request, self.timeout) as response:
                status = getattr(response, "status", getattr(response, "code", 200))
                if int(status) >= 400:
                    raise RuntimeError(f"HTTP {status}")
                body = response.read()
            rows = _feed_rows(body, feed_url=feed_url, fetched_at=fetched_at)
        except Exception as exc:  # noqa: BLE001
            failure_kind = _feed_failure_kind(exc)
            warning = f"{failure_kind} project_blog_rss feed_url={feed_url}: {exc}"
            warnings.append(warning)
            feed_health.append(event_source_registry.feed_health_from_fetch(
                feed_url=feed_url,
                last_failure_at=fetched_at.isoformat(),
                failure_type=_feed_health_failure_type(exc, failure_kind),
                rows_fetched=0,
                rows_kept=0,
                rows_rejected=0,
                failure_count=1,
            ))
            if self.required:
                raise
            log.warning(warning)
            if self.fail_fast_on_error and failure_kind == "provider_failure":
                warning = "provider_failure project_blog_rss fail-fast enabled; skipped remaining feeds after provider-level failure"
                warnings.append(warning)
                log.warning(warning)
                break
            continue
        parsed_events = news_events_from_items(
            rows,
            provider=self.name,
            start=start,
            end=end,
            fetched_at=fetched_at,
        )
        events.extend(parsed_events)
        feed_health.append(event_source_registry.feed_health_from_fetch(
            feed_url=feed_url,
            last_success_at=fetched_at.isoformat(),
            rows_fetched=len(rows),
            rows_kept=len(parsed_events),
            rows_rejected=max(0, len(rows) - len(parsed_events)),
        ))
    self.last_warnings = tuple(warnings)
    self.last_feed_health = tuple(feed_health)
    return events


def _feed_rows(body: bytes, *, feed_url: str, fetched_at: datetime) -> list[Mapping[str, Any]]:
    root = ET.fromstring(body)
    rows: list[Mapping[str, Any]] = []
    rss_items = [elem for elem in root.iter() if _local_name(elem.tag) == "item"]
    atom_entries = [elem for elem in root.iter() if _local_name(elem.tag) == "entry"]
    for item in rss_items:
        row = _rss_item_row(item, feed_url=feed_url, fetched_at=fetched_at)
        if row:
            rows.append(row)
    for entry in atom_entries:
        row = _atom_entry_row(entry, feed_url=feed_url, fetched_at=fetched_at)
        if row:
            rows.append(row)
    return rows


def _rss_item_row(item: ET.Element, *, feed_url: str, fetched_at: datetime) -> dict[str, Any] | None:
    title = _child_text(item, "title")
    if not title:
        return None
    link = _child_text(item, "link")
    return {
        "id": _child_text(item, "guid") or link or title,
        "title": title,
        "summary": _child_text(item, "description"),
        "pubDate": _child_text(item, "pubDate") or _child_text(item, "published") or _child_text(item, "updated"),
        "link": link,
        "feed_url": feed_url,
        "fetched_at": fetched_at.isoformat(),
        "source_confidence": 0.70,
    }


def _atom_entry_row(entry: ET.Element, *, feed_url: str, fetched_at: datetime) -> dict[str, Any] | None:
    title = _child_text(entry, "title")
    if not title:
        return None
    link = _atom_link(entry)
    return {
        "id": _child_text(entry, "id") or link or title,
        "title": title,
        "summary": _child_text(entry, "summary") or _child_text(entry, "content"),
        "published_at": _child_text(entry, "published") or _child_text(entry, "updated"),
        "link": link,
        "feed_url": feed_url,
        "fetched_at": fetched_at.isoformat(),
        "source_confidence": 0.70,
    }


def _child_text(parent: ET.Element, name: str) -> str | None:
    for child in parent:
        if _local_name(child.tag) == name:
            text = "".join(child.itertext()).strip()
            return text or None
    return None


def _atom_link(entry: ET.Element) -> str | None:
    fallback: str | None = None
    for child in entry:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if not href:
            text = "".join(child.itertext()).strip()
            href = text or None
        if not href:
            continue
        if child.attrib.get("rel", "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _local_name(tag: object) -> str:
    text = str(tag)
    return text.rsplit("}", 1)[-1] if "}" in text else text


def _feed_failure_kind(exc: Exception) -> str:
    """Classify one-feed failures separately from broad provider failures."""
    if isinstance(exc, HTTPError):
        return "feed_failure"
    if isinstance(exc, (TimeoutError, URLError, OSError)):
        return "provider_failure"
    text = str(exc).lower()
    if "http " in text or text.startswith("http"):
        return "feed_failure"
    if isinstance(exc, ET.ParseError):
        return "feed_failure"
    return "provider_failure"


def _feed_health_failure_type(exc: Exception, failure_kind: str) -> str:
    if isinstance(exc, HTTPError):
        return f"http_{exc.code}"
    text = str(exc).casefold()
    if "http 403" in text or "403" == text.strip():
        return "http_403"
    if failure_kind == "feed_failure":
        return "feed_failure"
    return "provider_failure"
