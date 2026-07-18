"""Bounded read-only projection of live/no-send campaign evidence for the lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys


SCHEMA_ID = "decision_radar.empirical_live_campaign_projection"
LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = (LEGACY_SCHEMA_VERSION, SCHEMA_VERSION)
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


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


__all__ = [
    "LEGACY_SCHEMA_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "load_live_campaign_projection",
    "project_live_campaign",
]
