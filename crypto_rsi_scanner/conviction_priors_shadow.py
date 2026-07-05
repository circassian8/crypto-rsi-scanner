"""Shadow-only conviction-prior comparison report.

This module reads existing local paper/outcome artifacts when present and writes
recommendations-only diagnostics. It does not load priors into runtime config or
change scanner thresholds.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .signal_registry import SETUPS


REPORT_JSON = "conviction_priors_shadow_report.json"
REPORT_MD = "conviction_priors_shadow_report.md"


def build_shadow_report(*, out_dir: str | Path = "research", outcome_paths: Iterable[str | Path] = ()) -> dict[str, Any]:
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in outcome_paths:
        rows.extend(_read_jsonl(path))
    by_setup: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        setup = str(row.get("setup_type") or row.get("setup") or "unknown")
        value = _return_value(row)
        if value is not None:
            by_setup[setup].append(value)
    setup_rows = {}
    for setup_key, setup in sorted(SETUPS.items()):
        returns = by_setup.get(setup_key, [])
        suggestion = _suggest_prior(returns)
        setup_rows[setup_key] = {
            "setup_type": setup_key,
            "current_default_prior": setup.edge_priors.get("neutral"),
            "sample_count": len(returns),
            "mean_forward_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
            "shadow_prior_suggestion": suggestion,
            "min_sample_warning": len(returns) < 30,
            "auto_apply": False,
        }
    payload = {
        "schema_version": "conviction_priors_shadow_report_v1",
        "row_type": "conviction_priors_shadow_report",
        "outcome_rows_read": len(rows),
        "setups": setup_rows,
        "recommendations_only": True,
        "auto_apply": False,
        "auto_apply_thresholds": False,
        "runtime_priors_changed": False,
    }
    (out / REPORT_JSON).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / REPORT_MD).write_text(format_shadow_report(payload), encoding="utf-8")
    return payload


def format_shadow_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Conviction Priors Shadow Report",
        "",
        "Shadow-only comparison. No runtime priors or thresholds are changed.",
        "",
        f"- outcome_rows_read: `{payload.get('outcome_rows_read')}`",
        f"- recommendations_only: `{payload.get('recommendations_only')}`",
        f"- auto_apply: `{payload.get('auto_apply')}`",
        "",
        "## Setups",
        "",
    ]
    for setup, row in sorted((payload.get("setups") or {}).items()):
        lines.append(
            f"- {setup}: current={row.get('current_default_prior')} "
            f"samples={row.get('sample_count')} shadow={row.get('shadow_prior_suggestion')} "
            f"min_sample_warning={row.get('min_sample_warning')}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, Mapping):
            rows.append(dict(loaded))
    return rows


def _return_value(row: Mapping[str, Any]) -> float | None:
    for field in ("ret_pct", "return_pct", "forward_return_pct", "horizon_return_pct"):
        try:
            if row.get(field) is not None:
                return float(row[field])
        except (TypeError, ValueError):
            return None
    return None


def _suggest_prior(values: list[float]) -> int | None:
    if len(values) < 30:
        return None
    mean = sum(values) / len(values)
    if mean >= 3:
        return 70
    if mean >= 1:
        return 60
    if mean <= -3:
        return 30
    if mean <= -1:
        return 40
    return 50


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write shadow-only conviction prior diagnostics.")
    parser.add_argument("--out-dir", default="research")
    parser.add_argument("--outcomes", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_shadow_report(out_dir=args.out_dir, outcome_paths=args.outcomes)
    print(f"conviction_priors_shadow_report: {Path(args.out_dir) / REPORT_MD}")
    print(f"runtime_priors_changed={payload['runtime_priors_changed']} auto_apply={payload['auto_apply']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
