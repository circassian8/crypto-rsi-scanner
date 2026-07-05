"""RSI indicator, scanner scoring, and universe regression tests."""

from __future__ import annotations

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---

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
        assert "sparkline" not in path.read_text(encoding="utf-8")
    finally:
        config.CSV_OUT = orig


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
