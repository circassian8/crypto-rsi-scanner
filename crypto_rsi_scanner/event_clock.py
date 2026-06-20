"""Research-clock helpers for deterministic event-radar runs."""

from __future__ import annotations

from datetime import datetime, timezone


FIXED_CLOCK_STALE_HOURS = 24.0
FIXED_CLOCK_FUTURE_TOLERANCE_HOURS = 1.0


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


def event_clock_status(
    config_value: str | datetime | None = None,
    *,
    override: str | datetime | None = None,
    wall_clock_now: datetime | None = None,
) -> dict[str, object]:
    """Return a reportable description of the active event research clock."""
    wall = _as_utc(wall_clock_now or datetime.now(timezone.utc))
    override_now = parse_event_now(override)
    config_now = parse_event_now(config_value)
    fixed = override_now or config_now
    if fixed is None:
        return {
            "clock_mode": "live",
            "research_now": wall.isoformat(),
            "wall_clock_now": wall.isoformat(),
            "fixed_clock_age_hours": None,
            "fixed_clock_source": None,
            "warnings": (),
        }
    age_hours = (wall - fixed).total_seconds() / 3600.0
    warnings: list[str] = ["fixed research clock active"]
    if age_hours > FIXED_CLOCK_STALE_HOURS:
        warnings.append(f"fixed research clock is stale by {age_hours:.1f}h")
    elif age_hours < -FIXED_CLOCK_FUTURE_TOLERANCE_HOURS:
        warnings.append(f"fixed research clock is in the future by {abs(age_hours):.1f}h")
    return {
        "clock_mode": "fixed",
        "research_now": fixed.isoformat(),
        "wall_clock_now": wall.isoformat(),
        "fixed_clock_age_hours": round(age_hours, 4),
        "fixed_clock_source": "override" if override_now is not None else "config",
        "warnings": tuple(warnings),
    }


def fixed_clock_notification_blocker(
    status: dict[str, object],
    *,
    stale_hours: float = FIXED_CLOCK_STALE_HOURS,
    future_tolerance_hours: float = FIXED_CLOCK_FUTURE_TOLERANCE_HOURS,
) -> str | None:
    """Return a send blocker when a fixed notification clock is too old or future-dated."""
    if str(status.get("clock_mode") or "") != "fixed":
        return None
    age = status.get("fixed_clock_age_hours")
    try:
        age_hours = float(age)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if age_hours > stale_hours:
        return (
            f"fixed research clock is stale by {age_hours:.1f}h; unset RSI_EVENT_RESEARCH_NOW "
            "or set RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1 to override"
        )
    if age_hours < -future_tolerance_hours:
        return (
            f"fixed research clock is in the future by {abs(age_hours):.1f}h; unset RSI_EVENT_RESEARCH_NOW "
            "or set RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1 to override"
        )
    return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
