"""Compatibility shim for Event Alpha Bybit announcement preflight.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight``.
"""

from __future__ import annotations

from .event_alpha.providers import bybit_announcements_preflight as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
