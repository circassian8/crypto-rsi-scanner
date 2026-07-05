"""Public Event Alpha notification pipeline entrypoint.

The behavior-compatible implementation remains in ``pipeline_core`` while
notification internals move into smaller modules. Keep this file as a small
compatibility export surface.
"""

from __future__ import annotations

from typing import Any

from . import pipeline_core as _api


def select_research_review_candidates_with_diagnostics(*args: Any, **kwargs: Any) -> Any:
    return _api.select_research_review_candidates_with_diagnostics(*args, **kwargs)


def write_notification_plan_preview(*args: Any, **kwargs: Any) -> Any:
    return _api.write_notification_plan_preview(*args, **kwargs)


def send_notifications(*args: Any, **kwargs: Any) -> Any:
    return _api.send_notifications(*args, **kwargs)


_OVERRIDES = {
    "select_research_review_candidates_with_diagnostics": select_research_review_candidates_with_diagnostics,
    "write_notification_plan_preview": write_notification_plan_preview,
    "send_notifications": send_notifications,
}

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
