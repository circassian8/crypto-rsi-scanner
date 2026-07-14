"""Timestamp presentation value."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimePresentation:
    """Local, relative, and exact UTC views of one instant."""

    available: bool
    local_label: str
    relative_label: str
    utc_label: str
    iso_utc: str
    timezone_label: str

    @property
    def primary_label(self) -> str:
        if not self.available:
            return "Unavailable"
        return f"{self.relative_label} · {self.local_label}"
