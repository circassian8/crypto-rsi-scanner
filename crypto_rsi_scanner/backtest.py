"""Offline backtester: replay the live signal logic over real daily OHLC history
and measure each setup's edge AGAINST a regime base-rate benchmark.

Why the benchmark matters: a setup like breakdown_risk (oversold in a downtrend)
"confirms" often simply because downtrends persist. Comparing each setup's
confirm-rate and forward return to the base rate of the *same regime* (what a
random day in that regime did) isolates the RSI signal's actual contribution —
so a gaudy hit-rate that's really just "trends trend" shows up as ~0 edge.

Faithfulness: it reuses the package's own pure functions (wilder_rsi, decide_flag,
trend_regime, setup_for, conviction_score, favorable) over a trailing window the
same length as a live scan, and grades only fresh crossings (is_new), exactly as
the live scanner does.

Data: Binance 1d klines — free, no key, real OHLC closes (the live scanner runs
RSI on CoinGecko snapshot-prices, so this is also a cleaner price source).
Universe: current top-N by market cap from CoinGecko, falling back to a built-in
list of majors if CoinGecko is unreachable.

Caveats it does NOT correct for: (1) survivorship — today's top-N over past
history skips coins that dropped out; (2) single venue (Binance USDT pairs);
(3) no fees/slippage. This measures signal *edge*, not a tradable P&L.

Usage:
  python -m crypto_rsi_scanner.backtest --top-n 80 --days 730
  python -m crypto_rsi_scanner.backtest --symbols BTC,ETH,SOL --days 365
  python -m crypto_rsi_scanner.backtest --top-n 80 --days 1460 --costs --walk-forward
"""

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

from . import config
from .client import CoinGeckoClient
from .indicators import (
    adaptive_thresholds,
    annualized_vol,
    conviction_score,
    detect_divergence,
    rsi_z_score,
    volume_ratio,
    wilder_rsi,
)
from .outcomes import favorable
from .signal_registry import (
    SETUPS,
    canonical_market_regime,
    market_alignment,
    setup_for,
    setup_has_edge,
)
from .state_features import (
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
from .universe import candidate_count, filter_markets, format_exclusions

log = logging.getLogger(__name__)

HORIZONS = config.OUTCOME_HORIZONS
PRIMARY = config.OUTCOME_PRIMARY_HORIZON
LB = config.LOOKBACK_DAYS_DAILY  # trailing window per "scan", mirrors live
_START = max(LB, config.REGIME_LONG_MA)

# Point-in-time conditioning features (no lookahead): trailing realized vol and
# trailing return (downside momentum). Used to test *when* a setup's expected
# direction actually holds — e.g. does oversold-in-downtrend only keep falling
# in high-volatility crashes?
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
# Setups with a single defining regime, sliceable by --slice.
_SETUP_REGIME = {
    "breakdown_risk": ("DOWNTREND", "down"),
    "dip_buy": ("UPTREND", "up"),
    "trend_continuation": ("UPTREND", "up"),
}
# data-api.binance.vision is Binance's public market-data mirror: same kline
# format, no key, and (unlike api.binance.com, which 451s from restricted
# locations) no geo-block. api.binance.com is kept as a fallback.
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


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

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
    day with close, volume (base asset) and quote_volume (USDT ≈ dollar volume,
    field 7 — the basis for point-in-time volume-rank universe membership)."""
    idx = pd.to_datetime([r[0] for r in ordered], unit="ms", utc=True)
    return pd.DataFrame({
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

    Expected columns: `date`, `close`, and optional `volume`. Dates are parsed as
    UTC, sorted, and tailed to `days` so one fixture can smoke multiple windows.
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
        volume = (
            pd.to_numeric(raw["volume"], errors="coerce")
            if "volume" in raw
            else pd.Series(0.0, index=raw.index)
        )
        df = pd.DataFrame({
            "close": close.to_numpy(),
            "volume": volume.to_numpy(),
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


# Fiat / pegged bases that trade against USDT but aren't crypto momentum assets.
# Leveraged tokens (BTCUP/ETHDOWN, …) need no suffix filter: Binance delisted
# them all, so status=TRADING already excludes them — and a suffix filter would
# wrongly drop real coins like JUP or SYRUP.
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


# --------------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------------- #

def _severity(flag: str, rsi: float) -> str:
    for threshold, level in config.SEVERITY_TIERS.get(flag, []):
        if flag == "OB" and rsi >= threshold:
            return level
        if flag == "OS" and rsi <= threshold:
            return level
    return "WATCH"


def _weekly_asof(weekly_rsi: pd.Series, ts: pd.Timestamp) -> float | None:
    prior = weekly_rsi.loc[weekly_rsi.index <= ts]
    return float(prior.iloc[-1]) if len(prior) else None


def market_regime_series(close: pd.Series) -> pd.Series:
    """BULL / BEAR / CHOP per date from a leader series (BTC), via the same MA
    structure as trend_regime. This is the market backdrop each signal is tagged
    with — distinct from a coin's own trend. 'NA' during the 200d warm-up."""
    sma_s = close.rolling(config.REGIME_SHORT_MA).mean()
    sma_l = close.rolling(config.REGIME_LONG_MA).mean()
    slope = sma_l - sma_l.shift(config.REGIME_SLOPE_LOOKBACK)
    above, aligned = close > sma_l, sma_s > sma_l
    out = pd.Series("CHOP", index=close.index, dtype=object)
    out[above & aligned & (slope >= 0)] = "BULL"
    out[(~above) & (~aligned) & (slope <= 0)] = "BEAR"
    out[sma_l.isna() | sma_s.isna()] = "NA"
    return out


def _trend_regime_series(close: pd.Series) -> pd.Series:
    sma_s = close.rolling(config.REGIME_SHORT_MA).mean()
    sma_l = close.rolling(config.REGIME_LONG_MA).mean()
    slope = sma_l - sma_l.shift(config.REGIME_SLOPE_LOOKBACK)
    above, aligned = close > sma_l, sma_s > sma_l
    out = pd.Series("RANGE", index=close.index, dtype=object)
    out[above & aligned & (slope >= 0)] = "UPTREND"
    out[(~above) & (~aligned) & (slope <= 0)] = "DOWNTREND"
    out[sma_l.isna() | sma_s.isna()] = "UNKNOWN"
    return out


def _active_mask(frame: pd.DataFrame, membership: pd.DataFrame | None) -> pd.DataFrame:
    active = frame.notna()
    if membership is None:
        return active
    member = membership.reindex(index=frame.index, columns=frame.columns, fill_value=False)
    return active & member.astype(bool)


def _pct_true(values: pd.DataFrame, active: pd.DataFrame) -> pd.Series:
    valid = active & values.notna()
    denom = valid.sum(axis=1).replace(0, np.nan)
    return (values.where(valid).sum(axis=1) / denom).replace([np.inf, -np.inf], np.nan)


def _cross_sectional_rank_frame(values: pd.DataFrame, active: pd.DataFrame) -> pd.DataFrame:
    masked = values.where(active)
    ranks = masked.rank(axis=1, method="average", ascending=True)
    counts = masked.count(axis=1)
    denom = (counts - 1).replace(0, np.nan)
    out = ranks.sub(1, axis=0).div(denom, axis=0)
    return out.fillna(0.5)


def _volume_z_series(volume: pd.Series, window: int = 90) -> pd.Series:
    mean = volume.rolling(window, min_periods=window).mean()
    std = volume.rolling(window, min_periods=window).std(ddof=0)
    return ((volume - mean) / std.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_state_frames(
    frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame | None = None,
    *,
    volume_is_usd: bool = False,
) -> dict[str, pd.DataFrame]:
    """Point-in-time state labels per coin/date for state-conditioned research.

    `membership` lets the PIT path compute breadth and ranks only from coins that
    were actually in the universe on each date.
    """
    if not frames:
        return {}

    close_frame = pd.DataFrame({sym: df["close"] for sym, df in frames.items()}).sort_index()
    active = _active_mask(close_frame, membership)

    rsi_frame = pd.DataFrame({
        sym: wilder_rsi(df["close"], config.RSI_PERIOD)
        for sym, df in frames.items()
    }).reindex(close_frame.index)
    rsi_active = rsi_frame.where(active)
    n_rsi = rsi_active.notna().sum(axis=1).replace(0, np.nan)
    median_rsi = rsi_active.median(axis=1)
    pct_rsi_lt_30 = (rsi_active.lt(30).where(rsi_active.notna()).sum(axis=1) / n_rsi)
    pct_rsi_lt_40 = (rsi_active.lt(40).where(rsi_active.notna()).sum(axis=1) / n_rsi)
    pct_rsi_gt_60 = (rsi_active.gt(60).where(rsi_active.notna()).sum(axis=1) / n_rsi)

    ma50 = close_frame.rolling(50, min_periods=50).mean()
    ma200 = close_frame.rolling(200, min_periods=200).mean()
    pct_above_50 = _pct_true(close_frame.gt(ma50), active & ma50.notna())
    pct_above_200 = _pct_true(close_frame.gt(ma200), active & ma200.notna())
    pct_above_50_chg = pct_above_50 - pct_above_50.shift(5)
    pct_above_200_chg = pct_above_200 - pct_above_200.shift(5)
    breadth = pd.Series(index=close_frame.index, dtype=object)
    for ts in close_frame.index:
        breadth.loc[ts] = breadth_state(
            median_rsi=None if pd.isna(median_rsi.loc[ts]) else float(median_rsi.loc[ts]),
            pct_rsi_lt_30=None if pd.isna(pct_rsi_lt_30.loc[ts]) else float(pct_rsi_lt_30.loc[ts]),
            pct_rsi_lt_40=None if pd.isna(pct_rsi_lt_40.loc[ts]) else float(pct_rsi_lt_40.loc[ts]),
            pct_rsi_gt_60=None if pd.isna(pct_rsi_gt_60.loc[ts]) else float(pct_rsi_gt_60.loc[ts]),
            pct_above_50dma=None if pd.isna(pct_above_50.loc[ts]) else float(pct_above_50.loc[ts]),
            pct_above_200dma=None if pd.isna(pct_above_200.loc[ts]) else float(pct_above_200.loc[ts]),
            pct_above_50dma_chg_5d=None if pd.isna(pct_above_50_chg.loc[ts]) else float(pct_above_50_chg.loc[ts]),
            pct_above_200dma_chg_5d=None if pd.isna(pct_above_200_chg.loc[ts]) else float(pct_above_200_chg.loc[ts]),
        )

    rank30 = _cross_sectional_rank_frame(close_frame / close_frame.shift(30) - 1.0, active)
    rank90 = _cross_sectional_rank_frame(close_frame / close_frame.shift(90) - 1.0, active)
    avg_rank = (rank30 + rank90) / 2.0

    btc_close = None
    for key in ("BTC", "bitcoin", "btc"):
        if key in close_frame:
            btc_close = close_frame[key]
            break
    btc_ret = btc_close.pct_change(fill_method=None) if btc_close is not None else None

    out: dict[str, pd.DataFrame] = {}
    for sym, df in frames.items():
        close = df["close"]
        volume = df["volume"]
        idx = close.index
        rv20 = realized_vol_series(close, 20).reindex(idx)
        rv60 = realized_vol_series(close, 60).reindex(idx)
        rv_pct = trailing_percentile_series(rv20, 252).reindex(idx).fillna(0.5)
        vol_states = pd.Series(
            [volatility_state(a, b, c) for a, b, c in zip(rv20, rv60, rv_pct)],
            index=idx,
            dtype=object,
        )

        rs = avg_rank[sym].reindex(idx).map(rank_bucket)
        dollar = volume if volume_is_usd else close * volume
        dollar20 = dollar.rolling(20, min_periods=1).mean()
        mcap = df["mcap"] if "mcap" in df else pd.Series(np.nan, index=idx)
        turnover = (dollar20 / mcap.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        liq = pd.Series(
            [liquidity_bucket(dv, tv) for dv, tv in zip(dollar20, turnover)],
            index=idx,
            dtype=object,
        )

        vol_z = _volume_z_series(volume, 90)
        ret_1d = close.pct_change(fill_method=None).fillna(0.0)
        volume_states = pd.Series(
            [volume_price_state(r, z) for r, z in zip(ret_1d, vol_z)],
            index=idx,
            dtype=object,
        )
        breadth_for_coin = breadth.reindex(idx).fillna("unknown")
        regime = _trend_regime_series(close)
        ret30 = close.pct_change(30, fill_method=None).fillna(0.0)

        beta = pd.Series(0.0, index=idx)
        r2 = pd.Series(0.0, index=idx)
        if btc_ret is not None and sym not in ("BTC", "bitcoin", "btc"):
            ret = close.pct_change(fill_method=None)
            cov = ret.rolling(60, min_periods=20).cov(btc_ret)
            var = btc_ret.rolling(60, min_periods=20).var()
            beta = (cov / var.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            corr = ret.rolling(60, min_periods=20).corr(btc_ret).replace([np.inf, -np.inf], np.nan)
            r2 = corr.pow(2).fillna(0.0)
        elif btc_ret is not None:
            beta = pd.Series(1.0, index=idx)
            r2 = pd.Series(1.0, index=idx)

        knife = pd.Series(
            [
                falling_knife_score(
                    vol_state=vs,
                    breadth_state=str(br or "unknown"),
                    rs_bucket=rb,
                    regime=rg,
                    volume_state=vp,
                    ret_30d=float(rt) if np.isfinite(rt) else 0.0,
                    btc_beta_60=float(bt) if np.isfinite(bt) else 0.0,
                    beta_r2_60=float(rr) if np.isfinite(rr) else 0.0,
                )
                for vs, br, rb, rg, vp, rt, bt, rr in zip(
                    vol_states, breadth_for_coin, rs, regime, volume_states, ret30, beta, r2
                )
            ],
            index=idx,
            dtype=int,
        )
        out[sym] = pd.DataFrame({
            "vol_state": vol_states,
            "breadth_state": breadth_for_coin,
            "rs_bucket": rs.fillna("mid"),
            "liquidity_bucket": liq.fillna("unknown"),
            "falling_knife_score": knife,
            "knife_bucket": knife.map(falling_knife_bucket),
        }, index=idx)
    return out


def walk_coin(df: pd.DataFrame, signals: list, regime_base: dict,
              cond_base: dict | None = None, member=None,
              mkt_arr=None, mkt_base: dict | None = None,
              trigger: str = "cross_into",
              state_frame: pd.DataFrame | None = None,
              state_base: dict | None = None,
              label: str = "") -> None:
    """Walk one coin day by day. Appends graded crossing signals to `signals`
    and, for *every* day, the forward returns into `regime_base[(regime, h)]`
    (the benchmark each setup is measured against). If `cond_base` is given, also
    records (vol, mom, ret) per day for the conditional (sliced) analysis.

    `member`, if given, is a per-day bool array (point-in-time top-N membership):
    days where the coin was NOT in the universe contribute neither signals nor
    base-rate days, which is what removes survivorship bias. RSI/regime are still
    computed every day so crossing detection stays correct across gaps."""
    if cond_base is None:
        cond_base = defaultdict(list)
    if mkt_base is None:
        mkt_base = defaultdict(list)
    if state_base is None:
        state_base = defaultdict(list)
    closes = df["close"]
    volumes = df["volume"]
    n = len(closes)
    if n < _START + max(HORIZONS) + 1:
        return

    rsi_full = wilder_rsi(closes, config.RSI_PERIOD)
    weekly = closes.resample("W").last().dropna()
    weekly_rsi = wilder_rsi(weekly, config.RSI_PERIOD).dropna()

    # Rolling MAs over the full series: value at t uses exactly the trailing
    # window, so this matches trend_regime() bar-for-bar but far cheaper.
    sma_s = closes.rolling(config.REGIME_SHORT_MA).mean()
    sma_l = closes.rolling(config.REGIME_LONG_MA).mean()

    def regime_at(t: int) -> str:
        sl, ss = sma_l.iloc[t], sma_s.iloc[t]
        if np.isnan(sl) or np.isnan(ss):
            return "UNKNOWN"
        price = closes.iloc[t]
        slope = 0.0
        j = t - config.REGIME_SLOPE_LOOKBACK
        if j >= 0 and not np.isnan(sma_l.iloc[j]):
            slope = sl - sma_l.iloc[j]
        above, aligned = price > sl, ss > sl
        if above and aligned and slope >= 0:
            return "UPTREND"
        if (not above) and (not aligned) and slope <= 0:
            return "DOWNTREND"
        return "RANGE"

    prev_in_ob = prev_in_os = False
    closes_v = closes.to_numpy()
    rsi_v = rsi_full.to_numpy()

    for t in range(_START, n):
        cur_rsi = rsi_v[t]
        if np.isnan(cur_rsi):
            prev_in_ob = prev_in_os = False
            continue
        regime = regime_at(t)
        entry = closes_v[t]

        in_universe = member is None or bool(member[t])
        mkt = str(mkt_arr[t]) if mkt_arr is not None else ""

        # point-in-time conditioning features (no lookahead)
        vol_t = annualized_vol(closes.iloc[max(0, t - VOL_WINDOW):t + 1])
        mom_t = ((closes_v[t] / closes_v[t - MOM_WINDOW] - 1.0) * 100.0
                 if t >= MOM_WINDOW else float("nan"))
        state = {}
        if state_frame is not None:
            ts = closes.index[t]
            if ts in state_frame.index:
                state = state_frame.loc[ts].to_dict()

        # benchmark: forward returns for every in-universe day in this regime
        if in_universe:
            for h in HORIZONS:
                if t + h < n and entry > 0:
                    ret_h = (closes_v[t + h] / entry - 1.0) * 100.0
                    regime_base[(regime, h)].append(ret_h)
                    cond_base[(regime, h)].append((vol_t, mom_t, ret_h))
                    mkt_base[(regime, mkt, h)].append(ret_h)
                    for feature in _STATE_FEATURES:
                        bucket = state.get(feature)
                        if bucket not in (None, "", "unknown"):
                            state_base[(regime, feature, str(bucket), h)].append(ret_h)

        lo = t - LB + 1
        win_rsi = rsi_full.iloc[lo:t + 1].dropna()
        if len(win_rsi) < 30:
            prev_in_ob = prev_in_os = False
            continue
        adapt_ob, adapt_os = adaptive_thresholds(
            win_rsi, config.ADAPTIVE_OB_PERCENTILE, config.ADAPTIVE_OS_PERCENTILE
        )
        eff_ob = min(config.RSI_OB, adapt_ob)
        eff_os = max(config.RSI_OS, adapt_os)

        # Entry trigger. cross_into: the day RSI first pierces the zone (current
        # live behaviour — catches the knife). confirm: the day RSI turns back
        # OUT of the zone (the bounce/rollover has started).
        in_ob = float(cur_rsi) >= eff_ob
        in_os = float(cur_rsi) <= eff_os
        if trigger == "confirm":
            fire_ob = prev_in_ob and not in_ob   # rolled back below overbought
            fire_os = prev_in_os and not in_os    # bounced back above oversold
        else:  # cross_into
            fire_ob = in_ob and not prev_in_ob
            fire_os = in_os and not prev_in_os
        prev_in_ob, prev_in_os = in_ob, in_os

        flag = "OB" if fire_ob else ("OS" if fire_os else "")
        if not flag or not in_universe:
            continue

        setup, exp = setup_for(flag, regime)
        aligned = market_alignment(setup, mkt)
        win_close = closes.iloc[lo:t + 1]
        sig = {
            "flag": flag,
            "severity": _severity(flag, float(cur_rsi)),
            "setup_type": setup,
            "expected_dir": exp,
            "market_aligned": aligned,
            "rsi_4h": None,
            "rsi_weekly": _weekly_asof(weekly_rsi, closes.index[t]),
            "rsi_z": rsi_z_score(win_rsi, config.RSI_Z_WINDOW),
            "volume_ratio": volume_ratio(volumes.iloc[lo:t + 1], config.VOLUME_AVG_WINDOW),
            "divergence": detect_divergence(
                win_close, win_rsi, config.DIVERGENCE_LOOKBACK, config.DIVERGENCE_ORDER
            ),
        }
        conv = conviction_score(sig)
        for h in HORIZONS:
            if t + h >= n or entry <= 0:
                continue
            ret = (closes_v[t + h] / entry - 1.0) * 100.0
            signals.append({
                "setup": setup, "exp": exp, "regime": regime, "h": h,
                "ret": ret, "fav": favorable(exp, ret), "conv": conv,
                "vol": vol_t, "mom": mom_t, "mkt": mkt,
                "ts": closes.index[t], "symbol": label,
                "vol_state": state.get("vol_state"),
                "breadth_state": state.get("breadth_state"),
                "rs_bucket": state.get("rs_bucket"),
                "liquidity_bucket": state.get("liquidity_bucket"),
                "knife_bucket": state.get("knife_bucket"),
                "falling_knife_score": state.get("falling_knife_score"),
            })


# --------------------------------------------------------------------------- #
# Aggregation (pure — unit-tested without network)
# --------------------------------------------------------------------------- #

def _sign(exp: str) -> float:
    return 1.0 if exp == "up" else -1.0


def _base_rates(regime_base: dict) -> tuple[dict, dict]:
    """(base_conf, base_mean): base_conf[(regime, h, dir)] = P(move that dir) on
    any day in that regime; base_mean[(regime, h)] = mean forward return."""
    base_conf, base_mean = {}, {}
    for (regime, h), rets in regime_base.items():
        arr = np.asarray(rets, dtype=float)
        if not len(arr):
            continue
        base_mean[(regime, h)] = float(arr.mean())
        base_conf[(regime, h, "up")] = float((arr > 0).mean())
        base_conf[(regime, h, "down")] = float((arr < 0).mean())
    return base_conf, base_mean


def summarize(signals: list, regime_base: dict, horizons=HORIZONS) -> list[dict]:
    """Per (setup, horizon): n, confirm%, regime base%, edge (confirm-base), raw
    median/avg return, and median *directional excess* return over the regime."""
    base_conf, base_mean = _base_rates(regime_base)
    groups: dict = defaultdict(list)
    for s in signals:
        groups[(s["setup"], s["h"])].append(s)

    rows = []
    for (setup, h), sigs in sorted(groups.items()):
        rets = [s["ret"] for s in sigs]
        conf = 100.0 * statistics.fmean(s["fav"] for s in sigs)
        base = 100.0 * statistics.fmean(
            base_conf.get((s["regime"], h, s["exp"]), 0.0) for s in sigs
        )
        excess = [
            _sign(s["exp"]) * (s["ret"] - base_mean.get((s["regime"], h), 0.0))
            for s in sigs
        ]
        rows.append({
            "setup": setup, "h": h, "n": len(sigs),
            "conf": conf, "base": base, "edge": conf - base,
            "med_ret": statistics.median(rets), "avg_ret": statistics.fmean(rets),
            "med_excess": statistics.median(excess),
        })
    return rows


def _bucket(c: float) -> str:
    return "high (65+)" if c >= 65 else "med (40-64)" if c >= 40 else "low (<40)"


def summarize_by_conviction(signals: list, regime_base: dict, horizon: int) -> list[dict]:
    base_conf, _ = _base_rates(regime_base)
    groups: dict = defaultdict(list)
    for s in signals:
        if s["h"] == horizon:
            groups[_bucket(s["conv"])].append(s)
    order = ["low (<40)", "med (40-64)", "high (65+)"]
    rows = []
    for bucket in order:
        sigs = groups.get(bucket)
        if not sigs:
            continue
        conf = 100.0 * statistics.fmean(s["fav"] for s in sigs)
        base = 100.0 * statistics.fmean(
            base_conf.get((s["regime"], horizon, s["exp"]), 0.0) for s in sigs
        )
        rows.append({"bucket": bucket, "n": len(sigs), "conf": conf,
                     "base": base, "edge": conf - base})
    return rows


def summarize_market(signals: list, mkt_base: dict, horizon: int) -> list[dict]:
    """Per (setup, market regime): confirm% vs a base rate conditioned on the
    SAME (coin-regime, market-regime). This separates bull/bear so a setup that
    only works in one regime can't hide inside a blended average."""
    bconf: dict = {}
    for (regime, mkt, h), rets in mkt_base.items():
        arr = np.asarray(rets, dtype=float)
        if not len(arr):
            continue
        bconf[(regime, mkt, h, "up")] = float((arr > 0).mean())
        bconf[(regime, mkt, h, "down")] = float((arr < 0).mean())

    groups: dict = defaultdict(list)
    for s in signals:
        if s["h"] == horizon and s.get("mkt") not in (None, "", "NA"):
            groups[(s["setup"], s["mkt"])].append(s)

    rows = []
    for (setup, mkt), sigs in sorted(groups.items()):
        conf = 100.0 * statistics.fmean(s["fav"] for s in sigs)
        base = 100.0 * statistics.fmean(
            bconf.get((s["regime"], mkt, horizon, s["exp"]), 0.0) for s in sigs
        )
        rows.append({"setup": setup, "mkt": mkt, "n": len(sigs), "conf": conf,
                     "base": base, "edge": conf - base,
                     "med": statistics.median(s["ret"] for s in sigs)})
    return rows


def summarize_state_slices(
    signals: list,
    state_base: dict,
    horizon: int = PRIMARY,
    *,
    min_n: int = 8,
    setup: str | None = None,
) -> list[dict]:
    """Per setup x state bucket edge vs same-regime, same-state base days."""
    bconf: dict = {}
    for (regime, feature, bucket, h), rets in state_base.items():
        if h != horizon:
            continue
        arr = np.asarray(rets, dtype=float)
        if not len(arr):
            continue
        bconf[(regime, feature, bucket, h, "up")] = float((arr > 0).mean())
        bconf[(regime, feature, bucket, h, "down")] = float((arr < 0).mean())

    groups: dict = defaultdict(list)
    for s in signals:
        if s["h"] != horizon:
            continue
        if setup and s["setup"] != setup:
            continue
        for feature in _STATE_FEATURES:
            bucket = s.get(feature)
            if bucket not in (None, "", "unknown"):
                groups[(feature, str(bucket), s["setup"])].append(s)

    rows = []
    for (feature, bucket, setup_name), sigs in groups.items():
        if len(sigs) < min_n:
            continue
        conf = 100.0 * statistics.fmean(s["fav"] for s in sigs)
        base = 100.0 * statistics.fmean(
            bconf.get((s["regime"], feature, bucket, horizon, s["exp"]), 0.0)
            for s in sigs
        )
        base_cells = {(s["regime"], feature, bucket, horizon) for s in sigs}
        base_n = sum(len(state_base.get(cell, [])) for cell in base_cells)
        rows.append({
            "feature": feature,
            "bucket": bucket,
            "setup": setup_name,
            "n": len(sigs),
            "base_n": base_n,
            "conf": conf,
            "base": base,
            "edge": conf - base,
            "med": statistics.median(s["ret"] for s in sigs),
            "med_dir": statistics.median(_dir_ret(s) for s in sigs),
        })
    return sorted(rows, key=lambda r: (_state_feature_order(r["feature"], r["bucket"]), r["setup"]))


_STATE_BUCKET_ORDER = {
    "vol_state": ("low_compressed", "normal", "high", "high_expanding", "crisis"),
    "breadth_state": (
        "breadth_collapse", "washout", "washout_recovery", "neutral",
        "risk_on_narrow", "risk_on_broad",
    ),
    "rs_bucket": ("low", "mid", "high"),
    "liquidity_bucket": ("low", "mid", "high"),
    "knife_bucket": ("low", "elevated", "high"),
}


def _state_feature_order(feature: str, bucket: str) -> tuple:
    feature_order = list(_STATE_FEATURES).index(feature) if feature in _STATE_FEATURES else 99
    buckets = _STATE_BUCKET_ORDER.get(feature, ())
    bucket_order = buckets.index(bucket) if bucket in buckets else 99
    return feature_order, bucket_order, bucket


# --------------------------------------------------------------------------- #
# Backtest-to-registry calibration
# --------------------------------------------------------------------------- #

CALIBRATION_SCHEMA = 1
CALIBRATION_MAX_SWING = 18
CALIBRATION_MIN_PRIOR = 5
CALIBRATION_MAX_PRIOR = 90


def _clamp_prior(v: int) -> int:
    return max(CALIBRATION_MIN_PRIOR, min(CALIBRATION_MAX_PRIOR, v))


def _calibrated_prior(default: int, edge_pct: float, n: int, min_samples: int) -> int:
    """Move a registry prior toward measured edge, but only cautiously.

    `edge_pct` is confirm-rate minus same-regime base rate in percentage points.
    The conversion is deliberately damped and sample-size scaled so small or
    noisy backtests do not rewrite live conviction too aggressively.
    """
    if n < min_samples:
        return default
    confidence = min(1.0, n / max(1, 4 * min_samples))
    raw_delta = max(-CALIBRATION_MAX_SWING, min(CALIBRATION_MAX_SWING, edge_pct * 0.45))
    return _clamp_prior(int(round(default + raw_delta * confidence)))


def build_registry_prior_export(
    signals: list,
    mkt_base: dict,
    *,
    n_coins: int,
    days: int,
    source: str,
    pit: bool = False,
    trigger: str = "cross_into",
    horizon: int = PRIMARY,
    min_samples: int = 8,
) -> dict:
    """Build a registry calibration artifact from a completed backtest run.

    The artifact is machine-readable by `signal_registry.load_prior_overrides`,
    but still includes evidence cells so a human can review what moved.
    """
    rows = summarize_market(signals, mkt_base, horizon)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    evidence_by_setup: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        setup_type = r["setup"]
        alignment = market_alignment(setup_type, r["mkt"])
        cell = {
            "market_regime": r["mkt"],
            "canonical_market_regime": canonical_market_regime(r["mkt"]),
            "alignment": alignment,
            "n": int(r["n"]),
            "confirm_pct": round(float(r["conf"]), 2),
            "base_pct": round(float(r["base"]), 2),
            "edge_pct": round(float(r["edge"]), 2),
            "median_return_pct": round(float(r["med"]), 4),
            "used": bool(r["n"] >= min_samples),
        }
        grouped[(setup_type, alignment)].append(cell)
        evidence_by_setup[setup_type].append(cell)

    payload = {
        "schema": CALIBRATION_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "primary_horizon_days": horizon,
        "min_samples": min_samples,
        "run": {
            "source": source,
            "days": days,
            "n_coins": n_coins,
            "pit": pit,
            "trigger": trigger,
            "graded_observations": len(signals),
        },
        "setups": {},
    }

    for setup_type, setup in SETUPS.items():
        calibrated = dict(setup.edge_priors)
        notes: list[str] = []
        if setup.has_edge:
            for alignment in ("favorable", "neutral", "adverse"):
                cells = grouped.get((setup_type, alignment), [])
                used = [c for c in cells if c["used"]]
                if not used:
                    continue
                n = sum(c["n"] for c in used)
                edge = sum(c["edge_pct"] * c["n"] for c in used) / n
                calibrated[alignment] = _calibrated_prior(
                    setup.edge_priors[alignment], edge, n, min_samples
                )
        else:
            notes.append("context_only_no_edge_not_auto_promoted")

        payload["setups"][setup_type] = {
            "label": setup.label,
            "has_edge": setup.has_edge,
            "default_edge_priors": dict(setup.edge_priors),
            "edge_priors": calibrated,
            "evidence": sorted(
                evidence_by_setup.get(setup_type, []),
                key=lambda c: (c["alignment"], c["market_regime"]),
            ),
        }
        if notes:
            payload["setups"][setup_type]["notes"] = notes
    return payload


def write_registry_prior_export(path: str | Path, payload: dict) -> Path:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def format_market(signals: list, mkt_base: dict, horizon: int) -> str:
    cov: dict = defaultdict(int)
    for (regime, mkt, h), rets in mkt_base.items():
        if h == horizon and mkt not in ("", "NA"):
            cov[mkt] += len(rets)
    coverage = "  ".join(f"{m}:{cov[m]}" for m in ("BULL", "CHOP", "BEAR") if cov.get(m))

    out = [f"\nMarket-regime coverage ({horizon}d base-days): {coverage or 'none'}"]
    out.append(f"By setup × MARKET regime at {horizon}d (BTC bull/bear/chop):")
    out.append(f"  {'setup':<19}{'mkt':<6}{'n':>5}{'conf%':>7}{'base%':>7}{'edge':>7}{'medRet':>9}")
    for r in summarize_market(signals, mkt_base, horizon):
        out.append(f"  {r['setup']:<19}{r['mkt']:<6}{r['n']:>5}{r['conf']:>6.0f}%"
                   f"{r['base']:>6.0f}%{r['edge']:>+6.0f}{r['med']:>8.1f}%")
    return "\n".join(out)


def format_state_slices(
    signals: list,
    state_base: dict,
    horizon: int = PRIMARY,
    *,
    min_n: int = 8,
    setup: str | None = None,
) -> str:
    rows = summarize_state_slices(
        signals, state_base, horizon, min_n=min_n, setup=setup
    )
    out = [
        "\nState-conditioned edge slices "
        f"at {horizon}d (base = same coin-regime + same state bucket):"
    ]
    if not rows:
        out.append(f"  No state buckets met min_n={min_n}. Try more days/coins.")
        return "\n".join(out)

    out.append(f"  {'feature':<25}{'bucket':<20}{'setup':<19}"
               f"{'n':>5}{'baseN':>7}{'conf%':>7}{'base%':>7}"
               f"{'edge':>7}{'medRet':>9}{'medDir':>9}")
    for r in rows:
        label = _STATE_FEATURES.get(r["feature"], r["feature"])
        out.append(
            f"  {label:<25}{r['bucket']:<20}{r['setup']:<19}"
            f"{r['n']:>5}{r['base_n']:>7}{r['conf']:>6.0f}%"
            f"{r['base']:>6.0f}%{r['edge']:>+6.0f}"
            f"{r['med']:>8.1f}%{r['med_dir']:>+8.1f}%"
        )
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Trigger A/B (cross-into the zone vs confirm on the turn out)
# --------------------------------------------------------------------------- #

def _dir_ret(s: dict) -> float:
    """Direction-adjusted return: positive = price moved the setup's way."""
    return s["ret"] if s["exp"] == "up" else -s["ret"]


def _actionable_summary(signals: list, horizon: int) -> dict | None:
    """Tradeable book: edge-bearing setups in a non-adverse market regime — the
    same filter the live gating uses. win% and direction-adjusted PnL."""
    rows = [s for s in signals if s["h"] == horizon
            and setup_has_edge(s["setup"])
            and market_alignment(s["setup"], s["mkt"]) != "adverse"]
    if not rows:
        return None
    pnl = [_dir_ret(s) for s in rows]
    return {"n": len(rows), "win": 100.0 * statistics.fmean(s["fav"] for s in rows),
            "avg": statistics.fmean(pnl), "med": statistics.median(pnl)}


def _liquidity_slippage_multiplier(bucket: str | None) -> float:
    return {"high": 0.5, "mid": 1.0, "low": 2.0}.get(str(bucket or ""), 1.25)


def _cost_adjusted_return(signal: dict, fee_bps: float, slippage_bps: float) -> float:
    """Direction-adjusted return after a simple round-trip fee/slippage model."""
    slip = slippage_bps * _liquidity_slippage_multiplier(signal.get("liquidity_bucket"))
    return _dir_ret(signal) - (fee_bps + slip) / 100.0


def _cost_stats(rows: list[dict], fee_bps: float, slippage_bps: float) -> dict | None:
    if not rows:
        return None
    net = [_cost_adjusted_return(s, fee_bps, slippage_bps) for s in rows]
    ordered = sorted(rows, key=lambda s: (str(s.get("ts") or ""), str(s.get("symbol") or "")))
    eq, peak, maxdd = 1.0, 1.0, 0.0
    for s in ordered:
        eq *= 1.0 + _cost_adjusted_return(s, fee_bps, slippage_bps) / 100.0
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak if peak > 0 else 0.0)
    wins = sum(1 for r in net if r > 0)
    return {
        "n": len(net),
        "win": 100.0 * wins / len(net),
        "avg": statistics.fmean(net),
        "med": statistics.median(net),
        "equity": (eq - 1.0) * 100.0,
        "maxdd": 100.0 * maxdd,
    }


def _cap_trades_per_day(rows: list[dict], max_trades_per_day: int | None) -> list[dict]:
    if not max_trades_per_day or max_trades_per_day <= 0:
        return rows
    chosen: list[dict] = []
    by_day: dict[str, list[dict]] = defaultdict(list)
    for s in rows:
        ts = pd.Timestamp(s.get("ts")) if s.get("ts") is not None else pd.NaT
        day = "unknown" if pd.isna(ts) else ts.date().isoformat()
        by_day[day].append(s)
    for day in sorted(by_day):
        ranked = sorted(by_day[day], key=lambda s: (s.get("conv") or 0), reverse=True)
        chosen.extend(ranked[:max_trades_per_day])
    return chosen


def _format_cost_row(label: str, st: dict | None) -> str:
    if not st:
        return f"  {label:<22} (no signals)"
    return (
        f"  {label:<22}{st['n']:>5}{st['win']:>6.0f}%"
        f"{st['avg']:>+8.2f}%{st['med']:>+8.2f}%"
        f"{st['equity']:>+9.1f}%{st['maxdd']:>7.0f}%"
    )


def format_cost_report(
    signals: list,
    *,
    horizon: int = PRIMARY,
    fee_bps: float = 10.0,
    slippage_bps: float = 20.0,
    max_trades_per_day: int | None = None,
) -> str:
    """Cost-aware, direction-adjusted performance for the backtest signals."""
    crossed = [s for s in signals if s["h"] == horizon]
    actionable = [
        s for s in crossed
        if setup_has_edge(s["setup"]) and market_alignment(s["setup"], s.get("mkt")) != "adverse"
    ]
    control = [s for s in crossed if s not in actionable]
    actionable = _cap_trades_per_day(actionable, max_trades_per_day)

    out = [
        f"\nCost-aware backtest book at {horizon}d:",
        f"  cost = {fee_bps:.1f} bps fee + liquidity-scaled {slippage_bps:.1f} bps slippage",
    ]
    if max_trades_per_day:
        out.append(f"  cap = top {max_trades_per_day} actionable signal(s) per day by conviction")
    out.append(f"  {'book/setup':<22}{'n':>5}{'win%':>7}{'avgNet':>9}{'medNet':>9}{'equity':>10}{'maxDD':>7}")
    out.append(_format_cost_row("all", _cost_stats(crossed, fee_bps, slippage_bps)))
    out.append(_format_cost_row("actionable", _cost_stats(actionable, fee_bps, slippage_bps)))
    out.append(_format_cost_row("control", _cost_stats(control, fee_bps, slippage_bps)))

    setups = sorted({s["setup"] for s in actionable})
    if setups:
        out.append("  -- actionable by setup --")
        for setup in setups:
            rows = [s for s in actionable if s["setup"] == setup]
            out.append(_format_cost_row(setup, _cost_stats(rows, fee_bps, slippage_bps)))
    return "\n".join(out)


def _time_folds(signals: list, folds: int, horizon: int) -> list[list[dict]]:
    rows = sorted([s for s in signals if s["h"] == horizon and s.get("ts") is not None],
                  key=lambda s: pd.Timestamp(s["ts"]))
    if folds < 2 or len(rows) < folds:
        return []
    size = max(1, len(rows) // folds)
    out = [rows[i * size:(i + 1) * size] for i in range(folds - 1)]
    out.append(rows[(folds - 1) * size:])
    return [f for f in out if f]


def _setup_confirm(rows: list[dict], setup: str) -> dict | None:
    sub = [s for s in rows if s["setup"] == setup]
    if not sub:
        return None
    return {
        "n": len(sub),
        "conf": 100.0 * statistics.fmean(s["fav"] for s in sub),
        "med_dir": statistics.median(_dir_ret(s) for s in sub),
    }


def format_walk_forward(signals: list, *, horizon: int = PRIMARY, folds: int = 4) -> str:
    """Simple time-split check: do setup hit-rates persist into the next fold?"""
    split = _time_folds(signals, folds, horizon)
    out = [f"\nWalk-forward setup stability at {horizon}d ({len(split)} time folds):"]
    if len(split) < 2:
        out.append("  Not enough timestamped signals for walk-forward analysis.")
        return "\n".join(out)
    out.append("  Train = all earlier folds; test = next chronological fold.")
    out.append(f"  {'fold':<6}{'setup':<19}{'trainN':>7}{'train%':>8}{'testN':>7}{'test%':>8}{'testMed':>9}")
    setups = sorted({s["setup"] for s in signals if s["h"] == horizon})
    for i in range(1, len(split)):
        train = [s for f in split[:i] for s in f]
        test = split[i]
        for setup in setups:
            tr = _setup_confirm(train, setup)
            te = _setup_confirm(test, setup)
            if not tr or not te:
                continue
            out.append(
                f"  {i:<6}{setup:<19}{tr['n']:>7}{tr['conf']:>7.0f}%"
                f"{te['n']:>7}{te['conf']:>7.0f}%{te['med_dir']:>+8.1f}%"
            )
    return "\n".join(out)


def format_trigger_comparison(results: dict, horizons=(3, PRIMARY)) -> str:
    out = ["=" * 64,
           "TRIGGER A/B — enter on the TURN (confirm) vs the pierce (cross-in)",
           "edge = setup confirm% − same-regime base%; PnL = direction-adjusted",
           "=" * 64]

    out.append(f"\nActionable book @ {PRIMARY}d (edge-bearing, non-adverse regime):")
    out.append(f"  {'trigger':<12}{'n':>6}{'win%':>7}{'avgPnL':>9}{'medPnL':>9}")
    for trig, res in results.items():
        st = _actionable_summary(res[0], PRIMARY)
        out.append(f"  {trig:<12}{st['n']:>6}{st['win']:>6.0f}%{st['avg']:>+8.1f}%{st['med']:>+8.1f}%"
                   if st else f"  {trig:<12}  (no signals)")

    for h in horizons:
        summ = {trig: {r["setup"]: r for r in summarize(res[0], res[1]) if r["h"] == h}
                for trig, res in results.items()}
        setups = sorted({s for d in summ.values() for s in d})
        out.append(f"\nPer-setup edge @ {h}d  (n / edge per trigger):")
        out.append("  " + f"{'setup':<19}" + "".join(f"{t:>16}" for t in results))
        for s in setups:
            line = f"  {s:<19}"
            for trig in results:
                r = summ[trig].get(s)
                line += f"{(str(r['n'])+'/'+format(r['edge'],'+.0f')):>16}" if r else f"{'—':>16}"
            out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Conditional slice — "WHEN does a setup's expected direction hold?"
# --------------------------------------------------------------------------- #

def _isnan(x) -> bool:
    return isinstance(x, float) and math.isnan(x)


def conditional_table(
    signals: list, cond_base: dict, setup: str, regime: str, expected_dir: str,
    horizon: int, feature: str, min_n: int = 8,
) -> tuple | None:
    """Slice one setup by a point-in-time feature (vol/mom) into terciles, and
    within each bucket compare the signal's confirm-rate to a base rate
    conditioned on the SAME bucket. This avoids re-introducing the tautology:
    if high-vol downtrend days all fall anyway, a high signal confirm% in that
    bucket still shows ~0 edge. Returns ((q1, q2), rows) or None."""
    fi = _FEATURE_IDX[feature]
    sig = [s for s in signals
           if s["setup"] == setup and s["h"] == horizon and not _isnan(s[feature])]
    if len(sig) < 3 * min_n:
        return None
    base = [b for b in cond_base.get((regime, horizon), []) if not _isnan(b[fi])]

    vals = sorted(s[feature] for s in sig)
    q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    bounds = [(float("-inf"), q1), (q1, q2), (q2, float("inf"))]
    confirms = (lambda r: r < 0) if expected_dir == "down" else (lambda r: r > 0)

    rows = []
    for lo, hi in bounds:
        ss = [s for s in sig if lo <= s[feature] < hi]
        bb = [b for b in base if lo <= b[fi] < hi]
        if len(ss) < min_n:
            rows.append(None)
            continue
        rows.append({
            "n": len(ss),
            "sig": 100.0 * statistics.fmean(confirms(s["ret"]) for s in ss),
            "base": (100.0 * statistics.fmean(confirms(b[2]) for b in bb)
                     if bb else float("nan")),
            "med": statistics.median(s["ret"] for s in ss),
        })
    if all(r is None for r in rows):
        return None
    for r in rows:
        if r is not None:
            r["edge"] = float("nan") if _isnan(r["base"]) else r["sig"] - r["base"]
    return (q1, q2), rows


def _range_str(name: str, q1: float, q2: float, feature: str) -> str:
    fmt = (lambda v: f"{v:.2f}") if feature == "vol" else (lambda v: f"{v:+.0f}%")
    if name == "low":
        return f"<{fmt(q1)}"
    if name == "high":
        return f">{fmt(q2)}"
    return f"{fmt(q1)}…{fmt(q2)}"


def format_conditional(setup: str, regime: str, feature: str, horizon: int,
                       result: tuple) -> str:
    (q1, q2), rows = result
    out = [f"\n{setup} in {regime.lower()} by {_FEATURE_LABEL[feature]} "
           f"(terciles), {horizon}d horizon:"]
    out.append(f"  {'bucket':<7}{'range':<14}{'n':>5}{'conf%':>7}{'base%':>7}{'edge':>7}{'medRet':>9}")
    for name, r in zip(("low", "mid", "high"), rows):
        if not r:
            continue
        base = "  n/a" if _isnan(r["base"]) else f"{r['base']:>6.0f}%"
        edge = "   n/a" if _isnan(r["edge"]) else f"{r['edge']:>+6.0f}"
        out.append(f"  {name:<7}{_range_str(name, q1, q2, feature):<14}{r['n']:>5}"
                   f"{r['sig']:>6.0f}%{base}{edge}{r['med']:>8.1f}%")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def format_report(signals: list, regime_base: dict, n_coins: int, days: int,
                  source: str = "Binance 1d klines", pit: bool = False) -> str:
    out: list[str] = ["=" * 64, "RSI BACKTEST — setup edge vs regime base rate"]
    out.append(f"Universe: {n_coins} coins · {days}d {source} · "
               f"{len(signals)} graded obs")
    out.append("Edge = signal confirm% minus the SAME regime's base confirm%.")
    out.append("A high confirm% with ~0 edge is just 'trends trend', not signal.")
    out.append("=" * 64)

    if not signals:
        out.append("\nNo signals generated — no usable price history fetched.")
        out.append("Try --symbols BTC,ETH,SOL or check Binance reachability.")
        return "\n".join(out)

    out.append("\nBy setup × horizon (confirm = moved the expected way):")
    out.append(f"  {'setup':<19}{'h':>4}{'n':>6}{'conf%':>7}{'base%':>7}"
               f"{'edge':>7}{'medRet':>8}{'medExc':>8}")
    for r in summarize(signals, regime_base):
        out.append(
            f"  {r['setup']:<19}{str(r['h'])+'d':>4}{r['n']:>6}"
            f"{r['conf']:>6.0f}%{r['base']:>6.0f}%{r['edge']:>+6.0f}"
            f"{r['med_ret']:>7.1f}%{r['med_excess']:>+7.1f}"
        )

    out.append("\nRegime base rates (any day; P = moved that way over h):")
    out.append(f"  {'regime':<11}{'h':>4}{'n':>7}{'P(up)':>7}{'P(down)':>9}{'medRet':>8}")
    for (regime, h) in sorted(regime_base):
        arr = np.asarray(regime_base[(regime, h)], dtype=float)
        if not len(arr):
            continue
        out.append(
            f"  {regime:<11}{str(h)+'d':>4}{len(arr):>7}"
            f"{100*(arr>0).mean():>6.0f}%{100*(arr<0).mean():>8.0f}%"
            f"{np.median(arr):>7.1f}%"
        )

    conv_rows = summarize_by_conviction(signals, regime_base, PRIMARY)
    if conv_rows:
        out.append(f"\nBy conviction at {PRIMARY}d (does the score earn its edge?):")
        out.append(f"  {'bucket':<12}{'n':>6}{'conf%':>7}{'base%':>7}{'edge':>7}")
        for r in conv_rows:
            out.append(f"  {r['bucket']:<12}{r['n']:>6}{r['conf']:>6.0f}%"
                       f"{r['base']:>6.0f}%{r['edge']:>+6.0f}")

    out.append("\n" + "=" * 64)
    if pit:
        out.append("Point-in-time top-N (survivorship-reduced). Residual bias:")
        out.append("coins that fell below the candidate pool floor still vanish.")
    else:
        out.append("Caveats: survivorship (today's top-N), single venue, no fees.")
    out.append("Edge > 0 means the RSI entry beat just being in that regime.")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Point-in-time universe (survivorship fix)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Point-in-time universe by VOLUME RANK (no CoinGecko Pro key needed)
# --------------------------------------------------------------------------- #
# The mcap-based PIT path is capped at 365d by the CoinGecko demo key — a
# bear-only window that can't validate bull/chop rules. Binance klines are free
# for ~5y and carry quote (USDT) volume, so we define membership as "top-N by
# trailing dollar volume on each date": fully point-in-time, and arguably a
# better *tradeable-universe* definition than market cap. Residual biases:
# single venue, USDT pairs only (coins are invisible before their Binance
# listing), and fully-delisted pairs are absent from today's exchangeInfo.

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


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

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


def _validate_cli_args(p: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.top_n < 1:
        p.error("--top-n must be >= 1")
    if args.days < 1:
        p.error("--days must be >= 1")
    if args.pool < 1:
        p.error("--pool must be >= 1")
    if args.volume_window < 1:
        p.error("--volume-window must be >= 1")
    if args.max_trades_per_day < 0:
        p.error("--max-trades-per-day must be >= 0")
    if args.walk_forward_folds < 2:
        p.error("--walk-forward-folds must be >= 2")
    if args.pit and args.pit_volume:
        p.error("--pit and --pit-volume are mutually exclusive")
    if args.compare_triggers and args.pit:
        p.error("--compare-triggers is not supported with --pit; use --pit-volume or the default Binance path")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Backtest RSI setups vs regime base rates.")
    p.add_argument("--top-n", type=int, default=80, help="Top-N coins by mcap.")
    p.add_argument("--days", type=int, default=1460,
                   help="History length in days (Binance paginates; ~1460 = 4y "
                        "spans the 2022 bear. CoinGecko/PIT capped at 365 on a demo key).")
    p.add_argument("--symbols", default=None, help="Comma list to override the universe.")
    p.add_argument("--pit", action="store_true",
                   help="Point-in-time universe (fixes survivorship; uses CoinGecko "
                        "price+market-cap history instead of Binance).")
    p.add_argument("--pit-volume", action="store_true",
                   help="Point-in-time universe by trailing dollar-VOLUME rank over "
                        "the full Binance USDT pool — 5y history with no CoinGecko "
                        "Pro key. Ignores --pool/--symbols (whole pool).")
    p.add_argument("--volume-window", type=int, default=VOLUME_MEMBERSHIP_WINDOW,
                   help="Trailing window (days) for --pit-volume membership rank.")
    p.add_argument("--pool", type=int, default=150,
                   help="PIT candidate pool size (bigger = less survivorship, slower).")
    p.add_argument("--pit-cache-dir", default=str(config.BACKTEST_CACHE_DIR),
                   help="Directory for cached CoinGecko PIT market_chart JSON.")
    p.add_argument("--no-pit-cache", action="store_true",
                   help="Disable the CoinGecko PIT history cache for this run.")
    p.add_argument("--refresh-pit-cache", action="store_true",
                   help="Refetch PIT histories even when cached JSON exists.")
    p.add_argument("--fixture-dir", default=None,
                   help="Load Binance-path OHLC CSV fixtures instead of network. "
                        "Ignored in --pit mode.")
    p.add_argument("--slice", default=None,
                   help="Conditionally slice one setup by vol/momentum: "
                        f"{', '.join(_SETUP_REGIME)}.")
    p.add_argument("--slice-horizons", default="1,3,7",
                   help="Horizons (days) to show in the slice, comma-separated.")
    p.add_argument("--state-slices", action="store_true",
                   help="Show setup edge by shadow state buckets: volatility, "
                        "breadth, relative strength, liquidity, and falling-knife risk.")
    p.add_argument("--state-min-samples", type=int, default=8,
                   help="Minimum signals needed to print a state-slice row.")
    p.add_argument("--costs", action="store_true",
                   help="Print a cost/slippage-aware actionable-book report.")
    p.add_argument("--fee-bps", type=float, default=10.0,
                   help="Round-trip fee in basis points for --costs.")
    p.add_argument("--slippage-bps", type=float, default=20.0,
                   help="Base round-trip slippage bps for --costs; scaled by liquidity bucket when available.")
    p.add_argument("--max-trades-per-day", type=int, default=0,
                   help="For --costs, keep only top-N actionable signals per day by conviction.")
    p.add_argument("--walk-forward", action="store_true",
                   help="Print chronological setup stability folds for the primary horizon.")
    p.add_argument("--walk-forward-folds", type=int, default=4,
                   help="Number of chronological folds for --walk-forward.")
    p.add_argument("--trigger", choices=("cross_into", "confirm"), default="cross_into",
                   help="Entry: cross_into (pierce the zone, default) or confirm (turn back out).")
    p.add_argument("--compare-triggers", action="store_true",
                   help="A/B both triggers on the same data; supports default Binance path or --pit-volume.")
    p.add_argument("--export-priors", default=None, metavar="PATH",
                   help="Write a registry prior calibration JSON from this backtest.")
    p.add_argument("--prior-min-samples", type=int, default=8,
                   help="Minimum setup x market samples needed to move a prior.")
    p.add_argument("--min-signals", type=int, default=0,
                   help="Exit non-zero if fewer than this many graded observations are produced.")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    _validate_cli_args(p, args)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S",
    )

    if args.compare_triggers:
        if args.export_priors:
            log.warning("--export-priors is ignored with --compare-triggers")
        pit_cache_dir = None if args.no_pit_cache else Path(args.pit_cache_dir).expanduser()
        if args.pit_volume:
            if args.fixture_dir:
                log.warning("--fixture-dir is ignored with --pit-volume")
            log.info("Volume-PIT trigger A/B: top-%d by trailing %dd volume (%dd history)...",
                     args.top_n, args.volume_window, args.days)
            results, ok = run_pit_volume_triggers(
                args.top_n,
                args.days,
                cache_dir=pit_cache_dir,
                refresh_cache=args.refresh_pit_cache,
                volume_window=args.volume_window,
            )
        elif args.symbols:
            universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
            log.info("Trigger A/B on %d symbols (%dd, paginated)...", len(universe), args.days)
            results, ok = run_triggers(universe, args.days, fixture_dir=args.fixture_dir)
        elif args.fixture_dir:
            universe = fixture_symbols(args.fixture_dir)[:args.top_n]
            log.info("Trigger A/B on %d symbols (%dd, paginated)...", len(universe), args.days)
            results, ok = run_triggers(universe, args.days, fixture_dir=args.fixture_dir)
        else:
            universe = cg_top_symbols(args.top_n)
            log.info("Trigger A/B on %d symbols (%dd, paginated)...", len(universe), args.days)
            results, ok = run_triggers(universe, args.days, fixture_dir=args.fixture_dir)
        log.info("Done: %d usable coins", ok)
        print("\n" + format_trigger_comparison(results) + "\n")
        return

    if args.pit_volume:
        if args.fixture_dir:
            log.warning("--fixture-dir is ignored with --pit-volume")
        pit_cache_dir = None if args.no_pit_cache else Path(args.pit_cache_dir).expanduser()
        log.info("Volume-PIT mode: top-%d by trailing %dd dollar volume, %dd history...",
                 args.top_n, args.volume_window, args.days)
        signals, regime_base, cond_base, mkt_base, state_base, ok = run_pit_volume(
            args.top_n,
            args.days,
            args.trigger,
            state_slices=args.state_slices,
            cache_dir=pit_cache_dir,
            refresh_cache=args.refresh_pit_cache,
            volume_window=args.volume_window,
        )
        source = f"Binance 1d klines (PIT top-N by {args.volume_window}d volume)"
        report_days = args.days
    elif args.pit:
        if args.fixture_dir:
            log.warning("--fixture-dir is ignored with --pit")
        pool = cg_top_coins(args.pool)
        if not pool:
            print("PIT mode needs CoinGecko, but the universe fetch failed.")
            return
        days = args.days
        if config.COINGECKO_KEY_TYPE != "pro":
            days = min(days, 365)
            log.info("Demo/free CoinGecko key: capping history at 365d "
                     "(a pro key extends this).")
        pit_cache_dir = None if args.no_pit_cache else Path(args.pit_cache_dir).expanduser()
        log.info("PIT mode: pool=%d, top-%d membership, %dd CoinGecko history...",
                 len(pool), args.top_n, days)
        signals, regime_base, cond_base, mkt_base, state_base, ok = run_pit(
            pool,
            args.top_n,
            days,
            args.trigger,
            state_slices=args.state_slices,
            cache_dir=pit_cache_dir,
            refresh_cache=args.refresh_pit_cache,
        )
        source, report_days = "CoinGecko daily (point-in-time top-N)", days
    else:
        if args.symbols:
            universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        elif args.fixture_dir:
            universe = fixture_symbols(args.fixture_dir)[:args.top_n]
        else:
            universe = cg_top_symbols(args.top_n)
        source = "fixture Binance 1d klines" if args.fixture_dir else "Binance 1d klines"
        log.info("Universe: %d symbols; fetching %s (%dd, paginated, %s)...",
                 len(universe), source, args.days, args.trigger)
        signals, regime_base, cond_base, mkt_base, state_base, ok = run(
            universe, args.days, args.trigger, state_slices=args.state_slices,
            fixture_dir=args.fixture_dir)
        report_days = args.days

    log.info("Usable history: %d coins; %d graded observations", ok, len(signals))
    is_pit = args.pit or args.pit_volume
    print("\n" + format_report(signals, regime_base, ok, report_days,
                                source=source, pit=is_pit) + "\n")
    if mkt_base:
        print(format_market(signals, mkt_base, PRIMARY))
        print(format_market(signals, mkt_base, 1))
    if args.state_slices:
        print(format_state_slices(
            signals, state_base, PRIMARY, min_n=args.state_min_samples,
            setup=args.slice,
        ))
    if args.costs:
        print(format_cost_report(
            signals,
            horizon=PRIMARY,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
            max_trades_per_day=args.max_trades_per_day or None,
        ))
    if args.walk_forward:
        print(format_walk_forward(
            signals,
            horizon=PRIMARY,
            folds=args.walk_forward_folds,
        ))

    if args.export_priors:
        payload = build_registry_prior_export(
            signals,
            mkt_base,
            n_coins=ok,
            days=report_days,
            source=source,
            pit=is_pit,
            trigger=args.trigger,
            min_samples=args.prior_min_samples,
        )
        out = write_registry_prior_export(args.export_priors, payload)
        log.info("Wrote registry prior calibration: %s", out)

    if args.min_signals and len(signals) < args.min_signals:
        raise SystemExit(
            f"Backtest produced {len(signals)} graded observations; "
            f"expected at least {args.min_signals}."
        )

    if args.slice:
        sr = _SETUP_REGIME.get(args.slice)
        if not sr:
            print(f"--slice supports: {', '.join(_SETUP_REGIME)}")
            return
        regime, exp = sr
        horizons = [int(h) for h in args.slice_horizons.split(",") if h.strip()]
        print("=" * 64)
        print(f"CONDITIONAL SLICE — when does '{args.slice}' (expect {exp}) hold?")
        print("=" * 64)
        for feature in ("vol", "mom"):
            for h in horizons:
                res = conditional_table(signals, cond_base, args.slice, regime, exp, h, feature)
                if res:
                    print(format_conditional(args.slice, regime, feature, h, res))
        print()


if __name__ == "__main__":
    main()
