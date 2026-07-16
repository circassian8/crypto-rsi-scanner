"""Pure diagnostics over verified compact Empirical Lab archive rows.

The producers in this module accept the decoded idea and episode records from
``empirical_replay_persistence``.  They never read files, providers,
authorization, dashboard state, or production policy.  Score diagnostics are
descriptive and remain conditioned on the route that was actually assigned at
the frozen representative observation.  Market-wide risk grouping is formed
only from point-in-time representative fields and never from outcomes.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence

from . import empirical_replay_analysis
from . import empirical_report_diagnostic_validation
from . import empirical_replay_persistence
from . import empirical_replay_store
from . import empirical_validation_protocol
from ..radar import market_units


ROUTE_CALIBRATION_SCHEMA_ID = (
    empirical_report_diagnostic_validation.ROUTE_CALIBRATION_SCHEMA_ID
)
MARKET_RISK_SCHEMA_ID = empirical_report_diagnostic_validation.MARKET_RISK_SCHEMA_ID
SCHEMA_VERSION = empirical_report_diagnostic_validation.SCHEMA_VERSION

ROUTES = empirical_replay_analysis.ROUTES
SCORE_FIELDS = empirical_replay_analysis.SCORE_FIELDS
SCORE_BUCKETS = empirical_replay_analysis.SCORE_BUCKETS
SCORE_EXPECTATIONS = empirical_replay_analysis.SCORE_EXPECTATIONS
CONDITIONING_DIMENSIONS = empirical_report_diagnostic_validation.CONDITIONING_DIMENSIONS
SELECTION_PARTITIONS = empirical_report_diagnostic_validation.SELECTION_PARTITIONS
AFFECTED_ASSET_LIMITS = empirical_report_diagnostic_validation.AFFECTED_ASSET_LIMITS
CORRELATED_FAMILY_STATUS = empirical_report_diagnostic_validation.CORRELATED_FAMILY_STATUS

_HEX = frozenset("0123456789abcdef")
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
}


@dataclass(frozen=True)
class _Representative:
    episode_id: str
    candidate_id: str
    partition: str
    idea: Mapping[str, Any]
    projection: Mapping[str, Any]
    values: Mapping[str, Any]
    outcome: Mapping[str, Any] | None


def build_route_conditioned_calibration(
    idea_rows: Iterable[Mapping[str, Any]],
    episode_rows: Iterable[Mapping[str, Any]],
    *,
    source_run_fingerprint: str,
) -> dict[str, Any]:
    """Build descriptive score diagnostics from exact episode representatives."""

    fingerprint = _source_fingerprint(source_run_fingerprint)
    ideas = tuple(idea_rows)
    episodes = tuple(episode_rows)
    representatives = _representatives(ideas, episodes, include_outcomes=True)
    protocol = _protocol()
    descriptive_minimum = int(protocol["minimum_samples"]["descriptive"])
    cohort_minimum = int(protocol["minimum_samples"]["cohort_directional"])

    route_diagnostics = [
        _conditioned_cohort(
            [row for row in representatives if _route(row) == route],
            route=route,
            dimension="route",
            value=route,
            descriptive_minimum=descriptive_minimum,
            cohort_minimum=cohort_minimum,
        )
        for route in ROUTES
    ]
    partition_route_diagnostics = [
        {
            "partition": partition,
            **_conditioned_cohort(
                [
                    row
                    for row in representatives
                    if row.partition == partition and _route(row) == route
                ],
                route=route,
                dimension="route",
                value=route,
                descriptive_minimum=descriptive_minimum,
                cohort_minimum=cohort_minimum,
            ),
        }
        for partition in SELECTION_PARTITIONS
        for route in ROUTES
    ]
    dimension_values = {
        dimension: sorted(
            {
                _dimension_value(row, dimension)
                for row in representatives
            }
            | {"unknown"}
        )
        for dimension in CONDITIONING_DIMENSIONS
    }
    conditioned = [
        _conditioned_cohort(
            [
                row
                for row in representatives
                if _route(row) == route
                and _dimension_value(row, dimension) == value
            ],
            route=route,
            dimension=dimension,
            value=value,
            descriptive_minimum=descriptive_minimum,
            cohort_minimum=cohort_minimum,
        )
        for route in ROUTES
        for dimension in CONDITIONING_DIMENSIONS
        for value in dimension_values[dimension]
    ]
    composition = _between_route_composition(representatives)
    partitions = _partitions(representatives)
    payload: dict[str, Any] = {
        "schema_id": ROUTE_CALIBRATION_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": "route_conditioned_fixed_bucket_descriptive_diagnostics",
        "source_run_fingerprint": fingerprint,
        "partitions": partitions,
        "partition_policy": "development_and_validation_only",
        "input_basis": "verified_compact_idea_and_episode_rows",
        "archive_record_digests_preverified": True,
        "representative_join": "exact_candidate_snapshot_and_episode_identity",
        "episode_count": len(representatives),
        "idea_record_count": len(ideas),
        "episode_record_count": len(episodes),
        "score_fields": list(SCORE_FIELDS),
        "score_buckets": [
            {"name": label, "lower_inclusive": lower, "upper_exclusive": upper}
            for label, lower, upper in SCORE_BUCKETS
        ],
        "minimum_samples": {
            "adjacent_bucket_comparison_each_bucket": descriptive_minimum,
            "cohort_directional": cohort_minimum,
            "below_cohort_directional_status": "insufficient_exploratory",
        },
        "route_score_diagnostics": route_diagnostics,
        "partition_route_score_diagnostics": partition_route_diagnostics,
        "partition_route_score_diagnostic_count": (
            len(SELECTION_PARTITIONS) * len(ROUTES)
        ),
        "partition_route_score_diagnostics_closed": True,
        "route_conditioned_dimension_cohorts": conditioned,
        "between_route_bucket_composition": composition,
        "composition_reconciliation": _composition_reconciliation(
            representatives, composition
        ),
        "multiple_comparison_warning": protocol["statistics"][
            "multiple_comparison_policy"
        ],
        "outcome_unit": "direction_adjusted_return_fraction",
        "probabilistic_calibration_claim": False,
        "causal_claim": False,
        "model_changed": False,
        "production_policy_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    payload["diagnostic_digest"] = _digest(payload)
    return payload


def build_market_wide_risk_diagnostics(
    idea_rows: Iterable[Mapping[str, Any]],
    episode_rows: Iterable[Mapping[str, Any]],
    *,
    source_run_fingerprint: str,
) -> dict[str, Any]:
    """Group point-in-time risk-watch representatives without reading outcomes."""

    fingerprint = _source_fingerprint(source_run_fingerprint)
    ideas = tuple(idea_rows)
    episodes = tuple(episode_rows)
    representatives = _representatives(ideas, episodes, include_outcomes=False)
    risk_rows = [row for row in representatives if _route(row) == "risk_watch"]
    by_day: dict[tuple[str, str], list[_Representative]] = defaultdict(list)
    for row in risk_rows:
        by_day[(row.partition, _utc_day(row.values.get("observed_at")))].append(row)
    daily = [
        _daily_risk_group(partition, day, rows)
        for (partition, day), rows in sorted(by_day.items())
    ]
    payload: dict[str, Any] = {
        "schema_id": MARKET_RISK_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": "outcome_blind_exact_utc_day_cross_asset_risk_grouping",
        "source_run_fingerprint": fingerprint,
        "partitions": _partitions(representatives),
        "partition_policy": "development_and_validation_only",
        "input_basis": "verified_compact_idea_and_episode_rows",
        "archive_record_digests_preverified": True,
        "representative_join": "exact_candidate_snapshot_and_episode_identity",
        "risk_item_rule": "representative_radar_route_equals_risk_watch",
        "episode_count": len(representatives),
        "risk_item_count": len(risk_rows),
        "risk_observed_day_count": len(daily),
        "market_wide_group_count": sum(
            row["market_wide_episode_status"] == "formed" for row in daily
        ),
        "minimum_distinct_assets_for_market_wide_group": AFFECTED_ASSET_LIMITS[0],
        "affected_asset_limits": list(AFFECTED_ASSET_LIMITS),
        "affected_asset_ranking": [
            "return_24h_most_negative_missing_last",
            "volume_zscore_24h_highest_missing_last",
            "liquidity_usd_highest_missing_last",
            "canonical_asset_id_ascending",
        ],
        "daily_risk_groups": daily,
        "regime_conditioned_visibility": _regime_visibility(risk_rows),
        "correlated_family_suppression_status": CORRELATED_FAMILY_STATUS,
        "correlated_family_suppression_applied": False,
        "outcomes_used_for_group_formation": False,
        "outcome_fields_read_for_group_formation": False,
        "causal_claim": False,
        "model_changed": False,
        "production_policy_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    payload["diagnostic_digest"] = _digest(payload)
    return payload


def validate_route_conditioned_calibration(
    value: Mapping[str, Any], *, source_run_fingerprint: str | None = None
) -> dict[str, Any]:
    return empirical_report_diagnostic_validation.validate_route_conditioned_calibration(
        value, source_run_fingerprint=source_run_fingerprint
    )


def validate_market_wide_risk_diagnostics(
    value: Mapping[str, Any], *, source_run_fingerprint: str | None = None
) -> dict[str, Any]:
    return empirical_report_diagnostic_validation.validate_market_wide_risk_diagnostics(
        value, source_run_fingerprint=source_run_fingerprint
    )


def _conditioned_cohort(
    rows: Sequence[_Representative],
    *,
    route: str,
    dimension: str,
    value: str,
    descriptive_minimum: int,
    cohort_minimum: int,
) -> dict[str, Any]:
    diagnostics = [
        _score_diagnostic(
            rows,
            field,
            descriptive_minimum=descriptive_minimum,
            cohort_minimum=cohort_minimum,
        )
        for field in SCORE_FIELDS
    ]
    return {
        "route": route,
        "conditioning_dimension": dimension,
        "conditioning_value": value,
        "episode_count": len(rows),
        "matured_episode_count": sum(_matured(row) for row in rows),
        "score_diagnostics": diagnostics,
        "descriptive_only": True,
        "policy_eligible": False,
        "auto_apply": False,
    }


def _score_diagnostic(
    rows: Sequence[_Representative],
    field: str,
    *,
    descriptive_minimum: int,
    cohort_minimum: int,
) -> dict[str, Any]:
    buckets: list[dict[str, Any]] = []
    for label, lower, upper in SCORE_BUCKETS:
        members = [
            row for row in rows if lower <= _score(row.projection.get(field)) < upper
        ]
        returns = [
            value
            for row in members
            if (value := _directional_return(row)) is not None
        ]
        status, strength = _sample_status(
            len(returns), descriptive_minimum, cohort_minimum
        )
        buckets.append(
            {
                "score_bucket": label,
                "lower_inclusive": lower,
                "upper_exclusive": upper,
                "episode_count": len(members),
                "matured_episode_count": sum(_matured(row) for row in members),
                "matured_sample_size": len(returns),
                "sample_status": status,
                "evidence_strength": strength,
                "cohort_directional_minimum_met": len(returns) >= cohort_minimum,
                "mean_directional_return_fraction": (
                    round(mean(returns), 12) if returns else None
                ),
                "median_directional_return_fraction": (
                    round(median(returns), 12) if returns else None
                ),
                "hit_rate": (
                    round(sum(value > 0.0 for value in returns) / len(returns), 12)
                    if returns
                    else None
                ),
                "policy_eligible": False,
            }
        )
    comparisons = [
        _adjacent_comparison(
            lower,
            higher,
            expected=SCORE_EXPECTATIONS[field],
            descriptive_minimum=descriptive_minimum,
        )
        for lower, higher in zip(buckets, buckets[1:])
    ]
    return {
        "score_field": field,
        "expected_relationship": SCORE_EXPECTATIONS[field],
        "buckets": buckets,
        "adjacent_comparisons": comparisons,
        "evaluated_adjacent_pair_count": sum(
            row["evaluation_status"] == "evaluated" for row in comparisons
        ),
        "violation_count": sum(row.get("violation") is True for row in comparisons),
        "interpretation": "descriptive_route_conditioned_unadjusted",
        "probabilistic_calibration_claim": False,
        "model_changed": False,
        "policy_eligible": False,
        "auto_apply": False,
    }


def _adjacent_comparison(
    lower: Mapping[str, Any],
    higher: Mapping[str, Any],
    *,
    expected: str,
    descriptive_minimum: int,
) -> dict[str, Any]:
    eligible = (
        int(lower["matured_sample_size"]) >= descriptive_minimum
        and int(higher["matured_sample_size"]) >= descriptive_minimum
    )
    delta: float | None = None
    violation: bool | None = None
    if eligible:
        delta = round(
            float(higher["mean_directional_return_fraction"])
            - float(lower["mean_directional_return_fraction"]),
            12,
        )
        violation = delta < 0.0 if expected.startswith("nondecreasing") else delta > 0.0
    return {
        "lower_bucket": lower["score_bucket"],
        "higher_bucket": higher["score_bucket"],
        "lower_matured_sample_size": lower["matured_sample_size"],
        "higher_matured_sample_size": higher["matured_sample_size"],
        "minimum_matured_sample_size_each": descriptive_minimum,
        "evaluation_status": "evaluated" if eligible else "insufficient_sample",
        "observed_delta_fraction": delta,
        "expected_relationship": expected,
        "violation": violation,
        "statistical_significance_claim": False,
    }


def _between_route_composition(
    rows: Sequence[_Representative],
) -> list[dict[str, Any]]:
    route_totals = Counter(_route(row) for row in rows)
    output: list[dict[str, Any]] = []
    for field in SCORE_FIELDS:
        for label, lower, upper in SCORE_BUCKETS:
            members = [
                row
                for row in rows
                if lower <= _score(row.projection.get(field)) < upper
            ]
            counts = Counter(_route(row) for row in members)
            bucket_total = len(members)
            routes = [
                {
                    "route": route,
                    "episode_count": counts[route],
                    "share_of_score_bucket": (
                        round(counts[route] / bucket_total, 12)
                        if bucket_total
                        else None
                    ),
                    "share_of_route": (
                        round(counts[route] / route_totals[route], 12)
                        if route_totals[route]
                        else None
                    ),
                }
                for route in ROUTES
            ]
            output.append(
                {
                    "score_field": field,
                    "score_bucket": label,
                    "episode_count": bucket_total,
                    "routes": routes,
                    "route_counts_reconcile": (
                        sum(item["episode_count"] for item in routes) == bucket_total
                    ),
                }
            )
    return output


def _composition_reconciliation(
    rows: Sequence[_Representative],
    composition: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    per_field = []
    for field in SCORE_FIELDS:
        observed = sum(
            int(row["episode_count"])
            for row in composition
            if row["score_field"] == field
        )
        per_field.append(
            {
                "score_field": field,
                "expected_episode_count": len(rows),
                "bucket_membership_count": observed,
                "reconciles": observed == len(rows),
            }
        )
    return {
        "per_score_field": per_field,
        "all_score_fields_reconcile": all(row["reconciles"] for row in per_field),
        "all_route_counts_reconcile": all(
            row["route_counts_reconcile"] for row in composition
        ),
    }


def _daily_risk_group(
    partition: str, day: str, rows: Sequence[_Representative]
) -> dict[str, Any]:
    by_asset: dict[str, list[_Representative]] = defaultdict(list)
    for row in rows:
        by_asset[_asset_id(row)].append(row)
    selected = [
        sorted(asset_rows, key=_risk_rank)[0]
        for _asset, asset_rows in sorted(by_asset.items())
    ]
    ranked = sorted(selected, key=_risk_rank)
    assets = [_risk_asset(row, rank=index + 1) for index, row in enumerate(ranked)]
    regimes = Counter(_dimension_value(row, "market_regime") for row in rows)
    return {
        "partition": partition,
        "utc_day": day,
        "day_basis": "representative_observed_at_normalized_to_utc_date",
        "risk_item_count": len(rows),
        "distinct_asset_count": len(assets),
        "dependent_same_asset_item_count": len(rows) - len(assets),
        "market_wide_episode_status": (
            "formed" if len(assets) >= AFFECTED_ASSET_LIMITS[0]
            else "insufficient_distinct_assets"
        ),
        "affected_asset_lists": [
            {
                "limit": limit,
                "assets": [row["canonical_asset_id"] for row in assets[:limit]],
                "asset_count": min(len(assets), limit),
                "truncated": len(assets) > limit,
            }
            for limit in AFFECTED_ASSET_LIMITS
        ],
        "ranked_asset_evidence": assets[: AFFECTED_ASSET_LIMITS[-1]],
        "market_regime_counts": dict(sorted(regimes.items())),
        "market_regime_status": "consistent" if len(regimes) == 1 else "mixed",
        "correlated_family_suppression_status": CORRELATED_FAMILY_STATUS,
        "correlated_family_suppression_applied": False,
        "outcomes_used_for_group_formation": False,
        "policy_eligible": False,
        "auto_apply": False,
    }


def _risk_asset(row: _Representative, *, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "canonical_asset_id": _asset_id(row),
        "episode_id": row.episode_id,
        "candidate_id": row.candidate_id,
        "partition": row.partition,
        "return_24h_fraction": _return_24h(row),
        "volume_zscore_24h": _number(row.values.get("volume_zscore_24h")),
        "liquidity_usd": _liquidity(row),
        "market_regime": _dimension_value(row, "market_regime"),
    }


def _regime_visibility(rows: Sequence[_Representative]) -> list[dict[str, Any]]:
    grouped: dict[str, list[_Representative]] = defaultdict(list)
    for row in rows:
        grouped[_dimension_value(row, "market_regime")].append(row)
    grouped.setdefault("unknown", [])
    total = len(rows)
    return [
        {
            "market_regime": regime,
            "risk_item_count": len(grouped[regime]),
            "distinct_asset_count": len({_asset_id(row) for row in grouped[regime]}),
            "observed_day_count": len(
                {
                    (row.partition, _utc_day(row.values.get("observed_at")))
                    for row in grouped[regime]
                }
            ),
            "share_of_risk_items": (
                round(len(grouped[regime]) / total, 12) if total else None
            ),
            "descriptive_only": True,
            "policy_eligible": False,
        }
        for regime in sorted(grouped)
    ]


def _representatives(
    ideas_raw: Sequence[Mapping[str, Any]],
    episodes_raw: Sequence[Mapping[str, Any]],
    *,
    include_outcomes: bool,
) -> list[_Representative]:
    ideas = _idea_index(ideas_raw)
    preflight: list[tuple[Mapping[str, Any], Mapping[str, Any], str]] = []
    seen_episodes: set[str] = set()
    seen_members: set[str] = set()
    seen_representatives: set[str] = set()
    for episode in episodes_raw:
        if not isinstance(episode, Mapping):
            raise ValueError("diagnostic_episode_record_not_mapping")
        if episode.get("schema_id") != empirical_replay_persistence.EPISODE_RECORD_SCHEMA_ID:
            raise ValueError("diagnostic_episode_record_schema_invalid")
        episode_id = _required_text(episode.get("episode_id"), "episode_id")
        if episode_id in seen_episodes:
            raise ValueError("diagnostic_duplicate_episode_id")
        seen_episodes.add(episode_id)
        representative_id = _required_text(
            episode.get("representative_idea_id"), "representative_idea_id"
        )
        members = episode.get("members")
        if not isinstance(members, list) or not members:
            raise ValueError("diagnostic_episode_members_invalid")
        if episode.get("member_count") != len(members) or episode.get(
            "dependent_repeat_count"
        ) != len(members) - 1:
            raise ValueError("diagnostic_episode_member_count_mismatch")
        representative_idea = ideas.get(representative_id)
        if representative_idea is None:
            raise ValueError("diagnostic_episode_idea_reference_missing")
        expected_partition = _idea_partition(representative_idea)
        representative_member: Mapping[str, Any] | None = None
        for index, member in enumerate(members):
            if not isinstance(member, Mapping):
                raise ValueError("diagnostic_episode_member_invalid")
            candidate_id = _required_text(
                member.get("candidate_id"), "member_candidate_id"
            )
            if candidate_id in seen_members:
                raise ValueError("diagnostic_idea_member_reused")
            seen_members.add(candidate_id)
            idea = ideas.get(candidate_id)
            if idea is None:
                raise ValueError("diagnostic_episode_idea_reference_missing")
            if member.get("idea_snapshot_sha256") != idea.get("snapshot_sha256"):
                raise ValueError("diagnostic_episode_snapshot_reference_mismatch")
            if member.get("idea_id") != candidate_id:
                raise ValueError("diagnostic_episode_candidate_reference_mismatch")
            _validate_episode_member_identity(
                episode, idea, member, expected_partition=expected_partition
            )
            is_representative = member.get("is_representative") is True
            if not isinstance(member.get("is_representative"), bool):
                raise ValueError("diagnostic_episode_member_representative_flag_invalid")
            if is_representative:
                if representative_member is not None:
                    raise ValueError("diagnostic_multiple_representatives")
                representative_member = member
                if index != 0:
                    raise ValueError("diagnostic_representative_not_first")
        if (
            representative_member is None
            or representative_member.get("candidate_id") != representative_id
        ):
            raise ValueError("diagnostic_representative_reference_mismatch")
        if representative_id in seen_representatives:
            raise ValueError("diagnostic_representative_reused")
        seen_representatives.add(representative_id)
        idea = ideas[representative_id]
        partition = _idea_partition(idea)
        # This rejection deliberately precedes any representative_outcome read.
        if partition not in SELECTION_PARTITIONS:
            raise ValueError("diagnostic_final_test_or_nonselection_partition_rejected")
        _validate_episode_identity(episode, idea)
        preflight.append((episode, idea, episode_id))
    if seen_members != set(ideas):
        raise ValueError("diagnostic_idea_episode_membership_not_closed")

    result: list[_Representative] = []
    for episode, idea, episode_id in preflight:
        if include_outcomes:
            _validate_record_digest(
                episode,
                "archive_episode_sha256",
                "diagnostic_episode_digest_mismatch",
            )
        outcome: Mapping[str, Any] | None = None
        if include_outcomes:
            raw_outcome = episode.get("representative_outcome")
            if not isinstance(raw_outcome, Mapping):
                raise ValueError("diagnostic_representative_outcome_missing")
            outcome = raw_outcome
            if (
                str(outcome.get("episode_id") or "") != episode_id
                or str(outcome.get("idea_id") or "")
                != str(episode.get("representative_idea_id") or "")
            ):
                raise ValueError("diagnostic_representative_outcome_reference_mismatch")
            outcome_partition = str(outcome.get("partition") or "")
            if outcome_partition and outcome_partition != _idea_partition(idea):
                raise ValueError("diagnostic_representative_outcome_partition_mismatch")
        projection = idea.get("decision_projection")
        values = _representative_values(idea, episode_id)
        for field in SCORE_FIELDS:
            _score(projection.get(field))
        result.append(
            _Representative(
                episode_id=episode_id,
                candidate_id=str(episode.get("representative_idea_id") or ""),
                partition=_idea_partition(idea),
                idea=idea,
                projection=projection,
                values=values,
                outcome=outcome,
            )
        )
    return sorted(result, key=lambda row: (row.partition, row.episode_id))


def _idea_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("diagnostic_idea_record_not_mapping")
        if row.get("schema_id") != empirical_replay_persistence.IDEA_RECORD_SCHEMA_ID:
            raise ValueError("diagnostic_idea_record_schema_invalid")
        identity = row.get("identity")
        replay = row.get("replay")
        projection = row.get("decision_projection")
        if not all(isinstance(value, Mapping) for value in (identity, replay, projection)):
            raise ValueError("diagnostic_idea_record_values_invalid")
        candidate_id = _required_text(identity.get("candidate_id"), "candidate_id")
        if candidate_id in output:
            raise ValueError("diagnostic_duplicate_candidate_id")
        partition = _idea_partition(row)
        if partition not in SELECTION_PARTITIONS:
            raise ValueError("diagnostic_final_test_or_nonselection_partition_rejected")
        _validate_record_digest(
            row, "snapshot_sha256", "diagnostic_idea_snapshot_digest_mismatch"
        )
        output[candidate_id] = row
    return output


def _validate_episode_identity(
    episode: Mapping[str, Any], idea: Mapping[str, Any]
) -> None:
    identity = idea["identity"]
    replay = idea["replay"]
    projection = idea["decision_projection"]
    checks = (
        (
            str(episode.get("canonical_asset_id") or ""),
            str(identity.get("canonical_asset_id") or ""),
            "diagnostic_episode_asset_identity_mismatch",
        ),
        (
            str(episode.get("directional_bias") or ""),
            str(projection.get("directional_bias") or ""),
            "diagnostic_episode_directional_bias_mismatch",
        ),
        (
            str(episode.get("episode_start_at") or ""),
            str(replay.get("observed_at") or ""),
            "diagnostic_episode_representative_timestamp_mismatch",
        ),
    )
    for observed, expected, error in checks:
        if not observed or observed != expected:
            raise ValueError(error)


def _validate_episode_member_identity(
    episode: Mapping[str, Any],
    idea: Mapping[str, Any],
    member: Mapping[str, Any],
    *,
    expected_partition: str,
) -> None:
    identity = idea["identity"]
    replay = idea["replay"]
    projection = idea["decision_projection"]
    checks = (
        (identity.get("canonical_asset_id"), episode.get("canonical_asset_id"), "asset"),
        (projection.get("directional_bias"), episode.get("directional_bias"), "direction"),
        (member.get("observed_at"), replay.get("observed_at"), "timestamp"),
    )
    if _idea_partition(idea) != expected_partition:
        raise ValueError("diagnostic_episode_member_partition_mismatch")
    for observed, expected, label in checks:
        if observed in (None, "") or str(observed) != str(expected):
            raise ValueError(f"diagnostic_episode_member_{label}_mismatch")


def _representative_values(
    idea: Mapping[str, Any], episode_id: str
) -> dict[str, Any]:
    identity = idea["identity"]
    replay = idea["replay"]
    projection = idea["decision_projection"]
    context = idea.get("point_in_time_context")
    market = idea.get("market_features")
    value = {
        **(dict(context) if isinstance(context, Mapping) else {}),
        **(dict(market) if isinstance(market, Mapping) else {}),
        **dict(projection),
        "episode_id": episode_id,
        "candidate_id": identity.get("candidate_id"),
        "canonical_asset_id": identity.get("canonical_asset_id"),
        "observed_at": replay.get("observed_at"),
        "partition": replay.get("replay_partition"),
    }
    return value


def _validate_record_digest(
    row: Mapping[str, Any], digest_field: str, error: str
) -> None:
    expected = row.get(digest_field)
    payload = {key: value for key, value in row.items() if key != digest_field}
    observed = hashlib.sha256(
        empirical_replay_store.canonical_json_bytes(payload)
    ).hexdigest()
    if expected != observed:
        raise ValueError(error)


def _protocol() -> Mapping[str, Any]:
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("diagnostic_frozen_protocol_invalid:" + ";".join(errors))
    return protocol


def _directional_return(row: _Representative) -> float | None:
    if row.outcome is None:
        return None
    view = empirical_replay_analysis._EpisodeView(
        row.episode_id, row.values, row.outcome
    )
    return empirical_replay_analysis._directional_return(view)


def _matured(row: _Representative) -> bool:
    if row.outcome is None:
        return False
    view = empirical_replay_analysis._EpisodeView(
        row.episode_id, row.values, row.outcome
    )
    return empirical_replay_analysis._is_matured(view)


def _sample_status(
    count: int, descriptive_minimum: int, cohort_minimum: int
) -> tuple[str, str]:
    if count == 0:
        return "no_sample", "no_evidence"
    if count < descriptive_minimum:
        return "insufficient_sample", "insufficient"
    if count < cohort_minimum:
        return "insufficient_exploratory", "exploratory_below_cohort_minimum"
    return "cohort_directional_sample", "cohort_directional"


def _route(row: _Representative) -> str:
    value = _token(row.projection.get("radar_route"))
    if value not in ROUTES:
        raise ValueError("diagnostic_unknown_radar_route")
    return value


def _dimension_value(row: _Representative, dimension: str) -> str:
    value = _token(row.values.get(dimension))
    if dimension == "data_quality_mode" and not value:
        value = _token(row.values.get("replay_data_quality_mode"))
    return value or "unknown"


def _idea_partition(idea: Mapping[str, Any]) -> str:
    replay = idea.get("replay")
    if not isinstance(replay, Mapping):
        raise ValueError("diagnostic_idea_replay_invalid")
    return _required_text(replay.get("replay_partition"), "replay_partition")


def _partitions(rows: Sequence[_Representative]) -> list[str]:
    return list(SELECTION_PARTITIONS)


def _asset_id(row: _Representative) -> str:
    value = _token(row.values.get("canonical_asset_id"))
    if not value:
        raise ValueError("diagnostic_canonical_asset_id_required")
    return value


def _risk_rank(row: _Representative) -> tuple[Any, ...]:
    return_24h = _return_24h(row)
    volume_z = _number(row.values.get("volume_zscore_24h"))
    liquidity = _liquidity(row)
    return (
        return_24h is None,
        return_24h if return_24h is not None else 0.0,
        volume_z is None,
        -volume_z if volume_z is not None else 0.0,
        liquidity is None,
        -liquidity if liquidity is not None else 0.0,
        _asset_id(row),
        row.episode_id,
    )


def _return_24h(row: _Representative) -> float | None:
    raw = row.values.get("return_24h")
    if raw is None:
        return None
    value = _number(raw)
    if value is None:
        raise ValueError("diagnostic_return_24h_invalid")
    overrides: Mapping[str, Any] | None = None
    for key in market_units.RETURN_UNIT_METADATA_KEYS:
        if key not in row.values:
            continue
        candidate = row.values.get(key)
        if not isinstance(candidate, Mapping):
            raise ValueError("diagnostic_return_units_invalid")
        if overrides is None:
            overrides = candidate
    has_field_override = overrides is not None and "return_24h" in overrides
    has_global_declaration = any(
        row.values.get(key) not in (None, "")
        for key in ("return_unit", "source_return_unit", "market_return_unit", "unit")
    )
    if not has_field_override and not has_global_declaration:
        raise ValueError("diagnostic_return_24h_unit_missing_or_unknown")
    unit = market_units.return_unit_for_field(
        row.values,
        "return_24h",
        default=market_units.RETURN_UNIT_UNKNOWN,
    )
    if unit == market_units.RETURN_UNIT_UNKNOWN:
        raise ValueError("diagnostic_return_24h_unit_missing_or_unknown")
    if unit == market_units.RETURN_UNIT_FRACTION:
        if abs(value) > 3.0:
            raise ValueError("diagnostic_return_24h_fraction_implausible")
        return value
    if abs(value) > 300.0:
        raise ValueError("diagnostic_return_24h_percent_points_implausible")
    return value / 100.0


def _liquidity(row: _Representative) -> float | None:
    return _number(row.values.get("liquidity_usd"))


def _utc_day(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("diagnostic_observed_at_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("diagnostic_observed_at_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("diagnostic_observed_at_timezone_required")
    return parsed.astimezone(timezone.utc).date().isoformat()


def _score(value: Any) -> float:
    number = _number(value)
    if number is None or not 0.0 <= number <= 100.0:
        raise ValueError("diagnostic_score_out_of_bounds")
    return number


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _token(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


def _required_text(value: Any, field: str) -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        raise ValueError(f"diagnostic_{field}_required")
    return text


def _source_fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise ValueError("diagnostic_source_run_fingerprint_invalid")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        empirical_replay_store.canonical_json_bytes(value)
    ).hexdigest()


__all__ = [
    "AFFECTED_ASSET_LIMITS",
    "CONDITIONING_DIMENSIONS",
    "CORRELATED_FAMILY_STATUS",
    "MARKET_RISK_SCHEMA_ID",
    "ROUTE_CALIBRATION_SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_market_wide_risk_diagnostics",
    "build_route_conditioned_calibration",
    "validate_market_wide_risk_diagnostics",
    "validate_route_conditioned_calibration",
]
