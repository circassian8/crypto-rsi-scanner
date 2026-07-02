"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.playbooks`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import playbooks as _playbooks

globals().update(
    {
        name: getattr(_playbooks, name)
        for name in dir(_playbooks)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_playbooks)
    if not (name.startswith("__") and name.endswith("__"))
)
