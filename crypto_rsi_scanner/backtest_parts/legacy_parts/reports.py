"""Split implementation for `crypto_rsi_scanner/backtest_parts/legacy.py` (reports)."""

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
