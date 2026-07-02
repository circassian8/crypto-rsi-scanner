"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.classification`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import classification as _classification

globals().update(
    {
        name: getattr(_classification, name)
        for name in dir(_classification)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_classification)
    if not (name.startswith("__") and name.endswith("__"))
)
