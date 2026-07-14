"""Immutable presentation contract for a turnover-ratio history series."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TurnoverSeriesPresentation:
    """Copied chart values plus the one operator-facing unit/metric contract."""

    rows: tuple[Mapping[str, object], ...]
    title: str
    summary: str
    state_detail: str
    metric_label: str
    unit_label: str
    value_key: str
    value_format: str
    proxy: bool


__all__ = ("TurnoverSeriesPresentation",)
