"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.replay`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import replay as _alpha_replay

globals().update(
    {
        name: getattr(_alpha_replay, name)
        for name in dir(_alpha_replay)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_alpha_replay)
    if not (name.startswith("__") and name.endswith("__"))
)
