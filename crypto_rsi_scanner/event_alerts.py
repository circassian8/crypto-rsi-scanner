"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.alerts`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import alerts as _alerts

globals().update(
    {
        name: getattr(_alerts, name)
        for name in dir(_alerts)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_alerts)
    if not (name.startswith("__") and name.endswith("__"))
)
