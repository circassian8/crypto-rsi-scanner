"""Focused outcomes package refactor tests."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone


def test_outcome_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_integrated_radar_outcomes", "crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes", "fill_integrated_radar_outcomes"),
        ("crypto_rsi_scanner.event_alpha_calibration", "crypto_rsi_scanner.event_alpha.outcomes.calibration", "format_calibration_report"),
        ("crypto_rsi_scanner.event_alpha_eval_export", "crypto_rsi_scanner.event_alpha.outcomes.feedback", "export_cases_from_feedback"),
        ("crypto_rsi_scanner.event_alpha_feedback_readiness", "crypto_rsi_scanner.event_alpha.outcomes.feedback", "build_feedback_readiness"),
        ("crypto_rsi_scanner.event_alpha_burn_in", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "build_burn_in_scorecard"),
        ("crypto_rsi_scanner.event_alpha_burn_in_readiness", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "build_burn_in_readiness"),
        ("crypto_rsi_scanner.event_alpha_burn_in_pack", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "export_burn_in_pack"),
        ("crypto_rsi_scanner.event_alpha_quality_review", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_quality_review"),
        ("crypto_rsi_scanner.event_alpha_quality_coverage", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_latest_run_quality_coverage"),
        ("crypto_rsi_scanner.event_alpha_signal_quality", "crypto_rsi_scanner.event_alpha.outcomes.quality", "evaluate_signal_quality_cases"),
        ("crypto_rsi_scanner.event_alpha_signal_quality_export", "crypto_rsi_scanner.event_alpha.outcomes.quality", "export_signal_quality_cases"),
        ("crypto_rsi_scanner.event_alpha_tuning", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_tuning_worksheet"),
        ("crypto_rsi_scanner.event_alpha_priors", "crypto_rsi_scanner.event_alpha.outcomes.priors", "apply_priors_to_alerts"),
        ("crypto_rsi_scanner.event_alpha_policy_simulator", "crypto_rsi_scanner.event_alpha.outcomes.policy_simulator", "simulate_policy"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_integrated_radar_outcome_smoke_writes_research_only_artifacts(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    candidate = {
        "candidate_id": "candidate:TESTLIST",
        "core_opportunity_id": "core:TESTLIST",
        "run_id": "run-1",
        "profile": "fixture",
        "artifact_namespace": "pytest_outcomes",
        "symbol": "TESTLIST",
        "coin_id": "testlist",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "source_origin": "official_exchange",
        "source_pack": "listing_pack",
        "provider": "pytest",
        "market_state_class": "high_liquidity_breakout",
        "source_strength": "structured",
        "observed_at": "2026-06-15T16:00:00+00:00",
        "market_state_snapshot": {"price": 1.0},
    }
    (tmp_path / integrated_radar.INTEGRATED_CANDIDATES_FILENAME).write_text(
        json.dumps(candidate, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows = integrated_radar_outcomes.fill_integrated_radar_outcomes(
        tmp_path,
        observed_at=datetime(2026, 6, 15, 17, tzinfo=timezone.utc),
    )
    loaded = integrated_radar_outcomes.load_integrated_radar_outcomes(tmp_path)
    report = (tmp_path / integrated_radar.INTEGRATED_OUTCOME_REPORT_FILENAME).read_text(encoding="utf-8")

    assert len(rows) == 1
    assert loaded == rows
    assert rows[0]["outcome_label"] == "early_good"
    assert rows[0]["research_only"] is True
    assert rows[0]["trade_created"] is False
    assert rows[0]["paper_trade_created"] is False
    assert rows[0]["normal_rsi_signal_written"] is False
    assert rows[0]["triggered_fade_created"] is False
    assert "validation_rate" in integrated_radar_outcomes.format_integrated_radar_calibration_report(rows)
    assert "early_good" in report


def test_calibration_report_keeps_research_only_terms():
    from crypto_rsi_scanner.event_alpha.outcomes import calibration

    alert = {
        "alert_key": "core:TESTLIST",
        "core_opportunity_id": "core:TESTLIST",
        "symbol": "TESTLIST",
        "coin_id": "testlist",
        "playbook_type": "listing",
        "source": "official_exchange",
        "source_provider": "pytest",
        "tier": "watchlist",
        "primary_horizon_return": 0.08,
        "direction_hit": True,
    }
    feedback = {
        "target": "core:TESTLIST",
        "label": "useful",
        "source_provider": "pytest",
        "source_pack": "listing_pack",
    }

    report = calibration.format_calibration_report([alert], feedback_rows=[feedback])

    assert "EVENT ALPHA CALIBRATION REPORT" in report
    assert "useful=1" in report
    assert "recommendations:" in report
    assert "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed." in report


def test_feedback_readiness_smoke_is_research_only():
    from crypto_rsi_scanner.event_alpha.outcomes import feedback

    result = feedback.build_feedback_readiness(
        profile="fixture",
        artifact_namespace="pytest_outcomes",
        card_paths=[],
        alert_rows=[],
        feedback_rows=[],
        watchlist_entries=[],
    )
    text = feedback.format_feedback_readiness(result)

    assert result.ready is True
    assert "EVENT ALPHA FEEDBACK READINESS" in text
    assert "warnings: no_research_cards_found, no_alert_snapshots_found" in text
    assert "Artifact-only check; no sends, trades, paper rows, normal RSI rows, or event-fade state were changed." in text
