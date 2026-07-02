"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.near_miss`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import near_miss as _near_miss

globals().update(
    {
        name: getattr(_near_miss, name)
        for name in dir(_near_miss)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_near_miss)
    if not (name.startswith("__") and name.endswith("__"))
)
