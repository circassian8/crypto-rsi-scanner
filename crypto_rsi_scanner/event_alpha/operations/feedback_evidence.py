"""Exact joined human-feedback evidence shared by operating reports."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any, Callable, Mapping

from ..outcomes import feedback_eligibility


RowLoader = Callable[..., list[dict[str, Any]]]


def load_exact_namespace_feedback(
    base: Path,
    cutoff: Any,
    namespaces: list[str] | tuple[str, ...],
    row_loader: RowLoader,
    evaluated_at: Any,
    *,
    core_rows: Collection[Mapping[str, Any]] | None = None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    """Load feedback and retain only exact, latest, Core-authorized labels."""

    cores = (
        [dict(row) for row in core_rows]
        if core_rows is not None
        else row_loader(
            base,
            "event_core_opportunities.jsonl",
            cutoff=cutoff,
            namespaces=namespaces,
        )
    )
    supplied = row_loader(
        base,
        "event_alpha_feedback.jsonl",
        cutoff=cutoff,
        namespaces=namespaces,
    )
    eligible, excluded, reason_counts = (
        feedback_eligibility.partition_joined_calibration_feedback(
            supplied,
            cores,
            now=evaluated_at,
        )
    )
    return supplied, list(eligible), list(excluded), reason_counts


def telemetry(
    supplied: Collection[Mapping[str, Any]],
    eligible: Collection[Mapping[str, Any]],
    excluded: Collection[Mapping[str, Any]],
    reason_counts: Mapping[str, int],
) -> dict[str, Any]:
    """Return the one feedback denominator contract used by all operations."""

    return {
        "feedback_rows_supplied": len(supplied),
        "feedback_rows_eligible": len(eligible),
        "feedback_rows_excluded": len(excluded),
        "feedback_exclusion_reason_counts": dict(reason_counts),
    }


__all__ = ("load_exact_namespace_feedback", "telemetry")
