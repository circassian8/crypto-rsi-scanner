"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.watchlist`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import watchlist as _watchlist

globals().update(
    {
        name: getattr(_watchlist, name)
        for name in dir(_watchlist)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_watchlist)
    if not (name.startswith("__") and name.endswith("__"))
)
