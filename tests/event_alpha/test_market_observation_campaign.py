"""Artifact-derived Decision Radar observation-campaign report tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import operator_state
from crypto_rsi_scanner.event_alpha.dashboard.readiness import CURRENT_NAMESPACE_POINTER
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli
from crypto_rsi_scanner.event_alpha.operations import daily_operations_publication
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
from crypto_rsi_scanner.event_alpha.operations import market_no_send_audit
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_no_send_publication
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign as campaign
from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign_regime_audit,
)
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign_render
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
                "cold_asset_count": 0,
                "other_asset_count": 0,
            }
        },
        "point_in_time_control_context_readiness": {
            "schema_id": "decision_radar.point_in_time_control_context_readiness",
            "schema_version": 1,
            "status": "partial",
            "retained_observation_count": 9,
            "counted_observation_count": 8,
            "point_in_time_universe_context_row_count": 2,
            "complete_match_context_row_count": 0,
            "field_coverage_counts": {
                "control_liquidity_tier": 2,
                "market_regime": 0,
                "protocol_partition": 0,
            },
            "selection_performed": False,
            "historical_context_backfilled": False,
            "protocol_v2_evidence_eligible": False,
        },
        "current_universe_maturity": {
            "status": "warming",
            "scope": "current_authoritative_universe",
            "expected_asset_count": 2,
            "observed_asset_count": 2,
            "observed_asset_ids": ["test-a", "test-b"],
            "missing_asset_count": 0,
            "missing_asset_ids": [],
            "non_warm_asset_ids": ["test-a", "test-b"],
            "baseline_observation_count": 8,
            "baseline_counted_observation_count": 8,
            "baseline_warm_asset_count": 0,
            "next_cycle_point_in_time_eligible_at": (
                "2026-07-13T18:30:00+00:00"
            ),
            "next_cycle_point_in_time_eligible_asset_count": 0,
            "next_cycle_point_in_time_basis": (
                "same_asset_retained_history_before_future_observation"
            ),
            "baseline_feature_readiness": {
                "volume": {
                    "status_counts": {"warming": 2},
                    "warm_asset_count": 0,
                    "warming_asset_count": 2,
                    "cold_asset_count": 0,
                    "other_asset_count": 0,
                    "asset_count": 2,
                    "minimum_sample_count": 4,
                    "maximum_sample_count": 4,
                    "required_sample_count": 8,
                    "sample_count_deficit_asset_count": 2,
                    "minimum_coverage_seconds": 10_800,
                    "maximum_coverage_seconds": 10_800,
                    "required_coverage_seconds": 25_200,
                    "coverage_deficit_asset_count": 2,
                    "next_cycle_point_in_time_eligible_asset_count": 0,
                    "deficit_assets": [
                        {
                            "canonical_asset_id": asset_id,
                            "status": "warming",
                            "sample_count": 4,
                            "required_sample_count": 8,
                            "sample_deficit": 4,
                            "coverage_seconds": 10_800,
                            "required_coverage_seconds": 25_200,
                            "coverage_deficit_seconds": 14_400,
                        }
                        for asset_id in ("test-a", "test-b")
                    ],
                }
            },
            "research_only": True,
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
            current_market_observations=(
                {"canonical_asset_id": "test-a"},
                {"canonical_asset_id": "test-b"},
            ),
        )
    )


def _current_regime_market_rows(observed_at: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank in range(1, 31):
        asset_id = (
            "bitcoin" if rank == 1
            else "pump-fun" if rank == 16
            else "whitebit" if rank == 28
            else f"asset-{rank:02d}"
        )
        symbol = "BTC" if rank == 1 else "PUMP" if rank == 16 else "WBT" if rank == 28 else f"A{rank:02d}"
        observation_id = f"current-regime-observation-{rank}"
        anchor_id = f"current-regime-anchor-{rank}"
        row: dict[str, object] = {
            "canonical_asset_id": asset_id,
            "symbol": symbol,
            "observed_at": observed_at,
            "point_in_time_universe_member": True,
            "point_in_time_volume_rank": rank,
            "point_in_time_universe_size": 30,
            "point_in_time_universe_limit": 30,
            "point_in_time_universe_policy": (
                "bounded_top_liquid_by_total_volume"
            ),
            "market_history": {
                "baseline_counted": True,
                "observation_id": observation_id,
            },
            "return_24h": float(rank) / 1000.0,
            "return_unit": "fraction",
            "market_feature_basis": {
                "returns": "provider_derived_sparkline",
            },
            "temporal_return_24h": float(rank) / 10.0,
            "return_units": {"temporal_return_24h": "percent_points"},
            "market_feature_evidence": {
                "temporal_return_24h": {
                    "basis": "temporal_baseline",
                    "status": "ready",
                    "calculation": "price_horizon_return",
                    "sample_count": 1,
                    "current_observation_id": observation_id,
                    "baseline_first_observation_id": anchor_id,
                    "baseline_last_observation_id": anchor_id,
                    "baseline_input_observation_count": 1,
                    "baseline_observation_ids_sha256": hashlib.sha256(
                        json.dumps([anchor_id], separators=(",", ":")).encode(
                            "utf-8"
                        )
                    ).hexdigest(),
                    "providers": ["coingecko"],
                    "data_modes": ["live"],
                    "research_only": True,
                }
            },
            "research_only": True,
        }
        if rank in {16, 28}:
            row.pop("temporal_return_24h")
            row["return_units"] = {}
            row["market_feature_evidence"] = {}
        rows.append(row)
    return rows


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


def test_current_authority_regime_input_replay_binds_exact_source_and_names_gaps(
    tmp_path,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    namespace = "radar_market_no_send_regime"
    observed_at = "2026-07-20T08:17:58.624044+00:00"
    _manifest_path, manifest, _candidates = write_countable_generation(
        base,
        namespace,
        observed_at,
        candidates=[],
        market_rows=_current_regime_market_rows(observed_at),
    )
    namespace_dir = base / namespace
    snapshot = (
        campaign.market_observation_campaign_snapshots
        .capture_market_source_snapshot(
            namespace_dir,
            manifest=manifest,
            artifact="event_market_no_send_market_rows.json",
        )
    )
    authority = {
        "artifact_namespace": namespace,
        "run_id": manifest["run_id"],
        "revision": 7,
        "operator_state_sha256": "a" * 64,
    }

    value = campaign._current_control_regime_input(
        current_authority=authority,
        market_source_snapshot=snapshot,
    )

    assert value["status"] == "incomplete"
    assert value["source_artifact_sha256"] == manifest["request_cache_sha256"]
    assert value["source_snapshot_verified"] is True
    diagnostic = value["diagnostic"]
    assert diagnostic["eligible_input_count"] == 28
    assert diagnostic["missing_input_count"] == 2
    assert diagnostic["missing_inputs_with_current_snapshot_return_count"] == 2
    assert [row["canonical_asset_id"] for row in diagnostic["missing_inputs"]] == [
        "pump-fun",
        "whitebit",
    ]
    assert value["retained_history_mutated"] is False
    assert value["provider_calls"] == value["writes"] == 0
    assert campaign.current_control_regime_input_valid(
        value,
        expected_authority=authority,
    )
    rendered = "\n".join(
        market_observation_campaign_render._current_control_regime_input_lines(
            value
        )
    )
    assert "Eligible causal 24-hour inputs: `28/30`" in rendered
    assert "`pump-fun (PUMP), rank 16`" in rendered
    assert "`whitebit (WBT), rank 28`" in rendered
    assert "current-snapshot 24-hour return: `2.8%`" in rendered.casefold()
    assert "never a substitute for a retained temporal anchor" in rendered
    assert "historical backfill: `false`" in rendered

    source_path = namespace_dir / "event_market_no_send_market_rows.json"
    source = market_no_send_io.read_json_object(source_path)
    source["rows"][0]["temporal_return_24h"] = 999.0
    market_no_send_io.write_json_atomic(source_path, source)
    with pytest.raises(
        campaign.MarketNoSendError,
        match="market_source_snapshot_digest_mismatch",
    ):
        (
            campaign.market_observation_campaign_snapshots
            .capture_market_source_snapshot(
                namespace_dir,
                manifest=manifest,
                artifact="event_market_no_send_market_rows.json",
            )
        )


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
    assert first["campaign_metrics"]["real_observations"] == 3
    assert first["campaign_metrics"]["baseline_counted_observation_count"] == 8
    assert first["campaign_metrics"]["too_close_observation_count"] == 1
    assert first["campaign_metrics"]["real_candidates"] == 3
    assert first["campaign_metrics"]["current_ideas"] == 2
    assert first["campaign_metrics"]["historical_ideas"] == 1
    assert first["campaign_metrics"]["route_counts"] == {
        "dashboard_watch": 1,
        "diagnostic": 1,
        "risk_watch": 1,
    }
    assert first["campaign_metrics"]["direct_feature_count"] == 13
    assert first["campaign_metrics"]["proxy_feature_count"] == 6
    assert len(first["authoritative_generations"]) == 1
    assert len(first["non_authoritative_complete_generations"]) == 1
    assert first["authoritative_generations"][0][
        "current_authority_control_market_regime_input"
    ]["current_authority_only"] is True
    assert first["non_authoritative_complete_generations"][0][
        "current_authority_control_market_regime_input"
    ] is None
    assert len(first["provider_failed_attempts"]) == 1
    assert len(first["blocked_or_preflight_attempts"]) == 1
    assert first["outcomes"]["source"] == "canonical_candidate_pending_base"
    assert first["outcomes"]["pending"] == 3
    assert first["outcomes"]["matured"] == 0
    assert first["human_review_timing"]["status"] == "no_events"
    assert first["human_review_queue"]["status"] == "no_eligible_ideas"
    assert first["campaign_metrics"]["review_timing_first_views"] == 0
    assert first["campaign_metrics"]["review_timing_completed_reviews"] == 0
    assert first["campaign_metrics"]["review_timing_action_required"] == 0
    assert first["pointer"]["exact_operator_binding"] is True
    shadow_audit = first["shadow_temporal_surprise_campaign_audit"]
    assert shadow_audit["status"] == "unavailable"
    assert shadow_audit["source_history"]["status"] == "missing"
    assert shadow_audit["source_history"]["row_count"] == 0
    assert shadow_audit["input_row_count"] == 0
    assert shadow_audit["excluded_not_baseline_counted_count"] == 0
    assert shadow_audit["input_rejected_count"] == 0
    assert shadow_audit["valid_baseline_counted_row_count"] == 0
    assert shadow_audit["evaluated_observation_count"] == 0
    assert shadow_audit["evaluation_error_count"] == 0
    assert shadow_audit["provider_calls"] == 0
    assert shadow_audit["writes"] == 0
    assert shadow_audit["routing_eligible"] is False
    assert shadow_audit["protocol_v2_evidence_eligible"] is False
    regime_audit = first["control_market_regime_generation_audit"]
    assert regime_audit["status"] == "unavailable"
    assert regime_audit["input_generation_count"] == 2
    assert regime_audit["verified_source_generation_count"] == 2
    assert regime_audit["source_row_count"] == 3
    assert regime_audit["complete_universe_generation_count"] == 0
    assert regime_audit["ready_generation_count"] == 0
    assert regime_audit["incomplete_generation_count"] == 0
    assert regime_audit["latest_complete_generation"] is None
    assert regime_audit["routing_eligible"] is False
    assert regime_audit["protocol_v2_evidence_eligible"] is False
    conclusion = first["campaign_v2_conclusion"]
    assert conclusion["baseline_status"] == "warming"
    assert conclusion["baseline_coverage"] == {
        "retained_observations": 9,
        "counted_observations": 8,
        "asset_count": 2,
        "warm_asset_count": 0,
    }
    assert conclusion["current_universe_baseline"] == {
        "status": "warming",
        "expected_asset_count": 2,
        "observed_asset_count": 2,
        "warm_asset_count": 0,
        "missing_asset_count": 0,
    }
    assert conclusion["pointer_history_count"] == 1
    assert conclusion["current_authority"]["artifact_namespace"] == (
        "radar_market_no_send_a"
    )
    assert conclusion["current_authority"]["exact_operator_binding"] is True
    assert conclusion["spread_provider_selection"] == (
        "selected_bybit_usdt_linear_perpetuals"
    )
    assert conclusion["spread_evidence_status"] == (
        "awaiting_authorized_immutable_capture"
    )
    assert conclusion["spread_readiness_command"] == (
        "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
    )
    assert conclusion["data_quality_limitation_categories"] == [
        "execution_quality_spread",
        "proxy_market_features",
        "temporal_baseline_maturity",
    ]
    spread_limit = first["data_quality_limitations"][0]
    assert spread_limit["provider_selection"] == (
        "selected_bybit_usdt_linear_perpetuals"
    )
    assert spread_limit["evidence_status"] == (
        "awaiting_authorized_immutable_capture"
    )
    assert spread_limit["next_safe_command"] == (
        "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
    )
    assert "explicit_flag_plus_CONFIRM=1" in spread_limit["authorization_boundary"]
    assert first["next_observation"]["eligible_now"] is False
    assert first["safety"]["provider_calls_made_by_report"] == 0
    assert all(
        row["campaign_counting_source"]
        == "decision_radar_campaign_contract"
        for row in (*first["authoritative_generations"], *first["non_authoritative_complete_generations"])
    )
    markdown = market_observation_campaign_render.format_campaign_report(first)
    assert "Latest exact-generation row readiness" in markdown
    assert "Retained-history maturity and latest point-in-time feature availability are separate" in markdown
    assert "Retained-history feature maturity for current-universe assets" in markdown
    assert "Future-observation eligibility is conditional on the same canonical asset" in markdown
    assert "Existing history cadence boundary" in markdown
    assert "Provider-call eligibility: `not inferred`" in markdown
    assert "Prospective matched-control context" in markdown
    assert "Exact current control-regime input replay" in markdown
    assert "Exact-generation control-regime history" in markdown
    assert "membership overlap is descriptive, not causal attribution" in markdown
    assert "Retained history mutated by report: `false`" in markdown
    assert "Complete point-in-time universe rows: `2/8`" in markdown
    assert "Complete matched-control context rows: `0/8`" in markdown
    assert "Market-regime coverage: `0/8`" in markdown
    assert "Historical context backfilled: `false`" in markdown
    assert "test-a [warming; samples 4/8 (gap 4)" in markdown
    assert "Causal temporal-surprise replay" in markdown
    assert "does not mean every projection is ready" in markdown

    tampered = json.loads(json.dumps(first))
    tampered["shadow_temporal_surprise_campaign_audit"]["routing_eligible"] = True
    with pytest.raises(
        campaign.MarketNoSendError,
        match="shadow temporal-surprise campaign audit invalid",
    ):
        campaign.format_campaign_report(tampered)

    tampered = json.loads(json.dumps(first))
    tampered["control_market_regime_generation_audit"][
        "routing_eligible"
    ] = True
    with pytest.raises(
        campaign.MarketNoSendError,
        match="control market-regime generation audit invalid",
    ):
        campaign.format_campaign_report(tampered)


def test_outcome_recovery_projection_matches_full_report_without_unrelated_analytics(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        _readiness,
    )
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )
    full = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)

    def unrelated_analytics_must_not_run(*_args, **_kwargs):
        raise AssertionError("outcome recovery rebuilt unrelated campaign analytics")

    monkeypatch.setattr(
        campaign.market_observation_campaign_shadow_surprise,
        "build_campaign_shadow_surprise_audit",
        unrelated_analytics_must_not_run,
    )
    monkeypatch.setattr(
        campaign.market_observation_campaign_baseline,
        "build_baseline_maturity",
        unrelated_analytics_must_not_run,
    )
    monkeypatch.setattr(
        campaign.market_observation_campaign_episodes,
        "build_campaign_anomaly_episode_shadow",
        unrelated_analytics_must_not_run,
    )
    monkeypatch.setattr(
        campaign.decision_review_timing_queue,
        "build_review_timing_queue",
        unrelated_analytics_must_not_run,
    )

    projection = campaign.build_outcome_recovery_projection(
        base,
        evaluated_at=_EVALUATED,
    )

    assert projection["schema_id"] == campaign.OUTCOME_RECOVERY_PROJECTION_SCHEMA
    assert projection["schema_version"] == (
        campaign.OUTCOME_RECOVERY_PROJECTION_VERSION
    )
    assert projection["projection_scope"] == (
        "exact_pointer_counted_candidates_outcome_ledger_and_market_history"
    )
    assert projection["full_campaign_report_rebuilt"] is False
    assert projection["generation_count"] == 2
    assert projection["counted_generation_count"] == 2
    assert projection["pointer"] == full["pointer"]
    assert projection["outcomes"] == full["outcomes"]
    assert projection["safety"] == {
        "provider_calls": 0,
        "writes": 0,
        "history_mutated": False,
        "outcomes_mutated": False,
        "research_only": True,
    }


def test_review_timing_projection_matches_full_generation_truth_without_analytics(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        _readiness,
    )
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )
    full = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)
    full_generations = (
        *full["authoritative_generations"],
        *full["non_authoritative_complete_generations"],
    )

    def unrelated_analytics_must_not_run(*_args, **_kwargs):
        raise AssertionError("review queue rebuilt unrelated campaign analytics")

    for owner, field in (
        (
            campaign.market_observation_campaign_shadow_surprise,
            "build_campaign_shadow_surprise_audit",
        ),
        (
            campaign.market_observation_campaign_baseline,
            "build_baseline_maturity",
        ),
        (
            campaign.market_observation_campaign_episodes,
            "build_campaign_anomaly_episode_shadow",
        ),
        (
            campaign.market_observation_campaign_scorecard,
            "build_campaign_decision_episode_scorecard",
        ),
    ):
        monkeypatch.setattr(owner, field, unrelated_analytics_must_not_run)

    projection = campaign.build_review_timing_generation_projection(
        base,
        evaluated_at=_EVALUATED,
    )
    expected = sorted(
        (
            {
                "artifact_namespace": row["artifact_namespace"],
                "campaign_counted": row["campaign_counted"],
                "candidate_count": row["candidate_count"],
                "publication": {
                    field: row["publication"][field]
                    for field in (
                        "ever_authoritative",
                        "final_publication_receipt_valid",
                        "operations_receipt_valid",
                    )
                },
            }
            for row in full_generations
        ),
        key=lambda row: row["artifact_namespace"],
    )

    assert projection["schema_id"] == (
        campaign.REVIEW_TIMING_GENERATION_PROJECTION_SCHEMA
    )
    assert projection["schema_version"] == (
        campaign.REVIEW_TIMING_GENERATION_PROJECTION_VERSION
    )
    assert projection["projection_scope"] == (
        "exact_complete_generation_counting_and_final_receipt_state"
    )
    assert projection["full_campaign_report_rebuilt"] is False
    assert projection["generation_count"] == len(full_generations) == 2
    assert sorted(
        projection["generation_summaries"],
        key=lambda row: row["artifact_namespace"],
    ) == expected
    assert projection["safety"] == {
        "provider_calls": 0,
        "writes": 0,
        "review_events_created": 0,
        "dashboard_authority_mutated": False,
        "research_only": True,
    }


def _ready_regime_market_rows(observed_at: str) -> list[dict[str, object]]:
    rows = _current_regime_market_rows(observed_at)
    for rank, row in enumerate(rows, start=1):
        observation_id = row["market_history"]["observation_id"]
        anchor_id = f"ready-regime-anchor-{rank}"
        row["temporal_return_24h"] = float(rank) / 10.0
        row["return_units"]["temporal_return_24h"] = "percent_points"
        row["market_feature_evidence"]["temporal_return_24h"] = {
            "basis": "temporal_baseline",
            "status": "ready",
            "calculation": "price_horizon_return",
            "sample_count": 1,
            "current_observation_id": observation_id,
            "baseline_first_observation_id": anchor_id,
            "baseline_last_observation_id": anchor_id,
            "baseline_input_observation_count": 1,
            "baseline_observation_ids_sha256": hashlib.sha256(
                json.dumps([anchor_id], separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest(),
            "providers": ["coingecko"],
            "data_modes": ["live"],
            "research_only": True,
        }
    return rows


def _regime_audit_generation(
    namespace: str,
    observed_at: str,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "artifact_namespace": namespace,
        "run_id": f"{observed_at}|no_key_live",
        "observed_at": observed_at,
        "campaign_counted": True,
        "_market_source_snapshot_rows": rows,
        "_market_source_snapshot_sha256": hashlib.sha256(
            namespace.encode("utf-8")
        ).hexdigest(),
        "_market_source_snapshot_row_count": len(rows),
        "_market_source_snapshot_verified": True,
    }


def test_control_regime_generation_audit_separates_recent_entry_overlap():
    first_at = "2026-07-20T10:00:00+00:00"
    second_at = "2026-07-20T11:00:00+00:00"
    third_at = "2026-07-20T12:00:00+00:00"
    first_rows = _ready_regime_market_rows(first_at)
    second_rows = _ready_regime_market_rows(second_at)
    third_rows = _ready_regime_market_rows(third_at)
    for rows in (second_rows, third_rows):
        replacement = rows[-1]
        replacement["canonical_asset_id"] = "new-entry"
        replacement["symbol"] = "NEW"
        replacement.pop("temporal_return_24h")
        replacement["return_units"].pop("temporal_return_24h")
        replacement["market_feature_evidence"].pop("temporal_return_24h")

    audit = (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit([
            _regime_audit_generation("generation-a", first_at, first_rows),
            _regime_audit_generation("generation-b", second_at, second_rows),
            _regime_audit_generation("generation-c", third_at, third_rows),
        ])
    )

    assert audit["status"] == "incomplete"
    assert audit["complete_universe_generation_count"] == 3
    assert audit["ready_generation_count"] == 1
    assert audit["incomplete_generation_count"] == 2
    assert audit["transition_count"] == 2
    assert audit["universe_change_transition_count"] == 1
    assert audit["entered_asset_event_count"] == 1
    assert audit["exited_asset_event_count"] == 1
    assert audit["incomplete_with_recent_entry_count"] == 2
    assert audit["incomplete_without_recent_entry_count"] == 0
    assert audit["recent_entry_missing_asset_event_count"] == 2
    assert audit["missing_asset_generation_counts"] == {"new-entry": 2}
    assert audit["schema_version"] == 4
    assert audit["membership_clock_scope"] == (
        "prospective_complete_point_in_time_universes_only"
    )
    assert audit["precontract_history_used_for_membership_clock"] is False
    assert audit["latest_missing_input_anchor_audit"]["status"] == (
        "unavailable"
    )
    assert audit["latest_missing_input_anchor_audit"]["reason"] == (
        "retained_history_unavailable"
    )
    cadence = audit["observation_cadence_gap_audit"]
    assert cadence["status"] == "within_anchor_tolerance"
    assert cadence["complete_generation_count"] == 3
    assert cadence["adjacent_interval_count"] == 2
    assert cadence["anchor_tolerance_seconds"] == 21_600
    assert cadence["within_anchor_tolerance_interval_count"] == 2
    assert cadence["exceeding_anchor_tolerance_interval_count"] == 0
    assert cadence["latest_interval"]["interval_seconds"] == 3_600.0
    assert cadence["maximum_interval"]["interval_seconds"] == 3_600.0
    assert cadence["gap_examples"] == []
    assert cadence["future_endpoint_eligibility_inferred"] is False
    assert audit["latest_complete_generation"][
        "recent_entry_missing_asset_ids"
    ] == ["new-entry"]
    membership = audit["latest_complete_generation"][
        "missing_input_membership_context"
    ]
    assert membership == [{
        "canonical_asset_id": "new-entry",
        "membership_start_known": True,
        "membership_start_basis": "observed_entry",
        "continuous_membership_started_at": second_at,
        "continuous_membership_age_seconds": 3_600,
        "within_recent_membership_window": True,
        "anchor_eligibility_inferred": False,
    }]
    assert (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(audit)
    ) == []

    tampered = json.loads(json.dumps(audit))
    tampered["incomplete_with_recent_entry_count"] = 3
    assert "incomplete_generation_count_not_closed" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )

    tampered = json.loads(json.dumps(audit))
    tampered["latest_complete_generation"][
        "missing_input_membership_context"
    ][0]["continuous_membership_age_seconds"] = 3_601
    assert "latest_membership_context_0_age_invalid" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )

    tampered = json.loads(json.dumps(audit))
    tampered["latest_complete_generation"][
        "missing_input_membership_context"
    ][0]["anchor_eligibility_inferred"] = True
    assert "latest_membership_context_0_anchor_eligibility_invalid" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )


def test_control_regime_generation_audit_measures_exact_cadence_gap() -> None:
    first_at = "2026-07-20T19:41:41.729110+00:00"
    second_at = "2026-07-21T09:05:58.044865+00:00"
    third_at = "2026-07-21T10:05:58.044865+00:00"
    audit = (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit([
            _regime_audit_generation(
                "cadence-generation-a",
                first_at,
                _ready_regime_market_rows(first_at),
            ),
            _regime_audit_generation(
                "cadence-generation-b",
                second_at,
                _ready_regime_market_rows(second_at),
            ),
            _regime_audit_generation(
                "cadence-generation-c",
                third_at,
                _ready_regime_market_rows(third_at),
            ),
        ])
    )

    cadence = audit["observation_cadence_gap_audit"]
    assert cadence["status"] == "gaps_observed"
    assert cadence["complete_generation_count"] == 3
    assert cadence["adjacent_interval_count"] == 2
    assert cadence["within_anchor_tolerance_interval_count"] == 1
    assert cadence["exceeding_anchor_tolerance_interval_count"] == 1
    assert cadence["latest_interval"]["interval_seconds"] == 3_600.0
    assert cadence["latest_interval"]["exceeds_anchor_tolerance"] is False
    assert cadence["maximum_interval"] == cadence["gap_examples"][0]
    assert cadence["maximum_interval"]["start_observed_at"] == first_at
    assert cadence["maximum_interval"]["end_observed_at"] == second_at
    assert cadence["maximum_interval"]["interval_seconds"] == 48_256.315755
    assert cadence["maximum_interval"]["excess_seconds"] == 26_656.315755
    assert cadence["gap_examples_truncated"] is False
    assert cadence["future_endpoint_eligibility_inferred"] is False
    cadence_summary = (
        market_observation_campaign_render._cadence_gap_audit_summary(cadence)
    )
    assert "1/2 adjacent intervals exceed" in cadence_summary
    assert "maximum 13.4h" in cadence_summary
    assert "continuity risk only" in cadence_summary
    limitations = campaign._data_quality_limitations(
        {
            "selected_market_row_count": 1,
            "spread_available_count": 1,
            "proxy_feature_count": 0,
            "current_universe_baseline_status": "warm",
            "baseline_status": "warm",
        },
        regime_audit=audit,
    )
    assert len(limitations) == 1
    cadence_limitation = limitations[0]
    assert cadence_limitation["category"] == "observation_cadence_continuity"
    assert cadence_limitation["complete_generation_count"] == 3
    assert cadence_limitation["adjacent_interval_count"] == 2
    assert cadence_limitation["exceeding_anchor_tolerance_interval_count"] == 1
    assert cadence_limitation["anchor_tolerance_seconds"] == 21_600
    assert cadence_limitation["maximum_interval"] == cadence["maximum_interval"]
    assert cadence_limitation["future_endpoint_eligibility_inferred"] is False
    assert cadence_limitation["scheduling_policy_changed"] is False
    assert cadence_limitation["provider_calls"] == cadence_limitation["writes"] == 0
    assert (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(audit)
    ) == []

    tampered = json.loads(json.dumps(audit))
    tampered["observation_cadence_gap_audit"]["gap_examples"][0][
        "excess_seconds"
    ] += 1
    assert "cadence_gap_example_0_derivation_invalid" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )

    tampered = json.loads(json.dumps(audit))
    tampered["observation_cadence_gap_audit"][
        "future_endpoint_eligibility_inferred"
    ] = True
    assert "cadence_gap_future_endpoint_eligibility_inferred_invalid" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )


def test_observation_cadence_gap_audit_closes_empty_and_single_clock() -> None:
    empty = (
        market_observation_campaign_regime_audit
        .build_observation_cadence_gap_audit([])
    )
    assert empty["status"] == "empty"
    assert empty["complete_generation_count"] == 0
    assert empty["latest_interval"] is None
    assert empty["maximum_interval"] is None

    observed_at = "2026-07-20T19:41:41.729110+00:00"
    single = (
        market_observation_campaign_regime_audit
        .build_observation_cadence_gap_audit([{
            "artifact_namespace": "single-generation",
            "run_id": f"{observed_at}|no_key_live",
            "observed_at": observed_at,
        }])
    )
    assert single["status"] == "insufficient_history"
    assert single["complete_generation_count"] == 1
    assert single["adjacent_interval_count"] == 0
    assert single["gap_examples"] == []


def test_control_regime_generation_audit_keeps_schema_v3_readable() -> None:
    observed_at = "2026-07-20T19:41:41.729110+00:00"
    current = (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit([
            _regime_audit_generation(
                "legacy-generation",
                observed_at,
                _ready_regime_market_rows(observed_at),
            )
        ])
    )
    legacy = json.loads(json.dumps(current))
    legacy["schema_version"] = 3
    legacy.pop("observation_cadence_gap_audit")

    assert (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(legacy)
    ) == []

    drifted = json.loads(json.dumps(current))
    drifted["observation_cadence_gap_audit"]["complete_generation_count"] = 2
    drifted["observation_cadence_gap_audit"]["adjacent_interval_count"] = 1
    assert "cadence_gap_complete_generation_count_mismatch" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(drifted)
    )


def test_control_regime_generation_audit_does_not_invent_first_entry_clock():
    observed_at = "2026-07-20T10:00:00+00:00"
    rows = _ready_regime_market_rows(observed_at)
    missing = rows[-1]
    missing.pop("temporal_return_24h")
    missing["return_units"].pop("temporal_return_24h")
    missing["market_feature_evidence"].pop("temporal_return_24h")

    audit = (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit([
            _regime_audit_generation("generation-a", observed_at, rows),
        ])
    )

    assert audit["latest_complete_generation"][
        "missing_input_membership_context"
    ] == [{
        "canonical_asset_id": "asset-30",
        "membership_start_known": False,
        "membership_start_basis": "unknown_before_first_complete_generation",
        "continuous_membership_started_at": None,
        "continuous_membership_age_seconds": None,
        "within_recent_membership_window": False,
        "anchor_eligibility_inferred": False,
    }]
    assert audit["latest_complete_generation"][
        "recent_entry_missing_asset_ids"
    ] == []


def test_control_regime_generation_audit_explains_latest_anchor_window():
    observed_at = "2026-07-22T00:12:04.506884+00:00"
    rows = _ready_regime_market_rows(observed_at)
    missing = rows[-1]
    missing["price"] = 110.0
    missing.pop("temporal_return_24h")
    missing["return_units"].pop("temporal_return_24h")
    missing["market_feature_evidence"].pop("temporal_return_24h")
    asset_id = missing["canonical_asset_id"]
    endpoint_id = missing["market_history"]["observation_id"]
    history_rows = [
        {
            "canonical_asset_id": asset_id,
            "observation_id": "anchor-too-old",
            "observed_at": "2026-07-19T23:45:20.832390+00:00",
            "price": 99.0,
        },
        {
            "canonical_asset_id": asset_id,
            "observation_id": "post-target-observation",
            "observed_at": "2026-07-21T12:12:41.339533+00:00",
            "price": 105.0,
        },
        {
            "canonical_asset_id": asset_id,
            "observation_id": endpoint_id,
            "observed_at": observed_at,
            "price": 110.0,
        },
    ]
    audit = (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit(
            [_regime_audit_generation("generation-a", observed_at, rows)],
            retained_history_snapshot={
                "status": "observed",
                "artifact": "event_market_history.jsonl",
                "sha256": "a" * 64,
                "size_bytes": 1_024,
                "row_count": len(history_rows),
                "binding_source": "campaign_market_history_exact_bytes",
                "rows": history_rows,
            },
        )
    )

    anchor_audit = audit["latest_missing_input_anchor_audit"]
    assert anchor_audit["status"] == "observed"
    assert anchor_audit["reason"] == "anchor_windows_replayed"
    assert anchor_audit["missing_input_count"] == 1
    assert anchor_audit["all_missing_inputs_explained"] is True
    diagnostic = anchor_audit["diagnostics"][0]
    assert diagnostic["canonical_asset_id"] == asset_id
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["reason"] == "latest_causal_anchor_before_window"
    assert diagnostic["target_at"] == "2026-07-21T00:12:04.506884+00:00"
    assert diagnostic["anchor_window_start_at"] == (
        "2026-07-20T18:12:04.506884+00:00"
    )
    assert diagnostic["candidate_anchor_count"] == 0
    assert diagnostic["nearest_causal_before_window"]["observation_id"] == (
        "anchor-too-old"
    )
    assert diagnostic["nearest_post_target_observation"]["observation_id"] == (
        "post-target-observation"
    )
    assert diagnostic["future_endpoint_eligibility_inferred"] is False

    tampered = json.loads(json.dumps(audit))
    tampered["latest_missing_input_anchor_audit"]["diagnostics"][0][
        "future_endpoint_eligibility_inferred"
    ] = True
    assert "anchor_audit_diagnostic_invalid" in (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(tampered)
    )


def test_final_receipts_reconcile_attempt_publication_operations_and_current(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    namespace = "radar_market_no_send_a"
    namespace_dir = base / namespace
    operator_path = namespace_dir / campaign.OPERATOR_STATE_FILENAME
    operator_path.unlink()
    run_id = "2026-07-13T15:00:00+00:00|no_key_live"
    run_ledger = namespace_dir / "event_alpha_runs.jsonl"
    market_no_send_io.write_jsonl(
        run_ledger,
        [{
            "run_id": run_id,
            "profile": "no_key_live",
            "artifact_namespace": namespace,
            "run_mode": "operational",
        }],
    )
    operator = operator_state.begin_run(
        namespace_dir,
        {
            "run_id": run_id,
            "profile": "no_key_live",
            "artifact_namespace": namespace,
            "run_mode": "operational",
        },
        run_ledger_path=run_ledger,
        updated_at=datetime.fromisoformat("2026-07-13T17:30:00+00:00"),
    )
    operator = operator_state.record_doctor_status(
        namespace_dir,
        run_id=run_id,
        profile="no_key_live",
        artifact_namespace=namespace,
        expected_revision=int(operator["revision"]),
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        blocker_count=0,
        warning_count=0,
        checked_at=datetime.fromisoformat("2026-07-13T17:30:00+00:00"),
    )
    pointer = market_no_send_io.read_json_object(base / CURRENT_NAMESPACE_POINTER)
    pointer["profile"] = operator["profile"]
    pointer["run_id"] = operator["run_id"]
    pointer["revision"] = operator["revision"]
    pointer["operator_state_sha256"] = operator_state.operator_authority_digest(
        operator
    )
    market_no_send_io.write_json_atomic(base / CURRENT_NAMESPACE_POINTER, pointer)
    audit_path = namespace_dir / campaign.PILOT_AUDIT_FILENAME
    audit = market_no_send_io.read_json_object(audit_path)
    audit["publication"]["status"] = "not_published"
    audit["exact_operator_revision"] = operator["revision"]
    audit["publication"]["pointer_revision"] = operator["revision"]
    audit["publication"]["pointer_operator_state_sha256"] = pointer[
        "operator_state_sha256"
    ]
    market_no_send_io.write_json_atomic(audit_path, audit)
    cycle_id = "c" * 32
    _write_jsonl(
        base / daily_operations_publication.CYCLE_LEDGER_FILENAME,
        [{
            "contract_version": 1,
            "row_type": "decision_radar_daily_operations_cycle",
            "cycle_id": cycle_id,
            "recorded_at": "2026-07-13T17:31:00+00:00",
            "artifact_namespace": namespace,
            "status": "succeeded",
            "reason": "published_and_restarted",
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "pointer_published": True,
            "dashboard_restarted": True,
            "pointer_rolled_back": False,
            "pointer_invalidated": False,
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        }],
    )
    _write_json(
        base / daily_operations_publication.STATE_FILENAME,
        {
            "contract_version": 1,
            "row_type": "decision_radar_daily_operations_state",
            "updated_at": "2026-07-13T17:31:00+00:00",
            "last_cycle_id": cycle_id,
            "last_cycle_status": "succeeded",
            "last_cycle_reason": "published_and_restarted",
            "last_cycle_namespace": namespace,
            "last_successful_namespace": namespace,
            "last_successful_publication": "2026-07-13T17:31:00+00:00",
            "last_readiness_check": "2026-07-13T17:30:00+00:00",
            "live_provider_authorized": True,
            "provider_call_attempted": True,
            "pointer_published": True,
            "dashboard_restarted": True,
            "pointer_invalidated": False,
            "scheduler_enabled": False,
            "scheduler_loaded": False,
            "scheduler_healthy": True,
            "scheduler_reason": "not_installed",
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        },
    )
    daily_operations_publication.reconcile_current_publication(
        base,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at="2026-07-13T17:32:00+00:00",
    )
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        _readiness,
    )
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        _dashboard_authority,
    )
    monkeypatch.setattr(
        campaign.decision_review_timing_queue,
        "build_review_timing_queue",
        lambda *_args, **_kwargs: {
            "schema_id": "decision_radar.idea_review_timing_queue",
            "schema_version": 1,
            "generated_at": _EVALUATED,
            "status": "no_eligible_ideas",
            "eligible_generation_count": 0,
            "eligible_idea_count": 0,
            "action_required_count": 0,
            "not_viewed_count": 0,
            "in_review_count": 0,
            "complete_count": 0,
            "skipped_candidate_count": 2,
            "skipped_generation_reason_counts": {
                "minimal_publication_fixture": 1
            },
            "events_in_window_count": 0,
            "events_after_evaluated_at_count": 0,
            "records": [],
        },
    )

    report = campaign.build_campaign_report(base, evaluated_at=_EVALUATED)
    current = next(
        row for row in report["authoritative_generations"]
        if row["artifact_namespace"] == namespace
    )["publication"]

    assert current["attempt_audit_status"] == "not_published"
    assert current["publication_status"] == "published"
    assert current["operations_status"] == "dashboard_restarted"
    assert current["audit_status"] == "published"
    assert current["currently_authoritative"] is True
    assert current["final_publication_receipt_valid"] is True
    assert current["operations_receipt_valid"] is True
    assert current["first_authoritative_at"] == "2026-07-13T17:31:00+00:00"
    assert current["contract_errors"] == []


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
        "make radar-daily-ops-readiness PYTHON=.venv/bin/python"
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
    assert prior["publication"]["ever_authoritative"] is True
    assert prior["publication"]["first_authoritative_at"] == (
        "2026-07-13T17:31:00+00:00"
    )
    assert prior["publication"]["audit_authority_binding_valid"] is True
    assert prior["publication"]["authority_source"] == (
        "pilot_audit_exact_binding"
    )
    assert prior["publication"]["attempt_audit_status"] == "not_published"
    assert prior["publication"]["publication_status"] == (
        "published_legacy_audit"
    )
    assert prior["publication"]["audit_status"] == "published_legacy_audit"
    assert prior["publication"]["operations_status"] == "legacy_not_recorded"
    assert prior["publication"]["currently_authoritative"] is False
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


def test_canonical_managed_namespace_cannot_fall_back_to_legacy_audit(
    tmp_path,
) -> None:
    base = tmp_path / "artifacts"
    base.mkdir()
    _fixture(base)
    namespace = "radar_market_no_send_a"
    namespace_dir = base / namespace
    manifest = market_no_send_io.read_json_object(
        namespace_dir / campaign.RUN_MANIFEST_FILENAME
    )
    audit = market_no_send_io.read_json_object(
        namespace_dir / campaign.PILOT_AUDIT_FILENAME
    )
    operator = market_no_send_io.read_json_object(
        namespace_dir / campaign.OPERATOR_STATE_FILENAME
    )
    pointer = market_no_send_io.read_json_object(base / CURRENT_NAMESPACE_POINTER)
    _write_jsonl(
        base / daily_operations_publication.CYCLE_LEDGER_FILENAME,
        [
            {
                "artifact_namespace": namespace,
                "cycle_id": "managed-cycle",
                "status": "succeeded",
            }
        ],
    )

    values, artifacts = campaign._generation_publication(
        namespace_dir,
        run_id=str(manifest["run_id"]),
        audit=audit,
        operator=operator,
        current_authority=pointer,
    )

    assert values["audit_authority_binding_valid"] is False
    assert values["publication_status"] == "missing_final_receipt"
    assert values["currently_authoritative"] is False
    assert values["ever_authoritative"] is False
    assert values["first_authoritative_at"] is None
    assert artifacts["prepublication_audit"] is None


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
    readiness = _readiness()
    source_group = readiness["current_universe_maturity"][
        "baseline_feature_readiness"
    ]["volume"]
    readiness["current_universe_maturity"][
        "baseline_feature_readiness"
    ] = {
        name: json.loads(json.dumps(source_group))
        for name in (
            "btc_eth_relative",
            "returns_1h",
            "returns_24h",
            "returns_4h",
            "turnover",
            "volatility",
            "volume",
        )
    }
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        lambda *_args, **_kwargs: readiness,
    )
    current_authority = _dashboard_authority()
    current_authority.snapshot.generation_authority_checked_at = _EVALUATED
    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        lambda *_args, **_kwargs: current_authority,
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
    dashboard_path = (
        output / "RADAR_LIVE_OBSERVATION_CAMPAIGN_DASHBOARD.json"
    )
    first_json = json_path.read_bytes()
    first_markdown = markdown_path.read_bytes()
    first_dashboard = dashboard_path.read_bytes()
    assert b"\n  \"" not in first_json
    dashboard_projection = json.loads(first_dashboard)
    assert dashboard_projection["source_report_sha256"] == hashlib.sha256(
        first_json
    ).hexdigest()
    assert dashboard_projection["source_report_size_bytes"] == len(first_json)
    assert dashboard_projection["projection"]["shadow_temporal_surprise"][
        "asset_variation_projection_status"
    ] == "summary_only_full_evidence_in_source_report"
    assert b"secret-token" not in first_json
    assert b"must-not-leak" not in first_json
    assert b"no trade recommendation" in first_markdown.lower()
    assert b"bybit usdt-linear perpetuals are the selected execution surface" in (
        first_markdown.lower()
    )
    assert b"spread-provider selection remains deferred" not in first_markdown.lower()
    assert b"3 outcomes are pending and 0 outcomes are matured" in first_markdown
    assert b"1 provider failure and 1 blocked/preflight attempt" in first_markdown
    assert b"Duplicate observations: `0`" in first_markdown
    assert b"Conflicting duplicate observations: `0`" in first_markdown
    assert (
        b"| Feature group | Warm | Warming | Cold | Other | Samples min-max / required | "
        b"Elapsed min-max / required | Status counts |"
        in first_markdown
    )
    assert b"below)" in first_markdown
    assert b"### Current authoritative universe" in first_markdown
    assert b"### Retained campaign history" in first_markdown

    assert market_no_send_cli.main([
        "campaign-report",
        "--artifact-base", str(base),
        "--output-dir", str(output),
        "--evaluated-at", _EVALUATED,
    ]) == 0
    capsys.readouterr()
    assert json_path.read_bytes() == first_json
    assert dashboard_path.read_bytes() == first_dashboard
    assert markdown_path.read_bytes() == first_markdown


def test_campaign_writer_removes_stale_dashboard_projection_without_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    base = tmp_path / "artifacts"
    output = tmp_path / "research"
    base.mkdir()
    output.mkdir()
    _fixture(base)
    stale_projection = (
        output / "RADAR_LIVE_OBSERVATION_CAMPAIGN_DASHBOARD.json"
    )
    stale_projection.write_text('{"stale":true}\n', encoding="utf-8")
    monkeypatch.setattr(
        campaign.market_no_send_history_cache,
        "cache_readiness",
        _readiness,
    )

    def rejected_authority(*_args, **_kwargs):
        raise campaign.dashboard_readiness.DashboardReadinessError(
            "generation:stale"
        )

    monkeypatch.setattr(
        campaign.dashboard_readiness,
        "resolve_authoritative_dashboard",
        rejected_authority,
    )

    json_path, markdown_path, report = campaign.write_campaign_report(
        base,
        output,
        evaluated_at=_EVALUATED,
    )

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert report["pointer"]["status"] == "invalid_or_untrusted"
    assert stale_projection.exists() is False


def test_campaign_make_target_is_read_only_and_does_not_enable_authorization():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "radar-market-campaign-report:" in makefile
    target = makefile.split("radar-market-campaign-report:\n", 1)[1].split(
        "radar-market-no-send:", 1
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


def test_campaign_outcome_state_uses_only_canonical_primary_horizon():
    base = {
        "primary_horizon": "24h",
        "horizon_metadata": {
            "4h": {"maturity_status": "matured"},
            "24h": {"maturity_status": "pending"},
        },
        "maturation_state": "matured",
        "return_by_horizon": {"4h": 0.12, "24h": None},
    }

    assert campaign._outcome_state(base) == "not_due"
    assert campaign._outcome_state({
        **base,
        "horizon_metadata": {
            "4h": {"maturity_status": "matured"},
            "24h": {"maturity_status": "missing_data"},
        },
    }) == "due_missing_price"
    assert campaign._outcome_state({
        **base,
        "horizon_metadata": {
            "4h": {"maturity_status": "pending"},
            "24h": {"maturity_status": "matured"},
        },
        "return_by_horizon": {"4h": None, "24h": -0.02},
    }) == "matured"

    metrics = campaign._outcome_metrics((
        base,
        {
            **base,
            "horizon_metadata": {
                "4h": {"maturity_status": "matured"},
                "24h": {"maturity_status": "missing_data"},
            },
        },
    ))
    assert metrics["pending"] == metrics["not_due"] == 1
    assert metrics["missing_data"] == metrics["due_missing_price"] == 1
    assert metrics["matured"] == 0
    assert metrics["status_counts"] == {
        "due_missing_price": 1,
        "not_due": 1,
    }


def test_due_missing_price_diagnostic_proves_nearest_price_is_outside_window():
    due = datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc)
    outcome = {
        "outcome_identity_key": "outcome:one",
        "source_artifact_namespace": "radar_market_no_send_one",
        "candidate_id": "candidate:one",
        "core_opportunity_id": "core:one",
        "symbol": "TEST",
        "coin_id": "test-coin",
        "observed_at": (due - timedelta(days=1)).isoformat(),
        "primary_horizon": "24h",
        "outcome_evaluated_at": (due + timedelta(days=2)).isoformat(),
        "observation_price_id": "entry",
        "horizon_metadata": {
            "24h": {
                "due_at": due.isoformat(),
                "maturity_status": "missing_data",
                "price_observation_id": None,
            },
        },
    }
    history = {
        "status": "observed",
        "artifact": campaign.HISTORY_FILENAME,
        "sha256": "a" * 64,
        "row_count": 2,
        "binding_source": "campaign_market_history_exact_bytes",
        "rows": (
            {
                "symbol": "TEST",
                "coin_id": "test-coin",
                "observed_at": (due - timedelta(minutes=30)).isoformat(),
                "price": 10.0,
                "provider": "coingecko",
                "observation_id": "before",
            },
            {
                "symbol": "TEST",
                "coin_id": "test-coin",
                "observed_at": (due + timedelta(hours=25)).isoformat(),
                "price": 11.0,
                "provider": "coingecko",
                "observation_id": "after-too-late",
            },
        ),
    }

    metrics = campaign._outcome_metrics((outcome,), history_snapshot=history)

    assert metrics["due_missing_price"] == 1
    assert metrics["due_missing_price_detail_count"] == 1
    assert metrics["price_history_snapshot"] == {
        "status": "observed",
        "artifact": campaign.HISTORY_FILENAME,
        "sha256": "a" * 64,
        "row_count": 2,
        "binding_source": "campaign_market_history_exact_bytes",
    }
    detail = metrics["due_missing_price_details"][0]
    assert detail["allowed_lag_seconds"] == 24 * 60 * 60
    assert detail["allowed_latest_price_at"] == (
        due + timedelta(hours=24)
    ).isoformat()
    assert detail["first_retained_price_after_due"]["observation_id"] == (
        "after-too-late"
    )
    assert detail["first_post_due_lag_seconds"] == 25 * 60 * 60
    assert detail["seconds_beyond_allowed_window"] == 60 * 60
    assert detail["resolution_status"] == (
        "first_post_due_price_outside_allowed_window"
    )
    assert detail["ledger_refresh_can_resolve_from_retained_history"] is False
    assert detail["historical_point_in_time_evidence_required"] is True
    assert detail["interpolation_permitted"] is False
    markdown = market_observation_campaign_render.format_campaign_report(
        {"outcomes": metrics}
    )
    assert "Due outcomes without a qualifying price" in markdown
    assert "first_post_due_price_outside_allowed_window" in markdown
    assert "1.00 h" in markdown


def test_due_missing_price_diagnostic_flags_stale_ledger_when_price_is_available():
    due = datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc)
    outcome = {
        "symbol": "TEST",
        "coin_id": "test-coin",
        "observed_at": (due - timedelta(days=1)).isoformat(),
        "primary_horizon": "24h",
        "horizon_metadata": {
            "24h": {
                "due_at": due.isoformat(),
                "maturity_status": "missing_data",
                "price_observation_id": None,
            },
        },
    }
    history = {
        "status": "observed",
        "rows": ({
            "symbol": "TEST",
            "coin_id": "test-coin",
            "observed_at": (due + timedelta(hours=2)).isoformat(),
            "price": 10.5,
            "provider": "coingecko",
            "observation_id": "qualifying",
        },),
    }

    detail = campaign._outcome_metrics(
        (outcome,),
        history_snapshot=history,
    )["due_missing_price_details"][0]

    assert detail["qualifying_price_observation_count"] == 1
    assert detail["resolution_status"] == (
        "qualifying_price_available_ledger_refresh_required"
    )
    assert detail["ledger_refresh_can_resolve_from_retained_history"] is True
    assert detail["historical_point_in_time_evidence_required"] is False


def test_campaign_outcome_state_preserves_legacy_primary_fallback_only():
    assert campaign._outcome_state({"maturation_state": "matured"}) == "matured"
    assert campaign._outcome_state({
        "primary_horizon": "24h",
        "return_by_horizon": {"4h": 0.1, "24h": None},
    }) == "other"
    assert campaign._outcome_state({
        "primary_horizon": "24h",
        "return_by_horizon": {"4h": 0.1, "24h": 0.2},
    }) == "matured"


def test_campaign_outcome_state_rejects_mature_status_without_primary_return():
    row = {
        "primary_horizon": "24h",
        "horizon_metadata": {
            "4h": {"maturity_status": "matured"},
            "24h": {"maturity_status": "matured"},
        },
        "maturation_state": "matured",
        "primary_horizon_return": None,
        "return_by_horizon": {"4h": 0.1, "24h": None},
    }
    assert campaign._outcome_state(row) == "other"
    without_metadata = dict(row)
    without_metadata.pop("horizon_metadata")
    assert campaign._outcome_state(without_metadata) == "other"
    assert campaign._outcome_metrics((row,))["matured"] == 0
    assert campaign._outcome_metrics((row,))["other"] == 1
    assert campaign._outcome_state({
        **row,
        "primary_horizon_return": 0.2,
        "return_by_horizon": {"4h": 0.1, "24h": -0.2},
    }) == "other"


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
