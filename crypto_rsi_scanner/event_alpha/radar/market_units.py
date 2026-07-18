"""Return-unit helpers for Event Alpha market artifacts.

Raw/latest market snapshots use fractional returns by default:
``0.012`` means ``+1.2%``. Persisted market-state snapshots use percentage
points by default: ``1.2`` means ``+1.2%``. These helpers keep conversion
centralized so market-state artifacts cannot be multiplied by 100 twice.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping


RETURN_UNIT_FRACTION = "fraction"
RETURN_UNIT_PERCENT_POINTS = "percent_points"
RETURN_UNIT_UNKNOWN = "unknown"

RETURN_UNIT_METADATA_KEYS = (
    "return_units",
    "return_unit_by_field",
    "field_return_units",
)

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

_TEMPORAL_RETURN_KEY = re.compile(
    r"temporal_(?:return|return_volatility|relative_return_vs_(?:btc|eth))_[1-9][0-9]*h"
)


def is_return_unit_field(field: object) -> bool:
    """Return whether ``field`` may carry percentage/fraction unit metadata.

    Rolling market-history enrichment retains its point-in-time derived returns
    beside the canonical model inputs.  Their names are deliberately closed to
    the three generated temporal families; arbitrary metadata keys still fail
    unit validation.
    """

    text = str(field or "")
    return text in RETURN_KEYS or _TEMPORAL_RETURN_KEY.fullmatch(text) is not None


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


def return_unit_for_field(
    row: Mapping[str, Any] | None,
    field: str,
    *,
    default: str = RETURN_UNIT_FRACTION,
) -> str:
    """Return the declared unit for one return field.

    A field-level declaration wins over the snapshot-wide declaration.  The
    helper deliberately does not infer from the numeric value once explicit
    metadata exists, so a value such as ``10.0`` declared as a fraction stays
    invalid instead of being silently reinterpreted as ten percentage points.
    """

    if not isinstance(row, Mapping):
        return _clean_unit(default)
    overrides = _return_unit_overrides(row)
    if overrides is not None and field in overrides:
        return _clean_unit(overrides.get(field))
    return infer_return_unit(row, default=default, keys=(field,))


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
    overrides = _return_unit_overrides(snapshot)
    if overrides is None and any(key in snapshot for key in RETURN_UNIT_METADATA_KEYS):
        warnings.append("invalid_return_unit_metadata")
        overrides = {}
    for key in overrides or {}:
        if not is_return_unit_field(key):
            warnings.append(f"unknown_return_unit_field:{key}")
    validated_fields = list(RETURN_KEYS)
    validated_fields.extend(
        str(key)
        for key in overrides or {}
        if is_return_unit_field(key) and str(key) not in RETURN_KEYS
    )
    for key in validated_fields:
        if key not in snapshot or snapshot.get(key) in (None, ""):
            continue
        parsed = _float(snapshot.get(key))
        field_unit = return_unit_for_field(snapshot, key, default=unit)
        if parsed is None:
            warnings.append(f"invalid_return_value:{key}")
            continue
        if field_unit == RETURN_UNIT_UNKNOWN:
            warnings.append(f"return_unit_missing:{key}")
            continue
        if field_unit == RETURN_UNIT_FRACTION and abs(parsed) > 3.0:
            warnings.append(f"implausible_fraction_return:{key}")
            continue
        normalized = normalize_return_percent_points(parsed, field_unit)
        if normalized is not None and abs(normalized) > 300.0:
            warnings.append(f"implausible_normalized_return:{key}")
    if isinstance(reference_snapshot, Mapping):
        compared_keys = ("return_1h", "return_4h", "return_24h")
        for key in compared_keys:
            actual_unit = return_unit_for_field(snapshot, key, default=unit)
            ref_unit = return_unit_for_field(
                reference_snapshot,
                key,
                default=RETURN_UNIT_FRACTION,
            )
            actual = normalize_return_percent_points(snapshot.get(key), actual_unit)
            expected = normalize_return_percent_points(reference_snapshot.get(key), ref_unit)
            if actual is None or expected is None:
                continue
            if abs(expected) > 1e-9 and abs(actual - expected) > max(5.0, abs(expected) * 10.0):
                warnings.append(f"{key}_unit_mismatch")
            if abs(actual) > 50.0 and abs(expected) < 10.0:
                warnings.append(f"{key}_possible_double_scaled")
    for key, threshold in (("return_1h", 50.0), ("return_4h", 80.0)):
        actual = normalize_return_percent_points(
            snapshot.get(key),
            return_unit_for_field(snapshot, key, default=unit),
        )
        if actual is not None and abs(actual) > threshold:
            warnings.append(f"{key}_extreme_without_unit_context")
    return tuple(dict.fromkeys(warnings))


def _return_unit_overrides(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in RETURN_UNIT_METADATA_KEYS:
        if key not in row:
            continue
        value = row.get(key)
        return value if isinstance(value, Mapping) else None
    return {}


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
