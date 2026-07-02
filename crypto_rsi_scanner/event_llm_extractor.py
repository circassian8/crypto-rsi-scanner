"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.extractor`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import extractor as _llm_extractor

globals().update(
    {
        name: getattr(_llm_extractor, name)
        for name in dir(_llm_extractor)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_extractor)
    if not (name.startswith("__") and name.endswith("__"))
)
