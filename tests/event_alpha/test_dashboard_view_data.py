"""Pure operator-query regressions for the dashboard."""

from crypto_rsi_scanner.event_alpha.dashboard.view_data import (
    dashboard_query,
    filter_sort_candidates,
    filter_sort_observations,
)


def _candidate(symbol: str, *, route: str, actionability: float, risk: float):
    return {
        "core_opportunity_id": f"core:{symbol.casefold()}",
        "symbol": symbol,
        "coin_id": symbol.casefold(),
        "_dashboard_route": route,
        "radar_route": route,
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led", "technical_led"],
        "directional_bias": "long_watch",
        "actionability_score": actionability,
        "evidence_confidence_score": 72,
        "risk_score": risk,
        "urgency_score": 68,
        "timing_state": "active",
        "market_phase": "breakout",
        "catalyst_status": "unknown",
        "tradability_status": "provisional",
        "spread_status": "unavailable",
        "market_data_freshness": "fresh",
        "preferred_horizon": "4h",
        "data_mode": "live",
        "candidate_source_mode": "live_no_send",
    }


def test_candidate_query_supports_search_filters_and_attention_sort():
    low = _candidate("LOW", route="dashboard_watch", actionability=50, risk=30)
    high = _candidate("HIGH", route="high_confidence_watch", actionability=88, risk=45)

    assert filter_sort_candidates((low, high))[0]["symbol"] == "HIGH"
    assert filter_sort_candidates((low, high), {"search": "low"}) == (low,)
    assert filter_sort_candidates((low, high), {"route": "dashboard_watch"}) == (low,)
    assert filter_sort_candidates((low, high), {"origin": "technical_led"}) == (high, low)
    assert filter_sort_candidates((low, high), {"actionability": "very_high"}) == (high,)
    assert filter_sort_candidates((low, high), {"risk": "low"}) == (low,)


def test_candidate_query_is_bounded_and_ignores_unknown_fields():
    assert dashboard_query({"search": "  BTC  ", "unknown": "x"}) == {"search": "btc"}
    assert dashboard_query({"search": "x" * 121}) == {}


def test_market_observations_support_search_quality_filter_and_sort():
    rows = (
        {
            "symbol": "AAA", "return_24h": 2.0, "volume_24h": 10,
            "freshness_status": "fresh", "spread_status": "unavailable",
            "data_mode": "live",
        },
        {
            "symbol": "BBB", "return_24h": 8.0, "volume_24h": 5,
            "freshness_status": "stale", "spread_status": "verified_good",
            "data_mode": "live",
        },
    )

    assert [row["symbol"] for row in filter_sort_observations(rows)] == ["BBB", "AAA"]
    assert filter_sort_observations(rows, {"search": "aaa"}) == (rows[0],)
    assert filter_sort_observations(rows, {"freshness": "fresh"}) == (rows[0],)
    assert [row["symbol"] for row in filter_sort_observations(rows, {"sort": "volume_desc"})] == ["AAA", "BBB"]
