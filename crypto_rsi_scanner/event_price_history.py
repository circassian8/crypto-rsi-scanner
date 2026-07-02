"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.price_history`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import price_history as _price_history

globals().update(
    {
        name: getattr(_price_history, name)
        for name in dir(_price_history)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_price_history)
    if not (name.startswith("__") and name.endswith("__"))
)
