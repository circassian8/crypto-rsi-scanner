"""Pure parsers for the official U.S. macro calendar source pack.

The parsers in this module never perform network or filesystem I/O.  They
translate already-captured Federal Reserve, BLS, and BEA schedule responses
into the existing unified-calendar input shape.  Calendar rows are research
context only: they contain no trade direction, execution instruction, or
consensus values.
"""

from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import CalendarValidationError, normalize_unified_calendar_event


FEDERAL_RESERVE_FOMC_URL = (
    "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
)
BLS_RELEASE_CALENDAR_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_CPI_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
BLS_EMPLOYMENT_SCHEDULE_URL = (
    "https://www.bls.gov/schedule/news_release/empsit.htm"
)
BEA_RELEASE_DATES_URL = "https://apps.bea.gov/API/signup/release_dates.json"
BEA_RELEASE_SCHEDULE_URL = "https://www.bea.gov/news/schedule/"

OFFICIAL_MACRO_SOURCE_NAMES = ("bls", "federal_reserve", "bea")

_NEW_YORK = ZoneInfo("America/New_York")
_MONTHS = {
    name.casefold(): number
    for number, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}
_MONTHS.update({name[:3].casefold(): value for name, value in tuple(_MONTHS.items())})
_FOMC_HEADING_RE = re.compile(r"\b(20\d{2})\s+FOMC\s+Meetings\b", re.I)
_FOMC_DATES_RE = re.compile(r"^(\d{1,2})(?:\s*-\s*(\d{1,2}))?(\*)?$")
_ICS_DATETIME_RE = re.compile(r"^(\d{8})T(\d{4}(?:\d{2})?)(Z)?$")
_ICS_DATE_RE = re.compile(r"^\d{8}$")
_BEA_SERIES = {
    "Gross Domestic Product": ("gdp", "macro_release"),
    "Personal Income and Outlays": ("personal-income-and-outlays", "inflation"),
}


class _OfficialMacroParseError(ValueError):
    """Closed, payload-free parse failure for one official source."""

    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(self.code)


OfficialMacroParseError = _OfficialMacroParseError


@dataclass(frozen=True)
class _OfficialMacroParsedSource:
    """Deterministic rows and counts produced from one captured response."""

    source: str
    rows: tuple[dict[str, Any], ...]
    source_rows_seen: int
    rejected_rows: int = 0

    def __post_init__(self) -> None:
        if self.source not in OFFICIAL_MACRO_SOURCE_NAMES:
            raise ValueError("unsupported official macro source")
        if (
            self.source_rows_seen < 0
            or self.source_rows_seen < len(self.rows)
            or self.rejected_rows < 0
        ):
            raise ValueError("official macro source counters are invalid")


OfficialMacroParsedSource = _OfficialMacroParsedSource


def parse_federal_reserve_fomc_html(
    payload: bytes | str,
    *,
    acquired_at: datetime | str,
) -> OfficialMacroParsedSource:
    """Parse official FOMC meeting dates as bounded New York date windows.

    The Federal Reserve calendar does not state a policy-decision time and says
    future meeting dates are tentative.  Consequently this parser never emits
    an exact ``scheduled_at`` value for an FOMC row.
    """

    text = _decoded_text(payload, source="federal_reserve")
    parser = _FomcHTMLParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise OfficialMacroParseError("federal_reserve_html_invalid") from exc
    acquired = _aware_utc(acquired_at)
    rows: list[dict[str, Any]] = []
    rejected = 0
    for item in parser.meetings:
        try:
            start_day, end_day, projections = _fomc_date_bounds(
                year=item.year,
                month_text=item.month,
                date_text=item.dates,
            )
        except OfficialMacroParseError:
            rejected += 1
            continue
        start_local = datetime.combine(start_day, time.min, tzinfo=_NEW_YORK)
        end_local = datetime.combine(end_day, time(23, 59, 59), tzinfo=_NEW_YORK)
        end_utc = end_local.astimezone(timezone.utc)
        title = "Federal Open Market Committee meeting"
        if projections:
            title += " with Summary of Economic Projections"
        row = _event_row(
            event_id=f"macro:fed:fomc:{start_day.isoformat()}",
            title=title,
            event_kind="central_bank",
            acquired_at=acquired,
            source="Federal Reserve Board",
            source_url=FEDERAL_RESERVE_FOMC_URL,
            importance="critical",
            window_start=start_local.astimezone(timezone.utc).isoformat(),
            window_end=end_utc.isoformat(),
            time_certainty="window",
            tracking_status=(
                "completed" if end_utc < acquired else "needs_confirmation"
            ),
            impact_window_before="24h",
            impact_window_after="8h",
            reminders=("7d", "24h", "1h"),
            source_timezone="America/New_York",
        )
        rows.append(row)
    if not rows and parser.year_heading_count == 0:
        raise OfficialMacroParseError("federal_reserve_fomc_rows_missing")
    return OfficialMacroParsedSource(
        source="federal_reserve",
        rows=_dedupe_rows(rows, source="federal_reserve"),
        source_rows_seen=len(parser.meetings),
        rejected_rows=rejected,
    )


def parse_bls_release_calendar_ics(
    payload: bytes | str,
    *,
    acquired_at: datetime | str,
) -> OfficialMacroParsedSource:
    """Parse only CPI and Employment Situation events from the BLS ICS feed."""

    text = _decoded_text(payload, source="bls")
    calendar_properties, events = _parse_ics(text)
    calendar_timezone = _calendar_timezone(calendar_properties)
    acquired = _aware_utc(acquired_at)
    rows: list[dict[str, Any]] = []
    uid_timings: dict[str, str] = {}
    rejected = 0
    for event in events:
        try:
            summary = _one_ics_value(event, "SUMMARY", required=True)
            series = _bls_series(summary.value)
            if series is None:
                continue
            status_value = _one_ics_value(event, "STATUS", required=False)
            status = (
                _decode_ics_text(status_value.value).strip().casefold()
                if status_value is not None
                else "confirmed"
            )
            if status in {"cancelled", "canceled"}:
                continue
            dtstart = _one_ics_value(event, "DTSTART", required=True)
            timing = _ics_timing(
                dtstart.value,
                dtstart.params,
                default_timezone=calendar_timezone,
            )
            uid_value = _one_ics_value(event, "UID", required=False)
            uid = (
                _decode_ics_text(uid_value.value).strip()
                if uid_value is not None
                else f"{series}|{timing.identity}"
            )
            if not uid or len(uid) > 512:
                raise OfficialMacroParseError("bls_uid_invalid")
            previous_timing = uid_timings.get(uid)
            if previous_timing is not None and previous_timing != timing.identity:
                raise OfficialMacroParseError("bls_uid_timing_conflict")
            uid_timings[uid] = timing.identity
            event_identity = hashlib.sha256(
                f"{series}|{timing.identity}".encode("utf-8")
            ).hexdigest()[:16]
            event_id = f"macro:bls:{series}:{event_identity}"
            is_tentative = status == "tentative"
            schedule_url = (
                BLS_CPI_SCHEDULE_URL
                if series == "cpi"
                else BLS_EMPLOYMENT_SCHEDULE_URL
            )
            row = _event_row(
                event_id=event_id,
                title=(
                    "Consumer Price Index release"
                    if series == "cpi"
                    else "Employment Situation release"
                ),
                event_kind="inflation" if series == "cpi" else "employment",
                acquired_at=acquired,
                source="US Bureau of Labor Statistics",
                source_url=schedule_url,
                importance="high",
                scheduled_at=timing.scheduled_at,
                window_start=timing.window_start,
                window_end=timing.window_end,
                time_certainty=(
                    "estimated"
                    if is_tentative
                    else "window" if timing.window_start else "exact"
                ),
                tracking_status=(
                    "needs_confirmation"
                    if is_tentative
                    else "completed" if timing.end < acquired else "upcoming"
                ),
                impact_window_before="12h",
                impact_window_after="6h",
                reminders=("24h", "1h"),
                source_timezone=timing.source_timezone,
            )
            rows.append(row)
        except OfficialMacroParseError as exc:
            if exc.code == "bls_uid_timing_conflict":
                raise
            rejected += 1
    if not rows and rejected:
        raise OfficialMacroParseError("bls_calendar_rows_invalid")
    return OfficialMacroParsedSource(
        source="bls",
        rows=_dedupe_rows(rows, source="bls"),
        source_rows_seen=len(events),
        rejected_rows=rejected,
    )


def parse_bea_release_dates_json(
    payload: bytes | str,
    *,
    acquired_at: datetime | str,
) -> OfficialMacroParsedSource:
    """Parse GDP and Personal Income and Outlays dates from BEA's JSON feed."""

    text = _decoded_text(payload, source="bea")
    try:
        parsed = json.loads(text, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, ValueError) as exc:
        raise OfficialMacroParseError("bea_json_invalid") from exc
    if not isinstance(parsed, Mapping):
        raise OfficialMacroParseError("bea_json_container_invalid")
    acquired = _aware_utc(acquired_at)
    rows: list[dict[str, Any]] = []
    source_rows_seen = 0
    for official_name, (slug, event_kind) in _BEA_SERIES.items():
        value = parsed.get(official_name)
        if not isinstance(value, Mapping):
            raise OfficialMacroParseError(f"bea_required_series_missing:{slug}")
        raw_dates = value.get("release_dates")
        if not isinstance(raw_dates, Sequence) or isinstance(raw_dates, (str, bytes)):
            raise OfficialMacroParseError(f"bea_release_dates_invalid:{slug}")
        source_rows_seen += len(raw_dates)
        for raw in raw_dates:
            source_scheduled = _aware_datetime(raw)
            scheduled = source_scheduled.astimezone(timezone.utc)
            source_timezone = str(source_scheduled.tzinfo)
            identity = scheduled.strftime("%Y%m%dT%H%M%SZ")
            rows.append(
                _event_row(
                    event_id=f"macro:bea:{slug}:{identity}",
                    title=(
                        "Gross Domestic Product release"
                        if slug == "gdp"
                        else "Personal Income and Outlays release (includes PCE price index)"
                    ),
                    event_kind=event_kind,
                    acquired_at=acquired,
                    source="US Bureau of Economic Analysis",
                    source_url=BEA_RELEASE_SCHEDULE_URL,
                    importance="high",
                    scheduled_at=scheduled.isoformat(),
                    time_certainty="exact",
                    tracking_status=(
                        "completed" if scheduled < acquired else "upcoming"
                    ),
                    impact_window_before="12h",
                    impact_window_after="6h",
                    reminders=("24h", "1h"),
                    source_timezone=source_timezone,
                )
            )
    return OfficialMacroParsedSource(
        source="bea",
        rows=_dedupe_rows(rows, source="bea"),
        source_rows_seen=source_rows_seen,
    )


def merge_official_macro_sources(
    sources: Iterable[OfficialMacroParsedSource],
    *,
    require_all: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Merge observed official sources with strict IDs and optional full coverage."""

    by_source: dict[str, OfficialMacroParsedSource] = {}
    for source in sources:
        if source.source in by_source:
            raise OfficialMacroParseError(f"official_source_duplicate:{source.source}")
        by_source[source.source] = source
    missing = set(OFFICIAL_MACRO_SOURCE_NAMES).difference(by_source)
    if require_all and missing:
        raise OfficialMacroParseError(
            "official_source_missing:" + ",".join(sorted(missing))
        )
    rows = [
        row
        for name in OFFICIAL_MACRO_SOURCE_NAMES
        if name in by_source
        for row in by_source[name].rows
    ]
    return _dedupe_rows(rows, source="official_macro_pack")


@dataclass(frozen=True)
class _FomcMeeting:
    year: int
    month: str
    dates: str


class _FomcHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meetings: list[_FomcMeeting] = []
        self._depth = 0
        self._year: int | None = None
        self._row_depth: int | None = None
        self._row_year: int | None = None
        self._month_parts: list[str] = []
        self._date_parts: list[str] = []
        self._capture: str | None = None
        self._capture_depth: int | None = None
        self.year_heading_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "div":
            return
        self._depth += 1
        classes = set(dict(attrs).get("class", "").split())
        if self._row_depth is None and "fomc-meeting" in classes:
            self._row_depth = self._depth
            self._row_year = self._year
            self._month_parts = []
            self._date_parts = []
        if self._row_depth is not None:
            if "fomc-meeting__month" in classes:
                self._capture, self._capture_depth = "month", self._depth
            elif "fomc-meeting__date" in classes:
                self._capture, self._capture_depth = "date", self._depth

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "div":
            return
        if self._capture_depth == self._depth:
            self._capture = None
            self._capture_depth = None
        if self._row_depth == self._depth:
            month = " ".join("".join(self._month_parts).split())
            dates = " ".join("".join(self._date_parts).split())
            if self._row_year is not None and month and dates:
                self.meetings.append(_FomcMeeting(self._row_year, month, dates))
            self._row_depth = None
            self._row_year = None
            self._month_parts = []
            self._date_parts = []
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        heading = _FOMC_HEADING_RE.search(data)
        if heading:
            self._year = int(heading.group(1))
            self.year_heading_count += 1
        if self._capture == "month":
            self._month_parts.append(data)
        elif self._capture == "date":
            self._date_parts.append(data)


@dataclass(frozen=True)
class _IcsProperty:
    value: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class _IcsTiming:
    scheduled_at: str | None
    window_start: str | None
    window_end: str | None
    start: datetime
    end: datetime
    identity: str
    source_timezone: str


def _parse_ics(
    text: str,
) -> tuple[dict[str, list[_IcsProperty]], tuple[dict[str, list[_IcsProperty]], ...]]:
    unfolded = re.sub(r"(?:\r\n|\n|\r)[ \t]", "", text)
    lines = unfolded.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    calendar: dict[str, list[_IcsProperty]] = {}
    events: list[dict[str, list[_IcsProperty]]] = []
    current: dict[str, list[_IcsProperty]] | None = None
    saw_calendar = False
    for line in lines:
        if not line:
            continue
        if ":" not in line:
            raise OfficialMacroParseError("bls_ics_line_invalid")
        raw_name, value = line.split(":", 1)
        parts = raw_name.split(";")
        name = parts[0].strip().upper()
        params: dict[str, str] = {}
        for raw_param in parts[1:]:
            if "=" not in raw_param:
                raise OfficialMacroParseError("bls_ics_parameter_invalid")
            key, parameter_value = raw_param.split("=", 1)
            params[key.strip().upper()] = parameter_value.strip().strip('"')
        if name == "BEGIN" and value.strip().upper() == "VCALENDAR":
            saw_calendar = True
            continue
        if name == "END" and value.strip().upper() == "VCALENDAR":
            continue
        if name == "BEGIN" and value.strip().upper() == "VEVENT":
            if current is not None:
                raise OfficialMacroParseError("bls_ics_nested_event")
            current = {}
            continue
        if name == "END" and value.strip().upper() == "VEVENT":
            if current is None:
                raise OfficialMacroParseError("bls_ics_event_end_invalid")
            events.append(current)
            current = None
            continue
        target = current if current is not None else calendar
        target.setdefault(name, []).append(_IcsProperty(value=value, params=params))
    if not saw_calendar or current is not None:
        raise OfficialMacroParseError("bls_ics_container_invalid")
    return calendar, tuple(events)


def _one_ics_value(
    event: Mapping[str, Sequence[_IcsProperty]],
    name: str,
    *,
    required: bool,
) -> _IcsProperty | None:
    values = event.get(name) or ()
    if len(values) > 1:
        raise OfficialMacroParseError(f"bls_ics_{name.casefold()}_duplicate")
    if not values:
        if required:
            raise OfficialMacroParseError(f"bls_ics_{name.casefold()}_missing")
        return None
    return values[0]


def _calendar_timezone(properties: Mapping[str, Sequence[_IcsProperty]]) -> str:
    values = properties.get("X-WR-TIMEZONE") or ()
    if not values:
        return "America/New_York"
    if len(values) != 1:
        raise OfficialMacroParseError("bls_ics_calendar_timezone_duplicate")
    return _canonical_timezone(values[0].value)


def _ics_timing(
    raw: str,
    params: Mapping[str, str],
    *,
    default_timezone: str,
) -> _IcsTiming:
    value = raw.strip()
    timezone_name = _canonical_timezone(params.get("TZID") or default_timezone)
    if _ICS_DATE_RE.fullmatch(value):
        zone = _zone(timezone_name)
        parsed_date = datetime.strptime(value, "%Y%m%d").date()
        start = datetime.combine(parsed_date, time.min, tzinfo=zone).astimezone(timezone.utc)
        end = datetime.combine(parsed_date, time(23, 59, 59), tzinfo=zone).astimezone(timezone.utc)
        return _IcsTiming(
            scheduled_at=None,
            window_start=start.isoformat(),
            window_end=end.isoformat(),
            start=start,
            end=end,
            identity=parsed_date.isoformat(),
            source_timezone=timezone_name,
        )
    matched = _ICS_DATETIME_RE.fullmatch(value)
    if not matched:
        raise OfficialMacroParseError("bls_ics_datetime_invalid")
    date_part, time_part, utc_marker = matched.groups()
    fmt = "%Y%m%d%H%M%S" if len(time_part) == 6 else "%Y%m%d%H%M"
    parsed = datetime.strptime(date_part + time_part, fmt)
    if utc_marker:
        source_timezone = "UTC"
        source_zone = timezone.utc
    else:
        source_timezone = timezone_name
        source_zone = _zone(timezone_name)
    aware = parsed.replace(tzinfo=source_zone).astimezone(timezone.utc)
    return _IcsTiming(
        scheduled_at=aware.isoformat(),
        window_start=None,
        window_end=None,
        start=aware,
        end=aware,
        identity=aware.isoformat(),
        source_timezone=source_timezone,
    )


def _bls_series(summary: str) -> str | None:
    normalized = " ".join(_decode_ics_text(summary).split()).casefold()
    if normalized == "consumer price index":
        return "cpi"
    if normalized in {"employment situation", "the employment situation"}:
        return "employment"
    return None


def _decode_ics_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _canonical_timezone(value: str) -> str:
    text = str(value or "").strip()
    aliases = {
        "America/Washington_DC": "America/New_York",
        "US/Eastern": "America/New_York",
    }
    return aliases.get(text, text or "America/New_York")


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise OfficialMacroParseError("bls_ics_timezone_invalid") from exc


def _fomc_date_bounds(
    *, year: int, month_text: str, date_text: str
) -> tuple[date, date, bool]:
    cleaned_dates = " ".join(date_text.replace("–", "-").replace("—", "-").split())
    if "notation vote" in cleaned_dates.casefold():
        raise OfficialMacroParseError("federal_reserve_notation_vote_excluded")
    matched = _FOMC_DATES_RE.fullmatch(cleaned_dates)
    if not matched:
        raise OfficialMacroParseError("federal_reserve_date_invalid")
    start_day = int(matched.group(1))
    end_day = int(matched.group(2) or start_day)
    projections = bool(matched.group(3))
    month_parts = [part.strip().casefold() for part in month_text.split("/")]
    if not month_parts or len(month_parts) > 2:
        raise OfficialMacroParseError("federal_reserve_month_invalid")
    try:
        start_month = _MONTHS[month_parts[0]]
        end_month = _MONTHS[month_parts[-1]]
    except KeyError as exc:
        raise OfficialMacroParseError("federal_reserve_month_invalid") from exc
    end_year = year
    if len(month_parts) == 1 and end_day < start_day:
        end_month = 1 if start_month == 12 else start_month + 1
        end_year = year + 1 if start_month == 12 else year
    elif len(month_parts) == 2 and end_month < start_month:
        end_year += 1
    if start_day > monthrange(year, start_month)[1] or end_day > monthrange(end_year, end_month)[1]:
        raise OfficialMacroParseError("federal_reserve_date_invalid")
    return date(year, start_month, start_day), date(end_year, end_month, end_day), projections


def _event_row(
    *,
    event_id: str,
    title: str,
    event_kind: str,
    acquired_at: datetime,
    source: str,
    source_url: str,
    importance: str,
    scheduled_at: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    time_certainty: str,
    tracking_status: str,
    impact_window_before: str,
    impact_window_after: str,
    reminders: Sequence[str],
    source_timezone: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "calendar_event_id": event_id,
        "title": title,
        "event_kind": event_kind,
        "scheduled_at": scheduled_at,
        "window_start": window_start,
        "window_end": window_end,
        "time_certainty": time_certainty,
        "importance": importance,
        "affected_assets": ["CRYPTO_MARKET"],
        "source": source,
        "source_url": source_url,
        "timezone": source_timezone,
        "reminder_windows": list(reminders),
        "post_event_tracking_status": tracking_status,
        "impact_window_before": impact_window_before,
        "impact_window_after": impact_window_after,
        "fetched_at": acquired_at.isoformat(),
        "research_only": True,
        "no_send": True,
        "no_send_rehearsal": True,
    }
    try:
        normalize_unified_calendar_event(row)
    except CalendarValidationError as exc:
        raise OfficialMacroParseError(
            f"official_calendar_row_invalid:{exc.code.value}"
        ) from exc
    return row


def _dedupe_rows(
    rows: Iterable[Mapping[str, Any]], *, source: str
) -> tuple[dict[str, Any], ...]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        event_id = str(row.get("calendar_event_id") or "")
        previous = by_id.get(event_id)
        if previous is not None and previous != row:
            raise OfficialMacroParseError(f"{source}_calendar_id_conflict")
        by_id[event_id] = row
    return tuple(
        sorted(
            by_id.values(),
            key=lambda row: (
                str(row.get("scheduled_at") or row.get("window_start") or "~"),
                str(row.get("calendar_event_id") or ""),
            ),
        )
    )


def _decoded_text(payload: bytes | str, *, source: str) -> str:
    if isinstance(payload, str):
        return payload.lstrip("\ufeff")
    if not isinstance(payload, bytes):
        raise OfficialMacroParseError(f"{source}_payload_type_invalid")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OfficialMacroParseError(f"{source}_payload_encoding_invalid") from exc


def _aware_utc(value: datetime | str) -> datetime:
    return _aware_datetime(value).astimezone(timezone.utc)


def _aware_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise OfficialMacroParseError("official_macro_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise OfficialMacroParseError("official_macro_timestamp_timezone_missing")
    return parsed


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


__all__ = (
    "BEA_RELEASE_DATES_URL",
    "BEA_RELEASE_SCHEDULE_URL",
    "BLS_CPI_SCHEDULE_URL",
    "BLS_EMPLOYMENT_SCHEDULE_URL",
    "BLS_RELEASE_CALENDAR_URL",
    "FEDERAL_RESERVE_FOMC_URL",
    "OFFICIAL_MACRO_SOURCE_NAMES",
    "OfficialMacroParseError",
    "OfficialMacroParsedSource",
    "merge_official_macro_sources",
    "parse_bea_release_dates_json",
    "parse_bls_release_calendar_ics",
    "parse_federal_reserve_fomc_html",
)
