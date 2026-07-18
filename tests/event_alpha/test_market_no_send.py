"""Guarded market-led no-send generation and pointer publication tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    DashboardReadinessError,
    publish_current_namespace_pointer,
    read_current_namespace_pointer,
    resolve_authoritative_dashboard,
)
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_calendar
from crypto_rsi_scanner.event_alpha.operations import market_no_send_features
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli


_OBSERVED = "2026-07-12T12:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _clear_context_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def _configure_live_test(monkeypatch: pytest.MonkeyPatch, artifact_base: Path, *, fixture_dir=None) -> None:
    _clear_context_overrides(monkeypatch)
    monkeypatch.setenv(market_no_send.LIVE_AUTH_ENV, "1")
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(market_no_send.config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", artifact_base)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_valid_pointer(base: Path, *, namespace: str = "previous_authority") -> bytes:
    payload = {
        "contract_version": 1,
        "artifact_namespace": namespace,
        "profile": "fixture",
        "run_id": "previous-run",
        "revision": 1,
        "operator_state_sha256": "a" * 64,
        "generation_authority_status": "authoritative",
        "authority_checked_at": _OBSERVED,
    }
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    (base / CURRENT_NAMESPACE_POINTER).write_bytes(data)
    return data


def test_injected_environment_cannot_authorize_or_call_live_provider(
    tmp_path,
    monkeypatch,
):
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    pointer = artifact_base / CURRENT_NAMESPACE_POINTER
    pointer_before = _write_valid_pointer(artifact_base)
    calls = 0
    monkeypatch.delenv(market_no_send.LIVE_AUTH_ENV, raising=False)
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)
    monkeypatch.setattr(market_no_send.config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", artifact_base)

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("provider must not be called")

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=artifact_base,
        artifact_namespace="blocked_no_auth",
        top_n=5,
        provider=forbidden_provider,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        observed_at=_OBSERVED,
    )

    assert result.status == "blocked"
    assert result.live_provider_authorized is False
    assert result.provider_call_attempted is False
    assert result.provider_request_succeeded is False
    assert result.namespace_dir is None
    assert calls == 0
    assert pointer.read_bytes() == pointer_before
    assert not (artifact_base / "blocked_no_auth").exists()


def test_noncanonical_live_artifact_base_blocks_before_provider_call(
    tmp_path,
    monkeypatch,
):
    canonical_base = tmp_path / "canonical"
    requested_base = tmp_path / "other"
    canonical_base.mkdir()
    requested_base.mkdir()
    _configure_live_test(monkeypatch, canonical_base)
    calls = 0

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("noncanonical live base must block before provider call")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", forbidden_provider)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=requested_base,
        artifact_namespace="noncanonical_live_base",
        top_n=5,
        observed_at=_OBSERVED,
    )

    assert result.status == "blocked"
    assert result.failure_class == "noncanonical_artifact_base"
    assert result.provider_call_attempted is False
    assert calls == 0
    assert not (requested_base / "noncanonical_live_base").exists()


def test_unauthorized_cli_attempt_is_successful_and_writes_safe_audit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(market_no_send.LIVE_AUTH_ENV, raising=False)
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)

    status = market_no_send_cli.main([
        "run",
        "--artifact-base", str(tmp_path),
        "--namespace", "blocked_pilot",
        "--top-n", "5",
    ])

    assert status == 0
    audit = json.loads(
        (tmp_path / market_no_send.PILOT_AUDIT_JSON_FILENAME).read_text(encoding="utf-8")
    )
    assert audit["attempt_status"] == "blocked"
    assert audit["provider_call_attempted"] is False
    assert audit["provider_request_succeeded"] is False
    assert audit["candidate_source_mode"] == "preflight_only"
    assert audit["publication"]["status"] == "not_attempted"
    assert market_no_send.LIVE_AUTH_ENV in audit["next_safe_command"]
    assert "make radar-daily-ops-cycle" in audit["next_safe_command"]


def test_fixture_mode_blocks_live_claim_before_provider_call(tmp_path, monkeypatch):
    calls = 0

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        return []

    artifact_base = tmp_path / "artifacts"
    _configure_live_test(monkeypatch, artifact_base, fixture_dir=tmp_path / "fixtures")
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=artifact_base,
        artifact_namespace="blocked_fixture",
        top_n=5,
        provider=forbidden_provider,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=tmp_path / "fixtures",
        observed_at=_OBSERVED,
    )

    assert result.status == "blocked"
    assert result.live_provider_authorized is True
    assert result.provider_call_attempted is False
    assert calls == 0


def test_cadence_blocked_generation_never_calls_provider_or_changes_pointer(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    history_dir = tmp_path / market_no_send.market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir(parents=True)
    market_no_send_io.write_jsonl(history_dir / market_no_send.HISTORY_FILENAME, [{
        "schema_id": "event_alpha.market_history_observation",
        "schema_version": 1,
        "canonical_asset_id": "bitcoin",
        "coin_id": "bitcoin",
        "symbol": "BTC",
        "observed_at": observed.isoformat(),
        "observation_id": "mhobs-cadence-test",
        "price": 100_000.0,
        "volume_24h": 1_000_000_000.0,
        "turnover_24h": 0.05,
        "source": "coingecko",
        "provider": "coingecko",
        "research_only": True,
    }])
    pointer_before = _write_valid_pointer(tmp_path)
    calls = 0

    def forbidden(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("cadence gate must run before the provider")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", forbidden)
    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="cadence_blocked",
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        now=observed + timedelta(minutes=10),
    )
    assert readiness.status == "blocked"
    assert readiness.cadence_status == "waiting"
    assert readiness.next_eligible_observation_at == (
        observed + timedelta(hours=1)
    ).isoformat()

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="cadence_blocked",
        top_n=5,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        observed_at=observed + timedelta(hours=2),
    )
    assert result.status == "blocked"
    assert result.provider_call_attempted is False
    assert calls == 0
    assert (tmp_path / CURRENT_NAMESPACE_POINTER).read_bytes() == pointer_before
    assert not (tmp_path / "cadence_blocked").exists()


def test_malformed_live_history_cache_blocks_before_provider_call(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    history_dir = (
        tmp_path
        / market_no_send.market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
    )
    history_dir.mkdir()
    (history_dir / market_no_send.HISTORY_FILENAME).write_text(
        "{malformed-json\n",
        encoding="utf-8",
    )
    calls = 0

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("invalid history must block before provider call")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", forbidden_provider)
    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="invalid_history",
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="invalid_history",
        top_n=5,
    )

    assert readiness.ready is False
    assert readiness.cache_status == "invalid"
    assert readiness.cache_error == "shared market history is invalid"
    assert result.status == "blocked"
    assert result.provider_call_attempted is False
    assert calls == 0
    assert not (tmp_path / "invalid_history").exists()


def test_live_observed_at_argument_cannot_backdate_provider_evidence(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    monkeypatch.setattr(
        market_no_send,
        "_fetch_live_coingecko_rows",
        lambda _limit: market_no_send._smoke_rows(),
    )
    started_at = datetime.now(timezone.utc)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="live_clock_guard",
        top_n=5,
        observed_at="2000-01-01T00:00:00+00:00",
    )

    assert result.complete is True
    result_observed_at = datetime.fromisoformat(result.observed_at)
    assert result_observed_at >= started_at
    assert result_observed_at != datetime(2000, 1, 1, tzinfo=timezone.utc)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["observed_at"] == result.observed_at


def test_mocked_fresh_market_data_builds_market_led_ideas_and_blocks_low_liquidity(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="market_mock",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )

    assert result.complete is True
    assert result.market_anomalies == 3
    assert result.candidates == 3
    assert result.core_rows == 2
    namespace_dir = tmp_path / "market_mock"
    rows = _jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl")
    by_symbol = {str(row["symbol"]): row for row in rows}

    spread_verified = by_symbol["MKTFLOW"]
    assert spread_verified["primary_thesis_origin"] == "market_led"
    assert spread_verified["catalyst_status"] == "unknown"
    assert spread_verified["radar_actionable"] is True
    assert spread_verified["radar_route"] in {
        "actionable_watch",
        "high_confidence_watch",
        "rapid_market_anomaly",
    }

    no_spread = by_symbol["MKTNOSPREAD"]
    assert no_spread["primary_thesis_origin"] == "market_led"
    assert no_spread["spread_status"] == "unavailable"
    assert no_spread["radar_route"] == "dashboard_watch"
    assert no_spread["radar_actionable"] is False

    low_liquidity = by_symbol["MKTLOW"]
    assert low_liquidity["radar_route"] == "diagnostic"
    assert low_liquidity["radar_actionable"] is False
    assert low_liquidity["market_snapshot"]["liquidity_usd"] == 18_000.0
    assert low_liquidity["market_snapshot"]["spread_bps"] == 320.0

    manifest = json.loads(
        (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    request = json.loads(
        (namespace_dir / market_no_send.REQUEST_CACHE_FILENAME).read_text(encoding="utf-8")
    )
    request_ledger = json.loads(
        (namespace_dir / market_no_send.REQUEST_LEDGER_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["data_mode"] == "mock"
    assert manifest["provider"] == "mock_coingecko"
    assert manifest["contract_counted_status"] == "not_counted"
    assert manifest["candidate_source_mode"] == "mocked_fixture"
    assert manifest["burn_in_eligible"] is False
    assert manifest["burn_in_counted"] is False
    assert manifest["no_send"] is True
    assert manifest["pointer_published"] is False
    assert request["observed_at"] == _OBSERVED
    assert request["contract_counted_status"] == "not_counted"
    assert all(request[field] == 0 for field in market_no_send._SAFETY_COUNTERS)
    assert request_ledger["endpoint_path"] == "/coins/markets"
    assert request_ledger["duration_ms"] == 0
    assert request_ledger["http_status"] is None
    assert request_ledger["result_count"] == len(market_no_send._smoke_rows())
    assert request_ledger["retry_count"] == 0
    assert request_ledger["error_class"] is None
    assert request_ledger["cache_behavior"] == "mocked_fixture"
    assert all(
        row["provider_source_artifact"] == market_no_send.REQUEST_CACHE_FILENAME
        for row in request["rows"]
    )
    operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    provenance = operator_state["market_no_send_provenance"]
    assert provenance["data_acquisition_mode"] == "mocked_fixture"
    assert provenance["provider"] == "mock_coingecko"
    assert provenance["provider_source_artifact"] == market_no_send.REQUEST_CACHE_FILENAME
    assert provenance["request_ledger_path"] == market_no_send.REQUEST_LEDGER_FILENAME
    assert provenance["candidate_source_mode"] == "mocked_fixture"
    assert provenance["burn_in_eligible"] is False
    assert provenance["burn_in_counted"] is False
    assert provenance["measurement_program"] == "decision_radar_live_observation_campaign_v2"
    assert provenance["decision_radar_campaign_counted"] is False
    assert provenance["provenance_contract_valid"] is True
    assert operator_state["send_attempted"] is False
    assert schema_v1.validate_row_against_schema(operator_state, "operator_state_v1") == []
    assert {
        "market_no_send_source_cache",
        "market_no_send_request_ledger",
        "market_no_send_generation",
        "integrated_candidates",
        "integrated_outcomes",
    }.issubset(operator_state["artifacts"])
    _json_path, _md_path, audit = market_no_send.write_market_no_send_pilot_audit(
        tmp_path,
        "market_mock",
        now=_OBSERVED,
    )
    assert audit["candidate_count"] == result.candidates
    assert audit["outcome_placeholder_count"] == result.candidates
    assert audit["candidate_outcome_count_match"] is True
    assert audit["pilot_audit_contract_version"] == 1
    assert audit["market_provenance_contract_version"] == market_no_send.CONTRACT_VERSION
    assert audit["provider_adapter_invoked"] is True
    assert audit["network_call_attempted"] is False
    assert audit["baseline"]["baseline_observations_per_asset"]
    assert audit["market_observation_quality_scope"] == (
        "exact_generation_market_state_snapshots"
    )
    assert audit["market_observation_quality"] == audit["idea_quality"]
    assert audit["market_observation_quality_source_artifact"] == (
        "event_market_state_snapshots.jsonl"
    )


def test_mock_market_generation_preserves_explicit_calendar_snapshot_end_to_end(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    calendar_path = tmp_path / "calendar-current.json"
    calendar_path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "observed_at": _OBSERVED,
                "source_mode": "operator_verified_calendar_snapshot",
                "data_acquisition_mode": "operator_verified_export",
                "source_provider": "operator_calendar",
                "events": [
                    {
                        "id": "macro-release-1",
                        "title": "Macro liquidity release",
                        "event_kind": "macro",
                        "scheduled_at": "2026-07-20T12:00:00Z",
                        "time_certainty": "exact",
                        "importance": "critical",
                        "affected_assets": ["MKTFLOW"],
                        "source": "operator_calendar",
                        "source_url": "https://example.com/calendar/macro-release-1",
                        "timezone": "UTC",
                        "forecast": 2.5,
                        "previous": 2.2,
                        "impact_window_before": "24h",
                        "impact_window_after": "4h",
                        "research_only": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="market_calendar_mock",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(calendar_path)},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )

    assert result.complete is True
    namespace_dir = tmp_path / "market_calendar_mock"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    calendar_status = manifest["calendar_snapshot"]
    assert calendar_status["status"] == "healthy_nonempty"
    assert calendar_status["retained_row_count"] == 1
    assert calendar_status["scheduled_catalyst_count"] == 1
    assert calendar_status["scheduled_catalyst_artifact_sha256"]
    assert calendar_status["unlock_candidate_count"] == 0
    assert calendar_status["unlock_source_status"] == "not_configured"
    assert calendar_status["normalization_input_count"] == 1
    assert calendar_status["normalization_valid_input_count"] == 1
    assert calendar_status["normalization_rejected_count"] == 0
    assert calendar_status["unified_calendar_artifact_row_count"] == 1
    assert calendar_status["unified_calendar_artifact_sha256"]
    assert calendar_status["copy_artifact_sha256"]
    copied = json.loads(
        (
            namespace_dir / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
        ).read_text(encoding="utf-8")
    )
    assert copied["events"][0]["id"] == "macro-release-1"
    assert copied["canonical_rows_sha256"] == calendar_status["canonical_rows_sha256"]
    assert not (namespace_dir / "event_unlock_candidates.jsonl").exists()
    assert not (namespace_dir / "event_unlock_risk_report.md").exists()

    calendar_rows = _jsonl(namespace_dir / "event_unified_calendar_events.jsonl")
    assert len(calendar_rows) == 1
    calendar_row = calendar_rows[0]
    assert calendar_row["calendar_event_id"] == "macro-release-1"
    assert calendar_row["time_certainty"] == "exact"
    assert calendar_row["importance"] == "critical"
    assert calendar_row["affected_assets"] == ["MKTFLOW"]
    assert calendar_row["forecast_value"] == 2.5
    assert calendar_row["previous_value"] == 2.2

    input_manifest = json.loads(
        (namespace_dir / "event_integrated_radar_input_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    scheduled = next(
        row
        for row in input_manifest["sidecars"]
        if row["sidecar_name"] == "scheduled_catalyst"
    )
    assert scheduled["coverage_status"] == "healthy_nonempty"
    assert scheduled["row_counts"] == {"rows": 1}
    unlock = next(
        row
        for row in input_manifest["sidecars"]
        if row["sidecar_name"] == "unlock"
    )
    assert unlock["coverage_status"] == "not_configured"
    operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    assert operator_state["artifacts"]["market_no_send_calendar_source"]["status"] == "current"


def test_provider_failure_is_fail_soft_and_preserves_dashboard_pointer(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    tmp_path.mkdir(exist_ok=True)
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer_before = _write_valid_pointer(tmp_path)

    calls = 0

    def unavailable(_limit):
        nonlocal calls
        calls += 1
        raise TimeoutError("secret-bearing provider details must not escape")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", unavailable)

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="provider_failure",
        top_n=5,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        observed_at=_OBSERVED,
    )

    assert result.status == "provider_unavailable"
    assert result.failure_class == "TimeoutError"
    assert result.provider_call_attempted is True
    assert result.provider_request_succeeded is False
    assert calls == 1
    assert pointer.read_bytes() == pointer_before
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["failure_class"] == "TimeoutError"
    assert "secret-bearing" not in result.manifest_path.read_text(encoding="utf-8")
    failure_ledger_text = result.request_ledger_path.read_text(encoding="utf-8")
    failure_ledger = json.loads(failure_ledger_text)
    assert failure_ledger["endpoint_path"] == "/coins/markets"
    assert failure_ledger["provider_request_succeeded"] is False
    assert failure_ledger["http_status"] is None
    assert failure_ledger["result_count"] == 0
    assert failure_ledger["retry_count"] == 0
    assert failure_ledger["error_class"] == "TimeoutError"
    assert "secret-bearing" not in failure_ledger_text
    assert not {
        "headers", "query", "params", "token", "api_key", "authorization",
        "recipient", "recipient_id", "chat_id",
    }.intersection(key.casefold() for key in failure_ledger)


def test_controlled_live_no_send_generation_publishes_exact_dashboard_authority(
    tmp_path,
    monkeypatch,
):
    """Prove the approved live adapter path from source row to dashboard authority."""

    _configure_live_test(monkeypatch, tmp_path)
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    namespace = "controlled_live_publication"
    calls = 0

    def controlled_live_provider(_limit):
        nonlocal calls
        calls += 1
        return market_no_send._smoke_rows()

    # Keep ``provider=None`` so the production-approved adapter owns the live
    # attribution; replace only its network boundary with deterministic rows.
    monkeypatch.setattr(
        market_no_send,
        "_fetch_live_coingecko_rows",
        controlled_live_provider,
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        top_n=5,
        observed_at=observed,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )

    assert result.complete is True
    assert calls == 1
    assert result.candidate_source_mode == "live_no_send"
    assert result.provenance_contract_valid is True
    assert result.decision_radar_campaign_counted is True
    assert result.burn_in_counted is False
    observed_text = result.observed_at
    live_observed = datetime.fromisoformat(observed_text)
    namespace_dir = tmp_path / namespace

    source = json.loads(
        (namespace_dir / market_no_send.REQUEST_CACHE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    request_ledger = json.loads(
        (namespace_dir / market_no_send.REQUEST_LEDGER_FILENAME).read_text(encoding="utf-8")
    )
    snapshots = _jsonl(namespace_dir / "event_market_state_snapshots.jsonl")
    anomalies = _jsonl(namespace_dir / "event_market_anomalies.jsonl")
    catalyst_queue = _jsonl(
        namespace_dir / "event_market_anomaly_catalyst_search_queue.jsonl"
    )
    candidates = _jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl")
    core_rows = _jsonl(namespace_dir / "event_core_opportunities.jsonl")
    outcomes = _jsonl(namespace_dir / "event_integrated_radar_outcomes.jsonl")
    cards = tuple(
        path
        for path in (namespace_dir / "research_cards").glob("*.md")
        if path.name != "index.md"
    )
    preview = (namespace_dir / "event_decision_v2_notification_preview.md").read_text(
        encoding="utf-8"
    )
    brief = (namespace_dir / "event_alpha_daily_brief.md").read_text(encoding="utf-8")

    assert source["provider"] == "coingecko"
    assert source["provider_request_succeeded"] is True
    assert source["measurement_program"] == "decision_radar_live_observation_campaign_v2"
    assert source["decision_radar_campaign_counted"] is True
    assert source["rows"]
    assert all("shadow_temporal_surprise" not in row for row in source["rows"])
    assert request_ledger["endpoint_path"] == "/coins/markets"
    assert request_ledger["http_status"] == 200
    assert request_ledger["result_count"] == len(market_no_send._smoke_rows())
    assert request_ledger["retry_count"] == 0
    assert request_ledger["error_class"] is None
    assert request_ledger["cache_behavior"] == "network"
    assert request_ledger["live_provider_authorized"] is True
    assert request_ledger["no_send"] is True
    health = json.loads(
        (namespace_dir / market_no_send.market_no_send_provider.PROVIDER_HEALTH_FILENAME).read_text(
            encoding="utf-8"
        )
    )["providers"][market_no_send.market_no_send_provider.PROVIDER_HEALTH_KEY]
    assert health["run_id"] == result.run_id
    assert health["request_http_status"] == request_ledger["http_status"]
    assert health["request_result_count"] == request_ledger["result_count"]
    assert health["request_retry_count"] == request_ledger["retry_count"]
    assert len(snapshots) == result.selected_market_rows
    assert len(anomalies) == result.market_anomalies
    assert len(candidates) == result.candidates
    assert len(core_rows) == result.core_rows
    assert len(outcomes) == len(candidates)
    assert len(cards) == result.cards
    history_rows = _jsonl(namespace_dir / market_no_send.HISTORY_FILENAME)
    assert all("shadow_temporal_surprise" not in row for row in history_rows)
    assert all("shadow_temporal_surprise" in row for row in snapshots)
    assert all("shadow_temporal_surprise" in row for row in anomalies)
    assert all(
        "shadow_temporal_surprise" not in row.get("market_state_snapshot", {})
        for row in anomalies
    )
    assert all("shadow_temporal_surprise" not in row for row in candidates)
    assert all(
        "shadow_temporal_surprise" not in row.get("decision_projection", {})
        for row in candidates
    )
    assert all("shadow_temporal_surprise" not in row for row in core_rows)
    assert all("shadow_temporal_surprise" not in row for row in outcomes)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["calendar_snapshot"]["status"] == "not_configured"
    assert manifest["calendar_snapshot"]["configured"] is False
    assert manifest["market_quality_source_artifact"] == "event_market_state_snapshots.jsonl"
    assert sum(manifest["baseline_status_counts"].values()) == len(snapshots)
    assert manifest["direct_feature_count"] == sum(
        int(row["market_data_quality"]["direct_feature_count"])
        for row in snapshots
    )
    assert manifest["proxy_feature_count"] == sum(
        int(row["market_data_quality"]["proxy_feature_count"])
        for row in snapshots
    )
    assert "Crypto Radar Decision v2 Preview" in preview
    assert "live_provider / live_no_send / coingecko" in preview
    assert "Decision Radar campaign eligible / counted: true / true" in preview
    assert all(row["candidate_source_mode"] == "live_no_send" for row in snapshots)
    assert all(row["candidate_source_mode"] == "live_no_send" for row in anomalies)
    assert all(row["market_provenance"]["decision_radar_campaign_counted"] is True for row in candidates)
    assert all(row["market_provenance"]["burn_in_counted"] is False for row in candidates)
    assert all(row["market_provenance"]["decision_radar_campaign_counted"] is True for row in core_rows)
    assert all(row["market_provenance"]["burn_in_counted"] is False for row in core_rows)
    assert all(row["market_provenance"]["decision_radar_campaign_counted"] is True for row in outcomes)
    assert all(row["market_provenance"]["burn_in_counted"] is False for row in outcomes)
    card_text = "\n".join(path.read_text(encoding="utf-8") for path in cards)
    assert "- Data acquisition mode: live_provider" in card_text
    assert "- Candidate source mode: live_no_send" in card_text
    assert "- Decision Radar campaign-counted candidate: true" in card_text
    core_by_id = {str(row["core_opportunity_id"]): row for row in core_rows}
    outcome_by_candidate = {str(row["candidate_id"]): row for row in outcomes}
    for candidate in candidates:
        reference = candidate["decision_projection"]["market_context_reference"]
        assert reference["source"] == "coingecko"
        assert reference["observed_at"] == observed_text
        assert reference["freshness_status"] == "fresh"
        assert reference["market_snapshot_id"]
        outcome = outcome_by_candidate[str(candidate["candidate_id"])]
        assert outcome["decision_projection"]["market_context_reference"] == reference
        core = core_by_id.get(str(candidate["core_opportunity_id"]))
        if core is None:
            assert candidate["opportunity_type"] == "DIAGNOSTIC"
            continue
        assert core["market_context_reference"] == reference
        assert core["decision_projection"]["market_context_reference"] == reference
        rendered_reference = (
            "- Market context reference: "
            f"source={reference['source']}; observed_at={reference['observed_at']}; "
            f"freshness={reference['freshness_status']}; "
            f"snapshot_id={reference['market_snapshot_id']}"
        )
        assert rendered_reference in card_text
        assert rendered_reference in preview
        assert rendered_reference in brief

    doctor_env = os.environ.copy()
    doctor_env.update({
        "RSI_EVENT_ALERTS_ENABLED": "0",
        "RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED": "0",
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(tmp_path),
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE": namespace,
        "RSI_EVENT_ALPHA_RUN_MODE": "operational",
        "RSI_EVENT_RESEARCH_NOW": observed_text,
    })
    doctor = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "main.py"),
            "--event-alpha-artifact-doctor",
            "--event-alpha-profile",
            "no_key_live",
            "--event-alpha-artifact-namespace",
            namespace,
            "--event-alpha-artifact-doctor-strict",
        ],
        cwd=namespace_dir,
        env=doctor_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr

    operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    assert operator_state["doctor"]["status"] != "BLOCKED"
    assert operator_state["doctor"]["authoritative"] is True
    assert operator_state["market_no_send_provenance"]["decision_radar_campaign_counted"] is True
    assert operator_state["market_no_send_provenance"]["burn_in_counted"] is False
    for artifact_name, expected_count in (
        ("market_state_snapshots", len(snapshots)),
        ("market_anomalies", len(anomalies)),
        ("market_anomaly_catalyst_search_queue", len(catalyst_queue)),
    ):
        artifact = operator_state["artifacts"][artifact_name]
        assert artifact["status"] == "current"
        assert artifact["count"] == expected_count
        assert artifact["sha256"]

    checked_at = datetime.now(timezone.utc)
    published = market_no_send.publish_market_no_send_generation(
        tmp_path,
        namespace,
        now=checked_at,
        publisher=publish_current_namespace_pointer,
    )
    pointer = read_current_namespace_pointer(tmp_path)
    assert pointer["artifact_namespace"] == namespace
    assert pointer["run_id"] == result.run_id
    assert pointer["revision"] == published.snapshot.revision
    assert pointer["operator_state_sha256"] == published.snapshot.operator_state_sha256
    pointer_before_reverification = (tmp_path / CURRENT_NAMESPACE_POINTER).read_bytes()

    doctor_reverification = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "main.py"),
            "--event-alpha-artifact-doctor",
            "--event-alpha-profile",
            "no_key_live",
            "--event-alpha-artifact-namespace",
            namespace,
            "--event-alpha-artifact-doctor-strict",
        ],
        cwd=namespace_dir,
        env=doctor_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor_reverification.returncode == 0, (
        doctor_reverification.stdout + doctor_reverification.stderr
    )
    reverified_operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    assert reverified_operator_state["revision"] == operator_state["revision"]
    assert reverified_operator_state["doctor"]["status"] == operator_state["doctor"]["status"]
    assert reverified_operator_state["doctor"]["blocker_count"] == operator_state["doctor"]["blocker_count"]
    assert reverified_operator_state["doctor"]["warning_count"] == operator_state["doctor"]["warning_count"]
    assert (tmp_path / CURRENT_NAMESPACE_POINTER).read_bytes() == pointer_before_reverification

    checked_at = datetime.now(timezone.utc)
    resolved = resolve_authoritative_dashboard(tmp_path, now=checked_at)
    loaded = load_dashboard_snapshot(tmp_path, namespace, now=checked_at)
    assert resolved.namespace_source == "pointer"
    assert resolved.snapshot.generation_authoritative is True
    assert loaded.generation_authoritative is True
    assert loaded.run_id == result.run_id
    assert len(loaded.current_candidates) == result.core_rows
    assert len(loaded.current_outcomes) == result.candidates
    assert loaded.cumulative_outcomes == ()
    for dashboard_row in loaded.current_candidates:
        source_candidate = next(
            row
            for row in candidates
            if row["core_opportunity_id"] == dashboard_row["core_opportunity_id"]
        )
        assert dashboard_row["decision_projection"]["market_context_reference"] == (
            source_candidate["decision_projection"]["market_context_reference"]
        )
    assert loaded.cumulative_history_metadata[
        "event_integrated_radar_outcomes.jsonl"
    ]["authority"] == "current_generation_fingerprint_verified"
    _json_path, _md_path, audit = market_no_send.write_market_no_send_pilot_audit(
        tmp_path,
        namespace,
        now=checked_at,
    )
    assert audit["publication"]["status"] == "published"
    assert audit["publication"]["points_to_attempt"] is True
    assert audit["dashboard"]["trusted_current"] is True
    assert audit["provider_adapter_invoked"] is True
    assert audit["network_call_attempted"] is True
    assert audit["exact_run_id"] == result.run_id
    assert audit["exact_operator_revision"] == published.snapshot.revision
    assert audit["baseline"]["baseline_status_counts"]
    assert audit["feature_basis"]

    from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility
    from crypto_rsi_scanner.event_alpha.operations import market_observation_outcomes

    campaign_rows = market_observation_outcomes.load_campaign_outcomes(tmp_path)
    assert len(campaign_rows) == len(candidates)
    assert all(row["measurement_program"] == "decision_radar_live_observation_campaign_v2" for row in campaign_rows)
    candidate_bytes = (namespace_dir / "event_integrated_radar_candidates.jsonl").read_bytes()
    pointer_bytes = (tmp_path / CURRENT_NAMESPACE_POINTER).read_bytes()
    history_path = (
        tmp_path
        / market_no_send.market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
        / market_no_send.HISTORY_FILENAME
    )
    history_rows = _jsonl(history_path)
    for candidate in candidates:
        if str(candidate["core_opportunity_id"]) not in core_by_id:
            continue
        entry = next(
            row for row in history_rows
            if row.get("coin_id") == candidate.get("coin_id")
            and row.get("observed_at") == observed_text
        )
        for horizon, seconds in outcome_eligibility.OUTCOME_HORIZON_SECONDS.items():
            close_at = live_observed + timedelta(seconds=seconds)
            history_rows.append({
                **entry,
                "observed_at": close_at.isoformat(),
                "observation_id": f"{entry['observation_id']}-{horizon}",
                "price": float(entry["price"]) * 1.01,
            })
    market_no_send_io.write_jsonl(history_path, history_rows)
    refreshed = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=live_observed + timedelta(days=8),
    )
    assert refreshed["maturation_counts"].get("matured", 0) >= 1
    matured_rows = market_observation_outcomes.load_campaign_outcomes(tmp_path)
    assert any(
        row.get("maturation_state") == "matured"
        and row.get("outcome_data_source") == "observed_market_prices"
        for row in matured_rows
    )
    assert (namespace_dir / "event_integrated_radar_candidates.jsonl").read_bytes() == candidate_bytes
    assert (tmp_path / CURRENT_NAMESPACE_POINTER).read_bytes() == pointer_bytes


def test_controlled_live_clean_zero_generation_is_strict_publishable(
    tmp_path,
    monkeypatch,
):
    """A real cold-baseline observation may publish honestly with zero ideas."""

    _configure_live_test(monkeypatch, tmp_path)
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    namespace = "controlled_live_clean_zero"
    rows = [dict(row) for row in market_no_send._smoke_rows()]
    for row in rows:
        row.update({
            "return_1h": 0.0,
            "return_4h": 0.0,
            "return_24h": 0.0,
            "volume_zscore_24h": 0.0,
        })
    monkeypatch.setattr(
        market_no_send,
        "_fetch_live_coingecko_rows",
        lambda _limit: rows,
    )

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        top_n=5,
        observed_at=observed,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )

    namespace_dir = tmp_path / namespace
    core_path = namespace_dir / "event_core_opportunities.jsonl"
    assert result.complete is True
    assert result.candidates == 0
    assert result.core_rows == 0
    assert result.cards == 0
    assert core_path.is_file()
    assert core_path.read_bytes() == b""
    before_doctor = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    assert before_doctor["manifest_status"] == "complete"

    doctor_env = os.environ.copy()
    doctor_env.update({
        "RSI_EVENT_ALERTS_ENABLED": "0",
        "RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED": "0",
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(tmp_path),
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE": namespace,
        "RSI_EVENT_ALPHA_RUN_MODE": "operational",
        "RSI_EVENT_RESEARCH_NOW": result.observed_at,
    })
    doctor = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "main.py"),
            "--event-alpha-artifact-doctor",
            "--event-alpha-profile",
            "no_key_live",
            "--event-alpha-artifact-namespace",
            namespace,
            "--event-alpha-artifact-doctor-strict",
        ],
        cwd=namespace_dir,
        env=doctor_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    after_doctor = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    assert after_doctor["doctor"]["authoritative"] is True
    assert after_doctor["doctor"]["blocker_count"] == 0

    market_no_send.publish_market_no_send_generation(
        tmp_path,
        namespace,
        now=datetime.now(timezone.utc),
        publisher=publish_current_namespace_pointer,
    )
    assert read_current_namespace_pointer(tmp_path)["artifact_namespace"] == namespace


def test_mock_generation_cannot_replace_existing_fixture_pointer(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="mock_pointer_guard",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )
    assert result.complete
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b"fixture-authority-stays\n")

    with pytest.raises(market_no_send.MarketNoSendError, match="not publishable"):
        market_no_send.publish_market_no_send_generation(
            tmp_path,
            "mock_pointer_guard",
            now=_OBSERVED,
            publisher=publish_current_namespace_pointer,
        )

    assert pointer.read_bytes() == b"fixture-authority-stays\n"


def test_live_manifest_without_matching_operator_authority_cannot_replace_pointer(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    namespace = "live_candidate"
    monkeypatch.setattr(
        market_no_send,
        "_fetch_live_coingecko_rows",
        lambda _limit: market_no_send._smoke_rows(),
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        top_n=5,
        observed_at=_OBSERVED,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert result.complete
    namespace_dir = tmp_path / namespace
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    ledger = json.loads(
        (namespace_dir / market_no_send.REQUEST_LEDGER_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["candidate_source_mode"] == "live_no_send"
    assert manifest["provenance_contract_valid"] is True
    assert manifest["decision_radar_campaign_eligible"] is True
    assert manifest["decision_radar_campaign_counted"] is True
    assert manifest["burn_in_eligible"] is False
    assert manifest["burn_in_counted"] is False
    assert ledger["provider_source_artifact_sha256"] == manifest["request_cache_sha256"]
    assert ledger["decision_radar_campaign_counted"] is True
    assert ledger["burn_in_counted"] is False
    (namespace_dir / "event_alpha_operator_state.json").unlink()
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b"previous-fixture-pointer\n")

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="operator state identity does not match",
    ):
        market_no_send.publish_market_no_send_generation(
            tmp_path,
            namespace,
            now=_OBSERVED,
            publisher=publish_current_namespace_pointer,
        )

    assert pointer.read_bytes() == b"previous-fixture-pointer\n"


def test_injected_callable_cannot_claim_live_coingecko_provenance(tmp_path, monkeypatch):
    _configure_live_test(monkeypatch, tmp_path)
    with pytest.raises(market_no_send.MarketNoSendError, match="cannot claim live"):
        market_no_send.run_market_no_send_generation(
            artifact_base_dir=tmp_path,
            artifact_namespace="injected_live_claim",
            top_n=5,
            provider=lambda _limit: market_no_send._smoke_rows(),
            observed_at=_OBSERVED,
            environ={market_no_send.LIVE_AUTH_ENV: "1"},
            fixture_dir=None,
        )


def test_market_make_targets_do_not_force_live_authorization():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "radar-market-no-send-readiness:" in makefile
    assert "radar-market-no-send:" in makefile
    assert "radar-market-no-send-smoke:" in makefile
    readiness_target = makefile.split("radar-market-no-send-readiness:\n", 1)[1].split(
        "radar-market-campaign-report:\n", 1
    )[0]
    target = makefile.split(
        "radar-market-no-send: radar-daily-ops-cycle\n", 1
    )[1].split(
        "radar-market-no-send-smoke:", 1
    )[0]
    daily_operations_target = makefile.split(
        "radar-daily-ops-cycle:\n", 1
    )[1].split("radar-daily-ops-install:", 1)[0]
    assert "market_no_send campaign-report" not in readiness_target
    assert "delegates to the receipt-backed Daily Operations coordinator" in target
    assert "market_no_send run" not in target
    assert "market_no_send publish" not in target
    assert "operations.daily_operations cycle" in daily_operations_target
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" not in daily_operations_target
    assert "RSI_EVENT_ALPHA_RUN_MODE=operational" in daily_operations_target
    assert "radar_market_no_send_$(shell date -u +%Y%m%dt%H%M%Sz)" in makefile


def test_market_writer_namespace_parent_symlink_swap_fails_closed(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    namespace_dir = base / "market_write_race"
    namespace_dir.mkdir(parents=True)
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    target.write_bytes(b'{"status":"safe-before"}\n')
    displaced = base / "market_write_race.checked"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / market_no_send.RUN_MANIFEST_FILENAME
    outside_marker = b'{"status":"outside-unchanged"}\n'
    outside_target.write_bytes(outside_marker)
    original_open = market_no_send_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == namespace_dir.name and dir_fd is not None and not swapped:
            namespace_dir.rename(displaced)
            namespace_dir.symlink_to(outside, target_is_directory=True)
            # Identity verification must still fail if no-follow is ineffective.
            flags &= ~market_no_send_io.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(market_no_send_io.os, "open", racing_open)
    with pytest.raises(market_no_send.MarketNoSendError, match="write failed"):
        market_no_send._write_json_atomic(target, {"status": "must-not-escape"})

    assert swapped is True
    assert outside_target.read_bytes() == outside_marker
    assert (displaced / target.name).read_bytes() == b'{"status":"safe-before"}\n'
    assert not tuple(outside.glob(".*.tmp"))
    assert not tuple(displaced.glob(".*.tmp"))


def test_market_reader_namespace_parent_symlink_swap_does_not_read_outside(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    namespace_dir = base / "market_read_race"
    namespace_dir.mkdir(parents=True)
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    target.write_text('{"status":"safe"}\n', encoding="utf-8")
    displaced = base / "market_read_race.checked"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / target.name).write_text('{"status":"outside"}\n', encoding="utf-8")
    original_open = market_no_send_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == namespace_dir.name and dir_fd is not None and not swapped:
            namespace_dir.rename(displaced)
            namespace_dir.symlink_to(outside, target_is_directory=True)
            flags &= ~market_no_send_io.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(market_no_send_io.os, "open", racing_open)
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="missing or unreadable",
    ):
        market_no_send._read_json_object(target)
    assert swapped is True


def test_market_reader_rejects_same_inode_mutation_during_read(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market_in_place_read_race"
    namespace_dir.mkdir()
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    target.write_bytes(b'{"status":"safe"}\n')
    replacement = b'{"status":"evil"}\n'
    original_fstat = market_no_send_io.os.fstat
    regular_fstat_calls = 0

    def mutating_fstat(descriptor):
        nonlocal regular_fstat_calls
        info = original_fstat(descriptor)
        if stat.S_ISREG(info.st_mode):
            regular_fstat_calls += 1
            if regular_fstat_calls == 2:
                target.write_bytes(replacement)
                os.utime(
                    target,
                    ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000),
                )
                info = original_fstat(descriptor)
        return info

    monkeypatch.setattr(market_no_send_io.os, "fstat", mutating_fstat)

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="missing or unreadable",
    ):
        market_no_send_io.read_regular_bytes(target)

    assert regular_fstat_calls == 2
    assert target.read_bytes() == replacement


def test_market_artifact_io_fails_closed_without_descriptor_features(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market_unsupported"
    namespace_dir.mkdir()
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    monkeypatch.setattr(market_no_send_io, "_OPEN_SUPPORTS_DIR_FD", False)

    with pytest.raises(market_no_send.MarketNoSendError, match="unsupported"):
        market_no_send._write_json_atomic(target, {"status": "blocked"})
    with pytest.raises(market_no_send.MarketNoSendError, match="unsupported"):
        market_no_send._read_json_object(target)
    assert not target.exists()


def test_market_quality_counts_use_populated_snapshot_and_treat_cold_as_warming(
    tmp_path,
):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        json.dumps({
            "market_state_snapshot": {},
            "market_snapshot": {
                "market_data_quality": {
                    "baseline_status": "cold",
                    "direct_feature_count": 4,
                    "proxy_feature_count": 2,
                },
            },
        }) + "\n",
        encoding="utf-8",
    )

    counts = market_no_send_features.market_quality_counts(path)

    assert counts["baseline_status"] == "warming"
    assert counts["baseline_warming_assets"] == 1
    assert counts["direct_feature_count"] == 4
    assert counts["proxy_feature_count"] == 2


def test_calendar_snapshot_copy_drift_blocks_campaign_publication_validation(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    calendar_path = tmp_path / "calendar-current.json"
    calendar_path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "observed_at": _OBSERVED,
                "source_mode": "operator_verified_calendar_snapshot",
                "data_acquisition_mode": "operator_verified_export",
                "source_provider": "operator_calendar",
                "events": [
                    {
                        "id": "calendar-1",
                        "title": "Calendar publication binding",
                        "event_kind": "protocol",
                        "scheduled_at": "2026-07-20T12:00:00Z",
                        "time_certainty": "exact",
                        "importance": "high",
                        "affected_assets": ["MKTFLOW"],
                        "source": "operator_calendar",
                        "source_url": "https://example.com/calendar/calendar-1",
                        "research_only": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="calendar_binding",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(calendar_path)},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )
    namespace_dir = result.namespace_dir
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    path = namespace_dir / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME

    market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )
    scheduled_path = namespace_dir / "event_scheduled_catalysts.jsonl"
    scheduled_original = scheduled_path.read_bytes()
    scheduled_rows = _jsonl(scheduled_path)
    scheduled_rows[0]["title"] = "Tampered scheduled meaning"
    scheduled_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in scheduled_rows
        ),
        encoding="utf-8",
    )
    scheduled_drift = json.loads(json.dumps(manifest))
    scheduled_drift["calendar_snapshot"][
        "scheduled_catalyst_artifact_sha256"
    ] = hashlib.sha256(scheduled_path.read_bytes()).hexdigest()
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="scheduled_semantics_mismatch",
    ):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            scheduled_drift,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
    scheduled_path.write_bytes(scheduled_original)

    unified_path = namespace_dir / "event_unified_calendar_events.jsonl"
    unified_original = unified_path.read_bytes()
    unified_rows = _jsonl(unified_path)
    unified_rows[0]["calendar_event_id"] = "calendar:tampered"
    unified_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in unified_rows
        ),
        encoding="utf-8",
    )
    unified_drift = json.loads(json.dumps(manifest))
    unified_drift["calendar_snapshot"][
        "unified_calendar_artifact_sha256"
    ] = hashlib.sha256(unified_path.read_bytes()).hexdigest()
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="unified_semantics_mismatch",
    ):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            unified_drift,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
    unified_path.write_bytes(unified_original)

    count_drift = json.loads(json.dumps(manifest))
    count_drift["calendar_snapshot"]["normalization_input_count"] = 2
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="normalization_count_mismatch",
    ):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            count_drift,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
    status_drift = json.loads(json.dumps(manifest))
    status_drift["calendar_snapshot"]["status"] = "healthy_empty"
    with pytest.raises(market_no_send.MarketNoSendError, match="status_count_mismatch"):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            status_drift,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["events"][0]["id"] = "drifted"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(market_no_send.MarketNoSendError, match="binding_mismatch"):
        market_no_send.market_no_send_publication._validate_optional_calendar_snapshot(
            manifest,
            namespace_dir=namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )


def test_unusable_calendar_status_forbids_derived_source_copy(tmp_path):
    metadata = market_no_send_calendar.MarketNoSendCalendarSnapshot(
        status="not_configured"
    ).to_dict()
    manifest = {
        "artifact_namespace": tmp_path.name,
        "calendar_snapshot": metadata,
    }
    validate = market_no_send.market_no_send_publication._validate_optional_calendar_snapshot

    validate(
        manifest,
        namespace_dir=tmp_path,
        run_id="run-no-calendar",
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )
    market_no_send_io.write_json_atomic(
        tmp_path / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME,
        {"unexpected": "derived calendar source"},
    )

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="unusable_copy_present",
    ):
        validate(
            manifest,
            namespace_dir=tmp_path,
            run_id="run-no-calendar",
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )
