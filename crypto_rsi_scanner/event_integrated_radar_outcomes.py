"""Compatibility shim for integrated Event Alpha radar outcomes.

Deprecated import path; use
``crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes``.
"""

from __future__ import annotations

from .event_alpha.outcomes import integrated_radar_outcomes as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
