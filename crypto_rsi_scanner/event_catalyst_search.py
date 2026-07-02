"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.catalyst_search`."""

from __future__ import annotations

from .event_alpha.radar import catalyst_search as _catalyst_search

globals().update(
    {
        name: getattr(_catalyst_search, name)
        for name in dir(_catalyst_search)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_catalyst_search)
    if not (name.startswith("__") and name.endswith("__"))
)
