"""Split implementation for `crypto_rsi_scanner/backtest_parts/api.py` (costs)."""

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
