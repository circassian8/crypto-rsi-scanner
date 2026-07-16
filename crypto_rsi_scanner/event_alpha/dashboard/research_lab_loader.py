"""Bounded, read-only loading for the Decision Radar Research Lab.

Research evidence is deliberately independent of the authoritative dashboard
generation.  Only four fixed report names are inspected, every buffer is read
once through a descriptor-anchored directory, and failures degrade the lab
surface without changing production authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys
from ..operations.empirical_live_campaign import project_live_campaign
from .secure_reader import _DashboardNamespaceReadError, open_anchored_namespace


VALIDATION_REPORT = "DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json"
WALK_FORWARD_REPORT = "DECISION_RADAR_WALK_FORWARD_REPORT.json"
POLICY_REPORT = "DECISION_RADAR_POLICY_SIMULATION_REPORT.json"
LIVE_CAMPAIGN_REPORT = "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"

ROUTES = (
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
    "diagnostic",
)
ORIGINS = (
    "market_led",
    "catalyst_led",
    "technical_led",
    "derivatives_led",
    "onchain_led",
    "fundamental_led",
    "macro_led",
)

_REPORT_FILES = {
    "validation": (VALIDATION_REPORT, 8 * 1024 * 1024),
    "walk_forward": (WALK_FORWARD_REPORT, 4 * 1024 * 1024),
    "policy": (POLICY_REPORT, 4 * 1024 * 1024),
    "live_campaign": (LIVE_CAMPAIGN_REPORT, 2 * 1024 * 1024),
}
_VALIDATION_SCHEMA = "decision_radar.empirical_validation_report"
_ANALYSIS_SCHEMA = "decision_radar.empirical_replay_analysis"
_WALK_SCHEMA = "decision_radar.empirical_walk_forward"
_POLICY_REPORT_SCHEMA = "decision_radar.empirical_policy_report"
_POLICY_SIMULATION_SCHEMA = "decision_radar.empirical_policy_simulation"
_ZERO_SIDE_EFFECT_FIELDS = (
    "normal_rsi_signal_rows_written",
    "paper_trades_created",
    "provider_calls",
    "provider_calls_made_by_report",
    "telegram_sends",
    "trades_created",
    "triggered_fade_created",
    "writes",
)


def load_research_lab_snapshot(research_root: str | Path | None) -> dict[str, Any]:
    """Return one closed Research Lab read model; never raise for bad evidence."""

    if research_root is None:
        return _unavailable_snapshot("research_root_not_configured")
    root = Path(research_root).expanduser()
    records: dict[str, dict[str, Any]] = {}
    try:
        with open_anchored_namespace(root) as reader:
            for key, (filename, maximum) in _REPORT_FILES.items():
                records[key] = _read_report(reader, key, filename, maximum)
    except _DashboardNamespaceReadError:
        return _unavailable_snapshot(
            "research_root_unavailable_or_unsafe",
            report_status="unavailable",
        )

    ready_count = sum(record.get("status") == "ready" for record in records.values())
    status = "ready" if ready_count == len(_REPORT_FILES) else "partial" if ready_count else "unavailable"
    warnings = [
        f"{record['filename']}:{record['status']}"
        for record in records.values()
        if record.get("status") != "ready"
    ]
    return {
        "status": status,
        "reports": records,
        "warnings": tuple(warnings),
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
        "dashboard_authority_mutations": 0,
        "provider_calls": 0,
        "writes": 0,
    }


def _unavailable_snapshot(
    reason: str,
    *,
    report_status: str = "not_configured",
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reports": {
            key: {
                "filename": filename,
                "status": report_status,
                "sha256": None,
                "size_bytes": None,
                "projection": {},
            }
            for key, (filename, _maximum) in _REPORT_FILES.items()
        },
        "warnings": (reason,),
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
        "dashboard_authority_mutations": 0,
        "provider_calls": 0,
        "writes": 0,
    }


def _read_report(reader: Any, key: str, filename: str, maximum: int) -> dict[str, Any]:
    data, read_error = reader.read_bytes(filename, max_bytes=maximum)
    base = {
        "filename": filename,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "size_bytes": len(data) if data is not None else None,
        "projection": {},
    }
    if read_error == "artifact_missing":
        return {**base, "status": "missing"}
    if read_error == "artifact_too_large":
        return {**base, "status": "oversized"}
    if read_error or data is None:
        return {**base, "status": "unsafe_or_unreadable"}
    if len(data) > maximum:
        return {**base, "status": "oversized"}
    try:
        parsed = loads_no_duplicate_keys(data.decode("utf-8"))
        if not isinstance(parsed, Mapping):
            raise ValueError("report_not_object")
        projector = {
            "validation": _project_validation,
            "walk_forward": _project_walk_forward,
            "policy": _project_policy,
            "live_campaign": _project_live,
        }[key]
        projection = projector(parsed)
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return {**base, "status": "invalid"}
    return {**base, "status": "ready", "projection": projection}


def _project_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    schema_id = str(value.get("schema_id") or "")
    if schema_id == _ANALYSIS_SCHEMA:
        _require_research_safety(value)
        analyses = [_project_analysis(value)]
        wrapper: Mapping[str, Any] = {}
    elif schema_id == _VALIDATION_SCHEMA:
        _require_research_safety(value)
        wrapper = value
        analyses = [
            _project_analysis(row)
            for row in _analysis_rows(value.get("empirical_analysis"))
        ]
        if not analyses:
            raise ValueError("empirical_analysis_missing")
    else:
        raise ValueError("validation_schema_invalid")
    return {
        "schema_id": schema_id,
        "generated_at": _text(wrapper.get("generated_at"), 96),
        "status": _text(wrapper.get("status"), 96) or "ready",
        "analyses": analyses[:8],
        "replay_summary": _bounded_value(wrapper.get("replay_summary")),
        "controls_and_benchmarks": _bounded_value(wrapper.get("controls_and_benchmarks")),
        "live_campaign": _bounded_value(wrapper.get("live_campaign")),
        "final_test_confirmation": _bounded_value(wrapper.get("final_test_confirmation")),
        "conclusions": _bounded_value(wrapper.get("conclusions")),
        "limitations": _bounded_value(wrapper.get("limitations")),
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
    }


def _analysis_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping) and value.get("schema_id") == _ANALYSIS_SCHEMA:
        return [value]
    if isinstance(value, list):
        return [row for row in value[:8] if isinstance(row, Mapping) and row.get("schema_id") == _ANALYSIS_SCHEMA]
    if isinstance(value, Mapping):
        if value.get("schema_id") == "decision_radar.empirical_partition_analyses":
            return _analysis_rows(value.get("partitions"))
        rows = [
            row for _name, row in list(sorted(value.items()))[:8]
            if isinstance(row, Mapping) and row.get("schema_id") == _ANALYSIS_SCHEMA
        ]
        return rows
    return []


def _project_analysis(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_id") != _ANALYSIS_SCHEMA:
        raise ValueError("analysis_schema_invalid")
    _require_research_safety(value)
    _require_zero_safety(value.get("safety"))
    return {
        "schema_id": _ANALYSIS_SCHEMA,
        "partition": _text(value.get("partition"), 64),
        "evidence_mode": _text(value.get("evidence_mode"), 64),
        "episode_count": _count(value.get("episode_count")),
        "matured_episode_count": _count(value.get("matured_episode_count")),
        "directional_return_sample_size": _count(value.get("directional_return_sample_size")),
        "route_cohorts": _cohorts(value.get("route_cohorts"), expected=ROUTES),
        "primary_origin_cohorts": _cohorts(value.get("primary_origin_cohorts"), expected=ORIGINS),
        "score_monotonicity": _monotonicity(value.get("score_monotonicity")),
        "market_regime_cohorts": _cohorts(value.get("market_regime_cohorts")),
        "liquidity_tier_cohorts": _cohorts(value.get("liquidity_tier_cohorts")),
        "data_quality_cohorts": _cohorts(value.get("data_quality_cohorts")),
        "market_catalyst_cohorts": _cohorts(value.get("market_catalyst_cohorts")),
        "cost_sensitivity": _project_costs(value.get("cost_sensitivity")),
        "operator_burden": _project_burden(value.get("operator_burden")),
        "missed_opportunity_classifications": _classification_rows(
            value.get("missed_opportunity_classifications"), kind="missed"
        ),
        "false_positive_and_late_classifications": _classification_rows(
            value.get("false_positive_and_late_classifications"), kind="false_late"
        ),
        "multiple_comparison_warning": _text(value.get("multiple_comparison_warning"), 1024),
        "analysis_digest": _text(value.get("analysis_digest"), 128),
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
    }


def _cohorts(value: Any, *, expected: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    rows = [row for row in value[:64] if isinstance(row, Mapping)] if isinstance(value, list) else []
    projected = [_project_cohort(row) for row in rows]
    if expected:
        by_name = {row["cohort"]: row for row in projected}
        if set(by_name) != set(expected) or len(projected) != len(expected):
            raise ValueError("closed_cohort_taxonomy_invalid")
        return [by_name[name] for name in expected]
    return projected


def _project_cohort(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "mean_directional_return_fraction",
        "median_directional_return_fraction",
        "trimmed_mean_10pct_directional_return_fraction",
        "hit_rate",
        "downside_5pct_fraction",
        "worst_directional_return_fraction",
        "mean_mfe_fraction",
        "mean_mae_fraction",
        "mfe_to_mae_ratio_of_means",
    )
    return {
        "cohort": _text(row.get("cohort"), 128) or "unknown",
        "cohort_type": _text(row.get("cohort_type"), 96),
        "partition": _text(row.get("partition"), 64),
        "evidence_mode": _text(row.get("evidence_mode"), 64),
        "episode_count": _count(row.get("episode_count")),
        "matured_episode_count": _count(row.get("matured_episode_count")),
        "sample_size": _count(row.get("sample_size")),
        "sample_status": _text(row.get("sample_status"), 64),
        "evidence_strength": _text(row.get("evidence_strength"), 64),
        "result_direction": _text(row.get("result_direction"), 64),
        **{field: _number(row.get(field)) for field in fields},
        "uncertainty": _bounded_value(row.get("uncertainty"), depth=2),
    }


def _monotonicity(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value[:16]:
        if not isinstance(row, Mapping):
            continue
        rows.append({
            "score_field": _text(row.get("score_field"), 96),
            "partition": _text(row.get("partition"), 64),
            "evidence_mode": _text(row.get("evidence_mode"), 64),
            "expected_relationship": _text(row.get("expected_relationship"), 256),
            "comparable_pair_count": _count(row.get("comparable_pair_count")),
            "violation_count": _count(row.get("violation_count")),
            "buckets": _cohorts(row.get("buckets")),
        })
    return rows


def _project_costs(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    scenarios = []
    for row in list(value.get("scenarios") or [])[:16]:
        if not isinstance(row, Mapping):
            continue
        scenarios.append({
            "round_trip_cost_bps": _count(row.get("round_trip_cost_bps")),
            "sample_size": _count(row.get("sample_size")),
            "sample_status": _text(row.get("sample_status"), 64),
            "evidence_strength": _text(row.get("evidence_strength"), 64),
            "mean_net_directional_return_fraction": _number(row.get("mean_net_directional_return_fraction")),
            "median_net_directional_return_fraction": _number(row.get("median_net_directional_return_fraction")),
            "net_hit_rate": _number(row.get("net_hit_rate")),
            "mean_survives_assumed_cost": row.get("mean_survives_assumed_cost") if isinstance(row.get("mean_survives_assumed_cost"), bool) else None,
        })
    return {
        "gross_sample_size": _count(value.get("gross_sample_size")),
        "gross_mean_directional_return_fraction": _number(value.get("gross_mean_directional_return_fraction")),
        "break_even_mean_round_trip_cost_bps": _number(value.get("break_even_mean_round_trip_cost_bps")),
        "historical_spread_observed": value.get("historical_spread_observed") is True,
        "cost_basis": _text(value.get("cost_basis"), 256),
        "scenarios": scenarios,
    }


def _project_burden(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "partition": _text(value.get("partition"), 64),
        "evidence_mode": _text(value.get("evidence_mode"), 64),
        "episode_count": _count(value.get("episode_count")),
        "observed_day_count": _count(value.get("observed_day_count")),
        "family_count": _count(value.get("family_count")),
        "mean_ideas_per_observed_day": _number(value.get("mean_ideas_per_observed_day")),
        "daily": _burden_rows(value.get("daily")),
        "families": _burden_rows(value.get("families")),
    }


def _burden_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    keys = (
        "idea_count", "urgent_item_count", "digest_item_count",
        "repeated_family_item_count", "review_required_count", "system_warning_count",
    )
    return [
        {
            "dimension": _text(row.get("dimension"), 32),
            "name": _text(row.get("name"), 128),
            **{key: _count(row.get(key)) for key in keys},
        }
        for row in value[:64]
        if isinstance(row, Mapping)
    ]


def _classification_rows(value: Any, *, kind: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for row in value[:128]:
        if not isinstance(row, Mapping):
            continue
        common = {"episode_id": _text(row.get("episode_id"), 128)}
        if kind == "missed":
            common.update({
                "classification": _text(row.get("classification"), 64),
                "qualifies": row.get("qualifies") is True,
                "primary_reason": _text(row.get("primary_reason"), 128),
                "reason_codes": _strings(row.get("reason_codes"), 16, 128),
                "qualification_failure_reasons": _strings(row.get("qualification_failure_reasons"), 16, 128),
            })
        else:
            common.update({
                "classification_status": _text(row.get("classification_status"), 64),
                "false_positive": row.get("false_positive") is True,
                "late_idea": row.get("late_idea") is True,
                "symptom_codes": _strings(row.get("symptom_codes"), 24, 128),
                "issue_source_codes": _strings(row.get("issue_source_codes"), 24, 128),
            })
        rows.append(common)
    return rows


def _project_walk_forward(value: Mapping[str, Any]) -> dict[str, Any]:
    candidate = value if value.get("schema_id") == _WALK_SCHEMA else value.get("walk_forward")
    if not isinstance(candidate, Mapping) or candidate.get("schema_id") != _WALK_SCHEMA:
        raise ValueError("walk_forward_schema_invalid")
    _require_research_safety(candidate)
    folds = []
    for row in list(candidate.get("folds") or [])[:64]:
        if not isinstance(row, Mapping):
            continue
        result = row.get("test_result") if isinstance(row.get("test_result"), Mapping) else {}
        folds.append({
            "fold": _count(row.get("fold")),
            "train_start": _text(row.get("train_start"), 64),
            "train_end_exclusive": _text(row.get("train_end_exclusive"), 64),
            "test_start": _text(row.get("test_start"), 64),
            "test_end_exclusive": _text(row.get("test_end_exclusive"), 64),
            "train_episode_count": _count(row.get("train_episode_count")),
            "test_episode_count": _count(row.get("test_episode_count")),
            "selected_scenario": _text(row.get("selected_scenario"), 96),
            "selection_used_final_test": row.get("selection_used_final_test") is True,
            "test_result": _project_scenario(result),
        })
    return {
        "schema_id": _WALK_SCHEMA,
        "status": _text(candidate.get("status"), 96),
        "selection_partitions": _strings(candidate.get("selection_partitions"), 8, 64),
        "final_test_accessed": candidate.get("final_test_accessed") is True,
        "fold_count": _count(candidate.get("fold_count")),
        "nonempty_fold_count": _count(candidate.get("nonempty_fold_count")),
        "minimum_fold_count": _count(candidate.get("minimum_fold_count")),
        "folds": folds,
        "research_only": True,
        "auto_apply": False,
    }


def _project_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    schema_id = str(value.get("schema_id") or "")
    if schema_id == _POLICY_SIMULATION_SCHEMA:
        _require_research_safety(value)
        wrapper: Mapping[str, Any] = {}
        simulation = value
    elif schema_id == _POLICY_REPORT_SCHEMA:
        _require_research_safety(value)
        wrapper = value
        simulation = value.get("selection_simulation")
        if not isinstance(simulation, Mapping):
            raise ValueError("selection_simulation_missing")
    else:
        raise ValueError("policy_schema_invalid")
    if simulation.get("schema_id") != _POLICY_SIMULATION_SCHEMA:
        raise ValueError("policy_simulation_schema_invalid")
    _require_research_safety(simulation)
    scenarios = [
        _project_scenario(row)
        for row in list(simulation.get("scenarios") or [])[:32]
        if isinstance(row, Mapping)
    ]
    recommendations_source = wrapper.get("recommendations") or simulation.get("recommendations")
    recommendations = [
        {
            "scenario": _text(row.get("scenario"), 96),
            "status": _text(row.get("status"), 64),
            "reason": _text(row.get("reason"), 512),
            "sample_size": _count(row.get("sample_size")),
            "evidence_strength": _text(row.get("evidence_strength"), 96),
            "human_approval_required": row.get("human_approval_required") is True,
            "auto_apply": row.get("auto_apply") is True,
        }
        for row in list(recommendations_source or [])[:32]
        if isinstance(row, Mapping)
    ]
    if any(row["auto_apply"] for row in recommendations):
        raise ValueError("policy_recommendation_auto_apply_invalid")
    return {
        "schema_id": schema_id,
        "status": _text(wrapper.get("status"), 96) or "shadow_only",
        "partitions": _strings(simulation.get("partitions"), 8, 64),
        "episode_representatives": _count(simulation.get("episode_representatives")),
        "scenarios": scenarios,
        "recommendations": recommendations,
        "multiple_comparison_warning": _text(simulation.get("multiple_comparison_warning"), 1024),
        "recommendation_seal": _bounded_value(wrapper.get("recommendation_seal")),
        "final_test_confirmation": _bounded_value(wrapper.get("final_test_confirmation")),
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
    }


def _project_scenario(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scenario": _text(row.get("scenario"), 96),
        "episode_count": _count(row.get("episode_count")),
        "visible_episode_count": _count(row.get("visible_episode_count")),
        "matured_visible_episode_count": _count(row.get("matured_visible_episode_count")),
        "route_change_count": _count(row.get("route_change_count")),
        "cooldown_suppressed_count": _count(row.get("cooldown_suppressed_count")),
        "urgent_item_count": _count(row.get("urgent_item_count")),
        "active_day_count": _count(row.get("active_day_count")),
        "ideas_per_active_day": _number(row.get("ideas_per_active_day")),
        "mean_directional_return_fraction": _number(row.get("mean_directional_return_fraction")),
        "median_directional_return_fraction": _number(row.get("median_directional_return_fraction")),
        "hit_rate": _number(row.get("hit_rate")),
        "quick_failure_rate": _number(row.get("quick_failure_rate")),
        "evidence_strength": _text(row.get("evidence_strength"), 96),
    }


def _project_live(value: Mapping[str, Any]) -> dict[str, Any]:
    projected = project_live_campaign(value)
    if projected.get("research_only") is not True or projected.get("auto_apply") is not False:
        raise ValueError("live_projection_safety_invalid")
    return _bounded_value(projected, depth=5)


def _require_research_safety(value: Mapping[str, Any]) -> None:
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        raise ValueError("research_safety_invalid")
    if value.get("policy_eligible") is True:
        raise ValueError("policy_eligibility_invalid")
    if value.get("production_policy_mutations") not in (None, 0):
        raise ValueError("production_policy_mutation_invalid")


def _require_zero_safety(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("safety_missing")
    for field in _ZERO_SIDE_EFFECT_FIELDS:
        if field in value and value.get(field) != 0:
            raise ValueError("side_effect_claim_invalid")


def _bounded_value(value: Any, *, depth: int = 4) -> Any:
    if depth <= 0:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if not isinstance(value, float) or math.isfinite(value) else None
    if isinstance(value, str):
        return value[:1024]
    if isinstance(value, Mapping):
        return {
            str(key)[:128]: _bounded_value(item, depth=depth - 1)
            for key, item in list(sorted(value.items(), key=lambda pair: str(pair[0])))[:64]
        }
    if isinstance(value, (list, tuple)):
        return [_bounded_value(item, depth=depth - 1) for item in value[:64]]
    return _text(value, 256)


def _strings(value: Any, maximum: int, length: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_text(item, length) for item in value[:maximum]]


def _text(value: Any, maximum: int) -> str:
    return str(value or "")[:maximum]


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


__all__ = (
    "LIVE_CAMPAIGN_REPORT",
    "ORIGINS",
    "POLICY_REPORT",
    "ROUTES",
    "VALIDATION_REPORT",
    "WALK_FORWARD_REPORT",
    "load_research_lab_snapshot",
)
