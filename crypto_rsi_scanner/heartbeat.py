"""Dead-man's-switch / health alerting.

A scanner that fails silently is worse than no scanner. These helpers push a
short health alert to Telegram when a run crashes, returns no data, or degrades
(many coins failing to fetch) — so silent breakage surfaces immediately instead
of hiding in the logs.
"""

from __future__ import annotations

import logging

from . import config
from .notifications import send_telegram

log = logging.getLogger(__name__)


def _send(text: str, storage) -> None:
    recipients = None
    if storage is not None:
        recipients = storage.active_subscribers() or None
    send_telegram(text, parse_mode="HTML", chat_ids=recipients)


def alert_failure(exc: Exception, storage=None) -> None:
    """The run raised before completing — notify that the scanner is down."""
    if not config.HEARTBEAT_ENABLED:
        return
    text = (
        "🚨 <b>RSI Scanner FAILED</b>\n"
        f"The run crashed: <code>{type(exc).__name__}: {str(exc)[:300]}</code>\n"
        "No scan was produced. Check network / API key / logs."
    )
    try:
        _send(text, storage)
        log.info("Heartbeat failure alert sent")
    except Exception as e:  # never let the alerter mask the original error
        log.error("Heartbeat failure alert could not be sent: %s", e)


def check_health(stats: dict, storage=None) -> bool:
    """Inspect a completed run's stats; alert on no-data or heavy degradation.
    Returns True if healthy, False if a warning was raised."""
    if not config.HEARTBEAT_ENABLED:
        return True

    requested = stats.get("requested", 0)
    fetched = stats.get("fetched", 0)
    analyzed = stats.get("analyzed", 0)

    if requested == 0 or fetched == 0:
        _send(
            "🚨 <b>RSI Scanner — NO DATA</b>\n"
            "The run completed but fetched no price data. Likely a dead API key "
            "or network outage.",
            storage,
        )
        log.warning("Heartbeat: no data fetched")
        return False

    fail_ratio = 1.0 - (fetched / requested)
    if fail_ratio > config.HEARTBEAT_MAX_FETCH_FAIL_RATIO:
        _send(
            "⚠️ <b>RSI Scanner — DEGRADED</b>\n"
            f"Only {fetched}/{requested} coins fetched "
            f"({fail_ratio:.0%} failed). Results may be incomplete — possible "
            "rate-limiting or partial outage.",
            storage,
        )
        log.warning("Heartbeat: degraded fetch (%d/%d)", fetched, requested)
        return False

    log.info("Heartbeat: healthy (%d/%d fetched, %d analyzed)", fetched, requested, analyzed)
    return True
