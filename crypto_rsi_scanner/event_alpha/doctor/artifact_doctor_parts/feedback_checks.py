"""Feedback eligibility telemetry for the Event Alpha artifact doctor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ...outcomes import feedback_eligibility

_DUPLICATE_REASONS = {
    "duplicate_feedback_id",
    "duplicate_feedback_row",
    "ambiguous_feedback_timestamp",
}
_FUTURE_REASONS = {
    "feedback_marked_in_future",
    "core_authority_generated_in_future",
}
_UNSAFE_REASONS = {
    "core_authority_safety_contract_invalid",
    "feedback_before_core_generation",
    "feedback_safety_contract_invalid",
    "invalid_feedback_notes",
    "invalid_feedback_source",
    "non_research_feedback",
}
_MISSING_CORE_REASONS = {
    "missing_core_authority",
}
_AMBIGUOUS_CORE_REASONS = {
    "ambiguous_core_authority",
    "core_authority_identity_mismatch",
    "duplicate_core_authority",
    "invalid_core_authority_attribution",
    "invalid_core_authority_contract",
}
_EXPECTED_EFFECTIVE_ONLY_REASONS = {"superseded_feedback"}


def summarize_feedback_eligibility(
    feedback_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: datetime | None = None,
    jsonl_diagnostics: Any = None,
) -> dict[str, Any]:
    """Return deterministic, payload-free feedback firewall counters."""

    now = evaluated_at or datetime.now(timezone.utc)
    supplied = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    eligible, excluded, reason_counts = (
        feedback_eligibility.partition_joined_calibration_feedback(
            supplied,
            cores,
            now=now,
        )
    )
    excluded_rows = list(excluded)
    contract_invalid = sum(
        1
        for row in supplied
        if feedback_eligibility.has_feedback_eligibility_marker(row)
        and feedback_eligibility.validate_contract(row)
    )
    persisted_true = sum(
        1 for row in supplied if row.get("calibration_eligible") is True
    )
    expected_effective_only = sum(
        1
        for row in excluded_rows
        if set(row.get("calibration_ineligible_reasons") or ())
        and not (
            set(row.get("calibration_ineligible_reasons") or ())
            - _EXPECTED_EFFECTIVE_ONLY_REASONS
        )
    )
    persisted_eligible_invalid = max(
        0,
        persisted_true - len(eligible) - expected_effective_only,
    )
    diagnostics = jsonl_diagnostics
    return {
        "feedback_rows_supplied": len(supplied),
        "feedback_rows_eligible": len(eligible),
        "feedback_rows_excluded": len(excluded_rows),
        "feedback_exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "feedback_eligibility_contract_invalid": contract_invalid,
        "feedback_persisted_eligible_invalid": persisted_eligible_invalid,
        "feedback_legacy_rows": sum(
            1
            for row in supplied
            if not feedback_eligibility.has_feedback_eligibility_marker(row)
        ),
        "feedback_duplicate_rows": _rows_with_reasons(excluded_rows, _DUPLICATE_REASONS),
        "feedback_future_rows": _rows_with_reasons(excluded_rows, _FUTURE_REASONS),
        "feedback_unsafe_rows": _rows_with_reasons(excluded_rows, _UNSAFE_REASONS),
        "feedback_missing_core_rows": _rows_with_reasons(
            excluded_rows,
            _MISSING_CORE_REASONS,
        ),
        "feedback_ambiguous_core_rows": _rows_with_reasons(
            excluded_rows,
            _AMBIGUOUS_CORE_REASONS,
        ),
        "feedback_superseded_rows": _rows_with_reasons(
            excluded_rows,
            {"superseded_feedback"},
        ),
        "feedback_duplicate_json_keys": (
            len(diagnostics.duplicate_key_lines) if diagnostics is not None else 0
        ),
        "feedback_invalid_jsonl": (
            len(diagnostics.invalid_json_lines) + len(diagnostics.non_object_lines)
            if diagnostics is not None
            else 0
        ),
        "feedback_jsonl_read_errors": (
            1 if diagnostics is not None and diagnostics.read_error else 0
        ),
    }


def _rows_with_reasons(
    rows: Iterable[Mapping[str, Any]],
    wanted: set[str],
) -> int:
    return sum(
        1
        for row in rows
        if wanted & set(row.get("calibration_ineligible_reasons") or ())
    )


__all__ = ("summarize_feedback_eligibility",)
