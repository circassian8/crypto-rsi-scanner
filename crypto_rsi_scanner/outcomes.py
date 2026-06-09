"""Signal outcome tracking.

For each past crossing we recorded, measure what price did N days later using the
daily closes already fetched each scan (no extra API calls). Then aggregate into
hit-rates and forward-return stats so the scanner can grade its own signals.

Each signal is graded against *its own setup's* expected direction rather than a
single mean-reversion yardstick (see indicators.setup_for): a dip_buy or
trend_continuation setup is "favorable" when price RISES, a breakdown_risk or a
mean-reversion-from-overbought setup when price FALLS. This is what makes the
hit-rates honest — a correct breakdown call no longer counts as a failed bounce.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd

from . import config
from .signal_registry import market_alignment, setup_for, setup_has_edge
from .state_features import falling_knife_bucket

log = logging.getLogger(__name__)


def favorable(expected_dir: str, ret_pct: float) -> int:
    """1 if price moved the way this setup expected.

    expected_dir is 'up' or 'down' (from setup_for). Legacy 'OB'/'OS' flags are
    still accepted and read as the base mean-reversion direction, so old call
    sites and stored rows keep working."""
    d = expected_dir
    if d in ("OB", "PRE_OB"):
        d = "down"
    elif d in ("OS", "PRE_OS"):
        d = "up"
    if d == "up":
        return 1 if ret_pct > 0 else 0
    return 1 if ret_pct < 0 else 0  # 'down' / fallback


def _setup_key(d: dict) -> str:
    """setup_type for a row, deriving from flag+regime when not stored (older
    rows, or ad-hoc dicts in tests)."""
    st = d.get("setup_type")
    if st and not (isinstance(st, float) and pd.isna(st)):
        return st
    return setup_for(d.get("flag", ""), d.get("regime") or "")[0]


def _present(value: object) -> bool:
    if value is None:
        return False
    try:
        return not pd.isna(value)
    except (TypeError, ValueError):
        return True


def _market_alignment_key(d: dict) -> str:
    aligned = d.get("market_aligned")
    if _present(aligned):
        return str(aligned)
    return market_alignment(_setup_key(d), d.get("market_regime"))


def _is_actionable(d: dict) -> bool:
    return setup_has_edge(_setup_key(d)) and _market_alignment_key(d) != "adverse"


def _state_doc(d: dict) -> dict:
    raw = d.get("state_json")
    if not _present(raw):
        return {}
    try:
        doc = json.loads(str(raw))
    except Exception:  # noqa: BLE001
        return {}
    return doc if isinstance(doc, dict) else {}


def _state_bucket(d: dict, feature: str) -> str:
    doc = _state_doc(d)
    if feature == "volatility":
        return str((doc.get("volatility") or {}).get("state") or "unknown")
    if feature == "breadth":
        return str((doc.get("breadth") or {}).get("state") or "unknown")
    if feature == "relative_strength":
        return str((doc.get("relative_strength") or {}).get("bucket") or "unknown")
    if feature == "liquidity":
        return str((doc.get("liquidity") or {}).get("bucket") or "unknown")
    if feature == "falling_knife":
        risk = doc.get("risk") or {}
        if "falling_knife_score" not in risk:
            return "unknown"
        return falling_knife_bucket(risk.get("falling_knife_score"))
    return "unknown"


def _price_asof(closes: pd.Series, ts: datetime) -> float | None:
    """Last close at or before ts (None if unavailable).

    Uses a boolean mask rather than Series.asof(): in pandas 3, asof() raises
    "Cannot losslessly convert units" when the index resolution (e.g. ms, from
    unit='ms' parsing) differs from the comparison Timestamp (us). A mask
    comparison is resolution-agnostic.
    """
    if closes is None or closes.empty:
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None and getattr(closes.index, "tz", None) is not None:
        t = t.tz_localize(closes.index.tz)
    prior = closes.loc[closes.index <= t]
    if prior.empty:
        return None
    val = prior.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


def evaluate_coin(
    storage,
    coin_id: str,
    closes: pd.Series,
    horizons: list[int],
    now: datetime | None = None,
) -> int:
    """Record any newly-matured outcomes for one coin. Returns count written."""
    now = now or datetime.now(timezone.utc)
    max_h = max(horizons)
    since = (now - timedelta(days=max_h + 5)).isoformat()

    written = 0
    for row in storage.signals_for_outcome(coin_id, since):
        sid = row["id"]
        run_at = datetime.fromisoformat(row["run_at"])
        flag = row["flag"]
        # grade against this setup's expected direction (derive if not stored)
        exp_dir = row["expected_dir"] or setup_for(flag, row["regime"] or "")[1]

        entry = _price_asof(closes, run_at)
        if entry is None or entry <= 0:
            entry = row["price"]  # fallback to the price recorded at scan time
        if not entry or entry <= 0:
            continue

        for h in horizons:
            if storage.has_outcome(sid, h):
                continue
            if (now - run_at).total_seconds() / 86400.0 < h:
                continue  # not matured yet
            exit_price = _price_asof(closes, run_at + timedelta(days=h))
            if exit_price is None or exit_price <= 0:
                continue
            ret_pct = (exit_price / entry - 1.0) * 100.0
            storage.save_outcome(sid, h, entry, exit_price, ret_pct, favorable(exp_dir, ret_pct))
            written += 1
    return written


def evaluate_all(storage, closes_map: dict, horizons: list[int] | None = None) -> int:
    horizons = horizons or config.OUTCOME_HORIZONS
    total = 0
    for coin_id, closes in closes_map.items():
        try:
            total += evaluate_coin(storage, coin_id, closes, horizons)
        except Exception as e:  # one coin shouldn't break the batch
            log.warning("Outcome eval failed for %s: %s", coin_id, e)
    return total


# --------------------------------------------------------------------------- #
# Track records (inline hit-rates for live alerts)
# --------------------------------------------------------------------------- #

MIN_SAMPLES_FOR_TRACK = 4  # don't show a hit-rate from too few past signals


def track_records(rows: list, horizon: int) -> dict:
    """Aggregate matured outcomes into per-setup_type hit-rates at one horizon.
    Returns {setup_type: {"n", "hit", "med_ret"}} for live lookup. "hit" counts
    signals that went the way the setup expected (favorable)."""
    by_key: dict[str, list] = {}
    for r in rows:
        d = dict(r)
        if d["horizon_days"] != horizon:
            continue
        if d["flag"] not in ("OB", "OS"):
            continue  # only graded crossings
        key = _setup_key(d)
        if not key:
            continue
        by_key.setdefault(key, []).append((d["favorable"], d["ret_pct"]))

    stats = {}
    for key, vals in by_key.items():
        n = len(vals)
        if n < MIN_SAMPLES_FOR_TRACK:
            continue
        hit = sum(f for f, _ in vals)
        rets = sorted(r for _, r in vals)
        med = rets[len(rets) // 2] if len(rets) % 2 else (rets[len(rets) // 2 - 1] + rets[len(rets) // 2]) / 2
        stats[key] = {"n": n, "hit": hit, "med_ret": med}
    return stats


def track_record_text(setup_type: str, stats: dict, horizon: int) -> str:
    """One-line historical track record for a signal's setup, or '' if there's
    not enough matured history. "confirmed" = went the way the setup expected."""
    rec = stats.get(setup_type)
    if not rec:
        return ""
    pct = round(100 * rec["hit"] / rec["n"])
    label = setup_type.replace("_", " ")
    return (
        f"📊 history: {label} confirmed {rec['hit']}/{rec['n']} ({pct}%) "
        f"at {horizon}d, med {rec['med_ret']:+.1f}%"
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _bucket_conviction(c: float) -> str:
    if c >= 65:
        return "high (65+)"
    if c >= 40:
        return "med (40-64)"
    return "low (<40)"


def build_report(rows: list, primary_horizon: int = 7) -> str:
    if not rows:
        return (
            "No matured signal outcomes yet.\n"
            "Outcomes accrue automatically as the daily scan runs — check back "
            "after signals have had a few days (up to ~2 weeks) to play out."
        )

    df = pd.DataFrame([dict(r) for r in rows])
    df["setup_type"] = df.apply(_setup_key, axis=1)
    df["market_aligned"] = df.apply(_market_alignment_key, axis=1)
    df["book"] = df.apply(lambda r: "actionable" if _is_actionable(r) else "control", axis=1)
    crossed = df[df["flag"].isin(["OB", "OS"])].copy()

    out: list[str] = []
    out.append("=" * 60)
    out.append("RSI SIGNAL OUTCOMES")
    out.append("Each setup graded against its own expected direction.")
    out.append(f"Total matured observations: {len(df)}")
    out.append("=" * 60)

    # --- by setup x horizon (confirmed = price went the expected way) ---
    out.append("\nBy setup × horizon (confirmed = moved the expected way):")
    out.append(f"  {'setup':<19}{'horizon':>7}{'n':>6}{'medRet':>9}{'avgRet':>9}{'conf%':>7}")
    for setup in sorted(crossed["setup_type"].dropna().unique()):
        sub = crossed[crossed["setup_type"] == setup]
        for h in sorted(df["horizon_days"].unique()):
            s = sub[sub["horizon_days"] == h]
            if s.empty:
                continue
            out.append(
                f"  {setup:<19}{h:>5}d {len(s):>5}"
                f"{s['ret_pct'].median():>8.1f}%"
                f"{s['ret_pct'].mean():>8.1f}%"
                f"{100 * s['favorable'].mean():>6.0f}%"
            )

    # --- conviction breakdown at primary horizon (validates the score) ---
    ph = crossed[crossed["horizon_days"] == primary_horizon]
    if not ph.empty:
        ph = ph.copy()
        ph["bucket"] = ph["conviction"].map(_bucket_conviction)
        out.append(f"\nBy actionable/control at {primary_horizon}d:")
        out.append(f"  {'book':<12}{'n':>5}{'medRet':>9}{'conf%':>7}")
        for book in ("actionable", "control"):
            g = ph[ph["book"] == book]
            if g.empty:
                continue
            out.append(
                f"  {book:<12}{len(g):>5}"
                f"{g['ret_pct'].median():>8.1f}%{100 * g['favorable'].mean():>6.0f}%"
            )

        alignments = [a for a in ("favorable", "neutral", "adverse")
                      if not ph[ph["market_aligned"] == a].empty]
        if alignments:
            out.append(f"\nBy market alignment at {primary_horizon}d:")
            out.append(f"  {'alignment':<12}{'n':>5}{'medRet':>9}{'conf%':>7}")
            for aligned in alignments:
                g = ph[ph["market_aligned"] == aligned]
                out.append(
                    f"  {aligned:<12}{len(g):>5}"
                    f"{g['ret_pct'].median():>8.1f}%{100 * g['favorable'].mean():>6.0f}%"
                )

        out.append(f"\nBy conviction at {primary_horizon}d (does higher score = better?):")
        out.append(f"  {'bucket':<12}{'n':>5}{'medRet':>9}{'conf%':>7}")
        for bucket in ("low (<40)", "med (40-64)", "high (65+)"):
            g = ph[ph["bucket"] == bucket]
            if g.empty:
                continue
            out.append(
                f"  {bucket:<12}{len(g):>5}"
                f"{g['ret_pct'].median():>8.1f}%{100 * g['favorable'].mean():>6.0f}%"
            )

        state_features = {
            "volatility": "volatility",
            "breadth": "breadth",
            "relative_strength": "relative strength",
            "liquidity": "liquidity",
            "falling_knife": "falling-knife",
        }
        state_lines: list[str] = []
        for feature, label in state_features.items():
            buckets = sorted({_state_bucket(dict(r), feature) for _, r in ph.iterrows()})
            buckets = [b for b in buckets if b != "unknown"]
            if not buckets:
                continue
            state_lines.append(f"  {label}:")
            state_lines.append(f"    {'bucket':<18}{'n':>5}{'medRet':>9}{'conf%':>7}")
            for bucket in buckets:
                mask = ph.apply(lambda r, f=feature, b=bucket: _state_bucket(dict(r), f) == b, axis=1)
                g = ph[mask]
                state_lines.append(
                    f"    {bucket:<18}{len(g):>5}"
                    f"{g['ret_pct'].median():>8.1f}%{100 * g['favorable'].mean():>6.0f}%"
                )
        if state_lines:
            out.append(f"\nBy state cohort at {primary_horizon}d:")
            out.extend(state_lines)

    out.append("\n" + "=" * 60)
    out.append("Note: the scanner fetches extra recent histories for pending")
    out.append("outcomes when coins leave today's top universe. Overlapping")
    out.append("signals are de-correlated by scoring only crossing events")
    out.append("(is_new), not every day in-zone.")
    return "\n".join(out)
