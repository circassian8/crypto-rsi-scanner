"""Research-only paper-risk scenario report."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

from .storage import Storage


REPORT_JSON = "PAPER_RISK_RESEARCH.json"
REPORT_MD = "PAPER_RISK_RESEARCH.md"


def path_metrics(
    entry_price: float,
    prices: Iterable[float],
    *,
    direction: str = "long",
    stop_pct: float | None = None,
) -> dict[str, Any]:
    clean_prices = [float(price) for price in prices if float(price) > 0]
    if entry_price <= 0 or not clean_prices:
        return {"return_pct": None, "mfe_pct": None, "mae_pct": None, "stopped": False}
    sign = 1.0 if direction == "long" else -1.0
    path_returns = [sign * (price / entry_price - 1.0) * 100.0 for price in clean_prices]
    stopped = False
    realized = path_returns[-1]
    if stop_pct is not None:
        for value in path_returns:
            if value <= -abs(stop_pct) + 1e-9:
                realized = -abs(stop_pct)
                stopped = True
                break
    return {
        "return_pct": realized,
        "mfe_pct": max(path_returns),
        "mae_pct": min(path_returns),
        "stopped": stopped,
    }


def summarize_returns(values: Iterable[float]) -> dict[str, Any]:
    returns = [float(value) for value in values]
    if not returns:
        return {"count": 0}
    ordered = sorted(returns)
    trim = ordered[1:-1] if len(ordered) > 4 else ordered
    losses = [value for value in returns if value < 0]
    return {
        "count": len(returns),
        "win_rate": round(100.0 * sum(1 for value in returns if value > 0) / len(returns), 2),
        "avg_return": statistics.fmean(returns),
        "median_return": statistics.median(returns),
        "trimmed_mean": statistics.fmean(trim),
        "worst_case": min(returns),
        "worst_1pct": ordered[max(0, int(len(ordered) * 0.01) - 1)],
        "tail_loss_count": sum(1 for value in returns if value <= -10.0),
        "drawdown_proxy": abs(min(losses)) if losses else 0.0,
    }


def build_research_report(*, db_path: str | Path = "rsi_scanner.db", out_dir: str | Path = "research") -> dict[str, Any]:
    storage = Storage(str(db_path))
    try:
        trades = [dict(row) for row in storage.closed_paper_trades()]
    finally:
        storage.close()
    return build_research_report_from_trades(trades, out_dir=out_dir)


def build_research_report_from_trades(trades: list[Mapping[str, Any]], *, out_dir: str | Path = "research") -> dict[str, Any]:
    scenarios = {
        "baseline": _scenario(trades),
        "exclude_breakdown_risk": _scenario([row for row in trades if row.get("setup_type") != "breakdown_risk"]),
        "mean_reversion_chop_only": _scenario(
            [
                row for row in trades
                if row.get("setup_type") == "mean_reversion" and str(row.get("market_regime") or "").upper() in {"CHOP", "RANGE", "SIDEWAYS"}
            ]
        ),
        "exclude_trend_continuation_outside_bull": _scenario(
            [
                row for row in trades
                if not (
                    row.get("setup_type") == "trend_continuation"
                    and str(row.get("market_regime") or "").upper() not in {"BULL", "UPTREND"}
                )
            ]
        ),
    }
    for stop in (10, 15, 20):
        scenarios[f"stop_{stop}_pct_shadow"] = _scenario(trades, stop_pct=float(stop))
    payload = {
        "schema_version": "paper_risk_research_v1",
        "row_type": "paper_risk_research",
        "research_only": True,
        "trades_read": len(trades),
        "scenarios": scenarios,
        "paper_opening_behavior_changed": False,
        "execution_logic_changed": False,
        "auto_apply": False,
    }
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    (out / REPORT_JSON).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / REPORT_MD).write_text(format_research_report(payload), encoding="utf-8")
    return payload


def format_research_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Paper Risk Research",
        "",
        "Research-only scenario view over closed paper rows. Paper opening/closing behavior is unchanged.",
        "",
        f"- trades_read: `{payload.get('trades_read')}`",
        f"- paper_opening_behavior_changed: `{payload.get('paper_opening_behavior_changed')}`",
        f"- auto_apply: `{payload.get('auto_apply')}`",
        "",
    ]
    for name, row in sorted((payload.get("scenarios") or {}).items()):
        lines.append(f"- {name}: n={row.get('count')} avg={row.get('avg_return')} worst={row.get('worst_case')}")
    return "\n".join(lines).rstrip() + "\n"


def _scenario(trades: Iterable[Mapping[str, Any]], *, stop_pct: float | None = None) -> dict[str, Any]:
    returns: list[float] = []
    stopped = 0
    for row in trades:
        if stop_pct is None:
            value = row.get("ret_pct")
            if value is not None:
                try:
                    returns.append(float(value))
                except (TypeError, ValueError):
                    pass
            continue
        metrics = path_metrics(
            float(row.get("entry_price") or 0.0),
            [float(row.get("exit_price") or 0.0)],
            direction=str(row.get("direction") or "long"),
            stop_pct=stop_pct,
        )
        if metrics["return_pct"] is not None:
            returns.append(float(metrics["return_pct"]))
            stopped += int(bool(metrics["stopped"]))
    summary = summarize_returns(returns)
    summary["stopped_count"] = stopped
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write research-only paper risk scenario report.")
    parser.add_argument("--db-path", default="rsi_scanner.db")
    parser.add_argument("--out-dir", default="research")
    args = parser.parse_args(argv)
    payload = build_research_report(db_path=args.db_path, out_dir=args.out_dir)
    print(f"paper_risk_research: {Path(args.out_dir) / REPORT_MD}")
    print(f"trades_read={payload['trades_read']} paper_opening_behavior_changed={payload['paper_opening_behavior_changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
