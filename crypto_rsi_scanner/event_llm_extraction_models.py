"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.extraction_models`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import extraction_models as _llm_extraction_models

globals().update(
    {
        name: getattr(_llm_extraction_models, name)
        for name in dir(_llm_extraction_models)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_extraction_models)
    if not (name.startswith("__") and name.endswith("__"))
)
