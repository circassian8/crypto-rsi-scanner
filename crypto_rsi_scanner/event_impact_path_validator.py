"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.impact_path_validator`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import impact_path_validator as _impact_path_validator

globals().update(
    {
        name: getattr(_impact_path_validator, name)
        for name in dir(_impact_path_validator)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_impact_path_validator)
    if not (name.startswith("__") and name.endswith("__"))
)
