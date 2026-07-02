"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.outcomes.eval`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.outcomes import eval as _eval

globals().update(
    {
        name: getattr(_eval, name)
        for name in dir(_eval)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_eval)
    if not (name.startswith("__") and name.endswith("__"))
)
