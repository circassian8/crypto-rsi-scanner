"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.config.v1_readiness`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.config import v1_readiness as _v1_readiness

globals().update(
    {
        name: getattr(_v1_readiness, name)
        for name in dir(_v1_readiness)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_v1_readiness)
    if not (name.startswith("__") and name.endswith("__"))
)
