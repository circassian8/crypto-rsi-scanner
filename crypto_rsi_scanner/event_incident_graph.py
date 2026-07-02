"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.incident_graph`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import incident_graph as _incident_graph

globals().update(
    {
        name: getattr(_incident_graph, name)
        for name in dir(_incident_graph)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_incident_graph)
    if not (name.startswith("__") and name.endswith("__"))
)
