"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.doctor.environment`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.doctor import environment as _environment

globals().update(
    {
        name: getattr(_environment, name)
        for name in dir(_environment)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_environment)
    if not (name.startswith("__") and name.endswith("__"))
)
