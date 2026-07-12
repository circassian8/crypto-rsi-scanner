"""Nested contract for the burn-in dashboard's current evidence window."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any


CURRENT_WINDOW_FIELDS = frozenset(
    {
        "source",
        "window_days",
        "window_start",
        "window_end",
        "included_namespace_count",
        "real_burn_in_candidate_count",
        "non_burn_in_candidate_count",
        "feedback_rows_eligible",
        "outcome_rows_eligible",
        "near_miss_count",
        "quality_capped_count",
        "interpretation",
    }
)
_COUNTER_FIELDS = CURRENT_WINDOW_FIELDS - {
    "source",
    "window_start",
    "window_end",
    "interpretation",
}
_COUNT_AUTHORITIES = {
    "window_days": "window_days",
    "included_namespace_count": "included_namespace_count",
    "real_burn_in_candidate_count": "real_burn_in_candidate_count",
    "non_burn_in_candidate_count": "non_burn_in_candidate_count",
    "feedback_rows_eligible": "feedback_rows_eligible",
    "outcome_rows_eligible": "outcome_rows_eligible",
    "near_miss_count": "near_miss_count",
    "quality_capped_count": "quality_capped_count",
}


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate the closed, descriptive current-window summary when present."""

    if "current_window_interpretation" not in row:
        return []
    window = row.get("current_window_interpretation")
    if not isinstance(window, Mapping):
        return []  # The registry's top-level type check owns this diagnostic.

    errors: list[str] = []
    actual_fields = set(window)
    if CURRENT_WINDOW_FIELDS - actual_fields:
        errors.append("measurement_current_window_missing_field")
    if actual_fields - CURRENT_WINDOW_FIELDS:
        errors.append("measurement_current_window_unknown_field")
    for field_name in _COUNTER_FIELDS:
        value = window.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"measurement_current_window_invalid_counter:{field_name}")
    for field_name in ("source", "interpretation"):
        if not isinstance(window.get(field_name), str) or not str(window.get(field_name)).strip():
            errors.append(f"measurement_current_window_invalid_text:{field_name}")
    if window.get("source") != "selected_filtered_namespaces":
        errors.append("measurement_current_window_invalid_source")
    if not isinstance(row.get("low_sample_warning"), bool):
        errors.append("measurement_current_window_invalid_low_sample_warning")
    for nested_field, authority_field in _COUNT_AUTHORITIES.items():
        if window.get(nested_field) != row.get(authority_field):
            errors.append(
                f"measurement_current_window_authority_mismatch:{nested_field}"
            )
    start = _aware_timestamp(window.get("window_start"))
    end = _aware_timestamp(window.get("window_end"))
    generated_at = _aware_timestamp(row.get("generated_at"))
    if start is None:
        errors.append("measurement_current_window_invalid_timestamp:window_start")
    if end is None:
        errors.append("measurement_current_window_invalid_timestamp:window_end")
    if start is not None and end is not None and start > end:
        errors.append("measurement_current_window_reversed_bounds")
    if end is not None and generated_at != end:
        errors.append("measurement_current_window_end_mismatch")
    window_days = window.get("window_days")
    if (
        start is not None
        and end is not None
        and isinstance(window_days, int)
        and not isinstance(window_days, bool)
        and start != end - timedelta(days=window_days)
    ):
        errors.append("measurement_current_window_start_mismatch")
    expected_interpretation = (
        "insufficient exact current-window evidence for threshold changes"
        if row.get("low_sample_warning")
        else "descriptive current-window evidence; thresholds remain review-only"
    )
    if window.get("interpretation") != expected_interpretation:
        errors.append("measurement_current_window_interpretation_mismatch")
    return errors


def _aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        text = value.strip()
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


__all__ = ("CURRENT_WINDOW_FIELDS", "validate_contract")
