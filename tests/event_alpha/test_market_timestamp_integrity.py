"""Fail-closed observation-clock regressions for market anomaly artifacts."""

from __future__ import annotations

from datetime import datetime

import pytest


def _anomaly(**overrides):
    row = {
        "needs_catalyst_search": True,
        "market_anomaly_id": "ma:test:clock",
        "canonical_asset_id": "test-token",
        "symbol": "TEST",
        "coin_id": "test-token",
        "market_state_class": "confirmed_breakout",
        "priority": 75.0,
        "suggested_source_packs_to_search": ["official_exchange_announcements"],
    }
    row.update(overrides)
    return row


def test_market_snapshot_rejects_malformed_selected_observation_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    with pytest.raises(ValueError, match="observed_at is invalid"):
        market_state.snapshot_from_market_row({
            "symbol": "TEST",
            "coin_id": "test-token",
            "observed_at": "not-a-time",
        })

    with pytest.raises(ValueError, match="observed_at argument is invalid"):
        market_state.snapshot_from_market_row(
            {
                "symbol": "TEST",
                "coin_id": "test-token",
                "observed_at": "2026-07-19T08:00:00Z",
            },
            observed_at="not-a-time",
        )


def test_market_snapshot_rejects_timezone_naive_selected_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    with pytest.raises(ValueError, match="observed_at is invalid"):
        market_state.snapshot_from_market_row({
            "symbol": "TEST",
            "coin_id": "test-token",
            "observed_at": "2026-07-19T08:00:00",
        })

    with pytest.raises(ValueError, match="observed_at argument is invalid"):
        market_state.snapshot_from_market_row(
            {
                "symbol": "TEST",
                "coin_id": "test-token",
                "observed_at": "2026-07-19T08:00:00Z",
            },
            observed_at=datetime(2026, 7, 19, 8),
        )


def test_invalid_row_clock_cannot_imply_freshness_under_valid_run_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    snapshot = market_state.snapshot_from_market_row(
        {
            "symbol": "TEST",
            "coin_id": "test-token",
            "observed_at": "not-a-time",
        },
        observed_at="2026-07-19T08:00:00Z",
    )

    assert snapshot.observed_at == "2026-07-19T08:00:00+00:00"
    assert snapshot.freshness_status == "unknown"
    assert "invalid_source_observation_time" in snapshot.warnings


def test_naive_row_clock_cannot_retain_claimed_freshness_under_valid_run_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    snapshot = market_state.snapshot_from_market_row(
        {
            "symbol": "TEST",
            "coin_id": "test-token",
            "observed_at": "2026-07-19T08:00:00",
            "freshness_status": "fresh",
        },
        observed_at="2026-07-19T08:05:00Z",
    )

    assert snapshot.observed_at == "2026-07-19T08:05:00+00:00"
    assert snapshot.freshness_status == "unknown"
    assert "invalid_source_observation_time" in snapshot.warnings


def test_catalyst_queue_rejects_malformed_higher_authority_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    with pytest.raises(ValueError, match="anomaly observed_at is invalid"):
        market_anomaly_scanner.build_catalyst_search_queue(
            [_anomaly(
                observed_at="not-a-time",
                market_state_snapshot={"observed_at": "2026-07-19T08:00:00Z"},
            )],
            observed_at="2026-07-19T08:00:00Z",
        )

    with pytest.raises(ValueError, match="snapshot observed_at is invalid"):
        market_anomaly_scanner.build_catalyst_search_queue(
            [_anomaly(market_state_snapshot={"observed_at": "not-a-time"})],
            observed_at="2026-07-19T08:00:00Z",
        )


def test_catalyst_queue_rejects_timezone_naive_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    with pytest.raises(ValueError, match="anomaly observed_at is invalid"):
        market_anomaly_scanner.build_catalyst_search_queue(
            [_anomaly(observed_at="2026-07-19T08:00:00")],
        )

    with pytest.raises(ValueError, match="snapshot observed_at is invalid"):
        market_anomaly_scanner.build_catalyst_search_queue(
            [_anomaly(market_state_snapshot={"observed_at": datetime(2026, 7, 19, 8)})],
        )


def test_catalyst_queue_deadline_uses_valid_snapshot_clock():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    queue = market_anomaly_scanner.build_catalyst_search_queue([
        _anomaly(market_state_snapshot={"observed_at": "2026-07-19T08:00:00Z"})
    ])

    assert queue[0]["search_deadline"] == "2026-07-19T14:00:00+00:00"
