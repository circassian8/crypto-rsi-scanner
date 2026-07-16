from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_live_campaign import (
    load_live_campaign_projection,
    project_live_campaign,
)


def _report():
    return {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "generated_at": "2026-07-16T02:47:32Z",
        "campaign_status": "in_progress_baseline_warming",
        "campaign_metrics": {
            "real_cycles": 8,
            "real_observations": 240,
            "historical_ideas": 2,
            "route_counts": {"risk_watch": 2},
        },
        "shadow_anomaly_episodes": {
            "status": "ready",
            "method": "fixed_start_window_declustering",
            "primary_episode_count": 1,
            "primary_repeat_member_count": 1,
            "sensitivity_counts": {"24h": {"episode_count": 1, "repeat_member_count": 1}},
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


def test_live_campaign_projection_stays_separate_and_insufficient() -> None:
    projection = project_live_campaign(_report())
    assert projection["evidence_mode"] == "live_no_send"
    assert projection["campaign_metrics"]["real_observations"] == 240
    assert projection["episodes"]["primary_episode_count"] == 1
    assert projection["episodes"]["representatives"][0]["radar_route"] == "risk_watch"
    assert projection["evidence_strength"] == "insufficient_sample"
    assert projection["replay_evidence_aggregated"] is False
    assert projection["policy_eligible"] is False
    assert projection["auto_apply"] is False
    assert projection["provider_calls"] == projection["writes"] == 0


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
