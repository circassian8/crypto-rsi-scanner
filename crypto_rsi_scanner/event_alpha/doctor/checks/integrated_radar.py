"""Integrated radar, core-opportunity, and card consistency checks."""

from __future__ import annotations

from collections.abc import Mapping

from ._utils import Messages, ctx_mapping, ctx_value, emit


def apply_core_card_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    core_store_available = bool(ctx_value(ctx, "core_store_available", False))
    card_count = int(ctx_value(ctx, "card_count", 0) or 0)
    include_test_artifacts = bool(ctx_value(ctx, "include_test_artifacts", False))
    include_api_artifacts = bool(ctx_value(ctx, "include_api_artifacts", False))
    acquisition_final_conflicts = ctx_mapping(ctx, "acquisition_final_conflicts")
    daily_brief_conflicts = ctx_mapping(ctx, "daily_brief_conflicts")
    live_confirmation_conflicts = ctx_mapping(ctx, "live_confirmation_conflicts")
    raw_core_conflicts = ctx_mapping(ctx, "raw_core_conflicts")
    opportunity_lane_conflicts = ctx_mapping(ctx, "opportunity_lane_conflicts")
    market_anomaly_conflicts = ctx_mapping(ctx, "market_anomaly_conflicts")

    if card_count and not ctx_value(ctx, "index_present", False):
        emit(blockers, warnings, "research cards exist but index.md was not found", blocker=strict)
    if ctx_value(ctx, "cards_missing_lineage", 0):
        emit(blockers, warnings, f"research cards missing current lineage: {ctx_value(ctx, 'cards_missing_lineage')}", blocker=strict)
    if ctx_value(ctx, "cards_missing_feedback_target", 0):
        emit(blockers, warnings, f"research cards missing feedback target: {ctx_value(ctx, 'cards_missing_feedback_target')}", blocker=strict)
    if ctx_value(ctx, "visible_missing_cards", 0):
        message = f"visible_core_opportunities_missing_cards={ctx_value(ctx, 'visible_missing_cards')}"
        emit(blockers, warnings, message, blocker=strict and bool(ctx_value(ctx, "fresh_visible_missing_cards", 0)))
    if ctx_value(ctx, "visible_missing_store_rows", 0):
        message = f"visible_core_opportunities_missing_store_rows={ctx_value(ctx, 'visible_missing_store_rows')}"
        strict_core_store = strict and not include_test_artifacts and not include_api_artifacts
        emit(blockers, warnings, message, blocker=strict_core_store)
    if ctx_value(ctx, "duplicate_store_rows", 0):
        warnings.append(f"duplicate_core_opportunity_store_rows={ctx_value(ctx, 'duplicate_store_rows')}")
    if ctx_value(ctx, "store_rows_missing_card_path", 0):
        message = f"core_opportunity_store_rows_missing_card_path={ctx_value(ctx, 'store_rows_missing_card_path')}"
        emit(blockers, warnings, message, blocker=strict and bool(card_count))
    if ctx_value(ctx, "core_cards_missing_store", 0):
        message = f"core_cards_missing_store_row={ctx_value(ctx, 'core_cards_missing_store')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "orphan_core_cards", 0):
        warnings.append(f"orphan_core_opportunity_cards={ctx_value(ctx, 'orphan_core_cards')}")
    if ctx_value(ctx, "diagnostic_fake_core", 0):
        warnings.append(f"diagnostic_snapshots_with_fake_core_id={ctx_value(ctx, 'diagnostic_fake_core')}")
    if ctx_value(ctx, "snapshot_core_missing_store", 0):
        message = f"alert_snapshots_core_id_missing_from_store={ctx_value(ctx, 'snapshot_core_missing_store')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "acquisition_core_missing_store", 0):
        message = f"evidence_acquisition_core_id_missing_from_store={ctx_value(ctx, 'acquisition_core_missing_store')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_primary_mismatches", 0):
        message = f"card_primary_fields_mismatch_core_store={ctx_value(ctx, 'card_primary_mismatches')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_acquisition_mismatches", 0):
        message = f"card_evidence_acquisition_count_mismatch={ctx_value(ctx, 'card_acquisition_mismatches')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if acquisition_final_conflicts.get("evidence_acquisition_stale_validated_digest", 0):
        message = (
            "evidence_acquisition_stale_validated_digest="
            f"{acquisition_final_conflicts['evidence_acquisition_stale_validated_digest']}"
        )
        emit(blockers, warnings, message, blocker=strict)
    if ctx_value(ctx, "card_source_pack_mismatches", 0):
        message = f"card_source_pack_mismatch_core_acquisition={ctx_value(ctx, 'card_source_pack_mismatches')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_support_blockers", 0):
        message = f"card_primary_section_contains_support_row_blockers={ctx_value(ctx, 'card_support_blockers')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_upgrade_inconsistent", 0):
        message = f"card_upgrade_text_inconsistent_with_final_level={ctx_value(ctx, 'card_upgrade_inconsistent')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_market_missing", 0):
        message = f"card_market_confirmation_missing_but_core_has_market_confirmation={ctx_value(ctx, 'card_market_missing')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "card_source_unknown", 0):
        message = f"card_latest_source_unknown_but_accepted_evidence_exists={ctx_value(ctx, 'card_source_unknown')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "promoted_core_in_weak", 0):
        emit(blockers, warnings, f"quality_review_promoted_core_in_weak_section={ctx_value(ctx, 'promoted_core_in_weak')}", blocker=strict)
    if ctx_value(ctx, "market_freshness_contradictions", 0):
        emit(blockers, warnings, f"market_freshness_contradictory_summary={ctx_value(ctx, 'market_freshness_contradictions')}", blocker=strict)
    if ctx_value(ctx, "upgrade_high_priority", 0):
        emit(blockers, warnings, f"upgrade_candidates_include_high_priority={ctx_value(ctx, 'upgrade_high_priority')}", blocker=strict)
    if ctx_value(ctx, "card_group_mismatches", 0):
        message = f"daily_brief_card_group_mismatch_with_index={ctx_value(ctx, 'card_group_mismatches')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    for key in (
        "daily_brief_missing_selected_run",
        "daily_brief_selected_run_mismatch",
        "daily_brief_core_count_mismatch_store",
        "daily_brief_research_review_lane_missing",
        "daily_brief_source_coverage_path_missing",
        "daily_brief_coinalyze_source_coverage_mismatch",
    ):
        count = daily_brief_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    if ctx_value(ctx, "core_route_conflicts", 0):
        message = f"core_route_conflicts_with_opportunity_level={ctx_value(ctx, 'core_route_conflicts')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    for key in (
        "live_validated_without_confirmation",
        "live_sector_digest_without_asset",
        "live_rejected_results_promoted",
        "live_skipped_budget_promoted",
    ):
        count = live_confirmation_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict and core_store_available)
    for key in (
        "raw_core_validated_without_confirmation",
        "raw_core_source_only_narrative_validated",
        "raw_core_cryptopanic_tag_only_direct_path_confirmed",
        "raw_core_suppressed_duplicate_validated_stale",
    ):
        count = raw_core_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict and core_store_available)
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
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict and core_store_available)
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
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "market_anomaly_missing_freshness_status",
        "market_anomaly_needs_search_without_plan",
    ):
        count = market_anomaly_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")


def apply_integrated_artifact_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    integrated_conflicts = ctx_mapping(ctx, "integrated_conflicts")
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
        "integrated_dex_low_liquidity_promoted_confirmed",
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
        "integrated_delivery_card_path_not_rendered",
        "integrated_api_preview_alerts_wording",
        "integrated_manifest_daily_brief_unavailable",
        "integrated_outcome_missing_for_candidate",
        "integrated_outcome_side_effect_flag",
        "integrated_outcome_schema_missing",
        "integrated_outcome_missing_identity",
        "integrated_outcome_returns_without_price",
        "integrated_outcome_diagnostic_in_performance",
        "integrated_calibration_diagnostic_in_main_priors",
        "integrated_calibration_prior_safety_missing",
        "integrated_calibration_api_alias_top_level",
        "integrated_outcome_return_double_scaled",
        "integrated_outcome_missing_data_unlabeled",
        "integrated_outcome_thesis_move_missing",
        "integrated_outcome_card_thesis_interpretation_missing",
        "integrated_outcome_card_trade_wording",
        "integrated_performance_diagnostic_in_main_aggregate",
        "integrated_performance_auto_apply_enabled",
        "integrated_performance_low_sample_missing_warning",
        "integrated_performance_trade_pnl_wording",
        "integrated_created_normal_rsi_signal",
        "integrated_created_triggered_fade",
    ):
        count = integrated_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)


def apply_identity_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    core_store_available = bool(ctx_value(ctx, "core_store_available", False))
    alerts = ctx_value(ctx, "alerts", ())
    card_count = int(ctx_value(ctx, "card_count", 0) or 0)

    if ctx_value(ctx, "evidence_count_mismatches", 0):
        emit(blockers, warnings, f"evidence_count_mismatch={ctx_value(ctx, 'evidence_count_mismatches')}", blocker=strict)
    if ctx_value(ctx, "visible_sector_cores", 0):
        emit(blockers, warnings, f"visible_sector_core_without_config={ctx_value(ctx, 'visible_sector_cores')}", blocker=strict)
    if ctx_value(ctx, "duplicate_proxy_cores", 0):
        emit(blockers, warnings, f"duplicate_proxy_core_rows={ctx_value(ctx, 'duplicate_proxy_cores')}", blocker=strict)
    if ctx_value(ctx, "visible_missing_targets", 0):
        message = f"visible_core_opportunities_missing_feedback_targets={ctx_value(ctx, 'visible_missing_targets')}"
        emit(blockers, warnings, message, blocker=strict and bool(ctx_value(ctx, "fresh_visible_missing_targets", 0)))
    if ctx_value(ctx, "snapshots_missing_core", 0):
        warnings.append(f"alert_snapshots_missing_core_opportunity_id={ctx_value(ctx, 'snapshots_missing_core')}")
    if ctx_value(ctx, "snapshots_missing_feedback", 0):
        emit(blockers, warnings, f"alert_snapshots_missing_feedback_target={ctx_value(ctx, 'snapshots_missing_feedback')}", blocker=strict)
    if ctx_value(ctx, "inbox_core_missing_card", 0):
        message = f"inbox_core_item_missing_card={ctx_value(ctx, 'inbox_core_missing_card')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "inbox_core_alert_target", 0):
        message = (
            "inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists="
            f"{ctx_value(ctx, 'inbox_core_alert_target')}"
        )
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "inbox_diag_visible_default", 0):
        emit(blockers, warnings, f"inbox_diagnostic_snapshot_visible_by_default={ctx_value(ctx, 'inbox_diag_visible_default')}", blocker=strict)
    if ctx_value(ctx, "audit_primary_not_canonical", 0):
        message = f"audit_primary_snapshot_not_canonical_when_canonical_exists={ctx_value(ctx, 'audit_primary_not_canonical')}"
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if ctx_value(ctx, "diagnostic_snapshots_missing_feedback", 0):
        warnings.append(
            "feedback_readiness_counts_diagnostic_as_required="
            f"{ctx_value(ctx, 'diagnostic_snapshots_missing_feedback')}"
        )
    if alerts and not card_count:
        has_priority_alerts = any(
            isinstance(row, Mapping) and str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"}
            for row in alerts
        )
        if has_priority_alerts:
            warnings.append("high-priority/triggered snapshots exist but no research cards were found")
