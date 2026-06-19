"""Derivative/supply enrichment selection for active Event Alpha watchlist rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from . import event_watchlist


@dataclass(frozen=True)
class EventWatchlistEnrichmentResult:
    derivatives_source: str
    supply_source: str
    derivatives: dict[str, dict[str, Any]]
    supply: dict[str, dict[str, Any]]
    assets_requested: int
    warnings: tuple[str, ...] = ()


class WatchlistDerivativesProvider(Protocol):
    name: str

    def fetch_derivatives(
        self,
        entries: Iterable[event_watchlist.EventWatchlistEntry],
        *,
        max_assets: int = 50,
    ) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
        ...


class WatchlistSupplyProvider(Protocol):
    name: str

    def fetch_supply(
        self,
        entries: Iterable[event_watchlist.EventWatchlistEntry],
        *,
        max_assets: int = 50,
    ) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
        ...


class FixtureWatchlistDerivativesProvider:
    name = "fixture_derivatives"

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.rows = [dict(row) for row in rows if isinstance(row, Mapping)]

    def fetch_derivatives(
        self,
        entries: Iterable[event_watchlist.EventWatchlistEntry],
        *,
        max_assets: int = 50,
    ) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
        return _rows_for_entries(self.rows, entries, max_assets=max_assets), ()


class FixtureWatchlistSupplyProvider:
    name = "fixture_supply"

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.rows = [dict(row) for row in rows if isinstance(row, Mapping)]

    def fetch_supply(
        self,
        entries: Iterable[event_watchlist.EventWatchlistEntry],
        *,
        max_assets: int = 50,
    ) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
        return _rows_for_entries(self.rows, entries, max_assets=max_assets), ()


def enrichment_for_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    derivatives_source: str = "cycle",
    supply_source: str = "cycle",
    derivatives_rows: Iterable[Mapping[str, Any]] = (),
    supply_rows: Iterable[Mapping[str, Any]] = (),
    derivatives_provider: WatchlistDerivativesProvider | None = None,
    supply_provider: WatchlistSupplyProvider | None = None,
    max_assets: int = 50,
) -> EventWatchlistEnrichmentResult:
    """Return derivative/supply rows relevant to active watchlist assets.

    This is an artifact-only scaffold. It selects supplied fixture/cycle rows and
    deliberately does not fetch live provider data.
    """
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
    derivatives, derivative_warnings = _fetch_derivatives(
        active,
        source=derivatives_source,
        rows=derivatives_rows,
        provider=derivatives_provider,
        max_assets=max_assets,
    )
    supply, supply_warnings = _fetch_supply(
        active,
        source=supply_source,
        rows=supply_rows,
        provider=supply_provider,
        max_assets=max_assets,
    )
    warnings = tuple(dict.fromkeys((*derivative_warnings, *supply_warnings)))
    return EventWatchlistEnrichmentResult(
        derivatives_source=derivatives_source,
        supply_source=supply_source,
        derivatives=derivatives,
        supply=supply,
        assets_requested=len(active),
        warnings=warnings,
    )


def load_enrichment_rows(path: str | Path | None) -> list[dict[str, Any]]:
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
        for key in ("rows", "snapshots", "data", "supply", "derivatives"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _fetch_derivatives(
    entries: list[event_watchlist.EventWatchlistEntry],
    *,
    source: str,
    rows: Iterable[Mapping[str, Any]],
    provider: WatchlistDerivativesProvider | None,
    max_assets: int,
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    mode = str(source or "cycle").strip().lower()
    if mode in {"none", "off", "disabled"}:
        return {}, ()
    if provider is not None:
        try:
            return provider.fetch_derivatives(entries, max_assets=max_assets)
        except Exception as exc:  # noqa: BLE001 - fail-soft research scaffold
            return {}, (f"watchlist derivatives provider failed: {type(exc).__name__}: {exc}",)
    if mode in {"cycle", "fixture"}:
        data = _rows_for_entries(rows, entries, max_assets=max_assets)
        return data, () if data else (f"no {mode} derivative rows matched active watchlist assets",)
    return {}, (f"unknown watchlist derivatives source {source!r}",)


def _fetch_supply(
    entries: list[event_watchlist.EventWatchlistEntry],
    *,
    source: str,
    rows: Iterable[Mapping[str, Any]],
    provider: WatchlistSupplyProvider | None,
    max_assets: int,
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    mode = str(source or "cycle").strip().lower()
    if mode in {"none", "off", "disabled"}:
        return {}, ()
    if provider is not None:
        try:
            return provider.fetch_supply(entries, max_assets=max_assets)
        except Exception as exc:  # noqa: BLE001 - fail-soft research scaffold
            return {}, (f"watchlist supply provider failed: {type(exc).__name__}: {exc}",)
    if mode in {"cycle", "fixture"}:
        data = _rows_for_entries(rows, entries, max_assets=max_assets)
        return data, () if data else (f"no {mode} supply rows matched active watchlist assets",)
    return {}, (f"unknown watchlist supply source {source!r}",)


def _rows_for_entries(
    rows: Iterable[Mapping[str, Any]],
    entries: Iterable[event_watchlist.EventWatchlistEntry],
    *,
    max_assets: int,
) -> dict[str, dict[str, Any]]:
    wanted_coin_ids = {entry.coin_id.casefold() for entry in entries if entry.coin_id}
    wanted_symbols = {entry.symbol.upper() for entry in entries if entry.symbol}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        coin_id = str(row.get("coin_id") or row.get("id") or "").casefold()
        symbol = str(row.get("symbol") or row.get("base_symbol") or row.get("base_asset") or "").upper()
        if coin_id not in wanted_coin_ids and symbol not in wanted_symbols:
            continue
        data = dict(row)
        if coin_id:
            out[coin_id] = data
        if symbol:
            out[symbol] = data
        if len(out) >= max(1, int(max_assets or 1)) * 2:
            break
    return out
