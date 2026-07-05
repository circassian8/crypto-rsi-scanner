"""Compatibility exports for the CryptoPanic provider package.

Implementation lives in ``provider.py`` and ``provider_support.py``. This module
keeps historical imports working without defining public provider classes here.
"""

from __future__ import annotations

from . import provider_support as _support
from .provider import CryptoPanicProvider

for _name in dir(_support):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_support, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("__"))
