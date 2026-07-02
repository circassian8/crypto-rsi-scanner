"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.notifications.router`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.notifications import router as _alpha_router

globals().update(
    {
        name: getattr(_alpha_router, name)
        for name in dir(_alpha_router)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_alpha_router)
    if not (name.startswith("__") and name.endswith("__"))
)
