"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit`."""

from __future__ import annotations

from .event_alpha.artifacts import opportunity_audit as _opportunity_audit

globals().update(
    {
        name: getattr(_opportunity_audit, name)
        for name in dir(_opportunity_audit)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_opportunity_audit)
    if not (name.startswith("__") and name.endswith("__"))
)
