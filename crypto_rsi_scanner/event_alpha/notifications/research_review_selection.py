"""Research-review notification selection helpers."""

from __future__ import annotations

from typing import Any

from . import pipeline_legacy as _legacy


def select_research_review_candidates_with_diagnostics(*args: Any, **kwargs: Any) -> Any:
    return _legacy.select_research_review_candidates_with_diagnostics(*args, **kwargs)


__all__ = ("select_research_review_candidates_with_diagnostics",)
