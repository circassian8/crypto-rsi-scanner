"""Event Alpha watchlist report rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
from .models import *  # noqa: F403 - split modules share legacy model names


def format_watchlist_refresh_result(result: EventWatchlistRefreshResult) -> str:
    rows = [
        "=" * 76,
        "EVENT WATCHLIST REFRESH (research-only; not trade signals)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"observed_at: {result.observed_at}",
        f"rows_written: {result.rows_written}",
        f"candidates: {len(result.entries)} · alertable escalations: {len(result.alert_entries)}",
        "",
    ]
    if result.alert_entries:
        rows.append("Escalations:")
        for entry in result.alert_entries:
            rows.extend(_entry_lines(entry))
            rows.append("")
    else:
        rows.append("No meaningful state escalations. Duplicate/no-catalyst rows were persisted only as research state.")
    return "\n".join(rows).rstrip()


def format_watchlist_report(result: EventWatchlistReadResult) -> str:
    rows = [
        "=" * 76,
        "EVENT WATCHLIST REPORT (research-only; not trade signals)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"rows_read: {result.rows_read} · latest_entries: {len(result.entries)}",
    ]
    if not result.entries:
        rows.append("")
        rows.append("No event watchlist state found.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for entry in result.entries:
        counts[entry.state] = counts.get(entry.state, 0) + 1
    rows.append("states: " + ", ".join(f"{state}={count}" for state, count in sorted(counts.items())))
    rows.append("")
    for entry in result.entries:
        rows.extend(_entry_lines(entry))
        rows.append("")
    return "\n".join(rows).rstrip()


def _entry_lines(entry: EventWatchlistEntry) -> list[str]:
    effective = entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown"
    rule = entry.latest_rule_playbook_type
    playbook_line = (
        f"  playbook: {effective} "
        f"score={entry.latest_playbook_score if entry.latest_playbook_score is not None else 0} "
        f"action={entry.latest_playbook_action or 'store_only'}"
    )
    if rule and rule != effective:
        playbook_line += f" · rule={rule}"
    transition = (
        f"  transition: {entry.previous_state or 'new'} -> {entry.state}"
        + (
            f" · quality-capped from {entry.requested_state_before_quality_gate}: {entry.quality_state_block_reason}"
            if entry.state_quality_capped
            else " · alertable escalation"
            if entry.should_alert and not entry.material_change_reasons
            else f" · alertable material change: {', '.join(entry.material_change_reasons)}"
            if entry.should_alert
            else f" · suppressed: {entry.suppressed_reason}"
        )
    )
    return [
        f"{entry.state:<16} score={entry.latest_score:>3} high={entry.highest_score:>3} "
        f"{entry.symbol}/{entry.coin_id}",
        f"  event: {entry.latest_event_name}",
        f"  cluster: {entry.cluster_id or 'legacy'}",
        f"  external: {entry.external_asset or 'unknown'} · relationship: {entry.relationship_type}",
        f"  first_seen: {entry.first_seen_at} · last_seen: {entry.last_seen_at}",
        f"  tier: {entry.latest_tier or 'unknown'} · source_count: {entry.source_count} · source: {entry.latest_source}",
        playbook_line,
        transition,
    ]


def _entry_sort_key(entry: EventWatchlistEntry) -> tuple[int, int, str]:
    return (-_state_rank(entry.state), -entry.highest_score, entry.symbol)


def _state_rank(state: str | EventWatchlistState | None) -> int:
    if isinstance(state, EventWatchlistState):
        state = state.value
    return _STATE_RANK.get(str(state or ""), -1)


def _state_value(state: str | EventWatchlistState | None) -> str:
    value = state.value if isinstance(state, EventWatchlistState) else str(state or "")
    return value if value in _STATE_RANK else EventWatchlistState.RAW_EVIDENCE.value
