"""Compatibility shim for Event Alpha run ledgers.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.artifacts.run_ledger``.
"""

from __future__ import annotations

from .event_alpha.artifacts import run_ledger as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
