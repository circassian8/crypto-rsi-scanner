"""Pure matched controls, benchmarks, and missed moves for empirical replay.

Selections use only point-in-time observation, idea, and trace fields.  Future
OHLCV is joined only after each selection is frozen, through the existing
empirical path-outcome producer.  The module performs no I/O, network access,
notification, trading, or production mutation.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from . import (
    empirical_missed_attribution,
    empirical_replay_benchmark_metrics,
    empirical_validation_protocol,
)
from .empirical_replay_outcome_join import (
    _outcome_frames_for_symbol,
    outcome_idea as _outcome_idea,
    outcomes_by_idea_id as _outcomes_by_idea_id,
)


SCHEMA_ID = "decision_radar.empirical_replay_controls"
SCHEMA_VERSION = 1
METHOD = "frozen_outcome_blind_controls_benchmarks_and_missed_moves"
DETAIL_ROW_LIMIT = 256

_PROTOCOL = empirical_validation_protocol.protocol_values()
_CONTROL_RULE = _PROTOCOL["matched_controls"]
_MISSED_RULE = _PROTOCOL["missed_opportunity_rule"]
_BENCHMARK_POLICIES = tuple(_PROTOCOL["benchmark_policies"])
_PRIMARY_DAYS = int(_PROTOCOL["outcomes"]["primary_horizon_days"])
_EPISODE_HOURS = int(_PROTOCOL["episodes"]["primary_window_hours"])
_SEED = int(_CONTROL_RULE["seed"])
_VISIBLE_ROUTES = {
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
}
_DIRECTION_VALUES = {"long", "fade_short_review", "risk", "neutral"}
_QUALIFICATION_FAILURES = (
    "minimum_point_in_time_liquidity_not_met",
    "point_in_time_membership_not_proven",
    "warm_baseline_not_proven",
    "operator_visible_idea_present",
    "endpoint_outcome_contract_mismatch",
)
_QUALIFICATION_STATES = (
    "qualified_missed_opportunity",
    "economic_move_excluded_research_or_tradability",
    "economic_move_already_operator_visible",
    "economic_move_excluded_outcome_contract",
)
_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}


def build_empirical_replay_controls(
    observations: Iterable[Mapping[str, Any]],
    trace_rows: Iterable[Mapping[str, Any]],
    idea_rows: Iterable[Mapping[str, Any]],
    price_frames: Mapping[str, pd.DataFrame],
    *,
    evaluated_at: datetime | str,
    evidence_mode: str = "historical_replay",
) -> dict[str, Any]:
    """Build the frozen controls, benchmarks, and missed-move contract."""

    _require_frozen_protocol()
    evaluated = _required_utc(evaluated_at, field="evaluated_at")
    if not isinstance(evidence_mode, str) or not evidence_mode.strip():
        raise ValueError("evidence_mode_required")
    normalized_observations = _observations(observations)
    normalized_ideas = _ideas(idea_rows)
    traces = _traces(trace_rows)

    selection = _select_controls(normalized_observations, normalized_ideas)
    controls = _attach_control_outcomes(
        selection,
        price_frames=price_frames,
        evaluated_at=evaluated,
    )
    missed = _missed_moves(
        normalized_observations,
        normalized_ideas,
        traces,
        price_frames=price_frames,
        evaluated_at=evaluated,
    )
    benchmarks = _benchmarks(
        normalized_observations,
        controls,
        price_frames=price_frames,
        evaluated_at=evaluated,
    )
    public_controls = _bounded_control_rows(controls)
    result: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "protocol_version": _PROTOCOL["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(),
        "evaluated_at": evaluated.isoformat(),
        "evidence_mode": evidence_mode.strip(),
        "observation_count": len(normalized_observations),
        "trace_count": len(traces),
        "idea_count": len(normalized_ideas),
        "matched_non_signal_controls": public_controls,
        "missed_move_evaluation": missed,
        "benchmark_rows": benchmarks,
        "benchmark_policy_order": list(_BENCHMARK_POLICIES),
        "selection_uses_outcomes": False,
        "matched_control_causal_claim": False,
        "final_test_used_for_tuning": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_SAFETY),
    }
    result["contract_digest"] = _digest(result)
    return result


def _bounded_control_rows(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    rows = [dict(row) for row in value.get("rows") or () if isinstance(row, Mapping)]
    rows.sort(
        key=lambda row: (
            row.get("status") != "selected",
            str(row.get("signal_episode_id") or ""),
            str(row.get("control_id") or ""),
        )
    )
    output["row_count"] = len(rows)
    output["row_detail_limit"] = DETAIL_ROW_LIMIT
    output["rows_truncated"] = len(rows) > DETAIL_ROW_LIMIT
    output["rows"] = rows[:DETAIL_ROW_LIMIT]
    return output


def select_matched_non_signal_controls(
    observations: Iterable[Mapping[str, Any]],
    idea_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Select controls from point-in-time fields without reading any outcomes."""

    _require_frozen_protocol()
    return _select_controls(_observations(observations), _ideas(idea_rows))


def _select_controls(
    observations: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    representatives = _signal_episode_representatives(ideas)
    signal_assets_by_timestamp: dict[str, set[str]] = defaultdict(set)
    for idea in ideas:
        signal_assets_by_timestamp[str(idea["observed_at"])].add(
            str(idea["canonical_asset_id"])
        )
    candidate_index: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = (
        defaultdict(list)
    )
    for row in observations:
        if (
            row["point_in_time_universe_member"] is True
            and row["baseline_warm"] is True
        ):
            candidate_index[_control_match_key(row)].append(row)

    rows: list[dict[str, Any]] = []
    for representative in representatives:
        observed_at = str(representative["observed_at"])
        candidates = [
            row
            for row in candidate_index.get(_control_match_key(representative), ())
            if row["canonical_asset_id"]
            not in signal_assets_by_timestamp.get(observed_at, set())
            and row["canonical_asset_id"]
            != representative["canonical_asset_id"]
        ]
        ranked = sorted(
            candidates,
            key=lambda row: (
                _selection_rank(
                    representative["episode_id"],
                    row,
                    policy="matched_non_signal",
                ),
                row["canonical_asset_id"],
                row["symbol"],
            ),
        )
        selected = ranked[: int(_CONTROL_RULE["controls_per_episode"])]
        if not selected:
            rows.append(
                {
                    "signal_episode_id": representative["episode_id"],
                    "signal_representative": dict(representative),
                    "status": "unavailable",
                    "unavailable_reason": "no_exact_matched_non_signal_candidate",
                    "candidate_pool_count": len(candidates),
                    "control_id": None,
                    "control_observation": None,
                    "selection_rank_digest": None,
                    "outcome": None,
                }
            )
            continue
        for candidate in selected:
            rank = _selection_rank(
                representative["episode_id"],
                candidate,
                policy="matched_non_signal",
            )
            control_id = "matched-control-v1:" + _digest(
                {
                    "signal_episode_id": representative["episode_id"],
                    "control_observation_identity": _observation_identity(candidate),
                    "rank": rank,
                }
            )
            rows.append(
                {
                    "signal_episode_id": representative["episode_id"],
                    "signal_representative": dict(representative),
                    "status": "selected",
                    "unavailable_reason": None,
                    "candidate_pool_count": len(candidates),
                    "control_id": control_id,
                    "control_observation": dict(candidate),
                    "selection_rank_digest": rank,
                    "outcome": None,
                }
            )
    value: dict[str, Any] = {
        "schema_id": "decision_radar.empirical_matched_control_selection",
        "schema_version": 1,
        "method": "exact_fields_then_deterministic_hash_rank",
        "match_fields": list(_CONTROL_RULE["match_fields"]),
        "controls_per_episode": int(_CONTROL_RULE["controls_per_episode"]),
        "exclude_signal_assets_same_timestamp": True,
        "selection_uses_outcomes": False,
        "seed": _SEED,
        "signal_episode_count": len(representatives),
        "selected_control_count": sum(row["status"] == "selected" for row in rows),
        "unavailable_control_count": sum(
            row["status"] == "unavailable" for row in rows
        ),
        "rows": rows,
    }
    value["selection_digest"] = _digest(value)
    return value


def _control_match_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("partition") or ""),
        str(row.get("observation_date") or str(row.get("observed_at") or "")[:10]),
        str(row.get("market_regime") or "unknown"),
        str(row.get("liquidity_tier") or "unknown"),
    )


def _attach_control_outcomes(
    selection: Mapping[str, Any],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, Any]:
    value = deepcopy(dict(selection))
    rows = [dict(row) for row in value["rows"]]
    synthetic: list[dict[str, Any]] = []
    for row in rows:
        if row["status"] != "selected":
            continue
        signal = row["signal_representative"]
        observation = row["control_observation"]
        synthetic.append(
            _outcome_idea(
                idea_id=row["control_id"],
                observation=observation,
                direction=str(signal["directional_bias"]),
                family=f"matched_non_signal:{row['signal_episode_id']}",
            )
        )
    outcomes = _outcomes_by_idea_id(
        synthetic,
        price_frames=price_frames,
        evaluated_at=evaluated_at,
    )
    for row in rows:
        if row["control_id"]:
            row["outcome"] = outcomes.get(row["control_id"])
    value["rows"] = rows
    value["matured_control_count"] = sum(
        _outcome_matured(row.get("outcome")) for row in rows
    )
    value["selection_digest"] = selection["selection_digest"]
    value["outcomes_joined_after_selection"] = True
    value["causal_claim"] = False
    value["research_only"] = True
    value["auto_apply"] = False
    value["contract_digest"] = _digest(value)
    return value


def _missed_moves(
    observations: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
    traces: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, Any]:
    close_lookup = _close_lookup(price_frames)
    ideas_by_key: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for idea in ideas:
        ideas_by_key[_identity_key(idea)].append(idea)
    state_counts, selected = _select_missed_endpoint_candidates(
        observations,
        traces,
        ideas_by_key,
        close_lookup=close_lookup,
        evaluated_at=evaluated_at,
    )
    scored = _score_missed_endpoint_candidates(
        selected,
        price_frames=price_frames,
        evaluated_at=evaluated_at,
    )
    return {
        "schema_id": "decision_radar.empirical_missed_move_evaluation",
        "schema_version": 1,
        "method": "frozen_primary_endpoint_then_trace_failure_attribution",
        "primary_horizon_days": _PRIMARY_DAYS,
        "long_endpoint_return_min_fraction": float(
            _MISSED_RULE["long_endpoint_return_min_fraction"]
        ),
        "risk_endpoint_return_max_fraction": float(
            _MISSED_RULE["risk_endpoint_return_max_fraction"]
        ),
        "minimum_trailing_quote_volume_usd": float(
            _MISSED_RULE["minimum_trailing_quote_volume_usd"]
        ),
        "maximum_future_excursion_alone_sufficient": False,
        "evaluation_state_counts": dict(sorted(state_counts.items())),
        "endpoint_candidate_count": len(selected),
        "endpoint_economic_move_count": len(selected),
        "missed_opportunity_count": scored["missed_opportunity_count"],
        "qualified_missed_opportunity_count": scored["missed_opportunity_count"],
        "economic_move_excluded_count": scored["economic_move_excluded_count"],
        "qualification_state_counts": scored["qualification_state_counts"],
        "qualification_failure_counts": scored["qualification_failure_counts"],
        "qualification_population_reconciled": scored[
            "qualification_population_reconciled"
        ],
        "failure_stage_counts": scored["failure_stage_counts"],
        "missed_reason_taxonomy": list(
            empirical_missed_attribution.REASON_TAXONOMY
        ),
        "missed_reason_counts": scored["missed_reason_counts"],
        "missed_reason_count_scope": "all_endpoint_threshold_economic_moves",
        "missed_reason_population_reconciled": scored[
            "missed_reason_population_reconciled"
        ],
        "qualified_missed_reason_counts": scored[
            "qualified_missed_reason_counts"
        ],
        "reason_representative_examples": scored[
            "reason_representative_examples"
        ],
        "qualification_failure_representative_examples": scored[
            "qualification_failure_representative_examples"
        ],
        "representative_example_limit_per_reason": 1,
        "endpoint_candidates": scored["endpoint_candidates"],
        "missed_opportunities": scored["missed_opportunities"],
        "detail_row_limit": DETAIL_ROW_LIMIT,
        "endpoint_candidates_truncated": len(selected) > DETAIL_ROW_LIMIT,
        "missed_opportunities_truncated": (
            scored["missed_opportunity_count"] > DETAIL_ROW_LIMIT
        ),
        "full_path_outcomes_computed_for_prequalified_only": True,
        "nonqualifying_path_outcomes_not_computed": True,
        "outcomes_joined_after_endpoint_selection": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _select_missed_endpoint_candidates(
    observations: Sequence[Mapping[str, Any]],
    traces: Mapping[tuple[str, str], Mapping[str, Any]],
    ideas_by_key: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    close_lookup: Mapping[str, Mapping[datetime, float]],
    evaluated_at: datetime,
) -> tuple[Counter[str], list[dict[str, Any]]]:
    state_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for observation in observations:
        due = _required_utc(observation["observed_at"], field="observed_at") + timedelta(
            days=_PRIMARY_DAYS
        )
        if evaluated_at < due:
            state_counts["pending"] += 1
            continue
        raw_return = _endpoint_return(observation, close_lookup, days=_PRIMARY_DAYS)
        if raw_return is None:
            state_counts["missing_data"] += 1
            continue
        state_counts["matured"] += 1
        direction = (
            "long"
            if raw_return
            >= float(_MISSED_RULE["long_endpoint_return_min_fraction"])
            else "risk"
            if raw_return
            <= float(_MISSED_RULE["risk_endpoint_return_max_fraction"])
            else None
        )
        if direction is None:
            state_counts["endpoint_below_threshold"] += 1
            continue
        state_counts["endpoint_threshold_crossed"] += 1
        key = _identity_key(observation)
        trace = traces.get(key)
        linked_ideas = ideas_by_key.get(key, [])
        visible = _operator_visible(trace, linked_ideas)
        liquidity = _liquidity(observation)
        failures: list[str] = []
        if liquidity is None or liquidity < float(
            _MISSED_RULE["minimum_trailing_quote_volume_usd"]
        ):
            failures.append("minimum_point_in_time_liquidity_not_met")
        if observation["point_in_time_universe_member"] is not True:
            failures.append("point_in_time_membership_not_proven")
        if observation["baseline_warm"] is not True:
            failures.append("warm_baseline_not_proven")
        if visible is True:
            failures.append("operator_visible_idea_present")
        failure_stage = _failure_stage(trace, visible=visible)
        attribution = empirical_missed_attribution.classify_missed_attribution(
            trace,
            observation,
            qualification_failure_reasons=failures,
        )
        missed_id = "missed-move-v1:" + _digest(
            {
                "observation": _observation_identity(observation),
                "direction": direction,
                "primary_endpoint_return_fraction": raw_return,
            }
        )
        candidate = {
            "missed_move_id": missed_id,
            "observation": dict(observation),
            "directional_bias": direction,
            "primary_endpoint_return_fraction": raw_return,
            "endpoint_rule_crossed": True,
            "maximum_future_excursion_alone_sufficient": False,
            "point_in_time_liquidity_usd": liquidity,
            "operator_visible_idea": visible,
            "trace_status": trace.get("trace_status") if trace else "missing",
            "failure_stage": failure_stage,
            "primary_reason": attribution["primary_reason"],
            "reason_codes": attribution["reason_codes"],
            "reason_evidence": attribution["reason_evidence"],
            "projection_validation_error_codes": attribution[
                "projection_validation_error_codes"
            ],
            "diagnostic_concern_class": attribution[
                "diagnostic_concern_class"
            ],
            "attribution_uses_future_outcome": False,
            "qualification_failure_reasons": failures,
            "qualifies_as_missed_opportunity": not failures,
            "qualification_state": _qualification_state(failures),
        }
        selected.append(candidate)
    return state_counts, selected


def _score_missed_endpoint_candidates(
    selected: Sequence[Mapping[str, Any]],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, Any]:
    endpoint_details: list[dict[str, Any]] = []
    opportunity_details: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    qualified_attribution_rows: list[dict[str, Any]] = []
    reason_representatives: dict[str, dict[str, Any]] = {}
    qualification_representatives: dict[str, dict[str, Any]] = {}
    qualification_failure_counts: Counter[str] = Counter()
    qualification_state_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    prequalified = [
        dict(row)
        for row in selected
        if row.get("qualifies_as_missed_opportunity") is True
    ]
    scored_prequalified = _join_prequalified_missed_outcomes(
        prequalified,
        price_frames,
        evaluated_at=evaluated_at,
    )
    for candidate in selected:
        detail = scored_prequalified.get(str(candidate["missed_move_id"]))
        if detail is None:
            detail = {
                **dict(candidate),
                "qualification_state": _qualification_state(
                    candidate.get("qualification_failure_reasons") or ()
                ),
                "outcome": {
                    "status": "not_computed_nonqualifying",
                    "primary_horizon_return": candidate[
                        "primary_endpoint_return_fraction"
                    ],
                    "return_unit": "fraction",
                },
            }
        state = str(detail["qualification_state"])
        qualification_state_counts[state] += 1
        attribution = {
            "primary_reason": detail["primary_reason"],
            "reason_codes": list(detail["reason_codes"]),
        }
        attribution_rows.append(attribution)
        for failure in detail.get("qualification_failure_reasons") or ():
            if str(failure) in _QUALIFICATION_FAILURES:
                qualification_failure_counts[str(failure)] += 1
                _retain_representative(
                    qualification_representatives,
                    str(failure),
                    detail,
                )
        for reason in detail.get("reason_codes") or ():
            if str(reason) in empirical_missed_attribution.REASON_TAXONOMY:
                _retain_representative(reason_representatives, str(reason), detail)
        if detail.get("qualifies_as_missed_opportunity") is True:
            failure_counts[str(detail["failure_stage"])] += 1
            qualified_attribution_rows.append(attribution)
            _retain_missed_detail(opportunity_details, detail)
        _retain_missed_detail(endpoint_details, detail)

    missed_count = qualification_state_counts["qualified_missed_opportunity"]
    endpoint_rows = _bounded_details_with_representatives(
        endpoint_details,
        [
            *reason_representatives.values(),
            *qualification_representatives.values(),
        ],
    )
    opportunity_rows = _bounded_details_with_representatives(
        opportunity_details,
        [
            detail
            for detail in reason_representatives.values()
            if detail.get("qualifies_as_missed_opportunity") is True
        ],
    )
    closed_states = {
        state: qualification_state_counts[state] for state in _QUALIFICATION_STATES
    }
    closed_failures = {
        failure: qualification_failure_counts[failure]
        for failure in _QUALIFICATION_FAILURES
    }
    all_reason_counts = empirical_missed_attribution.closed_reason_counts(
        attribution_rows
    )
    return {
        "missed_opportunity_count": missed_count,
        "economic_move_excluded_count": len(selected) - missed_count,
        "qualification_state_counts": closed_states,
        "qualification_failure_counts": closed_failures,
        "qualification_population_reconciled": (
            sum(closed_states.values()) == len(selected)
            and missed_count + (len(selected) - missed_count) == len(selected)
        ),
        "failure_stage_counts": dict(sorted(failure_counts.items())),
        "missed_reason_counts": all_reason_counts,
        "missed_reason_population_reconciled": (
            sum(row["primary_count"] for row in all_reason_counts)
            == len(selected)
        ),
        "qualified_missed_reason_counts": (
            empirical_missed_attribution.closed_reason_counts(
                qualified_attribution_rows
            )
        ),
        "reason_representative_examples": [
            {
                "reason": reason,
                "candidate": reason_representatives[reason],
            }
            for reason in empirical_missed_attribution.REASON_TAXONOMY
            if reason in reason_representatives
        ],
        "qualification_failure_representative_examples": [
            {
                "qualification_failure": failure,
                "candidate": qualification_representatives[failure],
            }
            for failure in _QUALIFICATION_FAILURES
            if failure in qualification_representatives
        ],
        "endpoint_candidates": endpoint_rows,
        "missed_opportunities": opportunity_rows,
    }


def _join_prequalified_missed_outcomes(
    candidates: Sequence[Mapping[str, Any]],
    price_frames: Mapping[str, pd.DataFrame],
    *,
    evaluated_at: datetime,
) -> dict[str, dict[str, Any]]:
    synthetic = [
        _outcome_idea(
            idea_id=str(candidate["missed_move_id"]),
            observation=candidate["observation"],
            direction=str(candidate["directional_bias"]),
            family="missed_move_evaluation",
        )
        for candidate in candidates
    ]
    outcomes = _outcomes_by_idea_id(
        synthetic,
        price_frames=price_frames,
        evaluated_at=evaluated_at,
    )
    output: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        outcome = outcomes[str(candidate["missed_move_id"])]
        detail = {**candidate, "outcome": outcome}
        observed_return = _finite(outcome.get("primary_horizon_return"))
        if observed_return is None or not math.isclose(
            observed_return,
            candidate["primary_endpoint_return_fraction"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            detail["qualification_failure_reasons"] = [
                *candidate["qualification_failure_reasons"],
                "endpoint_outcome_contract_mismatch",
            ]
            detail["qualifies_as_missed_opportunity"] = False
            detail["qualification_state"] = (
                "economic_move_excluded_outcome_contract"
            )
        else:
            detail["qualification_state"] = "qualified_missed_opportunity"
        output[str(candidate["missed_move_id"])] = detail
    return output


def _retain_missed_detail(
    rows: list[dict[str, Any]],
    detail: Mapping[str, Any],
) -> None:
    rows.append(dict(detail))
    if len(rows) > DETAIL_ROW_LIMIT * 2:
        rows.sort(key=_missed_detail_rank)
        del rows[DETAIL_ROW_LIMIT:]


def _retain_representative(
    rows: dict[str, dict[str, Any]],
    key: str,
    detail: Mapping[str, Any],
) -> None:
    current = rows.get(key)
    candidate = dict(detail)
    if current is None or _missed_detail_rank(candidate) < _missed_detail_rank(current):
        rows[key] = candidate


def _bounded_details_with_representatives(
    top_rows: Sequence[Mapping[str, Any]],
    representative_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    required: dict[str, dict[str, Any]] = {}
    for row in representative_rows:
        required[str(row.get("missed_move_id") or "")] = dict(row)
    required.pop("", None)
    ordered_required = sorted(required.values(), key=_missed_detail_rank)
    remaining = {
        str(row.get("missed_move_id") or ""): dict(row) for row in top_rows
    }
    for identifier in required:
        remaining.pop(identifier, None)
    ordered_remaining = sorted(remaining.values(), key=_missed_detail_rank)
    return [
        *ordered_required[:DETAIL_ROW_LIMIT],
        *ordered_remaining[: max(0, DETAIL_ROW_LIMIT - len(ordered_required))],
    ]


def _qualification_state(failures: Sequence[Any]) -> str:
    values = {str(value) for value in failures}
    if "endpoint_outcome_contract_mismatch" in values:
        return "economic_move_excluded_outcome_contract"
    if values.intersection({
        "minimum_point_in_time_liquidity_not_met",
        "point_in_time_membership_not_proven",
        "warm_baseline_not_proven",
    }):
        return "economic_move_excluded_research_or_tradability"
    if "operator_visible_idea_present" in values:
        return "economic_move_already_operator_visible"
    return "qualified_missed_opportunity"


def _missed_detail_rank(row: Mapping[str, Any]) -> tuple[Any, ...]:
    observation = row.get("observation")
    return (
        row.get("qualifies_as_missed_opportunity") is not True,
        -abs(float(row.get("primary_endpoint_return_fraction") or 0.0)),
        str(
            observation.get("observed_at")
            if isinstance(observation, Mapping)
            else ""
        ),
        str(row.get("missed_move_id") or ""),
    )


def _benchmarks(
    observations: Sequence[Mapping[str, Any]],
    controls: Mapping[str, Any],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in observations
        if row["point_in_time_universe_member"] is True and row["baseline_warm"] is True
    ]
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[(row["partition"], row["observation_date"])].append(row)

    selections_by_policy: dict[str, list[dict[str, Any]]] = {
        policy: [] for policy in _BENCHMARK_POLICIES
    }
    unavailable: dict[str, Counter[str]] = {
        policy: Counter() for policy in _BENCHMARK_POLICIES
    }
    _add_matched_control_benchmark(
        controls,
        selections=selections_by_policy,
        unavailable=unavailable,
    )
    _add_observation_benchmarks(
        groups,
        selections=selections_by_policy,
        unavailable=unavailable,
    )
    _add_context_benchmarks(
        groups,
        price_frames=price_frames,
        selections=selections_by_policy,
        unavailable=unavailable,
    )
    _attach_benchmark_outcomes(
        selections_by_policy,
        price_frames=price_frames,
        evaluated_at=evaluated_at,
    )
    return [
        empirical_replay_benchmark_metrics.build_benchmark_row(
            policy,
            selections_by_policy[policy],
            unavailable[policy],
            eligible_group_count=len(groups),
            detail_row_limit=DETAIL_ROW_LIMIT,
        )
        for policy in _BENCHMARK_POLICIES
    ]


def _add_matched_control_benchmark(
    controls: Mapping[str, Any],
    *,
    selections: Mapping[str, list[dict[str, Any]]],
    unavailable: Mapping[str, Counter[str]],
) -> None:
    for row in controls["rows"]:
        if row["status"] != "selected":
            unavailable["matched_non_signal"][
                row.get("unavailable_reason") or "control_unavailable"
            ] += 1
            continue
        selections["matched_non_signal"].append(
            {
                "selection_id": row["control_id"],
                "policy": "matched_non_signal",
                "selection_rule": "exact_match_then_deterministic_hash_rank",
                "observation": row["control_observation"],
                "directional_bias": row["signal_representative"][
                    "directional_bias"
                ],
                "selection_metric": None,
                "selection_metric_value": None,
                "outcome": row.get("outcome"),
            }
        )


def _add_observation_benchmarks(
    groups: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    selections: Mapping[str, list[dict[str, Any]]],
    unavailable: Mapping[str, Counter[str]],
) -> None:
    for group_key in sorted(groups):
        rows = groups[group_key]
        for policy, metric, getter, direction_getter, rule in _benchmark_specs():
            selected = _top_metric_row(
                rows,
                getter=getter,
                policy=policy,
                group_key=group_key,
            )
            if selected is None:
                unavailable[policy][f"{metric}_unavailable"] += 1
                continue
            observation, value = selected
            selection_id = "benchmark-v1:" + _digest(
                {
                    "policy": policy,
                    "group": group_key,
                    "observation": _observation_identity(observation),
                    "metric": value,
                }
            )
            selections[policy].append(
                {
                    "selection_id": selection_id,
                    "policy": policy,
                    "selection_rule": rule,
                    "observation": dict(observation),
                    "directional_bias": direction_getter(observation, value),
                    "selection_metric": metric,
                    "selection_metric_value": value,
                    "outcome": None,
                }
            )


def _benchmark_specs() -> tuple[tuple[str, str, Any, Any, str], ...]:
    return (
        (
            "same_day_top_raw_mover",
            "return_24h",
            lambda row: _return_fraction(row, "return_24h"),
            lambda _row, _value: "long",
            "highest_point_in_time_24h_return",
        ),
        (
            "volume_anomaly_only",
            "volume_zscore_24h",
            lambda row: _finite(row.get("volume_zscore_24h")),
            lambda row, _value: (
                "long"
                if (_return_fraction(row, "return_24h") or 0.0) >= 0
                else "risk"
            ),
            "highest_point_in_time_volume_zscore",
        ),
        (
            "rsi_only",
            "absolute_rsi_distance_from_50",
            lambda row: (
                abs(value - 50.0)
                if (value := _finite(row.get("rsi"))) is not None
                else None
            ),
            lambda row, _value: (
                "long" if float(row["rsi"]) <= 50.0 else "fade_short_review"
            ),
            "largest_point_in_time_absolute_rsi_distance_from_50",
        ),
        (
            "top_relative_strength",
            "relative_return_vs_btc_24h",
            lambda row: _return_fraction(row, "relative_return_vs_btc_24h"),
            lambda _row, _value: "long",
            "highest_point_in_time_relative_return_vs_btc_24h",
        ),
        (
            "late_momentum_fade",
            "return_7d",
            lambda row: _return_fraction(row, "return_7d"),
            lambda _row, _value: "fade_short_review",
            "highest_point_in_time_7d_return_then_fade",
        ),
    )


def _add_context_benchmarks(
    groups: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    selections: Mapping[str, list[dict[str, Any]]],
    unavailable: Mapping[str, Counter[str]],
) -> None:
    for benchmark, policy in (
        ("BTC", "btc_buy_and_hold_context"),
        ("ETH", "eth_buy_and_hold_context"),
    ):
        symbol = _benchmark_symbol(price_frames, benchmark)
        if symbol is None:
            unavailable[policy]["benchmark_price_frame_missing"] += max(1, len(groups))
            continue
        for partition, date in sorted(groups):
            observed_at = _date_timestamp_for_group(groups[(partition, date)])
            observation = {
                "canonical_asset_id": benchmark.casefold(),
                "symbol": symbol,
                "observed_at": observed_at,
                "observation_date": date,
                "partition": partition,
                "market_regime": "context",
                "liquidity_tier": "benchmark",
                "liquidity_usd": None,
                "trailing_quote_volume_usd": None,
                "point_in_time_universe_member": True,
                "baseline_status": "warm",
                "baseline_warm": True,
                "data_quality_mode": "historical_ohlcv",
                "return_unit": "fraction",
            }
            selection_id = "benchmark-v1:" + _digest(
                {"policy": policy, "partition": partition, "observed_at": observed_at}
            )
            selections[policy].append(
                {
                    "selection_id": selection_id,
                    "policy": policy,
                    "selection_rule": "long_context_at_each_eligible_observation_date",
                    "observation": observation,
                    "directional_bias": "long",
                    "selection_metric": None,
                    "selection_metric_value": None,
                    "outcome": None,
                }
            )


def _attach_benchmark_outcomes(
    selections: Mapping[str, list[dict[str, Any]]],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> None:
    synthetic: list[dict[str, Any]] = []
    for policy, policy_selections in selections.items():
        if policy == "matched_non_signal":
            continue
        for selection in policy_selections:
            synthetic.append(
                _outcome_idea(
                    idea_id=selection["selection_id"],
                    observation=selection["observation"],
                    direction=selection["directional_bias"],
                    family=f"benchmark:{policy}:{selection['selection_id']}",
                )
            )
    outcomes = _outcomes_by_idea_id(
        synthetic,
        price_frames=price_frames,
        evaluated_at=evaluated_at,
    )
    for policy, policy_selections in selections.items():
        if policy == "matched_non_signal":
            continue
        for selection in policy_selections:
            selection["outcome"] = outcomes.get(selection["selection_id"])


def _observations(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        observed = _required_utc(raw.get("observed_at"), field="observed_at")
        symbol = _required_text(raw.get("symbol"), field="symbol").upper()
        canonical = _required_text(
            raw.get("canonical_asset_id") or raw.get("coin_id") or symbol,
            field="canonical_asset_id",
        )
        value = {
            "canonical_asset_id": canonical,
            "symbol": symbol,
            "observed_at": observed.isoformat(),
            "observation_date": observed.date().isoformat(),
            "partition": str(raw.get("partition") or raw.get("replay_partition") or "unassigned"),
            "market_regime": str(raw.get("market_regime") or "unknown"),
            "liquidity_tier": str(raw.get("liquidity_tier") or "unknown"),
            "liquidity_usd": _finite(raw.get("liquidity_usd")),
            "trailing_quote_volume_usd": _finite(
                raw.get("trailing_quote_volume_usd")
                if raw.get("trailing_quote_volume_usd") is not None
                else raw.get("trailing_quote_volume")
            ),
            "point_in_time_universe_member": raw.get(
                "point_in_time_universe_member"
            )
            is True,
            "baseline_status": str(
                raw.get("baseline_status") or raw.get("baseline_maturity") or "missing"
            ),
            "baseline_warm": str(
                raw.get("baseline_status") or raw.get("baseline_maturity") or ""
            )
            in {"warm", "complete"},
            "data_quality_mode": str(
                raw.get("data_quality_mode") or "missing"
            ),
            "return_unit": str(raw.get("return_unit") or "unknown"),
            "return_units": _json_ready(raw.get("return_units") or {}),
            "return_24h": _finite(raw.get("return_24h")),
            "return_72h": _finite(raw.get("return_72h")),
            "return_7d": _finite(raw.get("return_7d")),
            "relative_return_vs_btc_24h": _finite(
                raw.get("relative_return_vs_btc_24h")
            ),
            "volume_zscore_24h": _finite(raw.get("volume_zscore_24h")),
            "rsi": _finite(raw.get("rsi")),
        }
        key = _identity_key(value)
        if key in seen:
            raise ValueError("duplicate_observation_identity")
        seen.add(key)
        value["observation_digest"] = _digest(value)
        output.append(value)
    return sorted(output, key=lambda row: (row["observed_at"], row["canonical_asset_id"]))


def _ideas(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        projection = raw.get("decision_projection")
        projection = dict(projection) if isinstance(projection, Mapping) else {}

        def value(*names: str) -> Any:
            for source in (raw, projection):
                for name in names:
                    candidate = source.get(name)
                    if candidate not in (None, ""):
                        return candidate
            return None

        observed = _required_utc(value("observed_at"), field="idea_observed_at")
        symbol = _required_text(value("symbol"), field="idea_symbol").upper()
        canonical = _required_text(
            value("canonical_asset_id", "coin_id") or symbol,
            field="idea_canonical_asset_id",
        )
        direction = str(value("directional_bias") or "neutral")
        if direction not in _DIRECTION_VALUES:
            direction = "neutral"
        route = str(value("radar_route") or "diagnostic")
        output.append(
            {
                "idea_id": str(
                    value("idea_id", "candidate_id")
                    or "derived:" + _digest({"asset": canonical, "at": observed.isoformat()})
                ),
                "canonical_asset_id": canonical,
                "symbol": symbol,
                "observed_at": observed.isoformat(),
                "observation_date": observed.date().isoformat(),
                "partition": str(value("partition", "replay_partition") or "unassigned"),
                "market_regime": str(value("market_regime") or "unknown"),
                "liquidity_tier": str(value("liquidity_tier") or "unknown"),
                "directional_bias": direction,
                "anomaly_family": str(
                    value("anomaly_family", "candidate_family_id", "anomaly_type")
                    or "unknown"
                ),
                "radar_route": route,
                "operator_visible": (
                    value("operator_visible", "operator_visible_idea")
                    if isinstance(
                        value("operator_visible", "operator_visible_idea"), bool
                    )
                    else route in _VISIBLE_ROUTES
                ),
            }
        )
    return sorted(output, key=lambda row: (row["observed_at"], row["idea_id"]))


def _traces(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        observed = _required_utc(raw.get("observed_at"), field="trace_observed_at")
        canonical = _required_text(
            raw.get("canonical_asset_id") or raw.get("coin_id") or raw.get("symbol"),
            field="trace_canonical_asset_id",
        )
        value = {
            "canonical_asset_id": canonical,
            "symbol": str(raw.get("symbol") or "").upper(),
            "observed_at": observed.isoformat(),
            "trace_status": str(raw.get("trace_status") or "unknown"),
            "failure_stage": (
                str(raw.get("failure_stage")) if raw.get("failure_stage") else None
            ),
            "operator_visible": (
                raw.get("operator_visible")
                if isinstance(raw.get("operator_visible"), bool)
                else None
            ),
            "radar_route": str(raw.get("radar_route") or ""),
            "hard_blockers": [
                str(item)
                for item in raw.get("hard_blockers") or ()
                if str(item)
            ],
            "warnings": [
                str(item) for item in raw.get("warnings") or () if str(item)
            ],
            "actionability_score": _finite(raw.get("actionability_score")),
            "evidence_confidence_score": _finite(
                raw.get("evidence_confidence_score")
            ),
            "risk_score": _finite(raw.get("risk_score")),
            "urgency_score": _finite(raw.get("urgency_score")),
            "chase_risk_score": _finite(raw.get("chase_risk_score")),
            "catalyst_status": str(raw.get("catalyst_status") or ""),
            "spread_status": str(raw.get("spread_status") or ""),
            "rsi_context_present": (
                raw.get("rsi_context_present")
                if isinstance(raw.get("rsi_context_present"), bool)
                else None
            ),
            "projection_validation_error_codes": [
                str(item)
                for item in raw.get("projection_validation_error_codes") or ()
                if str(item)
            ][:16],
            "projection_validation_concern_class": str(
                raw.get("projection_validation_concern_class") or ""
            ),
        }
        key = _identity_key(value)
        if key in output:
            raise ValueError("duplicate_trace_identity")
        output[key] = value
    return output


def _signal_episode_representatives(
    ideas: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for idea in ideas:
        groups[
            (
                str(idea["canonical_asset_id"]),
                str(idea["directional_bias"]),
                str(idea["anomaly_family"]),
            )
        ].append(idea)
    representatives: list[dict[str, Any]] = []
    for identity in sorted(groups):
        ordered = sorted(
            groups[identity], key=lambda row: (row["observed_at"], row["idea_id"])
        )
        window_end: datetime | None = None
        for idea in ordered:
            observed = _required_utc(idea["observed_at"], field="observed_at")
            if window_end is not None and observed <= window_end:
                continue
            window_end = observed + timedelta(hours=_EPISODE_HOURS)
            episode_id = "control-signal-episode-v1:" + _digest(
                {
                    "identity": identity,
                    "observed_at": observed.isoformat(),
                    "idea_id": idea["idea_id"],
                }
            )
            representatives.append({**dict(idea), "episode_id": episode_id})
    return sorted(
        representatives, key=lambda row: (row["observed_at"], row["episode_id"])
    )


def _top_metric_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    getter: Any,
    policy: str,
    group_key: tuple[str, str],
) -> tuple[Mapping[str, Any], float] | None:
    candidates = [
        (row, value)
        for row in rows
        if (value := _finite(getter(row))) is not None
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            -item[1],
            _selection_rank(
                f"{group_key[0]}:{group_key[1]}", item[0], policy=policy
            ),
            item[0]["canonical_asset_id"],
        ),
    )[0]


def _selection_rank(
    anchor: str, observation: Mapping[str, Any], *, policy: str
) -> str:
    return hashlib.sha256(
        (
            f"{_SEED}|{policy}|{anchor}|{observation['partition']}|"
            f"{observation['observation_date']}|{observation['market_regime']}|"
            f"{observation['liquidity_tier']}|{observation['canonical_asset_id']}|"
            f"{observation['observed_at']}"
        ).encode("utf-8")
    ).hexdigest()


def _return_fraction(row: Mapping[str, Any], field: str) -> float | None:
    value = _finite(row.get(field))
    if value is None:
        return None
    units = row.get("return_units")
    unit = units.get(field) if isinstance(units, Mapping) else None
    unit = str(unit or row.get("return_unit") or "")
    if unit in {"fraction", "decimal_fraction", "fraction_by_protocol"}:
        return value
    if unit in {"percent_points", "percentage_points", "pct_points"}:
        return value / 100.0
    return None


def _close_lookup(
    frames: Mapping[str, pd.DataFrame],
) -> dict[str, dict[datetime, float]]:
    output: dict[str, dict[datetime, float]] = {}
    for raw_symbol, raw_frame in frames.items():
        symbol = str(raw_symbol or "").upper()
        if not symbol or not isinstance(raw_frame, pd.DataFrame):
            continue
        frame = raw_frame.copy(deep=False)
        columns = {str(column).casefold(): column for column in frame.columns}
        close_column = columns.get("close")
        if close_column is None:
            continue
        timestamp_column = next(
            (
                columns[name]
                for name in ("timestamp", "observed_at", "date", "open_time")
                if name in columns
            ),
            None,
        )
        raw_times: Any = frame.index if timestamp_column is None else frame[timestamp_column]
        try:
            timestamps = _timestamp_index(raw_times)
        except (TypeError, ValueError, OverflowError):
            continue
        if timestamps.has_duplicates or timestamps.isna().any():
            continue
        values: dict[datetime, float] = {}
        for timestamp, raw_close in zip(timestamps, frame[close_column], strict=True):
            close = _finite(raw_close)
            if close is not None and close > 0:
                values[timestamp.to_pydatetime()] = close
        output[symbol] = values
    return output


def _endpoint_return(
    observation: Mapping[str, Any],
    lookup: Mapping[str, Mapping[datetime, float]],
    *,
    days: int,
) -> float | None:
    observed = _required_utc(observation["observed_at"], field="observed_at")
    prices = lookup.get(str(observation["symbol"]).upper())
    if prices is None:
        return None
    entry = prices.get(observed)
    exit_price = prices.get(observed + timedelta(days=days))
    if entry is None or exit_price is None or entry <= 0:
        return None
    return exit_price / entry - 1.0


def _timestamp_index(values: Any) -> pd.DatetimeIndex:
    series = pd.Series(values)
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        result = pd.to_datetime(series, utc=True)
    else:
        numeric = pd.to_numeric(series, errors="coerce")
        if len(series) and numeric.notna().all():
            maximum = float(numeric.abs().max())
            unit = (
                "ns"
                if maximum >= 1e17
                else "us"
                if maximum >= 1e14
                else "ms"
                if maximum >= 1e11
                else "s"
            )
            result = pd.to_datetime(numeric, unit=unit, utc=True)
        else:
            result = pd.to_datetime(series, utc=True)
    return pd.DatetimeIndex(result)


def _operator_visible(
    trace: Mapping[str, Any] | None,
    ideas: Sequence[Mapping[str, Any]],
) -> bool:
    if any(idea.get("operator_visible") is True for idea in ideas):
        return True
    if trace is not None and trace.get("operator_visible") is True:
        return True
    return False


def _failure_stage(
    trace: Mapping[str, Any] | None,
    *,
    visible: bool,
) -> str:
    if trace is None:
        return "trace_missing"
    if trace.get("failure_stage"):
        return str(trace["failure_stage"])
    if visible:
        return "operator_visible_idea_present"
    if trace.get("trace_status") == "idea":
        return "decision_not_operator_visible"
    return "unclassified_trace_failure"


def _liquidity(observation: Mapping[str, Any]) -> float | None:
    value = _finite(observation.get("trailing_quote_volume_usd"))
    return value if value is not None else _finite(observation.get("liquidity_usd"))


def _benchmark_symbol(
    frames: Mapping[str, pd.DataFrame], benchmark: str
) -> str | None:
    by_upper = {str(key).upper(): str(key) for key in frames}
    for name in (benchmark, f"{benchmark}USDT"):
        if name in by_upper:
            return name
    return None


def _date_timestamp_for_group(rows: Sequence[Mapping[str, Any]]) -> str:
    return min(str(row["observed_at"]) for row in rows)


def _observation_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_asset_id": row["canonical_asset_id"],
        "symbol": row["symbol"],
        "observed_at": row["observed_at"],
        "partition": row["partition"],
    }


def _identity_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["canonical_asset_id"]), str(row["observed_at"])


def _outcome_matured(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("status") == "matured"


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    return value.strip()


def _required_utc(value: Any, *, field: str) -> datetime:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _require_frozen_protocol() -> None:
    errors = empirical_validation_protocol.validate_protocol(_PROTOCOL)
    if errors:
        raise ValueError("frozen_protocol_invalid:" + ";".join(errors))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_ready(item) for item in value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().astimezone(timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA:
        return None
    return deepcopy(value)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _json_ready(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "METHOD",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_empirical_replay_controls",
    "select_matched_non_signal_controls",
]
