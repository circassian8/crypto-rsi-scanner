"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.budget`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import budget as _budget

globals().update(
    {
        name: getattr(_budget, name)
        for name in dir(_budget)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_budget)
    if not (name.startswith("__") and name.endswith("__"))
)
