"""Observational KuCoin announcement readiness regressions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.kucoin_announcements_readiness import (
    AUTHORIZATION_ACTION,
    CAPTURE_SMOKE_COMMAND,
    CURRENT_ANNOUNCEMENTS_PATH,
    CURRENT_CONTRACT_VERSION,
    CURRENT_OFFICIAL_API_DOC,
    CURRENT_SMOKE_COMMAND,
    FUTURE_CAPTURE_COMMAND,
    LIVE_AUTH_ENV,
    READINESS_COMMAND,
    ROLLBACK_COMMAND,
    SMOKE_COMMAND,
    build_kucoin_announcement_readiness,
    main,
)


NOW = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)


def test_absent_authorization_is_explicit_and_never_calls_or_writes() -> None:
    value = build_kucoin_announcement_readiness(environ={}, now=NOW)

    assert value["status"] == "blocked"
    assert value["ready"] is False
    assert value["checked_at"] == "2026-07-19T02:00:00Z"
    assert value["runtime_authorization_env"] == LIVE_AUTH_ENV
    assert value["runtime_provider_authorized"] is False
    assert value["authorization_mutated"] is False
    assert value["reasons"] == [
        "runtime_provider_authorization_absent",
        "current_uta_immutable_capture_not_implemented",
        "live_capture_transport_not_implemented",
    ]
    assert value["provider_call_planned"] is False
    assert value["provider_call_attempted"] is False
    assert value["provider_request_count"] == 0
    assert value["writes_performed"] is False
    assert value["expected_provider_activity"] == "none_readiness_only"
    assert value["next_safe_command"] == CURRENT_SMOKE_COMMAND
    assert value["current_response_contract_smoke_command"] == CURRENT_SMOKE_COMMAND
    assert value["legacy_capture_smoke_command"] == CAPTURE_SMOKE_COMMAND
    assert value["legacy_response_contract_smoke_command"] == SMOKE_COMMAND
    assert value["operator_action_required"] == AUTHORIZATION_ACTION
    assert value["rollback_disable_command"] == ROLLBACK_COMMAND


def test_present_authorization_cannot_unlock_superseded_or_unimplemented_capture() -> None:
    value = build_kucoin_announcement_readiness(
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
    )

    assert value["runtime_provider_authorized"] is True
    assert value["ready"] is False
    assert value["reasons"] == [
        "current_uta_immutable_capture_not_implemented",
        "live_capture_transport_not_implemented"
    ]
    assert value["provider_contract_configured"] is True
    assert value["current_contract"]["path"] == CURRENT_ANNOUNCEMENTS_PATH
    assert value["current_contract"]["contract_version"] == CURRENT_CONTRACT_VERSION
    assert value["current_contract"]["official_api_doc"] == CURRENT_OFFICIAL_API_DOC
    assert value["current_contract"]["status"] == (
        "offline_fixture_verified_capture_not_implemented"
    )
    assert value["current_contract"]["request_plan"] == value["request_plan"]
    assert value["legacy_contract"]["status"] == (
        "fixture_verified_historical_not_live_eligible"
    )
    assert value["legacy_contract"]["path"] == "/api/v3/announcements"
    assert value["live_capture_configured"] is False
    assert value["immutable_capture_boundary_implemented"] is False
    assert value["legacy_immutable_capture_boundary_implemented"] is True
    assert value["capture_command_available"] is False
    assert value["strict_capture_doctor_implemented"] is False
    assert value["legacy_strict_capture_doctor_implemented"] is True
    assert value["future_capture_command"] == FUTURE_CAPTURE_COMMAND
    assert value["operator_action_required"] == (
        "unset_unreviewed_authorization_and_wait_for_current_UTA_capture_implementation"
    )
    assert value["provider_call_planned"] is False


def test_request_window_and_future_activity_are_exact_and_bounded() -> None:
    value = build_kucoin_announcement_readiness(environ={}, now=NOW)
    plan = value["request_plan"]

    assert value["request_window_start"] == "2026-07-18T02:00:00Z"
    assert value["request_window_end"] == "2026-07-19T02:00:00Z"
    assert value["maximum_provider_request_count"] == 20
    assert value["legacy_maximum_provider_request_count"] == 20
    assert plan["initial_query"]["startTime"] == 1784340000000
    assert plan["initial_query"]["endTime"] == 1784426400000
    assert plan["initial_query"]["pageNumber"] == 1
    assert plan["initial_query"]["pageSize"] == 50
    assert plan["initial_query"]["type"] == "latest-announcements"
    assert plan["initial_query"]["language"] == "en_US"
    assert value[
        "expected_provider_activity_if_future_authorized_capture_is_implemented"
    ] == "between_1_and_20_current_UTA_public_GETs_no_redirects_or_retries"
    assert value["exact_response_input_contract_implemented"] is True
    assert value["legacy_exact_response_input_contract_implemented"] is True
    assert value["redirects_allowed"] is False
    assert value["retries_allowed"] is False
    assert value["alternate_hosts_allowed"] is False
    assert value["proxy_or_vpn_bypass_allowed"] is False


def test_readiness_preserves_all_research_only_boundaries() -> None:
    value = build_kucoin_announcement_readiness(environ={}, now=NOW)

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
