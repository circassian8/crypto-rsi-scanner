"""No-network calendar snapshot boundary tests for the Decision campaign."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import common
from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_calendar


NOW = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)


def _event(event_id: str = "calendar-current", **updates):
    row = {
        "id": event_id,
        "title": "Current scheduled event",
        "event_kind": "protocol",
        "scheduled_at": "2026-07-20T12:00:00Z",
        "time_certainty": "exact",
        "importance": "high",
        "affected_assets": ["BTC"],
        "source": "operator_calendar",
        "source_url": "https://example.com/calendar/current",
        "research_only": True,
        "no_send_rehearsal": True,
    }
    row.update(updates)
    return row


def _live_container(events, **updates):
    payload = {
        "contract_version": market_no_send_calendar.CALENDAR_SNAPSHOT_CONTRACT_VERSION,
        "observed_at": NOW.isoformat(),
        "source_mode": "operator_verified_calendar_snapshot",
        "data_acquisition_mode": "operator_verified_export",
        "source_provider": "operator_calendar",
        "events": events,
    }
    payload.update(updates)
    return payload


def _load(path, **updates):
    return market_no_send_calendar.load_market_no_send_calendar_snapshot(
        environ={market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(path)},
        now=NOW,
        **updates,
    )


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_calendar_snapshot_unconfigured_is_explicit_and_side_effect_free():
    result = market_no_send_calendar.load_market_no_send_calendar_snapshot(
        environ={},
        now=NOW,
    )

    assert result.status == "not_configured"
    assert result.configured is False
    assert result.raw_rows == ()
    assert result.provider_call_attempted is False
    assert result.network_call_attempted is False
    assert result.provider_authorization_mutated is False
    assert result.no_send is True
    assert result.research_only is True
    assert result.to_dict()["telegram_sends"] == 0
    assert set(market_no_send_calendar.CALENDAR_SNAPSHOT_STATUSES) == {
        "not_configured",
        "healthy_empty",
        "healthy_nonempty",
        "stale",
        "unavailable",
        "fixture_rejected_live",
    }


@pytest.mark.parametrize("field", ["research_only", "no_send", "no_send_rehearsal"])
def test_live_calendar_rejects_false_row_safety_flags(tmp_path, field):
    path = tmp_path / f"calendar-false-{field}.json"
    path.write_text(
        json.dumps(_live_container([_event(**{field: False})])),
        encoding="utf-8",
    )

    result = _load(path)

    assert result.status == "unavailable"
    assert result.error_class == "calendar_event_safety_flag_invalid"
    assert result.raw_rows == ()
    assert result.no_send is True
    assert result.research_only is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "fixture"),
        ("source", "test_calendar"),
        ("source_class", "mock"),
    ],
)
def test_live_calendar_rejects_fixture_marked_row_provenance(
    tmp_path,
    field,
    value,
):
    path = tmp_path / f"calendar-row-{field}.json"
    path.write_text(
        json.dumps(_live_container([_event(**{field: value})])),
        encoding="utf-8",
    )

    result = _load(path)

    assert result.status == "fixture_rejected_live"
    assert result.error_class == "fixture_provenance"
    assert result.raw_rows == ()


@pytest.mark.parametrize("container_key", [None, "events", "data", "items"])
def test_calendar_snapshot_accepts_bounded_list_and_named_containers(tmp_path, container_key):
    path = tmp_path / f"calendar-{container_key or 'list'}.json"
    rows = [_event()]
    payload = rows if container_key is None else {
        "observed_at": NOW.isoformat(),
        container_key: rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    if container_key is None:
        os.utime(path, (NOW.timestamp(), NOW.timestamp()))

    result = _load(path, data_mode="mock", run_mode="fixture")

    assert result.status == "healthy_nonempty"
    assert result.usable is True
    assert result.raw_rows == tuple(rows)
    assert result.source_row_count == 1
    assert result.retained_row_count == 1
    assert result.source_filename == "configured_calendar_snapshot.json"
    assert result.source_sha256 and len(result.source_sha256) == 64
    assert result.canonical_rows_sha256 and len(result.canonical_rows_sha256) == 64
    assert result.freshness_basis == (
        "file_mtime" if container_key is None else "container:observed_at"
    )
    assert result.copy_digest_metadata == {
        "copy_artifact_filename": "event_market_no_send_calendar_source.json",
        "source_sha256": result.source_sha256,
        "canonical_rows_sha256": result.canonical_rows_sha256,
        "source_size_bytes": result.source_size_bytes,
        "source_row_count": 1,
        "retained_row_count": 1,
    }


def test_calendar_snapshot_filters_before_and_after_bounded_window(tmp_path):
    path = tmp_path / "calendar-window.json"
    payload = _live_container(
        [
            _event("old", scheduled_at="2026-07-10T12:00:00Z"),
            _event("current"),
            _event("far", scheduled_at="2027-01-20T12:00:00Z"),
        ]
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _load(
        path,
        past_grace=timedelta(hours=12),
        lookahead=timedelta(days=60),
    )

    assert result.status == "healthy_nonempty"
    assert [row["id"] for row in result.raw_rows] == ["current"]
    assert result.source_row_count == 3
    assert result.dropped_before_window_count == 1
    assert result.dropped_after_window_count == 1


def test_calendar_snapshot_distinguishes_fresh_empty_from_stale(tmp_path):
    fresh = tmp_path / "calendar-empty.json"
    fresh.write_text(
        json.dumps(_live_container([])),
        encoding="utf-8",
    )
    stale = tmp_path / "calendar-stale.json"
    stale.write_text(
        json.dumps(
            _live_container(
                [_event()],
                observed_at=(NOW - timedelta(days=3)).isoformat(),
            )
        ),
        encoding="utf-8",
    )

    empty_result = _load(fresh)
    stale_result = _load(stale, max_age=timedelta(hours=24))

    assert empty_result.status == "healthy_empty"
    assert empty_result.source_row_count == 0
    assert empty_result.canonical_rows_sha256 is not None
    assert stale_result.status == "stale"
    assert stale_result.raw_rows == ()
    assert stale_result.source_row_count == 1
    assert stale_result.error_class == "snapshot_too_old"


def test_live_operational_calendar_rejects_fixture_path_without_reading(tmp_path):
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    path = fixture_dir / "calendar.json"
    original = json.dumps({"observed_at": NOW.isoformat(), "events": [_event()]})
    path.write_text(original, encoding="utf-8")

    result = _load(path)

    assert result.status == "fixture_rejected_live"
    assert result.error_class == "fixture_path"
    assert result.source_sha256 is None
    assert path.read_text(encoding="utf-8") == original
    allowed_for_fixture_test = _load(path, data_mode="mock", run_mode="fixture")
    assert allowed_for_fixture_test.status == "healthy_nonempty"


@pytest.mark.parametrize(
    "provenance_update",
    [
        {"profile": "fixture"},
        {"run_mode": "replay"},
        {"source_provenance": {"data_mode": "test"}},
        {"fixture_mode": True},
    ],
)
def test_live_operational_calendar_rejects_fixture_test_replay_provenance(
    tmp_path,
    provenance_update,
):
    path = tmp_path / "calendar-current.json"
    payload = {"observed_at": NOW.isoformat(), "events": [_event()]}
    payload.update(provenance_update)
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _load(path)

    assert result.status == "fixture_rejected_live"
    assert result.error_class == "fixture_provenance"
    assert result.raw_rows == ()
    assert result.source_sha256 is not None


def test_calendar_snapshot_secure_read_rejects_symlink_and_oversize(tmp_path):
    target = tmp_path / "calendar-target.json"
    target.write_text(
        json.dumps({"observed_at": NOW.isoformat(), "events": [_event()]}),
        encoding="utf-8",
    )
    link = tmp_path / "calendar-link.json"
    link.symlink_to(target.name)
    oversized = tmp_path / "calendar-large.json"
    oversized.write_text(json.dumps({"events": [_event(description="x" * 500)]}), encoding="utf-8")

    link_result = _load(link)
    large_result = _load(oversized, max_bytes=128)

    assert link_result.status == "unavailable"
    assert link_result.error_class in {"snapshot_not_regular", "snapshot_unreadable"}
    assert large_result.status == "unavailable"
    assert large_result.error_class == "snapshot_too_large"


def test_calendar_snapshot_secure_read_rejects_symlinked_parent(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    path = real / "calendar.json"
    path.write_text(
        json.dumps({"observed_at": NOW.isoformat(), "events": [_event()]}),
        encoding="utf-8",
    )
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real.name, target_is_directory=True)

    result = _load(linked_parent / path.name)

    assert result.status == "unavailable"
    assert result.error_class == "snapshot_parent_symlink"


def test_calendar_snapshot_detects_in_place_change_during_read(tmp_path, monkeypatch):
    path = tmp_path / "calendar-current.json"
    path.write_text(
        json.dumps({"observed_at": NOW.isoformat(), "events": [_event()]}),
        encoding="utf-8",
    )
    original_read = os.read
    changed = False

    def swapping_read(descriptor, size):
        nonlocal changed
        chunk = original_read(descriptor, size)
        if chunk and not changed:
            changed = True
            path.write_text(
                json.dumps({"observed_at": NOW.isoformat(), "events": []}),
                encoding="utf-8",
            )
        return chunk

    monkeypatch.setattr(market_no_send_calendar.os, "read", swapping_read)
    result = _load(path)

    assert result.status == "unavailable"
    assert result.error_class == "snapshot_changed"


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"unexpected": []}, "snapshot_container_missing"),
        ({"events": ["not-a-row"]}, "snapshot_non_mapping_row"),
        (
            {"observed_at": "2026-07-13T20:00:00Z", "events": [_event(scheduled_at="secret-invalid-time")]},
            "calendar_event_time_invalid",
        ),
        (
            {"observed_at": "2026-07-13T20:00:00Z", "events": [_event(scheduled_at=None)]},
            "calendar_event_time_missing",
        ),
    ],
)
def test_calendar_snapshot_invalid_content_fails_closed_without_payload_echo(
    tmp_path,
    payload,
    expected_error,
):
    path = tmp_path / "calendar-invalid.json"
    if "events" in payload and all(isinstance(row, dict) for row in payload["events"]):
        payload = _live_container(payload["events"])
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _load(path)

    assert result.status == "unavailable"
    assert result.error_class == expected_error
    assert "secret" not in json.dumps(result.to_dict()).casefold()


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ([_event()], "live_snapshot_versioned_container_required"),
        (
            {"observed_at": NOW.isoformat(), "events": [_event()]},
            "live_snapshot_contract_version_invalid",
        ),
        (
            _live_container([_event()], source_mode="arbitrary_source"),
            "live_snapshot_source_mode_invalid",
        ),
        (
            _live_container([_event()], data_acquisition_mode="arbitrary_mode"),
            "live_snapshot_acquisition_mode_invalid",
        ),
        (
            _live_container([_event()], source_provider="fixture_alias"),
            "live_snapshot_source_provider_invalid",
        ),
    ],
)
def test_live_calendar_requires_closed_versioned_provenance(
    tmp_path,
    payload,
    expected_error,
):
    path = tmp_path / "calendar-live-contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _load(path)

    assert result.status in {"unavailable", "fixture_rejected_live"}
    assert result.error_class == expected_error
    assert result.raw_rows == ()


@pytest.mark.parametrize(
    ("event", "expected_error"),
    [
        (_event(private_note="must not persist"), "calendar_event_field_unsupported"),
        (
            _event(description="api_key=calendar-secret"),
            "calendar_event_sensitive_value",
        ),
        (
            _event(description="sk-proj-" + "A" * 20),
            "calendar_event_sensitive_value",
        ),
        (
            _event(description="ghp_" + "A" * 20),
            "calendar_event_sensitive_value",
        ),
        (
            _event(description="Bearer " + "abcdefghijklmnop"),
            "calendar_event_sensitive_value",
        ),
        (
            _event(source_url="https://user:password@example.com/calendar"),
            "calendar_source_url_unsafe",
        ),
        (
            _event(
                source_url="https://example.com/calendar/sk-proj-" + "A" * 20
            ),
            "calendar_source_url_unsafe",
        ),
        (
            _event(source_url="https://example.com/calendar?token=secret"),
            "calendar_source_url_unsafe",
        ),
        (
            _event(reminder_windows=[{"api_key": "secret"}]),
            "calendar_event_sequence_invalid",
        ),
        (
            _event(affected_assets=[{"symbol": "BTC", "private": "secret"}]),
            "calendar_affected_asset_field_unsupported",
        ),
        (
            _event(affected_assets=["X" * 4097]),
            "calendar_event_text_too_long",
        ),
    ],
)
def test_calendar_snapshot_rejects_unknown_nested_and_secret_bearing_fields(
    tmp_path,
    event,
    expected_error,
):
    path = tmp_path / "calendar-sensitive.json"
    path.write_text(json.dumps(_live_container([event])), encoding="utf-8")

    result = _load(path)

    assert result.status == "unavailable"
    assert result.error_class == expected_error
    assert result.raw_rows == ()
    assert "calendar-secret" not in json.dumps(result.to_dict())


def test_live_calendar_rejects_raw_telegram_bot_token_value(tmp_path):
    synthetic_token = "123456789:" + "A" * 35
    path = tmp_path / "calendar-telegram-token.json"
    path.write_text(
        json.dumps(_live_container([_event(title=synthetic_token)])),
        encoding="utf-8",
    )

    result = _load(path)

    serialized = json.dumps(result.to_dict(include_rows=True))
    assert result.status == "unavailable"
    assert result.error_class == "calendar_event_sensitive_value"
    assert result.raw_rows == ()
    assert synthetic_token not in serialized
    details = list(common.classify_secret_hits_in_text(synthetic_token))
    assert any(
        detail["status"] == "blocker"
        and detail["token"] == "telegram_bot_token"
        for detail in details
    )
    scrubbed, redactions = common.scrub_operator_text(synthetic_token)
    assert redactions == 1
    assert synthetic_token not in scrubbed
    assert "<redacted-telegram-bot-token>" in scrubbed


def test_calendar_snapshot_never_calls_network_mutates_auth_or_writes(tmp_path, monkeypatch):
    path = tmp_path / "calendar-current.json"
    original = json.dumps(_live_container([_event()]))
    path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE", "sentinel-authorization")
    monkeypatch.setenv("COINMARKETCAL_API_KEY", "sentinel-key")
    environment_before = {
        "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": os.environ["RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"],
        "COINMARKETCAL_API_KEY": os.environ["COINMARKETCAL_API_KEY"],
    }
    directory_before = {item.name for item in tmp_path.iterdir()}

    def forbidden_network(*args, **kwargs):
        raise AssertionError("calendar snapshot loader attempted network access")

    monkeypatch.setattr("socket.create_connection", forbidden_network)
    result = market_no_send_calendar.load_market_no_send_calendar_snapshot(
        environ={
            market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(path),
            **environment_before,
        },
        now=NOW,
    )

    assert result.status == "healthy_nonempty"
    assert result.provider_call_attempted is False
    assert result.network_call_attempted is False
    assert result.provider_authorization_mutated is False
    assert result.strict_alerts_created == 0
    assert result.created_alert is False
    assert result.notification_send_enabled is False
    assert result.execution_enabled is False
    assert path.read_text(encoding="utf-8") == original
    assert {item.name for item in tmp_path.iterdir()} == directory_before
    assert {
        "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": os.environ["RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"],
        "COINMARKETCAL_API_KEY": os.environ["COINMARKETCAL_API_KEY"],
    } == environment_before
    safe_metadata = result.to_dict()
    assert "rows" not in safe_metadata
    assert str(tmp_path) not in json.dumps(safe_metadata)


def test_unlock_title_and_amount_drift_blocks_calendar_publication(
    tmp_path,
    monkeypatch,
):
    for name in (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    calendar_path = tmp_path / "calendar-unlock-current.json"
    calendar_path.write_text(
        json.dumps(
            _live_container(
                [
                    _event(
                        "calendar-unlock-1",
                        title="MKTFLOW token unlock",
                        event_type="token_unlock",
                        affected_assets=["MKTFLOW"],
                        source_class="structured_calendar",
                        source_url=(
                            "https://example.com/calendar/calendar-unlock-1"
                        ),
                        tokens_unlocked=1_000_000,
                        unlock_pct_circulating_supply=0.08,
                        unlock_vs_30d_adv=1.5,
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="calendar_unlock_binding",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=NOW,
        environ={
            market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(calendar_path)
        },
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )
    namespace_dir = result.namespace_dir
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    unlock_path = namespace_dir / "event_unlock_candidates.jsonl"
    unlock_rows = _jsonl(unlock_path)
    assert manifest["calendar_snapshot"]["unlock_candidate_count"] == 1
    assert unlock_rows[0]["event_name"] == "MKTFLOW token unlock"
    assert unlock_rows[0]["tokens_unlocked"] == 1_000_000
    market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )

    unlock_rows[0]["event_name"] = "Tampered unlock title"
    unlock_rows[0]["tokens_unlocked"] = 50_000_000
    unlock_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in unlock_rows
        ),
        encoding="utf-8",
    )
    drifted_manifest = json.loads(json.dumps(manifest))
    drifted_manifest["calendar_snapshot"][
        "unlock_candidate_artifact_sha256"
    ] = hashlib.sha256(unlock_path.read_bytes()).hexdigest()

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="unlock_semantics_mismatch",
    ):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            drifted_manifest,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
