"""Compatibility shim for Event Alpha DEX/on-chain readiness.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness``.
"""

from __future__ import annotations

from .event_alpha.providers import dex_onchain_readiness as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
