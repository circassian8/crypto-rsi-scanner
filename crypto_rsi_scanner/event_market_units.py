"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.market_units`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import market_units as _market_units

globals().update(
    {
        name: getattr(_market_units, name)
        for name in dir(_market_units)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_market_units)
    if not (name.startswith("__") and name.endswith("__"))
)
