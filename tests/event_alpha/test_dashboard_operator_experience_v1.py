from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page


_NOW = datetime(2026, 7, 12, 7, 0, tzinfo=timezone.utc)


def _sparse_snapshot():
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    observations = (
        {
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "return_24h": 2.0,
            "return_unit": "percent_points",
            "spread_status": "unavailable",
            "freshness_status": "fresh",
            "market_data_quality": {"baseline_status": "warming"},
        },
        {
            "symbol": "ETH",
            "coin_id": "ethereum",
            "return_24h": -1.0,
            "return_unit": "percent_points",
            "spread_status": "unavailable",
            "freshness_status": "fresh",
            "market_data_quality": {"baseline_status": "warming"},
        },
    )
    return replace(
        snapshot,
        current_candidates=(),
        current_market_observations=observations,
        current_market_anomalies=(),
        current_calendar_events=(),
        current_outcomes=(),
        market_generation={
            "raw_market_row_count": 80,
            "selected_market_row_count": 2,
        },
        current_request_ledger={
            "raw_market_row_count": 80,
            "selected_market_row_count": 2,
        },
        source_coverage={
            "packs": [
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "not_configured",
                }
            ]
        },
    )


def test_today_distinguishes_zero_ideas_from_zero_market_data() -> None:
    page = render_dashboard_page(_sparse_snapshot(), "/")

    assert page.status_code == 200
    assert "No immediate Decision idea qualified" in page.body
    assert "The scan evaluated 2 assets" in page.body
    assert "does not mean the provider or dashboard failed" in page.body
    assert "Calendar acquisition not configured" in page.body
    assert "Execution spread unavailable" in page.body


def test_market_radar_accounts_for_every_layer_without_inventing_rows() -> None:
    page = render_dashboard_page(_sparse_snapshot(), "/market-radar")

    assert page.status_code == 200
    assert "Where the rows went" in page.body
    assert "Provider rows" in page.body
    assert "Selected universe" in page.body
    assert "Exact observations" in page.body
    assert "Anomaly evidence" in page.body
    assert "Integrated candidates" in page.body
    assert "Core / operator ideas" in page.body
    assert "All 2 selected assets survive into the exact observation layer" in page.body
    assert "scanner qualification and canonical consolidation" in page.body
    assert "not a dashboard data-loss gap" in page.body


def test_integrated_generation_does_not_imply_every_idea_descended_from_market_anomalies() -> None:
    source = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    snapshot = replace(
        source,
        current_market_observations=(),
        current_market_anomalies=(),
        market_generation={},
        current_request_ledger={},
    )

    page = render_dashboard_page(snapshot, "/market-radar")

    assert 'aria-label="Independent integrated layer counts"' in page.body
    assert "no market-only funnel receipt" in page.body
    assert "does not infer a causal chain" in page.body
    assert '<span class="funnel-arrow"' not in page.body


def test_exact_generation_summary_separates_candidate_rows_from_visible_ideas() -> None:
    page = render_dashboard_page(
        load_dashboard_snapshot(
            "fixtures/event_alpha/radar_dashboard",
            "current",
            now=_NOW,
        ),
        "/ideas",
    )

    assert "4 candidate rows" in page.body
    assert "3 operator-visible" in page.body
