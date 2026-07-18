"""Closed reconciliation tests for campaign attempt audit representations."""

from __future__ import annotations

import json

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign as campaign,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendError,
)
from tests.event_alpha import test_market_observation_campaign as campaign_test


def _attempt(
    *,
    attempt_id: str | None,
    run_id: str | None,
    succeeded: bool = False,
) -> dict[str, object]:
    return {
        "attempt_id": attempt_id,
        "artifact_namespace": "radar_market_no_send_failed",
        "run_id": run_id,
        "observed_at": "2026-07-18T01:47:01.192491+00:00",
        "attempt_status": "provider_unavailable",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_request_succeeded": succeeded,
        "failure_class": "ClientConnectorDNSError",
        "candidate_source_mode": "live_no_send",
        "no_send": True,
        "research_only": True,
    }


def test_attempt_reconciliation_enriches_one_unique_root_receipt():
    receipt = _attempt(attempt_id="attempt-1", run_id=None)
    namespace = _attempt(
        attempt_id=None,
        run_id="2026-07-18T01:47:01.192491+00:00|no_key_live",
    )

    forward = campaign._deduplicate_attempts([receipt, namespace])
    reverse = campaign._deduplicate_attempts([namespace, receipt])

    assert forward == reverse
    assert len(forward) == 1
    assert forward[0]["attempt_id"] == "attempt-1"
    assert forward[0]["run_id"] == (
        "2026-07-18T01:47:01.192491+00:00|no_key_live"
    )


def test_attempt_reconciliation_rejects_conflicting_same_id():
    receipt = _attempt(attempt_id="attempt-1", run_id=None)
    contradiction = _attempt(attempt_id="attempt-1", run_id=None, succeeded=True)

    with pytest.raises(MarketNoSendError, match="representations conflict"):
        campaign._deduplicate_attempts([receipt, contradiction])


def test_attempt_reconciliation_rejects_conflicting_namespace_projection():
    receipt = _attempt(attempt_id="attempt-1", run_id=None)
    contradiction = _attempt(attempt_id=None, run_id=None, succeeded=True)

    with pytest.raises(MarketNoSendError, match="representations conflict"):
        campaign._deduplicate_attempts([receipt, contradiction])


def test_attempt_reconciliation_rejects_ambiguous_namespace_projection():
    first = _attempt(attempt_id="attempt-1", run_id=None)
    second = _attempt(attempt_id="attempt-2", run_id=None)
    namespace = _attempt(
        attempt_id=None,
        run_id="2026-07-18T01:47:01.192491+00:00|no_key_live",
    )

    with pytest.raises(MarketNoSendError, match="projection is ambiguous"):
        campaign._deduplicate_attempts([first, second, namespace])


def test_campaign_report_counts_one_cross_artifact_failed_attempt(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    campaign_test._fixture(base)
    manifest_path = base / "radar_market_no_send_failed" / campaign.RUN_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = "2026-07-13T16:30:00+00:00|no_key_live"
    campaign_test._write_json(manifest_path, manifest)
    failed_attempt = {
        "attempt_id": "failed-attempt-id",
        "artifact_namespace": "radar_market_no_send_failed",
        "status": "failed",
        "observed_at": "2026-07-13T16:30:00+00:00",
        "run_id": None,
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_request_succeeded": False,
        "failure_class": "http_error",
        "candidate_source_mode": "live_no_send",
        "no_send": True,
        "research_only": True,
        "row_type": "event_market_no_send_attempt",
    }
    campaign_test._write_jsonl(
        base / "event_market_no_send_attempts.jsonl",
        [failed_attempt],
    )
    campaign_test._write_json(
        base / "event_market_no_send_latest_attempt.json",
        {**failed_attempt, "row_type": "event_market_no_send_latest_attempt"},
    )
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        campaign_test._readiness,
    )
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        campaign_test._dashboard_authority,
    )

    report = campaign.build_campaign_report(
        base,
        evaluated_at=campaign_test._EVALUATED,
    )

    assert report["campaign_metrics"]["provider_failed_attempts"] == 1
    assert len(report["provider_failed_attempts"]) == 1
    assert report["provider_failed_attempts"][0]["attempt_id"] == "failed-attempt-id"
    assert report["provider_failed_attempts"][0]["run_id"] == (
        "2026-07-13T16:30:00+00:00|no_key_live"
    )
