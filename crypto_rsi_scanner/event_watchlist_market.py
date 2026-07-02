"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.watchlist_market`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import watchlist_market as _watchlist_market

globals().update(
    {
        name: getattr(_watchlist_market, name)
        for name in dir(_watchlist_market)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_watchlist_market)
    if not (name.startswith("__") and name.endswith("__"))
)
