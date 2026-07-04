"""Shared helpers for fixture-backed news/narrative providers."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..event_core.models import RawDiscoveredEvent
from crypto_rsi_scanner.event_alpha.radar.resolver import clean_text
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)

EXTERNAL_ASSET_ALIASES = (
    ("SpaceX", ("spacex", "spcx")),
    ("OpenAI", ("openai", "open ai", "chatgpt")),
    ("Anthropic", ("anthropic", "claude")),
    ("Stripe", ("stripe",)),
    ("Databricks", ("databricks",)),
    ("Anduril", ("anduril",)),
    ("Figma", ("figma",)),
    ("xAI", ("xai", "x.ai")),
    ("Kraken", ("kraken",)),
    ("Tesla", ("tesla",)),
    ("Nvidia", ("nvidia",)),
    ("World Cup", ("world cup",)),
    ("Champions League", ("champions league",)),
    ("Iran", ("iran",)),
    ("US election", ("us election", "u.s. election", "presidential election")),
)

_ENTITY_TOKEN = r"(?:xAI|XAI|[A-Z][A-Za-z0-9&.'-]*)"
_ENTITY_PHRASE = rf"{_ENTITY_TOKEN}(?:\s+{_ENTITY_TOKEN}){{0,3}}"
_EXPOSURE_ENTITY_RE = re.compile(
    rf"\b(?i:synthetic exposure to|exposure to|pre-ipo access to|pre IPO access to|"
    rf"tokenized shares? of|tokenized stock of|stock token tied to|market for|"
    rf"perpetual market for|prediction market for|bet on|bets on)\s+(?P<entity>{_ENTITY_PHRASE})\b",
)
_IPO_ENTITY_BEFORE_RE = re.compile(
    rf"\b(?P<entity>{_ENTITY_PHRASE})\s+(?i:IPO|pre-IPO|pre IPO|public debut|direct listing)\b",
)
_IPO_ENTITY_AFTER_RE = re.compile(
    rf"\b(?i:IPO of|IPO for|pre-IPO shares of|pre IPO shares of|public debut of)\s+"
    rf"(?P<entity>{_ENTITY_PHRASE})\b",
)
_SPORTS_MATCH_RE = re.compile(
    rf"\b(?P<home>{_ENTITY_PHRASE})\s+(?i:vs\.?|v\.?)\s+(?P<away>{_ENTITY_PHRASE})\b",
)
_GENERIC_ENTITY_WORDS = {
    "A",
    "An",
    "And",
    "Before",
    "Coin",
    "Crypto",
    "ETF",
    "Event",
    "Exchange",
    "Launch",
    "Market",
    "Markets",
    "News",
    "Prediction",
    "Protocol",
    "Shares",
    "Stock",
    "Token",
    "Trade",
    "Trading",
    "Will",
}
_ENTITY_ACTION_WORDS = {
    "Adds",
    "Announces",
    "Closes",
    "Debuts",
    "Down",
    "Falls",
    "Launches",
    "Lists",
    "Offers",
    "Opens",
    "Rallies",
    "Reveals",
    "Shuts",
    "Surges",
    "Unveils",
    "Winds",
}

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_DATE_PREFIX = r"(?:on|by|before|after|until|through|ahead\s+of|into|for)"
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_TEXT_MONTH_DATE_RE = re.compile(
    rf"\b{_DATE_PREFIX}\s+(?:the\s+)?"
    rf"(?:(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?[,]?\s+)?"
    rf"(?P<month>{_MONTH_PATTERN})\.?\s+"
    rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"(?:[,]?\s+(?P<year>20\d{{2}}))?\b",
    re.IGNORECASE,
)
_TEXT_ISO_DATE_RE = re.compile(
    rf"\b{_DATE_PREFIX}\s+(?P<year>20\d{{2}})-(?P<month>\d{{1,2}})-(?P<day>\d{{1,2}})\b",
    re.IGNORECASE,
)


def fetch_news_events(
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
            raise FileNotFoundError(f"{provider} news fixture not found: {p}")
        log.warning("%s news fixture missing: %s", provider, p)
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        rows = _news_items(raw)
    except Exception as exc:  # noqa: BLE001
        if required:
            raise ValueError(f"invalid {provider} news fixture {p}: {exc}") from exc
        log.warning("%s news fixture load failed: %s", provider, exc)
        return []

    return news_events_from_items(rows, provider=provider, start=start, end=end)


def news_events_from_items(
    rows: Iterable[Mapping[str, Any]],
    *,
    provider: str,
    start: datetime,
    end: datetime,
    fetched_at: datetime | None = None,
) -> list[RawDiscoveredEvent]:
    """Convert already-loaded news rows into filtered raw discovery events."""
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    fetched_at_utc = _as_utc(fetched_at) if fetched_at else None
    out: list[RawDiscoveredEvent] = []
    for row in rows:
        payload = dict(row)
        if fetched_at_utc and not any(k in payload for k in ("fetched_at", "fetchedAt", "updated_at")):
            payload["fetched_at"] = fetched_at_utc.isoformat()
        event = _raw_event_from_row(payload, provider)
        if event is None:
            continue
        reference_time = event.published_at or event.fetched_at
        if start_utc <= reference_time <= end_utc:
            out.append(event)
    return out


def _news_items(raw: object, *, allow_empty: bool = False) -> list[Mapping[str, Any]]:
    rows = list(_walk_items(raw))
    if not rows and not allow_empty:
        raise ValueError("news fixture does not contain any article objects")
    return rows


def _walk_items(raw: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                yield from _walk_items(item)
        return
    if not isinstance(raw, Mapping):
        return
    for key in ("results", "articles", "items", "features", "events", "data", "rows", "list"):
        value = raw.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    yield from _walk_items(item)
            return
    if raw.get("properties") and isinstance(raw.get("properties"), Mapping):
        merged = {**dict(raw["properties"]), **{k: v for k, v in raw.items() if k != "properties"}}
        yield merged
        return
    if raw.get("title") or raw.get("headline") or raw.get("name"):
        yield raw


def _raw_event_from_row(row: Mapping[str, Any], provider: str) -> RawDiscoveredEvent | None:
    title = str(row.get("title") or row.get("headline") or row.get("name") or "").strip()
    if not title:
        return None
    body = str(
        row.get("body")
        or row.get("description")
        or row.get("summary")
        or row.get("content")
        or row.get("seendate")
        or ""
    )
    fetched_at = _parse_time(row.get("fetched_at") or row.get("fetchedAt") or row.get("updated_at")) or datetime.now(
        timezone.utc,
    )
    published_at = _parse_time(
        row.get("published_at")
        or row.get("publishedAt")
        or row.get("published_on")
        or row.get("created_at")
        or row.get("pubDate")
        or row.get("seendate")
    )
    source_url = row.get("source_url") or row.get("url") or row.get("link") or row.get("article_url")
    raw_id = str(row.get("raw_id") or row.get("id") or row.get("url") or f"{provider}:{content_hash(dict(row))[:16]}")
    payload = dict(row)
    payload["source_provider"] = provider
    if row.get("feed_url"):
        payload["feed_url"] = row.get("feed_url")
    currency_tags = _currency_tags(row)
    if currency_tags:
        payload["currency_tags"] = currency_tags
    if provider == "cryptopanic":
        payload["source_class"] = "cryptopanic_tagged" if currency_tags else "crypto_news"
        if _cryptopanic_narrative_heat(row, title, body):
            payload["narrative_heat"] = True
    elif provider == "project_blog_rss" and row.get("feed_url"):
        payload["source_class"] = "project_rss_feed"
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    if not event_payload:
        event_payload = _infer_event_payload(title, body, row)
        payload["event"] = event_payload
    return RawDiscoveredEvent(
        raw_id=f"{provider}:{raw_id}",
        provider=provider,
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=str(source_url) if source_url else None,
        title=title,
        body=body or None,
        raw_json=payload,
        source_confidence=float(row.get("source_confidence") or event_payload.get("confidence") or 0.65),
        content_hash=content_hash(payload),
    )


def _infer_event_payload(title: str, body: str, row: Mapping[str, Any]) -> dict[str, Any]:
    raw_text = f"{title} {body}"
    text = clean_text(raw_text)
    event_type = "other"
    if any(token in text for token in (
        "pre ipo",
        "pre-ipo",
        "tokenized stock",
        "synthetic exposure",
        "public debut",
    )) or re.search(r"\bipo\b", text):
        event_type = "ipo_proxy"
    elif any(token in text for token in ("prediction market", "election", "inauguration")):
        event_type = "political_event"
    elif any(token in text for token in ("fan token", "world cup", "match kickoff", "fixture")):
        event_type = "sports_event"
    elif "etf" in text:
        event_type = "etf_approval"

    event_time = _parse_time(row.get("event_time") or row.get("eventTime") or row.get("catalyst_time"))
    event_time_source = "explicit" if event_time else None
    if event_time is None:
        reference_time = (
            _parse_time(
                row.get("published_at")
                or row.get("publishedAt")
                or row.get("published_on")
                or row.get("created_at")
                or row.get("pubDate")
                or row.get("seendate")
            )
            or _parse_time(row.get("fetched_at") or row.get("fetchedAt") or row.get("updated_at"))
            or datetime.now(timezone.utc)
        )
        event_time = _infer_text_event_time(title, body, reference_time)
        event_time_source = "text_date" if event_time else None
    external_asset = row.get("external_asset") or row.get("externalAsset") or infer_external_asset(raw_text)
    return {
        "event_name": str(row.get("event_name") or row.get("eventName") or title),
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": 1.0 if event_time_source == "explicit" else (0.60 if event_time else 0.0),
        "event_time_source": event_time_source,
        "external_asset": external_asset,
        "confidence": float(row.get("source_confidence") or 0.65),
        "description": body or title,
    }


def infer_external_asset(text: str) -> str | None:
    """Infer a likely external catalyst asset from clear proxy-event language."""
    clean = clean_text(text)
    for name, aliases in EXTERNAL_ASSET_ALIASES:
        if any(alias in clean for alias in aliases):
            return name
    for pattern in (_EXPOSURE_ENTITY_RE, _IPO_ENTITY_BEFORE_RE, _IPO_ENTITY_AFTER_RE):
        match = pattern.search(text)
        if not match:
            continue
        entity = _normalized_external_entity(match.group("entity"))
        if entity:
            return entity
    sports_match = _SPORTS_MATCH_RE.search(text)
    if sports_match:
        home = _normalized_external_entity(sports_match.group("home"))
        away = _normalized_external_entity(sports_match.group("away"))
        if home and away:
            return f"{home} vs {away}"
    return None


def _infer_external_asset(text: str) -> str | None:
    return infer_external_asset(text)


def _currency_tags(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("currencies", "currency_tags", "currencyTags", "tags"):
        raw = row.get(key)
        if isinstance(raw, Mapping):
            raw = raw.values()
        if isinstance(raw, str):
            values.extend(part.strip() for part in raw.replace(";", ",").split(","))
        elif isinstance(raw, Iterable):
            for item in raw:
                if isinstance(item, Mapping):
                    for child_key in ("code", "symbol", "slug", "currency", "title"):
                        if item.get(child_key):
                            values.append(str(item.get(child_key)))
                elif item not in (None, ""):
                    values.append(str(item))
    return tuple(dict.fromkeys(value.strip().upper() for value in values if value and value.strip()))


def _cryptopanic_narrative_heat(row: Mapping[str, Any], title: str, body: str) -> bool:
    text = clean_text(" ".join(str(value or "") for value in (
        title,
        body,
        row.get("kind"),
        row.get("filter"),
        row.get("status"),
        row.get("metadata"),
        row.get("votes"),
    )))
    return any(token in text for token in ("hot", "rising", "important", "bullish"))


def _normalized_external_entity(value: object) -> str | None:
    raw = str(value or "").strip()
    raw = re.sub(r"^[\"'“”‘’([{]+|[\"'“”‘’)\]},.:;!?]+$", "", raw)
    raw = re.sub(r"'s\b", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return None
    words = raw.split()
    while words and words[0] in _GENERIC_ENTITY_WORDS:
        words.pop(0)
    while words and words[-1] in _GENERIC_ENTITY_WORDS:
        words.pop()
    if not words:
        return None
    if any(word in _ENTITY_ACTION_WORDS for word in words):
        return None
    if all(word in _GENERIC_ENTITY_WORDS for word in words):
        return None
    entity = " ".join(words)
    if len(entity) < 2:
        return None
    return "xAI" if entity.casefold() in {"xai", "x.ai"} else entity


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if raw.isdigit() and len(raw) == 14:
            return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        if "," in raw:
            try:
                dt = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                dt = None
            if dt is not None:
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return parse_datetime(value)


def _infer_text_event_time(title: str, body: str, reference_time: datetime) -> datetime | None:
    text = f"{title} {body or ''}"
    for pattern in (_TEXT_ISO_DATE_RE, _TEXT_MONTH_DATE_RE):
        match = pattern.search(text)
        if not match:
            continue
        try:
            if pattern is _TEXT_ISO_DATE_RE:
                year = int(match.group("year"))
                month = int(match.group("month"))
            else:
                month = _MONTHS[match.group("month").lower().rstrip(".")]
                year = int(match.group("year")) if match.group("year") else _as_utc(reference_time).year
            day = int(match.group("day"))
            inferred = datetime(year, month, day, tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError):
            continue
        if match.groupdict().get("year") is None and inferred + timedelta(days=2) < _as_utc(reference_time):
            try:
                inferred = inferred.replace(year=inferred.year + 1)
            except ValueError:
                continue
        return inferred
    return None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
