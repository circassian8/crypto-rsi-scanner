"""Compatibility shim for :mod:`crypto_rsi_scanner.event_core.clock`."""

from __future__ import annotations

from crypto_rsi_scanner.event_core import clock as _clock

globals().update(
    {
        name: getattr(_clock, name)
        for name in dir(_clock)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_clock)
    if not (name.startswith("__") and name.endswith("__"))
)
