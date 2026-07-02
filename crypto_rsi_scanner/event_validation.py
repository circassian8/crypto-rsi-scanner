"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.validation`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import validation as _validation

globals().update(
    {
        name: getattr(_validation, name)
        for name in dir(_validation)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_validation)
    if not (name.startswith("__") and name.endswith("__"))
)
