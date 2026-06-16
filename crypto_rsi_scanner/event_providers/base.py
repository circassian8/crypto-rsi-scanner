"""Provider protocols for event-discovery research adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..event_models import DiscoveredAsset, RawDiscoveredEvent


class EventProvider(Protocol):
    name: str

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        """Return raw event evidence for the requested window."""


class AssetUniverseProvider(Protocol):
    name: str

    def fetch_assets(self) -> list[DiscoveredAsset]:
        """Return assets available for event-to-asset resolution."""
