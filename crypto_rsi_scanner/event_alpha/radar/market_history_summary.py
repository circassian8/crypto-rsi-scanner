"""Canonical summary assembly for rolling market-history evaluations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_market_history_summary(
    *,
    schema_id: str,
    schema_version: int,
    evaluated_at: str,
    config: Mapping[str, Any],
    current_row_count: int,
    historical_row_count: int,
    accepted_current_count: int,
    accepted_historical_count: int,
    current_cadence_counts: Mapping[str, int],
    historical_cadence_counts: Mapping[str, int],
    minimum_observation_spacing_seconds: int,
    rejection_counts: Mapping[str, int],
    rejection_examples: Sequence[Mapping[str, Any]],
    retained: Sequence[Mapping[str, Any]],
    retained_asset_count: int,
    pruned_by_age: int,
    pruned_by_limit: int,
    warmup_status_counts: Mapping[str, int],
    warmup_feature_counts: Mapping[str, Mapping[str, int]],
    warmup_group_counts: Mapping[str, Mapping[str, int]],
    feature_basis_counts: Mapping[str, int],
) -> dict[str, Any]:
    """Build the closed, deterministic market-history telemetry summary."""

    return {
        "schema_id": schema_id,
        "schema_version": schema_version,
        "evaluated_at": evaluated_at,
        "config": dict(config),
        "input_counts": {
            "current_rows": current_row_count,
            "existing_history_rows": historical_row_count,
        },
        "accepted_counts": {
            "current_observations": accepted_current_count,
            "historical_observations": accepted_historical_count,
        },
        "baseline_counting": {
            "current": dict(sorted(current_cadence_counts.items())),
            "history": dict(sorted(historical_cadence_counts.items())),
            "minimum_observation_spacing_seconds": minimum_observation_spacing_seconds,
        },
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "rejection_examples": sorted(
            (dict(item) for item in rejection_examples),
            key=lambda item: (
                str(item.get("role") or ""),
                int(item.get("input_index") or 0),
                str(item.get("reason") or ""),
            ),
        ),
        "retention": {
            "retained_observations": len(retained),
            "retained_assets": retained_asset_count,
            "pruned_by_age": pruned_by_age,
            "pruned_by_limit": pruned_by_limit,
            "oldest_observed_at": min(
                (str(item["observed_at"]) for item in retained),
                default=None,
            ),
            "newest_observed_at": max(
                (str(item["observed_at"]) for item in retained),
                default=None,
            ),
        },
        "warmup": {
            "row_status_counts": dict(sorted(warmup_status_counts.items())),
            "feature_status_counts": {
                feature: dict(sorted(counts.items()))
                for feature, counts in sorted(warmup_feature_counts.items())
            },
            "group_status_counts": {
                group: dict(sorted(counts.items()))
                for group, counts in sorted(warmup_group_counts.items())
            },
        },
        "feature_basis_counts": dict(sorted(feature_basis_counts.items())),
        "research_only": True,
    }
