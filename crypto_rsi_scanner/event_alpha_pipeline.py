"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.pipeline`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import pipeline as _alpha_pipeline

globals().update(
    {
        name: getattr(_alpha_pipeline, name)
        for name in dir(_alpha_pipeline)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_alpha_pipeline)
    if not (name.startswith("__") and name.endswith("__"))
)
