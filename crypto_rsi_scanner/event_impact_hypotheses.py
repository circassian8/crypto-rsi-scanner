"""Compatibility shim for Event Alpha impact hypotheses.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.radar.impact_hypotheses``.
"""

from __future__ import annotations

from .event_alpha.radar import impact_hypotheses as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
