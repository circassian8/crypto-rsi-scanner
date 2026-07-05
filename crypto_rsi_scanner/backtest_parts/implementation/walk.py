"""Split implementation for `crypto_rsi_scanner/backtest_parts/api.py` (walk)."""

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
from .data import *  # noqa: F403

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
    denom = valid.sum(axis=1).astype("float64").mask(lambda row: row == 0, np.nan)
    numerator = values.where(valid).astype("float64").sum(axis=1)
    out = numerator / denom
    return out.mask(~np.isfinite(out), np.nan)
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


def _append_backtest_signal_rows(
    signals: list,
    *,
    closes: pd.Series,
    closes_v: np.ndarray,
    t: int,
    n: int,
    entry: float,
    setup: str,
    exp: str,
    regime: str,
    conv: int,
    vol_t: float,
    mom_t: float,
    mkt: str,
    label: str,
    state: dict,
) -> None:
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


def _regime_at(closes: pd.Series, sma_l: pd.Series, sma_s: pd.Series, t: int) -> str:
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

    prev_in_ob = prev_in_os = False
    closes_v = closes.to_numpy()
    rsi_v = rsi_full.to_numpy()

    for t in range(_START, n):
        cur_rsi = rsi_v[t]
        if np.isnan(cur_rsi):
            prev_in_ob = prev_in_os = False
            continue
        regime = _regime_at(closes, sma_l, sma_s, t)
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
        _append_backtest_signal_rows(
            signals,
            closes=closes,
            closes_v=closes_v,
            t=t,
            n=n,
            entry=entry,
            setup=setup,
            exp=exp,
            regime=regime,
            conv=conv,
            vol_t=vol_t,
            mom_t=mom_t,
            mkt=mkt,
            label=label,
            state=state,
        )
