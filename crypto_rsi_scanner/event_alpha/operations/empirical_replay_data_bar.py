"""Completed-bar value object for empirical replay inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ReplayBar:
    """One completed daily bar; ``observed_at`` is the daily close boundary."""

    bar_open_at: datetime
    observed_at: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float
    base_volume: float
    quote_volume: float
    bar_duration_seconds: int
    full_daily_bar: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-shaped copy suitable for outcome-path calculations."""

        return {
            "bar_open_at": _iso(self.bar_open_at),
            "observed_at": _iso(self.observed_at),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "base_volume": self.base_volume,
            "quote_volume": self.quote_volume,
            "bar_duration_seconds": self.bar_duration_seconds,
            "full_daily_bar": self.full_daily_bar,
        }


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ("ReplayBar",)
