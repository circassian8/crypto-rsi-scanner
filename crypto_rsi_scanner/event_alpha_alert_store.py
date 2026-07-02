"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.alert_store`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import alert_store as _alpha_alert_store

globals().update(
    {
        name: getattr(_alpha_alert_store, name)
        for name in dir(_alpha_alert_store)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_alpha_alert_store)
    if not (name.startswith("__") and name.endswith("__"))
)
