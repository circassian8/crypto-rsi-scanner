"""Compatibility shim for Event Alpha Coinalyze preflight.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight``.
"""

from __future__ import annotations

from .event_alpha.providers import coinalyze_preflight as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
