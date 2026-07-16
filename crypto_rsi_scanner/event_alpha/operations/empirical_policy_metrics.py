"""Deterministic metrics for empirical shadow-policy simulations.

The public lifecycle and sealing contract remains in ``empirical_policy_lab``.
This module contains only the pure, per-scenario evaluation and aggregation
work so architecture limits cannot obscure that lifecycle.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any, Iterable, Mapping


_VISIBLE_ROUTES = {
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
}


def simulate_scenario(
    rows: list[Mapping[str, Any]],
    outcome_index: Mapping[str, Mapping[str, Any]],
    scenario: Mapping[str, Any],
    protocol: Mapping[str, Any],
    *,
    selected_observation_days: set[str] | None = None,
    observed_day_denominator_basis: str = (
        "fallback_episode_active_utc_days_only"
    ),
) -> dict[str, Any]:
    """Evaluate and summarize one frozen scenario without side effects."""

    # Imported only after empirical_policy_lab has initialized.  The lab owns
    # the canonical projection/outcome primitives; keeping them there avoids a
    # second implementation while this module owns only metric aggregation.
    from . import empirical_policy_lab as primitives

    changes = dict(scenario.get("changes") or {})
    evaluated = _evaluate_rows(
        rows,
        outcome_index,
        changes=changes,
        protocol=protocol,
        primitives=primitives,
    )
    cooldown = int(changes.get("family_cooldown_hours") or 0)
    if cooldown:
        primitives._apply_family_cooldown(evaluated, cooldown)
    return _scenario_summary(
        rows,
        evaluated,
        name=str(scenario["name"]),
        changes=changes,
        protocol=protocol,
        selected_observation_days=selected_observation_days,
        observed_day_denominator_basis=observed_day_denominator_basis,
        primitives=primitives,
    )


def _evaluate_rows(
    rows: list[Mapping[str, Any]],
    outcome_index: Mapping[str, Mapping[str, Any]],
    *,
    changes: Mapping[str, Any],
    protocol: Mapping[str, Any],
    primitives: Any,
) -> list[dict[str, Any]]:
    urgent_routes = frozenset(
        str(value) for value in protocol["operator_burden"]["urgent_routes"]
    )
    evaluated: list[dict[str, Any]] = []
    for idea in rows:
        original = primitives.decision_model_values(idea)
        if not original:
            raise ValueError("shadow-policy idea missing canonical projection")
        projection = primitives._scenario_projection(idea, original, changes)
        route = str(projection.get("radar_route") or "diagnostic")
        primary_return = primitives._directional_return(idea, outcome_index)
        expiry = primitives._scenario_expiry_values(
            idea,
            original,
            projection,
            cap_requested="maximum_expiry_hours" in changes,
        )
        policy_return, return_basis = primitives._scenario_directional_return(
            idea,
            outcome_index,
            primary_return=primary_return,
            shadow_expires_at=expiry["shadow_expires_at"],
            expiry_policy_changed=expiry["expiry_policy_changed"],
        )
        evaluated.append(
            {
                "candidate_id": str(idea.get("candidate_id") or ""),
                "episode_id": str(
                    idea.get("episode_id") or idea.get("candidate_id") or ""
                ),
                "family_id": str(
                    idea.get("candidate_family_id")
                    or idea.get("canonical_asset_id")
                    or ""
                ),
                "observed_at": str(idea.get("observed_at") or ""),
                "market_regime": str(
                    idea.get("market_regime") or "unknown"
                ),
                "route": route,
                "original_route": str(
                    original.get("radar_route") or "diagnostic"
                ),
                "visible": route in _VISIBLE_ROUTES,
                "urgent": route in urgent_routes,
                "return_fraction": policy_return,
                "primary_return_fraction": primary_return,
                "return_basis": return_basis,
                **expiry,
            }
        )
    return evaluated


def _scenario_summary(
    rows: list[Mapping[str, Any]],
    evaluated: list[dict[str, Any]],
    *,
    name: str,
    changes: Mapping[str, Any],
    protocol: Mapping[str, Any],
    selected_observation_days: set[str] | None,
    observed_day_denominator_basis: str,
    primitives: Any,
) -> dict[str, Any]:
    visible = [
        row
        for row in evaluated
        if row["visible"] and not row.get("cooldown_suppressed")
    ]
    matured = [
        row for row in visible if row["return_fraction"] is not None
    ]
    returns = [float(row["return_fraction"]) for row in matured]
    visible_days = {str(row["observed_at"])[:10] for row in visible}
    idea_active_days = {
        str(row["observed_at"])[:10] for row in evaluated
    }
    observed_days = (
        set(selected_observation_days)
        if selected_observation_days is not None
        else set(idea_active_days)
    )
    if not idea_active_days <= observed_days:
        raise ValueError("idea_active_day_outside_selected_observation_days")
    route_change_count = sum(
        row["route"] != row["original_route"] for row in evaluated
    )
    cooldown_suppressed_count = sum(
        bool(row.get("cooldown_suppressed")) for row in evaluated
    )
    expiry_capped_count = sum(
        bool(row.get("expiry_policy_changed")) for row in evaluated
    )
    lifetimes = _lifetime_metrics(visible, primitives)
    return {
        "scenario": name,
        "changes": dict(changes),
        "episode_count": len(rows),
        "candidate_volume": len(rows),
        "visible_episode_count": len(visible),
        "matured_visible_episode_count": len(matured),
        "route_change_count": route_change_count,
        "cooldown_suppressed_count": cooldown_suppressed_count,
        "expiry_capped_count": expiry_capped_count,
        "material_policy_change_count": (
            route_change_count
            + cooldown_suppressed_count
            + expiry_capped_count
        ),
        **lifetimes,
        "return_basis_counts": dict(
            sorted(
                Counter(
                    str(row["return_basis"]) for row in evaluated
                ).items()
            )
        ),
        "urgent_item_count": sum(row["urgent"] for row in visible),
        "active_day_count": len(visible_days),
        "visible_idea_active_day_count": len(visible_days),
        "idea_active_day_count": len(idea_active_days),
        "observed_day_count": len(observed_days),
        "zero_idea_observed_day_count": max(
            0, len(observed_days) - len(idea_active_days)
        ),
        "observed_day_denominator_basis": observed_day_denominator_basis,
        "selected_observation_days_sha256": primitives._days_digest(
            observed_days
        ),
        **_rate_metrics(
            evaluated,
            visible,
            visible_days=visible_days,
            idea_active_days=idea_active_days,
            observed_days=observed_days,
        ),
        "mean_directional_return_fraction": (
            primitives._rounded(mean(returns)) if returns else None
        ),
        "median_directional_return_fraction": (
            primitives._rounded(median(returns)) if returns else None
        ),
        "hit_rate": (
            primitives._rounded(
                sum(value > 0 for value in returns) / len(returns)
            )
            if returns
            else None
        ),
        "quick_failure_rate": (
            primitives._rounded(
                sum(value <= -0.05 for value in returns) / len(returns)
            )
            if returns
            else None
        ),
        "route_counts": dict(
            sorted(Counter(row["route"] for row in evaluated).items())
        ),
        "visible_route_counts": dict(
            sorted(Counter(row["route"] for row in visible).items())
        ),
        "route_change_matrix": _route_change_matrix(evaluated),
        "operator_burden": _policy_operator_burden(
            evaluated,
            visible,
            observed_days=observed_days,
            idea_active_days=idea_active_days,
            observed_day_denominator_basis=observed_day_denominator_basis,
            primitives=primitives,
        ),
        "false_positive_summary": _policy_false_positive_summary(
            matured, primitives
        ),
        "missed_opportunity_proxy": _policy_missed_proxy(
            evaluated, primitives
        ),
        "regime_stability": _policy_regime_stability(
            matured, protocol, primitives
        ),
        "assumed_cost_sensitivity": _policy_cost_sensitivity(
            returns, protocol, primitives
        ),
        "evidence_strength": primitives._evidence_strength(
            len(matured), protocol
        ),
        "outcome_basis": (
            "episode_representative_directional_primary_horizon"
        ),
        "historical_spread_basis": "unavailable",
        "costs_observed": False,
        "research_only": True,
        "auto_apply": False,
    }


def _rate_metrics(
    evaluated: list[Mapping[str, Any]],
    visible: list[Mapping[str, Any]],
    *,
    visible_days: set[str],
    idea_active_days: set[str],
    observed_days: set[str],
) -> dict[str, float]:
    return {
        "ideas_per_active_day": (
            round(len(visible) / len(visible_days), 6)
            if visible_days
            else 0.0
        ),
        "ideas_per_observed_day": (
            round(len(visible) / len(observed_days), 6)
            if observed_days
            else 0.0
        ),
        "candidate_ideas_per_observed_day": (
            round(len(evaluated) / len(observed_days), 6)
            if observed_days
            else 0.0
        ),
        "visible_ideas_per_idea_active_day": (
            round(len(visible) / len(idea_active_days), 6)
            if idea_active_days
            else 0.0
        ),
    }


def _lifetime_metrics(
    visible: list[Mapping[str, Any]], primitives: Any
) -> dict[str, Any]:
    visible_lifetimes = [
        float(row["shadow_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("shadow_operator_lifetime_hours")
        )
        is not None
    ]
    original_visible_lifetimes = [
        float(row["original_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("original_operator_lifetime_hours")
        )
        is not None
    ]
    paired_lifetime_reductions = [
        float(row["original_operator_lifetime_hours"])
        - float(row["shadow_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("original_operator_lifetime_hours")
        )
        is not None
        and primitives._finite(
            row.get("shadow_operator_lifetime_hours")
        )
        is not None
    ]
    return {
        "visible_operator_lifetime_hours": primitives._rounded(
            sum(visible_lifetimes)
        ),
        "original_visible_operator_lifetime_hours": primitives._rounded(
            sum(original_visible_lifetimes)
        ),
        "visible_operator_lifetime_reduction_hours": primitives._rounded(
            sum(paired_lifetime_reductions)
        ),
        "mean_visible_operator_lifetime_hours": (
            primitives._rounded(mean(visible_lifetimes))
            if visible_lifetimes
            else None
        ),
        "operator_lifetime_evaluable_episode_count": len(
            visible_lifetimes
        ),
    }


def _route_change_matrix(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    counts = Counter(
        (str(row["original_route"]), str(row["route"]))
        for row in rows
        if row["original_route"] != row["route"]
    )
    return [
        {"from_route": source, "to_route": target, "count": count}
        for (source, target), count in sorted(counts.items())
    ]


def _policy_operator_burden(
    rows: list[Mapping[str, Any]],
    visible: list[Mapping[str, Any]],
    *,
    observed_days: set[str],
    idea_active_days: set[str],
    observed_day_denominator_basis: str,
    primitives: Any,
) -> dict[str, Any]:
    visible_by_day: dict[str, int] = defaultdict(int)
    urgent_by_day: dict[str, int] = defaultdict(int)
    family_counts: Counter[str] = Counter()
    for row in visible:
        day = str(row["observed_at"])[:10]
        visible_by_day[day] += 1
        urgent_by_day[day] += int(row["urgent"])
        family_counts[str(row["family_id"])] += 1
    lifetimes = _burden_lifetime_values(visible, primitives)
    days = max(1, len(observed_days))
    return {
        "counting_unit": "episode_representative",
        "observed_day_count": len(observed_days),
        "selected_observation_day_count": len(observed_days),
        "idea_active_day_count": len(idea_active_days),
        "active_day_count": len(visible_by_day),
        "visible_idea_active_day_count": len(visible_by_day),
        "zero_idea_observed_day_count": max(
            0, len(observed_days) - len(idea_active_days)
        ),
        "observed_day_denominator_basis": observed_day_denominator_basis,
        "selected_observation_days_sha256": primitives._days_digest(
            observed_days
        ),
        "visible_episode_count": len(visible),
        "urgent_item_count": sum(urgent_by_day.values()),
        "candidate_ideas_per_observed_day": primitives._rounded(
            len(rows) / days
        ),
        "ideas_per_observed_day": primitives._rounded(
            len(visible) / days
        ),
        "ideas_per_active_day": (
            primitives._rounded(len(visible) / len(visible_by_day))
            if visible_by_day
            else 0.0
        ),
        "urgent_items_per_observed_day": primitives._rounded(
            sum(urgent_by_day.values()) / days
        ),
        "maximum_ideas_on_one_day": max(
            visible_by_day.values(), default=0
        ),
        "maximum_urgent_items_on_one_day": max(
            urgent_by_day.values(), default=0
        ),
        "visible_family_count": len(family_counts),
        "repeated_family_item_count": sum(
            max(0, count - 1) for count in family_counts.values()
        ),
        "cooldown_suppressed_count": sum(
            bool(row.get("cooldown_suppressed")) for row in rows
        ),
        "expiry_capped_count": sum(
            bool(row.get("expiry_policy_changed")) for row in rows
        ),
        "visible_operator_lifetime_hours": primitives._rounded(
            sum(lifetimes["shadow"])
        ),
        "original_visible_operator_lifetime_hours": primitives._rounded(
            sum(lifetimes["original"])
        ),
        "visible_operator_lifetime_reduction_hours": primitives._rounded(
            sum(lifetimes["reductions"])
        ),
        "mean_visible_operator_lifetime_hours": (
            primitives._rounded(mean(lifetimes["shadow"]))
            if lifetimes["shadow"]
            else None
        ),
        "operator_lifetime_evaluable_episode_count": len(
            lifetimes["shadow"]
        ),
        "operator_lifetime_basis": (
            "canonical_or_shadow_expires_at_minus_observed_at"
        ),
        "selection_uses_outcomes": False,
        "research_only": True,
    }


def _burden_lifetime_values(
    visible: list[Mapping[str, Any]], primitives: Any
) -> dict[str, list[float]]:
    shadow = [
        float(row["shadow_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("shadow_operator_lifetime_hours")
        )
        is not None
    ]
    original = [
        float(row["original_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("original_operator_lifetime_hours")
        )
        is not None
    ]
    reductions = [
        float(row["original_operator_lifetime_hours"])
        - float(row["shadow_operator_lifetime_hours"])
        for row in visible
        if primitives._finite(
            row.get("original_operator_lifetime_hours")
        )
        is not None
        and primitives._finite(
            row.get("shadow_operator_lifetime_hours")
        )
        is not None
    ]
    return {"shadow": shadow, "original": original, "reductions": reductions}


def _policy_false_positive_summary(
    matured: list[Mapping[str, Any]], primitives: Any
) -> dict[str, Any]:
    failures = sum(
        float(row["return_fraction"]) <= -0.05 for row in matured
    )
    return {
        "quick_failure_definition_fraction": -0.05,
        "matured_visible_episode_count": len(matured),
        "quick_failure_count": failures,
        "quick_failure_rate": (
            primitives._rounded(failures / len(matured))
            if matured
            else None
        ),
        "outcome_basis_counts": dict(
            sorted(
                Counter(
                    str(row["return_basis"]) for row in matured
                ).items()
            )
        ),
        "status": "available" if matured else "insufficient_sample",
        "research_only": True,
    }


def _policy_missed_proxy(
    rows: list[Mapping[str, Any]], primitives: Any
) -> dict[str, Any]:
    route_hidden = [
        row
        for row in rows
        if (not row["visible"] or row.get("cooldown_suppressed"))
        and row["return_fraction"] is not None
    ]
    expiry_hidden = [
        row
        for row in rows
        if row.get("expiry_policy_changed")
        and primitives._finite(row.get("return_fraction")) is not None
        and float(row["return_fraction"]) <= 0
        and primitives._finite(row.get("primary_return_fraction"))
        is not None
        and float(row["primary_return_fraction"]) > 0
    ]
    hidden_by_id = {
        str(row["candidate_id"]): row
        for row in (*route_hidden, *expiry_hidden)
    }
    positive = sum(
        (
            float(row["primary_return_fraction"]) > 0
            if row.get("expiry_policy_changed")
            else float(row["return_fraction"]) > 0
        )
        for row in hidden_by_id.values()
    )
    return {
        "definition": (
            "generated_episode_hidden_by_shadow_policy_or_expired_before_"
            "positive_primary_directional_resolution"
        ),
        "systematic_missed_move_evaluator_claim": False,
        "hidden_matured_episode_count": len(hidden_by_id),
        "hidden_positive_episode_count": positive,
        "route_or_cooldown_hidden_matured_episode_count": len(route_hidden),
        "expired_before_positive_primary_resolution_count": len(expiry_hidden),
        "selection_uses_outcomes": False,
        "outcomes_joined_after_policy_selection": True,
        "research_only": True,
    }


def _policy_regime_stability(
    matured: list[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    primitives: Any,
) -> dict[str, Any]:
    closed = (
        "bull",
        "bear",
        "chop",
        "high_volatility",
        "low_volatility",
        "risk_on",
        "risk_off",
        "unknown",
    )
    groups: dict[str, list[float]] = defaultdict(list)
    for row in matured:
        regime = str(
            row.get("market_regime") or "unknown"
        ).strip().casefold()
        groups[regime if regime in closed else "unknown"].append(
            float(row["return_fraction"])
        )
    cohorts = []
    for regime in closed:
        values = groups.get(regime, [])
        cohorts.append(
            {
                "regime": regime,
                "sample_size": len(values),
                "evidence_strength": primitives._evidence_strength(
                    len(values), protocol
                ),
                "mean_directional_return_fraction": (
                    primitives._rounded(mean(values)) if values else None
                ),
                "hit_rate": (
                    primitives._rounded(
                        sum(value > 0 for value in values) / len(values)
                    )
                    if values
                    else None
                ),
                "status": "available" if values else "no_sample",
            }
        )
    directional = [
        row
        for row in cohorts
        if row["evidence_strength"] == "policy_candidate_sample"
    ]
    return {
        "cohorts": cohorts,
        "comparable_regime_count": len(directional),
        "status": "exploratory" if len(directional) >= 2 else "not_evaluable",
        "multiple_comparison_warning": protocol["statistics"][
            "multiple_comparison_policy"
        ],
        "research_only": True,
    }


def _policy_cost_sensitivity(
    returns: list[float],
    protocol: Mapping[str, Any],
    primitives: Any,
) -> dict[str, Any]:
    rows = []
    for bps in protocol["cost_scenarios"]["round_trip_cost_bps"]:
        net = [value - float(bps) / 10_000.0 for value in returns]
        rows.append(
            {
                "round_trip_cost_bps": int(bps),
                "sample_size": len(net),
                "mean_net_directional_return_fraction": (
                    primitives._rounded(mean(net)) if net else None
                ),
                "net_hit_rate": (
                    primitives._rounded(
                        sum(value > 0 for value in net) / len(net)
                    )
                    if net
                    else None
                ),
                "status": "available" if net else "insufficient_sample",
            }
        )
    gross_mean = mean(returns) if returns else None
    return {
        "cost_basis": "assumed_sensitivity_not_observed",
        "historical_spread_observed": False,
        "break_even_mean_round_trip_cost_bps": (
            max(0.0, gross_mean * 10_000.0)
            if gross_mean is not None
            else None
        ),
        "scenarios": rows,
        "research_only": True,
    }
