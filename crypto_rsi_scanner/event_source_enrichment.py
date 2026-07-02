"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.source_enrichment`."""

from __future__ import annotations

from .event_alpha.radar import source_enrichment as _source_enrichment

globals().update(
    {
        name: getattr(_source_enrichment, name)
        for name in dir(_source_enrichment)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_source_enrichment)
    if not (name.startswith("__") and name.endswith("__"))
)
