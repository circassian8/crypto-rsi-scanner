"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.daily_brief`."""

from __future__ import annotations

from .event_alpha.artifacts import daily_brief as _daily_brief

globals().update(
    {
        name: getattr(_daily_brief, name)
        for name in dir(_daily_brief)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_daily_brief)
    if not (name.startswith("__") and name.endswith("__"))
)
