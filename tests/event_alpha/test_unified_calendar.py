"""Fixture-first unified calendar contract tests."""

from __future__ import annotations

import hashlib
import json
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.radar.calendar import (
    CALENDAR_EVENT_KINDS,
    CALENDAR_REJECTION_CODES,
    CalendarRejectionCode,
    CalendarValidationError,
    UnifiedCalendarEvent,
    UnifiedCalendarNormalizationTelemetry,
    format_unified_calendar_preview,
    load_unified_calendar_artifact,
    load_unified_calendar_fixture,
    load_unified_calendar_fixture_raw_rows,
    load_unified_calendar_fixture_with_telemetry,
    normalize_unified_calendar_event,
    normalize_unified_calendar_rows,
    normalize_unified_calendar_rows_with_telemetry,
    write_unified_calendar_artifact,
)


_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_FIXTURE = _ROOT / "fixtures/event_discovery/unified_calendar_events.json"
_DASHBOARD_CALENDAR = (
    _ROOT / "fixtures/event_alpha/radar_dashboard/current/event_unified_calendar_events.jsonl"
)


def _calendar_row(**updates):
    row = {
        "id": "calendar-safe",
        "title": "Safe calendar event",
        "event_kind": "regulatory",
        "scheduled_at": "2026-08-01T12:00:00Z",
        "time_certainty": "exact",
        "importance": "high",
        "affected_assets": ["BTC"],
        "source": "Fixture",
        "source_url": "https://example.com/calendar",
        "reminder_windows": ["24h"],
        "post_event_tracking_status": "upcoming",
    }
    row.update(updates)
    return row


_MAPPING_REJECTION_CASES = (
    ({"title": ""}, CalendarRejectionCode.MISSING_TITLE),
    ({"event_kind": "not_registered"}, CalendarRejectionCode.UNSUPPORTED_EVENT_KIND),
    ({"time_certainty": "not_registered"}, CalendarRejectionCode.UNSUPPORTED_TIME_CERTAINTY),
    ({"importance": "not_registered"}, CalendarRejectionCode.UNSUPPORTED_IMPORTANCE),
    (
        {"post_event_tracking_status": "not_registered"},
        CalendarRejectionCode.UNSUPPORTED_TRACKING_STATUS,
    ),
    ({"source_url": "not-an-http-url"}, CalendarRejectionCode.INVALID_SOURCE_URL),
    ({"scheduled_at": "not-a-time"}, CalendarRejectionCode.INVALID_TIMESTAMP),
    ({"scheduled_at": None}, CalendarRejectionCode.EXACT_MISSING_SCHEDULED_AT),
    (
        {
            "scheduled_at": None,
            "time_certainty": "window",
            "window_start": "2026-08-01T00:00:00Z",
            "window_end": None,
        },
        CalendarRejectionCode.WINDOW_MISSING_BOUNDS,
    ),
    (
        {
            "scheduled_at": None,
            "time_certainty": "window",
            "window_start": "2026-08-02T00:00:00Z",
            "window_end": "2026-08-01T00:00:00Z",
        },
        CalendarRejectionCode.WINDOW_END_BEFORE_START,
    ),
    ({"reminder_windows": ["0h"]}, CalendarRejectionCode.INVALID_REMINDER_WINDOW),
    ({"research_only": False}, CalendarRejectionCode.UNSAFE_RESEARCH_ONLY),
    ({"no_send_rehearsal": False}, CalendarRejectionCode.UNSAFE_NO_SEND_REHEARSAL),
    ({"notification_send_enabled": True}, CalendarRejectionCode.UNSAFE_SIDE_EFFECT_FLAG),
    ({"telegram_sends": "0"}, CalendarRejectionCode.INVALID_SIDE_EFFECT_COUNTER),
    ({"telegram_sends": 1}, CalendarRejectionCode.NONZERO_SIDE_EFFECT_COUNTER),
)


def test_unified_calendar_fixture_covers_all_kinds_and_canonical_fields():
    before = hashlib.sha256(_SOURCE_FIXTURE.read_bytes()).hexdigest()
    rows = load_unified_calendar_fixture(
        _SOURCE_FIXTURE,
        profile="fixture",
        artifact_namespace="calendar_fixture",
        run_mode="fixture",
        run_id="calendar-run",
        observed_at="2026-06-15T16:00:00Z",
    )

    assert {row["event_kind"] for row in rows} == set(CALENDAR_EVENT_KINDS)
    assert all(row["research_only"] is True for row in rows)
    assert all(row["no_send_rehearsal"] is True for row in rows)
    assert all(row["telegram_sends"] == 0 for row in rows)
    assert all(row["trades_created"] == 0 for row in rows)
    assert all(row["paper_trades_created"] == 0 for row in rows)
    assert all(row["normal_rsi_signal_rows_written"] == 0 for row in rows)
    assert all(row["triggered_fade_created"] == 0 for row in rows)
    assert all("window_start_at" not in row for row in rows)
    assert all("date_certainty" not in row for row in rows)
    assert all("tracking_state" not in row for row in rows)
    assert all(schema_v1.validate_row_against_schema(row, "unified_calendar_event_v1") == [] for row in rows)
    assert hashlib.sha256(_SOURCE_FIXTURE.read_bytes()).hexdigest() == before


def test_unified_calendar_uncertain_date_uses_bounded_window():
    rows = load_unified_calendar_fixture(_SOURCE_FIXTURE)
    uncertain = next(row for row in rows if row["calendar_event_id"] == "calendar-testtge-window-2026")

    assert uncertain["scheduled_at"] is None
    assert uncertain["window_start"] == "2026-07-01T00:00:00+00:00"
    assert uncertain["window_end"] == "2026-07-15T23:59:59+00:00"
    assert uncertain["time_certainty"] == "window"
    assert uncertain["post_event_tracking_status"] == "needs_confirmation"


def test_unified_calendar_accepts_old_input_aliases_but_emits_canonical_names():
    row = normalize_unified_calendar_event(
        {
            "id": "alias-window",
            "title": "Alias input window",
            "event_kind": "regulatory",
            "window_start_at": "2026-08-01T00:00:00Z",
            "window_end_at": "2026-08-03T00:00:00Z",
            "date_certainty": "window",
            "tracking_state": "needs_confirmation",
            "importance": "high",
            "affected_assets": ["BTC"],
            "source": "Fixture",
            "source_url": "https://example.com/calendar",
            "reminder_windows": ["24h"],
        }
    ).to_dict()

    assert row["window_start"] == "2026-08-01T00:00:00+00:00"
    assert row["window_end"] == "2026-08-03T00:00:00+00:00"
    assert row["time_certainty"] == "window"
    assert row["post_event_tracking_status"] == "needs_confirmation"
    assert not {"window_start_at", "window_end_at", "date_certainty", "tracking_state"} & set(row)


def test_unified_calendar_rejects_invalid_timing_url_and_side_effects():
    cases = (
        ({"source_url": "javascript:alert(1)"}, "source_url"),
        ({"window_end": "2026-07-01T00:00:00Z"}, "precedes"),
        ({"telegram_sends": 1}, "side effects"),
        ({"paper_trades_created": 1}, "side effects"),
        ({"triggered_fade_created": 1}, "side effects"),
        ({"notification_send_enabled": True}, "cannot enable"),
        ({"notification_send_enabled": "false"}, "ambiguously encode"),
        ({"research_only": "true"}, "ambiguously encode"),
        ({"telegram_sends": "0"}, "invalid safety counter"),
    )
    base = {
        "id": "safe-window",
        "title": "Safe window",
        "event_kind": "regulatory",
        "window_start": "2026-07-02T00:00:00Z",
        "window_end": "2026-07-03T00:00:00Z",
        "time_certainty": "window",
        "importance": "high",
        "affected_assets": ["BTC"],
        "source": "Fixture",
        "source_url": "https://example.com/calendar",
        "reminder_windows": ["24h"],
        "post_event_tracking_status": "needs_confirmation",
        "research_only": True,
    }
    for updates, error_fragment in cases:
        with pytest.raises(CalendarValidationError, match=error_fragment):
            normalize_unified_calendar_event({**base, **updates})


def test_unified_calendar_artifact_filters_exact_operator_identity():
    rows = load_unified_calendar_artifact(
        _DASHBOARD_CALENDAR,
        run_id="dashboard-run-current",
        profile="fixture",
        artifact_namespace="current",
    )

    assert {row["calendar_event_id"] for row in rows} == {
        "calendar:current-cpi",
        "calendar:current-regulatory-window",
    }
    assert all(row["run_id"] == "dashboard-run-current" for row in rows)


def test_scheduled_sidecar_rows_produce_atomic_artifact_and_no_send_preview(tmp_path):
    rows = normalize_unified_calendar_rows(
        ({
            "event_id": "scheduled-upgrade",
            "title": "Protocol upgrade",
            "event_type": "protocol_upgrade",
            "event_start_time": "2026-08-01T12:00:00Z",
            "symbol": "UP",
            "provider": "fixture_calendar",
            "source_url": "https://example.com/upgrade",
            "event_status": "confirmed",
        },),
        profile="fixture",
        artifact_namespace="calendar_write",
        run_mode="fixture",
        run_id="calendar-write-run",
        observed_at="2026-07-12T12:00:00Z",
    )
    path = write_unified_calendar_artifact(tmp_path / "event_unified_calendar_events.jsonl", rows)
    preview = format_unified_calendar_preview(rows)

    assert len(load_unified_calendar_artifact(path, run_id="calendar-write-run")) == 1
    assert "Protocol upgrade" in preview
    assert "Research-only / no-send preview" in preview
    assert "notifications sent: 0" in preview


def test_calendar_mapping_validation_sites_emit_closed_payload_free_codes():
    for updates, expected_code in _MAPPING_REJECTION_CASES:
        with pytest.raises(CalendarValidationError) as raised:
            normalize_unified_calendar_event(_calendar_row(**updates))
        assert raised.value.code is expected_code


def test_calendar_direct_validation_sites_complete_the_closed_reason_enum():
    event = {
        "calendar_event_id": "calendar-direct",
        "title": "Direct calendar event",
        "event_kind": "regulatory",
        "scheduled_at": "2026-08-01T12:00:00+00:00",
        "window_start": None,
        "window_end": None,
        "time_certainty": "exact",
        "importance": "high",
        "affected_assets": ("BTC",),
        "source": "Fixture",
        "source_url": "https://example.com/calendar",
        "reminder_windows": ("24h",),
        "post_event_tracking_status": "upcoming",
    }
    direct_cases = (
        ({"calendar_event_id": ""}, CalendarRejectionCode.MISSING_EVENT_ID),
        ({"source": ""}, CalendarRejectionCode.MISSING_SOURCE),
        ({"event_kind": "not_registered"}, CalendarRejectionCode.UNSUPPORTED_EVENT_KIND),
    )
    for updates, expected_code in direct_cases:
        with pytest.raises(CalendarValidationError) as raised:
            UnifiedCalendarEvent(**dict(event, **updates))
        assert raised.value.code is expected_code

    covered = {code for _updates, code in _MAPPING_REJECTION_CASES}
    covered.update(code for _updates, code in direct_cases)
    assert covered == set(CalendarRejectionCode)
    assert CALENDAR_REJECTION_CODES == {code.value for code in CalendarRejectionCode}


def test_calendar_adversarial_timestamps_urls_and_counters_are_coded_rejections():
    timezone_underflow = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14)))
    invalid_timestamps = (
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        10**10000,
        timezone_underflow,
    )
    for invalid in invalid_timestamps:
        with pytest.raises(CalendarValidationError) as raised:
            normalize_unified_calendar_event(_calendar_row(scheduled_at=invalid))
        assert raised.value.code is CalendarRejectionCode.INVALID_TIMESTAMP

    for invalid_url in ("http://[broken", "https://example.com:not-a-port/path"):
        with pytest.raises(CalendarValidationError) as raised:
            normalize_unified_calendar_event(_calendar_row(source_url=invalid_url))
        assert raised.value.code is CalendarRejectionCode.INVALID_SOURCE_URL

    with pytest.raises(CalendarValidationError) as raised:
        normalize_unified_calendar_event(_calendar_row(telegram_sends=float("inf")))
    assert raised.value.code is CalendarRejectionCode.INVALID_SIDE_EFFECT_COUNTER


def test_calendar_validation_messages_and_telemetry_never_echo_malicious_values():
    secret = "secret-token-calendar-payload"
    cases = (
        {"event_kind": secret},
        {"importance": secret},
        {"post_event_tracking_status": secret},
        {"scheduled_at": secret},
        {"source_url": f"https://example.com:{secret}"},
        {"reminder_windows": [secret]},
        {"notification_send_enabled": secret},
    )
    for updates in cases:
        with pytest.raises(CalendarValidationError) as raised:
            normalize_unified_calendar_event(_calendar_row(**updates))
        assert secret not in str(raised.value)
        assert raised.value.code.value in CALENDAR_REJECTION_CODES
        assert raised.value.__cause__ is None
        formatted = "".join(
            traceback.format_exception(raised.type, raised.value, raised.tb)
        )
        assert secret not in formatted


def test_calendar_normalization_telemetry_counts_raw_rows_once_and_is_deterministic():
    secret = "secret-calendar-row-value"
    first = _calendar_row(id="duplicate", title="First valid")
    invalid_duplicate = _calendar_row(
        id="duplicate",
        title=secret,
        source_url=f"not-a-url-{secret}",
    )
    last = _calendar_row(id="duplicate", title="Last valid")
    invalid_time = _calendar_row(id=secret, scheduled_at=secret, source=secret)
    raw_rows = [first, f"non-mapping-{secret}", invalid_time, invalid_duplicate, last]

    class OneShotRows:
        def __init__(self, values):
            self.values = values
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations != 1:
                raise AssertionError("calendar rows were iterated more than once")
            return iter(self.values)

    one_shot = OneShotRows(raw_rows)
    result = normalize_unified_calendar_rows_with_telemetry(
        one_shot,
        profile="fixture",
        artifact_namespace="calendar_telemetry",
        run_mode="fixture",
        run_id="calendar-telemetry-run",
        observed_at="2026-07-12T12:00:00Z",
    )

    assert one_shot.iterations == 1
    assert len(result.rows) == 1
    assert result.rows[0]["title"] == "Last valid"
    assert result.telemetry.to_dict() == {
        "contract_version": 1,
        "dedupe_policy": "last_valid_row_wins",
        "input_rows": 5,
        "accepted_rows": 2,
        "output_rows": 1,
        "duplicate_overwrite_rows": 1,
        "non_mapping_rows": 1,
        "rejected_rows": 2,
        "rejected_reason_counts": {
            "invalid_source_url": 1,
            "invalid_timestamp": 1,
        },
    }
    serialized = json.dumps(result.telemetry.to_dict(), sort_keys=True)
    assert secret not in serialized
    assert "not-a-url" not in serialized
    assert list(result.telemetry.rejected_reason_counts) == [
        "invalid_source_url",
        "invalid_timestamp",
    ]

    repeated = normalize_unified_calendar_rows_with_telemetry(
        raw_rows,
        profile="fixture",
        artifact_namespace="calendar_telemetry",
        run_mode="fixture",
        run_id="calendar-telemetry-run",
        observed_at="2026-07-12T12:00:00Z",
    )
    compatible_rows = normalize_unified_calendar_rows(
        raw_rows,
        profile="fixture",
        artifact_namespace="calendar_telemetry",
        run_mode="fixture",
        run_id="calendar-telemetry-run",
        observed_at="2026-07-12T12:00:00Z",
    )
    assert repeated == result
    assert isinstance(compatible_rows, tuple)
    assert compatible_rows == result.rows


def test_calendar_invalid_final_duplicate_never_erases_or_counts_as_an_overwrite():
    first = _calendar_row(id="duplicate", title="Valid row survives")
    invalid_final = _calendar_row(
        id="duplicate",
        title="Rejected duplicate",
        source_url="not-an-http-url",
    )

    result = normalize_unified_calendar_rows_with_telemetry(
        (first, invalid_final),
        profile="fixture",
        artifact_namespace="calendar_invalid_duplicate",
        run_mode="fixture",
        run_id="calendar-invalid-duplicate",
        observed_at="2026-07-12T12:00:00Z",
    )

    assert len(result.rows) == 1
    assert result.rows[0]["title"] == "Valid row survives"
    assert result.telemetry.accepted_rows == 1
    assert result.telemetry.output_rows == 1
    assert result.telemetry.duplicate_overwrite_rows == 0
    assert result.telemetry.rejected_rows == 1
    assert result.telemetry.rejected_reason_counts == {"invalid_source_url": 1}


def test_calendar_raw_fixture_loader_uses_first_present_key_without_fallthrough(tmp_path):
    valid = _calendar_row(id="items-must-not-win")
    fixture = tmp_path / "empty-events.json"
    fixture.write_text(
        json.dumps({"events": [], "items": [valid], "data": [valid]}),
        encoding="utf-8",
    )

    assert load_unified_calendar_fixture_raw_rows(fixture) == ()
    assert load_unified_calendar_fixture(fixture) == ()
    result = load_unified_calendar_fixture_with_telemetry(fixture)
    assert result.rows == ()
    assert result.telemetry.input_rows == 0

    fixture.write_text(json.dumps({"events": None, "items": [valid]}), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain an event list"):
        load_unified_calendar_fixture_raw_rows(fixture)

    fixture.write_text("{}", encoding="utf-8")
    assert load_unified_calendar_fixture_raw_rows(fixture) == ()

    secret = "secret-container-key"
    fixture.write_text(json.dumps({secret: []}), encoding="utf-8")
    with pytest.raises(ValueError) as raised:
        load_unified_calendar_fixture_raw_rows(fixture)
    assert str(raised.value) == (
        "unified calendar fixture object must contain events, items, or data"
    )
    assert secret not in str(raised.value)


def test_calendar_raw_fixture_loader_rejects_duplicate_json_keys_without_echo(tmp_path):
    secret = "secret-duplicate-calendar-value"
    fixture = tmp_path / "duplicate-keys.json"
    payloads = (
        f'{{"events":[],"events":[{{"title":"{secret}"}}]}}',
        f'{{"events":[{{"title":"safe","title":"{secret}"}}]}}',
    )
    for payload in payloads:
        fixture.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError) as raised:
            load_unified_calendar_fixture_raw_rows(fixture)
        assert str(raised.value) == (
            "unified calendar fixture contains duplicate JSON object keys"
        )
        assert secret not in str(raised.value)
        assert raised.value.__cause__ is None


def test_calendar_fixture_compatibility_and_raw_rejection_accounting(tmp_path):
    secret = "secret-fixture-value"
    valid = _calendar_row(id="fixture-valid")
    invalid = _calendar_row(id=secret, source_url=f"bad-{secret}")
    payload = {"events": [valid, f"non-mapping-{secret}", invalid]}
    fixture = tmp_path / "mixed-events.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    assert load_unified_calendar_fixture_raw_rows(fixture) == tuple(payload["events"])
    with pytest.raises(CalendarValidationError) as raised:
        load_unified_calendar_fixture(fixture)
    assert raised.value.code is CalendarRejectionCode.INVALID_SOURCE_URL

    result = load_unified_calendar_fixture_with_telemetry(fixture)
    assert len(result.rows) == 1
    assert result.telemetry.to_dict() == {
        "contract_version": 1,
        "dedupe_policy": "last_valid_row_wins",
        "input_rows": 3,
        "accepted_rows": 1,
        "output_rows": 1,
        "duplicate_overwrite_rows": 0,
        "non_mapping_rows": 1,
        "rejected_rows": 1,
        "rejected_reason_counts": {"invalid_source_url": 1},
    }
    assert secret not in json.dumps(result.telemetry.to_dict(), sort_keys=True)


def test_calendar_telemetry_type_enforces_counter_and_reason_invariants():
    valid = {
        "contract_version": 1,
        "dedupe_policy": "last_valid_row_wins",
        "input_rows": 1,
        "accepted_rows": 1,
        "output_rows": 1,
        "duplicate_overwrite_rows": 0,
        "non_mapping_rows": 0,
        "rejected_rows": 0,
        "rejected_reason_counts": {},
    }
    assert UnifiedCalendarNormalizationTelemetry(**valid).to_dict() == valid

    invalid_cases = (
        {"contract_version": True},
        {"dedupe_policy": "first_row_wins"},
        {"input_rows": True},
        {"input_rows": -1},
        {"input_rows": 2},
        {"accepted_rows": 2},
        {"output_rows": 0},
        {
            "input_rows": 1,
            "accepted_rows": 0,
            "output_rows": 0,
            "rejected_rows": 1,
            "rejected_reason_counts": {"unregistered_reason": 1},
        },
        {
            "input_rows": 1,
            "accepted_rows": 0,
            "output_rows": 0,
            "rejected_rows": 1,
            "rejected_reason_counts": {"invalid_timestamp": 0},
        },
        {
            "input_rows": 1,
            "accepted_rows": 0,
            "output_rows": 0,
            "rejected_rows": 1,
            "rejected_reason_counts": {"invalid_timestamp": True},
        },
        {
            "input_rows": 1,
            "accepted_rows": 0,
            "output_rows": 0,
            "rejected_rows": 1,
            "rejected_reason_counts": {"invalid_timestamp": 2},
        },
    )
    for updates in invalid_cases:
        with pytest.raises(ValueError):
            UnifiedCalendarNormalizationTelemetry(**dict(valid, **updates))
