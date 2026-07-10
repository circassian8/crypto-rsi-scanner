"""Paper-trading scoreboard.

Every new OB/OS crossing opens a virtual position (long if the setup expects
price up, short if down), one per coin at a time. It closes after PAPER_HOLD_DAYS
at that day's close — priced from the daily closes already fetched each scan, so
no extra API calls. The point is an honest, live answer to "do the gated signals
actually make money?", with the regime-aligned ("actionable") book shown next to
the adverse/no-edge ("control") book the gating filters out.

Simplifications (stated in the report): 1 unit per trade, fixed-horizon exit (no
stops), and the equity curve treats trades sequentially by exit time even though
they overlap — so it's an edge proxy, not a literal account balance.
"""

from __future__ import annotations

import logging
import json
import statistics
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from . import config
from .signal_registry import setup_has_edge
from .state_features import falling_knife_bucket
from .outcomes import _price_asof

log = logging.getLogger(__name__)

OUTLIER_REVIEW_THRESHOLD_PCT = 50.0
RETURN_CONSISTENCY_TOLERANCE_PCT = 0.01


def _direction(expected_dir: str) -> str:
    return "long" if expected_dir == "up" else "short"


def _is_actionable(t: dict) -> bool:
    """A trade the gating would actually surface: a setup with edge, in a market
    regime that isn't adverse to it."""
    return setup_has_edge(t.get("setup_type")) and t.get("market_aligned") != "adverse"


# --------------------------------------------------------------------------- #
# Open / close (called each scan)
# --------------------------------------------------------------------------- #

def update(storage, signals: list[dict], closes_map: dict, now: datetime | None = None
           ) -> tuple[int, int]:
    """Open trades for new crossings, close matured ones. Returns (opened, closed)."""
    if not config.PAPER_TRADING_ENABLED:
        return 0, 0
    now = now or datetime.now(timezone.utc)
    closed = _close_matured(storage, closes_map, now)
    opened = _open_new(storage, signals, now)
    return opened, closed


def _open_new(storage, signals: list[dict], now: datetime) -> int:
    opened = 0
    for s in signals:
        if s.get("flag") not in ("OB", "OS") or not s.get("is_new"):
            continue
        coin_id = s.get("coin_id")
        entry = s.get("price")
        if not coin_id or not entry or entry <= 0:
            continue
        if storage.has_open_trade(coin_id):
            continue
        storage.open_paper_trade(
            symbol=s["symbol"], coin_id=coin_id, setup_type=s.get("setup_type"),
            market_regime=s.get("market_regime"), market_aligned=s.get("market_aligned"),
            state_json=s.get("state_json"),
            direction=_direction(s.get("expected_dir")),
            conviction=int(s.get("conviction") or 0), entry_price=float(entry),
            entry_at=now.isoformat(), hold_days=config.PAPER_HOLD_DAYS,
        )
        opened += 1
    return opened


def _close_matured(storage, closes_map: dict, now: datetime) -> int:
    closed = 0
    for t in storage.open_paper_trades():
        entry_at = datetime.fromisoformat(t["entry_at"])
        age_days = (now - entry_at).total_seconds() / 86400.0
        if age_days < t["hold_days"]:
            continue
        closes = closes_map.get(t["coin_id"])
        exit_price = (_price_asof(closes, entry_at + timedelta(days=t["hold_days"]))
                      if closes is not None else None)
        if not exit_price or exit_price <= 0:
            # coin left the scanned universe; give it a grace window, then drop it
            if age_days > t["hold_days"] + 21:
                storage.abandon_paper_trade(t["id"])
            continue
        sign = 1.0 if t["direction"] == "long" else -1.0
        ret = sign * (exit_price / t["entry_price"] - 1.0) * 100.0
        storage.close_paper_trade(t["id"], exit_price, now.isoformat(), ret)
        closed += 1
    return closed


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _stats(trades: list[dict]) -> dict | None:
    rets = [t["ret_pct"] for t in trades if t.get("ret_pct") is not None]
    if not rets:
        return None
    n = len(rets)
    wins = sum(1 for r in rets if r > 0)
    ordered_rets = sorted(rets)
    trimmed = ordered_rets[1:-1] if len(ordered_rets) > 4 else ordered_rets
    mae_values = [
        float(t.get("mae_pct"))
        for t in trades
        if t.get("mae_pct") is not None
    ]
    # sequential equity by exit time (overlap ignored — an edge proxy)
    ordered = sorted((t for t in trades if t.get("ret_pct") is not None),
                     key=lambda t: t.get("exit_at") or "")
    eq, peak, maxdd = 1.0, 1.0, 0.0
    for t in ordered:
        eq *= 1.0 + t["ret_pct"] / 100.0
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak if peak > 0 else 0.0)
    return {
        "n": n, "win": 100.0 * wins / n,
        "avg": statistics.fmean(rets), "med": statistics.median(rets),
        "total": sum(rets), "equity": eq, "maxdd": 100.0 * maxdd,
        "count": n,
        "win_rate": 100.0 * wins / n,
        "avg_return": statistics.fmean(rets),
        "median_return": statistics.median(rets),
        "trimmed_mean": statistics.fmean(trimmed),
        "worst_case": min(rets),
        "max_adverse_excursion": min(mae_values) if mae_values else min(rets),
    }


def _fmt_stats(label: str, st: dict | None, indent: str = "") -> str:
    if not st:
        return f"{indent}{label:<34} (no closed trades)"
    return (f"{indent}{label:<22}{st['n']:>4}{st['win']:>6.0f}%"
            f"{st['avg']:>+7.1f}%{st['med']:>+7.1f}%"
            f"{(st['equity'] - 1) * 100:>+8.1f}%{st['maxdd']:>7.0f}%")


def _fmt_trimmed_mean(st: dict | None) -> str:
    return f"{st['trimmed_mean']:+.1f}%" if st else "n/a"


def _conviction_bucket(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if v < 50:
        return "0-49"
    if v < 65:
        return "50-64"
    if v < 80:
        return "65-79"
    return "80-100"


def _group_stats(trades: list[dict], key_fn) -> dict[str, dict | None]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        groups[str(key_fn(trade) or "?")].append(trade)
    return {label: _stats(rows) for label, rows in sorted(groups.items())}


def _conviction_bucket_scope_stats(closed: list[dict]) -> dict[str, dict[str, dict | None]]:
    groups = {
        "actionable": [t for t in closed if _is_actionable(t)],
        "control": [t for t in closed if not _is_actionable(t)],
        "all_diagnostic": closed,
    }
    return {
        scope: _group_stats(rows, lambda t: _conviction_bucket(t.get("conviction")))
        for scope, rows in groups.items()
    }


def _conviction_bucket_rows(closed: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for scope, stats_by_bucket in _conviction_bucket_scope_stats(closed).items():
        for bucket, stats in stats_by_bucket.items():
            if not stats:
                continue
            rows.append(
                {
                    "cohort_scope": scope,
                    "conviction_bucket": bucket,
                    "count": stats["count"],
                    "win_rate": stats["win_rate"],
                    "avg_return": stats["avg_return"],
                    "median_return": stats["median_return"],
                    "trimmed_mean": stats["trimmed_mean"],
                    "worst_case": stats["worst_case"],
                    "max_adverse_excursion": stats["max_adverse_excursion"],
                }
            )
    return rows


def _state_doc(trade: dict) -> dict:
    raw = trade.get("state_json")
    if not raw:
        return {}
    try:
        doc = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}
    return doc if isinstance(doc, dict) else {}


def _state_bucket(trade: dict, path: str) -> str:
    doc = _state_doc(trade)
    if path == "volatility":
        return str((doc.get("volatility") or {}).get("state") or "unknown")
    if path == "breadth":
        return str((doc.get("breadth") or {}).get("state") or "unknown")
    if path == "relative_strength":
        return str((doc.get("relative_strength") or {}).get("bucket") or "unknown")
    if path == "liquidity":
        return str((doc.get("liquidity") or {}).get("bucket") or "unknown")
    if path == "falling_knife":
        risk = doc.get("risk") or {}
        if "falling_knife_score" not in risk:
            return "unknown"
        return falling_knife_bucket(risk.get("falling_knife_score"))
    return "unknown"


_STATE_COHORTS = {
    "volatility": "volatility",
    "breadth": "breadth",
    "relative_strength": "relative strength",
    "liquidity": "liquidity",
    "falling_knife": "falling-knife",
}


def _state_group_stats(trades: list[dict]) -> dict[str, dict[str, dict | None]]:
    return {
        feature: _group_stats(trades, lambda t, f=feature: _state_bucket(t, f))
        for feature in _STATE_COHORTS
    }


def _open_position(t: dict) -> dict:
    return {
        "symbol": t.get("symbol"),
        "coin_id": t.get("coin_id"),
        "setup_type": t.get("setup_type"),
        "market_regime": t.get("market_regime"),
        "market_aligned": t.get("market_aligned"),
        "direction": t.get("direction"),
        "conviction": t.get("conviction"),
        "entry_price": t.get("entry_price"),
        "entry_at": t.get("entry_at"),
        "hold_days": t.get("hold_days"),
    }


def build_outlier_review(
    trades: list[dict],
    *,
    threshold_pct: float = OUTLIER_REVIEW_THRESHOLD_PCT,
) -> dict:
    """Surface extreme paper outcomes without removing them from statistics."""
    threshold = abs(float(threshold_pct))
    rows: list[dict] = []
    for trade in trades:
        try:
            ret_pct = float(trade.get("ret_pct"))
        except (TypeError, ValueError):
            continue
        if abs(ret_pct) < threshold:
            continue
        try:
            entry_price = float(trade.get("entry_price") or 0.0)
            exit_price = float(trade.get("exit_price") or 0.0)
        except (TypeError, ValueError):
            entry_price = 0.0
            exit_price = 0.0
        recomputed_ret_pct = None
        delta_pct = None
        if entry_price > 0 and exit_price > 0:
            sign = 1.0 if str(trade.get("direction") or "long") == "long" else -1.0
            recomputed_ret_pct = sign * (exit_price / entry_price - 1.0) * 100.0
            delta_pct = abs(recomputed_ret_pct - ret_pct)
        rows.append(
            {
                "paper_trade_id": trade.get("id"),
                "symbol": trade.get("symbol"),
                "coin_id": trade.get("coin_id"),
                "setup_type": trade.get("setup_type"),
                "market_regime": trade.get("market_regime"),
                "market_aligned": trade.get("market_aligned"),
                "direction": trade.get("direction"),
                "conviction": trade.get("conviction"),
                "entry_price": entry_price or None,
                "exit_price": exit_price or None,
                "entry_at": trade.get("entry_at"),
                "exit_at": trade.get("exit_at"),
                "hold_days": trade.get("hold_days"),
                "ret_pct": ret_pct,
                "recomputed_ret_pct": recomputed_ret_pct,
                "stored_return_delta_pct": delta_pct,
                "stored_price_return_check": (
                    "consistent"
                    if delta_pct is not None and delta_pct <= RETURN_CONSISTENCY_TOLERANCE_PCT
                    else "mismatch_or_missing"
                ),
                "volatility_state": _state_bucket(trade, "volatility"),
                "liquidity_bucket": _state_bucket(trade, "liquidity"),
                "falling_knife_bucket": _state_bucket(trade, "falling_knife"),
            }
        )
    rows.sort(key=lambda row: abs(float(row["ret_pct"])), reverse=True)
    return {
        "threshold_pct": threshold,
        "count": len(rows),
        "retained_in_aggregate_stats": True,
        "auto_excluded": False,
        "rows": rows,
    }


def summary(storage, now: datetime | None = None) -> dict:
    closed = [dict(r) for r in storage.closed_paper_trades()]
    open_ = [dict(r) for r in storage.open_paper_trades()]
    actionable = [t for t in closed if _is_actionable(t)]
    control = [t for t in closed if not _is_actionable(t)]
    now = now or datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "hold_days": config.PAPER_HOLD_DAYS,
        "closed_count": len(closed),
        "open_count": len(open_),
        "books": {
            "all": _stats(closed),
            "actionable": _stats(actionable),
            "control": _stats(control),
        },
        "by_setup": _group_stats(closed, lambda t: t.get("setup_type") or "?"),
        "by_market_regime": _group_stats(closed, lambda t: t.get("market_regime") or "?"),
        "by_market_alignment": _group_stats(closed, lambda t: t.get("market_aligned") or "?"),
        "by_conviction_bucket": _group_stats(closed, lambda t: _conviction_bucket(t.get("conviction"))),
        "by_conviction_bucket_by_scope": _conviction_bucket_scope_stats(closed),
        "conviction_bucket_cohorts": _conviction_bucket_rows(closed),
        "by_state": _state_group_stats(closed),
        "outlier_review": build_outlier_review(closed),
        "open_positions": [_open_position(t) for t in open_],
    }


def report(storage, now: datetime | None = None, *, cohorts: bool = False) -> str:
    closed = [dict(r) for r in storage.closed_paper_trades()]
    open_ = [dict(r) for r in storage.open_paper_trades()]
    if not closed and not open_:
        return (
            "No paper trades yet.\n"
            "A virtual trade opens on each new overbought/oversold crossing and "
            f"closes after {config.PAPER_HOLD_DAYS}d — check back once a few have matured."
        )

    out = ["=" * 64, "PAPER-TRADE SCOREBOARD"]
    out.append(f"Closed: {len(closed)} · Open: {len(open_)} · "
               f"hold {config.PAPER_HOLD_DAYS}d, 1 unit/trade")
    out.append("Long = expects up (dip/bounce); Short = expects down (overbought).")
    out.append("=" * 64)

    header = f"  {'book':<22}{'n':>4}{'win%':>6}{'avg':>7}{'med':>7}{'equity':>8}{'maxDD':>7}"
    out.append("\nReturns per trade, and sequential equity (overlap ignored):")
    out.append(header)
    actionable = [t for t in closed if _is_actionable(t)]
    control = [t for t in closed if not _is_actionable(t)]
    all_stats = _stats(closed)
    actionable_stats = _stats(actionable)
    control_stats = _stats(control)
    out.append(_fmt_stats("ALL closed", all_stats))
    out.append(_fmt_stats("→ actionable (gated)", actionable_stats))
    out.append(_fmt_stats("→ control (gated-out)", control_stats))
    out.append(
        "Robust check (drop one best/worst when n>4): "
        f"all={_fmt_trimmed_mean(all_stats)} · "
        f"actionable={_fmt_trimmed_mean(actionable_stats)} · "
        f"control={_fmt_trimmed_mean(control_stats)}"
    )

    # by setup
    setups = sorted({t.get("setup_type") or "?" for t in closed})
    if setups:
        out.append("\nBy setup:")
        out.append(header.replace("book", "setup"))
        for setup in setups:
            out.append(_fmt_stats(setup, _stats([t for t in closed
                                                 if (t.get("setup_type") or "?") == setup])))

    # by market regime at entry
    regimes = sorted({t.get("market_regime") or "?" for t in closed})
    if len(regimes) > 1:
        out.append("\nBy market regime at entry:")
        out.append(header.replace("book", "market"))
        for mr in regimes:
            out.append(_fmt_stats(mr.lower(), _stats([t for t in closed
                                                      if (t.get("market_regime") or "?") == mr])))

    alignments = sorted({t.get("market_aligned") or "?" for t in closed})
    if len(alignments) > 1:
        out.append("\nBy market alignment:")
        out.append(header.replace("book", "alignment"))
        for aligned in alignments:
            out.append(_fmt_stats(aligned, _stats([t for t in closed
                                                   if (t.get("market_aligned") or "?") == aligned])))

    buckets = ("0-49", "50-64", "65-79", "80-100", "unknown")
    present_buckets = [b for b in buckets if any(_conviction_bucket(t.get("conviction")) == b for t in closed)]
    if present_buckets:
        out.append("\nBy conviction bucket:")
        out.append(header.replace("book", "conviction"))
        for bucket in present_buckets:
            out.append(_fmt_stats(bucket, _stats([t for t in closed
                                                  if _conviction_bucket(t.get("conviction")) == bucket])))
        scoped = _conviction_bucket_scope_stats(closed)
        for scope, rows in scoped.items():
            scoped_buckets = [bucket for bucket in buckets if bucket in rows and rows[bucket]]
            if not scoped_buckets:
                continue
            title = {
                "actionable": "actionable",
                "control": "control",
                "all_diagnostic": "all rows diagnostic",
            }.get(scope, scope)
            out.append(f"\nBy conviction bucket ({title}):")
            out.append(header.replace("book", "conviction"))
            for bucket in scoped_buckets:
                out.append(_fmt_stats(bucket, rows[bucket]))

    if cohorts and closed:
        out.append("\nBy state cohort:")
        for feature, label in _STATE_COHORTS.items():
            rows = {
                bucket: st
                for bucket, st in _group_stats(
                    closed, lambda t, f=feature: _state_bucket(t, f)
                ).items()
                if bucket != "unknown" and st
            }
            if not rows:
                continue
            out.append(f"\n  {label}:")
            out.append(header.replace("book", "bucket"))
            for bucket, st in rows.items():
                out.append(_fmt_stats(bucket, st, indent="  "))

    outlier_review = build_outlier_review(closed)
    if outlier_review["rows"]:
        out.append(
            f"\nExtreme outcomes for review (|return| >= "
            f"{outlier_review['threshold_pct']:.0f}%; retained in all statistics):"
        )
        for row in outlier_review["rows"]:
            out.append(
                f"  {str(row.get('symbol') or '?'):<7} "
                f"{str(row.get('direction') or '?'):<5} "
                f"{float(row['ret_pct']):>+7.1f}% · "
                f"{row.get('setup_type') or '?'} · "
                f"price-check={row['stored_price_return_check']} · "
                f"vol={row['volatility_state']} · liq={row['liquidity_bucket']}"
            )
        out.append("  Diagnostic only: no rows are removed and no thresholds are auto-applied.")

    if open_:
        out.append(f"\nOpen positions ({len(open_)}): "
                   + ", ".join(f"{t['symbol']}({t['direction'][0]})" for t in open_[:12])
                   + (" …" if len(open_) > 12 else ""))

    out.append("\n" + "=" * 64)
    out.append("'actionable' = edge-bearing setup in a non-adverse regime (what the")
    out.append("scanner surfaces); 'control' = what the gating filters out.")
    return "\n".join(out)
