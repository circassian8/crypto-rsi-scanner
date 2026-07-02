"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.research_cards`."""

from __future__ import annotations

from .event_alpha.artifacts import research_cards as _research_cards

globals().update(
    {
        name: getattr(_research_cards, name)
        for name in dir(_research_cards)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_research_cards)
    if not (name.startswith("__") and name.endswith("__"))
)
