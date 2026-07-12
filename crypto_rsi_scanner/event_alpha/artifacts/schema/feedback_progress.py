"""Typed schema and semantic checks for feedback-progress artifacts."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any


SCHEMA_ID = "event_alpha_feedback_progress_v1"
ROW_TYPE = "event_alpha_feedback_progress"
SCHEMA_VERSION = "event_alpha_feedback_progress_v1"

COUNTER_FIELDS = (
    "labels_today",
    "labels_this_week",
    "labels_total",
    "unlabeled_review_items",
    "feedback_rows_supplied",
    "feedback_rows_eligible",
    "feedback_rows_excluded",
)
BREAKDOWN_FIELDS = (
    "labels_by_type",
    "labels_by_opportunity_type",
    "labels_by_source_pack",
    "labels_by_provider",
    "labels_by_candidate_family",
)
SAFETY_FIELDS = (
    "research_only",
    "no_send_rehearsal",
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)


def schema_specs(
    schema_factory: Callable[..., Any],
    *,
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    """Return the closed typed schema for one feedback-progress document."""

    required = (
        "schema_version",
        "row_type",
        "generated_at",
        "profile",
        "artifact_namespace",
        "namespace_dir",
        "window_days",
        *COUNTER_FIELDS,
        "label_coverage_pct",
        *SAFETY_FIELDS,
    )
    field_types = {
        "schema_version": "str",
        "row_type": "str",
        "generated_at": "str",
        "profile": "str",
        "artifact_namespace": "str",
        "namespace_dir": "str",
        "window_days": "int",
        **{field: "int" for field in COUNTER_FIELDS},
        **{field: "dict" for field in BREAKDOWN_FIELDS},
        "feedback_exclusion_reason_counts": "dict",
        "label_coverage_pct": "float",
        "stale_unresolved_feedback_targets": "list",
        "research_only": "bool",
        "no_send_rehearsal": "bool",
        **{field: "int" for field in SAFETY_FIELDS[2:]},
    }
    return {
        SCHEMA_ID: schema_factory(
            SCHEMA_ID,
            required=required,
            optional=(
                "schema_id",
                *BREAKDOWN_FIELDS,
                "feedback_exclusion_reason_counts",
                "stale_unresolved_feedback_targets",
            ),
            types=field_types,
            safety=SAFETY_FIELDS,
            timestamps=("generated_at",),
            lineage=common_lineage,
        )
    }


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate feedback denominators, clocks, summaries, and no-send posture."""

    errors: list[str] = []
    if row.get("schema_version") != SCHEMA_VERSION:
        errors.append("feedback_progress_schema_version_invalid")
    if row.get("row_type") != ROW_TYPE:
        errors.append("feedback_progress_row_type_invalid")
    if _aware_timestamp(row.get("generated_at")) is None:
        errors.append("feedback_progress_generated_at_invalid")
    if not _positive_int(row.get("window_days")):
        errors.append("feedback_progress_window_days_invalid")

    counters = {field: _nonnegative_int(row.get(field)) for field in COUNTER_FIELDS}
    for field, value in counters.items():
        if value is None:
            errors.append(f"feedback_progress_counter_invalid:{field}")
    supplied = counters["feedback_rows_supplied"]
    eligible = counters["feedback_rows_eligible"]
    excluded = counters["feedback_rows_excluded"]
    if None not in (supplied, eligible, excluded) and supplied != eligible + excluded:
        errors.append("feedback_progress_denominator_mismatch")
    labels_total = counters["labels_total"]
    if labels_total is not None and eligible is not None and labels_total != eligible:
        errors.append("feedback_progress_labels_total_mismatch")
    today = counters["labels_today"]
    this_week = counters["labels_this_week"]
    if (
        None not in (today, this_week, labels_total)
        and not today <= this_week <= labels_total
    ):
        errors.append("feedback_progress_window_count_mismatch")

    for field in BREAKDOWN_FIELDS:
        total = _count_mapping_total(row.get(field))
        if total is None:
            errors.append(f"feedback_progress_breakdown_invalid:{field}")
        elif labels_total is not None and total != labels_total:
            errors.append(f"feedback_progress_breakdown_total_mismatch:{field}")
    exclusion_total = _count_mapping_total(row.get("feedback_exclusion_reason_counts"))
    if exclusion_total is None:
        errors.append("feedback_progress_exclusion_reasons_invalid")
    elif excluded is not None and (
        (excluded == 0 and exclusion_total != 0)
        or (excluded > 0 and exclusion_total < excluded)
    ):
        errors.append("feedback_progress_exclusion_reasons_mismatch")

    coverage = row.get("label_coverage_pct")
    if (
        not isinstance(coverage, (int, float))
        or isinstance(coverage, bool)
        or not math.isfinite(float(coverage))
        or not 0.0 <= float(coverage) <= 100.0
    ):
        errors.append("feedback_progress_label_coverage_invalid")
    stale_targets = row.get("stale_unresolved_feedback_targets")
    if (
        not isinstance(stale_targets, list)
        or any(not isinstance(item, str) or not item.strip() for item in stale_targets)
        or len(stale_targets) != len(set(stale_targets))
    ):
        errors.append("feedback_progress_stale_targets_invalid")
    if row.get("research_only") is not True:
        errors.append("feedback_progress_not_research_only")
    if row.get("no_send_rehearsal") is not True:
        errors.append("feedback_progress_not_no_send")
    return list(dict.fromkeys(errors))


def _aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        text = value.strip()
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _nonnegative_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value


def _positive_int(value: object) -> bool:
    parsed = _nonnegative_int(value)
    return parsed is not None and parsed > 0


def _count_mapping_total(value: object) -> int | None:
    if not isinstance(value, Mapping):
        return None
    total = 0
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip():
            return None
        parsed = _nonnegative_int(count)
        if parsed is None:
            return None
        total += parsed
    return total


__all__ = (
    "BREAKDOWN_FIELDS",
    "COUNTER_FIELDS",
    "ROW_TYPE",
    "SAFETY_FIELDS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "schema_specs",
    "validate_contract",
)
