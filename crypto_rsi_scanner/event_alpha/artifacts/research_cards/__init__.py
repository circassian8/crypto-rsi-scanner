"""Public research-card artifact entrypoint."""

from __future__ import annotations

from . import legacy as _legacy

for _name in dir(_legacy):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_legacy, _name)

__all__ = tuple(
    name for name in dir(_legacy) if not (name.startswith("__") and name.endswith("__"))
)
