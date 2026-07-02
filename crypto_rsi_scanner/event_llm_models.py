"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.models`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import models as _llm_models

globals().update(
    {
        name: getattr(_llm_models, name)
        for name in dir(_llm_models)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_models)
    if not (name.startswith("__") and name.endswith("__"))
)
