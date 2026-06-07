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
        "market_regime": "UPTREND", "price": 70000.0, "is_new": 1,
    })
    row = st.conn.execute(
        "SELECT symbol, market_regime, setup_type FROM signals"
    ).fetchone()
    assert row["symbol"] == "BTC" and row["market_regime"] == "UPTREND"
    assert row["setup_type"] == "trend_continuation"
    st.close()


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
         "symbol": "A", "severity": "ALERT"},
        {"horizon_days": 7, "ret_pct": 2.0, "favorable": 0, "flag": "OB",
         "regime": "UPTREND", "regime_note": "continuation", "conviction": 55,
         "symbol": "B", "severity": "WATCH"},
        {"horizon_days": 7, "ret_pct": 4.0, "favorable": 1, "flag": "OS",
         "regime": "DOWNTREND", "regime_note": "continuation", "conviction": 70,
         "symbol": "C", "severity": "ALERT"},
    ]
    out = build_report(rows, primary_horizon=7)
    assert "RSI SIGNAL OUTCOMES" in out
    assert "By setup" in out and "By conviction" in out


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
         "market_aligned": "favorable", "conviction": 70},
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
    assert rows["BBB"]["direction"] == "short" and rows["BBB"]["ret_pct"] < -5  # rose, short loses
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
        "market_aligned, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('AAA','aaa','dip_buy','UPTREND','favorable','long',70,100,'2026-05-01',7,"
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
    st.close()


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
