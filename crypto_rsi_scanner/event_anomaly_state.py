"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.anomaly_state`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import anomaly_state as _anomaly_state

globals().update(
    {
        name: getattr(_anomaly_state, name)
        for name in dir(_anomaly_state)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_anomaly_state)
    if not (name.startswith("__") and name.endswith("__"))
)
