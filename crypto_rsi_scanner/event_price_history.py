"""Research-only price fixture export for event-fade validation.

This module builds local OHLCV artifacts for validation samples. It does not
write live scanner storage, route alerts, open paper trades, or imply execution.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from . import backtest

PRICE_FIXTURE_SCHEMA_VERSION = "event_fade_outcome_prices_v1"
log = logging.getLogger(__name__)


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
    interval: str


def export_outcome_price_fixture(
    sample_rows: Iterable[Mapping[str, Any]],
    out_path: str | Path,
    *,
    days: int | None = None,
    fixture_dir: str | Path | None = None,
    cache_dir: str | Path | None = None,
    refresh_cache: bool = False,
    interval: str = "1d",
    now: datetime | None = None,
) -> EventFadeOutcomePriceExportResult:
    """Write a local price fixture for triggered validation rows."""
    rows = [dict(row) for row in sample_rows]
    assets = _triggered_assets(rows)
    resolved_days = days if days and days > 0 else _history_days(rows, now=now)
    resolved_interval = _normalize_interval(interval)
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
                interval=resolved_interval,
                fixture_dir=fixture_root,
                cache_dir=cache_root,
                refresh_cache=refresh_cache,
                session=session,
            )
            if frame is None or frame.empty:
                missing.append(asset.symbol)
                continue
            price_rows.extend(_price_rows(asset, frame, interval=resolved_interval))
    finally:
        if session is not None:
            session.close()

    payload = {
        "schema_version": PRICE_FIXTURE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": f"fixture:{fixture_root}:{resolved_interval}" if fixture_root else f"binance_{resolved_interval}_klines",
        "interval": resolved_interval,
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
        interval=resolved_interval,
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
    interval: str,
    fixture_dir: Path | None,
    cache_dir: Path | None,
    refresh_cache: bool,
    session: requests.Session | None,
) -> pd.DataFrame | None:
    pair = _binance_pair(asset.symbol)
    if fixture_dir is not None:
        frame = backtest.load_klines_fixture(pair, days, fixture_dir)
        return frame if frame is not None else backtest.load_klines_fixture(asset.symbol, days, fixture_dir)
    if interval == "1h":
        return _fetch_interval_klines(
            pair,
            days,
            interval=interval,
            session=session,
            cache_dir=cache_dir,
            refresh_cache=refresh_cache,
        )
    return backtest.fetch_klines(
        pair,
        days,
        session,
        cache_dir=cache_dir,
        refresh_cache=refresh_cache,
    )


def _fetch_interval_klines(
    symbol: str,
    days: int,
    *,
    interval: str,
    session: requests.Session | None,
    cache_dir: Path | None,
    refresh_cache: bool,
) -> pd.DataFrame | None:
    if interval == "1d":
        return backtest.fetch_klines(
            symbol,
            days,
            session,
            cache_dir=cache_dir,
            refresh_cache=refresh_cache,
        )
    cached = None if refresh_cache else _load_interval_klines_cache(cache_dir, symbol, days, interval)
    if cached is not None:
        return backtest._klines_rows_to_frame(cached)
    if session is None:
        return None
    rows = None
    for host in backtest._BINANCE_HOSTS:
        try:
            rows = _klines_paged_interval(host, symbol, days, interval, session)
            if rows:
                break
        except Exception as exc:  # noqa: BLE001
            log.debug("event-fade %s klines %s via %s failed: %s", interval, symbol, host, exc)
    if not rows:
        return None
    ordered = [rows[key] for key in sorted(rows)]
    _write_interval_klines_cache(cache_dir, symbol, days, interval, ordered)
    return backtest._klines_rows_to_frame(ordered)


def _klines_paged_interval(
    host: str,
    symbol: str,
    days: int,
    interval: str,
    session: requests.Session,
) -> dict[int, list] | None:
    interval_ms = _interval_ms(interval)
    end_ms = int(time.time() * 1000)
    cursor = end_ms - days * 86_400_000
    rows: dict[int, list] = {}
    while True:
        response = session.get(
            host,
            params={"symbol": symbol, "interval": interval, "limit": 1000, "startTime": cursor},
            timeout=20,
        )
        if response.status_code != 200:
            return rows or None
        batch = response.json()
        if not batch:
            break
        for row in batch:
            rows[int(row[0])] = row
        last_open = int(batch[-1][0])
        if len(batch) < 1000 or last_open + interval_ms >= end_ms:
            break
        cursor = last_open + interval_ms
    return rows or None


def _interval_cache_path(cache_dir: Path, symbol: str, days: int, interval: str) -> Path:
    return cache_dir / "event_fade_outcome_klines" / interval / f"{symbol}-{days}d.json"


def _load_interval_klines_cache(
    cache_dir: Path | None,
    symbol: str,
    days: int,
    interval: str,
) -> list | None:
    if cache_dir is None:
        return None
    path = _interval_cache_path(cache_dir, symbol, days, interval)
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("Ignoring unreadable event-fade outcome klines cache %s: %s", path, exc)
        return None
    return rows if isinstance(rows, list) and rows else None


def _write_interval_klines_cache(
    cache_dir: Path | None,
    symbol: str,
    days: int,
    interval: str,
    rows: list,
) -> None:
    if cache_dir is None:
        return
    path = _interval_cache_path(cache_dir, symbol, days, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _price_rows(asset: EventFadePriceAsset, frame: pd.DataFrame, *, interval: str) -> list[dict[str, Any]]:
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
            "interval": interval,
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


def _normalize_interval(value: str) -> str:
    interval = str(value or "1d").strip().lower()
    if interval not in {"1d", "1h"}:
        raise ValueError("event-fade outcome price interval must be '1d' or '1h'")
    return interval


def _interval_ms(interval: str) -> int:
    return 3_600_000 if interval == "1h" else 86_400_000


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
