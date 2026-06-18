"""Market-row selection for active Event Alpha watchlist monitoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

from . import event_watchlist
from .client import CoinGeckoClient
from .event_models import EventDiscoveryResult
from .event_providers.coingecko_universe import _run_async


@dataclass(frozen=True)
class EventWatchlistMarketResult:
    source: str
    rows: list[dict[str, Any]]
    assets_requested: int
    rows_selected: int
    warnings: tuple[str, ...] = ()
    cache_status: str | None = None


class EventWatchlistMarketProvider(Protocol):
    name: str

    def fetch_market_rows(
        self,
        coin_ids: Iterable[str],
        *,
        max_assets: int = 50,
    ) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        ...


class FixtureWatchlistMarketProvider:
    """Targeted provider over caller-supplied fixture rows."""

    name = "fixture"

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self._rows = [dict(row) for row in rows if isinstance(row, Mapping)]

    def fetch_market_rows(
        self,
        coin_ids: Iterable[str],
        *,
        max_assets: int = 50,
    ) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        wanted = {str(coin_id or "").casefold() for coin_id in coin_ids if str(coin_id or "").strip()}
        out: list[dict[str, Any]] = []
        for row in self._rows:
            coin_id = str(row.get("coin_id") or row.get("id") or "").casefold()
            if coin_id in wanted:
                out.append(dict(row))
            if len(out) >= max_assets:
                break
        return out, ()


class CoinGeckoWatchlistMarketProvider:
    """Fail-soft targeted CoinGecko adapter.

    The optional fetcher keeps this module offline-testable. A live caller can
    inject a function that accepts coin ids and returns CoinGecko-style market
    rows; absent that, the provider reports a warning and returns no rows.
    """

    name = "coingecko"

    def __init__(
        self,
        fetcher: Callable[[tuple[str, ...]], Iterable[Mapping[str, Any]]] | None = None,
        *,
        live_enabled: bool = False,
        cache_ttl_seconds: int = 900,
        client_factory: Callable[[], Any] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self.live_enabled = live_enabled
        self.cache_ttl_seconds = max(0, int(cache_ttl_seconds or 0))
        self.client_factory = client_factory or CoinGeckoClient
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._cache: dict[tuple[str, ...], tuple[datetime, list[dict[str, Any]]]] = {}
        self.last_cache_status: str = "miss"

    def fetch_market_rows(
        self,
        coin_ids: Iterable[str],
        *,
        max_assets: int = 50,
    ) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        ids = tuple(dict.fromkeys(str(coin_id or "").strip() for coin_id in coin_ids if str(coin_id or "").strip()))
        ids = ids[: max(1, int(max_assets or 1))]
        if not ids:
            return [], ()
        cache_key = tuple(sorted(ids))
        cached = self._cache.get(cache_key)
        observed = self._as_utc(self.now_fn())
        if cached is not None and self.cache_ttl_seconds > 0:
            cached_at, rows = cached
            if cached_at + timedelta(seconds=self.cache_ttl_seconds) >= observed:
                self.last_cache_status = "hit"
                return [dict(row) for row in rows], ()
        try:
            if self._fetcher is not None:
                rows = [dict(row) for row in self._fetcher(ids) if isinstance(row, Mapping)]
            elif self.live_enabled:
                rows = self._fetch_live_rows(ids)
            else:
                self.last_cache_status = "disabled"
                return [], ("CoinGecko targeted watchlist lookup is not configured; using fallback rows",)
        except Exception as exc:  # pragma: no cover - defensive fail-soft guard
            self.last_cache_status = "error"
            return [], (f"CoinGecko targeted watchlist lookup failed: {type(exc).__name__}: {exc}",)
        self._cache[cache_key] = (observed, [dict(row) for row in rows])
        self.last_cache_status = "miss"
        return rows, ()

    def _fetch_live_rows(self, ids: tuple[str, ...]) -> list[dict[str, Any]]:
        return _run_async(self._fetch_live_rows_async(ids))

    async def _fetch_live_rows_async(self, ids: tuple[str, ...]) -> list[dict[str, Any]]:
        async with self.client_factory() as client:
            rows = await client._get(  # noqa: SLF001 - no public targeted markets helper yet
                "/coins/markets",
                {
                    "vs_currency": "usd",
                    "ids": ",".join(ids),
                    "order": "market_cap_desc",
                    "per_page": min(250, max(1, len(ids))),
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h,7d",
                },
            )
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def market_rows_for_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    source: str = "cycle",
    fixture_rows: Iterable[Mapping[str, Any]] = (),
    cycle_rows: Iterable[Mapping[str, Any]] = (),
    discovery_result: EventDiscoveryResult | None = None,
    targeted_lookup: bool = False,
    targeted_provider: EventWatchlistMarketProvider | None = None,
    max_assets: int = 50,
    cache_ttl_seconds: int = 900,
    now: datetime | None = None,
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
    targeted_rows: list[dict[str, Any]] = []
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if targeted_lookup and active:
        provider = targeted_provider or (
            FixtureWatchlistMarketProvider(fixture_rows)
            if clean_source == "fixture"
            else CoinGeckoWatchlistMarketProvider()
            if clean_source == "coingecko"
            else None
        )
        if provider is not None:
            fetched, provider_warnings = provider.fetch_market_rows(
                (entry.coin_id for entry in active),
                max_assets=max_assets,
            )
            warnings.extend(provider_warnings)
            targeted_rows = _select_rows(fetched, active)
            if targeted_rows:
                for row in targeted_rows:
                    row.setdefault("watchlist_market_source", getattr(provider, "name", clean_source))
                    row.setdefault("watchlist_market_observed_at", observed.isoformat())
                candidate_rows.extend(targeted_rows)
            provider_cache_status = getattr(provider, "last_cache_status", None)
        else:
            warnings.append(f"targeted watchlist market lookup is not available for source {clean_source!r}")
            provider_cache_status = None
    else:
        provider_cache_status = None
    if clean_source == "fixture":
        candidate_rows.extend(dict(row) for row in fixture_rows if isinstance(row, Mapping))
    elif clean_source in {"cycle", "coingecko"}:
        candidate_rows.extend(dict(row) for row in cycle_rows if isinstance(row, Mapping))
        if not candidate_rows and discovery_result is not None:
            candidate_rows = _market_rows_from_discovery(discovery_result)
    else:
        warnings.append(f"unknown watchlist market source {source!r}; no rows selected")
    selected = _select_rows(candidate_rows, active)
    if active and not selected:
        warnings.append(f"no {clean_source} market rows matched active watchlist assets")
    return EventWatchlistMarketResult(
        source=clean_source,
        rows=selected,
        assets_requested=len(active),
        rows_selected=len(selected),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_status=provider_cache_status or f"ttl={int(cache_ttl_seconds or 0)}s",
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
