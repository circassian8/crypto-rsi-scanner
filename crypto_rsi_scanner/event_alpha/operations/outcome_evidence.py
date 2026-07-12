"""Exact joined outcome evidence loader shared by operating reports."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any, Callable, Mapping

from ..outcomes import outcome_eligibility


RowLoader = Callable[..., list[dict[str, Any]]]


def load_exact_namespace_outcomes(
    base: Path,
    cutoff: Any,
    namespaces: list[str] | tuple[str, ...],
    row_loader: RowLoader,
    evaluated_at: Any,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    """Load candidate/core authority and partition both outcome artifact families."""

    candidates = row_loader(
        base,
        "event_integrated_radar_candidates.jsonl",
        cutoff=cutoff,
        namespaces=namespaces,
    )
    cores = row_loader(
        base,
        "event_core_opportunities.jsonl",
        cutoff=cutoff,
        namespaces=namespaces,
    )
    supplied = [
        *row_loader(
            base,
            "event_integrated_radar_outcomes.jsonl",
            cutoff=cutoff,
            namespaces=namespaces,
        ),
        *row_loader(
            base,
            "event_alpha_outcomes.jsonl",
            cutoff=cutoff,
            namespaces=namespaces,
        ),
    ]
    eligible, excluded, reason_counts = (
        outcome_eligibility.partition_joined_calibration_outcomes(
            supplied,
            candidates,
            cores,
            evaluated_at=evaluated_at,
        )
    )
    return (
        candidates,
        cores,
        supplied,
        list(eligible),
        list(excluded),
        reason_counts,
    )


def telemetry(
    supplied: Collection[Mapping[str, Any]],
    eligible: Collection[Mapping[str, Any]],
    excluded: Collection[Mapping[str, Any]],
    reason_counts: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "outcome_rows_supplied": len(supplied),
        "outcome_rows_eligible": len(eligible),
        "outcome_rows_excluded": len(excluded),
        "outcome_exclusion_reason_counts": dict(reason_counts),
    }


__all__ = ("load_exact_namespace_outcomes", "telemetry")
