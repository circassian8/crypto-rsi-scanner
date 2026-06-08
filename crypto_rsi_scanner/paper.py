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
import statistics
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from . import config
from .signal_registry import setup_has_edge
from .outcomes import _price_asof

log = logging.getLogger(__name__)


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
    return _open_new(storage, signals, now), _close_matured(storage, closes_map, now)


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
    }


def _fmt_stats(label: str, st: dict | None, indent: str = "") -> str:
    if not st:
        return f"{indent}{label:<34} (no closed trades)"
    return (f"{indent}{label:<22}{st['n']:>4}{st['win']:>6.0f}%"
            f"{st['avg']:>+7.1f}%{st['med']:>+7.1f}%"
            f"{(st['equity'] - 1) * 100:>+8.1f}%{st['maxdd']:>7.0f}%")


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
        "open_positions": [_open_position(t) for t in open_],
    }


def report(storage, now: datetime | None = None) -> str:
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
    out.append(_fmt_stats("ALL closed", _stats(closed)))
    actionable = [t for t in closed if _is_actionable(t)]
    control = [t for t in closed if not _is_actionable(t)]
    out.append(_fmt_stats("→ actionable (gated)", _stats(actionable)))
    out.append(_fmt_stats("→ control (gated-out)", _stats(control)))

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

    if open_:
        out.append(f"\nOpen positions ({len(open_)}): "
                   + ", ".join(f"{t['symbol']}({t['direction'][0]})" for t in open_[:12])
                   + (" …" if len(open_) > 12 else ""))

    out.append("\n" + "=" * 64)
    out.append("'actionable' = edge-bearing setup in a non-adverse regime (what the")
    out.append("scanner surfaces); 'control' = what the gating filters out.")
    return "\n".join(out)
