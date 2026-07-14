"""Pure value formatting and normalization for the calendar dashboard.

These helpers operate only on already-loaded calendar rows.  They do not read
artifacts, discover providers, or change canonical Decision data.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from .components import safe_external_href
from .presentation import (
    UNAVAILABLE,
    format_duration,
    humanize_enum,
    humanize_reason,
)


_GLOBAL_ASSETS = {"ALL", "CRYPTO", "CRYPTO_MARKET", "GLOBAL", "MARKET", "MARKET_WIDE"}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr|d|day|w|week)s?\s*$", re.I)
_UTC = timezone.utc


def _event_sort_key(row: Mapping[str, Any]) -> tuple[datetime, str]:
    instant = _event_instant(row) or datetime.max.replace(tzinfo=_UTC)
    return instant, str(row.get("title") or "").casefold()


def _event_instant(row: Mapping[str, Any]) -> datetime | None:
    for field in ("window_start", "scheduled_at", "window_end"):
        parsed = _parse_instant(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_instant(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=_UTC)
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(normalized)
            except ValueError:
                return None
            parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=_UTC)
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_UTC)
    return parsed.astimezone(_UTC)


def _day_heading(day: date | None, current: date) -> str:
    if day is None:
        return "Date to be confirmed"
    relative = ""
    if day == current:
        relative = "Today · "
    elif (day - current).days == 1:
        relative = "Tomorrow · "
    year = f", {day.year}" if day.year != current.year else ""
    return f"{relative}{day:%A, %B} {day.day}{year}"


def _importance(row: Mapping[str, Any]) -> str:
    return _token(row.get("importance") or row.get("impact")) or "unknown"


def _importance_sort(value: str) -> tuple[int, str]:
    return ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(value, 9), value)


def _importance_tone(value: str) -> str:
    return {"critical": "danger", "high": "warning", "medium": "info", "low": "neutral"}.get(value, "muted")


def _temporal_label(value: str) -> str:
    return {
        "active": "Active risk window",
        "upcoming": "Upcoming",
        "past": "Passed",
    }.get(value, "Upcoming")


def _temporal_tone(value: str) -> str:
    return {
        "active": "warning",
        "upcoming": "info",
        "past": "muted",
    }.get(value, "info")


def _certainty_label(value: str, *, has_window: bool = False) -> str:
    if has_window:
        return "Scheduled window"
    labels = {
        "confirmed": "Confirmed time",
        "exact": "Confirmed time",
        "scheduled": "Scheduled time",
        "window": "Scheduled window",
        "range": "Scheduled window",
        "approximate": "Approximate time",
        "estimated": "Approximate time",
        "date_only": "Date known · time unconfirmed",
        "unknown": "Timing unconfirmed",
        "unconfirmed": "Timing unconfirmed",
    }
    return labels.get(value, "Timing certainty not recorded")


def _event_is_exact(row: Mapping[str, Any]) -> bool:
    certainty = _token(row.get("time_certainty"))
    return (
        certainty in {"confirmed", "exact", "scheduled"}
        and row.get("scheduled_at") not in (None, "")
        and not _has_window(row)
    )


def _has_window(row: Mapping[str, Any]) -> bool:
    return row.get("window_start") not in (None, "") or row.get("window_end") not in (None, "")


def _category_tokens(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[object] = [row.get("category"), row.get("event_category"), row.get("event_kind")]
    values.extend(_iter_values(row.get("categories")))
    return tuple(dict.fromkeys(value for item in values if (value := _token(item))))


def _scope(row: Mapping[str, Any]) -> str:
    explicit = _token(row.get("scope") or row.get("market_scope"))
    if explicit in {"global", "market", "market_wide"}:
        return "market_wide"
    if explicit in {"asset", "asset_specific", "token_specific"}:
        return "asset_specific"
    assets = _asset_tokens(row)
    return "market_wide" if not assets or assets & _GLOBAL_ASSETS else "asset_specific"


def _matches_filters(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    """Apply presentation-only calendar filters to one projected event row."""

    temporal_state = str(
        row.get("_dashboard_calendar_temporal_state") or "upcoming"
    )
    time_filter = filters.get("time") or "current"
    if time_filter == "current" and temporal_state not in {"active", "upcoming"}:
        return False
    if time_filter in {"active", "upcoming", "past"} and temporal_state != time_filter:
        return False
    if filters.get("importance") and filters["importance"] != _importance(row):
        return False
    if filters.get("category") and filters["category"] not in _category_tokens(row):
        return False
    if filters.get("scope") and filters["scope"] != _scope(row):
        return False
    search = filters.get("search")
    if search:
        text = " ".join(
            str(value or "")
            for value in (
                row.get("title"),
                row.get("source"),
                row.get("provider"),
                row.get("description"),
                " ".join(_assets(row)),
                " ".join(_category_tokens(row)),
            )
        ).casefold()
        if search not in text:
            return False
    return True


def _assets(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in _iter_values(row.get("affected_assets")) if str(value).strip())


def _asset_tokens(row: Mapping[str, Any]) -> set[str]:
    return {_asset_token(value) for value in _assets(row) if _asset_token(value)}


def _asset_token(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _impact_window(row: Mapping[str, Any]) -> str:
    before = _duration_value(row.get("impact_window_before"))
    after = _duration_value(row.get("impact_window_after"))
    if before != UNAVAILABLE and after != UNAVAILABLE:
        return f"From {before} before through {after} after"
    if before != UNAVAILABLE:
        return f"Begins {before} before the event"
    if after != UNAVAILABLE:
        return f"Continues {after} after the event"
    return "Not recorded"


def _raw_impact_window(row: Mapping[str, Any]) -> str:
    before = str(row.get("impact_window_before") or "").strip()
    after = str(row.get("impact_window_after") or "").strip()
    if before and after:
        return f"-{before} / +{after}"
    if before:
        return f"-{before}"
    if after:
        return f"+{after}"
    return "Not recorded"


def _reminder_labels(value: object) -> tuple[str, ...]:
    labels = []
    for item in _iter_values(value):
        raw = item.get("offset") if isinstance(item, Mapping) else item
        label = _duration_value(raw)
        if label != UNAVAILABLE:
            labels.append(f"{label} before")
    return tuple(labels)


def _duration_value(value: object) -> str:
    seconds = _duration_seconds(value)
    return format_duration(seconds) if seconds is not None else UNAVAILABLE


def _duration_seconds(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = _finite_number(value)
        return number if number is not None and number >= 0 else None
    match = _DURATION.fullmatch(str(value or ""))
    if not match:
        return None
    magnitude = float(match.group(1))
    unit = match.group(2).casefold()
    multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
        "d": 86400,
        "day": 86400,
        "w": 604800,
        "week": 604800,
    }[unit]
    return magnitude * multiplier


def _source(row: Mapping[str, Any]) -> tuple[str, str]:
    label = _operator_text(
        row.get("source") or row.get("provider"),
        fallback="Recorded source",
    )
    raw = str(row.get("source_url") or "").strip()
    if not raw:
        return label, ""
    safe_url = safe_external_href(raw)
    if safe_url is None:
        return label, ""
    return label, safe_url


def _operator_text(value: object, *, reason: bool = False, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if "_" in text and not any(character.isspace() for character in text):
        return humanize_reason(text) if reason else humanize_enum(text)
    return text


def _iter_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def _token(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


__all__ = ()
