"""Lean market input normalization and one explicitly authorized live read."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import math
import os
from typing import Mapping, Sequence

import pandas as pd

from crypto_rsi_scanner import config as shared_config
from crypto_rsi_scanner.client import CoinGeckoClient
from crypto_rsi_scanner.indicators import wilder_rsi

from .models import MarketSnapshot, UniverseAsset


LIVE_AUTH_ENV = "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"
MAX_LIVE_ROWS = 250


class _MarketDataError(ValueError):
    """Raised when market input cannot be interpreted without guessing units."""


MarketDataError = _MarketDataError


def live_provider_authorized(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return str(env.get(LIVE_AUTH_ENV, "")).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def fetch_live_market_rows(
    *,
    environ: Mapping[str, str] | None = None,
    limit: int = MAX_LIVE_ROWS,
) -> tuple[tuple[Mapping[str, object], ...], dict[str, object]]:
    """Make one already-authorized public CoinGecko market-list request."""

    if not live_provider_authorized(environ):
        raise MarketDataError(f"{LIVE_AUTH_ENV}=1 is required for a live scan")
    if shared_config.FIXTURE_DIR is not None:
        raise MarketDataError("fixture mode must be unset before a live scan")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 250:
        raise MarketDataError("live market row limit must be between 1 and 250")

    async def collect() -> tuple[tuple[Mapping[str, object], ...], dict[str, object]]:
        client = CoinGeckoClient(timeout_seconds=8.0, max_retries=1)
        async with client:
            rows = await client.get_top_markets_by_volume(limit)
        materialized = tuple(row for row in rows if isinstance(row, Mapping))
        telemetry = dict(client.last_request_telemetry or {})
        return materialized, {
            "endpoint_path": telemetry.get("endpoint_path"),
            "http_status": telemetry.get("http_status"),
            "result_count": len(materialized),
            "retry_count": telemetry.get("retry_count", 0),
            "duration_ms": telemetry.get("duration_ms"),
            "error_class": telemetry.get("error_class"),
        }

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(collect())
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError("live market collection failed") from exc
    raise MarketDataError("live market collection cannot run inside an active event loop")


def normalize_snapshots(
    rows: Sequence[Mapping[str, object]],
    assets: Sequence[UniverseAsset],
    *,
    observed_at: datetime,
    source_mode: str,
) -> tuple[MarketSnapshot, ...]:
    if observed_at.tzinfo is None:
        raise MarketDataError("market observation time must be timezone-aware")
    if source_mode not in {"live_no_send", "imported_snapshot", "fixture"}:
        raise MarketDataError("market source mode is invalid")
    rows_by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        canonical_id = row.get("id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            continue
        key = canonical_id.strip()
        if key in rows_by_id:
            raise MarketDataError("market canonical identity is duplicated")
        rows_by_id[key] = row

    snapshots: list[MarketSnapshot] = []
    for asset in assets:
        row = rows_by_id.get(asset.canonical_asset_id)
        if row is None or not asset.active or asset.bybit_instrument is None:
            continue
        snapshots.append(
            normalize_snapshot(
                row,
                asset,
                observed_at=observed_at,
                source_mode=source_mode,
            )
        )
    return tuple(snapshots)


def normalize_snapshot(
    row: Mapping[str, object],
    asset: UniverseAsset,
    *,
    observed_at: datetime,
    source_mode: str,
) -> MarketSnapshot:
    declared_unit = row.get("return_unit")
    if declared_unit not in (None, "", "percent_points", "percentage_points"):
        raise MarketDataError("market return unit is not percent points")
    price = _positive(row.get("current_price"), "current_price")
    market_cap = _positive(row.get("market_cap"), "market_cap")
    volume = _positive(row.get("total_volume"), "total_volume")
    sparkline = _sparkline(row.get("sparkline_in_7d"))
    return_1h = _return_pp(
        row.get("price_change_percentage_1h_in_currency"),
        "price_change_percentage_1h_in_currency",
    )
    return_24h = _return_pp(
        row.get("price_change_percentage_24h_in_currency"),
        "price_change_percentage_24h_in_currency",
    )
    return_7d = _return_pp(
        row.get("price_change_percentage_7d_in_currency"),
        "price_change_percentage_7d_in_currency",
    )
    rsi = _rsi(sparkline)
    spread = _optional_nonnegative(row.get("spread_bps"), "spread_bps")
    available_returns = sum(
        value is not None for value in (return_1h, return_24h, return_7d)
    )
    data_quality = (
        "complete"
        if available_returns >= 3 and rsi is not None
        else "usable"
        if available_returns >= 2
        else "insufficient_market_context"
    )
    return MarketSnapshot(
        canonical_asset_id=asset.canonical_asset_id,
        symbol=asset.symbol,
        name=asset.name,
        bybit_instrument=asset.bybit_instrument,
        observed_at=observed_at.astimezone(timezone.utc).isoformat(),
        source_mode=source_mode,
        price_usd=price,
        market_cap_usd=market_cap,
        volume_usd_24h=volume,
        turnover_ratio_24h=volume / market_cap,
        return_1h_pp=return_1h,
        return_24h_pp=return_24h,
        return_7d_pp=return_7d,
        rsi_14=rsi,
        spread_bps=spread,
        sparkline_prices=sparkline,
        return_basis="coingecko_direct_percent_point_fields",
        rsi_basis=(
            "wilder_14_on_coingecko_7d_sparkline_points_proxy"
            if rsi is not None
            else "unavailable_insufficient_sparkline"
        ),
        data_quality=data_quality,
    )


def _sparkline(value: object) -> tuple[float, ...]:
    if not isinstance(value, Mapping):
        return ()
    prices = value.get("price")
    if not isinstance(prices, list) or len(prices) > 500:
        return ()
    normalized: list[float] = []
    for item in prices:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return ()
        parsed = float(item)
        if not math.isfinite(parsed) or parsed <= 0:
            return ()
        normalized.append(parsed)
    return tuple(normalized)


def _rsi(prices: Sequence[float]) -> float | None:
    if len(prices) < 15:
        return None
    value = float(wilder_rsi(pd.Series(prices, dtype=float), period=14).iloc[-1])
    return value if math.isfinite(value) else None


def _positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is missing or invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise MarketDataError(f"{label} must be positive and finite")
    return parsed


def _return_pp(value: object, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or abs(parsed) > 500:
        raise MarketDataError(f"{label} is outside plausible percent-point bounds")
    return parsed


def _optional_nonnegative(value: object, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0 or parsed > 10_000:
        raise MarketDataError(f"{label} is outside plausible bounds")
    return parsed


__all__ = (
    "LIVE_AUTH_ENV",
    "MAX_LIVE_ROWS",
    "MarketDataError",
    "fetch_live_market_rows",
    "live_provider_authorized",
    "normalize_snapshot",
    "normalize_snapshots",
)
