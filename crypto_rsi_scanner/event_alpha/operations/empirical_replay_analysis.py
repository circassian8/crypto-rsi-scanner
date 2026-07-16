"""Pure descriptive analysis over frozen Decision Radar replay episodes.

The module accepts already-materialized episode representatives and outcomes.
It performs no I/O and has no path to providers, authorization, notifications,
dashboard authority, production policy, or trading state.  All returns emitted
by this module are fractions; declared percent-point inputs are converted
explicitly before analysis.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from . import empirical_validation_protocol
from . import empirical_replay_dimensions
from . import empirical_operator_burden
from . import empirical_survivability
from .empirical_replay_statistics import _bootstrap_mean_ci, _mean, _robust_summary


SCHEMA_ID = "decision_radar.empirical_replay_analysis"
SCHEMA_VERSION = 1
METHOD = "frozen_episode_representative_descriptive_analysis"

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
PRIMARY_ORIGINS = empirical_replay_dimensions.CONTRIBUTING_ORIGINS
SCORE_FIELDS = (
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "chase_risk_score",
)
SCORE_EXPECTATIONS = {
    "actionability_score": "nondecreasing_outcome_quality",
    "evidence_confidence_score": "nondecreasing_outcome_quality",
    "risk_score": "nonincreasing_outcome_quality",
    "urgency_score": "nondecreasing_outcome_quality",
    "chase_risk_score": "nonincreasing_outcome_quality",
}
SCORE_BUCKETS = (
    ("0_19", 0.0, 20.0),
    ("20_39", 20.0, 40.0),
    ("40_59", 40.0, 60.0),
    ("60_79", 60.0, 80.0),
    ("80_100", 80.0, 100.000000001),
)
MARKET_CATALYST_CATEGORIES = (
    "market_led_unknown_catalyst",
    "market_led_later_catalyst_discovery",
    "catalyst_led_before_market_reaction",
    "catalyst_led_after_significant_reaction",
    "mixed_market_and_catalyst",
    "technical_plus_market",
    "derivatives_plus_market",
    "onchain_plus_market",
    "unclassified",
)
_DIRECTION_SIGN = {
    "long": 1.0,
    "fade_short_review": -1.0,
    "risk": -1.0,
}
_PERCENT_POINT_UNITS = {"percent_points", "percentage_points", "pct_points"}
_FRACTION_UNITS = {"fraction", "decimal_fraction", "fraction_by_protocol"}
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
class _EpisodeView:
    episode_id: str
    representative: Mapping[str, Any]
    outcome: Mapping[str, Any]


def build_empirical_replay_analysis(
    representatives: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]] = (),
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int | None = None,
    selected_observation_days: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build one deterministic, closed, descriptive replay analysis.

    ``partition`` identifies one frozen chronological partition.  Mixing rows
    that explicitly claim another partition is rejected.  ``evidence_mode`` is
    an honest caller-supplied label such as ``historical_replay``, ``fixture``,
    or ``live_no_send``; it does not change any computation.
    """

    protocol, evidence_mode, resamples, views = _analysis_context(
        representatives,
        outcomes,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
    )
    payload = _analysis_payload(
        views,
        protocol=protocol,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=resamples,
        selected_observation_days=selected_observation_days,
    )
    payload["analysis_digest"] = _digest(payload)
    return payload


def _analysis_context(
    representatives: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int | None,
) -> tuple[Mapping[str, Any], str, int, list[_EpisodeView]]:
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("frozen_protocol_invalid:" + ";".join(errors))
    if not isinstance(evidence_mode, str) or not evidence_mode.strip():
        raise ValueError("evidence_mode_required")
    selected_mode = evidence_mode.strip()
    allowed = {str(row["name"]) for row in protocol["partitions"]}
    fixture = partition == "fixture" and "fixture" in selected_mode.casefold()
    if partition not in allowed and not fixture:
        raise ValueError("partition_not_frozen_protocol_partition")
    resamples = _bootstrap_resamples(bootstrap_resamples, protocol)
    views = _episode_views(representatives, outcomes, partition=partition)
    return protocol, selected_mode, resamples, views


def _fixed_cohort_sections(
    views: Sequence[_EpisodeView],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    route_groups = _groups(views, lambda row: _text(row.representative.get("radar_route")))
    origin_groups = _groups(
        views,
        lambda row: _text(row.representative.get("primary_thesis_origin")),
    )
    market_catalyst_groups = _groups(
        views,
        lambda row: classify_market_catalyst_category(row.representative)["category"],
    )
    def rows(cohort_type: str, names: Sequence[str], groups: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            _cohort_row(
                cohort_type,
                name,
                groups.get(name, ()),
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for name in names
        ]
    return (
        rows("radar_route", ROUTES, route_groups),
        rows("primary_thesis_origin", PRIMARY_ORIGINS, origin_groups),
        rows(
            "market_catalyst_category",
            MARKET_CATALYST_CATEGORIES,
            market_catalyst_groups,
        ),
    )


def _analysis_payload(
    views: Sequence[_EpisodeView],
    *,
    protocol: Mapping[str, Any],
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
    selected_observation_days: Iterable[str] | None,
) -> dict[str, Any]:
    route_cohorts, origin_cohorts, market_catalyst_cohorts = (
        _fixed_cohort_sections(
            views,
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        )
    )
    false_late = [
        classify_false_positive_and_late(
            view.representative,
            view.outcome,
        )
        for view in views
    ]
    missed = [
        classify_missed_opportunity(view.representative, view.outcome)
        for view in views
        if view.representative.get("analysis_role") == "missed_candidate"
        or _operator_visible_state(view.representative) is False
    ]
    dimension_analysis = empirical_replay_dimensions.build_empirical_dimension_analysis(
        (
            {"episode_id": view.episode_id, "representative": view.representative, "outcome": view.outcome}
            for view in views
        ),
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
    )

    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "partition": partition,
        "evidence_mode": evidence_mode,
        "return_unit": "fraction",
        "bootstrap_unit": "episode",
        "bootstrap_resamples": bootstrap_resamples,
        "episode_count": len(views),
        "matured_episode_count": sum(_is_matured(view) for view in views),
        "directional_return_sample_size": len(_directional_returns(views)),
        "unclassified_route_count": sum(
            1 for view in views
            if _text(view.representative.get("radar_route")) not in ROUTES
        ),
        "unclassified_primary_origin_count": sum(
            1 for view in views
            if _text(view.representative.get("primary_thesis_origin"))
            not in PRIMARY_ORIGINS
        ),
        "invalid_declared_return_unit_count": sum(
            _has_invalid_declared_return_unit(view) for view in views
        ),
        "route_cohorts": route_cohorts,
        "primary_origin_cohorts": origin_cohorts,
        "score_monotonicity": [
            _score_monotonicity(
                views,
                score_field=field,
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for field in SCORE_FIELDS
        ],
        "market_regime_cohorts": _dynamic_cohorts(
            views,
            cohort_type="market_regime",
            getter=lambda row: _text(row.representative.get("market_regime")),
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "liquidity_tier_cohorts": _dynamic_cohorts(
            views,
            cohort_type="liquidity_tier",
            getter=lambda row: _text(row.representative.get("liquidity_tier")),
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "data_quality_cohorts": _dynamic_cohorts(
            views,
            cohort_type="data_quality_mode",
            getter=lambda row: _data_quality_mode(row, evidence_mode),
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "dimension_analysis": dimension_analysis,
        "market_catalyst_cohorts": market_catalyst_cohorts,
        "cost_sensitivity": _cost_sensitivity(
            views,
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
            cost_bps=protocol["cost_scenarios"]["round_trip_cost_bps"],
            assumed_label=protocol["cost_scenarios"]["unobserved_cost_label"],
        ),
        "operator_burden": operator_burden(
            (view.representative for view in views),
            partition=partition,
            evidence_mode=evidence_mode,
            selected_observation_days=selected_observation_days,
        ),
        "survivability": empirical_survivability.build_empirical_survivability(
            (view.representative for view in views),
            (view.outcome for view in views),
            partition=partition,
            evidence_mode=evidence_mode,
        ),
        "missed_opportunity_classifications": missed,
        "false_positive_and_late_classifications": false_late,
        "multiple_comparison_warning": protocol["statistics"][
            "multiple_comparison_policy"
        ],
        "causal_claim": False,
        "production_policy_claim": False,
        "policy_eligible": False,
        "recommendation": None,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    return payload


def build_empirical_replay_analysis_from_episodes(
    episodes: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int | None = None,
    selected_observation_days: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Adapt the replay outcome producer's bound episode dictionaries.

    The adapter copies the frozen first representative and its corresponding
    ``representative_outcome`` under the parent episode identity.  Positional
    outcome joins are never used.
    """

    if isinstance(episodes, Mapping):
        raw_episodes = episodes.get("episodes")
        if not isinstance(raw_episodes, list):
            raise ValueError("episode_collection_required")
    else:
        raw_episodes = list(episodes)
    representatives: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for raw in raw_episodes:
        if not isinstance(raw, Mapping):
            raise ValueError("episode_row_not_mapping")
        episode_id = _required_episode_id(raw)
        raw_representative = raw.get("representative")
        raw_outcome = raw.get("representative_outcome")
        if not isinstance(raw_representative, Mapping):
            raise ValueError("episode_representative_required")
        if not isinstance(raw_outcome, Mapping):
            raise ValueError("episode_representative_outcome_required")
        representative = dict(raw_representative)
        representative.update({
            "episode_id": episode_id,
            "partition": partition,
            "episode_member_count": raw.get("member_count"),
            "dependent_repeat_count": raw.get("dependent_repeat_count"),
        })
        for target, source in (
            ("anomaly_family", "anomaly_family"),
            ("observed_at", "episode_start_at"),
            ("canonical_asset_id", "canonical_asset_id"),
            ("directional_bias", "directional_bias"),
        ):
            if representative.get(target) in (None, "") and raw.get(source) not in (
                None,
                "",
            ):
                representative[target] = raw[source]
        outcome = dict(raw_outcome)
        outcome["episode_id"] = episode_id
        outcome["partition"] = partition
        representatives.append(representative)
        outcomes.append(outcome)
    return build_empirical_replay_analysis(
        representatives,
        outcomes,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
        selected_observation_days=selected_observation_days,
    )


def classify_market_catalyst_category(
    representative: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify only from explicit origins and supplied point-in-time timing."""

    representative = _flatten_representative(representative)
    explicit = _text(representative.get("market_catalyst_category"))
    if explicit in MARKET_CATALYST_CATEGORIES and explicit != "unclassified":
        return _market_catalyst_result(explicit, "explicit_point_in_time_category")

    primary = _text(representative.get("primary_thesis_origin"))
    origins = _origin_set(representative)
    if "market_led" in origins and "catalyst_led" in origins:
        return _market_catalyst_result(
            "mixed_market_and_catalyst",
            "exact_contributing_origins",
        )
    for origin, category in (
        ("technical_led", "technical_plus_market"),
        ("derivatives_led", "derivatives_plus_market"),
        ("onchain_led", "onchain_plus_market"),
    ):
        if "market_led" in origins and origin in origins:
            return _market_catalyst_result(category, "exact_contributing_origins")

    timing = _text(
        representative.get("catalyst_attribution_timing")
        or representative.get("catalyst_timing_vs_market_reaction")
    )
    if primary == "market_led":
        if timing in {
            "later_discovery",
            "discovered_after_observation",
            "after_observation",
        } or representative.get("catalyst_discovered_after_observation") is True:
            return _market_catalyst_result(
                "market_led_later_catalyst_discovery",
                "supplied_catalyst_timing",
            )
        status_at_observation = _text(
            representative.get("catalyst_status_at_observation")
            or representative.get("catalyst_status")
        )
        if (
            status_at_observation == "unknown"
            or representative.get("catalyst_known_at_observation") is False
        ):
            return _market_catalyst_result(
                "market_led_unknown_catalyst",
                "canonical_projection_at_observation",
            )
    if primary == "catalyst_led":
        if timing in {"before_market_reaction", "antecedent_to_market_reaction"}:
            return _market_catalyst_result(
                "catalyst_led_before_market_reaction",
                "supplied_catalyst_timing",
            )
        if timing in {
            "after_significant_reaction",
            "after_significant_market_reaction",
            "after_market_reaction",
        }:
            return _market_catalyst_result(
                "catalyst_led_after_significant_reaction",
                "supplied_catalyst_timing",
            )
        exact = _exact_timestamp_order(representative)
        if exact is not None:
            return _market_catalyst_result(
                (
                    "catalyst_led_before_market_reaction"
                    if exact <= 0
                    else "catalyst_led_after_significant_reaction"
                ),
                "supplied_exact_timestamps",
            )
    return _market_catalyst_result("unclassified", "exact_timing_unavailable")


def classify_missed_opportunity(
    representative: Mapping[str, Any],
    outcome: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen endpoint, tradability, and maturity missed-move rule."""

    protocol = empirical_validation_protocol.protocol_values()
    rule = protocol["missed_opportunity_rule"]
    view = _ad_hoc_view(representative, outcome)
    representative = view.representative
    raw_return = _primary_return(view)
    bias = _text(representative.get("directional_bias"))
    volume = _number(
        representative.get("trailing_quote_volume_usd")
        if representative.get("trailing_quote_volume_usd") is not None
        else representative.get("liquidity_usd")
    )
    membership = (
        representative.get("point_in_time_membership") is True
        or representative.get("point_in_time_universe_member") is True
        or representative.get("in_universe") is True
    )
    warm = (
        representative.get("baseline_warm") is True
        or _text(representative.get("baseline_status")) in {"warm", "complete"}
    )
    visible = _operator_visible_state(representative) is True
    if bias in {"risk", "fade_short_review"}:
        meaningful_endpoint = (
            raw_return is not None
            and raw_return <= float(rule["risk_endpoint_return_max_fraction"])
        )
    else:
        meaningful_endpoint = (
            raw_return is not None
            and raw_return >= float(rule["long_endpoint_return_min_fraction"])
        )
    qualification_failures: list[str] = []
    if not _is_matured(view):
        qualification_failures.append("outcome_not_matured")
    if not meaningful_endpoint:
        qualification_failures.append("primary_endpoint_below_frozen_threshold")
    if volume is None or volume < float(rule["minimum_trailing_quote_volume_usd"]):
        qualification_failures.append("minimum_point_in_time_liquidity_not_met")
    if not membership:
        qualification_failures.append("point_in_time_membership_not_proven")
    if not warm:
        qualification_failures.append("warm_baseline_not_proven")
    if visible:
        qualification_failures.append("operator_visible_idea_present")
    qualifies = not qualification_failures
    reasons = _missed_reason_codes(representative) if qualifies else []
    if qualifies and not reasons:
        reasons = ["unexplained_by_supplied_point_in_time_fields"]
    return {
        "episode_id": view.episode_id,
        "classification": "missed_opportunity" if qualifies else "not_missed_opportunity",
        "qualifies": qualifies,
        "primary_reason": reasons[0] if reasons else None,
        "reason_codes": reasons,
        "qualification_failure_reasons": qualification_failures,
        "primary_horizon_return_fraction": raw_return,
        "minimum_long_return_fraction": float(
            rule["long_endpoint_return_min_fraction"]
        ),
        "maximum_risk_return_fraction": float(
            rule["risk_endpoint_return_max_fraction"]
        ),
        "minimum_trailing_quote_volume_usd": float(
            rule["minimum_trailing_quote_volume_usd"]
        ),
        "maximum_future_excursion_alone_is_sufficient": False,
        "return_unit": "fraction",
        "evidence_strength": "descriptive_rule_classification" if qualifies else "not_applicable",
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def classify_false_positive_and_late(
    representative: Mapping[str, Any],
    outcome: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify false-positive and late-entry symptoms using frozen rules."""

    protocol = empirical_validation_protocol.protocol_values()
    rules = protocol["false_positive_and_late_rules"]
    view = _ad_hoc_view(representative, outcome)
    representative = view.representative
    one_day = _directional_horizon_return(view, "1d")
    primary = _directional_return(view)
    mfe = _mfe(view)
    mae = _mae(view)
    asymmetry = (
        mfe / abs(mae) if mfe is not None and mae not in (None, 0.0) else None
    )
    pre_signal = _pre_signal_directional_move(view)
    chase = _score(representative.get("chase_risk_score"))
    failed_quickly = (
        one_day is not None
        and one_day <= float(rules["quick_failure_return_fraction"])
    )
    reversed_immediately = (
        representative.get("reversed_immediately") is True
        or _text(view.outcome.get("outcome_classification")) == "reversal"
        and failed_quickly
    )
    poor_asymmetry = (
        asymmetry is not None
        and asymmetry <= float(rules["poor_asymmetry_mfe_to_abs_mae_max"])
    )
    late_pre_signal = (
        pre_signal is not None
        and pre_signal >= float(rules["late_pre_signal_move_7d_fraction"])
    )
    high_chase = chase is not None and chase >= float(rules["high_chase_risk_min"])
    too_extended = (
        _text(representative.get("timing_state")) in {"extended", "exhausted"}
        or _text(representative.get("market_phase")) in {"extended", "exhaustion"}
    )
    known_catalyst_poor_timing = (
        classify_market_catalyst_category(representative)["category"]
        == "catalyst_led_after_significant_reaction"
        and primary is not None
        and primary <= 0.0
    )
    symptoms = [
        name
        for name, present in (
            ("failed_quickly", failed_quickly),
            ("reversed_immediately", reversed_immediately),
            ("poor_mfe_to_mae_asymmetry", poor_asymmetry),
            ("late_pre_signal_move", late_pre_signal),
            ("high_chase_risk", high_chase),
            ("too_extended", too_extended),
            ("proxy_data_dependency", _proxy_only(representative)),
            ("liquidity_or_spread_limited", _liquidity_or_spread_limited(representative)),
            ("excessive_operator_noise", representative.get("excessive_operator_noise") is True),
            ("repeated_episode_noise", _repeat_count(representative) > 0),
            ("known_catalyst_poor_timing", known_catalyst_poor_timing),
        )
        if present
    ]
    false_positive = failed_quickly or reversed_immediately or poor_asymmetry
    late_idea = late_pre_signal or high_chase or too_extended or known_catalyst_poor_timing
    issue_sources = _false_late_issue_sources(representative, symptoms)
    evaluable = _is_matured(view) and primary is not None
    return {
        "episode_id": view.episode_id,
        "classification_status": "evaluated" if evaluable else "not_evaluable",
        "false_positive": bool(evaluable and false_positive),
        "late_idea": bool(evaluable and late_idea),
        "symptom_codes": symptoms if evaluable else [],
        "issue_source_codes": issue_sources if evaluable else [],
        "primary_directional_return_fraction": primary,
        "one_day_directional_return_fraction": one_day,
        "mfe_fraction": mfe,
        "mae_fraction": mae,
        "mfe_to_mae_ratio": asymmetry,
        "pre_signal_directional_move_7d_fraction": pre_signal,
        "chase_risk_score": chase,
        "return_unit": "fraction",
        "classification_is_descriptive": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def operator_burden(
    representatives: Iterable[Mapping[str, Any]],
    *,
    partition: str,
    evidence_mode: str,
    selected_observation_days: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the frozen, outcome-blind operator burden simulation."""

    return empirical_operator_burden.build_operator_notification_burden(
        representatives,
        partition=partition,
        evidence_mode=evidence_mode,
        selected_observation_days=selected_observation_days,
    )


def _cohort_row(
    cohort_type: str,
    name: str,
    views: Sequence[_EpisodeView],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    directional = _directional_returns(views)
    raw = [value for view in views if (value := _primary_return(view)) is not None and _is_matured(view)]
    mfe = [value for view in views if (value := _mfe(view)) is not None and _is_matured(view)]
    mae = [value for view in views if (value := _mae(view)) is not None and _is_matured(view)]
    summary = _robust_summary(directional)
    mfe_summary = _robust_summary(mfe)
    mae_summary = _robust_summary(mae)
    sample_status, strength = _sample_evidence(len(directional))
    uncertainty = _bootstrap_mean_ci(
        directional,
        resamples=bootstrap_resamples,
        label=f"{partition}\0{evidence_mode}\0{cohort_type}\0{name}",
    )
    mean = summary["mean"]
    return {
        "cohort_type": cohort_type,
        "cohort": name,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": len(views),
        "matured_episode_count": sum(_is_matured(view) for view in views),
        "sample_size": len(directional),
        "sample_status": sample_status,
        "evidence_strength": strength,
        "result_direction": _result_direction(mean),
        "raw_return_sample_size": len(raw),
        "mean_raw_primary_return_fraction": _mean(raw),
        "mean_directional_return_fraction": mean,
        "median_directional_return_fraction": summary["median"],
        "trimmed_mean_10pct_directional_return_fraction": summary["trimmed_mean_10pct"],
        "hit_rate": (
            sum(value > 0.0 for value in directional) / len(directional)
            if directional else None
        ),
        "downside_5pct_fraction": summary["downside_5pct"],
        "worst_directional_return_fraction": min(directional) if directional else None,
        "mfe_sample_size": len(mfe),
        "mean_mfe_fraction": mfe_summary["mean"],
        "median_mfe_fraction": mfe_summary["median"],
        "trimmed_mean_10pct_mfe_fraction": mfe_summary["trimmed_mean_10pct"],
        "mae_sample_size": len(mae),
        "mean_mae_fraction": mae_summary["mean"],
        "median_mae_fraction": mae_summary["median"],
        "trimmed_mean_10pct_mae_fraction": mae_summary["trimmed_mean_10pct"],
        "mfe_to_mae_ratio_of_means": (
            mfe_summary["mean"] / abs(mae_summary["mean"])
            if mfe_summary["mean"] is not None and mae_summary["mean"] not in (None, 0.0)
            else None
        ),
        "excursion_sign_convention": {
            "mfe": "nonnegative_direction_adjusted_fraction",
            "mae": "nonpositive_direction_adjusted_fraction",
        },
        "uncertainty": uncertainty,
        "return_basis": "direction_aligned_primary_horizon_return",
        "return_unit": "fraction",
        "multiple_comparison_adjusted": False,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _score_monotonicity(
    views: Sequence[_EpisodeView],
    *,
    score_field: str,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    buckets: list[dict[str, Any]] = []
    for label, lower, upper in SCORE_BUCKETS:
        members = [
            view for view in views
            if (score := _score(view.representative.get(score_field))) is not None
            and lower <= score < upper
        ]
        buckets.append(_cohort_row(
            f"{score_field}_bucket",
            label,
            members,
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        ))
    populated = [row for row in buckets if row["sample_size"] > 0]
    comparisons: list[dict[str, Any]] = []
    expected = SCORE_EXPECTATIONS[score_field]
    for lower, higher in zip(populated, populated[1:]):
        delta = (
            float(higher["mean_directional_return_fraction"])
            - float(lower["mean_directional_return_fraction"])
        )
        violation = delta < 0.0 if expected.startswith("nondecreasing") else delta > 0.0
        comparisons.append({
            "lower_bucket": lower["cohort"],
            "higher_bucket": higher["cohort"],
            "lower_sample_size": lower["sample_size"],
            "higher_sample_size": higher["sample_size"],
            "lower_mean_directional_return_fraction": lower["mean_directional_return_fraction"],
            "higher_mean_directional_return_fraction": higher["mean_directional_return_fraction"],
            "observed_delta_fraction": delta,
            "expected_relationship": expected,
            "violation": violation,
            "statistical_significance_claim": False,
        })
    return {
        "score_field": score_field,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "expected_relationship": expected,
        "buckets": buckets,
        "comparable_pair_count": len(comparisons),
        "violation_count": sum(row["violation"] for row in comparisons),
        "evaluation_status": "evaluated" if comparisons else "not_evaluable",
        "not_evaluable_reason": (
            None if comparisons else "fewer_than_two_populated_score_buckets"
        ),
        "comparisons": comparisons,
        "interpretation": "descriptive_unadjusted_monotonicity_check",
        "probabilistic_calibration_claim": False,
        "model_changed": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _cost_sensitivity(
    views: Sequence[_EpisodeView],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
    cost_bps: Sequence[int],
    assumed_label: str,
) -> dict[str, Any]:
    gross = _directional_returns(views)
    gross_mean = _mean(gross)
    break_even = max(0.0, gross_mean * 10_000.0) if gross_mean is not None else None
    scenarios: list[dict[str, Any]] = []
    for bps in cost_bps:
        fraction = float(bps) / 10_000.0
        net = [value - fraction for value in gross]
        summary = _robust_summary(net)
        sample_status, strength = _sample_evidence(len(net))
        scenarios.append({
            "partition": partition,
            "evidence_mode": evidence_mode,
            "round_trip_cost_bps": int(bps),
            "round_trip_cost_fraction": fraction,
            "cost_basis": assumed_label,
            "historical_spread_observed": False,
            "sample_size": len(net),
            "sample_status": sample_status,
            "evidence_strength": strength,
            "mean_net_directional_return_fraction": summary["mean"],
            "median_net_directional_return_fraction": summary["median"],
            "trimmed_mean_10pct_net_directional_return_fraction": summary["trimmed_mean_10pct"],
            "net_hit_rate": sum(value > 0.0 for value in net) / len(net) if net else None,
            "downside_5pct_fraction": summary["downside_5pct"],
            "mean_survives_assumed_cost": summary["mean"] > 0.0 if summary["mean"] is not None else None,
            "uncertainty": _bootstrap_mean_ci(
                net,
                resamples=bootstrap_resamples,
                label=f"{partition}\0{evidence_mode}\0cost\0{bps}",
            ),
            "return_unit": "fraction",
            "cost_unit": "basis_points",
            "policy_eligible": False,
            "research_only": True,
            "auto_apply": False,
        })
    return {
        "partition": partition,
        "evidence_mode": evidence_mode,
        "gross_sample_size": len(gross),
        "gross_mean_directional_return_fraction": gross_mean,
        "break_even_mean_round_trip_cost_bps": break_even,
        "break_even_basis": "mean_directional_return_assumed_cost_sensitivity",
        "historical_spread_observed": False,
        "cost_basis": assumed_label,
        "scenarios": scenarios,
        "return_unit": "fraction",
        "cost_unit": "basis_points",
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _dynamic_cohorts(
    views: Sequence[_EpisodeView],
    *,
    cohort_type: str,
    getter: Any,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> list[dict[str, Any]]:
    grouped = _groups(views, lambda row: getter(row) or "unknown")
    grouped.setdefault("unknown", [])
    return [
        _cohort_row(
            cohort_type,
            name,
            grouped[name],
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        )
        for name in sorted(grouped)
    ]


def _episode_views(
    representatives: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    partition: str,
) -> list[_EpisodeView]:
    reps = [
        _flatten_representative(row)
        for row in representatives
        if isinstance(row, Mapping)
    ]
    outcome_by_id: dict[str, dict[str, Any]] = {}
    for raw in outcomes:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        episode_id = _required_episode_id(row)
        if episode_id in outcome_by_id:
            raise ValueError("duplicate_outcome_episode_id")
        outcome_by_id[episode_id] = row
    views: list[_EpisodeView] = []
    seen: set[str] = set()
    for rep in reps:
        episode_id = _required_episode_id(rep)
        if episode_id in seen:
            raise ValueError("duplicate_representative_episode_id")
        seen.add(episode_id)
        claimed_partition = _text(rep.get("partition"))
        if claimed_partition and claimed_partition != partition:
            raise ValueError("representative_partition_mismatch")
        outcome = outcome_by_id.pop(episode_id, {})
        outcome_partition = _text(outcome.get("partition"))
        if outcome_partition and outcome_partition != partition:
            raise ValueError("outcome_partition_mismatch")
        views.append(_EpisodeView(episode_id, rep, outcome))
    if outcome_by_id:
        raise ValueError("orphan_outcome_episode_id")
    return sorted(views, key=lambda row: (row.episode_id, _digest(row.representative)))


def _ad_hoc_view(
    representative: Mapping[str, Any], outcome: Mapping[str, Any] | None
) -> _EpisodeView:
    rep = _flatten_representative(representative)
    episode_id = _text(rep.get("episode_id")) or _digest(rep)
    return _EpisodeView(episode_id, rep, dict(outcome or {}))


def _directional_returns(views: Sequence[_EpisodeView]) -> list[float]:
    return [value for view in views if (value := _directional_return(view)) is not None]


def _directional_return(view: _EpisodeView) -> float | None:
    for field in (
        "primary_direction_adjusted_return",
        "direction_adjusted_return_fraction",
        "directional_return",
    ):
        explicit = _fraction_from_view(view, field)
        if explicit is not None:
            return explicit if _is_matured(view) else None
    nested = _primary_horizon_values(view)
    explicit = _fraction_from_mapping(nested, "direction_adjusted_return_fraction")
    if explicit is not None:
        return explicit if _is_matured(view) else None
    return _directional_value(view.representative, _primary_return(view)) if _is_matured(view) else None


def _primary_return(view: _EpisodeView) -> float | None:
    for field in ("primary_horizon_return_fraction", "primary_horizon_return"):
        value = _fraction_from_view(view, field)
        if value is not None:
            return value
    nested = _primary_horizon_values(view)
    for field in ("raw_return_fraction", "primary_horizon_return"):
        value = _fraction_from_mapping(nested, field)
        if value is not None:
            return value
    return None


def _directional_horizon_return(view: _EpisodeView, horizon: str) -> float | None:
    for source in (view.outcome, view.representative):
        mapped = source.get("return_by_horizon") or source.get("horizons")
        if isinstance(mapped, Mapping) and mapped.get(horizon) is not None:
            horizon_value = mapped.get(horizon)
            if isinstance(horizon_value, Mapping):
                value = _fraction_from_mapping(
                    horizon_value,
                    "direction_adjusted_return_fraction",
                )
                if value is not None:
                    return value
                value = _fraction_from_mapping(horizon_value, "raw_return_fraction")
            else:
                value = _fraction_value(
                    horizon_value,
                    source.get("return_unit") or "fraction_by_protocol",
                )
            return _directional_value(view.representative, value)
        direct = _fraction_from_mapping(source, f"return_{horizon}")
        if direct is not None:
            return _directional_value(view.representative, direct)
    return None


def _mfe(view: _EpisodeView) -> float | None:
    for field in ("mfe_fraction", "max_favorable_excursion", "maximum_favorable_excursion"):
        value = _fraction_from_view(view, field)
        if value is not None:
            return max(0.0, value)
    nested = _primary_horizon_values(view)
    for field in ("mfe_fraction", "max_favorable_excursion_fraction"):
        value = _fraction_from_mapping(nested, field)
        if value is not None:
            return max(0.0, value)
    return None


def _mae(view: _EpisodeView) -> float | None:
    for field in ("mae_fraction", "max_adverse_excursion", "maximum_adverse_excursion"):
        value = _fraction_from_view(view, field)
        if value is not None:
            return -abs(value)
    nested = _primary_horizon_values(view)
    for field in ("mae_fraction", "max_adverse_excursion_fraction"):
        value = _fraction_from_mapping(nested, field)
        if value is not None:
            return -abs(value)
    return None


def _pre_signal_directional_move(view: _EpisodeView) -> float | None:
    for source in (view.outcome, view.representative):
        raw = source.get("pre_signal_move_7d")
        if isinstance(raw, Mapping):
            adjusted = _fraction_from_mapping(
                raw,
                "direction_adjusted_return_fraction",
            )
            if adjusted is not None:
                return adjusted
            value = _fraction_from_mapping(raw, "raw_return_fraction")
        else:
            value = _fraction_from_mapping(source, "pre_signal_move_7d")
        if value is not None:
            return _directional_value(view.representative, value)
    return None


def _is_matured(view: _EpisodeView) -> bool:
    for source in (view.outcome, view.representative):
        state = _text(
            source.get("outcome_state")
            or source.get("maturation_state")
            or source.get("outcome_status")
            or source.get("status")
        )
        if state:
            if state == "matured":
                return True
            if state in {
                "not_due",
                "pending",
                "due_missing_price",
                "missing_data",
                "contract_excluded",
            }:
                return False
        if source.get("matured") is True:
            return True
    nested_state = _text(_primary_horizon_values(view).get("maturity_status"))
    if nested_state:
        return nested_state == "matured"
    return False


def _fraction_from_view(view: _EpisodeView, field: str) -> float | None:
    for source in (view.outcome, view.representative):
        value = _fraction_from_mapping(source, field)
        if value is not None:
            return value
    return None


def _fraction_from_mapping(source: Mapping[str, Any], field: str) -> float | None:
    raw = source.get(field)
    if raw is None:
        return None
    if field.endswith("_fraction"):
        unit = source.get(f"{field}_unit") or "fraction"
    elif field.startswith("primary_horizon_return"):
        unit = source.get(f"{field}_unit") or source.get(
            "primary_horizon_return_unit"
        )
    else:
        unit = source.get(f"{field}_unit")
    if unit in (None, ""):
        unit = source.get("return_unit") or "fraction_by_protocol"
    return _fraction_value(raw, unit)


def _primary_horizon_values(view: _EpisodeView) -> Mapping[str, Any]:
    for source in (view.outcome, view.representative):
        direct = source.get("primary_metrics")
        if isinstance(direct, Mapping):
            return direct
        primary = _text(source.get("primary_horizon")) or "3d"
        horizons = source.get("horizons")
        if isinstance(horizons, Mapping) and isinstance(horizons.get(primary), Mapping):
            return horizons[primary]
    return {}


def _flatten_representative(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    projection = row.get("decision_projection")
    if isinstance(projection, Mapping):
        for key, value in projection.items():
            result.setdefault(str(key), value)
    aliases = {
        "partition": "replay_partition",
        "operator_visible_idea": "operator_visible",
        "data_quality_mode": "replay_data_quality_mode",
        "anomaly_family": "candidate_family_id",
    }
    for target, source in aliases.items():
        if target not in result and source in result:
            result[target] = result[source]
    feature_quality = row.get("replay_feature_quality")
    if isinstance(feature_quality, Mapping):
        result.setdefault(
            "catalyst_attribution_timing",
            feature_quality.get("catalyst_evidence_timing"),
        )
    return result


def _operator_visible_state(row: Mapping[str, Any]) -> bool | None:
    for field in ("operator_visible_idea", "operator_visible"):
        value = row.get(field)
        if isinstance(value, bool):
            return value
    return None


def _fraction_value(raw: Any, unit: Any) -> float | None:
    value = _number(raw)
    if value is None:
        return None
    normalized_unit = _text(unit)
    if normalized_unit in _FRACTION_UNITS:
        return value
    if normalized_unit in _PERCENT_POINT_UNITS:
        return value / 100.0
    return None


def _has_invalid_declared_return_unit(view: _EpisodeView) -> bool:
    for source in (view.outcome, view.representative):
        for field in (
            "primary_horizon_return",
            "primary_horizon_return_fraction",
            "max_favorable_excursion",
            "max_adverse_excursion",
            "mfe_fraction",
            "mae_fraction",
        ):
            if source.get(field) is None:
                continue
            unit = source.get(f"{field}_unit") or source.get("return_unit")
            if unit not in (None, "") and _text(unit) not in _FRACTION_UNITS | _PERCENT_POINT_UNITS:
                return True
    return False


def _directional_value(representative: Mapping[str, Any], value: float | None) -> float | None:
    if value is None:
        return None
    sign = _DIRECTION_SIGN.get(_text(representative.get("directional_bias")))
    return value * sign if sign is not None else None


def _sample_evidence(sample_size: int) -> tuple[str, str]:
    if sample_size == 0:
        return "no_sample", "no_evidence"
    if sample_size < 5:
        return "insufficient_sample", "insufficient"
    if sample_size < 30:
        return "descriptive_sample", "descriptive_only"
    if sample_size < 100:
        return "cohort_directional_sample", "exploratory"
    return "shadow_recommendation_sample", "stronger_exploratory"


def _result_direction(mean: float | None) -> str:
    if mean is None:
        return "no_result"
    if mean > 0.0:
        return "positive_descriptive"
    if mean < 0.0:
        return "negative_descriptive"
    return "flat_descriptive"


def _market_catalyst_result(category: str, basis: str) -> dict[str, Any]:
    return {
        "category": category,
        "timing_basis": basis,
        "retrospective_attribution_used": False,
        "causal_claim": False,
        "research_only": True,
        "auto_apply": False,
    }


def _exact_timestamp_order(row: Mapping[str, Any]) -> int | None:
    if (
        _text(row.get("catalyst_time_certainty")) != "exact"
        or _text(row.get("market_reaction_time_certainty")) != "exact"
    ):
        return None
    catalyst = _aware_datetime(row.get("catalyst_public_at"))
    reaction = _aware_datetime(row.get("market_reaction_started_at"))
    if catalyst is None or reaction is None:
        return None
    return -1 if catalyst < reaction else (1 if catalyst > reaction else 0)


def _missed_reason_codes(row: Mapping[str, Any]) -> list[str]:
    checks = (
        ("no_anomaly_generated", row.get("anomaly_generated") is False),
        ("insufficient_history", _text(row.get("baseline_status")) == "insufficient_history"),
        ("data_stale", _text(row.get("freshness_status")) == "stale"),
        ("liquidity_gate", row.get("liquidity_gate_passed") is False),
        ("spread_unavailable", _text(row.get("spread_status")) == "unavailable"),
        ("proxy_only_data_cap", row.get("proxy_only_data_cap") is True),
        ("actionability_below_threshold", row.get("actionability_below_threshold") is True),
        ("risk_too_high", row.get("risk_too_high") is True),
        ("duplicate_suppression", row.get("duplicate_suppressed") is True),
        ("identity_failure", row.get("identity_failure") is True),
        ("calendar_risk", row.get("calendar_risk_blocked") is True),
        ("missing_technical_context", row.get("technical_context_missing") is True),
        ("catalyst_uncertainty", row.get("catalyst_uncertainty_blocked") is True),
        ("feature_bug", row.get("feature_bug") is True),
        ("universe_exclusion", row.get("universe_excluded") is True),
        ("outcome_outside_supported_horizon", row.get("outcome_outside_supported_horizon") is True),
    )
    return [name for name, present in checks if present]


def _false_late_issue_sources(row: Mapping[str, Any], symptoms: Sequence[str]) -> list[str]:
    sources: list[str] = []
    symptom_set = set(symptoms)
    if symptom_set & {"failed_quickly", "reversed_immediately"}:
        sources.append("anomaly_detection")
    if symptom_set & {"late_pre_signal_move", "high_chase_risk", "too_extended", "known_catalyst_poor_timing"}:
        sources.append("timing_model")
    if "poor_mfe_to_mae_asymmetry" in symptom_set:
        sources.append("actionability_model")
    if row.get("risk_too_low_for_realized_outcome") is True:
        sources.append("risk_model")
    if row.get("route_policy_concern") is True:
        sources.append("route_policy")
    if symptom_set & {"proxy_data_dependency", "liquidity_or_spread_limited"}:
        sources.append("data_quality")
    if row.get("source_quality_concern") is True:
        sources.append("source_quality")
    if _text(row.get("spread_status")) in {"unavailable", "stale"}:
        sources.append("missing_execution_evidence")
    if "repeated_episode_noise" in symptom_set:
        sources.append("duplicate_policy")
    if row.get("expiry_policy_concern") is True:
        sources.append("expiry_policy")
    return list(dict.fromkeys(sources))


def _data_quality_mode(view: _EpisodeView, fallback: str) -> str:
    for source in (view.representative, view.outcome):
        value = _text(
            source.get("data_quality_mode")
            or source.get("replay_data_quality_mode")
            or source.get("evidence_mode")
        )
        if value:
            return value
    return fallback


def _proxy_only(row: Mapping[str, Any]) -> bool:
    if row.get("proxy_only") is True:
        return True
    mode = _text(row.get("data_quality_mode"))
    if "proxy" in mode:
        return True
    basis = row.get("feature_basis")
    return isinstance(basis, Mapping) and bool(basis) and all(
        "proxy" in _text(value) for value in basis.values()
    )


def _liquidity_or_spread_limited(row: Mapping[str, Any]) -> bool:
    return (
        row.get("liquidity_gate_passed") is False
        or _text(row.get("tradability_status")) in {"poor", "blocked"}
        or _text(row.get("spread_status")) in {"verified_wide", "unavailable", "stale"}
    )


def _repeat_count(row: Mapping[str, Any]) -> int:
    explicit = row.get("dependent_repeat_count")
    if type(explicit) is int and explicit >= 0:
        return explicit
    members = row.get("episode_member_count")
    return max(0, members - 1) if type(members) is int and members >= 1 else 0


def _origin_set(row: Mapping[str, Any]) -> set[str]:
    raw = row.get("thesis_origins")
    origins = {
        _text(value) for value in raw
    } if isinstance(raw, (list, tuple, set)) else set()
    primary = _text(row.get("primary_thesis_origin"))
    if primary:
        origins.add(primary)
    return {value for value in origins if value}


def _groups(views: Sequence[_EpisodeView], getter: Any) -> dict[str, list[_EpisodeView]]:
    grouped: dict[str, list[_EpisodeView]] = defaultdict(list)
    for view in views:
        grouped[getter(view) or "unknown"].append(view)
    return grouped


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _required_episode_id(row: Mapping[str, Any]) -> str:
    value = _text(row.get("episode_id"))
    if not value:
        raise ValueError("episode_id_required")
    return value


def _bootstrap_resamples(value: int | None, protocol: Mapping[str, Any]) -> int:
    selected = (
        protocol["statistics"]["bootstrap_resamples_full"]
        if value is None
        else value
    )
    if type(selected) is not int or not 1 <= selected <= 100_000:
        raise ValueError("bootstrap_resamples_out_of_bounds")
    return selected


def _score(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and 0.0 <= number <= 100.0 else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "MARKET_CATALYST_CATEGORIES",
    "METHOD",
    "PRIMARY_ORIGINS",
    "ROUTES",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCORE_FIELDS",
    "build_empirical_replay_analysis",
    "build_empirical_replay_analysis_from_episodes",
    "classify_false_positive_and_late",
    "classify_market_catalyst_category",
    "classify_missed_opportunity",
    "operator_burden",
]
