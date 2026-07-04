"""Binance announcement provider class."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ...event_core.models import RawDiscoveredEvent
from .provider_support import (
    fetch_binance_announcement_events,
    fetch_binance_live_events,
    fetch_binance_live_items,
    initialize_binance_announcement_provider,
)


class BinanceAnnouncementProvider:
    name = "binance_announcements"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initialize_binance_announcement_provider(self, *args, **kwargs)

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_binance_announcement_events(self, start, end)

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_binance_live_events(self, start, end)

    async def _fetch_live_items(self) -> list[dict[str, Any]]:
        return await fetch_binance_live_items(self)

__all__ = ("BinanceAnnouncementProvider",)
