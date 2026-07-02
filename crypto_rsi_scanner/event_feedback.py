"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.outcomes.feedback_labels`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.outcomes import feedback_labels as _feedback

globals().update(
    {
        name: getattr(_feedback, name)
        for name in dir(_feedback)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_feedback)
    if not (name.startswith("__") and name.endswith("__"))
)
