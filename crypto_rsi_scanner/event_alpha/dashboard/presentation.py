"""Pure operator-facing presentation helpers for the local radar dashboard.

The dashboard's artifacts remain canonical. This module only turns their
already-validated values into concise labels, and deliberately returns one
consistent unavailable value instead of inventing missing precision.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Iterable
from zoneinfo import ZoneInfo

from .presentation_models import (
    CalendarWindowPresentation,
    ScoreBand,
    SemanticStatus,
    TimePresentation,
)


UNAVAILABLE = "Unavailable"

_UTC = timezone.utc
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN_BREAKS = re.compile(r"[_\-\s]+")

_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "btc": "BTC",
    "eth": "ETH",
    "http": "HTTP",
    "https": "HTTPS",
    "id": "ID",
    "ids": "IDs",
    "llm": "LLM",
    "oi": "OI",
    "rsi": "RSI",
    "sha": "SHA",
    "tge": "TGE",
    "url": "URL",
    "utc": "UTC",
}

_ENUM_LABELS = {
    "actionable_watch": "Actionable watch",
    "high_confidence_watch": "High-confidence watch",
    "rapid_market_anomaly": "Rapid market anomaly",
    "dashboard_watch": "Dashboard watch",
    "fade_exhaustion_review": "Fade / exhaustion review",
    "risk_watch": "Risk watch",
    "calendar_risk": "Calendar / scheduled risk",
    "diagnostic": "Diagnostic",
    "market_led": "Market-led",
    "catalyst_led": "Catalyst-led",
    "technical_led": "Technical-led",
    "derivatives_led": "Derivatives-led",
    "onchain_led": "On-chain-led",
    "fundamental_led": "Fundamental-led",
    "macro_led": "Macro-led",
    "live_no_send": "Live / real data · no-send",
    "live_provider": "Live / real data",
    "mocked_fixture": "Mocked fixture",
    "artifact_replay": "Artifact replay",
    "healthy_empty": "Healthy · no matching rows",
    "observed_healthy": "Observed healthy",
    "not_configured": "Not configured",
    "not_observed": "Not observed",
    "not_evaluated": "Not evaluated",
    "research_only": "Research only",
    "no_send": "No-send",
    "no_send_rehearsal": "No-send rehearsal",
    "percent_points": "Percentage points",
    "date_only": "Date known · time unconfirmed",
}

_REASON_LABELS = {
    "cause_unknown_market_dislocation": "The market moved, but the cause is still unknown.",
    "needs_market_confirmation": "Needs clearer price and volume confirmation.",
    "needs_fresh_market_confirmation": "Needs a fresh price and volume update.",
    "needs_strong_market_confirmation": "Needs stronger price and volume confirmation.",
    "needs_higher_quality_source": "Needs a stronger independent source.",
    "needs_identity_validation": "Needs deterministic asset identity validation.",
    "market_context_stale_capped": "Market context is stale, so visibility is capped.",
    "market_context_missing": "Market context is missing.",
    "market_context_unknown_timestamp": "The market-context timestamp is unknown.",
    "identity_low_confidence": "Asset identity confidence is too low.",
    "source_noise": "Likely source-noise artifact.",
    "ticker_collision": "Ticker or common-word collision risk.",
    "ticker_word_collision": "Ticker or common-word collision risk.",
    "diagnostic_only": "Diagnostic or control row only.",
    "quality_gate_blocked": "The quality gate blocked promotion.",
    "spread_unavailable": "Spread evidence is unavailable.",
    "spread_unverified": "Spread has not been independently verified.",
    "freshness_unknown": "Data freshness is unknown.",
}


_UNAVAILABLE_TIME = TimePresentation(
    available=False,
    local_label=UNAVAILABLE,
    relative_label=UNAVAILABLE,
    utc_label=UNAVAILABLE,
    iso_utc="",
    timezone_label=UNAVAILABLE,
)


def present_time(
    value: object,
    *,
    now: datetime | str | None = None,
    tz: tzinfo | str | None = None,
) -> TimePresentation:
    """Present one timestamp with deterministic clock and timezone hooks."""

    instant = _parse_timestamp(value)
    if instant is None:
        return _UNAVAILABLE_TIME
    local_tz = _resolve_timezone(tz)
    current = _resolve_now(now)
    local = instant.astimezone(local_tz)
    current_local = current.astimezone(local_tz)
    return TimePresentation(
        available=True,
        local_label=_local_datetime_label(local, current_local),
        relative_label=_relative_label(instant - current),
        utc_label=_exact_utc_label(instant),
        iso_utc=_iso_utc(instant),
        timezone_label=_timezone_name(local),
    )


def format_local_time(
    value: object,
    *,
    now: datetime | str | None = None,
    tz: tzinfo | str | None = None,
) -> str:
    return present_time(value, now=now, tz=tz).local_label


def format_relative_time(value: object, *, now: datetime | str | None = None) -> str:
    instant = _parse_timestamp(value)
    if instant is None:
        return UNAVAILABLE
    return _relative_label(instant - _resolve_now(now))


def format_exact_utc(value: object) -> str:
    instant = _parse_timestamp(value)
    return _exact_utc_label(instant) if instant is not None else UNAVAILABLE


def present_calendar_window(
    *,
    scheduled_at: object = None,
    window_start: object = None,
    window_end: object = None,
    time_certainty: object = None,
    now: datetime | str | None = None,
    tz: tzinfo | str | None = None,
) -> CalendarWindowPresentation:
    """Present scheduled timing while preserving approximate/date-only status."""

    start = _parse_timestamp(window_start)
    end = _parse_timestamp(window_end)
    scheduled = _parse_timestamp(scheduled_at)
    token = _normal_token(time_certainty)
    source_is_date_only = any(
        _is_date_only(value) for value in (scheduled_at, window_start, window_end)
    )
    date_only = token in {"date_only", "day_only", "date_known"} or (
        not token and source_is_date_only
    )
    approximate = token in {"approximate", "estimated", "inferred", "tentative"}
    unconfirmed = token in {"unknown", "unconfirmed", "tbd", "not_confirmed"}

    first = start or scheduled or end
    if first is None:
        return CalendarWindowPresentation(
            available=False,
            label=UNAVAILABLE,
            certainty_label=_certainty_label(token),
            relative_label=UNAVAILABLE,
            utc_label=UNAVAILABLE,
        )

    local_tz = _resolve_timezone(tz)
    current = _resolve_now(now)
    current_local = current.astimezone(local_tz)
    if date_only:
        first_local = first.astimezone(local_tz)
        last_local = (end or start or scheduled or first).astimezone(local_tz)
        if first_local.date() == last_local.date():
            label = _calendar_date(first_local.date(), current_local.date())
        else:
            label = (
                f"{_calendar_date(first_local.date(), current_local.date())}"
                f" – {_calendar_date(last_local.date(), current_local.date())}"
            )
        return CalendarWindowPresentation(
            available=True,
            label=f"{label} · time unconfirmed",
            certainty_label="Date known · time unconfirmed",
            relative_label=UNAVAILABLE,
            utc_label=UNAVAILABLE,
        )

    first_local = first.astimezone(local_tz)
    last = end if end is not None and end >= first else None
    if last is not None and last != first:
        last_local = last.astimezone(local_tz)
        label = _calendar_range_label(first_local, last_local, current_local)
        label = f"Window: {label}"
        utc_label = f"{_exact_utc_label(first)} – {_exact_utc_label(last)}"
    else:
        label = _local_datetime_label(first_local, current_local)
        utc_label = _exact_utc_label(first)

    if approximate:
        label = f"Around {label.removeprefix('Window: ')} · approximate"
    elif unconfirmed:
        label = f"{label} · time unconfirmed"
    elif token not in {"exact", "confirmed", "scheduled", "window", "range"}:
        label = f"{label} · certainty not recorded"

    return CalendarWindowPresentation(
        available=True,
        label=label,
        certainty_label=_certainty_label(token),
        relative_label=_relative_label(first - current),
        utc_label=utc_label,
    )


def format_calendar_window(**kwargs: object) -> str:
    """Return only the primary label from present_calendar_window."""

    return present_calendar_window(**kwargs).label


def humanize_identifier(value: object, *, fallback: str = UNAVAILABLE) -> str:
    """Turn a machine identifier into stable sentence-case operator text."""

    if value is None or isinstance(value, bool):
        return fallback
    raw = str(value).strip()
    if not raw:
        return fallback
    token = _normal_token(raw)
    if token in _ENUM_LABELS:
        return _ENUM_LABELS[token]
    separated = _CAMEL_BOUNDARY.sub(" ", raw)
    words = [word for word in _TOKEN_BREAKS.split(separated) if word]
    if not words:
        return fallback
    rendered = [_ACRONYMS.get(word.casefold(), word.casefold()) for word in words]
    if rendered[0] not in _ACRONYMS.values():
        rendered[0] = rendered[0].capitalize()
    return " ".join(rendered)


def humanize_enum(value: object, *, fallback: str = UNAVAILABLE) -> str:
    return humanize_identifier(value, fallback=fallback)


def humanize_reason(value: object, *, fallback: str = UNAVAILABLE) -> str:
    if value is None:
        return fallback
    raw = str(value).strip()
    if not raw:
        return fallback
    token = _normal_token(raw)
    if token in _REASON_LABELS:
        return _REASON_LABELS[token]
    label = humanize_identifier(raw, fallback=fallback)
    return label if label.endswith((".", "!", "?")) else f"{label}."


def humanize_reasons(
    values: Iterable[object] | object,
    *,
    limit: int = 5,
    fallback: str = UNAVAILABLE,
) -> str:
    if isinstance(values, (str, bytes)) or values is None:
        materialized = [values]
    else:
        try:
            materialized = list(values)  # type: ignore[arg-type]
        except TypeError:
            materialized = [values]
    translated = [humanize_reason(value, fallback="") for value in materialized]
    translated = list(dict.fromkeys(value for value in translated if value))
    if not translated:
        return fallback
    bounded = max(1, int(limit))
    visible = translated[:bounded]
    remainder = len(translated) - len(visible)
    suffix = f" +{remainder} more" if remainder else ""
    return " ".join(visible) + suffix


def format_number(
    value: object,
    *,
    decimals: int = 1,
    compact: bool = False,
    signed: bool = False,
) -> str:
    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    precision = _validated_decimals(decimals)
    if compact:
        return _compact_number(number, decimals=precision, signed=signed)
    prefix = "+" if signed and number > 0 else ""
    return prefix + _trimmed(f"{number:,.{precision}f}")


def format_compact_number(
    value: object,
    *,
    decimals: int = 1,
    signed: bool = False,
) -> str:
    return format_number(value, decimals=decimals, compact=True, signed=signed)


def format_currency(
    value: object,
    *,
    currency: str = "$",
    decimals: int = 1,
    compact: bool = True,
    signed: bool = False,
) -> str:
    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    magnitude = format_number(abs(number), decimals=decimals, compact=compact)
    unit = str(currency or "$").strip() or "$"
    amount = f"{unit}{magnitude}" if unit in {"$", "€", "£", "¥"} else f"{unit} {magnitude}"
    sign = "-" if number < 0 else "+" if signed and number > 0 else ""
    return sign + amount


def format_percent(
    value: object,
    *,
    unit: str = "percent_points",
    decimals: int = 1,
    signed: bool = False,
) -> str:
    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    normalized_unit = _normal_token(unit)
    if normalized_unit in {"fraction", "ratio"}:
        number *= 100.0
    elif normalized_unit not in {"percent", "percentage", "percent_points", "percentage_points"}:
        raise ValueError(f"unsupported percent unit: {unit!r}")
    return f"{format_number(number, decimals=decimals, signed=signed)}%"


def format_duration(value: object) -> str:
    seconds_value = _finite_number(value)
    if seconds_value is None or seconds_value < 0:
        return UNAVAILABLE
    seconds = int(round(seconds_value))
    if seconds < 60:
        return f"{seconds} sec"
    units = ((86400, "day"), (3600, "hr"), (60, "min"))
    parts: list[str] = []
    remaining = seconds
    for size, label in units:
        count, remaining = divmod(remaining, size)
        if count:
            suffix = "s" if label == "day" and count != 1 else ""
            parts.append(f"{count} {label}{suffix}")
        if len(parts) == 2:
            break
    return " ".join(parts) or "0 min"


def format_score(value: object) -> str:
    number = _bounded_score(value)
    if number is None:
        return UNAVAILABLE
    return _trimmed(f"{number:.1f}")


def score_band(value: object, *, dimension: str = "quality") -> ScoreBand:
    number = _bounded_score(value)
    if number is None:
        return ScoreBand("unknown", UNAVAILABLE, "muted")
    normalized = _normal_token(dimension)
    if normalized in {"risk", "chase_risk", "manipulation_risk"}:
        if number < 35:
            return ScoreBand("low", "Low", "positive")
        if number < 65:
            return ScoreBand("moderate", "Moderate", "warning")
        return ScoreBand("high", "High", "danger")
    if normalized == "urgency":
        if number < 35:
            return ScoreBand("low", "Low", "muted")
        if number < 70:
            return ScoreBand("moderate", "Moderate", "info")
        return ScoreBand("high", "High", "warning")
    if number < 40:
        return ScoreBand("low", "Low", "danger")
    if number < 70:
        return ScoreBand("moderate", "Moderate", "warning")
    return ScoreBand("high", "High", "positive")


def semantic_status(value: object) -> SemanticStatus:
    """Map operator state into a label and a non-domain-specific visual tone."""

    if isinstance(value, bool):
        return SemanticStatus(
            str(value).lower(),
            "Yes" if value else "No",
            "positive" if value else "muted",
        )
    token = _normal_token(value)
    if not token:
        return SemanticStatus("unknown", UNAVAILABLE, "muted")
    exact_tones = {
        "authoritative": "positive",
        "current": "positive",
        "healthy": "positive",
        "healthy_empty": "positive",
        "observed_healthy": "positive",
        "complete": "positive",
        "completed": "positive",
        "confirmed": "positive",
        "fresh": "positive",
        "verified": "positive",
        "valid": "positive",
        "passed": "positive",
        "success": "positive",
        "actionable": "positive",
        "available": "positive",
        "live": "info",
        "live_no_send": "info",
        "dashboard_watch": "info",
        "research_only": "info",
        "no_send": "info",
        "pending": "warning",
        "warming": "warning",
        "partial": "warning",
        "approximate": "warning",
        "unconfirmed": "warning",
        "backoff": "warning",
        "rate_limited": "warning",
        "degraded": "warning",
        "unknown": "muted",
        "not_configured": "muted",
        "not_observed": "muted",
        "not_evaluated": "muted",
        "unavailable": "muted",
        "blocked": "danger",
        "failed": "danger",
        "error": "danger",
        "untrusted": "danger",
        "stale": "danger",
        "expired": "danger",
        "rejected": "danger",
        "invalid": "danger",
    }
    tone = exact_tones.get(token)
    if tone is None:
        if any(
            part in token
            for part in (
                "blocked",
                "failed",
                "error",
                "untrusted",
                "stale",
                "expired",
                "rejected",
                "invalid",
            )
        ):
            tone = "danger"
        elif any(
            part in token
            for part in ("warning", "pending", "warming", "backoff", "degraded", "risk")
        ):
            tone = "warning"
        elif any(
            part in token
            for part in ("healthy", "complete", "confirmed", "fresh", "verified", "success", "valid")
        ):
            tone = "positive"
        elif "live" in token or "watch" in token:
            tone = "info"
        else:
            tone = "neutral"
    return SemanticStatus(token, humanize_enum(token), tone)


def status_tone(value: object) -> str:
    return semantic_status(value).tone


def _parse_timestamp(value: object) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=_UTC)
    elif isinstance(value, (int, float)):
        number = _finite_number(value)
        if number is None:
            return None
        try:
            parsed = datetime.fromtimestamp(number, tz=_UTC)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(normalized)
            except ValueError:
                return None
            parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=_UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_UTC)
    return parsed.astimezone(_UTC)


def _resolve_timezone(value: tzinfo | str | None) -> tzinfo:
    if value is None:
        return datetime.now().astimezone().tzinfo or _UTC
    if isinstance(value, str):
        return ZoneInfo(value)
    return value


def _resolve_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(tz=_UTC)
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise ValueError(f"invalid presentation clock: {value!r}")
    return parsed


def _relative_label(delta: timedelta) -> str:
    seconds_float = delta.total_seconds()
    future = seconds_float > 0
    seconds = int(abs(seconds_float))
    if seconds < 5:
        return "just now"
    units = (
        (365 * 86400, "year"),
        (30 * 86400, "month"),
        (7 * 86400, "week"),
        (86400, "day"),
        (3600, "hr"),
        (60, "min"),
        (1, "sec"),
    )
    for size, label in units:
        if seconds >= size:
            count = seconds // size
            suffix = "s" if label in {"year", "month", "week", "day"} and count != 1 else ""
            text = f"{count} {label}{suffix}"
            return f"in {text}" if future else f"{text} ago"
    return "just now"


def _local_datetime_label(value: datetime, now: datetime) -> str:
    if value.date() == now.date():
        date_label = "Today"
    elif value.date() == now.date() + timedelta(days=1):
        date_label = "Tomorrow"
    elif value.date() == now.date() - timedelta(days=1):
        date_label = "Yesterday"
    else:
        date_label = _calendar_date(value.date(), now.date())
    return f"{date_label}, {value:%H:%M} {_timezone_name(value)}"


def _calendar_range_label(start: datetime, end: datetime, now: datetime) -> str:
    if start.date() == end.date() and _timezone_name(start) == _timezone_name(end):
        return (
            f"{_calendar_date(start.date(), now.date())}, "
            f"{start:%H:%M}–{end:%H:%M} {_timezone_name(start)}"
        )
    return f"{_local_datetime_label(start, now)} – {_local_datetime_label(end, now)}"


def _calendar_date(value: date, current: date) -> str:
    if value.year == current.year:
        return f"{value:%b} {value.day}"
    return f"{value:%b} {value.day}, {value.year}"


def _timezone_name(value: datetime) -> str:
    name = value.tzname()
    if name:
        return name
    offset = value.utcoffset()
    if offset is None:
        return "local"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "−"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _exact_utc_label(value: datetime) -> str:
    utc = value.astimezone(_UTC)
    fractional = f".{utc.microsecond:06d}" if utc.microsecond else ""
    return f"{utc:%Y-%m-%d %H:%M:%S}{fractional} UTC"


def _iso_utc(value: datetime) -> str:
    timespec = "microseconds" if value.microsecond else "seconds"
    return value.astimezone(_UTC).isoformat(timespec=timespec).replace("+00:00", "Z")


def _certainty_label(token: str) -> str:
    labels = {
        "exact": "Confirmed time",
        "confirmed": "Confirmed time",
        "scheduled": "Scheduled time",
        "window": "Scheduled window",
        "range": "Scheduled window",
        "date_only": "Date known · time unconfirmed",
        "day_only": "Date known · time unconfirmed",
        "date_known": "Date known · time unconfirmed",
        "approximate": "Approximate time",
        "estimated": "Approximate time",
        "inferred": "Inferred time",
        "tentative": "Tentative time",
        "unknown": "Timing unconfirmed",
        "unconfirmed": "Timing unconfirmed",
        "tbd": "Timing unconfirmed",
        "not_confirmed": "Timing unconfirmed",
    }
    return labels.get(token, "Timing certainty not recorded")


def _is_date_only(value: object) -> bool:
    if isinstance(value, date) and not isinstance(value, datetime):
        return True
    return isinstance(value, str) and bool(_DATE_ONLY.fullmatch(value.strip()))


def _normal_token(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bounded_score(value: object) -> float | None:
    number = _finite_number(value)
    if number is None or not 0 <= number <= 100:
        return None
    return number


def _validated_decimals(value: int) -> int:
    try:
        decimals = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("decimals must be an integer") from exc
    if not 0 <= decimals <= 8:
        raise ValueError("decimals must be between 0 and 8")
    return decimals


def _compact_number(number: float, *, decimals: int, signed: bool) -> str:
    absolute = abs(number)
    units = ((1e15, "Q"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))
    divisor, suffix = next(
        ((size, label) for size, label in units if absolute >= size),
        (1.0, ""),
    )
    scaled = number / divisor
    prefix = "+" if signed and scaled > 0 else ""
    return prefix + _trimmed(f"{scaled:.{decimals}f}") + suffix


def _trimmed(value: str) -> str:
    if "." not in value:
        return value
    return value.rstrip("0").rstrip(".")


__all__ = (
    "CalendarWindowPresentation",
    "ScoreBand",
    "SemanticStatus",
    "TimePresentation",
    "UNAVAILABLE",
    "format_calendar_window",
    "format_compact_number",
    "format_currency",
    "format_duration",
    "format_exact_utc",
    "format_local_time",
    "format_number",
    "format_percent",
    "format_relative_time",
    "format_score",
    "humanize_enum",
    "humanize_identifier",
    "humanize_reason",
    "humanize_reasons",
    "present_calendar_window",
    "present_time",
    "score_band",
    "semantic_status",
    "status_tone",
)
