"""Static North Star policy for robust temporal-surprise shadow evidence."""

from __future__ import annotations

from typing import Any, Mapping


SHADOW_TEMPORAL_SURPRISE_POLICY: dict[str, Any] = {
    "schema_id": "event_alpha.shadow_temporal_surprise",
    "schema_version": 1,
    "features": ["volume_24h", "turnover_24h"],
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
    "attachment": "top_level_post_scan_snapshot_and_anomaly_metadata_only",
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


def append_shadow_temporal_surprise_north_star(
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


__all__ = (
    "SHADOW_TEMPORAL_SURPRISE_POLICY",
    "append_shadow_temporal_surprise_north_star",
)
