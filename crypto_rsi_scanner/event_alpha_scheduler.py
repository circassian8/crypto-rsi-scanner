"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.config.scheduler`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.config import scheduler as _scheduler

globals().update(
    {
        name: getattr(_scheduler, name)
        for name in dir(_scheduler)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_scheduler)
    if not (name.startswith("__") and name.endswith("__"))
)
