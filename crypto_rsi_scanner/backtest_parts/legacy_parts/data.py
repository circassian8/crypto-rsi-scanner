"""Split implementation for `crypto_rsi_scanner/backtest_parts/legacy.py` (data)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import re
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from ... import config
from ...client import CoinGeckoClient
from ...indicators import (
    adaptive_thresholds,
    annualized_vol,
    conviction_score,
    detect_divergence,
    rsi_z_score,
    volume_ratio,
    wilder_rsi,
)
from ...outcomes import favorable
from ...signal_registry import (
    SETUPS,
    canonical_market_regime,
    market_alignment,
    setup_for,
    setup_has_edge,
)
from ...state_features import (
    breadth_state,
    falling_knife_bucket,
    falling_knife_score,
    liquidity_bucket,
    rank_bucket,
    realized_vol_series,
    trailing_percentile_series,
    volatility_state,
    volume_price_state,
)
from ...universe import candidate_count, filter_markets, format_exclusions
# Shared globals are injected by legacy.py after import.

log = logging.getLogger(__name__)
HORIZONS = config.OUTCOME_HORIZONS
PRIMARY = config.OUTCOME_PRIMARY_HORIZON
LB = config.LOOKBACK_DAYS_DAILY  # trailing window per "scan", mirrors live
_START = max(LB, config.REGIME_LONG_MA)
VOL_WINDOW = 20
MOM_WINDOW = 14
_FEATURE_IDX = {"vol": 0, "mom": 1}
_FEATURE_LABEL = {"vol": "trailing 20d annualized vol", "mom": "trailing 14d return"}
_STATE_FEATURES = {
    "vol_state": "volatility state",
    "breadth_state": "market breadth state",
    "rs_bucket": "relative-strength bucket",
    "liquidity_bucket": "liquidity bucket",
    "knife_bucket": "falling-knife bucket",
}
_SETUP_REGIME = {
    "breakdown_risk": ("DOWNTREND", "down"),
    "dip_buy": ("UPTREND", "up"),
    "trend_continuation": ("UPTREND", "up"),
}
_BINANCE_HOSTS = (
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
)
_DEFAULT_UNIVERSE = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "LINK", "AVAX",
    "DOT", "MATIC", "LTC", "BCH", "UNI", "ATOM", "XLM", "ETC", "FIL", "APT",
    "NEAR", "ICP", "ARB", "OP", "INJ", "SUI", "SEI", "AAVE", "GRT", "ALGO",
    "RUNE", "FTM", "SAND", "MANA", "AXS", "EOS", "THETA", "EGLD", "FLOW", "CRV",
]
def _klines_paged(host: str, symbol: str, days: int, session: requests.Session):
    """Page Binance klines back `days` (>1000 candles needs multiple calls).
    Returns {open_ms: row} or None if the host rejects the very first call."""
    end_ms = int(time.time() * 1000)
    cursor = end_ms - days * 86_400_000
    rows: dict = {}
    while True:
        r = session.get(host, params={"symbol": symbol, "interval": "1d",
                                      "limit": 1000, "startTime": cursor}, timeout=20)
        if r.status_code != 200:  # 451 geo-block / 400 bad symbol
            return rows or None
        batch = r.json()
        if not batch:
            break
        for row in batch:
            rows[row[0]] = row
        last_open = batch[-1][0]
        if len(batch) < 1000 or last_open + 86_400_000 >= end_ms:
            break
        cursor = last_open + 86_400_000
    return rows or None
def _klines_rows_to_frame(ordered: list) -> pd.DataFrame:
    """Kline rows (Binance array format, time-ordered) -> DataFrame indexed by UTC
    day with high/low/close, volume (base asset) and quote_volume (USDT ≈ dollar
    volume, field 7 — the basis for point-in-time volume-rank universe
    membership)."""
    idx = pd.to_datetime([r[0] for r in ordered], unit="ms", utc=True)
    return pd.DataFrame({
        "high": pd.Series([float(r[2]) for r in ordered], index=idx, dtype=float),
        "low": pd.Series([float(r[3]) for r in ordered], index=idx, dtype=float),
        "close": pd.Series([float(r[4]) for r in ordered], index=idx, dtype=float),
        "volume": pd.Series([float(r[5]) for r in ordered], index=idx, dtype=float),
        "quote_volume": pd.Series([float(r[7]) for r in ordered], index=idx, dtype=float),
    })
def _binance_klines_cache_path(cache_dir: Path, symbol: str, days: int) -> Path:
    return cache_dir / "binance_klines" / f"{_safe_cache_name(symbol)}-{days}d.json"
def _load_binance_klines_cache(cache_dir: Path | None, symbol: str, days: int) -> list | None:
    if cache_dir is None:
        return None
    path = _binance_klines_cache_path(cache_dir, symbol, days)
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("Ignoring unreadable klines cache %s: %s", path, e)
        return None
    return rows if isinstance(rows, list) and rows else None
def _write_binance_klines_cache(cache_dir: Path | None, symbol: str, days: int, rows: list) -> None:
    if cache_dir is None:
        return
    path = _binance_klines_cache_path(cache_dir, symbol, days)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
def fetch_klines(
    symbol: str,
    days: int,
    session: requests.Session | None,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
) -> pd.DataFrame | None:
    """Binance 1d klines -> DataFrame[close, volume, quote_volume] (UTC),
    paginated back `days`. With `cache_dir`, raw rows are cached like the
    CoinGecko PIT cache (research data is as-of fetch time; --refresh-pit-cache
    refetches). On a cache hit the session is never touched."""
    ordered: list | None = None
    if not refresh_cache:
        ordered = _load_binance_klines_cache(cache_dir, symbol, days)
    if ordered is None:
        if session is None:
            return None
        rows = None
        for host in _BINANCE_HOSTS:
            try:
                rows = _klines_paged(host, symbol, days, session)
                if rows:
                    break
            except Exception as e:  # noqa: BLE001
                log.debug("klines %s via %s failed: %s", symbol, host, e)
        if not rows:
            return None
        ordered = [rows[k] for k in sorted(rows)]
        _write_binance_klines_cache(cache_dir, symbol, days, ordered)
    return _klines_rows_to_frame(ordered)
def _fixture_klines_path(fixture_dir: str | Path, symbol: str) -> Path | None:
    root = Path(fixture_dir).expanduser()
    candidates = (
        root / "klines" / f"{symbol}.csv",
        root / f"{symbol}.csv",
    )
    for path in candidates:
        if path.exists():
            return path
    return None
def load_klines_fixture(symbol: str, days: int, fixture_dir: str | Path) -> pd.DataFrame | None:
    """Load a checked-in Binance-style daily OHLC fixture CSV.

    Expected columns: `date`, `close`, and optional `high`, `low`, `volume`, and
    `quote_volume`. Dates are parsed as UTC, sorted, and tailed to `days` so one
    fixture can smoke multiple windows.
    """
    path = _fixture_klines_path(fixture_dir, symbol)
    if path is None:
        log.warning("Fixture klines missing for %s in %s", symbol, fixture_dir)
        return None
    try:
        raw = pd.read_csv(path)
        if "date" not in raw or "close" not in raw:
            raise ValueError("fixture CSV must contain date and close columns")
        idx = pd.to_datetime(raw["date"], utc=True)
        close = pd.to_numeric(raw["close"], errors="coerce")
        high = (
            pd.to_numeric(raw["high"], errors="coerce")
            if "high" in raw
            else close
        )
        low = (
            pd.to_numeric(raw["low"], errors="coerce")
            if "low" in raw
            else close
        )
        volume = (
            pd.to_numeric(raw["volume"], errors="coerce")
            if "volume" in raw
            else pd.Series(0.0, index=raw.index)
        )
        quote_volume = (
            pd.to_numeric(raw["quote_volume"], errors="coerce")
            if "quote_volume" in raw
            else close * volume
        )
        df = pd.DataFrame({
            "high": high.to_numpy(),
            "low": low.to_numpy(),
            "close": close.to_numpy(),
            "volume": volume.to_numpy(),
            "quote_volume": quote_volume.to_numpy(),
        }, index=idx)
        df = df.sort_index().dropna(subset=["close"])
        return df.tail(days) if days > 0 else df
    except Exception as e:  # noqa: BLE001
        log.warning("Fixture klines unreadable for %s (%s): %s", symbol, path, e)
        return None
def fixture_symbols(fixture_dir: str | Path) -> list[str]:
    """Infer base symbols from fixture CSV names such as BTCUSDT.csv."""
    root = Path(fixture_dir).expanduser()
    search = root / "klines" if (root / "klines").exists() else root
    out: list[str] = []
    for path in sorted(search.glob("*.csv")):
        sym = path.stem.upper()
        if sym.endswith("USDT"):
            sym = sym[:-4]
        if sym and sym not in out:
            out.append(sym)
    return out
def _cg_base_headers() -> tuple[str, dict]:
    key = config.COINGECKO_API_KEY
    if key and config.COINGECKO_KEY_TYPE == "pro":
        return "https://pro-api.coingecko.com/api/v3", {"x-cg-pro-api-key": key}
    if key:
        return "https://api.coingecko.com/api/v3", {"x-cg-demo-api-key": key}
    return "https://api.coingecko.com/api/v3", {}
def cg_top_coins(n: int) -> list[dict]:
    """Current clean top-N coins by market cap as [{'id','symbol'}].

    Uses the same universe hygiene as the live scanner. Empty list on failure.
    """
    base, headers = _cg_base_headers()
    try:
        fetch_n = candidate_count(n)
        r = requests.get(
            f"{base}/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc",
                    "per_page": fetch_n, "page": 1,
                    "price_change_percentage": "24h"},
            headers=headers, timeout=30,
        )
        r.raise_for_status()
        clean, excluded = filter_markets(r.json(), limit=n)
        if excluded:
            log.info("CoinGecko universe hygiene excluded: %s", format_exclusions(excluded))
        return [
            {"id": m["id"], "symbol": str(m["symbol"]).upper()}
            for m in clean
            if m.get("id") and m.get("symbol")
        ][:n]
    except Exception as e:  # noqa: BLE001
        log.warning("CoinGecko universe fetch failed (%s)", e)
        return []
_FIAT_OR_PEGGED_BASES = {
    "eur", "gbp", "aud", "try", "brl", "ars", "uah", "rub", "ngn", "bidr",
    "idrt", "aeur", "usdp", "ust", "wusd", "xusd",
}
def _filter_usdt_bases(symbols: list[dict]) -> list[str]:
    """exchangeInfo symbol dicts -> sorted unique base assets for the volume-PIT
    pool: USDT-quoted, currently TRADING, minus stables/wrapped/fiat."""
    bases: set[str] = set()
    for s in symbols:
        if s.get("quoteAsset") != "USDT" or s.get("status") != "TRADING":
            continue
        base = (s.get("baseAsset") or "").upper()
        if not base:
            continue
        low = base.lower()
        if low in config.EXCLUDE_SYMBOLS or low in _FIAT_OR_PEGGED_BASES:
            continue
        bases.add(base)
    return sorted(bases)
def binance_usdt_pool(session: requests.Session) -> list[str]:
    """Every currently-TRADING Binance USDT base (hygiene-filtered) — the
    candidate pool for point-in-time volume-rank membership. Residual
    survivorship: pairs Binance has fully delisted are absent from exchangeInfo,
    so coins that died off the venue can't re-enter the sample."""
    for host in _BINANCE_HOSTS:
        url = host.replace("/klines", "/exchangeInfo")
        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                continue
            return _filter_usdt_bases(r.json().get("symbols", []))
        except Exception as e:  # noqa: BLE001
            log.debug("exchangeInfo via %s failed: %s", url, e)
    return []
def cg_top_symbols(n: int) -> list[str]:
    """Top-N symbols for the (survivorship-biased) Binance path; falls back to a
    built-in list if CoinGecko is unreachable."""
    syms = [c["symbol"] for c in cg_top_coins(n)]
    return syms or list(_DEFAULT_UNIVERSE)
def _parse_cg_chart(data: dict) -> pd.DataFrame | None:
    """CoinGecko /market_chart -> daily DataFrame[close, mcap, volume] (UTC)."""
    prices = data.get("prices") or []
    if len(prices) < 2:
        return None

    def _daily(pairs, how):
        s = pd.Series({p[0]: p[1] for p in pairs}, dtype=float)
        s.index = pd.to_datetime(s.index, unit="ms", utc=True).floor("D")
        return s.groupby(level=0).sum() if how == "sum" else s.groupby(level=0).last()

    close = _daily(prices, "last")
    mcaps = data.get("market_caps") or []
    vols = data.get("total_volumes") or []
    mcap = _daily(mcaps, "last").reindex(close.index) if mcaps else pd.Series(np.nan, index=close.index)
    vol = _daily(vols, "sum").reindex(close.index) if vols else pd.Series(0.0, index=close.index)
    return pd.DataFrame({"close": close, "mcap": mcap, "volume": vol}).dropna(subset=["close"])
def _safe_cache_name(coin_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", coin_id).strip("_") or "coin"
def _cg_chart_cache_path(cache_dir: Path, coin_id: str, days: int) -> Path:
    return cache_dir / "coingecko_market_chart" / f"{_safe_cache_name(coin_id)}-{days}d.json"
def _load_cg_chart_cache(cache_dir: Path | None, coin_id: str, days: int) -> dict | None:
    if cache_dir is None:
        return None
    path = _cg_chart_cache_path(cache_dir, coin_id, days)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("Ignoring unreadable PIT cache %s: %s", path, e)
        return None
    return data if isinstance(data, dict) else None
def _write_cg_chart_cache(cache_dir: Path | None, coin_id: str, days: int, data: dict) -> None:
    if cache_dir is None:
        return
    path = _cg_chart_cache_path(cache_dir, coin_id, days)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    tmp.replace(path)
async def _fetch_cg_histories(
    ids: list[str],
    days: int,
    *,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
) -> dict:
    """Fetch market_chart (price + market cap + volume) for the candidate pool,
    in parallel under the client's rate limiter. Cache raw JSON so interrupted
    PIT research runs can resume without re-spending API quota."""
    raw_by_id: dict[str, dict] = {}
    missing: list[str] = []
    if not refresh_cache:
        for cid in ids:
            cached = _load_cg_chart_cache(cache_dir, cid, days)
            if cached is None:
                missing.append(cid)
            else:
                raw_by_id[cid] = cached
    else:
        missing = list(ids)

    if missing:
        async with CoinGeckoClient() as client:
            async def one(cid):
                try:
                    data = await client.get_market_chart(cid, days)
                    _write_cg_chart_cache(cache_dir, cid, days, data)
                    return cid, data
                except Exception as e:  # noqa: BLE001
                    log.debug("cg chart %s failed: %s", cid, e)
                    return cid, None
            results = await asyncio.gather(*[one(c) for c in missing])
        for cid, raw in results:
            if isinstance(raw, dict):
                raw_by_id[cid] = raw

    if cache_dir is not None:
        log.info(
            "PIT cache: %d hit(s), %d miss(es), dir=%s",
            len(ids) - len(missing),
            len(missing),
            cache_dir,
        )

    parsed: dict[str, pd.DataFrame] = {}
    for cid, raw in raw_by_id.items():
        try:
            parsed[cid] = _parse_cg_chart(raw)
        except Exception as e:  # noqa: BLE001
            log.debug("cg chart %s parse failed: %s", cid, e)
            parsed[cid] = None

    min_len = _START + max(HORIZONS) + 1
    out = {cid: df for cid, df in parsed.items() if df is not None and len(df) >= min_len}
    log.info("PIT: usable history for %d/%d candidates", len(out), len(ids))
    return out
def build_pit_membership(histories: dict, top_n: int) -> pd.DataFrame:
    """Per-date top-N membership: rank candidates by their market cap on each
    date; the top_n are 'in universe' that day. Bool DataFrame[date x coin_id]."""
    mcap = pd.DataFrame({cid: df["mcap"] for cid, df in histories.items()}).sort_index()
    rank = mcap.rank(axis=1, ascending=False, method="min")
    return rank.le(top_n) & mcap.notna()
def run_pit(
    pool: list[dict],
    top_n: int,
    days: int,
    trigger: str = "cross_into",
    state_slices: bool = False,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
) -> tuple[list, dict, dict, dict, dict, int]:
    histories = asyncio.run(_fetch_cg_histories(
        [c["id"] for c in pool],
        days,
        cache_dir=cache_dir,
        refresh_cache=refresh_cache,
    ))
    signals: list = []
    regime_base: dict = defaultdict(list)
    cond_base: dict = defaultdict(list)
    mkt_base: dict = defaultdict(list)
    state_base: dict = defaultdict(list)
    if not histories:
        return signals, regime_base, cond_base, mkt_base, state_base, 0
    member_df = build_pit_membership(histories, top_n)
    state_frames = (
        build_state_frames(histories, member_df, volume_is_usd=True)
        if state_slices else {}
    )
    mkt = (market_regime_series(histories["bitcoin"]["close"])
           if "bitcoin" in histories else None)
    for cid, df in histories.items():
        mem = member_df[cid].reindex(df.index, fill_value=False).to_numpy()
        if not mem.any():
            continue
        mkt_arr = mkt.reindex(df.index).fillna("NA").to_numpy() if mkt is not None else None
        walk_coin(df, signals, regime_base, cond_base, member=mem,
                  mkt_arr=mkt_arr, mkt_base=mkt_base, trigger=trigger,
                  state_frame=state_frames.get(cid), state_base=state_base,
                  label=cid)
    return signals, regime_base, cond_base, mkt_base, state_base, len(histories)
VOLUME_MEMBERSHIP_WINDOW = 30
def _require_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
def _has_binance_klines_cache(
    cache_dir: Path | None,
    symbol: str,
    days: int,
    refresh_cache: bool,
) -> bool:
    return (
        cache_dir is not None
        and not refresh_cache
        and _binance_klines_cache_path(cache_dir, symbol, days).exists()
    )
def build_volume_membership(frames: dict, top_n: int,
                            window: int = VOLUME_MEMBERSHIP_WINDOW) -> pd.DataFrame:
    """Per-date top-N membership by trailing `window`-day mean dollar volume.
    Bool DataFrame[date x symbol]; a symbol needs `window` days of history before
    it can enter (no lookahead — the trailing mean at t uses days <= t)."""
    _require_positive_int("top_n", top_n)
    _require_positive_int("window", window)
    qv = pd.DataFrame(
        {sym: df["quote_volume"] for sym, df in frames.items()}
    ).sort_index()
    trail = qv.rolling(window, min_periods=window).mean()
    rank = trail.rank(axis=1, ascending=False, method="min")
    return rank.le(top_n) & trail.notna()
def _fetch_volume_pit_frames(
    days: int,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
) -> dict:
    """Fetch/cache the whole Binance USDT pool once for volume-PIT research."""
    with requests.Session() as session:
        pool = binance_usdt_pool(session)
        if not pool:
            log.error("Volume-PIT: could not fetch the Binance USDT symbol pool.")
            return {}
        if "BTC" not in pool:
            pool = ["BTC"] + pool  # always need BTC for the market regime
        log.info("Volume-PIT pool: %d Binance USDT bases (%dd history)...", len(pool), days)

        min_len = _START + max(HORIZONS) + 1
        frames: dict = {}
        for i, base in enumerate(pool, 1):
            symbol = base + "USDT"
            from_cache = _has_binance_klines_cache(cache_dir, symbol, days, refresh_cache)
            df = fetch_klines(symbol, days, session,
                              cache_dir=cache_dir, refresh_cache=refresh_cache)
            if df is not None and len(df) >= min_len:
                frames[base] = df
            if i % 50 == 0:
                log.info("  ...%d/%d fetched (%d usable)", i, len(pool), len(frames))
            if not from_cache:
                time.sleep(0.03)  # be polite to the API when we actually hit it
    log.info("Volume-PIT: usable history for %d/%d candidates", len(frames), len(pool))
    return frames
def _walk_volume_pit_frames(
    frames: dict,
    top_n: int,
    trigger: str = "cross_into",
    state_slices: bool = False,
    volume_window: int = VOLUME_MEMBERSHIP_WINDOW,
) -> tuple[list, dict, dict, dict, dict]:
    """Walk an already-fetched volume-PIT frame set under one trigger."""
    signals: list = []
    regime_base: dict = defaultdict(list)
    cond_base: dict = defaultdict(list)
    mkt_base: dict = defaultdict(list)
    state_base: dict = defaultdict(list)
    if not frames:
        return signals, regime_base, cond_base, mkt_base, state_base

    member_df = build_volume_membership(frames, top_n, volume_window)
    # Walk on dollar volume so volume_ratio matches the live scanner (CoinGecko
    # volumes are USD); the plain Binance path keeps base volume untouched.
    usd_frames = {sym: df.assign(volume=df["quote_volume"]) for sym, df in frames.items()}
    state_frames = (
        build_state_frames(usd_frames, member_df, volume_is_usd=True)
        if state_slices else {}
    )
    mkt = market_regime_series(frames["BTC"]["close"]) if "BTC" in frames else None
    if mkt is None:
        log.warning("Volume-PIT: no BTC history; market-regime breakdown disabled.")

    for sym, df in usd_frames.items():
        mem = member_df[sym].reindex(df.index, fill_value=False).to_numpy()
        if not mem.any():
            continue
        mkt_arr = mkt.reindex(df.index).fillna("NA").to_numpy() if mkt is not None else None
        walk_coin(df, signals, regime_base, cond_base, member=mem,
                  mkt_arr=mkt_arr, mkt_base=mkt_base, trigger=trigger,
                  state_frame=state_frames.get(sym), state_base=state_base,
                  label=sym)
    return signals, regime_base, cond_base, mkt_base, state_base
def run_pit_volume(
    top_n: int,
    days: int,
    trigger: str = "cross_into",
    state_slices: bool = False,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
    volume_window: int = VOLUME_MEMBERSHIP_WINDOW,
) -> tuple[list, dict, dict, dict, dict, int]:
    """Volume-rank PIT backtest over the full Binance USDT pool."""
    frames = _fetch_volume_pit_frames(days, cache_dir=cache_dir, refresh_cache=refresh_cache)
    signals, regime_base, cond_base, mkt_base, state_base = _walk_volume_pit_frames(
        frames,
        top_n,
        trigger=trigger,
        state_slices=state_slices,
        volume_window=volume_window,
    )
    return signals, regime_base, cond_base, mkt_base, state_base, len(frames)
def run_pit_volume_triggers(
    top_n: int,
    days: int,
    triggers=("cross_into", "confirm"),
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
    volume_window: int = VOLUME_MEMBERSHIP_WINDOW,
) -> tuple[dict, int]:
    """Fetch the volume-PIT universe once, then A/B triggers on that same data."""
    frames = _fetch_volume_pit_frames(days, cache_dir=cache_dir, refresh_cache=refresh_cache)
    results = {
        trig: _walk_volume_pit_frames(
            frames,
            top_n,
            trigger=trig,
            volume_window=volume_window,
        )
        for trig in triggers
    }
    return results, len(frames)
def _fetch_all(
    universe: list[str],
    days: int,
    fixture_dir: str | Path | None = None,
) -> tuple[dict, pd.Series | None]:
    """Fetch every coin's klines once (so triggers can be A/B'd on the same data)
    plus BTC's market-regime series."""
    session = None if fixture_dir else requests.Session()

    def _get(symbol: str) -> pd.DataFrame | None:
        if fixture_dir:
            return load_klines_fixture(symbol, days, fixture_dir)
        return fetch_klines(symbol, days, session)

    btc = _get("BTCUSDT")
    mkt = market_regime_series(btc["close"]) if btc is not None else None
    if mkt is None:
        log.warning("Could not fetch BTC; market-regime breakdown disabled.")
    frames: dict = {}
    for i, sym in enumerate(universe, 1):
        df = _get(sym + "USDT")
        if df is not None and len(df) >= _START + max(HORIZONS) + 1:
            frames[sym] = df
        if i % 20 == 0:
            log.info("  ...%d/%d fetched (%d usable)", i, len(universe), len(frames))
        if not fixture_dir:
            time.sleep(0.04)  # be polite to the API
    return frames, mkt
def _walk_all(
    frames: dict,
    mkt,
    trigger: str = "cross_into",
    state_slices: bool = False,
) -> tuple[list, dict, dict, dict, dict]:
    signals: list = []
    regime_base: dict = defaultdict(list)
    cond_base: dict = defaultdict(list)
    mkt_base: dict = defaultdict(list)
    state_base: dict = defaultdict(list)
    state_frames = build_state_frames(frames, volume_is_usd=False) if state_slices else {}
    for sym, df in frames.items():
        mkt_arr = mkt.reindex(df.index).fillna("NA").to_numpy() if mkt is not None else None
        walk_coin(df, signals, regime_base, cond_base,
                  mkt_arr=mkt_arr, mkt_base=mkt_base, trigger=trigger,
                  state_frame=state_frames.get(sym), state_base=state_base,
                  label=sym)
    return signals, regime_base, cond_base, mkt_base, state_base
def run(
    universe: list[str],
    days: int,
    trigger: str = "cross_into",
    state_slices: bool = False,
    fixture_dir: str | Path | None = None,
) -> tuple[list, dict, dict, dict, dict, int]:
    frames, mkt = _fetch_all(universe, days, fixture_dir=fixture_dir)
    s, rb, cb, mb, sb = _walk_all(frames, mkt, trigger, state_slices)
    return s, rb, cb, mb, sb, len(frames)
def run_triggers(universe: list[str], days: int,
                 triggers=("cross_into", "confirm"),
                 fixture_dir: str | Path | None = None) -> tuple[dict, int]:
    """Fetch once, walk under each trigger — for an apples-to-apples A/B."""
    frames, mkt = _fetch_all(universe, days, fixture_dir=fixture_dir)
    results = {trig: _walk_all(frames, mkt, trig) for trig in triggers}
    return results, len(frames)
