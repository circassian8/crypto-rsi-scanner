"""Build the lean top-liquid plus manual-watchlist trading universe."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

from crypto_rsi_scanner.universe import exclusion_reason

from .bybit_universe import read_json_document
from .config import TOP_LIQUID_LIMIT
from .models import BybitInstrument, UniverseAsset


class _LeanUniverseError(ValueError):
    """Raised when market input cannot produce an honest universe projection."""


LeanUniverseError = _LeanUniverseError


@dataclass(frozen=True)
class LeanUniverseResult:
    status: str
    active_assets: tuple[UniverseAsset, ...]
    blocked_assets: tuple[UniverseAsset, ...]
    market_input_count: int
    top_liquid_count: int
    watchlist_count: int
    exclusion_counts: Mapping[str, int]
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "active_asset_count": len(self.active_assets),
            "active_assets": [row.to_dict() for row in self.active_assets],
            "blocked_asset_count": len(self.blocked_assets),
            "blocked_assets": [row.to_dict() for row in self.blocked_assets],
            "market_input_count": self.market_input_count,
            "top_liquid_count": self.top_liquid_count,
            "watchlist_count": self.watchlist_count,
            "exclusion_counts": dict(sorted(self.exclusion_counts.items())),
            "venue": "bybit",
            "instrument_type": "usdt_perpetual",
            "research_only": self.research_only,
        }


def load_market_rows(
    path: Path,
    *,
    require_genuine: bool = False,
) -> tuple[Mapping[str, object], ...]:
    payload, _digest = read_json_document(path, require_genuine=require_genuine)
    if not isinstance(payload, list):
        raise LeanUniverseError("market rows must be a JSON array")
    if len(payload) > 1_000:
        raise LeanUniverseError("market row input exceeds the bound")
    if not all(isinstance(row, Mapping) for row in payload):
        raise LeanUniverseError("market rows must be objects")
    return tuple(payload)


def build_universe(
    market_rows: Sequence[Mapping[str, object]],
    instruments: Sequence[BybitInstrument],
    manual_watchlist: Sequence[Mapping[str, object]] = (),
    *,
    limit: int = TOP_LIQUID_LIMIT,
) -> LeanUniverseResult:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise LeanUniverseError("universe limit must be between 1 and 200")
    clean: list[dict[str, object]] = []
    excluded: Counter[str] = Counter()
    for raw in market_rows:
        row = dict(raw)
        reason = exclusion_reason(row)
        volume = _finite_positive(row.get("total_volume"))
        price = _finite_positive(row.get("current_price"))
        market_cap = _finite_positive(row.get("market_cap"))
        canonical_id = row.get("id")
        symbol = row.get("symbol")
        name = row.get("name")
        if reason:
            excluded[reason] += 1
            continue
        if volume is None:
            excluded["missing_liquidity"] += 1
            continue
        if price is None:
            excluded["missing_price"] += 1
            continue
        if market_cap is None:
            excluded["missing_market_cap"] += 1
            continue
        if not all(
            isinstance(value, str) and value.strip()
            for value in (canonical_id, symbol, name)
        ):
            excluded["missing_identity"] += 1
            continue
        clean.append({
            **row,
            "id": str(canonical_id).strip(),
            "symbol": str(symbol).strip().upper(),
            "name": str(name).strip(),
            "_volume": volume,
            "_market_cap": market_cap,
        })
    clean.sort(
        key=lambda row: (
            -float(row["_volume"]),
            _rank_value(row.get("market_cap_rank")),
            str(row["id"]),
        )
    )
    top = clean[:limit]
    symbol_counts = Counter(str(row["symbol"]) for row in top)
    market_by_id = {str(row["id"]): row for row in clean}
    instrument_by_base = {row.base_coin: row for row in instruments}
    if len(instrument_by_base) != len(instruments):
        raise LeanUniverseError("Bybit base-coin identity is ambiguous")

    active_by_id: dict[str, UniverseAsset] = {}
    blocked_by_key: dict[tuple[str, str], UniverseAsset] = {}
    for rank, row in enumerate(top, start=1):
        candidate = _resolve_asset(
            row,
            instrument_by_base,
            liquidity_rank=rank,
            origins=("top_liquid",),
            ambiguous_symbol=symbol_counts[str(row["symbol"])] != 1,
        )
        if candidate.active:
            active_by_id[candidate.canonical_asset_id] = candidate
        else:
            blocked_by_key[(candidate.canonical_asset_id, "top_liquid")] = candidate

    for raw in manual_watchlist:
        canonical_id = raw.get("canonical_asset_id")
        symbol = raw.get("symbol")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            raise LeanUniverseError("watchlist canonical asset id is invalid")
        if not isinstance(symbol, str) or not symbol.strip():
            raise LeanUniverseError("watchlist symbol is invalid")
        canonical_id = canonical_id.strip()
        expected_symbol = symbol.strip().upper()
        market = market_by_id.get(canonical_id)
        if market is None:
            candidate = UniverseAsset(
                canonical_asset_id=canonical_id,
                symbol=expected_symbol,
                name=canonical_id,
                liquidity_rank=None,
                total_volume_usd_24h=None,
                bybit_instrument=(
                    instrument_by_base[expected_symbol].instrument_id
                    if expected_symbol in instrument_by_base else None
                ),
                origins=("manual_watchlist",),
                status="blocked_unverified",
                reason="market_data_missing",
                instrument_source_mode=(
                    instrument_by_base[expected_symbol].source_mode
                    if expected_symbol in instrument_by_base else None
                ),
            )
        elif str(market["symbol"]) != expected_symbol:
            candidate = UniverseAsset(
                canonical_asset_id=canonical_id,
                symbol=expected_symbol,
                name=str(market["name"]),
                liquidity_rank=None,
                total_volume_usd_24h=float(market["_volume"]),
                bybit_instrument=None,
                origins=("manual_watchlist",),
                status="blocked_unverified",
                reason="watchlist_identity_mismatch",
                instrument_source_mode=None,
            )
        else:
            candidate = _resolve_asset(
                market,
                instrument_by_base,
                liquidity_rank=None,
                origins=("manual_watchlist",),
                ambiguous_symbol=sum(
                    1 for row in clean if row["symbol"] == expected_symbol
                ) != 1,
            )
        existing = active_by_id.get(canonical_id)
        if candidate.active and existing is not None:
            active_by_id[canonical_id] = UniverseAsset(
                canonical_asset_id=existing.canonical_asset_id,
                symbol=existing.symbol,
                name=existing.name,
                liquidity_rank=existing.liquidity_rank,
                total_volume_usd_24h=existing.total_volume_usd_24h,
                bybit_instrument=existing.bybit_instrument,
                origins=tuple(
                    dict.fromkeys(existing.origins + ("manual_watchlist",))
                ),
                status=existing.status,
                reason=existing.reason,
                instrument_source_mode=existing.instrument_source_mode,
            )
        elif candidate.active:
            active_by_id[canonical_id] = candidate
        else:
            blocked_by_key[(canonical_id, "manual_watchlist")] = candidate

    active = tuple(
        sorted(
            active_by_id.values(),
            key=lambda row: (
                row.liquidity_rank is None,
                row.liquidity_rank or 10_000,
                row.symbol,
            ),
        )
    )
    blocked = tuple(
        sorted(
            blocked_by_key.values(),
            key=lambda row: (row.reason or "", row.symbol, row.canonical_asset_id),
        )
    )
    if not instruments:
        status = "bybit_catalog_missing"
    elif not market_rows:
        status = "market_data_missing"
    elif not active:
        status = "no_verified_active_assets"
    else:
        status = "ready"
    return LeanUniverseResult(
        status=status,
        active_assets=active,
        blocked_assets=blocked,
        market_input_count=len(market_rows),
        top_liquid_count=len(top),
        watchlist_count=len(manual_watchlist),
        exclusion_counts=excluded,
    )


def _resolve_asset(
    market: Mapping[str, object],
    instrument_by_base: Mapping[str, BybitInstrument],
    *,
    liquidity_rank: int | None,
    origins: tuple[str, ...],
    ambiguous_symbol: bool,
) -> UniverseAsset:
    canonical_id = str(market["id"])
    symbol = str(market["symbol"])
    instrument = instrument_by_base.get(symbol)
    reason = None
    if ambiguous_symbol:
        reason = "ambiguous_market_symbol"
    elif instrument is None:
        reason = "bybit_usdt_perpetual_unverified"
    return UniverseAsset(
        canonical_asset_id=canonical_id,
        symbol=symbol,
        name=str(market["name"]),
        liquidity_rank=liquidity_rank,
        total_volume_usd_24h=float(market["_volume"]),
        bybit_instrument=instrument.instrument_id if instrument and not reason else None,
        origins=origins,
        status="active" if instrument and not reason else "blocked_unverified",
        reason=reason,
        instrument_source_mode=instrument.source_mode if instrument else None,
    )


def _finite_positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def _rank_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return math.inf
    number = float(value)
    return number if math.isfinite(number) and number > 0 else math.inf


__all__ = (
    "LeanUniverseError",
    "LeanUniverseResult",
    "build_universe",
    "load_market_rows",
)
