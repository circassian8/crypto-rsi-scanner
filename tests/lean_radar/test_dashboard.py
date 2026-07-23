from __future__ import annotations

import hashlib
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
    build_preview_database,
    run_dashboard_smoke,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


PRIMARY_PATHS = ("/", "/ideas", "/market", "/calendar", "/outcomes", "/health")


def _store(tmp_path: Path) -> LeanRadarStore:
    return LeanRadarStore(build_preview_database(tmp_path / "lean.db"))


def test_dashboard_smoke_renders_exactly_six_primary_pages() -> None:
    result = run_dashboard_smoke()

    assert result["status"] == "passed"
    assert result["page_count"] == 6
    assert result["database_unchanged_by_get_head"] is True
    assert result["raw_internal_values_hidden"] is True
    assert result["provider_call_attempted"] is False
    assert result["telegram_send_attempted"] is False


def test_every_primary_page_is_human_readable_and_responsive(tmp_path: Path) -> None:
    app = LeanRadarDashboardApp(_store(tmp_path))

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
    body = LeanRadarDashboardApp(_store(tmp_path)).response(
        method="GET",
        path="/",
    ).body.decode("utf-8")

    assert "Scheduled risk in the next 24 hours" in body
    assert "Context only · creates no direction" in body
    assert "Federal Reserve rate decision" in body
    assert "Open calendar →" in body


def test_ideas_filters_and_detail_use_operator_language(tmp_path: Path) -> None:
    app = LeanRadarDashboardApp(_store(tmp_path))

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
    app = LeanRadarDashboardApp(store)
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
    missing_response = LeanRadarDashboardApp(missing).response(method="GET", path="/")

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
    invalid = LeanRadarDashboardApp(store).response(method="GET", path="/")
    assert invalid.status_code == 503
    assert b"Runtime state is not ready" in invalid.body


def test_dashboard_loader_returns_closed_bounded_runtime_truth(tmp_path: Path) -> None:
    state = load_dashboard_state(_store(tmp_path))

    assert state.catalog_count == 5
    assert len(state.active_ideas) == 4
    assert len(state.latest_snapshots) == 5
    assert len(state.calendar_events) == 2
    assert len(state.outcomes) == 16
    assert state.health_status is not None
    assert state.health_status["current_authorization_status"] == "present"
    assert state.health_status["last_provider_call_attempted"] is False


def test_dashboard_server_refuses_non_loopback_binding(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(LeanDashboardDataError, match="loopback-only"):
        serve_dashboard(store, host="0.0.0.0", port=8766)
