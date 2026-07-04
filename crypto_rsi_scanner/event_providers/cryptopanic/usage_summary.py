"""CryptoPanic request usage summary model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CryptoPanicUsageSummary:
    ledger_path: Path | None
    weekly_limit: int
    daily_soft_limit: int
    rolling_7d_requests: int
    today_requests: int
    remaining_weekly: int | None
    remaining_daily_soft: int | None
    successful_requests: int = 0
    failed_requests: int = 0
    partial_success: bool = False
    last_request_at: datetime | None = None
    last_status_code: int | None = None
    last_error_class: str | None = None


__all__ = ("CryptoPanicUsageSummary",)
