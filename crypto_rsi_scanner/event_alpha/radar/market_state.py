"""Normalized market-state snapshots for Event Alpha research artifacts.

This module is pure: it reads already-collected market rows and produces a
stable snapshot schema. It does not create alerts, routes, paper rows, or
event-fade triggers.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.radar.market_units as event_market_units
from crypto_rsi_scanner.event_alpha.artifacts.schema import (
    market_feature_evidence as event_market_feature_evidence,
)


_INTERNAL_TEMPORAL_RETURN_UNIT_FIELD = re.compile(
    r"temporal_(?:return|return_volatility|relative_return_vs_(?:btc|eth))_[1-9][0-9]*h"
)
_COMMON_UNIT_EXTREME_WARNINGS = frozenset(
    {
        "return_1h_extreme_without_unit_context",
        "return_4h_extreme_without_unit_context",
    }
)


@dataclass(frozen=True)
class MarketStateSnapshot:
    symbol: str
    coin_id: str
    canonical_asset_id: str
    observed_at: str
    price: float | None = None
    return_5m: float | None = None
    return_15m: float | None = None
    return_1h: float | None = None
    return_4h: float | None = None
    return_24h: float | None = None
    relative_return_vs_btc_1h: float | None = None
    relative_return_vs_btc_4h: float | None = None
    relative_return_vs_btc_24h: float | None = None
    relative_return_vs_eth_1h: float | None = None
    relative_return_vs_eth_4h: float | None = None
    relative_return_vs_eth_24h: float | None = None
    volume_24h: float | None = None
    volume_zscore_24h: float | None = None
    turnover_zscore: float | None = None
    volume_to_market_cap: float | None = None
    liquidity_usd: float | None = None
    spread_bps: float | None = None
    open_interest_delta: float | None = None
    funding_level: float | None = None
    funding_zscore: float | None = None
    liquidation_imbalance: float | None = None
    dex_volume_change: float | None = None
    dex_liquidity_change: float | None = None
    event_age_hours: float | None = None
    market_data_source: str = "unknown"
    freshness_status: str = "unknown"
    market_history_observation_id: str | None = None
    market_feature_evidence: Mapping[str, Any] = field(default_factory=dict)
    return_unit: str = event_market_units.RETURN_UNIT_PERCENT_POINTS
    source_return_unit: str = event_market_units.RETURN_UNIT_UNKNOWN
    threshold_unit: str = event_market_units.RETURN_UNIT_PERCENT_POINTS
    return_units: Mapping[str, str] = field(default_factory=dict)
    source_return_units: Mapping[str, str] = field(default_factory=dict)
    observed_fields: tuple[str, ...] = ()
    unit_warnings: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.market_history_observation_id is None:
            data.pop("market_history_observation_id")
        if not self.market_feature_evidence:
            data.pop("market_feature_evidence")
        else:
            data["market_feature_evidence_contract_version"] = (
                event_market_feature_evidence.CONTRACT_VERSION
            )
        data["observed_fields"] = list(self.observed_fields)
        data["return_units"] = dict(self.return_units)
        data["source_return_units"] = dict(self.source_return_units)
        data["unit_warnings"] = list(self.unit_warnings)
        data["warnings"] = list(self.warnings)
        return data


def snapshot_from_market_row(
    row: Mapping[str, Any],
    *,
    observed_at: datetime | str | None = None,
    btc_benchmark: Mapping[str, Any] | None = None,
    eth_benchmark: Mapping[str, Any] | None = None,
) -> MarketStateSnapshot:
    """Build a stable market-state snapshot from a CoinGecko-style row."""
    observed = _observed_at(row, observed_at)
    symbol = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
    coin_id = str(row.get("coin_id") or row.get("id") or "").strip()
    canonical_asset_id = str(row.get("canonical_asset_id") or coin_id or symbol).strip()
    warnings: list[str] = []
    fields: list[str] = []
    source_unit = event_market_units.infer_return_unit(row, default=event_market_units.RETURN_UNIT_FRACTION)
    normalized_returns = _normalized_return_values(
        row,
        btc_benchmark=btc_benchmark,
        eth_benchmark=eth_benchmark,
        source_unit=source_unit,
    )

    def capture(name: str, value: float | None) -> float | None:
        if value is not None:
            fields.append(name)
        return value

    market_cap = _float(_first_present_value(row, "market_cap", "mcap"))
    volume_24h = _float(_first_present_value(row, "volume_24h", "total_volume", "spot_volume_24h"))
    volume_mcap = _float(
        _first_present_value(row, "volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")
    )
    if volume_mcap is None and volume_24h is not None and market_cap and market_cap > 0:
        volume_mcap = volume_24h / market_cap
    if not symbol and not coin_id:
        warnings.append("missing_asset_identity")

    freshness = str(
        row.get("market_context_freshness_status")
        or row.get("freshness_status")
        or ("fresh" if _has_valid_row_observation_time(row) else "unknown")
    )
    source = str(row.get("market_data_source") or row.get("source") or "fixture")
    market_history_observation_id = _optional_string(
        row.get("market_history_observation_id"),
        field_name="market_history_observation_id",
    )
    market_feature_evidence = _project_market_feature_evidence(
        row,
        market_history_observation_id=market_history_observation_id,
    )
    normalized_return_units = {
        name: event_market_units.RETURN_UNIT_PERCENT_POINTS
        for name, value in normalized_returns.items()
        if value is not None
    }
    source_return_units = {
        name: event_market_units.return_unit_for_field(row, name, default=source_unit)
        for name in normalized_return_units
        if row.get(name) not in (None, "")
    }
    unit_warnings = list(event_market_units.validate_market_snapshot_units(
        {
            "return_unit": event_market_units.RETURN_UNIT_PERCENT_POINTS,
            "return_units": normalized_return_units,
            **normalized_returns,
        },
        row,
    ))
    if row.get("return_unit") not in (None, "") or any(
        key in row for key in event_market_units.RETURN_UNIT_METADATA_KEYS
    ):
        unit_warnings.extend(_source_unit_warnings(row))
    snapshot = MarketStateSnapshot(
        symbol=symbol,
        coin_id=coin_id,
        canonical_asset_id=canonical_asset_id,
        observed_at=observed.isoformat(),
        price=capture("price", _float(_first_present_value(row, "price", "current_price"))),
        return_5m=capture("return_5m", normalized_returns["return_5m"]),
        return_15m=capture("return_15m", normalized_returns["return_15m"]),
        return_1h=capture("return_1h", normalized_returns["return_1h"]),
        return_4h=capture("return_4h", normalized_returns["return_4h"]),
        return_24h=capture("return_24h", normalized_returns["return_24h"]),
        relative_return_vs_btc_1h=capture("relative_return_vs_btc_1h", normalized_returns["relative_return_vs_btc_1h"]),
        relative_return_vs_btc_4h=capture("relative_return_vs_btc_4h", normalized_returns["relative_return_vs_btc_4h"]),
        relative_return_vs_btc_24h=capture("relative_return_vs_btc_24h", normalized_returns["relative_return_vs_btc_24h"]),
        relative_return_vs_eth_1h=capture("relative_return_vs_eth_1h", normalized_returns["relative_return_vs_eth_1h"]),
        relative_return_vs_eth_4h=capture("relative_return_vs_eth_4h", normalized_returns["relative_return_vs_eth_4h"]),
        relative_return_vs_eth_24h=capture("relative_return_vs_eth_24h", normalized_returns["relative_return_vs_eth_24h"]),
        volume_24h=capture("volume_24h", volume_24h),
        volume_zscore_24h=capture(
            "volume_zscore_24h",
            _float(_first_present_value(row, "volume_zscore_24h", "volume_zscore")),
        ),
        turnover_zscore=capture("turnover_zscore", _float(row.get("turnover_zscore"))),
        volume_to_market_cap=capture("volume_to_market_cap", volume_mcap),
        liquidity_usd=capture(
            "liquidity_usd",
            _float(_first_present_value(row, "liquidity_usd", "order_book_liquidity_usd")),
        ),
        spread_bps=capture("spread_bps", _float(row.get("spread_bps"))),
        open_interest_delta=capture("open_interest_delta", normalized_returns["open_interest_delta"]),
        funding_level=capture(
            "funding_level",
            _float(_first_present_value(row, "funding_level", "funding_rate")),
        ),
        funding_zscore=capture("funding_zscore", _float(row.get("funding_zscore"))),
        liquidation_imbalance=capture("liquidation_imbalance", _float(row.get("liquidation_imbalance"))),
        dex_volume_change=capture("dex_volume_change", normalized_returns["dex_volume_change"]),
        dex_liquidity_change=capture("dex_liquidity_change", normalized_returns["dex_liquidity_change"]),
        event_age_hours=capture("event_age_hours", _float(row.get("event_age_hours"))),
        market_data_source=source,
        freshness_status=freshness,
        market_history_observation_id=market_history_observation_id,
        market_feature_evidence=market_feature_evidence,
        return_unit=event_market_units.RETURN_UNIT_PERCENT_POINTS,
        source_return_unit=source_unit,
        threshold_unit=event_market_units.RETURN_UNIT_PERCENT_POINTS,
        return_units=normalized_return_units,
        source_return_units=source_return_units,
        observed_fields=tuple(dict.fromkeys(fields)),
        unit_warnings=tuple(dict.fromkeys(unit_warnings)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return snapshot


def _project_market_feature_evidence(
    row: Mapping[str, Any],
    *,
    market_history_observation_id: str | None,
) -> dict[str, Any]:
    projection = event_market_feature_evidence.canonical_projection(
        row.get("market_feature_evidence"),
        expected_current_observation_id=market_history_observation_id,
    )
    contract_version = row.get("market_feature_evidence_contract_version")
    if contract_version is not None and (
        type(contract_version) is not int
        or contract_version != event_market_feature_evidence.CONTRACT_VERSION
    ):
        raise ValueError("market_feature_evidence_invalid:value:contract_version")
    has_temporal_evidence = event_market_feature_evidence.contains_temporal_evidence(
        projection
    )
    contract_is_claimed = (
        contract_version == event_market_feature_evidence.CONTRACT_VERSION
        or bool(projection)
    )
    if (
        contract_is_claimed
        and market_history_observation_id is not None
        and not has_temporal_evidence
    ):
        raise ValueError(
            "market_feature_evidence_invalid:value:missing_for_history_observation"
        )
    if market_history_observation_id is None and has_temporal_evidence:
        raise ValueError(
            "market_feature_evidence_invalid:value:market_history_observation_id_missing"
        )
    return projection


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _source_unit_warnings(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate the source fields consumed by the canonical snapshot.

    Rolling-history rows also retain explicitly unitized ``temporal_*``
    evidence fields.  Those are not canonical snapshot inputs, so remove only
    the three exact internally generated families from the source projection.
    Unknown metadata remains visible.  The normalized projection above already
    performs field-aware 1h/4h extreme checks; suppress the source validator's
    duplicate common-unit heuristic because a mixed row may legitimately use a
    fractional provider default plus percentage-point field overrides.
    """

    projected = dict(row)
    for metadata_key in event_market_units.RETURN_UNIT_METADATA_KEYS:
        value = projected.get(metadata_key)
        if not isinstance(value, Mapping):
            continue
        projected[metadata_key] = {
            str(field): unit
            for field, unit in value.items()
            if _INTERNAL_TEMPORAL_RETURN_UNIT_FIELD.fullmatch(str(field)) is None
        }
    return tuple(
        warning
        for warning in event_market_units.validate_market_snapshot_units(projected)
        if warning not in _COMMON_UNIT_EXTREME_WARNINGS
    )


def _normalized_return_values(
    row: Mapping[str, Any],
    *,
    btc_benchmark: Mapping[str, Any] | None,
    eth_benchmark: Mapping[str, Any] | None,
    source_unit: str,
) -> dict[str, float | None]:
    """Normalize row and benchmark return fields to percent points."""

    def field_unit(
        name: str,
        *,
        source: Mapping[str, Any] = row,
        default: str = source_unit,
    ) -> str:
        return event_market_units.return_unit_for_field(source, name, default=default)

    r1h = _percent_value(
        _first_present_value(row, "return_1h", "price_change_percentage_1h_in_currency"),
        unit=field_unit("return_1h"),
    )
    r4h = _percent_value(
        _first_present_value(row, "return_4h", "price_change_percentage_4h_in_currency"),
        unit=field_unit("return_4h"),
    )
    r24h = _percent_value(
        _first_present_value(
            row,
            "return_24h",
            "price_change_24h",
            "price_change_percentage_24h_in_currency",
        ),
        unit=field_unit("return_24h"),
    )
    btc = btc_benchmark or {}
    eth = eth_benchmark or {}
    relative_returns = {
        "relative_return_vs_btc_1h": _percent_value(
            _first_present_value(row, "relative_return_vs_btc_1h", "rel_btc_1h"),
            unit=field_unit("relative_return_vs_btc_1h"),
        ),
        "relative_return_vs_btc_4h": _percent_value(
            _first_present_value(row, "relative_return_vs_btc_4h", "rel_btc_4h"),
            unit=field_unit("relative_return_vs_btc_4h"),
        ),
        "relative_return_vs_btc_24h": _percent_value(
            _first_present_value(
                row,
                "relative_return_vs_btc_24h",
                "relative_strength_vs_btc",
                "btc_relative_return",
            ),
            unit=field_unit("relative_return_vs_btc_24h"),
        ),
        "relative_return_vs_eth_1h": _percent_value(
            _first_present_value(row, "relative_return_vs_eth_1h", "rel_eth_1h"),
            unit=field_unit("relative_return_vs_eth_1h"),
        ),
        "relative_return_vs_eth_4h": _percent_value(
            _first_present_value(row, "relative_return_vs_eth_4h", "rel_eth_4h"),
            unit=field_unit("relative_return_vs_eth_4h"),
        ),
        "relative_return_vs_eth_24h": _percent_value(
            _first_present_value(row, "relative_return_vs_eth_24h", "rel_eth_24h"),
            unit=field_unit("relative_return_vs_eth_24h"),
        ),
    }
    benchmark_inputs = (
        ("relative_return_vs_btc_1h", r1h, btc, "return_1h"),
        ("relative_return_vs_btc_4h", r4h, btc, "return_4h"),
        ("relative_return_vs_btc_24h", r24h, btc, "return_24h"),
        ("relative_return_vs_eth_1h", r1h, eth, "return_1h"),
        ("relative_return_vs_eth_4h", r4h, eth, "return_4h"),
        ("relative_return_vs_eth_24h", r24h, eth, "return_24h"),
    )
    for target, asset_return, benchmark, benchmark_field in benchmark_inputs:
        if relative_returns[target] is not None or asset_return is None:
            continue
        benchmark_unit = field_unit(benchmark_field, source=benchmark)
        benchmark_return = _percent_value(
            _first_present_value(
                benchmark,
                benchmark_field,
                f"price_change_percentage_{benchmark_field.removeprefix('return_')}_in_currency",
            ),
            unit=benchmark_unit,
        )
        if benchmark_return is not None:
            relative_returns[target] = asset_return - benchmark_return

    return {
        "return_5m": _percent_value(row.get("return_5m"), unit=field_unit("return_5m")),
        "return_15m": _percent_value(row.get("return_15m"), unit=field_unit("return_15m")),
        "return_1h": r1h,
        "return_4h": r4h,
        "return_24h": r24h,
        **relative_returns,
        "open_interest_delta": _percent_value(
            _first_present_value(row, "open_interest_delta", "open_interest_delta_24h"),
            unit=field_unit(
                "open_interest_delta",
                default=event_market_units.RETURN_UNIT_PERCENT_POINTS,
            ),
        ),
        "dex_volume_change": _percent_value(
            row.get("dex_volume_change"),
            unit=field_unit("dex_volume_change"),
        ),
        "dex_liquidity_change": _percent_value(
            row.get("dex_liquidity_change"),
            unit=field_unit("dex_liquidity_change"),
        ),
    }


def benchmark_rows(market_rows: list[Mapping[str, Any]]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Return BTC and ETH benchmark rows when present."""
    btc: Mapping[str, Any] = {}
    eth: Mapping[str, Any] = {}
    for row in market_rows:
        symbol = str(row.get("symbol") or "").upper()
        coin_id = str(row.get("coin_id") or row.get("id") or "").casefold()
        if symbol == "BTC" or coin_id == "bitcoin":
            btc = row
        elif symbol == "ETH" or coin_id == "ethereum":
            eth = row
    return btc, eth


def _observed_at(row: Mapping[str, Any], observed_at: datetime | str | None) -> datetime:
    for field_name, value in (
        ("observed_at argument", observed_at),
        ("observed_at", row.get("observed_at")),
        ("timestamp", row.get("timestamp")),
    ):
        if value in (None, ""):
            continue
        parsed = _parse_observation_time(value)
        if parsed is None:
            raise ValueError(f"market state {field_name} is invalid")
        return parsed
    return datetime.now(timezone.utc)


def _has_valid_row_observation_time(row: Mapping[str, Any]) -> bool:
    value = _first_present_value(row, "observed_at", "timestamp")
    return value is not None and _parse_observation_time(value) is not None


def _parse_observation_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str) and value.strip():
        try:
            return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _percent_value(value: object, *, unit: str | None) -> float | None:
    # Provider booleans are semantic flags, never numeric market evidence. Keep
    # this rejection at the ingestion boundary because market_units.py is part
    # of the byte-frozen Protocol-v1 diagnostics contract.
    if isinstance(value, bool):
        return None
    return event_market_units.normalize_return_percent_points(value, unit)


def _first_present_value(row: Mapping[str, Any], *keys: str) -> object:
    """Return the first explicit non-empty value without treating zero as absent."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


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


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
