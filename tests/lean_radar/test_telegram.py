from __future__ import annotations

from datetime import timedelta
import hashlib
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.dashboard_smoke import (
    SMOKE_NOW,
    build_preview_database,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore, LeanRadarStoreError
from crypto_rsi_scanner.lean_radar.telegram import (
    MAX_ITEMS_PER_MESSAGE,
    LeanTelegramError,
    build_telegram_plan,
    render_telegram_preview,
    render_telegram_readiness,
    send_telegram_plan,
    telegram_readiness,
)


NOW = SMOKE_NOW + timedelta(minutes=5)


def _store(tmp_path: Path) -> LeanRadarStore:
    return LeanRadarStore(build_preview_database(tmp_path / "lean.db"))


def _all_updates(plan: dict[str, object]) -> list[dict[str, object]]:
    return [
        dict(update)
        for message in plan["messages"]
        for update in message["state_updates"]
    ]


def _replace_idea(store: LeanRadarStore, idea_id: str, **changes: object) -> None:
    with store.connect(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM ideas WHERE idea_id = ?", (idea_id,)
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload.update(changes)
        connection.execute(
            "UPDATE ideas SET payload_json = ? WHERE idea_id = ?",
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                idea_id,
            ),
        )
        connection.commit()


def _make_sources_genuine(store: LeanRadarStore) -> None:
    with store.connect(write=True) as connection:
        scan_row = connection.execute(
            "SELECT payload_json FROM system_health WHERE component = 'scan'"
        ).fetchone()
        scan = json.loads(scan_row["payload_json"])
        scan["source_mode"] = "imported_snapshot"
        connection.execute(
            "UPDATE system_health SET payload_json = ? WHERE component = 'scan'",
            (json.dumps(scan, sort_keys=True, separators=(",", ":")),),
        )
        for row in connection.execute(
            "SELECT idea_id, payload_json FROM ideas"
        ).fetchall():
            payload = json.loads(row["payload_json"])
            payload["source_context"]["market_source_mode"] = "imported_snapshot"
            connection.execute(
                "UPDATE ideas SET payload_json = ? WHERE idea_id = ?",
                (
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    row["idea_id"],
                ),
            )
        for row in connection.execute(
            "SELECT event_id, payload_json FROM calendar_events"
        ).fetchall():
            payload = json.loads(row["payload_json"])
            payload["source_mode"] = "imported_snapshot"
            connection.execute(
                "UPDATE calendar_events SET payload_json = ? WHERE event_id = ?",
                (
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    row["event_id"],
                ),
            )
        connection.commit()


def test_preview_is_first_class_read_only_and_human_worded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()

    plan = build_telegram_plan(store, evaluated_at=NOW)
    rendered = render_telegram_preview(plan)
    after = hashlib.sha256(store.path.read_bytes()).hexdigest()
    bodies = "\n".join(message["body"] for message in plan["messages"])

    assert plan["status"] == "ready"
    assert plan["due_item_count"] == 5
    assert plan["message_count"] == 4
    assert set(message["message_type"] for message in plan["messages"]) == {
        "urgent_review",
        "watchlist_update",
        "risk_calendar",
    }
    assert "SOL · Rapid market anomaly" in bodies
    assert "XRP · Exhaustion / fade review" in bodies
    assert "Fade / exhaustion review" in bodies
    assert "Federal Reserve rate decision" in bodies
    assert "Context only · creates no market direction" in bodies
    assert "Actionability" in bodies
    assert "Confidence" in bodies
    assert "Main risk:" in bodies
    assert "Confirms:" in bodies
    assert "Invalidates:" in bodies
    assert "Open dashboard detail" in bodies
    assert "Research only · human decision required" in bodies
    assert "rapid_market_anomaly" not in bodies
    assert "short_review" not in bodies
    assert "No send attempted." in rendered
    assert plan["telegram_send_attempted"] is False
    assert plan["provider_call_attempted"] is False
    assert plan["database_write_attempted"] is False
    assert before == after
    assert all(message["character_count"] <= 4096 for message in plan["messages"])


def test_missing_runtime_preview_is_safe_and_does_not_create_database(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "missing.db")

    plan = build_telegram_plan(store, evaluated_at=NOW)
    readiness = telegram_readiness(store, environ={}, evaluated_at=NOW)

    assert plan["status"] == "setup_required"
    assert plan["message_count"] == 0
    assert readiness["status"] == "setup_required"
    assert readiness["telegram_send_attempted"] is False
    assert not store.path.exists()


@pytest.mark.parametrize(
    "url",
    (
        "https://user:password@example.com",
        "https://example.com/private-token",
        "https://example.com/?token=secret",
        "file:///tmp/dashboard",
    ),
)
def test_preview_rejects_credential_bearing_or_non_http_dashboard_urls(
    tmp_path: Path,
    url: str,
) -> None:
    with pytest.raises(LeanTelegramError, match="dashboard URL is unsafe"):
        build_telegram_plan(_store(tmp_path), evaluated_at=NOW, dashboard_url=url)


def test_readiness_reports_only_secret_safe_configuration_metadata(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    environment = {
        "RSI_EVENT_ALERTS_ENABLED": "1",
        "TELEGRAM_BOT_TOKEN": "placeholder-token",
        "TELEGRAM_CHAT_ID": "chat-a,chat-b",
    }

    report = telegram_readiness(store, environ=environment, evaluated_at=NOW)
    rendered = render_telegram_readiness(report)
    serialized = json.dumps(report, sort_keys=True) + rendered

    assert report["status"] == "preview_ready"
    assert report["send_guard_enabled"] is True
    assert report["telegram_token_present"] is True
    assert report["telegram_recipient_count"] == 2
    assert report["current_send_eligibility"] == "blocked"
    assert "fixture" in " ".join(report["send_blockers"])
    assert "placeholder-token" not in serialized
    assert "chat-a" not in serialized
    assert "chat-b" not in serialized
    assert report["telegram_send_attempted"] is False


def test_unchanged_family_is_suppressed_until_material_change_or_cooldown(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = build_telegram_plan(store, evaluated_at=NOW)
    store.record_notification_deliveries(_all_updates(first), delivered_at=NOW)

    unchanged = build_telegram_plan(store, evaluated_at=NOW + timedelta(minutes=20))
    assert unchanged["message_count"] == 0
    assert unchanged["suppression_reasons"]["unchanged_cooldown"] == 5

    _replace_idea(
        store,
        "lean-sol-rapid-review",
        urgency_score=99.0,
        idea_type="market_breakout_long",
    )
    changed = build_telegram_plan(store, evaluated_at=NOW + timedelta(minutes=20))
    urgent = next(
        message
        for message in changed["messages"]
        if message["message_type"] == "urgent_review"
    )
    assert urgent["due_reasons"] == ["material_change"]
    assert urgent["visible_families"] == ["asset:SOL:upside_momentum"]

    store.record_notification_deliveries(
        urgent["state_updates"], delivered_at=NOW + timedelta(minutes=20)
    )
    cooldown = build_telegram_plan(
        store,
        evaluated_at=NOW + timedelta(minutes=141),
    )
    urgent_after_cooldown = next(
        message
        for message in cooldown["messages"]
        if message["message_type"] == "urgent_review"
    )
    assert urgent_after_cooldown["due_reasons"] == ["cooldown_elapsed"]


def test_many_distinct_urgent_items_are_grouped_without_a_daily_cap(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    base_payload = next(
        row
        for row in store.list_active_ideas()
        if row["idea_id"] == "lean-sol-rapid-review"
    )
    with store.connect(write=True) as connection:
        for index in range(12):
            payload = dict(base_payload)
            payload["idea_id"] = f"lean-urgent-{index:02d}"
            payload["symbol"] = f"T{index:02d}"
            payload["canonical_asset_id"] = f"test-urgent-{index:02d}"
            payload["bybit_instrument"] = f"T{index:02d}USDT"
            connection.execute(
                """
                INSERT INTO ideas (idea_id, created_at, expires_at, active, payload_json)
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    payload["idea_id"],
                    payload["created_at"],
                    payload["expires_at"],
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )
        connection.commit()

    plan = build_telegram_plan(store, evaluated_at=NOW)
    urgent = [
        message
        for message in plan["messages"]
        if message["message_type"] == "urgent_review"
    ]
    urgent_ids = [item for message in urgent for item in message["item_ids"]]

    assert plan["hard_urgent_daily_cap"] is None
    assert len(urgent_ids) == 13
    assert len(set(urgent_ids)) == 13
    assert all(message["market_wide"] is True for message in urgent)
    assert all(message["item_count"] <= MAX_ITEMS_PER_MESSAGE for message in urgent)
    assert all(message["character_count"] <= 4096 for message in urgent)
    assert "daily_cap" not in plan["suppression_reasons"]


def test_real_send_requires_confirmation_guard_configuration_and_genuine_state(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    calls: list[str] = []

    def sender(body: str, **_: object) -> bool:
        calls.append(body)
        return True

    environment = {
        "RSI_EVENT_ALERTS_ENABLED": "1",
        "TELEGRAM_BOT_TOKEN": "configured-but-never-rendered",
        "TELEGRAM_CHAT_ID": "chat-a",
    }
    unconfirmed = send_telegram_plan(
        store,
        confirm=False,
        environ=environment,
        evaluated_at=NOW,
        send_fn=sender,
    )
    fixture = send_telegram_plan(
        store,
        confirm=True,
        environ=environment,
        evaluated_at=NOW,
        send_fn=sender,
    )

    assert unconfirmed["status"] == "blocked"
    assert "confirmation" in unconfirmed["send_blockers"][0]
    assert fixture["status"] == "blocked"
    assert calls == []
    assert store.notification_states() == {}


def test_mocked_guarded_send_records_only_success_and_then_dedupes(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    _make_sources_genuine(store)
    calls: list[tuple[str, tuple[str, ...]]] = []

    def sender(body: str, **kwargs: object) -> bool:
        calls.append((body, tuple(kwargs["chat_ids"])))
        return True

    environment = {
        "RSI_EVENT_ALERTS_ENABLED": "1",
        "TELEGRAM_BOT_TOKEN": "configured-but-never-rendered",
        "TELEGRAM_CHAT_ID": "chat-a",
    }
    result = send_telegram_plan(
        store,
        confirm=True,
        environ=environment,
        evaluated_at=NOW,
        send_fn=sender,
    )
    after = build_telegram_plan(store, environ=environment, evaluated_at=NOW)

    assert result["status"] == "complete"
    assert result["attempted_message_count"] == 4
    assert result["delivered_message_count"] == 4
    assert result["failed_message_count"] == 0
    assert result["telegram_sends"] == 4
    assert len(calls) == 4
    assert all(recipients == ("chat-a",) for _, recipients in calls)
    assert len(store.notification_states()) == 5
    assert after["message_count"] == 0
    assert store.health_status("telegram")["telegram_sends"] == 4
    assert all(value == 0 for key, value in result.items() if key.endswith("_created"))


def test_failed_mock_send_does_not_consume_dedupe_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _make_sources_genuine(store)
    environment = {
        "RSI_EVENT_ALERTS_ENABLED": "1",
        "TELEGRAM_BOT_TOKEN": "configured-but-never-rendered",
        "TELEGRAM_CHAT_ID": "chat-a",
    }

    result = send_telegram_plan(
        store,
        confirm=True,
        environ=environment,
        evaluated_at=NOW,
        send_fn=lambda *_args, **_kwargs: False,
    )

    assert result["status"] == "failed"
    assert result["delivered_message_count"] == 0
    assert result["failed_message_count"] == 4
    assert store.notification_states() == {}
    assert build_telegram_plan(store, evaluated_at=NOW)["message_count"] == 4


def test_notification_send_lock_is_owned_and_expiring(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner = store.acquire_notification_send_lock(acquired_at=NOW, lease_seconds=60)

    assert owner is not None
    assert store.acquire_notification_send_lock(
        acquired_at=NOW + timedelta(seconds=30), lease_seconds=60
    ) is None
    assert store.release_notification_send_lock("0" * 32) is False
    assert store.release_notification_send_lock(owner) is True
    assert store.acquire_notification_send_lock(
        acquired_at=NOW + timedelta(seconds=31), lease_seconds=60
    ) is not None


def test_corrupt_notification_state_and_lock_fail_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    plan = build_telegram_plan(store, evaluated_at=NOW)
    store.record_notification_deliveries(_all_updates(plan), delivered_at=NOW)
    with store.connect(write=True) as connection:
        connection.execute(
            "UPDATE notification_state SET last_material_digest = 'invalid'"
        )
        connection.commit()

    with pytest.raises(LeanTelegramError, match="notification state is unavailable"):
        build_telegram_plan(store, evaluated_at=NOW + timedelta(minutes=1))

    with store.connect(write=True) as connection:
        connection.execute("DELETE FROM notification_state")
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("lean_telegram_send_lock", "not-json"),
        )
        connection.commit()
    with pytest.raises(LeanRadarStoreError, match="notification send lock is invalid"):
        store.acquire_notification_send_lock(acquired_at=NOW)
