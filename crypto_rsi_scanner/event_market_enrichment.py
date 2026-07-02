"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.market_enrichment`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import market_enrichment as _market_enrichment

globals().update(
    {
        name: getattr(_market_enrichment, name)
        for name in dir(_market_enrichment)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_market_enrichment)
    if not (name.startswith("__") and name.endswith("__"))
)
