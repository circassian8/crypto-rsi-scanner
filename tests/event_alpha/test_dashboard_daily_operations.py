"""Read-only dashboard coverage for Daily Operations maintenance telemetry."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json

from crypto_rsi_scanner.event_alpha.dashboard import maintenance_history
from crypto_rsi_scanner.event_alpha.dashboard import history as dashboard_history
from crypto_rsi_scanner.event_alpha.dashboard.app import RadarDashboardApp
from crypto_rsi_scanner.event_alpha.dashboard.campaign_page import render_campaign_page
from crypto_rsi_scanner.event_alpha.dashboard import loader as dashboard_loader
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import render_health_page
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page
from crypto_rsi_scanner.event_alpha.operations import (
    daily_operations_current_status,
    daily_operations_service,
    market_no_send,
)
from tests.event_alpha.test_dashboard_read_model_v1 import _NOW, _copy_namespace
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot
from tests.event_alpha.test_radar_dashboard import _request


_SAFETY = {
    "telegram_sends": 0,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}


def test_dashboard_history_public_exports_are_resolvable() -> None:
    for name in dashboard_history.__all__:
        assert hasattr(dashboard_history, name), name


def _service_state() -> dict[str, object]:
    return {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_service",
        "updated_at": "2026-07-12T06:00:00+00:00",
        "prepared": True,
        "operation": "install",
        "operation_ok": True,
        "operation_changed": True,
        "enabled": True,
        "installed": True,
        "loaded": True,
        "running": False,
        "healthy": True,
        "reason": "installed",
        "scheduler_reason": "owned_loaded",
        "scheduler_last_exit_code": 0,
        "scheduler_runs": 7,
        "scheduler_label": "com.nasrenkaraf.crypto-radar-daily-operations",
        "interval_seconds": 300,
        **_SAFETY,
        "no_send": True,
        "research_only": True,
        "plist_path": "/must/not/enter/the/read/model",
    }


def _maintenance_state() -> dict[str, object]:
    return {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_state",
        "updated_at": "2026-07-12T06:02:00+00:00",
        "last_cycle_id": "cycle-3",
        "last_cycle_status": "succeeded",
        "last_cycle_reason": "published_and_restarted",
        "last_cycle_namespace": "radar_market_no_send_3",
        "last_readiness_check": "2026-07-12T05:59:00+00:00",
        "last_attempted_observation": "2026-07-12T06:00:00+00:00",
        "last_successful_publication": "2026-07-12T06:02:00+00:00",
        "last_successful_namespace": "radar_market_no_send_3",
        "next_eligible_observation_at": "2026-07-12T07:00:00+00:00",
        "authorization_at_last_cycle": True,
        "authorization_checked_at_last_cycle": "2026-07-12T05:59:00+00:00",
        "live_provider_authorized": True,
        "provider_call_attempted": True,
        "pointer_published": True,
        "dashboard_restarted": True,
        "pointer_invalidated": False,
        "scheduler_enabled": True,
        "scheduler_loaded": True,
        "scheduler_healthy": True,
        "scheduler_reason": "owned_loaded",
        "scheduler_last_exit_code": 0,
        "scheduler_runs": 7,
        **_SAFETY,
        "no_send": True,
        "research_only": True,
        "authorization_header": "must-not-enter-the-read-model",
    }


def _current_status() -> dict[str, object]:
    return {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_current_status",
        "updated_at": "2026-07-12T06:02:30+00:00",
        "current_authorization_status": "not_authorized",
        "current_authorization_checked_at": "2026-07-12T06:02:30+00:00",
        "current_status_valid_until": "2026-07-12T06:17:30+00:00",
        "current_provider_call_eligibility": "blocked_authorization",
        "next_eligible_observation_at": "2026-07-12T07:00:00+00:00",
        "scheduler_enabled": True,
        "scheduler_loaded": True,
        "scheduler_healthy": True,
        "dashboard_owned": True,
        "readiness_status": "blocked",
        "readiness_reason": "provider_authorization_missing",
        "safe_manual_readiness_command": daily_operations_current_status.READINESS_COMMAND,
        "installation_command": daily_operations_current_status.INSTALL_COMMAND,
        "rollback_disable_command": daily_operations_current_status.DISABLE_COMMAND,
        "installation_requires_confirmation": True,
        "authorization_boundary": "existing_live_authorization_only",
        "implications": "missing_authorization_or_cadence_blocks_the_provider_boundary",
        "expected_provider_activity": "readiness_none_cycle_at_most_one_bounded_coingecko_request",
        "provider_call_attempted": False,
        **_SAFETY,
        "no_send": True,
        "research_only": True,
        "environment_value": "must-not-enter-the-read-model",
    }


def _cycle(index: int, status: str, reason: str) -> dict[str, object]:
    succeeded = status == "succeeded"
    attempted = status in {"succeeded", "failed"}
    return {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_cycle",
        "cycle_id": f"cycle-{index}",
        "recorded_at": f"2026-07-12T0{index}:00:00+00:00",
        "artifact_namespace": f"radar_market_no_send_{index}",
        "status": status,
        "reason": reason,
        "provider_call_attempted": attempted,
        "provider_request_succeeded": succeeded,
        "pointer_published": succeeded,
        "dashboard_restarted": succeeded,
        "pointer_rolled_back": False,
        "pointer_invalidated": False,
        **_SAFETY,
        "no_send": True,
        "research_only": True,
        "provider_token": "must-not-enter-the-read-model",
    }


def _write_maintenance_artifacts(tmp_path) -> None:
    (tmp_path / maintenance_history.SERVICE_FILENAME).write_text(
        json.dumps(_service_state()) + "\n",
        encoding="utf-8",
    )
    (tmp_path / maintenance_history.STATE_FILENAME).write_text(
        json.dumps(_maintenance_state()) + "\n",
        encoding="utf-8",
    )
    (tmp_path / maintenance_history.CURRENT_STATUS_FILENAME).write_text(
        json.dumps(_current_status()) + "\n",
        encoding="utf-8",
    )
    cycles = (
        _cycle(1, "attempted", "readiness_pending"),
        _cycle(2, "skipped", "provider_backoff_active"),
        _cycle(3, "succeeded", "published_and_restarted"),
    )
    (tmp_path / maintenance_history.CYCLE_LEDGER_FILENAME).write_text(
        "".join(json.dumps(row) + "\n" for row in cycles),
        encoding="utf-8",
    )


def test_current_status_rejects_noncanonical_ttl_or_clock_binding() -> None:
    now = datetime.fromisoformat(_NOW)
    invalid_rows = []

    extended = _current_status()
    extended["current_status_valid_until"] = "2026-07-12T07:02:30+00:00"
    invalid_rows.append(extended)

    mismatched_update = _current_status()
    mismatched_update["updated_at"] = "2026-07-12T06:02:29+00:00"
    invalid_rows.append(mismatched_update)

    future = _current_status()
    future.update(
        {
            "updated_at": "2026-07-12T06:04:00+00:00",
            "current_authorization_checked_at": "2026-07-12T06:04:00+00:00",
            "current_status_valid_until": "2026-07-12T06:19:00+00:00",
        }
    )
    invalid_rows.append(future)

    assert all(
        maintenance_history._project_current_status(row, now=now) == {}
        for row in invalid_rows
    )


def test_maintenance_history_is_bounded_allowlisted_and_non_authoritative(
    tmp_path,
    monkeypatch,
) -> None:
    _copy_namespace(tmp_path)
    _write_maintenance_artifacts(tmp_path)
    invalid = _cycle(4, "blocked", "provider_authorization_missing")
    invalid["trades_created"] = 1
    with (tmp_path / maintenance_history.CYCLE_LEDGER_FILENAME).open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(json.dumps(invalid) + "\n")
    monkeypatch.setattr(
        maintenance_history,
        "DASHBOARD_MAINTENANCE_CYCLE_LIMIT",
        3,
    )

    snapshot = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is True
    assert snapshot.maintenance_service["enabled"] is True
    assert "plist_path" not in snapshot.maintenance_service
    assert snapshot.maintenance_state["scheduler_healthy"] is True
    assert snapshot.maintenance_state["authorization_at_last_cycle"] is True
    assert snapshot.maintenance_state["pointer_invalidated"] is False
    assert "authorization_header" not in snapshot.maintenance_state
    assert snapshot.maintenance_current_status["current_authorization_status"] == "not_authorized"
    assert snapshot.maintenance_current_status["current_status_freshness"] == "current"
    assert "environment_value" not in snapshot.maintenance_current_status
    assert [row["cycle_id"] for row in snapshot.maintenance_cycles] == [
        "cycle-2",
        "cycle-3",
    ]
    assert all("provider_token" not in row for row in snapshot.maintenance_cycles)
    assert all(row["pointer_invalidated"] is False for row in snapshot.maintenance_cycles)
    metadata = snapshot.maintenance_history_metadata[
        maintenance_history.CYCLE_LEDGER_FILENAME
    ]
    assert metadata["authority"] == "maintenance_telemetry_non_authoritative"
    assert metadata["source_row_count"] == 4
    assert metadata["returned_row_count"] == 2
    assert metadata["row_limit"] == 3
    assert metadata["truncated"] is True
    assert metadata["rejected_row_count"] == 1
    assert metadata["error"] == "invalid_contract_rows"


def test_absent_or_unsafe_service_receipt_fails_closed(tmp_path) -> None:
    _copy_namespace(tmp_path)

    absent = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert absent.maintenance_service["prepared"] is True
    assert absent.maintenance_service["enabled"] is False
    assert absent.maintenance_service["healthy"] is True
    assert absent.maintenance_service["reason"] == "not_installed"
    absent_metadata = absent.maintenance_history_metadata[
        maintenance_history.SERVICE_FILENAME
    ]
    assert absent_metadata["defaulted"] is True
    assert absent_metadata["source_row_count"] == 0

    outside = tmp_path / "outside-service.json"
    outside.write_text(json.dumps(_service_state()) + "\n", encoding="utf-8")
    (tmp_path / maintenance_history.SERVICE_FILENAME).symlink_to(outside)

    unsafe = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert unsafe.maintenance_service == {}
    assert unsafe.maintenance_history_metadata[maintenance_history.SERVICE_FILENAME][
        "error"
    ] == "artifact_symlink_not_allowed"


def test_health_and_run_history_render_daily_operations_truth() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        operator_state={
            **source.operator_state,
            "run_started_at": "2026-07-14T10:00:00+00:00",
        },
        maintenance_service=_service_state(),
        maintenance_state=_maintenance_state(),
        maintenance_current_status=_current_status(),
        maintenance_cycles=(
            _cycle(2, "skipped", "provider_backoff_active"),
            _cycle(3, "succeeded", "published_and_restarted"),
        ),
        maintenance_history_metadata={
            maintenance_history.CYCLE_LEDGER_FILENAME: {
                "authority": "maintenance_telemetry_non_authoritative",
                "source_row_count": 2,
                "returned_row_count": 2,
                "error": None,
                "sha256": "9" * 64,
            }
        },
    )

    health = render_health_page(snapshot)
    history = render_campaign_page(snapshot, {})

    for label in (
        "Daily Operations maintenance",
        "Enabled",
        "Last readiness check",
        "Last attempted observation",
        "Last successful publication",
        "Next eligible observation",
        "Generation authority expiry",
        "Authorization at last cycle",
        "Authorization checked at last cycle",
        "Current authorization status",
        "Not authorized",
        "Current provider-call eligibility",
        "Scheduler health",
        "Latest skip / block reason",
        "Provider backoff active",
    ):
        assert label in health
    assert 'datetime="2026-07-14T16:00:00Z"' in health
    assert "does not inspect launchd or call a provider" in health
    assert "Daily maintenance cycle ledger" in history
    assert "Bounded Daily Operations maintenance cycles" in history
    assert "Provider backoff active" in history
    assert "Attempt status" in history
    assert "Published" in history
    assert "Dashboard restarted" in history
    assert "Historical / not current" in history
    assert "Maintenance telemetry / non-authoritative" in history


def test_run_history_separates_attempt_publication_operations_and_current() -> None:
    source = _snapshot()
    current = _cycle(3, "succeeded", "published_and_restarted")
    current["artifact_namespace"] = source.artifact_namespace
    snapshot = replace(source, maintenance_cycles=(current,))

    history = render_campaign_page(snapshot, {})

    for label in (
        "Attempt status",
        "Publication",
        "Operations",
        "Current authority",
        "Succeeded",
        "Published",
        "Dashboard restarted",
        "Current exact authority",
    ):
        assert label in history


def test_dashboard_get_and_head_only_read_persisted_maintenance_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    _copy_namespace(tmp_path)
    _write_maintenance_artifacts(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("dashboard request crossed an operational boundary")

    monkeypatch.setattr(
        daily_operations_service,
        "inspect_scheduler_health",
        forbidden,
    )
    monkeypatch.setattr(
        market_no_send,
        "build_market_no_send_readiness",
        forbidden,
    )
    before = {
        path.relative_to(tmp_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    app = RadarDashboardApp(tmp_path, "current", now=_NOW)

    get_response, get_body = _request(app, "/health")
    head_response, head_body = _request(app, "/campaign-history", method="HEAD")

    after = {
        path.relative_to(tmp_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert get_response["status"] == "200 OK"
    assert b"Daily Operations maintenance" in get_body
    assert head_response["status"] == "200 OK"
    assert head_body == b""
    assert after == before


def test_today_and_health_show_manual_expiry_guidance_without_enabling_service() -> None:
    source = _snapshot()
    service = {**_service_state(), "enabled": False, "installed": False, "loaded": False}
    state = {
        **_maintenance_state(),
        "scheduler_enabled": False,
        "scheduler_loaded": False,
        "next_eligible_observation_at": "2026-07-14T14:00:00+00:00",
    }
    current = {
        **_current_status(),
        "scheduler_enabled": False,
        "scheduler_loaded": False,
        "next_eligible_observation_at": "2026-07-14T14:00:00+00:00",
    }
    snapshot = replace(
        source,
        operator_state={
            **source.operator_state,
            "run_started_at": "2026-07-14T10:00:00+00:00",
        },
        generation_authority_checked_at="2026-07-14T15:00:00+00:00",
        maintenance_service=service,
        maintenance_state=state,
        maintenance_current_status=current,
    )

    today = render_today_page(snapshot)
    health = render_health_page(snapshot)

    for page in (today, health):
        assert daily_operations_current_status.READINESS_COMMAND in page
        assert daily_operations_current_status.INSTALL_COMMAND in page
        assert "maintenance is disabled" in page.casefold()
        assert "explicit confirmation" in page.casefold()
    assert snapshot.maintenance_service["enabled"] is False
