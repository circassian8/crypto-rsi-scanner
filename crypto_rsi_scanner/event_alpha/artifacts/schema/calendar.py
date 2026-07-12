"""Unified calendar schema specification and semantic checks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

SCHEMA_IDS = ("unified_calendar_event_v1",)

# This is the closed, persisted v1 telemetry contract.  It is mirrored here
# instead of importing the radar package so the artifact schema layer remains
# independent of its producer.
CALENDAR_NORMALIZATION_CONTRACT_VERSION = 1
CALENDAR_NORMALIZATION_DEDUPE_POLICY = "last_valid_row_wins"
CALENDAR_NORMALIZATION_COUNTER_FIELDS = (
    "input_rows",
    "accepted_rows",
    "output_rows",
    "duplicate_overwrite_rows",
    "non_mapping_rows",
    "rejected_rows",
)
CALENDAR_NORMALIZATION_FIELDS = frozenset(
    {
        "contract_version",
        "dedupe_policy",
        *CALENDAR_NORMALIZATION_COUNTER_FIELDS,
        "rejected_reason_counts",
    }
)
CALENDAR_NORMALIZATION_REJECTION_CODES = frozenset(
    {
        "missing_event_id",
        "missing_title",
        "unsupported_event_kind",
        "unsupported_time_certainty",
        "unsupported_importance",
        "unsupported_tracking_status",
        "missing_source",
        "invalid_source_url",
        "invalid_timestamp",
        "exact_missing_scheduled_at",
        "window_missing_bounds",
        "window_end_before_start",
        "invalid_reminder_window",
        "unsafe_research_only",
        "unsafe_no_send_rehearsal",
        "unsafe_side_effect_flag",
        "invalid_side_effect_counter",
        "nonzero_side_effect_counter",
    }
)


def schema_specs(
    schema_factory: Callable[..., Any],
    *,
    operation_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    safety = tuple(dict.fromkeys((
        "research_only", "created_alert", "notification_send_enabled", "execution_enabled",
        "paper_trading_enabled", "normal_rsi_routing_enabled", *operation_safety,
    )))
    return {
        "unified_calendar_event_v1": schema_factory(
            "unified_calendar_event_v1",
            required=(
                "row_type", "calendar_event_id", "title", "event_kind", "time_certainty",
                "importance", "affected_assets", "source", "source_url", "reminder_windows",
                "post_event_tracking_status", "research_only",
            ),
            optional=(
                "schema_id", "schema_version", "scheduled_at", "window_start", "window_end",
                "timezone", "forecast_value", "previous_value", "actual_value", "surprise_value",
                "impact_window_before", "impact_window_after",
                "observed_at", "created_alert", "notification_send_enabled", "execution_enabled",
                "paper_trading_enabled", "normal_rsi_routing_enabled", *operation_safety,
            ),
            types={
                "row_type": "str", "calendar_event_id": "str", "title": "str",
                "event_kind": "str", "time_certainty": "str", "importance": "str",
                "affected_assets": "list", "source": "str", "source_url": "str",
                "reminder_windows": "list", "post_event_tracking_status": "str",
                "timezone": "str", "forecast_value": "float", "previous_value": "float",
                "actual_value": "float", "surprise_value": "float",
                "impact_window_before": "str", "impact_window_after": "str",
                "research_only": "bool",
            },
            enums={
                "event_kind": (
                    "central_bank", "inflation", "employment", "macro_release", "crypto_unlock",
                    "exchange", "project", "protocol", "regulatory",
                    "options_expiry",
                ),
                "time_certainty": ("exact", "window", "estimated", "unknown"),
                "importance": ("low", "medium", "high", "critical"),
                "post_event_tracking_status": (
                    "upcoming", "active_window", "changed", "completed", "canceled",
                    "needs_confirmation",
                ),
            },
            safety=safety,
            timestamps=("scheduled_at", "window_start", "window_end", "observed_at"),
            lineage=common_lineage,
        )
    }


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    certainty = str(row.get("time_certainty") or "")
    scheduled = _timestamp(row.get("scheduled_at"))
    window_start = _timestamp(row.get("window_start"))
    window_end = _timestamp(row.get("window_end"))
    if certainty == "exact" and scheduled is None:
        errors.append("calendar_exact_missing_scheduled_at")
    if certainty == "window" and (window_start is None or window_end is None):
        errors.append("calendar_window_missing_bounds")
    if window_start is not None and window_end is not None and window_end < window_start:
        errors.append("calendar_window_end_before_start")
    parsed_url = urlsplit(str(row.get("source_url") or "").strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        errors.append("calendar_source_url_not_http")
    return errors


def validate_run_ledger_normalization_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate optional closed calendar-normalization telemetry on a run row."""

    if "unified_calendar_normalization" not in row:
        return []
    normalization = row.get("unified_calendar_normalization")
    if not isinstance(normalization, Mapping):
        return ["calendar_normalization_not_mapping"]

    errors: list[str] = []
    actual_fields = set(normalization)
    for field_name in sorted(CALENDAR_NORMALIZATION_FIELDS - actual_fields):
        errors.append(f"calendar_normalization_missing_field:{field_name}")
    if actual_fields - CALENDAR_NORMALIZATION_FIELDS:
        # Do not echo unknown field names: telemetry validation must not turn a
        # raw payload, URL, exception, or secret-shaped key into diagnostics.
        errors.append("calendar_normalization_unknown_field")

    contract_version = normalization.get("contract_version")
    if (
        not _literal_nonnegative_int(contract_version)
        or contract_version != CALENDAR_NORMALIZATION_CONTRACT_VERSION
    ):
        errors.append("calendar_normalization_contract_version_invalid")
    if normalization.get("dedupe_policy") != CALENDAR_NORMALIZATION_DEDUPE_POLICY:
        errors.append("calendar_normalization_dedupe_policy_invalid")

    counters: dict[str, int] = {}
    for field_name in CALENDAR_NORMALIZATION_COUNTER_FIELDS:
        value = normalization.get(field_name)
        if not _literal_nonnegative_int(value):
            errors.append(f"calendar_normalization_counter_invalid:{field_name}")
            continue
        counters[field_name] = value

    reason_counts = normalization.get("rejected_reason_counts")
    reason_total: int | None = None
    if not isinstance(reason_counts, Mapping):
        errors.append("calendar_normalization_rejected_reason_counts_invalid")
    else:
        reason_total = 0
        for reason, value in reason_counts.items():
            if not isinstance(reason, str) or reason not in CALENDAR_NORMALIZATION_REJECTION_CODES:
                errors.append("calendar_normalization_rejected_reason_unknown")
            if not _literal_nonnegative_int(value) or value == 0:
                errors.append("calendar_normalization_rejected_reason_count_invalid")
                continue
            reason_total += value

    if all(
        field_name in counters
        for field_name in ("input_rows", "accepted_rows", "non_mapping_rows", "rejected_rows")
    ) and counters["input_rows"] != (
        counters["accepted_rows"] + counters["non_mapping_rows"] + counters["rejected_rows"]
    ):
        errors.append("calendar_normalization_input_counter_mismatch")
    if all(
        field_name in counters
        for field_name in ("accepted_rows", "output_rows", "duplicate_overwrite_rows")
    ) and counters["accepted_rows"] != (
        counters["output_rows"] + counters["duplicate_overwrite_rows"]
    ):
        errors.append("calendar_normalization_accepted_counter_mismatch")
    if (
        "rejected_rows" in counters
        and reason_total is not None
        and counters["rejected_rows"] != reason_total
    ):
        errors.append("calendar_normalization_rejected_counter_mismatch")

    unified_calendar_rows = row.get("unified_calendar_rows")
    if not _literal_nonnegative_int(unified_calendar_rows):
        errors.append("calendar_normalization_unified_calendar_rows_invalid")
    elif (
        "output_rows" in counters
        and unified_calendar_rows != counters["output_rows"]
    ):
        errors.append("calendar_normalization_output_rows_mismatch")
    return errors


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _literal_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = (
    "CALENDAR_NORMALIZATION_CONTRACT_VERSION",
    "CALENDAR_NORMALIZATION_COUNTER_FIELDS",
    "CALENDAR_NORMALIZATION_DEDUPE_POLICY",
    "CALENDAR_NORMALIZATION_FIELDS",
    "CALENDAR_NORMALIZATION_REJECTION_CODES",
    "SCHEMA_IDS",
    "schema_specs",
    "validate_contract",
    "validate_run_ledger_normalization_contract",
)
