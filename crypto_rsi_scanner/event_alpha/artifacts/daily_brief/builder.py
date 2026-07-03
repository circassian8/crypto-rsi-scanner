"""Daily-brief builder compatibility surface."""

from __future__ import annotations

from typing import Any

from . import legacy as _legacy


def build_daily_brief(*args: Any, **kwargs: Any) -> Any:
    return _legacy.build_daily_brief(*args, **kwargs)


__all__ = ("build_daily_brief",)
