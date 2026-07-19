"""Canonical market-field alias precedence regressions."""

from __future__ import annotations


def test_market_state_canonical_zero_values_override_legacy_aliases():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_state

    row = {
        "symbol": "ZERO",
        "coin_id": "zero",
        "return_unit": "percent_points",
        "price": 0.0,
        "current_price": 99.0,
        "return_1h": 0.0,
        "price_change_percentage_1h_in_currency": 8.0,
        "return_4h": 0.0,
        "price_change_percentage_4h_in_currency": 12.0,
        "return_24h": 0.0,
        "price_change_24h": 20.0,
        "relative_return_vs_btc_4h": 0.0,
        "rel_btc_4h": 11.0,
        "volume_zscore_24h": 0.0,
        "volume_zscore": 4.0,
        "volume_24h": 0.0,
        "total_volume": 500_000_000.0,
        "liquidity_usd": 0.0,
        "order_book_liquidity_usd": 9_000_000.0,
        "market_cap": 0.0,
        "mcap": 50_000_000_000.0,
        "funding_level": 0.0,
        "funding_rate": 0.08,
        "open_interest_delta": 0.0,
        "open_interest_delta_24h": 35.0,
        "freshness_status": "fresh",
    }

    snapshot = market_state.snapshot_from_market_row(row).to_dict()

    for field in (
        "price",
        "return_1h",
        "return_4h",
        "return_24h",
        "relative_return_vs_btc_4h",
        "volume_zscore_24h",
        "volume_24h",
        "liquidity_usd",
        "funding_level",
        "open_interest_delta",
    ):
        assert snapshot[field] == 0.0
    assert market_anomaly_scanner.classify_market_state(snapshot, row) == "no_reaction"

    snapshot_rows, anomalies = market_anomaly_scanner.scan_market_rows(
        [row],
        observed_at="2026-06-15T16:00:00Z",
    )
    assert snapshot_rows[0]["liquidity_tier"] == "thin"
    assert anomalies == []

    benchmark = {
        "return_unit": "percent_points",
        "return_4h": 0.0,
        "price_change_percentage_4h_in_currency": 5.0,
    }
    benchmark_snapshot = market_state.snapshot_from_market_row(
        {
            "symbol": "BENCH",
            "coin_id": "bench",
            "return_unit": "percent_points",
            "return_4h": 2.0,
            "freshness_status": "fresh",
        },
        btc_benchmark=benchmark,
    )
    assert benchmark_snapshot.relative_return_vs_btc_4h == 2.0
