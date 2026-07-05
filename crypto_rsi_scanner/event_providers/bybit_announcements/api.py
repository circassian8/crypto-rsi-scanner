"""Compatibility exports for the Bybit announcement provider package."""

from __future__ import annotations

from . import provider_support as _support
from .provider import BybitAnnouncementProvider

for _name in dir(_support):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_support, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("__"))
