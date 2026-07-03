"""Coinalyze derivatives provider compatibility surface."""

from __future__ import annotations

from . import legacy as _legacy

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))

