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
    original_source_url = row.get("original_source_url") or row.get("source_url") or row.get("proof_url")
    event_type = _event_type(row, title, body)
    coin = _primary_coin(row)
    confidence = _source_confidence(row, confirmed=_confirmed(row))
    payload = dict(row)
    payload["event"] = {
        "event_name": title,
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": 0.90 if event_time else 0.0,
        "event_time_source": "structured_calendar" if event_time else None,
        "confidence": confidence,
        "description": _description_with_coins(row, body or title),
        "event_category": _event_category(row, event_type),
        "source_class": "structured_calendar",
        "source_mission": "catalyst_validation",
        "calendar_confirmed": _confirmed(row),
        "calendar_original_source_url": str(original_source_url) if original_source_url else None,
        "calendar_source_url": str(source_url) if source_url else None,
        "token_id": coin.get("id"),
        "token_symbol": coin.get("symbol"),
        "token_name": coin.get("name"),
    }
    payload["calendar"] = {
        "coin_id": coin.get("id"),
        "symbol": coin.get("symbol"),
        "name": coin.get("name"),
        "event_category": payload["event"]["event_category"],
        "event_type": event_type,
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_confidence": payload["event"]["event_time_confidence"],
        "event_time_source": payload["event"]["event_time_source"],
        "confirmed": _confirmed(row),
        "source_confidence": confidence,
        "source_class": "structured_calendar",
        "source_mission": "catalyst_validation",
        "source_url": str(source_url) if source_url else None,
        "original_source_url": str(original_source_url) if original_source_url else None,
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
        source_confidence=confidence,
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
    if "delisting" in text or "delist" in text:
        return "exchange_delisting"
    if "perp" in text or "perpetual" in text or "futures" in text:
        return "perp_listing"
    if "listing" in text or "listed on" in text or "trading pair" in text:
        return "exchange_listing"
    if "mainnet" in text:
        return "mainnet_launch"
    if "hard fork" in text:
        return "protocol_upgrade"
    if "governance" in text or "vote" in text:
        return "governance"
    if "upgrade" in text or "hard fork" in text:
        return "protocol_upgrade"
    if "tge" in text or "token generation" in text:
        return "tge"
    if "unlock" in text or "vesting" in text:
        return "token_unlock"
    if "ama" in text or "community call" in text:
        return "community_ama"
    return "crypto_calendar_event"


def _event_category(row: Mapping[str, Any], event_type: str) -> str:
    category = row.get("category")
    if category not in (None, ""):
        return str(category)
    categories = row.get("categories")
    if isinstance(categories, Iterable) and not isinstance(categories, (str, bytes, Mapping)):
        first = next((str(item) for item in categories if str(item).strip()), "")
        if first:
            return first
    return event_type


def _primary_coin(row: Mapping[str, Any]) -> dict[str, str | None]:
    coins = row.get("coins")
    if isinstance(coins, Iterable) and not isinstance(coins, (str, bytes, Mapping)):
        for coin in coins:
            if isinstance(coin, Mapping):
                return {
                    "id": _text_or_none(coin.get("id") or coin.get("coin_id")),
                    "name": _text_or_none(coin.get("name")),
                    "symbol": _text_or_none(coin.get("symbol"), upper=True),
                }
    return {
        "id": _text_or_none(row.get("coin_id") or row.get("token_id")),
        "name": _text_or_none(row.get("coin_name") or row.get("token_name")),
        "symbol": _text_or_none(row.get("symbol") or row.get("token_symbol"), upper=True),
    }


def _confirmed(row: Mapping[str, Any]) -> bool:
    value = row.get("confirmed", row.get("is_confirmed", row.get("proof_verified")))
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return bool(row.get("proof_url") or row.get("original_source_url"))
    return str(value).strip().casefold() in {"1", "true", "yes", "confirmed", "verified"}


def _source_confidence(row: Mapping[str, Any], *, confirmed: bool) -> float:
    try:
        value = float(row.get("source_confidence")) if row.get("source_confidence") not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    if value is None:
        value = 0.88 if confirmed else 0.72
    if value > 1.0:
        value = value / 100.0
    if not confirmed:
        value = min(value, 0.74)
    return max(0.0, min(1.0, value))


def _text_or_none(value: object, *, upper: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.upper() if upper else text


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
