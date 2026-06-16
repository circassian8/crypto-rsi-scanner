"""Fixture-backed CoinMarketCal-style event provider."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_models import RawDiscoveredEvent
from ..event_resolver import clean_text
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)


class CoinMarketCalProvider:
    name = "coinmarketcal"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = Path(path).expanduser() if path else None
        self.required = required

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        if self.path is None:
            return []
        try:
            rows = _load_rows(self.path)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("CoinMarketCal fixture load failed: %s", exc)
            return []

        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        out: list[RawDiscoveredEvent] = []
        for row in rows:
            event = _raw_event(row, self.name)
            if event is None:
                continue
            event_time = parse_datetime(event.raw_json["event"].get("event_time"))
            reference_time = event.published_at or event.fetched_at
            if event_time is not None:
                in_window = start_utc <= event_time <= end_utc
            else:
                in_window = start_utc <= reference_time <= end_utc
            if in_window:
                out.append(event)
        return out


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("events", raw.get("data")) if isinstance(raw, Mapping) else raw
    if not isinstance(rows, list):
        raise ValueError("CoinMarketCal fixture must be a list or {'events': [...]}")
    out: list[Mapping[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"CoinMarketCal row {idx} must be an object")
        out.append(row)
    return out


def _raw_event(row: Mapping[str, Any], provider: str) -> RawDiscoveredEvent | None:
    title = str(row.get("title") or row.get("name") or row.get("event_name") or "").strip()
    if not title:
        return None
    body = str(row.get("description") or row.get("body") or row.get("proof") or "")
    event_time = _first_dt(row, ("date_event", "event_date", "event_time", "date", "start_date"))
    published_at = _first_dt(row, ("published_at", "created_at", "createdAt", "date_added"))
    fetched_at = _first_dt(row, ("fetched_at", "updated_at", "updatedAt")) or published_at or datetime.now(timezone.utc)
    source_url = row.get("source_url") or row.get("proof_url") or row.get("url")
    event_type = _event_type(row, title, body)
    payload = dict(row)
    payload["event"] = {
        "event_name": title,
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": 0.90 if event_time else 0.0,
        "confidence": float(row.get("source_confidence") or 0.82),
        "description": _description_with_coins(row, body or title),
    }
    raw_id = str(row.get("raw_id") or row.get("id") or f"{provider}:{content_hash(payload)[:16]}")
    return RawDiscoveredEvent(
        raw_id=f"{provider}:{raw_id}",
        provider=provider,
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=str(source_url) if source_url else None,
        title=title,
        body=payload["event"]["description"],
        raw_json=payload,
        source_confidence=float(row.get("source_confidence") or 0.82),
        content_hash=content_hash(payload),
    )


def _event_type(row: Mapping[str, Any], title: str, body: str) -> str:
    text = clean_text(" ".join([
        title,
        body,
        " ".join(str(c) for c in row.get("categories") or ()),
    ]))
    if "airdrop" in text:
        return "airdrop"
    if "mainnet" in text:
        return "mainnet_launch"
    if "governance" in text or "vote" in text:
        return "governance"
    if "upgrade" in text or "hard fork" in text:
        return "protocol_upgrade"
    if "tge" in text or "token generation" in text:
        return "tge"
    return "crypto_calendar_event"


def _description_with_coins(row: Mapping[str, Any], description: str) -> str:
    coins = row.get("coins")
    if not isinstance(coins, Iterable) or isinstance(coins, (str, bytes, Mapping)):
        return description
    parts = [description]
    for coin in coins:
        if not isinstance(coin, Mapping):
            continue
        name = coin.get("name")
        symbol = coin.get("symbol")
        coin_id = coin.get("id")
        parts.append(" ".join(str(v) for v in (name, symbol, coin_id) if v))
    return " ".join(part for part in parts if part)


def _first_dt(row: Mapping[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        if row.get(key) not in (None, ""):
            return _parse_dt(row.get(key))
    return None


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
