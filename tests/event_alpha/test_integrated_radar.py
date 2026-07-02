"""Focused integrated-radar package refactor tests."""

from __future__ import annotations

import importlib
import json
from collections import Counter
from tempfile import TemporaryDirectory


def test_radar_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_integrated_radar", "crypto_rsi_scanner.event_alpha.radar.integrated_radar", "run_integrated_radar_cycle"),
        ("crypto_rsi_scanner.event_market_state", "crypto_rsi_scanner.event_alpha.radar.market_state", "MarketStateSnapshot"),
        ("crypto_rsi_scanner.event_market_reaction", "crypto_rsi_scanner.event_alpha.radar.market_reaction", "evaluate_market_reaction"),
        ("crypto_rsi_scanner.event_market_anomaly_scanner", "crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner", "scan_market_rows"),
        ("crypto_rsi_scanner.event_core_opportunities", "crypto_rsi_scanner.event_alpha.radar.core_opportunities", "CoreOpportunity"),
        ("crypto_rsi_scanner.event_core_opportunity_store", "crypto_rsi_scanner.event_alpha.radar.core_opportunity_store", "EventCoreOpportunityStoreConfig"),
        ("crypto_rsi_scanner.event_evidence_acquisition", "crypto_rsi_scanner.event_alpha.radar.evidence_acquisition", "run_evidence_acquisition"),
        ("crypto_rsi_scanner.event_opportunity_verdict", "crypto_rsi_scanner.event_alpha.radar.opportunity_verdict", "evaluate_opportunity"),
        ("crypto_rsi_scanner.event_impact_hypotheses", "crypto_rsi_scanner.event_alpha.radar.impact_hypotheses", "generate_impact_hypotheses"),
        ("crypto_rsi_scanner.event_impact_hypothesis_store", "crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store", "write_impact_hypotheses"),
        ("crypto_rsi_scanner.event_incident_store", "crypto_rsi_scanner.event_alpha.radar.incidents", "write_incidents"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_integrated_radar_fixture_lane_counts_and_core_types_stay_stable():
    from crypto_rsi_scanner.event_alpha.artifacts import context as artifact_context
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    with TemporaryDirectory() as tmp:
        context = artifact_context.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="pytest_integrated_radar",
        )
        result = integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        core_rows = [
            json.loads(line)
            for line in context.core_opportunity_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    assert Counter(row["opportunity_type"] for row in rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "DIAGNOSTIC": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    assert Counter(row["opportunity_type"] for row in core_rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert by_symbol["TESTLIST"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["SECTOR"]["opportunity_type"] == "DIAGNOSTIC"
    assert by_symbol["TESTPERP"]["normal_rsi_signal_written"] is False
    assert by_symbol["TESTFADE"]["triggered_fade_created"] is False
