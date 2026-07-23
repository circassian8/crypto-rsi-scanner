"""One fail-closed freshness rule for persisted Lean Radar scan truth."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping


def market_scan_freshness(
    scan: Mapping[str, object],
    *,
    evaluated_at: datetime,
    default_cadence_minutes: int = 20,
) -> tuple[str, float | None]:
    """Return whether the latest completed scan can support current ideas."""

    if evaluated_at.tzinfo is None:
        raise ValueError("market freshness clock must be timezone-aware")
    if scan.get("status") != "complete":
        return "incomplete", None
    observed_at = scan.get("observed_at")
    if not isinstance(observed_at, str):
        return "unavailable", None
    observed = _time(observed_at)
    age_seconds = (evaluated_at.astimezone(timezone.utc) - observed).total_seconds()
    if age_seconds < -60:
        return "future_invalid", age_seconds
    raw_cadence = scan.get("cadence_minutes", default_cadence_minutes)
    if (
        isinstance(raw_cadence, bool)
        or not isinstance(raw_cadence, (int, float))
        or not 15 <= float(raw_cadence) <= 30
    ):
        return "invalid_cadence", age_seconds
    if age_seconds <= float(raw_cadence) * 120:
        return "current", max(0.0, age_seconds)
    return "stale", age_seconds


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("market freshness timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("market freshness timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = ("market_scan_freshness",)
