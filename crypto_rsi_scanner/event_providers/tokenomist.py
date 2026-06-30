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
    coin_id = str(row.get("coin_id") or row.get("token_id") or "").strip()
    unlock_time = _first_dt(row, ("unlock_time", "unlock_date", "date", "event_time"))
    if not symbol or unlock_time is None:
        return None
    published_at = _first_dt(row, ("published_at", "created_at", "createdAt"))
    fetched_at = _first_dt(row, ("fetched_at", "updated_at", "updatedAt")) or published_at or datetime.now(timezone.utc)
    pct = _float_or_none(row.get("unlock_pct_circulating") or row.get("percent_of_circulating_supply"))
    amount = _float_or_none(row.get("unlock_amount") or row.get("amount"))
    unlock_kind = _unlock_kind(row)
    vesting_category = str(row.get("vesting_category") or row.get("category") or row.get("allocation") or "").strip()
    materiality = _unlock_materiality(pct)
    title = str(row.get("title") or f"{name} ({symbol}) token unlock")
    description = str(row.get("description") or row.get("notes") or title)
    source_confidence = _source_confidence(row, materiality=materiality)
    payload = dict(row)
    payload["event"] = {
        "event_name": title,
        "event_type": "token_unlock",
        "event_time": unlock_time.isoformat(),
        "event_time_confidence": 1.0,
        "event_time_source": "structured_unlock",
        "confidence": source_confidence,
        "description": f"{description} {name} {symbol}".strip(),
        "source_class": "structured_unlock",
        "source_mission": "supply_confirmation",
        "token_id": coin_id or None,
        "token_symbol": symbol,
        "token_name": name,
        "unlock_type": unlock_kind,
        "vesting_category": vesting_category or None,
        "unlock_materiality": materiality,
    }
    payload["supply"] = {
        "coin_id": coin_id or None,
        "symbol": symbol,
        "timestamp": unlock_time.isoformat(),
        "unlock_amount": amount,
        "unlock_pct_circulating": pct,
        "unlock_type": unlock_kind,
        "vesting_category": vesting_category or None,
        "unlock_materiality": materiality,
        "source_class": "structured_unlock",
        "source_mission": "supply_confirmation",
        "supply_event": "token_unlock",
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
        source_confidence=source_confidence,
        content_hash=content_hash(payload),
    )


def _unlock_kind(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("unlock_type", "type", "description", "notes", "title")).casefold()
    if "linear" in text or "stream" in text:
        return "linear"
    if "cliff" in text:
        return "cliff"
    return str(row.get("unlock_type") or row.get("type") or "scheduled").strip() or "scheduled"


def _unlock_materiality(pct: float | None) -> str:
    normalized = _normalize_pct(pct)
    if normalized is None:
        return "unknown"
    if normalized >= 0.10:
        return "large"
    if normalized >= 0.05:
        return "material"
    if normalized > 0:
        return "small"
    return "none"


def _normalize_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _source_confidence(row: Mapping[str, Any], *, materiality: str) -> float:
    try:
        value = float(row.get("source_confidence")) if row.get("source_confidence") not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    if value is None:
        value = 0.90
    if value > 1.0:
        value = value / 100.0
    if materiality == "unknown":
        value = min(value, 0.78)
    return max(0.0, min(1.0, value))


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
