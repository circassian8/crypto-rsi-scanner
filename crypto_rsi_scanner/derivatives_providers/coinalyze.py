"""Fixture-backed Coinalyze-style derivatives provider."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_resolver import clean_text
from ..event_providers.manual_json import parse_datetime

log = logging.getLogger(__name__)


class CoinalyzeDerivativesProvider:
    name = "coinalyze"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = Path(path).expanduser() if path else None
        self.required = required

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        if self.path is None:
            return {}
        try:
            rows = _load_rows(self.path)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Coinalyze derivatives fixture load failed: %s", exc)
            return {}

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            snapshot = _snapshot(row)
            if snapshot is None:
                continue
            for key in _keys(row, snapshot):
                out[key] = snapshot
        return out


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("snapshots", raw.get("data")) if isinstance(raw, Mapping) else raw
    if not isinstance(rows, list):
        raise ValueError("Coinalyze fixture must be a list or {'snapshots': [...]}")
    out: list[Mapping[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"Coinalyze row {idx} must be an object")
        out.append(row)
    return out


def _snapshot(row: Mapping[str, Any]) -> dict[str, Any] | None:
    symbol = _base_symbol(row)
    if not symbol:
        return None
    timestamp = _parse_dt(row.get("timestamp") or row.get("time") or row.get("created_at"))
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "perp_available": bool(row.get("perp_available", True)),
        "open_interest": _float_or_none(row.get("open_interest") or row.get("oi")),
        "open_interest_24h_change_pct": _float_or_none(
            row.get("open_interest_24h_change_pct")
            or row.get("oi_24h_change_pct")
            or row.get("open_interest_change_24h")
        ),
        "open_interest_to_market_cap": _float_or_none(
            row.get("open_interest_to_market_cap")
            or row.get("oi_to_market_cap")
        ),
        "funding_rate_8h": _float_or_none(row.get("funding_rate_8h") or row.get("funding_rate")),
        "funding_rate_percentile": _float_or_none(row.get("funding_rate_percentile")),
        "futures_volume_24h": _float_or_none(row.get("futures_volume_24h") or row.get("volume_24h")),
        "perp_spot_volume_ratio": _float_or_none(row.get("perp_spot_volume_ratio")),
        "liquidations_24h": _float_or_none(row.get("liquidations_24h")),
        "long_short_ratio": _float_or_none(row.get("long_short_ratio")),
        "basis": _float_or_none(row.get("basis")),
    }


def _keys(row: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    values = [
        row.get("coin_id"),
        row.get("base_asset"),
        row.get("base_symbol"),
        snapshot.get("symbol"),
        row.get("symbol"),
        row.get("market_symbol"),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        for key in _key_variants(str(value)):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _key_variants(value: str) -> tuple[str, ...]:
    raw = value.strip()
    if not raw:
        return ()
    upper = raw.upper()
    lower = clean_text(raw)
    base = _strip_quote_suffix(upper)
    return tuple(dict.fromkeys((
        lower,
        upper,
        clean_text(base),
        base,
    )))


def _base_symbol(row: Mapping[str, Any]) -> str:
    explicit = row.get("base_symbol") or row.get("base_asset")
    if explicit:
        return str(explicit).upper()
    symbol = str(row.get("symbol") or row.get("market_symbol") or "").upper()
    return _strip_quote_suffix(symbol)


def _strip_quote_suffix(symbol: str) -> str:
    upper = symbol.upper().strip()
    raw = upper.replace("-", "").replace("_", "").replace("/", "")
    if (
        raw.endswith("PERP")
        and len(raw) > len("PERP")
        and (
            upper.endswith(("-PERP", "_PERP", "/PERP"))
            or raw.endswith(("USDTPERP", "USDPERP"))
        )
    ):
        raw = raw[: -len("PERP")]
    for suffix in ("USDT", "USD"):
        if raw.endswith(suffix) and len(raw) > len(suffix):
            raw = raw[: -len(suffix)]
    return raw


def _parse_dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
