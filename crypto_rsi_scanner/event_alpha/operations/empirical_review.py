"""Pure targeted-review selection for empirical Decision Radar evidence.

The queue is an outcome-aware review aid, never a policy input.  It consumes
already-materialized replay artifacts, emits a bounded deterministic value,
and performs no I/O.  Optional human labels are described only as metadata;
this module neither reads nor writes a feedback ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from ..radar.decision_models import RadarDecisionConfig


SCHEMA_ID = "decision_radar.empirical_targeted_review_queue"
SCHEMA_VERSION = 1
MAX_QUEUE_ITEMS = 64
MAX_ITEMS_PER_CATEGORY = 8
BORDERLINE_DISTANCE_POINTS = 2.0

CATEGORY_ORDER = (
    "threshold_borderline",
    "monotonicity_violation",
    "high_actionability_failure",
    "low_actionability_success",
    "unknown_catalyst_winner",
    "confirmed_catalyst_loser",
    "missed_opportunity",
    "economic_move_qualification_exclusion",
    "manipulation_concern_candidate",
    "late_idea",
    "inconsistent_data_quality",
)

LABEL_TAXONOMY = (
    "useful",
    "not_useful",
    "too_late",
    "too_noisy",
    "manipulation_concern",
    "correct_risk_warning",
    "missed_confirmation",
    "duplicate",
    "data_problem",
)

_CATEGORY_RULES = {
    "threshold_borderline": (
        "matured episode within two score points of a frozen production route threshold"
    ),
    "monotonicity_violation": (
        "representative episode pair from an aggregate adjacent score-bucket violation"
    ),
    "high_actionability_failure": (
        "matured episode at or above the production actionable threshold with non-positive directional return"
    ),
    "low_actionability_success": (
        "matured episode below the production dashboard threshold with positive directional return"
    ),
    "unknown_catalyst_winner": (
        "matured catalyst-unknown episode with positive directional return"
    ),
    "confirmed_catalyst_loser": (
        "matured catalyst-confirmed episode with non-positive directional return"
    ),
    "missed_opportunity": (
        "predeclared missed-move evaluator row that qualifies as a missed opportunity"
    ),
    "economic_move_qualification_exclusion": (
        "endpoint-threshold economic move excluded by predeclared research, tradability, visibility, or outcome-contract requirements"
    ),
    "manipulation_concern_candidate": (
        "explicit manipulation warning, or low-liquidity high-chase false-positive pattern; concern candidate only"
    ),
    "late_idea": "frozen false-positive/late analysis classified the episode as late",
    "inconsistent_data_quality": (
        "explicitly conflicting data-quality, baseline, universe, unit, or safety fields"
    ),
}

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PROJECTION_VALIDATION_ERROR_CODES = {
    "return_unit_metadata_invalid",
    "return_unit_field_unknown",
    "return_unit_missing",
    "return_value_invalid",
    "return_fraction_implausible",
    "return_percent_implausible",
    "decision_field_missing",
    "decision_field_type_invalid",
    "decision_enum_invalid",
    "decision_score_or_expiry_invalid",
    "decision_actionability_contract_invalid",
    "decision_route_contract_invalid",
    "decision_calendar_contract_invalid",
    "decision_projection_contract_invalid",
    "decision_safety_contract_invalid",
    "decision_provenance_contract_invalid",
    "decision_contract_invalid_other",
    "canonical_projection_idempotence_failed",
}
_SCORE_BUCKETS = {
    "0_19": (0.0, 20.0),
    "20_39": (20.0, 40.0),
    "40_59": (40.0, 60.0),
    "60_79": (60.0, 80.0),
    "80_100": (80.0, 100.000000001),
}
_ZERO_SAFETY = {
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
    "feedback_writes": 0,
}


def build_targeted_review_queue(
    ideas: Iterable[Mapping[str, Any]],
    outcomes: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    analyses: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    controls: Mapping[str, Any] | None,
    *,
    run_fingerprint: str,
) -> dict[str, Any]:
    """Return one closed, bounded, deterministic empirical review queue."""

    if not _DIGEST.fullmatch(str(run_fingerprint or "")):
        raise ValueError("empirical review run fingerprint invalid")
    idea_rows = _mapping_rows(ideas)
    episode_rows = _episode_rows(outcomes)
    analysis_rows = _analysis_rows(analyses)
    control_value = dict(controls) if isinstance(controls, Mapping) else {}
    protocol_version, protocol_sha256 = _protocol_identity(
        idea_rows, analysis_rows, control_value
    )
    idea_index = _idea_index(idea_rows)
    false_late = _false_late_index(analysis_rows)
    episodes = _episode_views(episode_rows, idea_index, false_late)
    source_digests = _source_evidence_digests(
        idea_rows, episode_rows, analysis_rows, control_value
    )
    evidence_digest = _digest_value(source_digests)

    candidates: dict[str, list[dict[str, Any]]] = {
        category: [] for category in CATEGORY_ORDER
    }
    _add_episode_candidates(candidates, episodes)
    _add_monotonicity_candidates(candidates, episodes, analysis_rows)
    missed_eligible_count, missed_available_count, missed_source_truncated = (
        _add_missed_candidates(candidates, control_value)
    )
    for category in CATEGORY_ORDER:
        candidates[category] = _dedupe_and_sort(candidates[category])

    selected = _round_robin_select(candidates)
    items = _finalize_items(
        selected,
        run_fingerprint=run_fingerprint,
        protocol_version=protocol_version,
        protocol_sha256=protocol_sha256,
        queue_evidence_digest=evidence_digest,
    )
    selected_counts = {
        category: sum(category in item["categories"] for item in items)
        for category in CATEGORY_ORDER
    }
    category_rows = []
    for category in CATEGORY_ORDER:
        available = len(candidates[category])
        eligible = (
            missed_eligible_count if category == "missed_opportunity" else available
        )
        selected_count = selected_counts[category]
        category_rows.append({
            "category": category,
            "selection_rule": _CATEGORY_RULES[category],
            "eligible_count": eligible,
            "detail_rows_available": (
                missed_available_count
                if category == "missed_opportunity"
                else available
            ),
            "selected_count": selected_count,
            "truncated_count": max(0, eligible - selected_count),
            "source_rows_truncated": (
                missed_source_truncated
                if category == "missed_opportunity"
                else False
            ),
            "selection_status": (
                "zero_sample"
                if eligible == 0
                else "selected"
                if selected_count > 0
                else "eligible_not_selected"
            ),
            "maximum_selected": MAX_ITEMS_PER_CATEGORY,
            "research_only": True,
            "auto_apply": False,
        })

    body = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": "deterministic_outcome_aware_targeted_review_v1",
        "run_fingerprint": run_fingerprint,
        "protocol_version": protocol_version,
        "protocol_sha256": protocol_sha256,
        "evidence_digest": evidence_digest,
        "source_evidence_digests": source_digests,
        "closed_category_taxonomy": True,
        "category_order": list(CATEGORY_ORDER),
        "categories": category_rows,
        "items": items,
        "item_count": len(items),
        "maximum_item_count": MAX_QUEUE_ITEMS,
        "maximum_items_per_category": MAX_ITEMS_PER_CATEGORY,
        "queue_truncated": any(row["truncated_count"] > 0 for row in category_rows),
        "input_counts": {
            "idea_count": len(idea_rows),
            "episode_count": len(episode_rows),
            "matured_scoreable_episode_count": sum(
                row["scoreable"] for row in episodes
            ),
            "analysis_partition_count": len(analysis_rows),
            "missed_opportunity_detail_count": missed_available_count,
        },
        "human_feedback": {
            "optional": True,
            "required_for_automatic_conclusions": False,
            "append_only_required": True,
            "ledger_implemented_by_this_module": False,
            "labels": list(LABEL_TAXONOMY),
            "auto_apply": False,
        },
        "selection_uses_outcomes": True,
        "selection_changes_replay_results": False,
        "final_test_used_for_policy_selection": False,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    return {**body, "queue_digest": _digest_value(body)}


def _add_episode_candidates(
    candidates: dict[str, list[dict[str, Any]]],
    episodes: Sequence[dict[str, Any]],
) -> None:
    config = RadarDecisionConfig()
    thresholds = (
        ("actionability_score", "dashboard_watch_threshold", config.dashboard_watch_threshold),
        ("actionability_score", "actionability_threshold", config.actionability_threshold),
        ("actionability_score", "rapid_anomaly_actionability_threshold", config.rapid_anomaly_actionability_threshold),
        ("actionability_score", "high_confidence_threshold", config.high_confidence_threshold),
        ("evidence_confidence_score", "high_confidence_evidence_threshold", config.high_confidence_evidence_threshold),
        ("urgency_score", "rapid_anomaly_urgency_threshold", config.rapid_anomaly_urgency_threshold),
    )
    for episode in episodes:
        if episode["scoreable"]:
            distances = [
                (abs(score - threshold), field, name, threshold, score)
                for field, name, threshold in thresholds
                if (score := _finite(_value(episode["representative"], field)))
                is not None
            ]
            if distances:
                distance, field, name, threshold, score = min(
                    distances, key=lambda row: (row[0], row[2], row[1])
                )
                if distance <= BORDERLINE_DISTANCE_POINTS:
                    _append_episode_candidate(
                        candidates,
                        "threshold_borderline",
                        episode,
                        rank=(distance, -abs(episode["directional_return"]), episode["observed_at"], episode["episode_id"]),
                        reason={
                            "score_field": field,
                            "threshold_name": name,
                            "production_threshold": threshold,
                            "observed_score": score,
                            "absolute_distance_points": distance,
                            "maximum_distance_points": BORDERLINE_DISTANCE_POINTS,
                        },
                    )
            actionability = _finite(
                _value(episode["representative"], "actionability_score")
            )
            if (
                actionability is not None
                and actionability >= config.actionability_threshold
                and episode["directional_return"] <= 0.0
            ):
                _append_episode_candidate(
                    candidates,
                    "high_actionability_failure",
                    episode,
                    rank=(-actionability, episode["directional_return"], episode["observed_at"], episode["episode_id"]),
                    reason={
                        "actionability_score": actionability,
                        "production_actionability_threshold": config.actionability_threshold,
                    },
                )
            if (
                actionability is not None
                and actionability < config.dashboard_watch_threshold
                and episode["directional_return"] > 0.0
            ):
                _append_episode_candidate(
                    candidates,
                    "low_actionability_success",
                    episode,
                    rank=(actionability, -episode["directional_return"], episode["observed_at"], episode["episode_id"]),
                    reason={
                        "actionability_score": actionability,
                        "production_dashboard_threshold": config.dashboard_watch_threshold,
                    },
                )
            catalyst = _token(_value(episode["representative"], "catalyst_status"))
            if catalyst == "unknown" and episode["directional_return"] > 0.0:
                _append_episode_candidate(
                    candidates,
                    "unknown_catalyst_winner",
                    episode,
                    rank=(-episode["directional_return"], episode["observed_at"], episode["episode_id"]),
                    reason={"catalyst_status": "unknown"},
                )
            if catalyst == "confirmed" and episode["directional_return"] <= 0.0:
                _append_episode_candidate(
                    candidates,
                    "confirmed_catalyst_loser",
                    episode,
                    rank=(episode["directional_return"], episode["observed_at"], episode["episode_id"]),
                    reason={"catalyst_status": "confirmed"},
                )
        classification = episode["false_late"]
        if classification.get("late_idea") is True:
            pre_signal = _finite(
                classification.get("pre_signal_directional_move_7d_fraction")
            )
            chase = _finite(classification.get("chase_risk_score"))
            _append_episode_candidate(
                candidates,
                "late_idea",
                episode,
                rank=(-abs(pre_signal or 0.0), -(chase or 0.0), episode["observed_at"], episode["episode_id"]),
                reason={
                    "symptom_codes": _strings(classification.get("symptom_codes"), 16),
                    "issue_source_codes": _strings(classification.get("issue_source_codes"), 16),
                },
            )
        manipulation_codes = _manipulation_concern_codes(episode)
        if manipulation_codes:
            explicit = int("explicit_manipulation_marker" in manipulation_codes)
            _append_episode_candidate(
                candidates,
                "manipulation_concern_candidate",
                episode,
                rank=(-explicit, episode["directional_return"] if episode["scoreable"] else 0.0, episode["observed_at"], episode["episode_id"]),
                reason={
                    "classification": "concern_candidate",
                    "concern_basis_codes": manipulation_codes,
                    "manipulation_confirmed": False,
                },
            )
        inconsistency_codes = _data_quality_inconsistency_codes(episode)
        if inconsistency_codes:
            _append_episode_candidate(
                candidates,
                "inconsistent_data_quality",
                episode,
                rank=(-len(inconsistency_codes), episode["observed_at"], episode["episode_id"]),
                reason={"inconsistency_codes": inconsistency_codes},
            )


def _add_monotonicity_candidates(
    candidates: dict[str, list[dict[str, Any]]],
    episodes: Sequence[dict[str, Any]],
    analyses: Sequence[Mapping[str, Any]],
) -> None:
    by_partition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        if episode["scoreable"]:
            by_partition[episode["partition"]].append(episode)
    for analysis in analyses:
        partition = str(analysis.get("partition") or "")
        for score_row in _mapping_rows(analysis.get("score_monotonicity") or ()):
            score_field = str(score_row.get("score_field") or "")
            expected = str(score_row.get("expected_relationship") or "")
            for comparison in _mapping_rows(score_row.get("comparisons") or ()):
                if comparison.get("violation") is not True:
                    continue
                lower = _bucket_members(
                    by_partition.get(partition, ()), score_field, comparison.get("lower_bucket")
                )
                higher = _bucket_members(
                    by_partition.get(partition, ()), score_field, comparison.get("higher_bucket")
                )
                pair = _representative_violation_pair(lower, higher, expected)
                if pair is None:
                    continue
                lower_episode, higher_episode = pair
                pair_identity = {
                    "partition": partition,
                    "score_field": score_field,
                    "lower_episode_id": lower_episode["episode_id"],
                    "higher_episode_id": higher_episode["episode_id"],
                }
                target_id = "empirical-review-pair-v1:" + _digest_value(pair_identity)
                item = {
                    "target_kind": "episode_pair",
                    "target_id": target_id,
                    "episode_id": None,
                    "paired_episode_ids": [
                        lower_episode["episode_id"], higher_episode["episode_id"]
                    ],
                    "partition": partition,
                    "evidence_mode": str(analysis.get("evidence_mode") or ""),
                    "observed_at": min(
                        lower_episode["observed_at"], higher_episode["observed_at"]
                    ),
                    "symbol": "",
                    "canonical_asset_id": "",
                    "radar_route": "",
                    "primary_thesis_origin": "",
                    "catalyst_status": "",
                    "directional_bias": "",
                    "scores": {"score_field": score_field},
                    "outcome": {},
                    "data_quality": {},
                    "pair_examples": [
                        _pair_example(lower_episode, score_field, "lower_bucket"),
                        _pair_example(higher_episode, score_field, "higher_bucket"),
                    ],
                    "selection_reasons": {
                        "monotonicity_violation": {
                            "score_field": score_field,
                            "expected_relationship": expected,
                            "lower_bucket": comparison.get("lower_bucket"),
                            "higher_bucket": comparison.get("higher_bucket"),
                            "aggregate_observed_delta_fraction": _finite(
                                comparison.get("observed_delta_fraction")
                            ),
                            "aggregate_statistical_significance_claim": False,
                            "pair_is_representative_example_not_causal_proof": True,
                        }
                    },
                    "source_identity": {
                        "analysis_digest": str(analysis.get("analysis_digest") or ""),
                        "lower_episode_digest": lower_episode["episode_digest"],
                        "higher_episode_digest": higher_episode["episode_digest"],
                    },
                    "review_status": "unlabeled",
                    "causal_claim": False,
                    "policy_eligible": False,
                    "research_only": True,
                    "auto_apply": False,
                }
                delta = abs(_finite(comparison.get("observed_delta_fraction")) or 0.0)
                candidates["monotonicity_violation"].append({
                    "target_key": target_id,
                    "rank": (-delta, score_field, partition, target_id),
                    "item": item,
                })


def _add_missed_candidates(
    candidates: dict[str, list[dict[str, Any]]],
    controls: Mapping[str, Any],
) -> tuple[int, int, bool]:
    value = controls.get("missed_move_evaluation")
    missed = value if isinstance(value, Mapping) else {}
    details = [
        row
        for row in _mapping_rows(missed.get("missed_opportunities") or ())
        if row.get("qualifies_as_missed_opportunity") is True
    ]
    representative_rows = [
        wrapper.get("candidate")
        for wrapper in _mapping_rows(
            missed.get("reason_representative_examples") or ()
        )
        if isinstance(wrapper.get("candidate"), Mapping)
    ]
    representative_ids = {
        str(row.get("missed_move_id") or "") for row in representative_rows
    }
    source_rows: dict[str, Mapping[str, Any]] = {}
    for row in [*details, *representative_rows]:
        identity = str(row.get("missed_move_id") or _digest_value(row))
        source_rows[identity] = row
    controls_contract_digest = _declared_digest(
        controls.get("contract_digest"),
        fallback=_digest_value({
            "missed_opportunity_count": missed.get("missed_opportunity_count"),
            "missed_details": details,
            "reason_representatives": representative_rows,
        }),
        field="controls_contract_digest",
    )
    eligible_count = _nonnegative_int(missed.get("missed_opportunity_count"))
    if eligible_count < len(details):
        eligible_count = len(details)
    qualified_available = 0
    for row in source_rows.values():
        item, target_id, directional, observation = _missed_review_item(
            row,
            controls=controls,
            controls_contract_digest=controls_contract_digest,
        )
        qualified = row.get("qualifies_as_missed_opportunity") is True
        shared_reason = {
            "failure_stage": str(row.get("failure_stage") or ""),
            "trace_status": str(row.get("trace_status") or ""),
            "endpoint_rule_crossed": row.get("endpoint_rule_crossed") is True,
            "maximum_future_excursion_alone_sufficient": False,
            "primary_reason": str(row.get("primary_reason") or ""),
            "reason_codes": _strings(row.get("reason_codes"), 32),
            "qualification_state": str(row.get("qualification_state") or ""),
            "qualification_failure_reasons": _strings(
                row.get("qualification_failure_reasons"), 16
            ),
        }
        is_representative = target_id in representative_ids
        if qualified:
            qualified_available += 1
            qualified_item = _json_value(item)
            qualified_item["selection_reasons"] = {
                "missed_opportunity": shared_reason
            }
            candidates["missed_opportunity"].append({
                "target_key": target_id,
                "rank": (
                    0 if is_representative else 1,
                    str(row.get("primary_reason") or ""),
                    -abs(directional or 0.0),
                    str(observation.get("observed_at") or ""),
                    target_id,
                ),
                "item": qualified_item,
            })
        elif is_representative:
            excluded_item = _json_value(item)
            excluded_item["selection_reasons"] = {
                "economic_move_qualification_exclusion": {
                    **shared_reason,
                    "classified_as_missed_opportunity": False,
                }
            }
            candidates["economic_move_qualification_exclusion"].append({
                "target_key": target_id,
                "rank": (
                    str(row.get("primary_reason") or ""),
                    str(observation.get("observed_at") or ""),
                    target_id,
                ),
                "item": excluded_item,
            })
        validation_codes = _strings(
            row.get("projection_validation_error_codes"), 16
        )
        if validation_codes:
            inconsistent_item = _json_value(item)
            inconsistent_item["selection_reasons"] = {
                "inconsistent_data_quality": {
                    "inconsistency_codes": [
                        "canonical_projection_validation_failed"
                    ],
                    "projection_validation_error_codes": validation_codes,
                    "diagnostic_concern_class": str(
                        row.get("diagnostic_concern_class") or ""
                    ),
                }
            }
            candidates["inconsistent_data_quality"].append({
                "target_key": target_id,
                "rank": (
                    -len(validation_codes),
                    str(observation.get("observed_at") or ""),
                    target_id,
                ),
                "item": inconsistent_item,
            })
    source_truncated = (
        missed.get("missed_opportunities_truncated") is True
        or eligible_count > qualified_available
    )
    return eligible_count, qualified_available, source_truncated


def _missed_review_item(
    row: Mapping[str, Any],
    *,
    controls: Mapping[str, Any],
    controls_contract_digest: str,
) -> tuple[dict[str, Any], str, float | None, Mapping[str, Any]]:
    observation = (
        row.get("observation")
        if isinstance(row.get("observation"), Mapping)
        else {}
    )
    outcome = row.get("outcome") if isinstance(row.get("outcome"), Mapping) else {}
    target_id = str(row.get("missed_move_id") or "")
    if not target_id:
        target_id = "missed-move-v1:" + _digest_value({
            "observation": observation,
            "directional_bias": row.get("directional_bias"),
            "primary_endpoint_return_fraction": row.get(
                "primary_endpoint_return_fraction"
            ),
        })
    directional = _finite(
        outcome.get("primary_direction_adjusted_return")
        if outcome.get("primary_direction_adjusted_return") is not None
        else row.get("primary_endpoint_return_fraction")
    )
    item = {
        "target_kind": "missed_move",
        "target_id": target_id,
        "episode_id": None,
        "paired_episode_ids": [],
        "partition": str(observation.get("partition") or ""),
        "evidence_mode": str(controls.get("evidence_mode") or "historical_replay"),
        "observed_at": str(observation.get("observed_at") or ""),
        "symbol": str(observation.get("symbol") or ""),
        "canonical_asset_id": str(observation.get("canonical_asset_id") or ""),
        "radar_route": "not_operator_visible",
        "primary_thesis_origin": "unclassified_missed_move",
        "catalyst_status": "unavailable",
        "directional_bias": str(row.get("directional_bias") or ""),
        "scores": {},
        "outcome": _outcome_projection(outcome, directional),
        "data_quality": {
            "data_quality_mode": str(observation.get("data_quality_mode") or ""),
            "baseline_status": str(observation.get("baseline_status") or ""),
            "liquidity_tier": str(observation.get("liquidity_tier") or ""),
            "spread_status": "unavailable",
        },
        "pair_examples": [],
        "selection_reasons": {},
        "source_identity": {
            "missed_move_id": target_id,
            "observation_digest": str(observation.get("observation_digest") or ""),
            "controls_contract_digest": controls_contract_digest,
        },
        "review_status": "unlabeled",
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }
    return item, target_id, directional, observation


def _append_episode_candidate(
    candidates: dict[str, list[dict[str, Any]]],
    category: str,
    episode: Mapping[str, Any],
    *,
    rank: tuple[Any, ...],
    reason: Mapping[str, Any],
) -> None:
    item = _episode_item(episode)
    item["selection_reasons"] = {category: _json_value(reason)}
    candidates[category].append({
        "target_key": str(item["target_id"]),
        "rank": rank,
        "item": item,
    })


def _episode_item(episode: Mapping[str, Any]) -> dict[str, Any]:
    representative = episode["representative"]
    outcome = episode["outcome"]
    classification = episode["false_late"]
    return {
        "target_kind": "episode",
        "target_id": episode["episode_id"],
        "episode_id": episode["episode_id"],
        "paired_episode_ids": [],
        "partition": episode["partition"],
        "evidence_mode": _episode_evidence_mode(representative),
        "observed_at": episode["observed_at"],
        "symbol": str(representative.get("symbol") or ""),
        "canonical_asset_id": str(representative.get("canonical_asset_id") or ""),
        "radar_route": str(_value(representative, "radar_route") or ""),
        "primary_thesis_origin": str(
            _value(representative, "primary_thesis_origin") or ""
        ),
        "catalyst_status": str(_value(representative, "catalyst_status") or ""),
        "directional_bias": str(_value(representative, "directional_bias") or ""),
        "scores": {
            field: _finite(_value(representative, field))
            for field in (
                "actionability_score",
                "evidence_confidence_score",
                "risk_score",
                "urgency_score",
                "chase_risk_score",
            )
        },
        "outcome": _outcome_projection(outcome, episode["directional_return"]),
        "data_quality": {
            "data_quality_mode": str(representative.get("data_quality_mode") or ""),
            "replay_data_quality_mode": str(
                representative.get("replay_data_quality_mode") or ""
            ),
            "baseline_status": str(representative.get("baseline_status") or ""),
            "liquidity_tier": str(representative.get("liquidity_tier") or ""),
            "spread_status": str(_value(representative, "spread_status") or ""),
        },
        "false_positive": classification.get("false_positive") is True,
        "late_idea": classification.get("late_idea") is True,
        "symptom_codes": _strings(classification.get("symptom_codes"), 16),
        "pair_examples": [],
        "selection_reasons": {},
        "source_identity": {
            "episode_digest": episode["episode_digest"],
            "outcome_digest": episode["outcome_digest"],
            "candidate_id": str(representative.get("candidate_id") or ""),
            "core_opportunity_id": str(
                representative.get("core_opportunity_id") or ""
            ),
        },
        "review_status": "unlabeled",
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _outcome_projection(
    outcome: Mapping[str, Any], directional_return: float | None
) -> dict[str, Any]:
    return {
        "status": str(outcome.get("status") or ""),
        "primary_horizon": str(outcome.get("primary_horizon") or ""),
        "primary_direction_adjusted_return_fraction": directional_return,
        "primary_relative_return_vs_btc_fraction": _finite(
            outcome.get("primary_relative_return_vs_btc")
        ),
        "primary_relative_return_vs_eth_fraction": _finite(
            outcome.get("primary_relative_return_vs_eth")
        ),
        "max_favorable_excursion_fraction": _finite(
            outcome.get("max_favorable_excursion")
        ),
        "max_adverse_excursion_fraction": _finite(
            outcome.get("max_adverse_excursion")
        ),
        "time_to_mfe_hours": _finite(outcome.get("time_to_mfe_hours")),
        "time_to_mae_hours": _finite(outcome.get("time_to_mae_hours")),
        "time_to_invalidation_hours": _finite(
            outcome.get("time_to_invalidation_hours")
        ),
        "return_unit": "fraction",
    }


def _episode_views(
    episodes: Sequence[Mapping[str, Any]],
    idea_index: Mapping[str, Mapping[str, Any]],
    false_late: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for episode in episodes:
        representative_raw = episode.get("representative")
        outcome_raw = episode.get("representative_outcome")
        if not isinstance(representative_raw, Mapping) or not isinstance(
            outcome_raw, Mapping
        ):
            continue
        episode_id = str(episode.get("episode_id") or representative_raw.get("episode_id") or "")
        if not episode_id:
            continue
        idea = idea_index.get(str(representative_raw.get("candidate_id") or ""), {})
        representative = {**dict(idea), **dict(representative_raw)}
        outcome = dict(outcome_raw)
        identity_digest = _digest_value({
            "representative": representative,
            "outcome": outcome,
        })
        if episode_id in seen and seen[episode_id] != identity_digest:
            raise ValueError("empirical review duplicate episode drift")
        seen[episode_id] = identity_digest
        if any(row["episode_id"] == episode_id for row in output):
            continue
        directional = _finite(outcome.get("primary_direction_adjusted_return"))
        scoreable = outcome.get("status") == "matured" and directional is not None
        output.append({
            "episode_id": episode_id,
            "episode_digest": _declared_digest(
                episode.get("episode_digest"),
                fallback=identity_digest,
                field="episode_digest",
            ),
            "outcome_digest": _declared_digest(
                outcome.get("outcome_digest"),
                fallback=_digest_value(outcome),
                field="outcome_digest",
            ),
            "partition": str(representative.get("partition") or representative.get("replay_partition") or ""),
            "observed_at": str(representative.get("observed_at") or outcome.get("observed_at") or ""),
            "representative": representative,
            "outcome": outcome,
            "false_late": dict(false_late.get(episode_id) or {}),
            "directional_return": directional,
            "scoreable": scoreable,
        })
    return sorted(output, key=lambda row: (row["observed_at"], row["episode_id"]))


def _manipulation_concern_codes(episode: Mapping[str, Any]) -> list[str]:
    representative = episode["representative"]
    marker_fields = (
        representative.get("decision_hard_blockers"),
        representative.get("decision_soft_penalties"),
        representative.get("anomaly_type"),
    )
    marker_text = json.dumps(_json_value(marker_fields), sort_keys=True).casefold()
    codes: list[str] = []
    if any(
        marker in marker_text
        for marker in (
            "manipulation_suspected",
            "suspected_manipulation",
            "manipulation_risk_high",
            "wash_trad",
            "suspicious_low_liquidity",
            "low_liquidity_suspicious",
        )
    ):
        codes.append("explicit_manipulation_marker")
    risk_components = representative.get("risk_score_components")
    manipulation_risk = (
        _finite(risk_components.get("manipulation_risk"))
        if isinstance(risk_components, Mapping)
        else None
    )
    if manipulation_risk is not None and manipulation_risk >= 70.0:
        codes.append("high_manipulation_risk_component")
    classification = episode["false_late"]
    chase = _finite(classification.get("chase_risk_score"))
    liquidity = _token(representative.get("liquidity_tier"))
    if (
        classification.get("false_positive") is True
        and (chase or 0.0) >= 70.0
        and liquidity in {"low", "thin", "micro", "unknown", "unavailable"}
    ):
        codes.append("low_liquidity_high_chase_false_positive")
    return codes


def _episode_evidence_mode(representative: Mapping[str, Any]) -> str:
    partition = _token(
        representative.get("partition") or representative.get("replay_partition")
    )
    replay_mode = _token(representative.get("replay_mode"))
    if partition == "fixture" or "fixture" in replay_mode:
        return "fixture_replay"
    if _token(representative.get("data_mode")) == "replay" or replay_mode:
        return "historical_replay"
    return "unknown_replay_evidence"


def _data_quality_inconsistency_codes(episode: Mapping[str, Any]) -> list[str]:
    row = episode["representative"]
    codes: list[str] = []
    direct_mode = _token(row.get("data_quality_mode"))
    replay_mode = _token(row.get("replay_data_quality_mode"))
    if direct_mode and replay_mode and direct_mode != replay_mode:
        codes.append("data_quality_mode_conflict")
    baseline = _token(row.get("baseline_status"))
    warm = row.get("baseline_warm")
    if isinstance(warm, bool) and bool(baseline in {"warm", "complete"}) != warm:
        codes.append("baseline_maturity_conflict")
    visible = row.get("operator_visible_idea") is True or row.get("operator_visible") is True
    if row.get("point_in_time_universe_member") is False and visible:
        codes.append("operator_visible_outside_point_in_time_universe")
    if episode["outcome"].get("return_unit") not in (None, "", "fraction"):
        codes.append("unexpected_outcome_return_unit")
    if any(
        row.get(field) is True
        for field in (
            "decision_source_path_safety_failed",
            "decision_source_secret_safety_failed",
            "decision_source_side_effect_safety_failed",
        )
    ):
        codes.append("decision_source_safety_conflict")
    for error_code in _strings(row.get("projection_validation_error_codes"), 16):
        if error_code in _PROJECTION_VALIDATION_ERROR_CODES:
            codes.append(f"canonical_projection:{error_code}")
    return codes


def _representative_violation_pair(
    lower: Sequence[dict[str, Any]],
    higher: Sequence[dict[str, Any]],
    expected: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not lower or not higher:
        return None
    nondecreasing = expected.startswith("nondecreasing")
    if nondecreasing:
        low = min(lower, key=lambda row: (-row["directional_return"], row["episode_id"]))
        high = min(higher, key=lambda row: (row["directional_return"], row["episode_id"]))
        violates = low["directional_return"] > high["directional_return"]
    else:
        low = min(lower, key=lambda row: (row["directional_return"], row["episode_id"]))
        high = min(higher, key=lambda row: (-row["directional_return"], row["episode_id"]))
        violates = low["directional_return"] < high["directional_return"]
    return (low, high) if violates else None


def _bucket_members(
    episodes: Sequence[dict[str, Any]], score_field: str, bucket: Any
) -> list[dict[str, Any]]:
    bounds = _SCORE_BUCKETS.get(str(bucket or ""))
    if bounds is None:
        return []
    lower, upper = bounds
    return [
        episode
        for episode in episodes
        if (score := _finite(_value(episode["representative"], score_field)))
        is not None
        and lower <= score < upper
    ]


def _pair_example(
    episode: Mapping[str, Any], score_field: str, bucket_role: str
) -> dict[str, Any]:
    representative = episode["representative"]
    return {
        "bucket_role": bucket_role,
        "episode_id": episode["episode_id"],
        "episode_digest": episode["episode_digest"],
        "symbol": str(representative.get("symbol") or ""),
        "observed_at": episode["observed_at"],
        "score": _finite(_value(representative, score_field)),
        "primary_direction_adjusted_return_fraction": episode["directional_return"],
        "return_unit": "fraction",
    }


def _dedupe_and_sort(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = str(row.get("target_key") or "")
        if not key:
            continue
        previous = selected.get(key)
        if previous is None or tuple(row["rank"]) < tuple(previous["rank"]):
            selected[key] = row
    return sorted(
        selected.values(), key=lambda row: (tuple(row["rank"]), row["target_key"])
    )


def _round_robin_select(
    candidates: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for category_rank in range(MAX_ITEMS_PER_CATEGORY):
        for category in CATEGORY_ORDER:
            rows = candidates[category]
            if category_rank >= len(rows):
                continue
            candidate = rows[category_rank]
            key = str(candidate["target_key"])
            if key in selected:
                selected[key]["categories"].add(category)
                selected[key]["selection_reasons"].update(
                    candidate["item"].get("selection_reasons") or {}
                )
                selected[key]["category_ranks"][category] = category_rank
                continue
            if len(selected) >= MAX_QUEUE_ITEMS:
                continue
            item = _json_value(candidate["item"])
            selected[key] = {
                "item": item,
                "categories": {category},
                "selection_reasons": dict(item.get("selection_reasons") or {}),
                "category_ranks": {category: category_rank},
            }
    return selected


def _finalize_items(
    selected: Mapping[str, Mapping[str, Any]],
    *,
    run_fingerprint: str,
    protocol_version: str | None,
    protocol_sha256: str | None,
    queue_evidence_digest: str,
) -> list[dict[str, Any]]:
    category_index = {name: index for index, name in enumerate(CATEGORY_ORDER)}
    rows: list[dict[str, Any]] = []
    for key, selected_row in selected.items():
        item = dict(selected_row["item"])
        categories = sorted(selected_row["categories"], key=category_index.__getitem__)
        item["primary_category"] = categories[0]
        item["categories"] = categories
        item["selection_reasons"] = _json_value(selected_row["selection_reasons"])
        item["run_fingerprint"] = run_fingerprint
        item["protocol_version"] = protocol_version
        item["protocol_sha256"] = protocol_sha256
        item["queue_evidence_digest"] = queue_evidence_digest
        item["review_item_id"] = "empirical-review-item-v1:" + _digest_value({
            "run_fingerprint": run_fingerprint,
            "target_kind": item["target_kind"],
            "target_id": item["target_id"],
        })
        item["evidence_digest"] = _digest_value({
            name: value
            for name, value in item.items()
            if name not in {"evidence_digest", "rank"}
        })
        rows.append({
            **item,
            "_sort": (
                category_index[item["primary_category"]],
                selected_row["category_ranks"][item["primary_category"]],
                key,
            ),
        })
    rows.sort(key=lambda row: row["_sort"])
    output = []
    for index, row in enumerate(rows, 1):
        clean = {name: value for name, value in row.items() if name != "_sort"}
        output.append({"rank": index, **clean})
    return output


def _idea_index(ideas: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    digests: dict[str, str] = {}
    for row in ideas:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id:
            continue
        digest = _digest_value(row)
        if candidate_id in digests and digests[candidate_id] != digest:
            raise ValueError("empirical review duplicate idea drift")
        digests[candidate_id] = digest
        output[candidate_id] = row
    return output


def _false_late_index(
    analyses: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for analysis in analyses:
        for row in _mapping_rows(
            analysis.get("false_positive_and_late_classifications") or ()
        ):
            episode_id = str(row.get("episode_id") or "")
            if episode_id:
                output[episode_id] = row
    return output


def _source_evidence_digests(
    ideas: Sequence[Mapping[str, Any]],
    episodes: Sequence[Mapping[str, Any]],
    analyses: Sequence[Mapping[str, Any]],
    controls: Mapping[str, Any],
) -> dict[str, str]:
    idea_rows = [
        {
            "candidate_id": row.get("candidate_id"),
            "canonical_asset_id": row.get("canonical_asset_id"),
            "observed_at": row.get("observed_at"),
            "idea_evidence_digest": _digest_value(row),
        }
        for row in ideas
    ]
    episode_evidence = [
        {
            "episode_id": row.get("episode_id"),
            "episode_digest": _declared_digest(
                row.get("episode_digest"),
                fallback=_digest_value({
                    "representative": row.get("representative"),
                    "representative_outcome": row.get("representative_outcome"),
                }),
                field="episode_digest",
            ),
            "outcome_digest": _declared_digest(
                (row.get("representative_outcome") or {}).get("outcome_digest")
                if isinstance(row.get("representative_outcome"), Mapping)
                else None,
                fallback=_digest_value(row.get("representative_outcome") or {}),
                field="outcome_digest",
            ),
        }
        for row in episodes
    ]
    analysis_evidence = [
        {
            "partition": row.get("partition"),
            "analysis_digest": _declared_digest(
                row.get("analysis_digest"),
                fallback=_digest_value(row),
                field="analysis_digest",
            ),
        }
        for row in analyses
    ]
    missed = controls.get("missed_move_evaluation")
    missed_value = missed if isinstance(missed, Mapping) else {}
    control_evidence = {
        "contract_digest": _declared_digest(
            controls.get("contract_digest"),
            fallback=_digest_value({
                "missed_opportunity_count": missed_value.get(
                    "missed_opportunity_count"
                ),
                "missed_opportunities": missed_value.get("missed_opportunities") or [],
            }),
            field="controls_contract_digest",
        ),
        "missed_opportunity_count": missed_value.get("missed_opportunity_count"),
        "missed_detail_digests": sorted(
            _digest_value(row)
            for row in _mapping_rows(missed_value.get("missed_opportunities") or ())
        ),
    }
    return {
        "ideas": _digest_value(sorted(idea_rows, key=lambda row: str(row["candidate_id"]))),
        "episodes": _digest_value(sorted(episode_evidence, key=lambda row: str(row["episode_id"]))),
        "analyses": _digest_value(sorted(analysis_evidence, key=lambda row: str(row["partition"]))),
        "controls": _digest_value(control_evidence),
    }


def _protocol_identity(
    ideas: Sequence[Mapping[str, Any]],
    analyses: Sequence[Mapping[str, Any]],
    controls: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    versions = {
        str(value)
        for value in (
            *(row.get("replay_protocol_version") for row in ideas),
            *(row.get("protocol_version") for row in analyses),
            controls.get("protocol_version"),
        )
        if str(value or "")
    }
    digests = {
        str(value)
        for value in (
            *(row.get("replay_protocol_sha256") for row in ideas),
            *(row.get("protocol_sha256") for row in analyses),
            controls.get("protocol_sha256"),
        )
        if str(value or "")
    }
    if len(versions) > 1 or len(digests) > 1:
        raise ValueError("empirical review protocol identity drift")
    digest = next(iter(digests), None)
    if digest is not None and not _DIGEST.fullmatch(digest):
        raise ValueError("empirical review protocol digest invalid")
    return next(iter(versions), None), digest


def _episode_rows(
    value: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return _mapping_rows(value.get("episodes") or ())
    return _mapping_rows(value)


def _analysis_rows(
    value: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        partitions = value.get("partitions")
        if isinstance(partitions, Mapping):
            return [
                row
                for _name, row in sorted(partitions.items(), key=lambda pair: str(pair[0]))
                if isinstance(row, Mapping)
            ]
        if value.get("schema_id") == "decision_radar.empirical_replay_analysis":
            return [value]
        return [
            row
            for _name, row in sorted(value.items(), key=lambda pair: str(pair[0]))
            if isinstance(row, Mapping)
            and row.get("schema_id") == "decision_radar.empirical_replay_analysis"
        ]
    return _mapping_rows(value)


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _value(row: Mapping[str, Any], field: str) -> Any:
    if row.get(field) is not None:
        return row.get(field)
    projection = row.get("decision_projection")
    return projection.get(field) if isinstance(projection, Mapping) else None


def _strings(value: Any, maximum: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item)[:128] for item in value[:maximum] if str(item)]


def _token(value: Any) -> str:
    return str(value or "").strip().casefold()


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _declared_digest(value: Any, *, fallback: str, field: str) -> str:
    text = str(value or "")
    if not text:
        return fallback
    if not _DIGEST.fullmatch(text):
        raise ValueError(f"empirical review {field} invalid")
    return text


def _json_value(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("empirical review value is not canonical JSON") from exc


def _digest_value(value: Any) -> str:
    payload = json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = (
    "BORDERLINE_DISTANCE_POINTS",
    "CATEGORY_ORDER",
    "LABEL_TAXONOMY",
    "MAX_ITEMS_PER_CATEGORY",
    "MAX_QUEUE_ITEMS",
    "SCHEMA_ID",
    "build_targeted_review_queue",
)
