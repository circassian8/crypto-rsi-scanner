"""Bounded-score presentation value."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBand:
    """Human band and tone for a bounded 0-100 score."""

    key: str
    label: str
    tone: str
