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
from typing import Any, Mapping


SCHEMA_ID = "decision_radar.empirical_validation_protocol"
SCHEMA_VERSION = 1
PROTOCOL_VERSION = "decision_radar_empirical_validation_v1"
FROZEN_AT = "2026-07-16T06:00:00Z"
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
            "policy_selection_allowed": True,
        },
        {
            "name": "validation",
            "start_inclusive": "2023-01-01T00:00:00Z",
            "end_exclusive": "2025-01-01T00:00:00Z",
            "policy_selection_allowed": True,
        },
        {
            "name": "final_test",
            "start_inclusive": "2025-01-01T00:00:00Z",
            "end_exclusive": "2026-06-01T00:00:00Z",
            "policy_selection_allowed": False,
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
    },
    "episodes": {
        "method": "fixed_start_window",
        "primary_window_hours": 24,
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
        "scenario_set_frozen_with_protocol": True,
        "recommendation_set_must_be_hashed_before_final_test": True,
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


def validate_protocol(value: Mapping[str, Any]) -> list[str]:
    """Validate the closed rules that protect final-test isolation."""

    errors: list[str] = []
    if dict(value) != _PROTOCOL:
        errors.append("protocol_not_exact_frozen_v1")
    if value.get("status") != "frozen_before_final_test_evaluation":
        errors.append("protocol_not_frozen")
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        errors.append("research_safety_invalid")
    partitions = value.get("partitions")
    if not isinstance(partitions, list) or [row.get("name") for row in partitions if isinstance(row, Mapping)] != [
        "development", "validation", "final_test"
    ]:
        errors.append("partition_order_invalid")
    else:
        prior_end: datetime | None = None
        for row in partitions:
            try:
                start = _utc(row["start_inclusive"])
                end = _utc(row["end_exclusive"])
            except (KeyError, TypeError, ValueError):
                errors.append("partition_time_invalid")
                continue
            if start >= end:
                errors.append("partition_empty")
            if prior_end is not None and start != prior_end:
                errors.append("partition_gap_or_overlap")
            prior_end = end
        if partitions[-1].get("policy_selection_allowed") is not False:
            errors.append("final_test_selection_not_blocked")
    walk = value.get("walk_forward")
    if not isinstance(walk, Mapping) or walk.get("final_test_used_for_tuning") is not False:
        errors.append("final_test_firewall_invalid")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, Mapping) or outcomes.get("primary_horizon_days") != 3:
        errors.append("primary_outcome_drift")
    missed = value.get("missed_opportunity_rule")
    if not isinstance(missed, Mapping) or missed.get("maximum_future_excursion_alone_is_sufficient") is not False:
        errors.append("missed_opportunity_rule_invalid")
    safety = value.get("safety")
    if not isinstance(safety, Mapping) or any(type(item) is not int or item != 0 for item in safety.values()):
        errors.append("safety_counter_invalid")
    return list(dict.fromkeys(errors))


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
        "| Partition | Start inclusive | End exclusive | May select policy? |",
        "|---|---|---|---|",
    ]
    for row in partitions:
        lines.append(
            f"| {row['name']} | `{row['start_inclusive']}` | `{row['end_exclusive']}` | "
            f"`{str(row['policy_selection_allowed']).lower()}` |"
        )
    lines.extend([
        "",
        "Final-test outcomes may reject a frozen recommendation, but they may not select or tune one.",
        "",
        "## Point-in-time replay",
        "",
        "Daily observations are formed at the completed Binance candle close. Universe membership is the trailing 30-day quote-volume rank calculated with data available at that close. Rolling features use current and earlier bars only. The locally cached candidate pool retains a documented delisting-survivorship limitation.",
        "",
        "Intraday returns, historical spread/order-book quality, market cap, derivatives, calendar, catalyst, and on-chain context remain explicitly unavailable or missing unless an exact time-valid source is supplied. They are never invented or silently proxied.",
        "",
        "## Outcomes and episodes",
        "",
        "The frozen primary horizon is 3 days; 1, 7, and 14 days are sensitivity horizons. Outcome bars begin after the idea bar. Return, BTC/ETH-relative return, MFE, MAE, time-to-extremes, invalidation, continuation/reversal, expiry, and post-expiry behavior are measured. Fixed-start 24-hour episodes freeze the first eligible representative and retain dependent route/score/context progression without inflating sample size.",
        "",
        "## Controls, costs, and uncertainty",
        "",
        "Matched non-signal controls use date, regime, and liquidity and are selected by an outcome-blind deterministic hash. Simple raw-mover, volume, RSI, relative-strength, BTC/ETH, and late-fade benchmarks remain descriptive. Historical spread is unavailable; 0/20/50/100/200 bps round-trip costs are labeled assumptions. Episode bootstrap intervals are exploratory, and cohort tables carry multiple-comparison warnings.",
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
    "validate_protocol",
]
