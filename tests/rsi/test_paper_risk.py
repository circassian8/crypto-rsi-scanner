"""Paper, outcome, and risk-rendering regression tests."""

from __future__ import annotations

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---

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
