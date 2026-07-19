"""Static Tokenomist v5 readiness boundary regressions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.tokenomist_v5_readiness import (
    BLOCKERS,
    CAPTURE_SMOKE_COMMAND,
    FUTURE_CAPTURE_COMMAND,
    LIVE_AUTH_ENV,
    READINESS_COMMAND,
    RESPONSE_SMOKE_COMMAND,
    ROLLBACK_COMMAND,
    build_tokenomist_v5_readiness,
    main,
)


NOW = datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc)
NORTH_STAR_JSON = (
    Path(__file__).resolve().parents[2]
    / "research"
    / "CRYPTO_DECISION_RADAR_NORTH_STAR.json"
)


def test_readiness_is_static_blocked_and_non_activating() -> None:
    value = build_tokenomist_v5_readiness(environ={}, now=NOW)

    assert value["status"] == "blocked"
    assert value["ready"] is False
    assert value["checked_at"] == "2026-07-19T16:00:00Z"
    assert value["blockers"] == [
        "live_transport_not_implemented",
        "runtime_provider_authorization_absent",
        "provider_subscription_not_selected_or_authorized",
        "genuine_response_retention_and_redistribution_review_pending",
    ]
    assert value["live_transport_implemented"] is False
    assert value["legacy_provider_api_version"] == "v4"
    assert value["legacy_v4_status"] == "deprecated"
    assert value["legacy_v4_live_eligible"] is False
    assert value["completion_evidence"] == {
        "v5_response_contract": "fixture_closed",
        "v5_immutable_capture_contract": "fixture_closed_strict_doctor",
        "live_transport": "not_implemented",
        "genuine_provider_capture": "absent",
    }
    assert value["provider_subscription_status"] == "not_selected_or_authorized"
    assert value["runtime_authorization_env"] == LIVE_AUTH_ENV
    assert value["runtime_authorization_boundary_defined"] is True
    assert value["runtime_provider_authorized"] is False
    assert value["authorization_checked"] is True
    assert value["retention_terms_reviewed"] is False
    assert value["redistribution_terms_reviewed"] is False
    assert value["request_plan_created"] is False
    assert value["provider_call_planned"] is False
    assert value["provider_call_attempted"] is False
    assert value["provider_request_count"] == 0
    assert value["environment_reads"] == 1
    assert value["environment_authorization_reads"] == 1
    assert value["environment_credential_reads"] == 0
    assert value["credential_presence_inspected"] is False
    assert value["credential_values_read"] is False
    assert value["writes_performed"] is False


def test_readiness_exposes_only_safe_offline_next_action() -> None:
    value = build_tokenomist_v5_readiness(environ={}, now=NOW)

    assert value["next_safe_command"] == CAPTURE_SMOKE_COMMAND
    assert value["capture_smoke_command"] == CAPTURE_SMOKE_COMMAND
    assert value["response_contract_smoke_command"] == RESPONSE_SMOKE_COMMAND
    assert value["readiness_recheck_command"] == READINESS_COMMAND
    assert value["future_capture_command"] == FUTURE_CAPTURE_COMMAND
    assert value["live_capture_command_available"] is False
    assert LIVE_AUTH_ENV in value["authorization_boundary"]
    assert value["expected_provider_activity"] == "none_readiness_only"
    assert value["rollback_disable_command"] == ROLLBACK_COMMAND


def test_present_authorization_never_unlocks_missing_subscription_transport_or_retention() -> None:
    value = build_tokenomist_v5_readiness(
        environ={LIVE_AUTH_ENV: "true"},
        now=NOW,
    )

    assert value["runtime_provider_authorized"] is True
    assert value["ready"] is False
    assert value["blockers"] == list(BLOCKERS)
    assert value["provider_call_planned"] is False
    assert value["provider_call_attempted"] is False
    assert value["provider_request_count"] == 0


def test_unrelated_secret_environment_is_never_read_or_rendered() -> None:
    secret = "sk-proj-this-value-must-never-appear"
    value = build_tokenomist_v5_readiness(
        environ={
            LIVE_AUTH_ENV: "false",
            "TOKENOMIST_API_KEY": secret,
            "UNRELATED_PROVIDER_SECRET": "private-token-value",
        },
        now=NOW,
    )

    rendered = json.dumps(value, sort_keys=True)
    assert secret not in rendered
    assert "private-token-value" not in rendered
    assert "TOKENOMIST_API_KEY" not in rendered
    assert value["environment_reads"] == 1
    assert value["environment_credential_reads"] == 0
    assert value["credential_values_read"] is False


def test_readiness_preserves_all_detached_research_boundaries() -> None:
    value = build_tokenomist_v5_readiness(environ={}, now=NOW)

    assert value["latest_pointer_available"] is False
    assert value["latest_pointer_published"] is False
    assert value["campaign_attached"] is False
    assert value["dashboard_authority_eligible"] is False
    assert value["source_authority_eligible"] is False
    assert value["directional_authority"] is False
    assert value["decision_policy_applied"] is False
    assert value["protocol_v2_annex_bound"] is False
    assert value["protocol_v2_evidence_eligible"] is False
    assert value["research_only"] is True
    assert value["no_send"] is True
    assert value["orders_available"] is False
    assert value["trades_created"] == 0
    assert value["paper_trades_created"] == 0
    assert value["normal_rsi_signal_rows_written"] == 0
    assert value["triggered_fade_created"] == 0
    assert value["telegram_sends"] == 0


def test_cli_uses_no_network_and_renders_same_blocked_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert "live_transport_not_implemented" in value["blockers"]
    assert value["provider_call_attempted"] is False
    assert value["writes_performed"] is False


def test_makefile_exposes_only_offline_tokenomist_operator_targets() -> None:
    text = (Path(__file__).resolve().parents[2] / "Makefile").read_text()

    assert "radar-unlock-tokenomist-v5-smoke:" in text
    assert "radar-unlock-tokenomist-v5-capture-smoke:" in text
    assert "radar-unlock-tokenomist-v5-readiness:" in text
    assert "radar-unlock-tokenomist-v5-capture:" not in text
    assert "radar-unlock-tokenomist-v5-collect:" not in text


def test_north_star_records_fixture_only_unlock_boundary() -> None:
    payload = json.loads(NORTH_STAR_JSON.read_text(encoding="utf-8"))
    readiness = payload["structured_unlock_readiness"]
    decision = payload["operator_decisions"][
        "structured_unlock_subscription_and_capture"
    ]

    assert readiness["provider"] == "tokenomist"
    assert readiness["provider_api_version"] == "v5"
    assert readiness["legacy_v4_status"] == "deprecated_and_live_ineligible"
    assert readiness["response_contract_implemented"] is True
    assert readiness["fixture_capture_contract_implemented"] is True
    assert readiness["strict_fixture_capture_doctor_implemented"] is True
    assert readiness["fixture_capture_retained"] is False
    assert readiness["full_multipage_capture_contract_implemented"] is False
    assert readiness["live_transport_implemented"] is False
    assert readiness["genuine_provider_capture_present"] is False
    assert readiness["latest_pointer_published"] is False
    assert readiness["source_authority_eligible"] is False
    assert readiness["protocol_v2_input_quality_eligible"] is False
    assert readiness["decision_policy_applied"] is False
    assert readiness["protocol_v2_evidence_eligible"] is False
    assert readiness["readiness_provider_calls"] == 0
    assert decision["current_status"] == (
        "fixture_contract_closed_live_transport_and_subscription_unapproved"
    )
    assert decision["next_safe_command"].startswith(
        "make radar-unlock-tokenomist-v5-capture-smoke"
    )
    assert "RSI_DECISION_RADAR_TOKENOMIST_V5_LIVE" in decision[
        "authorization_boundary"
    ]
