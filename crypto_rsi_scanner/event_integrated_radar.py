"""Compatibility shim for integrated Event Alpha radar.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.radar.integrated_radar``.
"""

from __future__ import annotations

from .event_alpha.radar import integrated_radar as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
