"""Public Event Alpha notification pipeline entrypoint.

The behavior-compatible implementation remains in ``pipeline_legacy`` while
notification internals move into smaller modules. Keep this file as a small
compatibility export surface.
"""

from __future__ import annotations

from typing import Any

from . import pipeline_legacy as _legacy


def select_research_review_candidates_with_diagnostics(*args: Any, **kwargs: Any) -> Any:
    return _legacy.select_research_review_candidates_with_diagnostics(*args, **kwargs)


def write_notification_plan_preview(*args: Any, **kwargs: Any) -> Any:
    return _legacy.write_notification_plan_preview(*args, **kwargs)


def send_notifications(*args: Any, **kwargs: Any) -> Any:
    return _legacy.send_notifications(*args, **kwargs)


_OVERRIDES = {
    "select_research_review_candidates_with_diagnostics": select_research_review_candidates_with_diagnostics,
    "write_notification_plan_preview": write_notification_plan_preview,
    "send_notifications": send_notifications,
}

for _name in dir(_legacy):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    if _name in _OVERRIDES:
        continue
    globals()[_name] = getattr(_legacy, _name)

globals().update(_OVERRIDES)

__all__ = tuple(
    sorted(
        {
            *(name for name in dir(_legacy) if not (name.startswith("__") and name.endswith("__"))),
            *_OVERRIDES,
        }
    )
)
