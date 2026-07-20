from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_live_campaign import (
    load_live_campaign_projection,
    project_live_campaign,
)
from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign_shadow_surprise,
)


_REVIEW_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}


def _report():
    report = {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "generated_at": "2026-07-16T02:47:32Z",
        "campaign_status": "in_progress_baseline_warming",
        "campaign_metrics": {
            "real_cycles": 8,
            "real_observations": 240,
            "retained_observation_count": 240,
            "baseline_counted_observation_count": 210,
            "historical_ideas": 2,
            "route_counts": {"risk_watch": 2},
        },
        "baseline_maturity": {
            "point_in_time_control_context_readiness": {
                "schema_id": (
                    "decision_radar.point_in_time_control_context_readiness"
                ),
                "schema_version": 1,
                "status": "partial",
                "retained_observation_count": 240,
                "counted_observation_count": 210,
                "point_in_time_universe_context_row_count": 30,
                "complete_match_context_row_count": 0,
                "field_coverage_counts": {
                    "observation_date": 210,
                    "point_in_time_universe_member": 30,
                    "point_in_time_volume_rank": 30,
                    "point_in_time_universe_size": 30,
                    "point_in_time_universe_limit": 30,
                    "point_in_time_universe_policy": 30,
                    "control_liquidity_tier": 30,
                    "control_liquidity_tier_basis": 30,
                    "market_regime": 0,
                    "market_regime_basis": 0,
                    "protocol_partition": 0,
                    "protocol_partition_basis": 0,
                },
                "selection_match_fields": [
                    "partition",
                    "observation_date",
                    "market_regime",
                    "liquidity_tier",
                ],
                "selection_field_mapping": {
                    "partition": "protocol_partition",
                    "observation_date": "derived_from_observed_at_utc",
                    "market_regime": "market_regime",
                    "liquidity_tier": "control_liquidity_tier",
                },
                "selection_uses_outcomes": False,
                "selection_performed": False,
                "historical_context_backfilled": False,
                "protocol_v2_evidence_eligible": False,
                "provider_calls": 0,
                "writes": 0,
                "research_only": True,
            },
        },
        "shadow_anomaly_episodes": {
            "status": "ready",
            "method": "fixed_start_window_declustering",
            "primary_episode_count": 1,
            "primary_repeat_member_count": 1,
            "sensitivity_counts": {"24h": {"episode_count": 1, "repeat_member_count": 1}},
            "statistical_independence_claim": False,
            "cross_asset_independence_claim": False,
        },
        "outcomes": {"total": 2, "matured": 1, "pending": 0, "due_missing_price": 1},
        "decision_v2_episode_outcome_scorecard": {
            "status": "ready",
            "primary_episode_count": 1,
            "matured_episode_count": 1,
            "scoreable_directional_episode_count": 1,
            "representative_count": 1,
            "policy_conclusion": "insufficient_for_policy_change",
            "policy_conclusion_reasons": ["matched_non_idea_controls_unavailable"],
            "matched_control_available": False,
            "out_of_sample_validation_available": False,
            "representatives": [{
                "episode_id": "episode-1",
                "canonical_asset_id": "dexe",
                "observed_at": "2026-07-13T15:27:13Z",
                "radar_route": "risk_watch",
                "primary_thesis_origin": "market_led",
                "outcome_state": "matured",
                "primary_horizon_return": -0.01,
            }],
        },
        "data_quality_limitations": [{"category": "spread", "detail": "No trusted spread."}],
        "human_review_timing": {
            "schema_id": "decision_radar.idea_review_timing_report",
            "schema_version": 1,
            "generated_at": "2026-07-16T02:47:32Z",
            "status": "no_events",
            "ledger_event_count": 0,
            "events_in_window_count": 0,
            "events_after_evaluated_at_count": 0,
            "idea_record_count": 0,
            "first_view_record_count": 0,
            "completed_review_record_count": 0,
            "incomplete_review_record_count": 0,
            "records": [],
            "latency_seconds_definition": "idea_available_at_to_review_completed_at",
            "dashboard_reads_recorded_as_human_actions": False,
            "protocol_v2_evidence_eligible": False,
            "automatic_policy_effect": "none",
            "provider_calls": 0,
            "research_only": True,
            "safety": dict(_REVIEW_SAFETY),
        },
        "human_review_queue": {
            "schema_id": "decision_radar.idea_review_timing_queue_summary",
            "schema_version": 1,
            "generated_at": "2026-07-16T02:47:32Z",
            "status": "action_required",
            "eligible_generation_count": 2,
            "eligible_idea_count": 2,
            "action_required_count": 2,
            "not_viewed_count": 2,
            "in_review_count": 0,
            "complete_count": 0,
            "skipped_candidate_count": 1,
            "events_in_window_count": 0,
            "events_after_evaluated_at_count": 0,
            "records": [
                {
                    "artifact_namespace": "generation-1",
                    "idea_id": "idea-1",
                    "review_status": "not_viewed",
                    "first_operator_viewed_at": None,
                    "review_completed_at": None,
                },
                {
                    "artifact_namespace": "generation-2",
                    "idea_id": "idea-2",
                    "review_status": "not_viewed",
                    "first_operator_viewed_at": None,
                    "review_completed_at": None,
                },
            ],
            "absolute_paths_or_action_commands_embedded": False,
            "dashboard_reads_recorded_as_human_actions": False,
            "commands_require_explicit_confirmation": True,
            "protocol_v2_evidence_eligible": False,
            "automatic_policy_effect": "none",
            "provider_calls": 0,
            "writes": 0,
            "research_only": True,
            "safety": dict(_REVIEW_SAFETY),
        },
        "safety": {
            "research_only": True,
            "automatic_route_changes": False,
            "automatic_threshold_changes": False,
            "normal_rsi_signal_rows_written": 0,
            "paper_trades_created": 0,
            "provider_authorization_modified": False,
            "provider_calls_made_by_report": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "triggered_fade_created": 0,
        },
    }
    report["shadow_temporal_surprise_campaign_audit"] = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            {
                "status": "observed_empty",
                "artifact": "event_market_history.jsonl",
                "sha256": hashlib.sha256(b"").hexdigest(),
                "size_bytes": 0,
                "row_count": 0,
                "binding_source": "campaign_market_history_exact_bytes",
                "rows": [],
            },
            minimum_sample_count=8,
        )
    )
    return report


def test_live_campaign_projection_stays_separate_and_insufficient() -> None:
    projection = project_live_campaign(_report())
    assert projection["evidence_mode"] == "live_no_send"
    assert projection["campaign_metrics"]["real_observations"] == 240
    assert projection["episodes"]["primary_episode_count"] == 1
    assert projection["schema_version"] == 4
    assert projection["episodes"]["statistical_independence_claim"] is False
    assert projection["episodes"]["cross_asset_independence_claim"] is False
    assert projection["episodes"]["representatives"][0]["radar_route"] == "risk_watch"
    assert projection["evidence_strength"] == "insufficient_sample"
    assert projection["replay_evidence_aggregated"] is False
    assert projection["policy_eligible"] is False
    assert projection["auto_apply"] is False
    assert projection["provider_calls"] == projection["writes"] == 0
    assert projection["shadow_temporal_surprise"]["available"] is True
    assert projection["shadow_temporal_surprise"]["status"] == "empty"
    assert projection["human_review"]["eligible_idea_count"] == 2
    assert projection["human_review"]["action_required_count"] == 2
    assert projection["human_review"]["latency_evidence_status"] == (
        "unavailable_no_explicit_human_actions"
    )
    controls = projection["point_in_time_control_context"]
    assert controls["available"] is True
    assert controls["status"] == "partial"
    assert controls["counted_observation_count"] == 210
    assert controls["point_in_time_universe_context_row_count"] == 30
    assert controls["complete_match_context_row_count"] == 0
    assert controls["field_coverage_counts"]["market_regime"] == 0
    assert controls["selection_uses_outcomes"] is False
    assert controls["historical_context_backfilled"] is False
    assert controls["protocol_v2_evidence_eligible"] is False


def test_live_campaign_loader_rejects_duplicate_keys_and_symlink(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()))
    assert load_live_campaign_projection(path)["source_schema_id"].endswith("_v2")

    path.write_text('{"schema_id":"a","schema_id":"b"}')
    with pytest.raises(ValueError, match="unreadable"):
        load_live_campaign_projection(path)

    target = tmp_path / "target.json"
    target.write_text(json.dumps(_report()))
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ValueError, match="path invalid"):
        load_live_campaign_projection(path)


def test_live_campaign_projection_rejects_side_effect_claim() -> None:
    report = _report()
    report["safety"]["telegram_sends"] = 1
    with pytest.raises(ValueError, match="safety invalid"):
        project_live_campaign(report)


@pytest.mark.parametrize(
    "field",
    ("statistical_independence_claim", "cross_asset_independence_claim"),
)
def test_live_campaign_projection_rejects_independence_claim(field: str) -> None:
    report = _report()
    report["shadow_anomaly_episodes"][field] = True
    with pytest.raises(ValueError, match="episode independence claim invalid"):
        project_live_campaign(report)


def test_live_campaign_projection_marks_older_source_context_unavailable() -> None:
    report = _report()
    report.pop("shadow_temporal_surprise_campaign_audit")
    report.pop("human_review_timing")
    report.pop("human_review_queue")
    report.pop("baseline_maturity")

    projection = project_live_campaign(report)

    assert projection["shadow_temporal_surprise"] == {
        "available": False,
        "status": "not_available_in_source_report",
        "feature_coverage": {},
        "all_features_have_ready_evidence": False,
        "statistical_independence_claimed": False,
        "protocol_v2_evidence_eligible": False,
        "policy_eligible": False,
        "provider_calls": 0,
        "writes": 0,
    }
    assert projection["human_review"]["latency_evidence_status"] == (
        "unavailable_source_report_compatibility"
    )
    assert projection["point_in_time_control_context"]["available"] is False
    assert projection["point_in_time_control_context"]["status"] == (
        "not_available_in_source_report"
    )


def test_live_campaign_projection_rejects_shadow_audit_drift() -> None:
    report = _report()
    report["shadow_temporal_surprise_campaign_audit"][
        "statistical_independence_claimed"
    ] = True

    with pytest.raises(ValueError, match="shadow temporal surprise invalid"):
        project_live_campaign(report)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("human_review_queue", "action_required_count", 1),
        ("human_review_queue", "dashboard_reads_recorded_as_human_actions", True),
        ("human_review_timing", "provider_calls", 1),
    ),
)
def test_live_campaign_projection_rejects_human_review_drift(
    section: str, field: str, value: object
) -> None:
    report = _report()
    report[section][field] = value

    with pytest.raises(ValueError, match="human review invalid"):
        project_live_campaign(report)


def test_live_campaign_projection_rejects_incomplete_review_safety_contract() -> None:
    report = _report()
    report["human_review_queue"]["safety"].pop("orders")

    with pytest.raises(ValueError, match="human review invalid"):
        project_live_campaign(report)


def test_live_campaign_projection_rejects_review_status_count_contradiction() -> None:
    report = _report()
    report["human_review_queue"]["status"] = "complete"

    with pytest.raises(ValueError, match="human review invalid"):
        project_live_campaign(report)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("context", "selection_performed", True),
        ("context", "historical_context_backfilled", True),
        ("context", "complete_match_context_row_count", 31),
        ("metrics", "baseline_counted_observation_count", 209),
    ),
)
def test_live_campaign_projection_rejects_point_in_time_control_context_drift(
    section: str,
    field: str,
    value: object,
) -> None:
    report = _report()
    target = (
        report["baseline_maturity"]["point_in_time_control_context_readiness"]
        if section == "context"
        else report["campaign_metrics"]
    )
    target[field] = value

    with pytest.raises(ValueError, match="point-in-time control context invalid"):
        project_live_campaign(report)
