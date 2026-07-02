"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.identity`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import identity as _identity

globals().update(
    {
        name: getattr(_identity, name)
        for name in dir(_identity)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_identity)
    if not (name.startswith("__") and name.endswith("__"))
)
