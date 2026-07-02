"""Compatibility shim for Event Alpha notification SLO reports.

Deprecated import path; use
``crypto_rsi_scanner.event_alpha.notifications.slo``.
"""

from __future__ import annotations

from .event_alpha.notifications import slo as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
