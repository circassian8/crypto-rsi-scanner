from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.models import LeanIdea, LeanRadarModelError
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


def _idea(**overrides: object) -> LeanIdea:
    values: dict[str, object] = {
        "idea_id": "lean-btc-20260723",
        "created_at": "2026-07-23T00:00:00+00:00",
        "expires_at": "2026-07-23T04:00:00+00:00",
        "symbol": "BTC",
        "canonical_asset_id": "bitcoin",
        "bybit_instrument": "BTCUSDT",
        "horizon": "4h",
        "idea_type": "relative_strength_long",
        "directional_bias": "long",
        "actionability_score": 72,
        "confidence_score": 61,
        "risk_score": 44,
        "urgency_score": 67,
        "timing_state": "active",
        "market_phase": "acceleration",
        "catalyst_status": "unknown",
        "liquidity_status": "adequate",
        "spread_status": "unavailable",
        "data_quality": "usable_with_missing_execution_quality",
        "why_now": ("Outperforming BTC and ETH",),
        "supporting_facts": ("24h volume is elevated",),
        "risks": ("Catalyst is unknown",),
        "missing_information": ("Current Bybit spread",),
        "what_confirms": ("Holds the breakout",),
        "what_invalidates": ("Loses the prior range",),
        "dashboard_route": "watchlist",
        "telegram_route": "watchlist",
    }
    values.update(overrides)
    return LeanIdea(**values)  # type: ignore[arg-type]


def test_unknown_catalyst_is_valid_operator_truth() -> None:
    idea = _idea()

    assert idea.catalyst_status == "unknown"
    assert idea.dashboard_route == "watchlist"
    assert idea.research_only is True


def test_fade_wording_is_review_only() -> None:
    with pytest.raises(LeanRadarModelError, match="review-only"):
        _idea(
            idea_type="exhaustion_or_fade_review",
            directional_bias="short",
        )


def test_store_schema_has_product_state_but_no_execution_tables(tmp_path: Path) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    with store.connect(write=True):
        pass
    connection = sqlite3.connect(store.path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        connection.close()

    assert {
        "bybit_instruments",
        "manual_watchlist",
        "market_snapshots",
        "ideas",
        "outcomes",
        "calendar_events",
        "notification_state",
        "system_health",
    } <= tables
    assert not {"orders", "positions", "portfolio", "paper_trades"} & tables
