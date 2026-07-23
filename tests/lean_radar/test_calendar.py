from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.calendar import (
    LeanCalendarError,
    context_for_idea,
    load_calendar_snapshot,
    normalize_calendar_snapshot,
    score_adjustments,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    return {
        "schema_version": "lean_calendar_import_v1",
        "source_observed_at": "2026-07-23T11:30:00Z",
        "source_name": "Operator official-source bundle",
        "source_url": "https://example.org/calendar",
        "events": [
            {
                "event_id": "fomc-2026-07-23",
                "title": "Federal Reserve decision",
                "category": "fomc",
                "starts_at": "2026-07-23T14:00:00-04:00",
                "ends_at": "2026-07-23T18:30:00Z",
                "time_certainty": "window",
                "importance": "high",
                "affected_symbols": [],
            },
            {
                "event_id": "sol-unlock-2026-07-24",
                "title": "SOL scheduled unlock",
                "category": "crypto_unlock",
                "starts_at": "2026-07-24T00:00:00Z",
                "time_certainty": "exact",
                "importance": "medium",
                "affected_symbols": ["SOL"],
            },
            {
                "event_id": "eth-protocol-2026-07-24",
                "title": "ETH protocol event",
                "category": "protocol_event",
                "starts_at": "2026-07-24T01:00:00Z",
                "time_certainty": "exact",
                "importance": "medium",
                "affected_symbols": ["ETH"],
            },
        ],
    }


def test_calendar_import_is_typed_fingerprinted_and_timezone_normalized() -> None:
    events = normalize_calendar_snapshot(
        _payload(),
        source_mode="fixture",
        source_sha256="b" * 64,
    )

    assert len(events) == 3
    assert events[0].starts_at == "2026-07-23T18:00:00+00:00"
    assert events[0].source_sha256 == "b" * 64
    assert events[0].context_only is True
    assert events[0].research_only is True


def test_calendar_rejects_unknown_category_and_directional_fields() -> None:
    unknown = _payload()
    unknown["events"][0]["category"] = "rumor"  # type: ignore[index]
    with pytest.raises(LeanCalendarError, match="category"):
        normalize_calendar_snapshot(
            unknown,
            source_mode="fixture",
            source_sha256="c" * 64,
        )

    directional = _payload()
    directional["events"][0]["directional_bias"] = "long"  # type: ignore[index]
    with pytest.raises(LeanCalendarError, match="unsupported fields"):
        normalize_calendar_snapshot(
            directional,
            source_mode="fixture",
            source_sha256="d" * 64,
        )

    credential_url = _payload()
    credential_url["source_url"] = "https://example.org/calendar?api_key=do-not-store"
    with pytest.raises(LeanCalendarError, match="credential-like"):
        normalize_calendar_snapshot(
            credential_url,
            source_mode="fixture",
            source_sha256="1" * 64,
        )


def test_genuine_import_rejects_fixture_path_and_accepts_local_copy(
    tmp_path: Path,
) -> None:
    with pytest.raises(LeanCalendarError, match="fixture/test/mock/replay"):
        load_calendar_snapshot(
            ROOT / "fixtures/lean_radar/calendar_snapshot.json",
            source_mode="imported_snapshot",
        )
    fixture_events = load_calendar_snapshot(
        ROOT / "fixtures/lean_radar/calendar_snapshot.json",
        source_mode="fixture",
    )
    assert fixture_events[0].event_id == "fixture-fomc-2026-07-23"
    path = tmp_path / "official-calendar.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    events = load_calendar_snapshot(path, source_mode="imported_snapshot")

    assert len(events) == 3
    assert events[0].source_mode == "imported_snapshot"


def test_calendar_store_and_readiness_are_small_and_observational(
    tmp_path: Path,
) -> None:
    missing = LeanRadarStore(tmp_path / "missing.db")
    assert missing.calendar_status(evaluated_at=NOW)["status"] == "missing"
    assert not missing.path.exists()

    store = LeanRadarStore(tmp_path / "lean.db")
    events = normalize_calendar_snapshot(
        _payload(),
        source_mode="fixture",
        source_sha256="e" * 64,
    )
    store.upsert_calendar_events(events, imported_at=NOW)

    status = store.calendar_status(evaluated_at=NOW)
    loaded = store.list_calendar_events(
        start=NOW - timedelta(hours=1),
        end=NOW + timedelta(days=2),
    )
    assert status["status"] == "ready"
    assert status["event_count"] == 3
    assert status["upcoming_event_count"] == 3
    assert status["source_sha256"] == "e" * 64
    assert loaded == events


def test_calendar_with_only_past_events_is_not_reported_ready(tmp_path: Path) -> None:
    payload = _payload()
    payload["events"] = [
        {
            "event_id": "past-cpi",
            "title": "Past consumer price index",
            "category": "cpi",
            "starts_at": "2026-07-22T12:00:00Z",
            "time_certainty": "exact",
            "importance": "high",
            "affected_symbols": [],
        }
    ]
    events = normalize_calendar_snapshot(
        payload,
        source_mode="fixture",
        source_sha256="7" * 64,
    )
    store = LeanRadarStore(tmp_path / "lean.db")
    store.upsert_calendar_events(events, imported_at=NOW)

    status = store.calendar_status(evaluated_at=NOW)

    assert status["status"] == "no_upcoming"
    assert status["event_count"] == 1
    assert status["upcoming_event_count"] == 0
    assert status["next_event_at"] is None


def test_calendar_context_is_global_or_asset_linked_and_never_directional() -> None:
    events = normalize_calendar_snapshot(
        _payload(),
        source_mode="fixture",
        source_sha256="f" * 64,
    )

    sol = context_for_idea(events, symbol="SOL", evaluated_at=NOW)
    btc = context_for_idea(events, symbol="BTC", evaluated_at=NOW)

    assert [row["event_id"] for row in sol["events"]] == [
        "fomc-2026-07-23",
        "sol-unlock-2026-07-24",
    ]
    assert [row["event_id"] for row in btc["events"]] == [
        "fomc-2026-07-23"
    ]
    assert sol["directional_bias_created"] is False
    assert sol["context_only"] is True
    risk, urgency = score_adjustments(sol, evaluated_at=NOW)
    assert risk == 12.0
    assert urgency == 12.0
