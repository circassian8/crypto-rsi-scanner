"""Canonical market-field alias precedence regressions."""

from __future__ import annotations

import json


def test_market_state_identity_aliases_are_typed_and_presence_aware():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_state

    valid_fallback = market_state.snapshot_from_market_row(
        {
            "ticker": "SAFE",
            "id": "safe-token",
        },
        observed_at="2026-07-20T17:00:00Z",
    )
    assert valid_fallback.symbol == "SAFE"
    assert valid_fallback.coin_id == "safe-token"
    assert valid_fallback.canonical_asset_id == "safe-token"

    malformed = {
        "symbol": True,
        "ticker": "BORROWED",
        "coin_id": False,
        "id": "borrowed-token",
        "canonical_asset_id": {"unexpected": "mapping"},
        "name": {"unexpected": "mapping"},
        "return_unit": "percent_points",
        "return_4h": 12.0,
        "return_24h": 20.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 4.0,
        "liquidity_usd": 100_000_000.0,
        "spread_bps": 5.0,
        "freshness_status": "fresh",
    }
    snapshot = market_state.snapshot_from_market_row(
        malformed,
        observed_at="2026-07-20T17:00:00Z",
    )
    assert snapshot.symbol == ""
    assert snapshot.coin_id == ""
    assert snapshot.canonical_asset_id == ""
    assert "missing_asset_identity" in snapshot.warnings
    assert "invalid_canonical_asset_identity" in snapshot.warnings

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        [malformed],
        observed_at="2026-07-20T17:00:00Z",
    )
    assert len(snapshots) == 1
    assert anomalies == []


def test_market_freshness_claims_are_typed_and_presence_aware():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_state

    base = {
        "coin_id": "freshness-contract",
        "symbol": "FRESH",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "return_24h": 20.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 10_000_000.0,
    }

    malformed = {
        **base,
        "market_context_freshness_status": {"status": "fresh"},
        "freshness_status": "fresh",
    }
    snapshot = market_state.snapshot_from_market_row(
        malformed,
        observed_at="2026-07-21T11:45:00Z",
    )
    assert snapshot.freshness_status == "invalid"
    assert "invalid_market_freshness_status" in snapshot.warnings
    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        [malformed],
        observed_at="2026-07-21T11:45:00Z",
    )
    assert snapshots[0]["freshness_status"] == "invalid"
    assert anomalies == []

    canonical = market_state.snapshot_from_market_row(
        {**base, "market_context_freshness_status": " FRESH "},
        observed_at="2026-07-21T11:45:00Z",
    )
    assert canonical.freshness_status == "fresh"
    assert "invalid_market_freshness_status" not in canonical.warnings

    for status in ("unknown", "stale"):
        _, diagnostic_anomalies = market_anomaly_scanner.scan_market_rows(
            [{**base, "freshness_status": status}],
            observed_at="2026-07-21T11:45:00Z",
        )
        assert len(diagnostic_anomalies) == 1

    classification_snapshot = {
        key: value
        for key, value in base.items()
        if key not in {"coin_id", "symbol", "return_unit"}
    }
    for invalid in (True, {"status": "fresh"}, "banana", "invalid"):
        assert market_anomaly_scanner.classify_market_state({
            **classification_snapshot,
            "freshness_status": invalid,
        }) == market_anomaly_scanner.NO_REACTION


def test_benchmark_selection_rejects_invalid_fallthrough_conflict_and_duplicates():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    valid_eth = {"coin_id": "ethereum", "symbol": "ETH"}
    invalid_btc, eth = market_state.benchmark_rows([
        {"coin_id": False, "id": "bitcoin", "symbol": "NOTBTC"},
        valid_eth,
    ])
    assert invalid_btc == {}
    assert eth is valid_eth

    conflicting_btc, _eth = market_state.benchmark_rows([
        {"coin_id": "ethereum", "symbol": "BTC"},
    ])
    assert conflicting_btc == {}

    duplicate_btc, _eth = market_state.benchmark_rows([
        {"coin_id": "bitcoin", "symbol": "BTC", "price": 1},
        {"id": "bitcoin", "symbol": "BTC", "price": 2},
    ])
    assert duplicate_btc == {}


def test_catalyst_queue_rejects_non_text_anomaly_identity():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    base = {
        "needs_catalyst_search": True,
        "market_anomaly_id": "mkt:safe:test",
        "canonical_asset_id": "safe-token",
        "symbol": "SAFE",
        "coin_id": "safe-token",
        "priority": 50.0,
        "observed_at": "2026-07-20T17:00:00Z",
    }
    assert market_anomaly_scanner.build_catalyst_search_queue(
        [{**base, "market_anomaly_id": True}]
    ) == []
    assert market_anomaly_scanner.build_catalyst_search_queue(
        [{**base, "canonical_asset_id": False}]
    ) == []


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


def test_nonfinite_liquidity_cannot_claim_high_liquidity_or_raise_priority():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    snapshot_rows, anomalies = market_anomaly_scanner.scan_market_rows(
        [
            {
                "symbol": "INFINITE",
                "coin_id": "infinite",
                "return_unit": "percent_points",
                "return_4h": 10.0,
                "return_24h": 18.0,
                "relative_return_vs_btc_4h": 8.0,
                "volume_zscore_24h": 3.0,
                "liquidity_usd": float("inf"),
                "market_cap": float("inf"),
                "freshness_status": "fresh",
            }
        ],
        observed_at="2026-06-15T16:00:00Z",
    )

    assert snapshot_rows[0]["liquidity_usd"] is None
    assert snapshot_rows[0]["liquidity_tier"] is None
    assert "market_cap" not in snapshot_rows[0]
    assert anomalies[0]["anomaly_type"] == "confirmed_breakout"
    assert anomalies[0]["anomaly_bucket"] == "needs_catalyst_search"
    assert anomalies[0]["priority_components"]["liquidity_tier"] == 0.0
    assert anomalies[0]["priority_components"]["market_cap_turnover"] == 0.0
    json.dumps({"snapshots": snapshot_rows, "anomalies": anomalies}, allow_nan=False)


def test_direct_liquidity_value_overrides_conflicting_coarse_tier():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    base = {
        "coin_id": "liquidity-conflict",
        "symbol": "LIQ",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "return_24h": 20.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "freshness_status": "fresh",
    }

    _, thin = market_anomaly_scanner.scan_market_rows(
        [{**base, "liquidity_usd": 10_000.0, "liquidity_tier": "large"}],
        observed_at="2026-07-21T11:40:00Z",
    )
    assert thin[0]["anomaly_bucket"] == "needs_catalyst_search"
    assert thin[0]["priority_components"]["liquidity_tier"] == -7.0

    _, liquid = market_anomaly_scanner.scan_market_rows(
        [{**base, "liquidity_usd": 10_000_000.0, "liquidity_tier": "thin"}],
        observed_at="2026-07-21T11:40:00Z",
    )
    assert liquid[0]["anomaly_bucket"] == "high_liquidity_breakout"
    assert liquid[0]["priority_components"]["liquidity_tier"] == 9.0

    for invalid_liquidity in ({"borrowed": 10_000_000}, float("inf")):
        _, malformed = market_anomaly_scanner.scan_market_rows(
            [{
                **base,
                "liquidity_usd": invalid_liquidity,
                "liquidity_tier": "large",
            }],
            observed_at="2026-07-21T11:40:00Z",
        )
        assert malformed[0]["anomaly_bucket"] == "needs_catalyst_search"
        assert malformed[0]["priority_components"]["liquidity_tier"] == 0.0

    _, tier_only = market_anomaly_scanner.scan_market_rows(
        [{**base, "liquidity_tier": "large"}],
        observed_at="2026-07-21T11:40:00Z",
    )
    assert tier_only[0]["anomaly_bucket"] == "high_liquidity_breakout"
    assert tier_only[0]["priority_components"]["liquidity_tier"] == 10.0
