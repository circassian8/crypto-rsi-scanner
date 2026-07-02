"""Compatibility shim for Event Alpha namespace status markers.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.namespace.status``.
"""

from __future__ import annotations

from .event_alpha.namespace import status as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
