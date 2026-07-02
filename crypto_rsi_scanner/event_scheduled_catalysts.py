"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts`."""

from __future__ import annotations

from .event_alpha.radar import scheduled_catalysts as _scheduled_catalysts

globals().update(
    {
        name: getattr(_scheduled_catalysts, name)
        for name in dir(_scheduled_catalysts)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_scheduled_catalysts)
    if not (name.startswith("__") and name.endswith("__"))
)
