"""CryptoPanic provider compatibility surface."""

from __future__ import annotations

from . import api as _api

for _name in dir(_api):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_api, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))

