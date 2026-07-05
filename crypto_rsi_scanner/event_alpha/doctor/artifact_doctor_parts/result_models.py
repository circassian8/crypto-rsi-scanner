"""Result Models for the artifact doctor."""

from __future__ import annotations

from .runtime import *

@dataclass(frozen=True)
class _DoctorResultIdentityFields:
    status: str
    profile: str | None
    artifact_namespace: str | None
    run_rows: int
    alert_rows: int
    feedback_rows: int
    outcome_rows: int
    card_files: int
    research_card_files: int = 0
    research_card_index_present: bool = False
    cards_missing_lineage: int = 0
    cards_missing_feedback_target: int = 0


@dataclass(frozen=True)
class _DoctorResultCoreCoverageFields:
    visible_core_opportunities: int = 0
    core_opportunity_store_rows: int = 0
    visible_core_opportunities_missing_store_rows: int = 0
    duplicate_core_opportunity_store_rows: int = 0
    core_opportunity_store_rows_missing_card_path: int = 0
    visible_core_opportunities_missing_cards: int = 0
    visible_core_opportunities_missing_feedback_targets: int = 0
    alert_snapshots_missing_core_opportunity_id: int = 0
    alert_snapshots_missing_feedback_target: int = 0
    core_cards_missing_store_row: int = 0
    visible_core_cards_missing_store_row: int = 0
    orphan_core_opportunity_cards: int = 0
    diagnostic_snapshots_with_fake_core_id: int = 0
    alert_snapshots_core_id_missing_from_store: int = 0
    evidence_acquisition_core_id_missing_from_store: int = 0
    card_primary_fields_mismatch_core_store: int = 0
    card_evidence_acquisition_count_mismatch: int = 0
    evidence_acquisition_stale_validated_digest: int = 0
    card_source_pack_mismatch_core_acquisition: int = 0
    card_primary_section_contains_support_row_blockers: int = 0
    card_upgrade_text_inconsistent_with_final_level: int = 0
    audit_primary_impact_path_mismatch_core: int = 0
    audit_source_pack_mismatch_core: int = 0
    card_market_confirmation_missing_but_core_has_market_confirmation: int = 0
    card_latest_source_unknown_but_accepted_evidence_exists: int = 0
    quality_review_promoted_core_in_weak_section: int = 0
    market_freshness_contradictory_summary: int = 0
    quality_review_market_freshness_contradiction: int = 0
    upgrade_candidates_include_high_priority: int = 0
    daily_brief_card_group_mismatch_with_index: int = 0
    daily_brief_missing_selected_run: int = 0
    daily_brief_selected_run_mismatch: int = 0
    daily_brief_core_count_mismatch_store: int = 0
    daily_brief_research_review_lane_missing: int = 0
    daily_brief_source_coverage_path_missing: int = 0
    daily_brief_coinalyze_source_coverage_mismatch: int = 0
    core_route_conflicts_with_opportunity_level: int = 0
    live_validated_without_confirmation: int = 0
    live_sector_digest_without_asset: int = 0
    live_rejected_results_promoted: int = 0
    live_skipped_budget_promoted: int = 0
    raw_core_validated_without_confirmation: int = 0
    raw_core_source_only_narrative_validated: int = 0
    raw_core_cryptopanic_tag_only_direct_path_confirmed: int = 0
    raw_core_suppressed_duplicate_validated_stale: int = 0
    confirmed_long_without_source_market: int = 0
    fade_short_without_crowding_exhaustion: int = 0
    early_long_without_fresh_strong_source: int = 0
    risk_only_missing_evidence_only: int = 0
    cryptopanic_only_narrative_confirmed_lane: int = 0
    diagnostic_visible_default_operator_lane: int = 0
    core_missing_market_state_snapshot: int = 0
    market_state_return_unit_missing: int = 0
    market_state_possible_double_scaled: int = 0
    market_state_lane_possible_double_scaled: int = 0


@dataclass(frozen=True)
class _DoctorResultStructuredArtifactFields:
    market_anomaly_rows: int = 0
    market_anomaly_missing_market_state_snapshot: int = 0
    market_anomaly_missing_market_state_class: int = 0
    market_anomaly_confirmed_breakout_missing_evidence: int = 0
    market_anomaly_suspicious_illiquid_promoted_confirmed: int = 0
    market_anomaly_created_alert_rows: int = 0
    market_anomaly_missing_freshness_status: int = 0
    market_anomaly_needs_search_without_plan: int = 0
    official_exchange_candidate_rows: int = 0
    official_exchange_candidate_missing_source_fields: int = 0
    official_exchange_listing_without_official_source: int = 0
    official_exchange_secret_leak: int = 0
    official_exchange_delisting_long_research: int = 0
    official_exchange_quote_asset_misclassified: int = 0
    official_exchange_major_pair_noise_promoted_early_long: int = 0
    official_exchange_created_alert_rows: int = 0
    official_exchange_activation_missing_shared_schema: int = 0
    official_exchange_activation_live_without_ledger: int = 0
    official_exchange_activation_signed_listener_secret_leak: int = 0
    official_exchange_activation_forbidden_side_effect_claim: int = 0
    instrument_resolution_missing_canonical_id_when_fixture_has_it: int = 0
    instrument_resolution_quote_asset_misclassified: int = 0
    instrument_resolution_sector_visible_as_tradable: int = 0
    instrument_resolution_coinalyze_symbol_unlinked: int = 0
    scheduled_catalyst_rows: int = 0
    unlock_candidate_rows: int = 0
    derivatives_state_rows: int = 0
    fade_review_candidate_rows: int = 0
    dex_pool_state_rows: int = 0
    dex_pool_anomaly_rows: int = 0
    protocol_fundamental_rows: int = 0
    unlock_without_structured_evidence: int = 0
    unlock_missing_event_time: int = 0
    unlock_promoted_without_size_metrics: int = 0
    media_unlock_promoted_structured: int = 0
    stale_completed_catalyst_upcoming: int = 0
    calendar_event_missing_source_url: int = 0
    cryptopanic_unlock_proof: int = 0
    scheduled_catalyst_created_alert_rows: int = 0
    fade_review_without_completed_move: int = 0
    fade_review_without_crowding_exhaustion: int = 0
    fade_review_created_triggered_fade: int = 0
    fade_review_created_normal_rsi_signal: int = 0
    fade_review_notification_missing_disclaimer: int = 0
    derivatives_artifact_secret_leak: int = 0
    derivatives_state_missing_freshness_status: int = 0
    derivatives_metric_claim_implemented_missing: int = 0
    derivatives_unit_metadata_missing: int = 0
    stale_derivatives_snapshot_promoted_fade_review: int = 0
    confirmed_long_crowded_without_warning: int = 0


@dataclass(frozen=True)
class _DoctorResultIntegratedRadarFields:
    integrated_radar_candidate_rows: int = 0
    integrated_candidate_missing_opportunity_type: int = 0
    integrated_candidate_missing_market_state_snapshot: int = 0
    integrated_confirmed_long_without_source_market: int = 0
    integrated_early_long_without_fresh_strong_source: int = 0
    integrated_fade_without_crowding_exhaustion: int = 0
    integrated_risk_without_evidence: int = 0
    integrated_market_anomaly_confirmed: int = 0
    integrated_cryptopanic_confirmed: int = 0
    integrated_major_pair_early_long: int = 0
    integrated_input_manifest_missing: int = 0
    integrated_source_coverage_json_missing: int = 0
    integrated_candidate_core_missing: int = 0
    integrated_candidate_core_opportunity_type_mismatch: int = 0
    integrated_candidate_core_market_state_mismatch: int = 0
    integrated_candidate_core_route_level_mismatch: int = 0
    integrated_candidate_core_reason_code_loss: int = 0
    integrated_candidate_core_source_url_loss: int = 0
    integrated_candidate_core_official_event_loss: int = 0
    integrated_candidate_core_scheduled_event_loss: int = 0
    integrated_candidate_core_unlock_event_loss: int = 0
    integrated_candidate_core_derivatives_loss: int = 0
    integrated_candidate_card_opportunity_type_mismatch: int = 0
    integrated_candidate_card_why_now_mismatch: int = 0
    integrated_major_pair_card_early_long: int = 0
    integrated_card_generic_lane_override: int = 0
    card_opportunity_lane_core_mismatch: int = 0
    integrated_candidate_card_official_event_missing: int = 0
    integrated_candidate_card_source_url_missing: int = 0
    integrated_candidate_core_crowding_metadata_loss: int = 0
    derivatives_card_metric_claim_without_data: int = 0
    integrated_coinalyze_crowding_card_missing: int = 0
    integrated_coinalyze_loaded_no_rows_attached: int = 0
    integrated_coinalyze_missing_skip_reason: int = 0
    integrated_coinalyze_stale_loaded_without_warning: int = 0
    integrated_coinalyze_loaded_from_stale_namespace: int = 0
    integrated_fade_card_crowding_unknown: int = 0
    integrated_fade_card_missing_disclaimer: int = 0
    integrated_confirmed_long_crowding_warning_hidden: int = 0
    integrated_dex_low_liquidity_promoted_confirmed: int = 0
    integrated_market_confirmation_display_contradiction: int = 0
    integrated_derivatives_display_contradiction: int = 0
    integrated_manifest_mixed_timestamp_pair: int = 0
    integrated_core_silent_upgrade: int = 0
    integrated_diagnostic_visible_in_default_operator_section: int = 0
    integrated_preview_missing_disclaimer: int = 0
    integrated_delivery_ledger_missing: int = 0
    integrated_preview_lane_mismatch: int = 0
    integrated_delivery_missing_disclaimer: int = 0
    integrated_delivery_sent_in_no_send: int = 0
    integrated_delivery_side_effect_flag: int = 0
    integrated_delivery_missing_skip_reasons: int = 0
    integrated_delivery_card_path_absolute: int = 0
    integrated_delivery_card_path_not_rendered: int = 0
    integrated_operator_markdown_absolute_path: int = 0
    operator_structured_path_absolute: int = 0
    integrated_api_preview_alerts_wording: int = 0
    integrated_manifest_daily_brief_unavailable: int = 0


@dataclass(frozen=True)
class _DoctorResultIntegratedOutcomeFields:
    integrated_outcome_missing_for_candidate: int = 0
    integrated_outcome_side_effect_flag: int = 0
    integrated_outcome_schema_missing: int = 0
    integrated_outcome_missing_identity: int = 0
    integrated_outcome_returns_without_price: int = 0
    integrated_outcome_diagnostic_in_performance: int = 0
    integrated_calibration_diagnostic_in_main_priors: int = 0
    integrated_calibration_prior_safety_missing: int = 0
    integrated_calibration_api_alias_top_level: int = 0
    integrated_outcome_return_double_scaled: int = 0
    integrated_outcome_missing_data_unlabeled: int = 0
    integrated_outcome_thesis_move_missing: int = 0
    integrated_outcome_card_thesis_interpretation_missing: int = 0
    integrated_outcome_card_trade_wording: int = 0
    integrated_performance_diagnostic_in_main_aggregate: int = 0
    integrated_performance_auto_apply_enabled: int = 0
    integrated_performance_low_sample_missing_warning: int = 0
    integrated_performance_trade_pnl_wording: int = 0
    integrated_created_normal_rsi_signal: int = 0
    integrated_created_triggered_fade: int = 0


@dataclass(frozen=True)
class _DoctorResultProviderReadinessFields:
    source_coverage_report_missing: int = 0
    source_coverage_provider_status_unknown: int = 0
    source_coverage_provider_marked_healthy_without_observation: int = 0
    source_coverage_category_priority_missing: int = 0
    source_coverage_readiness_link_missing: int = 0
    source_coverage_context_provider_ranked_above_lane_critical: int = 0
    source_coverage_coinalyze_missing_linked_artifact: int = 0
    source_coverage_bybit_announcements_missing_linked_artifact: int = 0
    source_coverage_unlock_calendar_missing_linked_artifact: int = 0
    source_coverage_dex_onchain_missing_linked_artifact: int = 0
    live_provider_readiness_missing: int = 0
    live_provider_readiness_secret_leak: int = 0
    live_provider_readiness_live_calls_allowed_in_smoke: int = 0
    live_provider_readiness_configured_missing_env: int = 0
    coinalyze_preflight_secret_leak: int = 0
    coinalyze_preflight_live_call_allowed_in_smoke: int = 0
    coinalyze_preflight_configured_missing_env: int = 0
    coinalyze_preflight_ready_without_request_ledger: int = 0
    coinalyze_preflight_missing_fixture_parser_status: int = 0
    coinalyze_preflight_forbidden_side_effect_claim: int = 0
    coinalyze_rehearsal_secret_leak: int = 0
    coinalyze_rehearsal_live_without_ledger: int = 0
    coinalyze_rehearsal_live_call_allowed_in_smoke: int = 0
    coinalyze_rehearsal_live_without_explicit_allow: int = 0
    coinalyze_rehearsal_request_budget_exceeded: int = 0
    coinalyze_rehearsal_success_without_derivatives_state: int = 0
    coinalyze_rehearsal_success_without_crowding_candidates: int = 0
    coinalyze_provider_health_healthy_without_successful_ledger: int = 0
    coinalyze_rehearsal_forbidden_side_effect_claim: int = 0
    coinalyze_supported_metric_implemented_missing_state: int = 0


@dataclass(frozen=True)
class _DoctorResultProviderEvidenceFields:
    bybit_announcements_preflight_secret_leak: int = 0
    bybit_announcements_preflight_live_call_allowed_in_smoke: int = 0
    bybit_announcements_preflight_missing_fixture_parser_status: int = 0
    bybit_announcements_rehearsal_secret_leak: int = 0
    bybit_announcements_rehearsal_live_without_ledger: int = 0
    bybit_announcements_rehearsal_live_without_explicit_allow: int = 0
    bybit_announcements_rehearsal_unsupported_params: int = 0
    bybit_announcements_rehearsal_forbidden_side_effect_claim: int = 0
    unlock_calendar_preflight_secret_leak: int = 0
    unlock_calendar_preflight_live_without_ledger: int = 0
    unlock_calendar_preflight_live_call_allowed_in_smoke: int = 0
    unlock_calendar_preflight_missing_fixture_parser_status: int = 0
    unlock_calendar_preflight_forbidden_side_effect_claim: int = 0
    dex_onchain_readiness_secret_leak: int = 0
    dex_onchain_live_without_ledger: int = 0
    dex_onchain_live_call_allowed_in_smoke: int = 0
    dex_onchain_missing_fixture_parser_status: int = 0
    dex_onchain_forbidden_side_effect_claim: int = 0
    dex_low_liquidity_promoted_confirmed: int = 0
    protocol_metric_missing_source_time: int = 0
    source_pack_provider_status_missing: int = 0
    missing_provider_recommendations_missing: int = 0
    degraded_provider_absence_marked_meaningful: int = 0
    cryptopanic_configured_but_not_observed: int = 0
    cryptopanic_used_but_no_source_coverage_entry: int = 0
    cryptopanic_accepted_evidence_missing_from_card: int = 0
    cryptopanic_rejected_only_promoted: int = 0
    cryptopanic_token_printed_or_unredacted: int = 0
    cryptopanic_growth_unsupported_param_used: int = 0
    cryptopanic_duplicate_request_key: int = 0
    cryptopanic_invalid_currency_code: int = 0
    cryptopanic_empty_currency_request: int = 0
    cryptopanic_coin_id_sent_as_currency: int = 0
    cryptopanic_all_requests_failed: int = 0
    cryptopanic_json_parse_errors: int = 0
    cryptopanic_configured_but_unusable: int = 0
    cryptopanic_status_code_missing_on_http_failure: int = 0
    cryptopanic_body_excerpt_unredacted_token: int = 0
    cryptopanic_quota_exceeded: int = 0
    cryptopanic_request_ledger_missing_when_used: int = 0
    cryptopanic_success_with_backoff_status: int = 0
    cryptopanic_restore_token_recommendation_when_configured: int = 0
    evidence_count_mismatch: int = 0
    unconfirmed_narrative_daily_digest: int = 0
    single_source_no_market_fan_token_digest: int = 0
    visible_sector_core_without_config: int = 0
    duplicate_proxy_core_rows: int = 0
    runs_with_matching_snapshots: int = 0
    runs_with_missing_snapshots: int = 0
    runs_with_external_snapshot_paths: int = 0
    legacy_rows_skipped: int = 0
    legacy_rows_counted: int = 0


@dataclass(frozen=True)
class _DoctorResultNotificationFields:
    delivery_rows: int = 0
    latest_run_id: str | None = None
    latest_run_delivery_rows: int = 0
    legacy_delivery_rows: int = 0
    stale_delivery_rows: int = 0
    delivery_strict_scope: str = "all_rows"
    deliveries_partial_delivered: int = 0
    deliveries_failed: int = 0
    delivery_status_missing: int = 0
    delivery_status_detail_missing: int = 0
    delivery_mode_missing: int = 0
    delivery_state_inconsistent: int = 0
    delivery_would_send_sent_failed_inconsistent: int = 0
    delivery_identity_mismatch_core_store: int = 0
    delivery_core_id_missing: int = 0
    legacy_pre_core_delivery_identity: int = 0
    stale_delivery_identity_missing_core: int = 0
    delivery_feedback_target_missing: int = 0
    delivery_card_path_missing: int = 0
    delivery_alert_id_not_canonical: int = 0
    multi_item_delivery_missing_arrays: int = 0
    telegram_message_contains_absolute_path: int = 0
    telegram_message_contains_raw_debug_dump: int = 0
    research_review_digest_missing_confirmation_label: int = 0
    research_review_digest_contains_strict_alertable: int = 0
    research_review_digest_contains_hard_gated_candidate: int = 0
    research_review_digest_too_many_items: int = 0
    research_review_digest_missing_feedback_target: int = 0
    research_review_digest_skipped_without_reason: int = 0
    research_review_digest_missing_family_summary: int = 0
    research_review_digest_duplicate_visible_family_summary: int = 0
    research_review_digest_absolute_path: int = 0
    notification_body_card_mismatch_canonical: int = 0
    notification_body_feedback_mismatch_canonical: int = 0
    research_review_body_uses_hypothesis_target_when_core_exists: int = 0
    research_review_digest_enabled_but_lane_missing: int = 0
    research_review_digest_candidates_without_delivery: int = 0
    digest_item_without_live_confirmation: int = 0
    digest_item_rejected_results_only: int = 0
    strategic_broad_asset_digest_without_confirmation: int = 0
    notification_preview_missing: int = 0
    notification_preview_relpath_missing: int = 0
    notification_preview_path_unresolvable: int = 0
    notification_preview_run_summary_mismatch: int = 0
    notification_preview_llm_summary_mismatch: int = 0
    notification_preview_lane_counts_mismatch: int = 0
    notification_preview_core_count_mismatch: int = 0
    notification_preview_alertable_count_mismatch: int = 0
    notification_preview_missing_send_guard_status: int = 0
    notification_preview_send_guard_status_missing: int = 0
    notification_preview_no_send_status_unclear: int = 0
    notification_preview_api_alerts_wording: int = 0


@dataclass(frozen=True)
class _DoctorResultQualityIncidentFields:
    quality_fields_missing_count: int = 0
    hypothesis_rows_missing_opportunity_verdict: int = 0
    watchlist_rows_missing_quality_fields: int = 0
    alert_rows_missing_quality_fields: int = 0
    fresh_hypothesis_rows_missing_top_level_quality: int = 0
    fresh_watchlist_rows_missing_top_level_quality: int = 0
    fresh_alert_rows_missing_top_level_quality: int = 0
    legacy_quality_missing_rows: int = 0
    alertable_route_conflicts_with_opportunity_level: int = 0
    alert_snapshot_route_mismatch_core_store: int = 0
    alert_snapshot_level_mismatch_core_store: int = 0
    alert_snapshot_live_confirmation_stale: int = 0
    alert_snapshot_core_resolution_missing: int = 0
    alert_snapshot_pre_reconciliation_alertable: int = 0
    diagnostic_support_snapshot_alertable: int = 0
    diagnostic_support_snapshot_inherits_core_route: int = 0
    duplicate_alertable_snapshot_for_core: int = 0
    canonical_snapshot_missing_for_visible_core: int = 0
    inbox_core_item_missing_card: int = 0
    inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists: int = 0
    inbox_diagnostic_snapshot_visible_by_default: int = 0
    audit_primary_snapshot_not_canonical_when_canonical_exists: int = 0
    feedback_readiness_counts_diagnostic_as_required: int = 0
    fresh_quality_route_conflict_rows: int = 0
    legacy_quality_conflict_rows: int = 0
    alert_rows_missing_final_route: int = 0
    fresh_alert_rows_missing_final_route: int = 0
    watchlist_state_conflicts_with_quality: int = 0
    universal_watchlist_state_conflicts: int = 0
    non_hypothesis_watchlist_quality_conflicts: int = 0
    hypothesis_watchlist_quality_conflicts: int = 0
    quality_capped_watchlist_rows: int = 0
    active_watchlist_rows_quality_capped: int = 0
    fresh_watchlist_state_conflict_rows: int = 0
    legacy_watchlist_conflicts: int = 0
    hypothesis_rows_missing_incident_id: int = 0
    watchlist_hypothesis_rows_missing_incident_id: int = 0
    alert_hypothesis_rows_missing_incident_id: int = 0
    incident_rows_without_linked_hypotheses: int = 0
    incident_rows_without_linked_watchlist: int = 0
    canonical_unlinked_incidents: int = 0
    active_incident_without_qualified_link: int = 0
    linked_incident_without_qualified_link: int = 0
    weak_unqualified_incident_links: int = 0
    quality_blocked_links_present: int = 0
    quality_blocked_links_promoting_incident: int = 0
    diagnostic_incident_rows: int = 0
    raw_observation_incident_rows: int = 0
    external_context_incident_rows: int = 0
    rejected_incident_rows: int = 0
    incident_relevance_missing: int = 0
    invalid_canonical_incident_rows: int = 0
    garbage_primary_subject_incidents: int = 0
    fresh_incident_linkage_blockers: int = 0
    legacy_incident_linkage_warnings: int = 0


@dataclass(frozen=True)
class _DoctorResultNamespaceSchemaFields:
    namespace_status: str | None = None
    namespace_stale_deprecated: int = 0
    namespace_superseded_by: str | None = None
    strict_api: bool = False
    strict: bool = False
    schema_only: bool = False
    legacy_checks_skipped: bool = False
    schema_rows_validated: int = 0
    schema_validation_errors: int = 0
    missing_required_fields: int = 0
    invalid_enum_fields: int = 0
    invalid_path_fields: int = 0
    invalid_safety_fields: int = 0
    deprecated_field_usage: int = 0
    active_shim_modules_with_implementation_logic: int = 0
    old_path_internal_imports: int = 0
    old_path_test_imports: int = 0
    old_path_docs_references: int = 0
    old_path_import_allowed_exceptions: int = 0
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaArtifactDoctorResult(
    _DoctorResultNamespaceSchemaFields,
    _DoctorResultQualityIncidentFields,
    _DoctorResultNotificationFields,
    _DoctorResultProviderEvidenceFields,
    _DoctorResultProviderReadinessFields,
    _DoctorResultIntegratedOutcomeFields,
    _DoctorResultIntegratedRadarFields,
    _DoctorResultStructuredArtifactFields,
    _DoctorResultCoreCoverageFields,
    _DoctorResultIdentityFields,
):
    """Compatibility aggregate for artifact doctor counters."""

__all__ = (
    'EventAlphaArtifactDoctorResult',
)
