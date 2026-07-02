"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlsplit

from . import event_alpha_alert_store, event_alpha_artifacts, event_alpha_namespace_status, event_alpha_notification_inbox, event_alpha_quality_fields, event_alpha_router, event_alpha_source_coverage, event_artifact_paths, event_bybit_announcements_preflight, event_coinalyze_preflight, event_core_opportunities, event_core_opportunity_store, event_derivatives_crowding, event_integrated_radar, event_instrument_resolver, event_live_provider_readiness, event_market_anomaly_scanner, event_market_units, event_official_exchange, event_official_exchange_activation, event_opportunity_verdict, event_research_cards, event_scheduled_catalysts, event_unlock_calendar_preflight, event_watchlist
from . import event_alpha_notification_delivery as _delivery

STALE_PRE_CANONICAL_NOTIFICATION_WARNING = (
    "This namespace contains pre-canonical notification delivery rows. Do not use it "
    "for send-readiness. Run notify_llm_deep_rehearsal or fixture final check."
)


@dataclass(frozen=True)
class EventAlphaArtifactDoctorResult:
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
    integrated_legacy_preview_alerts_wording: int = 0
    integrated_manifest_daily_brief_unavailable: int = 0
    integrated_outcome_missing_for_candidate: int = 0
    integrated_outcome_side_effect_flag: int = 0
    integrated_outcome_schema_missing: int = 0
    integrated_outcome_missing_identity: int = 0
    integrated_outcome_returns_without_price: int = 0
    integrated_outcome_diagnostic_in_performance: int = 0
    integrated_calibration_diagnostic_in_main_priors: int = 0
    integrated_calibration_prior_safety_missing: int = 0
    integrated_calibration_legacy_alias_top_level: int = 0
    integrated_outcome_return_double_scaled: int = 0
    integrated_outcome_missing_data_unlabeled: int = 0
    integrated_outcome_thesis_move_missing: int = 0
    integrated_outcome_card_thesis_interpretation_missing: int = 0
    integrated_outcome_card_trade_wording: int = 0
    integrated_created_normal_rsi_signal: int = 0
    integrated_created_triggered_fade: int = 0
    source_coverage_report_missing: int = 0
    source_coverage_provider_status_unknown: int = 0
    source_coverage_provider_marked_healthy_without_observation: int = 0
    source_coverage_category_priority_missing: int = 0
    source_coverage_readiness_link_missing: int = 0
    source_coverage_context_provider_ranked_above_lane_critical: int = 0
    source_coverage_coinalyze_missing_linked_artifact: int = 0
    source_coverage_bybit_announcements_missing_linked_artifact: int = 0
    source_coverage_unlock_calendar_missing_linked_artifact: int = 0
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
    notification_preview_legacy_alerts_wording: int = 0
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
    namespace_status: str | None = None
    namespace_stale_deprecated: int = 0
    namespace_superseded_by: str | None = None
    strict_legacy: bool = False
    strict: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def diagnose_artifacts(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any] | object] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    incident_rows: Iterable[Mapping[str, Any] | object] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    market_anomaly_rows: Iterable[Mapping[str, Any]] | None = None,
    official_exchange_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    scheduled_catalyst_rows: Iterable[Mapping[str, Any]] | None = None,
    unlock_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    derivatives_state_rows: Iterable[Mapping[str, Any]] | None = None,
    fade_review_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    card_paths: Iterable[str | Path] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    source_coverage_report_path: str | Path | None = None,
    daily_brief_path: str | Path | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    inspected_alert_store_path: str | Path | None = None,
    strict: bool = False,
    strict_legacy: bool = False,
    delivery_strict_scope: str | None = None,
    include_stale_artifacts: bool = False,
) -> EventAlphaArtifactDoctorResult:
    """Diagnose cross-artifact lineage, mode, and profile/namespace cleanliness."""
    raw_runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    raw_alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    raw_feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    raw_outcomes = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    raw_hypotheses = [_row(row) for row in hypothesis_rows]
    raw_core_rows = [_row(row) for row in core_opportunity_rows]
    raw_watchlist = [_row(row) for row in watchlist_rows]
    raw_incidents = [_row(row) for row in incident_rows]
    raw_acquisition_rows = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    if market_anomaly_rows is None:
        default_market_anomaly_path = None
        if inspected_alert_store_path is not None:
            default_market_anomaly_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_market_anomaly_path = Path(source_coverage_report_path).parent
        raw_market_anomalies = list(event_market_anomaly_scanner.load_market_anomaly_rows(default_market_anomaly_path))
    else:
        raw_market_anomalies = [dict(row) for row in market_anomaly_rows if isinstance(row, Mapping)]
    if official_exchange_candidate_rows is None:
        default_official_exchange_path = None
        if inspected_alert_store_path is not None:
            default_official_exchange_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_official_exchange_path = Path(source_coverage_report_path).parent
        raw_official_exchange_candidates = list(event_official_exchange.load_official_listing_candidates(default_official_exchange_path))
    else:
        raw_official_exchange_candidates = [dict(row) for row in official_exchange_candidate_rows if isinstance(row, Mapping)]
    if scheduled_catalyst_rows is None:
        default_scheduled_path = None
        if inspected_alert_store_path is not None:
            default_scheduled_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_scheduled_path = Path(source_coverage_report_path).parent
        raw_scheduled_catalysts = list(event_scheduled_catalysts.load_scheduled_catalysts(default_scheduled_path))
    else:
        raw_scheduled_catalysts = [dict(row) for row in scheduled_catalyst_rows if isinstance(row, Mapping)]
    if unlock_candidate_rows is None:
        default_unlock_path = None
        if inspected_alert_store_path is not None:
            default_unlock_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_unlock_path = Path(source_coverage_report_path).parent
        raw_unlock_candidates = list(event_scheduled_catalysts.load_unlock_candidates(default_unlock_path))
    else:
        raw_unlock_candidates = [dict(row) for row in unlock_candidate_rows if isinstance(row, Mapping)]
    if derivatives_state_rows is None:
        default_derivatives_path = None
        if inspected_alert_store_path is not None:
            default_derivatives_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_derivatives_path = Path(source_coverage_report_path).parent
        raw_derivatives_state = list(event_derivatives_crowding.load_derivatives_state(default_derivatives_path))
    else:
        raw_derivatives_state = [dict(row) for row in derivatives_state_rows if isinstance(row, Mapping)]
    if fade_review_candidate_rows is None:
        default_fade_review_path = None
        if inspected_alert_store_path is not None:
            default_fade_review_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_fade_review_path = Path(source_coverage_report_path).parent
        raw_fade_review_candidates = list(event_derivatives_crowding.load_derivatives_candidates(default_fade_review_path))
        if not raw_fade_review_candidates:
            raw_fade_review_candidates = list(event_derivatives_crowding.load_fade_review_candidates(default_fade_review_path))
    else:
        raw_fade_review_candidates = [dict(row) for row in fade_review_candidate_rows if isinstance(row, Mapping)]
    default_integrated_path = None
    if inspected_alert_store_path is not None:
        default_integrated_path = Path(inspected_alert_store_path).parent / "event_integrated_radar_candidates.jsonl"
    elif source_coverage_report_path is not None:
        default_integrated_path = Path(source_coverage_report_path).parent / "event_integrated_radar_candidates.jsonl"
    raw_integrated_candidates = _read_jsonl(default_integrated_path) if default_integrated_path is not None else []
    default_integrated_dir = default_integrated_path.parent if default_integrated_path is not None else None
    integrated_manifest_path = (
        default_integrated_dir / "event_integrated_radar_input_manifest.json"
        if default_integrated_dir is not None
        else None
    )
    integrated_source_coverage_json_path = (
        default_integrated_dir / "event_alpha_source_coverage.json"
        if default_integrated_dir is not None
        else None
    )
    integrated_delivery_path = (
        default_integrated_dir / event_integrated_radar.INTEGRATED_DELIVERIES_FILENAME
        if default_integrated_dir is not None
        else None
    )
    integrated_outcomes_path = (
        default_integrated_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        if default_integrated_dir is not None
        else None
    )
    raw_legacy = sum(
        1 for row in (*raw_runs, *raw_alerts, *raw_feedback, *raw_outcomes)
        if event_alpha_artifacts.is_legacy_row(row)
    )
    runs = event_alpha_artifacts.filter_artifact_rows(
        raw_runs,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        raw_alerts,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    feedback = event_alpha_artifacts.filter_artifact_rows(
        raw_feedback,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    outcomes = event_alpha_artifacts.filter_artifact_rows(
        raw_outcomes,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    hypotheses = event_alpha_artifacts.filter_artifact_rows(
        raw_hypotheses,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    core_rows = event_alpha_artifacts.filter_artifact_rows(
        raw_core_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    watchlist = _filter_watchlist_rows_for_doctor(
        raw_watchlist,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    incidents = event_alpha_artifacts.filter_artifact_rows(
        raw_incidents,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
        raw_acquisition_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    market_anomalies = event_alpha_artifacts.filter_artifact_rows(
        raw_market_anomalies,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    official_exchange_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_official_exchange_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    scheduled_catalysts = event_alpha_artifacts.filter_artifact_rows(
        raw_scheduled_catalysts,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    unlock_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_unlock_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    derivatives_state = event_alpha_artifacts.filter_artifact_rows(
        raw_derivatives_state,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    fade_review_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_fade_review_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    integrated_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_integrated_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    matching_snapshot_runs = 0
    missing_snapshot_runs = 0
    external_snapshot_runs = 0
    if not runs:
        blockers.append("no matching operational/burn-in run rows found")
    latest_run_id = _latest_run_id(runs)
    latest_run = next((row for row in runs if str(row.get("run_id") or "") == str(latest_run_id or "")), None)
    effective_delivery_scope = _normalize_delivery_strict_scope(
        delivery_strict_scope,
        latest_run_id=latest_run_id,
        strict=strict,
    )
    run_ids = {str(row.get("run_id") or "") for row in runs if row.get("run_id")}
    alert_run_ids = {str(row.get("run_id") or "") for row in alerts if row.get("run_id")}
    alert_counts_by_run_id: dict[str, int] = {}
    for row in alerts:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            alert_counts_by_run_id[run_id] = alert_counts_by_run_id.get(run_id, 0) + 1
    for row in runs:
        if event_alpha_artifacts.is_non_operational_row(row) and not include_test_artifacts:
            continue
        alertable = int(row.get("alertable") or 0) > 0
        if not alertable:
            continue
        run_id = str(row.get("run_id") or "").strip()
        stale_for_latest_scope = (
            effective_delivery_scope == "latest_run"
            and bool(latest_run_id)
            and bool(run_id)
            and run_id != latest_run_id
        )
        matching = alert_counts_by_run_id.get(run_id, 0)
        availability = event_alpha_artifacts.classify_snapshot_availability(
            row,
            inspected_alert_store_path,
            matching,
        )
        if availability == event_alpha_artifacts.SNAPSHOT_AVAILABLE:
            matching_snapshot_runs += 1
        elif availability in {
            event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH,
            event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL,
        }:
            external_snapshot_runs += 1
        else:
            missing_snapshot_runs += 1
        if not bool(row.get("snapshot_write_success")):
            if str(row.get("snapshot_write_block_reason") or "") == "test_or_fixture_run":
                warnings.append(f"run {row.get('run_id') or 'unknown'} is test/fixture and skipped snapshots")
                if availability == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL:
                    _record_snapshot_availability_issue(
                        row,
                        availability,
                        blockers=blockers,
                        warnings=warnings,
                        strict=strict,
                    )
            else:
                message = f"alertable run {row.get('run_id') or 'unknown'} has no successful snapshot write"
                (warnings if stale_for_latest_scope else blockers).append(message)
        elif int(row.get("alertable") or 0) > 0 and int(row.get("snapshot_rows_written") or 0) <= 0:
            message = f"alertable run {row.get('run_id') or 'unknown'} wrote zero alert snapshots"
            (warnings if stale_for_latest_scope else blockers).append(message)
        elif availability != event_alpha_artifacts.SNAPSHOT_AVAILABLE:
            if stale_for_latest_scope:
                warnings.append(
                    f"stale alertable run {row.get('run_id') or 'unknown'} has snapshot availability={availability}"
                )
            else:
                _record_snapshot_availability_issue(
                    row,
                    availability,
                    blockers=blockers,
                    warnings=warnings,
                    strict=strict,
                )
    orphan_alerts = sorted(alert_run_ids - run_ids)
    if orphan_alerts:
        warnings.append(f"alert snapshots reference unknown run_id(s): {', '.join(orphan_alerts[:5])}")
    if any(row.get("run_id") in (None, "") for row in alerts):
        warnings.append("legacy alert snapshots without run_id lineage are present")
    alert_keys = {str(row.get("alert_key") or "") for row in alerts if row.get("alert_key")}
    feedback_keys = {str(row.get("key") or row.get("alert_key") or "") for row in feedback}
    outcome_keys = {str(row.get("alert_key") or "") for row in outcomes}
    unknown_feedback = sorted(key for key in feedback_keys if key and key not in alert_keys)
    unknown_outcomes = sorted(key for key in outcome_keys if key and key not in alert_keys)
    if unknown_feedback:
        message = f"feedback without matching alert snapshot: {', '.join(unknown_feedback[:5])}"
        (blockers if strict else warnings).append(message)
    if unknown_outcomes:
        message = f"outcomes without matching alert snapshot: {', '.join(unknown_outcomes[:5])}"
        (blockers if strict else warnings).append(message)
    namespaces = {
        event_alpha_artifacts.row_namespace(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    profiles = {
        event_alpha_artifacts.row_profile(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    if artifact_namespace and any(ns not in {artifact_namespace, "legacy"} for ns in namespaces):
        blockers.append("mixed artifact namespaces after filtering")
    elif len(namespaces - {"legacy"}) > 1:
        (blockers if strict else warnings).append("multiple artifact namespaces present")
    if profile and any(item not in {profile, "default"} for item in profiles):
        warnings.append("rows from multiple profiles are present")
    if provider_health_rows is not None and profile in {"no_key_live", "api_live", "full_llm_live", "research_send"}:
        if not provider_health_rows:
            message = "provider health rows missing for live/burn-in profile"
            (blockers if strict else warnings).append(message)
    if profile in {"full_llm_live", "no_key_llm"} and not list(llm_budget_rows):
        warnings.append("LLM budget rows missing for LLM profile")
    card_file_paths = [Path(path) for path in card_paths]
    research_card_paths = [path for path in card_file_paths if path.name != "index.md"]
    daily_brief_card_names = _daily_brief_card_names(daily_brief_path)
    card_count = len(research_card_paths)
    index_present = any(path.name == "index.md" for path in card_file_paths)
    cards_missing_lineage = sum(1 for path in research_card_paths if not event_research_cards.card_has_current_lineage(path))
    cards_missing_feedback_target = sum(1 for path in research_card_paths if not event_research_cards.card_feedback_target(path))
    card_group_map = event_research_cards.card_index_group_map(research_card_paths)
    card_core_ids = {value for path in research_card_paths for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_paths_by_core_id = {
        value: path
        for path in research_card_paths
        for value in (event_research_cards.card_core_opportunity_id(path),)
        if value
    }
    card_feedback_targets = {value for path in research_card_paths for value in (event_research_cards.card_feedback_target(path),) if value}
    visible_core = (
        event_core_opportunity_store.core_opportunities_from_rows(core_rows)
        if core_rows
        else event_core_opportunities.visible_core_opportunities([*watchlist, *alerts, *hypotheses])
    )
    visible_core_ids = {item.core_opportunity_id for item in visible_core}
    visible_core_by_id = {item.core_opportunity_id: item for item in visible_core}
    normalized_core_rows_by_id = {
        item.core_opportunity_id: dict(item.primary_row)
        for item in visible_core
        if item.core_opportunity_id
    }
    store_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows
        if str(row.get("core_opportunity_id") or "").strip()
    }
    core_rows_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows
        if str(row.get("core_opportunity_id") or "").strip()
    }
    core_store_available = bool(store_core_ids)
    visible_missing_store_rows = len(visible_core_ids - store_core_ids) if core_store_available else len(visible_core_ids)
    duplicate_store_rows = max(0, len(core_rows) - len(store_core_ids))
    store_rows_missing_card_path = sum(
        1
        for row in core_rows
        if not str(row.get("card_path") or row.get("research_card_path") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in card_paths_by_core_id
    )
    visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids)
    visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
    )
    core_card_paths = [
        path for path in research_card_paths
        if (card_group_map.get(path) or event_research_cards.card_index_group(path)) == "Core Opportunity Cards"
    ]
    core_cards_missing_store = sum(
        1
        for path in core_card_paths
        if event_research_cards.card_core_opportunity_id(path) not in store_core_ids
    )
    visible_core_cards_missing_store = core_cards_missing_store
    orphan_core_cards = core_cards_missing_store
    card_group_mismatches = sum(
        1
        for path in research_card_paths
        if (not daily_brief_card_names or path.name in daily_brief_card_names)
        and path in card_group_map
        and _expected_card_group_for_store_core(
            visible_core_by_id.get(str(event_research_cards.card_core_opportunity_id(path) or ""))
        ) not in {None, card_group_map[path]}
    )
    diagnostic_fake_core = sum(
        1
        for row in alerts
        if (
            bool(row.get("is_diagnostic_snapshot"))
            or event_core_opportunities.row_is_diagnostic(row)
        )
        and str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id_status") or "") not in {"diagnostic_support", "canonical"}
    )
    snapshot_core_missing_store = sum(
        1
        for row in alerts
        if str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in store_core_ids
        and not bool(row.get("is_diagnostic_snapshot"))
    )
    acquisition_core_missing_store = sum(
        1
        for row in acquisition_rows
        if str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in store_core_ids
        and str(row.get("core_opportunity_id_status") or "") not in {"diagnostic_support", "canonical"}
    )
    card_primary_mismatches = _card_primary_mismatches(research_card_paths, normalized_core_rows_by_id)
    card_acquisition_mismatches = _card_acquisition_count_mismatches(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    card_source_pack_mismatches = _card_source_pack_mismatches(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    card_support_blockers = _card_primary_section_contains_support_row_blockers(research_card_paths, normalized_core_rows_by_id)
    card_upgrade_inconsistent = _card_upgrade_text_inconsistent_with_final_level(research_card_paths, normalized_core_rows_by_id)
    card_market_missing = _card_market_confirmation_missing_but_core_has_market_confirmation(research_card_paths, normalized_core_rows_by_id)
    card_source_unknown = _card_latest_source_unknown_but_accepted_evidence_exists(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    audit_impact_mismatch = 0
    audit_source_pack_mismatch = 0
    market_freshness_contradictions = sum(1 for row in core_rows if _core_row_has_market_freshness_contradiction(row))
    promoted_core_in_weak = _promoted_core_rows_that_are_weak(core_rows)
    core_route_conflicts = _core_route_conflicts_with_opportunity_level(core_rows)
    live_confirmation_conflicts = _live_confirmation_conflicts(core_rows, profile=profile, artifact_namespace=artifact_namespace)
    raw_core_conflicts = _raw_core_live_confirmation_conflicts(
        core_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    opportunity_lane_conflicts = _opportunity_lane_conflicts(core_rows)
    market_anomaly_conflicts = _market_anomaly_artifact_conflicts(market_anomalies)
    official_exchange_conflicts = _official_exchange_artifact_conflicts(official_exchange_candidates)
    scheduled_conflicts = _scheduled_catalyst_artifact_conflicts((*scheduled_catalysts, *unlock_candidates))
    derivatives_conflicts = _derivatives_crowding_artifact_conflicts((*derivatives_state, *fade_review_candidates))
    integrated_conflicts = _integrated_radar_artifact_conflicts(
        integrated_candidates,
        core_rows=core_rows,
        research_card_paths=research_card_paths,
        daily_brief_path=daily_brief_path,
        manifest_path=integrated_manifest_path,
        source_coverage_json_path=integrated_source_coverage_json_path,
        delivery_path=integrated_delivery_path,
        outcome_path=integrated_outcomes_path,
        preview_path=(
            Path(inspected_alert_store_path).parent / "event_alpha_notification_preview.md"
            if inspected_alert_store_path is not None
            else (
                Path(source_coverage_report_path).parent / "event_alpha_notification_preview.md"
                if source_coverage_report_path is not None
                else None
            )
        ),
    )
    namespace_dir = _artifact_namespace_dir(
        inspected_alert_store_path,
        source_coverage_report_path,
        daily_brief_path,
        integrated_outcomes_path,
    )
    namespace_status = event_alpha_namespace_status.load_namespace_status(namespace_dir)
    if event_alpha_namespace_status.is_stale_deprecated(namespace_status) and not include_stale_artifacts:
        return EventAlphaArtifactDoctorResult(
            status="STALE",
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_rows=len(runs),
            alert_rows=len(alerts),
            feedback_rows=len(feedback),
            outcome_rows=len(outcomes),
            card_files=0,
            namespace_status=namespace_status.status if namespace_status else None,
            namespace_stale_deprecated=1,
            namespace_superseded_by=namespace_status.superseded_by if namespace_status else None,
            strict=strict,
            strict_legacy=strict_legacy,
            warnings=(event_alpha_namespace_status.format_namespace_status(namespace_status),),
        )
    structured_path_conflicts = _structured_operator_path_conflicts(
        (
            *runs,
            *alerts,
            *feedback,
            *outcomes,
            *hypotheses,
            *core_rows,
            *watchlist,
            *incidents,
            *acquisition_rows,
            *market_anomalies,
            *official_exchange_candidates,
            *scheduled_catalysts,
            *unlock_candidates,
            *derivatives_state,
            *fade_review_candidates,
            *integrated_candidates,
            *delivery_rows,
        )
    )
    if namespace_dir is not None:
        structured_path_conflicts += _structured_operator_path_file_conflicts(namespace_dir)
    integrated_conflicts["operator_structured_path_absolute"] = max(
        int(integrated_conflicts.get("operator_structured_path_absolute", 0)),
        int(structured_path_conflicts),
    )
    source_coverage_conflicts = _source_coverage_metadata_conflicts((*core_rows, *acquisition_rows))
    source_coverage_report_conflicts = _source_coverage_report_conflicts(source_coverage_report_path)
    live_provider_readiness_conflicts = _live_provider_readiness_conflicts(namespace_dir)
    coinalyze_preflight_conflicts = event_coinalyze_preflight.artifact_conflicts(namespace_dir)
    bybit_announcements_conflicts = event_bybit_announcements_preflight.artifact_conflicts(namespace_dir)
    unlock_calendar_conflicts = event_unlock_calendar_preflight.artifact_conflicts(namespace_dir)
    official_exchange_activation_conflicts = event_official_exchange_activation.artifact_conflicts(namespace_dir)
    instrument_resolution_conflicts = event_instrument_resolver.artifact_conflicts(namespace_dir)
    cryptopanic_conflicts = _cryptopanic_artifact_conflicts(
        acquisition_rows=acquisition_rows,
        core_rows=core_rows,
        research_card_paths=research_card_paths,
        source_coverage_report_path=source_coverage_report_path,
    )
    evidence_count_mismatches = _evidence_count_mismatches(acquisition_rows)
    acquisition_final_conflicts = _evidence_acquisition_final_field_conflicts(acquisition_rows)
    visible_sector_cores = _visible_sector_core_without_config(core_rows)
    duplicate_proxy_cores = _duplicate_proxy_core_rows(core_rows)
    daily_brief_conflicts = _daily_brief_consistency_conflicts(
        daily_brief_path,
        runs=runs,
        core_rows=core_rows,
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        source_coverage_report_path=source_coverage_report_path,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    upgrade_high_priority = 0
    fresh_visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids and _core_has_fresh_rows(item))
    fresh_visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
        and _core_has_fresh_rows(item)
    )
    snapshots_missing_core = sum(1 for row in alerts if _alert_snapshot_should_have_core_id(row) and not str(row.get("core_opportunity_id") or "").strip())
    snapshots_missing_feedback = sum(
        1 for row in alerts
        if _alert_snapshot_should_have_core_id(row)
        and not _alert_snapshot_is_diagnostic(row)
        and not _alert_has_feedback_target(row)
    )
    diagnostic_snapshots_missing_feedback = sum(
        1 for row in alerts
        if _alert_snapshot_is_diagnostic(row) and not _alert_has_feedback_target(row)
    )
    review_cards_dir = card_file_paths[0].parent if card_file_paths else None
    review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        profile,
        artifact_namespace,
        include_diagnostics=True,
        notification_runs=runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    default_review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        profile,
        artifact_namespace,
        include_diagnostics=False,
        notification_runs=runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    inbox_core_missing_card = sum(
        1 for item in review_items
        if not item.is_diagnostic and item.core_opportunity_id and not item.card_path
    )
    inbox_core_alert_target = sum(
        1 for item in review_items
        if not item.is_diagnostic
        and item.core_opportunity_id
        and item.feedback_target
        and item.feedback_target != item.core_opportunity_id
        and item.feedback_target.startswith("ea:")
    )
    inbox_diag_visible_default = sum(1 for item in default_review_items if item.is_diagnostic)
    audit_primary_not_canonical = _audit_primary_snapshot_not_canonical_when_canonical_exists(alerts, store_core_ids)
    if card_count and not index_present:
        message = "research cards exist but index.md was not found"
        (blockers if strict else warnings).append(message)
    if cards_missing_lineage:
        message = f"research cards missing current lineage: {cards_missing_lineage}"
        (blockers if strict else warnings).append(message)
    if cards_missing_feedback_target:
        message = f"research cards missing feedback target: {cards_missing_feedback_target}"
        (blockers if strict else warnings).append(message)
    if visible_missing_cards:
        message = f"visible_core_opportunities_missing_cards={visible_missing_cards}"
        (blockers if strict and fresh_visible_missing_cards else warnings).append(message)
    if visible_missing_store_rows:
        message = f"visible_core_opportunities_missing_store_rows={visible_missing_store_rows}"
        strict_core_store = strict and not include_test_artifacts and not include_legacy_artifacts
        (blockers if strict_core_store else warnings).append(message)
    if duplicate_store_rows:
        warnings.append(f"duplicate_core_opportunity_store_rows={duplicate_store_rows}")
    if store_rows_missing_card_path:
        message = f"core_opportunity_store_rows_missing_card_path={store_rows_missing_card_path}"
        (blockers if strict and card_count else warnings).append(message)
    if core_cards_missing_store:
        message = f"core_cards_missing_store_row={core_cards_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if orphan_core_cards:
        warnings.append(f"orphan_core_opportunity_cards={orphan_core_cards}")
    if diagnostic_fake_core:
        warnings.append(f"diagnostic_snapshots_with_fake_core_id={diagnostic_fake_core}")
    if snapshot_core_missing_store:
        message = f"alert_snapshots_core_id_missing_from_store={snapshot_core_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if acquisition_core_missing_store:
        message = f"evidence_acquisition_core_id_missing_from_store={acquisition_core_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_primary_mismatches:
        message = f"card_primary_fields_mismatch_core_store={card_primary_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_acquisition_mismatches:
        message = f"card_evidence_acquisition_count_mismatch={card_acquisition_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if acquisition_final_conflicts["evidence_acquisition_stale_validated_digest"]:
        message = (
            "evidence_acquisition_stale_validated_digest="
            f"{acquisition_final_conflicts['evidence_acquisition_stale_validated_digest']}"
        )
        (blockers if strict else warnings).append(message)
    if card_source_pack_mismatches:
        message = f"card_source_pack_mismatch_core_acquisition={card_source_pack_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_support_blockers:
        message = f"card_primary_section_contains_support_row_blockers={card_support_blockers}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_upgrade_inconsistent:
        message = f"card_upgrade_text_inconsistent_with_final_level={card_upgrade_inconsistent}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_market_missing:
        message = f"card_market_confirmation_missing_but_core_has_market_confirmation={card_market_missing}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_source_unknown:
        message = f"card_latest_source_unknown_but_accepted_evidence_exists={card_source_unknown}"
        (blockers if strict and core_store_available else warnings).append(message)
    if promoted_core_in_weak:
        message = f"quality_review_promoted_core_in_weak_section={promoted_core_in_weak}"
        (blockers if strict else warnings).append(message)
    if market_freshness_contradictions:
        message = f"market_freshness_contradictory_summary={market_freshness_contradictions}"
        (blockers if strict else warnings).append(message)
    if upgrade_high_priority:
        message = f"upgrade_candidates_include_high_priority={upgrade_high_priority}"
        (blockers if strict else warnings).append(message)
    if card_group_mismatches:
        message = f"daily_brief_card_group_mismatch_with_index={card_group_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    for key in (
        "daily_brief_missing_selected_run",
        "daily_brief_selected_run_mismatch",
        "daily_brief_core_count_mismatch_store",
        "daily_brief_research_review_lane_missing",
        "daily_brief_source_coverage_path_missing",
        "daily_brief_coinalyze_source_coverage_mismatch",
    ):
        count = daily_brief_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    if core_route_conflicts:
        message = f"core_route_conflicts_with_opportunity_level={core_route_conflicts}"
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_validated_without_confirmation"]:
        message = (
            "live_validated_without_confirmation="
            f"{live_confirmation_conflicts['live_validated_without_confirmation']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_sector_digest_without_asset"]:
        message = (
            "live_sector_digest_without_asset="
            f"{live_confirmation_conflicts['live_sector_digest_without_asset']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_rejected_results_promoted"]:
        message = (
            "live_rejected_results_promoted="
            f"{live_confirmation_conflicts['live_rejected_results_promoted']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_skipped_budget_promoted"]:
        message = (
            "live_skipped_budget_promoted="
            f"{live_confirmation_conflicts['live_skipped_budget_promoted']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    for key in (
        "raw_core_validated_without_confirmation",
        "raw_core_source_only_narrative_validated",
        "raw_core_cryptopanic_tag_only_direct_path_confirmed",
        "raw_core_suppressed_duplicate_validated_stale",
    ):
        count = raw_core_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict and core_store_available else warnings).append(message)
    for key in (
        "confirmed_long_without_source_market",
        "fade_short_without_crowding_exhaustion",
        "early_long_without_fresh_strong_source",
        "risk_only_missing_evidence_only",
        "cryptopanic_only_narrative_confirmed_lane",
        "diagnostic_visible_default_operator_lane",
        "core_missing_market_state_snapshot",
        "market_state_possible_double_scaled",
        "market_state_lane_possible_double_scaled",
    ):
        count = opportunity_lane_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict and core_store_available else warnings).append(message)
    if opportunity_lane_conflicts.get("market_state_return_unit_missing", 0):
        warnings.append(
            "market_state_return_unit_missing="
            f"{opportunity_lane_conflicts['market_state_return_unit_missing']}"
        )
    for key in (
        "market_anomaly_missing_market_state_snapshot",
        "market_anomaly_missing_market_state_class",
        "market_anomaly_confirmed_breakout_missing_evidence",
        "market_anomaly_suspicious_illiquid_promoted_confirmed",
        "market_anomaly_created_alert_rows",
    ):
        count = market_anomaly_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    for key in (
        "market_anomaly_missing_freshness_status",
        "market_anomaly_needs_search_without_plan",
    ):
        count = market_anomaly_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")
    for key in (
        "official_exchange_candidate_missing_source_fields",
        "official_exchange_listing_without_official_source",
        "official_exchange_secret_leak",
        "official_exchange_delisting_long_research",
        "official_exchange_quote_asset_misclassified",
        "official_exchange_major_pair_noise_promoted_early_long",
        "official_exchange_created_alert_rows",
    ):
        count = official_exchange_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)
    for key in (
        "official_exchange_activation_missing_shared_schema",
        "official_exchange_activation_live_without_ledger",
        "official_exchange_activation_signed_listener_secret_leak",
        "official_exchange_activation_forbidden_side_effect_claim",
    ):
        count = official_exchange_activation_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)
    for key in (
        "instrument_resolution_missing_canonical_id_when_fixture_has_it",
        "instrument_resolution_quote_asset_misclassified",
        "instrument_resolution_sector_visible_as_tradable",
    ):
        count = instrument_resolution_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            if strict or key in {
                "instrument_resolution_quote_asset_misclassified",
                "instrument_resolution_sector_visible_as_tradable",
            }:
                blockers.append(message)
            else:
                warnings.append(message)
    if instrument_resolution_conflicts.get("instrument_resolution_coinalyze_symbol_unlinked", 0):
        warnings.append(
            "instrument_resolution_coinalyze_symbol_unlinked="
            f"{instrument_resolution_conflicts['instrument_resolution_coinalyze_symbol_unlinked']}"
        )
    for key in (
        "unlock_without_structured_evidence",
        "unlock_missing_event_time",
        "unlock_promoted_without_size_metrics",
        "media_unlock_promoted_structured",
        "stale_completed_catalyst_upcoming",
        "cryptopanic_unlock_proof",
        "scheduled_catalyst_created_alert_rows",
    ):
        count = scheduled_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)
    if scheduled_conflicts.get("calendar_event_missing_source_url", 0):
        message = f"calendar_event_missing_source_url={scheduled_conflicts['calendar_event_missing_source_url']}"
        (blockers if strict else warnings).append(message)
    for key in (
        "fade_review_without_completed_move",
        "fade_review_without_crowding_exhaustion",
        "fade_review_created_triggered_fade",
        "fade_review_created_normal_rsi_signal",
        "fade_review_notification_missing_disclaimer",
        "derivatives_artifact_secret_leak",
        "derivatives_metric_claim_implemented_missing",
        "stale_derivatives_snapshot_promoted_fade_review",
    ):
        count = derivatives_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)
    for key in (
        "derivatives_state_missing_freshness_status",
        "derivatives_unit_metadata_missing",
        "confirmed_long_crowded_without_warning",
    ):
        count = derivatives_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")
    for key in (
        "integrated_candidate_missing_opportunity_type",
        "integrated_candidate_missing_market_state_snapshot",
        "integrated_confirmed_long_without_source_market",
        "integrated_early_long_without_fresh_strong_source",
        "integrated_fade_without_crowding_exhaustion",
        "integrated_risk_without_evidence",
        "integrated_market_anomaly_confirmed",
        "integrated_cryptopanic_confirmed",
        "integrated_major_pair_early_long",
        "integrated_input_manifest_missing",
        "integrated_source_coverage_json_missing",
        "integrated_candidate_core_missing",
        "integrated_candidate_core_opportunity_type_mismatch",
        "integrated_candidate_core_market_state_mismatch",
        "integrated_candidate_core_route_level_mismatch",
        "integrated_candidate_core_reason_code_loss",
        "integrated_candidate_core_source_url_loss",
        "integrated_candidate_core_official_event_loss",
        "integrated_candidate_core_scheduled_event_loss",
        "integrated_candidate_core_unlock_event_loss",
        "integrated_candidate_core_derivatives_loss",
        "integrated_candidate_card_opportunity_type_mismatch",
        "integrated_candidate_card_why_now_mismatch",
        "integrated_major_pair_card_early_long",
        "integrated_card_generic_lane_override",
        "card_opportunity_lane_core_mismatch",
        "integrated_candidate_card_official_event_missing",
        "integrated_candidate_card_source_url_missing",
        "integrated_candidate_core_crowding_metadata_loss",
        "derivatives_card_metric_claim_without_data",
        "integrated_coinalyze_crowding_card_missing",
        "integrated_coinalyze_loaded_no_rows_attached",
        "integrated_coinalyze_missing_skip_reason",
        "integrated_coinalyze_stale_loaded_without_warning",
        "integrated_coinalyze_loaded_from_stale_namespace",
        "integrated_fade_card_crowding_unknown",
        "integrated_fade_card_missing_disclaimer",
        "integrated_confirmed_long_crowding_warning_hidden",
        "integrated_market_confirmation_display_contradiction",
        "integrated_derivatives_display_contradiction",
        "integrated_manifest_mixed_timestamp_pair",
        "integrated_core_silent_upgrade",
        "integrated_diagnostic_visible_in_default_operator_section",
        "integrated_preview_missing_disclaimer",
        "integrated_delivery_ledger_missing",
        "integrated_preview_lane_mismatch",
        "integrated_delivery_missing_disclaimer",
        "integrated_delivery_sent_in_no_send",
        "integrated_delivery_side_effect_flag",
        "integrated_delivery_missing_skip_reasons",
        "integrated_delivery_card_path_absolute",
        "integrated_delivery_card_path_not_rendered",
        "integrated_operator_markdown_absolute_path",
        "operator_structured_path_absolute",
        "integrated_legacy_preview_alerts_wording",
        "integrated_manifest_daily_brief_unavailable",
        "integrated_outcome_missing_for_candidate",
        "integrated_outcome_side_effect_flag",
        "integrated_outcome_schema_missing",
        "integrated_outcome_missing_identity",
        "integrated_outcome_returns_without_price",
        "integrated_outcome_diagnostic_in_performance",
        "integrated_calibration_diagnostic_in_main_priors",
        "integrated_calibration_prior_safety_missing",
        "integrated_calibration_legacy_alias_top_level",
        "integrated_outcome_return_double_scaled",
        "integrated_outcome_missing_data_unlabeled",
        "integrated_outcome_thesis_move_missing",
        "integrated_outcome_card_thesis_interpretation_missing",
        "integrated_outcome_card_trade_wording",
        "integrated_created_normal_rsi_signal",
        "integrated_created_triggered_fade",
    ):
        count = integrated_conflicts.get(key, 0)
        if count:
            message = f"{key}={count}"
            (blockers if strict else warnings).append(message)
    if source_coverage_report_conflicts["source_coverage_report_missing"]:
        warnings.append(
            "source_coverage_report_missing="
            f"{source_coverage_report_conflicts['source_coverage_report_missing']}"
        )
    if source_coverage_report_conflicts["source_coverage_provider_status_unknown"]:
        warnings.append(
            "source_coverage_provider_status_unknown="
            f"{source_coverage_report_conflicts['source_coverage_provider_status_unknown']}"
        )
    if source_coverage_report_conflicts["source_coverage_provider_marked_healthy_without_observation"]:
        message = (
            "source_coverage_provider_marked_healthy_without_observation="
            f"{source_coverage_report_conflicts['source_coverage_provider_marked_healthy_without_observation']}"
        )
        (blockers if strict else warnings).append(message)
    if source_coverage_report_conflicts["source_coverage_category_priority_missing"]:
        warnings.append(
            "source_coverage_category_priority_missing="
            f"{source_coverage_report_conflicts['source_coverage_category_priority_missing']}"
        )
    if source_coverage_report_conflicts.get("source_coverage_readiness_link_missing", 0):
        warnings.append(
            "source_coverage_readiness_link_missing="
            f"{source_coverage_report_conflicts['source_coverage_readiness_link_missing']}"
        )
    if source_coverage_report_conflicts["source_coverage_context_provider_ranked_above_lane_critical"]:
        message = (
            "source_coverage_context_provider_ranked_above_lane_critical="
            f"{source_coverage_report_conflicts['source_coverage_context_provider_ranked_above_lane_critical']}"
        )
        (blockers if strict else warnings).append(message)
    if source_coverage_report_conflicts["source_coverage_coinalyze_missing_linked_artifact"]:
        message = (
            "source_coverage_coinalyze_missing_linked_artifact="
            f"{source_coverage_report_conflicts['source_coverage_coinalyze_missing_linked_artifact']}"
        )
        (blockers if strict else warnings).append(message)
    if source_coverage_report_conflicts["source_coverage_bybit_announcements_missing_linked_artifact"]:
        message = (
            "source_coverage_bybit_announcements_missing_linked_artifact="
            f"{source_coverage_report_conflicts['source_coverage_bybit_announcements_missing_linked_artifact']}"
        )
        (blockers if strict else warnings).append(message)
    if source_coverage_report_conflicts["source_coverage_unlock_calendar_missing_linked_artifact"]:
        message = (
            "source_coverage_unlock_calendar_missing_linked_artifact="
            f"{source_coverage_report_conflicts['source_coverage_unlock_calendar_missing_linked_artifact']}"
        )
        (blockers if strict else warnings).append(message)
    if live_provider_readiness_conflicts["live_provider_readiness_missing"]:
        warnings.append(
            "live_provider_readiness_missing="
            f"{live_provider_readiness_conflicts['live_provider_readiness_missing']}"
        )
    for key in (
        "live_provider_readiness_secret_leak",
        "live_provider_readiness_live_calls_allowed_in_smoke",
        "live_provider_readiness_configured_missing_env",
    ):
        count = live_provider_readiness_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    for key in (
        "coinalyze_preflight_secret_leak",
        "coinalyze_preflight_live_call_allowed_in_smoke",
        "coinalyze_preflight_configured_missing_env",
        "coinalyze_preflight_ready_without_request_ledger",
        "coinalyze_preflight_missing_fixture_parser_status",
        "coinalyze_preflight_forbidden_side_effect_claim",
        "coinalyze_rehearsal_secret_leak",
        "coinalyze_rehearsal_live_without_ledger",
        "coinalyze_rehearsal_live_call_allowed_in_smoke",
        "coinalyze_rehearsal_live_without_explicit_allow",
        "coinalyze_rehearsal_request_budget_exceeded",
        "coinalyze_rehearsal_success_without_derivatives_state",
        "coinalyze_rehearsal_success_without_crowding_candidates",
        "coinalyze_provider_health_healthy_without_successful_ledger",
        "coinalyze_rehearsal_forbidden_side_effect_claim",
        "coinalyze_supported_metric_implemented_missing_state",
    ):
        count = coinalyze_preflight_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    for key in (
        "bybit_announcements_preflight_secret_leak",
        "bybit_announcements_preflight_live_call_allowed_in_smoke",
        "bybit_announcements_preflight_missing_fixture_parser_status",
        "bybit_announcements_rehearsal_secret_leak",
        "bybit_announcements_rehearsal_live_without_ledger",
        "bybit_announcements_rehearsal_live_without_explicit_allow",
        "bybit_announcements_rehearsal_unsupported_params",
        "bybit_announcements_rehearsal_forbidden_side_effect_claim",
    ):
        count = bybit_announcements_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    for key in (
        "unlock_calendar_preflight_secret_leak",
        "unlock_calendar_preflight_live_without_ledger",
        "unlock_calendar_preflight_live_call_allowed_in_smoke",
        "unlock_calendar_preflight_missing_fixture_parser_status",
        "unlock_calendar_preflight_forbidden_side_effect_claim",
    ):
        count = unlock_calendar_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        (blockers if strict else warnings).append(message)
    if source_coverage_conflicts["source_pack_provider_status_missing"]:
        warnings.append(
            "source_pack_provider_status_missing="
            f"{source_coverage_conflicts['source_pack_provider_status_missing']}"
        )
    if source_coverage_conflicts["missing_provider_recommendations_missing"]:
        warnings.append(
            "missing_provider_recommendations_missing="
            f"{source_coverage_conflicts['missing_provider_recommendations_missing']}"
        )
    if source_coverage_conflicts["degraded_provider_absence_marked_meaningful"]:
        message = (
            "degraded_provider_absence_marked_meaningful="
            f"{source_coverage_conflicts['degraded_provider_absence_marked_meaningful']}"
        )
        (blockers if strict else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_configured_but_not_observed"]:
        warnings.append(
            "cryptopanic_configured_but_not_observed="
            f"{cryptopanic_conflicts['cryptopanic_configured_but_not_observed']}"
        )
    if cryptopanic_conflicts["cryptopanic_used_but_no_source_coverage_entry"]:
        message = (
            "cryptopanic_used_but_no_source_coverage_entry="
            f"{cryptopanic_conflicts['cryptopanic_used_but_no_source_coverage_entry']}"
        )
        (blockers if strict else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_accepted_evidence_missing_from_card"]:
        message = (
            "cryptopanic_accepted_evidence_missing_from_card="
            f"{cryptopanic_conflicts['cryptopanic_accepted_evidence_missing_from_card']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_rejected_only_promoted"]:
        message = (
            "cryptopanic_rejected_only_promoted="
            f"{cryptopanic_conflicts['cryptopanic_rejected_only_promoted']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_token_printed_or_unredacted"]:
        message = (
            "cryptopanic_token_printed_or_unredacted="
            f"{cryptopanic_conflicts['cryptopanic_token_printed_or_unredacted']}"
        )
        (blockers if strict else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_growth_unsupported_param_used"]:
        message = (
            "cryptopanic_growth_unsupported_param_used="
            f"{cryptopanic_conflicts['cryptopanic_growth_unsupported_param_used']}"
        )
        (blockers if strict else warnings).append(message)
    for key in (
        "cryptopanic_duplicate_request_key",
        "cryptopanic_invalid_currency_code",
        "cryptopanic_empty_currency_request",
        "cryptopanic_coin_id_sent_as_currency",
        "cryptopanic_status_code_missing_on_http_failure",
        "cryptopanic_body_excerpt_unredacted_token",
    ):
        if cryptopanic_conflicts[key]:
            message = f"{key}={cryptopanic_conflicts[key]}"
            (blockers if strict else warnings).append(message)
    for key in (
        "cryptopanic_all_requests_failed",
        "cryptopanic_json_parse_errors",
        "cryptopanic_configured_but_unusable",
    ):
        if cryptopanic_conflicts[key]:
            message = f"{key}={cryptopanic_conflicts[key]}"
            warnings.append(message)
    if cryptopanic_conflicts["cryptopanic_quota_exceeded"]:
        message = f"cryptopanic_quota_exceeded={cryptopanic_conflicts['cryptopanic_quota_exceeded']}"
        (blockers if strict else warnings).append(message)
    if cryptopanic_conflicts["cryptopanic_request_ledger_missing_when_used"]:
        message = (
            "cryptopanic_request_ledger_missing_when_used="
            f"{cryptopanic_conflicts['cryptopanic_request_ledger_missing_when_used']}"
        )
        (blockers if strict else warnings).append(message)
    for key in (
        "cryptopanic_success_with_backoff_status",
        "cryptopanic_restore_token_recommendation_when_configured",
    ):
        if cryptopanic_conflicts[key]:
            message = f"{key}={cryptopanic_conflicts[key]}"
            (blockers if strict else warnings).append(message)
    if evidence_count_mismatches:
        message = f"evidence_count_mismatch={evidence_count_mismatches}"
        (blockers if strict else warnings).append(message)
    if visible_sector_cores:
        message = f"visible_sector_core_without_config={visible_sector_cores}"
        (blockers if strict else warnings).append(message)
    if duplicate_proxy_cores:
        message = f"duplicate_proxy_core_rows={duplicate_proxy_cores}"
        (blockers if strict else warnings).append(message)
    if visible_missing_targets:
        message = f"visible_core_opportunities_missing_feedback_targets={visible_missing_targets}"
        (blockers if strict and fresh_visible_missing_targets else warnings).append(message)
    if snapshots_missing_core:
        warnings.append(f"alert_snapshots_missing_core_opportunity_id={snapshots_missing_core}")
    if snapshots_missing_feedback:
        message = f"alert_snapshots_missing_feedback_target={snapshots_missing_feedback}"
        (blockers if strict else warnings).append(message)
    if inbox_core_missing_card:
        message = f"inbox_core_item_missing_card={inbox_core_missing_card}"
        (blockers if strict and core_store_available else warnings).append(message)
    if inbox_core_alert_target:
        message = (
            "inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists="
            f"{inbox_core_alert_target}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if inbox_diag_visible_default:
        message = f"inbox_diagnostic_snapshot_visible_by_default={inbox_diag_visible_default}"
        (blockers if strict else warnings).append(message)
    if audit_primary_not_canonical:
        message = f"audit_primary_snapshot_not_canonical_when_canonical_exists={audit_primary_not_canonical}"
        (blockers if strict and core_store_available else warnings).append(message)
    if diagnostic_snapshots_missing_feedback:
        warnings.append(
            "feedback_readiness_counts_diagnostic_as_required="
            f"{diagnostic_snapshots_missing_feedback}"
        )
    if alerts and not card_count and any(str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} for row in alerts):
        warnings.append("high-priority/triggered snapshots exist but no research cards were found")
    research_review_enabled_but_lane_missing = 0
    research_review_candidates_without_delivery = 0
    if latest_run:
        rr_enabled = bool(latest_run.get("research_review_digest_enabled"))
        rr_candidates = _as_int(latest_run.get("research_review_digest_candidates"))
        rr_would_send = _as_int(latest_run.get("research_review_digest_would_send"))
        latest_lanes = {
            str(row.get("lane") or "")
            for row in delivery_rows
            if isinstance(row, Mapping)
            and latest_run_id
            and str(row.get("run_id") or "") == str(latest_run_id)
        }
        if rr_enabled and (rr_candidates or rr_would_send) and "research_review_digest" not in latest_lanes:
            research_review_enabled_but_lane_missing = 1
            if rr_candidates:
                research_review_candidates_without_delivery = 1
    if research_review_enabled_but_lane_missing:
        message = "research_review_digest_enabled_but_lane_missing=1"
        (blockers if strict else warnings).append(message)
    if research_review_candidates_without_delivery:
        message = "research_review_digest_candidates_without_delivery=1"
        (blockers if strict else warnings).append(message)
    delivery_summary = _delivery.summarize_delivery_rows([row for row in delivery_rows if isinstance(row, Mapping)])
    if delivery_summary.failed:
        warnings.append(
            f"notification deliveries failed: {delivery_summary.failed} failed delivery row(s) for this profile/namespace"
        )
    delivery_conflicts = _notification_delivery_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        core_rows_by_id=core_rows_by_id,
        latest_run_id=latest_run_id,
        strict_scope=effective_delivery_scope,
    )
    preview_conflicts = _notification_preview_consistency_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        latest_run=latest_run,
        core_rows=core_rows,
        latest_run_id=latest_run_id,
    )
    if delivery_conflicts["delivery_identity_mismatch_core_store"]:
        message = (
            "delivery_identity_mismatch_core_store="
            f"{delivery_conflicts['delivery_identity_mismatch_core_store']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_core_id_missing"]:
        message = f"delivery_core_id_missing={delivery_conflicts['delivery_core_id_missing']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_feedback_target_missing"]:
        message = f"delivery_feedback_target_missing={delivery_conflicts['delivery_feedback_target_missing']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_card_path_missing"]:
        message = f"delivery_card_path_missing={delivery_conflicts['delivery_card_path_missing']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_alert_id_not_canonical"]:
        message = (
            "delivery_alert_id_not_canonical="
            f"{delivery_conflicts['delivery_alert_id_not_canonical']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_status_missing"]:
        message = f"delivery_status_missing={delivery_conflicts['delivery_status_missing']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_status_detail_missing"]:
        message = (
            "delivery_status_detail_missing="
            f"{delivery_conflicts['delivery_status_detail_missing']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_mode_missing"]:
        message = f"delivery_mode_missing={delivery_conflicts['delivery_mode_missing']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_state_inconsistent"]:
        message = f"delivery_state_inconsistent={delivery_conflicts['delivery_state_inconsistent']}"
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_would_send_sent_failed_inconsistent"]:
        message = (
            "delivery_would_send_sent_failed_inconsistent="
            f"{delivery_conflicts['delivery_would_send_sent_failed_inconsistent']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["digest_item_without_live_confirmation"]:
        message = (
            "digest_item_without_live_confirmation="
            f"{delivery_conflicts['digest_item_without_live_confirmation']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["digest_item_rejected_results_only"]:
        message = (
            "digest_item_rejected_results_only="
            f"{delivery_conflicts['digest_item_rejected_results_only']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["strategic_broad_asset_digest_without_confirmation"]:
        message = (
            "strategic_broad_asset_digest_without_confirmation="
            f"{delivery_conflicts['strategic_broad_asset_digest_without_confirmation']}"
        )
        (blockers if strict else warnings).append(message)
    for key in (
        "unconfirmed_narrative_daily_digest",
        "single_source_no_market_fan_token_digest",
    ):
        if delivery_conflicts[key]:
            message = f"{key}={delivery_conflicts[key]}"
            (blockers if strict else warnings).append(message)
    if delivery_conflicts["telegram_message_contains_absolute_path"]:
        message = (
            "telegram_message_contains_absolute_path="
            f"{delivery_conflicts['telegram_message_contains_absolute_path']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["telegram_message_contains_raw_debug_dump"]:
        message = (
            "telegram_message_contains_raw_debug_dump="
            f"{delivery_conflicts['telegram_message_contains_raw_debug_dump']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["multi_item_delivery_missing_arrays"]:
        message = f"multi_item_delivery_missing_arrays={delivery_conflicts['multi_item_delivery_missing_arrays']}"
        (blockers if strict else warnings).append(message)
    for key in (
        "notification_body_card_mismatch_canonical",
        "notification_body_feedback_mismatch_canonical",
        "research_review_body_uses_hypothesis_target_when_core_exists",
    ):
        if delivery_conflicts[key]:
            message = f"{key}={delivery_conflicts[key]}"
            (blockers if strict else warnings).append(message)
    for key in (
        "research_review_digest_missing_confirmation_label",
        "research_review_digest_contains_strict_alertable",
        "research_review_digest_contains_hard_gated_candidate",
        "research_review_digest_too_many_items",
        "research_review_digest_missing_feedback_target",
        "research_review_digest_skipped_without_reason",
        "research_review_digest_missing_family_summary",
        "research_review_digest_duplicate_visible_family_summary",
        "research_review_digest_absolute_path",
    ):
        if delivery_conflicts[key]:
            message = f"{key}={delivery_conflicts[key]}"
            if key in {
                "research_review_digest_contains_strict_alertable",
                "research_review_digest_contains_hard_gated_candidate",
                "research_review_digest_missing_feedback_target",
                "research_review_digest_skipped_without_reason",
                "research_review_digest_missing_family_summary",
                "research_review_digest_duplicate_visible_family_summary",
                "research_review_digest_absolute_path",
            }:
                (blockers if strict else warnings).append(message)
            else:
                warnings.append(message)
    if delivery_conflicts["notification_preview_missing"]:
        warnings.append(f"notification_preview_missing={delivery_conflicts['notification_preview_missing']}")
    if delivery_conflicts["notification_preview_relpath_missing"]:
        message = (
            "notification_preview_relpath_missing="
            f"{delivery_conflicts['notification_preview_relpath_missing']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["notification_preview_path_unresolvable"]:
        message = (
            "notification_preview_path_unresolvable="
            f"{delivery_conflicts['notification_preview_path_unresolvable']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_run_summary_mismatch"]:
        message = (
            "notification_preview_run_summary_mismatch="
            f"{preview_conflicts['notification_preview_run_summary_mismatch']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_llm_summary_mismatch"]:
        message = (
            "notification_preview_llm_summary_mismatch="
            f"{preview_conflicts['notification_preview_llm_summary_mismatch']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_lane_counts_mismatch"]:
        message = (
            "notification_preview_lane_counts_mismatch="
            f"{preview_conflicts['notification_preview_lane_counts_mismatch']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_core_count_mismatch"]:
        message = (
            "notification_preview_core_count_mismatch="
            f"{preview_conflicts['notification_preview_core_count_mismatch']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_alertable_count_mismatch"]:
        message = (
            "notification_preview_alertable_count_mismatch="
            f"{preview_conflicts['notification_preview_alertable_count_mismatch']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_missing_send_guard_status"]:
        message = (
            "notification_preview_missing_send_guard_status="
            f"{preview_conflicts['notification_preview_missing_send_guard_status']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_send_guard_status_missing"]:
        message = (
            "notification_preview_send_guard_status_missing="
            f"{preview_conflicts['notification_preview_send_guard_status_missing']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_no_send_status_unclear"]:
        message = (
            "notification_preview_no_send_status_unclear="
            f"{preview_conflicts['notification_preview_no_send_status_unclear']}"
        )
        (blockers if strict else warnings).append(message)
    if preview_conflicts["notification_preview_legacy_alerts_wording"]:
        message = (
            "notification_preview_legacy_alerts_wording="
            f"{preview_conflicts['notification_preview_legacy_alerts_wording']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["stale_delivery_identity_missing_core"]:
        warnings.append(
            "stale_delivery_identity_missing_core="
            f"{delivery_conflicts['stale_delivery_identity_missing_core']}"
        )
    if delivery_conflicts["legacy_pre_core_delivery_identity"]:
        warnings.append(
            "legacy_pre_core_delivery_identity="
            f"{delivery_conflicts['legacy_pre_core_delivery_identity']}"
        )
    if delivery_conflicts["stale_delivery_identity_missing_core"] or delivery_conflicts["legacy_pre_core_delivery_identity"]:
        warnings.append(STALE_PRE_CANONICAL_NOTIFICATION_WARNING)
    quality = _quality_missing_summary(
        hypotheses=hypotheses,
        watchlist=watchlist,
        alerts=alerts,
    )
    fresh_missing = (
        quality["fresh_hypothesis_rows_missing_top_level_quality"]
        + quality["fresh_watchlist_rows_missing_top_level_quality"]
        + quality["fresh_alert_rows_missing_top_level_quality"]
    )
    if quality["quality_fields_missing_count"]:
        message = (
            "quality fields missing: "
            f"total={quality['quality_fields_missing_count']} "
            f"hypotheses_missing_verdict={quality['hypothesis_rows_missing_opportunity_verdict']} "
            f"watchlist_missing={quality['watchlist_rows_missing_quality_fields']} "
            f"alerts_missing={quality['alert_rows_missing_quality_fields']}"
            f" fresh_hypotheses_missing_top_level={quality['fresh_hypothesis_rows_missing_top_level_quality']} "
            f"fresh_watchlist_missing_top_level={quality['fresh_watchlist_rows_missing_top_level_quality']} "
            f"fresh_alerts_missing_top_level={quality['fresh_alert_rows_missing_top_level_quality']} "
            f"legacy_quality_missing={quality['legacy_quality_missing_rows']}"
        )
        if fresh_missing:
            (blockers if strict else warnings).append(message)
        else:
            warnings.append(message)
    route_conflict_alerts = _latest_run_rows(alerts, runs)
    route_conflicts = _alertable_quality_route_conflicts(route_conflict_alerts)
    snapshot_core_conflicts = _alert_snapshot_core_conflicts(route_conflict_alerts, core_rows)
    fresh_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=False)
    legacy_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=True)
    missing_final_route = _missing_final_route_rows(route_conflict_alerts)
    fresh_missing_final_route = _missing_final_route_rows(route_conflict_alerts, legacy=False)
    if route_conflicts:
        message = f"alertable_route_conflicts_with_opportunity_level={route_conflicts}"
        warnings.append(message)
    if snapshot_core_conflicts["route_mismatch"]:
        message = f"alert_snapshot_route_mismatch_core_store={snapshot_core_conflicts['route_mismatch']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["level_mismatch"]:
        message = f"alert_snapshot_level_mismatch_core_store={snapshot_core_conflicts['level_mismatch']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["live_confirmation_stale"]:
        message = f"alert_snapshot_live_confirmation_stale={snapshot_core_conflicts['live_confirmation_stale']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["core_resolution_missing"]:
        message = f"alert_snapshot_core_resolution_missing={snapshot_core_conflicts['core_resolution_missing']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["pre_reconciliation_alertable"]:
        warnings.append(
            "alert_snapshot_pre_reconciliation_alertable="
            f"{snapshot_core_conflicts['pre_reconciliation_alertable']}"
        )
    if snapshot_core_conflicts["diagnostic_support_alertable"]:
        message = f"diagnostic_support_snapshot_alertable={snapshot_core_conflicts['diagnostic_support_alertable']}"
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["diagnostic_support_inherits_core_route"]:
        message = (
            "diagnostic_support_snapshot_inherits_core_route="
            f"{snapshot_core_conflicts['diagnostic_support_inherits_core_route']}"
        )
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["duplicate_alertable_snapshot_for_core"]:
        message = (
            "duplicate_alertable_snapshot_for_core="
            f"{snapshot_core_conflicts['duplicate_alertable_snapshot_for_core']}"
        )
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["canonical_snapshot_missing_for_visible_core"]:
        warnings.append(
            "canonical_snapshot_missing_for_visible_core="
            f"{snapshot_core_conflicts['canonical_snapshot_missing_for_visible_core']}"
        )
    if fresh_route_conflicts and strict:
        blockers.append(f"fresh_quality_route_conflict_rows={fresh_route_conflicts}")
    if legacy_route_conflicts:
        message = f"legacy_quality_conflict_rows={legacy_route_conflicts}"
        (blockers if strict and strict_legacy else warnings).append(message)
    if fresh_missing_final_route and strict:
        blockers.append(f"fresh_alert_rows_missing_final_route={fresh_missing_final_route}")
    watchlist_conflicts = _watchlist_quality_state_conflicts(watchlist)
    if watchlist_conflicts["quality_capped_watchlist_rows"]:
        warnings.append(
            f"quality-capped rows present: {watchlist_conflicts['quality_capped_watchlist_rows']}"
        )
    if watchlist_conflicts["non_hypothesis_watchlist_quality_conflicts"]:
        warnings.append(
            "non_hypothesis_watchlist_quality_conflicts="
            f"{watchlist_conflicts['non_hypothesis_watchlist_quality_conflicts']}"
        )
    if watchlist_conflicts["hypothesis_watchlist_quality_conflicts"]:
        warnings.append(
            "hypothesis_watchlist_quality_conflicts="
            f"{watchlist_conflicts['hypothesis_watchlist_quality_conflicts']}"
        )
    if watchlist_conflicts["watchlist_state_conflicts_with_quality"]:
        warnings.append(
            f"watchlist_state_conflicts_with_quality={watchlist_conflicts['watchlist_state_conflicts_with_quality']}"
        )
    if watchlist_conflicts["fresh_uncapped"]:
        message = f"fresh_watchlist_state_conflict_rows={watchlist_conflicts['fresh_uncapped']}"
        (blockers if strict else warnings).append(message)
    if watchlist_conflicts["legacy"]:
        message = f"legacy_watchlist_conflicts={watchlist_conflicts['legacy']}"
        (blockers if strict and strict_legacy else warnings).append(message)
    incident_linkage = _incident_linkage_summary(
        hypotheses=hypotheses,
        watchlist=watchlist,
        alerts=alerts,
        incidents=incidents,
    )
    if incident_linkage["hypothesis_rows_missing_incident_id"]:
        message = f"hypothesis_rows_missing_incident_id={incident_linkage['hypothesis_rows_missing_incident_id']}"
        (blockers if strict and incident_linkage["fresh_missing_hypotheses"] else warnings).append(message)
    if incident_linkage["watchlist_hypothesis_rows_missing_incident_id"]:
        message = (
            "watchlist_hypothesis_rows_missing_incident_id="
            f"{incident_linkage['watchlist_hypothesis_rows_missing_incident_id']}"
        )
        (blockers if strict and incident_linkage["fresh_missing_watchlist"] else warnings).append(message)
    if incident_linkage["alert_hypothesis_rows_missing_incident_id"]:
        message = f"alert_hypothesis_rows_missing_incident_id={incident_linkage['alert_hypothesis_rows_missing_incident_id']}"
        (blockers if strict and incident_linkage["fresh_missing_alerts"] else warnings).append(message)
    if incident_linkage["incident_rows_without_linked_hypotheses"]:
        warnings.append(
            f"incident_rows_without_linked_hypotheses={incident_linkage['incident_rows_without_linked_hypotheses']}"
        )
    if incident_linkage["incident_rows_without_linked_watchlist"]:
        warnings.append(
            f"incident_rows_without_linked_watchlist={incident_linkage['incident_rows_without_linked_watchlist']}"
        )
    if incident_linkage["diagnostic_incident_rows"]:
        warnings.append(f"diagnostic_incident_rows={incident_linkage['diagnostic_incident_rows']}")
    if incident_linkage["raw_observation_incident_rows"]:
        warnings.append(f"raw_observation_incident_rows={incident_linkage['raw_observation_incident_rows']}")
    if incident_linkage["external_context_incident_rows"]:
        warnings.append(f"external_context_incident_rows={incident_linkage['external_context_incident_rows']}")
    if incident_linkage["rejected_incident_rows"]:
        warnings.append(f"rejected_incident_rows={incident_linkage['rejected_incident_rows']}")
    if incident_linkage["canonical_unlinked_incidents"]:
        warnings.append(f"canonical_unlinked_incidents={incident_linkage['canonical_unlinked_incidents']}")
    if incident_linkage["active_incident_without_qualified_link"]:
        message = f"active_incident_without_qualified_link={incident_linkage['active_incident_without_qualified_link']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["linked_incident_without_qualified_link"]:
        warnings.append(f"linked_incident_without_qualified_link={incident_linkage['linked_incident_without_qualified_link']}")
    if incident_linkage["weak_unqualified_incident_links"]:
        warnings.append(f"weak_unqualified_incident_links={incident_linkage['weak_unqualified_incident_links']}")
    if incident_linkage["quality_blocked_links_present"]:
        warnings.append(f"quality_blocked_links_present={incident_linkage['quality_blocked_links_present']}")
    if incident_linkage["quality_blocked_links_promoting_incident"]:
        message = f"quality_blocked_links_promoting_incident={incident_linkage['quality_blocked_links_promoting_incident']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["incident_relevance_missing"]:
        message = f"incident_relevance_missing={incident_linkage['incident_relevance_missing']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["garbage_primary_subject_incidents"]:
        warnings.append(f"garbage_primary_subject_incidents={incident_linkage['garbage_primary_subject_incidents']}")
    if incident_linkage["invalid_canonical_incident_rows"]:
        message = f"invalid_canonical_incident_rows={incident_linkage['invalid_canonical_incident_rows']}"
        (blockers if strict else warnings).append(message)
    status = "BLOCKED" if blockers else ("WARN" if warnings else "OK")
    return EventAlphaArtifactDoctorResult(
        status=status,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_rows=len(runs),
        alert_rows=len(alerts),
        feedback_rows=len(feedback),
        outcome_rows=len(outcomes),
        card_files=card_count,
        research_card_files=card_count,
        research_card_index_present=index_present,
        cards_missing_lineage=cards_missing_lineage,
        cards_missing_feedback_target=cards_missing_feedback_target,
        visible_core_opportunities=len(visible_core),
        core_opportunity_store_rows=len(core_rows),
        visible_core_opportunities_missing_store_rows=visible_missing_store_rows,
        duplicate_core_opportunity_store_rows=duplicate_store_rows,
        core_opportunity_store_rows_missing_card_path=store_rows_missing_card_path,
        visible_core_opportunities_missing_cards=visible_missing_cards,
        visible_core_opportunities_missing_feedback_targets=visible_missing_targets,
        alert_snapshots_missing_core_opportunity_id=snapshots_missing_core,
        alert_snapshots_missing_feedback_target=snapshots_missing_feedback,
        core_cards_missing_store_row=core_cards_missing_store,
        visible_core_cards_missing_store_row=visible_core_cards_missing_store,
        orphan_core_opportunity_cards=orphan_core_cards,
        diagnostic_snapshots_with_fake_core_id=diagnostic_fake_core,
        alert_snapshots_core_id_missing_from_store=snapshot_core_missing_store,
        evidence_acquisition_core_id_missing_from_store=acquisition_core_missing_store,
        card_primary_fields_mismatch_core_store=card_primary_mismatches,
        card_evidence_acquisition_count_mismatch=card_acquisition_mismatches,
        evidence_acquisition_stale_validated_digest=acquisition_final_conflicts["evidence_acquisition_stale_validated_digest"],
        card_source_pack_mismatch_core_acquisition=card_source_pack_mismatches,
        card_primary_section_contains_support_row_blockers=card_support_blockers,
        card_upgrade_text_inconsistent_with_final_level=card_upgrade_inconsistent,
        audit_primary_impact_path_mismatch_core=audit_impact_mismatch,
        audit_source_pack_mismatch_core=audit_source_pack_mismatch,
        card_market_confirmation_missing_but_core_has_market_confirmation=card_market_missing,
        card_latest_source_unknown_but_accepted_evidence_exists=card_source_unknown,
        quality_review_promoted_core_in_weak_section=promoted_core_in_weak,
        market_freshness_contradictory_summary=market_freshness_contradictions,
        quality_review_market_freshness_contradiction=market_freshness_contradictions,
        upgrade_candidates_include_high_priority=upgrade_high_priority,
        daily_brief_card_group_mismatch_with_index=card_group_mismatches,
        daily_brief_missing_selected_run=daily_brief_conflicts["daily_brief_missing_selected_run"],
        daily_brief_selected_run_mismatch=daily_brief_conflicts["daily_brief_selected_run_mismatch"],
        daily_brief_core_count_mismatch_store=daily_brief_conflicts["daily_brief_core_count_mismatch_store"],
        daily_brief_research_review_lane_missing=daily_brief_conflicts["daily_brief_research_review_lane_missing"],
        daily_brief_source_coverage_path_missing=daily_brief_conflicts["daily_brief_source_coverage_path_missing"],
        daily_brief_coinalyze_source_coverage_mismatch=daily_brief_conflicts[
            "daily_brief_coinalyze_source_coverage_mismatch"
        ],
        core_route_conflicts_with_opportunity_level=core_route_conflicts,
        live_validated_without_confirmation=live_confirmation_conflicts["live_validated_without_confirmation"],
        live_sector_digest_without_asset=live_confirmation_conflicts["live_sector_digest_without_asset"],
        live_rejected_results_promoted=live_confirmation_conflicts["live_rejected_results_promoted"],
        live_skipped_budget_promoted=live_confirmation_conflicts["live_skipped_budget_promoted"],
        raw_core_validated_without_confirmation=raw_core_conflicts["raw_core_validated_without_confirmation"],
        raw_core_source_only_narrative_validated=raw_core_conflicts["raw_core_source_only_narrative_validated"],
        raw_core_cryptopanic_tag_only_direct_path_confirmed=raw_core_conflicts["raw_core_cryptopanic_tag_only_direct_path_confirmed"],
        raw_core_suppressed_duplicate_validated_stale=raw_core_conflicts["raw_core_suppressed_duplicate_validated_stale"],
        confirmed_long_without_source_market=opportunity_lane_conflicts["confirmed_long_without_source_market"],
        fade_short_without_crowding_exhaustion=opportunity_lane_conflicts["fade_short_without_crowding_exhaustion"],
        early_long_without_fresh_strong_source=opportunity_lane_conflicts["early_long_without_fresh_strong_source"],
        risk_only_missing_evidence_only=opportunity_lane_conflicts["risk_only_missing_evidence_only"],
        cryptopanic_only_narrative_confirmed_lane=opportunity_lane_conflicts["cryptopanic_only_narrative_confirmed_lane"],
        diagnostic_visible_default_operator_lane=opportunity_lane_conflicts["diagnostic_visible_default_operator_lane"],
        core_missing_market_state_snapshot=opportunity_lane_conflicts["core_missing_market_state_snapshot"],
        market_state_return_unit_missing=opportunity_lane_conflicts["market_state_return_unit_missing"],
        market_state_possible_double_scaled=opportunity_lane_conflicts["market_state_possible_double_scaled"],
        market_state_lane_possible_double_scaled=opportunity_lane_conflicts["market_state_lane_possible_double_scaled"],
        market_anomaly_rows=len(market_anomalies),
        market_anomaly_missing_market_state_snapshot=market_anomaly_conflicts["market_anomaly_missing_market_state_snapshot"],
        market_anomaly_missing_market_state_class=market_anomaly_conflicts["market_anomaly_missing_market_state_class"],
        market_anomaly_confirmed_breakout_missing_evidence=market_anomaly_conflicts["market_anomaly_confirmed_breakout_missing_evidence"],
        market_anomaly_suspicious_illiquid_promoted_confirmed=market_anomaly_conflicts["market_anomaly_suspicious_illiquid_promoted_confirmed"],
        market_anomaly_created_alert_rows=market_anomaly_conflicts["market_anomaly_created_alert_rows"],
        market_anomaly_missing_freshness_status=market_anomaly_conflicts["market_anomaly_missing_freshness_status"],
        market_anomaly_needs_search_without_plan=market_anomaly_conflicts["market_anomaly_needs_search_without_plan"],
        official_exchange_candidate_rows=len(official_exchange_candidates),
        official_exchange_candidate_missing_source_fields=official_exchange_conflicts["official_exchange_candidate_missing_source_fields"],
        official_exchange_listing_without_official_source=official_exchange_conflicts["official_exchange_listing_without_official_source"],
        official_exchange_secret_leak=official_exchange_conflicts["official_exchange_secret_leak"],
        official_exchange_delisting_long_research=official_exchange_conflicts["official_exchange_delisting_long_research"],
        official_exchange_quote_asset_misclassified=official_exchange_conflicts["official_exchange_quote_asset_misclassified"],
        official_exchange_major_pair_noise_promoted_early_long=official_exchange_conflicts[
            "official_exchange_major_pair_noise_promoted_early_long"
        ],
        official_exchange_created_alert_rows=official_exchange_conflicts["official_exchange_created_alert_rows"],
        official_exchange_activation_missing_shared_schema=official_exchange_activation_conflicts[
            "official_exchange_activation_missing_shared_schema"
        ],
        official_exchange_activation_live_without_ledger=official_exchange_activation_conflicts[
            "official_exchange_activation_live_without_ledger"
        ],
        official_exchange_activation_signed_listener_secret_leak=official_exchange_activation_conflicts[
            "official_exchange_activation_signed_listener_secret_leak"
        ],
        official_exchange_activation_forbidden_side_effect_claim=official_exchange_activation_conflicts[
            "official_exchange_activation_forbidden_side_effect_claim"
        ],
        instrument_resolution_missing_canonical_id_when_fixture_has_it=instrument_resolution_conflicts[
            "instrument_resolution_missing_canonical_id_when_fixture_has_it"
        ],
        instrument_resolution_quote_asset_misclassified=instrument_resolution_conflicts[
            "instrument_resolution_quote_asset_misclassified"
        ],
        instrument_resolution_sector_visible_as_tradable=instrument_resolution_conflicts[
            "instrument_resolution_sector_visible_as_tradable"
        ],
        instrument_resolution_coinalyze_symbol_unlinked=instrument_resolution_conflicts[
            "instrument_resolution_coinalyze_symbol_unlinked"
        ],
        scheduled_catalyst_rows=len(scheduled_catalysts),
        unlock_candidate_rows=len(unlock_candidates),
        derivatives_state_rows=len(derivatives_state),
        fade_review_candidate_rows=len(fade_review_candidates),
        unlock_without_structured_evidence=scheduled_conflicts["unlock_without_structured_evidence"],
        unlock_missing_event_time=scheduled_conflicts["unlock_missing_event_time"],
        unlock_promoted_without_size_metrics=scheduled_conflicts["unlock_promoted_without_size_metrics"],
        media_unlock_promoted_structured=scheduled_conflicts["media_unlock_promoted_structured"],
        stale_completed_catalyst_upcoming=scheduled_conflicts["stale_completed_catalyst_upcoming"],
        calendar_event_missing_source_url=scheduled_conflicts["calendar_event_missing_source_url"],
        cryptopanic_unlock_proof=scheduled_conflicts["cryptopanic_unlock_proof"],
        scheduled_catalyst_created_alert_rows=scheduled_conflicts["scheduled_catalyst_created_alert_rows"],
        fade_review_without_completed_move=derivatives_conflicts["fade_review_without_completed_move"],
        fade_review_without_crowding_exhaustion=derivatives_conflicts["fade_review_without_crowding_exhaustion"],
        fade_review_created_triggered_fade=derivatives_conflicts["fade_review_created_triggered_fade"],
        fade_review_created_normal_rsi_signal=derivatives_conflicts["fade_review_created_normal_rsi_signal"],
        fade_review_notification_missing_disclaimer=derivatives_conflicts["fade_review_notification_missing_disclaimer"],
        derivatives_artifact_secret_leak=derivatives_conflicts["derivatives_artifact_secret_leak"],
        derivatives_state_missing_freshness_status=derivatives_conflicts["derivatives_state_missing_freshness_status"],
        derivatives_metric_claim_implemented_missing=derivatives_conflicts["derivatives_metric_claim_implemented_missing"],
        derivatives_unit_metadata_missing=derivatives_conflicts["derivatives_unit_metadata_missing"],
        stale_derivatives_snapshot_promoted_fade_review=derivatives_conflicts["stale_derivatives_snapshot_promoted_fade_review"],
        confirmed_long_crowded_without_warning=derivatives_conflicts["confirmed_long_crowded_without_warning"],
        integrated_radar_candidate_rows=len(integrated_candidates),
        integrated_candidate_missing_opportunity_type=integrated_conflicts["integrated_candidate_missing_opportunity_type"],
        integrated_candidate_missing_market_state_snapshot=integrated_conflicts["integrated_candidate_missing_market_state_snapshot"],
        integrated_confirmed_long_without_source_market=integrated_conflicts["integrated_confirmed_long_without_source_market"],
        integrated_early_long_without_fresh_strong_source=integrated_conflicts["integrated_early_long_without_fresh_strong_source"],
        integrated_fade_without_crowding_exhaustion=integrated_conflicts["integrated_fade_without_crowding_exhaustion"],
        integrated_risk_without_evidence=integrated_conflicts["integrated_risk_without_evidence"],
        integrated_market_anomaly_confirmed=integrated_conflicts["integrated_market_anomaly_confirmed"],
        integrated_cryptopanic_confirmed=integrated_conflicts["integrated_cryptopanic_confirmed"],
        integrated_major_pair_early_long=integrated_conflicts["integrated_major_pair_early_long"],
        integrated_input_manifest_missing=integrated_conflicts["integrated_input_manifest_missing"],
        integrated_source_coverage_json_missing=integrated_conflicts["integrated_source_coverage_json_missing"],
        integrated_candidate_core_missing=integrated_conflicts["integrated_candidate_core_missing"],
        integrated_candidate_core_opportunity_type_mismatch=integrated_conflicts["integrated_candidate_core_opportunity_type_mismatch"],
        integrated_candidate_core_market_state_mismatch=integrated_conflicts["integrated_candidate_core_market_state_mismatch"],
        integrated_candidate_core_route_level_mismatch=integrated_conflicts["integrated_candidate_core_route_level_mismatch"],
        integrated_candidate_core_reason_code_loss=integrated_conflicts["integrated_candidate_core_reason_code_loss"],
        integrated_candidate_core_source_url_loss=integrated_conflicts["integrated_candidate_core_source_url_loss"],
        integrated_candidate_core_official_event_loss=integrated_conflicts["integrated_candidate_core_official_event_loss"],
        integrated_candidate_core_scheduled_event_loss=integrated_conflicts["integrated_candidate_core_scheduled_event_loss"],
        integrated_candidate_core_unlock_event_loss=integrated_conflicts["integrated_candidate_core_unlock_event_loss"],
        integrated_candidate_core_derivatives_loss=integrated_conflicts["integrated_candidate_core_derivatives_loss"],
        integrated_candidate_card_opportunity_type_mismatch=integrated_conflicts["integrated_candidate_card_opportunity_type_mismatch"],
        integrated_candidate_card_why_now_mismatch=integrated_conflicts["integrated_candidate_card_why_now_mismatch"],
        integrated_major_pair_card_early_long=integrated_conflicts["integrated_major_pair_card_early_long"],
        integrated_card_generic_lane_override=integrated_conflicts["integrated_card_generic_lane_override"],
        card_opportunity_lane_core_mismatch=integrated_conflicts["card_opportunity_lane_core_mismatch"],
        integrated_candidate_card_official_event_missing=integrated_conflicts["integrated_candidate_card_official_event_missing"],
        integrated_candidate_card_source_url_missing=integrated_conflicts["integrated_candidate_card_source_url_missing"],
        integrated_candidate_core_crowding_metadata_loss=integrated_conflicts["integrated_candidate_core_crowding_metadata_loss"],
        derivatives_card_metric_claim_without_data=integrated_conflicts["derivatives_card_metric_claim_without_data"],
        integrated_coinalyze_crowding_card_missing=integrated_conflicts["integrated_coinalyze_crowding_card_missing"],
        integrated_coinalyze_loaded_no_rows_attached=integrated_conflicts["integrated_coinalyze_loaded_no_rows_attached"],
        integrated_coinalyze_missing_skip_reason=integrated_conflicts["integrated_coinalyze_missing_skip_reason"],
        integrated_coinalyze_stale_loaded_without_warning=integrated_conflicts["integrated_coinalyze_stale_loaded_without_warning"],
        integrated_coinalyze_loaded_from_stale_namespace=integrated_conflicts["integrated_coinalyze_loaded_from_stale_namespace"],
        integrated_fade_card_crowding_unknown=integrated_conflicts["integrated_fade_card_crowding_unknown"],
        integrated_fade_card_missing_disclaimer=integrated_conflicts["integrated_fade_card_missing_disclaimer"],
        integrated_confirmed_long_crowding_warning_hidden=integrated_conflicts["integrated_confirmed_long_crowding_warning_hidden"],
        integrated_market_confirmation_display_contradiction=integrated_conflicts["integrated_market_confirmation_display_contradiction"],
        integrated_derivatives_display_contradiction=integrated_conflicts["integrated_derivatives_display_contradiction"],
        integrated_manifest_mixed_timestamp_pair=integrated_conflicts["integrated_manifest_mixed_timestamp_pair"],
        integrated_core_silent_upgrade=integrated_conflicts["integrated_core_silent_upgrade"],
        integrated_diagnostic_visible_in_default_operator_section=integrated_conflicts["integrated_diagnostic_visible_in_default_operator_section"],
        integrated_preview_missing_disclaimer=integrated_conflicts["integrated_preview_missing_disclaimer"],
        integrated_delivery_ledger_missing=integrated_conflicts["integrated_delivery_ledger_missing"],
        integrated_preview_lane_mismatch=integrated_conflicts["integrated_preview_lane_mismatch"],
        integrated_delivery_missing_disclaimer=integrated_conflicts["integrated_delivery_missing_disclaimer"],
        integrated_delivery_sent_in_no_send=integrated_conflicts["integrated_delivery_sent_in_no_send"],
        integrated_delivery_side_effect_flag=integrated_conflicts["integrated_delivery_side_effect_flag"],
        integrated_delivery_missing_skip_reasons=integrated_conflicts["integrated_delivery_missing_skip_reasons"],
        integrated_delivery_card_path_absolute=integrated_conflicts["integrated_delivery_card_path_absolute"],
        integrated_delivery_card_path_not_rendered=integrated_conflicts["integrated_delivery_card_path_not_rendered"],
        integrated_operator_markdown_absolute_path=integrated_conflicts["integrated_operator_markdown_absolute_path"],
        operator_structured_path_absolute=integrated_conflicts["operator_structured_path_absolute"],
        integrated_legacy_preview_alerts_wording=integrated_conflicts["integrated_legacy_preview_alerts_wording"],
        integrated_manifest_daily_brief_unavailable=integrated_conflicts["integrated_manifest_daily_brief_unavailable"],
        integrated_outcome_missing_for_candidate=integrated_conflicts["integrated_outcome_missing_for_candidate"],
        integrated_outcome_side_effect_flag=integrated_conflicts["integrated_outcome_side_effect_flag"],
        integrated_outcome_schema_missing=integrated_conflicts["integrated_outcome_schema_missing"],
        integrated_outcome_missing_identity=integrated_conflicts["integrated_outcome_missing_identity"],
        integrated_outcome_returns_without_price=integrated_conflicts["integrated_outcome_returns_without_price"],
        integrated_outcome_diagnostic_in_performance=integrated_conflicts["integrated_outcome_diagnostic_in_performance"],
        integrated_calibration_diagnostic_in_main_priors=integrated_conflicts["integrated_calibration_diagnostic_in_main_priors"],
        integrated_calibration_prior_safety_missing=integrated_conflicts["integrated_calibration_prior_safety_missing"],
        integrated_calibration_legacy_alias_top_level=integrated_conflicts["integrated_calibration_legacy_alias_top_level"],
        integrated_outcome_return_double_scaled=integrated_conflicts["integrated_outcome_return_double_scaled"],
        integrated_outcome_missing_data_unlabeled=integrated_conflicts["integrated_outcome_missing_data_unlabeled"],
        integrated_outcome_thesis_move_missing=integrated_conflicts["integrated_outcome_thesis_move_missing"],
        integrated_outcome_card_thesis_interpretation_missing=integrated_conflicts[
            "integrated_outcome_card_thesis_interpretation_missing"
        ],
        integrated_outcome_card_trade_wording=integrated_conflicts["integrated_outcome_card_trade_wording"],
        integrated_created_normal_rsi_signal=integrated_conflicts["integrated_created_normal_rsi_signal"],
        integrated_created_triggered_fade=integrated_conflicts["integrated_created_triggered_fade"],
        source_coverage_report_missing=source_coverage_report_conflicts["source_coverage_report_missing"],
        source_coverage_provider_status_unknown=source_coverage_report_conflicts["source_coverage_provider_status_unknown"],
        source_coverage_provider_marked_healthy_without_observation=source_coverage_report_conflicts["source_coverage_provider_marked_healthy_without_observation"],
        source_coverage_category_priority_missing=source_coverage_report_conflicts[
            "source_coverage_category_priority_missing"
        ],
        source_coverage_readiness_link_missing=source_coverage_report_conflicts[
            "source_coverage_readiness_link_missing"
        ],
        source_coverage_context_provider_ranked_above_lane_critical=source_coverage_report_conflicts[
            "source_coverage_context_provider_ranked_above_lane_critical"
        ],
        source_coverage_coinalyze_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_coinalyze_missing_linked_artifact"
        ],
        source_coverage_bybit_announcements_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_bybit_announcements_missing_linked_artifact"
        ],
        source_coverage_unlock_calendar_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_unlock_calendar_missing_linked_artifact"
        ],
        live_provider_readiness_missing=live_provider_readiness_conflicts["live_provider_readiness_missing"],
        live_provider_readiness_secret_leak=live_provider_readiness_conflicts["live_provider_readiness_secret_leak"],
        live_provider_readiness_live_calls_allowed_in_smoke=live_provider_readiness_conflicts[
            "live_provider_readiness_live_calls_allowed_in_smoke"
        ],
        live_provider_readiness_configured_missing_env=live_provider_readiness_conflicts[
            "live_provider_readiness_configured_missing_env"
        ],
        coinalyze_preflight_secret_leak=coinalyze_preflight_conflicts["coinalyze_preflight_secret_leak"],
        coinalyze_preflight_live_call_allowed_in_smoke=coinalyze_preflight_conflicts[
            "coinalyze_preflight_live_call_allowed_in_smoke"
        ],
        coinalyze_preflight_configured_missing_env=coinalyze_preflight_conflicts[
            "coinalyze_preflight_configured_missing_env"
        ],
        coinalyze_preflight_ready_without_request_ledger=coinalyze_preflight_conflicts[
            "coinalyze_preflight_ready_without_request_ledger"
        ],
        coinalyze_preflight_missing_fixture_parser_status=coinalyze_preflight_conflicts[
            "coinalyze_preflight_missing_fixture_parser_status"
        ],
        coinalyze_preflight_forbidden_side_effect_claim=coinalyze_preflight_conflicts[
            "coinalyze_preflight_forbidden_side_effect_claim"
        ],
        coinalyze_rehearsal_secret_leak=coinalyze_preflight_conflicts["coinalyze_rehearsal_secret_leak"],
        coinalyze_rehearsal_live_without_ledger=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_without_ledger"
        ],
        coinalyze_rehearsal_live_call_allowed_in_smoke=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_call_allowed_in_smoke"
        ],
        coinalyze_rehearsal_live_without_explicit_allow=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_without_explicit_allow"
        ],
        coinalyze_rehearsal_request_budget_exceeded=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_request_budget_exceeded"
        ],
        coinalyze_rehearsal_success_without_derivatives_state=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_success_without_derivatives_state"
        ],
        coinalyze_rehearsal_success_without_crowding_candidates=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_success_without_crowding_candidates"
        ],
        coinalyze_provider_health_healthy_without_successful_ledger=coinalyze_preflight_conflicts[
            "coinalyze_provider_health_healthy_without_successful_ledger"
        ],
        coinalyze_rehearsal_forbidden_side_effect_claim=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_forbidden_side_effect_claim"
        ],
        coinalyze_supported_metric_implemented_missing_state=coinalyze_preflight_conflicts[
            "coinalyze_supported_metric_implemented_missing_state"
        ],
        bybit_announcements_preflight_secret_leak=bybit_announcements_conflicts[
            "bybit_announcements_preflight_secret_leak"
        ],
        bybit_announcements_preflight_live_call_allowed_in_smoke=bybit_announcements_conflicts[
            "bybit_announcements_preflight_live_call_allowed_in_smoke"
        ],
        bybit_announcements_preflight_missing_fixture_parser_status=bybit_announcements_conflicts[
            "bybit_announcements_preflight_missing_fixture_parser_status"
        ],
        bybit_announcements_rehearsal_secret_leak=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_secret_leak"
        ],
        bybit_announcements_rehearsal_live_without_ledger=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_live_without_ledger"
        ],
        bybit_announcements_rehearsal_live_without_explicit_allow=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_live_without_explicit_allow"
        ],
        bybit_announcements_rehearsal_unsupported_params=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_unsupported_params"
        ],
        bybit_announcements_rehearsal_forbidden_side_effect_claim=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_forbidden_side_effect_claim"
        ],
        unlock_calendar_preflight_secret_leak=unlock_calendar_conflicts[
            "unlock_calendar_preflight_secret_leak"
        ],
        unlock_calendar_preflight_live_without_ledger=unlock_calendar_conflicts[
            "unlock_calendar_preflight_live_without_ledger"
        ],
        unlock_calendar_preflight_live_call_allowed_in_smoke=unlock_calendar_conflicts[
            "unlock_calendar_preflight_live_call_allowed_in_smoke"
        ],
        unlock_calendar_preflight_missing_fixture_parser_status=unlock_calendar_conflicts[
            "unlock_calendar_preflight_missing_fixture_parser_status"
        ],
        unlock_calendar_preflight_forbidden_side_effect_claim=unlock_calendar_conflicts[
            "unlock_calendar_preflight_forbidden_side_effect_claim"
        ],
        source_pack_provider_status_missing=source_coverage_conflicts["source_pack_provider_status_missing"],
        missing_provider_recommendations_missing=source_coverage_conflicts["missing_provider_recommendations_missing"],
        degraded_provider_absence_marked_meaningful=source_coverage_conflicts["degraded_provider_absence_marked_meaningful"],
        cryptopanic_configured_but_not_observed=cryptopanic_conflicts["cryptopanic_configured_but_not_observed"],
        cryptopanic_used_but_no_source_coverage_entry=cryptopanic_conflicts["cryptopanic_used_but_no_source_coverage_entry"],
        cryptopanic_accepted_evidence_missing_from_card=cryptopanic_conflicts["cryptopanic_accepted_evidence_missing_from_card"],
        cryptopanic_rejected_only_promoted=cryptopanic_conflicts["cryptopanic_rejected_only_promoted"],
        cryptopanic_token_printed_or_unredacted=cryptopanic_conflicts["cryptopanic_token_printed_or_unredacted"],
        cryptopanic_growth_unsupported_param_used=cryptopanic_conflicts["cryptopanic_growth_unsupported_param_used"],
        cryptopanic_duplicate_request_key=cryptopanic_conflicts["cryptopanic_duplicate_request_key"],
        cryptopanic_invalid_currency_code=cryptopanic_conflicts["cryptopanic_invalid_currency_code"],
        cryptopanic_empty_currency_request=cryptopanic_conflicts["cryptopanic_empty_currency_request"],
        cryptopanic_coin_id_sent_as_currency=cryptopanic_conflicts["cryptopanic_coin_id_sent_as_currency"],
        cryptopanic_all_requests_failed=cryptopanic_conflicts["cryptopanic_all_requests_failed"],
        cryptopanic_json_parse_errors=cryptopanic_conflicts["cryptopanic_json_parse_errors"],
        cryptopanic_configured_but_unusable=cryptopanic_conflicts["cryptopanic_configured_but_unusable"],
        cryptopanic_status_code_missing_on_http_failure=cryptopanic_conflicts["cryptopanic_status_code_missing_on_http_failure"],
        cryptopanic_body_excerpt_unredacted_token=cryptopanic_conflicts["cryptopanic_body_excerpt_unredacted_token"],
        cryptopanic_quota_exceeded=cryptopanic_conflicts["cryptopanic_quota_exceeded"],
        cryptopanic_request_ledger_missing_when_used=cryptopanic_conflicts["cryptopanic_request_ledger_missing_when_used"],
        cryptopanic_success_with_backoff_status=cryptopanic_conflicts["cryptopanic_success_with_backoff_status"],
        cryptopanic_restore_token_recommendation_when_configured=cryptopanic_conflicts[
            "cryptopanic_restore_token_recommendation_when_configured"
        ],
        evidence_count_mismatch=evidence_count_mismatches,
        unconfirmed_narrative_daily_digest=delivery_conflicts["unconfirmed_narrative_daily_digest"],
        single_source_no_market_fan_token_digest=delivery_conflicts["single_source_no_market_fan_token_digest"],
        visible_sector_core_without_config=visible_sector_cores,
        duplicate_proxy_core_rows=duplicate_proxy_cores,
        runs_with_matching_snapshots=matching_snapshot_runs,
        runs_with_missing_snapshots=missing_snapshot_runs,
        runs_with_external_snapshot_paths=external_snapshot_runs,
        legacy_rows_skipped=0 if include_legacy_artifacts else raw_legacy,
        legacy_rows_counted=sum(
            1 for row in (*runs, *alerts, *feedback, *outcomes)
            if event_alpha_artifacts.is_legacy_row(row)
        ),
        delivery_rows=delivery_summary.rows,
        latest_run_id=latest_run_id,
        latest_run_delivery_rows=delivery_conflicts["latest_run_delivery_rows"],
        legacy_delivery_rows=delivery_conflicts["legacy_delivery_rows"],
        stale_delivery_rows=delivery_conflicts["stale_delivery_rows"],
        delivery_strict_scope=effective_delivery_scope,
        deliveries_partial_delivered=delivery_summary.partial_delivered,
        deliveries_failed=delivery_summary.failed,
        delivery_status_missing=delivery_conflicts["delivery_status_missing"],
        delivery_status_detail_missing=delivery_conflicts["delivery_status_detail_missing"],
        delivery_mode_missing=delivery_conflicts["delivery_mode_missing"],
        delivery_state_inconsistent=delivery_conflicts["delivery_state_inconsistent"],
        delivery_would_send_sent_failed_inconsistent=delivery_conflicts["delivery_would_send_sent_failed_inconsistent"],
        delivery_identity_mismatch_core_store=delivery_conflicts["delivery_identity_mismatch_core_store"],
        delivery_core_id_missing=delivery_conflicts["delivery_core_id_missing"],
        legacy_pre_core_delivery_identity=delivery_conflicts["legacy_pre_core_delivery_identity"],
        stale_delivery_identity_missing_core=delivery_conflicts["stale_delivery_identity_missing_core"],
        delivery_feedback_target_missing=delivery_conflicts["delivery_feedback_target_missing"],
        delivery_card_path_missing=delivery_conflicts["delivery_card_path_missing"],
        delivery_alert_id_not_canonical=delivery_conflicts["delivery_alert_id_not_canonical"],
        telegram_message_contains_absolute_path=delivery_conflicts["telegram_message_contains_absolute_path"],
        telegram_message_contains_raw_debug_dump=delivery_conflicts["telegram_message_contains_raw_debug_dump"],
        research_review_digest_missing_confirmation_label=delivery_conflicts["research_review_digest_missing_confirmation_label"],
        research_review_digest_contains_strict_alertable=delivery_conflicts["research_review_digest_contains_strict_alertable"],
        research_review_digest_contains_hard_gated_candidate=delivery_conflicts["research_review_digest_contains_hard_gated_candidate"],
        research_review_digest_too_many_items=delivery_conflicts["research_review_digest_too_many_items"],
        research_review_digest_missing_feedback_target=delivery_conflicts["research_review_digest_missing_feedback_target"],
        research_review_digest_skipped_without_reason=delivery_conflicts["research_review_digest_skipped_without_reason"],
        research_review_digest_missing_family_summary=delivery_conflicts["research_review_digest_missing_family_summary"],
        research_review_digest_duplicate_visible_family_summary=delivery_conflicts[
            "research_review_digest_duplicate_visible_family_summary"
        ],
        research_review_digest_absolute_path=delivery_conflicts["research_review_digest_absolute_path"],
        notification_body_card_mismatch_canonical=delivery_conflicts["notification_body_card_mismatch_canonical"],
        notification_body_feedback_mismatch_canonical=delivery_conflicts["notification_body_feedback_mismatch_canonical"],
        research_review_body_uses_hypothesis_target_when_core_exists=delivery_conflicts["research_review_body_uses_hypothesis_target_when_core_exists"],
        research_review_digest_enabled_but_lane_missing=research_review_enabled_but_lane_missing,
        research_review_digest_candidates_without_delivery=research_review_candidates_without_delivery,
        digest_item_without_live_confirmation=delivery_conflicts["digest_item_without_live_confirmation"],
        digest_item_rejected_results_only=delivery_conflicts["digest_item_rejected_results_only"],
        strategic_broad_asset_digest_without_confirmation=delivery_conflicts["strategic_broad_asset_digest_without_confirmation"],
        notification_preview_missing=delivery_conflicts["notification_preview_missing"],
        notification_preview_relpath_missing=delivery_conflicts["notification_preview_relpath_missing"],
        notification_preview_path_unresolvable=delivery_conflicts["notification_preview_path_unresolvable"],
        notification_preview_run_summary_mismatch=preview_conflicts["notification_preview_run_summary_mismatch"],
        notification_preview_llm_summary_mismatch=preview_conflicts["notification_preview_llm_summary_mismatch"],
        notification_preview_lane_counts_mismatch=preview_conflicts["notification_preview_lane_counts_mismatch"],
        notification_preview_core_count_mismatch=preview_conflicts["notification_preview_core_count_mismatch"],
        notification_preview_alertable_count_mismatch=preview_conflicts["notification_preview_alertable_count_mismatch"],
        notification_preview_missing_send_guard_status=preview_conflicts["notification_preview_missing_send_guard_status"],
        notification_preview_send_guard_status_missing=preview_conflicts["notification_preview_send_guard_status_missing"],
        notification_preview_no_send_status_unclear=preview_conflicts["notification_preview_no_send_status_unclear"],
        notification_preview_legacy_alerts_wording=preview_conflicts["notification_preview_legacy_alerts_wording"],
        quality_fields_missing_count=quality["quality_fields_missing_count"],
        hypothesis_rows_missing_opportunity_verdict=quality["hypothesis_rows_missing_opportunity_verdict"],
        watchlist_rows_missing_quality_fields=quality["watchlist_rows_missing_quality_fields"],
        alert_rows_missing_quality_fields=quality["alert_rows_missing_quality_fields"],
        fresh_hypothesis_rows_missing_top_level_quality=quality["fresh_hypothesis_rows_missing_top_level_quality"],
        fresh_watchlist_rows_missing_top_level_quality=quality["fresh_watchlist_rows_missing_top_level_quality"],
        fresh_alert_rows_missing_top_level_quality=quality["fresh_alert_rows_missing_top_level_quality"],
        legacy_quality_missing_rows=quality["legacy_quality_missing_rows"],
        alertable_route_conflicts_with_opportunity_level=route_conflicts,
        alert_snapshot_route_mismatch_core_store=snapshot_core_conflicts["route_mismatch"],
        alert_snapshot_level_mismatch_core_store=snapshot_core_conflicts["level_mismatch"],
        alert_snapshot_live_confirmation_stale=snapshot_core_conflicts["live_confirmation_stale"],
        alert_snapshot_core_resolution_missing=snapshot_core_conflicts["core_resolution_missing"],
        alert_snapshot_pre_reconciliation_alertable=snapshot_core_conflicts["pre_reconciliation_alertable"],
        diagnostic_support_snapshot_alertable=snapshot_core_conflicts["diagnostic_support_alertable"],
        diagnostic_support_snapshot_inherits_core_route=snapshot_core_conflicts["diagnostic_support_inherits_core_route"],
        duplicate_alertable_snapshot_for_core=snapshot_core_conflicts["duplicate_alertable_snapshot_for_core"],
        canonical_snapshot_missing_for_visible_core=snapshot_core_conflicts["canonical_snapshot_missing_for_visible_core"],
        inbox_core_item_missing_card=inbox_core_missing_card,
        inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists=inbox_core_alert_target,
        inbox_diagnostic_snapshot_visible_by_default=inbox_diag_visible_default,
        audit_primary_snapshot_not_canonical_when_canonical_exists=audit_primary_not_canonical,
        feedback_readiness_counts_diagnostic_as_required=diagnostic_snapshots_missing_feedback,
        fresh_quality_route_conflict_rows=fresh_route_conflicts,
        legacy_quality_conflict_rows=legacy_route_conflicts,
        alert_rows_missing_final_route=missing_final_route,
        fresh_alert_rows_missing_final_route=fresh_missing_final_route,
        watchlist_state_conflicts_with_quality=watchlist_conflicts["watchlist_state_conflicts_with_quality"],
        universal_watchlist_state_conflicts=watchlist_conflicts["universal_watchlist_state_conflicts"],
        non_hypothesis_watchlist_quality_conflicts=watchlist_conflicts["non_hypothesis_watchlist_quality_conflicts"],
        hypothesis_watchlist_quality_conflicts=watchlist_conflicts["hypothesis_watchlist_quality_conflicts"],
        quality_capped_watchlist_rows=watchlist_conflicts["quality_capped_watchlist_rows"],
        active_watchlist_rows_quality_capped=watchlist_conflicts["active_watchlist_rows_quality_capped"],
        fresh_watchlist_state_conflict_rows=watchlist_conflicts["fresh_uncapped"],
        legacy_watchlist_conflicts=watchlist_conflicts["legacy"],
        hypothesis_rows_missing_incident_id=incident_linkage["hypothesis_rows_missing_incident_id"],
        watchlist_hypothesis_rows_missing_incident_id=incident_linkage["watchlist_hypothesis_rows_missing_incident_id"],
        alert_hypothesis_rows_missing_incident_id=incident_linkage["alert_hypothesis_rows_missing_incident_id"],
        incident_rows_without_linked_hypotheses=incident_linkage["incident_rows_without_linked_hypotheses"],
        incident_rows_without_linked_watchlist=incident_linkage["incident_rows_without_linked_watchlist"],
        canonical_unlinked_incidents=incident_linkage["canonical_unlinked_incidents"],
        active_incident_without_qualified_link=incident_linkage["active_incident_without_qualified_link"],
        linked_incident_without_qualified_link=incident_linkage["linked_incident_without_qualified_link"],
        weak_unqualified_incident_links=incident_linkage["weak_unqualified_incident_links"],
        quality_blocked_links_present=incident_linkage["quality_blocked_links_present"],
        quality_blocked_links_promoting_incident=incident_linkage["quality_blocked_links_promoting_incident"],
        diagnostic_incident_rows=incident_linkage["diagnostic_incident_rows"],
        raw_observation_incident_rows=incident_linkage["raw_observation_incident_rows"],
        external_context_incident_rows=incident_linkage["external_context_incident_rows"],
        rejected_incident_rows=incident_linkage["rejected_incident_rows"],
        incident_relevance_missing=incident_linkage["incident_relevance_missing"],
        invalid_canonical_incident_rows=incident_linkage["invalid_canonical_incident_rows"],
        garbage_primary_subject_incidents=incident_linkage["garbage_primary_subject_incidents"],
        fresh_incident_linkage_blockers=(
            incident_linkage["fresh_missing_hypotheses"]
            + incident_linkage["fresh_missing_watchlist"]
            + incident_linkage["fresh_missing_alerts"]
        ),
        legacy_incident_linkage_warnings=(
            incident_linkage["legacy_missing_hypotheses"]
            + incident_linkage["legacy_missing_watchlist"]
            + incident_linkage["legacy_missing_alerts"]
        ),
        namespace_status=namespace_status.status if namespace_status else event_alpha_namespace_status.STATUS_ACTIVE,
        namespace_stale_deprecated=1 if event_alpha_namespace_status.is_stale_deprecated(namespace_status) else 0,
        namespace_superseded_by=namespace_status.superseded_by if namespace_status else None,
        strict_legacy=bool(strict_legacy),
        strict=bool(strict),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _read_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in source.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                rows.append(dict(item))
    except OSError:
        return []
    return rows


def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "feedback_target",
        "core_opportunity_id",
        "alert_id",
        "card_id",
        "alert_key",
        "snapshot_id",
    ))


def _alert_snapshot_should_have_core_id(row: Mapping[str, Any]) -> bool:
    if str(row.get("row_type") or "") not in {"", "event_alpha_alert_snapshot"}:
        return False
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    level = str(row.get("opportunity_level") or "").casefold()
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "")
    if event_alpha_router.route_value_is_alertable(route):
        return True
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
        return True
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    return state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }


def _alert_snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return event_alpha_notification_inbox.alert_snapshot_is_diagnostic(row)


def _audit_primary_snapshot_not_canonical_when_canonical_exists(
    alerts: Iterable[Mapping[str, Any]],
    store_core_ids: set[str],
) -> int:
    by_core: dict[str, list[dict[str, Any]]] = {}
    for row in alerts:
        core_id = str(row.get("core_opportunity_id") or row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
        if not core_id or core_id not in store_core_ids:
            continue
        by_core.setdefault(core_id, []).append(dict(row))
    conflicts = 0
    for rows in by_core.values():
        has_canonical = any(_snapshot_is_canonical(row) for row in rows)
        if not has_canonical:
            continue
        primary = _best_snapshot_for_doctor(rows)
        if not _snapshot_is_canonical(primary):
            conflicts += 1
    return conflicts


def _best_snapshot_for_doctor(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = [dict(row) for row in rows]
    if not items:
        return {}

    def rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
        diagnostic = _alert_snapshot_is_diagnostic(row)
        return (
            3 if _snapshot_is_canonical(row) else 0,
            1 if event_alpha_router.route_value_is_alertable(str(row.get("final_route_after_quality_gate") or row.get("route") or "")) and not diagnostic else 0,
            str(row.get("observed_at") or row.get("snapshot_id") or ""),
        )

    return max(items, key=rank)


def _snapshot_is_canonical(row: Mapping[str, Any]) -> bool:
    if _alert_snapshot_is_diagnostic(row):
        return False
    status = str(row.get("snapshot_core_resolution_status") or row.get("core_resolution_status") or "")
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
        or status in {"canonical", event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED}
        or bool(row.get("snapshot_core_reconciled"))
    )


def _expected_card_group_for_store_core(
    opportunity: event_core_opportunities.CoreOpportunity | None,
) -> str | None:
    if opportunity is None:
        return None
    primary = opportunity.primary_row
    lane_group = (
        event_research_cards.card_group_for_opportunity_lane(
            primary.get("opportunity_type")
            or primary.get("opportunity_lane")
        )
    )
    if lane_group is not None:
        return lane_group
    if opportunity.is_high_priority or opportunity.is_watchlist or opportunity.is_validated_digest or opportunity.alertable:
        return "Core Opportunity Cards"
    if (
        str(opportunity.final_state_after_quality_gate or "").strip()
        == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        or str(opportunity.primary_row.get("state_quality_capped") or "").strip().casefold()
        in {"1", "true", "yes", "y"}
        or opportunity.quality_capped_supporting_rows > 0
    ):
        return "Local-Only / Quality-Capped Cards"
    if str(opportunity.opportunity_level or "").casefold() == "local_only":
        return "Local-Only / Quality-Capped Cards"
    if str(opportunity.opportunity_level or "").casefold() == "exploratory" or opportunity.opportunity_score_final >= 50:
        return "Near-Miss Cards"
    if event_core_opportunities.core_opportunity_visibility_group(opportunity) is None:
        return "Diagnostic / Source-Noise / Control Cards"
    return "Local-Only / Quality-Capped Cards"


def _core_has_fresh_rows(opportunity: event_core_opportunities.CoreOpportunity) -> bool:
    return any(
        not event_alpha_artifacts.is_legacy_row(row)
        for row in (opportunity.primary_row, *opportunity.supporting_rows)
    )


def _card_primary_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    mismatches = 0
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        route = str(core.get("final_route_after_quality_gate") or "").strip()
        state = str(core.get("final_state_after_quality_gate") or "").strip()
        level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        route_line = _card_line_value(text, "Final route")
        verdict_line = _card_line_value(text, "Opportunity verdict")
        summary_line = _card_line_value(text, "State / alert tier")
        mismatch = False
        if route_line and route and route_line != route:
            mismatch = True
        if verdict_line and level and not verdict_line.startswith(level):
            mismatch = True
        if summary_line and state and not summary_line.startswith(f"{state} /"):
            mismatch = True
        if summary_line and route and not summary_line.endswith(f"/ {route}"):
            mismatch = True
        mismatches += int(mismatch)
    return mismatches


def _card_acquisition_count_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if view.accepted_evidence_count <= 0:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_evidence_count(text, "accepted")
        if rendered is not None and rendered != view.accepted_evidence_count:
            mismatches += 1
    return mismatches


def _card_source_pack_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if not view.source_pack:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_line_value(text, "Source pack")
        if rendered and rendered != view.source_pack:
            mismatches += 1
    return mismatches


def _card_primary_section_contains_support_row_blockers(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    blockers = (
        "blocked by generic cooccurrence",
        "needs proof that this event directly affects the token",
        "no token value-capture mechanism is visible",
    )
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        count += int(any(blocker in text for blocker in blockers))
    return count


def _card_upgrade_text_inconsistent_with_final_level(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        if str(core.get("opportunity_level") or core.get("final_opportunity_level") or "").casefold() == "high_priority":
            count += int("already high priority" not in text)
    return count


def _card_market_confirmation_missing_but_core_has_market_confirmation(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        has_market = core.get("market_confirmation_level") not in (None, "", "none") or core.get("market_confirmation_score") not in (None, "")
        if not has_market:
            continue
        text = _read_card_text(path).casefold()
        count += int("no market snapshot stored" in text or "market data: not available" in text)
    return count


def _card_latest_source_unknown_but_accepted_evidence_exists(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    count = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        core_id = event_research_cards.card_core_opportunity_id(path) or ""
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        accepted = max(int(core.get("evidence_acquisition_accepted_count") or 0), view.accepted_evidence_count)
        if accepted <= 0:
            continue
        text = _read_card_text(path).casefold()
        count += int("- latest source: unknown" in text or "- latest source: not available" in text)
    return count


def _card_core_row(path: Path, core_rows_by_id: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    core_id = event_research_cards.card_core_opportunity_id(path)
    return core_rows_by_id.get(core_id or "")


def _read_card_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _core_row_is_promoted(row: Mapping[str, Any]) -> bool:
    level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").casefold()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)


def _card_evidence_count(text: str, label: str) -> int | None:
    match = re.search(rf"\b{re.escape(label)}=(\d+)\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _promoted_core_rows_that_are_weak(core_rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in core_rows:
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "")
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        impact = str(row.get("impact_path_type") or row.get("primary_impact_path") or "")
        if level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route):
            if impact in {"generic_cooccurrence_only", "insufficient_data"}:
                count += 1
    return count


def _card_line_value(text: str, label: str) -> str | None:
    match = re.search(rf"^-\s*{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _core_row_has_market_freshness_contradiction(row: Mapping[str, Any]) -> bool:
    status = str(row.get("market_context_freshness_status") or "").casefold()
    source = str(row.get("market_context_source") or "").casefold()
    age = row.get("market_context_age_hours")
    cap = row.get("market_context_freshness_cap_applied")
    if status not in {"fresh", "fixture_allowed_stale"}:
        return False
    if source not in {"", "missing", "unknown"}:
        return False
    return age in (None, "", "unknown") and bool(cap)


def _quality_missing_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    hypothesis_rows = [dict(row) for row in hypotheses if dict(row).get("row_type") in {"event_impact_hypothesis", ""}]
    watchlist_rows = [dict(row) for row in watchlist if dict(row).get("row_type") in {"event_watchlist_state", ""}]
    alert_rows = [dict(row) for row in alerts if dict(row).get("row_type") in {"event_alpha_alert_snapshot", ""}]
    hypothesis_missing_verdict = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_level"))
        or event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_score_final"))
    )
    watchlist_missing = sum(1 for row in watchlist_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    alert_missing = sum(1 for row in alert_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    all_rows = [*hypothesis_rows, *watchlist_rows, *alert_rows]
    missing_rows = [
        row
        for row in all_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
    ]
    legacy_missing = sum(1 for row in missing_rows if event_alpha_artifacts.is_legacy_row(row))
    fresh_hypothesis_missing = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_watchlist_missing = sum(
        1
        for row in watchlist_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_alert_missing = sum(
        1
        for row in alert_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    return {
        "quality_fields_missing_count": len(missing_rows),
        "hypothesis_rows_missing_opportunity_verdict": hypothesis_missing_verdict,
        "watchlist_rows_missing_quality_fields": watchlist_missing,
        "alert_rows_missing_quality_fields": alert_missing,
        "fresh_hypothesis_rows_missing_top_level_quality": fresh_hypothesis_missing,
        "fresh_watchlist_rows_missing_top_level_quality": fresh_watchlist_missing,
        "fresh_alert_rows_missing_top_level_quality": fresh_alert_missing,
        "legacy_quality_missing_rows": legacy_missing,
        "non_legacy_quality_missing": max(0, len(missing_rows) - legacy_missing),
    }


def _latest_run_rows(rows: Iterable[Mapping[str, Any]], run_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    run_ids = [str(row.get("run_id") or "") for row in run_rows if str(row.get("run_id") or "")]
    if not run_ids:
        return [row for row in rows]
    latest = sorted(run_ids)[-1]
    latest_rows = [row for row in rows if str(row.get("run_id") or "") == latest]
    return latest_rows


def _alertable_quality_route_conflicts(alerts: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in alerts if _row_has_alertable_quality_conflict(row))


def _alert_snapshot_core_conflicts(
    alerts: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "route_mismatch": 0,
        "level_mismatch": 0,
        "live_confirmation_stale": 0,
        "core_resolution_missing": 0,
        "pre_reconciliation_alertable": 0,
        "diagnostic_support_alertable": 0,
        "diagnostic_support_inherits_core_route": 0,
        "duplicate_alertable_snapshot_for_core": 0,
        "canonical_snapshot_missing_for_visible_core": 0,
    }
    core_rows_tuple = tuple(core_rows)
    core_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
    }
    alertable_canonical_by_core_route: dict[tuple[str, str], int] = {}
    canonical_alertable_core_ids: set[str] = set()
    for row in alerts:
        if event_alpha_artifacts.is_legacy_row(row):
            continue
        if _is_diagnostic_support_snapshot(row):
            route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
            alertable = bool(row.get("alertable_after_quality_gate", row.get("route_alertable")))
            if alertable or event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_alertable"] += 1
            if event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_inherits_core_route"] += 1
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if not core_id:
            continue
        core = core_by_id.get(core_id)
        if core is None:
            out["core_resolution_missing"] += 1
            continue
        snapshot_reconciled = bool(row.get("snapshot_core_reconciled"))
        snapshot_route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        core_route = str(core.get("final_route_after_quality_gate") or core.get("route") or "").strip()
        snapshot_level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        core_level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        if snapshot_route != core_route and not snapshot_reconciled:
            out["route_mismatch"] += 1
        if snapshot_level != core_level and not snapshot_reconciled:
            out["level_mismatch"] += 1
        snapshot_promoted = (
            snapshot_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(snapshot_route)
        )
        core_promoted = (
            core_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(core_route)
        )
        if (
            bool(core.get("live_confirmation_capped")) or str(core.get("live_confirmation_status") or "") in {"missing", "unresolved"}
        ) and snapshot_promoted and not core_promoted and not snapshot_reconciled:
            out["live_confirmation_stale"] += 1
        requested_route = str(row.get("requested_route_before_core_reconciliation") or "").strip()
        if (
            snapshot_reconciled
            and event_alpha_router.route_value_is_alertable(requested_route)
            and not event_alpha_router.route_value_is_alertable(snapshot_route)
        ):
            out["pre_reconciliation_alertable"] += 1
        if event_alpha_router.route_value_is_alertable(snapshot_route):
            canonical_alertable_core_ids.add(core_id)
            key = (core_id, snapshot_route)
            alertable_canonical_by_core_route[key] = alertable_canonical_by_core_route.get(key, 0) + 1
    out["duplicate_alertable_snapshot_for_core"] = sum(
        max(0, count - 1)
        for count in alertable_canonical_by_core_route.values()
        if count > 1
    )
    alertable_visible_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
        and event_alpha_router.route_value_is_alertable(
            row.get("final_route_after_quality_gate") or row.get("route")
        )
        and not event_core_opportunities.row_is_diagnostic(row)
    }
    out["canonical_snapshot_missing_for_visible_core"] = len(alertable_visible_core_ids - canonical_alertable_core_ids)
    return out


def _is_diagnostic_support_snapshot(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or bool(row.get("is_diagnostic_snapshot"))
    )


def _quality_route_conflicts(alerts: Iterable[Mapping[str, Any]], *, legacy: bool) -> int:
    count = 0
    for row in alerts:
        is_legacy = event_alpha_artifacts.is_legacy_row(row)
        if legacy != is_legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification == event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT or _row_has_alertable_quality_conflict(row):
            count += 1
    return count


def _missing_final_route_rows(alerts: Iterable[Mapping[str, Any]], *, legacy: bool | None = None) -> int:
    count = 0
    for row in alerts:
        if legacy is not None and event_alpha_artifacts.is_legacy_row(row) != legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification in {
            event_alpha_alert_store.SNAPSHOT_MISSING_FINAL_ROUTE,
            event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
        }:
            count += 1
    return count


def _core_route_conflicts_with_opportunity_level(rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        }:
            continue
        if bool(row.get("state_quality_capped")):
            continue
        components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
        _, block = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=True)
        if block:
            continue
        count += 1
    return count


def _live_confirmation_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, int]:
    out = {
        "live_validated_without_confirmation": 0,
        "live_sector_digest_without_asset": 0,
        "live_rejected_results_promoted": 0,
        "live_skipped_budget_promoted": 0,
    }
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route not in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }:
            continue
        if not event_opportunity_verdict.live_confirmation_required(
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        ):
            continue
        if bool(row.get("live_confirmation_passed")):
            continue
        if str(row.get("live_confirmation_status") or "") == "confirmed":
            continue
        out["live_validated_without_confirmation"] += 1
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip().casefold()
        if symbol == "SECTOR" or coin_id in {"sports_fan_proxy", "political_meme_proxy", "ai_ipo_proxy", "rwa_preipo_proxy", "sector"}:
            out["live_sector_digest_without_asset"] += 1
        status = str(row.get("evidence_acquisition_status") or "").strip()
        if status == "rejected_results_only":
            out["live_rejected_results_promoted"] += 1
        if status == "skipped_budget":
            out["live_skipped_budget_promoted"] += 1
    return out


def _raw_core_live_confirmation_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, int]:
    out = {
        "raw_core_validated_without_confirmation": 0,
        "raw_core_source_only_narrative_validated": 0,
        "raw_core_cryptopanic_tag_only_direct_path_confirmed": 0,
        "raw_core_suppressed_duplicate_validated_stale": 0,
    }
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if not event_opportunity_verdict.live_confirmation_required(
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        ):
            continue
        verdict = event_opportunity_verdict.apply_live_confirmation_policy(
            row,
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        )
        raw_stale = bool(not verdict.confirmed or verdict.capped_level)
        if raw_stale:
            out["raw_core_validated_without_confirmation"] += 1
        if raw_stale and _raw_core_source_only_narrative(row):
            out["raw_core_source_only_narrative_validated"] += 1
        if _raw_core_cryptopanic_tag_only_direct_path(row) and str(row.get("live_confirmation_status") or "") == "confirmed":
            out["raw_core_cryptopanic_tag_only_direct_path_confirmed"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if raw_stale and route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value:
            out["raw_core_suppressed_duplicate_validated_stale"] += 1
    return out


def _opportunity_lane_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "confirmed_long_without_source_market": 0,
        "fade_short_without_crowding_exhaustion": 0,
        "early_long_without_fresh_strong_source": 0,
        "risk_only_missing_evidence_only": 0,
        "cryptopanic_only_narrative_confirmed_lane": 0,
        "diagnostic_visible_default_operator_lane": 0,
        "core_missing_market_state_snapshot": 0,
        "market_state_return_unit_missing": 0,
        "market_state_possible_double_scaled": 0,
        "market_state_lane_possible_double_scaled": 0,
    }
    for row in rows:
        lane = str(row.get("opportunity_type") or "").strip()
        if not lane:
            continue
        snapshot = row.get("market_state_snapshot")
        if not isinstance(snapshot, Mapping) or not snapshot:
            out["core_missing_market_state_snapshot"] += 1
            snapshot = {}
        elif not str(snapshot.get("return_unit") or "").strip():
            out["market_state_return_unit_missing"] += 1
        unit_warnings = set(event_market_units.validate_market_snapshot_units(
            snapshot if isinstance(snapshot, Mapping) else {},
            row.get("latest_market_snapshot") if isinstance(row.get("latest_market_snapshot"), Mapping) else row.get("market_snapshot") if isinstance(row.get("market_snapshot"), Mapping) else None,
        ))
        if any("possible_double_scaled" in warning or "unit_mismatch" in warning for warning in unit_warnings):
            out["market_state_possible_double_scaled"] += 1
            if lane in {"CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW"}:
                out["market_state_lane_possible_double_scaled"] += 1
        source_met = _truthy(row.get("source_requirements_met") if row.get("source_requirements_met") is not None else row.get("opportunity_type_source_requirements_met"))
        market_met = _truthy(row.get("market_requirements_met") if row.get("market_requirements_met") is not None else row.get("opportunity_type_market_requirements_met"))
        fade_met = _truthy(row.get("fade_requirements_met") if row.get("fade_requirements_met") is not None else row.get("opportunity_type_fade_requirements_met"))
        source_strength = str(row.get("source_strength") or row.get("opportunity_type_source_strength") or "").casefold()
        market_state = str(row.get("market_state_class") or row.get("market_state") or "").casefold()
        if lane == "CONFIRMED_LONG_RESEARCH" and (not source_met or not market_met):
            out["confirmed_long_without_source_market"] += 1
        if lane == "FADE_SHORT_REVIEW" and (not fade_met or market_state not in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"}):
            out["fade_short_without_crowding_exhaustion"] += 1
        if lane == "EARLY_LONG_RESEARCH" and (source_strength not in {"strong", "official_structured"} or market_state != "no_reaction"):
            out["early_long_without_fresh_strong_source"] += 1
        if lane == "CONFIRMED_LONG_RESEARCH" and _opportunity_lane_cryptopanic_only_narrative(row):
            out["cryptopanic_only_narrative_confirmed_lane"] += 1
        if lane == "RISK_ONLY" and _opportunity_lane_risk_only_missing_evidence(row):
            out["risk_only_missing_evidence_only"] += 1
        if lane == "DIAGNOSTIC" and _opportunity_lane_diagnostic_visible(row):
            out["diagnostic_visible_default_operator_lane"] += 1
    return out


def _market_anomaly_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "market_anomaly_missing_market_state_snapshot": 0,
        "market_anomaly_missing_market_state_class": 0,
        "market_anomaly_confirmed_breakout_missing_evidence": 0,
        "market_anomaly_suspicious_illiquid_promoted_confirmed": 0,
        "market_anomaly_created_alert_rows": 0,
        "market_anomaly_missing_freshness_status": 0,
        "market_anomaly_needs_search_without_plan": 0,
    }
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_tiers = {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    for row in rows:
        if str(row.get("row_type") or "") != "event_market_anomaly":
            continue
        anomaly_type = str(row.get("anomaly_type") or row.get("market_state") or "")
        if anomaly_type and not str(row.get("market_state_class") or "").strip():
            out["market_anomaly_missing_market_state_class"] += 1
        snapshot = row.get("market_state_snapshot")
        if not isinstance(snapshot, Mapping) or not snapshot:
            out["market_anomaly_missing_market_state_snapshot"] += 1
            snapshot = {}
        freshness = str(snapshot.get("freshness_status") or row.get("freshness_status") or "").strip()
        if not freshness:
            out["market_anomaly_missing_freshness_status"] += 1
        if anomaly_type == "confirmed_breakout":
            r4 = _safe_float(snapshot.get("return_4h"))
            r24 = _safe_float(snapshot.get("return_24h"))
            volume_z = _safe_float(snapshot.get("volume_zscore_24h"))
            rel_btc_4h = _safe_float(snapshot.get("relative_return_vs_btc_4h"))
            has_price = (r4 is not None and r4 >= 8.0) or (r24 is not None and r24 >= 15.0)
            has_volume = volume_z is not None and volume_z >= 2.0
            has_relative = rel_btc_4h is not None and rel_btc_4h >= 5.0
            if not (has_price and has_volume and has_relative):
                out["market_anomaly_confirmed_breakout_missing_evidence"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        opportunity_type = str(row.get("opportunity_type") or "").upper()
        anomaly_bucket = str(row.get("anomaly_bucket") or row.get("market_anomaly_bucket") or "").strip()
        created_alert = bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in alertable_routes or tier in alertable_tiers
        if created_alert:
            out["market_anomaly_created_alert_rows"] += 1
        if (anomaly_type == "suspicious_illiquid_move" or anomaly_bucket == "low_liquidity_suspicious") and (
            opportunity_type == "CONFIRMED_LONG_RESEARCH"
            or route in alertable_routes
            or tier in {"WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
        ):
            out["market_anomaly_suspicious_illiquid_promoted_confirmed"] += 1
        has_source_plan = bool(row.get("suggested_source_packs_to_search")) or bool(row.get("search_queries"))
        if bool(row.get("needs_catalyst_search")) and not has_source_plan:
            out["market_anomaly_needs_search_without_plan"] += 1
    return out


def _official_exchange_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "official_exchange_candidate_missing_source_fields": 0,
        "official_exchange_listing_without_official_source": 0,
        "official_exchange_secret_leak": 0,
        "official_exchange_delisting_long_research": 0,
        "official_exchange_quote_asset_misclassified": 0,
        "official_exchange_major_pair_noise_promoted_early_long": 0,
        "official_exchange_created_alert_rows": 0,
    }
    quote_assets = {"USD", "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "BTC", "ETH", "BNB", "EUR", "TRY", "BRL"}
    long_lanes = {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_tiers = {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    listing_packs = {"official_exchange_listing_pack", "official_perp_listing_pack", "listing_liquidity_pack", "perp_listing_squeeze_pack"}
    for row in rows:
        if str(row.get("row_type") or "") != "official_listing_candidate":
            continue
        missing_required = any(not str(row.get(key) or "").strip() for key in ("source_url", "title", "published_at"))
        if missing_required:
            out["official_exchange_candidate_missing_source_fields"] += 1
        source_class = str(row.get("source_class") or "").strip()
        source_pack = str(row.get("source_pack") or "").strip()
        if source_pack in listing_packs and source_class != "official_exchange":
            out["official_exchange_listing_without_official_source"] += 1
        payload_text = json.dumps(row, sort_keys=True, default=str)
        if any(token in payload_text.casefold() for token in ("api_key", "apikey", "secret", "signature=", "x-mbx-apikey", "telegram_bot_token")):
            out["official_exchange_secret_leak"] += 1
        event_type = str(row.get("event_type") or "").strip()
        opportunity_type = str(row.get("opportunity_type") or "").strip().upper()
        if event_type == "delisting" and opportunity_type in long_lanes:
            out["official_exchange_delisting_long_research"] += 1
        symbol = str(row.get("symbol") or "").upper().strip()
        pair_text = " ".join(
            str(value or "")
            for value in (
                row.get("pairs"),
                row.get("announcement_pairs"),
                row.get("title"),
                row.get("body"),
                row.get("event_name"),
            )
        ).upper()
        quote_assets_for_row = {str(value).upper() for value in row.get("quote_assets") or () if str(value).strip()}
        symbol_is_quote_side = (
            symbol in quote_assets_for_row
            or bool(symbol and re.search(rf"/{re.escape(symbol)}\b", pair_text))
        )
        if symbol in quote_assets and symbol_is_quote_side:
            out["official_exchange_quote_asset_misclassified"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        if bool(row.get("major_pair_simple_announcement")) and opportunity_type == "EARLY_LONG_RESEARCH":
            out["official_exchange_major_pair_noise_promoted_early_long"] += 1
        if bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in alertable_routes or tier in alertable_tiers:
            out["official_exchange_created_alert_rows"] += 1
    return out


def _scheduled_catalyst_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "unlock_without_structured_evidence": 0,
        "unlock_missing_event_time": 0,
        "unlock_promoted_without_size_metrics": 0,
        "media_unlock_promoted_structured": 0,
        "stale_completed_catalyst_upcoming": 0,
        "calendar_event_missing_source_url": 0,
        "cryptopanic_unlock_proof": 0,
        "scheduled_catalyst_created_alert_rows": 0,
    }
    strict_lanes = {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW", "RISK_ONLY"}
    promoted_risk_lanes = {"FADE_SHORT_REVIEW", "RISK_ONLY"}
    media_classes = {"cryptopanic_tagged", "crypto_news", "broad_news", "media_calendar", "social_or_unknown"}
    trusted_unlock_classes = {
        "structured_unlock",
        "supply_data",
        "official_project",
        "official_exchange",
        "structured_calendar",
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_type = str(row.get("row_type") or "")
        if row_type not in {"scheduled_catalyst_event", "unlock_event"}:
            continue
        event_type = str(row.get("event_type") or "")
        impact = str(row.get("impact_path_type") or "")
        source_class = str(row.get("source_class") or "").strip()
        lane = str(row.get("opportunity_type") or "").strip().upper()
        is_unlock = row_type == "unlock_event" or event_type in {"token_unlock", "vesting_cliff", "linear_emission"} or impact == "unlock_supply_event"
        if is_unlock:
            structured = bool(row.get("structured_unlock_evidence")) or source_class in trusted_unlock_classes
            if not structured and lane in strict_lanes:
                out["unlock_without_structured_evidence"] += 1
            if source_class in media_classes and lane in strict_lanes:
                out["media_unlock_promoted_structured"] += 1
            if source_class == "cryptopanic_tagged" and (
                bool(row.get("structured_unlock_evidence"))
                or "structured_unlock_source" in {str(item) for item in row.get("reason_codes") or ()}
                or lane in strict_lanes
            ):
                out["cryptopanic_unlock_proof"] += 1
            if not str(row.get("unlock_time") or row.get("event_start_time") or "").strip():
                out["unlock_missing_event_time"] += 1
            size_fields = (
                row.get("unlock_pct_circulating_supply"),
                row.get("unlock_pct_circulating"),
                row.get("unlock_pct_total_supply"),
                row.get("unlock_vs_30d_adv"),
                row.get("tokens_unlocked"),
                row.get("unlock_usd"),
            )
            if lane in promoted_risk_lanes and all(value in (None, "", [], {}, ()) for value in size_fields):
                out["unlock_promoted_without_size_metrics"] += 1
        if row_type == "scheduled_catalyst_event":
            if not str(row.get("source_url") or row.get("url") or "").strip():
                out["calendar_event_missing_source_url"] += 1
            status = str(row.get("event_status") or "").strip()
            age = _safe_float(row.get("event_age_hours"))
            if status == "completed" and age is not None and age > 24 and lane in {
                "EARLY_LONG_RESEARCH",
                "CONFIRMED_LONG_RESEARCH",
            }:
                out["stale_completed_catalyst_upcoming"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        if bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"} or tier in {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}:
            out["scheduled_catalyst_created_alert_rows"] += 1
    return out


def _derivatives_crowding_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "fade_review_without_completed_move": 0,
        "fade_review_without_crowding_exhaustion": 0,
        "fade_review_created_triggered_fade": 0,
        "fade_review_created_normal_rsi_signal": 0,
        "fade_review_notification_missing_disclaimer": 0,
        "derivatives_artifact_secret_leak": 0,
        "derivatives_state_missing_freshness_status": 0,
        "derivatives_metric_claim_implemented_missing": 0,
        "derivatives_unit_metadata_missing": 0,
        "stale_derivatives_snapshot_promoted_fade_review": 0,
        "confirmed_long_crowded_without_warning": 0,
    }
    implemented_claims: set[str] = set()
    metrics_with_values: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_type = str(row.get("row_type") or "")
        text = json.dumps(row, sort_keys=True, default=str).casefold()
        if _derivatives_row_has_secret_leak(row) or any(token in text for token in ("bearer ", "sk-proj-")):
            out["derivatives_artifact_secret_leak"] += 1
        if row_type == "derivatives_state_snapshot":
            if not str(row.get("freshness_status") or "").strip():
                out["derivatives_state_missing_freshness_status"] += 1
            metric_status = row.get("supported_metric_status")
            if isinstance(metric_status, Mapping):
                for metric, status in metric_status.items():
                    if str(status) == event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED:
                        implemented_claims.add(str(metric))
            for metric in event_derivatives_crowding.DERIVATIVES_SUPPORTED_METRICS:
                if _derivatives_metric_has_value(row, metric):
                    metrics_with_values.add(metric)
            out["derivatives_unit_metadata_missing"] += _derivatives_unit_metadata_missing(row)
            continue
        if row_type != "fade_short_review_candidate":
            continue
        opportunity = str(row.get("opportunity_type") or "").upper()
        crowding = str(row.get("crowding_class") or "").casefold()
        evidence = [str(item) for item in row.get("crowding_exhaustion_evidence") or () if str(item)]
        warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        disclaimer = str(row.get("research_only_disclaimer") or "")
        state = row.get("derivatives_state_snapshot") if isinstance(row.get("derivatives_state_snapshot"), Mapping) else row
        if opportunity == "FADE_SHORT_REVIEW":
            if not bool(row.get("completed_move")):
                out["fade_review_without_completed_move"] += 1
            if not bool(row.get("fade_requirements_met")) or not evidence:
                out["fade_review_without_crowding_exhaustion"] += 1
            if "Research-only" not in disclaimer or "Not a trade signal" not in disclaimer:
                out["fade_review_notification_missing_disclaimer"] += 1
            freshness = str(state.get("derivatives_snapshot_freshness_status") or state.get("freshness_status") or "").casefold()
            if freshness in {"stale", "expired"}:
                out["stale_derivatives_snapshot_promoted_fade_review"] += 1
        if bool(row.get("triggered_fade_created")) or str(row.get("signal_type") or "").upper() == "TRIGGERED_FADE":
            out["fade_review_created_triggered_fade"] += 1
        if bool(row.get("normal_rsi_signal_written")):
            out["fade_review_created_normal_rsi_signal"] += 1
        if opportunity == "CONFIRMED_LONG_RESEARCH" and crowding in {"high", "extreme"}:
            if not any("crowding" in warning.casefold() for warning in warnings):
                out["confirmed_long_crowded_without_warning"] += 1
    for metric in sorted(implemented_claims - metrics_with_values):
        if metric:
            out["derivatives_metric_claim_implemented_missing"] += 1
    return out


def _derivatives_metric_has_value(row: Mapping[str, Any], metric: str) -> bool:
    values = {
        "open_interest": ("open_interest", "open_interest_delta_1h", "open_interest_delta_4h", "open_interest_delta_24h"),
        "funding_rate": ("funding_rate",),
        "predicted_funding": ("predicted_funding_rate",),
        "liquidations": ("liquidation_long_usd", "liquidation_short_usd", "liquidation_imbalance"),
        "long_short_ratio": ("long_short_ratio",),
        "basis": ("basis",),
        "perp_volume": ("perp_volume", "perp_spot_volume_ratio"),
    }
    return any(row.get(key) not in (None, "", [], {}, ()) for key in values.get(metric, ()))


def _derivatives_unit_metadata_missing(row: Mapping[str, Any]) -> int:
    checks = (
        ("open_interest", "open_interest_unit"),
        ("funding_rate", "funding_rate_unit"),
        ("predicted_funding", "funding_rate_unit"),
        ("basis", "basis_unit"),
        ("liquidations", "liquidation_unit"),
        ("perp_volume", "volume_unit"),
    )
    missing = 0
    for metric, unit_key in checks:
        if _derivatives_metric_has_value(row, metric) and not str(row.get(unit_key) or "").strip():
            missing += 1
    return missing


def _derivatives_row_has_secret_leak(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lower = str(key).casefold()
            if any(token in lower for token in ("api_key", "auth_token", "secret", "token")):
                text = str(nested).strip()
                if text and text not in {"<redacted>", "redacted", "***", "none", "null"}:
                    return True
            if _derivatives_row_has_secret_leak(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_derivatives_row_has_secret_leak(item) for item in value)
    return False


def _integrated_radar_artifact_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    research_card_paths: Iterable[Path] = (),
    daily_brief_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    source_coverage_json_path: str | Path | None = None,
    delivery_path: str | Path | None = None,
    outcome_path: str | Path | None = None,
    preview_path: str | Path | None = None,
) -> dict[str, int]:
    out = {
        "integrated_candidate_missing_opportunity_type": 0,
        "integrated_candidate_missing_market_state_snapshot": 0,
        "integrated_confirmed_long_without_source_market": 0,
        "integrated_early_long_without_fresh_strong_source": 0,
        "integrated_fade_without_crowding_exhaustion": 0,
        "integrated_risk_without_evidence": 0,
        "integrated_market_anomaly_confirmed": 0,
        "integrated_cryptopanic_confirmed": 0,
        "integrated_major_pair_early_long": 0,
        "integrated_input_manifest_missing": 0,
        "integrated_source_coverage_json_missing": 0,
        "integrated_candidate_core_missing": 0,
        "integrated_candidate_core_opportunity_type_mismatch": 0,
        "integrated_candidate_core_market_state_mismatch": 0,
        "integrated_candidate_core_route_level_mismatch": 0,
        "integrated_candidate_core_reason_code_loss": 0,
        "integrated_candidate_core_source_url_loss": 0,
        "integrated_candidate_core_official_event_loss": 0,
        "integrated_candidate_core_scheduled_event_loss": 0,
        "integrated_candidate_core_unlock_event_loss": 0,
        "integrated_candidate_core_derivatives_loss": 0,
        "integrated_candidate_card_opportunity_type_mismatch": 0,
        "integrated_candidate_card_why_now_mismatch": 0,
        "integrated_major_pair_card_early_long": 0,
        "integrated_card_generic_lane_override": 0,
        "card_opportunity_lane_core_mismatch": 0,
        "integrated_candidate_card_official_event_missing": 0,
        "integrated_candidate_card_source_url_missing": 0,
        "integrated_candidate_core_crowding_metadata_loss": 0,
        "derivatives_card_metric_claim_without_data": 0,
        "integrated_coinalyze_crowding_card_missing": 0,
        "integrated_coinalyze_loaded_no_rows_attached": 0,
        "integrated_coinalyze_missing_skip_reason": 0,
        "integrated_coinalyze_stale_loaded_without_warning": 0,
        "integrated_coinalyze_loaded_from_stale_namespace": 0,
        "integrated_fade_card_crowding_unknown": 0,
        "integrated_fade_card_missing_disclaimer": 0,
        "integrated_confirmed_long_crowding_warning_hidden": 0,
        "integrated_market_confirmation_display_contradiction": 0,
        "integrated_derivatives_display_contradiction": 0,
        "integrated_manifest_mixed_timestamp_pair": 0,
        "integrated_core_silent_upgrade": 0,
        "integrated_diagnostic_visible_in_default_operator_section": 0,
        "integrated_preview_missing_disclaimer": 0,
        "integrated_delivery_ledger_missing": 0,
        "integrated_preview_lane_mismatch": 0,
        "integrated_delivery_missing_disclaimer": 0,
        "integrated_delivery_sent_in_no_send": 0,
        "integrated_delivery_side_effect_flag": 0,
        "integrated_delivery_missing_skip_reasons": 0,
        "integrated_delivery_card_path_absolute": 0,
        "integrated_delivery_card_path_not_rendered": 0,
        "integrated_operator_markdown_absolute_path": 0,
        "operator_structured_path_absolute": 0,
        "integrated_legacy_preview_alerts_wording": 0,
        "integrated_manifest_daily_brief_unavailable": 0,
        "integrated_outcome_missing_for_candidate": 0,
        "integrated_outcome_side_effect_flag": 0,
        "integrated_outcome_schema_missing": 0,
        "integrated_outcome_missing_identity": 0,
        "integrated_outcome_returns_without_price": 0,
        "integrated_outcome_diagnostic_in_performance": 0,
        "integrated_calibration_diagnostic_in_main_priors": 0,
        "integrated_calibration_prior_safety_missing": 0,
        "integrated_calibration_legacy_alias_top_level": 0,
        "integrated_outcome_return_double_scaled": 0,
        "integrated_outcome_missing_data_unlabeled": 0,
        "integrated_outcome_thesis_move_missing": 0,
        "integrated_outcome_card_thesis_interpretation_missing": 0,
        "integrated_outcome_card_trade_wording": 0,
        "integrated_created_normal_rsi_signal": 0,
        "integrated_created_triggered_fade": 0,
    }
    materialized_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    core_by_id = {str(row.get("core_opportunity_id") or ""): dict(row) for row in core_rows if isinstance(row, Mapping) and row.get("core_opportunity_id")}
    card_text_by_core = _card_text_by_core(research_card_paths)
    row_count = 0
    for row in materialized_rows:
        row_count += 1
        lane = str(row.get("opportunity_type") or "").strip().upper()
        if not lane:
            out["integrated_candidate_missing_opportunity_type"] += 1
            continue
        source_origins = {str(item).strip().casefold() for item in row.get("source_origins") or () if str(item).strip()}
        source_packs = {str(item).strip().casefold() for item in row.get("source_packs") or () if str(item).strip()}
        if not source_origins:
            source_origin = str(row.get("source_origin") or "").strip().casefold()
            if source_origin:
                source_origins.add(source_origin)
        if not source_packs:
            source_pack = str(row.get("source_pack") or "").strip().casefold()
            if source_pack:
                source_packs.add(source_pack)
        snapshot = row.get("market_state_snapshot")
        if lane not in {"UNCONFIRMED_RESEARCH", "DIAGNOSTIC"} and (not isinstance(snapshot, Mapping) or not snapshot):
            out["integrated_candidate_missing_market_state_snapshot"] += 1
        source_met = _truthy(row.get("source_requirements_met"))
        market_met = _truthy(row.get("market_requirements_met"))
        fade_met = _truthy(row.get("fade_requirements_met"))
        risk_met = _truthy(row.get("risk_requirements_met"))
        source_strength = str(row.get("source_strength") or "").casefold()
        market_state = str(row.get("market_state_class") or row.get("market_state") or "").casefold()
        if lane == "CONFIRMED_LONG_RESEARCH" and (not source_met or not market_met):
            out["integrated_confirmed_long_without_source_market"] += 1
        if lane == "EARLY_LONG_RESEARCH" and (
            source_strength not in {"strong", "official_structured"}
            or market_state != "no_reaction"
        ):
            out["integrated_early_long_without_fresh_strong_source"] += 1
        if lane == "FADE_SHORT_REVIEW" and (
            not fade_met
            or market_state not in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"}
        ):
            out["integrated_fade_without_crowding_exhaustion"] += 1
        if lane == "RISK_ONLY" and not (
            risk_met
            or row.get("unlock_event")
            or "unlock_supply_pack" in source_packs
            or str(row.get("event_type") or "").casefold() in {"unlock", "delisting", "exploit"}
        ):
            out["integrated_risk_without_evidence"] += 1
        if lane == "CONFIRMED_LONG_RESEARCH" and source_origins == {"market_anomaly"}:
            out["integrated_market_anomaly_confirmed"] += 1
        if lane == "CONFIRMED_LONG_RESEARCH" and any("cryptopanic" in item for item in source_packs) and not (
            source_origins - {"source_news", "news", "cryptopanic"}
        ):
            out["integrated_cryptopanic_confirmed"] += 1
        if lane == "EARLY_LONG_RESEARCH" and _truthy(row.get("major_pair_simple_announcement")):
            out["integrated_major_pair_early_long"] += 1
        if _truthy(row.get("normal_rsi_signal_written")):
            out["integrated_created_normal_rsi_signal"] += 1
        if _truthy(row.get("triggered_fade_created")) or str(row.get("signal_type") or "").upper() == "TRIGGERED_FADE":
            out["integrated_created_triggered_fade"] += 1
        _integrated_candidate_core_card_conflicts(row, core_by_id, card_text_by_core, out)
    if row_count and manifest_path is not None and not Path(manifest_path).exists():
        out["integrated_input_manifest_missing"] += 1
    elif row_count and manifest_path is not None:
        out["integrated_manifest_mixed_timestamp_pair"] += _integrated_manifest_mixed_timestamp_pairs(manifest_path)
        coinalyze_conflicts = _integrated_coinalyze_manifest_conflicts(manifest_path, materialized_rows)
        for key, value in coinalyze_conflicts.items():
            out[key] += value
    if row_count and source_coverage_json_path is not None and not Path(source_coverage_json_path).exists():
        out["integrated_source_coverage_json_missing"] += 1
    if row_count and daily_brief_path is not None:
        try:
            daily_text = Path(daily_brief_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            daily_text = ""
        if (
            manifest_path is not None
            and Path(manifest_path).exists()
            and "Input manifest: not available" in daily_text
        ):
            out["integrated_manifest_daily_brief_unavailable"] += 1
        if _daily_brief_has_integrated_diagnostic_leak(daily_text, materialized_rows):
            out["integrated_diagnostic_visible_in_default_operator_section"] += 1
    if row_count and preview_path is not None:
        try:
            preview_text = Path(preview_path).read_text(encoding="utf-8")
        except OSError:
            preview_text = ""
        if "Research-only" not in preview_text or "Not a trade signal" not in preview_text:
            out["integrated_preview_missing_disclaimer"] += 1
        if re.search(r"\bAlertable decisions:.*\bAlerts:\s*\d+", preview_text):
            out["integrated_legacy_preview_alerts_wording"] += 1
        if event_artifact_paths.has_operator_absolute_path(preview_text):
            out["integrated_operator_markdown_absolute_path"] += 1
    for operator_path in (*research_card_paths, *(path for path in (daily_brief_path, preview_path) if path is not None)):
        try:
            text = Path(operator_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if event_artifact_paths.has_operator_absolute_path(text):
            out["integrated_operator_markdown_absolute_path"] += 1
    delivery_rows = _read_jsonl(delivery_path) if delivery_path is not None and Path(delivery_path).exists() else []
    if row_count and delivery_path is not None and not Path(delivery_path).exists():
        out["integrated_delivery_ledger_missing"] += 1
    if delivery_rows:
        out.update(_merge_conflicts(out, _integrated_delivery_conflicts(delivery_rows, preview_path=preview_path)))
    outcome_rows = _read_jsonl(outcome_path) if outcome_path is not None and Path(outcome_path).exists() else []
    if outcome_rows:
        out.update(_merge_conflicts(out, _integrated_outcome_conflicts(materialized_rows, outcome_rows)))
    if outcome_path is not None:
        priors_path = Path(outcome_path).parent / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME
        out.update(_merge_conflicts(out, _integrated_calibration_conflicts(priors_path)))
    out["operator_structured_path_absolute"] += _structured_operator_path_conflicts(
        (*materialized_rows, *core_rows, *delivery_rows, *outcome_rows)
    )
    return out


def _merge_conflicts(base: Mapping[str, int], updates: Mapping[str, int]) -> dict[str, int]:
    out = dict(base)
    for key, value in updates.items():
        out[key] = int(out.get(key, 0)) + int(value or 0)
    return out


def _integrated_delivery_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    preview_path: str | Path | None,
) -> dict[str, int]:
    out = {
        "integrated_preview_lane_mismatch": 0,
        "integrated_delivery_missing_disclaimer": 0,
        "integrated_delivery_sent_in_no_send": 0,
        "integrated_delivery_side_effect_flag": 0,
        "integrated_delivery_missing_skip_reasons": 0,
        "integrated_delivery_card_path_absolute": 0,
        "integrated_delivery_card_path_not_rendered": 0,
        "integrated_operator_markdown_absolute_path": 0,
        "operator_structured_path_absolute": 0,
    }
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    preview_text = ""
    if preview_path is not None:
        try:
            preview_text = Path(preview_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            preview_text = ""
    for row in materialized:
        message = str(row.get("message_text") or "")
        if "Research-only" not in message or "Not a trade signal" not in message:
            out["integrated_delivery_missing_disclaimer"] += 1
        if row.get("sent") and row.get("no_send_rehearsal"):
            out["integrated_delivery_sent_in_no_send"] += 1
        for key in ("normal_rsi_signal_written", "triggered_fade_created", "paper_trade_created", "trade_created"):
            if _truthy(row.get(key)):
                out["integrated_delivery_side_effect_flag"] += 1
        if int(row.get("skipped_item_count") or 0) > 0 and not row.get("skipped_items"):
            out["integrated_delivery_missing_skip_reasons"] += 1
        if event_artifact_paths.has_operator_absolute_path(row.get("card_paths") or ()):
            out["integrated_delivery_card_path_absolute"] += 1
        card_paths = [str(item) for item in _tuple_value(row.get("card_paths")) if str(item).strip()]
        if card_paths:
            if "Card: none" in message:
                out["integrated_delivery_card_path_not_rendered"] += 1
            elif not any(path in message or Path(path).name in message for path in card_paths):
                out["integrated_delivery_card_path_not_rendered"] += 1
        if event_artifact_paths.has_operator_absolute_path(message):
            out["integrated_operator_markdown_absolute_path"] += 1
        out["operator_structured_path_absolute"] += _structured_operator_path_conflicts((row,))
        lane_title = str(row.get("lane_title") or "")
        if preview_text and lane_title and lane_title not in preview_text:
            out["integrated_preview_lane_mismatch"] += 1
    return out


def _integrated_outcome_conflicts(
    candidates: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "integrated_outcome_missing_for_candidate": 0,
        "integrated_outcome_side_effect_flag": 0,
        "integrated_outcome_schema_missing": 0,
        "integrated_outcome_missing_identity": 0,
        "integrated_outcome_returns_without_price": 0,
        "integrated_outcome_diagnostic_in_performance": 0,
        "integrated_outcome_return_double_scaled": 0,
        "integrated_outcome_missing_data_unlabeled": 0,
        "integrated_outcome_thesis_move_missing": 0,
    }
    outcome_rows = [dict(row) for row in outcomes if isinstance(row, Mapping)]
    outcome_by_candidate = {str(row.get("candidate_id") or ""): row for row in outcome_rows if row.get("candidate_id")}
    for candidate in candidates:
        if str(candidate.get("opportunity_type") or "") == "DIAGNOSTIC":
            continue
        if str(candidate.get("candidate_id") or "") not in outcome_by_candidate:
            out["integrated_outcome_missing_for_candidate"] += 1
    for row in outcome_rows:
        for key in ("normal_rsi_signal_written", "triggered_fade_created", "paper_trade_created", "trade_created"):
            if _truthy(row.get(key)):
                out["integrated_outcome_side_effect_flag"] += 1
        if not _truthy(row.get("no_trade_created")) or not _truthy(row.get("no_paper_trade_created")):
            out["integrated_outcome_schema_missing"] += 1
        if not (row.get("symbol") and row.get("coin_id")):
            out["integrated_outcome_missing_identity"] += 1
        if row.get("primary_horizon_return") is not None and row.get("price_at_observation") in (None, ""):
            out["integrated_outcome_returns_without_price"] += 1
        if str(row.get("opportunity_type") or "") == "DIAGNOSTIC" and _truthy(row.get("include_in_performance")):
            out["integrated_outcome_diagnostic_in_performance"] += 1
        returns = [row.get("primary_horizon_return")]
        horizons = row.get("horizons")
        if isinstance(horizons, Mapping):
            returns.extend(horizons.values())
        if str(row.get("outcome_status") or "").casefold() in {"filled", "partial"}:
            if not _tuple_value(row.get("outcome_horizons")):
                out["integrated_outcome_schema_missing"] += 1
            required_mappings = (
                "return_by_horizon",
                "relative_return_vs_btc_by_horizon",
                "relative_return_vs_eth_by_horizon",
                "max_favorable_excursion_by_window",
                "max_adverse_excursion_by_window",
            )
            for key in required_mappings:
                if not isinstance(row.get(key), Mapping):
                    out["integrated_outcome_schema_missing"] += 1
                    break
            thesis_required_mappings = (
                "thesis_return_by_horizon",
                "thesis_relative_return_vs_btc_by_horizon",
                "thesis_favorable_excursion_by_window",
                "thesis_adverse_excursion_by_window",
            )
            for key in thesis_required_mappings:
                if not isinstance(row.get(key), Mapping):
                    out["integrated_outcome_schema_missing"] += 1
                    break
            if not str(row.get("thesis_direction") or "").strip() or not str(
                row.get("thesis_outcome_interpretation") or ""
            ).strip():
                out["integrated_outcome_schema_missing"] += 1
            if not (
                row.get("benchmark_btc_price_at_observation") is not None
                or row.get("benchmark_eth_price_at_observation") is not None
            ):
                out["integrated_outcome_schema_missing"] += 1
        lane = str(row.get("opportunity_type") or "").upper()
        label = str(row.get("outcome_label") or "")
        thesis_primary = _safe_float(row.get("thesis_primary_move"))
        if lane == "FADE_SHORT_REVIEW" and label in {"fade_review_good", "useful"}:
            if thesis_primary is None or thesis_primary <= 0:
                out["integrated_outcome_thesis_move_missing"] += 1
        if lane == "RISK_ONLY" and label in {"risk_validated", "useful"}:
            if thesis_primary is None or thesis_primary <= 0:
                out["integrated_outcome_thesis_move_missing"] += 1
        if any(isinstance(value, (int, float)) and abs(float(value)) > 5.0 for value in returns):
            out["integrated_outcome_return_double_scaled"] += 1
        if str(row.get("outcome_status") or "") == "missing_data" and not row.get("missing_data_reason"):
            out["integrated_outcome_missing_data_unlabeled"] += 1
    return out


def _integrated_calibration_conflicts(path: str | Path | None) -> dict[str, int]:
    out = {
        "integrated_calibration_diagnostic_in_main_priors": 0,
        "integrated_calibration_prior_safety_missing": 0,
        "integrated_calibration_legacy_alias_top_level": 0,
    }
    if path is None or not Path(path).exists():
        return out
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(data, Mapping):
        return out
    priors = data.get("opportunity_type_priors")
    if not isinstance(priors, Mapping):
        return out
    if "DIAGNOSTIC" in {str(key).upper() for key in priors}:
        out["integrated_calibration_diagnostic_in_main_priors"] += 1
    if not _truthy(data.get("recommendation_only")) or _truthy(data.get("auto_apply")) or _truthy(data.get("eligible_for_auto_apply")):
        out["integrated_calibration_prior_safety_missing"] += 1
    for value in priors.values():
        if not isinstance(value, Mapping):
            out["integrated_calibration_prior_safety_missing"] += 1
            continue
        if ("useful" in value or "junk" in value) and not isinstance(value.get("legacy_aliases"), Mapping):
            out["integrated_calibration_legacy_alias_top_level"] += 1
        sample_size = _safe_float(value.get("sample_size"))
        min_sample_size = _safe_float(value.get("min_sample_size"))
        has_warning = bool(str(value.get("min_sample_warning") or "").strip())
        if (
            sample_size is None
            or min_sample_size is None
            or value.get("confidence") in (None, "")
            or not _truthy(value.get("recommendation_only"))
            or _truthy(value.get("eligible_for_auto_apply"))
            or _truthy(value.get("auto_apply"))
            or not str(value.get("excluded_from_auto_apply_reason") or "").strip()
            or not str(value.get("last_updated_at") or "").strip()
            or not str(value.get("horizon_basis") or "").strip()
        ):
            out["integrated_calibration_prior_safety_missing"] += 1
            continue
        if sample_size < min_sample_size and not has_warning:
            out["integrated_calibration_prior_safety_missing"] += 1
    return out


def _structured_operator_path_conflicts(rows: Iterable[Mapping[str, Any]]) -> int:
    conflicts = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        conflicts += _structured_operator_path_conflict_count(row)
    return conflicts


def _structured_operator_path_file_conflicts(namespace_dir: str | Path) -> int:
    base = Path(namespace_dir)
    if not base.exists() or not base.is_dir():
        return 0
    conflicts = 0
    for path in sorted((*base.glob("*.json"), *base.glob("*.jsonl"))):
        if path.name.startswith("."):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                conflicts += _structured_operator_path_conflict_count(payload)
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        conflicts += _structured_operator_path_conflict_count(payload)
    return conflicts


def _artifact_namespace_dir(*paths: str | Path | None) -> Path | None:
    for path in paths:
        if path in (None, ""):
            continue
        return Path(path).expanduser().parent
    return None


def _structured_operator_path_conflict_count(value: Any, *, key_name: str = "") -> int:
    if _operator_structured_path_debug_field(key_name):
        return 0
    if isinstance(value, Mapping):
        return sum(
            _structured_operator_path_conflict_count(item, key_name=str(key))
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return sum(_structured_operator_path_conflict_count(item, key_name=key_name) for item in value)
    if _operator_structured_path_field(key_name) and event_artifact_paths.has_operator_absolute_path(value):
        return 1
    return 0


def _operator_structured_path_debug_field(key_name: str) -> bool:
    return str(key_name or "").casefold().endswith("_abs_debug")


def _operator_structured_path_field(key_name: str) -> bool:
    clean = str(key_name or "").casefold()
    if not clean or _operator_structured_path_debug_field(clean):
        return False
    if clean.endswith("_relpath") or clean.endswith("_relpaths"):
        return False
    return (
        clean.endswith("_path")
        or clean.endswith("_paths")
        or clean.endswith("_dir")
        or clean.endswith("_dirs")
        or "card_path" in clean
    )


def _integrated_candidate_core_card_conflicts(
    candidate: Mapping[str, Any],
    core_by_id: Mapping[str, Mapping[str, Any]],
    card_text_by_core: Mapping[str, str],
    out: dict[str, int],
) -> None:
    if str(candidate.get("opportunity_type") or "").strip().upper() == "DIAGNOSTIC":
        return
    core_id = str(candidate.get("core_opportunity_id") or "").strip()
    if not core_id:
        return
    core = core_by_id.get(core_id)
    if core is None:
        out["integrated_candidate_core_missing"] += 1
        return
    candidate_lane = str(candidate.get("opportunity_type") or "").strip()
    core_lane = str(core.get("opportunity_type") or "").strip()
    if candidate_lane and core_lane and candidate_lane != core_lane:
        out["integrated_candidate_core_opportunity_type_mismatch"] += 1
    if _integrated_opportunity_rank(core_lane) > _integrated_opportunity_rank(candidate_lane):
        out["integrated_core_silent_upgrade"] += 1
    candidate_market = str(candidate.get("market_state_class") or candidate.get("market_state") or "").strip()
    core_market = str(core.get("market_state_class") or core.get("market_state") or "").strip()
    if candidate_market and core_market and candidate_market != core_market:
        out["integrated_candidate_core_market_state_mismatch"] += 1
    for key in ("final_route_after_quality_gate", "final_state_after_quality_gate", "final_opportunity_level", "opportunity_level"):
        candidate_value = str(candidate.get(key) or "").strip()
        core_value = str(core.get(key) or "").strip()
        if candidate_value and core_value and candidate_value != core_value:
            out["integrated_candidate_core_route_level_mismatch"] += 1
            break
    candidate_reasons = set(_tuple_value(candidate.get("reason_codes")))
    core_reasons = set(_tuple_value(core.get("reason_codes")))
    if candidate_reasons and not candidate_reasons.issubset(core_reasons):
        out["integrated_candidate_core_reason_code_loss"] += 1
    candidate_url = str(candidate.get("source_url") or candidate.get("latest_source_url") or "").strip()
    core_url = str(core.get("source_url") or core.get("latest_source_url") or core.get("official_exchange_url") or "").strip()
    if candidate_url and not core_url:
        out["integrated_candidate_core_source_url_loss"] += 1
    if isinstance(candidate.get("official_exchange_event"), Mapping) and not isinstance(core.get("official_exchange_event"), Mapping):
        out["integrated_candidate_core_official_event_loss"] += 1
    if isinstance(candidate.get("scheduled_catalyst_event"), Mapping) and not isinstance(core.get("scheduled_catalyst_event"), Mapping):
        out["integrated_candidate_core_scheduled_event_loss"] += 1
    if isinstance(candidate.get("unlock_event"), Mapping) and not isinstance(core.get("unlock_event"), Mapping):
        out["integrated_candidate_core_unlock_event_loss"] += 1
    if isinstance(candidate.get("derivatives_state_snapshot"), Mapping) and not isinstance(core.get("derivatives_state_snapshot"), Mapping):
        out["integrated_candidate_core_derivatives_loss"] += 1
    if str(candidate_lane).upper() == "FADE_SHORT_REVIEW":
        if not str(core.get("crowding_class") or "").strip() or not str(core.get("fade_readiness") or "").strip():
            out["integrated_candidate_core_crowding_metadata_loss"] += 1
        if not _tuple_value(core.get("crowding_exhaustion_evidence")):
            out["integrated_candidate_core_crowding_metadata_loss"] += 1
    card_text = card_text_by_core.get(core_id, "")
    if not card_text:
        return
    derivatives_state = candidate.get("derivatives_state_snapshot")
    if not isinstance(derivatives_state, Mapping):
        derivatives_state = core.get("derivatives_state_snapshot") if isinstance(core.get("derivatives_state_snapshot"), Mapping) else {}
    if derivatives_state:
        if not _derivatives_metric_has_value(derivatives_state, "predicted_funding") and re.search(
            r"(?i)\bpredicted(?: funding)?=(?:n/a|[+-]?\d+(?:\.\d+)?%)",
            card_text,
        ):
            out["derivatives_card_metric_claim_without_data"] += 1
        if not _derivatives_metric_has_value(derivatives_state, "basis") and re.search(
            r"(?im)^-\s*Basis:\s*(?:n/a|[+-]?\d+(?:\.\d+)?%)",
            card_text,
        ):
            out["derivatives_card_metric_claim_without_data"] += 1
    has_coinalyze_crowding = (
        _integrated_row_has_coinalyze(candidate)
        and (
            str(candidate.get("crowding_class") or core.get("crowding_class") or "").casefold() in {"moderate", "high", "extreme"}
            or bool(_tuple_value(candidate.get("crowding_exhaustion_evidence") or core.get("crowding_exhaustion_evidence")))
        )
    )
    if has_coinalyze_crowding and "coinalyze source:" not in card_text.casefold():
        out["integrated_coinalyze_crowding_card_missing"] += 1
    card_lane = _markdown_bullet_value(card_text, "Opportunity type", section="Opportunity Lane")
    core_lane_lit = str(core.get("opportunity_type") or "").strip()
    if candidate_lane and card_lane and card_lane != candidate_lane:
        out["integrated_candidate_card_opportunity_type_mismatch"] += 1
    if core_lane_lit and card_lane and card_lane != core_lane_lit:
        out["card_opportunity_lane_core_mismatch"] += 1
    if (
        str(candidate.get("symbol") or "").upper() in {"BTC", "ETH", "USDT", "USDC", "FDUSD"}
        and _truthy(candidate.get("major_pair_simple_announcement"))
        and card_lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}
    ):
        out["integrated_major_pair_card_early_long"] += 1
    card_why = _markdown_bullet_value(card_text, "Why now", section="Opportunity Lane")
    candidate_why = str(candidate.get("why_now") or "").strip()
    if candidate_why and card_why and candidate_why != card_why:
        out["integrated_candidate_card_why_now_mismatch"] += 1
    if card_why and "strong source with no reaction" in card_why.casefold() and candidate_why and candidate_why != card_why:
        out["integrated_card_generic_lane_override"] += 1
    if candidate_lane and not card_lane and candidate_lane not in card_text:
        out["integrated_candidate_card_opportunity_type_mismatch"] += 1
    if str(candidate_lane).upper() == "FADE_SHORT_REVIEW":
        if "Research-only" not in card_text or "Not a trade signal" not in card_text:
            out["integrated_fade_card_missing_disclaimer"] += 1
        if "Crowding class: unknown" in card_text or "Fade readiness: unknown" in card_text:
            out["integrated_fade_card_crowding_unknown"] += 1
        if "Derivatives crowding: n/a" in card_text or "Derivatives crowding: not available" in card_text:
            out["integrated_derivatives_display_contradiction"] += 1
    if str(candidate_lane).upper() in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        outcome_section = _markdown_section(card_text, "Outcome Tracking")
        if outcome_section and (
            "Thesis-favorable move:" not in outcome_section
            or "Thesis interpretation:" not in outcome_section
        ):
            out["integrated_outcome_card_thesis_interpretation_missing"] += 1
        lower_outcome = outcome_section.casefold()
        if (
            "profit" in lower_outcome
            or "entry" in lower_outcome
            or "position" in lower_outcome
            or ("pnl" in lower_outcome and "not pnl" not in lower_outcome)
        ):
            out["integrated_outcome_card_trade_wording"] += 1
    if str(candidate_lane).upper() == "CONFIRMED_LONG_RESEARCH":
        if "confirmed_long_derivatives_crowding_warning" in _tuple_value(candidate.get("warnings")) and "confirmed_long_derivatives_crowding_warning" not in card_text:
            out["integrated_confirmed_long_crowding_warning_hidden"] += 1
        if "Market confirmation: none" in card_text and "Integrated market state:" not in card_text:
            out["integrated_market_confirmation_display_contradiction"] += 1
    if _truthy(candidate.get("market_requirements_met")) and "Market confirmation: none" in card_text and "Integrated market state:" not in card_text:
        out["integrated_market_confirmation_display_contradiction"] += 1
    official_event = candidate.get("official_exchange_event")
    if isinstance(official_event, Mapping):
        expected = [
            str(official_event.get("exchange") or "").strip(),
            str(official_event.get("event_type") or "").strip(),
            str(official_event.get("source_url") or "").strip(),
        ]
        if "Official Exchange Evidence" not in card_text and not any(value and value in card_text for value in expected):
            out["integrated_candidate_card_official_event_missing"] += 1
    if candidate_url and candidate_url not in card_text:
        out["integrated_candidate_card_source_url_missing"] += 1


def _integrated_opportunity_rank(value: object) -> int:
    text = str(value or "").strip().upper()
    ranks = {
        "DIAGNOSTIC": 0,
        "UNCONFIRMED_RESEARCH": 1,
        "EARLY_LONG_RESEARCH": 2,
        "RISK_ONLY": 2,
        "CONFIRMED_LONG_RESEARCH": 3,
        "FADE_SHORT_REVIEW": 3,
    }
    return ranks.get(text, 0)


def _markdown_bullet_value(text: str, label: str, *, section: str | None = None) -> str | None:
    body = text
    if section:
        marker = f"## {section}"
        idx = body.find(marker)
        if idx >= 0:
            body = body[idx + len(marker):]
            next_section = body.find("\n## ")
            if next_section >= 0:
                body = body[:next_section]
    pattern = re.compile(rf"^\s*-\s*{re.escape(label)}:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(body)
    return match.group(1).strip() if match else None


def _markdown_section(text: str, section: str) -> str:
    marker = f"## {section}"
    idx = text.find(marker)
    if idx < 0:
        return ""
    body = text[idx + len(marker):]
    next_section = body.find("\n## ")
    if next_section >= 0:
        body = body[:next_section]
    return body.strip()


def _integrated_manifest_mixed_timestamp_pairs(path: str | Path) -> int:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(data, Mapping):
        return 0
    rows = data.get("sidecars")
    if not isinstance(rows, list):
        return 0
    conflicts = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("sidecar_research_observed_at") and row.get("sidecar_wall_started_at") and row.get("sidecar_wall_finished_at"):
            continue
        started = str(row.get("started_at") or "")
        finished = str(row.get("finished_at") or "")
        research = str(data.get("research_observed_at") or row.get("research_observed_at") or "")
        if started and finished and research and started == research and finished != research:
            conflicts += 1
    return conflicts


def _integrated_coinalyze_manifest_conflicts(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "integrated_coinalyze_loaded_no_rows_attached": 0,
        "integrated_coinalyze_missing_skip_reason": 0,
        "integrated_coinalyze_stale_loaded_without_warning": 0,
        "integrated_coinalyze_loaded_from_stale_namespace": 0,
    }
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(data, Mapping):
        return out
    coinalyze = _coinalyze_manifest_row(data)
    if not coinalyze:
        return out
    state_rows = _as_int(coinalyze.get("coinalyze_derivatives_state_rows_loaded") or data.get("coinalyze_derivatives_state_rows_loaded"))
    crowding_rows = _as_int(coinalyze.get("coinalyze_crowding_candidates_loaded") or data.get("coinalyze_crowding_candidates_loaded"))
    fade_rows = _as_int(coinalyze.get("coinalyze_fade_review_candidates_loaded") or data.get("coinalyze_fade_review_candidates_loaded"))
    loaded_count = state_rows + crowding_rows + fade_rows
    skip_reason = str(coinalyze.get("coinalyze_skip_reason") or data.get("coinalyze_skip_reason") or "").strip()
    mode = str(coinalyze.get("mode") or "").strip().casefold()
    warnings = {
        str(item).strip().casefold()
        for item in (*_tuple_value(coinalyze.get("warnings")), *_tuple_value(data.get("warnings")))
        if str(item).strip()
    }
    namespace_status = str(
        coinalyze.get("coinalyze_artifact_namespace_status")
        or data.get("coinalyze_artifact_namespace_status")
        or ""
    ).strip().casefold()
    freshness = str(
        coinalyze.get("coinalyze_freshness_status")
        or data.get("coinalyze_freshness_status")
        or ""
    ).strip().casefold()
    attached = sum(1 for row in rows if _integrated_row_has_coinalyze(row))
    if loaded_count > 0 and attached == 0 and not skip_reason:
        out["integrated_coinalyze_loaded_no_rows_attached"] += 1
    if (mode.startswith("skipped") or loaded_count == 0) and not skip_reason:
        out["integrated_coinalyze_missing_skip_reason"] += 1
    if loaded_count > 0 and freshness in {"stale", "expired"} and not any("coinalyze_freshness" in item for item in warnings):
        out["integrated_coinalyze_stale_loaded_without_warning"] += 1
    if loaded_count > 0 and namespace_status == event_alpha_namespace_status.STATUS_STALE_DEPRECATED:
        out["integrated_coinalyze_loaded_from_stale_namespace"] += 1
    return out


def _coinalyze_manifest_row(data: Mapping[str, Any]) -> Mapping[str, Any]:
    sidecars = data.get("sidecars")
    if isinstance(sidecars, list):
        for item in sidecars:
            if isinstance(item, Mapping) and str(item.get("sidecar_name") or "") == "coinalyze":
                return item
    if data.get("coinalyze_artifact_namespace") or data.get("coinalyze_skip_reason"):
        return data
    return {}


def _integrated_row_has_coinalyze(row: Mapping[str, Any]) -> bool:
    state = row.get("derivatives_state_snapshot")
    if not isinstance(state, Mapping):
        state = row.get("derivatives_snapshot") if isinstance(row.get("derivatives_snapshot"), Mapping) else {}
    return bool(
        row.get("coinalyze_derivatives_attached")
        or row.get("coinalyze_artifact_namespace")
        or row.get("coinalyze_source_artifact_path")
        or state.get("coinalyze_artifact_namespace")
        or state.get("coinalyze_source_artifact_path")
    )


def _daily_brief_has_integrated_diagnostic_leak(text: str, rows: Iterable[Mapping[str, Any]]) -> bool:
    diagnostic_symbols = {
        str(row.get("symbol") or "").strip()
        for row in rows
        if str(row.get("opportunity_type") or "").strip().upper() == "DIAGNOSTIC"
        and str(row.get("symbol") or "").strip()
    }
    if not diagnostic_symbols:
        return False
    diagnostics_pos = text.find("## Diagnostics Appendix")
    visible_text = text if diagnostics_pos < 0 else text[:diagnostics_pos]
    return any(f"{symbol}/" in visible_text for symbol in diagnostic_symbols)


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _opportunity_lane_risk_only_missing_evidence(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            " ".join(str(item) for item in row.get("opportunity_type_reason_codes") or row.get("reason_codes") or ()),
            " ".join(str(item) for item in row.get("why_not_alertable") or row.get("opportunity_type_why_not_alertable") or ()),
        )
    ).casefold()
    risk_tokens = (
        "exploit",
        "security",
        "delisting",
        "regulatory",
        "legal",
        "unlock",
        "supply",
        "liquidity_risk",
        "risk_off",
        "sell_pressure",
        "bridge_compromise",
        "chain_halt",
    )
    if any(token in text for token in risk_tokens):
        return False
    missing_tokens = ("strong_source_missing", "market_reaction_missing", "confirmed_long_requirements_not_met")
    return any(token in text for token in missing_tokens)


def _opportunity_lane_diagnostic_visible(row: Mapping[str, Any]) -> bool:
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or row.get("tier") or "").upper()
    level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").casefold()
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "").upper()
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_states = {"WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    return route in alertable_routes or state in alertable_states or level in {"validated_digest", "watchlist", "high_priority"}


def _opportunity_lane_cryptopanic_only_narrative(row: Mapping[str, Any]) -> bool:
    source_class = str(row.get("source_class") or "").casefold()
    reason_codes = {str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or row.get("reason_codes") or ()}
    if source_class != "cryptopanic_tagged" and "cryptopanic_currency_tag_match" not in reason_codes:
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            " ".join(str(item) for item in row.get("supporting_categories") or ()),
            " ".join(str(item) for item in row.get("supporting_impact_paths") or ()),
        )
    ).casefold()
    return any(token in text for token in ("fan", "sports", "proxy", "preipo", "pre-ipo", "rwa", "political_meme"))


def _raw_core_source_only_narrative(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            row.get("canonical_incident_name"),
            row.get("event_name"),
            row.get("latest_source_title"),
            " ".join(str(item) for item in row.get("supporting_categories") or ()),
            " ".join(str(item) for item in row.get("supporting_impact_paths") or ()),
        )
    ).casefold()
    narrative_tokens = (
        "fan_token",
        "fan token",
        "sports_fan",
        "sports fan",
        "world cup",
        "proxy",
        "preipo",
        "pre-ipo",
        "tokenized",
        "rwa",
        "political_meme",
        "venue_value",
    )
    if not any(token in text for token in narrative_tokens):
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    accepted = _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count"))
    market_level = str(row.get("market_confirmation_level") or row.get("market_reaction_confirmation") or "").casefold()
    freshness = str(row.get("market_context_freshness_status") or "").casefold()
    market_score = _raw_float_value(row.get("market_confirmation_score"))
    has_market = market_level in {"moderate", "strong"} or (market_score is not None and market_score >= 40)
    if freshness in {"missing", "stale", "unknown", "none", ""}:
        has_market = False
    return accepted <= 1 and not has_market


def _raw_core_cryptopanic_tag_only_direct_path(row: Mapping[str, Any]) -> bool:
    source_classes = {str(row.get("source_class") or "").casefold()}
    reason_codes = {str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or row.get("reason_codes") or ()}
    cryptopanic_tagged = "cryptopanic_tagged" in source_classes or "cryptopanic_currency_tag_match" in reason_codes
    if not cryptopanic_tagged:
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    if _raw_core_source_only_narrative(row):
        return True
    impact_path = str(row.get("impact_path_type") or row.get("primary_impact_path") or "").casefold()
    return impact_path == "unlock_supply_event" and _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count")) <= 1


def _raw_core_has_official_or_structured_evidence(row: Mapping[str, Any]) -> bool:
    values = {
        str(row.get("source_class") or "").casefold(),
        str(row.get("source_pack") or "").casefold(),
        *(str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or ()),
        *(str(item).casefold() for item in row.get("reason_codes") or ()),
    }
    return any(
        token in value
        for value in values
        for token in ("official", "structured", "tokenomist", "binance", "bybit", "exchange_listing", "direct_token_unlock_fact")
    )


def _raw_int_value(*values: Any) -> int:
    for value in values:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _raw_float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _source_coverage_metadata_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "source_pack_provider_status_missing": 0,
        "missing_provider_recommendations_missing": 0,
        "degraded_provider_absence_marked_meaningful": 0,
    }
    for row in rows:
        source_pack = str(row.get("source_pack") or row.get("evidence_acquisition_source_pack") or "").strip()
        if not source_pack:
            continue
        status = str(row.get("source_pack_coverage_status") or row.get("provider_coverage_status") or "").strip()
        has_source_coverage_metadata = any(
            key in row
            for key in (
                "source_pack_coverage_status",
                "provider_coverage_status",
                "providers_missing_for_confirmation",
                "providers_degraded_for_confirmation",
                "source_coverage_recommended_actions",
                "recommended_actions",
            )
        )
        if has_source_coverage_metadata and not status:
            out["source_pack_provider_status_missing"] += 1
        missing = _tuple_value(row.get("providers_missing_for_confirmation"))
        degraded = _tuple_value(row.get("providers_degraded_for_confirmation"))
        recs = _tuple_value(row.get("source_coverage_recommended_actions") or row.get("recommended_actions"))
        if (missing or degraded) and not recs:
            out["missing_provider_recommendations_missing"] += 1
        absence = bool(row.get("evidence_absence_is_meaningful") or row.get("evidence_absence_meaningful"))
        if status in {"degraded", "unavailable", "not_configured"} and absence:
            out["degraded_provider_absence_marked_meaningful"] += 1
    return out


def _source_coverage_report_conflicts(path: str | Path | None) -> dict[str, int]:
    out = {
        "source_coverage_report_missing": 0,
        "source_coverage_provider_status_unknown": 0,
        "source_coverage_provider_marked_healthy_without_observation": 0,
        "source_coverage_category_priority_missing": 0,
        "source_coverage_readiness_link_missing": 0,
        "source_coverage_context_provider_ranked_above_lane_critical": 0,
        "source_coverage_coinalyze_missing_linked_artifact": 0,
        "source_coverage_bybit_announcements_missing_linked_artifact": 0,
        "source_coverage_unlock_calendar_missing_linked_artifact": 0,
    }
    if path is None:
        return out
    report_path = Path(path)
    if not report_path.exists():
        if _source_coverage_report_required(report_path.parent):
            out["source_coverage_report_missing"] = 1
        return out
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError:
        out["source_coverage_report_missing"] = 1
        return out
    out["source_coverage_provider_status_unknown"] = text.count("provider coverage status: unknown")
    unknown_provider_lines = [
        line for line in text.splitlines()
        if line.strip().startswith("unknown/not observed providers:")
        and line.rsplit(":", 1)[-1].strip() not in {"", "none"}
    ]
    out["source_coverage_provider_status_unknown"] += len(unknown_provider_lines)
    blocks = text.split("\n- ")
    for block in blocks:
        healthy_line = next(
            (line for line in block.splitlines() if line.strip().startswith("healthy providers:")),
            "",
        )
        unknown_line = next(
            (line for line in block.splitlines() if line.strip().startswith("unknown/not observed providers:")),
            "",
        )
        healthy = set(_split_provider_line(healthy_line))
        unknown = set(_split_provider_line(unknown_line))
        if healthy & unknown:
            out["source_coverage_provider_marked_healthy_without_observation"] += len(healthy & unknown)
    if "Most useful next data source categories:" not in text:
        out["source_coverage_category_priority_missing"] = 1
    for artifact_name in (
        event_coinalyze_preflight.PREFLIGHT_JSON,
        event_coinalyze_preflight.PREFLIGHT_MD,
        event_coinalyze_preflight.REHEARSAL_JSON,
        event_coinalyze_preflight.REHEARSAL_MD,
        event_coinalyze_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_coinalyze_missing_linked_artifact"] += 1
    for artifact_name in (
        event_bybit_announcements_preflight.PREFLIGHT_JSON,
        event_bybit_announcements_preflight.PREFLIGHT_MD,
        event_bybit_announcements_preflight.REHEARSAL_JSON,
        event_bybit_announcements_preflight.REHEARSAL_MD,
        event_bybit_announcements_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_bybit_announcements_missing_linked_artifact"] += 1
    for artifact_name in (
        event_unlock_calendar_preflight.PREFLIGHT_JSON,
        event_unlock_calendar_preflight.PREFLIGHT_MD,
        event_unlock_calendar_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_unlock_calendar_missing_linked_artifact"] += 1
    readiness_present = "Live-provider activation readiness:" in text
    readiness_md_path = report_path.parent / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD
    readiness_json_path = report_path.parent / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON
    readiness_artifact_exists = readiness_md_path.exists() or readiness_json_path.exists()
    readiness_command_present = "event-alpha-live-provider-readiness" in text
    if readiness_artifact_exists:
        if not readiness_present or (
            event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD not in text
            and event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON not in text
        ):
            out["source_coverage_readiness_link_missing"] = 1
    elif not readiness_present or not readiness_command_present:
        out["source_coverage_readiness_link_missing"] = 1
    if "Recommended next activation order" not in text and "Most useful next data source categories:" not in text:
        out["source_coverage_readiness_link_missing"] = 1
    if "Most useful next data source categories:" in text:
        category_section = text.split("Most useful next data source categories:", 1)[1]
        category_section = category_section.split("Most useful next data source:", 1)[0]
        category_lower = category_section.casefold()
        context_pos = min(
            (pos for token in ("context/news", "cryptopanic", "rss", "gdelt") if (pos := category_lower.find(token)) >= 0),
            default=-1,
        )
        critical_pos = min(
            (
                pos
                for token in ("derivatives/oi/funding", "official exchange announcements", "structured unlock/calendar")
                if (pos := category_lower.find(token)) >= 0
            ),
            default=-1,
        )
        if context_pos >= 0 and critical_pos >= 0 and context_pos < critical_pos:
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
    if "Most useful next data source:" in text:
        top_section = text.split("Most useful next data source:", 1)[1]
        ranked = [line.strip() for line in top_section.splitlines() if line.strip().startswith("- ")][:5]
        full_ranked_section = "\n".join(
            line.strip() for line in top_section.splitlines() if line.strip().startswith("- ")
        )
        broad_idx = [
            idx for idx, line in enumerate(ranked)
            if any(token in line.casefold() for token in ("gdelt", "rss", "project_blog"))
        ]
        critical_idx = [
            idx for idx, line in enumerate(ranked)
            if any(token in line.casefold() for token in ("coinalyze", "tokenomist", "binance", "bybit", "coinbase", "kucoin", "okx"))
        ]
        if broad_idx and critical_idx and min(broad_idx) < min(critical_idx):
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
        coinalyze_gap = bool(
            re.search(
                r"(missing|degraded|backoff|not configured|not_configured)[^\n]{0,120}coinalyze"
                r"|coinalyze[^\n]{0,120}(missing|degraded|backoff|not configured|not_configured)",
                text,
                re.IGNORECASE,
            )
        )
        if coinalyze_gap and "coinalyze" not in full_ranked_section.casefold():
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
    return out


def _live_provider_readiness_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "live_provider_readiness_missing": 0,
        "live_provider_readiness_secret_leak": 0,
        "live_provider_readiness_live_calls_allowed_in_smoke": 0,
        "live_provider_readiness_configured_missing_env": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    json_path = base / event_live_provider_readiness.READINESS_JSON
    md_path = base / event_live_provider_readiness.READINESS_MD
    if not json_path.exists() and not md_path.exists():
        if _live_provider_readiness_required(base):
            out["live_provider_readiness_missing"] = 1
        return out
    texts: list[str] = []
    for path in (json_path, md_path):
        if not path.exists():
            continue
        try:
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            out["live_provider_readiness_missing"] = 1
    joined = "\n".join(texts)
    if _text_has_secret_like_value(joined):
        out["live_provider_readiness_secret_leak"] = 1
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, Mapping):
            smoke = bool(data.get("smoke_mode"))
            if smoke and bool(data.get("live_calls_allowed")):
                out["live_provider_readiness_live_calls_allowed_in_smoke"] += 1
            for provider in data.get("providers") or ():
                if not isinstance(provider, Mapping):
                    continue
                if smoke and bool(provider.get("live_call_allowed")):
                    out["live_provider_readiness_live_calls_allowed_in_smoke"] += 1
                if bool(provider.get("configured")) and str(provider.get("preflight_status") or "") == "missing_config":
                    out["live_provider_readiness_configured_missing_env"] += 1
    return out


def _text_has_secret_like_value(text: str) -> bool:
    patterns = (
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
        r"(?i)(api[_-]?key|secret|token)\s+[A-Za-z0-9._-]{24,}",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _source_coverage_report_required(namespace_dir: Path) -> bool:
    """Return true for namespaces that claim source/evidence/provider coverage."""

    required_markers = (
        "event_integrated_radar_candidates.jsonl",
        "event_evidence_acquisition.jsonl",
        "event_live_provider_activation_readiness.json",
        "event_live_provider_activation_readiness.md",
        "event_coinalyze_preflight.json",
        "event_coinalyze_preflight.md",
        "event_coinalyze_rehearsal_report.json",
        "event_coinalyze_rehearsal_report.md",
        "event_coinalyze_request_ledger.jsonl",
        "event_bybit_announcements_preflight.json",
        "event_bybit_announcements_preflight.md",
        "event_bybit_announcements_rehearsal_report.json",
        "event_bybit_announcements_rehearsal_report.md",
        "event_bybit_announcements_request_ledger.jsonl",
        "event_unlock_calendar_preflight.json",
        "event_unlock_calendar_preflight.md",
        "event_unlock_calendar_request_ledger.jsonl",
        "event_official_exchange_activation.json",
        "event_official_exchange_activation.md",
        "cryptopanic_request_ledger.jsonl",
    )
    return any((namespace_dir / name).exists() for name in required_markers)


def _live_provider_readiness_required(namespace_dir: Path) -> bool:
    """Pure notification-format smoke namespaces do not claim live-provider readiness."""

    if (namespace_dir / "event_live_provider_activation_readiness.json").exists():
        return True
    if (namespace_dir / "event_live_provider_activation_readiness.md").exists():
        return True
    required_markers = (
        "event_alpha_source_coverage.json",
        "event_integrated_radar_candidates.jsonl",
        "event_coinalyze_preflight.json",
        "event_coinalyze_preflight.md",
        "event_coinalyze_rehearsal_report.json",
        "event_coinalyze_rehearsal_report.md",
        "event_bybit_announcements_preflight.json",
        "event_bybit_announcements_preflight.md",
        "event_bybit_announcements_rehearsal_report.json",
        "event_bybit_announcements_rehearsal_report.md",
        "event_unlock_calendar_preflight.json",
        "event_unlock_calendar_preflight.md",
        "event_official_exchange_activation.json",
        "event_official_exchange_activation.md",
    )
    return any((namespace_dir / name).exists() for name in required_markers)


def _cryptopanic_artifact_conflicts(
    *,
    acquisition_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    research_card_paths: Iterable[Path],
    source_coverage_report_path: str | Path | None,
) -> dict[str, int]:
    out = {
        "cryptopanic_configured_but_not_observed": 0,
        "cryptopanic_used_but_no_source_coverage_entry": 0,
        "cryptopanic_accepted_evidence_missing_from_card": 0,
        "cryptopanic_rejected_only_promoted": 0,
        "cryptopanic_token_printed_or_unredacted": 0,
        "cryptopanic_growth_unsupported_param_used": 0,
        "cryptopanic_duplicate_request_key": 0,
        "cryptopanic_invalid_currency_code": 0,
        "cryptopanic_empty_currency_request": 0,
        "cryptopanic_coin_id_sent_as_currency": 0,
        "cryptopanic_all_requests_failed": 0,
        "cryptopanic_json_parse_errors": 0,
        "cryptopanic_configured_but_unusable": 0,
        "cryptopanic_status_code_missing_on_http_failure": 0,
        "cryptopanic_body_excerpt_unredacted_token": 0,
        "cryptopanic_quota_exceeded": 0,
        "cryptopanic_request_ledger_missing_when_used": 0,
        "cryptopanic_success_with_backoff_status": 0,
        "cryptopanic_restore_token_recommendation_when_configured": 0,
    }
    source_text = ""
    if source_coverage_report_path is not None and Path(source_coverage_report_path).exists():
        try:
            source_text = Path(source_coverage_report_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            source_text = ""
    if "CryptoPanic:" in source_text:
        if "- configured: true" in source_text and "- observed this run: false" in source_text:
            out["cryptopanic_configured_but_not_observed"] = 1
    acquisition = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    cryptopanic_used = any(_row_mentions_cryptopanic(row) for row in acquisition)
    if cryptopanic_used and "CryptoPanic:" not in source_text:
        out["cryptopanic_used_but_no_source_coverage_entry"] = 1
    accepted_core_ids = {
        str(row.get("core_opportunity_id") or "")
        for row in acquisition
        if _accepted_cryptopanic_count(row) > 0
    }
    if accepted_core_ids:
        card_text_by_core = _card_text_by_core(research_card_paths)
        for core_id in accepted_core_ids:
            if not core_id:
                continue
            text = card_text_by_core.get(core_id, "")
            if text and "cryptopanic" not in text.casefold():
                out["cryptopanic_accepted_evidence_missing_from_card"] += 1
    rejected_only_core_ids = {
        str(row.get("core_opportunity_id") or "")
        for row in acquisition
        if _row_mentions_cryptopanic(row)
        and _accepted_cryptopanic_count(row) <= 0
        and (
            str(row.get("status") or row.get("evidence_acquisition_status") or "") == "rejected_results_only"
            or _rejected_cryptopanic_count(row) > 0
        )
    }
    for row in core_rows:
        core_id = str(row.get("core_opportunity_id") or "")
        if core_id not in rejected_only_core_ids:
            continue
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "")
        alertable = bool(row.get("alertable_after_quality_gate") or row.get("route_alertable"))
        if alertable or route in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH"} or level in {"validated_digest", "watchlist", "high_priority"}:
            out["cryptopanic_rejected_only_promoted"] += 1
    source_path = Path(source_coverage_report_path) if source_coverage_report_path is not None else None
    ledger_path = source_path.with_name("cryptopanic_request_ledger.jsonl") if source_path is not None else None
    ledger_rows = _load_jsonl_rows(ledger_path) if ledger_path is not None else ()
    if cryptopanic_used and ledger_path is not None and not ledger_path.exists():
        out["cryptopanic_request_ledger_missing_when_used"] = 1
    for row in ledger_rows:
        redacted_url = str(row.get("request_url_redacted") or "")
        plan = str(row.get("plan") or "growth_weekly").strip().lower()
        if plan != "enterprise" and _growth_unsupported_params(redacted_url):
            out["cryptopanic_growth_unsupported_param_used"] += 1
        currencies = str(row.get("currencies") or "").strip()
        if not currencies:
            out["cryptopanic_empty_currency_request"] += 1
        for currency in [part.strip() for part in currencies.split(",") if part.strip()]:
            if currency != currency.upper() or not re.match(r"^[A-Z][A-Z0-9]{1,9}$", currency):
                out["cryptopanic_invalid_currency_code"] += 1
            if "-" in currency or "_" in currency or currency.casefold() in {"fetch-ai", "synapse-2", "chiliz"}:
                out["cryptopanic_coin_id_sent_as_currency"] += 1
        if "auth_token=" in redacted_url and "auth_token=%3Credacted%3E" not in redacted_url and "auth_token=<redacted>" not in redacted_url:
            out["cryptopanic_token_printed_or_unredacted"] = 1
        error_class = str(row.get("error_class") or "").strip()
        status_code = row.get("status_code")
        try:
            status_int = int(status_code) if status_code not in (None, "") else None
        except (TypeError, ValueError):
            status_int = None
        if error_class in {"json_parse_error", "empty_response"}:
            out["cryptopanic_json_parse_errors"] += 1
        if error_class in {"auth_failed", "rate_limited_or_forbidden", "server_error"} and status_int is None:
            out["cryptopanic_status_code_missing_on_http_failure"] += 1
        if _contains_unredacted_cryptopanic_secret(str(row.get("body_excerpt_redacted") or "")):
            out["cryptopanic_body_excerpt_unredacted_token"] += 1
    request_keys = [
        str(row.get("normalized_request_key") or row.get("request_url_redacted") or "").strip()
        for row in ledger_rows
        if str(row.get("normalized_request_key") or row.get("request_url_redacted") or "").strip()
    ]
    out["cryptopanic_duplicate_request_key"] = max(0, len(request_keys) - len(set(request_keys)))
    attempted_rows = [row for row in ledger_rows if row.get("quota_counted") is not False]
    successful_rows = [
        row
        for row in attempted_rows
        if not str(row.get("error_class") or "").strip()
        and ((_int_or_none(row.get("status_code"), 0) or 0) in range(200, 400))
    ]
    if attempted_rows:
        successes = sum(1 for row in attempted_rows if int(row.get("result_count") or 0) > 0 and not str(row.get("error_class") or ""))
        failures = sum(1 for row in attempted_rows if str(row.get("error_class") or "") or _int_or_none(row.get("status_code"), 0) >= 400)
        if failures and successes == 0 and failures == len(attempted_rows):
            out["cryptopanic_all_requests_failed"] = 1
    unusable_markers = (
        "coverage status: observed_parse_error",
        "coverage status: observed_rate_limited",
        "coverage status: observed_backoff_without_success",
        "coverage status: quota_exhausted",
    )
    if any(marker in source_text for marker in unusable_markers):
        out["cryptopanic_configured_but_unusable"] = 1
    if successful_rows and (
        "health status: backoff" in source_text
        or "coverage status: observed_backoff_without_success" in source_text
        or "coverage status: configured_but_backoff" in source_text
    ):
        out["cryptopanic_success_with_backoff_status"] = 1
    if successful_rows and (
        "configure CryptoPanic token" in source_text
        or "restore CryptoPanic token" in source_text
        or "verify the CryptoPanic token" in source_text
    ):
        out["cryptopanic_restore_token_recommendation_when_configured"] = 1
    if sum(1 for _ in ledger_rows) > 600:
        out["cryptopanic_quota_exceeded"] = 1
    combined_text = source_text + "\n" + "\n".join(_read_card_text(path) for path in research_card_paths)
    if _contains_unredacted_cryptopanic_secret(combined_text):
        out["cryptopanic_token_printed_or_unredacted"] = 1
    return out


def _evidence_count_mismatches(rows: Iterable[Mapping[str, Any]]) -> int:
    mismatches = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for count_key, list_key in (
            ("accepted_evidence_count", "accepted_evidence"),
            ("rejected_evidence_count", "rejected_evidence"),
        ):
            if count_key not in row:
                continue
            declared = _int_or_none(row.get(count_key))
            if declared is None:
                mismatches += 1
                continue
            if list_key not in row:
                # Legacy acquisition rows persisted only sample arrays; those are
                # intentionally incomplete and should remain readable.
                continue
            observed = len(_mapping_items(row.get(list_key)))
            if declared != observed:
                mismatches += 1
        legacy_accepted = _int_or_none(row.get("evidence_acquisition_accepted_count"))
        accepted = _int_or_none(row.get("accepted_evidence_count"))
        if legacy_accepted is not None and accepted is not None and legacy_accepted != accepted:
            mismatches += 1
        legacy_rejected = _int_or_none(row.get("evidence_acquisition_rejected_count"))
        rejected = _int_or_none(row.get("rejected_evidence_count"))
        if legacy_rejected is not None and rejected is not None and legacy_rejected != rejected:
            mismatches += 1
    return mismatches


def _evidence_acquisition_final_field_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {"evidence_acquisition_stale_validated_digest": 0}
    unresolved_statuses = {
        "rejected_results_only",
        "no_results",
        "skipped_budget",
        "not_executed",
        "not_configured",
        "provider_unavailable",
        "provider_backoff",
        "skipped_config",
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        accepted = _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count"))
        status = str(row.get("status") or row.get("evidence_acquisition_status") or row.get("acquisition_evidence_status") or "").strip()
        final_level = str(row.get("final_opportunity_level") or row.get("opportunity_level_after") or "").strip()
        if accepted <= 0 and status in unresolved_statuses and final_level in {"validated_digest", "watchlist", "high_priority"}:
            out["evidence_acquisition_stale_validated_digest"] += 1
    return out


def _daily_brief_card_names(path: str | Path | None) -> set[str]:
    if path is None:
        return set()
    brief_path = Path(path)
    if not brief_path.exists():
        return set()
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {
        match.group(1)
        for match in re.finditer(r"\[(card_[^\]\s]+?\.md)\]", text)
    }


def _visible_sector_core_without_config(rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold()
        if symbol != "SECTOR" and not coin_id.startswith("sector"):
            continue
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "").strip()
        visible = event_alpha_router.route_value_is_alertable(route) or level in {
            "validated_digest",
            "watchlist",
            "high_priority",
        }
        allowed = str(row.get("sector_review_enabled") or row.get("allow_sector_digest") or "").strip().casefold() in {
            "1",
            "true",
            "yes",
        }
        if visible and not allowed:
            count += 1
    return count


def _duplicate_proxy_core_rows(rows: Iterable[Mapping[str, Any]]) -> int:
    groups: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if event_core_opportunities.row_is_diagnostic(row):
            continue
        impact = str(row.get("impact_path_type") or row.get("primary_impact_path") or row.get("impact_path_reason") or "").casefold()
        source_pack = str(row.get("source_pack") or "").casefold()
        if not any(token in f"{impact} {source_pack}" for token in ("proxy", "preipo", "pre_ipo", "rwa", "venue")):
            continue
        symbol = str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold() or symbol
        if symbol == "SECTOR" or coin_id.startswith("sector"):
            continue
        incident = str(
            row.get("incident_id")
            or row.get("canonical_incident_name")
            or row.get("external_asset")
            or row.get("event_cluster_id")
            or ""
        ).strip().casefold()
        role = str(row.get("candidate_role") or row.get("relationship_type") or "").strip().casefold()
        family = "proxy_value_capture"
        key = (incident, coin_id, role or "proxy", family)
        groups[key] = groups.get(key, 0) + 1
    return sum(max(0, count - 1) for count in groups.values())


def _row_mentions_cryptopanic(row: Mapping[str, Any]) -> bool:
    values = (
        row.get("provider"),
        row.get("provider_hint"),
        row.get("provider_used"),
        row.get("source_class"),
        row.get("source_url"),
        row.get("providers_used"),
        row.get("evidence_acquisition_providers_used"),
        row.get("provider_failures"),
        row.get("reason_codes"),
        row.get("accepted_evidence"),
        row.get("rejected_evidence"),
        row.get("rejected_evidence_samples"),
        row.get("queries"),
    )
    return any("cryptopanic" in str(value).casefold() for value in values)


def _load_jsonl_rows(path: Path | None) -> tuple[Mapping[str, Any], ...]:
    if path is None or not path.exists():
        return ()
    rows: list[Mapping[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            import json

            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(value)
    except Exception:  # noqa: BLE001 - doctor must fail soft
        return tuple(rows)
    return tuple(rows)


def _growth_unsupported_params(redacted_url: str) -> tuple[str, ...]:
    unsupported = {"last_pull", "panic_period", "panic_sort", "search", "size", "with_content"}
    try:
        query = parse_qs(urlsplit(redacted_url).query)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(sorted(key for key in query if key in unsupported))


def _contains_unredacted_cryptopanic_secret(text: str) -> bool:
    if "RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN=" in text:
        return True
    for match in re.finditer(r"auth_token=([^&\s]+)", text):
        value = match.group(1)
        if value not in {"<redacted>", "%3Credacted%3E", "[redacted]"}:
            return True
    if re.search(r"\b[A-Fa-f0-9]{32,}\b", text):
        return True
    return False


def _int_or_none(value: object, default: int | None = None) -> int | None:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _accepted_cryptopanic_count(row: Mapping[str, Any]) -> int:
    accepted = row.get("accepted_evidence") or row.get("evidence_acquisition_accepted_evidence")
    return sum(1 for item in _mapping_items(accepted) if _row_mentions_cryptopanic(item))


def _rejected_cryptopanic_count(row: Mapping[str, Any]) -> int:
    rejected = row.get("rejected_evidence_samples") or row.get("rejected_evidence") or row.get("evidence_acquisition_rejected_samples")
    return sum(1 for item in _mapping_items(rejected) if _row_mentions_cryptopanic(item))


def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _card_text_by_core(paths: Iterable[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        text = _read_card_text(path)
        patterns = (
            r"core_opportunity_id:\s*([^\s]+)",
            r"^-\s*Core opportunity ID:\s*(.+?)\s*$",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.MULTILINE):
                core_id = str(match.group(1)).strip()
                if core_id and core_id.lower() != "none":
                    out[core_id] = text
    return out


def _daily_brief_consistency_conflicts(
    path: str | Path | None,
    *,
    runs: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    source_coverage_report_path: str | Path | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> dict[str, int]:
    out = {
        "daily_brief_missing_selected_run": 0,
        "daily_brief_selected_run_mismatch": 0,
        "daily_brief_core_count_mismatch_store": 0,
        "daily_brief_research_review_lane_missing": 0,
        "daily_brief_source_coverage_path_missing": 0,
        "daily_brief_coinalyze_source_coverage_mismatch": 0,
    }
    if path is None:
        return out
    brief_path = Path(path)
    if not brief_path.exists():
        return out
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return out
    run_list = [dict(row) for row in runs if isinstance(row, Mapping)]
    core_list = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    latest_id = _latest_run_id(run_list)
    latest_run = next((row for row in run_list if str(row.get("run_id") or "") == str(latest_id or "")), None)
    if run_list and "No run ledger rows found" in text:
        out["daily_brief_missing_selected_run"] = 1
    selected_profile = _daily_brief_line_value(text, "Selected run profile")
    selected_namespace = _daily_brief_line_value(text, "Selected run namespace")
    expected_profile = str((latest_run or {}).get("profile") or profile or "default").strip()
    expected_namespace = str((latest_run or {}).get("artifact_namespace") or artifact_namespace or "legacy").strip()
    if latest_run:
        if selected_profile in {"", "none"} or selected_namespace in {"", "none"}:
            out["daily_brief_selected_run_mismatch"] = 1
        elif selected_profile != expected_profile or selected_namespace != expected_namespace:
            out["daily_brief_selected_run_mismatch"] = 1
    rendered_expected_core_count = len(event_core_opportunity_store.core_opportunities_from_rows(core_list)) if core_list else 0
    rendered_core_count = _daily_brief_core_count(text)
    if core_list and rendered_core_count is not None and rendered_core_count != rendered_expected_core_count:
        out["daily_brief_core_count_mismatch_store"] = 1
    elif core_list and "Core opportunities: 0" in text:
        out["daily_brief_core_count_mismatch_store"] = 1
    research_review_expected = False
    if latest_run and (
        _as_int(latest_run.get("research_review_digest_candidates"))
        or _as_int(latest_run.get("research_review_digest_would_send"))
    ):
        research_review_expected = True
    if latest_id:
        research_review_expected = research_review_expected or any(
            str(row.get("run_id") or "") == str(latest_id)
            and str(row.get("lane") or "") == "research_review_digest"
            for row in delivery_rows
            if isinstance(row, Mapping)
        )
    review_section = _daily_brief_section(text, "### Research Review Digest")
    if research_review_expected and (
        not review_section
        or "Lane count sent/due: 0/0" in review_section
    ):
        out["daily_brief_research_review_lane_missing"] = 1
    if source_coverage_report_path is not None and Path(source_coverage_report_path).exists():
        source_text = str(source_coverage_report_path)
        if source_text not in text and Path(source_coverage_report_path).name not in text:
            out["daily_brief_source_coverage_path_missing"] = 1
        try:
            source_body = Path(source_coverage_report_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            source_body = ""
        coverage_links_coinalyze = (
            event_coinalyze_preflight.PREFLIGHT_JSON in source_body
            or event_coinalyze_preflight.PREFLIGHT_MD in source_body
            or event_coinalyze_preflight.REHEARSAL_MD in source_body
        )
        brief_says_missing = "Coinalyze preflight: not generated" in text or "Coinalyze preflight: not written yet" in text
        if coverage_links_coinalyze and brief_says_missing:
            out["daily_brief_coinalyze_source_coverage_mismatch"] = 1
    return out


def _daily_brief_line_value(text: str, label: str) -> str:
    prefix = f"{label}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[-1].strip()
    return ""


def _daily_brief_core_count(text: str) -> int | None:
    match = re.search(r"^- Core opportunities:\s+(\d+)\b", text, flags=re.MULTILINE)
    if not match:
        return None
    return _as_int(match.group(1))


def _daily_brief_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    next_heading = text.find("\n### ", start + len(heading))
    if next_heading < 0:
        return text[start:]
    return text[start:next_heading]


def _split_provider_line(line: str) -> tuple[str, ...]:
    if ":" not in line:
        return ()
    value = line.rsplit(":", 1)[-1].strip()
    if not value or value == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _tuple_value(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value if str(key).strip())
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),)


def _notification_delivery_conflicts(
    *,
    delivery_rows: Iterable[Mapping[str, Any]],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    latest_run_id: str | None = None,
    strict_scope: str = "all_rows",
) -> dict[str, int]:
    out = {
        "latest_run_delivery_rows": 0,
        "legacy_delivery_rows": 0,
        "stale_delivery_rows": 0,
        "delivery_identity_mismatch_core_store": 0,
        "delivery_core_id_missing": 0,
        "legacy_pre_core_delivery_identity": 0,
        "stale_delivery_identity_missing_core": 0,
        "delivery_feedback_target_missing": 0,
        "delivery_card_path_missing": 0,
        "delivery_alert_id_not_canonical": 0,
        "telegram_message_contains_absolute_path": 0,
        "telegram_message_contains_raw_debug_dump": 0,
        "research_review_digest_missing_confirmation_label": 0,
        "research_review_digest_contains_strict_alertable": 0,
        "research_review_digest_contains_hard_gated_candidate": 0,
        "research_review_digest_too_many_items": 0,
        "research_review_digest_missing_feedback_target": 0,
        "research_review_digest_skipped_without_reason": 0,
        "research_review_digest_missing_family_summary": 0,
        "research_review_digest_duplicate_visible_family_summary": 0,
        "research_review_digest_absolute_path": 0,
        "notification_body_card_mismatch_canonical": 0,
        "notification_body_feedback_mismatch_canonical": 0,
        "research_review_body_uses_hypothesis_target_when_core_exists": 0,
        "digest_item_without_live_confirmation": 0,
        "digest_item_rejected_results_only": 0,
        "strategic_broad_asset_digest_without_confirmation": 0,
        "unconfirmed_narrative_daily_digest": 0,
        "single_source_no_market_fan_token_digest": 0,
        "multi_item_delivery_missing_arrays": 0,
        "notification_preview_missing": 0,
        "notification_preview_relpath_missing": 0,
        "notification_preview_path_unresolvable": 0,
        "delivery_status_missing": 0,
        "delivery_status_detail_missing": 0,
        "delivery_mode_missing": 0,
        "delivery_state_inconsistent": 0,
        "delivery_would_send_sent_failed_inconsistent": 0,
    }
    scope = _normalize_delivery_strict_scope(strict_scope, latest_run_id=latest_run_id, strict=True)
    latest = _delivery.latest_rows_by_delivery(delivery_rows)
    for row in latest:
        row_run_id = str(row.get("run_id") or "").strip()
        is_latest_run = bool(latest_run_id and row_run_id == latest_run_id)
        if latest_run_id:
            if is_latest_run:
                out["latest_run_delivery_rows"] += 1
            else:
                out["stale_delivery_rows"] += 1
                if _delivery_is_legacy_pre_core_identity(row):
                    out["legacy_delivery_rows"] += 1
                if _delivery_lacks_core_identity(row):
                    out["stale_delivery_identity_missing_core"] += 1
                    if _delivery_is_legacy_pre_core_identity(row):
                        out["legacy_pre_core_delivery_identity"] += 1
        if scope == "latest_run" and latest_run_id and not is_latest_run:
            continue
        status_conflicts = _delivery_status_field_conflicts(row)
        for key, value in status_conflicts.items():
            out[key] += value
        preview_relpath = str(row.get("notification_preview_relpath") or "").strip()
        if not preview_relpath and is_latest_run:
            out["notification_preview_relpath_missing"] += 1
        path, _source = _delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
        )
        telegram_body = ""
        if path is None:
            out["notification_preview_missing"] += 1
            out["notification_preview_path_unresolvable"] += 1
        else:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                out["notification_preview_missing"] += 1
                out["notification_preview_path_unresolvable"] += 1
            else:
                telegram_body = "\n".join(_telegram_preview_bodies(text)) or text
                if re.search(r"/Users/|/tmp/|/private/tmp/", telegram_body):
                    out["telegram_message_contains_absolute_path"] += 1
                if re.search(r"\b(alert_id|card_id|research_card|route|lane)=", telegram_body):
                    out["telegram_message_contains_raw_debug_dump"] += 1
        lane = str(row.get("lane") or "")
        scalar_core_ids = _tuple_value(row.get("core_opportunity_id"))
        core_ids = _tuple_value(row.get("core_opportunity_ids")) or scalar_core_ids
        alert_ids = _tuple_value(row.get("alert_id"))
        cores = tuple(core_rows_by_id[core_id] for core_id in core_ids if core_id in core_rows_by_id)
        missing_core_ids = tuple(core_id for core_id in core_ids if core_id not in core_rows_by_id)
        core = cores[0] if len(cores) == 1 else None
        if lane == "research_review_digest":
            if "Not alertable" not in telegram_body or "Missing confirmation" not in telegram_body:
                out["research_review_digest_missing_confirmation_label"] += 1
            if re.search(r"/Users/|/tmp/|/private/tmp/", telegram_body):
                out["research_review_digest_absolute_path"] += 1
            if len(re.findall(r"(?m)^\d+\.\s*<b>", telegram_body)) > 10:
                out["research_review_digest_too_many_items"] += 1
            if not str(row.get("feedback_target") or "").strip():
                out["research_review_digest_missing_feedback_target"] += 1
            summary = row.get("channel_summary") if isinstance(row.get("channel_summary"), Mapping) else {}
            skipped_count = _as_int(row.get("skipped_candidate_count") or summary.get("skipped_candidate_count") if isinstance(summary, Mapping) else 0)
            if skipped_count > 0:
                reason_counts = (
                    row.get("skipped_reason_counts")
                    if isinstance(row.get("skipped_reason_counts"), Mapping)
                    else summary.get("skipped_reason_counts") or summary.get("skip_reason_counts")
                    if isinstance(summary, Mapping)
                    else {}
                )
                skipped_items = (
                    row.get("skipped_candidates_sample")
                    if isinstance(row.get("skipped_candidates_sample"), list)
                    else summary.get("skipped_candidates_sample") or summary.get("skipped_candidates")
                    if isinstance(summary, Mapping)
                    else []
                )
                display_family_summary = (
                    row.get("skipped_display_family_summary")
                    if isinstance(row.get("skipped_display_family_summary"), list)
                    else summary.get("skipped_display_family_summary")
                    if isinstance(summary, Mapping) and isinstance(summary.get("skipped_display_family_summary"), list)
                    else None
                )
                family_summary = (
                    display_family_summary
                    if isinstance(display_family_summary, list)
                    else row.get("skipped_family_summary")
                    if isinstance(row.get("skipped_family_summary"), list)
                    else summary.get("skipped_family_summary")
                    if isinstance(summary, Mapping) and isinstance(summary.get("skipped_family_summary"), list)
                    else []
                )
                has_reason_counts = isinstance(reason_counts, Mapping) and any(str(key).strip() for key in reason_counts)
                if not has_reason_counts:
                    out["research_review_digest_skipped_without_reason"] += 1
                has_family_summary = isinstance(family_summary, list) and any(
                    isinstance(item, Mapping) and str(item.get("display_family_id") or item.get("candidate_family_id") or item.get("label") or "").strip()
                    for item in family_summary
                )
                if skipped_count > 10 and not has_family_summary:
                    out["research_review_digest_missing_family_summary"] += 1
                if re.search(r"(?im)\+\d+\s+more skipped candidates", telegram_body) and not has_family_summary:
                    out["research_review_digest_missing_family_summary"] += 1
                if has_family_summary:
                    family_keys = {
                        str(item.get("display_family_id") or item.get("candidate_family_id") or item.get("label") or "").strip()
                        for item in family_summary
                        if isinstance(item, Mapping)
                    }
                    family_keys.update(
                        str(item.get("label") or f"{item.get('symbol')}/{item.get('coin_id')}" or "").strip()
                        for item in family_summary
                        if isinstance(item, Mapping)
                    )
                    if isinstance(display_family_summary, list):
                        visible_labels: list[str] = []
                        for family_item in display_family_summary:
                            if not isinstance(family_item, Mapping) or bool(family_item.get("display_hidden")):
                                continue
                            label = str(
                                family_item.get("display_label")
                                or family_item.get("label")
                                or f"{family_item.get('symbol')}/{family_item.get('coin_id')}"
                                or ""
                            ).strip().casefold()
                            if label:
                                visible_labels.append(label)
                        if len(visible_labels) != len(set(visible_labels)):
                            out["research_review_digest_duplicate_visible_family_summary"] += 1
                    material_missing = [
                        item for item in skipped_items
                        if isinstance(item, Mapping)
                        and (
                            _as_int(item.get("skipped_count")) >= 10
                            or _as_float(item.get("score") or item.get("rank_score")) >= 60
                        )
                        and str(
                            item.get("display_family_id")
                            or f"{item.get('symbol')}/{item.get('coin_id')}"
                            or item.get("candidate_family_id")
                            or ""
                        ).strip()
                        and str(
                            item.get("display_family_id")
                            or f"{item.get('symbol')}/{item.get('coin_id')}"
                            or item.get("candidate_family_id")
                            or ""
                        ).strip() not in family_keys
                    ]
                    if material_missing:
                        out["research_review_digest_missing_family_summary"] += 1
            if core_ids:
                body_lower = telegram_body.casefold()
                card_paths = _tuple_value(row.get("canonical_card_paths")) or _tuple_value(row.get("canonical_card_path"))
                feedback_targets = _tuple_value(row.get("feedback_targets")) or _tuple_value(row.get("feedback_target"))
                for card_path in card_paths:
                    basename = Path(str(card_path)).name
                    if basename and basename.casefold() not in body_lower:
                        out["notification_body_card_mismatch_canonical"] += 1
                for target in feedback_targets:
                    if target and str(target).casefold() not in body_lower:
                        out["notification_body_feedback_mismatch_canonical"] += 1
                if re.search(r"(?im)^\s*feedback target:\s*hyp:", telegram_body):
                    out["research_review_body_uses_hypothesis_target_when_core_exists"] += 1
            for digest_core in cores:
                if _research_review_core_is_alertable(digest_core):
                    out["research_review_digest_contains_strict_alertable"] += 1
                if _research_review_core_is_hard_gated(digest_core):
                    out["research_review_digest_contains_hard_gated_candidate"] += 1
        if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
            continue
        if lane == "daily_digest" and len(scalar_core_ids) > 1 and not _tuple_value(row.get("core_opportunity_ids")):
            out["multi_item_delivery_missing_arrays"] += 1
        requires_core = _delivery_requires_core_identity(row)
        if requires_core:
            if not core_ids:
                out["delivery_core_id_missing"] += 1
            if not str(row.get("feedback_target") or "").strip():
                out["delivery_feedback_target_missing"] += 1
            if not str(row.get("canonical_card_path") or "").strip():
                out["delivery_card_path_missing"] += 1
        if missing_core_ids:
            out["delivery_identity_mismatch_core_store"] += 1
        if (
            requires_core
            and alert_ids
            and lane != "triggered_fade"
            and (not core_ids or set(alert_ids) != set(core_ids))
        ):
            out["delivery_alert_id_not_canonical"] += 1
        if cores and lane in {"daily_digest", "instant_escalation"}:
            for delivery_core in cores:
                if _delivery_core_lacks_live_confirmation(delivery_core):
                    out["digest_item_without_live_confirmation"] += 1
                if lane == "daily_digest" and _delivery_core_is_unconfirmed_narrative(delivery_core):
                    out["unconfirmed_narrative_daily_digest"] += 1
                    if _delivery_core_is_single_source_no_market_fan_token(delivery_core):
                        out["single_source_no_market_fan_token_digest"] += 1
                if str(delivery_core.get("evidence_acquisition_status") or "") == "rejected_results_only":
                    out["digest_item_rejected_results_only"] += 1
                if _delivery_core_is_strategic_broad_asset_context(delivery_core):
                    out["strategic_broad_asset_digest_without_confirmation"] += 1
    return out


def _delivery_status_field_conflicts(row: Mapping[str, Any]) -> dict[str, int]:
    out = {
        "delivery_status_missing": 0,
        "delivery_status_detail_missing": 0,
        "delivery_mode_missing": 0,
        "delivery_state_inconsistent": 0,
        "delivery_would_send_sent_failed_inconsistent": 0,
    }
    delivery_mode = str(row.get("delivery_mode") or "").strip()
    delivery_state = str(row.get("delivery_state") or "").strip()
    status = str(row.get("status") or "").strip()
    status_detail = str(row.get("status_detail") or "").strip()
    if not delivery_state or not status:
        out["delivery_status_missing"] += 1
    if not status_detail:
        out["delivery_status_detail_missing"] += 1
    if not delivery_mode:
        out["delivery_mode_missing"] += 1
    if not delivery_state or not status_detail or not delivery_mode:
        return out

    state = str(row.get("state") or "")
    sent = _boolish(row.get("sent"))
    failed = _boolish(row.get("failed"))
    would_send = _boolish(row.get("would_send"))
    guard_enabled = _boolish(row.get("send_guard_enabled"))
    if delivery_state == _delivery.DELIVERY_STATE_SENT and not sent:
        out["delivery_state_inconsistent"] += 1
    if delivery_state == _delivery.DELIVERY_STATE_FAILED and not failed:
        out["delivery_state_inconsistent"] += 1
    if delivery_state == _delivery.DELIVERY_STATE_BLOCKED and (sent or failed):
        out["delivery_state_inconsistent"] += 1
    if sent and failed:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if sent and status_detail != _delivery.STATUS_DETAIL_SENT:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if state == _delivery.STATE_BLOCKED and sent:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if status_detail == _delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED and guard_enabled:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if sent and not guard_enabled:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if would_send and not (sent or failed) and delivery_state not in {
        _delivery.DELIVERY_STATE_BLOCKED,
        _delivery.DELIVERY_STATE_PREVIEW,
        _delivery.DELIVERY_STATE_SUPPRESSED,
    }:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    return out


def _notification_preview_consistency_conflicts(
    *,
    delivery_rows: Iterable[Mapping[str, Any]],
    latest_run: Mapping[str, Any] | None,
    core_rows: Iterable[Mapping[str, Any]],
    latest_run_id: str | None,
) -> dict[str, int]:
    out = {
        "notification_preview_run_summary_mismatch": 0,
        "notification_preview_llm_summary_mismatch": 0,
        "notification_preview_lane_counts_mismatch": 0,
        "notification_preview_core_count_mismatch": 0,
        "notification_preview_alertable_count_mismatch": 0,
        "notification_preview_missing_send_guard_status": 0,
        "notification_preview_send_guard_status_missing": 0,
        "notification_preview_no_send_status_unclear": 0,
        "notification_preview_legacy_alerts_wording": 0,
    }
    if not latest_run:
        return out
    path = _latest_preview_path(delivery_rows, latest_run_id=latest_run_id)
    if path is None:
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    summary = _parse_notification_preview_summary(text)
    out["notification_preview_legacy_alerts_wording"] += _active_preview_legacy_alerts_wording_count(
        delivery_rows,
        latest_run=latest_run,
        latest_run_id=latest_run_id,
    )
    if not summary:
        return out
    if "completed" in summary:
        expected = bool(latest_run.get("cycle_completed", True))
        if bool(summary["completed"]) != expected:
            out["notification_preview_run_summary_mismatch"] += 1
    if "raw_events" in summary:
        if _as_int(summary["raw_events"]) != _as_int(latest_run.get("raw_events")):
            out["notification_preview_run_summary_mismatch"] += 1
    if "extraction_rows" in summary:
        if _as_int(summary["extraction_rows"]) != _as_int(latest_run.get("extraction_rows")):
            out["notification_preview_run_summary_mismatch"] += 1
    if "core_opportunities" in summary:
        expected_core = _as_int(latest_run.get("core_opportunity_rows_written"))
        if expected_core <= 0:
            expected_core = sum(
                1
                for row in core_rows
                if str(row.get("run_id") or "") == str(latest_run_id or "")
            )
        if _as_int(summary["core_opportunities"]) != expected_core:
            out["notification_preview_core_count_mismatch"] += 1
    if "alertable" in summary:
        if _as_int(summary["alertable"]) != _as_int(latest_run.get("alertable")):
            out["notification_preview_alertable_count_mismatch"] += 1
    if "llm_calls" in summary:
        if _as_int(summary["llm_calls"]) != _as_int(latest_run.get("llm_calls_attempted")):
            out["notification_preview_llm_summary_mismatch"] += 1
    if "llm_skips" in summary:
        if _as_int(summary["llm_skips"]) != _as_int(latest_run.get("llm_skipped_due_budget")):
            out["notification_preview_llm_summary_mismatch"] += 1
    if "lane_due" in summary:
        expected_due = sum(_as_int(value) for value in dict(latest_run.get("send_lane_items_attempted") or {}).values())
        if _as_int(summary["lane_due"]) != expected_due:
            out["notification_preview_lane_counts_mismatch"] += 1
    if "lane_sent" in summary:
        expected_sent = sum(_as_int(value) for value in dict(latest_run.get("send_lane_items_delivered") or {}).values())
        if _as_int(summary["lane_sent"]) != expected_sent:
            out["notification_preview_lane_counts_mismatch"] += 1
    has_guard_line = bool(re.search(r"(?im)^Send guard:\s*.+$", text))
    if not has_guard_line:
        out["notification_preview_missing_send_guard_status"] += 1
        out["notification_preview_send_guard_status_missing"] += 1
    if _preview_is_no_send_or_blocked(delivery_rows, latest_run_id=latest_run_id) and not re.search(
        r"(?i)(no-send rehearsal|would_send_but_guard_disabled|send guard is disabled|blocked_by_send_guard|notifications paused)",
        text,
    ):
        out["notification_preview_no_send_status_unclear"] += 1
    return out


def _active_preview_legacy_alerts_wording_count(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run: Mapping[str, Any] | None,
    latest_run_id: str | None,
) -> int:
    paths: set[Path] = set()
    for row in _delivery.latest_rows_by_delivery(delivery_rows):
        if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
            continue
        path, _source = _delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
        )
        if path is not None:
            paths.add(path)
    count = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _notification_preview_legacy_alerts_wording(text, latest_run=latest_run):
            count += 1
    return count


def _notification_preview_legacy_alerts_wording(text: str, *, latest_run: Mapping[str, Any] | None) -> bool:
    strict_alerts = _as_int((latest_run or {}).get("alerts"))
    bodies = "\n".join(_telegram_preview_bodies(text)) or text
    if strict_alerts > 0:
        return False
    return bool(
        re.search(
            r"(?im)^Alertable decisions:\s*\d+\s*(?:·|-|\|)\s*Alerts:\s*[1-9]\d*\b",
            bodies,
        )
    )


def _latest_preview_path(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run_id: str | None,
) -> Path | None:
    latest = _delivery.latest_rows_by_delivery(delivery_rows)
    candidates: list[tuple[str, str]] = []
    for row in latest:
        if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
            continue
        path, _source = _delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
        )
        if path is None:
            continue
        stamp = str(row.get("attempted_at") or row.get("delivered_at") or "")
        candidates.append((stamp, str(path)))
    if not candidates:
        return None
    candidates.sort()
    return Path(candidates[-1][1])


def _parse_notification_preview_summary(text: str) -> dict[str, Any]:
    bodies = "\n".join(_telegram_preview_bodies(text)) or text
    out: dict[str, Any] = {}
    completed = re.search(r"(?im)^Completed:\s*(yes|no)\b", bodies)
    if completed:
        out["completed"] = completed.group(1).casefold() == "yes"
    raw_core = re.search(
        r"(?im)^Raw events:\s*(\d+)\s*[·-]\s*Core opportunities:\s*(\d+)\b",
        bodies,
    )
    if raw_core:
        out["raw_events"] = raw_core.group(1)
        out["core_opportunities"] = raw_core.group(2)
    alertable = re.search(r"(?im)^Alertable decisions:\s*(\d+)\b", bodies)
    if alertable:
        out["alertable"] = alertable.group(1)
    extraction = re.search(r"(?im)^Extraction rows:\s*(\d+)\b", bodies)
    if extraction:
        out["extraction_rows"] = extraction.group(1)
    llm = re.search(r"(?im)^LLM calls/skips:\s*(\d+)\s*/\s*(\d+)\b", bodies)
    if llm:
        out["llm_calls"] = llm.group(1)
        out["llm_skips"] = llm.group(2)
    lanes = re.search(r"(?im)^Delivery lanes:\s*due=(\d+)\s*[·-]\s*sent=(\d+)\b", bodies)
    if lanes:
        out["lane_due"] = lanes.group(1)
        out["lane_sent"] = lanes.group(2)
    return out


def _preview_is_no_send_or_blocked(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run_id: str | None,
) -> bool:
    for row in _delivery.latest_rows_by_delivery(delivery_rows):
        if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
            continue
        if str(row.get("state") or "") == _delivery.STATE_BLOCKED:
            return True
    return False


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_delivery_strict_scope(
    value: str | None,
    *,
    latest_run_id: str | None,
    strict: bool,
) -> str:
    cleaned = str(value or "").strip().casefold()
    if cleaned in {"latest_run", "all_rows", "legacy_included"}:
        return cleaned
    if strict and latest_run_id:
        return "latest_run"
    return "all_rows"


def _latest_run_id(run_rows: Iterable[Mapping[str, Any]]) -> str | None:
    ids = [str(row.get("run_id") or "").strip() for row in run_rows if str(row.get("run_id") or "").strip()]
    if not ids:
        return None
    return sorted(ids)[-1]


def _delivery_lacks_core_identity(row: Mapping[str, Any]) -> bool:
    lane = str(row.get("lane") or "").strip()
    if lane not in {"daily_digest", "instant_escalation"}:
        return False
    return not (_tuple_value(row.get("core_opportunity_ids")) or _tuple_value(row.get("core_opportunity_id")))


def _delivery_is_legacy_pre_core_identity(row: Mapping[str, Any]) -> bool:
    reason = str(row.get("identity_reconciliation_reason") or "").strip().casefold()
    if reason in {"legacy", "legacy_delivery", "external", "source_alert_identity_legacy"}:
        return True
    if str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}:
        return True
    return _delivery_lacks_core_identity(row) and not str(row.get("feedback_target") or "").strip()


def _delivery_requires_core_identity(row: Mapping[str, Any]) -> bool:
    lane = str(row.get("lane") or "").strip()
    if lane not in {"daily_digest", "instant_escalation"}:
        return False
    reason = str(row.get("identity_reconciliation_reason") or "").strip().casefold()
    if reason in {"legacy", "legacy_delivery", "external", "source_alert_identity_legacy"}:
        return False
    if str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}:
        return False
    return True


def _telegram_preview_bodies(text: str) -> tuple[str, ...]:
    bodies = re.findall(r"```html\n(.*?)```", text, flags=re.DOTALL)
    if bodies:
        return tuple(bodies)
    if "Telegram Body" in text:
        return (text.split("Telegram Body", 1)[-1],)
    return ()


def _delivery_core_lacks_live_confirmation(core: Mapping[str, Any]) -> bool:
    if not event_alpha_router.route_value_is_alertable(core.get("final_route_after_quality_gate") or core.get("route")):
        return False
    status = str(core.get("evidence_acquisition_status") or "").strip()
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    source_class = str(core.get("source_class") or "").strip()
    market = str(core.get("market_confirmation_level") or "").casefold()
    freshness = str(core.get("market_context_freshness_status") or "").casefold()
    impact = str(core.get("impact_path_type") or "").casefold()
    strong_source = source_class in {
        "official_project",
        "official_exchange",
        "structured_event_calendar",
        "cryptopanic_tagged",
        "project_blog",
        "exchange_announcement",
    }
    direct_impact = impact in {
        "direct_token_event",
        "listing_liquidity_event",
        "unlock_supply_event",
        "exploit_security_event",
        "venue_value_capture",
        "fan_token_event",
    }
    fresh_market = market not in {"", "none", "missing", "unknown", "insufficient_data"} and freshness not in {"missing", "stale"}
    if accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate")):
        return False
    if strong_source or (fresh_market and direct_impact):
        return False
    return status in {
        "",
        "rejected_results_only",
        "no_results",
        "skipped_budget",
        "provider_unavailable",
        "skipped_config",
        "not_configured",
    } or confirmation in {"", "does_not_confirm", "unresolved", "coverage_gap"}


def _delivery_core_is_unconfirmed_narrative(core: Mapping[str, Any]) -> bool:
    source_pack = str(core.get("source_pack") or "").strip().casefold()
    if source_pack not in {"fan_sports_pack", "proxy_preipo_rwa_pack", "political_meme_pack"}:
        return False
    if not event_alpha_router.route_value_is_alertable(core.get("final_route_after_quality_gate") or core.get("route")):
        return False
    return _delivery_core_lacks_narrative_digest_confirmation(core)


def _delivery_core_is_single_source_no_market_fan_token(core: Mapping[str, Any]) -> bool:
    source_pack = str(core.get("source_pack") or "").strip().casefold()
    if source_pack != "fan_sports_pack":
        return False
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    provider_counts = _mapping_counts(core.get("accepted_provider_counts"))
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    no_market = market in {"", "none", "missing", "unknown", "insufficient_data"} or freshness in {"missing", "stale", "unknown"}
    return accepted <= 1 and provider_counts.get("cryptopanic", 0) >= 1 and no_market


def _delivery_core_lacks_narrative_digest_confirmation(core: Mapping[str, Any]) -> bool:
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    source_class = str(core.get("source_class") or "").strip().casefold()
    official_or_structured = source_class in {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    market_ok = market in {"moderate", "strong", "confirmed", "fresh"} and freshness not in {"missing", "stale", "unknown"}
    provider_counts = _mapping_counts(core.get("accepted_provider_counts"))
    reason_codes = " ".join(str(value) for value in _tuple_value(core.get("accepted_reason_codes")))
    reason_codes += " " + " ".join(str(value) for value in _mapping_counts(core.get("accepted_reason_code_counts")))
    cryptopanic_confirmed = provider_counts.get("cryptopanic", 0) > 0 and "cryptopanic_currency_tag_match" in reason_codes.casefold()
    if official_or_structured or accepted >= 2:
        return False
    if cryptopanic_confirmed and market_ok:
        return False
    return True


def _mapping_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw or 0)
        except (TypeError, ValueError):
            continue
        out[str(key).strip().casefold()] = max(0, count)
    return out


def _delivery_core_is_strategic_broad_asset_context(core: Mapping[str, Any]) -> bool:
    if not _delivery_core_lacks_live_confirmation(core):
        return False
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol not in {"BTC", "ETH", "SOL"} and coin_id not in {"bitcoin", "ethereum", "solana"}:
        return False
    impact = str(core.get("impact_path_type") or core.get("primary_impact_path") or "").strip().casefold()
    reason = str(core.get("impact_path_reason") or core.get("primary_impact_path_reason") or "").strip().casefold()
    if impact not in {"strategic_investment", "strategic_investment_or_valuation", "valuation_event"} and reason not in {
        "strategic_investment",
        "treasury_context",
        "external_equity_proxy_context",
    }:
        return False
    text = " ".join(
        str(core.get(key) or "")
        for key in (
            "canonical_incident_name",
            "incident_canonical_name",
            "latest_event_name",
            "event_name",
            "latest_source_title",
            "source_title",
            "latest_source",
            "source",
            "why_opportunity_visible",
            "final_verdict_reason",
        )
    ).casefold()
    return any(
        term in text
        for term in (
            "strategy",
            "microstrategy",
            "mstr",
            "treasury",
            "holdings",
            "valuation",
            "discount",
            "premium",
            "public company",
            "market structure",
        )
    )


def _research_review_core_is_alertable(core: Mapping[str, Any]) -> bool:
    route = str(core.get("final_route_after_quality_gate") or core.get("route") or "")
    level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
    if event_alpha_router.route_value_is_alertable(route):
        return True
    return level in {"validated_digest", "watchlist", "high_priority"}


def _research_review_core_is_hard_gated(core: Mapping[str, Any]) -> bool:
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol == "SECTOR" or coin_id.startswith("sector"):
        return True
    fields = " ".join(
        str(core.get(key) or "").casefold()
        for key in (
            "candidate_role",
            "relationship_type",
            "impact_path_type",
            "impact_path_reason",
            "playbook_type",
            "effective_playbook_type",
            "quality_gate_block_reason",
            "why_not_promoted",
            "why_local_only",
            "why_not_watchlist",
            "snapshot_class",
        )
    )
    return any(
        token in fields
        for token in (
            "source_noise",
            "ticker_word_collision",
            "ticker_collision",
            "word_collision",
            "generic_cooccurrence_only",
            "source_noise_control",
            "ambiguous_control",
            "diagnostic_support",
        )
    )


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    return text in {"1", "true", "yes", "y", "on"}


def _row_has_alertable_quality_conflict(row: Mapping[str, Any]) -> bool:
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    final_route, _ = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=False)
    route_alertable = bool(row.get("route_alertable"))
    route = str(row.get("route") or "")
    persisted_alertable = route_alertable or event_alpha_router.route_value_is_alertable(route)
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    if persisted_alertable and not final_alertable:
        return True
    if event_alpha_router.route_value_is_alertable(route) and route != final_route:
        return True
    if not final_alertable and not persisted_alertable:
        return False
    if final_route == "TRIGGERED_FADE_RESEARCH":
        return False
    level = str(data.get("opportunity_level") or "")
    if level in {"local_only", "exploratory", ""}:
        return True
    if str(data.get("impact_path_type") or "") == "insufficient_data":
        return True
    if str(data.get("candidate_role") or "") == "unknown_with_reason":
        return True
    if str(data.get("source_class") or "") == "insufficient_data":
        return True
    if str(data.get("evidence_specificity") or "") == "insufficient_data":
        return True
    try:
        score = float(data.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return score <= 0.0


def _watchlist_quality_state_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "watchlist_state_conflicts_with_quality": 0,
        "universal_watchlist_state_conflicts": 0,
        "non_hypothesis_watchlist_quality_conflicts": 0,
        "hypothesis_watchlist_quality_conflicts": 0,
        "quality_capped_watchlist_rows": 0,
        "active_watchlist_rows_quality_capped": 0,
        "fresh_uncapped": 0,
        "legacy": 0,
    }
    for row in rows:
        state = event_watchlist.final_state_value(row)
        requested = event_watchlist.requested_state_value(row)
        requested_active = requested in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        final_active = state in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        persisted_capped = row.get("state_quality_capped") is True
        capped = persisted_capped and not final_active
        has_conflict = _row_has_watchlist_quality_conflict(row)
        if capped and requested_active:
            out["quality_capped_watchlist_rows"] += 1
            out["active_watchlist_rows_quality_capped"] += 1
            continue
        if has_conflict:
            out["watchlist_state_conflicts_with_quality"] += 1
            out["universal_watchlist_state_conflicts"] += 1
            if _is_hypothesis_watchlist_row(row):
                out["hypothesis_watchlist_quality_conflicts"] += 1
            else:
                out["non_hypothesis_watchlist_quality_conflicts"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy"] += 1
            elif not capped or final_active:
                out["fresh_uncapped"] += 1
    return out


def _filter_watchlist_rows_for_doctor(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    """Filter watchlist rows while honoring path-scoped legacy metadata gaps.

    Older watchlist entries did not carry profile/run-mode fields even when
    they lived inside a profile namespace directory. Doctor callers pass rows
    from a resolved path, so missing metadata should not make those rows
    invisible to quality checks.
    """
    out: list[dict[str, Any]] = []
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        if not include_test_artifacts and event_alpha_artifacts.is_non_operational_row(data):
            continue
        row_profile = _clean_optional(data.get("profile"))
        if profile_key is not None and row_profile not in (None, profile_key):
            continue
        row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
        if namespace_key is not None and row_ns not in (None, namespace_key):
            continue
        if not include_legacy_artifacts and event_alpha_artifacts.is_legacy_row(data):
            if _row_has_watchlist_quality_conflict(data) or event_watchlist.state_is_quality_capped(data):
                if profile and not data.get("profile"):
                    data["profile"] = profile
                if artifact_namespace and not (data.get("artifact_namespace") or data.get("namespace")):
                    data["artifact_namespace"] = artifact_namespace
                if not data.get("run_mode"):
                    data["run_mode"] = "notification_burn_in" if str(profile or "").startswith("notify_") else "burn_in"
                data["_path_scoped_metadata_inferred"] = True
            else:
                continue
        out.append(data)
    return out


def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


def _row_has_watchlist_quality_conflict(row: Mapping[str, Any]) -> bool:
    if event_watchlist.final_state_value(row) == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return False
    requested = event_watchlist.requested_state_value(row)
    if requested not in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
        event_watchlist.EventWatchlistState.ARMED.value,
    }:
        return False
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    level = str(data.get("opportunity_level") or "")
    if level in {"local_only", "exploratory", ""}:
        return True
    if str(data.get("impact_path_type") or "") == "insufficient_data":
        return True
    if str(data.get("candidate_role") or "") == "unknown_with_reason":
        return True
    if str(data.get("source_class") or "") == "insufficient_data":
        return True
    if str(data.get("evidence_specificity") or "") == "insufficient_data":
        return True
    try:
        score = float(data.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return score <= 0.0


def _is_hypothesis_watchlist_row(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    return bool(row.get("hypothesis_id") or components.get("hypothesis_id") or str(row.get("relationship_type") or "") == "impact_hypothesis")


def _incident_linkage_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    incidents: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "hypothesis_rows_missing_incident_id": 0,
        "watchlist_hypothesis_rows_missing_incident_id": 0,
        "alert_hypothesis_rows_missing_incident_id": 0,
        "incident_rows_without_linked_hypotheses": 0,
        "incident_rows_without_linked_watchlist": 0,
        "canonical_unlinked_incidents": 0,
        "active_incident_without_qualified_link": 0,
        "linked_incident_without_qualified_link": 0,
        "weak_unqualified_incident_links": 0,
        "quality_blocked_links_present": 0,
        "quality_blocked_links_promoting_incident": 0,
        "fresh_missing_hypotheses": 0,
        "fresh_missing_watchlist": 0,
        "fresh_missing_alerts": 0,
        "legacy_missing_hypotheses": 0,
        "legacy_missing_watchlist": 0,
        "legacy_missing_alerts": 0,
        "diagnostic_incident_rows": 0,
        "raw_observation_incident_rows": 0,
        "external_context_incident_rows": 0,
        "rejected_incident_rows": 0,
        "incident_relevance_missing": 0,
        "invalid_canonical_incident_rows": 0,
        "garbage_primary_subject_incidents": 0,
    }
    for row in hypotheses:
        if dict(row).get("row_type") not in {"event_impact_hypothesis", ""}:
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_hypotheses"] += 1
            else:
                out["fresh_missing_hypotheses"] += 1
    for row in watchlist:
        if str(row.get("relationship_type") or "") != "impact_hypothesis":
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["watchlist_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_watchlist"] += 1
            else:
                out["fresh_missing_watchlist"] += 1
    for row in alerts:
        is_hypothesis = bool(row.get("hypothesis_id")) or str(row.get("relationship_type") or "") == "impact_hypothesis"
        if not is_hypothesis or _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["alert_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_alerts"] += 1
            else:
                out["fresh_missing_alerts"] += 1
    for row in incidents:
        if dict(row).get("row_type") != "event_incident":
            continue
        subject_quality = str(row.get("incident_subject_quality") or "").strip()
        diagnostic = row.get("diagnostic_only") is True
        relevance = str(row.get("incident_relevance_status") or "").strip()
        if not relevance:
            out["incident_relevance_missing"] += 1
        if _is_garbage_incident_subject(row.get("primary_subject")):
            out["garbage_primary_subject_incidents"] += 1
        if relevance == "raw_observation":
            out["raw_observation_incident_rows"] += 1
        if relevance == "external_context_only":
            out["external_context_incident_rows"] += 1
        if relevance == "rejected_incident":
            out["rejected_incident_rows"] += 1
        relevance_is_hidden = (
            relevance in {"raw_observation", "external_context_only", "rejected_incident"}
            or (relevance == "diagnostic_only" and subject_quality != "invalid")
        )
        if diagnostic or (relevance_is_hidden and relevance in {"diagnostic_only", "rejected_incident"}):
            out["diagnostic_incident_rows"] += 1
            continue
        if relevance_is_hidden:
            continue
        elif subject_quality in {"invalid", "diagnostic_only"}:
            out["invalid_canonical_incident_rows"] += 1
        operational = relevance in {"canonical_incident", "linked_incident", "active_incident"} or (not relevance and not diagnostic)
        qualified_links = int(row.get("qualified_link_count") or 0)
        weak_links = int(row.get("weak_link_count") or 0)
        quality_blocked_links = int(row.get("quality_blocked_link_count") or 0)
        if relevance == "active_incident" and qualified_links <= 0:
            out["active_incident_without_qualified_link"] += 1
        if relevance == "linked_incident" and qualified_links <= 0:
            out["linked_incident_without_qualified_link"] += 1
        if weak_links > 0:
            out["weak_unqualified_incident_links"] += weak_links
        if quality_blocked_links > 0:
            out["quality_blocked_links_present"] += quality_blocked_links
        if relevance in {"linked_incident", "active_incident"} and quality_blocked_links > 0 and qualified_links <= 0:
            out["quality_blocked_links_promoting_incident"] += quality_blocked_links
        if operational and not row.get("linked_hypothesis_ids"):
            out["incident_rows_without_linked_hypotheses"] += 1
        if operational and not row.get("linked_watchlist_keys"):
            out["incident_rows_without_linked_watchlist"] += 1
        if operational and not row.get("linked_hypothesis_ids") and not row.get("linked_watchlist_keys"):
            out["canonical_unlinked_incidents"] += 1
    return out


_GARBAGE_INCIDENT_SUBJECTS = {
    "about",
    "actions",
    "all",
    "announcements",
    "any",
    "any us",
    "best prediction market apps",
    "bitcoin and mstr are",
    "during",
    "here",
    "however",
    "it",
    "llm",
    "need",
    "non",
    "not",
    "note",
    "only",
    "polymarket invite code sbwire",
    "polymarket referral code sbwire",
    "polymarket world cup volume",
    "when",
    "where",
    "will",
    "yes",
}


def _is_garbage_incident_subject(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    text = " ".join(text.replace("-", " ").replace("_", " ").split())
    if not text:
        return False
    if text in _GARBAGE_INCIDENT_SUBJECTS:
        return True
    if "invite code" in text or "referral code" in text:
        return True
    if text.startswith("best ") and text.endswith(" apps"):
        return True
    if text.endswith(" are") and " and " in text:
        return True
    return False


def _row_incident_id(row: Mapping[str, Any]) -> str:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    return str(row.get("incident_id") or components.get("incident_id") or score.get("incident_id") or "").strip()


def _row_has_no_incident(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    status = str(
        row.get("incident_link_status")
        or components.get("incident_link_status")
        or score.get("incident_link_status")
        or ""
    ).strip()
    reason = str(
        row.get("incident_link_reason")
        or components.get("incident_link_reason")
        or score.get("incident_link_reason")
        or ""
    ).strip()
    if status == "no_incident" and reason:
        return True
    warnings = " ".join(str(value) for value in row.get("warnings") or ())
    return "no_incident" in warnings


def _record_snapshot_availability_issue(
    row: Mapping[str, Any],
    availability: str,
    *,
    blockers: list[str],
    warnings: list[str],
    strict: bool,
) -> None:
    run_id = str(row.get("run_id") or "unknown")
    path = event_alpha_artifacts.safe_path_label(row.get("alert_store_path"))
    run_mode = str(row.get("run_mode") or "legacy")
    if availability == event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH:
        blockers.append(
            f"alertable_run_missing_matching_snapshot_rows: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL:
        warnings.append(
            f"fixture_snapshot_external_allowed: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY:
        message = (
            f"legacy_run_missing_snapshot_rows: {run_id}; "
            f"snapshot availability unknown for legacy/default row"
        )
        (blockers if strict else warnings).append(message)
    else:
        target = blockers if run_mode in {"burn_in", "operational"} else warnings
        target.append(f"alertable_run_missing_matching_snapshot_rows: {run_id}")


def format_artifact_doctor_report(result: EventAlphaArtifactDoctorResult) -> str:
    lines = [
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
        f"strict_legacy: {str(result.strict_legacy).lower()}",
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
        (
            "core opportunity coverage: "
            f"visible_core_opportunities={result.visible_core_opportunities} "
            f"core_opportunity_store_rows={result.core_opportunity_store_rows} "
            f"visible_core_opportunities_missing_store_rows={result.visible_core_opportunities_missing_store_rows} "
            f"duplicate_core_opportunity_store_rows={result.duplicate_core_opportunity_store_rows} "
            f"core_opportunity_store_rows_missing_card_path={result.core_opportunity_store_rows_missing_card_path} "
            f"visible_core_opportunities_missing_cards={result.visible_core_opportunities_missing_cards} "
            f"visible_core_opportunities_missing_feedback_targets={result.visible_core_opportunities_missing_feedback_targets} "
            f"alert_snapshots_missing_core_opportunity_id={result.alert_snapshots_missing_core_opportunity_id} "
            f"alert_snapshots_missing_feedback_target={result.alert_snapshots_missing_feedback_target} "
            f"core_cards_missing_store_row={result.core_cards_missing_store_row} "
            f"visible_core_cards_missing_store_row={result.visible_core_cards_missing_store_row} "
            f"orphan_core_opportunity_cards={result.orphan_core_opportunity_cards} "
            f"diagnostic_snapshots_with_fake_core_id={result.diagnostic_snapshots_with_fake_core_id} "
            f"alert_snapshots_core_id_missing_from_store={result.alert_snapshots_core_id_missing_from_store} "
            f"evidence_acquisition_core_id_missing_from_store={result.evidence_acquisition_core_id_missing_from_store} "
            f"card_primary_fields_mismatch_core_store={result.card_primary_fields_mismatch_core_store} "
            f"card_evidence_acquisition_count_mismatch={result.card_evidence_acquisition_count_mismatch} "
            f"evidence_acquisition_stale_validated_digest={result.evidence_acquisition_stale_validated_digest} "
            f"card_source_pack_mismatch_core_acquisition={result.card_source_pack_mismatch_core_acquisition} "
            f"card_primary_section_contains_support_row_blockers={result.card_primary_section_contains_support_row_blockers} "
            f"card_upgrade_text_inconsistent_with_final_level={result.card_upgrade_text_inconsistent_with_final_level} "
            f"audit_primary_impact_path_mismatch_core={result.audit_primary_impact_path_mismatch_core} "
            f"audit_source_pack_mismatch_core={result.audit_source_pack_mismatch_core} "
            f"card_market_confirmation_missing_but_core_has_market_confirmation={result.card_market_confirmation_missing_but_core_has_market_confirmation} "
            f"card_latest_source_unknown_but_accepted_evidence_exists={result.card_latest_source_unknown_but_accepted_evidence_exists} "
            f"quality_review_promoted_core_in_weak_section={result.quality_review_promoted_core_in_weak_section} "
            f"market_freshness_contradictory_summary={result.market_freshness_contradictory_summary} "
            f"quality_review_market_freshness_contradiction={result.quality_review_market_freshness_contradiction} "
            f"upgrade_candidates_include_high_priority={result.upgrade_candidates_include_high_priority} "
            f"daily_brief_card_group_mismatch_with_index={result.daily_brief_card_group_mismatch_with_index} "
            f"daily_brief_missing_selected_run={result.daily_brief_missing_selected_run} "
            f"daily_brief_selected_run_mismatch={result.daily_brief_selected_run_mismatch} "
            f"daily_brief_core_count_mismatch_store={result.daily_brief_core_count_mismatch_store} "
            f"daily_brief_research_review_lane_missing={result.daily_brief_research_review_lane_missing} "
            f"daily_brief_source_coverage_path_missing={result.daily_brief_source_coverage_path_missing} "
            "daily_brief_coinalyze_source_coverage_mismatch="
            f"{result.daily_brief_coinalyze_source_coverage_mismatch} "
            f"core_route_conflicts_with_opportunity_level={result.core_route_conflicts_with_opportunity_level} "
            f"alert_snapshot_route_mismatch_core_store={result.alert_snapshot_route_mismatch_core_store} "
            f"alert_snapshot_level_mismatch_core_store={result.alert_snapshot_level_mismatch_core_store} "
            f"alert_snapshot_live_confirmation_stale={result.alert_snapshot_live_confirmation_stale} "
            f"alert_snapshot_core_resolution_missing={result.alert_snapshot_core_resolution_missing} "
            f"alert_snapshot_pre_reconciliation_alertable={result.alert_snapshot_pre_reconciliation_alertable} "
            f"diagnostic_support_snapshot_alertable={result.diagnostic_support_snapshot_alertable} "
            f"diagnostic_support_snapshot_inherits_core_route={result.diagnostic_support_snapshot_inherits_core_route} "
            f"duplicate_alertable_snapshot_for_core={result.duplicate_alertable_snapshot_for_core} "
            f"canonical_snapshot_missing_for_visible_core={result.canonical_snapshot_missing_for_visible_core} "
            f"inbox_core_item_missing_card={result.inbox_core_item_missing_card} "
            f"inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists={result.inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists} "
            f"inbox_diagnostic_snapshot_visible_by_default={result.inbox_diagnostic_snapshot_visible_by_default} "
            f"audit_primary_snapshot_not_canonical_when_canonical_exists={result.audit_primary_snapshot_not_canonical_when_canonical_exists} "
            f"feedback_readiness_counts_diagnostic_as_required={result.feedback_readiness_counts_diagnostic_as_required} "
            f"live_validated_without_confirmation={result.live_validated_without_confirmation} "
            f"live_sector_digest_without_asset={result.live_sector_digest_without_asset} "
            f"live_rejected_results_promoted={result.live_rejected_results_promoted} "
            f"live_skipped_budget_promoted={result.live_skipped_budget_promoted} "
            f"raw_core_validated_without_confirmation={result.raw_core_validated_without_confirmation} "
            f"raw_core_source_only_narrative_validated={result.raw_core_source_only_narrative_validated} "
            f"raw_core_cryptopanic_tag_only_direct_path_confirmed={result.raw_core_cryptopanic_tag_only_direct_path_confirmed} "
            f"raw_core_suppressed_duplicate_validated_stale={result.raw_core_suppressed_duplicate_validated_stale} "
            f"confirmed_long_without_source_market={result.confirmed_long_without_source_market} "
            f"fade_short_without_crowding_exhaustion={result.fade_short_without_crowding_exhaustion} "
            f"early_long_without_fresh_strong_source={result.early_long_without_fresh_strong_source} "
            f"risk_only_missing_evidence_only={result.risk_only_missing_evidence_only} "
            f"cryptopanic_only_narrative_confirmed_lane={result.cryptopanic_only_narrative_confirmed_lane} "
            f"diagnostic_visible_default_operator_lane={result.diagnostic_visible_default_operator_lane} "
            f"core_missing_market_state_snapshot={result.core_missing_market_state_snapshot} "
            f"market_state_return_unit_missing={result.market_state_return_unit_missing} "
            f"market_state_possible_double_scaled={result.market_state_possible_double_scaled} "
            f"market_state_lane_possible_double_scaled={result.market_state_lane_possible_double_scaled} "
            f"market_anomaly_rows={result.market_anomaly_rows} "
            f"market_anomaly_missing_market_state_snapshot={result.market_anomaly_missing_market_state_snapshot} "
            f"market_anomaly_missing_market_state_class={result.market_anomaly_missing_market_state_class} "
            f"market_anomaly_confirmed_breakout_missing_evidence={result.market_anomaly_confirmed_breakout_missing_evidence} "
            f"market_anomaly_suspicious_illiquid_promoted_confirmed={result.market_anomaly_suspicious_illiquid_promoted_confirmed} "
            f"market_anomaly_created_alert_rows={result.market_anomaly_created_alert_rows} "
            f"market_anomaly_missing_freshness_status={result.market_anomaly_missing_freshness_status} "
            f"market_anomaly_needs_search_without_plan={result.market_anomaly_needs_search_without_plan} "
            f"official_exchange_candidate_rows={result.official_exchange_candidate_rows} "
            f"official_exchange_candidate_missing_source_fields={result.official_exchange_candidate_missing_source_fields} "
            f"official_exchange_listing_without_official_source={result.official_exchange_listing_without_official_source} "
            f"official_exchange_secret_leak={result.official_exchange_secret_leak} "
            f"official_exchange_delisting_long_research={result.official_exchange_delisting_long_research} "
            f"official_exchange_quote_asset_misclassified={result.official_exchange_quote_asset_misclassified} "
            f"official_exchange_major_pair_noise_promoted_early_long={result.official_exchange_major_pair_noise_promoted_early_long} "
            f"official_exchange_created_alert_rows={result.official_exchange_created_alert_rows} "
            "official_exchange_activation_missing_shared_schema="
            f"{result.official_exchange_activation_missing_shared_schema} "
            "official_exchange_activation_live_without_ledger="
            f"{result.official_exchange_activation_live_without_ledger} "
            "official_exchange_activation_signed_listener_secret_leak="
            f"{result.official_exchange_activation_signed_listener_secret_leak} "
            "official_exchange_activation_forbidden_side_effect_claim="
            f"{result.official_exchange_activation_forbidden_side_effect_claim} "
            "instrument_resolution_missing_canonical_id_when_fixture_has_it="
            f"{result.instrument_resolution_missing_canonical_id_when_fixture_has_it} "
            "instrument_resolution_quote_asset_misclassified="
            f"{result.instrument_resolution_quote_asset_misclassified} "
            "instrument_resolution_sector_visible_as_tradable="
            f"{result.instrument_resolution_sector_visible_as_tradable} "
            "instrument_resolution_coinalyze_symbol_unlinked="
            f"{result.instrument_resolution_coinalyze_symbol_unlinked} "
            f"scheduled_catalyst_rows={result.scheduled_catalyst_rows} "
            f"unlock_candidate_rows={result.unlock_candidate_rows} "
            f"derivatives_state_rows={result.derivatives_state_rows} "
            f"fade_review_candidate_rows={result.fade_review_candidate_rows} "
            f"unlock_without_structured_evidence={result.unlock_without_structured_evidence} "
            f"unlock_missing_event_time={result.unlock_missing_event_time} "
            f"unlock_promoted_without_size_metrics={result.unlock_promoted_without_size_metrics} "
            f"media_unlock_promoted_structured={result.media_unlock_promoted_structured} "
            f"stale_completed_catalyst_upcoming={result.stale_completed_catalyst_upcoming} "
            f"calendar_event_missing_source_url={result.calendar_event_missing_source_url} "
            f"cryptopanic_unlock_proof={result.cryptopanic_unlock_proof} "
            f"scheduled_catalyst_created_alert_rows={result.scheduled_catalyst_created_alert_rows} "
            f"fade_review_without_completed_move={result.fade_review_without_completed_move} "
            f"fade_review_without_crowding_exhaustion={result.fade_review_without_crowding_exhaustion} "
            f"fade_review_created_triggered_fade={result.fade_review_created_triggered_fade} "
            f"fade_review_created_normal_rsi_signal={result.fade_review_created_normal_rsi_signal} "
            f"fade_review_notification_missing_disclaimer={result.fade_review_notification_missing_disclaimer} "
            f"derivatives_artifact_secret_leak={result.derivatives_artifact_secret_leak} "
            f"derivatives_state_missing_freshness_status={result.derivatives_state_missing_freshness_status} "
            "derivatives_metric_claim_implemented_missing="
            f"{result.derivatives_metric_claim_implemented_missing} "
            f"derivatives_unit_metadata_missing={result.derivatives_unit_metadata_missing} "
            "stale_derivatives_snapshot_promoted_fade_review="
            f"{result.stale_derivatives_snapshot_promoted_fade_review} "
            f"confirmed_long_crowded_without_warning={result.confirmed_long_crowded_without_warning} "
            f"integrated_radar_candidate_rows={result.integrated_radar_candidate_rows} "
            f"integrated_candidate_missing_opportunity_type={result.integrated_candidate_missing_opportunity_type} "
            f"integrated_candidate_missing_market_state_snapshot={result.integrated_candidate_missing_market_state_snapshot} "
            f"integrated_confirmed_long_without_source_market={result.integrated_confirmed_long_without_source_market} "
            f"integrated_early_long_without_fresh_strong_source={result.integrated_early_long_without_fresh_strong_source} "
            f"integrated_fade_without_crowding_exhaustion={result.integrated_fade_without_crowding_exhaustion} "
            f"integrated_risk_without_evidence={result.integrated_risk_without_evidence} "
            f"integrated_market_anomaly_confirmed={result.integrated_market_anomaly_confirmed} "
            f"integrated_cryptopanic_confirmed={result.integrated_cryptopanic_confirmed} "
            f"integrated_major_pair_early_long={result.integrated_major_pair_early_long} "
            f"integrated_input_manifest_missing={result.integrated_input_manifest_missing} "
            f"integrated_source_coverage_json_missing={result.integrated_source_coverage_json_missing} "
            f"integrated_candidate_core_missing={result.integrated_candidate_core_missing} "
            f"integrated_candidate_core_opportunity_type_mismatch={result.integrated_candidate_core_opportunity_type_mismatch} "
            f"integrated_candidate_core_market_state_mismatch={result.integrated_candidate_core_market_state_mismatch} "
            f"integrated_candidate_core_route_level_mismatch={result.integrated_candidate_core_route_level_mismatch} "
            f"integrated_candidate_core_reason_code_loss={result.integrated_candidate_core_reason_code_loss} "
            f"integrated_candidate_core_source_url_loss={result.integrated_candidate_core_source_url_loss} "
            f"integrated_candidate_core_official_event_loss={result.integrated_candidate_core_official_event_loss} "
            f"integrated_candidate_core_scheduled_event_loss={result.integrated_candidate_core_scheduled_event_loss} "
            f"integrated_candidate_core_unlock_event_loss={result.integrated_candidate_core_unlock_event_loss} "
            f"integrated_candidate_core_derivatives_loss={result.integrated_candidate_core_derivatives_loss} "
            f"integrated_candidate_card_opportunity_type_mismatch={result.integrated_candidate_card_opportunity_type_mismatch} "
            f"integrated_candidate_card_why_now_mismatch={result.integrated_candidate_card_why_now_mismatch} "
            f"integrated_major_pair_card_early_long={result.integrated_major_pair_card_early_long} "
            f"integrated_card_generic_lane_override={result.integrated_card_generic_lane_override} "
            f"card_opportunity_lane_core_mismatch={result.card_opportunity_lane_core_mismatch} "
            f"integrated_candidate_card_official_event_missing={result.integrated_candidate_card_official_event_missing} "
            f"integrated_candidate_card_source_url_missing={result.integrated_candidate_card_source_url_missing} "
            f"integrated_candidate_core_crowding_metadata_loss={result.integrated_candidate_core_crowding_metadata_loss} "
            f"derivatives_card_metric_claim_without_data={result.derivatives_card_metric_claim_without_data} "
            f"integrated_coinalyze_crowding_card_missing={result.integrated_coinalyze_crowding_card_missing} "
            f"integrated_coinalyze_loaded_no_rows_attached={result.integrated_coinalyze_loaded_no_rows_attached} "
            f"integrated_coinalyze_missing_skip_reason={result.integrated_coinalyze_missing_skip_reason} "
            f"integrated_coinalyze_stale_loaded_without_warning={result.integrated_coinalyze_stale_loaded_without_warning} "
            f"integrated_coinalyze_loaded_from_stale_namespace={result.integrated_coinalyze_loaded_from_stale_namespace} "
            f"integrated_fade_card_crowding_unknown={result.integrated_fade_card_crowding_unknown} "
            f"integrated_fade_card_missing_disclaimer={result.integrated_fade_card_missing_disclaimer} "
            f"integrated_confirmed_long_crowding_warning_hidden={result.integrated_confirmed_long_crowding_warning_hidden} "
            f"integrated_market_confirmation_display_contradiction={result.integrated_market_confirmation_display_contradiction} "
            f"integrated_derivatives_display_contradiction={result.integrated_derivatives_display_contradiction} "
            f"integrated_manifest_mixed_timestamp_pair={result.integrated_manifest_mixed_timestamp_pair} "
            f"integrated_core_silent_upgrade={result.integrated_core_silent_upgrade} "
            f"integrated_diagnostic_visible_in_default_operator_section={result.integrated_diagnostic_visible_in_default_operator_section} "
            f"integrated_preview_missing_disclaimer={result.integrated_preview_missing_disclaimer} "
            f"integrated_delivery_ledger_missing={result.integrated_delivery_ledger_missing} "
            f"integrated_preview_lane_mismatch={result.integrated_preview_lane_mismatch} "
            f"integrated_delivery_missing_disclaimer={result.integrated_delivery_missing_disclaimer} "
            f"integrated_delivery_sent_in_no_send={result.integrated_delivery_sent_in_no_send} "
            f"integrated_delivery_side_effect_flag={result.integrated_delivery_side_effect_flag} "
            f"integrated_delivery_missing_skip_reasons={result.integrated_delivery_missing_skip_reasons} "
            f"integrated_delivery_card_path_absolute={result.integrated_delivery_card_path_absolute} "
            f"integrated_delivery_card_path_not_rendered={result.integrated_delivery_card_path_not_rendered} "
            f"integrated_operator_markdown_absolute_path={result.integrated_operator_markdown_absolute_path} "
            f"operator_structured_path_absolute={result.operator_structured_path_absolute} "
            f"integrated_legacy_preview_alerts_wording={result.integrated_legacy_preview_alerts_wording} "
            f"integrated_manifest_daily_brief_unavailable={result.integrated_manifest_daily_brief_unavailable} "
            f"integrated_outcome_missing_for_candidate={result.integrated_outcome_missing_for_candidate} "
            f"integrated_outcome_side_effect_flag={result.integrated_outcome_side_effect_flag} "
            f"integrated_outcome_schema_missing={result.integrated_outcome_schema_missing} "
            f"integrated_outcome_missing_identity={result.integrated_outcome_missing_identity} "
            f"integrated_outcome_returns_without_price={result.integrated_outcome_returns_without_price} "
            f"integrated_outcome_diagnostic_in_performance={result.integrated_outcome_diagnostic_in_performance} "
            f"integrated_calibration_diagnostic_in_main_priors={result.integrated_calibration_diagnostic_in_main_priors} "
            f"integrated_calibration_prior_safety_missing={result.integrated_calibration_prior_safety_missing} "
            f"integrated_calibration_legacy_alias_top_level={result.integrated_calibration_legacy_alias_top_level} "
            f"integrated_outcome_return_double_scaled={result.integrated_outcome_return_double_scaled} "
            f"integrated_outcome_missing_data_unlabeled={result.integrated_outcome_missing_data_unlabeled} "
            f"integrated_outcome_thesis_move_missing={result.integrated_outcome_thesis_move_missing} "
            "integrated_outcome_card_thesis_interpretation_missing="
            f"{result.integrated_outcome_card_thesis_interpretation_missing} "
            f"integrated_outcome_card_trade_wording={result.integrated_outcome_card_trade_wording} "
            f"integrated_created_normal_rsi_signal={result.integrated_created_normal_rsi_signal} "
            f"integrated_created_triggered_fade={result.integrated_created_triggered_fade} "
            f"source_coverage_report_missing={result.source_coverage_report_missing} "
            f"source_coverage_provider_status_unknown={result.source_coverage_provider_status_unknown} "
            f"source_coverage_provider_marked_healthy_without_observation={result.source_coverage_provider_marked_healthy_without_observation} "
            f"source_coverage_category_priority_missing={result.source_coverage_category_priority_missing} "
            f"source_coverage_readiness_link_missing={result.source_coverage_readiness_link_missing} "
            f"source_coverage_context_provider_ranked_above_lane_critical={result.source_coverage_context_provider_ranked_above_lane_critical} "
            "source_coverage_coinalyze_missing_linked_artifact="
            f"{result.source_coverage_coinalyze_missing_linked_artifact} "
            "source_coverage_bybit_announcements_missing_linked_artifact="
            f"{result.source_coverage_bybit_announcements_missing_linked_artifact} "
            "source_coverage_unlock_calendar_missing_linked_artifact="
            f"{result.source_coverage_unlock_calendar_missing_linked_artifact} "
            f"live_provider_readiness_missing={result.live_provider_readiness_missing} "
            f"live_provider_readiness_secret_leak={result.live_provider_readiness_secret_leak} "
            f"live_provider_readiness_live_calls_allowed_in_smoke={result.live_provider_readiness_live_calls_allowed_in_smoke} "
            f"live_provider_readiness_configured_missing_env={result.live_provider_readiness_configured_missing_env} "
            f"coinalyze_preflight_secret_leak={result.coinalyze_preflight_secret_leak} "
            f"coinalyze_preflight_live_call_allowed_in_smoke={result.coinalyze_preflight_live_call_allowed_in_smoke} "
            f"coinalyze_preflight_configured_missing_env={result.coinalyze_preflight_configured_missing_env} "
            f"coinalyze_preflight_ready_without_request_ledger={result.coinalyze_preflight_ready_without_request_ledger} "
            f"coinalyze_preflight_missing_fixture_parser_status={result.coinalyze_preflight_missing_fixture_parser_status} "
            f"coinalyze_preflight_forbidden_side_effect_claim={result.coinalyze_preflight_forbidden_side_effect_claim} "
            f"coinalyze_rehearsal_secret_leak={result.coinalyze_rehearsal_secret_leak} "
            f"coinalyze_rehearsal_live_without_ledger={result.coinalyze_rehearsal_live_without_ledger} "
            "coinalyze_rehearsal_live_call_allowed_in_smoke="
            f"{result.coinalyze_rehearsal_live_call_allowed_in_smoke} "
            "coinalyze_rehearsal_live_without_explicit_allow="
            f"{result.coinalyze_rehearsal_live_without_explicit_allow} "
            f"coinalyze_rehearsal_request_budget_exceeded={result.coinalyze_rehearsal_request_budget_exceeded} "
            "coinalyze_rehearsal_success_without_derivatives_state="
            f"{result.coinalyze_rehearsal_success_without_derivatives_state} "
            "coinalyze_rehearsal_success_without_crowding_candidates="
            f"{result.coinalyze_rehearsal_success_without_crowding_candidates} "
            "coinalyze_provider_health_healthy_without_successful_ledger="
            f"{result.coinalyze_provider_health_healthy_without_successful_ledger} "
            "coinalyze_rehearsal_forbidden_side_effect_claim="
            f"{result.coinalyze_rehearsal_forbidden_side_effect_claim} "
            "coinalyze_supported_metric_implemented_missing_state="
            f"{result.coinalyze_supported_metric_implemented_missing_state} "
            f"bybit_announcements_preflight_secret_leak={result.bybit_announcements_preflight_secret_leak} "
            "bybit_announcements_preflight_live_call_allowed_in_smoke="
            f"{result.bybit_announcements_preflight_live_call_allowed_in_smoke} "
            "bybit_announcements_preflight_missing_fixture_parser_status="
            f"{result.bybit_announcements_preflight_missing_fixture_parser_status} "
            f"bybit_announcements_rehearsal_secret_leak={result.bybit_announcements_rehearsal_secret_leak} "
            "bybit_announcements_rehearsal_live_without_ledger="
            f"{result.bybit_announcements_rehearsal_live_without_ledger} "
            "bybit_announcements_rehearsal_live_without_explicit_allow="
            f"{result.bybit_announcements_rehearsal_live_without_explicit_allow} "
            "bybit_announcements_rehearsal_unsupported_params="
            f"{result.bybit_announcements_rehearsal_unsupported_params} "
            "bybit_announcements_rehearsal_forbidden_side_effect_claim="
            f"{result.bybit_announcements_rehearsal_forbidden_side_effect_claim} "
            "unlock_calendar_preflight_secret_leak="
            f"{result.unlock_calendar_preflight_secret_leak} "
            "unlock_calendar_preflight_live_without_ledger="
            f"{result.unlock_calendar_preflight_live_without_ledger} "
            "unlock_calendar_preflight_live_call_allowed_in_smoke="
            f"{result.unlock_calendar_preflight_live_call_allowed_in_smoke} "
            "unlock_calendar_preflight_missing_fixture_parser_status="
            f"{result.unlock_calendar_preflight_missing_fixture_parser_status} "
            "unlock_calendar_preflight_forbidden_side_effect_claim="
            f"{result.unlock_calendar_preflight_forbidden_side_effect_claim} "
            f"source_pack_provider_status_missing={result.source_pack_provider_status_missing} "
            f"missing_provider_recommendations_missing={result.missing_provider_recommendations_missing} "
            f"degraded_provider_absence_marked_meaningful={result.degraded_provider_absence_marked_meaningful} "
            f"cryptopanic_configured_but_not_observed={result.cryptopanic_configured_but_not_observed} "
            f"cryptopanic_used_but_no_source_coverage_entry={result.cryptopanic_used_but_no_source_coverage_entry} "
            f"cryptopanic_accepted_evidence_missing_from_card={result.cryptopanic_accepted_evidence_missing_from_card} "
            f"cryptopanic_rejected_only_promoted={result.cryptopanic_rejected_only_promoted} "
            f"cryptopanic_token_printed_or_unredacted={result.cryptopanic_token_printed_or_unredacted} "
            f"cryptopanic_growth_unsupported_param_used={result.cryptopanic_growth_unsupported_param_used} "
            f"cryptopanic_duplicate_request_key={result.cryptopanic_duplicate_request_key} "
            f"cryptopanic_invalid_currency_code={result.cryptopanic_invalid_currency_code} "
            f"cryptopanic_empty_currency_request={result.cryptopanic_empty_currency_request} "
            f"cryptopanic_coin_id_sent_as_currency={result.cryptopanic_coin_id_sent_as_currency} "
            f"cryptopanic_all_requests_failed={result.cryptopanic_all_requests_failed} "
            f"cryptopanic_json_parse_errors={result.cryptopanic_json_parse_errors} "
            f"cryptopanic_configured_but_unusable={result.cryptopanic_configured_but_unusable} "
            f"cryptopanic_status_code_missing_on_http_failure={result.cryptopanic_status_code_missing_on_http_failure} "
            f"cryptopanic_body_excerpt_unredacted_token={result.cryptopanic_body_excerpt_unredacted_token} "
            f"cryptopanic_quota_exceeded={result.cryptopanic_quota_exceeded} "
            f"cryptopanic_request_ledger_missing_when_used={result.cryptopanic_request_ledger_missing_when_used} "
            f"cryptopanic_success_with_backoff_status={result.cryptopanic_success_with_backoff_status} "
            "cryptopanic_restore_token_recommendation_when_configured="
            f"{result.cryptopanic_restore_token_recommendation_when_configured} "
            f"evidence_count_mismatch={result.evidence_count_mismatch} "
            f"visible_sector_core_without_config={result.visible_sector_core_without_config} "
            f"duplicate_proxy_core_rows={result.duplicate_proxy_core_rows}"
        ),
        (
            "snapshot lineage: "
            f"matching={result.runs_with_matching_snapshots} "
            f"missing={result.runs_with_missing_snapshots} "
            f"external={result.runs_with_external_snapshot_paths}"
        ),
        (
            "legacy rows: "
            f"skipped={result.legacy_rows_skipped} counted={result.legacy_rows_counted}"
        ),
        (
            "notification deliveries: "
            f"rows={result.delivery_rows} partial={result.deliveries_partial_delivered} failed={result.deliveries_failed} "
            f"status_missing={result.delivery_status_missing} "
            f"status_detail_missing={result.delivery_status_detail_missing} "
            f"mode_missing={result.delivery_mode_missing} "
            f"state_inconsistent={result.delivery_state_inconsistent} "
            f"would_send_inconsistent={result.delivery_would_send_sent_failed_inconsistent} "
            f"latest_run_id={result.latest_run_id or 'none'} "
            f"strict_scope={result.delivery_strict_scope} "
            f"latest_run_rows={result.latest_run_delivery_rows} "
            f"stale_rows={result.stale_delivery_rows} "
            f"legacy_rows={result.legacy_delivery_rows} "
            f"identity_mismatch={result.delivery_identity_mismatch_core_store} "
            f"core_missing={result.delivery_core_id_missing} "
            f"stale_core_missing={result.stale_delivery_identity_missing_core} "
            f"legacy_pre_core_identity={result.legacy_pre_core_delivery_identity} "
            f"feedback_missing={result.delivery_feedback_target_missing} "
            f"card_missing={result.delivery_card_path_missing} "
            f"alert_id_not_canonical={result.delivery_alert_id_not_canonical} "
            f"digest_without_confirmation={result.digest_item_without_live_confirmation} "
            f"digest_rejected_only={result.digest_item_rejected_results_only} "
            f"strategic_broad_digest={result.strategic_broad_asset_digest_without_confirmation} "
            f"unconfirmed_narrative_daily_digest={result.unconfirmed_narrative_daily_digest} "
            "single_source_no_market_fan_token_digest="
            f"{result.single_source_no_market_fan_token_digest} "
            f"preview_missing={result.notification_preview_missing} "
            f"preview_relpath_missing={result.notification_preview_relpath_missing} "
            f"preview_unresolvable={result.notification_preview_path_unresolvable} "
            f"preview_run_mismatch={result.notification_preview_run_summary_mismatch} "
            f"preview_llm_mismatch={result.notification_preview_llm_summary_mismatch} "
            f"preview_lane_mismatch={result.notification_preview_lane_counts_mismatch} "
            f"preview_core_mismatch={result.notification_preview_core_count_mismatch} "
            f"preview_alertable_mismatch={result.notification_preview_alertable_count_mismatch} "
            f"preview_missing_send_guard={result.notification_preview_missing_send_guard_status} "
            f"preview_send_guard_missing={result.notification_preview_send_guard_status_missing} "
            f"preview_no_send_unclear={result.notification_preview_no_send_status_unclear} "
            f"preview_legacy_alerts_wording={result.notification_preview_legacy_alerts_wording} "
            f"raw_debug_dump={result.telegram_message_contains_raw_debug_dump} "
            f"absolute_path={result.telegram_message_contains_absolute_path} "
            f"research_review_missing_label={result.research_review_digest_missing_confirmation_label} "
            f"research_review_alertable={result.research_review_digest_contains_strict_alertable} "
            f"research_review_hard_gated={result.research_review_digest_contains_hard_gated_candidate} "
            f"research_review_too_many={result.research_review_digest_too_many_items} "
            f"research_review_feedback_missing={result.research_review_digest_missing_feedback_target} "
            f"research_review_skipped_without_reason={result.research_review_digest_skipped_without_reason} "
            f"research_review_missing_family_summary={result.research_review_digest_missing_family_summary} "
            "research_review_duplicate_visible_family_summary="
            f"{result.research_review_digest_duplicate_visible_family_summary} "
            f"research_review_absolute_path={result.research_review_digest_absolute_path} "
            f"body_card_mismatch={result.notification_body_card_mismatch_canonical} "
            f"body_feedback_mismatch={result.notification_body_feedback_mismatch_canonical} "
            f"body_hypothesis_target={result.research_review_body_uses_hypothesis_target_when_core_exists} "
            f"research_review_lane_missing={result.research_review_digest_enabled_but_lane_missing} "
            f"research_review_no_delivery={result.research_review_digest_candidates_without_delivery}"
        ),
        (
            "quality fields: "
            f"missing_total={result.quality_fields_missing_count} "
            f"hypotheses_missing_verdict={result.hypothesis_rows_missing_opportunity_verdict} "
            f"watchlist_missing={result.watchlist_rows_missing_quality_fields} "
            f"alerts_missing={result.alert_rows_missing_quality_fields} "
            f"fresh_hypotheses_missing_top_level={result.fresh_hypothesis_rows_missing_top_level_quality} "
            f"fresh_watchlist_missing_top_level={result.fresh_watchlist_rows_missing_top_level_quality} "
            f"fresh_alerts_missing_top_level={result.fresh_alert_rows_missing_top_level_quality} "
            f"legacy_quality_missing={result.legacy_quality_missing_rows}"
        ),
        (
            "quality gate conflicts: "
            f"alertable_route_conflicts_with_opportunity_level={result.alertable_route_conflicts_with_opportunity_level} "
            f"fresh_quality_route_conflict_rows={result.fresh_quality_route_conflict_rows} "
            f"legacy_quality_conflict_rows={result.legacy_quality_conflict_rows} "
            f"alert_rows_missing_final_route={result.alert_rows_missing_final_route} "
            f"fresh_alert_rows_missing_final_route={result.fresh_alert_rows_missing_final_route}"
        ),
        (
            "watchlist quality state: "
            f"watchlist_state_conflicts_with_quality={result.watchlist_state_conflicts_with_quality} "
            f"universal={result.universal_watchlist_state_conflicts} "
            f"non_hypothesis={result.non_hypothesis_watchlist_quality_conflicts} "
            f"hypothesis={result.hypothesis_watchlist_quality_conflicts} "
            f"quality_capped={result.quality_capped_watchlist_rows} "
            f"active_watchlist_rows_quality_capped={result.active_watchlist_rows_quality_capped} "
            f"fresh_watchlist_state_conflict_rows={result.fresh_watchlist_state_conflict_rows} "
            f"legacy_watchlist_conflicts={result.legacy_watchlist_conflicts}"
        ),
        (
            "incident linkage: "
            f"hypothesis_rows_missing_incident_id={result.hypothesis_rows_missing_incident_id} "
            f"watchlist_hypothesis_rows_missing_incident_id={result.watchlist_hypothesis_rows_missing_incident_id} "
            f"alert_hypothesis_rows_missing_incident_id={result.alert_hypothesis_rows_missing_incident_id} "
            f"incident_rows_without_linked_hypotheses={result.incident_rows_without_linked_hypotheses} "
            f"incident_rows_without_linked_watchlist={result.incident_rows_without_linked_watchlist} "
            f"canonical_unlinked_incidents={result.canonical_unlinked_incidents} "
            f"active_incident_without_qualified_link={result.active_incident_without_qualified_link} "
            f"linked_incident_without_qualified_link={result.linked_incident_without_qualified_link} "
            f"weak_unqualified_incident_links={result.weak_unqualified_incident_links} "
            f"quality_blocked_links_present={result.quality_blocked_links_present} "
            f"quality_blocked_links_promoting_incident={result.quality_blocked_links_promoting_incident} "
            f"diagnostic_incident_rows={result.diagnostic_incident_rows} "
            f"raw_observation_incident_rows={result.raw_observation_incident_rows} "
            f"external_context_incident_rows={result.external_context_incident_rows} "
            f"rejected_incident_rows={result.rejected_incident_rows} "
            f"incident_relevance_missing={result.incident_relevance_missing} "
            f"invalid_canonical_incident_rows={result.invalid_canonical_incident_rows} "
            f"garbage_primary_subject_incidents={result.garbage_primary_subject_incidents} "
            f"fresh_blockers={result.fresh_incident_linkage_blockers} "
            f"legacy_warnings={result.legacy_incident_linkage_warnings}"
        ),
        "",
        "blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("Doctor reports artifact hygiene only; it does not send, trade, paper trade, or alter tiers.")
    return "\n".join(lines).rstrip()
