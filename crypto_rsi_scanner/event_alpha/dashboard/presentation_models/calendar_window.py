"""Calendar-window presentation value."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarWindowPresentation:
    """A calendar label that never claims more timing certainty than supplied."""

    available: bool
    label: str
    certainty_label: str
    relative_label: str
    utc_label: str
