"""Coinalyze-style derivatives provider for event-discovery research."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ..event_resolver import clean_text
from ..event_providers.manual_json import parse_datetime

log = logging.getLogger(__name__)

UrlOpen = Callable[[Request, float], Any]
Clock = Callable[[], float]


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class CoinalyzeDerivativesProvider:
    name = "coinalyze"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        api_key: str = "",
        symbols: Iterable[str] = (),
        base_url: str = "https://api.coinalyze.net/v1/",
        timeout: float = 10.0,
        history_interval: str = "1hour",
        lookback_hours: int = 24,
        convert_to_usd: bool = True,
        opener: UrlOpen | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.path = Path(path).expanduser() if path else None
        self.required = required
        self.live_enabled = live_enabled
        self.api_key = api_key
        self.symbols = tuple(symbol.strip() for symbol in symbols if str(symbol).strip())
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.history_interval = history_interval
        self.lookback_hours = lookback_hours
        self.convert_to_usd = convert_to_usd
        self.opener = opener or _urlopen_with_timeout
        self.clock = clock or time.time

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        if self.path is None and self.live_enabled:
            return self._fetch_live_snapshots()
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

    def _fetch_live_snapshots(self) -> dict[str, dict[str, Any]]:
        if not self.api_key:
            if self.required:
                raise ValueError("Coinalyze live derivatives fetch requires API key")
            log.warning("Coinalyze live derivatives fetch skipped: missing API key")
            return {}
        if not self.symbols:
            if self.required:
                raise ValueError("Coinalyze live derivatives fetch requires at least one symbol")
            log.warning("Coinalyze live derivatives fetch skipped: no symbols configured")
            return {}
        try:
            rows = self._fetch_live_rows()
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Coinalyze live derivatives fetch failed: %s", _safe_error(exc, self.api_key))
            return {}
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            snapshot = _snapshot(row)
            if snapshot is None:
                continue
            for key in _keys(row, snapshot):
                out[key] = snapshot
        return out

    def _fetch_live_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for symbols in _batches(self.symbols, 20):
            by_symbol = _base_rows(symbols)
            for item in self._get("open-interest", {"symbols": ",".join(symbols), "convert_to_usd": _bool_param(self.convert_to_usd)}):
                symbol = str(item.get("symbol") or "")
                if not symbol:
                    continue
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["open_interest"] = item.get("value")
                row["timestamp"] = _max_time(row.get("timestamp"), item.get("update"))
            for item in self._get("funding-rate", {"symbols": ",".join(symbols)}):
                symbol = str(item.get("symbol") or "")
                if not symbol:
                    continue
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["funding_rate_8h"] = item.get("value")
                row["timestamp"] = _max_time(row.get("timestamp"), item.get("update"))
            history_params = {
                "symbols": ",".join(symbols),
                "interval": self.history_interval,
                "from": str(int(self.clock()) - max(1, self.lookback_hours) * 3600),
                "to": str(int(self.clock())),
            }
            for item in self._get("open-interest-history", {**history_params, "convert_to_usd": _bool_param(self.convert_to_usd)}):
                symbol = str(item.get("symbol") or "")
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["open_interest_24h_change_pct"] = _history_change_pct(item.get("history"))
            for item in self._get("liquidation-history", {**history_params, "convert_to_usd": _bool_param(self.convert_to_usd)}):
                symbol = str(item.get("symbol") or "")
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["liquidations_24h"] = _liquidation_sum(item.get("history"))
            for item in self._get("long-short-ratio-history", history_params):
                symbol = str(item.get("symbol") or "")
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["long_short_ratio"] = _latest_history_value(item.get("history"), "r")
            for item in self._get("ohlcv-history", history_params):
                symbol = str(item.get("symbol") or "")
                row = by_symbol.setdefault(symbol, _live_base_row(symbol))
                row["futures_volume_24h"] = _history_sum(item.get("history"), "v")
            rows.extend(by_symbol.values())
        return rows

    def _get(self, path: str, params: Mapping[str, str]) -> list[Mapping[str, Any]]:
        url = urljoin(self.base_url, path) + "?" + urlencode(params)
        request = Request(url, headers={"Accept": "application/json", "api_key": self.api_key})
        with self.opener(request, self.timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"Coinalyze {path} response must be a list")
        return [dict(item) for item in raw if isinstance(item, Mapping)]


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


def _base_rows(symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
    return {symbol: _live_base_row(symbol) for symbol in symbols}


def _live_base_row(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market_symbol": symbol,
        "base_symbol": _strip_quote_suffix(symbol),
        "perp_available": True,
    }


def _snapshot(row: Mapping[str, Any]) -> dict[str, Any] | None:
    symbol = _base_symbol(row)
    if not symbol:
        return None
    timestamp = _parse_dt(row.get("timestamp") or row.get("time") or row.get("created_at"))
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "perp_available": bool(row.get("perp_available", True)),
        "open_interest": _float_or_none(_first_present(row, "open_interest", "oi")),
        "open_interest_24h_change_pct": _float_or_none(
            _first_present(row, "open_interest_24h_change_pct", "oi_24h_change_pct", "open_interest_change_24h")
        ),
        "open_interest_to_market_cap": _float_or_none(
            _first_present(row, "open_interest_to_market_cap", "oi_to_market_cap")
        ),
        "funding_rate_8h": _float_or_none(_first_present(row, "funding_rate_8h", "funding_rate")),
        "funding_rate_percentile": _float_or_none(row.get("funding_rate_percentile")),
        "futures_volume_24h": _float_or_none(_first_present(row, "futures_volume_24h", "volume_24h")),
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
    upper = upper.split(".", 1)[0]
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


def _first_present(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _batches(values: Iterable[str], size: int) -> Iterable[tuple[str, ...]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _history_values(history: object, field: str) -> list[float]:
    if not isinstance(history, list):
        return []
    out: list[float] = []
    for item in history:
        if not isinstance(item, Mapping):
            continue
        value = _float_or_none(item.get(field))
        if value is not None:
            out.append(value)
    return out


def _history_change_pct(history: object) -> float | None:
    values = _history_values(history, "c")
    if len(values) < 2:
        return None
    start = values[0]
    end = values[-1]
    if start == 0:
        return None
    return (end - start) / abs(start)


def _history_sum(history: object, field: str) -> float | None:
    values = _history_values(history, field)
    return sum(values) if values else None


def _liquidation_sum(history: object) -> float | None:
    if not isinstance(history, list):
        return None
    total = 0.0
    seen = False
    for item in history:
        if not isinstance(item, Mapping):
            continue
        for field in ("l", "s"):
            value = _float_or_none(item.get(field))
            if value is not None:
                total += value
                seen = True
    return total if seen else None


def _latest_history_value(history: object, field: str) -> float | None:
    values = _history_values(history, field)
    return values[-1] if values else None


def _max_time(left: object, right: object) -> object:
    left_dt = _parse_dt(left)
    right_dt = _parse_dt(right)
    if left_dt is None:
        return right
    if right_dt is None:
        return left
    return max(left_dt, right_dt).isoformat()


def _safe_error(exc: Exception, api_key: str) -> str:
    text = str(exc)
    if api_key:
        text = text.replace(api_key, "<coinalyze-api-key>")
    return text
