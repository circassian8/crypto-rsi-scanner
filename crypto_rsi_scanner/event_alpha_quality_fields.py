"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.outcomes.quality_fields`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.outcomes import quality_fields as _quality_fields

globals().update(
    {
        name: getattr(_quality_fields, name)
        for name in dir(_quality_fields)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_quality_fields)
    if not (name.startswith("__") and name.endswith("__"))
)
