"""Legacy Event Alpha import compatibility tests.

This is the only test module that intentionally imports old flat Event Alpha
shim paths. Product code and ordinary tests should use canonical package paths.
"""

from __future__ import annotations

import importlib


def test_radar_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_integrated_radar", "crypto_rsi_scanner.event_alpha.radar.integrated_radar", "run_integrated_radar_cycle"),
        ("crypto_rsi_scanner.event_market_state", "crypto_rsi_scanner.event_alpha.radar.market_state", "MarketStateSnapshot"),
        ("crypto_rsi_scanner.event_market_reaction", "crypto_rsi_scanner.event_alpha.radar.market_reaction", "evaluate_market_reaction"),
        ("crypto_rsi_scanner.event_market_anomaly_scanner", "crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner", "scan_market_rows"),
        ("crypto_rsi_scanner.event_core_opportunities", "crypto_rsi_scanner.event_alpha.radar.core_opportunities", "CoreOpportunity"),
        ("crypto_rsi_scanner.event_core_opportunity_store", "crypto_rsi_scanner.event_alpha.radar.core_opportunity_store", "EventCoreOpportunityStoreConfig"),
        ("crypto_rsi_scanner.event_evidence_acquisition", "crypto_rsi_scanner.event_alpha.radar.evidence_acquisition", "run_evidence_acquisition"),
        ("crypto_rsi_scanner.event_opportunity_verdict", "crypto_rsi_scanner.event_alpha.radar.opportunity_verdict", "evaluate_opportunity"),
        ("crypto_rsi_scanner.event_impact_hypotheses", "crypto_rsi_scanner.event_alpha.radar.impact_hypotheses", "generate_impact_hypotheses"),
        ("crypto_rsi_scanner.event_impact_hypothesis_store", "crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store", "write_impact_hypotheses"),
        ("crypto_rsi_scanner.event_incident_store", "crypto_rsi_scanner.event_alpha.radar.incidents", "write_incidents"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_notification_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_alpha_notifications", "crypto_rsi_scanner.event_alpha.notifications.pipeline", "build_notification_plan"),
        ("crypto_rsi_scanner.event_alpha_notification_delivery", "crypto_rsi_scanner.event_alpha.notifications.delivery", "build_record"),
        ("crypto_rsi_scanner.event_alpha_notification_sender", "crypto_rsi_scanner.event_alpha.notifications.sender", "NotificationSendAttemptResult"),
        ("crypto_rsi_scanner.event_alpha_notification_runs", "crypto_rsi_scanner.event_alpha.notifications.runs", "append_notification_run"),
        ("crypto_rsi_scanner.event_alpha_notification_go_no_go", "crypto_rsi_scanner.event_alpha.notifications.go_no_go", "build_go_no_go"),
        ("crypto_rsi_scanner.event_alpha_notification_checklist", "crypto_rsi_scanner.event_alpha.notifications.checklist", "build_notification_checklist"),
        ("crypto_rsi_scanner.event_alpha_notification_inbox", "crypto_rsi_scanner.event_alpha.notifications.inbox", "build_notification_inbox"),
        ("crypto_rsi_scanner.event_alpha_notification_pack", "crypto_rsi_scanner.event_alpha.notifications.pack", "export_notification_pack"),
        ("crypto_rsi_scanner.event_alpha_notification_pause", "crypto_rsi_scanner.event_alpha.notifications.pause", "read_pause_state"),
        ("crypto_rsi_scanner.event_alpha_notification_slo", "crypto_rsi_scanner.event_alpha.notifications.slo", "build_slo_report"),
        ("crypto_rsi_scanner.event_alpha_send_readiness", "crypto_rsi_scanner.event_alpha.notifications.readiness", "build_send_readiness"),
        ("crypto_rsi_scanner.event_alpha_telegram_final_check", "crypto_rsi_scanner.event_alpha.notifications.final_check", "build_final_check"),
        ("crypto_rsi_scanner.event_alpha_telegram_recipient_check", "crypto_rsi_scanner.event_alpha.notifications.recipient_check", "run_recipient_check"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_outcome_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_integrated_radar_outcomes", "crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes", "fill_integrated_radar_outcomes"),
        ("crypto_rsi_scanner.event_alpha_calibration", "crypto_rsi_scanner.event_alpha.outcomes.calibration", "format_calibration_report"),
        ("crypto_rsi_scanner.event_alpha_eval_export", "crypto_rsi_scanner.event_alpha.outcomes.feedback", "export_cases_from_feedback"),
        ("crypto_rsi_scanner.event_alpha_feedback_readiness", "crypto_rsi_scanner.event_alpha.outcomes.feedback", "build_feedback_readiness"),
        ("crypto_rsi_scanner.event_alpha_burn_in", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "build_burn_in_scorecard"),
        ("crypto_rsi_scanner.event_alpha_burn_in_readiness", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "build_burn_in_readiness"),
        ("crypto_rsi_scanner.event_alpha_burn_in_pack", "crypto_rsi_scanner.event_alpha.outcomes.burn_in", "export_burn_in_pack"),
        ("crypto_rsi_scanner.event_alpha_quality_review", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_quality_review"),
        ("crypto_rsi_scanner.event_alpha_quality_coverage", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_latest_run_quality_coverage"),
        ("crypto_rsi_scanner.event_alpha_signal_quality", "crypto_rsi_scanner.event_alpha.outcomes.quality", "evaluate_signal_quality_cases"),
        ("crypto_rsi_scanner.event_alpha_signal_quality_export", "crypto_rsi_scanner.event_alpha.outcomes.quality", "export_signal_quality_cases"),
        ("crypto_rsi_scanner.event_alpha_tuning", "crypto_rsi_scanner.event_alpha.outcomes.quality", "build_tuning_worksheet"),
        ("crypto_rsi_scanner.event_alpha_priors", "crypto_rsi_scanner.event_alpha.outcomes.priors", "apply_priors_to_alerts"),
        ("crypto_rsi_scanner.event_alpha_policy_simulator", "crypto_rsi_scanner.event_alpha.outcomes.policy_simulator", "simulate_policy"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_provider_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_coinalyze_preflight", "crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_live_provider_readiness", "crypto_rsi_scanner.event_alpha.providers.live_provider_readiness", "build_readiness_report"),
        ("crypto_rsi_scanner.event_official_exchange", "crypto_rsi_scanner.event_alpha.providers.official_exchange", "run_official_exchange_scan"),
        ("crypto_rsi_scanner.event_official_exchange_activation", "crypto_rsi_scanner.event_alpha.providers.official_exchange_activation", "build_activation_report"),
        ("crypto_rsi_scanner.event_alpha_cryptopanic", "crypto_rsi_scanner.event_alpha.providers.cryptopanic", "build_cryptopanic_preflight"),
        ("crypto_rsi_scanner.event_provider_health", "crypto_rsi_scanner.event_alpha.providers.provider_health", "record_provider_success"),
        ("crypto_rsi_scanner.event_source_registry", "crypto_rsi_scanner.event_alpha.providers.source_registry", "assess_source"),
        ("crypto_rsi_scanner.event_source_packs", "crypto_rsi_scanner.event_alpha.providers.source_packs", "get_source_pack"),
        ("crypto_rsi_scanner.event_bybit_announcements_preflight", "crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_unlock_calendar_preflight", "crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_dex_onchain_readiness", "crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness", "run_dex_onchain_readiness"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_recently_migrated_old_and_new_import_paths_share_key_callables():
    pairs = (
        ("crypto_rsi_scanner.event_research_cards", "crypto_rsi_scanner.event_alpha.artifacts.research_cards", "render_research_card"),
        ("crypto_rsi_scanner.event_alpha_daily_brief", "crypto_rsi_scanner.event_alpha.artifacts.daily_brief", "build_daily_brief"),
        ("crypto_rsi_scanner.event_derivatives_crowding", "crypto_rsi_scanner.event_alpha.radar.derivatives_crowding", "run_derivatives_crowding_scan"),
        ("crypto_rsi_scanner.event_scheduled_catalysts", "crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts", "run_scheduled_catalyst_scan"),
        ("crypto_rsi_scanner.event_asset_registry", "crypto_rsi_scanner.event_alpha.radar.asset_registry", "build_asset_registry"),
        ("crypto_rsi_scanner.event_instrument_resolver", "crypto_rsi_scanner.event_alpha.radar.instrument_resolver", "resolve_rows"),
        ("crypto_rsi_scanner.event_market_confirmation", "crypto_rsi_scanner.event_alpha.radar.market_confirmation", "evaluate_market_confirmation"),
        ("crypto_rsi_scanner.event_catalyst_search", "crypto_rsi_scanner.event_alpha.radar.catalyst_search", "run_catalyst_search"),
        ("crypto_rsi_scanner.event_source_enrichment", "crypto_rsi_scanner.event_alpha.radar.source_enrichment", "enrich_source_text"),
        ("crypto_rsi_scanner.event_opportunity_audit", "crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit", "format_opportunity_audit"),
        ("crypto_rsi_scanner.event_validation", "crypto_rsi_scanner.event_alpha.radar.validation", "ValidationOutcomeCandle"),
        ("crypto_rsi_scanner.event_discovery", "crypto_rsi_scanner.event_alpha.radar.discovery", "EventDiscoveryConfig"),
        ("crypto_rsi_scanner.event_near_miss", "crypto_rsi_scanner.event_alpha.radar.near_miss", "EventNearMissCandidate"),
        ("crypto_rsi_scanner.event_classification", "crypto_rsi_scanner.event_alpha.radar.classification", "classify_event_asset"),
        ("crypto_rsi_scanner.event_catalyst_frames", "crypto_rsi_scanner.event_alpha.radar.catalyst_frames", "build_catalyst_frames"),
        ("crypto_rsi_scanner.event_claim_semantics", "crypto_rsi_scanner.event_alpha.radar.claim_semantics", "extract_event_claims"),
        ("crypto_rsi_scanner.event_playbooks", "crypto_rsi_scanner.event_alpha.radar.playbooks", "assess_event_playbook"),
        ("crypto_rsi_scanner.event_impact_path_validator", "crypto_rsi_scanner.event_alpha.radar.impact_path_validator", "validate_impact_path"),
        ("crypto_rsi_scanner.event_evidence_quality", "crypto_rsi_scanner.event_alpha.radar.evidence_quality", "evaluate_evidence_quality"),
        ("crypto_rsi_scanner.event_market_enrichment", "crypto_rsi_scanner.event_alpha.radar.market_enrichment", "load_market_enrichment_rows"),
        ("crypto_rsi_scanner.event_llm_extractor", "crypto_rsi_scanner.event_alpha.radar.llm.extractor", "analyze_raw_events"),
        ("crypto_rsi_scanner.event_llm_analyzer", "crypto_rsi_scanner.event_alpha.radar.llm.analyzer", "analyze_event_candidates"),
        ("crypto_rsi_scanner.event_llm_evidence_planner", "crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner", "EvidencePlannerRequest"),
        ("crypto_rsi_scanner.event_llm_catalyst_frames", "crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames", "EventLLMCatalystFrameConfig"),
        ("crypto_rsi_scanner.event_llm_extract_eval", "crypto_rsi_scanner.event_alpha.radar.llm.extract_eval", "run_fixture_eval"),
        ("crypto_rsi_scanner.event_llm_eval", "crypto_rsi_scanner.event_alpha.radar.llm.eval", "run_fixture_eval"),
        ("crypto_rsi_scanner.event_llm_models", "crypto_rsi_scanner.event_alpha.radar.llm.models", "EventLLMAssetRole"),
        ("crypto_rsi_scanner.event_llm_extraction_models", "crypto_rsi_scanner.event_alpha.radar.llm.extraction_models", "EventLLMCatalystType"),
        ("crypto_rsi_scanner.event_alpha_alert_store", "crypto_rsi_scanner.event_alpha.artifacts.alert_store", "write_alert_snapshots"),
        ("crypto_rsi_scanner.event_alerts", "crypto_rsi_scanner.event_alpha.artifacts.alerts", "build_event_alert_candidates"),
        ("crypto_rsi_scanner.event_alpha_router", "crypto_rsi_scanner.event_alpha.notifications.router", "EventAlphaRoute"),
        ("crypto_rsi_scanner.event_alpha_pipeline", "crypto_rsi_scanner.event_alpha.radar.pipeline", "run_event_alpha_pipeline"),
        ("crypto_rsi_scanner.event_watchlist", "crypto_rsi_scanner.event_alpha.radar.watchlist", "EventWatchlistState"),
        ("crypto_rsi_scanner.event_watchlist_monitor", "crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor", "monitor_watchlist"),
        ("crypto_rsi_scanner.event_watchlist_enrichment", "crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment", "EventWatchlistEnrichmentResult"),
        ("crypto_rsi_scanner.event_watchlist_market", "crypto_rsi_scanner.event_alpha.radar.watchlist_market", "market_rows_for_watchlist"),
        ("crypto_rsi_scanner.event_alpha_replay", "crypto_rsi_scanner.event_alpha.artifacts.replay", "replay_from_artifacts"),
        ("crypto_rsi_scanner.event_feedback", "crypto_rsi_scanner.event_alpha.outcomes.feedback_labels", "mark_feedback"),
        ("crypto_rsi_scanner.event_incident_graph", "crypto_rsi_scanner.event_alpha.radar.incident_graph", "build_incidents"),
        ("crypto_rsi_scanner.event_identity", "crypto_rsi_scanner.event_alpha.radar.identity", "match_asset_identity"),
        ("crypto_rsi_scanner.event_graph", "crypto_rsi_scanner.event_alpha.radar.graph", "build_event_clusters"),
        ("crypto_rsi_scanner.event_resolver", "crypto_rsi_scanner.event_alpha.radar.resolver", "resolve_event_assets"),
        ("crypto_rsi_scanner.event_price_history", "crypto_rsi_scanner.event_alpha.radar.price_history", "export_outcome_price_fixture"),
        ("crypto_rsi_scanner.event_catalyst_frame_validator", "crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator", "validate_llm_catalyst_frames"),
        ("crypto_rsi_scanner.event_anomaly_state", "crypto_rsi_scanner.event_alpha.radar.anomaly_state", "build_anomaly_lifecycle"),
        ("crypto_rsi_scanner.event_anomaly_scanner", "crypto_rsi_scanner.event_alpha.radar.anomaly_scanner", "discover_market_anomalies"),
        ("crypto_rsi_scanner.event_market_units", "crypto_rsi_scanner.event_alpha.radar.market_units", "normalize_return_fraction"),
        ("crypto_rsi_scanner.event_llm_budget", "crypto_rsi_scanner.event_alpha.radar.llm.budget", "EventLLMBudgetRunTracker"),
        ("crypto_rsi_scanner.event_llm_catalyst_frames_eval", "crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval", "main"),
        ("crypto_rsi_scanner.event_source_reliability", "crypto_rsi_scanner.event_alpha.providers.source_reliability", "format_source_reliability_report"),
        ("crypto_rsi_scanner.event_cache", "crypto_rsi_scanner.event_alpha.artifacts.cache", "write_event_discovery_cache"),
        ("crypto_rsi_scanner.event_alpha_explain", "crypto_rsi_scanner.event_alpha.artifacts.explain", "format_last_run_explanation"),
        ("crypto_rsi_scanner.event_alpha_quality_fields", "crypto_rsi_scanner.event_alpha.outcomes.quality_fields", "ensure_quality_fields"),
        ("crypto_rsi_scanner.event_alpha_outcomes", "crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts", "summarize_outcome_metrics"),
        ("crypto_rsi_scanner.event_alpha_eval", "crypto_rsi_scanner.event_alpha.outcomes.eval", "run_eval"),
        ("crypto_rsi_scanner.event_alpha_burn_in_checklist", "crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist", "build_burn_in_checklist"),
        ("crypto_rsi_scanner.event_alpha_profiles", "crypto_rsi_scanner.event_alpha.config.profiles", "get_profile"),
        ("crypto_rsi_scanner.event_alpha_v1_readiness", "crypto_rsi_scanner.event_alpha.config.v1_readiness", "build_v1_readiness"),
        ("crypto_rsi_scanner.event_alpha_preflight", "crypto_rsi_scanner.event_alpha.config.preflight", "run_preflight"),
        ("crypto_rsi_scanner.event_alpha_health_guard", "crypto_rsi_scanner.event_alpha.config.health_guard", "evaluate_health_guard"),
        ("crypto_rsi_scanner.event_alpha_scheduler", "crypto_rsi_scanner.event_alpha.config.scheduler", "build_scheduler_status"),
        ("crypto_rsi_scanner.event_alpha_environment_doctor", "crypto_rsi_scanner.event_alpha.doctor.environment", "build_environment_doctor"),
        ("crypto_rsi_scanner.event_provider_status", "crypto_rsi_scanner.event_alpha.notifications.provider_status", "build_event_discovery_provider_status"),
        ("crypto_rsi_scanner.event_alpha_missed", "crypto_rsi_scanner.event_alpha.radar.missed", "detect_missed_opportunities"),
        ("crypto_rsi_scanner.event_alpha_reason_text", "crypto_rsi_scanner.event_alpha.artifacts.reason_text", "humanize_event_alpha_reason"),
        ("crypto_rsi_scanner.event_clock", "crypto_rsi_scanner.event_core.clock", "event_clock_status"),
        ("crypto_rsi_scanner.event_models", "crypto_rsi_scanner.event_core.models", "RawDiscoveredEvent"),
    )
    for old_name, new_name, attr in pairs:
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert getattr(old_module, attr) is getattr(new_module, attr)
