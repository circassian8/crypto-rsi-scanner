"""Pure closed report projection for the Decision Radar campaign."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from . import market_observation_campaign_snapshots


def nonnegative_int(value: object) -> int:
    """Return canonical count evidence; malformed or non-integral values are zero."""

    return value if type(value) is int and value >= 0 else 0


def build_report_value(
    *,
    schema_id: str,
    measurement_program: str,
    generated_at: str,
    status: str,
    metrics: Mapping[str, Any],
    baseline: Mapping[str, Any],
    authoritative: Sequence[Mapping[str, Any]],
    non_authoritative: Sequence[Mapping[str, Any]],
    provider_failed: Sequence[Mapping[str, Any]],
    blocked: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
    valid_generation_count: int,
    pointer: Mapping[str, Any],
    pointer_history: Sequence[Mapping[str, Any]],
    outcome_metrics: Mapping[str, Any],
    review_timing: Mapping[str, Any],
    episode_shadow: Mapping[str, Any],
    episode_input_audit: Mapping[str, Any],
    episode_scorecard: Mapping[str, Any],
    episode_coverage_frontier: Mapping[str, Any],
    shadow_surprise_audit: Mapping[str, Any],
    limitations: Sequence[Mapping[str, Any]],
    next_observation: Mapping[str, Any],
    conclusion: Mapping[str, Any],
    review_queue: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the schema-closed campaign report without reading or writing."""

    return {
        "contract_version": 2,
        "schema_id": schema_id,
        "schema_version": schema_id,
        "row_type": "decision_radar_live_observation_campaign_report",
        "measurement_program": measurement_program,
        "generated_at": generated_at,
        "campaign_status": status,
        "measurement_scope": {
            "decision_radar_live_observation_campaign": "included",
            "event_alpha_catalyst_burn_in": "separate_not_aggregated",
            "historical_market_provenance_v2_adapter": "read_only",
            "historical_rows_rewritten": False,
        },
        "campaign_metrics": dict(metrics),
        "baseline_maturity": dict(baseline),
        "authoritative_generations": (
            market_observation_campaign_snapshots.public_generation_rows(
                authoritative
            )
        ),
        "non_authoritative_complete_generations": (
            market_observation_campaign_snapshots.public_generation_rows(
                non_authoritative
            )
        ),
        "provider_failed_attempts": list(provider_failed),
        "blocked_or_preflight_attempts": list(blocked),
        "excluded_invalid_generations": (
            market_observation_campaign_snapshots.public_generation_rows(excluded)
        ),
        "generation_validation": {
            "valid_generation_count": valid_generation_count,
            "excluded_generation_count": len(excluded),
            "exclusion_reason_counts": dict(
                sorted(
                    Counter(
                        reason
                        for row in excluded
                        for reason in row.get("validation_errors", ())
                    ).items()
                )
            ),
        },
        "pointer": dict(pointer),
        "pointer_history": list(pointer_history),
        "outcomes": dict(outcome_metrics),
        "human_review_timing": dict(review_timing),
        "human_review_queue": dict(review_queue or {}),
        "shadow_anomaly_episodes": dict(episode_shadow),
        "shadow_anomaly_episode_input_audit": dict(episode_input_audit),
        "decision_v2_episode_outcome_scorecard": dict(episode_scorecard),
        "protocol_v2_episode_coverage_frontier": dict(
            episode_coverage_frontier
        ),
        "shadow_temporal_surprise_campaign_audit": dict(
            shadow_surprise_audit
        ),
        "data_quality_limitations": list(limitations),
        "next_observation": dict(next_observation),
        "campaign_v2_conclusion": dict(conclusion),
        "safety": {
            "research_only": True,
            "no_trade_recommendation": True,
            "provider_calls_made_by_report": 0,
            "provider_authorization_modified": False,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
            "automatic_threshold_changes": False,
            "automatic_route_changes": False,
        },
    }


__all__ = ("build_report_value", "nonnegative_int")
