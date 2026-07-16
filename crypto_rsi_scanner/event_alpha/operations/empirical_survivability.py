"""Pure cost, capacity, and operating-constraint replay sensitivities.

This module is intentionally descriptive.  Scenario definitions come only
from the frozen empirical-validation protocol.  Idea selection for capacity
constraints is chronological and outcome-blind; outcomes are joined only
after the selection has been frozen.  No result is eligible to mutate a
production policy or to make an execution claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_survivability"
SCHEMA_VERSION = 1
METHOD = "frozen_outcome_blind_cost_capacity_and_constraint_sensitivity"
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
HORIZON_DAYS = (1, 3, 7, 14)
_DIRECTION_SIGN = {"long": 1.0, "fade_short_review": -1.0, "risk": -1.0}
_MAX_SELECTION_IDS = 256
_ZERO_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "notifications": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
    "writes": 0,
}


@dataclass(frozen=True)
class _Idea:
    episode_id: str
    observed_at: datetime
    route: str
    direction_sign: float | None
    liquidity_usd: float | None
    row: Mapping[str, Any]


def build_empirical_survivability(
    representatives: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]] = (),
    *,
    partition: str,
    evidence_mode: str,
) -> dict[str, Any]:
    """Return bounded deterministic sensitivities with zero side effects."""

    protocol = _frozen_protocol()
    selected_partition, selected_mode = _validate_context(
        partition, evidence_mode, protocol
    )
    raw_ideas = list(representatives)
    ideas, idea_diagnostics = _normalize_ideas(
        raw_ideas, partition=selected_partition
    )
    outcome_index, outcome_diagnostics = _outcome_index(
        outcomes, partition=selected_partition
    )
    costs = protocol["cost_scenarios"]
    minimums = protocol["minimum_samples"]
    descriptive_minimum = int(minimums["descriptive"])
    cohort_minimum = int(minimums["cohort_directional"])

    result: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(
            protocol
        ),
        "partition": selected_partition,
        "evidence_mode": selected_mode,
        "input_basis": "episode_representative_ideas_and_frozen_path_outcomes",
        "input_idea_count": len(raw_ideas),
        "eligible_idea_count": len(ideas),
        "idea_input_diagnostics": idea_diagnostics,
        "outcome_input_diagnostics": outcome_diagnostics,
        "route_cost_survivability": _route_cost_survivability(
            ideas,
            outcome_index,
            costs=costs,
            minimum=cohort_minimum,
        ),
        "review_delay_sensitivity": _review_delay_sensitivity(
            ideas,
            outcome_index,
            delays=costs["review_delay_days"],
            minimum=descriptive_minimum,
        ),
        "component_cost_profiles": _component_profile_sensitivity(
            ideas,
            outcome_index,
            profiles=costs["component_profiles"],
            minimum=descriptive_minimum,
        ),
        "position_liquidity_capacity": _liquidity_capacity(
            ideas,
            fractions=costs["position_liquidity_fraction_scenarios"],
            minimum=descriptive_minimum,
        ),
        "simultaneous_position_caps": _simultaneous_cap_sensitivity(
            ideas,
            outcome_index,
            limits=costs["maximum_simultaneous_ideas"],
            minimum=descriptive_minimum,
        ),
        "daily_idea_caps": _daily_cap_sensitivity(
            ideas,
            outcome_index,
            limits=costs["maximum_daily_ideas"],
            minimum=descriptive_minimum,
        ),
        "fixed_stop_loss_sensitivity": _fixed_stop_sensitivity(
            ideas,
            outcome_index,
            stops=costs["stop_loss_fraction_scenarios"],
            minimum=descriptive_minimum,
        ),
        "trailing_stop_sensitivity": _trailing_stop_unavailable(
            costs["trailing_stop_fraction_scenarios"],
            path_status=str(costs["intraday_path_order_status"]),
        ),
        "maximum_holding_time_sensitivity": _holding_time_sensitivity(
            ideas,
            outcome_index,
            minimum=descriptive_minimum,
        ),
        "return_unit": "fraction",
        "cost_unit": "basis_points",
        "liquidity_capacity_unit": "usd_notional",
        "sign_convention": {
            "positive_return": "favorable_for_declared_direction",
            "negative_return": "adverse_for_declared_direction",
            "mae": "nonpositive_direction_adjusted_fraction",
        },
        "selection_basis": (
            "chronological_point_in_time_representative_fields_only;"
            "outcomes_joined_after_selection"
        ),
        "outcomes_used_for_selection": 0,
        "causal_claim": False,
        "execution_claim": False,
        "production_policy_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    result["sample_status"] = _sample_status(
        len(ideas), descriptive_minimum
    )
    result["evidence_status"] = _evidence_status(result["sample_status"])
    result["analysis_digest"] = _digest(result)
    return result


def _frozen_protocol() -> dict[str, Any]:
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("frozen_protocol_invalid:" + ";".join(errors))
    required = {
        "round_trip_cost_bps",
        "review_delay_days",
        "position_liquidity_fraction_scenarios",
        "maximum_simultaneous_ideas",
        "maximum_daily_ideas",
        "component_profiles",
        "stop_loss_fraction_scenarios",
        "trailing_stop_fraction_scenarios",
        "intraday_path_order_status",
    }
    costs = protocol.get("cost_scenarios")
    if not isinstance(costs, Mapping) or required - set(costs):
        raise ValueError("frozen_protocol_cost_scenarios_incomplete")
    return protocol


def _validate_context(
    partition: str,
    evidence_mode: str,
    protocol: Mapping[str, Any],
) -> tuple[str, str]:
    if not isinstance(partition, str) or not partition.strip():
        raise ValueError("partition_required")
    if not isinstance(evidence_mode, str) or not evidence_mode.strip():
        raise ValueError("evidence_mode_required")
    selected_partition = partition.strip()
    selected_mode = evidence_mode.strip()
    allowed = {
        str(row["name"])
        for row in protocol["partitions"]
        if isinstance(row, Mapping)
    }
    fixture = selected_partition == "fixture" and "fixture" in selected_mode.casefold()
    if selected_partition not in allowed and not fixture:
        raise ValueError("partition_not_frozen_protocol_partition")
    return selected_partition, selected_mode


def _normalize_ideas(
    raw_rows: Sequence[Any], *, partition: str
) -> tuple[list[_Idea], dict[str, Any]]:
    reasons: Counter[str] = Counter()
    ideas: list[_Idea] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            reasons["non_mapping_idea"] += 1
            continue
        row = _closed_projection(raw)
        claimed = str(row.get("replay_partition") or row.get("partition") or "")
        if claimed and claimed != partition:
            raise ValueError("representative_partition_mismatch")
        episode_id = _text(row.get("episode_id"))
        if not episode_id:
            reasons["episode_id_missing"] += 1
            continue
        if episode_id in seen:
            raise ValueError("duplicate_representative_episode_id")
        observed = _utc(row.get("observed_at"))
        if observed is None:
            reasons["observed_at_missing_or_invalid"] += 1
            continue
        seen.add(episode_id)
        direction = _text(row.get("directional_bias"))
        route = _text(row.get("radar_route")) or "unclassified"
        ideas.append(
            _Idea(
                episode_id=episode_id,
                observed_at=observed,
                route=route,
                direction_sign=_DIRECTION_SIGN.get(direction),
                liquidity_usd=_liquidity_usd(row),
                row=row,
            )
        )
    ideas.sort(key=_idea_order)
    return ideas, {
        "status": "complete" if not reasons else "partial",
        "accepted_count": len(ideas),
        "excluded_count": sum(reasons.values()),
        "excluded_reason_counts": dict(sorted(reasons.items())),
        "unclassified_route_count": sum(row.route not in ROUTES for row in ideas),
    }


def _outcome_index(
    raw_rows: Iterable[Mapping[str, Any]], *, partition: str
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    reasons: Counter[str] = Counter()
    supplied = 0
    for raw in raw_rows:
        supplied += 1
        if not isinstance(raw, Mapping):
            reasons["non_mapping_outcome"] += 1
            continue
        claimed = str(raw.get("replay_partition") or raw.get("partition") or "")
        if claimed and claimed != partition:
            raise ValueError("outcome_partition_mismatch")
        episode_id = _text(raw.get("episode_id"))
        if not episode_id:
            reasons["episode_id_missing"] += 1
            continue
        if episode_id in index:
            raise ValueError("duplicate_outcome_episode_id")
        index[episode_id] = dict(raw)
    return index, {
        "status": "complete" if not reasons else "partial",
        "supplied_count": supplied,
        "indexed_count": len(index),
        "excluded_reason_counts": dict(sorted(reasons.items())),
    }


def _route_cost_survivability(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    costs: Mapping[str, Any],
    minimum: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for route in ROUTES:
        selected = [idea for idea in ideas if idea.route == route]
        gross = _return_metrics(selected, outcomes, horizon_days=3, minimum=minimum)
        scenarios = []
        for raw_bps in costs["round_trip_cost_bps"]:
            bps = int(raw_bps)
            metrics = _return_metrics(
                selected,
                outcomes,
                horizon_days=3,
                cost_fraction=bps / 10_000.0,
                minimum=minimum,
            )
            scenarios.append(
                {
                    "round_trip_cost_bps": bps,
                    "round_trip_cost_fraction": bps / 10_000.0,
                    "cost_basis": costs["unobserved_cost_label"],
                    "historical_cost_observed": False,
                    "metrics": metrics,
                    "mean_survives_assumed_cost": _positive_mean(metrics),
                }
            )
        rows.append(
            {
                "route": route,
                "episode_count": len(selected),
                "sample_status": gross["sample_status"],
                "evidence_status": gross["evidence_status"],
                "gross_metrics": gross,
                "break_even_mean_round_trip_cost_bps": _break_even_bps(gross),
                "maximum_tolerable_round_trip_cost_bps": _break_even_bps(gross),
                "maximum_tolerable_cost_basis": (
                    "gross_mean_direction_adjusted_return_break_even;"
                    "descriptive_not_an_execution_limit"
                ),
                "assumed_cost_scenarios": scenarios,
            }
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "route_order": list(ROUTES),
        "routes": rows,
        "historical_spread_observation_status": costs[
            "historical_spread_observation_status"
        ],
        "costs_are_assumed_not_observed": True,
    }


def _review_delay_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    delays: Sequence[Any],
    minimum: int,
) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for raw_delay in delays:
        delay = int(raw_delay)
        metrics = _return_metrics(
            ideas,
            outcomes,
            horizon_days=3,
            review_delay_days=delay,
            minimum=minimum,
        )
        scenarios.append(
            {
                "review_delay_days": delay,
                "entry_basis": "idea_close" if delay == 0 else "1d_close",
                "exit_basis": "3d_close",
                "remaining_holding_days": 3 - delay,
                "selection_uses_outcomes": False,
                "metrics": metrics,
                "routes": [
                    {
                        "route": route,
                        "metrics": _return_metrics(
                            [idea for idea in ideas if idea.route == route],
                            outcomes,
                            horizon_days=3,
                            review_delay_days=delay,
                            minimum=minimum,
                        ),
                    }
                    for route in ROUTES
                ],
            }
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "scenarios": scenarios,
        "delay_entry_math": (
            "direction_sign*((1+raw_3d_return)/(1+raw_1d_return)-1)"
        ),
        "delay_is_assumed_review_and_execution_timing": True,
    }


def _component_profile_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    profiles: Sequence[Any],
    minimum: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    component_names = (
        "fee_bps",
        "spread_bps",
        "slippage_bps",
        "adverse_selection_bps",
    )
    for raw in profiles:
        if not isinstance(raw, Mapping):
            raise ValueError("component_profile_not_mapping")
        components = {name: int(raw.get(name) or 0) for name in component_names}
        if any(value < 0 for value in components.values()):
            raise ValueError("component_profile_negative_bps")
        total = sum(components.values())
        rows.append(
            {
                "name": str(raw.get("name") or "unnamed_profile"),
                "components_bps": components,
                "total_round_trip_cost_bps": total,
                "total_round_trip_cost_fraction": total / 10_000.0,
                "component_observation_status": {
                    name.removesuffix("_bps"): "assumed_not_observed"
                    for name in component_names
                },
                "metrics": _return_metrics(
                    ideas,
                    outcomes,
                    horizon_days=3,
                    cost_fraction=total / 10_000.0,
                    minimum=minimum,
                ),
                "routes": [
                    {
                        "route": route,
                        "metrics": _return_metrics(
                            [idea for idea in ideas if idea.route == route],
                            outcomes,
                            horizon_days=3,
                            cost_fraction=total / 10_000.0,
                            minimum=minimum,
                        ),
                    }
                    for route in ROUTES
                ],
            }
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "profiles": rows,
        "profile_values_are_assumed_not_observed": True,
        "execution_cost_measurement_claim": False,
    }


def _liquidity_capacity(
    ideas: Sequence[_Idea], *, fractions: Sequence[Any], minimum: int
) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for raw_fraction in fractions:
        fraction = float(raw_fraction)
        if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
            raise ValueError("liquidity_fraction_out_of_bounds")
        scenarios.append(
            {
                "position_liquidity_fraction": fraction,
                "overall": _capacity_metrics(ideas, fraction, minimum=minimum),
                "routes": [
                    {
                        "route": route,
                        **_capacity_metrics(
                            [idea for idea in ideas if idea.route == route],
                            fraction,
                            minimum=minimum,
                        ),
                    }
                    for route in ROUTES
                ],
            }
        )
    return {
        "status": "available" if any(i.liquidity_usd is not None for i in ideas) else "unavailable",
        "capacity_basis": (
            "point_in_time_trailing_daily_quote_volume_usd_times_assumed_fraction"
        ),
        "capacity_is_not_executable_size": True,
        "scenarios": scenarios,
        "unit": "usd_notional",
    }


def _capacity_metrics(
    ideas: Sequence[_Idea], fraction: float, *, minimum: int
) -> dict[str, Any]:
    values = [idea.liquidity_usd * fraction for idea in ideas if idea.liquidity_usd is not None]
    status = _sample_status(len(values), minimum)
    return {
        "episode_count": len(ideas),
        "sample_size": len(values),
        "missing_liquidity_count": len(ideas) - len(values),
        "sample_status": status,
        "evidence_status": _evidence_status(status),
        "mean_capacity_usd": _mean(values),
        "median_capacity_usd": _median(values),
        "minimum_capacity_usd": min(values) if values else None,
        "maximum_capacity_usd": max(values) if values else None,
        "unit": "usd_notional",
    }


def _simultaneous_cap_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    limits: Sequence[Any],
    minimum: int,
) -> dict[str, Any]:
    scenarios = []
    for raw_limit in limits:
        limit = int(raw_limit)
        if limit <= 0:
            raise ValueError("maximum_simultaneous_ideas_not_positive")
        selected = _simultaneous_selection(ideas, limit=limit, holding_days=3)
        scenarios.append(
            _cap_scenario(
                ideas,
                selected,
                outcomes,
                name="maximum_simultaneous_ideas",
                limit=limit,
                minimum=minimum,
            )
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "holding_assumption_days": 3,
        "release_rule": "position_released_at_observed_at_plus_3d",
        "selection_uses_outcomes": False,
        "scenarios": scenarios,
    }


def _daily_cap_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    limits: Sequence[Any],
    minimum: int,
) -> dict[str, Any]:
    scenarios = []
    for raw_limit in limits:
        limit = int(raw_limit)
        if limit <= 0:
            raise ValueError("maximum_daily_ideas_not_positive")
        selected = _daily_selection(ideas, limit=limit)
        scenarios.append(
            _cap_scenario(
                ideas,
                selected,
                outcomes,
                name="maximum_daily_ideas",
                limit=limit,
                minimum=minimum,
            )
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "day_basis": "observed_at_calendar_day_utc",
        "selection_uses_outcomes": False,
        "scenarios": scenarios,
    }


def _cap_scenario(
    supplied: Sequence[_Idea],
    selected: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    name: str,
    limit: int,
    minimum: int,
) -> dict[str, Any]:
    identifiers = [idea.episode_id for idea in selected]
    return {
        name: limit,
        "eligible_count": len(supplied),
        "selected_count": len(selected),
        "excluded_by_cap_count": len(supplied) - len(selected),
        "selected_episode_ids": identifiers[:_MAX_SELECTION_IDS],
        "selected_episode_ids_truncated": len(identifiers) > _MAX_SELECTION_IDS,
        "selected_episode_id_digest": _digest(identifiers),
        "selection_order": "observed_at_then_point_in_time_identity_digest",
        "selection_uses_outcomes": False,
        "outcomes_joined_after_selection": True,
        "metrics": _return_metrics(
            selected, outcomes, horizon_days=3, minimum=minimum
        ),
    }


def _simultaneous_selection(
    ideas: Sequence[_Idea], *, limit: int, holding_days: int
) -> list[_Idea]:
    selected: list[_Idea] = []
    active_until: list[datetime] = []
    for idea in sorted(ideas, key=_idea_order):
        active_until = [due for due in active_until if due > idea.observed_at]
        if len(active_until) >= limit:
            continue
        selected.append(idea)
        active_until.append(idea.observed_at + timedelta(days=holding_days))
        active_until.sort()
    return selected


def _daily_selection(ideas: Sequence[_Idea], *, limit: int) -> list[_Idea]:
    grouped: dict[str, list[_Idea]] = defaultdict(list)
    for idea in ideas:
        grouped[idea.observed_at.date().isoformat()].append(idea)
    selected: list[_Idea] = []
    for day in sorted(grouped):
        selected.extend(sorted(grouped[day], key=_idea_order)[:limit])
    return sorted(selected, key=_idea_order)


def _fixed_stop_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    stops: Sequence[Any],
    minimum: int,
) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for raw_stop in stops:
        stop = float(raw_stop)
        if not math.isfinite(stop) or not 0.0 < stop < 1.0:
            raise ValueError("stop_loss_fraction_out_of_bounds")
        overall = _return_metrics(
            ideas,
            outcomes,
            horizon_days=3,
            stop_loss_fraction=stop,
            minimum=minimum,
        )
        scenarios.append(
            {
                "stop_loss_fraction": stop,
                "overall": overall,
                "routes": [
                    {
                        "route": route,
                        "metrics": _return_metrics(
                            [idea for idea in ideas if idea.route == route],
                            outcomes,
                            horizon_days=3,
                            stop_loss_fraction=stop,
                            minimum=minimum,
                        ),
                    }
                    for route in ROUTES
                ],
            }
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "scenarios": scenarios,
        "assumptions": {
            "path_resolution": "daily_high_low_only",
            "trigger_rule": "3d_direction_adjusted_mae_lte_negative_stop",
            "fill_rule": "assumed_exact_stop_threshold",
            "gap_through_stop": "not_observable_and_assumed_absent",
            "intraday_high_low_order": "unavailable",
            "same_bar_stop_and_recovery_order": "unavailable",
            "execution_backtest_claim": False,
        },
    }


def _trailing_stop_unavailable(
    stops: Sequence[Any], *, path_status: str
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": "intraday_high_low_order_absent",
        "intraday_path_order_status": path_status,
        "scenarios": [
            {
                "trailing_stop_fraction": float(value),
                "status": "unavailable",
                "sample_size": 0,
                "metrics": None,
                "reason": "daily_bars_cannot_order_favorable_and_adverse_extremes",
            }
            for value in stops
        ],
        "fabricated_path_order": False,
        "execution_backtest_claim": False,
    }


def _holding_time_sensitivity(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    minimum: int,
) -> dict[str, Any]:
    scenarios = []
    for days in HORIZON_DAYS:
        scenarios.append(
            {
                "maximum_holding_days": days,
                "exit_basis": f"{days}d_close",
                "overall": _return_metrics(
                    ideas, outcomes, horizon_days=days, minimum=minimum
                ),
                "routes": [
                    {
                        "route": route,
                        "metrics": _return_metrics(
                            [idea for idea in ideas if idea.route == route],
                            outcomes,
                            horizon_days=days,
                            minimum=minimum,
                        ),
                    }
                    for route in ROUTES
                ],
            }
        )
    return {
        "status": "available" if ideas else "unavailable_no_sample",
        "horizon_order_days": list(HORIZON_DAYS),
        "scenarios": scenarios,
        "selection_uses_outcomes": False,
    }


def _return_metrics(
    ideas: Sequence[_Idea],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    horizon_days: int,
    minimum: int,
    review_delay_days: int = 0,
    cost_fraction: float = 0.0,
    stop_loss_fraction: float | None = None,
) -> dict[str, Any]:
    values: list[float] = []
    reasons: Counter[str] = Counter()
    stopped = 0
    matured = 0
    pending = 0
    for idea in ideas:
        outcome = outcomes.get(idea.episode_id)
        if outcome is None:
            reasons["outcome_missing"] += 1
            continue
        value, reason, maturity = _scenario_return(
            idea,
            outcome,
            horizon_days=horizon_days,
            review_delay_days=review_delay_days,
        )
        if maturity == "matured":
            matured += 1
        elif maturity == "pending":
            pending += 1
        if value is None:
            reasons[reason or "return_unavailable"] += 1
            continue
        if stop_loss_fraction is not None:
            mae, mae_reason = _mae(outcome, horizon_days=horizon_days)
            if mae is None:
                reasons[mae_reason or "mae_unavailable"] += 1
                continue
            if mae <= -stop_loss_fraction:
                value = -stop_loss_fraction
                stopped += 1
        values.append(value - cost_fraction)
    status = _sample_status(len(values), minimum)
    return {
        "selection_count": len(ideas),
        "matured_outcome_count": matured,
        "pending_outcome_count": pending,
        "sample_size": len(values),
        "missing_or_unusable_count": len(ideas) - len(values),
        "unavailable_reason_counts": dict(sorted(reasons.items())),
        "sample_status": status,
        "evidence_status": _evidence_status(status),
        "mean_direction_adjusted_return_fraction": _mean(values),
        "median_direction_adjusted_return_fraction": _median(values),
        "hit_rate": (
            sum(value > 0.0 for value in values) / len(values)
            if values
            else None
        ),
        "worst_direction_adjusted_return_fraction": min(values) if values else None,
        "best_direction_adjusted_return_fraction": max(values) if values else None,
        "assumed_round_trip_cost_fraction": cost_fraction,
        "fixed_stop_loss_fraction": stop_loss_fraction,
        "assumed_stop_trigger_count": stopped,
        "return_unit": "fraction",
        "selection_uses_outcomes": False,
        "outcomes_joined_after_selection": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _scenario_return(
    idea: _Idea,
    outcome: Mapping[str, Any],
    *,
    horizon_days: int,
    review_delay_days: int,
) -> tuple[float | None, str | None, str]:
    target = _horizon(outcome, horizon_days)
    if target is None:
        return None, f"{horizon_days}d_horizon_missing", "missing_data"
    maturity = str(target.get("maturity_status") or "missing_data")
    if maturity != "matured":
        return None, f"{horizon_days}d_horizon_{maturity}", maturity
    if str(target.get("return_unit") or "") != "fraction":
        return None, "return_unit_not_fraction", maturity
    if review_delay_days == 0:
        value = _finite(target.get("direction_adjusted_return_fraction"))
        return (
            (value, None, maturity)
            if value is not None
            else (None, "direction_adjusted_return_unavailable", maturity)
        )
    if review_delay_days != 1 or horizon_days != 3:
        return None, "unsupported_review_delay", maturity
    entry = _horizon(outcome, 1)
    if entry is None or str(entry.get("maturity_status") or "") != "matured":
        return None, "1d_delayed_entry_unavailable", maturity
    if str(entry.get("return_unit") or "") != "fraction":
        return None, "return_unit_not_fraction", maturity
    raw_entry = _finite(entry.get("raw_return_fraction"))
    raw_exit = _finite(target.get("raw_return_fraction"))
    if raw_entry is None or raw_exit is None or idea.direction_sign is None:
        return None, "delayed_return_inputs_unavailable", maturity
    if 1.0 + raw_entry <= 0.0:
        return None, "delayed_entry_price_nonpositive", maturity
    return idea.direction_sign * ((1.0 + raw_exit) / (1.0 + raw_entry) - 1.0), None, maturity


def _mae(
    outcome: Mapping[str, Any], *, horizon_days: int
) -> tuple[float | None, str | None]:
    horizon = _horizon(outcome, horizon_days)
    if horizon is None:
        return None, f"{horizon_days}d_horizon_missing"
    if str(horizon.get("return_unit") or "") != "fraction":
        return None, "mae_return_unit_not_fraction"
    value = _finite(horizon.get("max_adverse_excursion_fraction"))
    if value is None:
        return None, "mae_unavailable"
    if value > 0.0:
        return None, "mae_sign_invalid_expected_nonpositive"
    return value, None


def _horizon(outcome: Mapping[str, Any], days: int) -> Mapping[str, Any] | None:
    horizons = outcome.get("horizons")
    if not isinstance(horizons, Mapping):
        return None
    value = horizons.get(f"{days}d")
    return value if isinstance(value, Mapping) else None


def _closed_projection(raw: Mapping[str, Any]) -> dict[str, Any]:
    projection = raw.get("decision_projection")
    value = dict(projection) if isinstance(projection, Mapping) else {}
    value.update({str(key): item for key, item in raw.items()})
    return value


def _liquidity_usd(row: Mapping[str, Any]) -> float | None:
    for key in (
        "trailing_quote_volume_usd",
        "trailing_30d_mean_quote_volume_usd",
        "trailing_mean_quote_volume_usd",
        "liquidity_usd",
    ):
        value = _finite(row.get(key))
        if value is not None and value >= 0.0:
            return value
    return None


def _idea_order(idea: _Idea) -> tuple[str, str, str]:
    identity = {
        "episode_id": idea.episode_id,
        "route": idea.route,
        "directional_bias": idea.row.get("directional_bias"),
        "canonical_asset_id": idea.row.get("canonical_asset_id"),
        "observed_at": idea.observed_at.isoformat(),
    }
    return idea.observed_at.isoformat(), _digest(identity), idea.episode_id


def _sample_status(sample_size: int, minimum: int) -> str:
    if sample_size == 0:
        return "no_sample"
    if sample_size < minimum:
        return "insufficient_sample"
    return "descriptive_sample"


def _evidence_status(sample_status: str) -> str:
    return {
        "no_sample": "no_evidence",
        "insufficient_sample": "insufficient_evidence",
        "descriptive_sample": "descriptive_only",
    }[sample_status]


def _positive_mean(metrics: Mapping[str, Any]) -> bool | None:
    value = _finite(metrics.get("mean_direction_adjusted_return_fraction"))
    return value > 0.0 if value is not None else None


def _break_even_bps(metrics: Mapping[str, Any]) -> float | None:
    value = _finite(metrics.get("mean_direction_adjusted_return_fraction"))
    return max(0.0, value * 10_000.0) if value is not None else None


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    selected = float(value)
    return selected if math.isfinite(selected) else None


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "HORIZON_DAYS",
    "METHOD",
    "ROUTES",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_empirical_survivability",
]
