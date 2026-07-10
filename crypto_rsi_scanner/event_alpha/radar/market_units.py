"""Return-unit helpers for Event Alpha market artifacts.

Raw/latest market snapshots use fractional returns by default:
``0.012`` means ``+1.2%``. Persisted market-state snapshots use percentage
points by default: ``1.2`` means ``+1.2%``. These helpers keep conversion
centralized so market-state artifacts cannot be multiplied by 100 twice.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


RETURN_UNIT_FRACTION = "fraction"
RETURN_UNIT_PERCENT_POINTS = "percent_points"
RETURN_UNIT_UNKNOWN = "unknown"

RETURN_KEYS = (
    "return_5m",
    "return_15m",
    "return_1h",
    "return_4h",
    "return_24h",
    "return_72h",
    "return_7d",
    "relative_return_vs_btc",
    "relative_return_vs_eth",
    "relative_return_vs_sector",
    "relative_return_vs_btc_1h",
    "relative_return_vs_btc_4h",
    "relative_return_vs_btc_24h",
    "relative_return_vs_eth_1h",
    "relative_return_vs_eth_4h",
    "relative_return_vs_eth_24h",
    "open_interest_delta",
    "open_interest_delta_1h",
    "open_interest_delta_4h",
    "open_interest_delta_24h",
    "dex_volume_change",
    "dex_liquidity_change",
)


def infer_return_unit(
    row: Mapping[str, Any] | None,
    *,
    default: str = RETURN_UNIT_FRACTION,
    keys: tuple[str, ...] | None = None,
) -> str:
    """Infer return unit for a snapshot-like mapping.

    Explicit metadata wins. Without metadata, market-state rows are treated as
    percentage points because they are already normalized artifacts. Raw/latest
    market rows default to fractions. Large absolute values are also treated as
    percentage points for legacy fixture compatibility.
    """
    if not isinstance(row, Mapping):
        return _clean_unit(default)
    explicit = _clean_unit(
        row.get("return_unit")
        or row.get("source_return_unit")
        or row.get("market_return_unit")
        or row.get("unit")
    )
    if explicit != RETURN_UNIT_UNKNOWN:
        return explicit
    row_type = str(row.get("row_type") or "").casefold()
    schema = str(row.get("schema_version") or "").casefold()
    if row_type == "event_market_state_snapshot" or "market_state" in schema:
        return RETURN_UNIT_PERCENT_POINTS
    for key in keys or RETURN_KEYS:
        parsed = _float(row.get(key))
        if parsed is not None and abs(parsed) > 3.0:
            return RETURN_UNIT_PERCENT_POINTS
    return _clean_unit(default)


def normalize_return_fraction(value: object, unit_hint: str | None = None) -> float | None:
    """Return a fractional value where ``0.012`` means ``+1.2%``."""
    parsed = _float(value)
    if parsed is None:
        return None
    unit = _clean_unit(unit_hint)
    if unit == RETURN_UNIT_PERCENT_POINTS:
        return parsed / 100.0
    return parsed


def normalize_return_percent_points(value: object, unit_hint: str | None = None) -> float | None:
    """Return percentage points where ``1.2`` means ``+1.2%``."""
    parsed = _float(value)
    if parsed is None:
        return None
    unit = _clean_unit(unit_hint)
    if unit == RETURN_UNIT_PERCENT_POINTS:
        return parsed
    return parsed * 100.0


def format_return_pct(value: object, unit: str = RETURN_UNIT_FRACTION, *, digits: int = 2) -> str:
    pct = normalize_return_percent_points(value, unit)
    if pct is None:
        return "n/a"
    return f"{pct:+.{digits}f}%"


def validate_market_snapshot_units(
    snapshot: Mapping[str, Any] | None,
    reference_snapshot: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Return conservative warnings for inconsistent return units."""
    if not isinstance(snapshot, Mapping):
        return ("market_snapshot_missing",)
    warnings: list[str] = []
    unit = infer_return_unit(snapshot, default=RETURN_UNIT_PERCENT_POINTS)
    if not snapshot.get("return_unit"):
        warnings.append("return_unit_missing")
    if isinstance(reference_snapshot, Mapping):
        compared_keys = ("return_1h", "return_4h", "return_24h")
        ref_unit = infer_return_unit(
            reference_snapshot,
            default=RETURN_UNIT_FRACTION,
            keys=compared_keys,
        )
        for key in compared_keys:
            actual = normalize_return_percent_points(snapshot.get(key), unit)
            expected = normalize_return_percent_points(reference_snapshot.get(key), ref_unit)
            if actual is None or expected is None:
                continue
            if abs(expected) > 1e-9 and abs(actual - expected) > max(5.0, abs(expected) * 10.0):
                warnings.append(f"{key}_unit_mismatch")
            if abs(actual) > 50.0 and abs(expected) < 10.0:
                warnings.append(f"{key}_possible_double_scaled")
    for key, threshold in (("return_1h", 50.0), ("return_4h", 80.0)):
        actual = normalize_return_percent_points(snapshot.get(key), unit)
        if actual is not None and abs(actual) > threshold:
            warnings.append(f"{key}_extreme_without_unit_context")
    return tuple(dict.fromkeys(warnings))


def _clean_unit(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in {"fraction", "fractions", "decimal", "raw_fraction"}:
        return RETURN_UNIT_FRACTION
    if text in {"percent", "percentage", "percent_points", "percentage_points", "pct", "pct_points"}:
        return RETURN_UNIT_PERCENT_POINTS
    return RETURN_UNIT_UNKNOWN


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
