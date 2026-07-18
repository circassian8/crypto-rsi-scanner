"""Shared helpers for fixture-backed external catalyst providers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..event_core.models import RawDiscoveredEvent
from .manual_json import content_hash, parse_datetime

log = logging.getLogger(__name__)


def fetch_external_events(
    path: str | Path | None,
    *,
    provider: str,
    default_event_type: str,
    start: datetime,
    end: datetime,
    required: bool = False,
) -> list[RawDiscoveredEvent]:
    if path is None:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        if required:
            raise FileNotFoundError(f"{provider} external-catalyst fixture not found: {p}")
        log.warning("%s external-catalyst fixture missing: %s", provider, p)
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        rows = _external_items(raw)
    except Exception as exc:  # noqa: BLE001
        if required:
            raise ValueError(f"invalid {provider} external-catalyst fixture {p}: {exc}") from exc
        log.warning("%s external-catalyst fixture load failed: %s", provider, exc)
        return []

    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    out: list[RawDiscoveredEvent] = []
    for row in rows:
        event = _raw_event_from_row(row, provider, default_event_type)
        if event is None:
            continue
        reference_time = event.published_at or event.fetched_at
        if start_utc <= reference_time <= end_utc:
            out.append(event)
    return out


def _external_items(raw: object) -> list[Mapping[str, Any]]:
    rows = list(_walk_items(raw))
    if not rows:
        raise ValueError("external-catalyst fixture does not contain any event objects")
    return rows


def _walk_items(raw: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                yield from _walk_items(item)
        return
    if not isinstance(raw, Mapping):
        return
    for key in ("events", "items", "data", "rows", "list", "fixtures", "matches", "markets", "ipos"):
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
    if raw.get("title") or raw.get("name") or raw.get("question") or raw.get("company") or raw.get("home_team"):
        yield raw


def _raw_event_from_row(
    row: Mapping[str, Any],
    provider: str,
    default_event_type: str,
) -> RawDiscoveredEvent | None:
    title = _title(row)
    if not title:
        return None
    body = str(row.get("body") or row.get("description") or row.get("summary") or row.get("notes") or "")
    fetched_at = _parse_time(row.get("fetched_at") or row.get("fetchedAt") or row.get("updated_at")) or datetime.now(
        timezone.utc,
    )
    published_at = _parse_time(
        row.get("published_at")
        or row.get("publishedAt")
        or row.get("created_at")
        or row.get("createdAt")
        or row.get("creationDate")
        or row.get("announced_at")
        or row.get("updated_at")
    )
    event_time_raw = (
        row.get("event_time")
        or row.get("eventTime")
        or row.get("start_time")
        or row.get("startTime")
        or row.get("kickoff_time")
        or row.get("kickoffTime")
        or row.get("expected_date")
        or row.get("expectedDate")
        or row.get("close_time")
        or row.get("closeTime")
        or row.get("closedTime")
        or row.get("end_time")
        or row.get("endDate")
        or row.get("end_date")
    )
    event_time = _parse_time(event_time_raw)
    source_url = row.get("source_url") or row.get("url") or row.get("link") or row.get("market_url")
    raw_id = str(row.get("raw_id") or row.get("id") or row.get("url") or f"{provider}:{content_hash(dict(row))[:16]}")
    payload = dict(row)
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    if not event_payload:
        event_payload = {
            "event_name": str(row.get("event_name") or row.get("eventName") or title),
            "event_type": str(row.get("event_type") or row.get("eventType") or default_event_type),
            "event_time": event_time.isoformat() if event_time else None,
            "event_time_confidence": _event_time_confidence(event_time_raw, event_time),
            "external_asset": row.get("external_asset") or row.get("externalAsset") or row.get("company") or _team(row),
            "confidence": float(row.get("source_confidence") or 0.75),
            "description": body or title,
        }
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
        source_confidence=float(row.get("source_confidence") or event_payload.get("confidence") or 0.75),
        content_hash=content_hash(payload),
    )


def _title(row: Mapping[str, Any]) -> str:
    if row.get("title") or row.get("name") or row.get("question"):
        return str(row.get("title") or row.get("name") or row.get("question")).strip()
    if row.get("company"):
        return f"{row['company']} IPO calendar event"
    home = row.get("home_team") or row.get("homeTeam")
    away = row.get("away_team") or row.get("awayTeam")
    if home and away:
        return f"{home} vs {away}"
    return ""


def _team(row: Mapping[str, Any]) -> str | None:
    home = row.get("home_team") or row.get("homeTeam")
    away = row.get("away_team") or row.get("awayTeam")
    if home and away:
        return f"{home} vs {away}"
    return str(home or away) if home or away else None


def _event_time_confidence(raw_value: object, event_time: datetime | None) -> float:
    if event_time is None:
        return 0.0
    if isinstance(raw_value, str) and len(raw_value.strip()) <= 10:
        return 0.45
    return 1.0


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
