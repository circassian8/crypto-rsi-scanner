"""Compatibility shim for Event Alpha live-provider readiness.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.providers.live_provider_readiness``.
"""

from __future__ import annotations

from .event_alpha.providers import live_provider_readiness as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
