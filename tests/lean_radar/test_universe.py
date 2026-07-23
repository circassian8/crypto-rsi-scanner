from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.lean_radar.bybit_universe import load_catalog
from crypto_rsi_scanner.lean_radar.universe import build_universe, load_market_rows


ROOT = Path(__file__).resolve().parents[2]


def test_top_liquid_assets_are_intersected_with_confirmed_bybit_perps() -> None:
    instruments = load_catalog(
        ROOT / "fixtures/bybit_execution_quality/instruments_info.json",
        source_mode="fixture",
    )
    markets = load_market_rows(ROOT / "fixtures/coingecko_smoke/top_markets.json")

    result = build_universe(markets, instruments)

    assert result.status == "ready"
    assert [row.symbol for row in result.active_assets] == ["BTC", "ETH"]
    assert {row.symbol: row.reason for row in result.blocked_assets} == {
        "SOL": "bybit_usdt_perpetual_unverified"
    }
    assert result.exclusion_counts["stable_like"] == 1


def test_manual_watchlist_asset_without_bybit_contract_stays_blocked() -> None:
    instruments = load_catalog(
        ROOT / "fixtures/bybit_execution_quality/instruments_info.json",
        source_mode="fixture",
    )
    markets = load_market_rows(ROOT / "fixtures/coingecko_smoke/top_markets.json")

    result = build_universe(
        markets,
        instruments,
        (
            {"canonical_asset_id": "solana", "symbol": "SOL"},
            {"canonical_asset_id": "bitcoin", "symbol": "BTC"},
        ),
    )

    bitcoin = next(row for row in result.active_assets if row.symbol == "BTC")
    solana = next(
        row
        for row in result.blocked_assets
        if row.canonical_asset_id == "solana" and "manual_watchlist" in row.origins
    )
    assert bitcoin.origins == ("top_liquid", "manual_watchlist")
    assert solana.status == "blocked_unverified"
    assert solana.reason == "bybit_usdt_perpetual_unverified"


def test_without_catalog_no_asset_is_silently_tradable() -> None:
    markets = load_market_rows(ROOT / "fixtures/coingecko_smoke/top_markets.json")

    result = build_universe(markets, ())

    assert result.status == "bybit_catalog_missing"
    assert result.active_assets == ()
    assert all(row.bybit_instrument is None for row in result.blocked_assets)
