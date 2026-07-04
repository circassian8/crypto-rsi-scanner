"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (fixtures)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_providers.cryptopanic import CryptoPanicProvider, normalize_cryptopanic_currency_code
from ....event_providers.gdelt import GdeltProvider
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ..resolver import clean_text
from .models import *  # noqa: F403

def _event_payload_value(raw_event: RawDiscoveredEvent, key: str) -> str:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event_payload.get(key) or payload.get(key) or "")
def _text_contains_term(text: str, term: str) -> bool:
    source = clean_text(text)
    needle = clean_text(term)
    if not source or not needle:
        return False
    escaped = re.escape(needle).replace("\\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", source) is not None
def _first_text(*values: object) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"none", "null"}:
            return text
    return None
def _tuple_texts(*values: object) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            iterable = value.values()
        elif isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = (value,)
        for item in iterable:
            text = str(item or "").strip()
            if text:
                out.append(text)
    return tuple(dict.fromkeys(out))
def _event_name(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event.get("event_name") or raw.title or "")
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
