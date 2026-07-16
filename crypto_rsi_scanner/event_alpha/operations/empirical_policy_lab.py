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
from typing import Any, Iterable, Mapping

from ..radar.decision_model import reevaluate_radar_decision_fields
from ..radar.decision_model_surfaces import decision_model_values
from ..radar.decision_models import RadarDecisionConfig
from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_policy_simulation"
SCHEMA_VERSION = 1
SEAL_SCHEMA_ID = "decision_radar.empirical_recommendation_seal"
SEAL_SCHEMA_VERSION = 2
WALK_FORWARD_SCHEMA_ID = "decision_radar.empirical_walk_forward"
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
    selected_observation_days_by_partition: Mapping[
        str, Iterable[str]
    ] | None = None,
) -> dict[str, Any]:
    """Compare the frozen scenario set using episode representatives only."""

    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    selected_partitions = tuple(dict.fromkeys(str(value) for value in partitions))
    known_partitions = {str(row["name"]) for row in frozen["partitions"]}
    if not selected_partitions or not set(selected_partitions) <= known_partitions:
        raise ValueError("shadow-policy partitions invalid")
    rows = _episode_representatives(ideas, selected_partitions)
    day_sets, day_basis = _observation_days_by_partition(
        selected_observation_days_by_partition,
        partitions=selected_partitions,
        rows=rows,
        protocol=frozen,
    )
    selected_days = set().union(*(day_sets.values()))
    outcome_index = _outcome_index(outcomes)
    scenario_rows: list[dict[str, Any]] = []
    scenario_definitions = _scenario_definitions(frozen)
    for scenario in scenario_definitions:
        scenario_rows.append(
            _simulate_scenario(
                rows,
                outcome_index,
                scenario,
                frozen,
                selected_observation_days=selected_days,
                observed_day_denominator_basis=day_basis,
            )
        )
    production = next(row for row in scenario_rows if row["scenario"] == "production_policy")
    scenario_rows = [
        {**row, "comparison_to_production": _scenario_comparison(row, production)}
        for row in scenario_rows
    ]
    production = next(row for row in scenario_rows if row["scenario"] == "production_policy")
    recommendations = [
        _recommendation(row, production, frozen)
        for row in scenario_rows
        if row["scenario"] != "production_policy"
    ]
    seal_eligible = (
        day_basis == "exact_selected_observation_utc_days"
        and bool(selected_days)
    )
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "partitions": list(selected_partitions),
        "episode_representatives": len(rows),
        "selected_observation_day_count": len(selected_days),
        "idea_active_day_count": len(_idea_days(rows)),
        "observed_day_denominator_basis": day_basis,
        "selected_observation_days_sha256": _days_digest(selected_days),
        "recommendation_seal_eligible": seal_eligible,
        "recommendation_seal_ineligibility_reasons": (
            []
            if seal_eligible
            else [
                (
                    "selected_observation_days_empty"
                    if day_basis == "exact_selected_observation_utc_days"
                    else "exact_selected_observation_days_not_supplied"
                )
            ]
        ),
        "frozen_scenarios": scenario_definitions,
        "scenario_set_sha256": _sha256(_canonical_bytes(scenario_definitions)),
        "scenarios": scenario_rows,
        "recommendations": recommendations,
        "multiple_comparison_warning": frozen["statistics"]["multiple_comparison_policy"],
        "causal_claim": False,
        "research_only": True,
        "auto_apply": False,
        "human_approval_required": True,
        "production_policy_mutations": 0,
    }


def freeze_recommendation_set(
    simulation: Mapping[str, Any],
    *,
    selection_run_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Hash the development/validation recommendation set before final test."""

    if simulation.get("schema_id") != SCHEMA_ID:
        raise ValueError("recommendation simulation invalid")
    if simulation.get("partitions") != ["development", "validation"]:
        raise ValueError("recommendation seal requires development and validation only")
    if simulation.get("auto_apply") is not False or simulation.get("research_only") is not True:
        raise ValueError("recommendation simulation safety invalid")
    if (
        simulation.get("observed_day_denominator_basis")
        != "exact_selected_observation_utc_days"
        or simulation.get("recommendation_seal_eligible") is not True
    ):
        raise ValueError(
            "recommendation seal requires exact selected observation days"
        )
    scenario_definitions = _scenario_definitions_from_simulation(simulation)
    binding = _selection_run_binding(selection_run_binding)
    scenario_rows = simulation.get("scenarios")
    if not isinstance(scenario_rows, list):
        raise ValueError("recommendation simulation rows invalid")
    selected_day_count = simulation.get("selected_observation_day_count")
    selected_days_sha256 = simulation.get("selected_observation_days_sha256")
    if (
        not isinstance(selected_day_count, int)
        or selected_day_count <= 0
        or not _is_sha256(selected_days_sha256)
    ):
        raise ValueError(
            "recommendation seal requires exact selected observation days"
        )
    for row in scenario_rows:
        burden = row.get("operator_burden") if isinstance(row, Mapping) else None
        if (
            not isinstance(row, Mapping)
            or row.get("observed_day_denominator_basis")
            != simulation.get("observed_day_denominator_basis")
            or row.get("observed_day_count") != selected_day_count
            or row.get("selected_observation_days_sha256")
            != selected_days_sha256
            or not isinstance(burden, Mapping)
            or burden.get("observed_day_denominator_basis")
            != simulation.get("observed_day_denominator_basis")
            or burden.get("observed_day_count") != selected_day_count
            or burden.get("selected_observation_days_sha256")
            != selected_days_sha256
        ):
            raise ValueError(
                "recommendation seal selected observation days inconsistent"
            )
    production = next(
        (
            row
            for row in scenario_rows
            if isinstance(row, Mapping)
            and row.get("scenario") == "production_policy"
        ),
        None,
    )
    if not isinstance(production, Mapping):
        raise ValueError("recommendation simulation rows invalid")
    expected_recommendations = [
        _recommendation(row, production, empirical_validation_protocol.protocol_values())
        for row in scenario_rows
        if isinstance(row, Mapping) and row.get("scenario") != "production_policy"
    ]
    if simulation.get("recommendations") != expected_recommendations:
        raise ValueError("recommendation simulation decisions invalid")
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
    protocol = empirical_validation_protocol.protocol_values()
    shadow_rule = dict(protocol["shadow_recommendation_rule"])
    confirmation_rule = dict(protocol["final_test_confirmation_rule"])
    body = {
        "schema_id": SEAL_SCHEMA_ID,
        "schema_version": SEAL_SCHEMA_VERSION,
        "protocol_version": simulation["protocol_version"],
        "protocol_sha256": simulation["protocol_sha256"],
        "selection_partitions": ["development", "validation"],
        "final_test_used_for_selection": False,
        "selection_run_binding": binding,
        "selected_observation_day_count": int(
            simulation["selected_observation_day_count"]
        ),
        "observed_day_denominator_basis": simulation[
            "observed_day_denominator_basis"
        ],
        "selected_observation_days_sha256": simulation[
            "selected_observation_days_sha256"
        ],
        "frozen_scenarios": scenario_definitions,
        "scenario_set_sha256": _sha256(_canonical_bytes(scenario_definitions)),
        "shadow_recommendation_rule": shadow_rule,
        "shadow_recommendation_rule_sha256": _sha256(
            _canonical_bytes(shadow_rule)
        ),
        "final_test_confirmation_rule": confirmation_rule,
        "final_test_confirmation_rule_sha256": _sha256(
            _canonical_bytes(confirmation_rule)
        ),
        "recommendations": decisions,
        "simulation_sha256": _sha256(_canonical_bytes(simulation)),
        "research_only": True,
        "auto_apply": False,
        "human_approval_required": True,
    }
    return {**body, "seal_sha256": _sha256(_canonical_bytes(body))}


def validate_recommendation_seal(seal: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if (
        seal.get("schema_id") != SEAL_SCHEMA_ID
        or seal.get("schema_version") != SEAL_SCHEMA_VERSION
    ):
        errors.append("schema_invalid")
    if seal.get("selection_partitions") != ["development", "validation"]:
        errors.append("selection_partitions_invalid")
    if (
        seal.get("observed_day_denominator_basis")
        != "exact_selected_observation_utc_days"
        or not isinstance(seal.get("selected_observation_day_count"), int)
        or int(seal.get("selected_observation_day_count") or 0) <= 0
        or not _is_sha256(seal.get("selected_observation_days_sha256"))
    ):
        errors.append("selected_observation_day_denominator_invalid")
    if seal.get("final_test_used_for_selection") is not False:
        errors.append("final_test_firewall_invalid")
    if seal.get("research_only") is not True or seal.get("auto_apply") is not False:
        errors.append("safety_invalid")
    body = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if seal.get("seal_sha256") != _sha256(_canonical_bytes(body)):
        errors.append("seal_digest_invalid")
    if seal.get("protocol_sha256") != empirical_validation_protocol.protocol_sha256():
        errors.append("protocol_digest_invalid")
    current_scenarios = _scenario_definitions(
        empirical_validation_protocol.protocol_values()
    )
    frozen_scenarios = seal.get("frozen_scenarios")
    if frozen_scenarios != current_scenarios:
        errors.append("scenario_definitions_invalid")
    if (
        not isinstance(frozen_scenarios, list)
        or seal.get("scenario_set_sha256")
        != _sha256(_canonical_bytes(frozen_scenarios))
    ):
        errors.append("scenario_set_digest_invalid")
    protocol = empirical_validation_protocol.protocol_values()
    if seal.get("shadow_recommendation_rule") != protocol.get(
        "shadow_recommendation_rule"
    ) or seal.get("shadow_recommendation_rule_sha256") != _sha256(
        _canonical_bytes(protocol["shadow_recommendation_rule"])
    ):
        errors.append("shadow_recommendation_rule_invalid")
    if seal.get("final_test_confirmation_rule") != protocol.get(
        "final_test_confirmation_rule"
    ) or seal.get("final_test_confirmation_rule_sha256") != _sha256(
        _canonical_bytes(protocol["final_test_confirmation_rule"])
    ):
        errors.append("final_test_confirmation_rule_invalid")
    binding = seal.get("selection_run_binding")
    try:
        _selection_run_binding(binding if isinstance(binding, Mapping) else {})
    except ValueError:
        errors.append("selection_run_binding_invalid")
    expected = {
        row["name"] for row in current_scenarios if row["name"] != "production_policy"
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
    selected_observation_days_by_partition: Mapping[
        str, Iterable[str]
    ] | None = None,
) -> dict[str, Any]:
    """Evaluate only pre-sealed scenarios; final data cannot nominate one."""

    errors = validate_recommendation_seal(seal)
    if errors:
        raise ValueError("recommendation seal invalid:" + ";".join(errors))
    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    allowed = {row["scenario"] for row in seal.get("recommendations", []) if row.get("status") == "candidate"}
    representatives = _episode_representatives(ideas, ("final_test",))
    day_sets, day_basis = _observation_days_by_partition(
        selected_observation_days_by_partition,
        partitions=("final_test",),
        rows=representatives,
        protocol=frozen,
    )
    if day_basis != "exact_selected_observation_utc_days":
        raise ValueError(
            "final confirmation requires exact selected observation days"
        )
    selected_days = day_sets["final_test"]
    outcome_index = _outcome_index(outcomes)
    observed = [
        _simulate_scenario(
            representatives,
            outcome_index,
            scenario,
            frozen,
            selected_observation_days=selected_days,
            observed_day_denominator_basis=day_basis,
        )
        for scenario in seal["frozen_scenarios"]
        if scenario["name"] == "production_policy" or scenario["name"] in allowed
    ]
    production = next(
        row for row in observed if row["scenario"] == "production_policy"
    )
    confirmations = [
        _final_confirmation(
            next(row for row in observed if row["scenario"] == scenario),
            production,
            rule=seal["final_test_confirmation_rule"],
        )
        for scenario in sorted(allowed)
    ]
    return {
        "schema_id": "decision_radar.empirical_final_test_confirmation",
        "schema_version": 1,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "recommendation_seal_sha256": seal["seal_sha256"],
        "selection_run_binding": dict(seal["selection_run_binding"]),
        "scenario_set_sha256": seal["scenario_set_sha256"],
        "partition": "final_test",
        "selected_observation_day_count": len(selected_days),
        "idea_active_day_count": len(_idea_days(representatives)),
        "observed_day_denominator_basis": day_basis,
        "selected_observation_days_sha256": _days_digest(selected_days),
        "scenario_selection_performed": False,
        "evaluated_scenarios": observed,
        "candidate_scenarios": sorted(allowed),
        "final_test_confirmation_rule": dict(
            seal["final_test_confirmation_rule"]
        ),
        "final_test_confirmation_rule_sha256": seal[
            "final_test_confirmation_rule_sha256"
        ],
        "confirmations": confirmations,
        "confirmation_status": (
            "complete" if confirmations else "no_candidate_recommendations"
        ),
        "confirmed_candidate_count": sum(
            row["confirmation_status"] == "confirmed" for row in confirmations
        ),
        "rejected_candidate_count": sum(
            row["confirmation_status"] == "rejected" for row in confirmations
        ),
        "insufficient_sample_candidate_count": sum(
            row["confirmation_status"] == "insufficient_sample"
            for row in confirmations
        ),
        "final_test_used_for_selection": False,
        "human_approval_required": True,
        "production_policy_mutations": 0,
        "research_only": True,
        "auto_apply": False,
    }


def walk_forward_evaluation(
    ideas: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    protocol: Mapping[str, Any] | None = None,
    selected_observation_days_by_partition: Mapping[
        str, Iterable[str]
    ] | None = None,
) -> dict[str, Any]:
    """Run frozen rolling train/test folds over development and validation."""

    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    _require_protocol(frozen)
    all_rows = _episode_representatives(ideas, ("development", "validation"))
    day_sets, day_basis = _observation_days_by_partition(
        selected_observation_days_by_partition,
        partitions=("development", "validation"),
        rows=all_rows,
        protocol=frozen,
    )
    if day_basis != "exact_selected_observation_utc_days":
        raise ValueError(
            "walk-forward selection requires exact selected observation days"
        )
    all_observed_days = set().union(*day_sets.values())
    outcome_rows = list(outcomes)
    if not all_rows:
        return _empty_walk_forward(
            frozen,
            selected_observation_days=all_observed_days,
            observed_day_denominator_basis=day_basis,
        )
    start = _partition_start(frozen, "development")
    selection_end = _partition_end(frozen, "validation")
    train_window_days = int(frozen["walk_forward"]["rolling_train_days"])
    test_window_days = int(frozen["walk_forward"]["rolling_test_days"])
    folds: list[dict[str, Any]] = []
    train_start = start
    omitted_partial_test_window: dict[str, Any] | None = None
    while True:
        train_end = train_start + timedelta(days=train_window_days)
        test_end = min(
            train_end + timedelta(days=test_window_days), selection_end
        )
        if train_end >= selection_end or test_end <= train_end:
            break
        if test_end - train_end < timedelta(days=test_window_days):
            omitted_partial_test_window = {
                "test_start": train_end.isoformat(),
                "test_end_exclusive": test_end.isoformat(),
                "available_days": (test_end - train_end).days,
                "required_days": test_window_days,
                "status": "omitted_partial_test_fold",
            }
            break
        train = [row for row in all_rows if train_start <= _utc(row["observed_at"]) < train_end]
        test = [row for row in all_rows if train_end <= _utc(row["observed_at"]) < test_end]
        train_outcomes, train_purged = _purged_outcomes(
            outcome_rows, train, cutoff_exclusive=train_end, protocol=frozen
        )
        test_outcomes, test_purged = _purged_outcomes(
            outcome_rows, test, cutoff_exclusive=test_end, protocol=frozen
        )
        train_observed_days = _days_in_window(
            all_observed_days, train_start, train_end
        )
        test_observed_days = _days_in_window(
            all_observed_days, train_end, test_end
        )
        train_scenarios = _simulate_window(
            train,
            train_outcomes,
            frozen,
            selected_observation_days=train_observed_days,
            observed_day_denominator_basis=day_basis,
        )
        selected = _select_fold_scenario(train_scenarios, frozen)
        test_scenarios = _simulate_window(
            test,
            test_outcomes,
            frozen,
            selected_observation_days=test_observed_days,
            observed_day_denominator_basis=day_basis,
        )
        test_result = next(row for row in test_scenarios if row["scenario"] == selected)
        test_evaluable = int(
            test_result.get("matured_visible_episode_count") or 0
        )
        folds.append({
            "fold": len(folds) + 1,
            "train_start": train_start.isoformat(),
            "train_end_exclusive": train_end.isoformat(),
            "test_start": train_end.isoformat(),
            "test_end_exclusive": test_end.isoformat(),
            "train_episode_count": len(train),
            "train_selected_observation_day_count": len(train_observed_days),
            "train_idea_active_day_count": len(_idea_days(train)),
            "train_outcome_eligible_episode_count": len(train_outcomes),
            "train_outcome_purged_count": train_purged,
            "test_episode_count": len(test),
            "test_selected_observation_day_count": len(test_observed_days),
            "test_idea_active_day_count": len(_idea_days(test)),
            "test_outcome_eligible_episode_count": len(test_outcomes),
            "test_outcome_evaluable_episode_count": test_evaluable,
            "test_outcome_purged_count": test_purged,
            "selected_scenario": selected,
            "selection_used_final_test": False,
            "test_result": test_result,
        })
        train_start += timedelta(days=test_window_days)
    minimum = int(frozen["walk_forward"]["minimum_folds"])
    nonempty = sum(1 for row in folds if row["test_episode_count"] > 0)
    outcome_evaluable = sum(
        1
        for row in folds
        if row["test_outcome_evaluable_episode_count"] > 0
    )
    return {
        "schema_id": WALK_FORWARD_SCHEMA_ID,
        "schema_version": 1,
        "protocol_version": frozen["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(frozen),
        "selection_partitions": ["development", "validation"],
        "selected_observation_day_count": len(all_observed_days),
        "idea_active_day_count": len(_idea_days(all_rows)),
        "observed_day_denominator_basis": day_basis,
        "selected_observation_days_sha256": _days_digest(all_observed_days),
        "final_test_accessed": False,
        "folds": folds,
        "fold_count": len(folds),
        "nonempty_fold_count": nonempty,
        "outcome_evaluable_fold_count": outcome_evaluable,
        "minimum_fold_count": minimum,
        "outcome_purge_rule": frozen["walk_forward"]["outcome_purge_rule"],
        "partial_test_fold_policy": frozen["walk_forward"][
            "partial_test_fold_policy"
        ],
        "omitted_partial_test_window": omitted_partial_test_window,
        "status": (
            "complete"
            if outcome_evaluable >= minimum
            else "insufficient_walk_forward_folds"
        ),
        "research_only": True,
        "auto_apply": False,
    }


def _simulate_window(
    rows: list[Mapping[str, Any]],
    outcomes: list[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    selected_observation_days: set[str],
    observed_day_denominator_basis: str,
) -> list[dict[str, Any]]:
    index = _outcome_index(outcomes)
    return [
        _simulate_scenario(
            rows,
            index,
            scenario,
            protocol,
            selected_observation_days=selected_observation_days,
            observed_day_denominator_basis=observed_day_denominator_basis,
        )
        for scenario in _scenario_definitions(protocol)
    ]


def _simulate_scenario(
    rows: list[Mapping[str, Any]],
    outcome_index: Mapping[str, Mapping[str, Any]],
    scenario: Mapping[str, Any],
    protocol: Mapping[str, Any],
    *,
    selected_observation_days: set[str] | None = None,
    observed_day_denominator_basis: str = "fallback_episode_active_utc_days_only",
) -> dict[str, Any]:
    from .empirical_policy_metrics import simulate_scenario

    return simulate_scenario(
        rows,
        outcome_index,
        scenario,
        protocol,
        selected_observation_days=selected_observation_days,
        observed_day_denominator_basis=observed_day_denominator_basis,
    )


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
        # The stored canonical projection is the upstream authority for the
        # production result.  A shadow threshold may legitimately change its
        # mirrored route, so it must not remain nested while the hypothetical
        # result is being closed or the normal drift guard will reject it.
        source = dict(idea)
        source.pop("decision_projection", None)
        evaluated = {
            **source,
            **reevaluate_radar_decision_fields(source, cfg=cfg),
        }
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
    if "maximum_expiry_hours" in changes:
        cap_hours = _finite(changes.get("maximum_expiry_hours"))
        if cap_hours is None or cap_hours <= 0:
            raise ValueError("shadow maximum expiry hours invalid")
        observed = _utc(str(idea.get("observed_at") or ""))
        cap_at = observed + timedelta(hours=cap_hours)
        original_expiry = _optional_utc(projection.get("expires_at"))
        if original_expiry is not None and original_expiry <= observed:
            raise ValueError("shadow-policy canonical expiry invalid")
        shadow_expiry = (
            cap_at
            if original_expiry is None or original_expiry > cap_at
            else original_expiry
        )
        projection = {**projection, "expires_at": shadow_expiry.isoformat()}
    projection = {**projection, "radar_route": route, "radar_actionable": route in {"actionable_watch", "high_confidence_watch", "rapid_market_anomaly"}}
    return projection


def _recommendation(row: Mapping[str, Any], production: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    rule = protocol["shadow_recommendation_rule"]
    required = int(protocol["minimum_samples"][rule["minimum_sample_key"]])
    n = int(row["matured_visible_episode_count"])
    material_changes = int(row.get("material_policy_change_count") or 0)
    checks = _comparison_checks(row, production)
    if rule["requires_material_policy_change"] and material_changes == 0:
        status = "not_supported"
        reason = "scenario_produced_no_observable_policy_change"
    elif n < required:
        status = "insufficient_sample"
        reason = f"requires_at_least_{required}_matured_visible_episodes"
    elif checks["required_metrics_present"] is not True:
        status = str(rule["missing_required_metric_status"])
        reason = "frozen_required_metric_missing"
    elif all(
        checks[field] is True
        for field in (
            "mean_return_noninferior",
            "quick_failure_noninferior",
            "operator_burden_bounded",
        )
    ):
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
        "material_policy_change_count": material_changes,
        "comparison_checks": checks,
        "operator_burden": dict(row.get("operator_burden") or {}),
        "false_positive_summary": dict(
            row.get("false_positive_summary") or {}
        ),
        "missed_opportunity_proxy": dict(
            row.get("missed_opportunity_proxy") or {}
        ),
        "regime_stability": dict(row.get("regime_stability") or {}),
        "comparison_to_production": dict(
            row.get("comparison_to_production") or {}
        ),
        "evidence_strength": row["evidence_strength"],
        "human_approval_required": True,
        "auto_apply": False,
    }


def _final_confirmation(
    row: Mapping[str, Any],
    production: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    sample_size = int(row.get("matured_visible_episode_count") or 0)
    minimum = int(rule["minimum_matured_visible_episodes"])
    material_changes = int(row.get("material_policy_change_count") or 0)
    checks = {
        **_comparison_checks(row, production),
        "material_policy_change_observed": material_changes > 0,
    }
    if sample_size < minimum:
        status = "insufficient_sample"
        reason = f"requires_at_least_{minimum}_matured_visible_episodes"
    elif rule["requires_material_policy_change"] and material_changes == 0:
        status = "rejected"
        reason = "scenario_produced_no_observable_policy_change_in_final_test"
    elif checks["required_metrics_present"] is not True:
        status = str(rule["missing_required_metric_status"])
        reason = "frozen_required_metric_missing"
    elif all(
        checks[field] is True
        for field in (
            "mean_return_noninferior",
            "quick_failure_noninferior",
            "operator_burden_bounded",
        )
    ):
        status = "confirmed"
        reason = "frozen_noninferiority_failure_burden_rule_passed"
    else:
        status = "rejected"
        reason = "frozen_confirmation_rule_not_met"
    return {
        "scenario": row["scenario"],
        "selection_status": "candidate",
        "confirmation_status": status,
        "reason": reason,
        "sample_size": sample_size,
        "minimum_sample_size": minimum,
        "material_policy_change_count": material_changes,
        "checks": checks,
        "candidate_metrics": _confirmation_metrics(row),
        "production_metrics": _confirmation_metrics(production),
        "eligible_for_human_policy_review": status == "confirmed",
        "scenario_selection_performed": False,
        "human_approval_required": True,
        "production_policy_mutations": 0,
        "research_only": True,
        "auto_apply": False,
    }


def _confirmation_metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mean_directional_return_fraction": row.get(
            "mean_directional_return_fraction"
        ),
        "quick_failure_rate": row.get("quick_failure_rate"),
        "ideas_per_observed_day": row.get("ideas_per_observed_day"),
        "ideas_per_active_day_descriptive": row.get("ideas_per_active_day"),
        "observed_day_count": row.get("observed_day_count"),
        "observed_day_denominator_basis": row.get(
            "observed_day_denominator_basis"
        ),
        "selected_observation_days_sha256": row.get(
            "selected_observation_days_sha256"
        ),
        "matured_visible_episode_count": row.get(
            "matured_visible_episode_count"
        ),
    }


def _comparison_checks(
    row: Mapping[str, Any], production: Mapping[str, Any]
) -> dict[str, Any]:
    candidate_mean = _finite(row.get("mean_directional_return_fraction"))
    production_mean = _finite(production.get("mean_directional_return_fraction"))
    candidate_failure = _finite(row.get("quick_failure_rate"))
    production_failure = _finite(production.get("quick_failure_rate"))
    candidate_burden = _finite(row.get("ideas_per_observed_day"))
    production_burden = _finite(production.get("ideas_per_observed_day"))
    denominator_matches = (
        row.get("observed_day_denominator_basis")
        == production.get("observed_day_denominator_basis")
        and row.get("selected_observation_days_sha256")
        == production.get("selected_observation_days_sha256")
        and row.get("observed_day_count") == production.get("observed_day_count")
    )
    present = None not in (
        candidate_mean,
        production_mean,
        candidate_failure,
        production_failure,
        candidate_burden,
        production_burden,
    ) and denominator_matches
    return {
        "required_metrics_present": present,
        "operator_burden_metric": "ideas_per_observed_day",
        "operator_burden_denominator_match": denominator_matches,
        "operator_burden_denominator_basis": row.get(
            "observed_day_denominator_basis"
        ),
        "mean_return_noninferior": (
            candidate_mean >= production_mean if present else None
        ),
        "quick_failure_noninferior": (
            candidate_failure <= production_failure if present else None
        ),
        "operator_burden_bounded": (
            candidate_burden <= production_burden * 1.2 if present else None
        ),
        "operator_burden_max_ratio": 1.2,
    }


def _scenario_comparison(
    row: Mapping[str, Any], production: Mapping[str, Any]
) -> dict[str, Any]:
    false_positive = row.get("false_positive_summary") or {}
    base_false_positive = production.get("false_positive_summary") or {}
    missed = row.get("missed_opportunity_proxy") or {}
    base_missed = production.get("missed_opportunity_proxy") or {}
    burden = row.get("operator_burden") or {}
    base_burden = production.get("operator_burden") or {}
    return {
        "visible_episode_change": int(row.get("visible_episode_count") or 0)
        - int(production.get("visible_episode_count") or 0),
        "urgent_item_change": int(row.get("urgent_item_count") or 0)
        - int(production.get("urgent_item_count") or 0),
        "quick_failure_count_change": int(
            false_positive.get("quick_failure_count") or 0
        )
        - int(base_false_positive.get("quick_failure_count") or 0),
        "hidden_positive_episode_change": int(
            missed.get("hidden_positive_episode_count") or 0
        )
        - int(base_missed.get("hidden_positive_episode_count") or 0),
        "expired_before_positive_primary_resolution_change": int(
            missed.get("expired_before_positive_primary_resolution_count") or 0
        )
        - int(
            base_missed.get(
                "expired_before_positive_primary_resolution_count"
            )
            or 0
        ),
        "expiry_capped_count_change": int(
            row.get("expiry_capped_count") or 0
        )
        - int(production.get("expiry_capped_count") or 0),
        "visible_operator_lifetime_hours_change": _difference(
            burden.get("visible_operator_lifetime_hours"),
            base_burden.get("visible_operator_lifetime_hours"),
        ),
        "ideas_per_observed_day_change": _difference(
            burden.get("ideas_per_observed_day"),
            base_burden.get("ideas_per_observed_day"),
        ),
        "mean_directional_return_change_fraction": _difference(
            row.get("mean_directional_return_fraction"),
            production.get("mean_directional_return_fraction"),
        ),
        "comparison_is_descriptive": True,
        "causal_claim": False,
    }


def _purged_outcomes(
    outcomes: list[Mapping[str, Any]],
    ideas: list[Mapping[str, Any]],
    *,
    cutoff_exclusive: datetime,
    protocol: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], int]:
    ideas_by_id = {
        str(row.get("candidate_id") or row.get("idea_id") or ""): row
        for row in ideas
    }
    selected: list[Mapping[str, Any]] = []
    purged = 0
    for row in outcomes:
        key = str(
            row.get("candidate_id")
            or row.get("idea_id")
            or row.get("representative_candidate_id")
            or ""
        )
        idea = ideas_by_id.get(key)
        if idea is None:
            continue
        due = _primary_outcome_due(row, idea, protocol)
        if due >= cutoff_exclusive:
            purged += 1
            continue
        selected.append(row)
    return selected, purged


def _primary_outcome_due(
    outcome: Mapping[str, Any],
    idea: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> datetime:
    primary_days = int(protocol["outcomes"]["primary_horizon_days"])
    expected_label = f"{primary_days}d"
    primary = str(outcome.get("primary_horizon") or expected_label)
    if primary != expected_label:
        raise ValueError("primary outcome horizon does not match frozen protocol")
    observed = _utc(str(idea["observed_at"]))
    expected_due = observed + timedelta(days=primary_days)
    horizons = outcome.get("horizons")
    if isinstance(horizons, Mapping):
        row = horizons.get(primary)
        if isinstance(row, Mapping) and row.get("due_at"):
            stored_due = _utc(row["due_at"])
            if stored_due != expected_due:
                raise ValueError(
                    "primary outcome due_at does not match frozen horizon"
                )
            return stored_due
    return expected_due


def _difference(left: Any, right: Any) -> float | None:
    left_value = _finite(left)
    right_value = _finite(right)
    if left_value is None or right_value is None:
        return None
    return _rounded(left_value - right_value)


def _select_fold_scenario(rows: list[Mapping[str, Any]], protocol: Mapping[str, Any]) -> str:
    production = next(row for row in rows if row["scenario"] == "production_policy")
    candidates = [
        row for row in rows
        if row["scenario"] != "production_policy"
        and _recommendation(row, production, protocol)["status"] == "candidate"
    ]
    if not candidates:
        return "production_policy"
    return min(candidates, key=lambda row: (-float(row["mean_directional_return_fraction"]), float(row["ideas_per_observed_day"]), row["scenario"]))["scenario"]


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
        key = str(
            row.get("candidate_id")
            or row.get("idea_id")
            or row.get("representative_candidate_id")
            or ""
        )
        if key:
            result[key] = row
    return result


def _directional_return(idea: Mapping[str, Any], outcomes: Mapping[str, Mapping[str, Any]]) -> float | None:
    outcome = outcomes.get(str(idea.get("candidate_id") or ""))
    if not outcome or str(outcome.get("outcome_status") or outcome.get("status") or "") not in {"matured", "complete"}:
        return None
    for field in (
        "primary_directional_return_fraction",
        "directional_return_fraction",
        "primary_direction_adjusted_return",
        "primary_return_fraction",
        "primary_horizon_return",
        "return_3d_fraction",
    ):
        value = _finite(outcome.get(field))
        if value is not None:
            if field in {
                "primary_directional_return_fraction",
                "directional_return_fraction",
                "primary_direction_adjusted_return",
            }:
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


def _scenario_expiry_values(
    idea: Mapping[str, Any],
    original: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    cap_requested: bool,
) -> dict[str, Any]:
    observed = _utc(str(idea.get("observed_at") or ""))
    original_expiry = _optional_utc(original.get("expires_at"))
    shadow_expiry = _optional_utc(projection.get("expires_at"))
    if original_expiry is not None and original_expiry <= observed:
        raise ValueError("shadow-policy canonical expiry invalid")
    if shadow_expiry is not None and shadow_expiry <= observed:
        raise ValueError("shadow-policy expiry invalid")
    changed = bool(
        cap_requested
        and shadow_expiry is not None
        and (original_expiry is None or shadow_expiry < original_expiry)
    )
    return {
        "original_expires_at": (
            original_expiry.isoformat() if original_expiry is not None else None
        ),
        "shadow_expires_at": (
            shadow_expiry.isoformat() if shadow_expiry is not None else None
        ),
        "original_operator_lifetime_hours": (
            _rounded((original_expiry - observed).total_seconds() / 3600.0)
            if original_expiry is not None
            else None
        ),
        "shadow_operator_lifetime_hours": (
            _rounded((shadow_expiry - observed).total_seconds() / 3600.0)
            if shadow_expiry is not None
            else None
        ),
        "expiry_policy_changed": changed,
    }


def _scenario_directional_return(
    idea: Mapping[str, Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    primary_return: float | None,
    shadow_expires_at: Any,
    expiry_policy_changed: bool,
) -> tuple[float | None, str]:
    if not expiry_policy_changed:
        return primary_return, "primary_horizon"
    expiry = _optional_utc(shadow_expires_at)
    if expiry is None:
        raise ValueError("shadow-policy expiry missing after cap")
    outcome = outcomes.get(str(idea.get("candidate_id") or ""))
    if not isinstance(outcome, Mapping):
        return None, "shadow_expiry_outcome_unavailable"
    horizons = outcome.get("horizons")
    if isinstance(horizons, Mapping):
        for horizon in horizons.values():
            if not isinstance(horizon, Mapping):
                continue
            due = _optional_utc(horizon.get("due_at"))
            if due != expiry or str(horizon.get("maturity_status") or "") not in {
                "matured",
                "complete",
            }:
                continue
            adjusted = _finite(horizon.get("direction_adjusted_return_fraction"))
            if adjusted is not None:
                return adjusted, "shadow_expiry_exact_horizon"
            raw = _finite(horizon.get("raw_return_fraction"))
            if raw is not None:
                return (
                    _direction_adjusted(idea, raw),
                    "shadow_expiry_exact_horizon",
                )
    expiry_row = outcome.get("expiry")
    if isinstance(expiry_row, Mapping):
        recorded_expiry = _optional_utc(expiry_row.get("expires_at"))
        adjusted = _finite(
            expiry_row.get("direction_adjusted_return_at_expiry_fraction")
        )
        if recorded_expiry == expiry and adjusted is not None:
            return adjusted, "shadow_expiry_exact_assessment"
    return None, "shadow_expiry_outcome_unavailable"


def _direction_adjusted(idea: Mapping[str, Any], value: float) -> float:
    bias = str(decision_model_values(idea).get("directional_bias") or "long")
    return -value if bias in {"risk", "fade_short_review"} else value


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


def _observation_days_by_partition(
    supplied: Mapping[str, Iterable[str]] | None,
    *,
    partitions: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
    protocol: Mapping[str, Any],
) -> tuple[dict[str, set[str]], str]:
    selected = tuple(partitions)
    active_by_partition: dict[str, set[str]] = {name: set() for name in selected}
    for row in rows:
        partition = str(row.get("replay_partition") or row.get("partition") or "")
        if partition in active_by_partition:
            active_by_partition[partition].add(
                _utc(str(row.get("observed_at") or "")).date().isoformat()
            )
    if supplied is None:
        return active_by_partition, "fallback_episode_active_utc_days_only"
    output: dict[str, set[str]] = {}
    for partition in selected:
        if partition not in supplied:
            raise ValueError("selected_observation_days_partition_missing")
        days = {_normalize_utc_day(value) for value in supplied[partition]}
        start = _partition_start(protocol, partition).date()
        end = _partition_end(protocol, partition).date()
        if any(not (start <= datetime.strptime(day, "%Y-%m-%d").date() < end) for day in days):
            raise ValueError("selected_observation_day_outside_partition")
        if not active_by_partition[partition] <= days:
            raise ValueError("idea_active_day_outside_selected_observation_days")
        output[partition] = days
    return output, "exact_selected_observation_utc_days"


def _idea_days(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        _utc(str(row.get("observed_at") or "")).date().isoformat()
        for row in rows
    }


def _normalize_utc_day(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) == 10:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise ValueError("selected_observation_day_invalid") from exc
    try:
        return _utc(raw).date().isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("selected_observation_day_invalid") from exc


def _days_in_window(
    days: Iterable[str], start: datetime, end: datetime
) -> set[str]:
    return {
        day
        for day in days
        if start <= _utc(f"{day}T00:00:00Z") < end
    }


def _days_digest(days: Iterable[str]) -> str:
    return empirical_validation_protocol.selected_observation_days_sha256(days)


def _empty_walk_forward(
    protocol: Mapping[str, Any],
    *,
    selected_observation_days: set[str],
    observed_day_denominator_basis: str,
) -> dict[str, Any]:
    return {
        "schema_id": WALK_FORWARD_SCHEMA_ID,
        "schema_version": 1,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "selection_partitions": ["development", "validation"],
        "selected_observation_day_count": len(selected_observation_days),
        "idea_active_day_count": 0,
        "observed_day_denominator_basis": observed_day_denominator_basis,
        "selected_observation_days_sha256": _days_digest(
            selected_observation_days
        ),
        "final_test_accessed": False,
        "folds": [],
        "fold_count": 0,
        "nonempty_fold_count": 0,
        "outcome_evaluable_fold_count": 0,
        "minimum_fold_count": int(protocol["walk_forward"]["minimum_folds"]),
        "outcome_purge_rule": protocol["walk_forward"]["outcome_purge_rule"],
        "partial_test_fold_policy": protocol["walk_forward"][
            "partial_test_fold_policy"
        ],
        "omitted_partial_test_window": None,
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


def _scenario_definitions(protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = protocol.get("shadow_scenarios")
    if not isinstance(rows, list) or not rows:
        raise ValueError("empirical shadow scenarios invalid")
    try:
        copied = json.loads(
            json.dumps(
                rows,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("empirical shadow scenarios invalid") from exc
    if not isinstance(copied, list) or any(
        not isinstance(row, dict) or not str(row.get("name") or "")
        for row in copied
    ):
        raise ValueError("empirical shadow scenarios invalid")
    names = [str(row["name"]) for row in copied]
    if len(names) != len(set(names)) or "production_policy" not in names:
        raise ValueError("empirical shadow scenarios invalid")
    return copied


def _scenario_definitions_from_simulation(
    simulation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = simulation.get("frozen_scenarios")
    if not isinstance(rows, list):
        raise ValueError("recommendation simulation scenarios invalid")
    current = _scenario_definitions(empirical_validation_protocol.protocol_values())
    if rows != current:
        raise ValueError("recommendation simulation scenarios invalid")
    expected_digest = _sha256(_canonical_bytes(rows))
    if simulation.get("scenario_set_sha256") != expected_digest:
        raise ValueError("recommendation simulation scenario digest invalid")
    return current


def _selection_run_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "selection_run_fingerprint",
        "input_sha256",
        "code_sha256",
        "configuration_sha256",
        "mode",
        "simulation_artifact",
    }
    if set(value) != fields:
        raise ValueError("selection run binding invalid")
    for field in (
        "selection_run_fingerprint",
        "input_sha256",
        "code_sha256",
        "configuration_sha256",
    ):
        if not _is_sha256(value.get(field)):
            raise ValueError("selection run binding invalid")
    mode = str(value.get("mode") or "")
    if mode not in {"medium", "full"}:
        raise ValueError("selection run binding invalid")
    if value.get("simulation_artifact") != "shadow_policy_simulation.json":
        raise ValueError("selection run binding invalid")
    return {
        "selection_run_fingerprint": str(value["selection_run_fingerprint"]),
        "input_sha256": str(value["input_sha256"]),
        "code_sha256": str(value["code_sha256"]),
        "configuration_sha256": str(value["configuration_sha256"]),
        "mode": mode,
        "simulation_artifact": "shadow_policy_simulation.json",
    }


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp timezone required")
    return parsed.astimezone(timezone.utc)


def _optional_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return _utc(str(value))


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rounded(value: float) -> float:
    return round(float(value), 8)


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "evaluate_sealed_final_test",
    "freeze_recommendation_set",
    "simulate_shadow_policies",
    "validate_recommendation_seal",
    "walk_forward_evaluation",
]
