"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.config.health_guard`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.config import health_guard as _health_guard

globals().update(
    {
        name: getattr(_health_guard, name)
        for name in dir(_health_guard)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_health_guard)
    if not (name.startswith("__") and name.endswith("__"))
)
