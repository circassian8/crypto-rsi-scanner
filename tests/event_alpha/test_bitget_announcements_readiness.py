"""Observational Bitget announcement readiness regressions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bitget_announcements_readiness import (
    AUTHORIZATION_ACTION,
    FUTURE_CAPTURE_COMMAND,
    LIVE_AUTH_ENV,
    READINESS_COMMAND,
    ROLLBACK_COMMAND,
    SMOKE_COMMAND,
    build_bitget_announcement_readiness,
    main,
)


NOW = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)


def test_absent_authorization_is_explicit_and_never_calls_or_writes() -> None:
    value = build_bitget_announcement_readiness(environ={}, now=NOW)

    assert value["status"] == "blocked"
    assert value["ready"] is False
    assert value["checked_at"] == "2026-07-19T02:00:00Z"
    assert value["runtime_authorization_env"] == LIVE_AUTH_ENV
    assert value["runtime_provider_authorized"] is False
    assert value["authorization_mutated"] is False
    assert value["reasons"] == [
        "runtime_provider_authorization_absent",
        "immutable_capture_boundary_not_implemented",
        "strict_capture_doctor_not_implemented",
        "live_capture_transport_not_implemented",
    ]
    assert value["provider_call_planned"] is False
    assert value["provider_call_attempted"] is False
    assert value["provider_request_count"] == 0
    assert value["writes_performed"] is False
    assert value["expected_provider_activity"] == "none_readiness_only"
    assert value["next_safe_command"] == SMOKE_COMMAND
    assert value["operator_action_required"] == AUTHORIZATION_ACTION
    assert value["rollback_disable_command"] == ROLLBACK_COMMAND


def test_present_authorization_cannot_unlock_missing_capture_layers() -> None:
    value = build_bitget_announcement_readiness(
        environ={LIVE_AUTH_ENV: "true"},
        now=NOW,
    )

    assert value["runtime_provider_authorized"] is True
    assert value["ready"] is False
    assert value["reasons"] == [
        "immutable_capture_boundary_not_implemented",
        "strict_capture_doctor_not_implemented",
        "live_capture_transport_not_implemented",
    ]
    assert value["live_capture_configured"] is False
    assert value["immutable_capture_boundary_implemented"] is False
    assert value["capture_command_available"] is False
    assert value["strict_capture_doctor_implemented"] is False
    assert value["future_capture_command"] == FUTURE_CAPTURE_COMMAND
    assert value["operator_action_required"] == (
        "wait_for_capture_doctor_and_live_transport_implementation"
    )
    assert value["provider_call_planned"] is False


def test_request_window_and_future_activity_are_exact_and_bounded() -> None:
    value = build_bitget_announcement_readiness(environ={}, now=NOW)
    plan = value["request_plan"]

    assert value["request_window_start"] == "2026-06-18T02:00:00Z"
    assert value["request_window_end"] == "2026-07-19T02:00:00Z"
    assert value["maximum_provider_request_count"] == 20
    assert value["maximum_provider_response_rows"] == 200
    assert plan["path"] == "/api/v2/public/annoucements"
    assert plan["path_spelling_verified"] == "annoucements"
    assert plan["initial_query"] == {
        "startTime": "1781748000000",
        "endTime": "1784426400000",
        "limit": "10",
        "language": "en_US",
    }
    assert plan["pagination_policy"] == (
        "next_cursor_is_last_annId_from_previous_response"
    )
    assert value[
        "expected_provider_activity_if_future_authorized_capture_is_implemented"
    ] == "between_1_and_20_public_GETs_no_redirects_or_retries"
    assert value["redirects_allowed"] is False
    assert value["retries_allowed"] is False
    assert value["alternate_hosts_allowed"] is False
    assert value["proxy_or_vpn_bypass_allowed"] is False


def test_readiness_preserves_all_research_only_boundaries() -> None:
    value = build_bitget_announcement_readiness(environ={}, now=NOW)

    assert value["campaign_attached"] is False
    assert value["dashboard_authority_eligible"] is False
    assert value["context_only"] is True
    assert value["directional_authority"] is False
    assert value["decision_policy_applied"] is False
    assert value["protocol_v2_annex_bound"] is False
    assert value["protocol_v2_evidence_eligible"] is False
    assert value["research_only"] is True
    assert value["no_send"] is True
    assert value["credentials_read"] is False
    assert value["private_data_read"] is False
    assert value["orders_available"] is False
    assert value["trades_created"] == 0
    assert value["paper_trades_created"] == 0
    assert value["normal_rsi_signal_rows_written"] == 0
    assert value["triggered_fade_created"] == 0
    assert value["telegram_sends"] == 0


def test_cli_is_no_network_and_renders_the_same_blocked_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(LIVE_AUTH_ENV, raising=False)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("readiness must not use network")
        ),
    )

    assert main([]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "blocked"
    assert value["readiness_recheck_command"] == READINESS_COMMAND
    assert value["provider_call_attempted"] is False
    assert value["writes_performed"] is False
