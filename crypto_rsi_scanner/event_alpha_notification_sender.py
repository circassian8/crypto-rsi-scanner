"""Structured send-attempt metadata for Event Alpha notifications.

This module does not send on its own unless handed a sender callable by the
caller. It only normalizes boolean and structured sender results so the delivery
ledger can record recipient/chunk outcomes without exposing channel secrets.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

TELEGRAM_MAX_CHARS = 4096
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+")
_SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)")


@dataclass(frozen=True)
class NotificationSendAttemptResult:
    attempted: bool = False
    success: bool = False
    recipient_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    chunk_count: int = 0
    delivered_chunks: int = 0
    failed_chunks: int = 0
    error_class: str | None = None
    error_message_safe: str | None = None
    channel_summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_bool(
        cls,
        delivered: bool,
        *,
        recipient_count: int = 0,
        chunk_count: int = 1,
        channel: str = "telegram",
    ) -> "NotificationSendAttemptResult":
        recipients = max(0, int(recipient_count or 0))
        chunks = max(1, int(chunk_count or 1))
        delivered_count = recipients if delivered and recipients > 0 else (1 if delivered else 0)
        failed_count = 0 if delivered else max(1, recipients)
        return cls(
            attempted=True,
            success=bool(delivered),
            recipient_count=recipients,
            delivered_count=delivered_count,
            failed_count=failed_count,
            chunk_count=chunks,
            delivered_chunks=chunks if delivered else 0,
            failed_chunks=0 if delivered else chunks,
            error_class=None if delivered else "send_failed",
            error_message_safe=None if delivered else "no channel delivered",
            channel_summary={"channel": channel, "delivered": bool(delivered)},
        )


SendCallable = Callable[[str], bool | NotificationSendAttemptResult | Mapping[str, Any]]


def normalize_send_result(
    raw: bool | NotificationSendAttemptResult | Mapping[str, Any] | None,
    *,
    message: str = "",
    recipient_count: int = 0,
    channel: str = "telegram",
) -> NotificationSendAttemptResult:
    """Convert sender output into a structured send-attempt result."""
    if isinstance(raw, NotificationSendAttemptResult):
        return _with_computed_success(raw)
    if isinstance(raw, Mapping):
        return _from_mapping(raw, message=message, recipient_count=recipient_count, channel=channel)
    return NotificationSendAttemptResult.from_bool(
        bool(raw),
        recipient_count=recipient_count,
        chunk_count=telegram_chunk_count(message),
        channel=channel,
    )


def telegram_send_attempt(
    send_fn: Callable[..., bool | NotificationSendAttemptResult | Mapping[str, Any]],
    message: str,
    *,
    parse_mode: str | None = None,
    chat_ids: list[str] | tuple[str, ...] | None = None,
) -> NotificationSendAttemptResult:
    """Call an existing Telegram bool sender and wrap the result structurally."""
    recipients = len(chat_ids or ())
    try:
        raw = send_fn(message, parse_mode=parse_mode, chat_ids=chat_ids)
    except Exception as exc:  # noqa: BLE001 - notification send path must fail soft
        return NotificationSendAttemptResult(
            attempted=True,
            success=False,
            recipient_count=recipients,
            delivered_count=0,
            failed_count=max(1, recipients),
            chunk_count=telegram_chunk_count(message),
            delivered_chunks=0,
            failed_chunks=telegram_chunk_count(message),
            error_class=type(exc).__name__,
            error_message_safe=safe_error(exc),
            channel_summary={"channel": "telegram", "exception": type(exc).__name__},
        )
    return normalize_send_result(raw, message=message, recipient_count=recipients, channel="telegram")


def telegram_chunk_count(message: str, *, limit: int = TELEGRAM_MAX_CHARS) -> int:
    text = str(message or "")
    if not text:
        return 1
    return max(1, int(math.ceil(len(text) / max(1, int(limit or TELEGRAM_MAX_CHARS)))))


def safe_error(value: object) -> str | None:
    if value in (None, ""):
        return None
    cleaned = _SECRET_RE.sub(r"\1=[redacted]", str(value).replace("\n", " ").strip())
    return cleaned[:240] if cleaned else None


def _with_computed_success(result: NotificationSendAttemptResult) -> NotificationSendAttemptResult:
    success = bool(result.attempted and result.delivered_count > 0 and result.failed_count == 0)
    summary = dict(result.channel_summary or {})
    return NotificationSendAttemptResult(
        attempted=bool(result.attempted),
        success=success,
        recipient_count=max(0, int(result.recipient_count or 0)),
        delivered_count=max(0, int(result.delivered_count or 0)),
        failed_count=max(0, int(result.failed_count or 0)),
        chunk_count=max(0, int(result.chunk_count or 0)),
        delivered_chunks=max(0, int(result.delivered_chunks or 0)),
        failed_chunks=max(0, int(result.failed_chunks or 0)),
        error_class=(str(result.error_class)[:80] if result.error_class else None),
        error_message_safe=safe_error(result.error_message_safe),
        channel_summary=_redact_mapping(summary),
    )


def _from_mapping(
    raw: Mapping[str, Any],
    *,
    message: str,
    recipient_count: int,
    channel: str,
) -> NotificationSendAttemptResult:
    attempted = bool(raw.get("attempted", True))
    recipients = int(raw.get("recipient_count", recipient_count) or 0)
    chunks = int(raw.get("chunk_count", telegram_chunk_count(message)) or 0)
    delivered = int(raw.get("delivered_count", raw.get("delivered", 0)) or 0)
    failed = int(raw.get("failed_count", raw.get("failed", 0)) or 0)
    delivered_chunks = int(raw.get("delivered_chunks", chunks if delivered and not failed else 0) or 0)
    failed_chunks = int(raw.get("failed_chunks", 0 if delivered and not failed else chunks) or 0)
    summary = raw.get("channel_summary")
    if not isinstance(summary, Mapping):
        summary = {"channel": channel}
    return _with_computed_success(NotificationSendAttemptResult(
        attempted=attempted,
        success=bool(raw.get("success", False)),
        recipient_count=recipients,
        delivered_count=delivered,
        failed_count=failed,
        chunk_count=chunks,
        delivered_chunks=delivered_chunks,
        failed_chunks=failed_chunks,
        error_class=str(raw.get("error_class"))[:80] if raw.get("error_class") else None,
        error_message_safe=safe_error(raw.get("error_message_safe") or raw.get("error_message")),
        channel_summary=dict(summary),
    ))


def _redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key)
        if _SECRET_KEY_RE.search(key_text):
            out[key_text] = "[redacted]"
        elif isinstance(value, str):
            out[key_text] = _SECRET_RE.sub(r"\1=[redacted]", value)
        elif isinstance(value, Mapping):
            out[key_text] = _redact_mapping(value)
        else:
            out[key_text] = value
    return out
