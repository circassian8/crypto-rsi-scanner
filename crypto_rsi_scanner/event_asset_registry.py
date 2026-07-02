"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.asset_registry`."""

from __future__ import annotations

from .event_alpha.radar import asset_registry as _asset_registry

globals().update(
    {
        name: getattr(_asset_registry, name)
        for name in dir(_asset_registry)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_asset_registry)
    if not (name.startswith("__") and name.endswith("__"))
)
