"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import catalyst_frame_validator as _catalyst_frame_validator

globals().update(
    {
        name: getattr(_catalyst_frame_validator, name)
        for name in dir(_catalyst_frame_validator)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_catalyst_frame_validator)
    if not (name.startswith("__") and name.endswith("__"))
)
