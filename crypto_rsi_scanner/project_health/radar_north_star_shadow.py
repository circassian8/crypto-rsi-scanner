"""Static North Star policy for robust temporal-surprise shadow evidence."""

from __future__ import annotations

from typing import Any, Mapping


SHADOW_TEMPORAL_SURPRISE_POLICY: dict[str, Any] = {
    "schema_id": "event_alpha.shadow_temporal_surprise",
    "schema_version": 3,
    "legacy_schema_versions_readable": [1, 2],
    "features": ["volume_24h", "turnover_24h"],
    "signed_return_features": [
        "return_1h",
        "return_4h",
        "return_24h",
        "relative_return_vs_btc_1h",
        "relative_return_vs_btc_4h",
        "relative_return_vs_btc_24h",
        "relative_return_vs_eth_1h",
        "relative_return_vs_eth_4h",
        "relative_return_vs_eth_24h",
    ],
    "eligible_feature_basis": ["provider_observed", "derived_provider_ratio"],
    "derived_ratio_validation": "volume_div_market_cap_rel_tol_1e-9_abs_tol_1e-12",
    "proxy_or_cross_sectional_basis_eligible": False,
    "baseline": "same_asset_strictly_earlier_cadence_counted_observations",
    "history_binding": "exact_generation_artifact_basename_and_sha256",
    "history_fingerprint_verified_before_parse": True,
    "history_fingerprint_persisted_in_shadow": True,
    "namespace_binding": "exact_scan_device_inode_and_unchanged_bundle_hashes",
    "current_observation_in_own_baseline": False,
    "positive_finite_values_only": True,
    "transform": "natural_log",
    "location": "median_of_log_baseline",
    "scale": "median_absolute_deviation_times_1.482602218505602",
    "degenerate_mad_policy": "mad_le_1e-12_returns_null_without_epsilon_or_std_fallback",
    "descriptive_upper_tail": "(count_baseline_log_ge_current_log+1)/(n+1)",
    "descriptive_tail_is_p_value": False,
    "baseline_value_identity": (
        "feature_evaluation_values_rounded_to_12_decimal_places"
    ),
    "baseline_variation_diagnostics": [
        "distinct_baseline_value_count",
        "maximum_baseline_value_tie_count",
        "current_value_baseline_tie_count",
        "distinct_baseline_value_ratio",
        "nominal_one_sided_tail_rank_floor",
        "nominal_two_sided_tail_rank_floor_for_returns",
    ],
    "minimum_distinct_baseline_value_count": None,
    "variation_diagnostics_are_policy": False,
    "signed_return_unit": "percent_points",
    "signed_return_transform": "identity_preserves_sign",
    "signed_return_feature_basis": "provider_observed_price_ratio_only",
    "relative_return_feature_basis": (
        "provider_observed_asset_return_minus_provider_observed_benchmark_return"
    ),
    "return_horizons_hours": [1, 4, 24],
    "return_families_kept_separate": True,
    "return_anchor": "latest_at_or_before_exact_horizon_target",
    "return_anchor_tolerance": "max_300_seconds_or_25_percent_of_horizon",
    "benchmark_identities": ["btc:bitcoin_or_btc", "eth:ethereum_or_eth"],
    "benchmark_endpoint_alignment": "at_or_before_asset_within_300_seconds",
    "descriptive_lower_return_tail": (
        "(count_baseline_return_le_current_return+1)/(n+1)"
    ),
    "descriptive_upper_return_tail": (
        "(count_baseline_return_ge_current_return+1)/(n+1)"
    ),
    "descriptive_two_sided_return_tail": (
        "min(1,2*min(lower_tail_rank,upper_tail_rank))"
    ),
    "return_tail_ranks_are_p_values": False,
    "overlapping_return_samples_are_independent": False,
    "same_asset_relative_return_status": "not_applicable",
    "attachment": "top_level_post_scan_snapshot_and_anomaly_metadata_only",
    "campaign_audit_schema_id": (
        "decision_radar.shadow_temporal_surprise_campaign_audit"
    ),
    "campaign_audit_schema_version": 2,
    "campaign_audit_input": "one_read_exact_campaign_history_snapshot",
    "campaign_audit_replay": (
        "each_counted_row_against_strictly_earlier_same_asset_rows_and_"
        "at_or_before_benchmarks"
    ),
    "campaign_audit_non_counted_rows": "excluded_with_exact_count",
    "campaign_audit_invalid_or_duplicate_rows": "rejected_with_closed_reason_counts",
    "campaign_audit_source_bound_digest": (
        "changes_when_exact_history_snapshot_fingerprint_changes"
    ),
    "campaign_audit_causal_digest": (
        "prior_projection_values_stable_when_only_later_rows_are_appended"
    ),
    "campaign_audit_ready_semantics": (
        "every_modeled_feature_has_some_ready_evidence_not_every_projection_ready"
    ),
    "campaign_audit_ready_distribution": (
        "per_feature_robust_z_and_descriptive_tail_quantiles_over_ready_projections"
    ),
    "campaign_audit_quantile_method": (
        "linear_interpolation_sorted_ready_values"
    ),
    "campaign_audit_tail_ranks_are_p_values": False,
    "campaign_audit_overlapping_samples_are_independent": False,
    "campaign_audit_historical_rows_rewritten": False,
    "campaign_audit_provider_calls": 0,
    "campaign_audit_writes": 0,
    "campaign_audit_statistical_independence_claimed": False,
    "campaign_audit_protocol_v2_evidence_eligible": False,
    "canonical_history_or_provider_source_mutated": False,
    "copied_to_decision_projection": False,
    "routing_eligible": False,
    "priority_eligible": False,
    "decision_score_eligible": False,
    "score_adjustment_eligible": False,
    "auto_apply": False,
    "research_only": True,
    "method_references": [
        "https://doi.org/10.1111/j.2517-6161.1964.tb00553.x",
        "https://doi.org/10.1080/01621459.1993.10476408",
        "https://doi.org/10.1086/341527",
    ],
}

SHADOW_ANOMALY_EPISODE_POLICY: dict[str, Any] = {
    "schema_id": "event_alpha.shadow_anomaly_episodes",
    "schema_version": 1,
    "input_audit_schema_id": "event_alpha.shadow_anomaly_episode_input_audit",
    "input_audit_schema_version": 1,
    "source_population": "validated_campaign_counted_market_anomaly_candidates",
    "candidate_snapshot": "one_read_verified_manifest_digest_reused_across_report",
    "outcome_ledger_snapshot": "one_read_exact_bytes_reused_across_report",
    "outcome_ledger_statuses": ["missing", "observed_empty", "observed", "unavailable"],
    "input_statuses": ["empty", "ready", "partial", "unavailable"],
    "canonical_asset_identity_required": True,
    "symbol_fallback_allowed": False,
    "method": "fixed_start_window_declustering",
    "primary_window_hours": 24,
    "sensitivity_window_hours": [12, 24, 48],
    "boundary": "member_observed_at_lt_episode_start_plus_window",
    "repeat_extends_window": False,
    "representative": "chronologically_first_exact_identity_outcome_join_independent",
    "later_matured_member_may_replace_representative": False,
    "outcome_multiplicity": "inspect_raw_rows_before_lossy_campaign_deduplication",
    "outcome_claim_collisions": "distinct_connected_components_not_duplicate_rows",
    "input_audit_validation": "closed_keys_counts_closures_bindings_safety_and_digest",
    "membership_binding": "exact_namespace_run_candidate_outcome_anomaly_asset_time",
    "member_reference_limit": 256,
    "exclusion_reference_limit": 256,
    "references_complete_within_bound": True,
    "bound_exceeded_policy": "fail_closed_without_contract",
    "routing_eligible": False,
    "priority_eligible": False,
    "decision_score_eligible": False,
    "score_adjustment_eligible": False,
    "calibration_eligible": False,
    "threshold_change_eligible": False,
    "statistical_independence_claim": False,
    "cross_asset_independence_claim": False,
    "auto_apply": False,
    "research_only": True,
    "method_references": [
        "https://doi.org/10.1111/1467-9868.00401",
        "https://doi.org/10.1214/09-AOAS292",
        "https://doi.org/10.1086/260910",
        "https://doi.org/10.1080/01621459.1994.10476870",
    ],
}

PROTOCOL_V2_EPISODE_COVERAGE_FRONTIER_POLICY: dict[str, Any] = {
    "schema_id": "decision_radar.protocol_v2_episode_coverage_frontier",
    "schema_version": 1,
    "source_scorecard_schema_id": (
        "event_alpha.decision_v2_episode_outcome_scorecard"
    ),
    "source_scorecard_schema_version": 1,
    "canonical_routes": [
        "dashboard_watch",
        "actionable_watch",
        "high_confidence_watch",
        "rapid_market_anomaly",
        "fade_exhaustion_review",
        "risk_watch",
        "calendar_risk",
        "diagnostic",
    ],
    "canonical_primary_origins": [
        "market_led",
        "catalyst_led",
        "technical_led",
        "derivatives_led",
        "onchain_led",
        "fundamental_led",
        "macro_led",
    ],
    "zero_episode_categories_explicit": True,
    "source_binding": (
        "exact_scorecard_contract_input_binding_and_evaluated_at"
    ),
    "downstream_behavior": "copy_validated_projection_without_re_evaluation",
    "empirical_live_projection_schema_version": 5,
    "empirical_live_projection_prior_versions_readable": [1, 2, 3, 4],
    "research_lab_behavior": (
        "render_sealed_live_snapshot_separately_from_historical_replay"
    ),
    "sealed_protocol_v1_bundle_rewritten": False,
    "minimum_sample_policy_sealed": False,
    "sample_sufficiency_evaluable": False,
    "episode_independence": (
        "fixed_start_declustered_not_statistically_independent"
    ),
    "statistical_independence_claim": False,
    "cross_asset_independence_claim": False,
    "matched_control_available": False,
    "protocol_v2_annex_bound": False,
    "protocol_v2_evidence_eligible": False,
    "routing_eligible": False,
    "decision_score_eligible": False,
    "threshold_change_eligible": False,
    "provider_calls": 0,
    "writes": 0,
    "research_only": True,
}


def append_shadow_policies_north_star(
    lines: list[str],
    payload: Mapping[str, Any],
) -> None:
    policy = (
        payload.get("shadow_temporal_surprise_policy")
        if isinstance(payload.get("shadow_temporal_surprise_policy"), Mapping)
        else {}
    )
    lines.extend(["## Shadow Robust Temporal Surprise", ""])
    for key, value in policy.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    episode_policy = (
        payload.get("shadow_anomaly_episode_policy")
        if isinstance(payload.get("shadow_anomaly_episode_policy"), Mapping)
        else {}
    )
    lines.extend(["## Shadow Anomaly Episodes", ""])
    for key, value in episode_policy.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    frontier_policy = (
        payload.get("protocol_v2_episode_coverage_frontier_policy")
        if isinstance(
            payload.get("protocol_v2_episode_coverage_frontier_policy"),
            Mapping,
        )
        else {}
    )
    lines.extend(["## Protocol-v2 Episode Coverage Frontier", ""])
    for key, value in frontier_policy.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")


__all__ = (
    "PROTOCOL_V2_EPISODE_COVERAGE_FRONTIER_POLICY",
    "SHADOW_ANOMALY_EPISODE_POLICY",
    "SHADOW_TEMPORAL_SURPRISE_POLICY",
    "append_shadow_policies_north_star",
)
