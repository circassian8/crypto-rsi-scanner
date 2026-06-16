"""CoinGecko-style asset universe provider for event-discovery research."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable, Mapping

from .. import config, universe
from ..client import CoinGeckoClient
from ..event_models import DiscoveredAsset

log = logging.getLogger(__name__)

CoinGeckoClientFactory = Callable[[], Any]


class CoinGeckoUniverseProvider:
    """Load CoinGecko market rows from a local fixture and apply shared hygiene."""

    name = "coingecko_universe"

    def __init__(
        self,
        path: str | Path | None,
        *,
        limit: int | None = None,
        required: bool = False,
        live_enabled: bool = False,
        live_fetch_limit: int | None = None,
        client_factory: CoinGeckoClientFactory | None = None,
    ) -> None:
        self.path = Path(path).expanduser() if path else None
        self.limit = limit
        self.required = required
        self.live_enabled = live_enabled
        self.live_fetch_limit = live_fetch_limit
        self.client_factory = client_factory or CoinGeckoClient

    def fetch_assets(self) -> list[DiscoveredAsset]:
        if self.path is None and self.live_enabled:
            return self._fetch_live_assets()
        if self.path is None:
            return []
        try:
            markets = load_market_rows(self.path)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("CoinGecko universe fixture load failed: %s", exc)
            return []
        return assets_from_markets(markets, limit=self.limit)

    def _fetch_live_assets(self) -> list[DiscoveredAsset]:
        try:
            markets = _run_async(self._fetch_live_markets())
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("CoinGecko live universe fetch failed: %s", exc)
            return []
        return assets_from_markets(markets, limit=self.limit)

    async def _fetch_live_markets(self) -> list[dict[str, Any]]:
        target = self.limit or config.TOP_N
        fetch_n = self.live_fetch_limit or universe.candidate_count(target)
        async with self.client_factory() as client:
            rows = await client.get_top_markets(fetch_n)
        return [dict(row) for row in rows if isinstance(row, Mapping)]


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    close = getattr(coro, "close", None)
    if close:
        close()
    raise RuntimeError("CoinGecko live universe fetch cannot run inside an active event loop")


def load_market_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if p.is_dir():
        p = p / "top_markets.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"CoinGecko market fixture must be a list: {p}")
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"CoinGecko market fixture row {idx} must be an object")
        rows.append(dict(item))
    return rows


def assets_from_markets(markets: list[dict[str, Any]], *, limit: int | None = None) -> list[DiscoveredAsset]:
    clean, _excluded, _audit = universe.filter_markets_with_audit(markets, limit=limit)
    return [asset_from_market(row) for row in clean]


def asset_from_market(market: Mapping[str, Any]) -> DiscoveredAsset:
    symbol = str(market.get("symbol") or "").upper()
    name = str(market.get("name") or "")
    coin_id = str(market.get("id") or "")
    aliases = tuple(
        alias for alias in (coin_id, name, symbol)
        if alias
    )
    return DiscoveredAsset(
        coin_id=coin_id,
        symbol=symbol,
        name=name,
        market_cap=_float_or_none(market.get("market_cap")),
        volume_24h=_float_or_none(market.get("total_volume")),
        price=_float_or_none(market.get("current_price")),
        categories=tuple(str(c) for c in market.get("categories") or ()),
        contract_addresses=_contract_addresses(market),
        source="coingecko_universe",
        aliases=aliases,
    )


def _contract_addresses(market: Mapping[str, Any]) -> dict[str, str]:
    platforms = market.get("platforms")
    if isinstance(platforms, Mapping):
        return {str(chain): str(address) for chain, address in platforms.items() if address}
    address = market.get("contract_address")
    platform = market.get("asset_platform_id") or market.get("platform")
    if address and platform:
        return {str(platform): str(address)}
    return {}


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
