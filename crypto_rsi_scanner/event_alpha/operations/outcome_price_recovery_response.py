"""Exact in-memory provider response for outcome-price recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CapturedCoinGeckoResponse:
    """Exact single-attempt response retained only in process memory."""

    request_id: str
    provider_base_url: str
    http_status: int
    requested_at: datetime
    received_at: datetime
    body: bytes


__all__ = ("CapturedCoinGeckoResponse",)
