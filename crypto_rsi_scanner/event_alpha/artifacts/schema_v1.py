"""Compatibility aggregator for Event Alpha artifact schema v1."""

from __future__ import annotations

from .schema import registry as _api

for _name in dir(_api):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_api, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))
