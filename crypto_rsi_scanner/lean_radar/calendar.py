"""Strict local calendar import and context-only idea overlays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Mapping, Sequence

from .bybit_universe import BybitUniverseError, read_json_document
from .models import CalendarEvent, LeanRadarModelError


CALENDAR_SCHEMA_VERSION = "lean_calendar_import_v1"
MAX_CALENDAR_EVENTS = 1_000
PAST_CONTEXT_HOURS = 6
FUTURE_CONTEXT_HOURS = 72
GLOBAL_CATEGORIES = frozenset(
    {"fomc", "cpi", "ppi", "pce", "employment_report", "gdp"}
)
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "source_observed_at",
        "source_name",
        "source_url",
        "events",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "title",
        "category",
        "starts_at",
        "ends_at",
        "time_certainty",
        "importance",
        "affected_symbols",
        "source_url",
    }
)
_SECRET_MARKER = re.compile(
    r"(?:api.?key|authorization|bearer|bot.?token|secret)\s*[:=]",
    re.IGNORECASE,
)


class _LeanCalendarError(ValueError):
    """Raised when calendar input would overstate scheduled-event truth."""


LeanCalendarError = _LeanCalendarError


def load_calendar_snapshot(
    path: Path,
    *,
    source_mode: str,
) -> tuple[CalendarEvent, ...]:
    if source_mode not in {"imported_snapshot", "fixture"}:
        raise LeanCalendarError("calendar source mode is invalid")
    try:
        payload, digest = read_json_document(
            path,
            require_genuine=source_mode == "imported_snapshot",
        )
    except BybitUniverseError as exc:
        raise LeanCalendarError(str(exc)) from exc
    return normalize_calendar_snapshot(
        payload,
        source_mode=source_mode,
        source_sha256=digest,
    )


def normalize_calendar_snapshot(
    payload: object,
    *,
    source_mode: str,
    source_sha256: str,
) -> tuple[CalendarEvent, ...]:
    if not isinstance(payload, Mapping):
        raise LeanCalendarError("calendar snapshot must be an object")
    unexpected = set(payload) - _TOP_LEVEL_FIELDS
    if unexpected:
        raise LeanCalendarError("calendar snapshot contains unsupported fields")
    if payload.get("schema_version") != CALENDAR_SCHEMA_VERSION:
        raise LeanCalendarError("calendar schema version is unsupported")
    source_observed_at = _timestamp(payload.get("source_observed_at"), "source_observed_at")
    source_name = _text(payload.get("source_name"), "source_name", maximum=160)
    source_url = payload.get("source_url")
    if source_url is not None and not isinstance(source_url, str):
        raise LeanCalendarError("calendar source_url is invalid")
    rows = payload.get("events")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CALENDAR_EVENTS:
        raise LeanCalendarError("calendar events must be a bounded array")
    events: list[CalendarEvent] = []
    identifiers: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise LeanCalendarError("calendar event must be an object")
        if set(raw) - _EVENT_FIELDS:
            raise LeanCalendarError("calendar event contains unsupported fields")
        event_id = _text(raw.get("event_id"), "event_id", maximum=160)
        if event_id in identifiers:
            raise LeanCalendarError("calendar event identity is duplicated")
        identifiers.add(event_id)
        affected = raw.get("affected_symbols", [])
        if not isinstance(affected, list):
            raise LeanCalendarError("affected_symbols must be an array")
        symbols: list[str] = []
        for value in affected:
            if not isinstance(value, str):
                raise LeanCalendarError("affected symbol is invalid")
            symbols.append(value.strip().upper())
        event_url = raw.get("source_url", source_url)
        if event_url is not None and not isinstance(event_url, str):
            raise LeanCalendarError("calendar event source_url is invalid")
        try:
            events.append(
                CalendarEvent(
                    event_id=event_id,
                    title=_text(raw.get("title"), "title", maximum=300),
                    category=_text(raw.get("category"), "category", maximum=64),
                    starts_at=_timestamp(raw.get("starts_at"), "starts_at"),
                    ends_at=(
                        _timestamp(raw.get("ends_at"), "ends_at")
                        if raw.get("ends_at") is not None
                        else None
                    ),
                    time_certainty=_text(
                        raw.get("time_certainty"),
                        "time_certainty",
                        maximum=32,
                    ),
                    importance=_text(raw.get("importance"), "importance", maximum=16),
                    source_name=source_name,
                    source_url=event_url,
                    affected_symbols=tuple(symbols),
                    source_observed_at=source_observed_at,
                    source_mode=source_mode,
                    source_sha256=source_sha256,
                )
            )
        except LeanRadarModelError as exc:
            raise LeanCalendarError(str(exc)) from exc
    return tuple(sorted(events, key=lambda row: (row.starts_at, row.event_id)))


def context_for_idea(
    events: Sequence[CalendarEvent],
    *,
    symbol: str,
    evaluated_at: datetime,
) -> dict[str, object]:
    if evaluated_at.tzinfo is None:
        raise LeanCalendarError("calendar evaluation time must be timezone-aware")
    now = evaluated_at.astimezone(timezone.utc)
    lower = now - timedelta(hours=PAST_CONTEXT_HOURS)
    upper = now + timedelta(hours=FUTURE_CONTEXT_HOURS)
    attached: list[CalendarEvent] = []
    for event in events:
        start = _parse_time(event.starts_at)
        end = _parse_time(event.ends_at) if event.ends_at else start
        linked = event.category in GLOBAL_CATEGORIES or symbol in event.affected_symbols
        if linked and end >= lower and start <= upper:
            attached.append(event)
    if not attached:
        return {}
    attached.sort(key=lambda row: (row.starts_at, row.event_id))
    highest = max(
        attached,
        key=lambda row: {"low": 1, "medium": 2, "high": 3}[row.importance],
    ).importance
    future_times = [
        _parse_time(row.starts_at)
        for row in attached
        if _parse_time(row.starts_at) >= now
    ]
    next_event_at = min(future_times).isoformat() if future_times else None
    return {
        "status": "attached",
        "event_count": len(attached),
        "highest_importance": highest,
        "next_event_at": next_event_at,
        "context_only": True,
        "directional_bias_created": False,
        "events": [
            {
                "event_id": row.event_id,
                "title": row.title,
                "category": row.category,
                "starts_at": row.starts_at,
                "ends_at": row.ends_at,
                "time_certainty": row.time_certainty,
                "importance": row.importance,
                "source_name": row.source_name,
                "source_observed_at": row.source_observed_at,
                "source_mode": row.source_mode,
                "source_sha256": row.source_sha256,
                "affected_symbols": list(row.affected_symbols),
            }
            for row in attached
        ],
    }


def score_adjustments(
    context: Mapping[str, object] | None,
    *,
    evaluated_at: datetime,
) -> tuple[float, float]:
    if not context or context.get("status") != "attached":
        return (0.0, 0.0)
    rows = context.get("events")
    if not isinstance(rows, list):
        return (0.0, 0.0)
    now = evaluated_at.astimezone(timezone.utc)
    risk = 0.0
    urgency = 0.0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        importance = row.get("importance")
        risk = max(
            risk,
            {"low": 3.0, "medium": 7.0, "high": 12.0}.get(importance, 0.0),
        )
        raw_start = row.get("starts_at")
        raw_end = row.get("ends_at")
        if not isinstance(raw_start, str):
            continue
        start = _parse_time(raw_start)
        end = _parse_time(raw_end) if isinstance(raw_end, str) else start
        if start <= now <= end:
            hours = 0.0
        elif start >= now:
            hours = (start - now).total_seconds() / 3600
        else:
            continue
        if hours <= 6:
            event_urgency = {"low": 3.0, "medium": 7.0, "high": 12.0}.get(
                importance,
                0.0,
            )
        elif hours <= 24:
            event_urgency = {"low": 1.0, "medium": 3.0, "high": 6.0}.get(
                importance,
                0.0,
            )
        else:
            event_urgency = 0.0
        urgency = max(urgency, event_urgency)
    return (risk, urgency)


def _timestamp(value: object, label: str) -> str:
    text = _text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanCalendarError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanCalendarError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise LeanCalendarError(f"{label} is invalid")
    text = value.strip()
    if _SECRET_MARKER.search(text):
        raise LeanCalendarError(f"{label} contains a credential-like value")
    return text


__all__ = (
    "CALENDAR_SCHEMA_VERSION",
    "FUTURE_CONTEXT_HOURS",
    "GLOBAL_CATEGORIES",
    "LeanCalendarError",
    "context_for_idea",
    "load_calendar_snapshot",
    "normalize_calendar_snapshot",
    "score_adjustments",
)
