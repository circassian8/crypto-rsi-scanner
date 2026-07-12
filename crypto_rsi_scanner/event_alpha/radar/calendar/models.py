"""Pure unified-calendar models and validation.

Calendar rows are operator research context.  They are never trading or
notification instructions and carry explicit zero-side-effect facts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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


class CalendarValidationError(ValueError):
    """Raised when a calendar row violates its data or safety contract."""


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
        item.get("scheduled_at")
        or item.get("event_start_time")
        or item.get("event_time")
        or item.get("date_event")
    )
    window_start = _timestamp_text(
        item.get("window_start") or item.get("window_start_at") or item.get("date_window_start")
    )
    window_end = _timestamp_text(
        item.get("window_end") or item.get("window_end_at") or item.get("date_window_end")
    )
    certainty = _time_certainty(item, scheduled_at=scheduled_at, window_start=window_start, window_end=window_end)
    importance = _token(item.get("importance") or "medium")
    assets = _affected_assets(item)
    source = _text(item.get("source") or item.get("provider") or "fixture")
    source_url = _text(item.get("source_url") or item.get("url") or item.get("link"))
    reminders = _reminder_windows(item, importance=importance)
    tracking = _post_event_tracking_status(item, certainty=certainty)
    observed = _timestamp_text(observed_at or item.get("observed_at"))
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
        raise CalendarValidationError("calendar_event_id is required")
    if not event.title:
        raise CalendarValidationError("calendar title is required")
    if event.event_kind not in CALENDAR_EVENT_KINDS:
        raise CalendarValidationError(f"unsupported event_kind: {event.event_kind}")
    if event.time_certainty not in DATE_CERTAINTY_LEVELS:
        raise CalendarValidationError(f"unsupported time_certainty: {event.time_certainty}")
    if event.importance not in CALENDAR_IMPORTANCE_LEVELS:
        raise CalendarValidationError(f"unsupported importance: {event.importance}")
    if event.post_event_tracking_status not in CALENDAR_TRACKING_STATES:
        raise CalendarValidationError(
            f"unsupported post_event_tracking_status: {event.post_event_tracking_status}"
        )
    if not event.source:
        raise CalendarValidationError("calendar source is required")
    parsed_url = urlsplit(event.source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise CalendarValidationError("calendar source_url must be an absolute http(s) URL")
    scheduled = _parse_timestamp(event.scheduled_at)
    window_start = _parse_timestamp(event.window_start)
    window_end = _parse_timestamp(event.window_end)
    if event.time_certainty == "exact" and scheduled is None:
        raise CalendarValidationError("exact calendar date requires scheduled_at")
    if event.time_certainty == "window" and (window_start is None or window_end is None):
        raise CalendarValidationError("window calendar date requires window_start and window_end")
    if window_start is not None and window_end is not None and window_end < window_start:
        raise CalendarValidationError("calendar window_end precedes window_start")
    for reminder in event.reminder_windows:
        if not _REMINDER_RE.fullmatch(reminder):
            raise CalendarValidationError(f"invalid reminder window: {reminder}")


def _validate_input_safety(row: Mapping[str, Any]) -> None:
    if "research_only" in row and row.get("research_only") is not True:
        raise CalendarValidationError("calendar row cannot disable or ambiguously encode research_only")
    if "no_send_rehearsal" in row and row.get("no_send_rehearsal") is not True:
        raise CalendarValidationError("calendar row cannot disable or ambiguously encode no_send_rehearsal")
    for field in _FORBIDDEN_TRUE_FIELDS:
        if field in row and row.get(field) is not False:
            raise CalendarValidationError(f"calendar row cannot enable or ambiguously encode {field}")
    for field in _ZERO_SIDE_EFFECT_FIELDS:
        if field not in row:
            continue
        raw = row.get(field)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise CalendarValidationError(f"invalid safety counter: {field}")
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise CalendarValidationError(f"invalid safety counter: {field}") from exc
        if value != 0 or float(raw) != 0.0:
            raise CalendarValidationError(f"calendar row cannot report side effects: {field}")


def _event_kind(item: Mapping[str, Any]) -> str:
    raw = _token(item.get("event_kind") or item.get("event_type") or item.get("kind"))
    raw = _EVENT_KIND_ALIASES.get(raw, raw)
    if raw in CALENDAR_EVENT_KINDS:
        return raw
    raise CalendarValidationError(f"unsupported event_kind: {raw or 'missing'}")


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
        raise CalendarValidationError(f"invalid calendar timestamp: {value}")
    return parsed.isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _token(value: object) -> str:
    return _text(value).casefold().replace("-", "_").replace(" ", "_")


def _text(value: object) -> str:
    return str(value or "").strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


__all__ = (
    "CALENDAR_EVENT_KINDS",
    "CALENDAR_IMPORTANCE_LEVELS",
    "CALENDAR_TRACKING_STATES",
    "DATE_CERTAINTY_LEVELS",
    "CalendarValidationError",
    "UnifiedCalendarEvent",
    "normalize_unified_calendar_event",
)
