"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.eval`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import eval as _llm_eval

globals().update(
    {
        name: getattr(_llm_eval, name)
        for name in dir(_llm_eval)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_eval)
    if not (name.startswith("__") and name.endswith("__"))
)
