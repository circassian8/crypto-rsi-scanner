"""Compatibility shim for Event Alpha quality review reports.

Deprecated import path; use
``crypto_rsi_scanner.event_alpha.outcomes.quality``.
"""

from __future__ import annotations

from .event_alpha.outcomes import quality as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
