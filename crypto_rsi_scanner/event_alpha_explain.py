"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.explain`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import explain as _explain

globals().update(
    {
        name: getattr(_explain, name)
        for name in dir(_explain)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_explain)
    if not (name.startswith("__") and name.endswith("__"))
)
