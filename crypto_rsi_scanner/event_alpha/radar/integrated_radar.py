"""Public integrated Event Alpha radar entrypoint."""

from __future__ import annotations

from typing import Any

from .integrated import api as _api


def run_integrated_radar_cycle(*args: Any, **kwargs: Any) -> Any:
    return _api.run_integrated_radar_cycle(*args, **kwargs)


_OVERRIDES = {"run_integrated_radar_cycle": run_integrated_radar_cycle}

for _name in dir(_api):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    if _name in _OVERRIDES:
        continue
    globals()[_name] = getattr(_api, _name)

globals().update(_OVERRIDES)

__all__ = tuple(
    sorted(
        {
            *(name for name in dir(_api) if not (name.startswith("__") and name.endswith("__"))),
            *_OVERRIDES,
        }
    )
)
