"""Public research-card artifact entrypoint."""

from __future__ import annotations

from . import api as _api

for _name in dir(_api):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_api, _name)

__all__ = tuple(
    name for name in dir(_api) if not (name.startswith("__") and name.endswith("__"))
)
