"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import watchlist_enrichment as _watchlist_enrichment

globals().update(
    {
        name: getattr(_watchlist_enrichment, name)
        for name in dir(_watchlist_enrichment)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_watchlist_enrichment)
    if not (name.startswith("__") and name.endswith("__"))
)
