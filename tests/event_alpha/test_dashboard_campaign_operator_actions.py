from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.dashboard.campaign_operator_actions import (
    MAX_CAMPAIGN_REPORT_BYTES,
    load_campaign_operator_actions,
)
from crypto_rsi_scanner.event_alpha.dashboard.operator_work_queue import (
    render_operator_work_queue,
)
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import render_health_page
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot


_GENERATED_AT = "2026-07-18T20:43:03.720770+00:00"


def _campaign_report() -> dict[str, object]:
    return {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "schema_version": "decision_radar_live_observation_campaign_report_v2",
        "row_type": "decision_radar_live_observation_campaign_report",
        "contract_version": 2,
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "generated_at": _GENERATED_AT,
        "campaign_status": "in_progress_baseline_warming",
        "pointer": {
            "artifact_namespace": "radar_market_no_send_current",
            "run_id": "2026-07-14T10:00:00+00:00|no_key_live",
            "revision": 7,
            "status": "authoritative",
            "generation_authority_status": "authoritative",
            "readiness_validation": "passed",
            "exact_operator_binding": True,
            "readiness_error": None,
            "authority_checked_at": _GENERATED_AT,
        },
        "campaign_metrics": {
            "real_cycles": 21,
            "real_observations": 630,
            "retained_observation_count": 630,
            "baseline_counted_observation_count": 600,
            "baseline_warm_asset_count": 0,
            "historical_ideas": 5,
            "matured_outcomes": 1,
            "pending_outcomes": 3,
            "review_timing_action_required": 3,
            "spread_available_count": 0,
        },
        "human_review_queue": {
            "schema_id": "decision_radar.idea_review_timing_queue_summary",
            "schema_version": 1,
            "row_type": "decision_radar_idea_review_timing_queue_summary",
            "status": "action_required",
            "eligible_idea_count": 3,
            "action_required_count": 3,
            "not_viewed_count": 3,
            "in_review_count": 0,
            "complete_count": 0,
            "skipped_candidate_count": 2,
            "operator_queue_command": (
                "make radar-review-timing-queue PYTHON=.venv/bin/python"
            ),
            "commands_require_explicit_confirmation": True,
            "absolute_paths_or_action_commands_embedded": False,
            "dashboard_reads_recorded_as_human_actions": False,
            "automatic_policy_effect": "none",
            "provider_calls": 0,
            "writes": 0,
            "research_only": True,
            "safety": _zero_safety(),
            "records": [
                {
                    "artifact_namespace": f"published-{index}",
                    "idea_id": "iar:634eae4a52fb",
                    "radar_route": route,
                    "review_status": "not_viewed",
                    "idea_available_at": f"2026-07-18T0{index}:00:00+00:00",
                    "ignored_absolute_path": "/private/outside/generation",
                }
                for index, route in enumerate(
                    ("dashboard_watch", "diagnostic", "dashboard_watch"),
                    start=2,
                )
            ],
        },
        "outcomes": {
            "matured": 1,
            "pending": 3,
            "due_missing_price": 1,
            "due_missing_price_details": [
                {
                    "symbol": "DEXE",
                    "historical_point_in_time_evidence_required": True,
                    "interpolation_permitted": False,
                    "automatic_threshold_change_permitted": False,
                    "research_only": True,
                }
            ],
        },
        "data_quality_limitations": [
            {
                "category": "execution_quality_spread",
                "provider_selection": "selected_bybit_usdt_linear_perpetuals",
                "evidence_status": "awaiting_authorized_immutable_capture",
                "next_safe_command": (
                    "make radar-execution-quality-bybit-readiness "
                    "PYTHON=.venv/bin/python"
                ),
            },
            {"category": "temporal_baseline_maturity"},
        ],
        "safety": {
            "research_only": True,
            "no_trade_recommendation": True,
            "provider_authorization_modified": False,
            "automatic_route_changes": False,
            "automatic_threshold_changes": False,
            "normal_rsi_signal_rows_written": 0,
            "paper_trades_created": 0,
            "provider_calls_made_by_report": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "triggered_fade_created": 0,
        },
        "ignored_absolute_path": "/private/outside/report",
    }


def _zero_safety() -> dict[str, int]:
    return {
        "authorization_mutations": 0,
        "dashboard_authority_mutations": 0,
        "event_alpha_paper_trades": 0,
        "event_alpha_triggered_fade": 0,
        "normal_rsi_writes": 0,
        "orders": 0,
        "production_policy_mutations": 0,
        "provider_calls": 0,
        "telegram_sends": 0,
        "trades": 0,
    }


def _write_report(root: Path, report: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json").write_text(
        json.dumps(report, sort_keys=True),
        encoding="utf-8",
    )


def _load(root: Path) -> dict[str, object]:
    return load_campaign_operator_actions(
        root,
        artifact_namespace="radar_market_no_send_current",
        run_id="2026-07-14T10:00:00+00:00|no_key_live",
        revision=7,
    )


def test_campaign_operator_actions_projects_exact_safe_human_work(tmp_path: Path) -> None:
    _write_report(tmp_path, _campaign_report())

    result = _load(tmp_path)

    assert result["status"] == "ready"
    assert result["authority"] == "pointer_matched_campaign_context"
    assert result["provider_calls"] == result["writes"] == 0
    assert result["campaign_metrics"]["real_cycles"] == 21
    assert result["human_review"]["action_required_count"] == 3
    assert result["human_review"]["next_safe_command"] == (
        "make radar-review-timing-queue PYTHON=.venv/bin/python"
    )
    assert result["outcome_recovery"]["symbols"] == ("DEXE",)
    assert result["execution_quality"]["venue"] == "bybit"
    assert "/private/" not in repr(result)


def test_campaign_operator_actions_fail_closed_on_pointer_or_command_drift(
    tmp_path: Path,
) -> None:
    mismatched = _campaign_report()
    mismatched["pointer"]["revision"] = 8
    _write_report(tmp_path, mismatched)
    assert _load(tmp_path)["status"] == "unavailable"

    unsafe = _campaign_report()
    unsafe["human_review_queue"]["operator_queue_command"] = (
        "CONFIRM=1 make radar-review-timing-view"
    )
    _write_report(tmp_path, unsafe)
    result = _load(tmp_path)
    assert result["status"] == "unavailable"
    assert result["human_review"] == {}

    path_like = _campaign_report()
    path_like["human_review_queue"]["records"][0]["artifact_namespace"] = (
        "/private/outside/generation"
    )
    _write_report(tmp_path, path_like)
    assert _load(tmp_path)["status"] == "unavailable"


def test_campaign_operator_actions_rejects_oversized_report(tmp_path: Path) -> None:
    path = tmp_path / "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"
    path.write_bytes(b"{" + b" " * MAX_CAMPAIGN_REPORT_BYTES + b"}")

    result = _load(tmp_path)

    assert result["status"] == "unavailable"
    assert result["reason"] == "campaign_report_oversized"


def test_today_and_health_surface_campaign_actions_separate_from_current_truth() -> None:
    state = _campaign_report()
    root_projection = {
        "status": "ready",
        "authority": "pointer_matched_campaign_context",
        "campaign_status": state["campaign_status"],
        "campaign_metrics": state["campaign_metrics"],
        "human_review": {
            **state["human_review_queue"],
            "next_safe_command": state["human_review_queue"]["operator_queue_command"],
        },
        "outcome_recovery": {
            "due_missing_price_count": 1,
            "matured_count": 1,
            "pending_count": 3,
            "symbols": ("DEXE",),
            "next_safe_command": (
                "make radar-outcome-price-recovery-readiness "
                "PYTHON=.venv/bin/python"
            ),
        },
        "execution_quality": {
            "status": "awaiting_authorized_immutable_capture",
            "retained_observation_count": 630,
            "spread_available_count": 0,
            "next_safe_command": (
                "make radar-execution-quality-bybit-readiness "
                "PYTHON=.venv/bin/python"
            ),
        },
    }
    snapshot = replace(_snapshot(), campaign_operator_actions=root_projection)

    today = render_today_page(snapshot, query={})
    health = render_health_page(snapshot)
    panel = render_operator_work_queue(snapshot)

    for page in (today, health, panel):
        assert "Open operator work" in page
        assert "3 published idea records need explicit review" in page
        assert "1 outcome price gap needs point-in-time evidence" in page
        assert "DEXE" in page
        assert "Bybit USDT-perpetual spread evidence is still absent" in page
        assert "Trusted spread coverage is 0/630" in page
        assert "Dashboard reads never count as a review" in page
        assert "CONFIRM=1" not in page
    assert today.index("Open operator work") < today.index("Decision constraints")
    assert today.count("Execution spread unavailable") == 0
    assert health.count('id="human-work-queue"') == 1
    assert health.count("Spread evidence is unavailable") == 0


def test_operator_work_queue_stays_hidden_without_pointer_matched_context() -> None:
    snapshot = replace(
        _snapshot(),
        campaign_operator_actions={
            "status": "unavailable",
            "reason": "campaign_report_pointer_mismatch",
        },
    )

    assert render_operator_work_queue(snapshot) == ""
    assert "Open operator work" not in render_today_page(snapshot, query={})
