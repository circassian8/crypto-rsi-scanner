"""Bounded operator projection for the optional empirical hardening supplement."""

from __future__ import annotations

import math
from typing import Any, Mapping


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
SCORE_FIELDS = (
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "chase_risk_score",
)
FROZEN_COST_BPS = (0, 20, 50, 100, 200)


def project_hardening_operator_summary(
    value: Mapping[str, Any],
    *,
    validation_projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Project only bounded, operator-relevant fields after strict validation."""

    summary = value.get("operator_summary")
    if not isinstance(summary, Mapping):
        raise ValueError("hardening_supplement_operator_summary_missing")
    aggregate = _mapping_field(summary, "current_policy_aggregate")
    regime = _mapping_field(summary, "regime_summary")
    cost = _mapping_field(summary, "cost_summary")
    monotonicity = _mapping_field(summary, "score_monotonicity_summary")
    burden = _mapping_field(summary, "operator_burden_summary")
    gaps = _mapping_field(summary, "evidence_gap_summary")
    live = _mapping_field(summary, "live_status")
    route_values = _mapping_field(summary, "route_level_result")
    return {
        "result": _text(summary.get("result"), 96),
        "negative_conclusion": summary.get("negative_conclusion") is True,
        "final_confirmation_status": _text(
            summary.get("final_confirmation_status"), 96
        ),
        "current_policy_aggregate": {
            "scenario": _text(aggregate.get("scenario"), 96),
            "episode_count": _count(aggregate.get("episode_count")),
            "matured_visible_episode_count": _count(
                aggregate.get("matured_visible_episode_count")
            ),
            "mean_directional_return_fraction": _number(
                aggregate.get("mean_directional_return_fraction")
            ),
            "hit_rate": _number(aggregate.get("hit_rate")),
            "quick_failure_rate": _number(aggregate.get("quick_failure_rate")),
            "evidence_strength": _text(aggregate.get("evidence_strength"), 96),
        },
        "shadow_alternative_count": _count(
            summary.get("shadow_alternative_count")
        ),
        "unsupported_shadow_alternative_count": _count(
            summary.get("unsupported_shadow_alternative_count")
        ),
        "route_level_result": {
            route: _project_route(route_values.get(route))
            for route in ("risk_watch", "dashboard_watch")
        },
        "regime_dependence": _text(summary.get("regime_dependence"), 160),
        "regime_summary": {
            "status": _text(regime.get("status"), 160),
            "comparable_regime_count": _count(regime.get("comparable_regime_count")),
            "multiple_comparison_warning": _text(
                regime.get("multiple_comparison_warning"), 512
            ),
        },
        "historical_spread_observed": summary.get("historical_spread_observed")
        is True,
        "cost_basis": _text(summary.get("cost_basis"), 160),
        "cost_summary": {
            "historical_spread_observed": cost.get("historical_spread_observed")
            is True,
            "cost_bases": _strings(cost.get("cost_bases"), 8, 160),
            "interpretation": _text(cost.get("interpretation"), 256),
        },
        "score_monotonicity_violation_count": _count(
            summary.get("score_monotonicity_violation_count")
        ),
        "score_monotonicity_interpretation": _text(
            summary.get("score_monotonicity_interpretation"), 256
        ),
        "score_monotonicity_summary": {
            "violation_count": _count(monotonicity.get("violation_count")),
            "probabilistic_calibration_claim": monotonicity.get(
                "probabilistic_calibration_claim"
            )
            is True,
            "automatic_retuning": monotonicity.get("automatic_retuning") is True,
        },
        "maximum_urgent_items_on_one_day": _count(
            summary.get("maximum_urgent_items_on_one_day")
        ),
        "operator_burden_summary": {
            "maximum_urgent_items_on_one_day": _count(
                burden.get("maximum_urgent_items_on_one_day")
            ),
            "ideas_per_observed_day": _number(burden.get("ideas_per_observed_day")),
            "urgent_item_count": _count(burden.get("urgent_item_count")),
        },
        "routes_with_no_empirical_evidence": _strings(
            summary.get("routes_with_no_empirical_evidence"), len(ROUTES), 96
        ),
        "origins_with_no_empirical_evidence": _strings(
            summary.get("origins_with_no_empirical_evidence"), len(ORIGINS), 96
        ),
        "evidence_gap_summary": {
            "route_count": _count(gaps.get("route_count")),
            "origin_count": _count(gaps.get("origin_count")),
        },
        "missing_data": _strings(summary.get("missing_data"), 16, 512),
        "live_status": {
            "binding_status": _text(live.get("binding_status"), 160),
            "campaign_status": _text(live.get("campaign_status"), 160),
            "evidence_strength": _text(live.get("evidence_strength"), 160),
            "policy_conclusion": _text(live.get("policy_conclusion"), 160),
            "evidence_pooled_with_replay": live.get("evidence_pooled_with_replay")
            is True,
        },
        "production_policy_unchanged": summary.get("production_policy_unchanged")
        is True,
        "automatic_policy_application": summary.get(
            "automatic_policy_application"
        )
        is True,
        "route_conditioned_calibration": _project_route_conditioned(
            value.get("route_conditioned_calibration")
        ),
        "market_wide_risk_diagnostics": _project_market_wide_risk(
            value.get("market_wide_risk_diagnostics")
        ),
        "frozen_cost_sensitivity": _project_frozen_costs(validation_projection),
    }


def _project_route_conditioned(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("hardening_route_conditioned_calibration_missing")
    if tuple(value.get("partitions") or ()) != ("development", "validation"):
        raise ValueError("hardening_route_conditioned_partitions_invalid")
    if value.get("partition_route_score_diagnostics_closed") is not True:
        raise ValueError("hardening_route_conditioned_inventory_open")
    raw_rows = value.get("partition_route_score_diagnostics")
    if not isinstance(raw_rows, list) or len(raw_rows) != 2 * len(ROUTES):
        raise ValueError("hardening_route_conditioned_inventory_invalid")
    expected = tuple(
        (partition, route)
        for partition in ("development", "validation")
        for route in ROUTES
    )
    projected_rows = []
    observed = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise ValueError("hardening_route_conditioned_row_invalid")
        partition = _text(raw_row.get("partition"), 64)
        route = _text(raw_row.get("route"), 96)
        observed.append((partition, route))
        raw_scores = raw_row.get("score_diagnostics")
        if not isinstance(raw_scores, list) or len(raw_scores) != len(SCORE_FIELDS):
            raise ValueError("hardening_route_conditioned_scores_invalid")
        by_score: dict[str, dict[str, int]] = {}
        for raw_score in raw_scores:
            if not isinstance(raw_score, Mapping):
                raise ValueError("hardening_route_conditioned_score_invalid")
            score_field = _text(raw_score.get("score_field"), 96)
            if score_field in by_score:
                raise ValueError("hardening_route_conditioned_score_duplicate")
            by_score[score_field] = {
                "evaluated_pair_count": _count(
                    raw_score.get("evaluated_adjacent_pair_count")
                ),
                "violation_count": _count(raw_score.get("violation_count")),
            }
        if tuple(by_score) != SCORE_FIELDS:
            raise ValueError("hardening_route_conditioned_score_inventory_invalid")
        projected_rows.append({
            "partition": partition,
            "route": route,
            "episode_count": _count(raw_row.get("episode_count")),
            "matured_episode_count": _count(raw_row.get("matured_episode_count")),
            "score_counts": by_score,
            "evaluated_pair_count": sum(
                score["evaluated_pair_count"] for score in by_score.values()
            ),
            "violation_count": sum(
                score["violation_count"] for score in by_score.values()
            ),
        })
    if tuple(observed) != expected:
        raise ValueError("hardening_route_conditioned_closed_order_invalid")
    return {
        "partition_policy": _text(value.get("partition_policy"), 96),
        "partitions": ("development", "validation"),
        "score_fields": SCORE_FIELDS,
        "rows": projected_rows,
        "global_mixed_route_monotonicity_status": "confounded_by_route_composition",
        "probabilistic_calibration_claim": value.get(
            "probabilistic_calibration_claim"
        )
        is True,
        "automatic_retuning": False,
    }


def _project_market_wide_risk(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("hardening_market_wide_risk_diagnostics_missing")
    if tuple(value.get("partitions") or ()) != ("development", "validation"):
        raise ValueError("hardening_market_wide_risk_partitions_invalid")
    raw_days = value.get("daily_risk_groups")
    if not isinstance(raw_days, list) or len(raw_days) > 512:
        raise ValueError("hardening_market_wide_risk_days_invalid")
    peak = max(
        (row for row in raw_days if isinstance(row, Mapping)),
        key=lambda row: (
            _count(row.get("risk_item_count")),
            _count(row.get("distinct_asset_count")),
            _text(row.get("utc_day"), 32),
        ),
        default={},
    )
    top_assets = []
    ranked = peak.get("ranked_asset_evidence") if isinstance(peak, Mapping) else []
    if isinstance(ranked, list):
        for row in ranked[:10]:
            if isinstance(row, Mapping):
                asset = _text(row.get("canonical_asset_id"), 160)
                if asset:
                    top_assets.append(asset)
    peak_partition = _text(peak.get("partition"), 64)
    if not peak_partition:
        legacy = _strings(peak.get("partitions"), 1, 64)
        peak_partition = legacy[0] if legacy else ""
    return {
        "partition_policy": _text(value.get("partition_policy"), 96),
        "partitions": ("development", "validation"),
        "risk_item_count": _count(value.get("risk_item_count")),
        "partition_day_count": _count(value.get("risk_observed_day_count")),
        "market_wide_group_count": _count(value.get("market_wide_group_count")),
        "minimum_distinct_assets": _count(
            value.get("minimum_distinct_assets_for_market_wide_group")
        ),
        "outcomes_used_for_group_formation": value.get(
            "outcomes_used_for_group_formation"
        )
        is True,
        "correlated_family_suppression_applied": value.get(
            "correlated_family_suppression_applied"
        )
        is True,
        "correlated_family_suppression_status": _text(
            value.get("correlated_family_suppression_status"), 256
        ),
        "peak_group": {
            "utc_day": _text(peak.get("utc_day"), 32),
            "risk_item_count": _count(peak.get("risk_item_count")),
            "distinct_asset_count": _count(peak.get("distinct_asset_count")),
            "partition": peak_partition,
            "market_regime_status": _text(peak.get("market_regime_status"), 96),
            "top_assets": top_assets,
        },
    }


def _project_frozen_costs(
    validation_projection: Mapping[str, Any],
) -> dict[str, Any]:
    analyses = validation_projection.get("analyses")
    if not isinstance(analyses, list) or len(analyses) != 3:
        raise ValueError("hardening_frozen_cost_partitions_missing")
    if not all(isinstance(row, Mapping) for row in analyses):
        raise ValueError("hardening_frozen_cost_analysis_invalid")
    expected_partitions = ("development", "validation", "final_test")
    if tuple(str(row.get("partition") or "") for row in analyses) != expected_partitions:
        raise ValueError("hardening_frozen_cost_partitions_invalid")
    projected = []
    for analysis in analyses:
        costs = analysis.get("cost_sensitivity")
        if not isinstance(costs, Mapping):
            raise ValueError("hardening_frozen_cost_sensitivity_missing")
        raw_scenarios = costs.get("scenarios")
        if not isinstance(raw_scenarios, list) or not all(
            isinstance(row, Mapping) for row in raw_scenarios
        ):
            raise ValueError("hardening_frozen_cost_scenarios_missing")
        if tuple(row.get("round_trip_cost_bps") for row in raw_scenarios) != FROZEN_COST_BPS:
            raise ValueError("hardening_frozen_cost_inventory_invalid")
        scenarios = []
        for row in raw_scenarios:
            mean_net = _number(row.get("mean_net_directional_return_fraction"))
            hit_rate = _number(row.get("net_hit_rate"))
            if mean_net is None or hit_rate is None:
                raise ValueError("hardening_frozen_cost_value_invalid")
            scenarios.append({
                "round_trip_cost_bps": _count(row.get("round_trip_cost_bps")),
                "mean_net_directional_return_fraction": mean_net,
                "net_hit_rate": hit_rate,
            })
        partition = _text(analysis.get("partition"), 64)
        projected.append({
            "partition": partition,
            "sealed_final_display_only": partition == "final_test",
            "historical_spread_observed": costs.get("historical_spread_observed")
            is True,
            "cost_basis": _text(costs.get("cost_basis"), 256),
            "scenarios": scenarios,
        })
    return {
        "cost_bps": FROZEN_COST_BPS,
        "partitions": projected,
        "sealed_final_display_only": True,
        "execution_evidence": False,
    }


def _project_route(value: Any) -> dict[str, Any]:
    route = value if isinstance(value, Mapping) else {}
    partitions = route.get("partitions")
    partitions = partitions if isinstance(partitions, Mapping) else {}
    return {
        "evidence_status": _text(route.get("evidence_status"), 160),
        "matured_episode_count": _count(route.get("matured_episode_count")),
        "partitions": {
            partition: {
                "sample_size": _count(
                    _mapping_field(partitions, partition).get("sample_size")
                ),
                "result_direction": _text(
                    _mapping_field(partitions, partition).get("result_direction"),
                    160,
                ),
                "evidence_strength": _text(
                    _mapping_field(partitions, partition).get("evidence_strength"),
                    160,
                ),
            }
            for partition in ("development", "validation", "final_test")
        },
    }


def _mapping_field(value: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    selected = value.get(field)
    return selected if isinstance(selected, Mapping) else {}


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
    "FROZEN_COST_BPS",
    "ORIGINS",
    "ROUTES",
    "SCORE_FIELDS",
    "project_hardening_operator_summary",
)
