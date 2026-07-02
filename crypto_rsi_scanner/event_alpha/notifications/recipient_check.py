"""Guarded Telegram recipient diagnostic for Event Alpha notifications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from .sender import NotificationSendAttemptResult, normalize_send_result


SendOneFn = Callable[[str, str], bool | NotificationSendAttemptResult | dict]


@dataclass(frozen=True)
class TelegramRecipientCheckRow:
    recipient_summary: str
    attempted: bool
    delivered: bool
    failed: bool
    error_class: str | None = None
    error_message_safe: str | None = None


@dataclass(frozen=True)
class TelegramRecipientCheckResult:
    profile: str
    attempted: bool
    refused: bool
    block_reason: str | None
    recipient_count: int
    delivered_count: int
    failed_count: int
    rows: tuple[TelegramRecipientCheckRow, ...]


def run_recipient_check(
    recipients: Iterable[str],
    *,
    send_guard_enabled: bool,
    telegram_token_present: bool,
    profile: str,
    send_one: SendOneFn,
    now: datetime | None = None,
) -> TelegramRecipientCheckResult:
    """Send a tiny diagnostic message to each recipient, failing soft."""
    clean_recipients = [str(item).strip() for item in recipients if str(item).strip()]
    if not send_guard_enabled:
        return _refused(profile, clean_recipients, "RSI_EVENT_ALERTS_ENABLED is not enabled")
    if not telegram_token_present or not clean_recipients:
        return _refused(profile, clean_recipients, "Telegram token or recipients are not configured")
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: list[TelegramRecipientCheckRow] = []
    for chat_id in clean_recipients:
        message = (
            "Event Alpha Telegram recipient check\n"
            "Research-only diagnostic. Trading action: NONE.\n"
            f"profile={profile or 'default'} generated_at={observed.isoformat()}"
        )
        try:
            raw = send_one(message, chat_id)
        except Exception as exc:  # noqa: BLE001 - diagnostics must fail soft
            result = NotificationSendAttemptResult(
                attempted=True,
                success=False,
                recipient_count=1,
                delivered_count=0,
                failed_count=1,
                chunk_count=1,
                delivered_chunks=0,
                failed_chunks=1,
                error_class=type(exc).__name__,
                error_message_safe=str(exc)[:160],
            )
        else:
            result = normalize_send_result(raw, message=message, recipient_count=1, channel="telegram")
        rows.append(TelegramRecipientCheckRow(
            recipient_summary=redact_chat_id(chat_id),
            attempted=result.attempted,
            delivered=result.delivered_count > 0,
            failed=result.failed_count > 0 or (result.attempted and result.delivered_count <= 0),
            error_class=result.error_class,
            error_message_safe=result.error_message_safe,
        ))
    return TelegramRecipientCheckResult(
        profile=profile or "default",
        attempted=True,
        refused=False,
        block_reason=None,
        recipient_count=len(clean_recipients),
        delivered_count=sum(1 for row in rows if row.delivered),
        failed_count=sum(1 for row in rows if row.failed),
        rows=tuple(rows),
    )


def format_recipient_check(result: TelegramRecipientCheckResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA TELEGRAM RECIPIENT CHECK (research-only diagnostic)",
        "=" * 76,
        f"profile: {result.profile}",
        f"attempted: {_yes_no(result.attempted)}",
        f"refused: {_yes_no(result.refused)}",
        f"recipients: {result.recipient_count}",
        f"delivered: {result.delivered_count}",
        f"failed: {result.failed_count}",
    ]
    if result.block_reason:
        lines.append(f"block_reason: {result.block_reason}")
    lines.append("")
    if not result.rows:
        lines.append("- no recipient attempts")
    for row in result.rows:
        status = "delivered" if row.delivered else "failed"
        lines.append(f"- {row.recipient_summary}: {status}")
        if row.error_class or row.error_message_safe:
            lines.append(f"  error: {row.error_class or 'send_failed'} {row.error_message_safe or ''}".rstrip())
    if result.failed_count:
        lines.append("")
        lines.append("Suggested next step: remove or fix failed recipients before scheduled notification burn-in.")
    lines.append("No secrets or full chat IDs are printed. Trading action: NONE.")
    return "\n".join(lines).rstrip()


def redact_chat_id(chat_id: object) -> str:
    text = str(chat_id or "").strip()
    if not text:
        return "chat:empty"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"chat:{digest}:len{len(text)}"


def _refused(profile: str, recipients: list[str], reason: str) -> TelegramRecipientCheckResult:
    return TelegramRecipientCheckResult(
        profile=profile or "default",
        attempted=False,
        refused=True,
        block_reason=reason,
        recipient_count=len(recipients),
        delivered_count=0,
        failed_count=0,
        rows=(),
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
