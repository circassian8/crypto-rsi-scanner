"""Local-artifact replay summaries for Event Alpha Radar research runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaReplayResult:
    alert_rows: int
    watchlist_rows: int
    priors_enabled: bool = False
    llm_advisory: bool = False
    tier_counts: dict[str, int] | None = None
    route_counts: dict[str, int] | None = None
    score_before_after: tuple[tuple[str, int, int], ...] = ()
    warnings: tuple[str, ...] = ()


def replay_from_artifacts(
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_rows: Iterable[Mapping[str, Any]] = (),
    priors_enabled: bool = False,
    llm_advisory: bool = False,
) -> EventAlphaReplayResult:
    """Summarize a deterministic replay from already-collected artifacts.

    This replay intentionally does not call providers, send alerts, or mutate
    watchlist state. It is a daily debugging tool for comparing local outputs
    across prior/LLM modes.
    """
    alerts = [dict(row) for row in alert_rows]
    watch = [dict(row) for row in watchlist_rows]
    scores: list[tuple[str, int, int]] = []
    for row in alerts:
        before = _int(row.get("score_before_priors") or row.get("opportunity_score"))
        after = _int(row.get("score_after_priors") or row.get("opportunity_score"))
        if priors_enabled or before != after:
            scores.append((str(row.get("alert_key") or row.get("snapshot_id") or row.get("event_id") or ""), before, after))
    return EventAlphaReplayResult(
        alert_rows=len(alerts),
        watchlist_rows=len(watch),
        priors_enabled=bool(priors_enabled),
        llm_advisory=bool(llm_advisory),
        tier_counts=_counts(alerts, "tier"),
        route_counts=_counts(alerts, "route"),
        score_before_after=tuple(scores[:50]),
        warnings=("local artifacts only; no provider fetches or sends were attempted",),
    )


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def format_replay_report(result: EventAlphaReplayResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA REPLAY REPORT (local artifacts only)",
        "=" * 76,
        f"alerts={result.alert_rows} · watchlist_rows={result.watchlist_rows}",
        f"priors_enabled={str(result.priors_enabled).lower()} · llm_advisory={str(result.llm_advisory).lower()}",
        "tiers: " + _fmt_counts(result.tier_counts or {}),
        "routes: " + _fmt_counts(result.route_counts or {}),
    ]
    if result.score_before_after:
        lines.append("")
        lines.append("Prior score comparison:")
        for key, before, after in result.score_before_after[:20]:
            lines.append(f"- {key or 'unknown'}: {before} -> {after}")
    if result.warnings:
        lines.append("")
        lines.append("warnings: " + "; ".join(result.warnings))
    lines.append("No live providers, Telegram sends, paper trades, live DB rows, or execution were used.")
    return "\n".join(lines)


def _counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _fmt_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
