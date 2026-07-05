"""Public Event Alpha daily-brief entrypoint."""

from __future__ import annotations

from typing import Any

from . import api as _api


def build_daily_brief(*args: Any, **kwargs: Any) -> Any:
    return _api.build_daily_brief(*args, **kwargs)


_OVERRIDES = {"build_daily_brief": build_daily_brief}

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
