"""Backtest regression tests split from the legacy umbrella runner."""

from __future__ import annotations

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---

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
            "regime": "UPTREND" if setup == "dip_buy" else "DOWNTREND",
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

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 10,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 10,
    }
    mkt_wf = backtest.format_market_walk_forward(signals, mkt_base, folds=4, min_test_n=1)
    assert "Walk-forward setup × MARKET regime stability" in mkt_wf
    assert "Base = full-period same coin-regime × BTC-market base" in mkt_wf
    assert "dip_buy" in mkt_wf
    assert "BULL" in mkt_wf
    assert "+50" in mkt_wf


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
        {"baseAsset": "EURC", "quoteAsset": "USDT", "status": "TRADING"},  # euro stable
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
    assert list(df["high"]) == [2.0, 2.0]
    assert list(df["low"]) == [0.5, 1.0]
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
    assert list(df["high"]) == [2.0]
    assert list(df["low"]) == [0.5]
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
        "date,high,low,close,volume,quote_volume\n"
        "2026-01-02T00:00:00Z,102,99,101,1000,101000\n"
        "2026-01-01T00:00:00Z,101,98,100,900,90000\n"
        "2026-01-03T00:00:00Z,104,100,103,1100,113300\n"
    )
    (klines / "ETHUSDT.csv").write_text(
        "date,close,volume\n"
        "2026-01-01T00:00:00Z,10,50\n"
    )

    assert fixture_symbols(root) == ["BTC", "ETH"]
    df = load_klines_fixture("BTCUSDT", 2, root)
    assert df is not None
    assert list(df["close"]) == [101, 103]
    assert list(df["high"]) == [102, 104]
    assert list(df["low"]) == [99, 100]
    assert list(df["quote_volume"]) == [101000, 113300]
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
