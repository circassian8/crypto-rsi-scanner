"""Crypto Radar Decision Model v2 sections for the canonical daily brief.

This component renders only fields that were explicitly persisted by v2.  It
does not score candidates, infer values for legacy rows, or affect any route.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from crypto_rsi_scanner import config
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    PREVIEW_LANE_ORDER,
    PREVIEW_LANE_TITLES,
    decision_model_markdown_lines,
    decision_model_values,
    group_decision_rows,
)


def decision_model_daily_brief_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    include_diagnostics: bool = False,
) -> list[str]:
    """Return complete, presentation-only v2 lanes for explicit v2 rows."""

    if not config.EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED:
        return []
    groups = group_decision_rows(rows, include_diagnostics=True)
    if not any(groups.values()):
        return []
    show_diagnostics = (
        include_diagnostics
        and config.EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS
    )
    lines = [
        "",
        "## Crypto Radar Decision Model v2 Preview",
        "Research-only presentation lanes. They do not change legacy opportunity types or notification routing.",
    ]
    for lane in PREVIEW_LANE_ORDER:
        count = len(groups[lane])
        if lane == "decision_diagnostic" and not show_diagnostics:
            lines.append(f"- {PREVIEW_LANE_TITLES[lane]}: hidden ({count} explicit v2 row(s))")
        else:
            lines.append(f"- {PREVIEW_LANE_TITLES[lane]}: {count}")
    for lane in PREVIEW_LANE_ORDER:
        if lane == "decision_diagnostic" and not show_diagnostics:
            continue
        lines.extend(["", f"### {PREVIEW_LANE_TITLES[lane]}"])
        lane_rows = groups[lane]
        if not lane_rows:
            lines.append("- None.")
            continue
        for row in lane_rows[:10]:
            values = decision_model_values(row)
            lines.extend(["", f"#### {_candidate_label(row)}"])
            lines.extend(decision_model_markdown_lines(row))
    return lines


def _candidate_label(row: Mapping[str, Any]) -> str:
    symbol = str(row.get("symbol") or row.get("asset_symbol") or "unknown")
    coin_id = str(row.get("coin_id") or row.get("asset_coin_id") or "unknown")
    title = str(row.get("event_name") or row.get("title") or "research candidate")
    return f"{symbol}/{coin_id} - {title}"


__all__ = ("decision_model_daily_brief_lines",)
