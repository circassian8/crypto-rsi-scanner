"""Exact-attempt receipt tests for the live no-send Make workflow."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_attempt
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign
from crypto_rsi_scanner.event_alpha.dashboard.readiness import CURRENT_NAMESPACE_POINTER


def _configure_live_test(monkeypatch, artifact_base) -> None:
    monkeypatch.setenv(market_no_send.LIVE_AUTH_ENV, "1")
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)
    monkeypatch.setattr(
        market_no_send.config,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        artifact_base,
    )


def _attempt_result(
    namespace: str,
    *,
    status: str,
    observed_at: str,
    run_id: str | None = None,
    provider: str = "coingecko",
    failure_class: str | None = None,
) -> market_no_send.MarketNoSendGenerationResult:
    complete = status == "complete"
    return market_no_send.MarketNoSendGenerationResult(
        status=status,
        profile="no_key_live",
        artifact_namespace=namespace,
        namespace_dir=None,
        data_mode="live",
        provider=provider,
        observed_at=observed_at,
        live_provider_authorized=True,
        provider_call_attempted=complete,
        provider_request_succeeded=complete,
        run_id=run_id,
        failure_class=failure_class,
        data_acquisition_mode="live_provider" if complete else "preflight_only",
        candidate_source_mode="live_no_send" if complete else "preflight_only",
        provenance_contract_valid=complete,
        decision_radar_campaign_eligible=complete,
        decision_radar_campaign_counted=complete,
    )


def test_blocked_cli_attempt_cannot_reuse_an_older_complete_manifest(tmp_path, monkeypatch):
    namespace = "market_attempt"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir()
    old = {
        "status": "complete",
        "artifact_namespace": namespace,
        "run_id": "old-run",
        "observed_at": "2026-07-12T10:00:00+00:00",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "candidate_source_mode": "live_no_send",
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "decision_radar_campaign_counted": True,
        "burn_in_counted": False,
    }
    (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).write_text(
        json.dumps(old), encoding="utf-8"
    )
    (tmp_path / market_no_send_attempt.LATEST_ATTEMPT_FILENAME).write_text(
        json.dumps({
            "contract_version": 1,
            "row_type": "event_market_no_send_latest_attempt",
            **old,
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv(market_no_send.LIVE_AUTH_ENV, raising=False)
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)

    exit_code = market_no_send_cli.main([
        "run", "--artifact-base", str(tmp_path), "--namespace", namespace,
    ])
    status = market_no_send.market_no_send_generation_status(tmp_path, namespace)
    receipt = json.loads(
        (tmp_path / market_no_send_attempt.LATEST_ATTEMPT_FILENAME).read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert receipt["status"] == "blocked"
    assert receipt["provider_call_attempted"] is False
    assert status["complete"] is False
    assert status["exact_latest_attempt"] is False


def test_exact_status_requires_receipt_and_manifest_identity_match(tmp_path):
    namespace = "market_attempt"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir()
    manifest = {
        "status": "complete",
        "run_id": "current-run",
        "observed_at": "2026-07-12T12:00:00+00:00",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "candidate_source_mode": "live_no_send",
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "decision_radar_campaign_counted": True,
        "burn_in_counted": False,
    }
    (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    receipt = {
        "contract_version": 1,
        "row_type": "event_market_no_send_latest_attempt",
        "artifact_namespace": namespace,
        **manifest,
    }
    (tmp_path / market_no_send_attempt.LATEST_ATTEMPT_FILENAME).write_text(
        json.dumps(receipt), encoding="utf-8"
    )

    exact = market_no_send.market_no_send_generation_status(tmp_path, namespace)
    receipt["run_id"] = "stale-run"
    (tmp_path / market_no_send_attempt.LATEST_ATTEMPT_FILENAME).write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    drifted = market_no_send.market_no_send_generation_status(tmp_path, namespace)

    assert exact["complete"] is True
    assert exact["decision_radar_campaign_counted"] is True
    assert exact["burn_in_counted"] is False
    assert drifted["complete"] is False
    assert drifted["exact_latest_attempt"] is False


def test_current_authority_namespace_blocks_before_live_provider_call(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    namespace = "current_market_authority"
    pointer = {
        "contract_version": 1,
        "artifact_namespace": namespace,
        "profile": "no_key_live",
        "run_id": "current-run",
        "revision": 2,
        "operator_state_sha256": "a" * 64,
        "generation_authority_status": "authoritative",
        "authority_checked_at": datetime.now(timezone.utc).isoformat(),
    }
    (tmp_path / CURRENT_NAMESPACE_POINTER).write_text(json.dumps(pointer), encoding="utf-8")
    calls = 0

    def forbidden(_limit):
        nonlocal calls
        calls += 1
        return ()

    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        provider=forbidden,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )

    assert readiness.ready is False
    assert readiness.will_call_provider is False
    assert "<new-generation>" in readiness.next_safe_command
    assert result.status == "blocked"
    assert result.provider_call_attempted is False
    assert calls == 0


def test_existing_generation_namespace_is_single_use_before_live_provider_call(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    namespace = "used_market_generation"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir()
    (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).write_text(
        '{"status":"failed"}\n',
        encoding="utf-8",
    )
    calls = 0

    def forbidden(_limit):
        nonlocal calls
        calls += 1
        return ()

    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        provider=forbidden,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )

    assert readiness.ready is False
    assert readiness.will_call_provider is False
    assert "<new-generation>" in readiness.next_safe_command
    assert result.status == "blocked"
    assert result.provider_call_attempted is False
    assert calls == 0


def test_attempt_history_retains_blocked_runs_then_success_and_latest_is_exact(tmp_path):
    namespace = "market_attempt_history"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir()
    observed_at = "2026-07-13T18:00:00+00:00"
    results = (
        _attempt_result(
            namespace,
            status="blocked",
            observed_at=observed_at,
            failure_class="cadence_wait",
        ),
        _attempt_result(
            namespace,
            status="blocked",
            observed_at=observed_at,
            provider="coingecko_secret_token_do-not-store",
            failure_class="bearer_secret_token_do-not-store",
        ),
        _attempt_result(
            namespace,
            status="complete",
            observed_at="2026-07-13T19:00:00+00:00",
            run_id="2026-07-13T19:00:00+00:00|no_key_live",
        ),
    )
    manifest = {
        "status": "complete",
        "run_id": results[-1].run_id,
        "observed_at": results[-1].observed_at,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "candidate_source_mode": "live_no_send",
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "decision_radar_campaign_counted": True,
        "burn_in_counted": False,
    }
    (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    for result in results:
        market_no_send_attempt.record_attempt(tmp_path, namespace, result)

    ledger_text = (tmp_path / market_no_send_attempt.ATTEMPT_LEDGER_FILENAME).read_text(
        encoding="utf-8"
    )
    ledger = [json.loads(line) for line in ledger_text.splitlines() if line.strip()]
    latest = json.loads(
        (tmp_path / market_no_send_attempt.LATEST_ATTEMPT_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    campaign_attempts = market_observation_campaign._deduplicate_attempts(
        market_observation_campaign._load_root_attempts(tmp_path)
    )
    exact = market_no_send_attempt.exact_generation_status(
        tmp_path,
        namespace,
        manifest_filename=market_no_send.RUN_MANIFEST_FILENAME,
    )

    assert [row["status"] for row in ledger] == ["blocked", "blocked", "complete"]
    assert len({row["attempt_id"] for row in ledger}) == 3
    assert all(row["row_type"] == "event_market_no_send_attempt" for row in ledger)
    assert "do-not-store" not in ledger_text
    assert "secret_token" not in ledger_text
    assert ledger[1]["provider"] == "unknown"
    assert ledger[1]["failure_class"] == "redacted_provider_error"
    assert latest["attempt_id"] == ledger[-1]["attempt_id"]
    assert latest["run_id"] == results[-1].run_id
    assert latest["row_type"] == "event_market_no_send_latest_attempt"
    assert len(campaign_attempts) == 3
    assert exact["exact_latest_attempt"] is True


def test_attempt_history_is_bounded_to_newest_rows(tmp_path, monkeypatch):
    namespace = "market_attempt_bounded"
    monkeypatch.setattr(market_no_send_attempt, "ATTEMPT_LEDGER_MAX_ROWS", 3)

    for index in range(5):
        market_no_send_attempt.record_attempt(
            tmp_path,
            namespace,
            _attempt_result(
                namespace,
                status="blocked",
                observed_at=f"2026-07-13T{index:02d}:00:00+00:00",
                failure_class=f"blocked_{index}",
            ),
        )

    ledger = [
        json.loads(line)
        for line in (tmp_path / market_no_send_attempt.ATTEMPT_LEDGER_FILENAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert [row["failure_class"] for row in ledger] == [
        "blocked_2",
        "blocked_3",
        "blocked_4",
    ]


def test_live_cli_boundary_failure_is_sanitized_and_retained(
    tmp_path,
    monkeypatch,
    capsys,
):
    _configure_live_test(monkeypatch, tmp_path)

    def fail_before_result(**_kwargs):
        raise RuntimeError("bearer token SECRET_VALUE must never be persisted")

    monkeypatch.setattr(
        market_no_send,
        "run_market_no_send_generation",
        fail_before_result,
    )
    status = market_no_send_cli.main([
        "run",
        "--artifact-base",
        str(tmp_path),
        "--namespace",
        "boundary_failure",
    ])

    stderr = capsys.readouterr().err
    ledger_text = (
        tmp_path / market_no_send_attempt.ATTEMPT_LEDGER_FILENAME
    ).read_text(encoding="utf-8")
    row = json.loads(ledger_text.strip())
    assert status == 1
    assert "SECRET_VALUE" not in stderr
    assert "bearer token" not in stderr
    assert row["status"] == "boundary_failed"
    assert row["failure_class"] == "RuntimeError"
    assert "SECRET_VALUE" not in ledger_text


def test_boundary_failure_counts_a_pre_network_reservation_without_a_manifest(
    tmp_path,
):
    namespace = "reserved_boundary_failure"
    attempted = datetime.now(timezone.utc).replace(microsecond=0)
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace=namespace,
        acquired_at=attempted,
    ) as reservation:
        market_no_send_campaign_guard.mark_provider_call_reserved(
            reservation,
            attempted_at=attempted,
            minimum_spacing=timedelta(hours=1),
        )

    market_no_send_attempt.record_boundary_failure(
        tmp_path,
        namespace,
        failure=RuntimeError("post-provider artifact failure"),
        manifest_filename=market_no_send.RUN_MANIFEST_FILENAME,
    )
    row = json.loads(
        (tmp_path / market_no_send_attempt.ATTEMPT_LEDGER_FILENAME)
        .read_text(encoding="utf-8")
        .strip()
    )
    assert row["status"] == "boundary_failed"
    assert row["provider_call_attempted"] is True
    assert row["provider_request_succeeded"] is False
    assert row["data_acquisition_mode"] == "live_provider"


def test_boundary_failure_does_not_create_noncanonical_artifact_base(
    tmp_path,
    monkeypatch,
):
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    requested = tmp_path / "noncanonical"
    _configure_live_test(monkeypatch, canonical)
    monkeypatch.setattr(
        market_no_send,
        "run_market_no_send_generation",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("failure")),
    )

    status = market_no_send_cli.main([
        "run", "--artifact-base", str(requested), "--namespace", "boundary_failure",
    ])

    assert status == 1
    assert not requested.exists()
    assert not (canonical / market_no_send_attempt.ATTEMPT_LEDGER_FILENAME).exists()


@pytest.mark.parametrize("command", ("run", "publish", "readiness", "status"))
def test_operational_cli_rejects_injected_observation_clock(command):
    with pytest.raises(SystemExit):
        market_no_send_cli._parser().parse_args([
            command,
            "--observed-at",
            "2020-01-01T00:00:00Z",
        ])
