"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.outcomes import outcome_artifacts as _outcome_artifacts

globals().update(
    {
        name: getattr(_outcome_artifacts, name)
        for name in dir(_outcome_artifacts)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_outcome_artifacts)
    if not (name.startswith("__") and name.endswith("__"))
)
