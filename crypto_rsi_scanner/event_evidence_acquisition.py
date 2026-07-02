"""Compatibility shim for Event Alpha evidence acquisition.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.radar.evidence_acquisition``.
"""

from __future__ import annotations

from .event_alpha.radar import evidence_acquisition as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
