"""Exact-attempt receipt tests for the live no-send Make workflow."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_attempt
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli
from crypto_rsi_scanner.event_alpha.dashboard.readiness import CURRENT_NAMESPACE_POINTER


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
        "burn_in_counted": True,
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
        "burn_in_counted": True,
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
    assert exact["burn_in_counted"] is True
    assert drifted["complete"] is False
    assert drifted["exact_latest_attempt"] is False


def test_current_authority_namespace_blocks_before_live_provider_call(tmp_path):
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
