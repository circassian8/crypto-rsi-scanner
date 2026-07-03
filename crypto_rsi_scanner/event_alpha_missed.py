"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.missed`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import missed as _missed

globals().update(
    {
        name: getattr(_missed, name)
        for name in dir(_missed)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_missed)
    if not (name.startswith("__") and name.endswith("__"))
)
