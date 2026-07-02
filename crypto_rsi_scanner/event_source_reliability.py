"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.providers.source_reliability`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.providers import source_reliability as _source_reliability

globals().update(
    {
        name: getattr(_source_reliability, name)
        for name in dir(_source_reliability)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_source_reliability)
    if not (name.startswith("__") and name.endswith("__"))
)
