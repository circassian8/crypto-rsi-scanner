"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.discovery`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import discovery as _discovery

globals().update(
    {
        name: getattr(_discovery, name)
        for name in dir(_discovery)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_discovery)
    if not (name.startswith("__") and name.endswith("__"))
)
