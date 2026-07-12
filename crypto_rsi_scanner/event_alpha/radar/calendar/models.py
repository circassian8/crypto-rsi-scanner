"""Pure unified-calendar models and validation.

Calendar rows are operator research context.  They are never trading or
notification instructions and carry explicit zero-side-effect facts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


CALENDAR_EVENT_KINDS = frozenset(
    {
        "central_bank",
        "inflation",
        "employment",
        "macro_release",
        "crypto_unlock",
        "exchange",
        "project",
        "protocol",
        "regulatory",
    }
)
DATE_CERTAINTY_LEVELS = frozenset({"exact", "window", "estimated", "unknown"})
CALENDAR_IMPORTANCE_LEVELS = frozenset({"low", "medium", "high", "critical"})
CALENDAR_TRACKING_STATES = frozenset(
    {
        "upcoming",
        "active_window",
        "changed",
        "completed",
        "canceled",
        "needs_confirmation",
    }
)

_REMINDER_RE = re.compile(r"^[1-9][0-9]*(?:m|h|d|w)$")
_EVENT_KIND_ALIASES = {
    "cpi": "inflation",
    "ppi": "inflation",
    "inflation_release": "inflation",
    "jobs": "employment",
    "nonfarm_payrolls": "employment",
    "nfp": "employment",
    "fomc": "central_bank",
    "rate_decision": "central_bank",
    "token_unlock": "crypto_unlock",
    "vesting_cliff": "crypto_unlock",
    "linear_emission": "crypto_unlock",
    "listing": "exchange",
    "delisting": "exchange",
    "protocol_upgrade": "protocol",
    "mainnet": "protocol",
    "testnet": "protocol",
    "governance_vote": "protocol",
    "airdrop": "project",
}
_FORBIDDEN_TRUE_FIELDS = (
    "created_alert",
    "notification_send_enabled",
    "execution_enabled",
    "paper_trading_enabled",
    "normal_rsi_routing_enabled",
    "sent",
    "trade_created",
    "paper_trade_created",
    "normal_rsi_signal_written",
)
_ZERO_SIDE_EFFECT_FIELDS = (
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)


class CalendarRejectionCode(StrEnum):
    """Closed payload-free reason codes for rejected calendar mappings."""

    MISSING_EVENT_ID = "missing_event_id"
    MISSING_TITLE = "missing_title"
    UNSUPPORTED_EVENT_KIND = "unsupported_event_kind"
    UNSUPPORTED_TIME_CERTAINTY = "unsupported_time_certainty"
    UNSUPPORTED_IMPORTANCE = "unsupported_importance"
    UNSUPPORTED_TRACKING_STATUS = "unsupported_tracking_status"
    MISSING_SOURCE = "missing_source"
    INVALID_SOURCE_URL = "invalid_source_url"
    INVALID_TIMESTAMP = "invalid_timestamp"
    EXACT_MISSING_SCHEDULED_AT = "exact_missing_scheduled_at"
    WINDOW_MISSING_BOUNDS = "window_missing_bounds"
    WINDOW_END_BEFORE_START = "window_end_before_start"
    INVALID_REMINDER_WINDOW = "invalid_reminder_window"
    UNSAFE_RESEARCH_ONLY = "unsafe_research_only"
    UNSAFE_NO_SEND_REHEARSAL = "unsafe_no_send_rehearsal"
    UNSAFE_SIDE_EFFECT_FLAG = "unsafe_side_effect_flag"
    INVALID_SIDE_EFFECT_COUNTER = "invalid_side_effect_counter"
    NONZERO_SIDE_EFFECT_COUNTER = "nonzero_side_effect_counter"


CALENDAR_REJECTION_CODES = frozenset(code.value for code in CalendarRejectionCode)


class CalendarValidationError(ValueError):
    """Raised when a calendar row violates its data or safety contract."""

    def __init__(self, message: str, *, code: CalendarRejectionCode) -> None:
        if not isinstance(code, CalendarRejectionCode):
            raise TypeError("calendar validation errors require a registered rejection code")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class UnifiedCalendarEvent:
    calendar_event_id: str
    title: str
    event_kind: str
    scheduled_at: str | None
    window_start: str | None
    window_end: str | None
    time_certainty: str
    importance: str
    affected_assets: tuple[str, ...]
    source: str
    source_url: str
    reminder_windows: tuple[str, ...]
    post_event_tracking_status: str
    profile: str | None = None
    artifact_namespace: str | None = None
    run_mode: str | None = None
    run_id: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        _validate_event(self)

    def to_dict(self) -> dict[str, Any]:
        """Return the stable research-artifact representation."""

        return {
            "schema_version": 1,
            "row_type": "event_unified_calendar_event",
            "calendar_event_id": self.calendar_event_id,
            "title": self.title,
            "event_kind": self.event_kind,
            "scheduled_at": self.scheduled_at,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "time_certainty": self.time_certainty,
            "importance": self.importance,
            "affected_assets": list(self.affected_assets),
            "source": self.source,
            "source_url": self.source_url,
            "reminder_windows": list(self.reminder_windows),
            "post_event_tracking_status": self.post_event_tracking_status,
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "run_mode": self.run_mode,
            "run_id": self.run_id,
            "observed_at": self.observed_at,
            "research_only": True,
            "no_send_rehearsal": True,
            "sent": False,
            "created_alert": False,
            "notification_send_enabled": False,
            "execution_enabled": False,
            "paper_trading_enabled": False,
            "normal_rsi_routing_enabled": False,
            "trade_created": False,
            "paper_trade_created": False,
            "normal_rsi_signal_written": False,
            "strict_alerts_created": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "UnifiedCalendarEvent":
        _validate_input_safety(row)
        return normalize_unified_calendar_event(row)


def normalize_unified_calendar_event(
    item: Mapping[str, Any],
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: str | datetime | None = None,
) -> UnifiedCalendarEvent:
    """Normalize one fixture or local artifact row into the unified model."""

    _validate_input_safety(item)
    title = _text(item.get("title") or item.get("event_name") or item.get("name"))
    kind = _event_kind(item)
    scheduled_at = _timestamp_text(
        _first_present_nonempty(
            item,
            "scheduled_at",
            "event_start_time",
            "event_time",
            "date_event",
        )
    )
    window_start = _timestamp_text(
        _first_present_nonempty(item, "window_start", "window_start_at", "date_window_start")
    )
    window_end = _timestamp_text(
        _first_present_nonempty(item, "window_end", "window_end_at", "date_window_end")
    )
    certainty = _time_certainty(item, scheduled_at=scheduled_at, window_start=window_start, window_end=window_end)
    importance = _token(item.get("importance") or "medium")
    assets = _affected_assets(item)
    source = _text(item.get("source") or item.get("provider") or "fixture")
    source_url = _text(item.get("source_url") or item.get("url") or item.get("link"))
    reminders = _reminder_windows(item, importance=importance)
    tracking = _post_event_tracking_status(item, certainty=certainty)
    observed = _timestamp_text(observed_at if observed_at is not None else item.get("observed_at"))
    event_id = _text(item.get("calendar_event_id") or item.get("event_id") or item.get("id"))
    if not event_id:
        seed = "|".join((title, kind, scheduled_at or window_start or "unknown", source))
        event_id = f"cal:{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"
    return UnifiedCalendarEvent(
        calendar_event_id=event_id,
        title=title,
        event_kind=kind,
        scheduled_at=scheduled_at,
        window_start=window_start,
        window_end=window_end,
        time_certainty=certainty,
        importance=importance,
        affected_assets=assets,
        source=source,
        source_url=source_url,
        reminder_windows=reminders,
        post_event_tracking_status=tracking,
        profile=_optional_text(profile if profile is not None else item.get("profile")),
        artifact_namespace=_optional_text(
            artifact_namespace if artifact_namespace is not None else item.get("artifact_namespace")
        ),
        run_mode=_optional_text(run_mode if run_mode is not None else item.get("run_mode")),
        run_id=_optional_text(run_id if run_id is not None else item.get("run_id")),
        observed_at=observed,
    )


def _validate_event(event: UnifiedCalendarEvent) -> None:
    if not event.calendar_event_id:
        raise CalendarValidationError(
            "calendar_event_id is required",
            code=CalendarRejectionCode.MISSING_EVENT_ID,
        )
    if not event.title:
        raise CalendarValidationError(
            "calendar title is required",
            code=CalendarRejectionCode.MISSING_TITLE,
        )
    if event.event_kind not in CALENDAR_EVENT_KINDS:
        raise CalendarValidationError(
            "unsupported event_kind",
            code=CalendarRejectionCode.UNSUPPORTED_EVENT_KIND,
        )
    if event.time_certainty not in DATE_CERTAINTY_LEVELS:
        raise CalendarValidationError(
            "unsupported time_certainty",
            code=CalendarRejectionCode.UNSUPPORTED_TIME_CERTAINTY,
        )
    if event.importance not in CALENDAR_IMPORTANCE_LEVELS:
        raise CalendarValidationError(
            "unsupported importance",
            code=CalendarRejectionCode.UNSUPPORTED_IMPORTANCE,
        )
    if event.post_event_tracking_status not in CALENDAR_TRACKING_STATES:
        raise CalendarValidationError(
            "unsupported post_event_tracking_status",
            code=CalendarRejectionCode.UNSUPPORTED_TRACKING_STATUS,
        )
    if not event.source:
        raise CalendarValidationError(
            "calendar source is required",
            code=CalendarRejectionCode.MISSING_SOURCE,
        )
    try:
        parsed_url = urlsplit(event.source_url)
        parsed_url.port
    except ValueError:
        raise CalendarValidationError(
            "calendar source_url must be an absolute http(s) URL",
            code=CalendarRejectionCode.INVALID_SOURCE_URL,
        ) from None
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise CalendarValidationError(
            "calendar source_url must be an absolute http(s) URL",
            code=CalendarRejectionCode.INVALID_SOURCE_URL,
        )
    scheduled = _parse_timestamp(event.scheduled_at)
    window_start = _parse_timestamp(event.window_start)
    window_end = _parse_timestamp(event.window_end)
    if event.time_certainty == "exact" and scheduled is None:
        raise CalendarValidationError(
            "exact calendar date requires scheduled_at",
            code=CalendarRejectionCode.EXACT_MISSING_SCHEDULED_AT,
        )
    if event.time_certainty == "window" and (window_start is None or window_end is None):
        raise CalendarValidationError(
            "window calendar date requires window_start and window_end",
            code=CalendarRejectionCode.WINDOW_MISSING_BOUNDS,
        )
    if window_start is not None and window_end is not None and window_end < window_start:
        raise CalendarValidationError(
            "calendar window_end precedes window_start",
            code=CalendarRejectionCode.WINDOW_END_BEFORE_START,
        )
    for reminder in event.reminder_windows:
        if not _REMINDER_RE.fullmatch(reminder):
            raise CalendarValidationError(
                "invalid reminder window",
                code=CalendarRejectionCode.INVALID_REMINDER_WINDOW,
            )


def _validate_input_safety(row: Mapping[str, Any]) -> None:
    if "research_only" in row and row.get("research_only") is not True:
        raise CalendarValidationError(
            "calendar row cannot disable or ambiguously encode research_only",
            code=CalendarRejectionCode.UNSAFE_RESEARCH_ONLY,
        )
    if "no_send_rehearsal" in row and row.get("no_send_rehearsal") is not True:
        raise CalendarValidationError(
            "calendar row cannot disable or ambiguously encode no_send_rehearsal",
            code=CalendarRejectionCode.UNSAFE_NO_SEND_REHEARSAL,
        )
    for field in _FORBIDDEN_TRUE_FIELDS:
        if field in row and row.get(field) is not False:
            raise CalendarValidationError(
                "calendar row cannot enable or ambiguously encode side-effect fields",
                code=CalendarRejectionCode.UNSAFE_SIDE_EFFECT_FLAG,
            )
    for field in _ZERO_SIDE_EFFECT_FIELDS:
        if field not in row:
            continue
        raw = row.get(field)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise CalendarValidationError(
                "invalid safety counter",
                code=CalendarRejectionCode.INVALID_SIDE_EFFECT_COUNTER,
            )
        try:
            value = int(raw)
        except (OverflowError, TypeError, ValueError):
            raise CalendarValidationError(
                "invalid safety counter",
                code=CalendarRejectionCode.INVALID_SIDE_EFFECT_COUNTER,
            ) from None
        if value != 0 or float(raw) != 0.0:
            raise CalendarValidationError(
                "calendar row cannot report side effects",
                code=CalendarRejectionCode.NONZERO_SIDE_EFFECT_COUNTER,
            )


def _event_kind(item: Mapping[str, Any]) -> str:
    raw = _token(item.get("event_kind") or item.get("event_type") or item.get("kind"))
    raw = _EVENT_KIND_ALIASES.get(raw, raw)
    if raw in CALENDAR_EVENT_KINDS:
        return raw
    raise CalendarValidationError(
        "unsupported event_kind",
        code=CalendarRejectionCode.UNSUPPORTED_EVENT_KIND,
    )


def _time_certainty(
    item: Mapping[str, Any],
    *,
    scheduled_at: str | None,
    window_start: str | None,
    window_end: str | None,
) -> str:
    raw = _token(item.get("time_certainty") or item.get("date_certainty") or item.get("certainty"))
    if raw in {"confirmed", "known"}:
        raw = "exact"
    if raw in {"tentative", "rumored"}:
        raw = "estimated"
    if not raw:
        raw = "window" if window_start and window_end and not scheduled_at else "exact" if scheduled_at else "unknown"
    return raw


def _affected_assets(item: Mapping[str, Any]) -> tuple[str, ...]:
    raw_values: list[Any] = []
    for key in ("affected_assets", "symbols", "assets"):
        value = item.get(key)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            raw_values.extend(value)
    symbol = item.get("symbol")
    if symbol:
        raw_values.append(symbol)
    coins = item.get("coins")
    if isinstance(coins, Iterable) and not isinstance(coins, (str, bytes, Mapping)):
        for coin in coins:
            raw_values.append(coin.get("symbol") if isinstance(coin, Mapping) else coin)
    normalized = []
    for value in raw_values:
        text = _text(value).upper().replace(" ", "_")
        if text:
            normalized.append(text)
    return tuple(dict.fromkeys(normalized))


def _reminder_windows(item: Mapping[str, Any], *, importance: str) -> tuple[str, ...]:
    raw = item.get("reminder_windows")
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, Mapping)):
        values = [_text(value) for value in raw]
    else:
        values = ["7d", "24h", "1h"] if importance in {"high", "critical"} else ["24h"]
    return tuple(dict.fromkeys(value.casefold() for value in values if value))


def _post_event_tracking_status(item: Mapping[str, Any], *, certainty: str) -> str:
    raw = _token(
        item.get("post_event_tracking_status")
        or item.get("tracking_state")
        or item.get("event_status")
        or item.get("status")
    )
    aliases = {
        "confirmed": "upcoming",
        "tentative": "needs_confirmation",
        "rumored": "needs_confirmation",
        "cancelled": "canceled",
    }
    raw = aliases.get(raw, raw)
    if not raw:
        raw = "needs_confirmation" if certainty in {"estimated", "unknown"} else "upcoming"
    return raw


def _timestamp_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise CalendarValidationError(
            "invalid calendar timestamp",
            code=CalendarRejectionCode.INVALID_TIMESTAMP,
        )
    return parsed.isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            numeric = float(value)
            seconds = numeric / 1000.0 if numeric > 10_000_000_000 else numeric
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (OverflowError, ValueError):
            return None
    try:
        return (
            parsed.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None
            else parsed.astimezone(timezone.utc)
        )
    except (OSError, OverflowError, ValueError):
        return None


def _token(value: object) -> str:
    return _text(value).casefold().replace("-", "_").replace(" ", "_")


def _first_present_nonempty(item: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key not in item:
            continue
        value = item.get(key)
        if value is not None and value != "":
            return value
    return None


def _text(value: object) -> str:
    return str(value or "").strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


__all__ = (
    "CALENDAR_EVENT_KINDS",
    "CALENDAR_IMPORTANCE_LEVELS",
    "CALENDAR_REJECTION_CODES",
    "CALENDAR_TRACKING_STATES",
    "DATE_CERTAINTY_LEVELS",
    "CalendarRejectionCode",
    "CalendarValidationError",
    "UnifiedCalendarEvent",
    "normalize_unified_calendar_event",
)
