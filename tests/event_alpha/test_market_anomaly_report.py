"""Focused market-anomaly report truth regressions."""

from __future__ import annotations

from tempfile import TemporaryDirectory

import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner


def test_market_anomaly_report_uses_receipt_bound_snapshots():
    rows = scanner.load_market_rows("fixtures/event_market_anomaly/market_rows.json")
    with TemporaryDirectory() as tmp:
        result = scanner.run_market_anomaly_scan(
            market_rows=rows,
            namespace_dir=tmp,
            observed_at="2026-06-15T16:00:00Z",
            profile="fixture",
            artifact_namespace="market_anomaly_report_test",
        )
        report = result.report_path.read_text(encoding="utf-8")

    assert len(result.snapshots) == result.snapshot_count == 8
    assert "Scan Coverage and Gate Inputs" in report
    assert "Current Classification Contract" in report
    assert "Strongest Observed Movements (Diagnostic Only)" in report
    assert "return_4h=8/8" in report
    assert "does not recommend threshold or score changes" in report


def test_market_anomaly_zero_result_explains_exact_scan_coverage():
    report = scanner.format_market_anomaly_report(
        [],
        snapshots=[
            {
                "symbol": "CALM",
                "return_4h": 1.0,
                "return_24h": 2.0,
                "relative_return_vs_btc_4h": 0.5,
                "volume_zscore_24h": 0.2,
                "liquidity_usd": 10_000_000,
                "spread_bps": None,
                "freshness_status": "fresh",
                "market_data_quality": {"baseline_status": "warming"},
            }
        ],
        snapshot_count=99,
        profile="no_key_live",
        artifact_namespace="calm_generation",
    )

    assert "Market state snapshots: 1" in report
    assert "evaluated=1" in report
    assert "no_configured_reaction=1" in report
    assert "spread_bps=0/1" in report
    assert "fresh=1" in report
    assert "warming=1" in report
    assert "No row satisfied a configured anomaly rule" in report
    assert "not evidence that market collection was empty" in report
    assert "not an anomaly score, threshold distance, route, or tuning queue" in report
