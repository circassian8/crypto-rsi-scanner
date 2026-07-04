"""Canonical Event Alpha asset identity model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


QUOTE_ASSETS = frozenset({"USD", "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDD", "PYUSD"})
MAJOR_BASE_ASSETS = frozenset({"BTC", "ETH"})
THEME_OR_SECTOR_SYMBOLS = frozenset({"SECTOR", "THEME", "NARRATIVE"})


@dataclass(frozen=True)
class CanonicalAsset:
    canonical_asset_id: str
    symbol: str
    coin_id: str | None = None
    name: str | None = None
    aliases: tuple[str, ...] = ()
    contracts_by_chain: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    is_quote_asset: bool = False
    quote_asset_excluded: bool = False
    base_asset_excluded: bool = False
    major_base_asset: bool = False
    liquidity_tier: str | None = None
    venues: tuple[str, ...] = ()
    spot_symbols: tuple[str, ...] = ()
    perp_symbols: tuple[str, ...] = ()
    coinalyze_symbols: tuple[str, ...] = ()
    bybit_symbols: tuple[str, ...] = ()
    binance_symbols: tuple[str, ...] = ()
    dex_pool_ids: tuple[str, ...] = ()
    eligible_lanes: tuple[str, ...] = ()
    is_tradable_asset: bool = True
    is_theme_or_sector: bool = False
    diagnostics_reason: str | None = None
    asset_role: str | None = None
    source: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any], *, source: str | None = None) -> "CanonicalAsset":
        return canonical_asset_from_mapping(cls, row, source=source)

    def to_dict(self) -> dict[str, Any]:
        return canonical_asset_to_dict(self)


def canonical_asset_from_mapping(
    asset_cls: type[CanonicalAsset],
    row: Mapping[str, Any],
    *,
    source: str | None = None,
) -> CanonicalAsset:
    symbol = normalize_symbol(row.get("symbol") or row.get("base_symbol") or "")
    coin_id = _text(row.get("coin_id"))
    canonical_id = _text(row.get("canonical_asset_id")) or coin_id or symbol.casefold()
    is_quote = _bool(row.get("is_quote_asset")) or symbol in QUOTE_ASSETS
    is_theme = _bool(row.get("is_theme_or_sector")) or symbol in THEME_OR_SECTOR_SYMBOLS
    diagnostics_reason = _text(row.get("diagnostics_reason"))
    if is_quote and not diagnostics_reason:
        diagnostics_reason = "quote_asset_excluded"
    if is_theme and not diagnostics_reason:
        diagnostics_reason = "theme_or_sector_diagnostic"
    return asset_cls(
        canonical_asset_id=canonical_id,
        symbol=symbol,
        coin_id=coin_id,
        name=_text(row.get("name")),
        aliases=_tuple(row.get("aliases")),
        contracts_by_chain=_contracts(row.get("contracts_by_chain") or row.get("contracts")),
        is_quote_asset=is_quote,
        quote_asset_excluded=_bool(row.get("quote_asset_excluded")) or is_quote,
        base_asset_excluded=_bool(row.get("base_asset_excluded")),
        major_base_asset=_bool(row.get("major_base_asset")) or symbol in MAJOR_BASE_ASSETS,
        liquidity_tier=_text(row.get("liquidity_tier")),
        venues=_tuple(row.get("venues")),
        spot_symbols=_tuple(row.get("spot_symbols")),
        perp_symbols=_tuple(row.get("perp_symbols")),
        coinalyze_symbols=_tuple(row.get("coinalyze_symbols")),
        bybit_symbols=_tuple(row.get("bybit_symbols")),
        binance_symbols=_tuple(row.get("binance_symbols")),
        dex_pool_ids=_tuple(row.get("dex_pool_ids")),
        eligible_lanes=_tuple(row.get("eligible_lanes")),
        is_tradable_asset=(
            _bool(row.get("is_tradable_asset"))
            if row.get("is_tradable_asset") is not None
            else not (is_quote or is_theme)
        ),
        is_theme_or_sector=is_theme,
        diagnostics_reason=diagnostics_reason,
        asset_role=_text(row.get("asset_role") or row.get("role")),
        source=source or _text(row.get("source")),
    )


def canonical_asset_to_dict(asset: CanonicalAsset) -> dict[str, Any]:
    return {
        "canonical_asset_id": asset.canonical_asset_id,
        "symbol": asset.symbol,
        "coin_id": asset.coin_id,
        "name": asset.name,
        "aliases": list(asset.aliases),
        "contracts_by_chain": {chain: list(values) for chain, values in asset.contracts_by_chain.items()},
        "is_quote_asset": asset.is_quote_asset,
        "quote_asset_excluded": asset.quote_asset_excluded,
        "base_asset_excluded": asset.base_asset_excluded,
        "major_base_asset": asset.major_base_asset,
        "liquidity_tier": asset.liquidity_tier,
        "venues": list(asset.venues),
        "spot_symbols": list(asset.spot_symbols),
        "perp_symbols": list(asset.perp_symbols),
        "coinalyze_symbols": list(asset.coinalyze_symbols),
        "bybit_symbols": list(asset.bybit_symbols),
        "binance_symbols": list(asset.binance_symbols),
        "dex_pool_ids": list(asset.dex_pool_ids),
        "eligible_lanes": list(asset.eligible_lanes),
        "is_tradable_asset": asset.is_tradable_asset,
        "is_theme_or_sector": asset.is_theme_or_sector,
        "diagnostics_reason": asset.diagnostics_reason,
        "asset_role": asset.asset_role,
        "source": asset.source,
    }


def normalize_symbol(value: Any) -> str:
    return _text(value).strip().upper()


def quote_asset_symbols() -> tuple[str, ...]:
    return tuple(sorted(QUOTE_ASSETS))


def is_quote_asset_symbol(value: Any) -> bool:
    return normalize_symbol(value) in QUOTE_ASSETS


def is_theme_or_sector_symbol(value: Any) -> bool:
    return normalize_symbol(value) in THEME_OR_SECTOR_SYMBOLS


def _contracts(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for chain, addresses in value.items():
        chain_key = str(chain or "").strip().casefold()
        if not chain_key:
            continue
        if isinstance(addresses, str):
            values = (addresses,)
        elif isinstance(addresses, Iterable):
            values = tuple(str(item).strip() for item in addresses if str(item).strip())
        else:
            continue
        if values:
            out[chain_key] = tuple(dict.fromkeys(values))
    return out


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, Mapping):
        values = tuple(str(key) for key in value)
    elif isinstance(value, Iterable):
        values = tuple(str(item) for item in value)
    else:
        values = (str(value),)
    return tuple(dict.fromkeys(item.strip() for item in values if item and item.strip()))


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


__all__ = (
    "CanonicalAsset",
    "MAJOR_BASE_ASSETS",
    "QUOTE_ASSETS",
    "THEME_OR_SECTOR_SYMBOLS",
    "canonical_asset_from_mapping",
    "canonical_asset_to_dict",
    "is_quote_asset_symbol",
    "is_theme_or_sector_symbol",
    "normalize_symbol",
    "quote_asset_symbols",
)
