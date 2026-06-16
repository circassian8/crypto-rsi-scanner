"""Unit tests for the indicator math. Pure functions, no network.

Run with pytest:   pytest
Or standalone:     python tests/test_indicators.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_rsi_scanner.indicators import (
    adaptive_thresholds,
    annualized_vol,
    btc_correlation,
    conviction_score,
    decide_flag,
    detect_divergence,
    regime_note,
    rsi_rate_of_change,
    rsi_z_score,
    trend_regime,
    volume_ratio,
    wilder_rsi,
)
from crypto_rsi_scanner.scanner import classify_tier
from crypto_rsi_scanner import formatting


def test_rsi_bounds():
    s = pd.Series(np.random.RandomState(0).randn(200).cumsum() + 100)
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.between(0, 100).all()


def test_rsi_pure_uptrend_is_high():
    s = pd.Series(np.arange(1, 101, dtype=float))  # strictly increasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 100.0


def test_rsi_pure_downtrend_is_low():
    s = pd.Series(np.arange(100, 0, -1, dtype=float))  # strictly decreasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 0.0


def test_rsi_matches_known_value():
    # Classic Wilder worked example (first 14 deltas), final RSI ~ 70.46
    closes = pd.Series([
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ])
    rsi = wilder_rsi(closes, 14).dropna()
    assert abs(rsi.iloc[-1] - 70.46) < 0.5


def test_annualized_vol_constant_is_zero():
    s = pd.Series([100.0] * 50)
    assert annualized_vol(s) == 0.0


def test_z_score_zero_when_flat():
    rsi = pd.Series([50.0] * 100)
    assert rsi_z_score(rsi, 90) == 0.0


def test_rate_of_change():
    rsi = pd.Series([50, 52, 55, 66], dtype=float)
    assert rsi_rate_of_change(rsi, 3) == 16.0


def test_adaptive_thresholds_ordering():
    rsi = pd.Series(np.linspace(20, 80, 100))
    ob, os_ = adaptive_thresholds(rsi, 95, 5)
    assert os_ < ob
    assert 20 <= os_ <= 80 and 20 <= ob <= 80


def test_adaptive_thresholds_fallback_when_short():
    rsi = pd.Series([50.0, 51.0])
    assert adaptive_thresholds(rsi) == (70.0, 30.0)


def test_volume_ratio_spike():
    vols = pd.Series([100.0] * 20 + [300.0])
    assert abs(volume_ratio(vols, 20) - 3.0) < 1e-6


def test_state_features_realized_vol_flat_and_changing():
    from crypto_rsi_scanner import state_features as sf

    flat = pd.Series([100.0] * 80)
    changing = pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)) * 3.0)
    assert sf.realized_vol(flat, window=20) == 0.0
    assert sf.realized_vol(changing, window=20) > 0.0
    vol_s = sf.realized_vol_series(changing, window=20)
    assert vol_s.dropna().iloc[-1] > 0.0


def test_state_features_trailing_percentile_is_trailing_only():
    from crypto_rsi_scanner import state_features as sf

    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 0.0])
    pct = sf.trailing_percentile_series(s, window=5)
    assert pct.iloc[4] >= 0.9      # current max in [1,2,3,4,5]
    assert pct.iloc[5] <= 0.1      # current min in [2,3,4,5,0]
    assert sf.trailing_percentile(pd.Series([10.0] * 10), window=5) == 0.5


def test_state_features_volatility_state_rules():
    from crypto_rsi_scanner import state_features as sf

    assert sf.volatility_state(float("nan"), 0.2, 0.5) == "unknown"
    assert sf.volatility_state(0.10, 0.20, 0.20) == "low_compressed"
    assert sf.volatility_state(0.25, 0.25, 0.50) == "normal"
    assert sf.volatility_state(0.35, 0.30, 0.72) == "high"
    assert sf.volatility_state(0.40, 0.30, 0.80) == "high_expanding"
    assert sf.volatility_state(0.50, 0.35, 0.95) == "crisis"


def test_state_features_cross_sectional_ranks_monotonic():
    from crypto_rsi_scanner import state_features as sf

    ranks = sf.cross_sectional_ranks({"weak": -1.0, "mid": 0.0, "strong": 2.0})
    assert ranks["weak"] == 0.0
    assert ranks["mid"] == 0.5
    assert ranks["strong"] == 1.0
    tied = sf.cross_sectional_ranks({"a": 1.0, "b": 1.0, "c": float("nan")})
    assert tied["a"] == tied["b"]
    assert tied["c"] == 0.5


def test_state_features_rolling_beta_synthetic():
    from crypto_rsi_scanner import state_features as sf

    rng = np.random.RandomState(7)
    btc_ret = rng.normal(0.0005, 0.01, 140)
    asset_ret = 2.0 * btc_ret + rng.normal(0.0, 0.001, 140)
    eth_ret = rng.normal(0.0002, 0.012, 140)
    btc = pd.Series(100.0 * np.cumprod(1.0 + btc_ret))
    asset = pd.Series(50.0 * np.cumprod(1.0 + asset_ret))
    eth = pd.Series(80.0 * np.cumprod(1.0 + eth_ret))

    assert abs(sf.rolling_beta(asset, btc, window=120) - 2.0) < 0.15
    multi = sf.rolling_multi_beta(asset, {"BTC": btc, "ETH": eth}, window=120)
    assert abs(multi["beta_BTC"] - 2.0) < 0.15
    assert abs(multi["beta_ETH"]) < 0.15
    assert 0.0 <= multi["r2"] <= 1.0


def test_state_features_volume_and_liquidity():
    from crypto_rsi_scanner import state_features as sf

    volume = pd.Series([100.0] * 89 + [250.0])
    close = pd.Series([10.0] * 90)
    market_cap = pd.Series([10_000.0] * 90)

    assert sf.volume_z_score(volume, window=90) > 5.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=True) > 100.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=False) > 1000.0
    assert sf.turnover_20(close * volume, market_cap) > 0.10
    assert sf.volume_price_state(-0.04, 2.0) == "down_high_volume"
    assert sf.volume_price_state(0.04, 2.0) == "up_high_volume"
    assert sf.volume_price_state(0.0, 2.0) == "spike_flat_price"
    assert sf.volume_price_state(0.04, 0.0) == "up_normal_volume"
    assert sf.rank_bucket(0.9) == "high"
    assert sf.rank_bucket(0.1) == "low"
    assert sf.liquidity_bucket(1_000_000, 0.02) == "low"
    assert sf.liquidity_bucket(200_000_000, 0.0) == "high"
    assert sf.falling_knife_bucket(75) == "high"
    assert sf.falling_knife_score(
        vol_state="crisis",
        breadth_state="breadth_collapse",
        rs_bucket="low",
        regime="DOWNTREND",
        volume_state="down_high_volume",
        ret_30d=-0.30,
        btc_beta_60=1.5,
        beta_r2_60=0.6,
    ) >= 90


def test_state_features_breadth_snapshot_handles_missing_and_short_histories():
    from crypto_rsi_scanner import state_features as sf

    assert sf.breadth_snapshot({"a": pd.Series([1.0, 2.0])}, {})["state"] == "unknown"

    idx = pd.date_range("2026-01-01", periods=220, freq="D", tz="UTC")
    closes = {
        "a": pd.Series(np.linspace(10, 40, 220), index=idx),
        "b": pd.Series(np.linspace(20, 50, 220), index=idx),
        "c": pd.Series(np.linspace(30, 45, 220), index=idx),
        "short": pd.Series([1.0, 2.0, 3.0], index=idx[:3]),
    }
    rsi = {
        "a": pd.Series([65.0] * 220, index=idx),
        "b": pd.Series([62.0] * 220, index=idx),
        "c": pd.Series([45.0] * 220, index=idx),
    }
    snap = sf.breadth_snapshot(closes, rsi, asof=idx[-1])
    assert snap["median_rsi"] == 62.0
    assert snap["pct_rsi_gt_60"] == 2 / 3
    assert snap["pct_above_50dma"] == 1.0
    assert snap["pct_above_200dma"] == 1.0
    assert snap["state"] == "risk_on_broad"


def test_btc_correlation_perfect():
    btc = pd.Series(np.arange(1, 41, dtype=float))
    coin = btc * 2.0  # perfectly correlated returns
    assert btc_correlation(coin, btc, 30) > 0.99


def test_divergence_bearish():
    # price higher high, RSI lower high -> bearish
    n = 40
    price = pd.Series(np.concatenate([
        np.linspace(10, 20, 10),  # peak ~20
        np.linspace(20, 12, 10),
        np.linspace(12, 25, 10),  # higher peak ~25
        np.linspace(25, 18, 10),
    ]))
    rsi = pd.Series(np.concatenate([
        np.linspace(40, 85, 10),  # high RSI peak
        np.linspace(85, 45, 10),
        np.linspace(45, 70, 10),  # lower RSI peak
        np.linspace(70, 55, 10),
    ]))
    assert detect_divergence(price, rsi, lookback=40, order=3) == "bearish"


# --- event-fade research sleeve ---------------------------------------------

def _event_fade_velvet_candidate(now=None, *, direct=False, no_event_time=False, btc_risk_on=35):
    from datetime import datetime, timezone, timedelta
    from crypto_rsi_scanner import event_fade as ef

    now = now or datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    event_time = None if no_event_time else now - timedelta(hours=2)
    event = ef.CatalystEvent(
        event_id="testvelvet-spacex",
        coin_id="testvelvet",
        symbol="TESTVELVET",
        event_name="SpaceX IPO trading start",
        event_type="etf_approval" if direct else "ipo_proxy",
        event_time=event_time,
        first_seen_time=now - timedelta(days=2),
        source="manual_fixture",
        confidence=0.95,
        external_asset=None if direct else "SpaceX",
        is_proxy_narrative=not direct,
        is_direct_beneficiary=direct,
    )
    market = ef.EventMarketSnapshot(
        symbol="TESTVELVET",
        coin_id="testvelvet",
        timestamp=now,
        price=7.2,
        spot_volume_24h=8_000_000,
        market_cap=45_000_000,
        return_24h=1.2,
        return_72h=3.5,
        return_7d=8.5,
        distance_from_20d_ma=2.0,
        volume_zscore_24h=6.2,
        order_book_depth_1pct=8_000,
        order_book_depth_2pct=25_000,
        spread_bps=45,
    )
    derivatives = ef.EventDerivativesSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        perp_available=True,
        open_interest_24h_change_pct=0.65,
        open_interest_to_market_cap=0.40,
        funding_rate_8h=0.0012,
        perp_spot_volume_ratio=22,
        long_short_ratio=2.1,
        basis=0.025,
    )
    supply = ef.EventSupplyPressureSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        large_holder_exchange_inflow=True,
        cex_inflow_pct_supply=0.02,
        top_holder_concentration=0.62,
        team_or_mm_wallet_activity=True,
    )
    rsi = ef.EventRSISnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        rsi_daily=86,
        rsi_4h=78,
        rsi_weekly=72,
        target_overbought_score=90,
        btc_risk_on_score=btc_risk_on,
        rsi_rollover_confirmed=True,
        bearish_rsi_divergence=True,
    )
    technical = ef.EventTechnicalSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        event_vwap=8.1,
        price_below_event_vwap=True,
        failed_reclaim_event_vwap=True,
        lower_high_confirmed=True,
        first_support_broken=True,
        post_event_high=9.4,
        post_event_lower_high=8.6,
        invalidation_level=8.65,
        entry_reference_price=7.2,
    )
    return ef.FadeCandidate(
        "TESTVELVET", "testvelvet", event, market, derivatives, supply, rsi, technical
    )


def test_event_fade_component_scores_velvet_like_and_direct_beneficiary_low():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    score = ef.calculate_fade_score(candidate, cfg, now)
    assert score >= 80
    assert candidate.component_scores["event_clarity"] >= 70
    assert candidate.component_scores["proxy_purity"] >= 70
    assert candidate.component_scores["pre_event_pump"] >= 90
    assert candidate.component_scores["derivatives_crowding"] >= 80

    direct = _event_fade_velvet_candidate(now, direct=True)
    ef.calculate_fade_score(direct, cfg, now)
    assert direct.component_scores["proxy_purity"] < 50
    assert not ef.is_event_fade_candidate(direct, cfg, now)


def test_event_fade_pre_event_pump_and_optional_data_are_safe():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    event = ef.CatalystEvent(
        "pump-no-derivs", "p", "PUMP", "Manual catalyst", "other",
        now, confidence=0.9, is_proxy_narrative=True,
    )
    market = ef.EventMarketSnapshot(
        "PUMP", "p", now, 1.0, return_24h=0.8, return_7d=10.0, volume_zscore_24h=6.0
    )
    candidate = ef.FadeCandidate("PUMP", "p", event, market)
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    assert candidate.component_scores["pre_event_pump"] >= 90
    assert candidate.component_scores["derivatives_crowding"] == 50
    assert candidate.component_scores["supply_pressure"] == 50
    assert "derivatives data missing" in candidate.warnings


def test_event_fade_post_event_failure_requires_event_passed_and_confirmation():
    from datetime import datetime, timezone, timedelta
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now)
    before_event = candidate.event.event_time - timedelta(minutes=1)
    assert ef.score_post_event_failure(candidate.event, candidate.technical, candidate.rsi, before_event) == 0
    assert ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)

    candidate.technical.failed_reclaim_event_vwap = False
    candidate.technical.lower_high_confirmed = False
    candidate.technical.first_support_broken = False
    assert not ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)


def test_event_fade_state_machine_reaches_short_only_after_failure():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.SHORT_TRIGGERED
    assert signal.state == ef.FadeState.TRIGGERED_SHORT
    assert "dated proxy catalyst" in signal.reason_codes

    no_tech = _event_fade_velvet_candidate(now)
    no_tech.technical = None
    signal = ef.generate_fade_signal(no_tech, cfg, now)
    assert signal.signal_type != ef.FadeSignalType.SHORT_TRIGGERED


def test_event_fade_direct_beneficiary_never_triggers_short():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig(min_trigger_score=70)
    candidate = _event_fade_velvet_candidate(now, direct=True)
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert candidate.fade_score >= cfg.min_trigger_score
    assert candidate.component_scores["pre_event_pump"] == 100
    assert candidate.component_scores["post_event_failure"] == 100
    assert not ef.is_event_fade_candidate(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.NO_TRADE
    assert signal.state == ef.FadeState.DISCOVERED
    assert "not an eligible proxy event-fade candidate" in signal.warnings


def test_event_fade_non_proxy_event_never_triggers_even_if_manually_armed():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    candidate.event.is_proxy_narrative = False
    candidate.state = ef.FadeState.ARMED
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert not ef.is_event_fade_candidate(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.NO_TRADE
    assert signal.state == ef.FadeState.DISCOVERED


def test_event_fade_no_dated_catalyst_does_not_trigger():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now, no_event_time=True)
    signal = ef.generate_fade_signal(candidate, ef.EventFadeConfig(), now)
    assert candidate.component_scores["event_clarity"] < 70
    assert signal.signal_type != ef.FadeSignalType.SHORT_TRIGGERED


def test_event_fade_btc_risk_on_blocks_weak_short():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now, btc_risk_on=95)
    candidate.market.return_7d = 1.6
    candidate.derivatives.perp_spot_volume_ratio = 5.5
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    assert ef.is_btc_regime_blocking_short(candidate, ef.EventFadeConfig())
    assert not ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)


def test_event_fade_risk_sizing_and_technical_helpers():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    sizing = ef.calculate_position_size(
        account_equity=10_000,
        risk_pct=0.005,
        entry_price=7.0,
        stop_price=8.0,
        max_leverage_hint=2.0,
        liquidity_depth_2pct=1_000,
    )
    assert sizing["valid"]
    assert sizing["risk_usd"] == 50
    assert sizing["position_units"] == 50
    assert "notional is large relative to visible 2pct depth" in sizing["warnings"]
    assert not ef.calculate_position_size(10_000, 0.005, 7.0, 7.0, 2.0)["valid"]

    times = [datetime(2026, 1, i + 1, tzinfo=timezone.utc) for i in range(3)]
    assert abs(ef.anchored_vwap([10, 20, 30], [1, 1, 2], times, times[1]) - (80 / 3)) < 1e-9
    assert ef.price_below_level(9, 10)
    assert ef.failed_reclaim([8, 11, 9], 10, lookback=3)
    assert ef.lower_high_confirmed([10, 15, 12, 13, 11])
    assert ef.support_break_confirmed([12, 11, 9], 10)


def test_event_fade_json_loader_and_feature_vector():
    import json
    import tempfile
    from pathlib import Path
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    path = Path(tempfile.mkdtemp()) / "events.json"
    path.write_text(json.dumps([{
        "event_id": "testvelvet-spacex-ipo",
        "coin_id": "testvelvet",
        "symbol": "TESTVELVET",
        "event_name": "SpaceX IPO trading start",
        "event_type": "ipo_proxy",
        "event_time": "2026-06-12T13:30:00Z",
        "first_seen_time": "2026-06-10T00:00:00Z",
        "source": "manual_fixture",
        "confidence": 0.95,
        "external_asset": "SpaceX",
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
    }]))
    events = ef.load_event_fade_events(path)
    assert len(events) == 1
    assert events[0].symbol == "TESTVELVET"

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now)
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    vector = ef.event_fade_feature_vector(candidate)
    assert vector["event_type"] == "ipo_proxy"
    assert vector["fade_score"] >= 80
    assert vector["rsi_rollover_confirmed"] is True
    assert vector["eligible"] is True
    assert vector["signal_type"] == "NO_TRADE"
    assert candidate.state == ef.FadeState.DISCOVERED

    unscored = _event_fade_velvet_candidate(now)
    assert unscored.component_scores == {}
    vector = ef.event_fade_feature_vector(unscored, now=now)
    assert vector["fade_score"] >= 80
    assert vector["eligible"] is True
    assert unscored.component_scores["event_clarity"] >= 70
    assert unscored.state == ef.FadeState.DISCOVERED

    candidate.state = ef.FadeState.WATCHLISTED
    assert ef.event_fade_feature_vector(candidate)["signal_type"] == "WATCHLIST"
    assert ef.event_fade_feature_vector(candidate, ef.EventFadeConfig(min_watchlist_score=95))["signal_type"] == "NO_TRADE"


# --- event discovery research sleeve ----------------------------------------

def _event_discovery_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "raw_events.json", root / "asset_aliases.json"


def _coingecko_universe_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "coingecko_smoke" / "top_markets.json"


def _exchange_announcement_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "binance_announcements.json", root / "bybit_announcements.json"


def _structured_calendar_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "coinmarketcal_events.json", root / "tokenomist_unlocks.json"


def _derivatives_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "coinalyze_derivatives.json"


def _news_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "cryptopanic_news.json", root / "gdelt_news.json", root / "project_blog_rss.json"


def _external_catalyst_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "external_ipo_events.json", root / "sports_fixtures.json", root / "prediction_market_events.json"


def _supply_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return (
        root / "tokenomist_supply.json",
        root / "etherscan_supply.json",
        root / "arkham_supply.json",
        root / "dune_supply.json",
    )


def _event_discovery_fixture_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    return event_discovery.run_discovery(raw, assets, now=now)


def test_event_discovery_manual_provider_fixture_and_missing_path():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    events = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    assert len(events) == 6
    assert events[0].content_hash
    assert events[0].published_at <= events[0].fetched_at
    assert ManualJsonEventProvider(Path("/definitely/missing.json")).fetch_events(start, end) == []

    try:
        ManualJsonEventProvider(Path("/definitely/missing.json"), required=True).fetch_events(start, end)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("required missing manual fixture should fail")

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.json"
        bad_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        assert ManualJsonEventProvider(bad_path).fetch_events(start, end) == []

        try:
            ManualJsonEventProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed manual fixture should fail")


def test_event_discovery_coingecko_universe_provider_uses_hygiene():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    assets = CoinGeckoUniverseProvider(_coingecko_universe_fixture_path(), required=True).fetch_assets()
    by_id = {asset.coin_id: asset for asset in assets}
    assert set(by_id) == {"bitcoin", "ethereum", "solana"}
    assert by_id["bitcoin"].symbol == "BTC"
    assert by_id["bitcoin"].price == 68000.0
    assert by_id["bitcoin"].source == "coingecko_universe"
    assert "tether" not in by_id


def test_event_discovery_exchange_announcement_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    binance_events = BinanceAnnouncementProvider(binance_path, required=True).fetch_events(start, end)
    bybit_events = BybitAnnouncementProvider(bybit_path, required=True).fetch_events(start, end)
    assert len(binance_events) == 1
    assert len(bybit_events) == 1
    assert binance_events[0].provider == "binance_announcements"
    assert binance_events[0].raw_json["event"]["event_type"] == "exchange_listing"
    assert binance_events[0].raw_json["event"]["event_time"] == "2026-06-15T12:00:00+00:00"
    assert bybit_events[0].provider == "bybit_announcements"
    assert bybit_events[0].raw_json["event"]["event_type"] == "perp_listing"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_announcements.json"
        bad_path.write_text(json.dumps({"result": {"list": ["not an object"]}}), encoding="utf-8")
        assert BinanceAnnouncementProvider(bad_path).fetch_events(start, end) == []
        try:
            BinanceAnnouncementProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed announcement fixture should fail")


def test_event_discovery_structured_calendar_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.coinmarketcal import CoinMarketCalProvider
    from crypto_rsi_scanner.event_providers.tokenomist import TokenomistProvider

    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    calendar_events = CoinMarketCalProvider(coinmarketcal_path, required=True).fetch_events(start, end)
    unlock_events = TokenomistProvider(tokenomist_path, required=True).fetch_events(start, end)
    assert len(calendar_events) == 1
    assert len(unlock_events) == 1
    assert calendar_events[0].provider == "coinmarketcal"
    assert calendar_events[0].raw_json["event"]["event_type"] == "mainnet_launch"
    assert "TESTCAL" in (calendar_events[0].body or "")
    assert unlock_events[0].provider == "tokenomist"
    assert unlock_events[0].raw_json["event"]["event_type"] == "token_unlock"
    assert unlock_events[0].raw_json["supply"]["unlock_pct_circulating"] == 0.12

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_calendar.json"
        bad_path.write_text(json.dumps({"events": ["not an object"]}), encoding="utf-8")
        assert CoinMarketCalProvider(bad_path).fetch_events(start, end) == []
        try:
            CoinMarketCalProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed calendar fixture should fail")


def test_event_discovery_normalizes_and_dedupes_events():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    normalized = [event_discovery.normalize_raw_event(event) for event in raw]
    assert len(normalized) == 6
    deduped = event_discovery.dedupe_events(normalized)
    assert len(deduped) == 5
    spacex = [event for event in deduped if event.event_name == "SpaceX IPO trading start"][0]
    assert spacex.event_type == "ipo_proxy"
    assert spacex.external_asset == "SpaceX"
    assert len(spacex.raw_ids) == 2
    assert spacex.confidence == 1.0


def test_event_resolver_aliases_and_rejects_ticker_collision():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases, resolve_event_assets

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    normalized = event_discovery.dedupe_events(event_discovery.normalize_raw_event(event) for event in raw)
    spacex = [event for event in normalized if event.event_name == "SpaceX IPO trading start"][0]
    links = resolve_event_assets(spacex, assets)
    assert links[0].coin_id == "testvelvet"
    assert links[0].link_confidence >= 0.95
    assert links[0].match_reason in ("coin_id", "known_alias")

    collision = [event for event in normalized if event.event_id == "collide-ticker-only"][0]
    assert resolve_event_assets(collision, assets) == []
    low_conf = resolve_event_assets(collision, assets, min_confidence=0.0)
    assert all(link.link_confidence < 0.80 for link in low_conf)


def test_event_discovery_resolves_real_assets_from_clean_universe_fixture():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = event_discovery.load_discovery_assets(
        None,
        universe_path=_coingecko_universe_fixture_path(),
    )
    assert {asset.coin_id for asset in assets} == {"bitcoin", "ethereum", "solana"}

    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_coin = {candidate.asset.coin_id: candidate for candidate in result.candidates}
    assert set(by_coin) == {"bitcoin"}
    btc = by_coin["bitcoin"]
    assert btc.asset.symbol == "BTC"
    assert btc.asset.price == 68000.0
    assert btc.classification.is_direct_beneficiary is True
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_exchange_announcements_are_direct_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTLIST", "TESTPERP"}

    listing = by_symbol["TESTLIST"]
    assert listing.event.event_type == "exchange_listing"
    assert listing.classification.relationship_type == "direct_listing"
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.event.event_type == "perp_listing"
    assert perp.classification.relationship_type == "direct_listing"
    assert perp.classification.is_direct_beneficiary is True
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_calendar_and_unlock_events_are_direct_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTCAL", "TESTUNLOCK"}

    calendar = by_symbol["TESTCAL"]
    assert calendar.event.event_type == "mainnet_launch"
    assert calendar.classification.relationship_type == "direct_protocol_upgrade"
    assert calendar.classification.is_direct_beneficiary is True
    assert calendar.fade_signal.signal_type == FadeSignalType.NO_TRADE

    unlock = by_symbol["TESTUNLOCK"]
    assert unlock.event.event_type == "token_unlock"
    assert unlock.classification.relationship_type == "direct_unlock"
    assert unlock.classification.is_direct_beneficiary is True
    assert unlock.fade_candidate.supply.unlock_pct_circulating == 0.12
    assert unlock.fade_candidate.supply.unlock_amount == 2500000
    assert unlock.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_coinalyze_derivatives_provider_parses_fixture():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    snapshots = CoinalyzeDerivativesProvider(_derivatives_fixture_path(), required=True).fetch_snapshots()
    assert "testlist" in snapshots
    assert "TESTLIST" in snapshots
    assert "TESTLISTUSDT_PERP" in snapshots
    assert "TEST" not in snapshots
    listing = snapshots["testlist"]
    assert listing["symbol"] == "TESTLIST"
    assert listing["perp_available"] is True
    assert listing["funding_rate_8h"] == 0.0012
    assert listing["perp_spot_volume_ratio"] == 22.0
    assert snapshots["testperp"]["perp_available"] is False

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_derivatives.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert CoinalyzeDerivativesProvider(bad_path).fetch_snapshots() == {}
        try:
            CoinalyzeDerivativesProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed derivatives fixture should fail")


def test_event_discovery_derivatives_enrich_candidates_without_overriding_raw():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    ))
    assets = load_asset_aliases(aliases_path)
    derivatives = event_discovery.load_derivatives_snapshots(_derivatives_fixture_path())
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        derivatives_by_asset=derivatives,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.derivatives is not None
    assert listing.fade_candidate.derivatives.open_interest_24h_change_pct == 0.65
    assert listing.fade_candidate.component_scores["derivatives_crowding"] == 100
    assert listing.data_quality["has_derivatives_snapshot"] is True
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.fade_candidate.derivatives is not None
    assert perp.fade_candidate.derivatives.perp_available is False
    assert perp.fade_candidate.component_scores["derivatives_crowding"] == 30
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.derivatives is not None
    assert velvet.fade_candidate.derivatives.open_interest is None
    assert velvet.fade_candidate.derivatives.open_interest_to_market_cap == 0.4
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_supply_providers_parse_fixtures():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.supply_providers.arkham import ArkhamSupplyProvider
    from crypto_rsi_scanner.supply_providers.dune import DuneSupplyProvider
    from crypto_rsi_scanner.supply_providers.etherscan import EtherscanSupplyProvider
    from crypto_rsi_scanner.supply_providers.tokenomist import TokenomistSupplyProvider

    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    tokenomist = TokenomistSupplyProvider(tokenomist_path, required=True).fetch_snapshots()
    etherscan = EtherscanSupplyProvider(etherscan_path, required=True).fetch_snapshots()
    arkham = ArkhamSupplyProvider(arkham_path, required=True).fetch_snapshots()
    dune = DuneSupplyProvider(dune_path, required=True).fetch_snapshots()
    assert tokenomist["testprediction"]["unlock_pct_circulating"] == 0.08
    assert tokenomist["TESTPRED"]["unlock_amount"] == 1800000.0
    assert tokenomist["testvelvet"]["unlock_pct_circulating"] == 0.0
    assert tokenomist["TESTVELVET"]["top_holder_concentration"] == 0.10
    assert etherscan["testlist"]["large_holder_exchange_inflow"] is True
    assert etherscan["TESTLIST"]["cex_inflow_pct_supply"] == 0.04
    assert arkham["testai"]["team_or_mm_wallet_activity"] is True
    assert dune["testfan"]["admin_or_mint_risk"] is True

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_supply.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert TokenomistSupplyProvider(bad_path).fetch_snapshots() == {}
        try:
            TokenomistSupplyProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed supply fixture should fail")


def test_event_discovery_supply_enriches_without_overriding_raw_or_bypassing_gates():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, _bybit_path = _exchange_announcement_fixture_paths()
    _cryptopanic_path, _gdelt_path, _blog_path = _news_fixture_paths()
    _ipo_path, _sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    start = datetime(2026, 6, 13, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        prediction_market_events_path=prediction_path,
    ))
    assets = load_asset_aliases(aliases_path)
    supply = event_discovery.load_supply_snapshots(
        tokenomist_supply_path=tokenomist_path,
        etherscan_supply_path=etherscan_path,
        arkham_supply_path=arkham_path,
        dune_supply_path=dune_path,
    )
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        supply_by_asset=supply,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.supply is not None
    assert listing.fade_candidate.supply.large_holder_exchange_inflow is True
    assert listing.fade_candidate.component_scores["supply_pressure"] >= 60
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    pred = by_symbol["TESTPRED"]
    assert pred.fade_candidate.supply is not None
    assert pred.fade_candidate.supply.unlock_pct_circulating == 0.08
    assert pred.data_quality["has_supply_snapshot"] is True
    assert pred.fade_signal.signal_type in {FadeSignalType.NO_TRADE, FadeSignalType.WATCHLIST}

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.supply is not None
    assert velvet.fade_candidate.supply.top_holder_concentration == 0.62
    assert velvet.fade_candidate.supply.unlock_pct_circulating is None
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_news_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider
    from crypto_rsi_scanner.event_providers.gdelt import GdeltProvider
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    cryptopanic = CryptoPanicProvider(cryptopanic_path, required=True).fetch_events(start, end)
    gdelt = GdeltProvider(gdelt_path, required=True).fetch_events(start, end)
    blog = ProjectBlogRssProvider(blog_path, required=True).fetch_events(start, end)
    assert len(cryptopanic) == 2
    assert len(gdelt) == 1
    assert len(blog) == 2
    assert cryptopanic[0].provider == "cryptopanic"
    assert cryptopanic[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert gdelt[0].provider == "gdelt"
    assert gdelt[0].raw_json["event"]["event_type"] == "sports_event"
    assert blog[0].provider == "project_blog_rss"
    assert blog[0].raw_json["event"]["event_id"] == "testlate-anthropic-demo"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_news.json"
        bad_path.write_text(json.dumps({"results": ["not an object"]}), encoding="utf-8")
        assert CryptoPanicProvider(bad_path).fetch_events(start, end) == []
        try:
            CryptoPanicProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed news fixture should fail")


def test_event_discovery_news_pipeline_proxy_direct_late_and_ambiguous_safety():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        cryptopanic_path=cryptopanic_path,
        gdelt_path=gdelt_path,
        project_blog_rss_path=blog_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 5
    assert set(by_symbol) == {"TESTAI", "TESTBTC", "TESTFAN", "TESTLATE", "TESTAMBIG"}

    ai = by_symbol["TESTAI"]
    assert ai.classification.is_proxy_narrative is True
    assert ai.classification.is_direct_beneficiary is False
    assert ai.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED

    btc = by_symbol["TESTBTC"]
    assert btc.classification.is_direct_beneficiary is True
    assert btc.classification.relationship_type == "direct_token_event"
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE

    fan = by_symbol["TESTFAN"]
    assert fan.classification.is_proxy_narrative is True
    assert fan.classification.relationship_type in ("proxy_exposure", "proxy_attention")
    assert fan.fade_signal.signal_type == FadeSignalType.NO_TRADE

    late = by_symbol["TESTLATE"]
    assert late.classification.is_proxy_narrative is True
    assert late.fade_candidate.component_scores["event_clarity"] < 70
    assert late.fade_signal.signal_type == FadeSignalType.NO_TRADE

    ambiguous = by_symbol["TESTAMBIG"]
    assert ambiguous.classification.relationship_type == "ambiguous"
    assert ambiguous.data_quality["classifier_pass"] is False
    assert ambiguous.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_external_catalyst_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.external_ipo import ExternalIpoProvider
    from crypto_rsi_scanner.event_providers.prediction_market_events import PredictionMarketEventsProvider
    from crypto_rsi_scanner.event_providers.sports_fixtures import SportsFixturesProvider

    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    ipo_events = ExternalIpoProvider(ipo_path, required=True).fetch_events(start, end)
    sports_events = SportsFixturesProvider(sports_path, required=True).fetch_events(start, end)
    prediction_events = PredictionMarketEventsProvider(prediction_path, required=True).fetch_events(start, end)
    assert len(ipo_events) == 1
    assert len(sports_events) == 2
    assert len(prediction_events) == 2
    assert ipo_events[0].provider == "external_ipo"
    assert ipo_events[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert ipo_events[0].raw_json["event"]["event_time_confidence"] == 0.45
    assert sports_events[0].raw_json["event"]["event_type"] == "sports_event"
    assert prediction_events[0].raw_json["event"]["event_type"] == "external_proxy_event"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_external.json"
        bad_path.write_text(json.dumps({"events": ["not an object"]}), encoding="utf-8")
        assert ExternalIpoProvider(bad_path).fetch_events(start, end) == []
        try:
            ExternalIpoProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed external catalyst fixture should fail")


def test_event_discovery_external_catalysts_are_radar_first_and_link_narrowly():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        external_ipo_path=ipo_path,
        sports_fixtures_path=sports_path,
        prediction_market_events_path=prediction_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert len(raw) == 5
    event_names = {event.event_name for event in result.normalized_events}
    assert "SpaceX IPO calendar placeholder" in event_names
    assert "Test FC vs Rival FC" in event_names
    assert "Will the Example City election result be certified today?" in event_names

    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert set(by_symbol) == {"TESTFAN", "TESTPRED"}

    fan = by_symbol["TESTFAN"]
    assert fan.classification.is_proxy_narrative is True
    assert fan.event.event_type == "sports_event"
    assert fan.fade_signal.signal_type == FadeSignalType.NO_TRADE

    pred = by_symbol["TESTPRED"]
    assert pred.classification.is_proxy_narrative is True
    assert pred.event.event_type == "external_proxy_event"
    assert pred.fade_candidate.component_scores["pre_event_pump"] >= 60
    assert pred.fade_signal.signal_type in {FadeSignalType.NO_TRADE, FadeSignalType.WATCHLIST}


def test_event_classification_proxy_direct_and_ambiguous_cases():
    result = _event_discovery_fixture_result()
    by_coin = {classification.coin_id: classification for classification in result.classifications}
    assert by_coin["testvelvet"].is_proxy_narrative is True
    assert by_coin["testvelvet"].is_direct_beneficiary is False
    assert by_coin["testvelvet"].relationship_type == "proxy_exposure"
    assert by_coin["testbtc"].is_proxy_narrative is False
    assert by_coin["testbtc"].is_direct_beneficiary is True
    assert by_coin["testbtc"].relationship_type == "direct_token_event"
    assert by_coin["testtoken"].relationship_type == "direct_listing"
    assert by_coin["testpump"].relationship_type == "ambiguous"


def test_event_discovery_pipeline_and_event_fade_safety():
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType

    result = _event_discovery_fixture_result()
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(result.raw_events) == 6
    assert len(result.normalized_events) == 5
    assert "COLLIDE" not in by_symbol

    velvet = by_symbol["TESTVELVET"]
    assert velvet.classification.is_proxy_narrative is True
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED

    btc = by_symbol["TESTBTC"]
    assert btc.classification.is_direct_beneficiary is True
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert btc.fade_candidate.state.value == "DISCOVERED"

    listing = by_symbol["TESTTOKEN"]
    assert listing.classification.relationship_type == "direct_listing"
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    ambiguous = by_symbol["TESTPUMP"]
    assert ambiguous.classification.relationship_type == "ambiguous"
    assert ambiguous.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert ambiguous.data_quality["classifier_pass"] is False

    report = event_discovery.format_discovery_report(result)
    assert "EVENT DISCOVERY REPORT" in report
    assert "EVENT RADAR" in report
    assert "TESTVELVET" in report
    assert "TESTBTC" in report


def test_event_discovery_scanner_report_uses_local_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = events_path
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "EVENT DISCOVERY REPORT" in text
        assert "TESTVELVET" in text
        assert "TESTBTC" in text
        assert "no alerts, DB writes, or trades" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_exchange_only_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "TESTPERP" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_derivatives_fixture():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    derivatives_path = _derivatives_fixture_path()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = derivatives_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "TESTPERP" in text
        assert "deriv=yes" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_supply_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, _bybit_path = _exchange_announcement_fixture_paths()
    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_tokenomist_supply = config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH
    orig_etherscan_supply = config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH
    orig_arkham_supply = config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH
    orig_dune_supply = config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = tokenomist_path
    config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = etherscan_path
    config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = arkham_path
    config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = dune_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "supply=yes" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = orig_tokenomist_supply
        config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = orig_etherscan_supply
        config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = orig_arkham_supply
        config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = orig_dune_supply
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_news_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = cryptopanic_path
    config.EVENT_DISCOVERY_GDELT_PATH = gdelt_path
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = blog_path
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTAI" in text
        assert "TESTFAN" in text
        assert "TESTLATE" in text
        assert "TESTAMBIG" in text
        assert "proxy" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_external_catalyst_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = ipo_path
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = sports_path
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = prediction_path
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "SpaceX IPO calendar placeholder" in text
        assert "TESTFAN" in text
        assert "TESTPRED" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_structured_calendar_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = coinmarketcal_path
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = tokenomist_path
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTCAL" in text
        assert "TESTUNLOCK" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_conviction_monotonic_with_severity():
    base = {"flag": "OB", "rsi_z": 0.0, "volume_ratio": 1.0}
    watch = conviction_score({**base, "severity": "WATCH"})
    alert = conviction_score({**base, "severity": "ALERT"})
    extreme = conviction_score({**base, "severity": "EXTREME"})
    assert watch < alert < extreme


def test_conviction_rewards_confluence():
    weak = conviction_score({"flag": "OB", "severity": "WATCH"})
    strong = conviction_score({
        "flag": "OB",
        "severity": "WATCH",
        "rsi_4h": 75,
        "rsi_weekly": 72,
        "volume_ratio": 2.0,
        "divergence": "bearish",
        "rsi_z": 2.5,
    })
    assert strong > weak
    assert 0 <= strong <= 100


def test_conviction_uses_edge_prior_when_setup_known():
    favorable = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "favorable", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    adverse = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    no_edge = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "breakdown_risk",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    assert favorable > adverse > no_edge


def test_conviction_unflagged_is_zero():
    assert conviction_score({"flag": "", "severity": ""}) == 0


# --- pre-alert flag decision -------------------------------------------------

def test_decide_flag_crossed():
    assert decide_flag(72, 5, 70, 30, 5, 3) == "OB"
    assert decide_flag(25, -5, 70, 30, 5, 3) == "OS"


def test_decide_flag_pre_ob_requires_momentum():
    # within margin (67 in [65,70)) and rising fast -> PRE_OB
    assert decide_flag(67, 4, 70, 30, 5, 3) == "PRE_OB"
    # same level but not moving toward -> no flag
    assert decide_flag(67, 1, 70, 30, 5, 3) == ""


def test_decide_flag_pre_os():
    assert decide_flag(33, -4, 70, 30, 5, 3) == "PRE_OS"
    assert decide_flag(33, 0, 70, 30, 5, 3) == ""


def test_decide_flag_neutral():
    assert decide_flag(50, 1, 70, 30, 5, 3) == ""


def test_decide_flag_adaptive_threshold():
    # a coin whose effective OB is 64 flags OB at 65 even though < 70
    assert decide_flag(65, 2, 64, 30, 5, 3) == "OB"


# --- tier routing ------------------------------------------------------------

def test_classify_tier_instant_on_severity():
    assert classify_tier("OB", "EXTREME", 40) == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_classify_tier_instant_on_conviction():
    assert classify_tier("OB", "WATCH", 80) == "INSTANT"


def test_classify_tier_digest_low_conviction_watch():
    assert classify_tier("OB", "WATCH", 30) == "DIGEST"


def test_classify_tier_pre_always_digest():
    assert classify_tier("PRE_OB", "APPROACHING", 99) == "DIGEST"
    assert classify_tier("PRE_OS", "APPROACHING", 99) == "DIGEST"


def test_conviction_approaching_below_watch():
    appr = conviction_score({"flag": "PRE_OB", "severity": "APPROACHING"})
    watch = conviction_score({"flag": "OB", "severity": "WATCH"})
    assert appr < watch


# --- trend regime ------------------------------------------------------------

def test_regime_unknown_when_short():
    s = pd.Series(np.arange(50, dtype=float))
    assert trend_regime(s, 50, 200, 20) == "UNKNOWN"


def test_regime_uptrend():
    # steadily rising over 260 bars: price > 200MA, 50MA > 200MA, slope up
    s = pd.Series(np.linspace(10, 110, 260))
    assert trend_regime(s, 50, 200, 20) == "UPTREND"


def test_regime_downtrend():
    s = pd.Series(np.linspace(110, 10, 260))
    assert trend_regime(s, 50, 200, 20) == "DOWNTREND"


def test_regime_range():
    # oscillating with no net drift -> neither aligned up nor down
    x = np.arange(260)
    s = pd.Series(50 + 5 * np.sin(x / 5.0))
    assert trend_regime(s, 50, 200, 20) == "RANGE"


def test_regime_note_direction_matters():
    assert regime_note("OB", "UPTREND") == "continuation"
    assert regime_note("OB", "DOWNTREND") == "reversal?"
    assert regime_note("OS", "UPTREND") == "dip?"
    assert regime_note("OS", "DOWNTREND") == "continuation"
    # pre-states map to their direction
    assert regime_note("PRE_OB", "RANGE") == "range-top"
    assert regime_note("PRE_OS", "RANGE") == "range-bottom"


def test_regime_note_empty_when_unknown_or_unflagged():
    assert regime_note("OB", "UNKNOWN") == ""
    assert regime_note("", "UPTREND") == ""


# --- setup taxonomy (split signal intent) ------------------------------------

def test_signal_registry_definitions_cover_core_setups():
    from crypto_rsi_scanner import signal_registry as reg
    assert set(reg.SETUPS) == {
        "mean_reversion", "dip_buy", "trend_continuation", "breakdown_risk",
    }
    assert reg.signal_for("OB", "UPTREND").setup_type == "trend_continuation"
    assert reg.signal_for("OS", "DOWNTREND").expected_dir == "down"
    assert reg.edge_conviction_prior("dip_buy", "favorable") > reg.edge_conviction_prior("dip_buy", "adverse")
    assert reg.edge_conviction_prior("breakdown_risk", "favorable") == reg.edge_conviction_prior("breakdown_risk", "adverse")


def test_signal_registry_loads_explicit_prior_overrides():
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import signal_registry as reg

    path = Path(tempfile.mkdtemp()) / "registry_priors.json"
    path.write_text(json.dumps({
        "schema": 1,
        "setups": {
            "dip_buy": {"edge_priors": {"favorable": 73, "neutral": 41, "adverse": 11}},
            "breakdown_risk": {"edge_priors": {"adverse": 99, "no_edge": 19}},
        },
    }))
    overrides = reg.load_prior_overrides(path, strict=True)

    assert reg.edge_conviction_prior("dip_buy", "favorable", overrides=overrides) == 73
    assert reg.edge_conviction_prior("dip_buy", "adverse", overrides=overrides) == 11
    # Context-only setups still read the no_edge prior, never an alignment key.
    assert reg.edge_conviction_prior("breakdown_risk", "adverse", overrides=overrides) == 19


def test_setup_for_mapping():
    from crypto_rsi_scanner.indicators import setup_for
    assert setup_for("OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("OS", "UPTREND") == ("dip_buy", "up")
    assert setup_for("OS", "DOWNTREND") == ("breakdown_risk", "down")
    assert setup_for("OB", "DOWNTREND") == ("mean_reversion", "down")
    assert setup_for("OB", "RANGE") == ("mean_reversion", "down")
    assert setup_for("OS", "RANGE") == ("mean_reversion", "up")
    # pre-states collapse to their direction
    assert setup_for("PRE_OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("PRE_OS", "DOWNTREND") == ("breakdown_risk", "down")
    # unknown / missing regime -> base mean-reversion read
    assert setup_for("OB", "UNKNOWN") == ("mean_reversion", "down")
    assert setup_for("OS", "") == ("mean_reversion", "up")
    assert setup_for("", "UPTREND") == ("", "")


def test_favorable_by_direction():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("up", 5.0) == 1 and favorable("up", -5.0) == 0
    assert favorable("down", -5.0) == 1 and favorable("down", 5.0) == 0
    # legacy flags still accepted (base mean-reversion read)
    assert favorable("OB", -5.0) == 1
    assert favorable("OS", 5.0) == 1


def test_setup_aware_grading_flips_continuation():
    # The whole point: continuation setups are graded against their OWN
    # direction, so a correct continuation no longer counts as a failed reversion.
    from crypto_rsi_scanner.indicators import setup_for
    from crypto_rsi_scanner.outcomes import favorable
    # OS in a downtrend = breakdown_risk: price falling further CONFIRMS it
    _, exp = setup_for("OS", "DOWNTREND")
    assert favorable(exp, -8.0) == 1     # was 0 under the old OS=bounce convention
    # OB in an uptrend = trend_continuation: price rising CONFIRMS it
    _, exp = setup_for("OB", "UPTREND")
    assert favorable(exp, 6.0) == 1      # was 0 under the old OB=fade convention


def test_card_headlines_setup():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Dip Buy" in out and "expecting upside" in out


# --- market-regime gating ----------------------------------------------------

def test_market_alignment_mapping():
    from crypto_rsi_scanner.indicators import market_alignment
    assert market_alignment("dip_buy", "UPTREND") == "favorable"
    assert market_alignment("dip_buy", "BULL") == "favorable"  # backtest label
    assert market_alignment("trend_continuation", "UPTREND") == "favorable"
    assert market_alignment("mean_reversion", "RANGE") == "favorable"
    assert market_alignment("mean_reversion", "CHOP") == "favorable"  # backtest label
    assert market_alignment("mean_reversion", "UPTREND") == "adverse"
    assert market_alignment("dip_buy", "DOWNTREND") == "adverse"
    assert market_alignment("dip_buy", "BEAR") == "adverse"  # backtest label
    assert market_alignment("trend_continuation", "RANGE") == "adverse"
    # breakdown_risk: no edge anywhere -> never favorable
    assert market_alignment("breakdown_risk", "DOWNTREND") == "adverse"
    assert market_alignment("breakdown_risk", "RANGE") == "adverse"
    # neutral cells / unknown / unflagged
    assert market_alignment("mean_reversion", "DOWNTREND") == "neutral"
    assert market_alignment("dip_buy", "UNKNOWN") == "neutral"
    assert market_alignment("", "UPTREND") == "neutral"


def test_setup_has_edge():
    from crypto_rsi_scanner.indicators import setup_has_edge
    assert setup_has_edge("mean_reversion") and setup_has_edge("dip_buy")
    assert not setup_has_edge("breakdown_risk")
    assert not setup_has_edge("")


def test_market_conviction_adjustment():
    from crypto_rsi_scanner.indicators import market_conviction_adjustment
    assert market_conviction_adjustment(50, "favorable", 12) == 62
    assert market_conviction_adjustment(50, "adverse", 12) == 38
    assert market_conviction_adjustment(50, "neutral", 12) == 50
    assert market_conviction_adjustment(95, "favorable", 12) == 100   # clamped
    assert market_conviction_adjustment(5, "adverse", 12) == 0        # clamped


def test_classify_tier_market_gating():
    from crypto_rsi_scanner.scanner import classify_tier
    # adverse setup that would normally be INSTANT (ALERT) -> held to digest
    assert classify_tier("OB", "ALERT", 80, "adverse") == "DIGEST"
    # ...unless it's an outright extreme
    assert classify_tier("OB", "EXTREME", 80, "adverse") == "INSTANT"
    # favorable / neutral unaffected; default arg preserves old behavior
    assert classify_tier("OB", "ALERT", 10, "favorable") == "INSTANT"
    assert classify_tier("OB", "WATCH", 80, "neutral") == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_card_shows_market_alignment():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up",
                       market_regime="UPTREND", market_aligned="favorable")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Bull market" in out and "favors this setup" in out


def test_card_mutes_no_edge_setup():
    s = _sample_signal(setup_type="breakdown_risk", expected_dir="down",
                       market_regime="DOWNTREND", market_aligned="adverse")
    out = formatting.telegram_html("instant", [s], "t")
    assert "no historical edge" in out
    assert "expecting downside" not in out      # direction muted
    assert "Bear market" in out and "little edge" in out


def test_storage_save_signal_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "s.db")
    scan_id = st.save_scan(10, 2, 1)
    st.save_signal(scan_id, {
        "symbol": "BTC", "coin_id": "bitcoin", "flag": "OB", "severity": "ALERT",
        "rsi_daily": 75.0, "conviction": 60, "tier": "INSTANT", "regime": "UPTREND",
        "setup_type": "trend_continuation", "expected_dir": "up",
        "market_regime": "UPTREND", "market_aligned": "favorable",
        "price": 70000.0, "is_new": 1,
        "state_json": '{"version":1}',
    })
    row = st.conn.execute(
        "SELECT symbol, market_regime, market_aligned, setup_type, state_json FROM signals"
    ).fetchone()
    assert row["symbol"] == "BTC" and row["market_regime"] == "UPTREND"
    assert row["market_aligned"] == "favorable"
    assert row["setup_type"] == "trend_continuation"
    assert row["state_json"] == '{"version":1}'
    assert st.recent_signal_coin_ids("2020-01-01T00:00:00+00:00") == ["bitcoin"]
    st.close()


def test_scanner_state_context_is_shadow_only():
    import json
    from crypto_rsi_scanner import scanner

    idx = pd.date_range("2025-01-01", periods=240, freq="D", tz="UTC")
    rng = np.random.RandomState(42)
    btc = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)))), index=idx)
    eth = pd.Series(80 * np.exp(np.cumsum(rng.normal(0.001, 0.035, len(idx)))), index=idx)
    coin = pd.Series(20 * np.exp(np.cumsum(rng.normal(0.001, 0.05, len(idx)))), index=idx)
    vols = pd.Series(np.linspace(8_000_000, 12_000_000, len(idx)), index=idx)
    btc_vols = pd.Series(np.linspace(500_000_000, 650_000_000, len(idx)), index=idx)
    eth_vols = pd.Series(np.linspace(300_000_000, 400_000_000, len(idx)), index=idx)
    daily = {
        "bitcoin": (btc, btc_vols),
        "ethereum": (eth, eth_vols),
        "shadowcoin": (coin, vols),
    }
    market = {
        "id": "shadowcoin", "symbol": "shd", "name": "ShadowCoin",
        "current_price": float(coin.iloc[-1]), "market_cap": 300_000_000,
        "total_volume": 12_000_000, "market_cap_rank": 123,
    }
    coin_map = {
        "bitcoin": {"id": "bitcoin", "symbol": "btc", "market_cap": 1_000_000_000_000},
        "ethereum": {"id": "ethereum", "symbol": "eth", "market_cap": 500_000_000_000},
        "shadowcoin": market,
    }
    base = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND")
    ctx = scanner._build_state_context(daily, coin_map, btc, eth)
    shadow = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND", ctx)

    assert base is not None and shadow is not None
    for key in ("flag", "setup_type", "expected_dir", "market_aligned", "conviction", "tier"):
        assert shadow[key] == base[key]
    assert shadow["vol_state"] in {"unknown", "low_compressed", "normal", "high", "high_expanding", "crisis"}
    assert shadow["breadth_state"] == json.loads(shadow["state_json"])["breadth"]["state"]
    assert set(("rs_bucket", "liquidity_bucket", "falling_knife_score")).issubset(shadow)


def test_format_signal_adds_compact_state_tokens():
    from crypto_rsi_scanner import scanner

    s = _sample_signal(
        vol_state="crisis",
        breadth_state="washout",
        rs_bucket="low",
        liquidity_bucket="low",
        falling_knife_score=82,
    )
    line = scanner._format_signal(s, is_new=False)
    assert "vol-state:crisis" in line
    assert "breadth:washout" in line
    assert "RS:low" in line
    assert "liq:low" in line
    assert "knife:82" in line


def test_dry_run_csv_helper_does_not_write():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner, config

    path = Path(tempfile.mkdtemp()) / "latest.csv"
    orig = config.CSV_OUT
    config.CSV_OUT = path
    try:
        df = pd.DataFrame([{"symbol": "AAA", "sparkline": [1, 2], "state": {"x": 1}}])
        assert scanner._write_latest_csv(df, dry_run=True) is False
        assert not path.exists()
        assert scanner._write_latest_csv(df, dry_run=False) is True
        assert path.exists()
        assert "sparkline" not in path.read_text()
    finally:
        config.CSV_OUT = orig


# --- .env loader -------------------------------------------------------------

def test_dotenv_skips_empty_values():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.config import _load_dotenv

    env_path = Path(tempfile.mkdtemp()) / ".env"
    env_path.write_text("RSI_TEST_FILLED=hello\nRSI_TEST_EMPTY=\n# comment\n")

    for k in ("RSI_TEST_FILLED", "RSI_TEST_EMPTY"):
        os.environ.pop(k, None)
    try:
        _load_dotenv(env_path)
        # filled value is loaded; empty value is treated as unset (uses default)
        assert os.environ.get("RSI_TEST_FILLED") == "hello"
        assert "RSI_TEST_EMPTY" not in os.environ
    finally:
        os.environ.pop("RSI_TEST_FILLED", None)


# --- universe hygiene --------------------------------------------------------

def _market(**over):
    base = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 100.0, "market_cap": 1_000_000_000.0,
        "total_volume": 20_000_000.0,
        "price_change_percentage_24h_in_currency": 2.0,
    }
    base.update(over)
    return base


def test_universe_filters_stable_wrapped_and_bad_quality():
    from crypto_rsi_scanner import universe
    cases = [
        (_market(id="tether", symbol="usdt", name="Tether"), "stable_like"),
        (_market(id="usd1-wlfi", symbol="usd1", name="USD1"), "stable_like"),
        (_market(id="global-dollar", symbol="usdg", name="Global Dollar"), "stable_like"),
        (_market(id="usdtb", symbol="usdtb", name="USDtb"), "stable_like"),
        (_market(id="bfusd", symbol="bfusd", name="BFUSD"), "stable_like"),
        (_market(id="apxusd", symbol="apxusd", name="apxUSD"), "stable_like"),
        (_market(id="united-stables", symbol="u", name="United Stables"), "stable_like"),
        (_market(id="gho", symbol="gho", name="GHO"), "stable_like"),
        (_market(id="ylds", symbol="ylds", name="YLDS"), "stable_like"),
        (_market(id="usx", symbol="usx", name="USX"), "stable_like"),
        (_market(id="tether-gold", symbol="xaut", name="Tether Gold"), "stable_like"),
        (_market(id="pax-gold", symbol="paxg", name="PAX Gold"), "stable_like"),
        (_market(id="wrapped-bitcoin", symbol="wbtc", name="Wrapped Bitcoin"), "excluded_symbol"),
        (_market(id="bridged-eth", symbol="beth", name="Bridged ETH"), "wrapped_staked_or_synthetic"),
        (_market(id="thin", symbol="thin", name="Thin", total_volume=10.0), "low_liquidity"),
        (_market(id="bad", symbol="bad", name="Bad", price_change_percentage_24h_in_currency=900.0), "suspicious_24h_move"),
    ]
    for market, reason in cases:
        assert universe.exclusion_reason(market) == reason


def test_universe_keeps_stacks_and_limits_clean_results():
    from crypto_rsi_scanner import universe
    markets = [
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="ethereum", symbol="eth", name="Ethereum"),
    ]
    kept, excluded = universe.filter_markets(markets, limit=1)
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1


def test_universe_candidate_count_overfetches():
    from crypto_rsi_scanner import universe
    assert universe.candidate_count(20) > 20
    assert universe.candidate_count(500) <= 250


def test_universe_audit_keeps_exclusion_examples_after_limit():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import universe

    markets = [
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="thin", symbol="thin", name="Thin", total_volume=10.0),
    ]
    kept, excluded, audit = universe.filter_markets_with_audit(
        markets,
        limit=1,
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1
    assert excluded["low_liquidity"] == 1
    assert audit["kept_count"] == 1
    assert audit["excluded_count"] == 2
    assert {x["reason"] for x in audit["excluded_examples"]} == {"stable_like", "low_liquidity"}
    assert "UNIVERSE HYGIENE AUDIT" in universe.format_audit(audit)


def test_universe_audit_flags_suspicious_kept_rows():
    from crypto_rsi_scanner import universe

    audit = {
        "kept": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "rank": 1},
            {"id": "example-yield", "symbol": "yield", "name": "Example Yield", "rank": 99},
        ],
        "excluded_by_reason": {},
    }
    leaks = universe.suspicious_kept(audit)
    assert [x["symbol"] for x in leaks] == ["yield"]
    assert "suspicious kept" in universe.format_audit(audit)

    markets = [
        {
            "id": f"plain-{i}",
            "symbol": f"p{i}",
            "name": f"Plain {i}",
            "market_cap": 1_000_000_000,
            "total_volume": 20_000_000,
            "market_cap_rank": i + 1,
        }
        for i in range(90)
    ]
    markets.append({
        "id": "example-yield",
        "symbol": "yield",
        "name": "Example Yield",
        "market_cap": 900_000_000,
        "total_volume": 20_000_000,
        "market_cap_rank": 99,
    })
    _, _, full_audit = universe.filter_markets_with_audit(markets, limit=100)
    assert len(full_audit["kept"]) == 91
    assert universe.suspicious_kept(full_audit)[0]["symbol"] == "yield"


def test_scanner_fetch_universe_audit_uses_shared_filter():
    import asyncio
    from crypto_rsi_scanner import scanner

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get_top_markets(self, n):
            assert n >= 2
            return [
                _market(id="blockstack", symbol="stx", name="Stacks"),
                _market(id="usd1-wlfi", symbol="usd1", name="USD1"),
            ]

    orig = scanner.CoinGeckoClient
    scanner.CoinGeckoClient = FakeClient
    try:
        audit = asyncio.run(scanner.fetch_universe_audit(top_n=1))
    finally:
        scanner.CoinGeckoClient = orig

    assert audit["kept_count"] == 1
    assert audit["kept"][0]["symbol"] == "stx"
    assert audit["excluded_by_reason"] == {"stable_like": 1}


# --- telegram formatting -----------------------------------------------------

def _sample_signal(**over):
    base = {
        "symbol": "BNB", "flag": "OB", "severity": "WATCH", "conviction": 50,
        "tier": "DIGEST", "is_new": True, "rsi_daily": 72.7, "rsi_4h": 74.3,
        "rsi_weekly": 50.2, "rsi_z": 2.4, "rsi_delta": 20.0, "volume_ratio": 7.0,
        "btc_corr": 0.4, "divergence": None, "regime": "DOWNTREND",
        "regime_note": "reversal?", "line": "  BNB . c50 ...",
    }
    base.update(over)
    return base


def test_telegram_instant_has_html_and_emoji():
    s = _sample_signal(flag="OB", severity="EXTREME", conviction=93)
    out = formatting.telegram_html("instant", [s], "2026-05-31 19:59 UTC")
    assert "⚡" in out
    assert "<b>BNB</b>" in out
    assert "Conviction <b>93</b>/100" in out
    assert "RSI <b>73</b>" in out  # 72.7 -> 73


def test_telegram_digest_groups_by_direction():
    sigs = [
        _sample_signal(symbol="AAA", flag="OB"),
        _sample_signal(symbol="BBB", flag="OS", regime="DOWNTREND", regime_note="continuation"),
        _sample_signal(symbol="CCC", flag="PRE_OS", severity="APPROACHING", regime_note="continuation"),
    ]
    out = formatting.telegram_html("digest", sigs, "t")
    assert "Overbought" in out and "Oversold" in out and "Approaching" in out
    assert "<b>AAA</b>" in out and "<b>CCC</b>" in out


def test_telegram_escapes_special_chars():
    s = _sample_signal(symbol="A&B<X>")
    out = formatting.telegram_html("instant", [s], "t")
    assert "A&amp;B&lt;X&gt;" in out
    assert "<b>A&B<X></b>" not in out  # raw must not leak


def test_chart_link_escapes_quotes_in_href():
    s = _sample_signal(symbol='A&B<X>"')
    out = formatting.telegram_html("instant", [s], "t")
    assert 'symbol=A&amp;B&lt;X&gt;&quot;USDT' in out
    assert 'symbol=A&B<X>"USDT' not in out


def test_telegram_handles_missing_4h_nan():
    s = _sample_signal(rsi_4h=float("nan"))
    out = formatting.telegram_html("instant", [s], "t")
    assert "4H" not in out  # NaN timeframe omitted, no crash


def test_plain_text_uses_line():
    s = _sample_signal(line="  BNB . c50 stuff")
    out = formatting.plain_text("digest", [s], "t")
    assert "BNB . c50 stuff" in out


# --- signal outcome tracking -------------------------------------------------

def test_favorable_convention():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("OB", -5.0) == 1   # overbought + price fell = good
    assert favorable("OB", 5.0) == 0
    assert favorable("OS", 5.0) == 1    # oversold + price rose = good
    assert favorable("OS", -5.0) == 0
    assert favorable("PRE_OB", -2.0) == 1


def test_price_asof():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.date_range("2026-05-01", periods=10, freq="D", tz="UTC")
    closes = pd.Series(range(10), index=idx, dtype=float)
    # returns last value at/before the timestamp
    assert _price_asof(closes, datetime(2026, 5, 5, tzinfo=timezone.utc)) == 4.0
    assert _price_asof(pd.Series(dtype=float), datetime(2026, 5, 5, tzinfo=timezone.utc)) is None
    # before the series start -> None
    assert _price_asof(closes, datetime(2026, 4, 1, tzinfo=timezone.utc)) is None


def test_price_asof_mixed_time_units():
    # Regression: pandas 3 Series.asof() raises "Cannot losslessly convert
    # units" when index resolution (ms, from unit='ms' parsing) != Timestamp
    # resolution (us, from an isoformat string with microseconds).
    from datetime import datetime
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.to_datetime([1714521600000 + i * 86400000 for i in range(10)],
                         unit="ms", utc=True)  # ms-resolution index
    closes = pd.Series(range(10), index=idx, dtype=float)
    ts = datetime.fromisoformat("2026-05-02T07:08:23.760073+00:00")  # us-resolution
    val = _price_asof(closes, ts)  # must not raise
    assert val is not None and val >= 0


def test_outcome_evaluation_records_matured():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import outcomes

    db = Path(tempfile.mkdtemp()) / "o.db"
    st = Storage(db)
    now = datetime(2026, 5, 31, tzinfo=timezone.utc)
    run_at = now - timedelta(days=10)
    st.conn.execute(
        "INSERT INTO signals (symbol, coin_id, flag, severity, price, is_new, run_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("AAA", "aaa", "OB", "ALERT", 100.0, 1, run_at.isoformat()),
    )
    st.conn.commit()

    # price 100 at entry, then declines 1/day -> OB fade is favorable
    idx = pd.date_range(end=now, periods=16, freq="D", tz="UTC")
    vals = [100.0 if (d - pd.Timestamp(run_at)).days <= 0
            else 100.0 - (d - pd.Timestamp(run_at)).days for d in idx]
    closes = pd.Series(vals, index=idx)

    n = outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now)
    assert n == 3  # 1/3/7 matured; 14d not (only 10 days elapsed)
    recs = st.conn.execute(
        "SELECT horizon_days, ret_pct, favorable FROM outcomes ORDER BY horizon_days"
    ).fetchall()
    assert [r["horizon_days"] for r in recs] == [1, 3, 7]
    assert all(r["favorable"] == 1 for r in recs)
    assert abs(recs[-1]["ret_pct"] - (-7.0)) < 1e-6  # 93/100 - 1
    # idempotent: re-running records nothing new
    assert outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now) == 0
    st.close()


def test_build_report_empty_and_populated():
    from crypto_rsi_scanner.outcomes import build_report
    assert "No matured" in build_report([])

    rows = [
        {"horizon_days": 7, "ret_pct": -3.0, "favorable": 1, "flag": "OB",
         "regime": "DOWNTREND", "regime_note": "reversal?", "conviction": 80,
         "symbol": "A", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "neutral",
         "state_json": '{"volatility":{"state":"high"},"breadth":{"state":"washout"}}'},
        {"horizon_days": 7, "ret_pct": 2.0, "favorable": 0, "flag": "OB",
         "regime": "UPTREND", "regime_note": "continuation", "conviction": 55,
         "symbol": "B", "severity": "WATCH", "market_regime": "DOWNTREND",
         "market_aligned": "favorable"},
        {"horizon_days": 7, "ret_pct": 4.0, "favorable": 1, "flag": "OS",
         "regime": "DOWNTREND", "regime_note": "continuation", "conviction": 70,
         "symbol": "C", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "adverse"},
    ]
    out = build_report(rows, primary_horizon=7)
    assert "RSI SIGNAL OUTCOMES" in out
    assert "By setup" in out and "By conviction" in out
    assert "By actionable/control" in out
    assert "By market alignment" in out
    assert "By state cohort" in out and "washout" in out


# --- subscriber management ---------------------------------------------------

def _fresh_storage():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    return Storage(Path(tempfile.mkdtemp()) / "subs.db")


def test_subscribe_add_and_dedup():
    st = _fresh_storage()
    assert st.subscribe("111", "alice") is True       # new
    assert st.subscribe("111", "alice") is False      # already active -> no-op
    assert st.active_subscribers() == ["111"]
    st.close()


def test_unsubscribe_and_resubscribe():
    st = _fresh_storage()
    st.subscribe("111", "alice")
    st.subscribe("222", "bob")
    assert st.unsubscribe("111") is True
    assert st.unsubscribe("111") is False             # already inactive
    assert st.active_subscribers() == ["222"]
    assert st.subscribe("111", None) is True          # reactivated
    assert set(st.active_subscribers()) == {"111", "222"}
    st.close()


def test_seed_from_config(monkeypatch=None):
    from crypto_rsi_scanner import telegram, config
    st = _fresh_storage()
    orig = config.TELEGRAM_CHAT_IDS
    config.TELEGRAM_CHAT_IDS = ["999", "888"]
    try:
        telegram.seed_subscribers_from_config(st)
        assert set(st.active_subscribers()) == {"999", "888"}
    finally:
        config.TELEGRAM_CHAT_IDS = orig
        st.close()


# --- richer formatting (Part A) ----------------------------------------------

def test_sparkline_basic():
    assert formatting.sparkline([1, 2, 3, 4, 5, 6, 7, 8]) == "▁▂▃▄▅▆▇█"
    assert formatting.sparkline([]) == ""
    assert formatting.sparkline([5]) == ""
    assert set(formatting.sparkline([5, 5, 5])) == {"▁"}  # flat


def test_price_formatting():
    assert formatting._fmt_price(72000) == "$72,000"
    assert formatting._fmt_price(721.09) == "$721.09"
    assert formatting._fmt_price(0.0034) == "$0.0034"


def test_instant_card_has_rich_fields():
    s = _sample_signal(price=721.09, pct_24h=8.2, pct_7d=-3.1, ath_pct=-8.5,
                       sparkline=[700, 710, 690, 720])
    out = formatting.telegram_html("instant", [s], "t")
    assert "$721.09" in out
    assert "+8.2% 24h" in out
    assert "below ATH" in out
    assert "tradingview.com" in out  # chart link
    assert "<code>" in out          # sparkline


def test_digest_line_shows_24h():
    s = _sample_signal(pct_24h=-5.0)
    out = formatting.telegram_html("digest", [s], "t")
    assert "-5%" in out


# --- inline hit-rates (Part B) ------------------------------------------------

def test_track_records_and_text():
    from crypto_rsi_scanner import outcomes
    rows = []
    # 6 OB-in-downtrend, 5 favorable -> 83%
    for i in range(6):
        rows.append({"horizon_days": 7, "ret_pct": -4.0 if i < 5 else 2.0,
                     "favorable": 1 if i < 5 else 0, "flag": "OB",
                     "regime": "DOWNTREND", "regime_note": "reversal?",
                     "conviction": 70, "symbol": f"X{i}", "severity": "ALERT"})
    stats = outcomes.track_records(rows, 7)
    assert stats["mean_reversion"]["n"] == 6   # OB-in-downtrend -> mean_reversion
    txt = outcomes.track_record_text("mean_reversion", stats, 7)
    assert "5/6" in txt and "mean reversion" in txt


def test_track_record_insufficient_samples():
    from crypto_rsi_scanner import outcomes
    rows = [{"horizon_days": 7, "ret_pct": -4.0, "favorable": 1, "flag": "OB",
             "regime": "RANGE", "regime_note": "", "conviction": 50,
             "symbol": "A", "severity": "WATCH"}]
    stats = outcomes.track_records(rows, 7)  # only 1 sample < MIN
    assert stats == {}
    assert outcomes.track_record_text("mean_reversion", stats, 7) == ""


# --- heartbeat (Part D) -------------------------------------------------------

def test_heartbeat_health_checks(monkeypatch=None):
    from crypto_rsi_scanner import heartbeat, config
    sent = []
    orig = heartbeat.send_telegram
    heartbeat.send_telegram = lambda *a, **k: sent.append(a) or True
    try:
        assert heartbeat.check_health({"requested": 90, "fetched": 88, "analyzed": 80}) is True
        assert not sent
        # degraded: >30% failed
        assert heartbeat.check_health({"requested": 90, "fetched": 50, "analyzed": 40}) is False
        # no data
        assert heartbeat.check_health({"requested": 90, "fetched": 0, "analyzed": 0}) is False
        assert len(sent) == 2
    finally:
        heartbeat.send_telegram = orig


# --- bot commands (Part C) ----------------------------------------------------

def test_snapshot_save_load():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    sigs = [_sample_signal(symbol="AAA", flag="OB", conviction=80),
            _sample_signal(symbol="BBB", flag="OS", conviction=40)]
    telegram.save_latest_snapshot(st, sigs)
    loaded = telegram._load_snapshot(st)
    assert {s["symbol"] for s in loaded} == {"AAA", "BBB"}
    st.close()


def test_cmd_top_and_detail():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    telegram.save_latest_snapshot(st, [
        _sample_signal(symbol="AAA", flag="OB", conviction=80),
        _sample_signal(symbol="BBB", flag="OS", conviction=40),
    ])
    top = telegram._cmd_top(st)
    assert "AAA" in top and "BBB" in top
    detail = telegram._cmd_detail(st, "aaa")
    assert "AAA" in detail
    assert "isn't on the current watch-list" in telegram._cmd_detail(st, "ZZZ")
    st.close()


# --- self-tuning conviction --------------------------------------------------

def test_conviction_adjustment_insufficient_samples():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # below min_samples -> unchanged
    assert conviction_adjustment(50, 0.9, 3, min_samples=8) == 50
    assert conviction_adjustment(50, None, 100, min_samples=8) == 50


def test_conviction_adjustment_direction():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # high hit rate with ample samples -> nudges up; low -> nudges down
    up = conviction_adjustment(50, 0.9, 40, min_samples=8, max_swing=15)
    down = conviction_adjustment(50, 0.1, 40, min_samples=8, max_swing=15)
    assert up > 50 and down < 50
    # 50% hit rate -> no change
    assert conviction_adjustment(50, 0.5, 40, min_samples=8) == 50


def test_conviction_adjustment_bounded():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # swing capped; never exceeds max_swing, never leaves 0..100
    assert conviction_adjustment(95, 1.0, 100, max_swing=15) <= 100
    assert conviction_adjustment(5, 0.0, 100, max_swing=15) >= 0
    hi = conviction_adjustment(50, 1.0, 1000, min_samples=8, max_swing=15)
    assert hi - 50 <= 15


def test_conviction_adjustment_confidence_scaling():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # more samples -> larger (or equal) move toward the empirical signal
    few = conviction_adjustment(50, 0.9, 8, min_samples=8, max_swing=15)
    many = conviction_adjustment(50, 0.9, 80, min_samples=8, max_swing=15)
    assert (many - 50) >= (few - 50) >= 0


# --- macro context -----------------------------------------------------------

def test_macro_header_assembles():
    from crypto_rsi_scanner import macro
    m = {
        "n_ob": 17, "n_os": 3, "d_ob": 6, "d_os": -1,
        "fng": {"value": 22, "label": "Fear"},
        "btc_regime": "DOWNTREND",
        "glob": {"btc_dominance": 54.3, "mcap_change_24h": -2.8},
    }
    line = macro.macro_header(m)
    assert "F&amp;G 22 (Fear)" in line
    assert "Downtrend" in line
    assert "breadth 17🔴" in line and "3🟢" in line
    assert "-2.8% 24h" in line


def test_macro_header_empty_safe():
    from crypto_rsi_scanner import macro
    # missing pieces are omitted, never crash; breadth always present
    line = macro.macro_header({"n_ob": 0, "n_os": 0})
    assert "breadth" in line
    assert macro.macro_header(None) == ""


def test_macro_digest_includes_header():
    s = _sample_signal()
    out = formatting.telegram_html("digest", [s], "t", macro_line="🌍 test-macro")
    assert "test-macro" in out


def test_alert_render_smoke_suite():
    from crypto_rsi_scanner import alert_smoke
    results = alert_smoke.run_smoke()
    names = {r.name for r in results}
    assert names == {"telegram_instant", "telegram_digest", "plain_instant", "plain_digest"}
    assert all(r.chars > 0 for r in results)


# --- backtester ---------------------------------------------------------------

def test_backtest_edge_zero_when_signal_matches_base():
    # The anti-tautology guarantee: a setup that confirms 100% in a regime that
    # *always* moves that way has ZERO edge — it's just "trends trend".
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-5.0, -4.0, -6.0, -3.0]}  # P(down)=100%
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -5.0, "fav": 1, "conv": 60} for _ in range(4)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0 and r["base"] == 100.0
    assert abs(r["edge"]) < 1e-9


def test_backtest_positive_edge_when_signal_beats_base():
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-2.0, -1.0, 2.0, 1.0]}  # P(down)=50%, mean 0
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -3.0, "fav": 1, "conv": 60} for _ in range(5)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0
    assert abs(r["base"] - 50.0) < 1e-9
    assert abs(r["edge"] - 50.0) < 1e-9
    assert r["med_excess"] > 0  # fell more than the regime's average day


def test_backtest_conditional_table_buckets_by_feature():
    # low-vol oversold-in-downtrend bounces (+ret); high-vol continues down (-ret).
    # The slice should show that, with edge measured vs same-vol-bucket base days.
    from crypto_rsi_scanner import backtest
    signals = []
    for v, r in [(0.1, +3.0)] * 10 + [(0.5, -1.0)] * 10 + [(0.9, -6.0)] * 10:
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "h": 3, "ret": r, "fav": 1 if r < 0 else 0, "conv": 50,
                        "vol": v, "mom": -10.0})
    # base: each vol level falls ~50% of the time, regardless of vol
    cond_base = {("DOWNTREND", 3): [(v, -10.0, r)
                 for v in (0.1, 0.5, 0.9) for r in (-1.0, 1.0)] * 20}
    res = backtest.conditional_table(signals, cond_base, "breakdown_risk",
                                     "DOWNTREND", "down", 3, "vol")
    assert res is not None
    (q1, q2), rows = res
    assert rows[0]["sig"] < 20    # low vol -> rarely falls (bounces)
    assert rows[2]["sig"] > 80    # high vol -> keeps falling
    assert rows[2]["edge"] > 20   # and beats the same-vol-bucket base (~50%)


def test_backtest_market_regime_series():
    from crypto_rsi_scanner import backtest
    idx_up = pd.date_range("2020-01-01", periods=300, freq="D", tz="UTC")
    up = pd.Series(np.linspace(10, 110, 300), index=idx_up)
    down = pd.Series(np.linspace(110, 10, 300), index=idx_up)
    assert backtest.market_regime_series(up).iloc[-1] == "BULL"
    assert backtest.market_regime_series(down).iloc[-1] == "BEAR"
    assert backtest.market_regime_series(up).iloc[0] == "NA"  # 200d warm-up


def test_backtest_summarize_market_splits_regime():
    # mean_reversion confirms in BULL, fails in BEAR — must not blend away.
    from crypto_rsi_scanner import backtest
    signals = []
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BULL", "h": 7, "ret": 5.0, "fav": 1, "conv": 50})
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BEAR", "h": 7, "ret": -5.0, "fav": 0, "conv": 50})
    mkt_base = {("RANGE", "BULL", 7): [1.0, 1.0, -1.0, 1.0],   # base P(up)=75%
                ("RANGE", "BEAR", 7): [-1.0, -1.0, 1.0, -1.0]}  # base P(up)=25%
    by = {(r["setup"], r["mkt"]): r for r in backtest.summarize_market(signals, mkt_base, 7)}
    assert by[("mean_reversion", "BULL")]["conf"] == 100.0
    assert by[("mean_reversion", "BEAR")]["conf"] == 0.0
    assert abs(by[("mean_reversion", "BULL")]["edge"] - 25.0) < 1e-9   # 100 - 75
    assert abs(by[("mean_reversion", "BEAR")]["edge"] + 25.0) < 1e-9   # 0 - 25


def test_backtest_state_slices_compare_same_state_base():
    from crypto_rsi_scanner import backtest

    signals = []
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": 4.0, "fav": 1, "conv": 60,
                        "vol_state": "low_compressed", "breadth_state": "neutral",
                        "rs_bucket": "high", "liquidity_bucket": "high",
                        "knife_bucket": "low"})
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": -4.0, "fav": 0, "conv": 60,
                        "vol_state": "crisis", "breadth_state": "breadth_collapse",
                        "rs_bucket": "low", "liquidity_bucket": "low",
                        "knife_bucket": "high"})

    state_base = {
        ("UPTREND", "vol_state", "low_compressed", 7): [1.0, -1.0] * 20,
        ("UPTREND", "vol_state", "crisis", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "neutral", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "breadth_collapse", 7): [1.0, -1.0] * 20,
    }
    rows = backtest.summarize_state_slices(signals, state_base, 7, min_n=8)
    by = {(r["feature"], r["bucket"]): r for r in rows}
    assert by[("vol_state", "low_compressed")]["edge"] == 50.0
    assert by[("vol_state", "crisis")]["edge"] == -50.0
    assert by[("knife_bucket", "high")]["med_dir"] < 0
    text = backtest.format_state_slices(signals, state_base, 7, min_n=8)
    assert "State-conditioned edge slices" in text
    assert "falling-knife bucket" in text


def test_backtest_build_state_frames_contains_shadow_labels():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    btc = pd.DataFrame({
        "close": pd.Series(np.linspace(100, 180, len(idx)), index=idx),
        "volume": pd.Series(1_000.0, index=idx),
    })
    weak = pd.DataFrame({
        "close": pd.Series(np.linspace(80, 30, len(idx)), index=idx),
        "volume": pd.Series(np.linspace(20_000, 40_000, len(idx)), index=idx),
    })
    frames = {"BTC": btc, "WEAK": weak}
    state = backtest.build_state_frames(frames)
    assert set(state) == {"BTC", "WEAK"}
    cols = set(state["WEAK"].columns)
    assert {"vol_state", "breadth_state", "rs_bucket", "liquidity_bucket",
            "falling_knife_score", "knife_bucket"}.issubset(cols)
    assert state["WEAK"]["rs_bucket"].iloc[-1] in {"low", "mid", "high"}


def test_backtest_builds_registry_prior_calibration():
    from crypto_rsi_scanner import backtest, signal_registry as reg

    signals = []
    # Favorable dip-buy in BULL: 100% confirms vs 50% base -> prior should rise.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BULL", "h": 7, "ret": 4.0, "fav": 1, "conv": 60})
    # Adverse dip-buy in BEAR: 0% confirms vs 50% base -> prior should fall.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 0, "conv": 60})
    # Breakdown risk can have apparent edge in evidence, but it must stay context-only.
    for _ in range(16):
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 1, "conv": 40})

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 20,
        ("UPTREND", "BEAR", 7): [1.0, -1.0] * 20,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 20,
    }

    payload = backtest.build_registry_prior_export(
        signals, mkt_base, n_coins=3, days=365, source="unit-test", min_samples=8
    )
    priors = payload["setups"]["dip_buy"]["edge_priors"]
    defaults = reg.SETUPS["dip_buy"].edge_priors
    assert priors["favorable"] > defaults["favorable"]
    assert priors["adverse"] < defaults["adverse"]
    assert payload["setups"]["breakdown_risk"]["edge_priors"]["no_edge"] == (
        reg.SETUPS["breakdown_risk"].edge_priors["no_edge"]
    )
    assert "context_only_no_edge_not_auto_promoted" in payload["setups"]["breakdown_risk"]["notes"]


def test_backtest_cost_and_walk_forward_reports():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    signals = []
    for i, ts in enumerate(idx):
        setup = "dip_buy" if i % 2 == 0 else "breakdown_risk"
        exp = "up" if setup == "dip_buy" else "down"
        ret = 2.0 if setup == "dip_buy" else -1.0
        signals.append({
            "setup": setup,
            "exp": exp,
            "h": 7,
            "ret": ret,
            "fav": 1,
            "conv": 70 - i,
            "mkt": "BULL" if setup == "dip_buy" else "BEAR",
            "ts": ts,
            "symbol": f"T{i}",
            "liquidity_bucket": "low" if i == 0 else "high",
        })

    costs = backtest.format_cost_report(
        signals, fee_bps=10, slippage_bps=20, max_trades_per_day=1
    )
    assert "Cost-aware backtest book" in costs
    assert "actionable" in costs
    assert "dip_buy" in costs

    wf = backtest.format_walk_forward(signals, folds=4)
    assert "Walk-forward setup stability" in wf
    assert "Train = all earlier folds" in wf


def test_backtest_pit_membership():
    # Point-in-time top-2: a coin that's big early then shrinks should be a
    # member only while it ranks in the top-2 by mcap on each date.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=4, freq="D", tz="UTC")
    histories = {
        "big":   pd.DataFrame({"mcap": [100, 100, 100, 100]}, index=idx),
        "faller": pd.DataFrame({"mcap": [90, 90, 10, 10]}, index=idx),   # drops out
        "riser": pd.DataFrame({"mcap": [5, 5, 80, 80]}, index=idx),      # climbs in
    }
    member = backtest.build_pit_membership(histories, top_n=2)
    assert list(member["big"]) == [True, True, True, True]
    assert list(member["faller"]) == [True, True, False, False]
    assert list(member["riser"]) == [False, False, True, True]


def test_backtest_volume_membership_rolling_rank():
    # Membership = top-N by TRAILING mean dollar volume: needs `window` days of
    # history to enter (no lookahead), and rank flips follow the trailing mean.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    frames = {
        "BIG": pd.DataFrame({"quote_volume": [100.0] * 6}, index=idx),
        "FADE": pd.DataFrame({"quote_volume": [90, 90, 1, 1, 1, 1]}, index=idx),
        "RISE": pd.DataFrame({"quote_volume": [1, 1, 95, 95, 95, 95]}, index=idx),
    }
    m = backtest.build_volume_membership(frames, top_n=2, window=2)
    # day 0: trailing-2 mean undefined for everyone -> nobody is a member
    assert not m.iloc[0].any()
    assert list(m["BIG"])[1:] == [True] * 5
    # FADE trailing means: 90, 45.5, 1, 1, 1 — loses rank 2 to RISE (48) on day 2
    assert list(m["FADE"])[1:] == [True, False, False, False, False]
    # RISE trailing means: 1, 48, 95, 95, 95 — enters as soon as its ramp shows up
    assert list(m["RISE"])[1:] == [False, True, True, True, True]


def test_backtest_volume_membership_rejects_invalid_args():
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    frames = {"AAA": pd.DataFrame({"quote_volume": [1.0, 2.0, 3.0]}, index=idx)}

    try:
        backtest.build_volume_membership(frames, top_n=0, window=2)
    except ValueError as e:
        assert "top_n" in str(e)
    else:
        raise AssertionError("top_n=0 should fail")

    try:
        backtest.build_volume_membership(frames, top_n=1, window=0)
    except ValueError as e:
        assert "window" in str(e)
    else:
        raise AssertionError("window=0 should fail")


def test_backtest_main_rejects_invalid_cli_args():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    for argv in (
        ["--pit-volume", "--volume-window", "0"],
        ["--top-n", "0"],
        ["--compare-triggers", "--pit"],
    ):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                backtest.main(argv)
            except SystemExit as e:
                assert e.code == 2
            else:
                raise AssertionError(f"{argv} should fail")


def test_backtest_main_compare_triggers_uses_volume_pit():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    calls = {}
    orig_pit_triggers = backtest.run_pit_volume_triggers
    orig_triggers = backtest.run_triggers
    orig_format = backtest.format_trigger_comparison

    def fake_pit_triggers(top_n, days, **kwargs):
        calls["pit"] = {
            "top_n": top_n,
            "days": days,
            "cache_dir": kwargs.get("cache_dir"),
            "refresh_cache": kwargs.get("refresh_cache"),
            "volume_window": kwargs.get("volume_window"),
        }
        return {"cross_into": ([], {}, {}, {}, {}), "confirm": ([], {}, {}, {}, {})}, 2

    def fail_default_triggers(*args, **kwargs):
        raise AssertionError("default trigger path should not run")

    def fake_format(results):
        assert set(results) == {"cross_into", "confirm"}
        return "pit-volume comparison"

    backtest.run_pit_volume_triggers = fake_pit_triggers
    backtest.run_triggers = fail_default_triggers
    backtest.format_trigger_comparison = fake_format
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            backtest.main([
                "--compare-triggers",
                "--pit-volume",
                "--top-n", "7",
                "--days", "30",
                "--volume-window", "3",
                "--no-pit-cache",
            ])
        assert "pit-volume comparison" in out.getvalue()
        assert calls["pit"] == {
            "top_n": 7,
            "days": 30,
            "cache_dir": None,
            "refresh_cache": False,
            "volume_window": 3,
        }
    finally:
        backtest.run_pit_volume_triggers = orig_pit_triggers
        backtest.run_triggers = orig_triggers
        backtest.format_trigger_comparison = orig_format


def test_backtest_fetch_volume_pit_frames_cache_hit_no_sleep_and_closes_session():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    cache = Path(tempfile.mkdtemp())
    periods = backtest._START + max(backtest.HORIZONS) + 1
    rows = [
        [
            1735689600000 + i * 86_400_000,
            "1", "2", "0.5", str(100 + i), "10", 0, "15", 0, 0, 0, 0,
        ]
        for i in range(periods)
    ]
    for symbol in ("BTCUSDT", "ETHUSDT"):
        backtest._write_binance_klines_cache(cache, symbol, periods, rows)

    class FakeSession:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    fake_session = FakeSession()
    sleeps = []
    orig_session = backtest.requests.Session
    orig_pool = backtest.binance_usdt_pool
    orig_sleep = backtest.time.sleep
    backtest.requests.Session = lambda: fake_session
    backtest.binance_usdt_pool = lambda session: ["BTC", "ETH"]
    backtest.time.sleep = lambda seconds: sleeps.append(seconds)
    try:
        frames = backtest._fetch_volume_pit_frames(periods, cache_dir=cache)
        assert set(frames) == {"BTC", "ETH"}
        assert sleeps == []
        assert fake_session.closed is True
    finally:
        backtest.requests.Session = orig_session
        backtest.binance_usdt_pool = orig_pool
        backtest.time.sleep = orig_sleep


def test_backtest_filter_usdt_bases_hygiene():
    from crypto_rsi_scanner import backtest
    syms = [
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
        {"baseAsset": "JUP", "quoteAsset": "USDT", "status": "TRADING"},   # real coin, UP suffix
        {"baseAsset": "USDC", "quoteAsset": "USDT", "status": "TRADING"},  # stable
        {"baseAsset": "EUR", "quoteAsset": "USDT", "status": "TRADING"},   # fiat
        {"baseAsset": "WBTC", "quoteAsset": "USDT", "status": "TRADING"},  # wrapped
        {"baseAsset": "OLD", "quoteAsset": "USDT", "status": "BREAK"},     # not trading
        {"baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},    # wrong quote
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},   # dup
    ]
    assert backtest._filter_usdt_bases(syms) == ["BTC", "JUP"]


def test_backtest_klines_rows_to_frame_quote_volume():
    from crypto_rsi_scanner import backtest
    # Binance kline array: [open_ms, open, high, low, close, base_vol, close_ms, quote_vol, ...]
    rows = [
        [1735689600000, "1", "2", "0.5", "1.5", "1000", 0, "1500.5", 0, 0, 0, 0],
        [1735776000000, "1.5", "2", "1", "1.8", "2000", 0, "3600.25", 0, 0, 0, 0],
    ]
    df = backtest._klines_rows_to_frame(rows)
    assert list(df["close"]) == [1.5, 1.8]
    assert list(df["volume"]) == [1000.0, 2000.0]
    assert list(df["quote_volume"]) == [1500.5, 3600.25]
    assert df.index.tz is not None


def test_backtest_binance_klines_cache_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest
    cache = Path(tempfile.mkdtemp())
    rows = [[1735689600000, "1", "2", "0.5", "1.5", "10", 0, "15", 0, 0, 0, 0]]
    backtest._write_binance_klines_cache(cache, "AAAUSDT", 30, rows)
    # cache hit must not touch the network: session=None would fail otherwise
    df = backtest.fetch_klines("AAAUSDT", 30, session=None, cache_dir=cache)
    assert df is not None and list(df["quote_volume"]) == [15.0]
    # no cache entry + no session -> None (still no network)
    assert backtest.fetch_klines("BBBUSDT", 30, session=None, cache_dir=cache) is None


def test_backtest_pit_history_cache_roundtrip():
    import asyncio
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    data = {
        "prices": [[int(ts.timestamp() * 1000), float(i + 1)] for i, ts in enumerate(idx)],
        "market_caps": [[int(ts.timestamp() * 1000), float(1_000_000 + i)] for i, ts in enumerate(idx)],
        "total_volumes": [[int(ts.timestamp() * 1000), float(10_000 + i)] for i, ts in enumerate(idx)],
    }
    cache_dir = Path(tempfile.mkdtemp())
    backtest._write_cg_chart_cache(cache_dir, "bitcoin/test", 365, data)

    path = backtest._cg_chart_cache_path(cache_dir, "bitcoin/test", 365)
    assert path.name == "bitcoin_test-365d.json"
    assert backtest._load_cg_chart_cache(cache_dir, "bitcoin/test", 365)["prices"][0][1] == 1.0

    histories = asyncio.run(backtest._fetch_cg_histories(
        ["bitcoin/test"], 365, cache_dir=cache_dir
    ))
    assert set(histories) == {"bitcoin/test"}
    assert len(histories["bitcoin/test"]) == len(idx)
    assert {"close", "mcap", "volume"}.issubset(histories["bitcoin/test"].columns)


def test_backtest_klines_fixture_loader_and_symbols():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.backtest import fixture_symbols, load_klines_fixture

    root = Path(tempfile.mkdtemp()) / "fixture"
    klines = root / "klines"
    klines.mkdir(parents=True)
    (klines / "BTCUSDT.csv").write_text(
        "date,close,volume\n"
        "2026-01-02T00:00:00Z,101,1000\n"
        "2026-01-01T00:00:00Z,100,900\n"
        "2026-01-03T00:00:00Z,103,1100\n"
    )
    (klines / "ETHUSDT.csv").write_text(
        "date,close,volume\n"
        "2026-01-01T00:00:00Z,10,50\n"
    )

    assert fixture_symbols(root) == ["BTC", "ETH"]
    df = load_klines_fixture("BTCUSDT", 2, root)
    assert df is not None
    assert list(df["close"]) == [101, 103]
    assert str(df.index.tz) == "UTC"


def test_backtest_walk_respects_membership():
    # With a membership mask all-False, no signals and no base days accrue.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(2)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    sig: list = []
    base: dict = defaultdict(list)
    backtest.walk_coin(df, sig, base, member=np.zeros(n, dtype=bool))
    assert sig == [] and not base


def test_backtest_trigger_modes_differ():
    # An oscillator drives RSI in and out of OB/OS; cross_into and confirm enter
    # on opposite edges of the zone, so their graded outcomes must differ.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    n = 500
    close = pd.Series(
        100 + 20 * np.sin(np.arange(n) / 9.0),
        index=pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    out = {}
    for trig in ("cross_into", "confirm"):
        sig: list = []
        backtest.walk_coin(df, sig, defaultdict(list), trigger=trig)
        out[trig] = sig
    assert out["cross_into"] and out["confirm"]
    a = sorted(round(s["ret"], 3) for s in out["cross_into"] if s["h"] == 7)
    b = sorted(round(s["ret"], 3) for s in out["confirm"] if s["h"] == 7)
    assert a != b   # different entry timing -> different outcomes


def test_backtest_walk_generates_signals_offline():
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(1)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,  # noisy downtrend
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    signals: list = []
    regime_base: dict = defaultdict(list)
    backtest.walk_coin(df, signals, regime_base)
    assert signals, "expected crossing signals in a long downtrend"
    assert any(s["setup"] == "breakdown_risk" for s in signals)
    assert regime_base
    assert all(s["fav"] in (0, 1) and s["h"] in backtest.HORIZONS for s in signals)


# --- paper-trade scoreboard --------------------------------------------------

def test_paper_is_actionable():
    from crypto_rsi_scanner.paper import _is_actionable
    assert _is_actionable({"setup_type": "dip_buy", "market_aligned": "favorable"})
    assert _is_actionable({"setup_type": "mean_reversion", "market_aligned": "neutral"})
    assert not _is_actionable({"setup_type": "mean_reversion", "market_aligned": "adverse"})
    assert not _is_actionable({"setup_type": "breakdown_risk", "market_aligned": "neutral"})


def test_paper_open_close_pnl_sign():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    signals = [
        {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "dip_buy", "expected_dir": "up", "market_regime": "UPTREND",
         "market_aligned": "favorable", "conviction": 70, "state_json": '{"version":1}'},
        {"symbol": "BBB", "coin_id": "bbb", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "breakdown_risk", "expected_dir": "down", "market_regime": "DOWNTREND",
         "market_aligned": "adverse", "conviction": 40},
    ]
    assert paper.update(st, signals, {}, now=now0) == (2, 0)
    assert paper.update(st, signals, {}, now=now0) == (0, 0)   # one open per coin

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + 10.0 * i / h for i in range(len(idx))], index=idx)  # +10% by +h
    later = now0 + timedelta(days=h + 1)
    assert paper.update(st, [], {"aaa": closes, "bbb": closes}, now=later) == (0, 2)

    rows = {r["symbol"]: dict(r) for r in st.closed_paper_trades()}
    assert rows["AAA"]["direction"] == "long" and rows["AAA"]["ret_pct"] > 5   # rose, long wins
    assert rows["AAA"]["state_json"] == '{"version":1}'
    assert rows["BBB"]["direction"] == "short" and rows["BBB"]["ret_pct"] < -5  # rose, short loses
    st.close()


def test_paper_closes_before_opening_same_coin_new_crossing():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "roll.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
           "setup_type": "dip_buy", "expected_dir": "up",
           "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 70}
    assert paper.update(st, [sig], {}, now=now0) == (1, 0)

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + i for i in range(len(idx))], index=idx)
    later = now0 + timedelta(days=h + 1)
    new_sig = {**sig, "price": 120.0, "conviction": 75}
    assert paper.update(st, [new_sig], {"aaa": closes}, now=later) == (1, 1)
    assert len(st.closed_paper_trades()) == 1
    open_rows = [dict(r) for r in st.open_paper_trades()]
    assert len(open_rows) == 1
    assert open_rows[0]["entry_price"] == 120.0
    st.close()


def test_paper_not_closed_before_maturity():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p2.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = [{"symbol": "AAA", "coin_id": "aaa", "flag": "OB", "is_new": True, "price": 50.0,
            "setup_type": "trend_continuation", "expected_dir": "up",
            "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 60}]
    paper.update(st, sig, {}, now=now0)
    idx = pd.date_range(now0, periods=config.PAPER_HOLD_DAYS + 1, freq="D", tz="UTC")
    closes = pd.Series(55.0, index=idx)
    # only 1 day elapsed -> still open
    early = now0 + timedelta(days=1)
    assert paper.update(st, [], {"aaa": closes}, now=early) == (0, 0)
    assert len(st.open_paper_trades()) == 1
    st.close()


def test_paper_report_empty_and_populated():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper

    st = Storage(Path(tempfile.mkdtemp()) / "p3.db")
    assert "No paper trades yet" in paper.report(st)
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, state_json, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('AAA','aaa','dip_buy','UPTREND','favorable',"
        "'{\"volatility\":{\"state\":\"high\"},\"breadth\":{\"state\":\"washout\"},"
        "\"relative_strength\":{\"bucket\":\"low\"},\"liquidity\":{\"bucket\":\"mid\"},"
        "\"risk\":{\"falling_knife_score\":80}}',"
        "'long',70,100,'2026-05-01',7,"
        "110,'2026-05-08',10.0,'closed')"
    )
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('BBB','bbb','breakdown_risk','DOWNTREND','adverse','short',40,100,'2026-05-01',7,"
        "108,'2026-05-08',-8.0,'closed')"
    )
    st.conn.commit()
    out = paper.report(st)
    assert "PAPER-TRADE SCOREBOARD" in out
    assert "actionable" in out and "control" in out
    assert "By conviction bucket" in out
    cohorts = paper.report(st, cohorts=True)
    assert "By state cohort" in cohorts
    assert "volatility" in cohorts and "high" in cohorts
    assert "falling-knife" in cohorts
    data = paper.summary(st)
    assert data["closed_count"] == 2
    assert data["books"]["actionable"]["n"] == 1
    assert data["by_conviction_bucket"]["65-79"]["n"] == 1
    assert data["by_conviction_bucket"]["0-49"]["n"] == 1
    assert data["by_state"]["volatility"]["high"]["n"] == 1
    st.close()


def test_refresh_paper_closes_without_scan_or_alerts():
    import contextlib
    import io
    from crypto_rsi_scanner import scanner

    calls = {}

    class FakeStorage:
        def __init__(self, path):
            self.path = path
            calls["storage_path"] = path

        def open_paper_coin_ids(self):
            return ["aaa", "bbb"]

        def close(self):
            calls["closed_storage"] = True

    async def fake_fetch(ids):
        calls["fetch_ids"] = list(ids)
        return {"aaa": pd.Series([1.0]), "bbb": pd.Series([2.0])}

    def fake_update(storage, signals, closes_map):
        calls["update"] = (storage, list(signals), sorted(closes_map))
        return 0, 2

    def fake_report(storage, cohorts=False):
        calls["cohorts"] = cohorts
        return "paper report"

    orig_storage = scanner.Storage
    orig_fetch = scanner._fetch_extra_daily_closes
    orig_update = scanner.paper.update
    orig_report = scanner.paper.report
    scanner.Storage = FakeStorage
    scanner._fetch_extra_daily_closes = fake_fetch
    scanner.paper.update = fake_update
    scanner.paper.report = fake_report
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.refresh_paper(cohorts=True)
        assert "closed 2 trade(s)" in out.getvalue()
        assert "paper report" in out.getvalue()
        assert calls["fetch_ids"] == ["aaa", "bbb"]
        assert calls["update"][1] == []
        assert calls["update"][2] == ["aaa", "bbb"]
        assert calls["cohorts"] is True
        assert calls["closed_storage"] is True
    finally:
        scanner.Storage = orig_storage
        scanner._fetch_extra_daily_closes = orig_fetch
        scanner.paper.update = orig_update
        scanner.paper.report = orig_report


# --- regression: NaN enrichment from the DataFrame self-tune path -------------

def test_tg_card_tolerates_nan_enrichment():
    # _apply_live_edge_adjustments adds track_record/conviction_base columns; rows
    # without a value arrive here as NaN (float). _tg_card must not crash/leak it.
    s = _sample_signal(setup_type="mean_reversion", expected_dir="up",
                       track_record=float("nan"), conviction_base=float("nan"))
    out = formatting._tg_card(s)            # must not raise
    assert "nan" not in out.lower()


def test_live_edge_adjust_render_no_nan():
    import pandas as pd
    from crypto_rsi_scanner import scanner, outcomes

    class _FakeStore:
        def outcomes_joined(self):
            return [{"x": 1}]                # non-empty so the adjuster proceeds

    orig = outcomes.track_records
    outcomes.track_records = lambda rows, h: {"dip_buy": {"n": 10, "hit": 7, "med_ret": 2.0}}
    try:
        def row(sym, setup):
            return {"symbol": sym, "coin_id": sym.lower(), "flag": "OS",
                    "severity": "ALERT", "conviction": 55, "setup_type": setup,
                    "expected_dir": "up", "regime": "RANGE", "regime_note": "x",
                    "market_regime": "UPTREND", "market_aligned": "favorable",
                    "rsi_daily": 28.0, "rsi_4h": None, "rsi_weekly": None,
                    "rsi_z": 0.0, "rsi_delta": 0.0, "volume_ratio": 1.0,
                    "btc_corr": 0.0, "divergence": None, "price": 100.0}
        # AAA has a track record (dip_buy); ZZZ does NOT (mean_reversion) -> NaN row
        df = pd.DataFrame([row("AAA", "dip_buy"), row("ZZZ", "mean_reversion")])
        df = scanner._apply_live_edge_adjustments(df, _FakeStore())
        _, signals = scanner.build_message(df, {})
        for s in signals:
            card = formatting._tg_card(s)    # must not raise for the NaN-row coin
            assert "nan" not in card.lower(), f"NaN leaked for {s['symbol']}"
    finally:
        outcomes.track_records = orig


def test_route_notifications_only_marks_successful_sends():
    from crypto_rsi_scanner import scanner

    class Store:
        def __init__(self):
            self.alerted = []
            self.digest_marked = False
        def active_subscribers(self):
            return ["1"]
        def is_on_cooldown(self, symbol, flag, cooldown_hours):
            return False
        def mark_alerted(self, symbol, flag):
            self.alerted.append((symbol, flag))
        def digest_due(self, interval_hours):
            return True
        def mark_digest_sent(self):
            self.digest_marked = True

    signals = [
        {"symbol": "AAA", "flag": "OB", "tier": "INSTANT", "is_new": True, "conviction": 90},
        {"symbol": "BBB", "flag": "PRE_OS", "tier": "DIGEST", "is_new": True, "conviction": 35},
    ]
    orig = scanner.notify_all
    try:
        store = Store()
        scanner.notify_all = lambda *args, **kwargs: []
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is False and stats["digest_sent"] is False
        assert store.alerted == []
        assert store.digest_marked is False

        store = Store()
        scanner.notify_all = lambda *args, **kwargs: ["Telegram"]
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is True and stats["digest_sent"] is True
        assert store.alerted == [("AAA", "OB")]
        assert store.digest_marked is True
    finally:
        scanner.notify_all = orig


def test_telegram_send_chunks_long_messages():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def raise_for_status(self):
            return None

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS
    notifications.requests.post = lambda url, json, timeout: calls.append(json["text"]) or Response()
    config.TELEGRAM_BOT_TOKEN = "token"
    config.TELEGRAM_CHAT_IDS = ["1"]
    try:
        text = ("signal line\n\n" * 700).strip()
        assert len(text) > 4096
        assert notifications.send_telegram(text, parse_mode="HTML") is True
        assert len(calls) > 1
        assert all(len(body) <= 4096 for body in calls)
        assert not any("…" in body for body in calls)
        assert "signal line" in calls[-1]
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_scan_staleness_alert_dedup_and_recovery():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import telegram, heartbeat, config

    sent = []
    orig_alert = heartbeat.alert_stale_scan
    orig_int = config.STALE_CHECK_INTERVAL_SEC
    heartbeat.alert_stale_scan = lambda last, hrs, storage=None: sent.append(hrs)
    config.STALE_CHECK_INTERVAL_SEC = 0           # disable throttle for the test
    try:
        now = datetime(2026, 6, 8, tzinfo=timezone.utc)

        class Store:
            def __init__(self, dt):
                self.dt = dt
            def last_scan_at(self):
                return self.dt

        state: dict = {}
        telegram._check_scan_staleness(Store(now - timedelta(hours=2)), state, now=now)
        assert sent == []                          # fresh -> no alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 1                      # stale -> one alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=41)), state, now=now)
        assert len(sent) == 1                      # still stale -> no repeat (dedup)
        telegram._check_scan_staleness(Store(now - timedelta(hours=1)), state, now=now)
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 2                      # recovered then stale again -> re-alerts
        # no scan history yet -> never alerts
        telegram._check_scan_staleness(Store(None), {}, now=now)
        assert len(sent) == 2
    finally:
        heartbeat.alert_stale_scan = orig_alert
        config.STALE_CHECK_INTERVAL_SEC = orig_int


def test_scan_status_lifecycle_and_report():
    import json
    from datetime import datetime, timedelta, timezone

    from crypto_rsi_scanner import config, status_report, telegram

    st = _fresh_storage()
    orig_stale = config.STALE_SCAN_HOURS
    config.STALE_SCAN_HOURS = 36
    try:
        st.mark_scan_started(top_n=12)
        assert st.scan_status()["state"] == "running"

        st.mark_scan_success(
            top_n=12,
            requested=15,
            fetched=14,
            analyzed=12,
            coin_count=12,
            flagged_count=3,
            ob_count=2,
            os_count=1,
            instant_count=1,
            digest_count=2,
            matured_outcomes=4,
            paper_opened=1,
            paper_closed=0,
        )
        status = st.scan_status()
        assert status["state"] == "success"
        assert st.last_successful_scan_at() is not None
        telegram.save_latest_snapshot(st, [{"symbol": "AAA", "flag": "OB"}])
        st.subscribe("111", "alice")

        out = status_report.format_status(st)
        assert "health: OK" in out
        assert "fetch: requested 15, fetched 14, analyzed 12" in out
        assert "signals: scanned 12, flagged 3 (OB 2, OS 1)" in out
        assert "bot: 1 subscriber(s), 1 current snapshot signal(s)" in out

        old = datetime.now(timezone.utc) - timedelta(hours=40)
        status["last_success_at"] = old.isoformat()
        st.set_meta("scan_status", json.dumps(status))
        assert "health: STALE" in status_report.format_status(st, now=datetime.now(timezone.utc))
    finally:
        config.STALE_SCAN_HOURS = orig_stale
        st.close()


def test_scan_status_failure_and_bot_health_escapes():
    from crypto_rsi_scanner import telegram

    st = _fresh_storage()
    try:
        st.mark_scan_started(top_n=10)
        st.mark_scan_failure("bad <network> & token", requested=10, fetched=0, analyzed=0)
        plain = telegram._cmd_health(st)
        assert "RSI SCANNER STATUS" in plain
        assert "health: FAILED" in plain
        assert "bad &lt;network&gt; &amp; token" in plain
        assert "<network>" not in plain
    finally:
        st.close()


def test_sqlite_backup_api_integrity_and_retention():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample (value) VALUES ('ok')")
    conn.commit()
    conn.close()

    result = backup_database(
        src,
        backup_dir,
        keep=2,
        now=datetime(2026, 6, 8, 1, 2, 3, tzinfo=timezone.utc),
    )
    assert result.path.exists()
    assert result.quick_check == "ok"
    copied = sqlite3.connect(result.path)
    try:
        assert copied.execute("SELECT value FROM sample").fetchone()[0] == "ok"
    finally:
        copied.close()

    backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 4, tzinfo=timezone.utc))
    third = backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 5, tzinfo=timezone.utc))
    backups = sorted(backup_dir.glob("source-*.db"))
    assert len(backups) == 2
    assert backups[-1] == third.path
    assert not result.path.exists()


def test_sqlite_restore_drill_checks_schema_counts():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database, format_restore_result, verify_restore

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE paper_trades (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO scans DEFAULT VALUES")
    conn.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    backup = backup_database(
        src,
        backup_dir,
        now=datetime(2026, 6, 8, 2, 0, 0, tzinfo=timezone.utc),
    )
    result = verify_restore(
        backup.path,
        expected_tables=("scans", "signals", "meta", "paper_trades"),
    )
    assert result.quick_check == "ok"
    assert result.table_counts["scans"] == 1
    assert result.table_counts["meta"] == 1
    assert "SQLite restore drill complete" in format_restore_result(result)


def test_backup_freshness_status_report():
    import sqlite3
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner import config, status_report
    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "rsi_scanner.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    st = _fresh_storage()
    orig_db = config.DB_PATH
    orig_dir = config.BACKUP_DIR
    orig_keep = config.BACKUP_KEEP
    orig_stale = config.BACKUP_STALE_HOURS
    orig_logs = config.LOG_FILES
    config.DB_PATH = src
    config.BACKUP_DIR = backup_dir
    config.BACKUP_KEEP = 2
    config.BACKUP_STALE_HOURS = 24
    config.LOG_FILES = []
    try:
        created = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
        backup_database(src, backup_dir, keep=2, now=created)

        fresh = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: OK" in fresh
        assert "rsi_scanner-20260608T010000Z.db" in fresh
        assert "2.0h ago" in fresh
        assert "1/2 retained" in fresh

        stale = status_report.format_status(st, now=created + timedelta(hours=25))
        assert "backup: STALE" in stale

        config.BACKUP_DIR = root / "empty"
        missing = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: MISSING" in missing
        assert "run main.py --backup-db" in missing
    finally:
        config.DB_PATH = orig_db
        config.BACKUP_DIR = orig_dir
        config.BACKUP_KEEP = orig_keep
        config.BACKUP_STALE_HOURS = orig_stale
        config.LOG_FILES = orig_logs
        st.close()


def test_log_rotation_copytruncate_and_retention():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.ops import log_file_status, rotate_logs

    root = Path(tempfile.mkdtemp())
    log = root / "bot.log"
    first_time = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 6, 8, 1, 0, 1, tzinfo=timezone.utc)

    log.write_text("first rotation\n")
    first = rotate_logs([log], max_bytes=3, keep=1, now=first_time)[0]
    assert first.reason == "rotated"
    assert first.rotated_to is not None
    assert first.rotated_to.read_text() == "first rotation\n"
    assert log.read_text() == ""

    log.write_text("second rotation\n")
    second = rotate_logs([log], max_bytes=3, keep=1, now=second_time)[0]
    assert second.reason == "rotated"
    assert second.rotated_to is not None
    assert second.rotated_to.read_text() == "second rotation\n"
    assert not first.rotated_to.exists()
    assert len(list(root.glob("bot.log.*"))) == 1
    assert log.read_text() == ""

    status = log_file_status([log], max_bytes=3)[0]
    assert status.exists is True
    assert status.size_bytes == 0
    assert status.rotation_count == 1


def test_launchd_status_parser_and_formatter():
    from crypto_rsi_scanner.ops import _parse_launchctl_print, format_launchd_status

    text = """
gui/501/com.nasrenkaraf.rsibot = {
    path = /Users/nasrenkaraf/Library/LaunchAgents/com.nasrenkaraf.rsibot.plist
    state = running
    stdout path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    stderr path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    runs = 8
    pid = 73052
    last exit code = 0
}
"""
    status = _parse_launchctl_print("com.nasrenkaraf.rsibot", "gui/501", text)
    assert status.loaded is True
    assert status.state == "running"
    assert status.pid == 73052
    assert status.runs == 8
    assert status.last_exit_code == 0
    assert status.stdout_path.endswith("bot.log")

    out = format_launchd_status([status])
    assert "com.nasrenkaraf.rsibot: running, pid 73052, runs 8, last exit 0" in out
    assert "stdout: /Users/nasrenkaraf/crypto-rsi-scanner/bot.log" in out


def test_maintenance_agent_plist_contents():
    from pathlib import Path
    from crypto_rsi_scanner.ops import maintenance_agent_plist

    plist = maintenance_agent_plist(
        label="com.example.maint",
        python_path=Path("/repo/.venv/bin/python"),
        main_path=Path("/repo/main.py"),
        working_dir=Path("/repo"),
        log_path=Path("/repo/maintenance.log"),
        hour=3,
        minute=45,
    )
    assert plist["Label"] == "com.example.maint"
    assert plist["ProgramArguments"] == ["/repo/.venv/bin/python", "/repo/main.py", "--maintenance"]
    assert plist["WorkingDirectory"] == "/repo"
    assert plist["StandardOutPath"] == "/repo/maintenance.log"
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 45}
    assert plist["RunAtLoad"] is False


def test_coingecko_client_fixture_mode():
    import asyncio
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.client import CoinGeckoClient

    root = Path(tempfile.mkdtemp())
    chart_dir = root / "market_chart"
    chart_dir.mkdir()
    (root / "top_markets.json").write_text(json.dumps([
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
    ]))
    (chart_dir / "bitcoin.json").write_text(json.dumps({
        "prices": [[1, 100.0]],
        "total_volumes": [[1, 1000.0]],
    }))

    orig = config.FIXTURE_DIR
    config.FIXTURE_DIR = root
    try:
        async def _run():
            async with CoinGeckoClient() as client:
                markets = await client.get_top_markets(1)
                chart = await client.get_market_chart("bitcoin", 250)
                return markets, chart
        markets, chart = asyncio.run(_run())
        assert [m["id"] for m in markets] == ["bitcoin"]
        assert chart["prices"][0][1] == 100.0
    finally:
        config.FIXTURE_DIR = orig


def test_storage_wal_and_busy_timeout():
    # The scan and the always-on listener share one DB file; WAL + busy_timeout
    # let them read/write concurrently without "database is locked".
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "wal.db")
    try:
        assert str(st.conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert st.conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        st.close()


def _run_all():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(funcs) - failures}/{len(funcs)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
