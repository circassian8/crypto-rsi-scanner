"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.config.profiles`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.config import profiles as _profiles

globals().update(
    {
        name: getattr(_profiles, name)
        for name in dir(_profiles)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_profiles)
    if not (name.startswith("__") and name.endswith("__"))
)
