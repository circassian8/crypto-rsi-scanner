"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.evidence_quality`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import evidence_quality as _evidence_quality

globals().update(
    {
        name: getattr(_evidence_quality, name)
        for name in dir(_evidence_quality)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_evidence_quality)
    if not (name.startswith("__") and name.endswith("__"))
)
