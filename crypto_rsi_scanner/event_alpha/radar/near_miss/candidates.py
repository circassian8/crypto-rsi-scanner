"""Near-miss candidate selection helpers."""

from __future__ import annotations

from .legacy import detect_near_miss_rows, is_upgrade_candidate, near_miss_metadata_for_row, split_near_miss_candidates

__all__ = (
    "detect_near_miss_rows",
    "is_upgrade_candidate",
    "near_miss_metadata_for_row",
    "split_near_miss_candidates",
)

