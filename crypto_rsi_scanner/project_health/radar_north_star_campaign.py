"""Decision Radar campaign policy data for the North Star writer."""

from __future__ import annotations

from typing import Any

MARKET_NO_SEND_GENERATION: dict[str, Any] = {
    "targets": [
        "radar-market-no-send-readiness",
        "radar-daily-ops-cycle",
        "radar-market-no-send",
        "radar-market-no-send-smoke",
        "radar-market-campaign-report",
    ],
    "operator_cycle_target": "radar-daily-ops-cycle",
    "compatibility_alias": {
        "radar-market-no-send": "radar-daily-ops-cycle",
    },
    "publication_owner": "decision_radar_daily_operations_v1_1",
    "direct_low_level_publication": "disabled",
    "default_namespace": "radar_market_no_send",
    "provider": "coingecko",
    "run_mode": "operational",
    "measurement_program": {
        "name": "decision_radar_live_observation_campaign_v2",
        "event_alpha_catalyst_burn_in": "separate_not_aggregated",
        "campaign_report_target": "radar-market-campaign-report",
        "campaign_report_schema": "decision_radar_live_observation_campaign_report_v2",
        "campaign_report_provider_calls": 0,
        "historical_market_provenance_adapter": "read_only_no_rewrite",
    },
    "authorization": {
        "existing_explicit_environment_flag": "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1",
        "inferred_from_cache": False,
        "created_or_modified_by_application": False,
        "absent_behavior": "safe blocked result, no provider call, bounded local no-send attempt/audit/campaign-report evidence, pointer unchanged",
        "eligible_invocation_live_request_max": 1,
    },
    "provenance_contract": {
        "schema_version": "crypto_radar_market_provenance_v2",
        "contract_version": 2,
        "data_acquisition_modes": [
            "live_provider", "mocked_fixture", "artifact_replay", "preflight_only",
            "cache_replay",
        ],
        "candidate_source_modes": [
            "live_no_send",
            "mocked_fixture",
            "artifact_replay",
            "preflight_only",
        ],
        "decision_radar_campaign_counting_is_derived": True,
        "event_alpha_catalyst_burn_in_counted": False,
        "decision_market_rows_counted_in_event_alpha_catalyst_burn_in": False,
        "legacy_burn_in_fields": "read_only_compatibility_false_for_new_campaign_rows",
        "mock_or_fixture_may_validate_mechanics": True,
        "mock_or_fixture_decision_campaign_counted": False,
        "historical_flat_rows_silently_reclassified": False,
    },
    "provenance_fields": [
        "data_acquisition_mode",
        "candidate_source_mode",
        "provider",
        "provider_call_attempted",
        "provider_call_succeeded",
        "live_provider_authorized",
        "request_ledger_path",
        "request_ledger_sha256",
        "provider_source_artifact",
        "provider_source_artifact_sha256",
        "provider_generation_id",
        "cache_status",
        "provenance_contract_valid",
        "measurement_program",
        "decision_radar_campaign_eligible",
        "decision_radar_campaign_counted",
        "decision_radar_campaign_reason",
        "burn_in_eligible",
        "burn_in_counted",
        "burn_in_reason",
        "feature_basis",
        "data_quality",
        "validation_errors",
    ],
    "temporal_baseline": {
        "generation_snapshot_artifact": "event_market_history.jsonl", "shared_live_cache": "radar_market_history_cache/event_market_history.jsonl",
        "fixture_and_mock_cache_scope": "generation-local only; never seeds live history", "authoritative_namespace_mutation": "forbidden; use a new generation namespace backed by the bounded shared cache",
        "schema_id": "event_alpha.market_history_observation",
        "schema_version": 1,
        "default_limits": {
            "max_history_age_days": 45,
            "max_observations_per_asset": 256,
            "min_baseline_observations": 8,
            "max_current_age_hours": 6,
            "future_tolerance_minutes": 5,
        },
        "cadence_policy": {
            "configuration": "RSI_DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES",
            "default_minimum_observation_spacing_minutes": 60,
            "too_close_observation_status": "too_close",
            "too_close_observations_retained": True,
            "too_close_observations_count_in_baseline": False,
            "rapid_cycles_advance_warmup": False,
            "next_eligible_observation_at_reported": True,
            "stable_base_root_receipt": "event_decision_radar_campaign_reservation.json",
            "state_directory_replacement_resets_spacing": False,
        },
        "feature_readiness_groups": [
            "volume", "turnover", "volatility", "returns_1h", "returns_4h",
            "returns_24h", "btc_eth_relative",
        ],
        "required_feature_groups_must_all_be_warm": True,
        "warmup_requires_feature_sample_and_horizon_coverage": True,
        "baseline_excludes_current_observation": True,
        "direct_provider_fields_preserved": True,
        "only_explicit_proxy_fields_may_be_replaced": True,
        "derived_evidence": [
            "1h/4h/24h returns in percent points",
            "turnover and volume z-scores",
            "return volatility",
            "BTC and ETH relative returns",
            "observation ids and baseline bounds",
        ],
    },
    "outcome_policy": {
        "pending_placeholder_per_canonical_decision_candidate": True, "candidate_outcome_count_mismatch": "publication blocker",
        "cohort_drift": "blocker",
        "campaign_outcome_ledger": "radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl",
        "refresh_uses_local_artifacts_only": True,
        "refresh_provider_calls": 0,
        "automatic_threshold_or_route_changes": False,
    },
    "pilot_audit_artifacts": [
        "event_market_no_send_latest_attempt.json", "event_market_no_send_pilot_audit.json",
        "event_market_no_send_pilot_audit.md",
    ],
    "exact_attempt_policy": {
        "doctor_and_publish_require_latest_cli_receipt_manifest_match": True, "blocked_attempt_may_reuse_older_complete_manifest": False,
        "provider_health_artifact": "event_provider_health.json", "provider_errors_persisted_as_safe_classes_only": True,
        "bounded_attempt_ledger": "event_market_no_send_attempts.jsonl",
        "stable_provider_call_reservation": "event_decision_radar_campaign_reservation.json",
        "provider_call_reserved_before_network_boundary": True,
    },
    "request_telemetry": {
        "allowed_fields": [
            "endpoint_path", "request_started_at", "request_ended_at",
            "duration_ms", "http_status", "result_count", "retry_count",
            "error_class", "cache_behavior", "live_provider_authorized",
            "no_send",
        ],
        "forbidden_content": [
            "query parameters", "headers", "tokens", "raw response bodies",
            "raw exception text", "recipient identifiers",
        ],
        "provider_health_must_reconcile": True,
    },
    "market_context_lineage": {
        "canonical_fields": [
            "source", "observed_at", "freshness_status", "market_snapshot_id",
        ],
        "copied_to": [
            "candidate", "CoreOpportunity", "card", "preview", "outcome",
            "daily brief", "dashboard",
        ],
        "downstream_re_evaluation": False,
        "lineage_drift": "strict doctor blocker",
    },
    "defaults": {
        "research_only": True, "no_sends": True, "no_trades": True,
        "no_paper_trades": True, "no_normal_rsi_writes": True,
        "no_triggered_fade": True,
    },
    "dashboard_pointer_policy": {
        "fixture_or_mock_generation_eligible": False,
        "pointer_changes_on_blocked_failed_stale_or_untrusted_generation": False,
        "current_authoritative_namespace_is_immutable": True,
        "required_checks": [
            "real live-safe data mode", "complete operator state",
            "valid exact fingerprints", "matching canonical counts",
            "current run revision and operator-state binding",
            "fresh full strict doctor with zero blockers",
        ],
        "stable_authority_digest": {
            "excluded_clock_only_fields": ["updated_at", "doctor.verified_at"],
            "unchanged_doctor_rerun_changes_pointer_identity": False,
            "substantive_doctor_or_artifact_drift": "blocker",
        },
        "monotonic_authority_history": {
            "fields": ["ever_authoritative", "first_authoritative_at"],
            "separate_from_current_pointer_readiness": True,
            "re_audit_erases_historical_authority": False,
        },
    },
}

REVIEW_EXPORT_POLICY: dict[str, Any] = {
    "target": "export-src-with-artifacts",
    "fixed_utc_entry_timestamp": True,
    "default_timestamp": "1980-01-01T00:00:00Z",
    "source_date_epoch": "honored only when wall-clock-safe",
    "source_and_research_input_mtimes_mutated": False,
    "descriptor_anchored_symlink_toctou_checks_preserved": True,
    "configured_secret_scanning_preserved": True,
    "future_mtime_or_make_clock_skew_allowed": False,
}


__all__ = ("MARKET_NO_SEND_GENERATION", "REVIEW_EXPORT_POLICY")
