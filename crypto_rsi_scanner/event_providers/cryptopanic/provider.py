"""CryptoPanic provider class."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ...event_core.models import RawDiscoveredEvent
from .provider_support import (
    build_cryptopanic_request_url,
    cryptopanic_process_request_cache_key,
    cryptopanic_quota_skip_reason,
    cryptopanic_request_cache_key,
    cryptopanic_respect_min_interval,
    fetch_cryptopanic_events,
    fetch_cryptopanic_live_events,
    initialize_cryptopanic_provider,
    record_cryptopanic_request,
)


class CryptoPanicProvider:
    name = "cryptopanic"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initialize_cryptopanic_provider(self, *args, **kwargs)

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_cryptopanic_events(self, start, end)

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        return fetch_cryptopanic_live_events(self, start, end)

    def _request_url(self, token: str, *, currencies: str | None = None, page: int | None = None) -> str:
        return build_cryptopanic_request_url(self, token, currencies=currencies, page=page)

    def _request_cache_key(self, *, currencies: str, page: int) -> tuple[Any, ...]:
        return cryptopanic_request_cache_key(self, currencies=currencies, page=page)

    def _process_request_cache_key(self, request_key: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]] | None:
        return cryptopanic_process_request_cache_key(self, request_key)

    def _quota_skip_reason(self, *, now: datetime) -> str | None:
        return cryptopanic_quota_skip_reason(self, now=now)

    def _respect_min_interval(self, *, now: datetime) -> None:
        cryptopanic_respect_min_interval(self, now=now)

    def _record_request(self, **kwargs: Any) -> None:
        record_cryptopanic_request(self, **kwargs)

__all__ = ("CryptoPanicProvider",)
