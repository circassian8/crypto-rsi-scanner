"""Telegram and preview formatting facade for Event Alpha notifications."""

from __future__ import annotations

from .pipeline import (
    format_core_opportunity_telegram_digest,
    format_exploratory_telegram_digest,
    format_health_heartbeat,
    format_preview,
    format_research_review_telegram_digest,
)
from .sender import TELEGRAM_MAX_CHARS, telegram_chunk_count

__all__ = [
    "TELEGRAM_MAX_CHARS",
    "format_core_opportunity_telegram_digest",
    "format_exploratory_telegram_digest",
    "format_health_heartbeat",
    "format_preview",
    "format_research_review_telegram_digest",
    "telegram_chunk_count",
]
