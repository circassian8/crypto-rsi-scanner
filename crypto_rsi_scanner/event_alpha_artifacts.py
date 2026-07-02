"""Compatibility shim for Event Alpha artifact context helpers.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.artifacts.context``.
"""

from __future__ import annotations

from .event_alpha.artifacts import context as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
