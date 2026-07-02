"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.cache`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import cache as _cache

globals().update(
    {
        name: getattr(_cache, name)
        for name in dir(_cache)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_cache)
    if not (name.startswith("__") and name.endswith("__"))
)
