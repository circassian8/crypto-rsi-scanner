from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from . import config, formatting
from .event_alpha_notification_sender import NotificationSendAttemptResult, safe_error

log = logging.getLogger(__name__)


def _truncate(text: str, limit: int) -> str:
    """Truncate on a line boundary so we never cut an HTML tag in half."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit - 2)
    if cut == -1:
        cut = limit - 2
    return text[:cut] + "\n…"


def _message_chunks(text: str, limit: int) -> list[str]:
    """Split long messages on line boundaries without discarding content."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut <= 0:
            cut = rest.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    if rest:
        chunks.append(rest)
    return chunks


def send_telegram(
    text: str, parse_mode: str | None = None, chat_ids: list[str] | None = None
) -> bool:
    """Send to every recipient chat ID. Returns True if at least one delivers,
    so one bad/blocked recipient doesn't suppress the others.

    chat_ids defaults to the static list from config; callers (the scanner) pass
    the live subscriber list from the DB instead."""
    result = send_telegram_structured(text, parse_mode=parse_mode, chat_ids=chat_ids)
    return result.delivered_count > 0


def send_telegram_structured(
    text: str,
    parse_mode: str | None = None,
    chat_ids: list[str] | tuple[str, ...] | None = None,
) -> NotificationSendAttemptResult:
    """Send Telegram and return redacted recipient/chunk delivery details."""
    token = config.TELEGRAM_BOT_TOKEN
    configured = chat_ids if chat_ids is not None else config.TELEGRAM_CHAT_IDS
    recipients = list(configured or [])
    chunks = _message_chunks(text, 4096)
    summary: dict[str, object] = {
        "channel": "telegram",
        "recipient_count": len(recipients),
        "chunk_count": len(chunks),
    }
    if not token or not recipients:
        return NotificationSendAttemptResult(
            attempted=False,
            success=False,
            recipient_count=len(recipients),
            delivered_count=0,
            failed_count=0,
            chunk_count=len(chunks),
            delivered_chunks=0,
            failed_chunks=0,
            error_class="not_configured",
            error_message_safe="telegram token or chat ids missing",
            channel_summary={**summary, "configured": False},
        )

    delivered_recipients = 0
    failed_recipients = 0
    delivered_chunks = 0
    failed_chunks = 0
    first_error_class: str | None = None
    first_error_safe: str | None = None
    for chat_id in recipients:
        delivered_all = True
        for body in chunks:
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
                delivered_chunks += 1
            except Exception as e:
                delivered_all = False
                failed_chunks += 1
                if first_error_class is None:
                    first_error_class = type(e).__name__
                    first_error_safe = safe_error(config.redact_token(str(e)))
                # Most common cause: recipient never pressed Start on the bot.
                log.error("Telegram send to %s failed: %s", chat_id, config.redact_token(str(e)))
                break
        if delivered_all:
            delivered_recipients += 1
        else:
            failed_recipients += 1

    if delivered_recipients:
        log.info(
            "Telegram message sent to %d/%d recipient(s) in %d chunk(s)",
            delivered_recipients,
            len(recipients),
            len(chunks),
        )
    return NotificationSendAttemptResult(
        attempted=True,
        success=delivered_recipients > 0 and failed_recipients == 0,
        recipient_count=len(recipients),
        delivered_count=delivered_recipients,
        failed_count=failed_recipients,
        chunk_count=len(chunks),
        delivered_chunks=delivered_chunks,
        failed_chunks=failed_chunks,
        error_class=first_error_class,
        error_message_safe=first_error_safe,
        channel_summary={
            **summary,
            "configured": True,
            "delivered_count": delivered_recipients,
            "failed_count": failed_recipients,
            "delivered_chunks": delivered_chunks,
            "failed_chunks": failed_chunks,
        },
    )


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
