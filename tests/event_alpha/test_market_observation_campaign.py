"""Artifact-derived Decision Radar observation-campaign report tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.artifacts import operator_state
from crypto_rsi_scanner.event_alpha.dashboard.readiness import CURRENT_NAMESPACE_POINTER
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
from crypto_rsi_scanner.event_alpha.operations import market_no_send_audit
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_no_send_publication
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign as campaign
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    SAFETY_COUNTERS,
    MarketNoSendReadiness,
)
from tests.event_alpha.campaign_test_support import write_countable_generation


_EVALUATED = "2026-07-13T18:00:00+00:00"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest(
    namespace: str,
    observed_at: str,
    *,
    candidates: int,
    direct: int,
    proxy: int,
) -> dict[str, object]:
    run_id = f"{observed_at}|no_key_live"
    provenance = {
        "contract_version": 2,
        "schema_version": "crypto_radar_market_provenance_v2",
        "provenance_contract_valid": True,
        "measurement_program": campaign.CAMPAIGN_PROGRAM,
        "decision_radar_campaign_counted": True,
        "burn_in_counted": False,
        "data_quality": {
            "direct_feature_count": direct,
            "proxy_feature_count": proxy,
            "spread_available_count": 0,
            "baseline_status_counts": {"warming": candidates},
            "baseline_warm_assets": 0,
            "baseline_warming_assets": candidates,
        },
    }
    return {
        "contract_version": 2,
        "row_type": "event_market_no_send_generation",
        "artifact_namespace": namespace,
        "run_id": run_id,
        "observed_at": observed_at,
        "status": "complete",
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "live_provider_authorized": True,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provenance_contract_valid": True,
        "measurement_program": campaign.CAMPAIGN_PROGRAM,
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "no_send": True,
        "research_only": True,
        "candidate_count": candidates,
        "selected_market_row_count": 5,
        "market_provenance": provenance,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def _generation(
    base: Path,
    namespace: str,
    observed_at: str,
    *,
    routes: list[str],
    published: bool,
    direct: int,
    proxy: int,
) -> dict[str, object]:
    directory = base / namespace
    directory.mkdir(parents=True)
    _path, manifest, _candidates = write_countable_generation(
        base,
        namespace,
        observed_at,
        candidates=[
            {
                "candidate_id": f"{namespace}:{index}",
                "radar_route": route,
            }
            for index, route in enumerate(routes)
        ],
        direct_feature_count=direct,
        proxy_feature_count=proxy,
    )
    _write_jsonl(directory / "event_integrated_radar_outcomes.jsonl", [])
    operator = {
        "row_type": "event_alpha_operator_state",
        "artifact_namespace": namespace,
        "run_id": manifest["run_id"],
        "revision": 3,
        "doctor": {
            "authoritative": published,
            "status": "PASS",
            "blocker_count": 0,
            "warning_count": 0,
            "verified_revision": 3,
            "verified_at": "2026-07-13T17:30:00+00:00",
        },
    }
    _write_json(directory / campaign.OPERATOR_STATE_FILENAME, operator)
    _write_json(
        directory / campaign.PILOT_AUDIT_FILENAME,
        {
            "contract_version": 1,
            "row_type": "event_market_no_send_pilot_audit",
            "artifact_namespace": namespace,
            "exact_run_id": manifest["run_id"],
            "exact_operator_revision": operator["revision"],
            "generated_at": "2026-07-13T17:31:00+00:00",
            "attempt_status": "complete",
            "provider": "coingecko",
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "data_acquisition_mode": "live_provider",
            "candidate_source_mode": "live_no_send",
            "publication": {
                "status": "published" if published else "not_published",
                "pointer_namespace": namespace,
                "pointer_run_id": manifest["run_id"],
                "pointer_revision": operator["revision"],
                "pointer_operator_state_sha256": (
                    operator_state.operator_authority_digest(operator)
                ),
            },
            "safety": {"no_send": True, "research_only": True},
        },
    )
    return operator


def _fixture(base: Path) -> None:
    authoritative_operator = _generation(
        base,
        "radar_market_no_send_a",
        "2026-07-13T15:00:00+00:00",
        routes=["risk_watch", "diagnostic"],
        published=True,
        direct=10,
        proxy=4,
    )
    _generation(
        base,
        "radar_market_no_send_b",
        "2026-07-13T16:00:00+00:00",
        routes=["dashboard_watch"],
        published=False,
        direct=3,
        proxy=2,
    )
    failed = base / "radar_market_no_send_failed"
    failed.mkdir()
    _write_json(
        failed / campaign.RUN_MANIFEST_FILENAME,
        {
            "row_type": "event_market_no_send_generation",
            "status": "failed",
            "data_mode": "live",
            "data_acquisition_mode": "live_provider",
            "candidate_source_mode": "live_no_send",
            "provider": "coingecko",
            "provider_call_attempted": True,
            "provider_request_succeeded": False,
            "failure_class": "http_error",
            "observed_at": "2026-07-13T16:30:00+00:00",
            "no_send": True,
            "research_only": True,
        },
    )
    _write_json(
        base / campaign.PILOT_AUDIT_FILENAME,
        {
            "row_type": "event_market_no_send_pilot_audit",
            "artifact_namespace": "radar_market_no_send_blocked",
            "attempt_status": "blocked",
            "generated_at": "2026-07-13T14:00:00+00:00",
            "provider": "coingecko",
            "provider_call_attempted": False,
            "provider_request_succeeded": False,
            "data_acquisition_mode": "preflight_only",
            "candidate_source_mode": "preflight_only",
            "safety": {"no_send": True, "research_only": True},
        },
    )
    _write_json(
        base / CURRENT_NAMESPACE_POINTER,
        {
            "contract_version": 1,
            "artifact_namespace": "radar_market_no_send_a",
            "profile": "no_key_live",
            "run_id": "2026-07-13T15:00:00+00:00|no_key_live",
            "revision": 3,
            "operator_state_sha256": operator_state.operator_authority_digest(
                authoritative_operator
            ),
            "generation_authority_status": "authoritative",
            "authority_checked_at": "2026-07-13T17:31:00+00:00",
        },
    )
    _write_jsonl(
        base
        / "radar_market_history_cache"
        / campaign.CAMPAIGN_OUTCOMES_FILENAME,
        [
            {
                "outcome_identity_key": "a",
                "source_artifact_namespace": "radar_market_no_send_a",
                "maturation_state": "pending",
                "campaign_outcome_ledger": True,
            },
            {
                "outcome_identity_key": "b",
                "source_artifact_namespace": "radar_market_no_send_b",
                "maturation_state": "matured",
                "campaign_outcome_ledger": True,
            },
        ],
    )


def _readiness(*_args, **_kwargs):
    return {
        "baseline_status": "warming",
        "baseline_observation_count": 9,
        "baseline_counted_observation_count": 8,
        "baseline_too_close_observation_count": 1,
        "baseline_asset_count": 2,
        "baseline_warm_asset_count": 0,
        "minimum_observation_spacing_seconds": 3600,
        "baseline_newest_counted_observed_at": "2026-07-13T17:30:00+00:00",
        "next_eligible_observation_at": "2026-07-13T18:30:00+00:00",
        "cadence_status": "waiting",
        "baseline_feature_readiness": {
            "volume": {
                "status_counts": {"warming": 2},
                "warm_asset_count": 0,
                "warming_asset_count": 2,
            }
        },
    }


def _dashboard_authority(*_args, **_kwargs):
    return SimpleNamespace(
        snapshot=SimpleNamespace(
            artifact_namespace="radar_market_no_send_a",
            profile="no_key_live",
            run_id="2026-07-13T15:00:00+00:00|no_key_live",
            revision=3,
            operator_state_sha256="0" * 64,
            generation_authority_checked_at="2026-07-13T17:31:00+00:00",
        )
    )


def test_historical_market_provenance_v2_uses_read_only_counting_adapter():
    manifest = _manifest(
        "historical_market_generation",
        "2026-07-13T15:00:00+00:00",
        candidates=1,
        direct=1,
        proxy=0,
    )
    for field in (
        "measurement_program", "decision_radar_campaign_eligible",
        "decision_radar_campaign_counted", "decision_radar_campaign_reason",
    ):
        manifest.pop(field, None)
    manifest["burn_in_counted"] = True
    provenance = manifest["market_provenance"]
    assert isinstance(provenance, dict)
    provenance.pop("measurement_program", None)
    provenance.pop("decision_radar_campaign_counted", None)
    provenance["burn_in_counted"] = True

    counted, source, _reason = campaign._campaign_counting(manifest)

    assert counted is True
    assert source == "historical_market_provenance_v2_read_only_adapter"


def test_campaign_report_is_deterministic_and_separates_attempt_classes(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )

    first = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)
    second = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)

    assert first == second
    assert first["measurement_program"] == campaign.CAMPAIGN_PROGRAM
    assert first["measurement_scope"]["event_alpha_catalyst_burn_in"] == "separate_not_aggregated"
    assert first["campaign_metrics"]["real_cycles"] == 2
    assert first["campaign_metrics"]["real_candidates"] == 3
    assert first["campaign_metrics"]["route_counts"] == {
        "dashboard_watch": 1,
        "diagnostic": 1,
        "risk_watch": 1,
    }
    assert first["campaign_metrics"]["direct_feature_count"] == 13
    assert first["campaign_metrics"]["proxy_feature_count"] == 6
    assert len(first["authoritative_generations"]) == 1
    assert len(first["non_authoritative_complete_generations"]) == 1
    assert len(first["provider_failed_attempts"]) == 1
    assert len(first["blocked_or_preflight_attempts"]) == 1
    assert first["outcomes"]["source"] == "canonical_candidate_pending_base"
    assert first["outcomes"]["pending"] == 3
    assert first["outcomes"]["matured"] == 0
    assert first["pointer"]["exact_operator_binding"] is True
    conclusion = first["campaign_v2_conclusion"]
    assert conclusion["baseline_status"] == "warming"
    assert conclusion["baseline_coverage"] == {
        "retained_observations": 9,
        "counted_observations": 8,
        "asset_count": 2,
        "warm_asset_count": 0,
    }
    assert conclusion["pointer_history_count"] == 1
    assert conclusion["current_authority"]["artifact_namespace"] == (
        "radar_market_no_send_a"
    )
    assert conclusion["current_authority"]["exact_operator_binding"] is True
    assert conclusion["data_quality_limitation_categories"] == [
        "execution_quality_spread",
        "proxy_market_features",
        "temporal_baseline_maturity",
    ]
    assert first["next_observation"]["eligible_now"] is False
    assert first["safety"]["provider_calls_made_by_report"] == 0
    assert all(
        row["campaign_counting_source"]
        == "decision_radar_campaign_contract"
        for row in (*first["authoritative_generations"], *first["non_authoritative_complete_generations"])
    )


def test_campaign_report_honors_reserved_provider_call_cadence_without_history(
    tmp_path,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    attempted = datetime(2026, 7, 13, 18, 0, tzinfo=timezone.utc)
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        base,
        artifact_namespace="failed_before_history",
    ) as reservation:
        market_no_send_campaign_guard.mark_provider_call_reserved(
            reservation,
            attempted_at=attempted,
            minimum_spacing=timedelta(hours=1),
        )

    report = campaign.build_campaign_report(
        base,
        evaluated_at=attempted + timedelta(minutes=1),
    )

    assert report["next_observation"]["eligible_now"] is False
    assert report["next_observation"]["next_eligible_observation_at"] == (
        "2026-07-13T19:00:00+00:00"
    )
    assert report["next_observation"]["provider_call_reservation_next_at"] == (
        "2026-07-13T19:00:00+00:00"
    )
    assert report["next_observation"]["next_safe_operator_command"] == (
        "make radar-market-no-send-readiness PYTHON=.venv/bin/python"
    )


def test_reaudit_after_pointer_move_preserves_authority_history(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    namespace = "radar_market_no_send_a"
    readiness = MarketNoSendReadiness(
        status="ready",
        provider="coingecko",
        live_provider_authorized=True,
        provider_call_attempted=False,
        fixture_mode=False,
        no_send=True,
        research_only=True,
        top_n=30,
        fetch_limit=60,
        artifact_namespace=namespace,
        reasons=(),
    )
    first_json = base / namespace / campaign.PILOT_AUDIT_FILENAME
    assert market_no_send_io.read_json_object(first_json)["publication"]["status"] == (
        "published"
    )

    next_namespace = "radar_market_no_send_b"
    next_operator = market_no_send_io.read_json_object(
        base / next_namespace / campaign.OPERATOR_STATE_FILENAME
    )
    next_manifest = market_no_send_io.read_json_object(
        base / next_namespace / campaign.RUN_MANIFEST_FILENAME
    )
    _write_json(
        base / CURRENT_NAMESPACE_POINTER,
        {
            "contract_version": 1,
            "artifact_namespace": next_namespace,
            "profile": "no_key_live",
            "run_id": next_manifest["run_id"],
            "revision": next_operator["revision"],
            "operator_state_sha256": operator_state.operator_authority_digest(
                next_operator
            ),
            "generation_authority_status": "authoritative",
            "authority_checked_at": "2026-07-13T18:30:00+00:00",
        },
    )
    second_json, second_markdown, second = market_no_send_audit.write_pilot_audit(
        base=base,
        namespace=namespace,
        checked_at=datetime(2026, 7, 13, 19, tzinfo=timezone.utc),
        readiness=readiness,
        result=None,
        manifest_filename=campaign.RUN_MANIFEST_FILENAME,
        json_filename=campaign.PILOT_AUDIT_FILENAME,
        markdown_filename="event_market_no_send_pilot_audit.md",
        safety_counters=SAFETY_COUNTERS,
    )
    assert first_json == second_json
    assert second["publication"]["status"] == "not_published"
    assert second["publication"]["points_to_attempt"] is False
    assert second["publication"]["ever_authoritative"] is True
    assert second["publication"]["first_authoritative_at"] == (
        "2026-07-13T17:31:00+00:00"
    )
    assert second["publication"]["authority_binding"] == {
        "artifact_namespace": namespace,
        "run_id": "2026-07-13T15:00:00+00:00|no_key_live",
        "revision": 3,
        "operator_state_sha256": operator_state.operator_authority_digest(
            market_no_send_io.read_json_object(
                base / namespace / campaign.OPERATOR_STATE_FILENAME
            )
        ),
    }
    markdown = second_markdown.read_text(encoding="utf-8")
    assert "ever_authoritative: true" in markdown
    assert "first_authoritative_at: 2026-07-13T17:31:00+00:00" in markdown

    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)

    def next_authority(*_args, **_kwargs):
        return SimpleNamespace(
            snapshot=SimpleNamespace(
                artifact_namespace=next_namespace,
                profile="no_key_live",
                run_id=next_manifest["run_id"],
                revision=next_operator["revision"],
                operator_state_sha256="0" * 64,
                generation_authority_checked_at="2026-07-13T18:30:00+00:00",
            )
        )

    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        next_authority,
    )
    report = campaign.build_campaign_report(
        base,
        evaluated_at="2026-07-13T20:00:00+00:00",
    )
    history = {
        row["artifact_namespace"]: row
        for row in report["pointer_history"]
    }
    prior = next(
        row
        for row in report["authoritative_generations"]
        if row["artifact_namespace"] == namespace
    )
    assert prior["publication"] == {
        "ever_authoritative": True,
        "first_authoritative_at": "2026-07-13T17:31:00+00:00",
        "audit_authority_binding_valid": True,
        "authority_source": "pilot_audit_exact_binding",
        "audit_status": "not_published",
        "currently_authoritative": False,
    }
    assert history[namespace]["first_authoritative_at"] == (
        "2026-07-13T17:31:00+00:00"
    )
    assert history[namespace]["currently_authoritative"] is False


def test_copied_or_tampered_audit_cannot_invent_historical_authority(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)

    def rejected_authority(*_args, **_kwargs):
        raise campaign.dashboard_readiness.DashboardReadinessError("pointer unavailable")

    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        rejected_authority,
    )
    original = market_no_send_io.read_json_object(
        base / "radar_market_no_send_a" / campaign.PILOT_AUDIT_FILENAME
    )
    _write_json(
        base / "radar_market_no_send_b" / campaign.PILOT_AUDIT_FILENAME,
        original,
    )

    copied = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)
    assert [row["artifact_namespace"] for row in copied["authoritative_generations"]] == [
        "radar_market_no_send_a"
    ]
    copied_b = next(
        row for row in copied["non_authoritative_complete_generations"]
        if row["artifact_namespace"] == "radar_market_no_send_b"
    )
    assert copied_b["publication"]["audit_authority_binding_valid"] is False

    publication = original["publication"]
    assert isinstance(publication, dict)
    publication["pointer_operator_state_sha256"] = "0" * 64
    _write_json(
        base / "radar_market_no_send_a" / campaign.PILOT_AUDIT_FILENAME,
        original,
    )
    tampered = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)
    assert tampered["authoritative_generations"] == []
    assert {
        row["artifact_namespace"] for row in tampered["non_authoritative_complete_generations"]
    } == {"radar_market_no_send_a", "radar_market_no_send_b"}
    assert all(
        row["publication"]["audit_authority_binding_valid"] is False
        for row in tampered["non_authoritative_complete_generations"]
    )


def test_campaign_cli_writes_exact_reports_without_copying_request_secrets(
    tmp_path,
    monkeypatch,
    capsys,
):
    base = tmp_path / "artifacts"
    output = tmp_path / "research"
    base.mkdir()
    output.mkdir()
    _fixture(base)
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )

    status = market_no_send_cli.main([
        "campaign-report",
        "--artifact-base", str(base),
        "--output-dir", str(output),
        "--evaluated-at", _EVALUATED,
    ])

    assert status == 0
    stdout = capsys.readouterr().out
    assert "provider_calls=0" in stdout
    json_path = output / campaign.CAMPAIGN_REPORT_JSON_FILENAME
    markdown_path = output / campaign.CAMPAIGN_REPORT_MD_FILENAME
    first_json = json_path.read_bytes()
    first_markdown = markdown_path.read_bytes()
    assert b"secret-token" not in first_json
    assert b"must-not-leak" not in first_json
    assert b"no trade recommendation" in first_markdown.lower()
    assert b"spread-provider selection remains deferred" in first_markdown.lower()
    assert b"Duplicate observations: `0`" in first_markdown
    assert b"Conflicting duplicate observations: `0`" in first_markdown

    assert market_no_send_cli.main([
        "campaign-report",
        "--artifact-base", str(base),
        "--output-dir", str(output),
        "--evaluated-at", _EVALUATED,
    ]) == 0
    capsys.readouterr()
    assert json_path.read_bytes() == first_json
    assert markdown_path.read_bytes() == first_markdown


def test_campaign_make_target_is_read_only_and_does_not_enable_authorization():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "radar-market-campaign-report:" in makefile
    target = makefile.split("radar-market-campaign-report:\n", 1)[1].split(
        "radar-market-no-send:\n", 1
    )[0]
    assert "campaign-report" in target
    assert "--output-dir $(RADAR_MARKET_CAMPAIGN_OUTPUT_DIR)" in target
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" not in target
    assert "radar-market-no-send run" not in target


def test_malformed_generation_is_excluded_and_current_authority_requires_readiness(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    manifest_path = (
        base / "radar_market_no_send_b" / campaign.RUN_MANIFEST_FILENAME
    )
    manifest = market_no_send_io.read_json_object(manifest_path)
    manifest["candidate_count"] = 99
    market_no_send_io.write_json_atomic(manifest_path, manifest)
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)

    def rejected_authority(*_args, **_kwargs):
        raise campaign.dashboard_readiness.DashboardReadinessError(
            "fingerprinted current artifact drifted"
        )

    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        rejected_authority,
    )
    report = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)

    assert report["campaign_metrics"]["real_cycles"] == 1
    assert report["generation_validation"]["excluded_generation_count"] == 1
    excluded = report["excluded_invalid_generations"][0]
    assert excluded["artifact_namespace"] == "radar_market_no_send_b"
    assert any("candidate_count" in reason for reason in excluded["validation_errors"])
    assert report["pointer"]["exact_operator_binding"] is False
    assert report["pointer"]["readiness_validation"] == "failed"
    current = report["authoritative_generations"][0]["publication"]
    assert current["currently_authoritative"] is False


def test_post_generation_integrated_outcome_drift_excludes_generation(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    _write_jsonl(
        base / "radar_market_no_send_b" / "event_integrated_radar_outcomes.jsonl",
        [{
            "outcome_identity_key": "new-generation-pending",
            "candidate_id": "radar_market_no_send_b:0",
            "maturation_state": "pending",
        }],
    )
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )

    report = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)

    assert report["campaign_metrics"]["real_cycles"] == 1
    assert report["generation_validation"]["excluded_generation_count"] == 1
    excluded = report["excluded_invalid_generations"][0]
    assert excluded["artifact_namespace"] == "radar_market_no_send_b"
    assert any("integrated_outcome_artifact_binding" in reason for reason in excluded["validation_errors"])
    assert report["outcomes"]["total"] == 2
    assert report["outcomes"]["pending"] == 2
    assert report["outcomes"]["matured"] == 0
    assert report["outcomes"]["source"] == "canonical_candidate_pending_base"


def test_post_generation_core_drift_excludes_generation(tmp_path, monkeypatch):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    _write_jsonl(
        base / "radar_market_no_send_b" / "event_core_opportunities.jsonl",
        [{"core_opportunity_id": "post-generation-drift"}],
    )
    monkeypatch.setattr(campaign.market_no_send_history_cache, "cache_readiness", _readiness)
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )

    report = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)

    assert report["campaign_metrics"]["real_cycles"] == 1
    excluded = report["excluded_invalid_generations"][0]
    assert excluded["artifact_namespace"] == "radar_market_no_send_b"
    assert any("core_artifact_binding" in reason for reason in excluded["validation_errors"])


def test_unbound_legacy_supporting_rows_cannot_affect_campaign_outcomes(tmp_path):
    manifest_path, manifest, _rows = write_countable_generation(
        tmp_path,
        "legacy_unbound_support",
        "2026-07-13T15:00:00+00:00",
        candidates=[{"candidate_id": "legacy:0", "radar_route": "risk_watch"}],
        legacy=True,
    )
    namespace_dir = manifest_path.parent
    state_path = namespace_dir / campaign.OPERATOR_STATE_FILENAME
    state = market_no_send_io.read_json_object(state_path)
    artifacts = state["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts.pop("core_opportunities")
    artifacts.pop("integrated_outcomes")
    market_no_send_io.write_json_atomic(state_path, state)
    _write_jsonl(
        namespace_dir / "event_integrated_radar_outcomes.jsonl",
        [{"candidate_id": "legacy:0", "maturation_state": "matured"}],
    )

    validation = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    generations, _attempts, excluded = campaign._load_generations(
        tmp_path,
        current_authority={},
    )
    outcomes = campaign._campaign_outcomes(tmp_path, generations)

    assert validation.valid is True
    assert validation.core_artifact_bound is False
    assert validation.integrated_outcome_artifact_bound is False
    assert excluded == []
    assert campaign._outcome_metrics(outcomes)["matured"] == 0
    assert campaign._outcome_metrics(outcomes)["pending"] == 1


def test_legacy_v2_adapter_requires_exact_source_and_request_lineage(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    manifest_path, manifest, _rows = write_countable_generation(
        base,
        "legacy_exact",
        "2026-07-13T15:00:00+00:00",
        candidates=[{"candidate_id": "legacy:0", "radar_route": "risk_watch"}],
        legacy=True,
    )
    namespace_dir = manifest_path.parent
    validation = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    assert validation.valid is True
    assert validation.legacy_adapter is True

    candidate_path = namespace_dir / "event_integrated_radar_candidates.jsonl"
    candidate_bytes = candidate_path.read_bytes()
    candidate_rows = market_no_send_io.read_jsonl(candidate_path)
    candidate_rows[0]["radar_route"] = "diagnostic"
    market_no_send_io.write_jsonl(candidate_path, candidate_rows)
    candidate_drift = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    assert candidate_drift.valid is False
    assert any("candidate_binding" in reason for reason in candidate_drift.validation_errors)
    candidate_path.write_bytes(candidate_bytes)

    source_path = namespace_dir / "event_market_no_send_market_rows.json"
    source = market_no_send_io.read_json_object(source_path)
    source["rows"][0]["symbol"] = "DRIFT"
    market_no_send_io.write_json_atomic(source_path, source)
    drifted = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    assert drifted.valid is False
    assert any("digest" in reason for reason in drifted.validation_errors)


def test_campaign_candidate_digest_and_safety_are_closed(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    manifest_path, manifest, _rows = write_countable_generation(
        base,
        "candidate_closed",
        "2026-07-13T15:00:00+00:00",
        candidates=[{"candidate_id": "closed:0", "radar_route": "risk_watch"}],
    )
    namespace_dir = manifest_path.parent
    candidate_path = namespace_dir / "event_integrated_radar_candidates.jsonl"
    candidates = market_no_send_io.read_jsonl(candidate_path)
    candidates[0]["notification_send_enabled"] = True
    market_no_send_io.write_jsonl(candidate_path, candidates)

    digest_drift = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    assert digest_drift.valid is False
    assert any("candidate_artifact_digest" in reason for reason in digest_drift.validation_errors)

    manifest["candidate_artifact_sha256"] = hashlib.sha256(
        candidate_path.read_bytes()
    ).hexdigest()
    safety_drift = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace_dir.name,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename=campaign.REQUEST_LEDGER_FILENAME,
        safety_counters=SAFETY_COUNTERS,
    )
    assert safety_drift.valid is False
    assert any("candidate_lineage" in reason for reason in safety_drift.validation_errors)
