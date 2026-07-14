"""Semantic-status presentation value."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticStatus:
    """Human label plus a small, closed semantic color vocabulary."""

    token: str
    label: str
    tone: str
