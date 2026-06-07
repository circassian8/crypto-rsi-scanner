from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from . import config, formatting

log = logging.getLogger(__name__)


def _truncate(text: str, limit: int) -> str:
    """Truncate on a line boundary so we never cut an HTML tag in half."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit - 2)
    if cut == -1:
        cut = limit - 2
    return text[:cut] + "\n…"


def send_telegram(
    text: str, parse_mode: str | None = None, chat_ids: list[str] | None = None
) -> bool:
    """Send to every recipient chat ID. Returns True if at least one delivers,
    so one bad/blocked recipient doesn't suppress the others.

    chat_ids defaults to the static list from config; callers (the scanner) pass
    the live subscriber list from the DB instead."""
    token = config.TELEGRAM_BOT_TOKEN
    if chat_ids is None:
        chat_ids = config.TELEGRAM_CHAT_IDS
    if not token or not chat_ids:
        return False

    body = _truncate(text, 4096)
    sent = 0
    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": body,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=20,
            )
            r.raise_for_status()
            sent += 1
        except Exception as e:
            # Most common cause: recipient never pressed Start on the bot.
            log.error("Telegram send to %s failed: %s", chat_id, config.redact_token(str(e)))

    if sent:
        log.info("Telegram message sent to %d/%d recipient(s)", sent, len(chat_ids))
    return sent > 0


def send_discord(text: str) -> bool:
    url = config.DISCORD_WEBHOOK_URL
    if not url:
        return False
    try:
        r = requests.post(
            url,
            json={"content": _truncate(text, 2000)},
            timeout=20,
        )
        r.raise_for_status()
        log.info("Discord message sent")
        return True
    except Exception as e:
        log.error("Discord send failed: %s", e)
        return False


def send_email(subject: str, body: str) -> bool:
    if not all([config.SMTP_HOST, config.SMTP_USER, config.SMTP_PASS, config.EMAIL_TO]):
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.SMTP_USER
        msg["To"] = config.EMAIL_TO
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        log.info("Email sent to %s", config.EMAIL_TO)
        return True
    except Exception as e:
        log.error("Email send failed: %s", e)
        return False


def notify_all(
    kind: str,
    signals: list[dict],
    ts: str,
    chat_ids: list[str] | None = None,
    macro_line: str = "",
) -> list[str]:
    """Send a tiered alert, formatted per channel.

    kind: "instant" or "digest". Telegram gets rich HTML; Discord/email get a
    plain-text fallback. chat_ids, if given, overrides the static config list
    (the scanner passes the live DB subscriber list). macro_line is an optional
    market-context header line.
    """
    tg_text = formatting.telegram_html(kind, signals, ts, macro_line=macro_line)
    plain = formatting.plain_text(kind, signals, ts, macro_line=macro_line)
    label = "HEADS UP" if kind == "instant" else "Watch-list"
    subject = f"RSI {label} - {len(signals)}"

    sent: list[str] = []
    if send_telegram(tg_text, parse_mode="HTML", chat_ids=chat_ids):
        sent.append("Telegram")
    if send_discord(plain):
        sent.append("Discord")
    if send_email(subject, plain):
        sent.append("Email")
    if not sent:
        log.info("No notification channels configured")
    else:
        log.info("Notified via: %s", ", ".join(sent))
    return sent
