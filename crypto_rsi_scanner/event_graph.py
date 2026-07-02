"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.graph`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import graph as _graph

globals().update(
    {
        name: getattr(_graph, name)
        for name in dir(_graph)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_graph)
    if not (name.startswith("__") and name.endswith("__"))
)
