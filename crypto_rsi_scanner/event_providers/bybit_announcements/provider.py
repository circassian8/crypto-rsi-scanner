"""Bybit announcement provider class."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ...event_core.models import RawDiscoveredEvent
from .provider_support import (
    build_bybit_request_url,
    fetch_bybit_announcement_events,
    fetch_bybit_live_events,
    initialize_bybit_announcement_provider,
)


class BybitAnnouncementProvider:
    name = "bybit_announcements"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initialize_bybit_announcement_provider(self, *args, **kwargs)

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_bybit_announcement_events(self, start, end)

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_bybit_live_events(self, start, end)

    def _request_url(self) -> str:
        return build_bybit_request_url(self)

__all__ = ("BybitAnnouncementProvider",)
