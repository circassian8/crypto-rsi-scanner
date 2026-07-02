"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.outcomes import burn_in_checklist as _burn_in_checklist

globals().update(
    {
        name: getattr(_burn_in_checklist, name)
        for name in dir(_burn_in_checklist)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_burn_in_checklist)
    if not (name.startswith("__") and name.endswith("__"))
)
