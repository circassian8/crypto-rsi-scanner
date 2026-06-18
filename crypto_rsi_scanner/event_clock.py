"""Research-clock helpers for deterministic event-radar runs."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_event_now(value: str | datetime | None) -> datetime | None:
    """Parse an optional event research timestamp as timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid event research timestamp {value!r}; use ISO-8601 like 2026-06-15T16:00:00Z"
            ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def event_research_now(
    config_value: str | datetime | None = None,
    *,
    override: str | datetime | None = None,
) -> datetime:
    """Return the injected event research clock or the real UTC wall clock."""
    parsed = parse_event_now(override)
    if parsed is not None:
        return parsed
    parsed = parse_event_now(config_value)
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)
