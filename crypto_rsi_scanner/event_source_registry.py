"""Compatibility shim for Event Alpha source registry.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.providers.source_registry``.
"""

from __future__ import annotations

from .event_alpha.providers import source_registry as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
