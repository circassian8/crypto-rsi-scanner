"""Compatibility shim for Event Alpha calibration reports.

Deprecated import path; use
``crypto_rsi_scanner.event_alpha.outcomes.calibration``.
"""

from __future__ import annotations

from .event_alpha.outcomes import calibration as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
