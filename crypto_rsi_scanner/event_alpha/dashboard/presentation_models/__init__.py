"""Small presentation value objects used by dashboard formatting helpers.

Each public value object owns one module so the dashboard keeps the repository's
class-ownership contract without weakening its stable presentation imports.
"""

from .calendar_window import CalendarWindowPresentation
from .score_band import ScoreBand
from .semantic_status import SemanticStatus
from .time import TimePresentation
from .turnover_series import TurnoverSeriesPresentation


__all__ = (
    "CalendarWindowPresentation",
    "ScoreBand",
    "SemanticStatus",
    "TimePresentation",
    "TurnoverSeriesPresentation",
)
