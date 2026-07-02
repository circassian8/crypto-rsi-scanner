"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.catalyst_frames`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import catalyst_frames as _catalyst_frames

globals().update(
    {
        name: getattr(_catalyst_frames, name)
        for name in dir(_catalyst_frames)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_catalyst_frames)
    if not (name.startswith("__") and name.endswith("__"))
)
