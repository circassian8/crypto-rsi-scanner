"""Strict local Bybit USDT-perpetual catalog normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Mapping, Sequence

from .models import BybitInstrument


MAX_CATALOG_BYTES = 16 * 1024 * 1024
MAX_CATALOG_ROWS = 2_000
_NON_GENUINE_COMPONENTS = {"fixture", "fixtures", "mock", "replay", "test", "tests"}


class BybitUniverseError(ValueError):
    """Raised when a catalog cannot prove active Bybit USDT perpetuals."""


def read_json_document(path: Path, *, require_genuine: bool = False) -> tuple[object, str]:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise BybitUniverseError("catalog path must be absolute")
    if require_genuine and any(
        component.casefold() in _NON_GENUINE_COMPONENTS for component in candidate.parts
    ):
        raise BybitUniverseError("fixture/test/mock/replay catalog cannot be imported")
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise BybitUniverseError("catalog file is unavailable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise BybitUniverseError("catalog must be a regular non-symlink file")
    if before.st_nlink != 1 or before.st_size > MAX_CATALOG_BYTES:
        raise BybitUniverseError("catalog file violates link or size bounds")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(candidate, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise BybitUniverseError("catalog identity changed before read")
        chunks: list[bytes] = []
        remaining = MAX_CATALOG_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload_bytes = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(payload_bytes) > MAX_CATALOG_BYTES:
        raise BybitUniverseError("catalog file exceeds size bound")
    if (
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
    ):
        raise BybitUniverseError("catalog changed during read")
    try:
        payload = json.loads(payload_bytes, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BybitUniverseError("catalog is not valid UTF-8 JSON") from exc
    return payload, hashlib.sha256(payload_bytes).hexdigest()


def normalize_catalog(
    payload: object,
    *,
    source_mode: str,
    source_sha256: str,
) -> tuple[BybitInstrument, ...]:
    if source_mode not in {"live_no_send", "imported_catalog", "fixture"}:
        raise BybitUniverseError("catalog source mode is invalid")
    root = _mapping(payload, "catalog")
    if isinstance(root.get("retCode"), bool) or root.get("retCode") != 0:
        raise BybitUniverseError("Bybit catalog response is not successful")
    result = _mapping(root.get("result"), "result")
    if result.get("category") != "linear":
        raise BybitUniverseError("Bybit catalog is not the linear category")
    if result.get("nextPageCursor") != "":
        raise BybitUniverseError("Bybit catalog is incomplete or paginated")
    raw_rows = _sequence(result.get("list"), "result.list")
    if len(raw_rows) > MAX_CATALOG_ROWS:
        raise BybitUniverseError("Bybit catalog exceeds the row bound")
    observed_at = _provider_timestamp(root.get("time"))

    instruments: list[BybitInstrument] = []
    bases: set[str] = set()
    ids: set[str] = set()
    for index, raw in enumerate(raw_rows):
        row = _mapping(raw, f"instrument[{index}]")
        if (
            row.get("contractType") != "LinearPerpetual"
            or row.get("status") != "Trading"
            or row.get("quoteCoin") != "USDT"
            or row.get("settleCoin") != "USDT"
            or row.get("isPreListing") is not False
        ):
            continue
        instrument_id = _token(row.get("symbol"), "symbol")
        base_coin = _token(row.get("baseCoin"), "baseCoin")
        if instrument_id != f"{base_coin}USDT":
            raise BybitUniverseError("instrument symbol does not match base plus USDT")
        if instrument_id in ids or base_coin in bases:
            raise BybitUniverseError("active Bybit instrument identity is ambiguous")
        price_filter = _mapping(row.get("priceFilter"), "priceFilter")
        lot_filter = _mapping(row.get("lotSizeFilter"), "lotSizeFilter")
        if any(
            value in (None, "")
            for value in (
                price_filter.get("tickSize"),
                lot_filter.get("qtyStep"),
                lot_filter.get("minOrderQty"),
            )
        ):
            # An incomplete catalog row cannot confirm a tradable instrument.
            # Keep the complete catalog usable while leaving that base absent,
            # which makes any matching watchlist asset visibly unverified.
            continue
        instrument = BybitInstrument(
            instrument_id=instrument_id,
            base_coin=base_coin,
            quote_coin="USDT",
            settle_coin="USDT",
            contract_type="LinearPerpetual",
            status="Trading",
            tick_size=_positive_decimal(price_filter.get("tickSize"), "tickSize"),
            quantity_step=_positive_decimal(lot_filter.get("qtyStep"), "qtyStep"),
            minimum_quantity=_positive_decimal(
                lot_filter.get("minOrderQty"), "minOrderQty"
            ),
            maximum_limit_quantity=_optional_positive_decimal(
                lot_filter.get("maxOrderQty"), "maxOrderQty"
            ),
            maximum_market_quantity=_optional_positive_decimal(
                lot_filter.get("maxMktOrderQty"), "maxMktOrderQty"
            ),
            minimum_notional_usdt=_optional_positive_decimal(
                lot_filter.get("minNotionalValue"), "minNotionalValue"
            ),
            source_observed_at=observed_at,
            source_mode=source_mode,
            source_sha256=source_sha256,
        )
        instruments.append(instrument)
        ids.add(instrument_id)
        bases.add(base_coin)
    if not instruments:
        raise BybitUniverseError("catalog contains no active Bybit USDT perpetuals")
    return tuple(sorted(instruments, key=lambda item: (item.base_coin, item.instrument_id)))


def load_catalog(path: Path, *, source_mode: str) -> tuple[BybitInstrument, ...]:
    payload, digest = read_json_document(
        path, require_genuine=source_mode == "imported_catalog"
    )
    return normalize_catalog(payload, source_mode=source_mode, source_sha256=digest)


def _reject_duplicate_keys(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BybitUniverseError("catalog contains duplicate JSON keys")
        result[key] = value
    return result


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BybitUniverseError(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise BybitUniverseError(f"{label} must be an array")
    return value


def _token(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise BybitUniverseError(f"{label} must be text")
    token = value.strip().upper()
    if not token or len(token) > 40 or not token.isalnum():
        raise BybitUniverseError(f"{label} is invalid")
    return token


def _positive_decimal(value: object, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BybitUniverseError(f"{label} must be numeric text")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise BybitUniverseError(f"{label} is invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise BybitUniverseError(f"{label} must be positive")
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _optional_positive_decimal(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    return _positive_decimal(value, label)


def _provider_timestamp(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BybitUniverseError("catalog provider timestamp is invalid")
    milliseconds = int(value)
    if milliseconds <= 0 or float(milliseconds) != float(value):
        raise BybitUniverseError("catalog provider timestamp is invalid")
    try:
        observed = datetime.fromtimestamp(milliseconds / 1000, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise BybitUniverseError("catalog provider timestamp is out of range") from exc
    return observed.isoformat()


__all__ = (
    "MAX_CATALOG_BYTES",
    "MAX_CATALOG_ROWS",
    "BybitUniverseError",
    "load_catalog",
    "normalize_catalog",
    "read_json_document",
)
