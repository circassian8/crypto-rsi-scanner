"""Closed Radar-to-Bybit provider-query universe contract."""

from __future__ import annotations

import math
import re
from typing import Mapping, Sequence

from .bybit_execution_quality import bybit_base_symbol_requestable


UNIVERSE_SCHEMA_VERSION = 2
IDENTITY_JOIN_BASIS = "exact_radar_symbol_equals_bybit_base_coin_candidate_join"
CANONICAL_IDENTITY_STATUS = "pending_protocol_v2_annex_human_confirmation"
UNIVERSE_SELECTION_BASIS = (
    "exact_authoritative_top_liquid_market_observations_with_"
    "non_contract_shaped_symbols_excluded_before_provider"
)
RADAR_ASSET_KEYS = frozenset({
    "canonical_asset_id",
    "liquidity_rank",
    "liquidity_usd",
    "symbol",
})
UNIVERSE_KEYS = frozenset({
    "asset_count",
    "assets",
    "canonical_identity_status",
    "capture_id",
    "identity_join_basis",
    "preflight_excluded_asset_count",
    "preflight_excluded_assets",
    "provider_query_asset_count",
    "provider_query_assets",
    "research_only",
    "schema_id",
    "schema_version",
    "selection_basis",
})
EXCLUSION_REASON = "radar_symbol_not_bybit_base_contract_shape"
_CANONICAL_ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class BybitExecutionQualityUniverseError(ValueError):
    """Raised when the bounded provider-query universe is not canonical."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def partition_bybit_provider_query_assets(
    assets: Sequence[Mapping[str, object]],
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Validate, rank-check, and partition assets before any provider request."""

    requestable: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    identities: set[str] = set()
    symbols: set[str] = set()
    previous_order_key: tuple[float, str, str] | None = None
    for expected_rank, raw in enumerate(assets, start=1):
        if not isinstance(raw, Mapping) or set(raw) != RADAR_ASSET_KEYS:
            raise BybitExecutionQualityUniverseError("radar_asset_schema_invalid")
        canonical_id = raw.get("canonical_asset_id")
        symbol = raw.get("symbol")
        rank = raw.get("liquidity_rank")
        liquidity = raw.get("liquidity_usd")
        if (
            not isinstance(canonical_id, str)
            or not _CANONICAL_ASSET_ID_RE.fullmatch(canonical_id)
            or not isinstance(symbol, str)
            or symbol != symbol.strip().upper()
            or type(rank) is not int
            or rank != expected_rank
            or isinstance(liquidity, bool)
            or not isinstance(liquidity, (int, float))
            or not math.isfinite(float(liquidity))
            or float(liquidity) <= 0
            or canonical_id in identities
            or symbol in symbols
        ):
            raise BybitExecutionQualityUniverseError("radar_asset_identity_invalid")
        order_key = (-float(liquidity), canonical_id, symbol)
        if previous_order_key is not None and order_key < previous_order_key:
            raise BybitExecutionQualityUniverseError("radar_asset_order_invalid")
        previous_order_key = order_key
        identities.add(canonical_id)
        symbols.add(symbol)
        asset = dict(raw)
        if bybit_base_symbol_requestable(symbol):
            requestable.append(asset)
        else:
            excluded.append({**asset, "reason_code": EXCLUSION_REASON})
    return tuple(requestable), tuple(excluded)


def require_provider_query_assets(
    assets: Sequence[Mapping[str, object]],
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Return the closed partition or reject an empty provider-query subset."""

    requestable, excluded = partition_bybit_provider_query_assets(assets)
    if not requestable:
        raise BybitExecutionQualityUniverseError(
            "provider_query_asset_universe_empty"
        )
    return requestable, excluded


def build_capture_universe_values(
    *,
    capture_id: str,
    radar_assets: Sequence[Mapping[str, object]],
    provider_query_assets: Sequence[Mapping[str, object]],
    preflight_excluded_assets: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the exact immutable schema-v2 universe projection."""

    return {
        "schema_id": "decision_radar.bybit_execution_quality_radar_universe",
        "schema_version": UNIVERSE_SCHEMA_VERSION,
        "capture_id": capture_id,
        "asset_count": len(radar_assets),
        "assets": list(radar_assets),
        "provider_query_asset_count": len(provider_query_assets),
        "provider_query_assets": list(provider_query_assets),
        "preflight_excluded_asset_count": len(preflight_excluded_assets),
        "preflight_excluded_assets": list(preflight_excluded_assets),
        "selection_basis": UNIVERSE_SELECTION_BASIS,
        "identity_join_basis": IDENTITY_JOIN_BASIS,
        "canonical_identity_status": CANONICAL_IDENTITY_STATUS,
        "research_only": True,
    }


def capture_universe_projection_valid(
    universe: Mapping[str, object],
    *,
    capture_id: object,
) -> bool:
    """Return whether an immutable universe has the exact closed projection."""

    return (
        set(universe) == UNIVERSE_KEYS
        and universe.get("schema_id")
        == "decision_radar.bybit_execution_quality_radar_universe"
        and universe.get("schema_version") == UNIVERSE_SCHEMA_VERSION
        and universe.get("capture_id") == capture_id
        and universe.get("selection_basis") == UNIVERSE_SELECTION_BASIS
        and universe.get("identity_join_basis") == IDENTITY_JOIN_BASIS
        and universe.get("canonical_identity_status") == CANONICAL_IDENTITY_STATUS
        and universe.get("research_only") is True
    )


__all__ = (
    "CANONICAL_IDENTITY_STATUS",
    "IDENTITY_JOIN_BASIS",
    "RADAR_ASSET_KEYS",
    "UNIVERSE_KEYS",
    "UNIVERSE_SCHEMA_VERSION",
    "UNIVERSE_SELECTION_BASIS",
    "BybitExecutionQualityUniverseError",
    "build_capture_universe_values",
    "capture_universe_projection_valid",
    "partition_bybit_provider_query_assets",
    "require_provider_query_assets",
)
