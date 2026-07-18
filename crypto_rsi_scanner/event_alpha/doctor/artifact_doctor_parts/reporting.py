"""Reporting for the artifact doctor."""

from __future__ import annotations

from .runtime import *

_CounterField = tuple[str, str, object]

_CORE_OPPORTUNITY_COVERAGE_FIELDS: tuple[_CounterField, ...] = (
    ('visible_core_opportunities', 'visible_core_opportunities', None),
    ('core_opportunity_store_rows', 'core_opportunity_store_rows', None),
    ('visible_core_opportunities_missing_store_rows', 'visible_core_opportunities_missing_store_rows', None),
    ('duplicate_core_opportunity_store_rows', 'duplicate_core_opportunity_store_rows', None),
    ('core_opportunity_store_rows_missing_card_path', 'core_opportunity_store_rows_missing_card_path', None),
    ('visible_core_opportunities_missing_cards', 'visible_core_opportunities_missing_cards', None),
    ('visible_core_opportunities_missing_feedback_targets', 'visible_core_opportunities_missing_feedback_targets', None),
    ('alert_snapshots_missing_core_opportunity_id', 'alert_snapshots_missing_core_opportunity_id', None),
    ('alert_snapshots_missing_feedback_target', 'alert_snapshots_missing_feedback_target', None),
    ('core_cards_missing_store_row', 'core_cards_missing_store_row', None),
    ('visible_core_cards_missing_store_row', 'visible_core_cards_missing_store_row', None),
    ('orphan_core_opportunity_cards', 'orphan_core_opportunity_cards', None),
    ('diagnostic_snapshots_with_fake_core_id', 'diagnostic_snapshots_with_fake_core_id', None),
    ('alert_snapshots_core_id_missing_from_store', 'alert_snapshots_core_id_missing_from_store', None),
    ('evidence_acquisition_core_id_missing_from_store', 'evidence_acquisition_core_id_missing_from_store', None),
    ('card_primary_fields_mismatch_core_store', 'card_primary_fields_mismatch_core_store', None),
    ('card_evidence_acquisition_count_mismatch', 'card_evidence_acquisition_count_mismatch', None),
    ('evidence_acquisition_stale_validated_digest', 'evidence_acquisition_stale_validated_digest', None),
    ('card_source_pack_mismatch_core_acquisition', 'card_source_pack_mismatch_core_acquisition', None),
    ('card_primary_section_contains_support_row_blockers', 'card_primary_section_contains_support_row_blockers', None),
    ('card_upgrade_text_inconsistent_with_final_level', 'card_upgrade_text_inconsistent_with_final_level', None),
    ('audit_primary_impact_path_mismatch_core', 'audit_primary_impact_path_mismatch_core', None),
    ('audit_source_pack_mismatch_core', 'audit_source_pack_mismatch_core', None),
    ('card_market_confirmation_missing_but_core_has_market_confirmation', 'card_market_confirmation_missing_but_core_has_market_confirmation', None),
    ('card_latest_source_unknown_but_accepted_evidence_exists', 'card_latest_source_unknown_but_accepted_evidence_exists', None),
    ('quality_review_promoted_core_in_weak_section', 'quality_review_promoted_core_in_weak_section', None),
    ('market_freshness_contradictory_summary', 'market_freshness_contradictory_summary', None),
    ('quality_review_market_freshness_contradiction', 'quality_review_market_freshness_contradiction', None),
    ('upgrade_candidates_include_high_priority', 'upgrade_candidates_include_high_priority', None),
    ('daily_brief_card_group_mismatch_with_index', 'daily_brief_card_group_mismatch_with_index', None),
    ('daily_brief_missing_selected_run', 'daily_brief_missing_selected_run', None),
    ('daily_brief_selected_run_mismatch', 'daily_brief_selected_run_mismatch', None),
    ('daily_brief_core_count_mismatch_store', 'daily_brief_core_count_mismatch_store', None),
    ('daily_brief_research_review_lane_missing', 'daily_brief_research_review_lane_missing', None),
    ('daily_brief_source_coverage_path_missing', 'daily_brief_source_coverage_path_missing', None),
    ('daily_brief_coinalyze_source_coverage_mismatch', 'daily_brief_coinalyze_source_coverage_mismatch', None),
    ('core_route_conflicts_with_opportunity_level', 'core_route_conflicts_with_opportunity_level', None),
    ('alert_snapshot_route_mismatch_core_store', 'alert_snapshot_route_mismatch_core_store', None),
    ('alert_snapshot_level_mismatch_core_store', 'alert_snapshot_level_mismatch_core_store', None),
    ('alert_snapshot_live_confirmation_stale', 'alert_snapshot_live_confirmation_stale', None),
    ('alert_snapshot_core_resolution_missing', 'alert_snapshot_core_resolution_missing', None),
    ('alert_snapshot_pre_reconciliation_alertable', 'alert_snapshot_pre_reconciliation_alertable', None),
    ('diagnostic_support_snapshot_alertable', 'diagnostic_support_snapshot_alertable', None),
    ('diagnostic_support_snapshot_inherits_core_route', 'diagnostic_support_snapshot_inherits_core_route', None),
    ('duplicate_alertable_snapshot_for_core', 'duplicate_alertable_snapshot_for_core', None),
    ('canonical_snapshot_missing_for_visible_core', 'canonical_snapshot_missing_for_visible_core', None),
    ('inbox_core_item_missing_card', 'inbox_core_item_missing_card', None),
    ('inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists', 'inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists', None),
    ('inbox_diagnostic_snapshot_visible_by_default', 'inbox_diagnostic_snapshot_visible_by_default', None),
    ('audit_primary_snapshot_not_canonical_when_canonical_exists', 'audit_primary_snapshot_not_canonical_when_canonical_exists', None),
    ('feedback_readiness_counts_diagnostic_as_required', 'feedback_readiness_counts_diagnostic_as_required', None),
    ('live_validated_without_confirmation', 'live_validated_without_confirmation', None),
    ('live_sector_digest_without_asset', 'live_sector_digest_without_asset', None),
    ('live_rejected_results_promoted', 'live_rejected_results_promoted', None),
    ('live_skipped_budget_promoted', 'live_skipped_budget_promoted', None),
    ('raw_core_validated_without_confirmation', 'raw_core_validated_without_confirmation', None),
    ('raw_core_source_only_narrative_validated', 'raw_core_source_only_narrative_validated', None),
    ('raw_core_cryptopanic_tag_only_direct_path_confirmed', 'raw_core_cryptopanic_tag_only_direct_path_confirmed', None),
    ('raw_core_suppressed_duplicate_validated_stale', 'raw_core_suppressed_duplicate_validated_stale', None),
    ('confirmed_long_without_source_market', 'confirmed_long_without_source_market', None),
    ('fade_short_without_crowding_exhaustion', 'fade_short_without_crowding_exhaustion', None),
    ('early_long_without_fresh_strong_source', 'early_long_without_fresh_strong_source', None),
    ('risk_only_missing_evidence_only', 'risk_only_missing_evidence_only', None),
    ('cryptopanic_only_narrative_confirmed_lane', 'cryptopanic_only_narrative_confirmed_lane', None),
    ('diagnostic_visible_default_operator_lane', 'diagnostic_visible_default_operator_lane', None),
    ('core_missing_market_state_snapshot', 'core_missing_market_state_snapshot', None),
    ('market_state_return_unit_missing', 'market_state_return_unit_missing', None),
    ('market_state_possible_double_scaled', 'market_state_possible_double_scaled', None),
    ('market_state_lane_possible_double_scaled', 'market_state_lane_possible_double_scaled', None),
    ('market_anomaly_rows', 'market_anomaly_rows', None),
    ('market_anomaly_missing_market_state_snapshot', 'market_anomaly_missing_market_state_snapshot', None),
    ('market_anomaly_missing_market_state_class', 'market_anomaly_missing_market_state_class', None),
    ('market_anomaly_confirmed_breakout_missing_evidence', 'market_anomaly_confirmed_breakout_missing_evidence', None),
    ('market_anomaly_suspicious_illiquid_promoted_confirmed', 'market_anomaly_suspicious_illiquid_promoted_confirmed', None),
    ('market_anomaly_created_alert_rows', 'market_anomaly_created_alert_rows', None),
    ('market_anomaly_missing_freshness_status', 'market_anomaly_missing_freshness_status', None),
    ('market_anomaly_needs_search_without_plan', 'market_anomaly_needs_search_without_plan', None),
    ('official_exchange_candidate_rows', 'official_exchange_candidate_rows', None),
    ('official_exchange_candidate_missing_source_fields', 'official_exchange_candidate_missing_source_fields', None),
    ('official_exchange_listing_without_official_source', 'official_exchange_listing_without_official_source', None),
    ('official_exchange_secret_leak', 'official_exchange_secret_leak', None),
    ('official_exchange_delisting_long_research', 'official_exchange_delisting_long_research', None),
    ('official_exchange_quote_asset_misclassified', 'official_exchange_quote_asset_misclassified', None),
    ('official_exchange_major_pair_noise_promoted_early_long', 'official_exchange_major_pair_noise_promoted_early_long', None),
    ('official_exchange_created_alert_rows', 'official_exchange_created_alert_rows', None),
    ('official_exchange_activation_missing_shared_schema', 'official_exchange_activation_missing_shared_schema', None),
    ('official_exchange_activation_live_without_ledger', 'official_exchange_activation_live_without_ledger', None),
    ('official_exchange_activation_signed_listener_secret_leak', 'official_exchange_activation_signed_listener_secret_leak', None),
    ('official_exchange_activation_forbidden_side_effect_claim', 'official_exchange_activation_forbidden_side_effect_claim', None),
    ('instrument_resolution_missing_canonical_id_when_fixture_has_it', 'instrument_resolution_missing_canonical_id_when_fixture_has_it', None),
    ('instrument_resolution_quote_asset_misclassified', 'instrument_resolution_quote_asset_misclassified', None),
    ('instrument_resolution_sector_visible_as_tradable', 'instrument_resolution_sector_visible_as_tradable', None),
    ('instrument_resolution_coinalyze_symbol_unlinked', 'instrument_resolution_coinalyze_symbol_unlinked', None),
    ('scheduled_catalyst_rows', 'scheduled_catalyst_rows', None),
    ('unlock_candidate_rows', 'unlock_candidate_rows', None),
    ('derivatives_state_rows', 'derivatives_state_rows', None),
    ('fade_review_candidate_rows', 'fade_review_candidate_rows', None),
    ('unlock_without_structured_evidence', 'unlock_without_structured_evidence', None),
    ('unlock_missing_event_time', 'unlock_missing_event_time', None),
    ('unlock_promoted_without_size_metrics', 'unlock_promoted_without_size_metrics', None),
    ('media_unlock_promoted_structured', 'media_unlock_promoted_structured', None),
    ('stale_completed_catalyst_upcoming', 'stale_completed_catalyst_upcoming', None),
    ('calendar_event_missing_source_url', 'calendar_event_missing_source_url', None),
    ('cryptopanic_unlock_proof', 'cryptopanic_unlock_proof', None),
    ('scheduled_catalyst_created_alert_rows', 'scheduled_catalyst_created_alert_rows', None),
    ('fade_review_without_completed_move', 'fade_review_without_completed_move', None),
    ('fade_review_without_crowding_exhaustion', 'fade_review_without_crowding_exhaustion', None),
    ('fade_review_created_triggered_fade', 'fade_review_created_triggered_fade', None),
    ('fade_review_created_normal_rsi_signal', 'fade_review_created_normal_rsi_signal', None),
    ('fade_review_notification_missing_disclaimer', 'fade_review_notification_missing_disclaimer', None),
    ('derivatives_artifact_secret_leak', 'derivatives_artifact_secret_leak', None),
    ('derivatives_state_missing_freshness_status', 'derivatives_state_missing_freshness_status', None),
    ('derivatives_metric_claim_implemented_missing', 'derivatives_metric_claim_implemented_missing', None),
    ('derivatives_unit_metadata_missing', 'derivatives_unit_metadata_missing', None),
    ('stale_derivatives_snapshot_promoted_fade_review', 'stale_derivatives_snapshot_promoted_fade_review', None),
    ('confirmed_long_crowded_without_warning', 'confirmed_long_crowded_without_warning', None),
    ('integrated_radar_candidate_rows', 'integrated_radar_candidate_rows', None),
    ('integrated_candidate_missing_opportunity_type', 'integrated_candidate_missing_opportunity_type', None),
    ('integrated_candidate_missing_market_state_snapshot', 'integrated_candidate_missing_market_state_snapshot', None),
    ('integrated_confirmed_long_without_source_market', 'integrated_confirmed_long_without_source_market', None),
    ('integrated_early_long_without_fresh_strong_source', 'integrated_early_long_without_fresh_strong_source', None),
    ('integrated_fade_without_crowding_exhaustion', 'integrated_fade_without_crowding_exhaustion', None),
    ('integrated_risk_without_evidence', 'integrated_risk_without_evidence', None),
    ('integrated_market_anomaly_confirmed', 'integrated_market_anomaly_confirmed', None),
    ('integrated_cryptopanic_confirmed', 'integrated_cryptopanic_confirmed', None),
    ('integrated_major_pair_early_long', 'integrated_major_pair_early_long', None),
    ('integrated_input_manifest_missing', 'integrated_input_manifest_missing', None),
    ('integrated_source_coverage_json_missing', 'integrated_source_coverage_json_missing', None),
    ('integrated_candidate_core_missing', 'integrated_candidate_core_missing', None),
    ('integrated_candidate_core_opportunity_type_mismatch', 'integrated_candidate_core_opportunity_type_mismatch', None),
    ('integrated_candidate_core_market_state_mismatch', 'integrated_candidate_core_market_state_mismatch', None),
    ('integrated_candidate_core_route_level_mismatch', 'integrated_candidate_core_route_level_mismatch', None),
    ('integrated_candidate_core_reason_code_loss', 'integrated_candidate_core_reason_code_loss', None),
    ('integrated_candidate_core_source_url_loss', 'integrated_candidate_core_source_url_loss', None),
    ('integrated_candidate_core_official_event_loss', 'integrated_candidate_core_official_event_loss', None),
    ('integrated_candidate_core_scheduled_event_loss', 'integrated_candidate_core_scheduled_event_loss', None),
    ('integrated_candidate_core_unlock_event_loss', 'integrated_candidate_core_unlock_event_loss', None),
    ('integrated_candidate_core_derivatives_loss', 'integrated_candidate_core_derivatives_loss', None),
    ('integrated_candidate_core_decision_context_mismatch', 'integrated_candidate_core_decision_context_mismatch', None),
    ('integrated_candidate_core_decision_score_mismatch', 'integrated_candidate_core_decision_score_mismatch', None),
    ('integrated_dashboard_decision_authority_invalid', 'integrated_dashboard_decision_authority_invalid', None),
    ('integrated_candidate_expired_actionable', 'integrated_candidate_expired_actionable', None),
    ('integrated_core_expired_actionable', 'integrated_core_expired_actionable', None),
    ('integrated_preview_expired_actionable', 'integrated_preview_expired_actionable', None),
    ('integrated_dashboard_expired_actionable', 'integrated_dashboard_expired_actionable', None),
    ('integrated_candidate_card_opportunity_type_mismatch', 'integrated_candidate_card_opportunity_type_mismatch', None),
    ('integrated_candidate_card_decision_mismatch', 'integrated_candidate_card_decision_mismatch', None),
    ('integrated_candidate_card_why_now_mismatch', 'integrated_candidate_card_why_now_mismatch', None),
    ('integrated_major_pair_card_early_long', 'integrated_major_pair_card_early_long', None),
    ('integrated_card_generic_lane_override', 'integrated_card_generic_lane_override', None),
    ('card_opportunity_lane_core_mismatch', 'card_opportunity_lane_core_mismatch', None),
    ('integrated_candidate_card_official_event_missing', 'integrated_candidate_card_official_event_missing', None),
    ('integrated_candidate_card_source_url_missing', 'integrated_candidate_card_source_url_missing', None),
    ('integrated_candidate_core_crowding_metadata_loss', 'integrated_candidate_core_crowding_metadata_loss', None),
    ('derivatives_card_metric_claim_without_data', 'derivatives_card_metric_claim_without_data', None),
    ('integrated_coinalyze_crowding_card_missing', 'integrated_coinalyze_crowding_card_missing', None),
    ('integrated_coinalyze_loaded_no_rows_attached', 'integrated_coinalyze_loaded_no_rows_attached', None),
    ('integrated_coinalyze_missing_skip_reason', 'integrated_coinalyze_missing_skip_reason', None),
    ('integrated_coinalyze_stale_loaded_without_warning', 'integrated_coinalyze_stale_loaded_without_warning', None),
    ('integrated_coinalyze_loaded_from_stale_namespace', 'integrated_coinalyze_loaded_from_stale_namespace', None),
    ('integrated_fade_card_crowding_unknown', 'integrated_fade_card_crowding_unknown', None),
    ('integrated_fade_card_missing_disclaimer', 'integrated_fade_card_missing_disclaimer', None),
    ('integrated_confirmed_long_crowding_warning_hidden', 'integrated_confirmed_long_crowding_warning_hidden', None),
    ('integrated_market_confirmation_display_contradiction', 'integrated_market_confirmation_display_contradiction', None),
    ('integrated_derivatives_display_contradiction', 'integrated_derivatives_display_contradiction', None),
    ('integrated_manifest_mixed_timestamp_pair', 'integrated_manifest_mixed_timestamp_pair', None),
    ('integrated_core_silent_upgrade', 'integrated_core_silent_upgrade', None),
    ('integrated_diagnostic_visible_in_default_operator_section', 'integrated_diagnostic_visible_in_default_operator_section', None),
    ('integrated_preview_missing_disclaimer', 'integrated_preview_missing_disclaimer', None),
    ('integrated_delivery_ledger_missing', 'integrated_delivery_ledger_missing', None),
    ('integrated_preview_lane_mismatch', 'integrated_preview_lane_mismatch', None),
    ('integrated_delivery_missing_disclaimer', 'integrated_delivery_missing_disclaimer', None),
    ('integrated_delivery_sent_in_no_send', 'integrated_delivery_sent_in_no_send', None),
    ('integrated_delivery_side_effect_flag', 'integrated_delivery_side_effect_flag', None),
    ('integrated_delivery_missing_skip_reasons', 'integrated_delivery_missing_skip_reasons', None),
    ('integrated_delivery_card_path_absolute', 'integrated_delivery_card_path_absolute', None),
    ('integrated_delivery_card_path_not_rendered', 'integrated_delivery_card_path_not_rendered', None),
    ('integrated_operator_markdown_absolute_path', 'integrated_operator_markdown_absolute_path', None),
    ('operator_structured_path_absolute', 'operator_structured_path_absolute', None),
    ('integrated_api_preview_alerts_wording', 'integrated_api_preview_alerts_wording', None),
    ('integrated_manifest_daily_brief_unavailable', 'integrated_manifest_daily_brief_unavailable', None),
    ('integrated_outcome_missing_for_candidate', 'integrated_outcome_missing_for_candidate', None),
    ('integrated_outcome_side_effect_flag', 'integrated_outcome_side_effect_flag', None),
    ('integrated_outcome_schema_missing', 'integrated_outcome_schema_missing', None),
    ('integrated_outcome_missing_identity', 'integrated_outcome_missing_identity', None),
    ('integrated_outcome_returns_without_price', 'integrated_outcome_returns_without_price', None),
    ('integrated_outcome_diagnostic_in_performance', 'integrated_outcome_diagnostic_in_performance', None),
    ('integrated_calibration_diagnostic_in_main_priors', 'integrated_calibration_diagnostic_in_main_priors', None),
    ('integrated_calibration_prior_safety_missing', 'integrated_calibration_prior_safety_missing', None),
    ('integrated_calibration_api_alias_top_level', 'integrated_calibration_api_alias_top_level', None),
    ('integrated_outcome_return_double_scaled', 'integrated_outcome_return_double_scaled', None),
    ('integrated_outcome_missing_data_unlabeled', 'integrated_outcome_missing_data_unlabeled', None),
    ('integrated_outcome_thesis_move_missing', 'integrated_outcome_thesis_move_missing', None),
    ('integrated_outcome_eligibility_contract_invalid', 'integrated_outcome_eligibility_contract_invalid', None),
    ('integrated_outcome_synthetic_evidence_leak', 'integrated_outcome_synthetic_evidence_leak', None),
    ('integrated_outcome_immature_validation_claim', 'integrated_outcome_immature_validation_claim', None),
    ('integrated_outcome_duplicate_exact_identity', 'integrated_outcome_duplicate_exact_identity', None),
    ('integrated_outcome_ambiguous_exact_identity', 'integrated_outcome_ambiguous_exact_identity', None),
    ('integrated_outcome_eligible_provenance_missing', 'integrated_outcome_eligible_provenance_missing', None),
    ('integrated_outcome_identity_mismatch', 'integrated_outcome_identity_mismatch', None),
    ('integrated_outcome_decision_projection_mismatch', 'integrated_outcome_decision_projection_mismatch', None),
    ('integrated_outcome_card_thesis_interpretation_missing', 'integrated_outcome_card_thesis_interpretation_missing', None),
    ('integrated_outcome_card_trade_wording', 'integrated_outcome_card_trade_wording', None),
    ('integrated_performance_diagnostic_in_main_aggregate', 'integrated_performance_diagnostic_in_main_aggregate', None),
    ('integrated_performance_auto_apply_enabled', 'integrated_performance_auto_apply_enabled', None),
    ('integrated_performance_low_sample_missing_warning', 'integrated_performance_low_sample_missing_warning', None),
    ('integrated_performance_trade_pnl_wording', 'integrated_performance_trade_pnl_wording', None),
    ('integrated_created_normal_rsi_signal', 'integrated_created_normal_rsi_signal', None),
    ('integrated_created_triggered_fade', 'integrated_created_triggered_fade', None),
    ('source_coverage_report_missing', 'source_coverage_report_missing', None),
    ('source_coverage_provider_status_unknown', 'source_coverage_provider_status_unknown', None),
    ('source_coverage_provider_marked_healthy_without_observation', 'source_coverage_provider_marked_healthy_without_observation', None),
    ('source_coverage_category_priority_missing', 'source_coverage_category_priority_missing', None),
    ('source_coverage_readiness_link_missing', 'source_coverage_readiness_link_missing', None),
    ('source_coverage_context_provider_ranked_above_lane_critical', 'source_coverage_context_provider_ranked_above_lane_critical', None),
    ('source_coverage_coinalyze_missing_linked_artifact', 'source_coverage_coinalyze_missing_linked_artifact', None),
    ('source_coverage_bybit_announcements_missing_linked_artifact', 'source_coverage_bybit_announcements_missing_linked_artifact', None),
    ('source_coverage_unlock_calendar_missing_linked_artifact', 'source_coverage_unlock_calendar_missing_linked_artifact', None),
    ('live_provider_readiness_missing', 'live_provider_readiness_missing', None),
    ('live_provider_readiness_secret_leak', 'live_provider_readiness_secret_leak', None),
    ('live_provider_readiness_live_calls_allowed_in_smoke', 'live_provider_readiness_live_calls_allowed_in_smoke', None),
    ('live_provider_readiness_configured_missing_env', 'live_provider_readiness_configured_missing_env', None),
    ('coinalyze_preflight_secret_leak', 'coinalyze_preflight_secret_leak', None),
    ('coinalyze_preflight_live_call_allowed_in_smoke', 'coinalyze_preflight_live_call_allowed_in_smoke', None),
    ('coinalyze_preflight_configured_missing_env', 'coinalyze_preflight_configured_missing_env', None),
    ('coinalyze_preflight_ready_without_request_ledger', 'coinalyze_preflight_ready_without_request_ledger', None),
    ('coinalyze_preflight_missing_fixture_parser_status', 'coinalyze_preflight_missing_fixture_parser_status', None),
    ('coinalyze_preflight_forbidden_side_effect_claim', 'coinalyze_preflight_forbidden_side_effect_claim', None),
    ('coinalyze_rehearsal_secret_leak', 'coinalyze_rehearsal_secret_leak', None),
    ('coinalyze_rehearsal_live_without_ledger', 'coinalyze_rehearsal_live_without_ledger', None),
    ('coinalyze_rehearsal_live_call_allowed_in_smoke', 'coinalyze_rehearsal_live_call_allowed_in_smoke', None),
    ('coinalyze_rehearsal_live_without_explicit_allow', 'coinalyze_rehearsal_live_without_explicit_allow', None),
    ('coinalyze_rehearsal_request_budget_exceeded', 'coinalyze_rehearsal_request_budget_exceeded', None),
    ('coinalyze_rehearsal_success_without_derivatives_state', 'coinalyze_rehearsal_success_without_derivatives_state', None),
    ('coinalyze_rehearsal_success_without_crowding_candidates', 'coinalyze_rehearsal_success_without_crowding_candidates', None),
    ('coinalyze_provider_health_healthy_without_successful_ledger', 'coinalyze_provider_health_healthy_without_successful_ledger', None),
    ('coinalyze_rehearsal_forbidden_side_effect_claim', 'coinalyze_rehearsal_forbidden_side_effect_claim', None),
    ('coinalyze_supported_metric_implemented_missing_state', 'coinalyze_supported_metric_implemented_missing_state', None),
    ('bybit_announcements_preflight_secret_leak', 'bybit_announcements_preflight_secret_leak', None),
    ('bybit_announcements_preflight_live_call_allowed_in_smoke', 'bybit_announcements_preflight_live_call_allowed_in_smoke', None),
    ('bybit_announcements_preflight_missing_fixture_parser_status', 'bybit_announcements_preflight_missing_fixture_parser_status', None),
    ('bybit_announcements_rehearsal_secret_leak', 'bybit_announcements_rehearsal_secret_leak', None),
    ('bybit_announcements_rehearsal_live_without_ledger', 'bybit_announcements_rehearsal_live_without_ledger', None),
    ('bybit_announcements_rehearsal_live_without_explicit_allow', 'bybit_announcements_rehearsal_live_without_explicit_allow', None),
    ('bybit_announcements_rehearsal_unsupported_params', 'bybit_announcements_rehearsal_unsupported_params', None),
    ('bybit_announcements_rehearsal_accepted_source_invalid', 'bybit_announcements_rehearsal_accepted_source_invalid', None),
    ('bybit_announcements_rehearsal_forbidden_side_effect_claim', 'bybit_announcements_rehearsal_forbidden_side_effect_claim', None),
    ('unlock_calendar_preflight_secret_leak', 'unlock_calendar_preflight_secret_leak', None),
    ('unlock_calendar_preflight_live_without_ledger', 'unlock_calendar_preflight_live_without_ledger', None),
    ('unlock_calendar_preflight_live_call_allowed_in_smoke', 'unlock_calendar_preflight_live_call_allowed_in_smoke', None),
    ('unlock_calendar_preflight_missing_fixture_parser_status', 'unlock_calendar_preflight_missing_fixture_parser_status', None),
    ('unlock_calendar_preflight_forbidden_side_effect_claim', 'unlock_calendar_preflight_forbidden_side_effect_claim', None),
    ('source_pack_provider_status_missing', 'source_pack_provider_status_missing', None),
    ('missing_provider_recommendations_missing', 'missing_provider_recommendations_missing', None),
    ('degraded_provider_absence_marked_meaningful', 'degraded_provider_absence_marked_meaningful', None),
    ('cryptopanic_configured_but_not_observed', 'cryptopanic_configured_but_not_observed', None),
    ('cryptopanic_used_but_no_source_coverage_entry', 'cryptopanic_used_but_no_source_coverage_entry', None),
    ('cryptopanic_accepted_evidence_missing_from_card', 'cryptopanic_accepted_evidence_missing_from_card', None),
    ('cryptopanic_rejected_only_promoted', 'cryptopanic_rejected_only_promoted', None),
    ('cryptopanic_token_printed_or_unredacted', 'cryptopanic_token_printed_or_unredacted', None),
    ('cryptopanic_growth_unsupported_param_used', 'cryptopanic_growth_unsupported_param_used', None),
    ('cryptopanic_duplicate_request_key', 'cryptopanic_duplicate_request_key', None),
    ('cryptopanic_invalid_currency_code', 'cryptopanic_invalid_currency_code', None),
    ('cryptopanic_empty_currency_request', 'cryptopanic_empty_currency_request', None),
    ('cryptopanic_coin_id_sent_as_currency', 'cryptopanic_coin_id_sent_as_currency', None),
    ('cryptopanic_all_requests_failed', 'cryptopanic_all_requests_failed', None),
    ('cryptopanic_json_parse_errors', 'cryptopanic_json_parse_errors', None),
    ('cryptopanic_configured_but_unusable', 'cryptopanic_configured_but_unusable', None),
    ('cryptopanic_status_code_missing_on_http_failure', 'cryptopanic_status_code_missing_on_http_failure', None),
    ('cryptopanic_body_excerpt_unredacted_token', 'cryptopanic_body_excerpt_unredacted_token', None),
    ('cryptopanic_quota_exceeded', 'cryptopanic_quota_exceeded', None),
    ('cryptopanic_request_ledger_missing_when_used', 'cryptopanic_request_ledger_missing_when_used', None),
    ('cryptopanic_success_with_backoff_status', 'cryptopanic_success_with_backoff_status', None),
    ('cryptopanic_restore_token_recommendation_when_configured', 'cryptopanic_restore_token_recommendation_when_configured', None),
    ('cryptopanic_run_coverage_config_mismatch', 'cryptopanic_run_coverage_config_mismatch', None),
    ('cryptopanic_profile_disabled_coverage_mismatch', 'cryptopanic_profile_disabled_coverage_mismatch', None),
    ('cryptopanic_profile_disabled_credential_recommendation', 'cryptopanic_profile_disabled_credential_recommendation', None),
    ('source_coverage_blocker_summary_inconsistent', 'source_coverage_blocker_summary_inconsistent', None),
    ('evidence_count_mismatch', 'evidence_count_mismatch', None),
    ('visible_sector_core_without_config', 'visible_sector_core_without_config', None),
    ('duplicate_proxy_core_rows', 'duplicate_proxy_core_rows', None),
)

_FEEDBACK_ELIGIBILITY_FIELDS: tuple[_CounterField, ...] = (
    ('supplied', 'feedback_rows_supplied', None),
    ('eligible', 'feedback_rows_eligible', None),
    ('excluded', 'feedback_rows_excluded', None),
    ('contract_invalid', 'feedback_eligibility_contract_invalid', None),
    ('persisted_eligible_invalid', 'feedback_persisted_eligible_invalid', None),
    ('legacy', 'feedback_legacy_rows', None),
    ('duplicates', 'feedback_duplicate_rows', None),
    ('future', 'feedback_future_rows', None),
    ('unsafe', 'feedback_unsafe_rows', None),
    ('missing_core', 'feedback_missing_core_rows', None),
    ('ambiguous_core', 'feedback_ambiguous_core_rows', None),
    ('superseded', 'feedback_superseded_rows', None),
    ('duplicate_json_keys', 'feedback_duplicate_json_keys', None),
    ('invalid_jsonl', 'feedback_invalid_jsonl', None),
    ('jsonl_read_errors', 'feedback_jsonl_read_errors', None),
    ('reasons', 'feedback_exclusion_reason_counts', None),
)

_NOTIFICATION_DELIVERIES_FIELDS: tuple[_CounterField, ...] = (
    ('rows', 'delivery_rows', None),
    ('partial', 'deliveries_partial_delivered', None),
    ('failed', 'deliveries_failed', None),
    ('status_missing', 'delivery_status_missing', None),
    ('status_detail_missing', 'delivery_status_detail_missing', None),
    ('mode_missing', 'delivery_mode_missing', None),
    ('state_inconsistent', 'delivery_state_inconsistent', None),
    ('would_send_inconsistent', 'delivery_would_send_sent_failed_inconsistent', None),
    ('latest_run_id', 'latest_run_id', 'none'),
    ('strict_scope', 'delivery_strict_scope', None),
    ('latest_run_rows', 'latest_run_delivery_rows', None),
    ('stale_rows', 'stale_delivery_rows', None),
    ('legacy_rows', 'legacy_delivery_rows', None),
    ('identity_mismatch', 'delivery_identity_mismatch_core_store', None),
    ('core_missing', 'delivery_core_id_missing', None),
    ('stale_core_missing', 'stale_delivery_identity_missing_core', None),
    ('legacy_pre_core_identity', 'legacy_pre_core_delivery_identity', None),
    ('feedback_missing', 'delivery_feedback_target_missing', None),
    ('card_missing', 'delivery_card_path_missing', None),
    ('alert_id_not_canonical', 'delivery_alert_id_not_canonical', None),
    ('digest_without_confirmation', 'digest_item_without_live_confirmation', None),
    ('digest_rejected_only', 'digest_item_rejected_results_only', None),
    ('strategic_broad_digest', 'strategic_broad_asset_digest_without_confirmation', None),
    ('unconfirmed_narrative_daily_digest', 'unconfirmed_narrative_daily_digest', None),
    ('single_source_no_market_fan_token_digest', 'single_source_no_market_fan_token_digest', None),
    ('preview_missing', 'notification_preview_missing', None),
    ('preview_relpath_missing', 'notification_preview_relpath_missing', None),
    ('preview_unresolvable', 'notification_preview_path_unresolvable', None),
    ('preview_run_mismatch', 'notification_preview_run_summary_mismatch', None),
    ('preview_llm_mismatch', 'notification_preview_llm_summary_mismatch', None),
    ('preview_lane_mismatch', 'notification_preview_lane_counts_mismatch', None),
    ('preview_core_mismatch', 'notification_preview_core_count_mismatch', None),
    ('preview_alertable_mismatch', 'notification_preview_alertable_count_mismatch', None),
    ('preview_missing_send_guard', 'notification_preview_missing_send_guard_status', None),
    ('preview_send_guard_missing', 'notification_preview_send_guard_status_missing', None),
    ('preview_no_send_unclear', 'notification_preview_no_send_status_unclear', None),
    ('preview_api_alerts_wording', 'notification_preview_api_alerts_wording', None),
    ('raw_debug_dump', 'telegram_message_contains_raw_debug_dump', None),
    ('absolute_path', 'telegram_message_contains_absolute_path', None),
    ('research_review_missing_label', 'research_review_digest_missing_confirmation_label', None),
    ('research_review_alertable', 'research_review_digest_contains_strict_alertable', None),
    ('research_review_hard_gated', 'research_review_digest_contains_hard_gated_candidate', None),
    ('research_review_too_many', 'research_review_digest_too_many_items', None),
    ('research_review_feedback_missing', 'research_review_digest_missing_feedback_target', None),
    ('research_review_skipped_without_reason', 'research_review_digest_skipped_without_reason', None),
    ('research_review_missing_family_summary', 'research_review_digest_missing_family_summary', None),
    ('research_review_duplicate_visible_family_summary', 'research_review_digest_duplicate_visible_family_summary', None),
    ('research_review_absolute_path', 'research_review_digest_absolute_path', None),
    ('body_card_mismatch', 'notification_body_card_mismatch_canonical', None),
    ('body_feedback_mismatch', 'notification_body_feedback_mismatch_canonical', None),
    ('body_hypothesis_target', 'research_review_body_uses_hypothesis_target_when_core_exists', None),
    ('research_review_lane_missing', 'research_review_digest_enabled_but_lane_missing', None),
    ('research_review_no_delivery', 'research_review_digest_candidates_without_delivery', None),
)

_QUALITY_FIELDS: tuple[_CounterField, ...] = (
    ('missing_total', 'quality_fields_missing_count', None),
    ('hypotheses_missing_verdict', 'hypothesis_rows_missing_opportunity_verdict', None),
    ('watchlist_missing', 'watchlist_rows_missing_quality_fields', None),
    ('alerts_missing', 'alert_rows_missing_quality_fields', None),
    ('fresh_hypotheses_missing_top_level', 'fresh_hypothesis_rows_missing_top_level_quality', None),
    ('fresh_watchlist_missing_top_level', 'fresh_watchlist_rows_missing_top_level_quality', None),
    ('fresh_alerts_missing_top_level', 'fresh_alert_rows_missing_top_level_quality', None),
    ('legacy_quality_missing', 'legacy_quality_missing_rows', None),
)

_QUALITY_GATE_CONFLICTS_FIELDS: tuple[_CounterField, ...] = (
    ('alertable_route_conflicts_with_opportunity_level', 'alertable_route_conflicts_with_opportunity_level', None),
    ('fresh_quality_route_conflict_rows', 'fresh_quality_route_conflict_rows', None),
    ('legacy_quality_conflict_rows', 'legacy_quality_conflict_rows', None),
    ('alert_rows_missing_final_route', 'alert_rows_missing_final_route', None),
    ('fresh_alert_rows_missing_final_route', 'fresh_alert_rows_missing_final_route', None),
)

_WATCHLIST_QUALITY_STATE_FIELDS: tuple[_CounterField, ...] = (
    ('watchlist_state_conflicts_with_quality', 'watchlist_state_conflicts_with_quality', None),
    ('universal', 'universal_watchlist_state_conflicts', None),
    ('non_hypothesis', 'non_hypothesis_watchlist_quality_conflicts', None),
    ('hypothesis', 'hypothesis_watchlist_quality_conflicts', None),
    ('quality_capped', 'quality_capped_watchlist_rows', None),
    ('active_watchlist_rows_quality_capped', 'active_watchlist_rows_quality_capped', None),
    ('fresh_watchlist_state_conflict_rows', 'fresh_watchlist_state_conflict_rows', None),
    ('legacy_watchlist_conflicts', 'legacy_watchlist_conflicts', None),
)

_INCIDENT_LINKAGE_FIELDS: tuple[_CounterField, ...] = (
    ('hypothesis_rows_missing_incident_id', 'hypothesis_rows_missing_incident_id', None),
    ('watchlist_hypothesis_rows_missing_incident_id', 'watchlist_hypothesis_rows_missing_incident_id', None),
    ('alert_hypothesis_rows_missing_incident_id', 'alert_hypothesis_rows_missing_incident_id', None),
    ('incident_rows_without_linked_hypotheses', 'incident_rows_without_linked_hypotheses', None),
    ('incident_rows_without_linked_watchlist', 'incident_rows_without_linked_watchlist', None),
    ('canonical_unlinked_incidents', 'canonical_unlinked_incidents', None),
    ('active_incident_without_qualified_link', 'active_incident_without_qualified_link', None),
    ('linked_incident_without_qualified_link', 'linked_incident_without_qualified_link', None),
    ('weak_unqualified_incident_links', 'weak_unqualified_incident_links', None),
    ('quality_blocked_links_present', 'quality_blocked_links_present', None),
    ('quality_blocked_links_promoting_incident', 'quality_blocked_links_promoting_incident', None),
    ('diagnostic_incident_rows', 'diagnostic_incident_rows', None),
    ('raw_observation_incident_rows', 'raw_observation_incident_rows', None),
    ('external_context_incident_rows', 'external_context_incident_rows', None),
    ('rejected_incident_rows', 'rejected_incident_rows', None),
    ('incident_relevance_missing', 'incident_relevance_missing', None),
    ('invalid_canonical_incident_rows', 'invalid_canonical_incident_rows', None),
    ('garbage_primary_subject_incidents', 'garbage_primary_subject_incidents', None),
    ('fresh_blockers', 'fresh_incident_linkage_blockers', None),
    ('legacy_warnings', 'legacy_incident_linkage_warnings', None),
)


def _counter_value(result: object, attr: str, fallback: object) -> object:
    value = getattr(result, attr)
    if fallback is not None and not value:
        return fallback
    return value


def _counter_line(title: str, fields: tuple[_CounterField, ...], result: object) -> str:
    counters = (
        f"{label}={_counter_value(result, attr, fallback)}"
        for label, attr, fallback in fields
    )
    return f"{title}: " + " ".join(counters)


def _header_lines(result: EventAlphaArtifactDoctorResult) -> list[str]:
    return [
        "=" * 76,
        "EVENT ALPHA ARTIFACT DOCTOR (research artifact only)",
        "=" * 76,
        f"status: {result.status}",
        f"profile: {result.profile or 'any'}",
        f"namespace: {result.artifact_namespace or 'any'}",
        (
            "namespace_status: "
            f"{result.namespace_status or 'active'} "
            f"stale_deprecated={result.namespace_stale_deprecated} "
            f"superseded_by={result.namespace_superseded_by or 'none'}"
        ),
        f"strict: {str(result.strict).lower()}",
        f"strict_api: {str(result.strict_api).lower()}",
        doctor_report.phase_line(result),
        (
            "rows: "
            f"runs={result.run_rows} alerts={result.alert_rows} "
            f"feedback={result.feedback_rows} outcomes={result.outcome_rows} cards={result.card_files}"
        ),
        (
            "research cards: "
            f"research_card_files={result.research_card_files} "
            f"research_card_index_present={str(result.research_card_index_present).lower()} "
            f"cards_missing_lineage={result.cards_missing_lineage} "
            f"cards_missing_feedback_target={result.cards_missing_feedback_target}"
        ),
        doctor_report.schema_counter_line(result),
        *doctor_report.check_registry_lines(),
        (
            "shim hygiene: "
            "active_shim_modules_with_implementation_logic="
            f"{result.active_shim_modules_with_implementation_logic} "
            f"old_path_internal_imports={result.old_path_internal_imports} "
            f"old_path_test_imports={result.old_path_test_imports} "
            f"old_path_docs_references={result.old_path_docs_references} "
            f"old_path_import_allowed_exceptions={result.old_path_import_allowed_exceptions}"
        ),
    ]


def _snapshot_line(result: EventAlphaArtifactDoctorResult) -> str:
    return (
        "snapshot lineage: "
        f"matching={result.runs_with_matching_snapshots} "
        f"missing={result.runs_with_missing_snapshots} "
        f"external={result.runs_with_external_snapshot_paths}"
    )


def _api_rows_line(result: EventAlphaArtifactDoctorResult) -> str:
    return (
        "legacy rows: "
        f"skipped={result.legacy_rows_skipped} counted={result.legacy_rows_counted}"
    )


def _append_issue_sections(lines: list[str], result: EventAlphaArtifactDoctorResult) -> None:
    lines.extend(["", "blockers:"])
    if result.blockers:
        lines.extend(f"- {item}" for item in result.blockers)
    else:
        lines.append("- none")
    lines.extend(["", "warnings:"])
    if result.warnings:
        lines.extend(f"- {item}" for item in result.warnings)
    else:
        lines.append("- none")
    lines.append(
        "Doctor reports artifact hygiene only; it does not send, trade, paper trade, or alter tiers."
    )


def format_artifact_doctor_report(result: EventAlphaArtifactDoctorResult) -> str:
    lines = [
        *_header_lines(result),
        _counter_line("core opportunity coverage", _CORE_OPPORTUNITY_COVERAGE_FIELDS, result),
        _counter_line("feedback eligibility", _FEEDBACK_ELIGIBILITY_FIELDS, result),
        _snapshot_line(result),
        _api_rows_line(result),
        _counter_line("notification deliveries", _NOTIFICATION_DELIVERIES_FIELDS, result),
        _counter_line("quality fields", _QUALITY_FIELDS, result),
        _counter_line("quality gate conflicts", _QUALITY_GATE_CONFLICTS_FIELDS, result),
        _counter_line("watchlist quality state", _WATCHLIST_QUALITY_STATE_FIELDS, result),
        _counter_line("incident linkage", _INCIDENT_LINKAGE_FIELDS, result),
    ]
    _append_issue_sections(lines, result)
    return "\n".join(lines).rstrip()


__all__ = (
    "format_artifact_doctor_report",
)
