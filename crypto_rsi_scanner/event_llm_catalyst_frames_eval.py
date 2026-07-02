"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import catalyst_frames_eval as _catalyst_frames_eval

globals().update(
    {
        name: getattr(_catalyst_frames_eval, name)
        for name in dir(_catalyst_frames_eval)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_catalyst_frames_eval)
    if not (name.startswith("__") and name.endswith("__"))
)
