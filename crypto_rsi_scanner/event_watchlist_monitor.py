"""Research-only active watchlist monitor for Event Alpha Radar."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_market_enrichment, event_watchlist


ACTIVE_STATES = {
    event_watchlist.EventWatchlistState.RADAR.value,
    event_watchlist.EventWatchlistState.WATCHLIST.value,
    event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
    event_watchlist.EventWatchlistState.EVENT_PASSED.value,
    event_watchlist.EventWatchlistState.ARMED.value,
}

MONITOR_HINT_TO_ROUTER_REASON = {
    "EVENT_TIME_APPROACHING": "event_time_upgrade",
    "EVENT_PASSED": "event_time_upgrade",
    "POST_EVENT_MONITORING": "event_time_upgrade",
    "DERIVATIVES_HEATED": "derivatives_crowding_upgrade",
    "MARKET_SCORE_JUMP": "score_jump",
}


@dataclass(frozen=True)
class EventWatchlistMonitorRow:
    key: str
    symbol: str
    coin_id: str
    state: str
    event_name: str
    event_time: str | None
    event_countdown_hours: float | None
    event_age_hours: float | None
    current_price: float | None
    return_24h: float | None
    return_72h: float | None
    return_7d: float | None
    volume_to_market_cap: float | None
    volume_zscore_24h: float | None
    derivatives_crowding: int
    cluster_confidence: int
    state_transition_hints: tuple[str, ...]
    material_update: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventWatchlistMonitorResult:
    state_path: Path
    observed_at: str
    active_entries: int
    skipped_expired: int
    rows: list[EventWatchlistMonitorRow]


def monitor_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    market_rows: Iterable[Mapping[str, Any]] = (),
    now: datetime | None = None,
) -> EventWatchlistMonitorResult:
    """Refresh active watchlist rows with market/derivative observations.

    This produces synthetic research updates only. It never creates
    TRIGGERED_FADE; deterministic event_fade output remains the sole trigger
    source in the main Event Alpha pipeline.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    market_by_key = _market_by_key(market_rows, observed)
    rows: list[EventWatchlistMonitorRow] = []
    skipped = 0
    for entry in read_result.entries:
        if entry.state == event_watchlist.EventWatchlistState.EXPIRED.value:
            skipped += 1
            continue
        if entry.state not in ACTIVE_STATES:
            continue
        rows.append(_row_for_entry(entry, market_by_key, observed))
    return EventWatchlistMonitorResult(
        state_path=read_result.state_path,
        observed_at=observed.isoformat(),
        active_entries=len(rows),
        skipped_expired=skipped,
        rows=rows,
    )


def apply_monitor_updates_to_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    monitor_result: EventWatchlistMonitorResult,
    *,
    route_updates: bool = True,
    score_jump_threshold: int = 10,
) -> event_watchlist.EventWatchlistReadResult:
    """Return a read result with material monitor updates expressed for router policy.

    The monitor is observation-only. This adapter deliberately reuses the
    router's existing material-change fields and never promotes a row to
    TRIGGERED_FADE.
    """
    if not route_updates:
        return read_result
    row_by_key = {
        row.key: row
        for row in monitor_result.rows
        if row.material_update
    }
    if not row_by_key:
        return read_result
    updated: list[event_watchlist.EventWatchlistEntry] = []
    for entry in read_result.entries:
        row = row_by_key.get(entry.key)
        if row is None:
            updated.append(entry)
            continue
        reasons = tuple(dict.fromkeys(
            MONITOR_HINT_TO_ROUTER_REASON[hint]
            for hint in row.state_transition_hints
            if hint in MONITOR_HINT_TO_ROUTER_REASON
        ))
        if not reasons:
            updated.append(entry)
            continue
        next_state = entry.state
        if (
            "EVENT_PASSED" in row.state_transition_hints
            and entry.state not in {
                event_watchlist.EventWatchlistState.ARMED.value,
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_watchlist.EventWatchlistState.INVALIDATED.value,
                event_watchlist.EventWatchlistState.EXPIRED.value,
            }
        ):
            next_state = event_watchlist.EventWatchlistState.EVENT_PASSED.value
        if next_state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
            next_state = entry.state
        updated.append(replace(
            entry,
            state=next_state,
            previous_state=entry.state if next_state != entry.state else entry.previous_state,
            last_seen_at=monitor_result.observed_at,
            score_jump=max(
                entry.score_jump,
                score_jump_threshold if "score_jump" in reasons else 0,
            ),
            event_time_upgraded=entry.event_time_upgraded or "event_time_upgrade" in reasons,
            derivatives_crowding_upgraded=(
                entry.derivatives_crowding_upgraded or "derivatives_crowding_upgrade" in reasons
            ),
            material_change_reasons=tuple(dict.fromkeys((*entry.material_change_reasons, *reasons))),
            should_alert=True,
            suppressed_reason=None,
            warnings=tuple(dict.fromkeys((
                *entry.warnings,
                "watchlist_monitor:" + ",".join(row.state_transition_hints),
            ))),
        ))
    return event_watchlist.EventWatchlistReadResult(
        state_path=read_result.state_path,
        rows_read=read_result.rows_read,
        entries=updated,
        latest_only=read_result.latest_only,
    )


def format_watchlist_monitor_report(result: EventWatchlistMonitorResult) -> str:
    lines = [
        "=" * 76,
        "EVENT WATCHLIST MONITOR (research-only; no new source required)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"observed_at: {result.observed_at}",
        f"active_entries: {result.active_entries} · skipped_expired={result.skipped_expired}",
    ]
    if not result.rows:
        lines.append("")
        lines.append("No active watchlist rows to monitor.")
        return "\n".join(lines)
    material = [row for row in result.rows if row.material_update]
    lines.append(f"material_updates: {len(material)}")
    lines.append("")
    for row in result.rows:
        marker = "MATERIAL" if row.material_update else "observe"
        lines.append(
            f"{marker:<9} {row.state:<13} {row.symbol}/{row.coin_id} "
            f"r24={_fmt_pct(row.return_24h)} r72={_fmt_pct(row.return_72h)} r7d={_fmt_pct(row.return_7d)}"
        )
        lines.append(f"  event: {row.event_name}")
        if row.event_countdown_hours is not None:
            lines.append(f"  countdown_hours: {row.event_countdown_hours:.1f}")
        if row.event_age_hours is not None:
            lines.append(f"  event_age_hours: {row.event_age_hours:.1f}")
        lines.append(
            f"  derivatives={row.derivatives_crowding} cluster_conf={row.cluster_confidence} "
            f"volume/mcap={_fmt_num(row.volume_to_market_cap)} vz={_fmt_num(row.volume_zscore_24h)}"
        )
        if row.state_transition_hints:
            lines.append("  hints: " + ", ".join(row.state_transition_hints))
        if row.warnings:
            lines.append("  warnings: " + "; ".join(row.warnings))
    return "\n".join(lines).rstrip()


def load_market_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [dict(row) for row in raw if isinstance(row, Mapping)]
    if isinstance(raw, Mapping):
        for key in ("coins", "markets", "data", "rows"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _row_for_entry(
    entry: event_watchlist.EventWatchlistEntry,
    market_by_key: Mapping[str, Mapping[str, Any]],
    observed: datetime,
) -> EventWatchlistMonitorRow:
    market = market_by_key.get(entry.coin_id.casefold()) or market_by_key.get(entry.symbol.upper()) or {}
    current_price = _float(market.get("price") or market.get("current_price") or entry.latest_market_snapshot.get("price"))
    return_24h = _float(market.get("return_24h") or entry.latest_market_snapshot.get("return_24h"))
    return_72h = _float(market.get("return_72h") or entry.latest_market_snapshot.get("return_72h"))
    return_7d = _float(market.get("return_7d") or entry.latest_market_snapshot.get("return_7d"))
    volume_mcap = _float(market.get("volume_to_market_cap") or entry.latest_market_snapshot.get("volume_to_market_cap"))
    volume_z = _float(market.get("volume_zscore_24h") or entry.latest_market_snapshot.get("volume_zscore_24h"))
    derivatives = _int(entry.latest_score_components.get("derivatives_crowding"))
    cluster_conf = _int(entry.latest_score_components.get("cluster_confidence"))
    event_ts = _dt(entry.event_time)
    countdown = None
    age = None
    hints: list[str] = []
    if event_ts is not None:
        delta_hours = (event_ts - observed).total_seconds() / 3600.0
        if delta_hours >= 0:
            countdown = round(delta_hours, 4)
            if delta_hours <= 24:
                hints.append("EVENT_TIME_APPROACHING")
        else:
            age = round(abs(delta_hours), 4)
            hints.append("EVENT_PASSED")
            hints.append("POST_EVENT_MONITORING")
    if derivatives >= 50:
        hints.append("DERIVATIVES_HEATED")
    if (return_24h is not None and abs(return_24h) >= 0.15) or (volume_z is not None and volume_z >= 3.0):
        hints.append("MARKET_SCORE_JUMP")
    material = any(
        hint in set(hints)
        for hint in {"EVENT_TIME_APPROACHING", "EVENT_PASSED", "DERIVATIVES_HEATED", "MARKET_SCORE_JUMP"}
    )
    warnings = tuple(w for w in entry.warnings if w)
    if entry.state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        warnings = (*warnings, "monitor does not create triggered fade")
    return EventWatchlistMonitorRow(
        key=entry.key,
        symbol=entry.symbol,
        coin_id=entry.coin_id,
        state=entry.state,
        event_name=entry.latest_event_name,
        event_time=entry.event_time,
        event_countdown_hours=countdown,
        event_age_hours=age,
        current_price=current_price,
        return_24h=return_24h,
        return_72h=return_72h,
        return_7d=return_7d,
        volume_to_market_cap=volume_mcap,
        volume_zscore_24h=volume_z,
        derivatives_crowding=derivatives,
        cluster_confidence=cluster_conf,
        state_transition_hints=tuple(dict.fromkeys(hints)),
        material_update=material,
        warnings=warnings,
    )


def _market_by_key(rows: Iterable[Mapping[str, Any]], observed: datetime) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        snapshot = event_market_enrichment.market_snapshot_from_row(row, now=observed)
        enriched = dict(row)
        enriched.update(snapshot)
        volume_mcap = event_market_enrichment.volume_to_market_cap(row)
        if volume_mcap is not None:
            enriched["volume_to_market_cap"] = volume_mcap
        coin_id = str(enriched.get("coin_id") or enriched.get("id") or "").casefold()
        symbol = str(enriched.get("symbol") or "").upper()
        if coin_id:
            out[coin_id] = enriched
        if symbol:
            out[symbol] = enriched
    return out


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.1f}%"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
