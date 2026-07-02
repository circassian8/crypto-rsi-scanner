"""Compatibility shim for Event Alpha market anomaly scanning.

Deprecated import path; use ``crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner``.
"""

from __future__ import annotations

from .event_alpha.radar import market_anomaly_scanner as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
__all__ = [name for name in dir(_impl) if not name.startswith("_")]
