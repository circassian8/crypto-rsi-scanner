"""Compatibility shim for Event Alpha policy simulation.

Deprecated import path; use
``crypto_rsi_scanner.event_alpha.outcomes.policy_simulator``.
"""

from __future__ import annotations

from .event_alpha.outcomes import policy_simulator as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
