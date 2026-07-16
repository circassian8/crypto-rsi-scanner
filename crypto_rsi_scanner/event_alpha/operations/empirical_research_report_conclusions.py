"""Bounded operator conclusions for empirical report publication."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


ROUTES = (
    "high_confidence_watch", "actionable_watch", "rapid_market_anomaly",
    "dashboard_watch", "fade_exhaustion_review", "risk_watch",
    "calendar_risk", "diagnostic",
)
ORIGINS = (
    "market_led", "catalyst_led", "technical_led", "derivatives_led",
    "onchain_led", "fundamental_led", "macro_led",
)


def build_conclusions(
    selection: Mapping[str, Any],
    final: Mapping[str, Any],
    *,
    confirmation: Mapping[str, Any],
    walk: Mapping[str, Any],
    simulation: Mapping[str, Any],
    selection_controls: Mapping[str, Any],
    final_controls: Mapping[str, Any],
    live_binding: Mapping[str, Any],
) -> dict[str, Any]:
    analyses = _partition_index(selection, final)
    route_findings = _closed_cohort_findings(
        analyses, names=ROUTES, field="route_cohorts"
    )
    origin_findings = _closed_cohort_findings(
        analyses, names=ORIGINS, field="primary_origin_cohorts"
    )
    route_samples = {
        name: {
            partition: int(row.get("matured_episode_count") or 0)
            for partition, row in finding["partitions"].items()
        }
        for name, finding in route_findings.items()
    }
    no_evidence = [
        name for name, finding in route_findings.items()
        if finding["evidence_status"] == "no_empirical_evidence"
    ]
    warnings = {
        partition: row.get("multiple_comparison_warning")
        for partition, row in analyses.items()
    } | {"policy_simulation": simulation.get("multiple_comparison_warning")}
    return {
        "validated": _validated_claim(route_samples),
        "what_is_validated": [
            "immutable historical replay and episode accounting completed for the reported partitions",
            "closed route and origin cohort accounting reconciles to persisted canonical ideas and episodes",
            "the recommendation seal and final confirmation are bound to the frozen protocol and exact selected-day denominators",
        ],
        "what_is_not_validated": [
            "causal alpha or probabilistic calibration",
            "intraday timing, observed spread, order-book execution, slippage, or adverse selection",
            "any route or origin with no matured empirical episode",
            "automatic production threshold, route, or policy changes",
        ],
        "route_findings": route_findings,
        "origin_findings": origin_findings,
        "route_matured_episode_samples": route_samples,
        "routes_with_no_empirical_evidence": no_evidence,
        "no_evidence_is_not_validation": True,
        "score_monotonicity": _monotonicity_findings(analyses),
        "cost_and_survivability": {
            partition: {
                "cost_sensitivity": row.get("cost_sensitivity"),
                "survivability": row.get("survivability"),
            }
            for partition, row in analyses.items()
        },
        "walk_forward_stability": {
            key: walk.get(key)
            for key in (
                "status", "fold_count", "nonempty_fold_count",
                "outcome_evaluable_fold_count", "minimum_fold_count",
                "outcome_purge_rule", "selected_observation_day_count",
                "observed_day_denominator_basis", "final_test_accessed",
            )
        },
        "regime_and_data_quality": _regime_quality(analyses),
        "missed_opportunities": {
            partition: row.get("missed_opportunity_summary")
            for partition, row in analyses.items()
        } | {
            "selection_controls": selection_controls.get("missed_move_evaluation"),
            "final_test_controls": final_controls.get("missed_move_evaluation"),
        },
        "false_positives_and_late_ideas": {
            partition: row.get("false_positive_and_late_summary")
            for partition, row in analyses.items()
        },
        "operator_burden": {
            partition: row.get("operator_burden")
            for partition, row in analyses.items()
        },
        "shadow_recommendations": {
            "selection": simulation.get("recommendations", []),
            "final_confirmation": confirmation.get("confirmations", []),
            "human_approval_required": True,
            "auto_apply": False,
        },
        "multiple_comparison_warnings": warnings,
        "live_campaign_integration": _live_conclusion(live_binding),
        "additional_data_most_needed": [
            "observed bid-ask spread and order-book execution-quality snapshots",
            "intraday bars and exact decision-to-review latency",
            "direct catalyst, calendar, derivatives, and on-chain evidence with point-in-time lineage",
            "more independent matured episodes across routes, regimes, and data-quality cohorts",
        ],
        **_confirmation_summary(confirmation),
        "what_remains_unchanged": {
            "thresholds": True, "routes": True, "production_policy": True,
            "dashboard_authority": True, "provider_authorization": True,
            "notifications_and_execution": True,
        },
        "confirmation_verification_scope": "canonical persisted scenario reduction is exact-equal; compact reports do not reconstruct stripped raw threshold contexts or re-evaluate Decision v2",
        "next_human_boundary": "review sealed confirmation with sample size, regime coverage, data quality, cost survivability, and operator burden before any explicit policy decision",
        "causal_claim": False,
        "probabilistic_calibration_claim": False,
        "trade_recommendation": False,
        "production_policy_unchanged": True,
        "automatic_policy_application": False,
    }


def _validated_claim(samples: Mapping[str, Mapping[str, int]]) -> dict[str, Any]:
    return {
        "claim": "historical replay, episode accounting, controls, walk-forward, and sealed final-test mechanics executed under immutable bindings",
        "sample_size": sum(sum(parts.values()) for parts in samples.values()),
        "sample_unit": "matured_route_episode_memberships",
        "partition": "development_validation_and_final_test",
        "evidence_strength": "historical_replay_descriptive",
        "uncertainty": "route samples are uneven and are not causal evidence",
        "evidence_lane": "historical_replay",
        "policy_eligible": False,
        "human_approval_required": True,
    }


def _confirmation_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "final_confirmation_status": value.get("confirmation_status"),
        "confirmed_candidate_count": value.get("confirmed_candidate_count", 0),
        "rejected_candidate_count": value.get("rejected_candidate_count", 0),
        "insufficient_sample_candidate_count": value.get(
            "insufficient_sample_candidate_count", 0
        ),
    }


def _partition_index(*groups: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(partition): row
        for group in groups
        for partition, row in group.get("partitions", {}).items()
        if isinstance(row, Mapping)
    }


def _closed_cohort_findings(
    analyses: Mapping[str, Mapping[str, Any]],
    *,
    names: Sequence[str],
    field: str,
) -> dict[str, Any]:
    findings: dict[str, Any] = {}
    for name in names:
        partitions: dict[str, Any] = {}
        for partition, analysis in analyses.items():
            index = {
                str(row.get("cohort")): row
                for row in analysis.get(field, []) if isinstance(row, Mapping)
            }
            row = index.get(name, {})
            partitions[partition] = {
                key: row.get(key)
                for key in (
                    "episode_count", "matured_episode_count", "sample_size",
                    "sample_status", "evidence_strength", "result_direction",
                    "uncertainty",
                )
            }
        matured = sum(int(row.get("matured_episode_count") or 0) for row in partitions.values())
        findings[name] = {
            "matured_episode_count": matured,
            "sample_unit": "episode_representative",
            "evidence_status": (
                "historical_descriptive_evidence" if matured
                else "no_empirical_evidence"
            ),
            "partitions": partitions,
            "policy_eligible": False,
        }
    return findings


def _monotonicity_findings(
    analyses: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    findings: dict[str, Any] = {}
    for partition, analysis in analyses.items():
        rows = [
            row for row in analysis.get("score_monotonicity", [])
            if isinstance(row, Mapping)
        ]
        evaluated = sum(row.get("evaluation_status") == "evaluated" for row in rows)
        violations = sum(int(row.get("violation_count") or 0) for row in rows)
        findings[partition] = {
            "score_field_count": len(rows),
            "evaluated_score_field_count": evaluated,
            "violation_count": violations,
            "status": (
                "not_evaluable" if not evaluated
                else "violations_observed" if violations
                else "evaluated_no_observed_violations"
            ),
            "probabilistic_calibration_claim": False,
            "fields": rows,
        }
    return findings


def _regime_quality(
    analyses: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        partition: {
            "market_regime_cohorts": row.get("market_regime_cohorts", []),
            "data_quality_cohorts": row.get("data_quality_cohorts", []),
            "liquidity_tier_cohorts": row.get("liquidity_tier_cohorts", []),
        }
        for partition, row in analyses.items()
    }


def _live_conclusion(binding: Mapping[str, Any]) -> dict[str, Any]:
    projection = binding.get("canonical_projection")
    return {
        "status": binding.get("status"),
        "canonical_projection_sha256": binding.get("canonical_projection_sha256"),
        "campaign_status": (
            projection.get("campaign_status") if isinstance(projection, Mapping)
            else None
        ),
        "campaign_metrics": (
            projection.get("campaign_metrics") if isinstance(projection, Mapping)
            else None
        ),
        "evidence_pooled_with_replay": False,
        "separate_observational_lane": True,
    }


__all__ = ["ORIGINS", "ROUTES", "build_conclusions"]
