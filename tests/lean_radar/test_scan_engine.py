from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

import pytest

from crypto_rsi_scanner.lean_radar.config import LeanRadarSettings
from crypto_rsi_scanner.lean_radar.cli import run
from crypto_rsi_scanner.lean_radar.features import build_features
from crypto_rsi_scanner.lean_radar.ideas import build_idea
from crypto_rsi_scanner.lean_radar.market_data import (
    MarketDataError,
    normalize_snapshot,
)
from crypto_rsi_scanner.lean_radar.models import (
    BybitInstrument,
    MarketFeatures,
    MarketSnapshot,
    UniverseAsset,
)
from crypto_rsi_scanner.lean_radar.scan import run_scan
from crypto_rsi_scanner.lean_radar.setups import detect_setup
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore
from crypto_rsi_scanner.client import CoinGeckoClient


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def _instrument(symbol: str, *, source_mode: str = "fixture") -> BybitInstrument:
    return BybitInstrument(
        instrument_id=f"{symbol}USDT",
        base_coin=symbol,
        quote_coin="USDT",
        settle_coin="USDT",
        contract_type="LinearPerpetual",
        status="Trading",
        tick_size="0.001",
        quantity_step="0.1",
        minimum_quantity="0.1",
        maximum_limit_quantity="100000",
        maximum_market_quantity="10000",
        minimum_notional_usdt="5",
        source_observed_at=NOW.isoformat(),
        source_mode=source_mode,
        source_sha256="a" * 64,
    )


def _snapshot(**overrides: object) -> MarketSnapshot:
    values: dict[str, object] = {
        "canonical_asset_id": "solana",
        "symbol": "SOL",
        "name": "Solana",
        "bybit_instrument": "SOLUSDT",
        "observed_at": NOW.isoformat(),
        "source_mode": "fixture",
        "price_usd": 100.0,
        "market_cap_usd": 10_000_000_000.0,
        "volume_usd_24h": 1_000_000_000.0,
        "turnover_ratio_24h": 0.1,
        "return_1h_pp": 4.0,
        "return_24h_pp": 10.0,
        "return_7d_pp": 14.0,
        "rsi_14": 65.0,
        "spread_bps": 10.0,
        "sparkline_prices": tuple(100.0 for _ in range(30)),
        "return_basis": "test_percent_points",
        "rsi_basis": "test_wilder_14",
        "data_quality": "complete",
    }
    values.update(overrides)
    return MarketSnapshot(**values)  # type: ignore[arg-type]


def _features(**snapshot_overrides: object) -> MarketFeatures:
    return MarketFeatures(
        snapshot=_snapshot(**snapshot_overrides),
        baseline_status="warm",
        baseline_sample_count=12,
        volume_zscore=0.5,
        volume_signal_basis="rolling_log_volume_robust_zscore",
        turnover_cross_section_zscore=0.5,
        relative_btc_1h_pp=1.0,
        relative_btc_24h_pp=6.0,
        relative_eth_1h_pp=1.2,
        relative_eth_24h_pp=7.0,
        benchmark_status="ready",
        age_seconds=0.0,
        freshness_status="fresh",
        liquidity_status="adequate",
        chase_risk_score=24.0,
    )


def _market_row(
    canonical_id: str,
    symbol: str,
    *,
    market_cap: float,
    volume: float,
    return_1h: float = 0.5,
    return_24h: float,
    prices: list[float] | None = None,
    spread_bps: float | None = 10.0,
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": canonical_id,
        "symbol": symbol.casefold(),
        "name": canonical_id.replace("-", " ").title(),
        "current_price": (prices or [100.0])[-1],
        "market_cap": market_cap,
        "market_cap_rank": 1,
        "total_volume": volume,
        "price_change_percentage_1h_in_currency": return_1h,
        "price_change_percentage_24h_in_currency": return_24h,
        "price_change_percentage_7d_in_currency": return_24h * 1.5,
        "return_unit": "percent_points",
        "sparkline_in_7d": {"price": prices or _quiet_prices()},
    }
    if spread_bps is not None:
        row["spread_bps"] = spread_bps
    return row


def _quiet_prices() -> list[float]:
    return [100.0 + (0.4 if index % 2 else 0.0) for index in range(30)]


def _scan_rows() -> tuple[dict[str, object], ...]:
    rapid_prices = [100.0 for _ in range(25)] + [100.0, 102.0, 104.0, 107.0, 110.0]
    return (
        _market_row("bitcoin", "BTC", market_cap=1e12, volume=10e9, return_24h=1),
        _market_row("ethereum", "ETH", market_cap=5e11, volume=5e9, return_24h=1),
        _market_row(
            "solana",
            "SOL",
            market_cap=1e8,
            volume=8e7,
            return_1h=6,
            return_24h=12,
            prices=rapid_prices,
        ),
        _market_row("ripple", "XRP", market_cap=1e11, volume=1e9, return_24h=0),
        _market_row("dogecoin", "DOGE", market_cap=5e10, volume=5e8, return_24h=0),
    )


def _store(tmp_path: Path, *, source_mode: str = "fixture") -> LeanRadarStore:
    store = LeanRadarStore(tmp_path / "lean.db")
    store.replace_bybit_catalog(
        tuple(
            _instrument(symbol, source_mode=source_mode)
            for symbol in ("BTC", "ETH", "SOL", "XRP", "DOGE")
        )
    )
    return store


def test_unknown_catalyst_is_visible_but_lowers_confidence() -> None:
    features = _features()
    detection = detect_setup(features)
    assert detection is not None
    assert detection.idea_type == "market_breakout_long"

    unknown = build_idea(features, detection)
    known = build_idea(features, detection, catalyst_context={"status": "known"})

    assert unknown.catalyst_status == "unknown"
    assert unknown.dashboard_route != "diagnostic_hidden"
    assert unknown.confidence_score < known.confidence_score
    assert unknown.risk_score > known.risk_score
    assert unknown.actionability_score == known.actionability_score


def test_features_use_eight_prior_samples_and_direct_benchmark_returns() -> None:
    btc = _snapshot(
        canonical_asset_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        bybit_instrument="BTCUSDT",
        return_1h_pp=1.0,
        return_24h_pp=2.0,
    )
    eth = _snapshot(
        canonical_asset_id="ethereum",
        symbol="ETH",
        name="Ethereum",
        bybit_instrument="ETHUSDT",
        return_1h_pp=0.5,
        return_24h_pp=1.0,
    )
    sol = _snapshot(return_1h_pp=4.0, return_24h_pp=10.0)
    history = {
        "solana": [
            {"volume_usd_24h": 100_000_000.0 + index * 1_000_000.0}
            for index in range(8)
        ]
    }

    rows = build_features((btc, eth, sol), history, evaluated_at=NOW)
    sol_features = next(row for row in rows if row.snapshot.symbol == "SOL")

    assert sol_features.baseline_status == "warm"
    assert sol_features.baseline_sample_count == 8
    assert sol_features.volume_zscore is not None
    assert sol_features.benchmark_status == "ready"
    assert sol_features.relative_btc_1h_pp == 3.0
    assert sol_features.relative_eth_1h_pp == 3.5
    assert sol_features.relative_btc_24h_pp == 8.0
    assert sol_features.relative_eth_24h_pp == 9.0


@pytest.mark.parametrize(
    ("features", "expected_type"),
    (
        (
            replace(_features(return_1h_pp=6.0), volume_zscore=2.5),
            "rapid_market_anomaly",
        ),
        (
            _features(return_1h_pp=1.0, return_24h_pp=16.0, rsi_14=75.0),
            "exhaustion_or_fade_review",
        ),
        (
            _features(return_1h_pp=-1.0, return_24h_pp=-8.0, rsi_14=25.0),
            "pullback_or_mean_reversion",
        ),
    ),
)
def test_core_market_setups_are_explicit(
    features: MarketFeatures,
    expected_type: str,
) -> None:
    detection = detect_setup(features)

    assert detection is not None
    assert detection.idea_type == expected_type
    if expected_type == "exhaustion_or_fade_review":
        idea = build_idea(features, detection)
        assert idea.directional_bias == "short_review"
        assert any("not a short instruction" in risk for risk in idea.risks)


def test_stale_and_low_liquidity_pumps_fail_closed_as_diagnostics() -> None:
    stale = replace(_features(), freshness_status="stale", age_seconds=3600)
    illiquid = replace(
        _features(return_24h_pp=20.0),
        liquidity_status="insufficient",
    )

    assert detect_setup(stale).idea_type == "diagnostic"  # type: ignore[union-attr]
    assert detect_setup(illiquid).idea_type == "diagnostic"  # type: ignore[union-attr]


def test_missing_spread_caps_confidence_and_urgency() -> None:
    features = _features(spread_bps=None)
    detection = detect_setup(features)
    assert detection is not None

    idea = build_idea(features, detection)

    assert idea.spread_status == "unavailable"
    assert idea.confidence_score <= 60
    assert idea.urgency_score <= 55
    assert "Current Bybit spread and depth" in idea.missing_information


def test_return_units_are_percent_points_and_fraction_input_fails() -> None:
    asset = UniverseAsset(
        canonical_asset_id="solana",
        symbol="SOL",
        name="Solana",
        liquidity_rank=1,
        total_volume_usd_24h=1e9,
        bybit_instrument="SOLUSDT",
        origins=("top_liquid",),
        status="active",
        reason=None,
        instrument_source_mode="fixture",
    )
    row = _market_row(
        "solana",
        "SOL",
        market_cap=1e10,
        volume=1e9,
        return_24h=10.0,
    )

    snapshot = normalize_snapshot(row, asset, observed_at=NOW, source_mode="fixture")
    assert snapshot.return_24h_pp == 10.0
    assert "return_4h_pp" not in snapshot.to_dict()
    assert "sparkline_points_proxy" in snapshot.rsi_basis

    row["price_change_percentage_1h_in_currency"] = 2.5
    direct = normalize_snapshot(row, asset, observed_at=NOW, source_mode="fixture")
    assert direct.return_1h_pp == 2.5

    row["price_change_percentage_24h_in_currency"] = None
    no_direct_24h = normalize_snapshot(
        row,
        asset,
        observed_at=NOW,
        source_mode="fixture",
    )
    assert no_direct_24h.return_24h_pp is None

    row["price_change_percentage_24h_in_currency"] = 10.0
    row["return_unit"] = "fraction"
    with pytest.raises(MarketDataError, match="not percent points"):
        normalize_snapshot(row, asset, observed_at=NOW, source_mode="fixture")


def test_live_market_request_uses_the_contractual_volume_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("crypto_rsi_scanner.config.FIXTURE_DIR", None)
    captured: dict[str, object] = {}
    client = CoinGeckoClient()

    async def fake_get(path: str, params: dict[str, object]) -> list[dict[str, object]]:
        captured["path"] = path
        captured["params"] = params
        return []

    monkeypatch.setattr(client, "_get", fake_get)
    rows = asyncio.run(client.get_top_markets_by_volume(200))

    assert rows == []
    assert captured["path"] == "/coins/markets"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params["order"] == "volume_desc"
    assert params["per_page"] == 200
    assert params["sparkline"] == "true"
    assert params["price_change_percentage"] == "1h,24h,7d"


def test_end_to_end_scan_is_transactional_research_only_and_no_send(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)

    result = run_scan(
        store,
        settings,
        source_mode="fixture",
        rows=_scan_rows(),
        observed_at=NOW,
        evaluated_at=NOW,
    )

    assert result["status"] == "complete"
    assert result["snapshot_count"] == 5
    rapid = next(
        idea for idea in result["ideas"] if idea["canonical_asset_id"] == "solana"
    )
    assert rapid["idea_type"] == "rapid_market_anomaly"
    assert rapid["catalyst_status"] == "unknown"
    assert rapid["dashboard_route"] == rapid["telegram_route"] == "urgent_review"
    assert len(
        store.snapshot_history(
            "solana",
            before=(NOW + timedelta(seconds=1)).isoformat(),
        )
    ) == 1
    assert store.list_active_ideas()
    for field in (
        "telegram_sends",
        "trades_created",
        "orders_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        assert result[field] == 0


def test_live_scan_without_authorization_never_calls_provider(tmp_path: Path) -> None:
    store = _store(tmp_path, source_mode="imported_catalog")
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)
    called = False

    def provider() -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
        nonlocal called
        called = True
        return _scan_rows(), {}

    result = run_scan(
        store,
        settings,
        source_mode="live_no_send",
        environ={},
        provider=provider,
        evaluated_at=NOW,
    )

    assert result["status"] == "blocked"
    assert result["provider_call_attempted"] is False
    assert called is False
    assert store.last_scan_status() is None


def test_operator_scan_fails_nonzero_before_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, source_mode="imported_catalog")
    monkeypatch.delenv("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE", raising=False)

    code, result = run(("--db", str(store.path), "scan"))

    assert code == 2
    assert result["status"] == "blocked"
    assert result["provider_call_attempted"] is False
    assert result["current_provider_call_eligibility"] == "authorization_absent"


def test_cadence_block_prevents_a_second_provider_call(tmp_path: Path) -> None:
    store = _store(tmp_path, source_mode="imported_catalog")
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)
    first = run_scan(
        store,
        settings,
        source_mode="imported_snapshot",
        rows=_scan_rows(),
        observed_at=NOW,
        evaluated_at=NOW,
    )
    called = False

    def provider() -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
        nonlocal called
        called = True
        return _scan_rows(), {}

    second = run_scan(
        store,
        settings,
        source_mode="live_no_send",
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        provider=provider,
        evaluated_at=NOW + timedelta(minutes=5),
    )

    assert first["status"] == "complete"
    assert second["status"] == "blocked"
    assert second["cadence_eligible"] is False
    assert second["provider_call_attempted"] is False
    assert called is False


def test_provider_failure_is_recorded_truthfully_and_throttles_retry(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, source_mode="imported_catalog")
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)

    def failing_provider() -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
        raise RuntimeError("untrusted provider detail")

    failed = run_scan(
        store,
        settings,
        source_mode="live_no_send",
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        provider=failing_provider,
        evaluated_at=NOW,
    )
    called = False

    def second_provider() -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
        nonlocal called
        called = True
        return _scan_rows(), {}

    retry = run_scan(
        store,
        settings,
        source_mode="live_no_send",
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        provider=second_provider,
        evaluated_at=NOW + timedelta(minutes=5),
    )

    assert failed["status"] == "provider_failed"
    assert failed["provider_call_attempted"] is True
    assert failed["provider_call_succeeded"] is False
    assert failed["reason"] == "live market collection failed"
    assert "untrusted provider detail" not in str(failed)
    assert store.last_scan_status() == failed
    assert retry["status"] == "blocked"
    assert retry["provider_call_attempted"] is False
    assert called is False


def test_invalid_provider_evidence_records_successful_call_without_hiding_last_ideas(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, source_mode="imported_catalog")
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)
    prior_time = NOW - timedelta(minutes=30)
    complete = run_scan(
        store,
        settings,
        source_mode="imported_snapshot",
        rows=_scan_rows(),
        observed_at=prior_time,
        evaluated_at=prior_time,
    )
    prior_ideas = store.list_active_ideas()
    invalid_rows = [dict(row) for row in _scan_rows()]
    next(row for row in invalid_rows if row["id"] == "solana")["return_unit"] = "fraction"

    def provider() -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
        return tuple(invalid_rows), {"http_status": 200, "result_count": 5}

    blocked = run_scan(
        store,
        settings,
        source_mode="live_no_send",
        observed_at=NOW,
        evaluated_at=NOW,
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        provider=provider,
    )

    assert complete["status"] == "complete"
    assert prior_ideas
    assert blocked["status"] == "market_data_blocked"
    assert blocked["provider_call_attempted"] is True
    assert blocked["provider_call_succeeded"] is True
    assert blocked["reason"] == "provider market evidence failed validation"
    assert blocked["provider_telemetry"] == {"http_status": 200, "result_count": 5}
    assert store.list_active_ideas() == prior_ideas
