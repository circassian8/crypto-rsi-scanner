"""Models helpers for legacy daily brief."""

from __future__ import annotations

from .runtime import *

@dataclass(frozen=True)
class EventAlphaDailyBriefResult:
    path: Path
    markdown: str
    cards: tuple[Path, ...] = ()

__all__ = (
    'EventAlphaDailyBriefResult',
)
