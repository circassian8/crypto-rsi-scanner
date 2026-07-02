"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.anomaly_scanner`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import anomaly_scanner as _anomaly_scanner

globals().update(
    {
        name: getattr(_anomaly_scanner, name)
        for name in dir(_anomaly_scanner)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_anomaly_scanner)
    if not (name.startswith("__") and name.endswith("__"))
)
