"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.instrument_resolver`."""

from __future__ import annotations

from .event_alpha.radar import instrument_resolver as _instrument_resolver

globals().update(
    {
        name: getattr(_instrument_resolver, name)
        for name in dir(_instrument_resolver)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_instrument_resolver)
    if not (name.startswith("__") and name.endswith("__"))
)
