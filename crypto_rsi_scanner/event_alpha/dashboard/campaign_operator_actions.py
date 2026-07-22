"""Bounded campaign-wide operator actions for the read-only dashboard.

The canonical campaign report is historical context, never current-generation
authority.  This loader admits only a small, pointer-matched, zero-side-effect
projection so the dashboard can expose genuine human work without rescanning
the cumulative artifact tree or inspecting process environment variables.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import math
from pathlib import Path
import re
from typing import Any

from ..artifacts.json_lines import loads_no_duplicate_keys
from ..operations import (
    market_no_send_features,
    market_observation_campaign_episode_frontier,
    market_observation_campaign_regime_audit,
    market_observation_campaign_shadow_surprise,
)
from .secure_reader import _DashboardNamespaceReadError, open_anchored_namespace


MAX_CAMPAIGN_REPORT_BYTES = 8 * 1024 * 1024
MAX_REVIEW_RECORDS = 64
MAX_OUTCOME_GAPS = 20
CAMPAIGN_REPORT_JSON_FILENAME = "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"

_REPORT_SCHEMA = "decision_radar_live_observation_campaign_report_v2"
_REPORT_ROW_TYPE = "decision_radar_live_observation_campaign_report"
_QUEUE_SCHEMA = "decision_radar.idea_review_timing_queue_summary"
_QUEUE_COMMAND = "make radar-review-timing-queue PYTHON=.venv/bin/python"
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+|\-]{0,199}$")
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,31}$")
_OUTCOME_READINESS_COMMAND = (
    "make radar-outcome-price-recovery-readiness PYTHON=.venv/bin/python"
)
_BYBIT_READINESS_COMMAND = (
    "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
)
_NEXT_CYCLE_POINT_IN_TIME_BASIS = (
    "same_asset_retained_history_before_future_observation"
)
_BASELINE_FEATURE_GROUPS = (
    "btc_eth_relative",
    "returns_1h",
    "returns_24h",
    "returns_4h",
    "turnover",
    "volatility",
    "volume",
)
_ZERO_REPORT_SAFETY = (
    "normal_rsi_signal_rows_written",
    "paper_trades_created",
    "provider_calls_made_by_report",
    "telegram_sends",
    "trades_created",
    "triggered_fade_created",
)
_ZERO_QUEUE_SAFETY = (
    "authorization_mutations",
    "dashboard_authority_mutations",
    "event_alpha_paper_trades",
    "event_alpha_triggered_fade",
    "normal_rsi_writes",
    "orders",
    "production_policy_mutations",
    "provider_calls",
    "telegram_sends",
    "trades",
)
_CURRENT_REGIME_INPUT_SCHEMA = (
    "decision_radar.current_authority_control_market_regime_input"
)
_CURRENT_REGIME_INPUT_KEYS = {
    "schema_id", "schema_version", "status", "artifact_namespace", "run_id",
    "revision", "operator_state_sha256", "source_artifact",
    "source_artifact_sha256", "source_artifact_size_bytes", "source_row_count",
    "source_binding_source", "source_snapshot_verified", "diagnostic",
    "current_authority_only", "report_replay_only", "retained_history_mutated",
    "historical_context_backfilled", "provider_calls", "writes", "research_only",
}


def load_campaign_operator_actions(
    research_root: str | Path | None,
    *,
    artifact_namespace: str,
    run_id: str,
    revision: int,
    current_market_observations: Sequence[Mapping[str, Any]],
    operator_state_sha256: str | None = None,
) -> dict[str, Any]:
    """Load one safe campaign-action projection without calls or writes."""

    if research_root is None:
        return _unavailable("campaign_report_root_not_configured")
    root = Path(research_root).expanduser()
    try:
        with open_anchored_namespace(root) as reader:
            data, read_error = reader.read_bytes(
                CAMPAIGN_REPORT_JSON_FILENAME,
                max_bytes=MAX_CAMPAIGN_REPORT_BYTES,
            )
    except _DashboardNamespaceReadError:
        return _unavailable("campaign_report_root_unavailable_or_unsafe")
    if read_error == "artifact_missing":
        return _unavailable("campaign_report_missing")
    if read_error == "artifact_too_large":
        return _unavailable("campaign_report_oversized")
    if read_error or data is None:
        return _unavailable("campaign_report_unsafe_or_unreadable")
    try:
        parsed = loads_no_duplicate_keys(data.decode("utf-8"))
        if not isinstance(parsed, Mapping):
            raise ValueError("campaign_report_not_object")
        projection = _project_campaign_actions(
            parsed,
            artifact_namespace=artifact_namespace,
            run_id=run_id,
            revision=revision,
            current_market_observations=current_market_observations,
            operator_state_sha256=operator_state_sha256,
        )
    except (KeyError, TypeError, UnicodeError, ValueError):
        return _unavailable("campaign_report_contract_invalid")
    return {
        **projection,
        "status": "ready",
        "authority": "pointer_matched_campaign_context",
        "report_sha256": hashlib.sha256(data).hexdigest(),
        "report_size_bytes": len(data),
        "maximum_report_size_bytes": MAX_CAMPAIGN_REPORT_BYTES,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _project_campaign_actions(
    report: Mapping[str, Any],
    *,
    artifact_namespace: str,
    run_id: str,
    revision: int,
    current_market_observations: Sequence[Mapping[str, Any]],
    operator_state_sha256: str | None,
) -> dict[str, Any]:
    if (
        report.get("schema_id") != _REPORT_SCHEMA
        or report.get("schema_version") != _REPORT_SCHEMA
        or report.get("row_type") != _REPORT_ROW_TYPE
        or report.get("contract_version") != 2
        or report.get("measurement_program")
        != "decision_radar_live_observation_campaign_v2"
    ):
        raise ValueError("campaign_report_identity_invalid")
    _require_report_safety(report.get("safety"))
    generated_at = _timestamp(report.get("generated_at"), "generated_at")
    pointer = _mapping(report.get("pointer"), "pointer")
    if (
        pointer.get("artifact_namespace") != artifact_namespace
        or pointer.get("run_id") != run_id
        or _count(pointer.get("revision"), "pointer_revision") != revision
        or pointer.get("status") != "authoritative"
        or pointer.get("generation_authority_status") != "authoritative"
        or pointer.get("readiness_validation") != "passed"
        or pointer.get("exact_operator_binding") is not True
        or pointer.get("readiness_error") is not None
    ):
        raise ValueError("campaign_report_pointer_mismatch")
    pointer_checked_at = _timestamp(
        pointer.get("authority_checked_at"), "authority_checked_at"
    )
    if generated_at != pointer_checked_at:
        raise ValueError("campaign_report_terminal_clock_mismatch")

    metrics = _project_metrics(report.get("campaign_metrics"))
    review = _project_review_queue(report.get("human_review_queue"))
    outcomes = _project_outcome_gaps(report.get("outcomes"))
    episode_coverage = _project_episode_coverage(
        report.get("protocol_v2_episode_coverage_frontier"),
        scorecard=report.get("decision_v2_episode_outcome_scorecard"),
    )
    execution = _project_execution_quality(
        report.get("data_quality_limitations"),
        retained_observations=metrics["retained_observation_count"],
        spread_available=metrics["spread_available_count"],
    )
    current_exact_status_counts = _project_current_exact_baseline_counts(
        report.get("authoritative_generations"),
        artifact_namespace=artifact_namespace,
        run_id=run_id,
        loaded_rows=current_market_observations,
    )
    temporal_baseline = _project_temporal_baseline(
        report.get("baseline_maturity"),
        current_exact_status_counts=current_exact_status_counts,
    )
    current_regime_input = _project_current_control_regime_input(
        report.get("authoritative_generations"),
        artifact_namespace=artifact_namespace,
        run_id=run_id,
        revision=revision,
        operator_state_sha256=operator_state_sha256,
        expected_source_row_count=sum(current_exact_status_counts.values()),
    )
    if current_regime_input is not None:
        temporal_baseline["control_market_regime_input"] = current_regime_input
    regime_generation_audit = _project_control_regime_generation_audit(
        report.get("control_market_regime_generation_audit")
    )
    if regime_generation_audit is not None:
        temporal_baseline[
            "control_market_regime_generation_audit"
        ] = regime_generation_audit
    shadow_surprise = _project_shadow_surprise_audit(
        report.get("shadow_temporal_surprise_campaign_audit")
    )
    if metrics["review_timing_action_required"] != review["action_required_count"]:
        raise ValueError("campaign_report_review_count_mismatch")
    if metrics["matured_outcomes"] != outcomes["matured_count"]:
        raise ValueError("campaign_report_matured_outcome_count_mismatch")
    if metrics["pending_outcomes"] != outcomes["pending_count"]:
        raise ValueError("campaign_report_pending_outcome_count_mismatch")
    return {
        "report_generated_at": generated_at,
        "campaign_status": _identity(report.get("campaign_status"), "campaign_status"),
        "campaign_metrics": metrics,
        "human_review": review,
        "outcome_recovery": outcomes,
        "episode_coverage": episode_coverage,
        "shadow_temporal_surprise": shadow_surprise or {},
        "execution_quality": execution,
        "temporal_baseline": temporal_baseline,
        "pointer": {
            "artifact_namespace": artifact_namespace,
            "run_id": run_id,
            "revision": revision,
        },
    }


def _project_shadow_surprise_audit(
    value: Any,
) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    audit = _mapping(value, "shadow_temporal_surprise_campaign_audit")
    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(audit)
    )
    if errors:
        raise ValueError("campaign_shadow_temporal_surprise_invalid")
    feature_coverage = _mapping(
        audit.get("feature_coverage"),
        "shadow_temporal_surprise_feature_coverage",
    )
    if len(feature_coverage) > 16:
        raise ValueError("campaign_shadow_temporal_surprise_features_oversized")
    audit_schema_version = _count(
        audit.get("schema_version"), "shadow_audit_schema_version"
    )
    projected_features = {
        _identity(feature, "shadow_feature_identity"): (
            _project_shadow_surprise_feature(
                feature,
                row,
                distribution_available=audit_schema_version >= 2,
                variation_available=audit_schema_version >= 3,
            )
        )
        for feature, row in sorted(feature_coverage.items())
    }
    raw_asset_variation = audit.get("asset_variation_summaries", [])
    if audit_schema_version >= 4:
        if not isinstance(raw_asset_variation, list) or len(raw_asset_variation) > 128:
            raise ValueError("campaign_shadow_asset_variation_oversized")
        projected_asset_variation = tuple(
            _project_shadow_asset_variation(
                row,
                input_trace_available=audit_schema_version >= 5,
                return_sampling_timing_available=audit_schema_version >= 6,
                return_sampling_overlap_available=audit_schema_version >= 7,
            )
            for row in raw_asset_variation
        )
    else:
        projected_asset_variation = ()
    projection_status_counts = _project_status_counts(
        audit.get("projection_status_counts"),
        label="shadow_projection_status",
    )
    evaluated = _count(
        audit.get("evaluated_observation_count"),
        "shadow_evaluated_observation_count",
    )
    if sum(projection_status_counts.values()) != evaluated:
        raise ValueError("campaign_shadow_projection_status_count_mismatch")
    return {
        "schema_id": _identity(audit.get("schema_id"), "shadow_audit_schema_id"),
        "schema_version": audit_schema_version,
        "status": _identity(audit.get("status"), "shadow_audit_status"),
        "shadow_schema_id": _identity(
            audit.get("shadow_schema_id"), "shadow_source_schema_id"
        ),
        "shadow_schema_version": _count(
            audit.get("shadow_schema_version"), "shadow_source_schema_version"
        ),
        "evaluated_observation_count": evaluated,
        "asset_count": _count(audit.get("asset_count"), "shadow_asset_count"),
        "projection_status_counts": projection_status_counts,
        "feature_coverage": projected_features,
        "distribution_diagnostics_available": audit_schema_version >= 2,
        "variation_diagnostics_available": audit_schema_version >= 3,
        "asset_variation_diagnostics_available": audit_schema_version >= 4,
        "input_trace_diagnostics_available": audit_schema_version >= 5,
        "return_sampling_timing_diagnostics_available": (
            audit_schema_version >= 6
        ),
        "return_sampling_overlap_diagnostics_available": (
            audit_schema_version >= 7
        ),
        "asset_variation_summaries": projected_asset_variation,
        "source_bound_projection_digest": _identity(
            audit.get("source_bound_projection_digest"),
            "shadow_source_bound_digest",
        ),
        "causal_projection_digest": _identity(
            audit.get("causal_projection_digest"),
            "shadow_causal_digest",
        ),
        "all_features_have_ready_evidence": (
            audit.get("all_features_have_ready_evidence") is True
        ),
        "statistical_independence_claimed": False,
        "tail_ranks_are_p_values": False,
        "routing_eligible": False,
        "score_adjustment_eligible": False,
        "threshold_change_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _project_shadow_surprise_feature(
    feature: str,
    value: Any,
    *,
    distribution_available: bool,
    variation_available: bool,
) -> dict[str, Any]:
    row = _mapping(value, "shadow_temporal_surprise_feature")
    result = {
        "feature": _identity(row.get("feature"), "shadow_feature"),
        "family": _identity(row.get("family"), "shadow_feature_family"),
        "evaluated_observation_count": _count(
            row.get("evaluated_observation_count"),
            "shadow_feature_evaluated_count",
        ),
        "ready_count": _count(row.get("ready_count"), "shadow_feature_ready_count"),
        "status_counts": _project_status_counts(
            row.get("status_counts"), label="shadow_feature_status"
        ),
        "minimum_eligible_sample_count": _optional_count(
            row.get("minimum_eligible_sample_count"),
            "shadow_feature_minimum_sample_count",
        ),
        "maximum_eligible_sample_count": _optional_count(
            row.get("maximum_eligible_sample_count"),
            "shadow_feature_maximum_sample_count",
        ),
        "distribution_available": distribution_available,
        "variation_available": variation_available,
    }
    if distribution_available:
        result.update({
            "robust_z_p05": _optional_finite_number(
                row.get("robust_z_p05"), "shadow_feature_robust_z_p05"
            ),
            "robust_z_median": _optional_finite_number(
                row.get("robust_z_median"), "shadow_feature_robust_z_median"
            ),
            "robust_z_p95": _optional_finite_number(
                row.get("robust_z_p95"), "shadow_feature_robust_z_p95"
            ),
            "descriptive_tail_rank_kind": _identity(
                row.get("descriptive_tail_rank_kind"), "shadow_feature_tail_kind"
            ),
            "descriptive_tail_rank_minimum": _optional_finite_number(
                row.get("descriptive_tail_rank_minimum"),
                "shadow_feature_tail_minimum",
            ),
            "descriptive_tail_rank_median": _optional_finite_number(
                row.get("descriptive_tail_rank_median"),
                "shadow_feature_tail_median",
            ),
            "descriptive_tail_rank_p95": _optional_finite_number(
                row.get("descriptive_tail_rank_p95"),
                "shadow_feature_tail_p95",
            ),
            "minimum_tail_observation": _project_shadow_reference(
                row.get("minimum_descriptive_tail_rank_observation"),
                label="shadow_tail_extreme",
            ),
        })
    else:
        result.update({
            "robust_z_p05": None,
            "robust_z_median": None,
            "robust_z_p95": None,
            "descriptive_tail_rank_kind": None,
            "descriptive_tail_rank_minimum": None,
            "descriptive_tail_rank_median": None,
            "descriptive_tail_rank_p95": None,
            "minimum_tail_observation": None,
        })
    if variation_available:
        result.update({
            "variation_observation_count": _count(
                row.get("variation_observation_count"),
                "shadow_feature_variation_observation_count",
            ),
            "distinct_baseline_value_count_minimum": _optional_finite_number(
                row.get("distinct_baseline_value_count_minimum"),
                "shadow_feature_distinct_count_minimum",
            ),
            "distinct_baseline_value_count_median": _optional_finite_number(
                row.get("distinct_baseline_value_count_median"),
                "shadow_feature_distinct_count_median",
            ),
            "distinct_baseline_value_count_maximum": _optional_finite_number(
                row.get("distinct_baseline_value_count_maximum"),
                "shadow_feature_distinct_count_maximum",
            ),
            "distinct_baseline_value_ratio_minimum": _optional_finite_number(
                row.get("distinct_baseline_value_ratio_minimum"),
                "shadow_feature_distinct_ratio_minimum",
            ),
            "distinct_baseline_value_ratio_median": _optional_finite_number(
                row.get("distinct_baseline_value_ratio_median"),
                "shadow_feature_distinct_ratio_median",
            ),
            "distinct_baseline_value_ratio_p95": _optional_finite_number(
                row.get("distinct_baseline_value_ratio_p95"),
                "shadow_feature_distinct_ratio_p95",
            ),
            "distinct_baseline_value_ratio_maximum": _optional_finite_number(
                row.get("distinct_baseline_value_ratio_maximum"),
                "shadow_feature_distinct_ratio_maximum",
            ),
            "maximum_baseline_value_tie_count_maximum": _optional_count(
                row.get("maximum_baseline_value_tie_count_maximum"),
                "shadow_feature_maximum_tie_count",
            ),
            "maximum_baseline_value_tie_ratio_median": _optional_finite_number(
                row.get("maximum_baseline_value_tie_ratio_median"),
                "shadow_feature_maximum_tie_ratio_median",
            ),
            "maximum_baseline_value_tie_ratio_p95": _optional_finite_number(
                row.get("maximum_baseline_value_tie_ratio_p95"),
                "shadow_feature_maximum_tie_ratio_p95",
            ),
            "maximum_baseline_value_tie_ratio_maximum": _optional_finite_number(
                row.get("maximum_baseline_value_tie_ratio_maximum"),
                "shadow_feature_maximum_tie_ratio_maximum",
            ),
            "minimum_distinct_ratio_observation": (
                _project_shadow_variation_reference(
                    row.get(
                        "minimum_distinct_baseline_value_ratio_observation"
                    ),
                    label="shadow_minimum_distinct_ratio",
                )
            ),
            "maximum_tie_ratio_observation": (
                _project_shadow_variation_reference(
                    row.get("maximum_baseline_value_tie_ratio_observation"),
                    label="shadow_maximum_tie_ratio",
                )
            ),
        })
    else:
        result.update({
            "variation_observation_count": 0,
            "distinct_baseline_value_count_minimum": None,
            "distinct_baseline_value_count_median": None,
            "distinct_baseline_value_count_maximum": None,
            "distinct_baseline_value_ratio_minimum": None,
            "distinct_baseline_value_ratio_median": None,
            "distinct_baseline_value_ratio_p95": None,
            "distinct_baseline_value_ratio_maximum": None,
            "maximum_baseline_value_tie_count_maximum": None,
            "maximum_baseline_value_tie_ratio_median": None,
            "maximum_baseline_value_tie_ratio_p95": None,
            "maximum_baseline_value_tie_ratio_maximum": None,
            "minimum_distinct_ratio_observation": None,
            "maximum_tie_ratio_observation": None,
        })
    result.update({
        "tail_ranks_are_p_values": False,
        "overlapping_samples_are_independent": False,
        "variation_diagnostics_are_policy": False,
        "effective_sample_size_claimed": False,
    })
    return result


def _project_shadow_reference(value: Any, *, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    reference = _mapping(value, label)
    return {
        "canonical_asset_id": _identity(
            reference.get("canonical_asset_id"), f"{label}_asset"
        ),
        "observation_id": _identity(
            reference.get("observation_id"), f"{label}_observation"
        ),
        "observed_at": _timestamp(
            reference.get("observed_at"), f"{label}_observed_at"
        ),
    }


def _project_shadow_variation_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    reference = _mapping(value, label)
    return {
        **(_project_shadow_reference(reference, label=label) or {}),
        "sample_count": _count(reference.get("sample_count"), f"{label}_samples"),
        "distinct_baseline_value_count": _count(
            reference.get("distinct_baseline_value_count"),
            f"{label}_distinct_count",
        ),
        "distinct_baseline_value_ratio": _optional_finite_number(
            reference.get("distinct_baseline_value_ratio"),
            f"{label}_distinct_ratio",
        ),
        "maximum_baseline_value_tie_count": _count(
            reference.get("maximum_baseline_value_tie_count"),
            f"{label}_maximum_tie_count",
        ),
        "maximum_baseline_value_tie_ratio": _optional_finite_number(
            reference.get("maximum_baseline_value_tie_ratio"),
            f"{label}_maximum_tie_ratio",
        ),
    }


def _project_shadow_asset_variation(
    value: Any,
    *,
    input_trace_available: bool,
    return_sampling_timing_available: bool,
    return_sampling_overlap_available: bool,
) -> dict[str, Any]:
    row = _mapping(value, "shadow_asset_variation")
    raw_basis = _mapping(
        row.get("retained_feature_basis_counts"),
        "shadow_asset_feature_basis_counts",
    )
    raw_features = _mapping(
        row.get("feature_variation"),
        "shadow_asset_feature_variation",
    )
    if len(raw_features) > 16:
        raise ValueError("shadow_asset_feature_variation_oversized")
    return {
        "canonical_asset_id": _identity(
            row.get("canonical_asset_id"), "shadow_asset_identity"
        ),
        "evaluated_observation_count": _count(
            row.get("evaluated_observation_count"),
            "shadow_asset_evaluated_count",
        ),
        "retained_context_observation_count": _count(
            row.get("retained_context_observation_count"),
            "shadow_asset_context_count",
        ),
        "retained_symbol_counts": _project_context_counts(
            row.get("retained_symbol_counts"),
            label="shadow_asset_symbol",
        ),
        "retained_provider_counts": _project_context_counts(
            row.get("retained_provider_counts"),
            label="shadow_asset_provider",
        ),
        "retained_data_mode_counts": _project_context_counts(
            row.get("retained_data_mode_counts"),
            label="shadow_asset_data_mode",
        ),
        "retained_feature_basis_counts": {
            _identity(feature, "shadow_asset_basis_feature"): (
                _project_context_counts(
                    counts,
                    label="shadow_asset_feature_basis",
                )
            )
            for feature, counts in sorted(raw_basis.items())
        },
        "features_with_repeated_baseline_values": tuple(
            _identity(feature, "shadow_asset_repeated_feature")
            for feature in row.get("features_with_repeated_baseline_values", [])
        ),
        "feature_with_repeated_baseline_value_count": _count(
            row.get("feature_with_repeated_baseline_value_count"),
            "shadow_asset_repeated_feature_count",
        ),
        "feature_variation": {
            _identity(feature, "shadow_asset_feature_identity"): (
                _project_shadow_asset_feature_variation(
                    feature,
                    feature_row,
                    input_trace_available=input_trace_available,
                    return_sampling_timing_available=(
                        return_sampling_timing_available
                    ),
                    return_sampling_overlap_available=(
                        return_sampling_overlap_available
                    ),
                )
            )
            for feature, feature_row in sorted(raw_features.items())
        },
        "source_context_is_causal_attribution": False,
        "routing_eligible": False,
        "score_adjustment_eligible": False,
        "threshold_change_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def _project_shadow_asset_feature_variation(
    feature: str,
    value: Any,
    *,
    input_trace_available: bool = False,
    return_sampling_timing_available: bool = False,
    return_sampling_overlap_available: bool = False,
) -> dict[str, Any]:
    row = _mapping(value, "shadow_asset_feature_variation")
    result = {
        "feature": _identity(row.get("feature"), "shadow_asset_feature"),
        "family": _identity(row.get("family"), "shadow_asset_feature_family"),
        "evaluated_observation_count": _count(
            row.get("evaluated_observation_count"),
            "shadow_asset_feature_evaluated_count",
        ),
        "variation_observation_count": _count(
            row.get("variation_observation_count"),
            "shadow_asset_feature_variation_count",
        ),
        "repeated_baseline_value_observation_count": _count(
            row.get("repeated_baseline_value_observation_count"),
            "shadow_asset_feature_repeated_count",
        ),
        "all_distinct_baseline_value_observation_count": _count(
            row.get("all_distinct_baseline_value_observation_count"),
            "shadow_asset_feature_distinct_count",
        ),
        "descriptive_repetition_observation_share": _optional_finite_number(
            row.get("descriptive_repetition_observation_share"),
            "shadow_asset_feature_repetition_share",
        ),
        "distinct_baseline_value_ratio_minimum": _optional_finite_number(
            row.get("distinct_baseline_value_ratio_minimum"),
            "shadow_asset_feature_distinct_ratio_minimum",
        ),
        "distinct_baseline_value_ratio_median": _optional_finite_number(
            row.get("distinct_baseline_value_ratio_median"),
            "shadow_asset_feature_distinct_ratio_median",
        ),
        "maximum_baseline_value_tie_ratio_median": _optional_finite_number(
            row.get("maximum_baseline_value_tie_ratio_median"),
            "shadow_asset_feature_tie_ratio_median",
        ),
        "maximum_baseline_value_tie_ratio_maximum": _optional_finite_number(
            row.get("maximum_baseline_value_tie_ratio_maximum"),
            "shadow_asset_feature_tie_ratio_maximum",
        ),
        "latest_variation_observation": _project_shadow_variation_reference(
            row.get("latest_variation_observation"),
            label="shadow_asset_feature_latest_variation",
        ),
        "minimum_distinct_ratio_observation": (
            _project_shadow_variation_reference(
                row.get("minimum_distinct_baseline_value_ratio_observation"),
                label="shadow_asset_feature_minimum_distinct",
            )
        ),
        "maximum_tie_ratio_observation": _project_shadow_variation_reference(
            row.get("maximum_baseline_value_tie_ratio_observation"),
            label="shadow_asset_feature_maximum_tie",
        ),
        "variation_diagnostics_are_policy": False,
        "effective_sample_size_claimed": False,
        "overlapping_reference_sets_are_independent": False,
    }
    if input_trace_available:
        result.update({
            "input_trace_observation_count": _count(
                row.get("input_trace_observation_count"),
                "shadow_asset_feature_input_trace_count",
            ),
            "input_trace_status_counts": _project_status_counts(
                row.get("input_trace_status_counts"),
                label="shadow_asset_feature_input_trace_status",
            ),
            "source_tuple_repetition_observation_count": _count(
                row.get("source_tuple_repetition_observation_count"),
                "shadow_asset_feature_source_repetition_count",
            ),
            "transform_collision_observation_count": _count(
                row.get("transform_collision_observation_count"),
                "shadow_asset_feature_transform_collision_count",
            ),
            "mixed_source_and_transform_observation_count": _count(
                row.get("mixed_source_and_transform_observation_count"),
                "shadow_asset_feature_mixed_input_trace_count",
            ),
            "source_value_tuple_kind_counts": _project_status_counts(
                row.get("source_value_tuple_kind_counts"),
                label="shadow_asset_feature_source_tuple_kind",
            ),
            "maximum_source_value_tuple_repeat_excess_count": _count(
                row.get("maximum_source_value_tuple_repeat_excess_count"),
                "shadow_asset_feature_max_source_repeat_excess",
            ),
            "maximum_transform_collision_distinct_value_loss_count": _count(
                row.get(
                    "maximum_transform_collision_distinct_value_loss_count"
                ),
                "shadow_asset_feature_max_transform_collision_loss",
            ),
            "maximum_consecutive_source_value_tuple_count": _count(
                row.get("maximum_consecutive_source_value_tuple_count"),
                "shadow_asset_feature_max_source_run",
            ),
            "maximum_consecutive_derived_value_count": _count(
                row.get("maximum_consecutive_derived_value_count"),
                "shadow_asset_feature_max_derived_run",
            ),
            "latest_input_trace_observation": (
                _project_shadow_input_trace_reference(
                    row.get("latest_input_trace_observation"),
                    label="shadow_asset_feature_latest_input_trace",
                )
            ),
            "input_trace_diagnostics_are_policy": False,
            "provider_causation_claimed": False,
        })
    result["return_sampling_timing_summary"] = (
        _project_shadow_return_sampling_timing_summary(
            row.get("return_sampling_timing_summary"),
            overlap_available=return_sampling_overlap_available,
        )
        if return_sampling_timing_available
        else None
    )
    return result


def _project_shadow_return_sampling_timing_summary(
    value: Any,
    *,
    overlap_available: bool,
) -> dict[str, Any] | None:
    if value is None:
        return None
    summary = _mapping(value, "shadow_return_sampling_timing_summary")
    count_fields = (
        "observation_count",
        "asset_anchor_reuse_observation_count",
        "benchmark_endpoint_reuse_observation_count",
        "benchmark_anchor_reuse_observation_count",
        "nonzero_anchor_selection_error_observation_count",
        "nonzero_benchmark_alignment_lag_observation_count",
        "maximum_asset_anchor_reuse_excess_count",
        "maximum_asset_anchor_reuse_count",
        "maximum_consecutive_asset_anchor_reuse_count",
        "maximum_benchmark_endpoint_reuse_excess_count",
        "maximum_benchmark_endpoint_reuse_count",
        "maximum_consecutive_benchmark_endpoint_reuse_count",
        "maximum_benchmark_anchor_reuse_excess_count",
        "maximum_benchmark_anchor_reuse_count",
        "maximum_consecutive_benchmark_anchor_reuse_count",
    )
    seconds_fields = (
        "maximum_asset_anchor_selection_error_seconds",
        "maximum_benchmark_anchor_selection_error_seconds",
        "maximum_benchmark_endpoint_alignment_lag_seconds",
    )
    reference_fields = (
        "maximum_asset_anchor_reuse_observation",
        "maximum_asset_anchor_selection_error_observation",
        "maximum_benchmark_endpoint_reuse_observation",
        "maximum_benchmark_anchor_reuse_observation",
        "maximum_benchmark_anchor_selection_error_observation",
        "maximum_benchmark_endpoint_alignment_lag_observation",
    )
    result = {
        **{
            field: _count(summary.get(field), f"shadow_sampling_{field}")
            for field in count_fields
        },
        **{
            field: _optional_finite_number(
                summary.get(field), f"shadow_sampling_{field}"
            )
            for field in seconds_fields
        },
        **{
            field: _project_shadow_sampling_observation(
                summary.get(field), label=f"shadow_sampling_{field}"
            )
            for field in reference_fields
        },
        "timing_diagnostics_are_policy": False,
        "provider_causation_claimed": False,
        "statistical_independence_claimed": False,
        "projection_digest": _identity(
            summary.get("projection_digest"),
            "shadow_sampling_projection_digest",
        ),
    }
    if overlap_available:
        result.update({
            "asset_interval_overlap_summary": (
                _project_shadow_interval_overlap_summary(
                    summary.get("asset_interval_overlap_summary"),
                    label="shadow_sampling_asset_interval_overlap",
                )
            ),
            "benchmark_interval_overlap_summary": (
                _project_shadow_interval_overlap_summary(
                    summary.get("benchmark_interval_overlap_summary"),
                    label="shadow_sampling_benchmark_interval_overlap",
                )
                if summary.get("benchmark_interval_overlap_summary") is not None
                else None
            ),
            "overlap_diagnostics_are_policy": False,
            "effective_sample_size_claimed": False,
            "sample_weight_adjustment_applied": False,
        })
    return result


def _project_shadow_interval_overlap_summary(
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    summary = _mapping(value, label)
    count_fields = (
        "observation_count",
        "adjacent_overlap_observation_count",
        "interval_reuse_observation_count",
        "maximum_interval_reuse_excess_count",
        "maximum_interval_reuse_count",
        "maximum_consecutive_interval_reuse_count",
    )
    number_fields = (
        "unique_clock_coverage_ratio_minimum",
        "unique_clock_coverage_ratio_median",
        "unique_clock_coverage_ratio_maximum",
        "maximum_adjacent_overlap_seconds",
        "maximum_overlap_excess_seconds",
    )
    reference_fields = (
        "minimum_unique_clock_coverage_observation",
        "maximum_adjacent_overlap_observation",
        "maximum_overlap_excess_observation",
        "maximum_interval_reuse_observation",
    )
    return {
        **{
            field: _count(summary.get(field), f"{label}_{field}")
            for field in count_fields
        },
        **{
            field: _optional_finite_number(
                summary.get(field), f"{label}_{field}"
            )
            for field in number_fields
        },
        **{
            field: _project_shadow_interval_overlap_observation(
                summary.get(field), label=f"{label}_{field}"
            )
            for field in reference_fields
        },
        "overlap_diagnostics_are_policy": False,
        "effective_sample_size_claimed": False,
        "sample_weight_adjustment_applied": False,
        "statistical_independence_claimed": False,
        "projection_digest": _identity(
            summary.get("projection_digest"), f"{label}_projection_digest"
        ),
    }


def _project_shadow_interval_overlap_observation(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    row = _mapping(value, label)
    count_fields = (
        "sample_count",
        "interval_count",
        "distinct_interval_count",
        "interval_reuse_excess_count",
        "maximum_interval_reuse_count",
        "maximum_consecutive_interval_reuse_count",
        "adjacent_pair_count",
        "adjacent_overlapping_pair_count",
    )
    number_fields = (
        "maximum_adjacent_overlap_seconds",
        "total_interval_seconds",
        "unique_clock_coverage_seconds",
        "overlap_excess_seconds",
        "unique_clock_coverage_ratio",
    )
    return {
        **(_project_shadow_reference(row, label=label) or {}),
        **{
            field: _count(row.get(field), f"{label}_{field}")
            for field in count_fields
        },
        **{
            field: _optional_finite_number(
                row.get(field), f"{label}_{field}"
            )
            for field in number_fields
        },
        "interval_identity_sha256": _identity(
            row.get("interval_identity_sha256"), f"{label}_identity"
        ),
        "maximum_interval_reuse_reference": (
            _project_shadow_interval_reuse_reference(
                row.get("maximum_interval_reuse_reference"),
                label=f"{label}_maximum_interval_reuse_reference",
            )
        ),
        "maximum_adjacent_overlap_reference": (
            _project_shadow_adjacent_overlap_reference(
                row.get("maximum_adjacent_overlap_reference"),
                label=f"{label}_maximum_adjacent_overlap_reference",
            )
        ),
    }


def _project_shadow_interval_reuse_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    row = _mapping(value, label)
    return {
        "interval": _project_shadow_return_interval(
            row.get("interval"), label=f"{label}_interval"
        ),
        "reuse_count": _count(row.get("reuse_count"), f"{label}_reuse_count"),
        "first_asset_endpoint": _project_shadow_observation_reference(
            row.get("first_asset_endpoint"), label=f"{label}_first_endpoint"
        ),
        "last_asset_endpoint": _project_shadow_observation_reference(
            row.get("last_asset_endpoint"), label=f"{label}_last_endpoint"
        ),
    }


def _project_shadow_adjacent_overlap_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    row = _mapping(value, label)
    return {
        "first_asset_endpoint": _project_shadow_observation_reference(
            row.get("first_asset_endpoint"), label=f"{label}_first_endpoint"
        ),
        "second_asset_endpoint": _project_shadow_observation_reference(
            row.get("second_asset_endpoint"), label=f"{label}_second_endpoint"
        ),
        "first_interval": _project_shadow_return_interval(
            row.get("first_interval"), label=f"{label}_first_interval"
        ),
        "second_interval": _project_shadow_return_interval(
            row.get("second_interval"), label=f"{label}_second_interval"
        ),
        "overlap_seconds": _optional_finite_number(
            row.get("overlap_seconds"), f"{label}_overlap_seconds"
        ),
    }


def _project_shadow_return_interval(value: Any, *, label: str) -> dict[str, Any]:
    row = _mapping(value, label)
    return {
        "endpoint": _project_shadow_observation_reference(
            row.get("endpoint"), label=f"{label}_endpoint"
        ),
        "anchor": _project_shadow_observation_reference(
            row.get("anchor"), label=f"{label}_anchor"
        ),
    }


def _project_shadow_observation_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    row = _mapping(value, label)
    return {
        "observation_id": _identity(
            row.get("observation_id"), f"{label}_observation_id"
        ),
        "observed_at": _timestamp(
            row.get("observed_at"), f"{label}_observed_at"
        ),
    }


def _project_shadow_sampling_observation(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    reference = _mapping(value, label)
    result = {
        **(_project_shadow_reference(reference, label=label) or {}),
        "sample_count": _count(reference.get("sample_count"), f"{label}_samples"),
    }
    for field in (
        "reuse_excess_count",
        "maximum_reuse_count",
        "maximum_consecutive_reuse_count",
    ):
        if field in reference:
            result[field] = _count(reference.get(field), f"{label}_{field}")
    if "maximum_seconds" in reference:
        result["maximum_seconds"] = _optional_finite_number(
            reference.get("maximum_seconds"), f"{label}_maximum_seconds"
        )
    return result


def _project_shadow_input_trace_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    reference = _mapping(value, label)
    return {
        **(_project_shadow_reference(reference, label=label) or {}),
        "sample_count": _count(reference.get("sample_count"), f"{label}_samples"),
        "source_value_tuple_kind": _identity(
            reference.get("source_value_tuple_kind"),
            f"{label}_tuple_kind",
        ),
        "source_value_tuple_sha256": _identity(
            reference.get("source_value_tuple_sha256"),
            f"{label}_tuple_digest",
        ),
        "source_value_tuple_count": _count(
            reference.get("source_value_tuple_count"),
            f"{label}_tuple_count",
        ),
        "distinct_source_value_tuple_count": _count(
            reference.get("distinct_source_value_tuple_count"),
            f"{label}_distinct_tuple_count",
        ),
        "maximum_source_value_tuple_tie_count": _count(
            reference.get("maximum_source_value_tuple_tie_count"),
            f"{label}_maximum_tuple_tie",
        ),
        "source_value_tuple_repeat_excess_count": _count(
            reference.get("source_value_tuple_repeat_excess_count"),
            f"{label}_source_repeat_excess",
        ),
        "derived_value_repeat_excess_count": _count(
            reference.get("derived_value_repeat_excess_count"),
            f"{label}_derived_repeat_excess",
        ),
        "transform_collision_distinct_value_loss_count": _count(
            reference.get("transform_collision_distinct_value_loss_count"),
            f"{label}_transform_collision_loss",
        ),
        "maximum_consecutive_source_value_tuple_count": _count(
            reference.get("maximum_consecutive_source_value_tuple_count"),
            f"{label}_maximum_source_run",
        ),
        "maximum_consecutive_derived_value_count": _count(
            reference.get("maximum_consecutive_derived_value_count"),
            f"{label}_maximum_derived_run",
        ),
        "input_trace_status": _identity(
            reference.get("input_trace_status"),
            f"{label}_status",
        ),
    }


def _project_context_counts(value: Any, *, label: str) -> dict[str, int]:
    raw = _mapping(value, label)
    if len(raw) > 64:
        raise ValueError(f"{label}_oversized")
    return {
        _text(identity, 200): _count(count, label)
        for identity, count in sorted(raw.items())
    }


def _project_status_counts(value: Any, *, label: str) -> dict[str, int]:
    raw = _mapping(value, label)
    if len(raw) > 16:
        raise ValueError(f"{label}_oversized")
    return {
        _identity(status, label): _count(count, label)
        for status, count in sorted(raw.items())
    }


def _project_metrics(value: Any) -> dict[str, int]:
    metrics = _mapping(value, "campaign_metrics")
    projected = {
        name: _count(metrics.get(name), name)
        for name in (
            "real_cycles",
            "real_observations",
            "retained_observation_count",
            "baseline_counted_observation_count",
            "baseline_warm_asset_count",
            "historical_ideas",
            "matured_outcomes",
            "pending_outcomes",
            "review_timing_action_required",
            "spread_available_count",
        )
    }
    if projected["baseline_counted_observation_count"] > projected["retained_observation_count"]:
        raise ValueError("campaign_report_baseline_count_invalid")
    if projected["spread_available_count"] > projected["retained_observation_count"]:
        raise ValueError("campaign_report_spread_count_invalid")
    return projected


def _project_episode_coverage(
    value: Any,
    *,
    scorecard: Any,
) -> dict[str, Any]:
    frontier = _mapping(value, "protocol_v2_episode_coverage_frontier")
    source = _mapping(scorecard, "decision_v2_episode_outcome_scorecard")
    errors = (
        market_observation_campaign_episode_frontier
        .validate_protocol_v2_episode_coverage_frontier(
            frontier,
            scorecard=source,
        )
    )
    if errors:
        raise ValueError("campaign_episode_coverage_frontier_invalid")
    routes = _project_episode_coverage_rows(
        frontier.get("route_coverage"),
        expected_names=(
            market_observation_campaign_episode_frontier.CANONICAL_ROUTES
        ),
        label="route",
    )
    origins = _project_episode_coverage_rows(
        frontier.get("primary_origin_coverage"),
        expected_names=(
            market_observation_campaign_episode_frontier
            .CANONICAL_PRIMARY_ORIGINS
        ),
        label="primary_origin",
    )
    unobserved_routes = tuple(
        row["name"] for row in routes if row["episode_count"] == 0
    )
    unobserved_origins = tuple(
        row["name"] for row in origins if row["episode_count"] == 0
    )
    if tuple(frontier.get("unobserved_route_names") or ()) != unobserved_routes:
        raise ValueError("campaign_unobserved_routes_mismatch")
    if (
        tuple(frontier.get("unobserved_primary_origin_names") or ())
        != unobserved_origins
    ):
        raise ValueError("campaign_unobserved_origins_mismatch")
    return {
        "status": _identity(frontier.get("status"), "episode_coverage_status"),
        "episode_count": _count(frontier.get("episode_count"), "episode_count"),
        "repeat_member_count": _count(
            frontier.get("repeat_member_count"), "repeat_member_count"
        ),
        "matured_episode_count": _count(
            frontier.get("matured_episode_count"), "matured_episode_count"
        ),
        "route_population_count": len(routes),
        "observed_route_count": _count(
            frontier.get("observed_route_count"), "observed_route_count"
        ),
        "zero_episode_route_count": len(unobserved_routes),
        "unobserved_route_names": unobserved_routes,
        "route_coverage": routes,
        "primary_origin_population_count": len(origins),
        "observed_primary_origin_count": _count(
            frontier.get("observed_primary_origin_count"),
            "observed_primary_origin_count",
        ),
        "zero_episode_primary_origin_count": len(unobserved_origins),
        "unobserved_primary_origin_names": unobserved_origins,
        "primary_origin_coverage": origins,
        "canonical_category_coverage_complete": (
            frontier.get("canonical_category_coverage_complete") is True
        ),
        "minimum_sample_policy_sealed": False,
        "sample_sufficiency_evaluable": False,
        "statistical_independence_claim": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def _project_episode_coverage_rows(
    value: Any,
    *,
    expected_names: Sequence[str],
    label: str,
) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"campaign_{label}_coverage_invalid")
    if len(value) != len(expected_names):
        raise ValueError(f"campaign_{label}_coverage_count_invalid")
    rows: list[dict[str, Any]] = []
    for index, (raw, expected_name) in enumerate(zip(value, expected_names, strict=True)):
        row = _mapping(raw, f"{label}_coverage_{index}")
        name = _identity(row.get("name"), f"{label}_coverage_name")
        if name != expected_name:
            raise ValueError(f"campaign_{label}_coverage_name_mismatch")
        coverage_status = _identity(
            row.get("coverage_status"), f"{label}_coverage_status"
        )
        projected = {
            "name": name,
            "coverage_status": coverage_status,
            "episode_count": _count(row.get("episode_count"), "episode_count"),
            "matured_episode_count": _count(
                row.get("matured_episode_count"), "matured_episode_count"
            ),
            "due_missing_price_episode_count": _count(
                row.get("due_missing_price_episode_count"),
                "due_missing_price_episode_count",
            ),
            "not_due_episode_count": _count(
                row.get("not_due_episode_count"), "not_due_episode_count"
            ),
            "contract_excluded_episode_count": _count(
                row.get("contract_excluded_episode_count"),
                "contract_excluded_episode_count",
            ),
            "scoreable_directional_episode_count": _count(
                row.get("scoreable_directional_episode_count"),
                "scoreable_directional_episode_count",
            ),
            "aligned_episode_count": _count(
                row.get("aligned_episode_count"), "aligned_episode_count"
            ),
        }
        if coverage_status != (
            "observed" if projected["episode_count"] else "unobserved"
        ):
            raise ValueError(f"campaign_{label}_coverage_status_mismatch")
        rows.append(projected)
    return tuple(rows)


def _project_current_exact_baseline_counts(
    value: Any,
    *,
    artifact_namespace: str,
    run_id: str,
    loaded_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("campaign_authoritative_generations_invalid")
    matches: list[Mapping[str, Any]] = []
    for raw in value:
        row = _mapping(raw, "authoritative_generation")
        publication = _mapping(row.get("publication"), "generation_publication")
        if publication.get("currently_authoritative") is True:
            matches.append(row)
    if len(matches) != 1:
        raise ValueError("campaign_current_generation_count_invalid")
    current = matches[0]
    if (
        current.get("artifact_namespace") != artifact_namespace
        or current.get("run_id") != run_id
    ):
        raise ValueError("campaign_current_generation_identity_invalid")
    quality = _mapping(current.get("data_quality"), "current_generation_data_quality")
    raw_counts = _mapping(
        quality.get("baseline_status_counts"),
        "current_generation_baseline_status_counts",
    )
    if not raw_counts or len(raw_counts) > 16:
        raise ValueError("campaign_current_generation_baseline_counts_invalid")
    projected = {
        _identity(status, "current_generation_baseline_status"): _count(
            count, "current_generation_baseline_count"
        )
        for status, count in sorted(raw_counts.items())
    }
    loaded_counts: Counter[str] = Counter()
    for row in loaded_rows:
        status = str(
            _mapping(row, "loaded_market_observation").get(
                "temporal_baseline_status"
            )
            or "not_evaluated"
        ).strip().casefold()
        loaded_counts[
            _identity(status or "not_evaluated", "loaded_generation_baseline_status")
        ] += 1
    loaded = dict(sorted(loaded_counts.items()))
    if not loaded or projected != loaded:
        raise ValueError("campaign_current_generation_baseline_counts_mismatch")
    return projected


def _project_current_control_regime_input(
    value: Any,
    *,
    artifact_namespace: str,
    run_id: str,
    revision: int,
    operator_state_sha256: str | None,
    expected_source_row_count: int,
) -> dict[str, Any] | None:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("campaign_authoritative_generations_invalid")
    matches = [
        _mapping(raw, "authoritative_generation")
        for raw in value
        if isinstance(raw, Mapping)
        and _mapping(raw.get("publication"), "generation_publication").get(
            "currently_authoritative"
        ) is True
    ]
    if len(matches) != 1:
        raise ValueError("campaign_current_generation_count_invalid")
    raw = matches[0].get("current_authority_control_market_regime_input")
    if raw in (None, {}):
        return None
    projected = _mapping(raw, "current_control_market_regime_input")
    if set(projected) != _CURRENT_REGIME_INPUT_KEYS or any((
        projected.get("schema_id") != _CURRENT_REGIME_INPUT_SCHEMA,
        projected.get("schema_version") != 1,
        projected.get("status") not in {"ready", "incomplete", "unavailable"},
        projected.get("artifact_namespace") != artifact_namespace,
        projected.get("run_id") != run_id,
        projected.get("revision") != revision,
        projected.get("source_artifact")
        != "event_market_no_send_market_rows.json",
        projected.get("source_binding_source")
        != "manifest_request_cache_sha256",
        projected.get("source_snapshot_verified") is not True,
        projected.get("current_authority_only") is not True,
        projected.get("report_replay_only") is not True,
        projected.get("retained_history_mutated") is not False,
        projected.get("historical_context_backfilled") is not False,
        projected.get("provider_calls") != 0,
        projected.get("writes") != 0,
        projected.get("research_only") is not True,
    )):
        raise ValueError("campaign_current_regime_input_invalid")
    if operator_state_sha256 is not None and (
        projected.get("operator_state_sha256") != operator_state_sha256
    ):
        raise ValueError("campaign_current_regime_operator_binding_mismatch")
    digest = projected.get("source_artifact_sha256")
    operator_digest = projected.get("operator_state_sha256")
    source_size = projected.get("source_artifact_size_bytes")
    source_rows = projected.get("source_row_count")
    diagnostic = projected.get("diagnostic")
    if not (
        isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest)
        and isinstance(operator_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", operator_digest)
        and type(source_size) is int
        and source_size > 0
        and type(source_rows) is int
        and source_rows >= 0
        and source_rows == expected_source_row_count
        and market_no_send_features.control_market_regime_input_diagnostic_valid(
            diagnostic
        )
        and diagnostic.get("universe_row_count") == source_rows
        and diagnostic.get("status") == projected.get("status")
    ):
        raise ValueError("campaign_current_regime_input_diagnostic_invalid")
    return {
        "status": projected["status"],
        "source_artifact": projected["source_artifact"],
        "source_artifact_sha256": digest,
        "source_snapshot_verified": True,
        "universe_expected_count": diagnostic["universe_expected_count"],
        "eligible_input_count": diagnostic["eligible_input_count"],
        "missing_input_count": diagnostic["missing_input_count"],
        "missing_inputs": [dict(row) for row in diagnostic["missing_inputs"]],
        "replay_status": diagnostic["replayed_control_market_regime"]["status"],
        "replay_reason": diagnostic["replayed_control_market_regime"]["reason"],
        "replay_regime": diagnostic["replayed_control_market_regime"]["regime"],
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _project_control_regime_generation_audit(
    value: Any,
) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    audit = _mapping(value, "control_market_regime_generation_audit")
    errors = (
        market_observation_campaign_regime_audit
        .validate_control_regime_generation_audit(audit)
    )
    if errors:
        raise ValueError("campaign_control_regime_generation_audit_invalid")
    latest = audit.get("latest_complete_generation")
    latest_projection: dict[str, Any] | None = None
    if isinstance(latest, Mapping):
        membership_context = []
        for index, raw_context in enumerate(
            latest.get("missing_input_membership_context") or ()
        ):
            context = _mapping(
                raw_context,
                f"regime_generation_membership_context_{index}",
            )
            started_at = context.get("continuous_membership_started_at")
            membership_context.append({
                "canonical_asset_id": _identity(
                    context.get("canonical_asset_id"),
                    "regime_generation_membership_asset_id",
                ),
                "membership_start_known": (
                    context.get("membership_start_known") is True
                ),
                "membership_start_basis": _identity(
                    context.get("membership_start_basis"),
                    "regime_generation_membership_start_basis",
                ),
                "continuous_membership_started_at": (
                    _timestamp(
                        started_at,
                        "regime_generation_membership_started_at",
                    )
                    if started_at is not None
                    else None
                ),
                "continuous_membership_age_seconds": (
                    _count(
                        context.get("continuous_membership_age_seconds"),
                        "regime_generation_membership_age_seconds",
                    )
                    if context.get("continuous_membership_age_seconds")
                    is not None
                    else None
                ),
                "within_recent_membership_window": (
                    context.get("within_recent_membership_window") is True
                ),
                "anchor_eligibility_inferred": False,
            })
        latest_projection = {
            "observed_at": _timestamp(
                latest.get("observed_at"),
                "regime_generation_latest_observed_at",
            ),
            "status": _identity(
                latest.get("status"), "regime_generation_latest_status"
            ),
            "eligible_input_count": _count(
                latest.get("eligible_input_count"),
                "regime_generation_latest_eligible_count",
            ),
            "universe_expected_count": _count(
                latest.get("universe_expected_count"),
                "regime_generation_latest_expected_count",
            ),
            "missing_asset_ids": _identity_list(
                latest.get("missing_asset_ids"),
                "regime_generation_latest_missing_assets",
            ),
            "recent_entry_missing_asset_ids": _identity_list(
                latest.get("recent_entry_missing_asset_ids"),
                "regime_generation_latest_recent_missing_assets",
            ),
            "missing_input_membership_context": membership_context,
        }
    missing_counts = _mapping(
        audit.get("missing_asset_generation_counts"),
        "regime_generation_missing_asset_counts",
    )
    projected_missing_counts = {
        _identity(asset_id, "regime_generation_missing_asset_id"): _count(
            count, "regime_generation_missing_asset_count"
        )
        for asset_id, count in sorted(missing_counts.items())
    }
    return {
        "status": _identity(audit.get("status"), "regime_generation_status"),
        "input_generation_count": _count(
            audit.get("input_generation_count"),
            "regime_generation_input_count",
        ),
        "verified_source_generation_count": _count(
            audit.get("verified_source_generation_count"),
            "regime_generation_verified_count",
        ),
        "complete_universe_generation_count": _count(
            audit.get("complete_universe_generation_count"),
            "regime_generation_complete_count",
        ),
        "ready_generation_count": _count(
            audit.get("ready_generation_count"),
            "regime_generation_ready_count",
        ),
        "incomplete_generation_count": _count(
            audit.get("incomplete_generation_count"),
            "regime_generation_incomplete_count",
        ),
        "transition_count": _count(
            audit.get("transition_count"),
            "regime_generation_transition_count",
        ),
        "universe_change_transition_count": _count(
            audit.get("universe_change_transition_count"),
            "regime_generation_change_count",
        ),
        "incomplete_with_recent_entry_count": _count(
            audit.get("incomplete_with_recent_entry_count"),
            "regime_generation_recent_entry_count",
        ),
        "incomplete_without_recent_entry_count": _count(
            audit.get("incomplete_without_recent_entry_count"),
            "regime_generation_without_recent_entry_count",
        ),
        "missing_asset_generation_counts": projected_missing_counts,
        "missing_asset_distinct_count": _count(
            audit.get("missing_asset_distinct_count"),
            "regime_generation_missing_distinct_count",
        ),
        "missing_asset_counts_truncated": (
            audit.get("missing_asset_counts_truncated") is True
        ),
        "latest_complete_generation": latest_projection,
        "interpretation": audit["interpretation"],
        "membership_clock_scope": audit["membership_clock_scope"],
        "precontract_history_used_for_membership_clock": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _project_temporal_baseline(
    value: Any,
    *,
    current_exact_status_counts: Mapping[str, int],
) -> dict[str, Any]:
    maturity = _mapping(value, "baseline_maturity")
    current = _mapping(
        maturity.get("current_universe_maturity"),
        "current_universe_maturity",
    )
    status = _text(current.get("status"), 32)
    if status not in {"cold", "warming", "warm", "incomplete"}:
        raise ValueError("campaign_baseline_status_invalid")
    expected = _count(current.get("expected_asset_count"), "expected_asset_count")
    observed = _count(current.get("observed_asset_count"), "observed_asset_count")
    missing = _count(current.get("missing_asset_count"), "missing_asset_count")
    fully_warm = _count(
        current.get("baseline_warm_asset_count"),
        "baseline_warm_asset_count",
    )
    observed_ids = _identity_list(
        current.get("observed_asset_ids"), "observed_asset_ids"
    )
    missing_ids = _identity_list(
        current.get("missing_asset_ids"), "missing_asset_ids"
    )
    non_warm_ids = _identity_list(
        current.get("non_warm_asset_ids"), "non_warm_asset_ids"
    )
    next_cycle_eligible = _count(
        current.get("next_cycle_point_in_time_eligible_asset_count"),
        "next_cycle_point_in_time_eligible_asset_count",
    )
    raw_next_cycle_at = current.get("next_cycle_point_in_time_eligible_at")
    next_cycle_at = (
        _timestamp(raw_next_cycle_at, "next_cycle_point_in_time_eligible_at")
        if raw_next_cycle_at not in (None, "")
        else None
    )
    raw_global_next_eligible_at = maturity.get("next_eligible_observation_at")
    global_next_eligible_at = (
        _timestamp(raw_global_next_eligible_at, "next_eligible_observation_at")
        if raw_global_next_eligible_at not in (None, "")
        else None
    )
    if (
        observed + missing != expected
        or fully_warm > observed
        or len(observed_ids) != observed
        or len(missing_ids) != missing
        or set(observed_ids) & set(missing_ids)
        or len(set(observed_ids) | set(missing_ids)) != expected
        or not set(non_warm_ids).issubset(observed_ids)
        or len(non_warm_ids) + fully_warm != observed
        or next_cycle_eligible != fully_warm
        or next_cycle_at != global_next_eligible_at
        or sum(current_exact_status_counts.values()) != expected
        or current.get("next_cycle_point_in_time_basis")
        != _NEXT_CYCLE_POINT_IN_TIME_BASIS
    ):
        raise ValueError("campaign_baseline_universe_count_mismatch")
    source_groups = _mapping(
        current.get("baseline_feature_readiness"),
        "baseline_feature_readiness",
    )
    if set(source_groups) != set(_BASELINE_FEATURE_GROUPS):
        raise ValueError("campaign_baseline_feature_groups_invalid")
    groups: dict[str, dict[str, Any]] = {}
    deficit_identity_union: set[str] = set()
    for name in _BASELINE_FEATURE_GROUPS:
        details = _mapping(source_groups.get(name), f"baseline_feature_{name}")
        counts = {
            field: _count(details.get(field), f"{name}_{field}")
            for field in (
                "warm_asset_count",
                "warming_asset_count",
                "cold_asset_count",
                "other_asset_count",
                "asset_count",
            )
        }
        progress = {
            field: _count(details.get(field), f"{name}_{field}")
            for field in (
                "minimum_sample_count",
                "maximum_sample_count",
                "required_sample_count",
                "sample_count_deficit_asset_count",
                "minimum_coverage_seconds",
                "maximum_coverage_seconds",
                "required_coverage_seconds",
                "coverage_deficit_asset_count",
            )
        }
        eligible = _count(
            details.get("next_cycle_point_in_time_eligible_asset_count"),
            f"{name}_next_cycle_point_in_time_eligible_asset_count",
        )
        deficits = _project_feature_deficits(
            details.get("deficit_assets"),
            group=name,
            observed_asset_ids=observed_ids,
            required_sample_count=progress["required_sample_count"],
            required_coverage_seconds=progress["required_coverage_seconds"],
        )
        deficit_identity_union.update(
            row["canonical_asset_id"] for row in deficits
        )
        if (
            counts["asset_count"] != observed
            or sum(counts[field] for field in counts if field != "asset_count")
            != counts["asset_count"]
            or eligible != counts["warm_asset_count"]
            or len(deficits)
            != counts["asset_count"] - counts["warm_asset_count"]
            or sum(row["sample_deficit"] > 0 for row in deficits)
            != progress["sample_count_deficit_asset_count"]
            or sum(row["coverage_deficit_seconds"] > 0 for row in deficits)
            != progress["coverage_deficit_asset_count"]
        ):
            raise ValueError("campaign_baseline_feature_count_mismatch")
        _validate_feature_progress(progress, asset_count=counts["asset_count"])
        groups[name] = counts | progress | {
            "next_cycle_point_in_time_eligible_asset_count": eligible,
            "deficit_assets": deficits,
        }
    if deficit_identity_union != set(non_warm_ids):
        raise ValueError("campaign_baseline_non_warm_identity_mismatch")
    return {
        "status": status,
        "expected_asset_count": expected,
        "observed_asset_count": observed,
        "observed_asset_ids": observed_ids,
        "missing_asset_count": missing,
        "missing_asset_ids": missing_ids,
        "non_warm_asset_ids": non_warm_ids,
        "fully_warm_asset_count": fully_warm,
        "next_cycle_point_in_time_eligible_at": next_cycle_at,
        "next_cycle_point_in_time_eligible_asset_count": next_cycle_eligible,
        "next_cycle_point_in_time_basis": _NEXT_CYCLE_POINT_IN_TIME_BASIS,
        "current_exact_generation_status_counts": dict(
            current_exact_status_counts
        ),
        "feature_groups": groups,
    }


def _project_feature_deficits(
    value: Any,
    *,
    group: str,
    observed_asset_ids: Sequence[str],
    required_sample_count: int,
    required_coverage_seconds: int,
) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("campaign_baseline_feature_deficits_invalid")
    if len(value) > len(observed_asset_ids):
        raise ValueError("campaign_baseline_feature_deficits_oversized")
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        row = _mapping(raw, f"{group}_deficit_{index}")
        asset_id = _identity(
            row.get("canonical_asset_id"), f"{group}_deficit_asset_id"
        )
        status = _identity(row.get("status"), f"{group}_deficit_status")
        sample_count = _count(row.get("sample_count"), f"{group}_sample_count")
        required_samples = _count(
            row.get("required_sample_count"), f"{group}_required_sample_count"
        )
        sample_deficit = _count(
            row.get("sample_deficit"), f"{group}_sample_deficit"
        )
        coverage_seconds = _count(
            row.get("coverage_seconds"), f"{group}_coverage_seconds"
        )
        required_coverage = _count(
            row.get("required_coverage_seconds"),
            f"{group}_required_coverage_seconds",
        )
        coverage_deficit = _count(
            row.get("coverage_deficit_seconds"),
            f"{group}_coverage_deficit_seconds",
        )
        if (
            asset_id not in observed_asset_ids
            or status not in {"warming", "cold", "not_configured"}
            or required_samples != required_sample_count
            or required_coverage != required_coverage_seconds
            or sample_deficit != max(0, required_samples - sample_count)
            or coverage_deficit != max(0, required_coverage - coverage_seconds)
            or (sample_deficit == 0 and coverage_deficit == 0)
        ):
            raise ValueError("campaign_baseline_feature_deficit_invalid")
        rows.append(
            {
                "canonical_asset_id": asset_id,
                "status": status,
                "sample_count": sample_count,
                "required_sample_count": required_samples,
                "sample_deficit": sample_deficit,
                "coverage_seconds": coverage_seconds,
                "required_coverage_seconds": required_coverage,
                "coverage_deficit_seconds": coverage_deficit,
            }
        )
    identities = tuple(row["canonical_asset_id"] for row in rows)
    if identities != tuple(sorted(set(identities))):
        raise ValueError("campaign_baseline_feature_deficit_identity_invalid")
    return tuple(rows)


def _validate_feature_progress(
    progress: Mapping[str, int],
    *,
    asset_count: int,
) -> None:
    if asset_count == 0:
        if any(progress.values()):
            raise ValueError("campaign_baseline_empty_feature_progress_invalid")
        return
    minimum_sample = progress["minimum_sample_count"]
    maximum_sample = progress["maximum_sample_count"]
    required_sample = progress["required_sample_count"]
    sample_deficit = progress["sample_count_deficit_asset_count"]
    minimum_coverage = progress["minimum_coverage_seconds"]
    maximum_coverage = progress["maximum_coverage_seconds"]
    required_coverage = progress["required_coverage_seconds"]
    coverage_deficit = progress["coverage_deficit_asset_count"]
    if (
        minimum_sample > maximum_sample
        or required_sample <= 0
        or sample_deficit > asset_count
        or minimum_coverage > maximum_coverage
        or required_coverage <= 0
        or coverage_deficit > asset_count
    ):
        raise ValueError("campaign_baseline_feature_progress_invalid")
    if (
        (minimum_sample >= required_sample and sample_deficit != 0)
        or (maximum_sample < required_sample and sample_deficit != asset_count)
        or (
            minimum_sample < required_sample <= maximum_sample
            and not 0 < sample_deficit < asset_count
        )
        or (minimum_coverage >= required_coverage and coverage_deficit != 0)
        or (maximum_coverage < required_coverage and coverage_deficit != asset_count)
        or (
            minimum_coverage < required_coverage <= maximum_coverage
            and not 0 < coverage_deficit < asset_count
        )
    ):
        raise ValueError("campaign_baseline_feature_deficit_count_mismatch")


def _project_review_queue(value: Any) -> dict[str, Any]:
    queue = _mapping(value, "human_review_queue")
    if (
        queue.get("schema_id") != _QUEUE_SCHEMA
        or queue.get("schema_version") != 1
        or queue.get("row_type")
        != "decision_radar_idea_review_timing_queue_summary"
        or queue.get("research_only") is not True
        or queue.get("provider_calls") != 0
        or queue.get("writes") != 0
        or queue.get("automatic_policy_effect") != "none"
        or queue.get("dashboard_reads_recorded_as_human_actions") is not False
        or queue.get("commands_require_explicit_confirmation") is not True
        or queue.get("absolute_paths_or_action_commands_embedded") is not False
        or queue.get("operator_queue_command") != _QUEUE_COMMAND
    ):
        raise ValueError("campaign_review_queue_contract_invalid")
    _require_zero_mapping(queue.get("safety"), _ZERO_QUEUE_SAFETY, "queue_safety")
    records = queue.get("records")
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        raise ValueError("campaign_review_records_invalid")
    if len(records) > MAX_REVIEW_RECORDS:
        raise ValueError("campaign_review_records_oversized")
    projected_records = tuple(_project_review_record(row) for row in records)
    counts = {
        name: _count(queue.get(name), name)
        for name in (
            "eligible_idea_count",
            "action_required_count",
            "not_viewed_count",
            "in_review_count",
            "complete_count",
            "skipped_candidate_count",
        )
    }
    if counts["eligible_idea_count"] != len(projected_records):
        raise ValueError("campaign_review_record_count_mismatch")
    if counts["action_required_count"] != counts["not_viewed_count"] + counts["in_review_count"]:
        raise ValueError("campaign_review_action_count_mismatch")
    if counts["eligible_idea_count"] != counts["action_required_count"] + counts["complete_count"]:
        raise ValueError("campaign_review_status_count_mismatch")
    if queue.get("status") not in {"no_eligible_ideas", "action_required", "complete"}:
        raise ValueError("campaign_review_status_invalid")
    return {
        **counts,
        "status": str(queue.get("status")),
        "records": projected_records,
        "next_safe_command": _QUEUE_COMMAND,
        "command_effect": "read_only_queue_preview",
        "dashboard_reads_count_as_review": False,
        "requires_explicit_confirmation_to_record_review": True,
    }


def _project_review_record(value: Any) -> dict[str, Any]:
    row = _mapping(value, "review_record")
    status = _text(row.get("review_status"), 32)
    if status not in {"not_viewed", "in_review", "complete"}:
        raise ValueError("campaign_review_record_status_invalid")
    return {
        "artifact_namespace": _identity(
            row.get("artifact_namespace"), "artifact_namespace"
        ),
        "idea_id": _identity(row.get("idea_id"), "idea_id"),
        "radar_route": _identity(row.get("radar_route"), "radar_route"),
        "review_status": status,
        "idea_available_at": _timestamp(
            row.get("idea_available_at"), "idea_available_at"
        ),
    }


def _project_outcome_gaps(value: Any) -> dict[str, Any]:
    outcomes = _mapping(value, "outcomes")
    due = _count(outcomes.get("due_missing_price"), "due_missing_price")
    details = outcomes.get("due_missing_price_details")
    if isinstance(details, (str, bytes, bytearray)) or not isinstance(details, Sequence):
        raise ValueError("campaign_outcome_gap_details_invalid")
    if len(details) > MAX_OUTCOME_GAPS or len(details) != due:
        raise ValueError("campaign_outcome_gap_count_mismatch")
    symbols: list[str] = []
    for value_row in details:
        row = _mapping(value_row, "outcome_gap")
        if (
            row.get("historical_point_in_time_evidence_required") is not True
            or row.get("interpolation_permitted") is not False
            or row.get("research_only") is not True
            or row.get("automatic_threshold_change_permitted") is not False
        ):
            raise ValueError("campaign_outcome_gap_contract_invalid")
        symbol = _text(row.get("symbol"), 32)
        if symbol and _SYMBOL_RE.fullmatch(symbol) is None:
            raise ValueError("campaign_outcome_gap_symbol_invalid")
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return {
        "due_missing_price_count": due,
        "matured_count": _count(outcomes.get("matured"), "matured"),
        "pending_count": _count(outcomes.get("pending"), "pending"),
        "symbols": tuple(symbols),
        "next_safe_command": _OUTCOME_READINESS_COMMAND,
        "command_effect": "read_only_recovery_readiness",
        "interpolation_permitted": False,
    }


def _project_execution_quality(
    value: Any,
    *,
    retained_observations: int,
    spread_available: int,
) -> dict[str, Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("campaign_limitations_invalid")
    rows = [
        _mapping(row, "data_quality_limitation")
        for row in value[:32]
        if isinstance(row, Mapping)
        and row.get("category") == "execution_quality_spread"
    ]
    if spread_available == retained_observations and not rows:
        return {
            "status": "observed_complete",
            "venue": "bybit",
            "instrument": "usdt_linear_perpetual",
            "spread_available_count": spread_available,
            "retained_observation_count": retained_observations,
            "next_safe_command": None,
            "command_effect": "none",
            "authorization_created": False,
        }
    if len(rows) != 1:
        raise ValueError("campaign_execution_quality_limitation_missing")
    row = rows[0]
    if (
        row.get("provider_selection")
        != "selected_bybit_usdt_linear_perpetuals"
        or row.get("next_safe_command") != _BYBIT_READINESS_COMMAND
        or row.get("evidence_status")
        != "awaiting_authorized_immutable_capture"
    ):
        raise ValueError("campaign_execution_quality_contract_invalid")
    return {
        "status": "awaiting_authorized_immutable_capture",
        "venue": "bybit",
        "instrument": "usdt_linear_perpetual",
        "spread_available_count": spread_available,
        "retained_observation_count": retained_observations,
        "next_safe_command": _BYBIT_READINESS_COMMAND,
        "command_effect": "static_no_network_readiness",
        "authorization_created": False,
    }


def _require_report_safety(value: Any) -> None:
    safety = _mapping(value, "report_safety")
    if (
        safety.get("research_only") is not True
        or safety.get("no_trade_recommendation") is not True
        or safety.get("provider_authorization_modified") is not False
        or safety.get("automatic_route_changes") is not False
        or safety.get("automatic_threshold_changes") is not False
    ):
        raise ValueError("campaign_report_safety_invalid")
    _require_zero_mapping(safety, _ZERO_REPORT_SAFETY, "report_safety")


def _require_zero_mapping(value: Any, fields: Sequence[str], label: str) -> None:
    row = _mapping(value, label)
    if any(row.get(field) != 0 for field in fields):
        raise ValueError(f"{label}_side_effect_invalid")


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "authority": "campaign_context_unavailable",
        "reason": reason,
        "campaign_metrics": {},
        "human_review": {},
        "outcome_recovery": {},
        "episode_coverage": {},
        "execution_quality": {},
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label}_invalid")
    return value


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}_invalid")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError(f"{label}_invalid")
    return int(numeric)


def _optional_count(value: Any, label: str) -> int | None:
    return None if value is None else _count(value, label)


def _optional_finite_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}_invalid")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label}_invalid")
    return result


def _text(value: Any, maximum: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > maximum or any(ord(character) < 32 for character in text):
        raise ValueError("campaign_report_text_invalid")
    return text


def _identity(value: Any, label: str) -> str:
    text = _text(value, 200)
    if _IDENTITY_RE.fullmatch(text) is None:
        raise ValueError(f"{label}_invalid")
    return text


def _identity_list(value: Any, label: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{label}_invalid")
    if len(value) > 64:
        raise ValueError(f"{label}_oversized")
    identities = tuple(_identity(item, label) for item in value)
    if identities != tuple(sorted(set(identities))):
        raise ValueError(f"{label}_invalid")
    return identities


def _timestamp(value: Any, label: str) -> str:
    text = _text(value, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label}_invalid")
    return parsed.isoformat()


__all__ = (
    "MAX_CAMPAIGN_REPORT_BYTES",
    "load_campaign_operator_actions",
)
