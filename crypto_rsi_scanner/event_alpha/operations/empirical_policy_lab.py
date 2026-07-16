"""Pure shadow-policy and chronological walk-forward research.

This module never reads runtime configuration and never writes production
state.  Supported threshold scenarios re-run the production Decision-v2
evaluator on immutable replay ideas.  Policy-only scenarios are explicit
post-evaluation caps used solely to measure visibility and operator burden.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any, Iterable, Mapping

from ..radar.decision_model import reevaluate_radar_decision_fields
from ..radar.decision_model_surfaces import decision_model_values
from ..radar.decision_models import RadarDecisionConfig
from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_policy_simulation"
SCHEMA_VERSION = 1
SEAL_SCHEMA_ID = "decision_radar.empirical_recommendation_seal"
WALK_FORWARD_SCHEMA_ID = "decision_radar.empirical_walk_forward"
_VISIBLE_ROUTES = {
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
}
_URGENT_ROUTES = {"high_confidence_watch", "actionable_watch", "rapid_market_anomaly", "risk_watch"}
_CONFIG_CHANGE_FIELDS = {
    "dashboard_watch_threshold": "dashboard_watch_threshold",
    "actionability_threshold": "actionability_threshold",
    "rapid_urgency_threshold": "rapid_anomaly_urgency_threshold",
}


def simulate_shadow_policies(
    ideas: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    partitions: Iterable[str],
    protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare the frozen scenario set using episode representatives only."""

    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    selected_partitions = tuple(dict.fromkeys(str(value) for value in partitions))
    known_partitions = {str(row["name"]) for row in frozen["partitions"]}
    if not selected_partitions or not set(selected_partitions) <= known_partitions:
        raise ValueError("shadow-policy partitions invalid")
    rows = _episode_representatives(ideas, selected_partitions)
    outcome_index = _outcome_index(outcomes)
    scenario_rows: list[dict[str, Any]] = []
    for scenario in frozen["shadow_scenarios"]:
        scenario_rows.append(_simulate_scenario(rows, outcome_index, scenario, frozen))
    production = next(row for row in scenario_rows if row["scenario"] == "production_policy")
    recommendations = [
        _recommendation(row, production, frozen)
        for row in scenario_rows
        if row["scenario"] != "production_policy"
    ]
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "partitions": list(selected_partitions),
        "episode_representatives": len(rows),
        "scenarios": scenario_rows,
        "recommendations": recommendations,
        "multiple_comparison_warning": frozen["statistics"]["multiple_comparison_policy"],
        "causal_claim": False,
        "research_only": True,
        "auto_apply": False,
        "human_approval_required": True,
        "production_policy_mutations": 0,
    }


def freeze_recommendation_set(simulation: Mapping[str, Any]) -> dict[str, Any]:
    """Hash the development/validation recommendation set before final test."""

    if simulation.get("schema_id") != SCHEMA_ID:
        raise ValueError("recommendation simulation invalid")
    if simulation.get("partitions") != ["development", "validation"]:
        raise ValueError("recommendation seal requires development and validation only")
    if simulation.get("auto_apply") is not False or simulation.get("research_only") is not True:
        raise ValueError("recommendation simulation safety invalid")
    decisions = []
    for row in simulation.get("recommendations", []):
        if not isinstance(row, Mapping):
            raise ValueError("recommendation row invalid")
        decisions.append({
            "scenario": str(row.get("scenario") or ""),
            "status": str(row.get("status") or ""),
            "evidence_strength": str(row.get("evidence_strength") or ""),
            "reason": str(row.get("reason") or ""),
        })
    decisions.sort(key=lambda row: row["scenario"])
    body = {
        "schema_id": SEAL_SCHEMA_ID,
        "schema_version": 1,
        "protocol_version": simulation["protocol_version"],
        "protocol_sha256": simulation["protocol_sha256"],
        "selection_partitions": ["development", "validation"],
        "final_test_used_for_selection": False,
        "recommendations": decisions,
        "simulation_sha256": _sha256(_canonical_bytes(simulation)),
        "research_only": True,
        "auto_apply": False,
        "human_approval_required": True,
    }
    return {**body, "seal_sha256": _sha256(_canonical_bytes(body))}


def validate_recommendation_seal(seal: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if seal.get("schema_id") != SEAL_SCHEMA_ID or seal.get("schema_version") != 1:
        errors.append("schema_invalid")
    if seal.get("selection_partitions") != ["development", "validation"]:
        errors.append("selection_partitions_invalid")
    if seal.get("final_test_used_for_selection") is not False:
        errors.append("final_test_firewall_invalid")
    if seal.get("research_only") is not True or seal.get("auto_apply") is not False:
        errors.append("safety_invalid")
    body = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if seal.get("seal_sha256") != _sha256(_canonical_bytes(body)):
        errors.append("seal_digest_invalid")
    if seal.get("protocol_sha256") != empirical_validation_protocol.protocol_sha256():
        errors.append("protocol_digest_invalid")
    expected = {
        row["name"]
        for row in empirical_validation_protocol.protocol_values()["shadow_scenarios"]
        if row["name"] != "production_policy"
    }
    recommendations = seal.get("recommendations")
    if not isinstance(recommendations, list):
        errors.append("recommendations_invalid")
    else:
        names = [str(row.get("scenario") or "") for row in recommendations if isinstance(row, Mapping)]
        statuses = [str(row.get("status") or "") for row in recommendations if isinstance(row, Mapping)]
        if set(names) != expected or len(names) != len(expected):
            errors.append("recommendation_set_invalid")
        if any(value not in {"candidate", "not_supported", "insufficient_sample"} for value in statuses):
            errors.append("recommendation_status_invalid")
    return errors


def evaluate_sealed_final_test(
    ideas: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    seal: Mapping[str, Any],
    protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate only pre-sealed scenarios; final data cannot nominate one."""

    errors = validate_recommendation_seal(seal)
    if errors:
        raise ValueError("recommendation seal invalid:" + ";".join(errors))
    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    allowed = {row["scenario"] for row in seal.get("recommendations", []) if row.get("status") == "candidate"}
    representatives = _episode_representatives(ideas, ("final_test",))
    outcome_index = _outcome_index(outcomes)
    observed = [
        _simulate_scenario(representatives, outcome_index, scenario, frozen)
        for scenario in frozen["shadow_scenarios"]
        if scenario["name"] == "production_policy" or scenario["name"] in allowed
    ]
    return {
        "schema_id": "decision_radar.empirical_final_test_confirmation",
        "schema_version": 1,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "recommendation_seal_sha256": seal["seal_sha256"],
        "partition": "final_test",
        "scenario_selection_performed": False,
        "evaluated_scenarios": observed,
        "candidate_scenarios": sorted(allowed),
        "research_only": True,
        "auto_apply": False,
    }


def walk_forward_evaluation(
    ideas: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run frozen rolling train/test folds over development and validation."""

    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    all_rows = _episode_representatives(ideas, ("development", "validation"))
    outcome_rows = list(outcomes)
    if not all_rows:
        return _empty_walk_forward(frozen)
    start = _partition_start(frozen, "development")
    selection_end = _partition_end(frozen, "validation")
    train_days = int(frozen["walk_forward"]["rolling_train_days"])
    test_days = int(frozen["walk_forward"]["rolling_test_days"])
    folds: list[dict[str, Any]] = []
    train_start = start
    while True:
        train_end = train_start + timedelta(days=train_days)
        test_end = min(train_end + timedelta(days=test_days), selection_end)
        if train_end >= selection_end or test_end <= train_end:
            break
        train = [row for row in all_rows if train_start <= _utc(row["observed_at"]) < train_end]
        test = [row for row in all_rows if train_end <= _utc(row["observed_at"]) < test_end]
        train_scenarios = _simulate_window(train, outcome_rows, frozen)
        selected = _select_fold_scenario(train_scenarios, frozen)
        test_scenarios = _simulate_window(test, outcome_rows, frozen)
        test_result = next(row for row in test_scenarios if row["scenario"] == selected)
        folds.append({
            "fold": len(folds) + 1,
            "train_start": train_start.isoformat(),
            "train_end_exclusive": train_end.isoformat(),
            "test_start": train_end.isoformat(),
            "test_end_exclusive": test_end.isoformat(),
            "train_episode_count": len(train),
            "test_episode_count": len(test),
            "selected_scenario": selected,
            "selection_used_final_test": False,
            "test_result": test_result,
        })
        train_start += timedelta(days=test_days)
    minimum = int(frozen["walk_forward"]["minimum_folds"])
    completed = sum(1 for row in folds if row["test_episode_count"] > 0)
    return {
        "schema_id": WALK_FORWARD_SCHEMA_ID,
        "schema_version": 1,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "selection_partitions": ["development", "validation"],
        "final_test_accessed": False,
        "folds": folds,
        "fold_count": len(folds),
        "nonempty_fold_count": completed,
        "minimum_fold_count": minimum,
        "status": "complete" if completed >= minimum else "insufficient_walk_forward_folds",
        "research_only": True,
        "auto_apply": False,
    }


def _simulate_window(rows: list[Mapping[str, Any]], outcomes: list[Mapping[str, Any]], protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    index = _outcome_index(outcomes)
    return [_simulate_scenario(rows, index, scenario, protocol) for scenario in protocol["shadow_scenarios"]]


def _simulate_scenario(
    rows: list[Mapping[str, Any]],
    outcome_index: Mapping[str, Mapping[str, Any]],
    scenario: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    name = str(scenario["name"])
    changes = dict(scenario.get("changes") or {})
    evaluated: list[dict[str, Any]] = []
    for idea in rows:
        original = decision_model_values(idea)
        if not original:
            raise ValueError("shadow-policy idea missing canonical projection")
        projection = _scenario_projection(idea, original, changes)
        route = str(projection.get("radar_route") or "diagnostic")
        evaluated.append({
            "candidate_id": str(idea.get("candidate_id") or ""),
            "episode_id": str(idea.get("episode_id") or idea.get("candidate_id") or ""),
            "family_id": str(idea.get("candidate_family_id") or idea.get("canonical_asset_id") or ""),
            "observed_at": str(idea.get("observed_at") or ""),
            "market_regime": str(idea.get("market_regime") or "unknown"),
            "route": route,
            "original_route": str(original.get("radar_route") or "diagnostic"),
            "visible": route in _VISIBLE_ROUTES,
            "urgent": route in _URGENT_ROUTES,
            "return_fraction": _directional_return(idea, outcome_index),
        })
    cooldown = int(changes.get("family_cooldown_hours") or 0)
    if cooldown:
        _apply_family_cooldown(evaluated, cooldown)
    visible = [row for row in evaluated if row["visible"] and not row.get("cooldown_suppressed")]
    matured = [row for row in visible if row["return_fraction"] is not None]
    returns = [float(row["return_fraction"]) for row in matured]
    days = {str(row["observed_at"])[:10] for row in visible}
    return {
        "scenario": name,
        "changes": changes,
        "episode_count": len(rows),
        "visible_episode_count": len(visible),
        "matured_visible_episode_count": len(matured),
        "route_change_count": sum(row["route"] != row["original_route"] for row in evaluated),
        "cooldown_suppressed_count": sum(bool(row.get("cooldown_suppressed")) for row in evaluated),
        "urgent_item_count": sum(row["urgent"] for row in visible),
        "active_day_count": len(days),
        "ideas_per_active_day": round(len(visible) / len(days), 6) if days else 0.0,
        "mean_directional_return_fraction": _rounded(mean(returns)) if returns else None,
        "median_directional_return_fraction": _rounded(median(returns)) if returns else None,
        "hit_rate": _rounded(sum(value > 0 for value in returns) / len(returns)) if returns else None,
        "quick_failure_rate": _rounded(sum(value <= -0.05 for value in returns) / len(returns)) if returns else None,
        "evidence_strength": _evidence_strength(len(matured), protocol),
        "outcome_basis": "episode_representative_directional_primary_horizon",
        "historical_spread_basis": "unavailable",
        "costs_observed": False,
        "research_only": True,
        "auto_apply": False,
    }


def _scenario_projection(idea: Mapping[str, Any], original: Mapping[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    cfg = RadarDecisionConfig()
    replacements = {
        _CONFIG_CHANGE_FIELDS[key]: float(value)
        for key, value in changes.items()
        if key in _CONFIG_CHANGE_FIELDS
    }
    projection = dict(original)
    if replacements:
        cfg = replace(cfg, **replacements)
        evaluated = {**dict(idea), **reevaluate_radar_decision_fields(idea, cfg=cfg)}
        projection = decision_model_values(evaluated)
        if not projection:
            raise ValueError("shadow-policy reevaluation failed")
    route = str(projection.get("radar_route") or "diagnostic")
    if route in {"actionable_watch", "high_confidence_watch", "rapid_market_anomaly"}:
        if float(changes.get("actionable_min_evidence") or -math.inf) > float(projection.get("evidence_confidence_score") or 0):
            route = "dashboard_watch"
        if float(changes.get("actionable_max_risk") or math.inf) < float(projection.get("risk_score") or 0):
            route = "dashboard_watch"
        if changes.get("unknown_spread_actionable") is False and projection.get("spread_status") in {"unavailable", "stale"}:
            route = "dashboard_watch"
    projection = {**projection, "radar_route": route, "radar_actionable": route in {"actionable_watch", "high_confidence_watch", "rapid_market_anomaly"}}
    return projection


def _recommendation(row: Mapping[str, Any], production: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    required = int(protocol["minimum_samples"]["shadow_recommendation_development_validation"])
    n = int(row["matured_visible_episode_count"])
    status = "insufficient_sample"
    reason = f"requires_at_least_{required}_matured_visible_episodes"
    if n >= required:
        row_mean = row.get("mean_directional_return_fraction")
        base_mean = production.get("mean_directional_return_fraction")
        row_fail = row.get("quick_failure_rate")
        base_fail = production.get("quick_failure_rate")
        burden_limit = float(production.get("ideas_per_active_day") or 0) * 1.2
        if None not in (row_mean, base_mean, row_fail, base_fail) and row_mean >= base_mean and row_fail <= base_fail and row["ideas_per_active_day"] <= burden_limit:
            status = "candidate"
            reason = "noninferior_return_and_failure_with_bounded_operator_burden"
        else:
            status = "not_supported"
            reason = "frozen_multi_metric_rule_not_met"
    return {
        "scenario": row["scenario"],
        "status": status,
        "reason": reason,
        "sample_size": n,
        "evidence_strength": row["evidence_strength"],
        "human_approval_required": True,
        "auto_apply": False,
    }


def _select_fold_scenario(rows: list[Mapping[str, Any]], protocol: Mapping[str, Any]) -> str:
    production = next(row for row in rows if row["scenario"] == "production_policy")
    candidates = [
        row for row in rows
        if row["scenario"] != "production_policy"
        and _recommendation(row, production, protocol)["status"] == "candidate"
    ]
    if not candidates:
        return "production_policy"
    return min(candidates, key=lambda row: (-float(row["mean_directional_return_fraction"]), float(row["ideas_per_active_day"]), row["scenario"]))["scenario"]


def _episode_representatives(ideas: Iterable[Mapping[str, Any]], partitions: Iterable[str]) -> list[dict[str, Any]]:
    permitted = set(partitions)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    ordered = sorted((dict(row) for row in ideas), key=lambda row: (str(row.get("observed_at") or ""), str(row.get("candidate_id") or "")))
    for row in ordered:
        partition = str(row.get("replay_partition") or row.get("partition") or "")
        if partition not in permitted:
            continue
        episode_id = str(row.get("episode_id") or row.get("candidate_id") or "")
        if not episode_id or episode_id in seen:
            continue
        seen.add(episode_id)
        rows.append(row)
    return rows


def _outcome_index(outcomes: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in outcomes:
        if not isinstance(row, Mapping):
            continue
        key = str(row.get("candidate_id") or row.get("representative_candidate_id") or "")
        if key:
            result[key] = row
    return result


def _directional_return(idea: Mapping[str, Any], outcomes: Mapping[str, Mapping[str, Any]]) -> float | None:
    outcome = outcomes.get(str(idea.get("candidate_id") or ""))
    if not outcome or str(outcome.get("outcome_status") or outcome.get("status") or "") not in {"matured", "complete"}:
        return None
    for field in ("primary_directional_return_fraction", "directional_return_fraction", "primary_return_fraction", "return_3d_fraction"):
        value = _finite(outcome.get(field))
        if value is not None:
            if field in {"primary_directional_return_fraction", "directional_return_fraction"}:
                return value
            bias = str(decision_model_values(idea).get("directional_bias") or "long")
            return -value if bias in {"risk", "fade_short_review"} else value
    returns = outcome.get("returns")
    if isinstance(returns, Mapping):
        value = _finite(returns.get("3d"))
        if value is not None:
            bias = str(decision_model_values(idea).get("directional_bias") or "long")
            return -value if bias in {"risk", "fade_short_review"} else value
    return None


def _apply_family_cooldown(rows: list[dict[str, Any]], hours: int) -> None:
    seen: dict[str, datetime] = {}
    for row in sorted(rows, key=lambda item: (item["observed_at"], item["candidate_id"])):
        if not row["visible"]:
            continue
        current = _utc(row["observed_at"])
        prior = seen.get(row["family_id"])
        if prior is not None and current - prior < timedelta(hours=hours):
            row["cooldown_suppressed"] = True
        else:
            seen[row["family_id"]] = current


def _evidence_strength(sample_size: int, protocol: Mapping[str, Any]) -> str:
    minimum = protocol["minimum_samples"]
    if sample_size >= int(minimum["shadow_recommendation_development_validation"]):
        return "policy_candidate_sample"
    if sample_size >= int(minimum["cohort_directional"]):
        return "directional_descriptive"
    if sample_size >= int(minimum["descriptive"]):
        return "descriptive_only"
    return "insufficient_sample"


def _empty_walk_forward(protocol: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": WALK_FORWARD_SCHEMA_ID,
        "schema_version": 1,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "selection_partitions": ["development", "validation"],
        "final_test_accessed": False,
        "folds": [],
        "fold_count": 0,
        "nonempty_fold_count": 0,
        "minimum_fold_count": int(protocol["walk_forward"]["minimum_folds"]),
        "status": "insufficient_walk_forward_folds",
        "research_only": True,
        "auto_apply": False,
    }


def _partition_end(protocol: Mapping[str, Any], name: str) -> datetime:
    row = next(item for item in protocol["partitions"] if item["name"] == name)
    return _utc(row["end_exclusive"])


def _partition_start(protocol: Mapping[str, Any], name: str) -> datetime:
    row = next(item for item in protocol["partitions"] if item["name"] == name)
    return _utc(row["start_inclusive"])


def _require_protocol(protocol: Mapping[str, Any]) -> None:
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("empirical protocol invalid:" + ";".join(errors))


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp timezone required")
    return parsed.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rounded(value: float) -> float:
    return round(float(value), 8)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "evaluate_sealed_final_test",
    "freeze_recommendation_set",
    "simulate_shadow_policies",
    "validate_recommendation_seal",
    "walk_forward_evaluation",
]
