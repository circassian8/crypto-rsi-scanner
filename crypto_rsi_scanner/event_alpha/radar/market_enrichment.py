"""Research-only market enrichment for event-discovery candidates."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import config, universe
import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
from ...client import CoinGeckoClient
from ...event_providers.coingecko_universe import load_market_rows
from . import market_units as event_market_units
from .resolver import clean_text

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventMarketEnrichmentConfig:
    enabled: bool = False
    path: Path | None = None
    live: bool = False
    fetch_limit: int = 0
    limit: int | None = None


def load_market_enrichment_rows(
    path: str | Path | None,
    *,
    live: bool = False,
    fetch_limit: int = 0,
    limit: int | None = None,
    client_factory=CoinGeckoClient,
    fail_soft: bool = False,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Load CoinGecko-style market rows for research-only enrichment."""
    rows, warnings = load_market_enrichment_rows_safe(
        path,
        live=live,
        fetch_limit=fetch_limit,
        limit=limit,
        client_factory=client_factory,
        fail_soft=fail_soft,
        provider_health_cfg=provider_health_cfg,
        now=now,
    )
    if warnings and not fail_soft:
        # ``load_market_enrichment_rows_safe`` only returns warnings without
        # raising when fail_soft=True or a provider is already in backoff.
        raise RuntimeError("; ".join(warnings))
    return rows


def load_market_enrichment_rows_safe(
    path: str | Path | None,
    *,
    live: bool = False,
    fetch_limit: int = 0,
    limit: int | None = None,
    client_factory=CoinGeckoClient,
    fail_soft: bool = True,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Load CoinGecko-style market rows and optionally fail soft.

    Direct non-fail-soft callers keep the previous raising behavior. Notification
    burn-in callers can set ``fail_soft`` and receive an empty row set plus
    warning text when live CoinGecko is unavailable.
    """
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    observed = _as_utc(now or datetime.now(timezone.utc))
    try:
        if path:
            rows.extend(load_market_rows(path))
        elif live:
            if provider_health_cfg is not None:
                decision = event_provider_health.provider_allowed(
                    "coingecko",
                    cfg=provider_health_cfg,
                    now=observed,
                    provider_service="coingecko",
                    provider_role="market_enrichment",
                )
                if not decision.allowed:
                    warning = decision.reason or "provider coingecko:market_enrichment in backoff"
                    return [], (warning,)
            rows.extend(_run_async(_fetch_live_markets(
                fetch_limit=fetch_limit,
                limit=limit,
                client_factory=client_factory,
            )))
            if provider_health_cfg is not None and decision.reason != "provider_backoff_ignored_for_run":
                event_provider_health.record_provider_success(
                    "coingecko",
                    cfg=provider_health_cfg,
                    now=observed,
                    provider_kind="enrichment",
                    provider_service="coingecko",
                    provider_role="market_enrichment",
                )
    except Exception as exc:  # noqa: BLE001 - notification/research fail-soft path
        if provider_health_cfg is not None and live:
            event_provider_health.record_provider_failure(
                "coingecko",
                exc,
                cfg=provider_health_cfg,
                now=observed,
                provider_kind="enrichment",
                provider_service="coingecko",
                provider_role="market_enrichment",
            )
        warning = f"market_enrichment_live_fetch_failed: {type(exc).__name__}"
        log.warning("CoinGecko live market enrichment failed: %s", exc)
        if not fail_soft:
            raise
        warnings.append(warning)
        rows = []
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows, tuple(dict.fromkeys(warnings))


def market_snapshots_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Build market snapshot payloads keyed by coin id/symbol/name aliases."""
    timestamp = _as_utc(now or datetime.now(timezone.utc))
    snapshots: dict[str, dict[str, Any]] = {}
    for row in rows:
        snapshot = market_snapshot_from_row(row, now=timestamp)
        if not snapshot.get("coin_id") and not snapshot.get("symbol"):
            continue
        for key in _market_keys(row, snapshot):
            snapshots.setdefault(key, snapshot)
    return snapshots


def market_snapshot_from_row(row: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    timestamp = _as_utc(now or datetime.now(timezone.utc))
    prices = _sparkline_prices(row)
    price = _float(row.get("current_price"))
    market_cap = _float(row.get("market_cap"))
    volume_24h = _float(row.get("total_volume"))
    snapshot = {
        "coin_id": _text(row.get("id")),
        "symbol": _text(row.get("symbol")).upper(),
        "timestamp": timestamp.isoformat(),
        "return_unit": event_market_units.RETURN_UNIT_FRACTION,
        "price": price,
        "volume_24h": volume_24h,
        "spot_volume_24h": volume_24h,
        "market_cap": market_cap,
        "fdv": _float(row.get("fully_diluted_valuation")),
        "return_1h": _sparkline_return(prices, 1),
        "return_4h": _sparkline_return(prices, 4),
        "return_24h": _percent_to_fraction(row.get("price_change_percentage_24h_in_currency")),
        "return_72h": _sparkline_return(prices, 72),
        "return_7d": _percent_to_fraction(row.get("price_change_percentage_7d_in_currency")),
        "distance_from_20d_ma": _distance_from_window_average(prices, 20),
        "volume_zscore_24h": _float(row.get("volume_zscore_24h")),
    }
    if snapshot["return_24h"] is None:
        snapshot["return_24h"] = _sparkline_return(prices, 24)
    return {key: value for key, value in snapshot.items() if value is not None}


def volume_to_market_cap(row: Mapping[str, Any]) -> float | None:
    volume = _float(row.get("total_volume"))
    market_cap = _float(row.get("market_cap"))
    if volume is None or market_cap is None or market_cap <= 0:
        return None
    return volume / market_cap


def row_return_24h(row: Mapping[str, Any]) -> float | None:
    value = _percent_to_fraction(row.get("price_change_percentage_24h_in_currency"))
    if value is not None:
        return value
    return _sparkline_return(_sparkline_prices(row), 24)


def row_return_7d(row: Mapping[str, Any]) -> float | None:
    return _percent_to_fraction(row.get("price_change_percentage_7d_in_currency"))


async def _fetch_live_markets(*, fetch_limit: int, limit: int | None, client_factory) -> list[dict[str, Any]]:
    target = limit or config.TOP_N
    fetch_n = fetch_limit or universe.candidate_count(target)
    async with client_factory() as client:
        rows = await client.get_top_markets(fetch_n)
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    close = getattr(coro, "close", None)
    if close:
        close()
    raise RuntimeError("CoinGecko live market enrichment cannot run inside an active event loop")


def _market_keys(row: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    raw_values = (
        snapshot.get("coin_id"),
        snapshot.get("symbol"),
        row.get("name"),
    )
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        text = _text(value)
        if not text:
            continue
        for key in (clean_text(text), text.upper()):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _sparkline_prices(row: Mapping[str, Any]) -> tuple[float, ...]:
    sparkline = row.get("sparkline_in_7d")
    prices = sparkline.get("price") if isinstance(sparkline, Mapping) else None
    if not isinstance(prices, list):
        return ()
    out: list[float] = []
    for value in prices:
        parsed = _float(value)
        if parsed is not None and parsed > 0:
            out.append(parsed)
    return tuple(out)


def _sparkline_return(prices: tuple[float, ...], hours: int) -> float | None:
    if len(prices) <= hours:
        return None
    start = prices[-(hours + 1)]
    end = prices[-1]
    if start <= 0:
        return None
    return end / start - 1.0


def _distance_from_window_average(prices: tuple[float, ...], window: int) -> float | None:
    if len(prices) < window:
        return None
    window_prices = prices[-window:]
    avg = sum(window_prices) / len(window_prices)
    if avg <= 0:
        return None
    return prices[-1] / avg - 1.0


def _percent_to_fraction(value: object) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return parsed / 100.0


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
