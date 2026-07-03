"""Notification preview writer compatibility surface."""

from __future__ import annotations

from typing import Any

from . import pipeline_legacy as _legacy


def write_notification_plan_preview(*args: Any, **kwargs: Any) -> Any:
    return _legacy.write_notification_plan_preview(*args, **kwargs)


__all__ = ("write_notification_plan_preview",)
