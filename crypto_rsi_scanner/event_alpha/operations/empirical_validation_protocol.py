"""Frozen protocol for Decision Radar empirical validation v1.

This module is deliberately data-free.  It defines the point-in-time research
rules that must be fixed before the final-test partition is evaluated.  A
protocol change requires a new version; callers may not override partitions,
primary outcomes, missed-opportunity rules, or shadow scenarios at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_ID = "decision_radar.empirical_validation_protocol"
SCHEMA_VERSION = 1
PROTOCOL_VERSION = "decision_radar_empirical_validation_v1"
FROZEN_AT = "2026-07-16T05:30:00Z"
DETERMINISTIC_SEED = 20260716


_PROTOCOL: dict[str, Any] = {
    "schema_id": SCHEMA_ID,
    "schema_version": SCHEMA_VERSION,
    "protocol_version": PROTOCOL_VERSION,
    "frozen_at": FROZEN_AT,
    "status": "frozen_before_final_test_evaluation",
    "research_only": True,
    "auto_apply": False,
    "human_approval_required_for_policy_change": True,
    "historical_sources": [
        {
            "name": "binance_daily_ohlcv_cache",
            "mode": "historical_ohlcv",
            "fields": ["open_time", "high", "low", "close", "base_volume", "quote_volume"],
            "provider_calls_per_replay": 0,
            "known_limitation": "cached candidate pool reflects pairs retained locally and has residual delisting survivorship",
        },
        {
            "name": "binance_trailing_volume_membership",
            "mode": "point_in_time_volume_universe",
            "fields": ["trailing_30d_mean_quote_volume", "daily_rank"],
            "provider_calls_per_replay": 0,
            "known_limitation": "membership is point-in-time inside the cached candidate pool, not a complete historical listing master",
        },
        {
            "name": "decision_radar_live_campaign",
            "mode": "live_no_send",
            "provider_calls_per_research_report": 0,
            "known_limitation": "short observational stream remains separate from replay evidence",
        },
        {
            "name": "integrated_radar_fixture",
            "mode": "fixture",
            "provider_calls_per_replay": 0,
            "known_limitation": "mechanics coverage only; never evidence of forward value",
        },
    ],
    "analysis_window": {
        "start_inclusive": "2021-06-12T00:00:00Z",
        "idea_end_exclusive": "2026-06-01T00:00:00Z",
        "outcome_data_end_exclusive": "2026-06-18T00:00:00Z",
        "reason": "frozen from locally available daily-cache coverage while retaining future bars only for matured outcomes",
    },
    "partitions": [
        {
            "name": "development",
            "start_inclusive": "2021-06-12T00:00:00Z",
            "end_exclusive": "2023-01-01T00:00:00Z",
            "outcome_end_exclusive": "2023-01-15T00:00:00Z",
            "policy_selection_allowed": True,
        },
        {
            "name": "validation",
            "start_inclusive": "2023-01-15T00:00:00Z",
            "end_exclusive": "2025-01-01T00:00:00Z",
            "outcome_end_exclusive": "2025-01-15T00:00:00Z",
            "policy_selection_allowed": True,
        },
        {
            "name": "final_test",
            "start_inclusive": "2025-01-15T00:00:00Z",
            "end_exclusive": "2026-06-01T00:00:00Z",
            "outcome_end_exclusive": "2026-06-18T00:00:00Z",
            "policy_selection_allowed": False,
        },
    ],
    "partition_embargoes": [
        {
            "after_partition": "development",
            "before_partition": "validation",
            "start_inclusive": "2023-01-01T00:00:00Z",
            "end_exclusive": "2023-01-15T00:00:00Z",
            "purpose": "outcome_only_maximum_sensitivity_horizon_purge",
            "idea_evaluation_allowed": False,
        },
        {
            "after_partition": "validation",
            "before_partition": "final_test",
            "start_inclusive": "2025-01-01T00:00:00Z",
            "end_exclusive": "2025-01-15T00:00:00Z",
            "purpose": "outcome_only_maximum_sensitivity_horizon_purge",
            "idea_evaluation_allowed": False,
        },
    ],
    "point_in_time_universe": {
        "ranking_field": "trailing_mean_quote_volume_usd",
        "lookback_days": 30,
        "minimum_history_days": 30,
        "rank_at": "daily_candle_close",
        "full_top_n": 100,
        "medium_top_n": 30,
        "smoke_top_n": 3,
        "tie_method": "minimum_rank",
        "future_rank_forbidden": True,
        "current_metadata_fallback_forbidden": True,
    },
    "observation": {
        "cadence": "1d",
        "timestamp": "daily_candle_close",
        "entry_price": "same_daily_close_after_feature_observation",
        "minimum_spacing_hours": 24,
        "intraday_fields_without_intraday_data": "unavailable",
        "same_bar_high_low_for_outcome_forbidden": True,
    },
    "feature_warmup": {
        "return_days": [1, 3, 7, 14],
        "volume_zscore_lookback_days": 90,
        "volume_zscore_min_observations": 20,
        "liquidity_lookback_days": 30,
        "volatility_lookback_days": 30,
        "rsi_lookback_days": 14,
        "market_regime_long_ma_days": 200,
        "baseline_status_before_complete": "insufficient_history",
        "partial_feature_substitution": "forbidden",
    },
    "replay_data_quality_modes": [
        "temporal_direct",
        "provider_observed",
        "historical_ohlcv",
        "point_in_time_volume_universe",
        "cross_sectional_proxy",
        "calendar_fixture",
        "catalyst_replay",
        "missing",
        "unavailable",
    ],
    "missing_data_policy": {
        "spread_without_order_book": "unavailable",
        "market_cap_without_historical_series": "missing",
        "derivatives_without_historical_snapshot": "unavailable",
        "calendar_without_time_valid_snapshot": "missing",
        "catalyst_without_attribution_public_by_observation": "unknown",
        "onchain_without_historical_snapshot": "unavailable",
        "proxy_must_be_labeled": True,
        "direct_and_proxy_results_reported_separately": True,
    },
    "outcomes": {
        "primary_horizon_days": 3,
        "sensitivity_horizons_days": [1, 7, 14],
        "relative_benchmarks": ["BTC", "ETH"],
        "return_entry": "idea_close",
        "return_exit": "future_close",
        "mfe_basis": "future_high_after_idea_bar",
        "mae_basis": "future_low_after_idea_bar",
        "timing_metrics": [
            "time_to_mfe_hours",
            "time_to_mae_hours",
            "time_to_invalidation_hours",
            "pre_signal_move_7d",
        ],
        "classifications": [
            "continuation",
            "reversal",
            "breakout_failure",
            "fade_success",
            "risk_event_validation",
            "expired_without_resolution",
            "post_expiry_continuation",
            "post_expiry_reversal",
        ],
        "outcome_before_maturity": "pending",
        "outcome_data_visible_to_scoring": False,
        "partition_outcome_boundary_rule": "horizon_due_at_lt_outcome_end_exclusive",
        "partition_embargo_days": 14,
    },
    "episodes": {
        "method": "fixed_start_window",
        "primary_window_hours": 24,
        "boundary_rule": "member_observed_at_lte_episode_start_plus_window",
        "window_end_inclusive": True,
        "sensitivity_window_hours": [12, 48],
        "identity": ["canonical_asset_id", "directional_bias", "anomaly_family"],
        "representative": "first_eligible_observation",
        "representative_reselection": "forbidden",
        "dependent_repeats_counted_as_independent": False,
        "progression_fields": [
            "radar_route",
            "actionability_score",
            "evidence_confidence_score",
            "risk_score",
            "urgency_score",
            "chase_risk_score",
            "market_phase",
            "catalyst_status",
            "spread_status",
            "derivatives_status",
        ],
    },
    "missed_opportunity_rule": {
        "primary_horizon_days": 3,
        "long_endpoint_return_min_fraction": 0.12,
        "risk_endpoint_return_max_fraction": -0.10,
        "minimum_trailing_quote_volume_usd": 2_000_000.0,
        "requires_point_in_time_membership": True,
        "requires_warm_baseline": True,
        "requires_operator_visible_idea": False,
        "maximum_future_excursion_alone_is_sufficient": False,
        "classification_occurs_only_after_maturity": True,
    },
    "false_positive_and_late_rules": {
        "quick_failure_horizon_days": 1,
        "quick_failure_return_fraction": -0.05,
        "poor_asymmetry_mfe_to_abs_mae_max": 0.75,
        "late_pre_signal_move_7d_fraction": 0.20,
        "high_chase_risk_min": 70.0,
        "classification_is_descriptive": True,
    },
    "matched_controls": {
        "controls_per_episode": 1,
        "match_fields": ["partition", "observation_date", "market_regime", "liquidity_tier"],
        "exclude_signal_assets_same_timestamp": True,
        "selection": "deterministic_hash_rank",
        "selection_uses_outcomes": False,
        "seed": DETERMINISTIC_SEED,
    },
    "benchmark_policies": [
        "matched_non_signal",
        "same_day_top_raw_mover",
        "volume_anomaly_only",
        "rsi_only",
        "btc_buy_and_hold_context",
        "eth_buy_and_hold_context",
        "top_relative_strength",
        "late_momentum_fade",
    ],
    "cost_scenarios": {
        "round_trip_cost_bps": [0, 20, 50, 100, 200],
        "review_delay_days": [0, 1],
        "historical_spread_observation_status": "unavailable",
        "unobserved_cost_label": "assumed_sensitivity_not_observed",
        "break_even_cost_reported": True,
        "position_liquidity_fraction_scenarios": [0.0001, 0.001, 0.005],
        "maximum_simultaneous_ideas": [1, 3, 5],
        "maximum_daily_ideas": [1, 3, 5, 10],
        "component_profiles": [
            {
                "name": "fees_only",
                "fee_bps": 20,
                "spread_bps": 0,
                "slippage_bps": 0,
                "adverse_selection_bps": 0,
            },
            {
                "name": "fees_plus_assumed_spread",
                "fee_bps": 20,
                "spread_bps": 30,
                "slippage_bps": 0,
                "adverse_selection_bps": 0,
            },
            {
                "name": "fees_spread_slippage",
                "fee_bps": 20,
                "spread_bps": 30,
                "slippage_bps": 50,
                "adverse_selection_bps": 0,
            },
            {
                "name": "stressed_adverse_selection",
                "fee_bps": 20,
                "spread_bps": 30,
                "slippage_bps": 50,
                "adverse_selection_bps": 100,
            },
        ],
        "stop_loss_fraction_scenarios": [0.03, 0.05, 0.10],
        "trailing_stop_fraction_scenarios": [0.03, 0.05, 0.10],
        "intraday_path_order_status": "unavailable_from_daily_ohlcv",
    },
    "statistics": {
        "confidence_level": 0.95,
        "bootstrap_resamples_full": 2000,
        "bootstrap_resamples_medium": 500,
        "bootstrap_resamples_smoke": 100,
        "bootstrap_unit": "episode",
        "deterministic_seed": DETERMINISTIC_SEED,
        "reported_location": ["mean", "median", "trimmed_mean_10pct"],
        "reported_risk": ["hit_rate", "mfe", "mae", "downside_5pct", "drawdown_proxy"],
        "multiple_comparison_policy": "exploratory_cohorts_are_unadjusted_and_must_carry_a_multiple_comparison_warning",
        "causal_claims_from_matched_controls": False,
    },
    "minimum_samples": {
        "descriptive": 5,
        "cohort_directional": 30,
        "shadow_recommendation_development_validation": 100,
        "final_test_confirmation": 30,
        "live_policy_change": 100,
        "below_minimum_state": "insufficient_sample",
    },
    "shadow_scenarios": [
        {"name": "production_policy", "changes": {}},
        {"name": "dashboard_watch_40", "changes": {"dashboard_watch_threshold": 40.0}},
        {"name": "dashboard_watch_50", "changes": {"dashboard_watch_threshold": 50.0}},
        {"name": "actionable_70", "changes": {"actionability_threshold": 70.0}},
        {"name": "actionable_evidence_60", "changes": {"actionable_min_evidence": 60.0}},
        {"name": "actionable_max_risk_55", "changes": {"actionable_max_risk": 55.0}},
        {"name": "unknown_spread_dashboard_only", "changes": {"unknown_spread_actionable": False}},
        {"name": "rapid_urgency_78", "changes": {"rapid_urgency_threshold": 78.0}},
        {"name": "expiry_24h", "changes": {"maximum_expiry_hours": 24}},
        {"name": "family_cooldown_48h", "changes": {"family_cooldown_hours": 48}},
    ],
    "operator_burden": {
        "urgent_routes": [
            "high_confidence_watch",
            "actionable_watch",
            "rapid_market_anomaly",
            "risk_watch",
        ],
        "metrics": [
            "ideas_per_day",
            "urgent_items_per_day",
            "digest_items_per_day",
            "repeated_family_items",
            "material_change_interval_hours",
            "idea_lifetime_hours",
            "review_queue_size",
            "system_warning_volume",
            "calendar_reminder_volume",
        ],
        "budgets": {
            "urgent_per_cycle": [1, 3, 5],
            "urgent_per_day": [3, 5, 10],
            "one_item_per_visible_family": True,
            "material_change_only": True,
            "cooldown_hours": [6, 12, 24, 48],
        },
    },
    "walk_forward": {
        "selection_partitions": ["development", "validation"],
        "confirmation_partition": "final_test",
        "final_test_used_for_tuning": False,
        "rolling_train_days": 730,
        "rolling_test_days": 180,
        "minimum_folds": 3,
        "outcome_purge_rule": "primary_horizon_due_at_lt_fold_boundary",
        "partial_test_fold_policy": "omit_fold_shorter_than_rolling_test_days",
        "scenario_set_frozen_with_protocol": True,
        "recommendation_set_must_be_hashed_before_final_test": True,
    },
    "shadow_recommendation_rule": {
        "rule_id": "noninferior_return_failure_selected_day_burden_v1",
        "minimum_sample_key": "shadow_recommendation_development_validation",
        "requires_material_policy_change": True,
        "mean_directional_return_check": "candidate_gte_production",
        "quick_failure_rate_check": "candidate_lte_production",
        "ideas_per_selected_observation_day_check": (
            "candidate_lte_1_2x_production"
        ),
        "missing_required_metric_status": "not_supported",
        "candidate_status": "candidate",
        "scenario_selection_allowed": True,
    },
    "final_test_confirmation_rule": {
        "rule_id": "noninferior_return_failure_selected_day_burden_v1",
        "candidate_set": "sealed_development_validation_candidates_only",
        "minimum_sample_key": "final_test_confirmation",
        "minimum_matured_visible_episodes": 30,
        "requires_material_policy_change": True,
        "mean_directional_return_check": "candidate_gte_production",
        "quick_failure_rate_check": "candidate_lte_production",
        "ideas_per_selected_observation_day_check": (
            "candidate_lte_1_2x_production"
        ),
        "missing_required_metric_status": "rejected",
        "statuses": ["confirmed", "rejected", "insufficient_sample"],
        "scenario_selection_allowed": False,
    },
    "policy_change_rules": {
        "production_mutation_allowed": False,
        "recommendations_only": True,
        "final_test_may_reject_but_not_select_a_scenario": True,
        "requires_independent_human_approval": True,
        "requires_versioned_decision_and_rollback": True,
        "threshold_lowering_to_create_ideas": False,
    },
    "safety": {
        "provider_calls": 0,
        "authorization_mutations": 0,
        "telegram_sends": 0,
        "trades": 0,
        "orders": 0,
        "event_alpha_paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "dashboard_authority_mutations": 0,
    },
}


def protocol_values() -> dict[str, Any]:
    """Return a defensive copy of the immutable v1 protocol."""

    return deepcopy(_PROTOCOL)


def canonical_protocol_bytes(value: Mapping[str, Any] | None = None) -> bytes:
    payload = dict(value) if value is not None else _PROTOCOL
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def protocol_sha256(value: Mapping[str, Any] | None = None) -> str:
    return hashlib.sha256(canonical_protocol_bytes(value)).hexdigest()


def selected_observation_days_sha256(days: Iterable[str]) -> str:
    """Return the canonical digest for an exact set of selected UTC days."""

    selected: set[str] = set()
    for value in days:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("selected_observation_day_invalid")
        selected.add(value.strip())
    payload = ("\n".join(sorted(selected)) + ("\n" if selected else "")).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_protocol(value: Mapping[str, Any]) -> list[str]:
    """Validate the closed rules that protect final-test isolation."""

    errors: list[str] = []
    if dict(value) != _PROTOCOL:
        errors.append("protocol_not_exact_frozen_v1")
    if value.get("status") != "frozen_before_final_test_evaluation":
        errors.append("protocol_not_frozen")
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        errors.append("research_safety_invalid")
    errors.extend(_validate_partition_contract(value))
    walk = value.get("walk_forward")
    if not isinstance(walk, Mapping) or walk.get("final_test_used_for_tuning") is not False:
        errors.append("final_test_firewall_invalid")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, Mapping) or outcomes.get("primary_horizon_days") != 3:
        errors.append("primary_outcome_drift")
    elif (
        outcomes.get("partition_embargo_days") != max(
            outcomes.get("sensitivity_horizons_days") or [0]
        )
        or outcomes.get("partition_outcome_boundary_rule")
        != "horizon_due_at_lt_outcome_end_exclusive"
    ):
        errors.append("partition_outcome_firewall_invalid")
    warmup = value.get("feature_warmup")
    if not isinstance(warmup, Mapping) or (
        warmup.get("volume_zscore_lookback_days") != 90
        or warmup.get("volume_zscore_min_observations") != 20
    ):
        errors.append("volume_zscore_warmup_contract_invalid")
    episodes = value.get("episodes")
    if not isinstance(episodes, Mapping) or (
        episodes.get("primary_window_hours") != 24
        or episodes.get("boundary_rule")
        != "member_observed_at_lte_episode_start_plus_window"
        or episodes.get("window_end_inclusive") is not True
    ):
        errors.append("episode_boundary_contract_invalid")
    missed = value.get("missed_opportunity_rule")
    if not isinstance(missed, Mapping) or missed.get("maximum_future_excursion_alone_is_sufficient") is not False:
        errors.append("missed_opportunity_rule_invalid")
    confirmation = value.get("final_test_confirmation_rule")
    shadow_recommendation = value.get("shadow_recommendation_rule")
    minimum_samples = value.get("minimum_samples")
    if not isinstance(confirmation, Mapping) or not isinstance(
        minimum_samples, Mapping
    ):
        errors.append("final_test_confirmation_rule_invalid")
    elif (
        confirmation.get("minimum_sample_key") != "final_test_confirmation"
        or confirmation.get("minimum_matured_visible_episodes")
        != minimum_samples.get("final_test_confirmation")
        or confirmation.get("scenario_selection_allowed") is not False
        or confirmation.get("statuses")
        != ["confirmed", "rejected", "insufficient_sample"]
        or confirmation.get("ideas_per_selected_observation_day_check")
        != "candidate_lte_1_2x_production"
        or "ideas_per_active_day_check" in confirmation
    ):
        errors.append("final_test_confirmation_rule_invalid")
    if (
        not isinstance(shadow_recommendation, Mapping)
        or shadow_recommendation.get(
            "ideas_per_selected_observation_day_check"
        )
        != "candidate_lte_1_2x_production"
        or "ideas_per_active_day_check" in shadow_recommendation
    ):
        errors.append("shadow_recommendation_rule_invalid")
    operator_burden = value.get("operator_burden")
    if not isinstance(operator_burden, Mapping) or operator_burden.get(
        "urgent_routes"
    ) != [
        "high_confidence_watch",
        "actionable_watch",
        "rapid_market_anomaly",
        "risk_watch",
    ]:
        errors.append("operator_urgent_route_contract_invalid")
    costs = value.get("cost_scenarios")
    if not isinstance(costs, Mapping) or [
        sum(
            int(row.get(field) or 0)
            for field in (
                "fee_bps",
                "spread_bps",
                "slippage_bps",
                "adverse_selection_bps",
            )
        )
        for row in costs.get("component_profiles", [])
        if isinstance(row, Mapping)
    ] != [20, 50, 100, 200]:
        errors.append("cost_component_profile_contract_invalid")
    safety = value.get("safety")
    if not isinstance(safety, Mapping) or any(type(item) is not int or item != 0 for item in safety.values()):
        errors.append("safety_counter_invalid")
    return list(dict.fromkeys(errors))


def _validate_partition_contract(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    partitions = value.get("partitions")
    expected_names = ["development", "validation", "final_test"]
    if not isinstance(partitions, list) or [
        row.get("name") for row in partitions if isinstance(row, Mapping)
    ] != expected_names:
        return ["partition_order_invalid"]
    parsed: list[tuple[str, datetime, datetime, datetime]] = []
    for row in partitions:
        try:
            start = _utc(row["start_inclusive"])
            end = _utc(row["end_exclusive"])
            outcome_end = _utc(row["outcome_end_exclusive"])
        except (KeyError, TypeError, ValueError):
            errors.append("partition_time_invalid")
            continue
        if start >= end:
            errors.append("partition_empty")
        if outcome_end < end:
            errors.append("partition_outcome_window_invalid")
        parsed.append((str(row["name"]), start, end, outcome_end))
    if partitions[-1].get("policy_selection_allowed") is not False:
        errors.append("final_test_selection_not_blocked")
    embargoes = value.get("partition_embargoes")
    if not isinstance(embargoes, list):
        errors.append("partition_embargoes_invalid")
    elif len(parsed) == len(partitions):
        errors.extend(_validate_partition_embargoes(value, parsed, embargoes))
    return errors


def _validate_partition_embargoes(
    value: Mapping[str, Any],
    parsed: list[tuple[str, datetime, datetime, datetime]],
    embargoes: list[Any],
) -> list[str]:
    errors: list[str] = []
    expected: list[dict[str, Any]] = []
    outcomes = value.get("outcomes")
    embargo_days = int(outcomes.get("partition_embargo_days") or 0) if isinstance(
        outcomes, Mapping
    ) else 0
    for prior, current in zip(parsed, parsed[1:]):
        prior_name, _prior_start, prior_end, prior_outcome_end = prior
        current_name, current_start, _current_end, _current_outcome_end = current
        if current_start <= prior_end:
            errors.append("partition_gap_or_overlap")
            continue
        if prior_outcome_end != current_start:
            errors.append("partition_outcome_embargo_alignment_invalid")
        if (current_start - prior_end).days != embargo_days:
            errors.append("partition_embargo_duration_invalid")
        expected.append({
            "after_partition": prior_name,
            "before_partition": current_name,
            "start_inclusive": prior_end.isoformat().replace("+00:00", "Z"),
            "end_exclusive": current_start.isoformat().replace("+00:00", "Z"),
            "purpose": "outcome_only_maximum_sensitivity_horizon_purge",
            "idea_evaluation_allowed": False,
        })
    if embargoes != expected:
        errors.append("partition_embargoes_invalid")
    try:
        analysis_end = _utc(value["analysis_window"]["outcome_data_end_exclusive"])
    except (KeyError, TypeError, ValueError):
        errors.append("analysis_outcome_window_invalid")
    else:
        if parsed[-1][3] != analysis_end:
            errors.append("final_outcome_window_invalid")
    return errors


def render_protocol_markdown(value: Mapping[str, Any] | None = None) -> str:
    protocol = dict(value) if value is not None else protocol_values()
    errors = validate_protocol(protocol)
    partitions = protocol["partitions"]
    lines = [
        "# Decision Radar empirical-validation protocol v1",
        "",
        f"- Protocol: `{protocol['protocol_version']}`",
        f"- Frozen at: `{protocol['frozen_at']}` before final-test evaluation",
        f"- SHA-256: `{protocol_sha256(protocol)}`",
        f"- Validation: `{'valid' if not errors else 'invalid'}`",
        "- Research-only; recommendations never auto-apply to production.",
        "",
        "## Chronological partitions",
        "",
        "| Partition | Idea start | Idea end | Outcome end | May select policy? |",
        "|---|---|---|---|---|",
    ]
    for row in partitions:
        lines.append(
            f"| {row['name']} | `{row['start_inclusive']}` | `{row['end_exclusive']}` | "
            f"`{row['outcome_end_exclusive']}` | "
            f"`{str(row['policy_selection_allowed']).lower()}` |"
        )
    lines.extend([
        "",
        "Fourteen-day outcome-only embargoes separate idea partitions. They permit already-observed ideas to mature through the frozen sensitivity horizon without allowing new ideas into the next partition. The clean final-test idea window begins `2025-01-15T00:00:00Z`; earlier nominal holdout-tail dates are quarantined and are not final-test evidence.",
        "",
        "Final-test outcomes may reject a frozen recommendation, but they may not select or tune one. Every final verdict uses the sealed `noninferior_return_failure_selected_day_burden_v1` rule and requires at least 30 matured visible episodes. Its burden check uses the same complete set of selected UTC observation days for production and every shadow scenario, including days with zero ideas; active-idea-day rates remain descriptive only.",
        "",
        "## Point-in-time replay",
        "",
        "Daily observations are formed at the completed Binance candle close. Universe membership is the trailing 30-day quote-volume rank calculated with data available at that close. Rolling features use current and earlier bars only. The volume z-score uses a frozen 90-day lookback and requires 20 prior observations. Available daily RSI is retained only as read-only historical-OHLCV, point-in-time observational context; it cannot adjust scores, policy, or thesis origin. The locally cached candidate pool retains a documented delisting-survivorship limitation.",
        "",
        "Intraday returns, historical spread/order-book quality, market cap, derivatives, calendar, catalyst, and on-chain context remain explicitly unavailable or missing unless an exact time-valid source is supplied. They are never invented or silently proxied.",
        "",
        "## Outcomes and episodes",
        "",
        "The frozen primary horizon is 3 days; 1, 7, and 14 days are sensitivity horizons. Outcome bars begin after the idea bar. A horizon is readable only when its due time is strictly before the partition's frozen outcome boundary. Return, BTC/ETH-relative return, MFE, MAE, time-to-extremes, invalidation, continuation/reversal, expiry, and post-expiry behavior are measured. Fixed-start 24-hour episodes use an inclusive window end: an observation exactly 24 hours after the representative remains a dependent repeat. The first eligible representative stays frozen and dependent route/score/context progression is retained without inflating sample size; 12-hour and 48-hour grouping counts are reported as sensitivity only.",
        "",
        "## Controls, costs, and uncertainty",
        "",
        "Matched non-signal controls use date, regime, and liquidity and are selected by an outcome-blind deterministic hash. Simple raw-mover, volume, RSI, relative-strength, BTC/ETH, and late-fade benchmarks remain descriptive. Historical spread is unavailable; fee, spread, slippage, adverse-selection, 0/20/50/100/200 bps round-trip, delay, capacity, daily/simultaneous-budget, stop, and holding-period scenarios are labeled assumptions. Trailing-stop results remain unavailable when daily bars cannot establish intraday high/low order. Episode bootstrap intervals are exploratory, and cohort tables carry multiple-comparison warnings.",
        "",
        "## Evidence and approval boundaries",
        "",
        "Samples below the frozen minima are reported as `insufficient_sample`, not as positive or negative evidence. Development and validation may nominate a frozen shadow recommendation; final test only confirms or rejects it. Any production change requires a separate versioned human decision and rollback plan.",
        "",
        "## Safety",
        "",
        "Protocol inspection and replay make zero provider calls and cannot mutate authorization, dashboard authority, production policy, notifications, trades, orders, paper trades, RSI rows, or `TRIGGERED_FADE`.",
        "",
    ])
    return "\n".join(lines)


def check_tracked_protocol_files(root: Path) -> list[str]:
    errors: list[str] = []
    json_path = root / "research" / "DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.json"
    md_path = root / "research" / "DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.md"
    try:
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("tracked_protocol_json_unreadable")
    else:
        errors.extend(validate_protocol(loaded))
    try:
        observed_md = md_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("tracked_protocol_markdown_unreadable")
    else:
        if observed_md != render_protocol_markdown():
            errors.append("tracked_protocol_markdown_drift")
    return list(dict.fromkeys(errors))


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the frozen Decision Radar empirical protocol.")
    parser.add_argument("--json", action="store_true", help="Print the canonical JSON protocol.")
    parser.add_argument("--check", action="store_true", help="Validate the protocol and tracked protocol files.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    errors = validate_protocol(protocol_values())
    if args.check:
        errors.extend(check_tracked_protocol_files(Path(args.project_root).resolve()))
    if args.json:
        print(json.dumps(protocol_values(), indent=2, sort_keys=True))
    else:
        print(render_protocol_markdown(), end="")
    if errors:
        print("protocol_errors=" + ",".join(dict.fromkeys(errors)))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DETERMINISTIC_SEED",
    "FROZEN_AT",
    "PROTOCOL_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "canonical_protocol_bytes",
    "check_tracked_protocol_files",
    "protocol_sha256",
    "protocol_values",
    "render_protocol_markdown",
    "selected_observation_days_sha256",
    "validate_protocol",
]
