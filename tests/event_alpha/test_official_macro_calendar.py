from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.radar.calendar.official_macro import (
    OfficialMacroParseError,
    merge_official_macro_sources,
    parse_bea_release_dates_json,
    parse_bls_release_calendar_ics,
    parse_federal_reserve_fomc_html,
)


FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_alpha"
    / "official_macro_calendar"
)
ACQUIRED_AT = "2026-07-15T00:00:00Z"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _ics(*events: str) -> str:
    return "\n".join(
        (
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "X-WR-TIMEZONE:America/Washington_DC",
            *events,
            "END:VCALENDAR",
        )
    )


def _event(
    uid: str,
    summary: str,
    start: str,
    *,
    status: str = "CONFIRMED",
) -> str:
    return "\n".join(
        (
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART{start}",
            f"SUMMARY:{summary}",
            f"STATUS:{status}",
            "END:VEVENT",
        )
    )


def test_federal_reserve_parser_keeps_dates_as_windows_without_decision_time() -> None:
    result = parse_federal_reserve_fomc_html(
        _fixture("federal_reserve_fomc.html"), acquired_at=ACQUIRED_AT
    )

    assert result.source == "federal_reserve"
    assert result.source_rows_seen == 4
    assert result.rejected_rows == 1
    assert len(result.rows) == 3
    july = result.rows[0]
    assert july["calendar_event_id"] == "macro:fed:fomc:2026-07-28"
    assert july["scheduled_at"] is None
    assert july["window_start"] == "2026-07-28T04:00:00+00:00"
    assert july["window_end"] == "2026-07-30T03:59:59+00:00"
    assert july["time_certainty"] == "window"
    assert july["post_event_tracking_status"] == "needs_confirmation"
    assert july["timezone"] == "America/New_York"
    assert all("forecast_value" not in row for row in result.rows)
    assert all("notation" not in row["title"].casefold() for row in result.rows)
    assert "Summary of Economic Projections" in result.rows[1]["title"]


def test_federal_reserve_parser_fails_closed_on_structural_drift() -> None:
    with pytest.raises(
        OfficialMacroParseError, match="federal_reserve_fomc_rows_missing"
    ):
        parse_federal_reserve_fomc_html(
            "<html><h3>2026 meetings</h3><p>July 28-29</p></html>",
            acquired_at=ACQUIRED_AT,
        )


def test_bls_parser_selects_only_cpi_and_employment_with_dst_conversion() -> None:
    result = parse_bls_release_calendar_ics(
        _fixture("bls_release_calendar.ics"), acquired_at=ACQUIRED_AT
    )

    assert result.source_rows_seen == 5
    assert len(result.rows) == 4
    assert {row["event_kind"] for row in result.rows} == {
        "inflation",
        "employment",
    }
    assert {row["scheduled_at"] for row in result.rows} == {
        "2026-08-07T12:30:00+00:00",
        "2026-08-12T12:30:00+00:00",
        "2026-09-04T12:30:00+00:00",
        "2026-09-11T12:30:00+00:00",
    }
    assert all(row["time_certainty"] == "exact" for row in result.rows)
    assert all("forecast_value" not in row for row in result.rows)


def test_bls_date_only_and_tentative_values_remain_uncertain_windows() -> None:
    payload = _ics(
        _event(
            "cpi-date@bls.gov",
            "Consumer Price Index",
            ";VALUE=DATE:20260812",
            status="TENTATIVE",
        ),
        _event(
            "jobs@bls.gov",
            "Employment Situation",
            ";TZID=US/Eastern:20260807T083000",
        ),
    )

    result = parse_bls_release_calendar_ics(payload, acquired_at=ACQUIRED_AT)
    cpi = next(row for row in result.rows if row["event_kind"] == "inflation")
    assert cpi["scheduled_at"] is None
    assert cpi["window_start"] == "2026-08-12T04:00:00+00:00"
    assert cpi["window_end"] == "2026-08-13T03:59:59+00:00"
    assert cpi["time_certainty"] == "estimated"
    assert cpi["post_event_tracking_status"] == "needs_confirmation"


def test_bls_parser_preserves_london_source_timezone() -> None:
    payload = _ics(
        _event(
            "cpi-london@bls.gov",
            "Consumer Price Index",
            ";TZID=Europe/London:20260812T083000",
        ),
        _event(
            "jobs-london@bls.gov",
            "Employment Situation",
            ";TZID=Europe/London:20260807T083000",
        ),
    )

    result = parse_bls_release_calendar_ics(payload, acquired_at=ACQUIRED_AT)

    assert {row["timezone"] for row in result.rows} == {"Europe/London"}
    assert {row["scheduled_at"] for row in result.rows} == {
        "2026-08-07T07:30:00+00:00",
        "2026-08-12T07:30:00+00:00",
    }


def test_bls_canceled_or_malformed_required_series_does_not_count_as_present() -> None:
    payload = _ics(
        _event(
            "cpi-canceled@bls.gov",
            "Consumer Price Index",
            ";TZID=America/New_York:20260812T083000",
            status="CANCELLED",
        ),
        _event(
            "jobs@bls.gov",
            "Employment Situation",
            ";TZID=America/New_York:20260807T083000",
        ),
    )
    with pytest.raises(OfficialMacroParseError, match="bls_required_series_missing:cpi"):
        parse_bls_release_calendar_ics(payload, acquired_at=ACQUIRED_AT)


def test_bls_conflicting_duplicate_uid_fails_closed() -> None:
    payload = _ics(
        _event(
            "same@bls.gov",
            "Consumer Price Index",
            ";TZID=America/New_York:20260812T083000",
        ),
        _event(
            "same@bls.gov",
            "Consumer Price Index",
            ";TZID=America/New_York:20260911T083000",
        ),
        _event(
            "jobs@bls.gov",
            "Employment Situation",
            ";TZID=America/New_York:20260807T083000",
        ),
    )
    with pytest.raises(OfficialMacroParseError, match="bls_uid_timing_conflict"):
        parse_bls_release_calendar_ics(payload, acquired_at=ACQUIRED_AT)


def test_bea_parser_selects_gdp_and_personal_income_outlays_only() -> None:
    result = parse_bea_release_dates_json(
        _fixture("bea_release_dates.json"), acquired_at=ACQUIRED_AT
    )

    assert result.source_rows_seen == 4
    assert len(result.rows) == 4
    assert {row["event_kind"] for row in result.rows} == {
        "macro_release",
        "inflation",
    }
    assert all(row["time_certainty"] == "exact" for row in result.rows)
    assert all(row["timezone"] == "UTC" for row in result.rows)
    assert all("forecast_value" not in row for row in result.rows)
    assert not any("Trade" in row["title"] for row in result.rows)


def test_bea_parser_preserves_explicit_london_summer_offset() -> None:
    payload = json.dumps(
        {
            "Gross Domestic Product": {
                "release_dates": ["2026-07-30T08:30:00+01:00"]
            },
            "Personal Income and Outlays": {
                "release_dates": ["2026-07-31T08:30:00+01:00"]
            },
        }
    )

    result = parse_bea_release_dates_json(payload, acquired_at=ACQUIRED_AT)

    assert {row["timezone"] for row in result.rows} == {"UTC+01:00"}
    assert {row["scheduled_at"] for row in result.rows} == {
        "2026-07-30T07:30:00+00:00",
        "2026-07-31T07:30:00+00:00",
    }


@pytest.mark.parametrize(
    "payload,match",
    (
        (
            '{"Gross Domestic Product": {}, "Gross Domestic Product": {}}',
            "bea_json_invalid",
        ),
        (
            json.dumps(
                {
                    "Gross Domestic Product": {
                        "release_dates": ["2026-07-30T12:30:00"]
                    },
                    "Personal Income and Outlays": {
                        "release_dates": ["2026-07-30T12:30:00+00:00"]
                    },
                }
            ),
            "official_macro_timestamp_timezone_missing",
        ),
        (
            json.dumps(
                {
                    "Gross Domestic Product": {
                        "release_dates": ["2026-07-30T12:30:00+00:00"]
                    }
                }
            ),
            "bea_required_series_missing:personal-income-and-outlays",
        ),
    ),
)
def test_bea_parser_rejects_ambiguous_or_incomplete_payloads(
    payload: str, match: str
) -> None:
    with pytest.raises(OfficialMacroParseError, match=match):
        parse_bea_release_dates_json(payload, acquired_at=ACQUIRED_AT)


def test_complete_pack_merge_is_deterministic_and_requires_every_source() -> None:
    sources = (
        parse_federal_reserve_fomc_html(
            _fixture("federal_reserve_fomc.html"), acquired_at=ACQUIRED_AT
        ),
        parse_bls_release_calendar_ics(
            _fixture("bls_release_calendar.ics"), acquired_at=ACQUIRED_AT
        ),
        parse_bea_release_dates_json(
            _fixture("bea_release_dates.json"), acquired_at=ACQUIRED_AT
        ),
    )
    merged = merge_official_macro_sources(reversed(sources))
    assert len(merged) == 11
    assert len({row["calendar_event_id"] for row in merged}) == 11
    assert all(row["research_only"] is True for row in merged)
    assert all(row["no_send"] is True for row in merged)
    with pytest.raises(OfficialMacroParseError, match="official_source_missing:bea"):
        merge_official_macro_sources(sources[:2])
