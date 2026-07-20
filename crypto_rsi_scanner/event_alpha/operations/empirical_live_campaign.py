"""Bounded read-only projection of live/no-send campaign evidence for the lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys
from . import market_observation_campaign_shadow_surprise


SCHEMA_ID = "decision_radar.empirical_live_campaign_projection"
LEGACY_SCHEMA_VERSION = 1
PRIOR_SCHEMA_VERSION = 2
SCHEMA_VERSION = 3
SUPPORTED_SCHEMA_VERSIONS = (
    LEGACY_SCHEMA_VERSION,
    PRIOR_SCHEMA_VERSION,
    SCHEMA_VERSION,
)
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_REPRESENTATIVES = 128
_METRIC_FIELDS = (
    "real_cycles",
    "real_observations",
    "retained_observation_count",
    "baseline_counted_observation_count",
    "too_close_observation_count",
    "baseline_warm_asset_count",
    "real_candidates",
    "historical_ideas",
    "current_ideas",
    "matured_outcomes",
    "pending_outcomes",
    "spread_available_count",
    "spread_coverage_ratio",
    "direct_feature_count",
    "proxy_feature_count",
)
_REVIEW_SAFETY_FIELDS = frozenset({
    "provider_calls",
    "authorization_mutations",
    "telegram_sends",
    "trades",
    "orders",
    "event_alpha_paper_trades",
    "normal_rsi_writes",
    "event_alpha_triggered_fade",
    "dashboard_authority_mutations",
    "production_policy_mutations",
})


def load_live_campaign_projection(path: str | Path) -> dict[str, Any]:
    """Read one explicit report; never inspect env, providers, or pointers."""

    supplied = Path(path).expanduser()
    if supplied.is_symlink() or not supplied.is_file():
        raise ValueError("live campaign report path invalid")
    if supplied.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("live campaign report too large")
    try:
        value = loads_no_duplicate_keys(supplied.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("live campaign report unreadable") from exc
    if not isinstance(value, Mapping):
        raise ValueError("live campaign report invalid")
    return project_live_campaign(value)


def project_live_campaign(report: Mapping[str, Any]) -> dict[str, Any]:
    """Keep live evidence separate and strip authority/provider internals."""

    if report.get("schema_id") != "decision_radar_live_observation_campaign_report_v2":
        raise ValueError("live campaign schema invalid")
    safety = report.get("safety")
    if not isinstance(safety, Mapping):
        raise ValueError("live campaign safety missing")
    expected_zero = (
        "normal_rsi_signal_rows_written",
        "paper_trades_created",
        "provider_calls_made_by_report",
        "telegram_sends",
        "trades_created",
        "triggered_fade_created",
    )
    if safety.get("research_only") is not True or any(safety.get(field) != 0 for field in expected_zero):
        raise ValueError("live campaign safety invalid")
    if safety.get("provider_authorization_modified") is not False:
        raise ValueError("live campaign authorization mutation invalid")
    metrics = _mapping(report.get("campaign_metrics"))
    episodes = _mapping(report.get("shadow_anomaly_episodes"))
    if (
        episodes.get("statistical_independence_claim") is not False
        or episodes.get("cross_asset_independence_claim") is not False
    ):
        raise ValueError("live campaign episode independence claim invalid")
    scorecard = _mapping(report.get("decision_v2_episode_outcome_scorecard"))
    outcomes = _mapping(report.get("outcomes"))
    representatives = [
        _representative(row)
        for row in list(scorecard.get("representatives") or [])[:MAX_REPRESENTATIVES]
        if isinstance(row, Mapping)
    ]
    primary_episode_count = _integer(episodes.get("primary_episode_count"))
    matured = _integer(scorecard.get("matured_episode_count"))
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "evidence_mode": "live_no_send",
        "source_schema_id": report["schema_id"],
        "source_generated_at": str(report.get("generated_at") or ""),
        "campaign_status": str(report.get("campaign_status") or "unknown"),
        "campaign_metrics": {field: metrics.get(field) for field in _METRIC_FIELDS},
        "route_counts": _bounded_counts(metrics.get("route_counts")),
        "episodes": {
            "status": str(episodes.get("status") or "unavailable"),
            "method": str(episodes.get("method") or "unknown"),
            "primary_episode_count": primary_episode_count,
            "repeat_member_count": _integer(episodes.get("primary_repeat_member_count")),
            "sensitivity_counts": _mapping(episodes.get("sensitivity_counts")),
            "representative_count": len(representatives),
            "representatives": representatives,
            "representatives_truncated": _integer(scorecard.get("representative_count")) > len(representatives),
            "statistical_independence_claim": False,
            "cross_asset_independence_claim": False,
        },
        "outcomes": {
            "total": _integer(outcomes.get("total")),
            "matured": _integer(outcomes.get("matured")),
            "pending": _integer(outcomes.get("pending")),
            "due_missing_price": _integer(outcomes.get("due_missing_price")),
            "status_counts": _bounded_counts(outcomes.get("status_counts")),
        },
        "scorecard": {
            "status": str(scorecard.get("status") or "unavailable"),
            "primary_episode_count": _integer(scorecard.get("primary_episode_count")),
            "matured_episode_count": matured,
            "scoreable_directional_episode_count": _integer(scorecard.get("scoreable_directional_episode_count")),
            "policy_conclusion": str(scorecard.get("policy_conclusion") or "insufficient_for_policy_change"),
            "policy_conclusion_reasons": _bounded_strings(scorecard.get("policy_conclusion_reasons")),
            "matched_control_available": scorecard.get("matched_control_available") is True,
            "out_of_sample_validation_available": scorecard.get("out_of_sample_validation_available") is True,
            "exclusive_cohorts": _cohort_projection(scorecard.get("exclusive_cohorts")),
            "origin_cohorts": _cohort_rows(scorecard.get("nonexclusive_thesis_origin_cohorts")),
        },
        "shadow_temporal_surprise": _shadow_temporal_surprise_projection(report),
        "human_review": _human_review_projection(report),
        "limitations": _limitations(report.get("data_quality_limitations")),
        "evidence_strength": "insufficient_sample" if matured < 5 else "descriptive_only",
        "replay_evidence_aggregated": False,
        "fixture_evidence_aggregated": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "provider_calls": 0,
        "writes": 0,
        "authorization_mutations": 0,
        "dashboard_authority_mutations": 0,
    }


def _shadow_temporal_surprise_projection(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    value = report.get("shadow_temporal_surprise_campaign_audit")
    if value is None:
        return {
            "available": False,
            "status": "not_available_in_source_report",
            "feature_coverage": {},
            "all_features_have_ready_evidence": False,
            "statistical_independence_claimed": False,
            "protocol_v2_evidence_eligible": False,
            "policy_eligible": False,
            "provider_calls": 0,
            "writes": 0,
        }
    if not isinstance(value, Mapping):
        raise ValueError("live campaign shadow temporal surprise invalid")
    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(value)
    )
    if errors:
        raise ValueError("live campaign shadow temporal surprise invalid")
    source = _mapping(value.get("source_history"))
    coverage = _mapping(value.get("feature_coverage"))
    return {
        "available": True,
        "status": str(value.get("status") or "unavailable"),
        "source_history": {
            "status": str(source.get("status") or "unavailable"),
            "artifact": str(source.get("artifact") or ""),
            "sha256": str(source.get("sha256") or ""),
            "size_bytes": _integer(source.get("size_bytes")),
            "row_count": _integer(source.get("row_count")),
            "binding_source": str(source.get("binding_source") or ""),
        },
        "shadow_schema_id": str(value.get("shadow_schema_id") or ""),
        "shadow_schema_version": _integer(value.get("shadow_schema_version")),
        "minimum_sample_count": _integer(value.get("minimum_sample_count")),
        "input_row_count": _integer(value.get("input_row_count")),
        "excluded_not_baseline_counted_count": _integer(
            value.get("excluded_not_baseline_counted_count")
        ),
        "input_rejected_count": _integer(value.get("input_rejected_count")),
        "valid_baseline_counted_row_count": _integer(
            value.get("valid_baseline_counted_row_count")
        ),
        "evaluated_observation_count": _integer(
            value.get("evaluated_observation_count")
        ),
        "evaluation_error_count": _integer(value.get("evaluation_error_count")),
        "asset_count": _integer(value.get("asset_count")),
        "projection_status_counts": _bounded_counts(
            value.get("projection_status_counts")
        ),
        "return_status_counts": _bounded_counts(value.get("return_status_counts")),
        "feature_coverage": {
            str(feature): _shadow_feature_projection(row)
            for feature, row in sorted(coverage.items())
            if isinstance(row, Mapping)
        },
        "source_bound_projection_digest": str(
            value.get("source_bound_projection_digest") or ""
        ),
        "causal_projection_digest": str(value.get("causal_projection_digest") or ""),
        "all_features_have_ready_evidence": (
            value.get("all_features_have_ready_evidence") is True
        ),
        "statistical_independence_claimed": False,
        "routing_eligible": False,
        "priority_eligible": False,
        "score_adjustment_eligible": False,
        "decision_score_eligible": False,
        "threshold_change_eligible": False,
        "publication_authority": False,
        "protocol_v2_evidence_eligible": False,
        "policy_eligible": False,
        "auto_apply": False,
        "historical_rows_rewritten": False,
        "provider_calls": 0,
        "writes": 0,
    }


def _shadow_feature_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "feature": str(row.get("feature") or ""),
        "family": str(row.get("family") or "unknown"),
        "evaluated_observation_count": _integer(
            row.get("evaluated_observation_count")
        ),
        "ready_count": _integer(row.get("ready_count")),
        "status_counts": _bounded_counts(row.get("status_counts")),
        "minimum_sample_count": _integer(row.get("minimum_sample_count")),
        "minimum_eligible_sample_count": _optional_integer(
            row.get("minimum_eligible_sample_count")
        ),
        "maximum_eligible_sample_count": _optional_integer(
            row.get("maximum_eligible_sample_count")
        ),
        "projection_digest": str(row.get("projection_digest") or ""),
    }


def _human_review_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    timing = report.get("human_review_timing")
    queue = report.get("human_review_queue")
    if timing is None and queue is None:
        return {
            "available": False,
            "status": "not_available_in_source_report",
            "latency_evidence_status": "unavailable_source_report_compatibility",
            "completed_latency_sample_count": 0,
            "dashboard_reads_recorded_as_human_actions": False,
            "protocol_v2_evidence_eligible": False,
            "policy_eligible": False,
            "provider_calls": 0,
            "writes": 0,
        }
    if not isinstance(timing, Mapping) or not isinstance(queue, Mapping):
        raise ValueError("live campaign human review invalid")
    _validate_human_review_sources(timing, queue)
    eligible = _strict_integer(queue, "eligible_idea_count")
    completed = _strict_integer(timing, "completed_review_record_count")
    first_views = _strict_integer(timing, "first_view_record_count")
    latency_status = (
        "observed_descriptive"
        if completed
        else "incomplete_no_completed_reviews"
        if first_views
        else "unavailable_no_explicit_human_actions"
        if eligible
        else "unavailable_no_eligible_ideas"
    )
    return {
        "available": True,
        "status": str(queue.get("status") or "unknown"),
        "timing_status": str(timing.get("status") or "unknown"),
        "eligible_generation_count": _strict_integer(
            queue, "eligible_generation_count"
        ),
        "eligible_idea_count": eligible,
        "action_required_count": _strict_integer(queue, "action_required_count"),
        "not_viewed_count": _strict_integer(queue, "not_viewed_count"),
        "in_review_count": _strict_integer(queue, "in_review_count"),
        "queue_complete_count": _strict_integer(queue, "complete_count"),
        "skipped_candidate_count": _strict_integer(
            queue, "skipped_candidate_count"
        ),
        "ledger_event_count": _strict_integer(timing, "ledger_event_count"),
        "idea_record_count": _strict_integer(timing, "idea_record_count"),
        "first_view_record_count": first_views,
        "completed_review_record_count": completed,
        "incomplete_review_record_count": _strict_integer(
            timing, "incomplete_review_record_count"
        ),
        "events_after_evaluated_at_count": _strict_integer(
            timing, "events_after_evaluated_at_count"
        ),
        "latency_evidence_status": latency_status,
        "completed_latency_sample_count": completed,
        "latency_seconds_definition": str(
            timing.get("latency_seconds_definition") or ""
        ),
        "explicit_human_actions_only": True,
        "dashboard_reads_recorded_as_human_actions": False,
        "commands_require_explicit_confirmation": True,
        "protocol_v2_evidence_eligible": False,
        "policy_eligible": False,
        "automatic_policy_effect": "none",
        "provider_calls": 0,
        "writes": 0,
    }


def _validate_human_review_sources(
    timing: Mapping[str, Any], queue: Mapping[str, Any]
) -> None:
    if (
        timing.get("schema_id") != "decision_radar.idea_review_timing_report"
        or timing.get("schema_version") != 1
        or queue.get("schema_id")
        != "decision_radar.idea_review_timing_queue_summary"
        or queue.get("schema_version") != 1
        or timing.get("research_only") is not True
        or queue.get("research_only") is not True
        or timing.get("dashboard_reads_recorded_as_human_actions") is not False
        or queue.get("dashboard_reads_recorded_as_human_actions") is not False
        or queue.get("commands_require_explicit_confirmation") is not True
        or queue.get("absolute_paths_or_action_commands_embedded") is not False
        or timing.get("protocol_v2_evidence_eligible") is not False
        or queue.get("protocol_v2_evidence_eligible") is not False
        or timing.get("automatic_policy_effect") != "none"
        or queue.get("automatic_policy_effect") != "none"
        or timing.get("provider_calls") != 0
        or queue.get("provider_calls") != 0
        or queue.get("writes") != 0
        or timing.get("generated_at") != queue.get("generated_at")
        or not _zero_safety(timing.get("safety"))
        or not _zero_safety(queue.get("safety"))
    ):
        raise ValueError("live campaign human review invalid")
    queue_counts = {
        field: _strict_integer(queue, field)
        for field in (
            "eligible_idea_count",
            "action_required_count",
            "not_viewed_count",
            "in_review_count",
            "complete_count",
        )
    }
    timing_counts = {
        field: _strict_integer(timing, field)
        for field in (
            "ledger_event_count",
            "events_in_window_count",
            "events_after_evaluated_at_count",
            "idea_record_count",
            "first_view_record_count",
            "completed_review_record_count",
            "incomplete_review_record_count",
        )
    }
    queue_record_counts = _review_status_counts(
        queue.get("records"),
        expected_count=queue_counts["eligible_idea_count"],
    )
    timing_record_counts = _review_status_counts(
        timing.get("records"),
        expected_count=timing_counts["idea_record_count"],
    )
    expected_queue_status = (
        "no_eligible_ideas"
        if queue_counts["eligible_idea_count"] == 0
        else "action_required"
        if queue_counts["action_required_count"]
        else "complete"
    )
    expected_timing_status = (
        "no_events"
        if timing_counts["idea_record_count"] == 0
        else "complete"
        if timing_counts["completed_review_record_count"]
        == timing_counts["idea_record_count"]
        else "in_progress"
    )
    if (
        queue_counts["not_viewed_count"]
        + queue_counts["in_review_count"]
        + queue_counts["complete_count"]
        != queue_counts["eligible_idea_count"]
        or queue_counts["not_viewed_count"]
        + queue_counts["in_review_count"]
        != queue_counts["action_required_count"]
        or timing_counts["completed_review_record_count"]
        + timing_counts["incomplete_review_record_count"]
        != timing_counts["idea_record_count"]
        or timing_counts["completed_review_record_count"]
        > timing_counts["first_view_record_count"]
        or timing_counts["first_view_record_count"]
        > timing_counts["idea_record_count"]
        or timing_counts["events_in_window_count"]
        + timing_counts["events_after_evaluated_at_count"]
        != timing_counts["ledger_event_count"]
        or _strict_integer(queue, "events_in_window_count")
        != timing_counts["events_in_window_count"]
        or _strict_integer(queue, "events_after_evaluated_at_count")
        != timing_counts["events_after_evaluated_at_count"]
        or queue_record_counts["not_viewed"] != queue_counts["not_viewed_count"]
        or queue_record_counts["in_review"] != queue_counts["in_review_count"]
        or queue_record_counts["complete"] != queue_counts["complete_count"]
        or timing_record_counts["complete"]
        != timing_counts["completed_review_record_count"]
        or timing_record_counts["not_viewed"] + timing_record_counts["in_review"]
        != timing_counts["incomplete_review_record_count"]
        or queue.get("status") != expected_queue_status
        or timing.get("status") != expected_timing_status
    ):
        raise ValueError("live campaign human review invalid")


def _strict_integer(value: Mapping[str, Any], field: str) -> int:
    item = value.get(field)
    if type(item) is not int or item < 0:
        raise ValueError("live campaign human review invalid")
    return item


def _zero_safety(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value) == _REVIEW_SAFETY_FIELDS and all(
        type(item) is int and item == 0 for item in value.values()
    )


def _review_status_counts(value: Any, *, expected_count: int) -> dict[str, int]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise ValueError("live campaign human review invalid")
    counts = {"not_viewed": 0, "in_review": 0, "complete": 0}
    identities: set[tuple[str, str]] = set()
    for row in value:
        if not isinstance(row, Mapping):
            raise ValueError("live campaign human review invalid")
        status = row.get("review_status")
        first = row.get("first_operator_viewed_at")
        complete = row.get("review_completed_at")
        identity = (
            str(row.get("artifact_namespace") or ""),
            str(row.get("idea_id") or ""),
        )
        if (
            status not in counts
            or not all(identity)
            or identity in identities
            or (status == "not_viewed" and (first is not None or complete is not None))
            or (
                status == "in_review"
                and (not isinstance(first, str) or not first or complete is not None)
            )
            or (
                status == "complete"
                and (
                    not isinstance(first, str)
                    or not first
                    or not isinstance(complete, str)
                    or not complete
                )
            )
        ):
            raise ValueError("live campaign human review invalid")
        identities.add(identity)
        counts[str(status)] += 1
    return counts


def _representative(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": str(row.get("episode_id") or ""),
        "canonical_asset_id": str(row.get("canonical_asset_id") or ""),
        "observed_at": str(row.get("observed_at") or ""),
        "radar_route": str(row.get("radar_route") or "diagnostic"),
        "primary_thesis_origin": str(row.get("primary_thesis_origin") or "unknown"),
        "directional_bias": str(row.get("directional_bias") or "neutral"),
        "catalyst_status": str(row.get("catalyst_status") or "unknown"),
        "market_phase": str(row.get("market_phase") or "unknown"),
        "actionability_score": _number(row.get("actionability_score")),
        "evidence_confidence_score": _number(row.get("evidence_confidence_score")),
        "risk_score": _number(row.get("risk_score")),
        "outcome_state": str(row.get("outcome_state") or "unknown"),
        "primary_horizon": str(row.get("primary_horizon") or "unknown"),
        "primary_horizon_return": _number(row.get("primary_horizon_return")),
        "direction_alignment": str(row.get("direction_alignment") or "not_evaluated"),
    }


def _cohort_projection(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(name): _cohort_rows(rows)
        for name, rows in list(sorted(value.items()))[:32]
    }


def _cohort_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for row in value[:64]:
        if not isinstance(row, Mapping):
            continue
        rows.append({
            "name": str(row.get("name") or "unknown"),
            "episode_count": _integer(row.get("episode_count")),
            "matured_episode_count": _integer(row.get("matured_episode_count")),
            "mean_primary_horizon_return": _number(row.get("mean_primary_horizon_return")),
            "median_primary_horizon_return": _number(row.get("median_primary_horizon_return")),
            "alignment_rate": _number(row.get("alignment_rate")),
        })
    return rows


def _limitations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"category": str(row.get("category") or "unknown"), "detail": str(row.get("detail") or "")[:1024]}
        for row in value[:32]
        if isinstance(row, Mapping)
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bounded_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _integer(item) for key, item in list(sorted(value.items()))[:64]}


def _bounded_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:256] for item in value[:64]]


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _optional_integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


__all__ = [
    "LEGACY_SCHEMA_VERSION",
    "PRIOR_SCHEMA_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "load_live_campaign_projection",
    "project_live_campaign",
]
