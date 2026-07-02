"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.analyzer`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import analyzer as _llm_analyzer

globals().update(
    {
        name: getattr(_llm_analyzer, name)
        for name in dir(_llm_analyzer)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_analyzer)
    if not (name.startswith("__") and name.endswith("__"))
)
