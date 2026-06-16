"""Fixture-backed Tokenomist-style unlock provider."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_models import RawDiscoveredEvent
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)


class TokenomistProvider:
    name = "tokenomist"

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
            log.warning("Tokenomist fixture load failed: %s", exc)
            return []

        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        out: list[RawDiscoveredEvent] = []
        for row in rows:
            event = _raw_event(row, self.name)
            if event is None:
                continue
            event_time = parse_datetime(event.raw_json["event"].get("event_time"))
            if event_time and start_utc <= event_time <= end_utc:
                out.append(event)
        return out


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("unlocks", raw.get("data")) if isinstance(raw, Mapping) else raw
    if not isinstance(rows, list):
        raise ValueError("Tokenomist fixture must be a list or {'unlocks': [...]}")
    out: list[Mapping[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"Tokenomist row {idx} must be an object")
        out.append(row)
    return out


def _raw_event(row: Mapping[str, Any], provider: str) -> RawDiscoveredEvent | None:
    symbol = str(row.get("symbol") or row.get("token_symbol") or "").upper()
    name = str(row.get("name") or row.get("token_name") or symbol or "").strip()
    unlock_time = _first_dt(row, ("unlock_time", "unlock_date", "date", "event_time"))
    if not symbol or unlock_time is None:
        return None
    published_at = _first_dt(row, ("published_at", "created_at", "createdAt"))
    fetched_at = _first_dt(row, ("fetched_at", "updated_at", "updatedAt")) or published_at or datetime.now(timezone.utc)
    pct = _float_or_none(row.get("unlock_pct_circulating") or row.get("percent_of_circulating_supply"))
    amount = _float_or_none(row.get("unlock_amount") or row.get("amount"))
    title = str(row.get("title") or f"{name} ({symbol}) token unlock")
    description = str(row.get("description") or row.get("notes") or title)
    payload = dict(row)
    payload["event"] = {
        "event_name": title,
        "event_type": "token_unlock",
        "event_time": unlock_time.isoformat(),
        "event_time_confidence": 1.0,
        "confidence": float(row.get("source_confidence") or 0.90),
        "description": f"{description} {name} {symbol}".strip(),
    }
    payload["supply"] = {
        "symbol": symbol,
        "timestamp": unlock_time.isoformat(),
        "unlock_amount": amount,
        "unlock_pct_circulating": pct,
        "notes": description,
    }
    raw_id = str(row.get("raw_id") or row.get("id") or f"{provider}:{content_hash(payload)[:16]}")
    source_url = row.get("source_url") or row.get("url")
    return RawDiscoveredEvent(
        raw_id=f"{provider}:{raw_id}",
        provider=provider,
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=str(source_url) if source_url else None,
        title=title,
        body=payload["event"]["description"],
        raw_json=payload,
        source_confidence=float(row.get("source_confidence") or 0.90),
        content_hash=content_hash(payload),
    )


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


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
