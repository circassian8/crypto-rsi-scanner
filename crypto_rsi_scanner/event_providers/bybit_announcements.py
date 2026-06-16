"""Fixture-backed Bybit announcement provider for event discovery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..event_models import RawDiscoveredEvent
from ._announcement_common import fetch_announcement_events


class BybitAnnouncementProvider:
    name = "bybit_announcements"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = path
        self.required = required

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_announcement_events(
            self.path,
            provider=self.name,
            start=start,
            end=end,
            required=self.required,
        )
