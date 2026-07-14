from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.ideas_page import render_idea_detail
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.market_page import render_market_page
from crypto_rsi_scanner.event_alpha.dashboard.presentation import present_turnover_series


_NOW = datetime(2026, 7, 12, 7, 0, tzinfo=timezone.utc)
_BASIS = "cross_sectional_log_turnover_proxy"


def _turnover_chart(body: str) -> str:
    title_at = body.index("<title>Turnover history · proxy evidence</title>")
    start = body.rindex('<svg class="radar-inline-chart"', 0, title_at)
    end = body.index("</svg>", title_at) + len("</svg>")
    return body[start:end]


def test_turnover_presentation_copies_ratio_values_and_exposes_canonical_metadata() -> None:
    source = ({"turnover_24h": 0.056, "observation_id": "obs-1"},)

    presented = present_turnover_series(source, metric_basis=_BASIS)

    assert source == ({"turnover_24h": 0.056, "observation_id": "obs-1"},)
    assert "_dashboard_turnover_percent_points" not in source[0]
    assert presented.rows[0][presented.value_key] == pytest.approx(5.6)
    assert presented.value_format == "percent"
    assert presented.unit_label == "Percent of market cap"
    assert presented.metric_label == "Cross-sectional log-turnover proxy"
    assert "24h volume divided by market cap" in presented.summary
    assert "Proxy metric: Cross-sectional log-turnover proxy" in presented.state_detail


def test_market_and_idea_detail_share_turnover_values_units_and_proxy_metric_label() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    quality = {
        "baseline_status": "warming",
        "volume_zscore_basis": _BASIS,
    }
    candidate = {
        "core_opportunity_id": "core:dexe",
        "candidate_id": "candidate:dexe",
        "symbol": "DEXE",
        "coin_id": "dexe",
        "radar_route": "risk_watch",
        "_dashboard_route": "risk_watch",
        "_decision_model_status": "v2",
        "market_data_quality": quality,
        "research_only": True,
    }
    observation = {
        "symbol": "DEXE",
        "coin_id": "dexe",
        "price": 10.0,
        "volume_24h": 5_600_000.0,
        "turnover_24h": 0.056,
        "return_unit": "percent_points",
        "freshness_status": "fresh",
        "spread_status": "unavailable",
        "market_data_quality": quality,
    }
    history = (
        {
            "symbol": "DEXE",
            "coin_id": "dexe",
            "observed_at": "2026-07-12T05:00:00+00:00",
            "turnover_24h": 0.028,
        },
        {
            "symbol": "DEXE",
            "coin_id": "dexe",
            "observed_at": "2026-07-12T06:00:00+00:00",
            "turnover_24h": 0.056,
        },
    )
    rendered_snapshot = replace(
        snapshot,
        current_candidates=(candidate,),
        current_market_observations=(observation,),
        exact_market_history=history,
    )

    market_chart = _turnover_chart(render_market_page(rendered_snapshot, {}))
    status, _title, idea_body = render_idea_detail(rendered_snapshot, "core:dexe")
    idea_chart = _turnover_chart(idea_body)

    assert status == 200
    assert market_chart == idea_chart
    for chart in (market_chart, idea_chart):
        assert "+2.8%" in chart
        assert "+5.6%" in chart
        assert "Percent of market cap" in chart
        assert "Proxy metric: Cross-sectional log-turnover proxy" in chart
        assert "Proxy evidence" in chart
