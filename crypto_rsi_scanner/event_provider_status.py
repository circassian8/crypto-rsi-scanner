"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.notifications.provider_status`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.notifications import provider_status as _provider_status

globals().update(
    {
        name: getattr(_provider_status, name)
        for name in dir(_provider_status)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_provider_status)
    if not (name.startswith("__") and name.endswith("__"))
)
