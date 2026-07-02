"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.resolver`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import resolver as _resolver

globals().update(
    {
        name: getattr(_resolver, name)
        for name in dir(_resolver)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_resolver)
    if not (name.startswith("__") and name.endswith("__"))
)
