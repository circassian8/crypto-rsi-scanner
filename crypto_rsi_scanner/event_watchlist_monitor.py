"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.notifications import watchlist_monitor as _watchlist_monitor

globals().update(
    {
        name: getattr(_watchlist_monitor, name)
        for name in dir(_watchlist_monitor)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_watchlist_monitor)
    if not (name.startswith("__") and name.endswith("__"))
)
