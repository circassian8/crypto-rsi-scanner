"""Split implementation for `crypto_rsi_scanner/backtest_parts/api.py` (risk)."""

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
# Shared globals are injected by the package initializer after import.
from .data import *  # noqa: F403

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
def _setup_market_edge(
    rows: list[dict],
    setup: str,
    mkt: str,
    bconf: dict,
    horizon: int,
) -> dict | None:
    sub = [
        s for s in rows
        if (
            s["setup"] == setup
            and s.get("mkt") == mkt
            and s.get("mkt") not in (None, "", "NA")
        )
    ]
    if not sub:
        return None
    conf = 100.0 * statistics.fmean(s["fav"] for s in sub)
    base = _market_base_for_signals(sub, bconf, horizon)
    return {
        "n": len(sub),
        "conf": conf,
        "base": base,
        "edge": conf - base,
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
def format_market_walk_forward(
    signals: list,
    mkt_base: dict,
    *,
    horizon: int = PRIMARY,
    folds: int = 4,
    min_test_n: int = 8,
) -> str:
    """Chronological setup x BTC-market stability, with edge vs same-market base."""
    split = _time_folds(signals, folds, horizon)
    out = [
        f"\nWalk-forward setup × MARKET regime stability at {horizon}d "
        f"({len(split)} time folds):"
    ]
    if len(split) < 2:
        out.append("  Not enough timestamped signals for market-regime walk-forward analysis.")
        return "\n".join(out)
    if not mkt_base:
        out.append("  No market-regime base rates available.")
        return "\n".join(out)
    bconf = _market_base_conf(mkt_base)
    setups = sorted({s["setup"] for s in signals if s["h"] == horizon})
    mkts = sorted({
        s.get("mkt")
        for s in signals
        if s["h"] == horizon and s.get("mkt") not in (None, "", "NA")
    })
    out.append(
        "  Base = full-period same coin-regime × BTC-market base; "
        f"rows need testN >= {min_test_n}."
    )
    out.append(
        f"  {'fold':<6}{'setup':<19}{'mkt':<7}{'trainN':>7}{'trainEdge':>11}"
        f"{'testN':>7}{'testEdge':>10}{'testMed':>9}"
    )
    printed = 0
    for i in range(1, len(split)):
        train = [s for f in split[:i] for s in f]
        test = split[i]
        for setup in setups:
            for mkt in mkts:
                tr = _setup_market_edge(train, setup, mkt, bconf, horizon)
                te = _setup_market_edge(test, setup, mkt, bconf, horizon)
                if not tr or not te or te["n"] < min_test_n:
                    continue
                printed += 1
                out.append(
                    f"  {i:<6}{setup:<19}{mkt:<7}{tr['n']:>7}{tr['edge']:>+10.0f}"
                    f"{te['n']:>7}{te['edge']:>+9.0f}{te['med_dir']:>+8.1f}%"
                )
    if not printed:
        out.append("  No setup × market-regime folds met the minimum test sample size.")
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
