"""Compatibility shim for :mod:`crypto_rsi_scanner.event_core.models`."""

from __future__ import annotations

from crypto_rsi_scanner.event_core import models as _models

globals().update(
    {
        name: getattr(_models, name)
        for name in dir(_models)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_models)
    if not (name.startswith("__") and name.endswith("__"))
)
