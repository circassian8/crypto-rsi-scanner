"""Research-only price fixture export for event-fade validation.

This module builds local OHLCV artifacts for validation samples. It does not
write live scanner storage, route alerts, open paper trades, or imply execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from . import backtest

PRICE_FIXTURE_SCHEMA_VERSION = "event_fade_outcome_prices_v1"


@dataclass(frozen=True)
class EventFadePriceAsset:
    coin_id: str
    symbol: str


@dataclass(frozen=True)
class EventFadeOutcomePriceExportResult:
    out_path: Path
    assets_requested: int
    assets_written: int
    price_rows_written: int
    missing_assets: tuple[str, ...]
    days: int
    source: str


def export_outcome_price_fixture(
    sample_rows: Iterable[Mapping[str, Any]],
    out_path: str | Path,
    *,
    days: int | None = None,
    fixture_dir: str | Path | None = None,
    cache_dir: str | Path | None = None,
    refresh_cache: bool = False,
    now: datetime | None = None,
) -> EventFadeOutcomePriceExportResult:
    """Write a local price fixture for triggered validation rows."""
    rows = [dict(row) for row in sample_rows]
    assets = _triggered_assets(rows)
    resolved_days = days if days and days > 0 else _history_days(rows, now=now)
    fixture_root = Path(fixture_dir).expanduser() if fixture_dir else None
    cache_root = Path(cache_dir).expanduser() if cache_dir else None
    generated_at = _as_utc(now or datetime.now(timezone.utc)).isoformat()

    price_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    session = None if fixture_root else requests.Session()
    try:
        for asset in assets:
            frame = _load_asset_frame(
                asset,
                resolved_days,
                fixture_dir=fixture_root,
                cache_dir=cache_root,
                refresh_cache=refresh_cache,
                session=session,
            )
            if frame is None or frame.empty:
                missing.append(asset.symbol)
                continue
            price_rows.extend(_price_rows(asset, frame))
    finally:
        if session is not None:
            session.close()

    payload = {
        "schema_version": PRICE_FIXTURE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": f"fixture:{fixture_root}" if fixture_root else "binance_1d_klines",
        "days": resolved_days,
        "prices": price_rows,
    }
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return EventFadeOutcomePriceExportResult(
        out_path=out,
        assets_requested=len(assets),
        assets_written=len(assets) - len(missing),
        price_rows_written=len(price_rows),
        missing_assets=tuple(missing),
        days=resolved_days,
        source=str(payload["source"]),
    )


def _triggered_assets(rows: Iterable[Mapping[str, Any]]) -> tuple[EventFadePriceAsset, ...]:
    assets: dict[tuple[str, str], EventFadePriceAsset] = {}
    for row in rows:
        if str(row.get("signal_type") or "") != "SHORT_TRIGGERED":
            continue
        symbol = str(row.get("asset_symbol") or "").strip().upper()
        coin_id = str(row.get("asset_coin_id") or "").strip()
        if not symbol:
            continue
        key = (coin_id.casefold(), symbol)
        assets[key] = EventFadePriceAsset(coin_id=coin_id, symbol=symbol)
    return tuple(sorted(assets.values(), key=lambda asset: (asset.symbol, asset.coin_id)))


def _history_days(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    minimum_days: int = 30,
) -> int:
    current = _as_utc(now or datetime.now(timezone.utc))
    starts = [
        value
        for row in rows
        for value in (_dt(row.get("trigger_observed_at")), _dt(row.get("event_time")))
        if value is not None
    ]
    if not starts:
        return minimum_days
    age_days = max((current - min(starts)).total_seconds() / 86_400.0, 0.0)
    return max(minimum_days, int(age_days) + 8)


def _load_asset_frame(
    asset: EventFadePriceAsset,
    days: int,
    *,
    fixture_dir: Path | None,
    cache_dir: Path | None,
    refresh_cache: bool,
    session: requests.Session | None,
) -> pd.DataFrame | None:
    pair = _binance_pair(asset.symbol)
    if fixture_dir is not None:
        frame = backtest.load_klines_fixture(pair, days, fixture_dir)
        return frame if frame is not None else backtest.load_klines_fixture(asset.symbol, days, fixture_dir)
    return backtest.fetch_klines(
        pair,
        days,
        session,
        cache_dir=cache_dir,
        refresh_cache=refresh_cache,
    )


def _price_rows(asset: EventFadePriceAsset, frame: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ts, row in frame.sort_index().iterrows():
        close = _float(row.get("close"))
        if close is None or close <= 0:
            continue
        out.append({
            "asset_coin_id": asset.coin_id,
            "asset_symbol": asset.symbol,
            "timestamp": _timestamp_iso(ts),
            "close": close,
            "high": _float(row.get("high")) or close,
            "low": _float(row.get("low")) or close,
            "volume": _float(row.get("volume")),
            "quote_volume": _float(row.get("quote_volume")),
        })
    return out


def _timestamp_iso(value: object) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat()


def _binance_pair(symbol: str) -> str:
    symbol = str(symbol or "").strip().upper()
    return symbol if symbol.endswith("USDT") else f"{symbol}USDT"


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
