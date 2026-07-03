"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.artifacts.reason_text`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import reason_text as _reason_text

globals().update(
    {
        name: getattr(_reason_text, name)
        for name in dir(_reason_text)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_reason_text)
    if not (name.startswith("__") and name.endswith("__"))
)
