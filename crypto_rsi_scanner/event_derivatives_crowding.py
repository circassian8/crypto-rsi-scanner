"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.derivatives_crowding`."""

from __future__ import annotations

from .event_alpha.radar import derivatives_crowding as _derivatives_crowding

globals().update(
    {
        name: getattr(_derivatives_crowding, name)
        for name in dir(_derivatives_crowding)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_derivatives_crowding)
    if not (name.startswith("__") and name.endswith("__"))
)
