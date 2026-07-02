"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import catalyst_frames as _llm_catalyst_frames

globals().update(
    {
        name: getattr(_llm_catalyst_frames, name)
        for name in dir(_llm_catalyst_frames)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_catalyst_frames)
    if not (name.startswith("__") and name.endswith("__"))
)
