"""Current Protocol-v2 progress must stay separate from frozen audit evidence."""

from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_validation_protocol_v2_progress as progress,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_DOCUMENT_SHA256 = (
    "897b29a85ff38fb19f5c0eda7e8077bf4b3cbc18aa92270e03d3ffe413c8ae4e"
)
FROZEN_IMPLEMENTATION_SHA256 = (
    "78867805252783d887c4a8ee475e34edb289e9bc86aa8582723ba93bcc975e97"
)


def test_current_progress_records_confirmed_venue_and_real_blockers() -> None:
    values = progress.current_progress_values()
    decision = values["confirmed_execution_decision"]

    assert progress.validate_current_progress(values) == []
    assert values["progress_version"].endswith("_v4")
    assert values["as_of"] == "2026-07-19"
    assert values["status"] == "venue_selected_evidence_collection_blocked"
    assert decision["venue_id"] == "bybit"
    assert decision["instrument_mode"] == "usdt_linear_perpetual"
    assert decision["quote_currency"] == "USDT"
    assert decision["data_boundary"] == "public_market_data_only"
    assert decision["exact_eligible_instrument_ids"] == []
    assert decision["exact_eligible_instrument_set_sealed"] is False
    assert decision["credentials_or_private_account_data"] is False
    assert decision["orders_or_execution_or_trading"] is False
    assert "exact_eligible_instrument_set_not_sealed" in values[
        "current_activation_blockers"
    ]
    assert "live_market_temporal_baseline_not_yet_warm" in values[
        "current_activation_blockers"
    ]
    assert (
        "genuine_bybit_rest_funding_open_interest_positioning_capture_absent"
        in values["current_activation_blockers"]
    )
    assert "genuine_bybit_liquidation_stream_capture_absent" in values[
        "current_activation_blockers"
    ]
    liquidation = values["native_liquidation_contract"]
    assert liquidation["transport"] == "public_websocket"
    assert liquidation["topic_template"] == "allLiquidation.{instrument_id}"
    assert liquidation["offline_exact_message_normalizer_implemented"] is True
    assert liquidation["operator_transcript_immutable_import_implemented"] is True
    assert liquidation["operator_import_scope"] == "selected_application_payloads"
    assert liquidation["operator_import_coverage_status"] == "observed_messages_only"
    assert liquidation["operator_import_coverage_complete"] is False
    assert liquidation["project_websocket_listener_implemented"] is False
    assert liquidation["project_transport_capture_implemented"] is False
    assert liquidation["genuine_capture_present"] is False
    assert liquidation["provider_connection_attempted"] is False
    assert liquidation["protocol_v2_evidence_eligible"] is False
    assert "historical_outcome_recovery_incomplete" in values[
        "current_activation_blockers"
    ]
    assert (
        "explicit_human_review_timing_and_source_independence_labels_incomplete"
        in values["current_activation_blockers"]
    )
    assert "execution_venue_not_selected" not in values[
        "current_activation_blockers"
    ]
    assert set(values["safety"].values()) == {0}
    assert values["research_only"] is True


def test_frozen_readiness_files_remain_at_policy_fingerprints() -> None:
    document = REPO_ROOT / "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md"
    implementation = (
        REPO_ROOT
        / "crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2.py"
    )

    assert hashlib.sha256(document.read_bytes()).hexdigest() == FROZEN_DOCUMENT_SHA256
    assert (
        hashlib.sha256(implementation.read_bytes()).hexdigest()
        == FROZEN_IMPLEMENTATION_SHA256
    )
    frozen = progress.current_progress_values()["frozen_readiness_contract"]
    assert frozen["sha256"] == progress.FROZEN_READINESS_SHA256
    assert frozen["mutated"] is False


def test_progress_values_are_defensive_and_digest_is_deterministic() -> None:
    first = progress.current_progress_values()
    second = progress.current_progress_values()
    expected = progress.progress_sha256(second)
    first["current_activation_blockers"].append("invented")

    assert first != second
    assert deepcopy(second) == second
    assert progress.progress_sha256() == expected
    assert progress.canonical_progress_bytes().endswith(b"\n")


def test_progress_validation_fails_closed_on_audit_or_safety_drift() -> None:
    digest_drift = progress.current_progress_values()
    digest_drift["frozen_readiness_contract"]["sha256"] = "0" * 64
    safety_drift = progress.current_progress_values()
    safety_drift["safety"]["provider_calls"] = 1
    venue_drift = progress.current_progress_values()
    venue_drift["confirmed_execution_decision"]["venue_id"] = "other"
    blocker_drift = progress.current_progress_values()
    blocker_drift["current_activation_blockers"] = ["execution_venue_not_selected"]
    command_drift = progress.current_progress_values()
    command_drift["next_safe_commands"] = ["make unsafe-live-call"]
    version_drift = progress.current_progress_values()
    version_drift["progress_version"] = "decision_radar_progress_unknown"
    liquidation_drift = progress.current_progress_values()
    liquidation_drift["native_liquidation_contract"][
        "project_websocket_listener_implemented"
    ] = True

    for mutation in (
        digest_drift,
        safety_drift,
        venue_drift,
        blocker_drift,
        command_drift,
        version_drift,
        liquidation_drift,
    ):
        assert progress.validate_current_progress(mutation)


def test_progress_cli_reads_no_ambient_state_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("current progress must not perform external I/O")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setenv("RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE", "secret")

    before = tuple(tmp_path.iterdir())
    assert progress.main(["--json", "--check"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert tuple(tmp_path.iterdir()) == before == ()
    assert output.err == ""
    assert payload["confirmed_execution_decision"]["venue_id"] == "bybit"
    assert payload["safety"]["provider_calls"] == 0
    assert "secret" not in output.out


def test_progress_human_output_and_make_targets_are_explicit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert progress.main([]) == 0
    output = capsys.readouterr()
    assert "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS" in output.out
    assert "selected_execution_surface=bybit:usdt_linear_perpetual:USDT" in output.out
    assert "eligible_instrument_set=not_yet_sealed" in output.out
    assert "Current unresolved activation blockers:" in output.out
    assert "- exact_eligible_instrument_set_not_sealed" in output.out
    assert (
        "- genuine_bybit_rest_funding_open_interest_positioning_capture_absent"
        in output.out
    )
    assert "- genuine_bybit_liquidation_stream_capture_absent" in output.out
    assert "native_liquidation_surface=public_websocket:" in output.out
    assert "offline_normalizer=true detached_import=true" in output.out
    assert "project_listener=false project_transport_capture=false" in output.out
    assert "genuine_capture=false coverage=observed_messages_only" in output.out
    assert "offline/readiness/queue only; no provider calls" in output.out
    assert "radar-derivatives-bybit-liquidation-smoke" in output.out
    assert "radar-derivatives-bybit-liquidation-capture-smoke" in output.out
    assert "radar-outcome-price-recovery-readiness" in output.out
    assert "event-alpha-source-independence-oos-readiness" in output.out
    assert "provider_calls=0" in output.out

    rendered = []
    for target in (
        "radar-research-protocol-v2-progress",
        "radar-research-protocol-v2-progress-check",
    ):
        completed = subprocess.run(
            ["make", "-n", target, "PYTHON=python3"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rendered.append(completed.stdout)
    assert all("empirical_validation_protocol_v2_progress" in row for row in rendered)
    assert "--check" not in rendered[0]
    assert rendered[1].count("--check") == 1
    assert "provider" not in "\n".join(rendered).casefold()


def test_primary_readiness_target_leads_with_current_progress() -> None:
    completed = subprocess.run(
        ["make", "radar-research-protocol-v2-readiness", "PYTHON=python3"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    current_at = completed.stdout.index(
        "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS"
    )
    frozen_at = completed.stdout.index("DECISION RADAR EMPIRICAL PROTOCOL V2 READINESS")

    assert current_at < frozen_at
    assert "selected_execution_surface=bybit:usdt_linear_perpetual:USDT" in (
        completed.stdout
    )
    assert "execution_venue_not_selected" in completed.stdout[frozen_at:]
    assert "provider_calls=0" in completed.stdout
