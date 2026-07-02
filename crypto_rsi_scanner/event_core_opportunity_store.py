"""Compatibility shim for Event Alpha CoreOpportunity store.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.radar.core_opportunity_store``.
"""

from __future__ import annotations

from .event_alpha.radar import core_opportunity_store as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
