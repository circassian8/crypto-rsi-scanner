"""Split implementation for `crypto_rsi_scanner/backtest_parts/legacy.py` (cli)."""

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
        if mkt_base:
            print(format_market_walk_forward(
                signals,
                mkt_base,
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
