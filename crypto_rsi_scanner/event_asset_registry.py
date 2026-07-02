"""Canonical crypto asset registry for Event Alpha research artifacts.

The registry is an identity layer only. It normalizes provider symbols and
instrument names to a stable research asset id without creating alerts, paper
trades, normal RSI signal rows, or execution instructions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ASSET_REGISTRY_JSON = "event_asset_registry.json"

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
        return cls(
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_asset_id": self.canonical_asset_id,
            "symbol": self.symbol,
            "coin_id": self.coin_id,
            "name": self.name,
            "aliases": list(self.aliases),
            "contracts_by_chain": {chain: list(values) for chain, values in self.contracts_by_chain.items()},
            "is_quote_asset": self.is_quote_asset,
            "quote_asset_excluded": self.quote_asset_excluded,
            "base_asset_excluded": self.base_asset_excluded,
            "major_base_asset": self.major_base_asset,
            "liquidity_tier": self.liquidity_tier,
            "venues": list(self.venues),
            "spot_symbols": list(self.spot_symbols),
            "perp_symbols": list(self.perp_symbols),
            "coinalyze_symbols": list(self.coinalyze_symbols),
            "bybit_symbols": list(self.bybit_symbols),
            "binance_symbols": list(self.binance_symbols),
            "dex_pool_ids": list(self.dex_pool_ids),
            "eligible_lanes": list(self.eligible_lanes),
            "is_tradable_asset": self.is_tradable_asset,
            "is_theme_or_sector": self.is_theme_or_sector,
            "diagnostics_reason": self.diagnostics_reason,
            "asset_role": self.asset_role,
            "source": self.source,
        }


def load_asset_registry(path: str | Path | None) -> tuple[CanonicalAsset, ...]:
    if path is None:
        return ()
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return ()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = data.get("assets") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        return ()
    return tuple(
        CanonicalAsset.from_mapping(row, source="fixture_registry")
        for row in rows
        if isinstance(row, Mapping)
    )


def load_asset_registry_artifact(path_or_dir: str | Path | None) -> tuple[CanonicalAsset, ...]:
    if path_or_dir is None:
        return ()
    path = Path(path_or_dir).expanduser()
    if path.is_dir():
        path = path / ASSET_REGISTRY_JSON
    return load_asset_registry(path)


def assets_from_coingecko_universe(path: str | Path | None) -> tuple[CanonicalAsset, ...]:
    if path is None:
        return ()
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return ()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = data
    if isinstance(data, Mapping):
        rows = data.get("assets") or data.get("coins") or data.get("markets") or data.get("rows") or []
    if not isinstance(rows, list):
        return ()
    assets: list[CanonicalAsset] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        symbol = normalize_symbol(row.get("symbol"))
        coin_id = _text(row.get("id") or row.get("coin_id"))
        if not symbol or not coin_id:
            continue
        assets.append(
            CanonicalAsset(
                canonical_asset_id=coin_id,
                symbol=symbol,
                coin_id=coin_id,
                name=_text(row.get("name")),
                aliases=tuple(dict.fromkeys((symbol, coin_id, _text(row.get("name"))))),
                contracts_by_chain=_contracts(row.get("platforms") or row.get("contracts_by_chain")),
                is_quote_asset=symbol in QUOTE_ASSETS,
                quote_asset_excluded=symbol in QUOTE_ASSETS,
                base_asset_excluded=False,
                major_base_asset=symbol in MAJOR_BASE_ASSETS,
                liquidity_tier=_liquidity_tier(row),
                venues=("coingecko",),
                eligible_lanes=("research",),
                is_tradable_asset=symbol not in QUOTE_ASSETS,
                is_theme_or_sector=symbol in THEME_OR_SECTOR_SYMBOLS,
                diagnostics_reason="quote_asset_excluded" if symbol in QUOTE_ASSETS else None,
                source="coingecko_universe_cache",
            )
        )
    return tuple(assets)


def assets_from_official_exchange(rows: Iterable[Mapping[str, Any]]) -> tuple[CanonicalAsset, ...]:
    assets: list[CanonicalAsset] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        exchange = _text(row.get("exchange") or row.get("provider")) or "official_exchange"
        scope = _text(row.get("listing_scope") or row.get("event_type"))
        symbols = _candidate_symbols(row)
        coin_ids = _tuple(row.get("coin_ids"))
        pairs = _tuple(row.get("pairs"))
        if not symbols and pairs:
            symbols = tuple(dict.fromkeys(_pair_base_symbol(pair) for pair in pairs if _pair_base_symbol(pair)))
        for idx, symbol in enumerate(symbols):
            coin_id = _text(row.get("coin_id")) or (coin_ids[idx] if idx < len(coin_ids) else None) or symbol.casefold()
            bybit_symbols = pairs if "bybit" in exchange.casefold() else ()
            binance_symbols = pairs if "binance" in exchange.casefold() else ()
            spot_symbols = pairs if scope in {"spot", "new_trading_pair", "spot_listing"} else ()
            perp_symbols = pairs if "perp" in scope or "futures" in scope else ()
            if not perp_symbols and any("PERP" in pair.upper() or "USDT" in pair.upper() and "perp" in scope for pair in pairs):
                perp_symbols = pairs
            is_quote = symbol in QUOTE_ASSETS
            is_theme = symbol in THEME_OR_SECTOR_SYMBOLS
            assets.append(
                CanonicalAsset(
                    canonical_asset_id=coin_id,
                    symbol=symbol,
                    coin_id=coin_id,
                    name=None,
                    aliases=(symbol, coin_id),
                    contracts_by_chain=_contracts(row.get("contracts")),
                    is_quote_asset=is_quote,
                    quote_asset_excluded=is_quote,
                    base_asset_excluded=False,
                    major_base_asset=symbol in MAJOR_BASE_ASSETS,
                    liquidity_tier=None,
                    venues=(exchange,),
                    spot_symbols=spot_symbols,
                    perp_symbols=perp_symbols,
                    bybit_symbols=bybit_symbols,
                    binance_symbols=binance_symbols,
                    eligible_lanes=("official_exchange",),
                    is_tradable_asset=not (is_quote or is_theme),
                    is_theme_or_sector=is_theme,
                    diagnostics_reason=(
                        "quote_asset_excluded" if is_quote else "theme_or_sector_diagnostic" if is_theme else None
                    ),
                    source="official_exchange_artifact",
                )
            )
    return tuple(assets)


def assets_from_coinalyze(rows: Iterable[Mapping[str, Any]]) -> tuple[CanonicalAsset, ...]:
    assets: list[CanonicalAsset] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        market_symbol = _text(
            row.get("coinalyze_symbol")
            or row.get("market_symbol")
            or row.get("market")
            or row.get("symbol")
        )
        base_symbol = normalize_symbol(row.get("base_symbol") or row.get("base_asset") or _base_from_market_symbol(market_symbol))
        if not base_symbol:
            continue
        coin_id = _text(row.get("coin_id") or row.get("validated_coin_id")) or base_symbol.casefold()
        is_quote = base_symbol in QUOTE_ASSETS
        assets.append(
            CanonicalAsset(
                canonical_asset_id=coin_id,
                symbol=base_symbol,
                coin_id=coin_id,
                aliases=tuple(dict.fromkeys((base_symbol, coin_id))),
                is_quote_asset=is_quote,
                quote_asset_excluded=is_quote,
                base_asset_excluded=False,
                major_base_asset=base_symbol in MAJOR_BASE_ASSETS,
                venues=("coinalyze",),
                perp_symbols=(market_symbol,) if market_symbol else (),
                coinalyze_symbols=(market_symbol,) if market_symbol else (),
                eligible_lanes=("derivatives",),
                is_tradable_asset=not is_quote,
                is_theme_or_sector=base_symbol in THEME_OR_SECTOR_SYMBOLS,
                diagnostics_reason="quote_asset_excluded" if is_quote else None,
                source="coinalyze_derivatives_artifact",
            )
        )
    return tuple(assets)


def build_asset_registry(
    *,
    fixture_path: str | Path | None = None,
    coingecko_universe_path: str | Path | None = None,
    official_exchange_rows: Iterable[Mapping[str, Any]] = (),
    coinalyze_rows: Iterable[Mapping[str, Any]] = (),
) -> tuple[CanonicalAsset, ...]:
    assets = [
        *_built_in_assets(),
        *load_asset_registry(fixture_path),
        *assets_from_coingecko_universe(coingecko_universe_path),
        *assets_from_official_exchange(official_exchange_rows),
        *assets_from_coinalyze(coinalyze_rows),
    ]
    return _merge_assets(assets)


def write_asset_registry_artifact(
    registry: Iterable[CanonicalAsset],
    namespace_dir: str | Path,
    *,
    generated_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> Path:
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ASSET_REGISTRY_JSON
    rows = tuple(registry)
    payload = {
        "schema_version": 1,
        "row_type": "event_asset_registry",
        "research_only": True,
        "generated_at": _time_text(generated_at),
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "asset_count": len(rows),
        "assets": [asset.to_dict() for asset in rows],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def registry_index_keys(asset: CanonicalAsset) -> tuple[str, ...]:
    keys: list[str] = []
    for value in (
        asset.canonical_asset_id,
        asset.coin_id,
        asset.symbol,
        asset.name,
        *asset.aliases,
        *asset.spot_symbols,
        *asset.perp_symbols,
        *asset.coinalyze_symbols,
        *asset.bybit_symbols,
        *asset.binance_symbols,
        *asset.dex_pool_ids,
    ):
        keys.extend(identifier_key_variants(value))
    for values in asset.contracts_by_chain.values():
        for address in values:
            keys.extend(identifier_key_variants(address))
    return tuple(dict.fromkeys(key for key in keys if key))


def identifier_key_variants(value: Any) -> tuple[str, ...]:
    text = _text(value)
    if not text:
        return ()
    raw = text.strip()
    compact = re.sub(r"[\s/_:-]+", "", raw).casefold()
    variants = [raw.casefold(), compact]
    upper = raw.upper().replace("/", "")
    for suffix in ("USDT_PERP.A", "USDT_PERP", "USDT", "USD_PERP", "USD"):
        if upper.endswith(suffix):
            variants.append(upper[: -len(suffix)].casefold())
    if "/" in raw:
        variants.append(raw.split("/", 1)[0].casefold())
    if "_" in raw:
        variants.append(raw.split("_", 1)[0].casefold())
    return tuple(dict.fromkeys(item for item in variants if item))


def normalize_symbol(value: Any) -> str:
    return _text(value).strip().upper()


def quote_asset_symbols() -> tuple[str, ...]:
    return tuple(sorted(QUOTE_ASSETS))


def is_quote_asset_symbol(value: Any) -> bool:
    return normalize_symbol(value) in QUOTE_ASSETS


def is_theme_or_sector_symbol(value: Any) -> bool:
    return normalize_symbol(value) in THEME_OR_SECTOR_SYMBOLS


def _built_in_assets() -> tuple[CanonicalAsset, ...]:
    quote_assets = tuple(
        CanonicalAsset(
            canonical_asset_id=symbol.casefold(),
            symbol=symbol,
            coin_id=symbol.casefold(),
            name=symbol,
            aliases=(symbol,),
            is_quote_asset=True,
            quote_asset_excluded=True,
            base_asset_excluded=True,
            is_tradable_asset=False,
            diagnostics_reason="quote_asset_excluded",
            source="built_in_guardrail",
        )
        for symbol in sorted(QUOTE_ASSETS)
    )
    return (
        *quote_assets,
        CanonicalAsset(
            canonical_asset_id="sector",
            symbol="SECTOR",
            coin_id="sector",
            name="Sector or theme diagnostic",
            aliases=("SECTOR", "THEME", "sector", "theme"),
            is_tradable_asset=False,
            is_theme_or_sector=True,
            diagnostics_reason="theme_or_sector_diagnostic",
            source="built_in_guardrail",
        ),
    )


def _merge_assets(assets: Iterable[CanonicalAsset]) -> tuple[CanonicalAsset, ...]:
    records: dict[str, dict[str, Any]] = {}
    key_index: dict[str, str] = {}
    for asset in assets:
        if not asset.canonical_asset_id or not asset.symbol:
            continue
        incoming = asset.to_dict()
        target_id = None
        for key in registry_index_keys(asset):
            if key in key_index:
                target_id = key_index[key]
                break
        if target_id is None:
            target_id = asset.canonical_asset_id
            records[target_id] = incoming
        else:
            records[target_id] = _merge_record(records[target_id], incoming)
        for key in registry_index_keys(CanonicalAsset.from_mapping(records[target_id])):
            key_index.setdefault(key, target_id)
    out = [CanonicalAsset.from_mapping(row, source=_text(row.get("source"))) for row in records.values()]
    return tuple(sorted(out, key=lambda item: (item.symbol, item.canonical_asset_id)))


def _merge_record(existing: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(existing)
    for key in ("canonical_asset_id", "symbol", "coin_id", "name", "liquidity_tier", "diagnostics_reason", "asset_role", "source"):
        if not out.get(key) and incoming.get(key):
            out[key] = incoming.get(key)
    for key in (
        "aliases",
        "venues",
        "spot_symbols",
        "perp_symbols",
        "coinalyze_symbols",
        "bybit_symbols",
        "binance_symbols",
        "dex_pool_ids",
        "eligible_lanes",
    ):
        out[key] = list(dict.fromkeys((*_tuple(out.get(key)), *_tuple(incoming.get(key)))))
    out["contracts_by_chain"] = _merge_contracts(out.get("contracts_by_chain"), incoming.get("contracts_by_chain"))
    for key in ("is_quote_asset", "quote_asset_excluded", "base_asset_excluded", "major_base_asset", "is_theme_or_sector"):
        out[key] = _bool(out.get(key)) or _bool(incoming.get(key))
    if _bool(out.get("is_quote_asset")) or _bool(out.get("is_theme_or_sector")) or _bool(incoming.get("is_tradable_asset")) is False:
        out["is_tradable_asset"] = False
    else:
        out["is_tradable_asset"] = _bool(out.get("is_tradable_asset")) or _bool(incoming.get("is_tradable_asset"))
    return out


def _candidate_symbols(row: Mapping[str, Any]) -> tuple[str, ...]:
    symbol = normalize_symbol(row.get("symbol") or row.get("validated_symbol") or row.get("asset_symbol"))
    symbols = _tuple(row.get("symbols") or row.get("announcement_symbols"))
    normalized = [normalize_symbol(item) for item in ((*symbols, symbol) if symbol else symbols)]
    return tuple(dict.fromkeys(item for item in normalized if item))


def _base_from_market_symbol(value: Any) -> str:
    text = normalize_symbol(value)
    if not text:
        return ""
    if "/" in text:
        return normalize_symbol(text.split("/", 1)[0])
    for suffix in ("USDT_PERP.A", "USDT_PERP", "USDT", "USD_PERP", "USD"):
        if text.endswith(suffix):
            return normalize_symbol(text[: -len(suffix)])
    return text


def _pair_base_symbol(pair: str) -> str:
    text = str(pair or "").strip()
    if "/" in text:
        return normalize_symbol(text.split("/", 1)[0])
    return _base_from_market_symbol(text)


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


def _merge_contracts(left: Any, right: Any) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for source in (_contracts(left), _contracts(right)):
        for chain, values in source.items():
            merged[chain] = list(dict.fromkeys((*merged.get(chain, []), *values)))
    return merged


def _liquidity_tier(row: Mapping[str, Any]) -> str | None:
    rank = _int(row.get("market_cap_rank") or row.get("rank"))
    if rank and rank <= 50:
        return "large"
    if rank and rank <= 200:
        return "mid"
    volume = _float(row.get("total_volume") or row.get("volume_usd") or row.get("liquidity_usd"))
    if volume >= 50_000_000:
        return "large"
    if volume >= 5_000_000:
        return "mid"
    if volume > 0:
        return "thin"
    return None


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


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _time_text(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()
