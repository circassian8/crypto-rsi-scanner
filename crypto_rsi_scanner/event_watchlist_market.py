"""Market-row selection for active Event Alpha watchlist monitoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_watchlist
from .event_models import EventDiscoveryResult


@dataclass(frozen=True)
class EventWatchlistMarketResult:
    source: str
    rows: list[dict[str, Any]]
    assets_requested: int
    rows_selected: int
    warnings: tuple[str, ...] = ()


def market_rows_for_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    source: str = "cycle",
    fixture_rows: Iterable[Mapping[str, Any]] = (),
    cycle_rows: Iterable[Mapping[str, Any]] = (),
    discovery_result: EventDiscoveryResult | None = None,
    targeted_lookup: bool = False,
    max_assets: int = 50,
) -> EventWatchlistMarketResult:
    """Return market rows relevant to active watchlist assets.

    This module only selects already-available rows in Phase 1. Targeted live
    lookup is represented as a fail-soft warning until a concrete provider is
    approved.
    """
    clean_source = str(source or "cycle").strip().lower()
    active = [
        entry for entry in read_result.entries
        if entry.state in {
            event_watchlist.EventWatchlistState.RADAR.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
    ][: max(1, int(max_assets or 1))]
    warnings: list[str] = []
    if clean_source in {"off", "none", "disabled"}:
        return EventWatchlistMarketResult(clean_source, [], len(active), 0)
    candidate_rows: list[dict[str, Any]] = []
    if clean_source == "fixture":
        candidate_rows = [dict(row) for row in fixture_rows if isinstance(row, Mapping)]
    elif clean_source in {"cycle", "coingecko"}:
        candidate_rows = [dict(row) for row in cycle_rows if isinstance(row, Mapping)]
        if not candidate_rows and discovery_result is not None:
            candidate_rows = _market_rows_from_discovery(discovery_result)
    else:
        warnings.append(f"unknown watchlist market source {source!r}; no rows selected")
    if targeted_lookup:
        warnings.append("targeted watchlist market lookup is not configured; using available rows only")
    selected = _select_rows(candidate_rows, active)
    if active and not selected:
        warnings.append(f"no {clean_source} market rows matched active watchlist assets")
    return EventWatchlistMarketResult(
        source=clean_source,
        rows=selected,
        assets_requested=len(active),
        rows_selected=len(selected),
        warnings=tuple(dict.fromkeys(warnings)),
    )


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


def _select_rows(
    rows: Iterable[Mapping[str, Any]],
    entries: Iterable[event_watchlist.EventWatchlistEntry],
) -> list[dict[str, Any]]:
    wanted_coin_ids = {entry.coin_id.casefold() for entry in entries if entry.coin_id}
    wanted_symbols = {entry.symbol.upper() for entry in entries if entry.symbol}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        coin_id = str(row.get("coin_id") or row.get("id") or "").casefold()
        symbol = str(row.get("symbol") or "").upper()
        if coin_id not in wanted_coin_ids and symbol not in wanted_symbols:
            continue
        key = coin_id or symbol
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _market_rows_from_discovery(result: EventDiscoveryResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in result.raw_events:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        for key in ("market", "asset", "anomaly"):
            row = payload.get(key)
            if isinstance(row, Mapping):
                merged = dict(row)
                if "symbol" not in merged:
                    merged["symbol"] = payload.get("symbol")
                if "coin_id" not in merged:
                    merged["coin_id"] = payload.get("coin_id") or payload.get("id")
                rows.append(merged)
    return rows
