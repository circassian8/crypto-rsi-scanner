"""Shared helpers for fixture-backed exchange announcement providers."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..event_models import RawDiscoveredEvent
from ..event_resolver import clean_text
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)


def fetch_announcement_events(
    path: str | Path | None,
    *,
    provider: str,
    start: datetime,
    end: datetime,
    required: bool = False,
) -> list[RawDiscoveredEvent]:
    if path is None:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        if required:
            raise FileNotFoundError(f"{provider} announcement fixture not found: {p}")
        log.warning("%s announcement fixture missing: %s", provider, p)
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = _announcement_items(raw)
    except Exception as exc:  # noqa: BLE001
        if required:
            raise ValueError(f"invalid {provider} announcement fixture {p}: {exc}") from exc
        log.warning("%s announcement fixture load failed: %s", provider, exc)
        return []

    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    out: list[RawDiscoveredEvent] = []
    for item in items:
        event = _raw_event_from_item(item, provider)
        if event is None:
            continue
        reference_time = event.published_at or event.fetched_at
        if start_utc <= reference_time <= end_utc:
            out.append(event)
    return out


def _announcement_items(raw: object) -> list[Mapping[str, Any]]:
    items = list(_walk_announcement_items(raw))
    if not items:
        raise ValueError("announcement fixture does not contain any announcement objects")
    return items


def _walk_announcement_items(raw: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                if _has_nested_items(item):
                    yield from _walk_announcement_items(item)
                else:
                    yield item
        return
    if not isinstance(raw, Mapping):
        return
    cms_payload = _cms_data_payload(raw)
    if cms_payload is not None:
        yield cms_payload
        return
    for key in ("announcements", "articles", "list", "rows", "items"):
        value = raw.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    yield item
            return
    for key in ("data", "result", "catalogs", "catalog"):
        value = raw.get(key)
        if isinstance(value, (list, Mapping)):
            yield from _walk_announcement_items(value)
            return
    if raw.get("title"):
        yield raw


def _has_nested_items(item: Mapping[str, Any]) -> bool:
    return any(isinstance(item.get(key), (list, Mapping)) for key in (
        "announcements",
        "articles",
        "list",
        "rows",
        "items",
        "data",
        "result",
        "catalogs",
        "catalog",
    ))


def _raw_event_from_item(item: Mapping[str, Any], provider: str) -> RawDiscoveredEvent | None:
    title = str(item.get("title") or item.get("name") or item.get("headline") or "").strip()
    if not title:
        return None
    body = str(item.get("body") or item.get("content") or item.get("summary") or item.get("description") or "")
    event_type = _event_type(title, body)
    if event_type is None:
        return None

    fetched_at = _parse_time(
        item.get("fetched_at")
        or item.get("fetchedAt")
        or item.get("updatedAt")
        or item.get("updateTime")
        or item.get("releaseDate")
        or item.get("publishDate")
        or item.get("publishTime")
        or item.get("dateTimestamp")
    ) or datetime.now(timezone.utc)
    published_at = _parse_time(
        item.get("published_at")
        or item.get("publishedAt")
        or item.get("releaseDate")
        or item.get("publishDate")
        or item.get("publishTime")
        or item.get("publish_time")
        or item.get("dateTimestamp")
    )
    event_time = _parse_time(
        item.get("event_time")
        or item.get("listing_time")
        or item.get("listingTime")
        or item.get("tradingStartTime")
        or item.get("tradeStartTime")
        or item.get("launchTime")
        or item.get("startDateTimestamp")
        or item.get("startDataTimestamp")
    ) or published_at
    raw_id = str(
        item.get("raw_id")
        or item.get("id")
        or item.get("code")
        or item.get("articleId")
        or item.get("announcement_id")
        or f"{provider}:{content_hash(dict(item))[:16]}"
    )
    source_url = (
        item.get("source_url")
        or item.get("url")
        or item.get("articleUrl")
        or item.get("link")
    )
    payload = dict(item)
    payload["source_class"] = "official_exchange"
    payload["announcement_kind"] = event_type
    payload["announcement_symbols"] = _announcement_symbols(title, body)
    payload["event"] = {
        "event_name": title,
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": 1.0 if _has_explicit_event_time(item) else 0.60,
        "confidence": float(item.get("source_confidence") or 0.85),
        "description": body or title,
    }
    return RawDiscoveredEvent(
        raw_id=f"{provider}:{raw_id}",
        provider=provider,
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=str(source_url) if source_url else None,
        title=title,
        body=body or None,
        raw_json=payload,
        source_confidence=float(item.get("source_confidence") or 0.85),
        content_hash=content_hash(payload),
    )


def _event_type(title: str, body: str) -> str | None:
    text = clean_text(f"{title} {body}")
    if any(token in text for token in ("perpetual", "perp", "futures", "contract")):
        if any(token in text for token in ("list", "launch", "add", "new")):
            return "perp_listing"
    if any(token in text for token in (
        "will list",
        "new listing",
        "new cryptocurrency listing",
        "spot trading for",
        "opens trading",
        "open spot trading",
    )):
        return "exchange_listing"
    return None


def _announcement_symbols(title: str, body: str) -> tuple[str, ...]:
    text = f"{title} {body}"
    out: list[str] = []
    for match in re.finditer(r"\b([A-Z0-9]{2,12})(?:USDT|USDC|FDUSD|BTC|ETH)\b", text):
        out.append(match.group(1))
    for match in re.finditer(r"\(([A-Z0-9]{2,12})\)", text):
        out.append(match.group(1))
    for match in re.finditer(r"\b([A-Z0-9]{2,12})\s+(?:spot|perp|perpetual|futures|trading)\b", text, re.IGNORECASE):
        out.append(match.group(1).upper())
    return tuple(dict.fromkeys(value for value in out if value not in {"USD", "USDT", "USDC", "BTC", "ETH"}))


def _parse_time(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _has_explicit_event_time(item: Mapping[str, Any]) -> bool:
    return any(
        item.get(key) not in (None, "")
        for key in (
            "event_time",
            "listing_time",
            "listingTime",
            "tradingStartTime",
            "tradeStartTime",
            "launchTime",
            "startDateTimestamp",
            "startDataTimestamp",
        )
    )


def _cms_data_payload(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = raw.get("data")
    if data is None or raw.get("type") != "DATA":
        return None
    parsed: object
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return None
    else:
        parsed = data
    if not isinstance(parsed, Mapping):
        return None
    payload = dict(parsed)
    if raw.get("topic") is not None:
        payload["topic"] = raw.get("topic")
    if raw.get("type") is not None:
        payload["message_type"] = raw.get("type")
    return payload


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
