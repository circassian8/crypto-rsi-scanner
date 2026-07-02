"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.claim_semantics`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import claim_semantics as _claim_semantics

globals().update(
    {
        name: getattr(_claim_semantics, name)
        for name in dir(_claim_semantics)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_claim_semantics)
    if not (name.startswith("__") and name.endswith("__"))
)
