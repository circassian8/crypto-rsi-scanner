"""Split implementation for `crypto_rsi_scanner/backtest_parts/api.py` (results)."""

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
    bconf = _market_base_conf(mkt_base)

    groups: dict = defaultdict(list)
    for s in signals:
        if s["h"] == horizon and s.get("mkt") not in (None, "", "NA"):
            groups[(s["setup"], s["mkt"])].append(s)

    rows = []
    for (setup, mkt), sigs in sorted(groups.items()):
        conf = 100.0 * statistics.fmean(s["fav"] for s in sigs)
        base = _market_base_for_signals(sigs, bconf, horizon)
        rows.append({"setup": setup, "mkt": mkt, "n": len(sigs), "conf": conf,
                     "base": base, "edge": conf - base,
                     "med": statistics.median(s["ret"] for s in sigs)})
    return rows
def _market_base_conf(mkt_base: dict) -> dict:
    bconf: dict = {}
    for (regime, mkt, h), rets in mkt_base.items():
        arr = np.asarray(rets, dtype=float)
        if not len(arr):
            continue
        bconf[(regime, mkt, h, "up")] = float((arr > 0).mean())
        bconf[(regime, mkt, h, "down")] = float((arr < 0).mean())
    return bconf
def _market_base_for_signals(sigs: list[dict], bconf: dict, horizon: int) -> float:
    return 100.0 * statistics.fmean(
        bconf.get((s["regime"], s.get("mkt"), horizon, s["exp"]), 0.0) for s in sigs
    )
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
