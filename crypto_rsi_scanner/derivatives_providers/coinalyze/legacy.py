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

from ...event_resolver import clean_text
from ...event_providers.manual_json import parse_datetime

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
        base_symbols: Iterable[str] = (),
        auto_symbols: bool = True,
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
        self.base_symbols = tuple(_normalize_base_symbol(symbol) for symbol in base_symbols if str(symbol).strip())
        self.auto_symbols = auto_symbols
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.history_interval = history_interval
        self.lookback_hours = lookback_hours
        self.convert_to_usd = convert_to_usd
        self.opener = opener or _urlopen_with_timeout
        self.clock = clock or time.time
        self.last_warnings: tuple[str, ...] = ()

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        return _coinalyze_fetch_snapshots(self)

    def _fetch_live_snapshots(self) -> dict[str, dict[str, Any]]:
        return _coinalyze_fetch_live_snapshots(self)

    def _live_symbols(self) -> tuple[str, ...]:
        return _coinalyze_live_symbols(self)

    def _fetch_live_rows(self, live_symbols: Iterable[str]) -> list[dict[str, Any]]:
        return _coinalyze_fetch_live_rows(self, live_symbols)

    def _get(self, path: str, params: Mapping[str, str]) -> list[Mapping[str, Any]]:
        return _coinalyze_get(self, path, params)

    def _get_optional(self, path: str, params: Mapping[str, str]) -> list[Mapping[str, Any]]:
        return _coinalyze_get_optional(self, path, params)


def _coinalyze_fetch_snapshots(provider: CoinalyzeDerivativesProvider) -> dict[str, dict[str, Any]]:
    provider.last_warnings = ()
    if provider.path is None and provider.live_enabled:
        return provider._fetch_live_snapshots()
    if provider.path is None:
        return {}
    try:
        rows = _load_rows(provider.path)
    except Exception as exc:  # noqa: BLE001
        warning = f"Coinalyze derivatives fixture load failed: {exc}"
        provider.last_warnings = (warning,)
        if provider.required:
            raise
        log.warning(warning)
        return {}
    return _snapshots_by_key(rows)


def _coinalyze_fetch_live_snapshots(provider: CoinalyzeDerivativesProvider) -> dict[str, dict[str, Any]]:
    if not provider.api_key:
        warning = "Coinalyze live derivatives fetch skipped: missing API key"
        provider.last_warnings = (warning,)
        if provider.required:
            raise ValueError("Coinalyze live derivatives fetch requires API key")
        log.warning(warning)
        return {}
    try:
        symbols = provider._live_symbols()
        if not symbols:
            warning = "Coinalyze live derivatives fetch skipped: no symbols configured"
            provider.last_warnings = (warning,)
            if provider.required:
                raise ValueError("Coinalyze live derivatives fetch requires at least one symbol")
            log.warning(warning)
            return {}
        rows = provider._fetch_live_rows(symbols)
    except Exception as exc:  # noqa: BLE001
        safe_error = _safe_error(exc, provider.api_key)
        warning = f"Coinalyze live derivatives fetch failed: {safe_error}"
        provider.last_warnings = (warning,)
        if provider.required:
            raise
        log.warning(warning)
        return {}
    provider.last_warnings = tuple(dict.fromkeys(provider.last_warnings))
    return _snapshots_by_key(rows)


def _snapshots_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        snapshot = _snapshot(row)
        if snapshot is None:
            continue
        for key in _keys(row, snapshot):
            out[key] = snapshot
    return out


def _coinalyze_live_symbols(provider: CoinalyzeDerivativesProvider) -> tuple[str, ...]:
    if provider.symbols:
        return provider.symbols
    if not provider.auto_symbols or not provider.base_symbols:
        return ()
    markets = provider._get("future-markets", {})
    return resolve_future_market_symbols(markets, provider.base_symbols)


def _coinalyze_fetch_live_rows(
    provider: CoinalyzeDerivativesProvider,
    live_symbols: Iterable[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbols in _batches(live_symbols, 20):
        by_symbol = _base_rows(symbols)
        _coinalyze_apply_open_interest(provider, symbols, by_symbol)
        _coinalyze_apply_funding(provider, symbols, by_symbol)
        _coinalyze_apply_predicted_funding(provider, symbols, by_symbol)
        history_params = _coinalyze_history_params(provider, symbols)
        _coinalyze_apply_open_interest_history(provider, history_params, by_symbol)
        _coinalyze_apply_liquidation_history(provider, history_params, by_symbol)
        _coinalyze_apply_long_short_history(provider, history_params, by_symbol)
        _coinalyze_apply_ohlcv_history(provider, history_params, by_symbol)
        rows.extend(by_symbol.values())
    return rows


def _coinalyze_get(
    provider: CoinalyzeDerivativesProvider,
    path: str,
    params: Mapping[str, str],
) -> list[Mapping[str, Any]]:
    url = urljoin(provider.base_url, path) + "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "api_key": provider.api_key})
    with provider.opener(request, provider.timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Coinalyze {path} response must be a list")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _coinalyze_get_optional(
    provider: CoinalyzeDerivativesProvider,
    path: str,
    params: Mapping[str, str],
) -> list[Mapping[str, Any]]:
    try:
        return provider._get(path, params)
    except Exception as exc:  # noqa: BLE001 - optional live metric must fail soft
        warning = f"Coinalyze optional endpoint {path} skipped: {_safe_error(exc, provider.api_key)}"
        provider.last_warnings = tuple(dict.fromkeys((*provider.last_warnings, warning)))
        log.warning(warning)
        return []


def _coinalyze_apply_open_interest(
    provider: CoinalyzeDerivativesProvider,
    symbols: Iterable[str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    for item in provider._get("open-interest", {"symbols": ",".join(symbols), "convert_to_usd": _bool_param(provider.convert_to_usd)}):
        symbol = str(item.get("symbol") or "")
        if not symbol:
            continue
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["open_interest"] = item.get("value")
        row["open_interest_timestamp"] = _max_time(row.get("open_interest_timestamp"), item.get("update"))
        row["open_interest_unit"] = "usd_notional" if provider.convert_to_usd else "provider_native"
        row["timestamp"] = _max_time(row.get("timestamp"), item.get("update"))


def _coinalyze_apply_funding(
    provider: CoinalyzeDerivativesProvider,
    symbols: Iterable[str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    for item in provider._get("funding-rate", {"symbols": ",".join(symbols)}):
        symbol = str(item.get("symbol") or "")
        if not symbol:
            continue
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["funding_rate_8h"] = item.get("value")
        row["funding_timestamp"] = _max_time(row.get("funding_timestamp"), item.get("update"))
        row["funding_rate_unit"] = "decimal_rate"
        row["timestamp"] = _max_time(row.get("timestamp"), item.get("update"))


def _coinalyze_apply_predicted_funding(
    provider: CoinalyzeDerivativesProvider,
    symbols: Iterable[str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    for item in provider._get_optional("predicted-funding-rate", {"symbols": ",".join(symbols)}):
        symbol = str(item.get("symbol") or "")
        if not symbol:
            continue
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["predicted_funding_rate"] = item.get("value")
        row["predicted_funding_timestamp"] = _max_time(row.get("predicted_funding_timestamp"), item.get("update"))
        row["funding_rate_unit"] = "decimal_rate"
        row["timestamp"] = _max_time(row.get("timestamp"), item.get("update"))


def _coinalyze_history_params(
    provider: CoinalyzeDerivativesProvider,
    symbols: Iterable[str],
) -> dict[str, str]:
    return {
        "symbols": ",".join(symbols),
        "interval": provider.history_interval,
        "from": str(int(provider.clock()) - max(1, provider.lookback_hours) * 3600),
        "to": str(int(provider.clock())),
    }


def _coinalyze_apply_open_interest_history(
    provider: CoinalyzeDerivativesProvider,
    history_params: Mapping[str, str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    params = {**history_params, "convert_to_usd": _bool_param(provider.convert_to_usd)}
    for item in provider._get("open-interest-history", params):
        symbol = str(item.get("symbol") or "")
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["open_interest_24h_change_pct"] = _history_change_pct(item.get("history"))
        row["open_interest_history_timestamp"] = _latest_history_time(item.get("history"))
        row["open_interest_unit"] = "usd_notional" if provider.convert_to_usd else "provider_native"


def _coinalyze_apply_liquidation_history(
    provider: CoinalyzeDerivativesProvider,
    history_params: Mapping[str, str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    params = {**history_params, "convert_to_usd": _bool_param(provider.convert_to_usd)}
    for item in provider._get("liquidation-history", params):
        symbol = str(item.get("symbol") or "")
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["liquidations_24h"] = _liquidation_sum(item.get("history"))
        row["long_liquidations"] = _history_sum(item.get("history"), "l")
        row["short_liquidations"] = _history_sum(item.get("history"), "s")
        row["liquidation_timestamp"] = _latest_history_time(item.get("history"))
        row["liquidation_unit"] = "usd_notional" if provider.convert_to_usd else "provider_native"


def _coinalyze_apply_long_short_history(
    provider: CoinalyzeDerivativesProvider,
    history_params: Mapping[str, str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    for item in provider._get("long-short-ratio-history", history_params):
        symbol = str(item.get("symbol") or "")
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["long_short_ratio"] = _latest_history_value(item.get("history"), "r")
        row["long_short_timestamp"] = _latest_history_time(item.get("history"))


def _coinalyze_apply_ohlcv_history(
    provider: CoinalyzeDerivativesProvider,
    history_params: Mapping[str, str],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    for item in provider._get("ohlcv-history", history_params):
        symbol = str(item.get("symbol") or "")
        row = by_symbol.setdefault(symbol, _live_base_row(symbol))
        row["futures_price_24h_change_pct"] = _history_change_pct(item.get("history"))
        row["futures_volume_24h"] = _history_sum(item.get("history"), "v")
        row["ohlcv_timestamp"] = _latest_history_time(item.get("history"))
        row["volume_unit"] = "provider_native"


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


def resolve_future_market_symbols(
    markets: Iterable[Mapping[str, Any]],
    base_symbols: Iterable[str],
) -> tuple[str, ...]:
    """Select one preferred Coinalyze futures symbol for each requested base."""
    requested = [_normalize_base_symbol(symbol) for symbol in base_symbols if str(symbol).strip()]
    by_base: dict[str, tuple[int, str]] = {}
    for market in markets:
        symbol = str(market.get("symbol") or "").strip()
        base = _normalize_base_symbol(market.get("base_asset") or _strip_quote_suffix(symbol))
        if not symbol or base not in requested:
            continue
        score = _future_market_score(market)
        current = by_base.get(base)
        if current is None or score > current[0]:
            by_base[base] = (score, symbol)
    out: list[str] = []
    seen: set[str] = set()
    for base in requested:
        selected = by_base.get(base)
        if selected is None:
            continue
        symbol = selected[1]
        if symbol not in seen:
            seen.add(symbol)
            out.append(symbol)
    return tuple(out)


def _future_market_score(market: Mapping[str, Any]) -> int:
    score = 0
    if market.get("is_perpetual") is True:
        score += 100
    quote = str(market.get("quote_asset") or "").upper()
    if quote == "USDT":
        score += 40
    elif quote == "USD":
        score += 30
    margined = str(market.get("margined") or "").upper()
    if margined == "STABLE":
        score += 20
    exchange = str(market.get("exchange") or "").upper()
    if exchange in {"BINANCE", "BYBIT", "OKX"}:
        score += 5
    if str(market.get("symbol") or "").upper().endswith(".A"):
        score += 1
    return score


def _snapshot(row: Mapping[str, Any]) -> dict[str, Any] | None:
    symbol = _base_symbol(row)
    if not symbol:
        return None
    timestamp = _parse_dt(row.get("timestamp") or row.get("time") or row.get("created_at"))
    snapshot = {
        "symbol": symbol,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "perp_available": bool(row.get("perp_available", True)),
        "open_interest": _float_or_none(_first_present(row, "open_interest", "oi")),
        "open_interest_timestamp": _iso_time(_first_present(row, "open_interest_timestamp", "open_interest_observed_at")),
        "open_interest_unit": str(row.get("open_interest_unit") or "").strip() or None,
        "open_interest_24h_change_pct": _float_or_none(
            _first_present(row, "open_interest_24h_change_pct", "oi_24h_change_pct", "open_interest_change_24h")
        ),
        "open_interest_history_timestamp": _iso_time(_first_present(row, "open_interest_history_timestamp", "open_interest_history_observed_at")),
        "open_interest_to_market_cap": _float_or_none(
            _first_present(row, "open_interest_to_market_cap", "oi_to_market_cap")
        ),
        "funding_rate_8h": _float_or_none(_first_present(row, "funding_rate_8h", "funding_rate")),
        "predicted_funding_rate": _float_or_none(_first_present(row, "predicted_funding_rate", "predicted_funding")),
        "funding_timestamp": _iso_time(_first_present(row, "funding_timestamp", "funding_observed_at")),
        "predicted_funding_timestamp": _iso_time(_first_present(row, "predicted_funding_timestamp", "predicted_funding_observed_at")),
        "funding_rate_unit": str(row.get("funding_rate_unit") or "").strip() or None,
        "funding_rate_percentile": _float_or_none(row.get("funding_rate_percentile")),
        "futures_price_24h_change_pct": _float_or_none(
            _first_present(row, "futures_price_24h_change_pct", "price_return_24h", "return_24h", "price_change_24h")
        ),
        "ohlcv_timestamp": _iso_time(_first_present(row, "ohlcv_timestamp", "volume_timestamp", "volume_observed_at")),
        "futures_volume_24h": _float_or_none(_first_present(row, "futures_volume_24h", "volume_24h")),
        "volume_unit": str(row.get("volume_unit") or "").strip() or None,
        "perp_spot_volume_ratio": _float_or_none(row.get("perp_spot_volume_ratio")),
        "liquidations_24h": _float_or_none(row.get("liquidations_24h")),
        "long_liquidations": _float_or_none(_first_present(row, "long_liquidations", "long_liquidations_24h", "liquidation_long_usd")),
        "short_liquidations": _float_or_none(_first_present(row, "short_liquidations", "short_liquidations_24h", "liquidation_short_usd")),
        "liquidation_timestamp": _iso_time(_first_present(row, "liquidation_timestamp", "liquidation_observed_at")),
        "liquidation_unit": str(row.get("liquidation_unit") or "").strip() or None,
        "long_short_ratio": _float_or_none(row.get("long_short_ratio")),
        "long_short_timestamp": _iso_time(_first_present(row, "long_short_timestamp", "long_short_observed_at")),
        "basis": _float_or_none(row.get("basis")),
        "basis_timestamp": _iso_time(_first_present(row, "basis_timestamp", "basis_observed_at")),
        "basis_unit": str(row.get("basis_unit") or "").strip() or None,
    }
    metric_keys = tuple(key for key in snapshot if key not in {"symbol", "timestamp", "perp_available"})
    if not any(snapshot.get(key) is not None for key in metric_keys) and row.get("perp_available") is not False:
        return None
    return snapshot


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


def _normalize_base_symbol(value: object) -> str:
    return _strip_quote_suffix(str(value or "")).upper()


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


def _latest_history_time(history: object) -> str | None:
    if not isinstance(history, list):
        return None
    latest: datetime | None = None
    for item in history:
        if not isinstance(item, Mapping):
            continue
        timestamp = _parse_dt(item.get("t"))
        if timestamp is None:
            continue
        latest = timestamp if latest is None else max(latest, timestamp)
    return latest.isoformat() if latest else None


def _iso_time(value: object) -> str | None:
    parsed = _parse_dt(value)
    return parsed.isoformat() if parsed else None


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
