"""Fixture-backed external IPO catalyst provider for event discovery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..event_core.models import RawDiscoveredEvent
from ._external_common import fetch_external_events


class ExternalIpoProvider:
    name = "external_ipo"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = path
        self.required = required

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_external_events(
            self.path,
            provider=self.name,
            default_event_type="ipo_proxy",
            start=start,
            end=end,
            required=self.required,
        )
