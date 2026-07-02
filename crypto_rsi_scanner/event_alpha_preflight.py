"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.config.preflight`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.config import preflight as _preflight

globals().update(
    {
        name: getattr(_preflight, name)
        for name in dir(_preflight)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_preflight)
    if not (name.startswith("__") and name.endswith("__"))
)
