"""Closed Decision-v2 outcome scorecard over frozen anomaly episodes.

The first member of each fixed-start episode is the only representative.  This
module never reselects a representative from outcome availability, never uses
legacy Catalyst Radar lanes to grade direction, and never changes runtime
routing, scores, calibration, or thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from ..radar.decision_model_surfaces import decision_model_values
from ..radar.decision_models import decision_score_cohort_values
from . import anomaly_episode_shadow, outcome_eligibility
from .decision_episode_scorecard_contract import (
    materialize_outcome_validation_bindings as _materialize_outcome_validation_bindings,
    materialize_source_artifact_bindings as _materialize_source_artifact_bindings,
    outcome_validation_binding_errors as _outcome_validation_binding_errors,
    primary_outcome_state as _primary_outcome_state,
    representative_candidate_binding_errors as _representative_candidate_binding_errors,
    source_artifact_binding_errors as _source_artifact_binding_errors,
)


SCHEMA_ID = "event_alpha.decision_v2_episode_outcome_scorecard"
REPRESENTATIVE_SCHEMA_ID = (
    "event_alpha.decision_v2_episode_outcome_representative"
)
SCHEMA_VERSION = 1
METHOD = "frozen_primary_episode_representative_outcome_scorecard"
OUTCOME_STATES = (
    "matured",
    "not_due",
    "due_missing_price",
    "contract_excluded",
)
DIRECTION_ALIGNMENTS = (
    "aligned",
    "opposed",
    "flat",
    "non_directional",
    "not_evaluated",
)
EXCLUSIVE_COHORT_FIELDS = (
    "primary_thesis_origin",
    "radar_route",
    "directional_bias",
    "actionability_score_cohort",
    "evidence_confidence_score_cohort",
    "risk_score_cohort",
    "catalyst_status",
    "timing_state",
    "market_phase",
)
POLICY_CONCLUSION = "insufficient_for_policy_change"
POLICY_CONCLUSION_REASONS = (
    "matched_non_idea_controls_unavailable",
    "dependent_data_uncertainty_not_estimated",
    "out_of_sample_validation_unavailable",
)
_FALSE_POLICY = {
    "routing_eligible": False,
    "priority_eligible": False,
    "decision_score_eligible": False,
    "score_adjustment_eligible": False,
    "calibration_eligible": False,
    "threshold_change_eligible": False,
    "policy_change_eligible": False,
    "auto_apply": False,
}
_ZERO_SAFETY = {
    "provider_calls": 0,
    "writes": 0,
    "routing_changes": 0,
    "priority_changes": 0,
    "decision_score_changes": 0,
    "score_adjustments": 0,
    "calibration_changes": 0,
    "threshold_changes": 0,
    "authority_changes": 0,
}
_ROOT_KEYS = {
    "schema_id",
    "schema_version",
    "method",
    "status",
    "evaluated_at",
    "source_episode_schema_id",
    "source_episode_schema_version",
    "source_episode_contract_digest",
    "source_episode_input_binding_digest",
    "primary_episode_count",
    "primary_repeat_member_count",
    "candidate_rows_supplied",
    "core_rows_supplied",
    "outcome_rows_supplied",
    "source_artifact_binding_count",
    "source_artifact_bindings",
    "source_artifact_binding_digest",
    "outcome_validation_binding_count",
    "outcome_validation_bindings",
    "outcome_validation_binding_digest",
    "candidate_input_digest",
    "core_input_digest",
    "outcome_input_digest",
    "input_binding_digest",
    "representative_count",
    "matured_episode_count",
    "scoreable_directional_episode_count",
    "outcome_state_counts",
    "direction_alignment_counts",
    "outcome_cohort_persistence_status_counts",
    "representatives",
    "exclusive_cohorts",
    "nonexclusive_thesis_origin_cohorts",
    "contract_exclusion_reason_counts",
    "alignment_denominator",
    "policy_conclusion",
    "policy_conclusion_reasons",
    "statistical_independence_claim",
    "cross_asset_independence_claim",
    "matched_control_available",
    "dependent_uncertainty_estimated",
    "out_of_sample_validation_available",
    "research_only",
    "contract_digest",
    *_FALSE_POLICY,
    *_ZERO_SAFETY,
}
_REPRESENTATIVE_KEYS = {
    "schema_id",
    "schema_version",
    "episode_id",
    "episode_digest",
    "artifact_namespace",
    "run_id",
    "candidate_id",
    "core_opportunity_id",
    "outcome_identity_key",
    "canonical_asset_id",
    "observed_at",
    "candidate_row_digest",
    "core_row_digest",
    "outcome_row_digest",
    "decision_projection_digest",
    "primary_horizon",
    "primary_due_at",
    "primary_horizon_return",
    "outcome_state",
    "direction_alignment",
    "primary_thesis_origin",
    "thesis_origins",
    "radar_route",
    "directional_bias",
    "actionability_score",
    "actionability_score_cohort",
    "evidence_confidence_score",
    "evidence_confidence_score_cohort",
    "risk_score",
    "risk_score_cohort",
    "catalyst_status",
    "timing_state",
    "market_phase",
    "outcome_cohort_persistence_status",
    "outcome_cohort_persistence_reason",
    "canonical_score_cohorts",
    "declared_outcome_cohorts",
    "contract_exclusion_reasons",
    "representative_digest",
}
_COHORT_ROW_KEYS = {
    "name",
    "episode_count",
    "outcome_state_counts",
    "matured_episode_count",
    "direction_alignment_counts",
    "scoreable_directional_episode_count",
    "aligned_episode_count",
    "alignment_rate",
    "mean_primary_horizon_return",
    "median_primary_horizon_return",
}
_DIRECTION_SIGN = {
    "long": 1,
    "fade_short_review": -1,
    "risk": -1,
}


def build_decision_episode_scorecard(
    episode_value: Mapping[str, Any],
    candidate_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    outcome_rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: datetime | str,
    source_artifact_bindings: Iterable[Mapping[str, Any]],
    outcome_validation_bindings: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a pure scorecard from one closed episode value and exact rows."""

    episode_errors = anomaly_episode_shadow.validate_contract(episode_value)
    if episode_errors:
        raise ValueError("invalid_episode_contract:" + ";".join(episode_errors))
    evaluated = _required_utc(evaluated_at)
    candidates = _materialize_rows(candidate_rows)
    cores = _materialize_rows(core_rows)
    outcomes = _materialize_rows(outcome_rows)
    artifact_bindings = _materialize_source_artifact_bindings(
        source_artifact_bindings
    )
    validation_bindings = _materialize_outcome_validation_bindings(
        outcome_validation_bindings
    )
    binding_errors = _source_artifact_binding_errors(
        artifact_bindings,
        row_counts={
            "candidate": len(candidates),
            "core": len(cores),
            "outcome": len(outcomes),
        },
    )
    if binding_errors:
        raise ValueError("invalid_source_artifact_bindings:" + ";".join(binding_errors))
    validation_errors = _outcome_validation_binding_errors(validation_bindings)
    if validation_errors or len(validation_bindings) != len(outcomes):
        reasons = list(validation_errors)
        if len(validation_bindings) != len(outcomes):
            reasons.append("outcome_validation_binding_count_mismatch")
        raise ValueError("invalid_outcome_validation_bindings:" + ";".join(reasons))
    representatives = [
        _representative_result(
            episode,
            candidates=candidates,
            cores=cores,
            outcomes=outcomes,
            outcome_validations=validation_bindings,
            evaluated_at=evaluated,
        )
        for episode in episode_value["episodes"]
    ]
    representatives.sort(key=_representative_sort_key)
    state_counts = _closed_counts(
        (row["outcome_state"] for row in representatives), OUTCOME_STATES
    )
    alignment_counts = _closed_counts(
        (row["direction_alignment"] for row in representatives),
        DIRECTION_ALIGNMENTS,
    )
    persistence_counts = dict(sorted(Counter(
        str(row["outcome_cohort_persistence_status"])
        for row in representatives
    ).items()))
    input_values = {
        "source_episode_contract_digest": episode_value["contract_digest"],
        "source_episode_input_binding_digest": episode_value[
            "input_binding_digest"
        ],
        "candidate_input_digest": _rows_digest(candidates),
        "core_input_digest": _rows_digest(cores),
        "outcome_input_digest": _rows_digest(outcomes),
        "source_artifact_binding_digest": _digest(artifact_bindings),
        "outcome_validation_binding_digest": _digest(validation_bindings),
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "status": _status(representatives),
        "evaluated_at": evaluated.isoformat(),
        "source_episode_schema_id": episode_value["schema_id"],
        "source_episode_schema_version": episode_value["schema_version"],
        **input_values,
        "primary_episode_count": episode_value["primary_episode_count"],
        "primary_repeat_member_count": episode_value[
            "primary_repeat_member_count"
        ],
        "candidate_rows_supplied": len(candidates),
        "core_rows_supplied": len(cores),
        "outcome_rows_supplied": len(outcomes),
        "source_artifact_binding_count": len(artifact_bindings),
        "source_artifact_bindings": artifact_bindings,
        "outcome_validation_binding_count": len(validation_bindings),
        "outcome_validation_bindings": validation_bindings,
        "input_binding_digest": _digest(input_values),
        "representative_count": len(representatives),
        "matured_episode_count": state_counts["matured"],
        "scoreable_directional_episode_count": sum(
            alignment_counts[key] for key in ("aligned", "opposed", "flat")
        ),
        "outcome_state_counts": state_counts,
        "direction_alignment_counts": alignment_counts,
        "outcome_cohort_persistence_status_counts": persistence_counts,
        "representatives": representatives,
        "exclusive_cohorts": _exclusive_cohorts(representatives),
        "nonexclusive_thesis_origin_cohorts": _origin_cohorts(representatives),
        "contract_exclusion_reason_counts": dict(sorted(Counter(
            reason
            for row in representatives
            for reason in row["contract_exclusion_reasons"]
        ).items())),
        "alignment_denominator": "aligned_plus_opposed_plus_flat",
        "policy_conclusion": POLICY_CONCLUSION,
        "policy_conclusion_reasons": list(POLICY_CONCLUSION_REASONS),
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "matched_control_available": False,
        "dependent_uncertainty_estimated": False,
        "out_of_sample_validation_available": False,
        "research_only": True,
        **_FALSE_POLICY,
        **_ZERO_SAFETY,
    }
    payload["contract_digest"] = _digest(payload)
    errors = validate_contract(
        payload,
        episode_value=episode_value,
        candidate_rows=candidates,
    )
    if errors:
        raise RuntimeError("decision_episode_scorecard_invalid:" + ";".join(errors))
    return payload


def validate_contract(
    payload: Mapping[str, Any],
    *,
    episode_value: Mapping[str, Any] | None = None,
    candidate_rows: Iterable[Mapping[str, Any]] | None = None,
) -> list[str]:
    """Validate exact keys, closures, canonical grouping, and all digests."""

    if not isinstance(payload, Mapping):
        return ["contract_not_mapping"]
    errors: list[str] = []
    _check_exact_keys(payload, _ROOT_KEYS, "contract", errors)
    for key, expected in {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "alignment_denominator": "aligned_plus_opposed_plus_flat",
        "policy_conclusion": POLICY_CONCLUSION,
        "policy_conclusion_reasons": list(POLICY_CONCLUSION_REASONS),
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "matched_control_available": False,
        "dependent_uncertainty_estimated": False,
        "out_of_sample_validation_available": False,
        "research_only": True,
        **_FALSE_POLICY,
        **_ZERO_SAFETY,
    }.items():
        if payload.get(key) != expected or type(payload.get(key)) is not type(expected):
            errors.append(f"invalid_{key}")
    evaluated_at: datetime | None = None
    try:
        evaluated_at = _required_utc(payload.get("evaluated_at"))
    except (TypeError, ValueError):
        errors.append("invalid_evaluated_at")
    representatives = payload.get("representatives")
    if type(representatives) is not list:
        representatives = []
        errors.append("representatives_not_list")
    for index, row in enumerate(representatives):
        errors.extend(
            f"representative_{index}:{error}"
            for error in _validate_representative(
                row,
                evaluated_at=evaluated_at,
            )
        )
    if representatives != sorted(representatives, key=_representative_sort_key):
        errors.append("representatives_not_canonically_ordered")
    errors.extend(_validate_counts(payload, representatives))
    expected_exclusive = _exclusive_cohorts(representatives)
    if payload.get("exclusive_cohorts") != expected_exclusive:
        errors.append("exclusive_cohorts_mismatch")
    if payload.get("nonexclusive_thesis_origin_cohorts") != _origin_cohorts(
        representatives
    ):
        errors.append("nonexclusive_thesis_origin_cohorts_mismatch")
    expected_reasons = dict(sorted(Counter(
        reason
        for row in representatives
        for reason in row.get("contract_exclusion_reasons", ())
    ).items()))
    if payload.get("contract_exclusion_reason_counts") != expected_reasons:
        errors.append("contract_exclusion_reason_counts_mismatch")
    errors.extend(_validate_input_binding(payload, episode_value=episode_value))
    if candidate_rows is not None:
        errors.extend(_representative_candidate_binding_errors(payload, candidate_rows))
    values = dict(payload)
    values.pop("contract_digest", None)
    if not _digest_matches(payload.get("contract_digest"), values):
        errors.append("invalid_contract_digest")
    return sorted(set(errors))


def _representative_result(
    episode: Mapping[str, Any],
    *,
    candidates: Sequence[Mapping[str, Any]],
    cores: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
    outcome_validations: Sequence[Mapping[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    ref = episode["representative"]
    reasons: set[str] = set()
    candidate_matches = [row for row in candidates if _candidate_claims_ref(row, ref)]
    candidate = candidate_matches[0] if len(candidate_matches) == 1 else None
    if not candidate_matches:
        reasons.add("candidate_authority_missing")
    elif len(candidate_matches) > 1:
        reasons.add("candidate_authority_ambiguous")
    projection: dict[str, Any] = {}
    if candidate is not None:
        if not outcome_eligibility.valid_candidate_authority(candidate):
            reasons.add("candidate_authority_invalid")
        projection = decision_model_values(candidate)
        if not projection:
            reasons.add("candidate_decision_projection_invalid")
        elif not _projection_cohorts_valid(projection):
            reasons.add("candidate_decision_cohort_invalid")
    core = None
    core_matches: list[Mapping[str, Any]] = []
    if candidate is not None:
        core_matches = [row for row in cores if _core_claims_candidate(row, candidate)]
        core = core_matches[0] if len(core_matches) == 1 else None
        if not core_matches:
            if any(
                _core_context_claims_candidate(row, candidate)
                for row in cores
            ):
                reasons.add("core_integrated_candidate_id_mismatch")
            else:
                reasons.add("core_authority_missing")
        elif len(core_matches) > 1:
            reasons.add("core_authority_ambiguous")
        elif not outcome_eligibility.valid_core_authority(core):
            reasons.add("core_authority_invalid")
        elif projection and decision_model_values(core) != projection:
            reasons.add("core_decision_projection_mismatch")
    outcome_matches = [row for row in outcomes if _outcome_claims_ref(row, ref)]
    outcome = outcome_matches[0] if len(outcome_matches) == 1 else None
    if not outcome_matches:
        reasons.add("outcome_authority_missing")
    elif len(outcome_matches) > 1:
        reasons.add("outcome_authority_ambiguous")
    validation_matches = [
        row for row in outcome_validations if _validation_claims_ref(row, ref)
    ]
    outcome_validation = (
        validation_matches[0] if len(validation_matches) == 1 else None
    )
    if outcome is not None:
        if not validation_matches:
            reasons.add("outcome_validation_authority_missing")
        elif len(validation_matches) > 1:
            reasons.add("outcome_validation_authority_ambiguous")

    cohort_status = "unavailable"
    cohort_reason = "outcome_authority_unavailable"
    declared_cohorts = _declared_cohorts(outcome)
    primary_horizon = primary_due_at = primary_return = None
    state = "contract_excluded"
    if (
        outcome is not None
        and outcome_validation is not None
        and candidate is not None
        and projection
    ):
        outcome_reasons, cohort_status, cohort_reason = _outcome_contract_reasons(
            outcome,
            candidate=candidate,
            projection=projection,
            validation=outcome_validation,
            evaluated_at=evaluated_at,
        )
        reasons.update(outcome_reasons)
        if not reasons:
            state, primary_horizon, primary_due_at, primary_return = (
                _primary_outcome_state(outcome, evaluated_at=evaluated_at)
            )
            if state == "contract_excluded":
                reasons.add("primary_outcome_state_invalid")
    alignment = _direction_alignment(
        projection.get("directional_bias"),
        primary_return if state == "matured" else None,
    )
    canonical = _canonical_projection_values(projection)
    row: dict[str, Any] = {
        "schema_id": REPRESENTATIVE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "episode_id": episode["episode_id"],
        "episode_digest": episode["episode_digest"],
        "artifact_namespace": ref["artifact_namespace"],
        "run_id": ref["run_id"],
        "candidate_id": ref["candidate_id"],
        "core_opportunity_id": (
            candidate.get("core_opportunity_id") if candidate is not None else None
        ),
        "outcome_identity_key": ref["outcome_identity_key"],
        "canonical_asset_id": ref["canonical_asset_id"],
        "observed_at": ref["observed_at"],
        "candidate_row_digest": _digest(candidate) if candidate is not None else None,
        "core_row_digest": _digest(core) if core is not None else None,
        "outcome_row_digest": _digest(outcome) if outcome is not None else None,
        "decision_projection_digest": _digest(projection) if projection else None,
        "primary_horizon": primary_horizon,
        "primary_due_at": primary_due_at,
        "primary_horizon_return": primary_return,
        "outcome_state": state,
        "direction_alignment": alignment,
        **canonical,
        "outcome_cohort_persistence_status": cohort_status,
        "outcome_cohort_persistence_reason": cohort_reason,
        "canonical_score_cohorts": {
            field: canonical[field]
            for field in (
                "actionability_score_cohort",
                "evidence_confidence_score_cohort",
                "risk_score_cohort",
            )
        },
        "declared_outcome_cohorts": declared_cohorts,
        "contract_exclusion_reasons": sorted(reasons),
    }
    row["representative_digest"] = _digest(row)
    return row


def _outcome_contract_reasons(
    outcome: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    projection: Mapping[str, Any],
    validation: Mapping[str, Any],
    evaluated_at: datetime,
) -> tuple[set[str], str, str | None]:
    reasons: set[str] = set()
    if outcome.get("row_type") != "event_integrated_radar_outcome":
        reasons.add("outcome_authority_invalid")
    if any((
        outcome.get("campaign_outcome_ledger") is not True,
        outcome.get("measurement_program")
        != "decision_radar_live_observation_campaign_v2",
        outcome.get("source_artifact_namespace")
        != candidate.get("artifact_namespace"),
        outcome.get("campaign_calibration_scope") != "candidate_core_joined",
        outcome.get("campaign_outcome_authority") != "candidate_core_join",
        outcome.get("campaign_core_opportunity_present") is not True,
    )):
        reasons.add("campaign_outcome_contract_invalid")
    if outcome_eligibility.canonical_join_identity(outcome) != (
        outcome_eligibility.canonical_join_identity(candidate)
    ):
        reasons.add("outcome_identity_mismatch")
    expected_key = outcome_eligibility.build_outcome_identity_fields(candidate)[
        "outcome_identity_key"
    ]
    if outcome.get("outcome_identity_key") != expected_key:
        reasons.add("outcome_identity_mismatch")
    if decision_model_values(outcome) != dict(projection):
        reasons.add("outcome_decision_projection_mismatch")
    if outcome_eligibility.validate_contract(outcome):
        reasons.add("outcome_contract_invalid")
    if "historical_price_recovery" in (
        outcome_eligibility.calibration_ineligibility_reasons(outcome)
    ):
        reasons.add("historical_price_recovery_not_point_in_time")
    persisted_evaluated = outcome_eligibility.parse_aware_time(
        outcome.get("outcome_evaluated_at")
    )
    if persisted_evaluated is None or persisted_evaluated > evaluated_at:
        reasons.add("outcome_evaluation_clock_invalid")
    if not _outcome_safety_valid(outcome):
        reasons.add("outcome_safety_invalid")
    cohort_status = str(validation.get("score_cohort_status") or "invalid")
    raw_reason = validation.get("score_cohort_reason")
    cohort_reason = raw_reason if type(raw_reason) is str else None
    expected_cohorts = decision_score_cohort_values(projection)
    if any((
        validation.get("outcome_row_digest") != _digest(outcome),
        validation.get("valid") is not True,
        validation.get("reasons") != [],
        expected_cohorts is None,
        validation.get("canonical_score_cohorts") != expected_cohorts,
        cohort_status not in {
            "canonical_exact",
            "legacy_unversioned_exact",
            "legacy_null_derived_from_canonical_scores",
        },
    )):
        reasons.add("campaign_outcome_validation_invalid")
    if cohort_status == "invalid":
        reasons.add(cohort_reason or "decision_score_cohort_contract_invalid")
    return reasons, cohort_status, cohort_reason


def _canonical_projection_values(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not projection:
        return {
            "primary_thesis_origin": None,
            "thesis_origins": [],
            "radar_route": None,
            "directional_bias": None,
            "actionability_score": None,
            "actionability_score_cohort": "unknown",
            "evidence_confidence_score": None,
            "evidence_confidence_score_cohort": "unknown",
            "risk_score": None,
            "risk_score_cohort": "unknown",
            "catalyst_status": None,
            "timing_state": None,
            "market_phase": None,
        }
    actionability = _finite_score(projection.get("actionability_score"))
    evidence = _finite_score(projection.get("evidence_confidence_score"))
    risk = _finite_score(projection.get("risk_score"))
    score_cohorts = decision_score_cohort_values(projection) or {}
    return {
        "primary_thesis_origin": projection.get("primary_thesis_origin"),
        "thesis_origins": list(projection.get("thesis_origins") or ()),
        "radar_route": projection.get("radar_route"),
        "directional_bias": projection.get("directional_bias"),
        "actionability_score": actionability,
        "actionability_score_cohort": score_cohorts.get(
            "actionability_score_cohort",
            "unknown",
        ),
        "evidence_confidence_score": evidence,
        "evidence_confidence_score_cohort": score_cohorts.get(
            "evidence_confidence_score_cohort",
            "unknown",
        ),
        "risk_score": risk,
        "risk_score_cohort": score_cohorts.get("risk_score_cohort", "unknown"),
        "catalyst_status": projection.get("catalyst_status"),
        "timing_state": projection.get("timing_state"),
        "market_phase": projection.get("market_phase"),
    }


def _projection_cohorts_valid(projection: Mapping[str, Any]) -> bool:
    values = _canonical_projection_values(projection)
    return all(
        values[field] not in (None, "", "unknown")
        for field in (
            "actionability_score_cohort",
            "evidence_confidence_score_cohort",
            "risk_score_cohort",
        )
    )


def _declared_cohorts(outcome: Mapping[str, Any] | None) -> dict[str, Any]:
    values = {
        field: outcome.get(field) if outcome is not None else None
        for field in (
            "actionability_score_cohort",
            "evidence_confidence_score_cohort",
            "risk_score_cohort",
        )
    }
    values["decision_score_cohort_contract_version"] = (
        outcome.get("decision_score_cohort_contract_version")
        if outcome is not None
        else None
    )
    return values


def _direction_alignment(bias: Any, value: float | None) -> str:
    if value is None:
        return "not_evaluated"
    if bias == "neutral":
        return "non_directional"
    sign = _DIRECTION_SIGN.get(bias)
    if sign is None:
        return "not_evaluated"
    if value == 0.0:
        return "flat"
    return "aligned" if value * sign > 0 else "opposed"


def _exclusive_cohorts(
    representatives: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        field: _cohort_rows(_group_by_field(representatives, field))
        for field in EXCLUSIVE_COHORT_FIELDS
    }


def _origin_cohorts(
    representatives: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in representatives:
        origins = row.get("thesis_origins")
        names = (
            sorted(set(origins))
            if type(origins) is list and origins
            else ["unknown"]
        )
        for name in names:
            groups[str(name)].append(row)
    return _cohort_rows(groups)


def _group_by_field(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        groups[str(value) if value not in (None, "") else "unknown"].append(row)
    return groups


def _cohort_rows(
    groups: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    return [_cohort_row(name, groups[name]) for name in sorted(groups)]


def _cohort_row(name: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    states = _closed_counts((row.get("outcome_state") for row in rows), OUTCOME_STATES)
    alignments = _closed_counts(
        (row.get("direction_alignment") for row in rows), DIRECTION_ALIGNMENTS
    )
    scoreable = sum(alignments[key] for key in ("aligned", "opposed", "flat"))
    values = sorted(
        value
        for row in rows
        if row.get("outcome_state") == "matured"
        and (value := _finite_number(row.get("primary_horizon_return"))) is not None
    )
    return {
        "name": name,
        "episode_count": len(rows),
        "outcome_state_counts": states,
        "matured_episode_count": states["matured"],
        "direction_alignment_counts": alignments,
        "scoreable_directional_episode_count": scoreable,
        "aligned_episode_count": alignments["aligned"],
        "alignment_rate": alignments["aligned"] / scoreable if scoreable else None,
        "mean_primary_horizon_return": sum(values) / len(values) if values else None,
        "median_primary_horizon_return": statistics.median(values) if values else None,
    }


def _candidate_claims_ref(row: Mapping[str, Any], ref: Mapping[str, Any]) -> bool:
    if any(
        row.get(field) != ref.get(field)
        for field in ("artifact_namespace", "run_id", "candidate_id", "observed_at")
    ):
        return False
    if row.get("canonical_asset_id") != ref.get("canonical_asset_id"):
        return False
    try:
        key = outcome_eligibility.build_outcome_identity_fields(row)[
            "outcome_identity_key"
        ]
    except (KeyError, TypeError, ValueError):
        return False
    return key == ref.get("outcome_identity_key")


def _core_claims_candidate(
    row: Mapping[str, Any], candidate: Mapping[str, Any]
) -> bool:
    return (
        _core_context_claims_candidate(row, candidate)
        and row.get("integrated_candidate_id") == candidate.get("candidate_id")
    )


def _core_context_claims_candidate(
    row: Mapping[str, Any], candidate: Mapping[str, Any]
) -> bool:
    return all(
        row.get(field) == candidate.get(field)
        for field in (
            "core_opportunity_id",
            "run_id",
            "profile",
            "artifact_namespace",
        )
    )


def _outcome_claims_ref(row: Mapping[str, Any], ref: Mapping[str, Any]) -> bool:
    return (
        row.get("artifact_namespace") == ref.get("artifact_namespace")
        and row.get("run_id") == ref.get("run_id")
        and row.get("candidate_id") == ref.get("candidate_id")
        and row.get("observed_at") == ref.get("observed_at")
        and row.get("outcome_identity_key") == ref.get("outcome_identity_key")
    )


def _validation_claims_ref(
    row: Mapping[str, Any], ref: Mapping[str, Any]
) -> bool:
    return (
        row.get("artifact_namespace") == ref.get("artifact_namespace")
        and row.get("candidate_id") == ref.get("candidate_id")
        and row.get("outcome_identity_key") == ref.get("outcome_identity_key")
    )


def _outcome_safety_valid(row: Mapping[str, Any]) -> bool:
    return (
        row.get("research_only") is True
        and row.get("no_send_rehearsal") is True
        and all(
            row.get(field) is False
            for field in (
                "sent",
                "trade_created",
                "paper_trade_created",
                "normal_rsi_signal_written",
                "triggered_fade_created",
            )
        )
    )


def _validate_representative(
    row: Any,
    *,
    evaluated_at: datetime | None,
) -> list[str]:
    if type(row) is not dict:
        return ["not_object"]
    errors: list[str] = []
    _check_exact_keys(row, _REPRESENTATIVE_KEYS, "representative", errors)
    if row.get("schema_id") != REPRESENTATIVE_SCHEMA_ID:
        errors.append("invalid_schema_id")
    if row.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if row.get("outcome_state") not in OUTCOME_STATES:
        errors.append("invalid_outcome_state")
    if row.get("direction_alignment") not in DIRECTION_ALIGNMENTS:
        errors.append("invalid_direction_alignment")
    score_cohorts = decision_score_cohort_values(row)
    if score_cohorts is None:
        errors.append("invalid_canonical_scores")
    else:
        for field, expected in score_cohorts.items():
            if row.get(field) != expected:
                errors.append(f"{field}_mismatch")
    state = row.get("outcome_state")
    primary = row.get("primary_horizon")
    due = outcome_eligibility.parse_aware_time(row.get("primary_due_at"))
    primary_return = _finite_number(row.get("primary_horizon_return"))
    if state in {"matured", "not_due", "due_missing_price"}:
        if primary not in outcome_eligibility.OUTCOME_HORIZONS:
            errors.append("invalid_primary_horizon")
        if due is None:
            errors.append("invalid_primary_due_at")
    if state == "matured":
        if primary_return is None:
            errors.append("matured_primary_return_missing")
        if evaluated_at is not None and due is not None and due > evaluated_at:
            errors.append("matured_primary_due_after_evaluation")
    elif state in {"not_due", "due_missing_price", "contract_excluded"}:
        if row.get("primary_horizon_return") is not None:
            errors.append("nonmature_primary_return_present")
    if (
        state == "not_due"
        and evaluated_at is not None
        and due is not None
        and due <= evaluated_at
    ):
        errors.append("not_due_primary_is_due")
    if (
        state == "due_missing_price"
        and evaluated_at is not None
        and due is not None
        and due > evaluated_at
    ):
        errors.append("due_missing_primary_not_due")
    expected_alignment = _direction_alignment(
        row.get("directional_bias"),
        primary_return if state == "matured" else None,
    )
    if row.get("direction_alignment") != expected_alignment:
        errors.append("direction_alignment_mismatch")
    reasons = row.get("contract_exclusion_reasons")
    if type(reasons) is not list or reasons != sorted(set(reasons)):
        errors.append("invalid_contract_exclusion_reasons")
    if (row.get("outcome_state") == "contract_excluded") is not bool(reasons):
        errors.append("contract_exclusion_state_mismatch")
    for field in (
        "episode_digest",
        "outcome_identity_key",
        "candidate_row_digest",
        "core_row_digest",
        "outcome_row_digest",
        "decision_projection_digest",
    ):
        value = row.get(field)
        if value is not None and not _is_digest(value):
            errors.append(f"invalid_{field}")
    persistence_status = row.get("outcome_cohort_persistence_status")
    if persistence_status not in {
        "canonical_exact",
        "legacy_unversioned_exact",
        "legacy_null_derived_from_canonical_scores",
        "invalid",
        "unavailable",
    }:
        errors.append("invalid_outcome_cohort_persistence_status")
    persistence_reason = row.get("outcome_cohort_persistence_reason")
    if persistence_reason is not None and type(persistence_reason) is not str:
        errors.append("invalid_outcome_cohort_persistence_reason")
    canonical_cohorts = row.get("canonical_score_cohorts")
    expected_canonical = {
        field: row.get(field)
        for field in (
            "actionability_score_cohort",
            "evidence_confidence_score_cohort",
            "risk_score_cohort",
        )
    }
    if canonical_cohorts != expected_canonical:
        errors.append("canonical_score_cohorts_mismatch")
    declared = row.get("declared_outcome_cohorts")
    if not isinstance(declared, Mapping) or set(declared) != {
        "decision_score_cohort_contract_version",
        "actionability_score_cohort",
        "evidence_confidence_score_cohort",
        "risk_score_cohort",
    }:
        errors.append("invalid_declared_outcome_cohorts")
    values = dict(row)
    values.pop("representative_digest", None)
    if not _digest_matches(row.get("representative_digest"), values):
        errors.append("invalid_representative_digest")
    return errors


def _validate_counts(
    payload: Mapping[str, Any], representatives: Sequence[Mapping[str, Any]]
) -> list[str]:
    errors: list[str] = []
    count_fields = (
        "primary_episode_count",
        "primary_repeat_member_count",
        "candidate_rows_supplied",
        "core_rows_supplied",
        "outcome_rows_supplied",
        "source_artifact_binding_count",
        "outcome_validation_binding_count",
        "representative_count",
        "matured_episode_count",
        "scoreable_directional_episode_count",
    )
    for field in count_fields:
        if type(payload.get(field)) is not int or payload.get(field) < 0:
            errors.append(f"invalid_{field}")
    if payload.get("representative_count") != len(representatives):
        errors.append("representative_count_mismatch")
    if payload.get("primary_episode_count") != len(representatives):
        errors.append("primary_episode_count_mismatch")
    states = _closed_counts(
        (row.get("outcome_state") for row in representatives), OUTCOME_STATES
    )
    alignments = _closed_counts(
        (row.get("direction_alignment") for row in representatives),
        DIRECTION_ALIGNMENTS,
    )
    if payload.get("outcome_state_counts") != states:
        errors.append("outcome_state_counts_mismatch")
    if payload.get("direction_alignment_counts") != alignments:
        errors.append("direction_alignment_counts_mismatch")
    if payload.get("matured_episode_count") != states["matured"]:
        errors.append("matured_episode_count_mismatch")
    scoreable = sum(alignments[key] for key in ("aligned", "opposed", "flat"))
    if payload.get("scoreable_directional_episode_count") != scoreable:
        errors.append("scoreable_directional_episode_count_mismatch")
    persistence = dict(sorted(Counter(
        str(row.get("outcome_cohort_persistence_status"))
        for row in representatives
    ).items()))
    if payload.get("outcome_cohort_persistence_status_counts") != persistence:
        errors.append("outcome_cohort_persistence_status_counts_mismatch")
    if payload.get("status") != _status(representatives):
        errors.append("status_mismatch")
    return errors


def _validate_input_binding(
    payload: Mapping[str, Any],
    *,
    episode_value: Mapping[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    for field in (
        "source_episode_contract_digest",
        "source_episode_input_binding_digest",
        "candidate_input_digest",
        "core_input_digest",
        "outcome_input_digest",
        "source_artifact_binding_digest",
        "outcome_validation_binding_digest",
    ):
        if not _is_digest(payload.get(field)):
            errors.append(f"invalid_{field}")
    input_values = {
        field: payload.get(field)
        for field in (
            "source_episode_contract_digest",
            "source_episode_input_binding_digest",
            "candidate_input_digest",
            "core_input_digest",
            "outcome_input_digest",
            "source_artifact_binding_digest",
            "outcome_validation_binding_digest",
        )
    }
    if not _digest_matches(payload.get("input_binding_digest"), input_values):
        errors.append("input_binding_digest_mismatch")
    artifact_bindings = payload.get("source_artifact_bindings")
    if type(artifact_bindings) is not list:
        errors.append("source_artifact_bindings_not_list")
    else:
        errors.extend(_source_artifact_binding_errors(
            artifact_bindings,
            row_counts={
                "candidate": payload.get("candidate_rows_supplied"),
                "core": payload.get("core_rows_supplied"),
                "outcome": payload.get("outcome_rows_supplied"),
            },
        ))
        if payload.get("source_artifact_binding_count") != len(artifact_bindings):
            errors.append("source_artifact_binding_count_mismatch")
        if payload.get("source_artifact_binding_digest") != _digest(
            artifact_bindings
        ):
            errors.append("source_artifact_binding_digest_mismatch")
    validation_bindings = payload.get("outcome_validation_bindings")
    if type(validation_bindings) is not list:
        errors.append("outcome_validation_bindings_not_list")
    else:
        errors.extend(_outcome_validation_binding_errors(validation_bindings))
        if payload.get("outcome_validation_binding_count") != len(
            validation_bindings
        ):
            errors.append("outcome_validation_binding_count_mismatch")
        if len(validation_bindings) != payload.get("outcome_rows_supplied"):
            errors.append("outcome_validation_outcome_count_mismatch")
        if payload.get("outcome_validation_binding_digest") != _digest(
            validation_bindings
        ):
            errors.append("outcome_validation_binding_digest_mismatch")
    if episode_value is not None:
        episode_errors = anomaly_episode_shadow.validate_contract(episode_value)
        errors.extend(f"source_episode:{error}" for error in episode_errors)
        comparisons = {
            "source_episode_schema_id": "schema_id",
            "source_episode_schema_version": "schema_version",
            "source_episode_contract_digest": "contract_digest",
            "source_episode_input_binding_digest": "input_binding_digest",
            "primary_episode_count": "primary_episode_count",
            "primary_repeat_member_count": "primary_repeat_member_count",
        }
        for field, source_field in comparisons.items():
            if payload.get(field) != episode_value.get(source_field):
                errors.append(f"{field}_mismatch")
    return errors


def _status(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "empty"
    return (
        "partial"
        if any(row.get("outcome_state") == "contract_excluded" for row in rows)
        else "ready"
    )


def _closed_counts(values: Iterable[Any], allowed: Sequence[str]) -> dict[str, int]:
    counts = Counter(value for value in values if value in allowed)
    return {key: counts[key] for key in allowed}


def _representative_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("observed_at") or ""),
        str(row.get("canonical_asset_id") or ""),
        str(row.get("artifact_namespace") or ""),
        str(row.get("run_id") or ""),
        str(row.get("candidate_id") or ""),
    )


def _materialize_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    return sorted(materialized, key=lambda row: _digest(row))


def _rows_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return _digest(sorted(_digest(row) for row in rows))


def _finite_score(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and 0.0 <= number <= 100.0 else None


def _finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _required_utc(value: Any) -> datetime:
    parsed = outcome_eligibility.parse_aware_time(value)
    if parsed is None:
        raise ValueError("evaluated_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _check_exact_keys(
    row: Mapping[str, Any], expected: set[str], prefix: str, errors: list[str]
) -> None:
    errors.extend(f"{prefix}:missing_key:{key}" for key in sorted(expected - set(row)))
    errors.extend(f"{prefix}:unknown_key:{key}" for key in sorted(set(row) - expected))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _is_digest(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest_matches(expected: Any, value: Any) -> bool:
    try:
        return _is_digest(expected) and expected == _digest(value)
    except (OverflowError, TypeError, ValueError):
        return False


__all__ = (
    "DIRECTION_ALIGNMENTS",
    "EXCLUSIVE_COHORT_FIELDS",
    "METHOD",
    "OUTCOME_STATES",
    "POLICY_CONCLUSION",
    "REPRESENTATIVE_SCHEMA_ID",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_decision_episode_scorecard",
    "validate_contract",
)
