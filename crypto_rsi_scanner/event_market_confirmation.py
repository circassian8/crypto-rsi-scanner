"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.market_confirmation`."""

from __future__ import annotations

from .event_alpha.radar import market_confirmation as _market_confirmation

globals().update(
    {
        name: getattr(_market_confirmation, name)
        for name in dir(_market_confirmation)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_market_confirmation)
    if not (name.startswith("__") and name.endswith("__"))
)
