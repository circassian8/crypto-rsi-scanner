"""Fixture-first unified calendar contract tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.radar.calendar import (
    CALENDAR_EVENT_KINDS,
    CalendarValidationError,
    format_unified_calendar_preview,
    load_unified_calendar_artifact,
    load_unified_calendar_fixture,
    normalize_unified_calendar_event,
    normalize_unified_calendar_rows,
    write_unified_calendar_artifact,
)


_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_FIXTURE = _ROOT / "fixtures/event_discovery/unified_calendar_events.json"
_DASHBOARD_CALENDAR = (
    _ROOT / "fixtures/event_alpha/radar_dashboard/current/event_unified_calendar_events.jsonl"
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
