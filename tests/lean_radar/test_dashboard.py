from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.dashboard import (
    LeanRadarDashboardApp,
    serve_dashboard,
)
from crypto_rsi_scanner.lean_radar.dashboard_data import (
    LeanDashboardDataError,
    load_dashboard_state,
)
from crypto_rsi_scanner.lean_radar.dashboard_smoke import (
    SMOKE_NOW,
    build_preview_database,
    run_dashboard_smoke,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


PRIMARY_PATHS = ("/", "/ideas", "/market", "/calendar", "/outcomes", "/health")
NOW = SMOKE_NOW + timedelta(hours=1, minutes=5)


def _store(tmp_path: Path) -> LeanRadarStore:
    return LeanRadarStore(build_preview_database(tmp_path / "lean.db"))


def _app(store: LeanRadarStore) -> LeanRadarDashboardApp:
    return LeanRadarDashboardApp(store, evaluated_at=NOW)


def _replace_scan(store: LeanRadarStore, **changes: object) -> None:
    with store.connect(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM system_health WHERE component = 'scan'"
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload.update(changes)
        connection.execute(
            "UPDATE system_health SET checked_at = ?, status = ?, payload_json = ? "
            "WHERE component = 'scan'",
            (
                payload["checked_at"],
                payload["status"],
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        connection.commit()


def test_dashboard_smoke_renders_exactly_six_primary_pages() -> None:
    result = run_dashboard_smoke()

    assert result["status"] == "passed"
    assert result["page_count"] == 6
    assert result["database_unchanged_by_get_head"] is True
    assert result["raw_internal_values_hidden"] is True
    assert result["provider_call_attempted"] is False
    assert result["telegram_send_attempted"] is False


def test_every_primary_page_is_human_readable_and_responsive(tmp_path: Path) -> None:
    app = _app(_store(tmp_path))

    for path in PRIMARY_PATHS:
        response = app.response(method="GET", path=path)
        body = response.body.decode("utf-8")
        assert response.status_code == 200
        assert body.count('class="nav-link') == 6
        assert 'name="viewport"' in body
        assert "@media(max-width:760px)" in body
        assert "Research only" in body
        assert "Fixture data" in body
        assert "rapid_market_anomaly" not in body
        assert "urgent_review" not in body
        assert "2026-07-23T12:00:00" not in body


def test_today_surfaces_near_term_calendar_context_without_direction(
    tmp_path: Path,
) -> None:
    body = _app(_store(tmp_path)).response(
        method="GET",
        path="/",
    ).body.decode("utf-8")

    assert "Scheduled risk in the next 24 hours" in body
    assert "Context only · creates no direction" in body
    assert "Federal Reserve rate decision" in body
    assert "Open calendar →" in body


def test_ideas_filters_and_detail_use_operator_language(tmp_path: Path) -> None:
    app = _app(_store(tmp_path))

    filtered = app.response(
        method="GET",
        path="/ideas",
        query_string="route=urgent-review&sort=urgency&q=SOL",
    ).body.decode("utf-8")
    detail = app.response(
        method="GET",
        path="/ideas/lean-sol-rapid-review",
    ).body.decode("utf-8")

    assert "SOLUSDT" in filtered
    assert "XRPUSDT" not in filtered
    assert "Rapid market anomaly" in filtered
    assert "Why now" in detail
    assert "Price and activity" in detail
    assert "Technical context" in detail
    assert "Calendar context" in detail
    assert "Catalyst context" in detail
    assert "Outcome history" in detail
    assert "Current Bybit spread and depth" not in detail


def test_get_and_head_are_read_only_and_other_methods_are_rejected(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    app = _app(store)
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()

    get = app.response(method="GET", path="/health")
    head = app.response(method="HEAD", path="/health")
    post = app.response(method="POST", path="/")
    after = hashlib.sha256(store.path.read_bytes()).hexdigest()

    assert get.status_code == 200
    assert head.status_code == 200
    assert head.body == b""
    assert post.status_code == 405
    assert ("Allow", "GET, HEAD") in post.headers
    assert before == after


def test_missing_or_invalid_runtime_fails_closed_without_creation(tmp_path: Path) -> None:
    missing = LeanRadarStore(tmp_path / "missing.db")
    missing_response = _app(missing).response(method="GET", path="/")

    assert missing_response.status_code == 503
    assert b"Dashboard unavailable" in missing_response.body
    assert not missing.path.exists()

    store = _store(tmp_path)
    with store.connect(write=True) as connection:
        connection.execute(
            """
            UPDATE ideas SET payload_json = '{}'
            WHERE idea_id = (SELECT idea_id FROM ideas ORDER BY idea_id LIMIT 1)
            """
        )
        connection.commit()
    invalid = _app(store).response(method="GET", path="/")
    assert invalid.status_code == 503
    assert b"Runtime state is not ready" in invalid.body


def test_dashboard_loader_returns_closed_bounded_runtime_truth(tmp_path: Path) -> None:
    state = load_dashboard_state(_store(tmp_path), evaluated_at=NOW)

    assert state.catalog_count == 5
    assert state.market_idea_freshness == "current"
    assert state.suppressed_active_idea_count == 0
    assert len(state.active_ideas) == 4
    assert len(state.latest_snapshots) == 5
    assert len(state.calendar_events) == 2
    assert len(state.outcomes) == 16
    assert state.health_status is not None
    assert state.health_status["current_authorization_status"] == "present"
    assert state.health_status["last_provider_call_attempted"] is False
    assert state.health_status["telegram_mode"] == "preview_only"


def test_system_health_surfaces_telegram_preview_without_claiming_delivery(
    tmp_path: Path,
) -> None:
    body = _app(_store(tmp_path)).response(
        method="GET",
        path="/health",
    ).body.decode("utf-8")

    assert "Telegram" in body
    assert "Preview only" in body
    assert "preview messages · no send on page load" in body
    assert "Telegram sends</span>" in body


@pytest.mark.parametrize(
    ("changes", "expected_freshness"),
    (
        (
            {
                "status": "provider_failed",
                "checked_at": NOW.isoformat(),
                "observed_at": None,
            },
            "incomplete",
        ),
        (
            {
                "status": "complete",
                "checked_at": NOW.isoformat(),
                "observed_at": (NOW - timedelta(minutes=41)).isoformat(),
            },
            "stale",
        ),
    ),
)
def test_stale_or_incomplete_scan_hides_current_ideas_but_keeps_history(
    tmp_path: Path,
    changes: dict[str, object],
    expected_freshness: str,
) -> None:
    store = _store(tmp_path)
    _replace_scan(store, **changes)

    state = load_dashboard_state(store, evaluated_at=NOW)
    app = _app(store)
    today = app.response(method="GET", path="/").body.decode("utf-8")
    ideas = app.response(method="GET", path="/ideas").body.decode("utf-8")
    market = app.response(method="GET", path="/market").body.decode("utf-8")
    detail = app.response(
        method="GET", path="/ideas/lean-sol-rapid-review"
    ).body.decode("utf-8")

    assert state.market_idea_freshness == expected_freshness
    assert state.suppressed_active_idea_count == 4
    assert state.active_ideas == ()
    assert len(state.recent_ideas) == 4
    assert "4 stored ideas are hidden" in today
    assert "Rapid market anomaly" not in today
    assert "0 current ideas" in ideas
    assert "SOLUSDT" in market
    assert "Historical market snapshot" in market
    assert "Historical idea" in detail
    assert "not a current operator action" in detail


def test_dashboard_server_refuses_non_loopback_binding(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(LeanDashboardDataError, match="loopback-only"):
        serve_dashboard(store, host="0.0.0.0", port=8766)
