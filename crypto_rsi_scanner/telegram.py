"""Telegram subscriber management via the bot's getUpdates feed.

Anyone who presses Start (or sends /start) to the bot is auto-subscribed; /stop
opts them out. Each scan polls getUpdates, processes new commands, and replies
with a confirmation. This lets the alert list grow itself with no manual config.

getUpdates uses an offset cursor (stored in meta) so each update is processed
once. Note: getUpdates and webhooks are mutually exclusive — this assumes no
webhook is set on the bot (the default).
"""

from __future__ import annotations

import json
import logging
import time
import html
from datetime import datetime, timezone

import requests

from . import config

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"

_WELCOME = (
    "✅ You're subscribed to RSI Scanner alerts.\n"
    "Daily watch-list digest + instant pings for high-conviction overbought/"
    "oversold crossings in the top-100 coins.\n\n"
    "Commands: /top  /detail SYM  /stats  /score  /health  /help  /stop"
)
_GOODBYE = "👋 You've unsubscribed. Send /start to rejoin anytime."
_HELP = (
    "<b>RSI Scanner bot</b>\n"
    "/top — strongest current signals\n"
    "/detail SYM — full readout for one coin (e.g. /detail BNB)\n"
    "/stats — historical signal hit-rates\n"
    "/score — paper-trade scoreboard (realized P&amp;L)\n"
    "/health — scan/listener health\n"
    "/start — subscribe · /stop — unsubscribe\n"
    "/help — this message"
)


class _Unreachable(Exception):
    """Telegram API was unreachable (DNS/connection/timeout). Transient and
    expected when the host is asleep or offline, so callers decide how to react
    rather than logging an identical error on every poll."""


def _call(method: str, token: str, _timeout: int = 20, **params) -> dict | None:
    try:
        r = requests.post(
            _API.format(token=token, method=method), json=params, timeout=_timeout
        )
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        # Don't log here: offline, this fires on every poll. Signal the caller
        # (the listener logs once per outage and backs off). redact_token keeps
        # the bot token — embedded in the request URL — out of the message.
        raise _Unreachable(config.redact_token(str(e))) from None
    except Exception as e:
        log.error("Telegram %s failed: %s", method, config.redact_token(str(e)))
        return None


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        _call("sendMessage", token, chat_id=chat_id, text=text,
              parse_mode="HTML", disable_web_page_preview=True)
    except _Unreachable as e:
        log.debug("Telegram unreachable, could not reply to %s: %s", chat_id, e)


# --- latest-scan snapshot (so commands can answer between runs) ------------- #

def save_latest_snapshot(storage, signals: list[dict]) -> None:
    """Persist a trimmed copy of the latest signals for /top and /detail."""
    keep = (
        "symbol", "flag", "severity", "conviction", "conviction_base",
        "rsi_daily", "rsi_4h", "rsi_weekly", "rsi_z", "rsi_delta",
        "volume_ratio", "btc_corr", "divergence", "regime", "regime_note",
        "setup_type", "expected_dir", "market_regime", "market_aligned",
        "price", "pct_24h", "pct_7d", "ath_pct", "track_record",
        "vol_state", "breadth_state", "rs_bucket", "liquidity_bucket",
        "falling_knife_score",
    )
    trimmed = [{k: s.get(k) for k in keep} for s in signals]
    storage.set_meta("latest_signals", json.dumps(trimmed, default=str))


def _load_snapshot(storage) -> list[dict]:
    raw = storage.get_meta("latest_signals")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


# --- command handlers ------------------------------------------------------- #

def _cmd_top(storage) -> str:
    from .formatting import _tg_digest_line  # reuse the compact renderer
    sigs = _load_snapshot(storage)
    crossed = [s for s in sigs if s.get("flag") in ("OB", "OS")]
    crossed.sort(key=lambda s: s.get("conviction", 0), reverse=True)
    if not crossed:
        return "No active overbought/oversold signals right now."
    lines = ["🔝 <b>Top current signals</b>"]
    lines += [_tg_digest_line(s) for s in crossed[:10]]
    return "\n".join(lines)


def _cmd_detail(storage, arg: str) -> str:
    from .formatting import _tg_card
    sym = arg.strip().upper()
    if not sym:
        return "Usage: /detail SYM  (e.g. /detail BNB)"
    sigs = _load_snapshot(storage)
    match = next((s for s in sigs if str(s.get("symbol", "")).upper() == sym), None)
    if not match:
        return f"{sym} isn't on the current watch-list (not stretched, or outside the top-100)."
    return _tg_card(match)


def _cmd_stats(storage) -> str:
    from . import outcomes
    rows = storage.outcomes_joined()
    return "<pre>" + outcomes.build_report(rows, config.OUTCOME_PRIMARY_HORIZON) + "</pre>"


def _cmd_score(storage) -> str:
    from . import paper
    return "<pre>" + paper.report(storage) + "</pre>"


def _cmd_health(storage) -> str:
    from .status_report import format_status
    return "<pre>" + html.escape(format_status(storage), quote=False) + "</pre>"


def _dispatch_command(storage, token: str, chat_id: str, text: str) -> bool:
    """Handle a known command. Returns True if it was a command."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]  # strip @botname suffix
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/top", "/signals"):
        _send(token, chat_id, _cmd_top(storage))
    elif cmd == "/detail":
        _send(token, chat_id, _cmd_detail(storage, arg))
    elif cmd in ("/stats", "/report"):
        _send(token, chat_id, _cmd_stats(storage))
    elif cmd in ("/score", "/scoreboard"):
        _send(token, chat_id, _cmd_score(storage))
    elif cmd in ("/health", "/status"):
        _send(token, chat_id, _cmd_health(storage))
    elif cmd == "/help":
        _send(token, chat_id, _HELP)
    else:
        return False
    return True


def _process_update(storage, token: str, upd: dict) -> bool:
    """Handle one update (subscribe/unsubscribe/command). Returns True if it was
    a brand-new subscriber."""
    msg = upd.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None
    if not chat_id:
        return False
    text = (msg.get("text") or "").strip()
    low = text.lower()
    name = chat.get("username") or chat.get("first_name") or ""

    if low.startswith("/stop"):
        if storage.unsubscribe(chat_id):
            _send(token, chat_id, _GOODBYE)
            log.info("Unsubscribed %s", chat_id)
        return False
    if low.startswith("/") and not low.startswith("/start"):
        # informational command — answer, and subscribe quietly if new
        storage.subscribe(chat_id, name)
        if not _dispatch_command(storage, token, chat_id, text):
            _send(token, chat_id, _HELP)
        return False
    # /start or any first contact -> subscribe + welcome
    if storage.subscribe(chat_id, name):
        _send(token, chat_id, _WELCOME)
        log.info("New subscriber: %s (%s)", chat_id, name or "?")
        return True
    return False


def _poll_once(storage, token: str, long_poll: int = 0) -> int:
    """Fetch and process one batch of updates. Returns new-subscriber count.
    long_poll>0 makes getUpdates block server-side until a message arrives."""
    offset_raw = storage.get_meta("tg_update_offset")
    params = {"timeout": long_poll, "allowed_updates": ["message"]}
    if offset_raw:
        params["offset"] = int(offset_raw)

    # client timeout must exceed server long-poll window
    resp = _call("getUpdates", token, _timeout=long_poll + 15, **params)
    if not resp or not resp.get("ok"):
        return 0
    updates = resp.get("result", [])
    if not updates:
        return 0

    added = 0
    max_update_id = None
    for upd in updates:
        max_update_id = upd["update_id"]
        try:
            if _process_update(storage, token, upd):
                added += 1
        except Exception as e:
            log.error("Failed to process update %s: %s", upd.get("update_id"), e)

    if max_update_id is not None:
        storage.set_meta("tg_update_offset", str(max_update_id + 1))
    return added


def sync_subscribers(storage) -> int:
    """One non-blocking poll (used at scan time). Returns new-subscriber count."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        return 0
    try:
        return _poll_once(storage, token, long_poll=0)
    except _Unreachable as e:
        log.debug("Telegram unreachable during subscriber sync: %s", e)
        return 0


def _check_scan_staleness(storage, state: dict, now=None) -> None:
    """Watchdog: alert once (via heartbeat) if no successful scan has landed in
    config.STALE_SCAN_HOURS. `state` persists the throttle timer + alerted flag
    across listener iterations. No-op when heartbeat is off or there's no scan
    history yet (can't distinguish a fresh install from a stalled one)."""
    if not config.HEARTBEAT_ENABLED or config.STALE_SCAN_HOURS <= 0:
        return
    if time.monotonic() - state.get("last_check", 0.0) < config.STALE_CHECK_INTERVAL_SEC:
        return
    state["last_check"] = time.monotonic()

    last = (
        storage.last_successful_scan_at()
        if hasattr(storage, "last_successful_scan_at")
        else storage.last_scan_at()
    )
    if last is None:
        return
    now = now or datetime.now(timezone.utc)
    hours = (now - last).total_seconds() / 3600.0
    if hours >= config.STALE_SCAN_HOURS:
        if not state.get("alerted"):
            from . import heartbeat
            heartbeat.alert_stale_scan(last, hours, storage)
            state["alerted"] = True
    elif state.get("alerted"):
        log.info("Scan freshness recovered (last scan ~%.0fh ago).", hours)
        state["alerted"] = False


def listen(poll_seconds: int = 30) -> None:
    """Run a continuous long-polling loop so commands get answered in real time.
    Intended to run as a background service (separate from the daily scan)."""
    from .storage import Storage

    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        log.error("TELEGRAM_BOT_TOKEN not set; cannot listen.")
        return

    log.info("Bot listener started (long-poll %ss). Ctrl-C to stop.", poll_seconds)
    storage = Storage(config.DB_PATH)
    offline = False
    backoff = poll_seconds
    stale_state: dict = {}
    try:
        while True:
            try:
                _poll_once(storage, token, long_poll=poll_seconds)
                if offline:
                    log.info("Telegram reachable again — resuming normal polling.")
                    offline, backoff = False, poll_seconds
                # online: opportunistically check the daily scan hasn't gone silent
                _check_scan_staleness(storage, stale_state)
            except KeyboardInterrupt:
                raise
            except _Unreachable:
                # Offline (e.g. host asleep). Log once per outage, then back off
                # exponentially so we neither spin nor flood the log with
                # identical DNS errors. Recovery is logged above on the next
                # successful poll.
                if not offline:
                    log.warning(
                        "Telegram unreachable — backing off and suppressing "
                        "repeats until it recovers."
                    )
                    offline = True
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
            except Exception as e:
                log.error("Listener poll error: %s", config.redact_token(str(e)))
                time.sleep(5)
    except KeyboardInterrupt:
        log.info("Bot listener stopped.")
    finally:
        storage.close()


def seed_subscribers_from_config(storage) -> None:
    """One-time: ensure chat IDs listed in .env are in the subscriber table, so
    existing recipients keep working after switching to auto-subscribe."""
    for chat_id in config.TELEGRAM_CHAT_IDS:
        storage.subscribe(chat_id, name="seed")
