"""Legacy Event Alpha import compatibility tests.

This is the only test module that intentionally imports retained old flat Event
Alpha shim paths. Product code and ordinary tests should use canonical package
paths. Deleted non-public shim paths are asserted to fail import here so future
passes do not accidentally recreate them.
"""

from __future__ import annotations

import importlib
import sys


RETAINED_OLD_SHIM_MODULES = (
    ('crypto_rsi_scanner.event_alpha_artifacts', 'crypto_rsi_scanner.event_alpha.artifacts.context'),
    ('crypto_rsi_scanner.event_artifact_paths', 'crypto_rsi_scanner.event_alpha.artifacts.paths'),
    ('crypto_rsi_scanner.event_alpha_run_ledger', 'crypto_rsi_scanner.event_alpha.artifacts.run_ledger'),
    ('crypto_rsi_scanner.event_alpha_retention', 'crypto_rsi_scanner.event_alpha.artifacts.retention'),
    ('crypto_rsi_scanner.event_alpha_run_lock', 'crypto_rsi_scanner.event_alpha.artifacts.locks'),
    ('crypto_rsi_scanner.event_alpha_artifact_doctor', 'crypto_rsi_scanner.event_alpha.doctor.artifact_doctor'),
    ('crypto_rsi_scanner.event_alpha_profiles', 'crypto_rsi_scanner.event_alpha.config.profiles'),
    ('crypto_rsi_scanner.event_alpha_v1_readiness', 'crypto_rsi_scanner.event_alpha.config.v1_readiness'),
    ('crypto_rsi_scanner.event_alpha_preflight', 'crypto_rsi_scanner.event_alpha.config.preflight'),
)


DELETED_OLD_SHIM_MODULES = (
    'crypto_rsi_scanner.event_integrated_radar',
    'crypto_rsi_scanner.event_market_anomaly_scanner',
    'crypto_rsi_scanner.event_market_state',
    'crypto_rsi_scanner.event_market_reaction',
    'crypto_rsi_scanner.event_core_opportunities',
    'crypto_rsi_scanner.event_core_opportunity_store',
    'crypto_rsi_scanner.event_evidence_acquisition',
    'crypto_rsi_scanner.event_opportunity_verdict',
    'crypto_rsi_scanner.event_impact_hypotheses',
    'crypto_rsi_scanner.event_impact_hypothesis_store',
    'crypto_rsi_scanner.event_incident_store',
    'crypto_rsi_scanner.event_research_cards',
    'crypto_rsi_scanner.event_alpha_daily_brief',
    'crypto_rsi_scanner.event_opportunity_audit',
    'crypto_rsi_scanner.event_alpha_notifications',
    'crypto_rsi_scanner.event_alpha_notification_delivery',
    'crypto_rsi_scanner.event_alpha_notification_sender',
    'crypto_rsi_scanner.event_alpha_notification_runs',
    'crypto_rsi_scanner.event_alpha_notification_go_no_go',
    'crypto_rsi_scanner.event_alpha_notification_checklist',
    'crypto_rsi_scanner.event_alpha_notification_inbox',
    'crypto_rsi_scanner.event_alpha_notification_pack',
    'crypto_rsi_scanner.event_alpha_notification_pause',
    'crypto_rsi_scanner.event_alpha_notification_slo',
    'crypto_rsi_scanner.event_alpha_send_readiness',
    'crypto_rsi_scanner.event_alpha_telegram_final_check',
    'crypto_rsi_scanner.event_alpha_telegram_recipient_check',
    'crypto_rsi_scanner.event_integrated_radar_outcomes',
    'crypto_rsi_scanner.event_alpha_calibration',
    'crypto_rsi_scanner.event_alpha_eval_export',
    'crypto_rsi_scanner.event_alpha_feedback_readiness',
    'crypto_rsi_scanner.event_alpha_burn_in',
    'crypto_rsi_scanner.event_alpha_burn_in_readiness',
    'crypto_rsi_scanner.event_alpha_burn_in_pack',
    'crypto_rsi_scanner.event_alpha_quality_review',
    'crypto_rsi_scanner.event_alpha_quality_coverage',
    'crypto_rsi_scanner.event_alpha_signal_quality',
    'crypto_rsi_scanner.event_alpha_signal_quality_export',
    'crypto_rsi_scanner.event_alpha_tuning',
    'crypto_rsi_scanner.event_alpha_priors',
    'crypto_rsi_scanner.event_alpha_policy_simulator',
    'crypto_rsi_scanner.event_alpha_cryptopanic',
    'crypto_rsi_scanner.event_official_exchange',
    'crypto_rsi_scanner.event_official_exchange_activation',
    'crypto_rsi_scanner.event_coinalyze_preflight',
    'crypto_rsi_scanner.event_live_provider_readiness',
    'crypto_rsi_scanner.event_provider_health',
    'crypto_rsi_scanner.event_source_registry',
    'crypto_rsi_scanner.event_source_packs',
    'crypto_rsi_scanner.event_bybit_announcements_preflight',
    'crypto_rsi_scanner.event_unlock_calendar_preflight',
    'crypto_rsi_scanner.event_dex_onchain_readiness',
    'crypto_rsi_scanner.event_derivatives_crowding',
    'crypto_rsi_scanner.event_scheduled_catalysts',
    'crypto_rsi_scanner.event_asset_registry',
    'crypto_rsi_scanner.event_instrument_resolver',
    'crypto_rsi_scanner.event_market_confirmation',
    'crypto_rsi_scanner.event_catalyst_search',
    'crypto_rsi_scanner.event_source_enrichment',
    'crypto_rsi_scanner.event_validation',
    'crypto_rsi_scanner.event_discovery',
    'crypto_rsi_scanner.event_near_miss',
    'crypto_rsi_scanner.event_classification',
    'crypto_rsi_scanner.event_catalyst_frames',
    'crypto_rsi_scanner.event_claim_semantics',
    'crypto_rsi_scanner.event_playbooks',
    'crypto_rsi_scanner.event_impact_path_validator',
    'crypto_rsi_scanner.event_evidence_quality',
    'crypto_rsi_scanner.event_market_enrichment',
    'crypto_rsi_scanner.event_llm_extractor',
    'crypto_rsi_scanner.event_llm_analyzer',
    'crypto_rsi_scanner.event_llm_evidence_planner',
    'crypto_rsi_scanner.event_llm_catalyst_frames',
    'crypto_rsi_scanner.event_llm_models',
    'crypto_rsi_scanner.event_llm_extraction_models',
    'crypto_rsi_scanner.event_alpha_alert_store',
    'crypto_rsi_scanner.event_alerts',
    'crypto_rsi_scanner.event_alpha_router',
    'crypto_rsi_scanner.event_alpha_pipeline',
    'crypto_rsi_scanner.event_watchlist',
    'crypto_rsi_scanner.event_watchlist_monitor',
    'crypto_rsi_scanner.event_watchlist_enrichment',
    'crypto_rsi_scanner.event_watchlist_market',
    'crypto_rsi_scanner.event_alpha_replay',
    'crypto_rsi_scanner.event_feedback',
    'crypto_rsi_scanner.event_alpha_source_coverage',
    'crypto_rsi_scanner.event_alpha_namespace_status',
    'crypto_rsi_scanner.event_llm_extract_eval',
    'crypto_rsi_scanner.event_llm_eval',
    'crypto_rsi_scanner.event_incident_graph',
    'crypto_rsi_scanner.event_identity',
    'crypto_rsi_scanner.event_graph',
    'crypto_rsi_scanner.event_resolver',
    'crypto_rsi_scanner.event_price_history',
    'crypto_rsi_scanner.event_catalyst_frame_validator',
    'crypto_rsi_scanner.event_anomaly_state',
    'crypto_rsi_scanner.event_anomaly_scanner',
    'crypto_rsi_scanner.event_market_units',
    'crypto_rsi_scanner.event_llm_budget',
    'crypto_rsi_scanner.event_llm_catalyst_frames_eval',
    'crypto_rsi_scanner.event_source_reliability',
    'crypto_rsi_scanner.event_cache',
    'crypto_rsi_scanner.event_alpha_explain',
    'crypto_rsi_scanner.event_alpha_quality_fields',
    'crypto_rsi_scanner.event_alpha_outcomes',
    'crypto_rsi_scanner.event_alpha_eval',
    'crypto_rsi_scanner.event_alpha_burn_in_checklist',
    'crypto_rsi_scanner.event_alpha_health_guard',
    'crypto_rsi_scanner.event_alpha_scheduler',
    'crypto_rsi_scanner.event_alpha_environment_doctor',
    'crypto_rsi_scanner.event_provider_status',
    'crypto_rsi_scanner.event_alpha_missed',
    'crypto_rsi_scanner.event_alpha_reason_text',
    'crypto_rsi_scanner.event_clock',
    'crypto_rsi_scanner.event_models',
)


def test_retained_old_shim_import_paths_resolve_to_canonical_modules():
    for old_path, new_path in RETAINED_OLD_SHIM_MODULES:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        old_exports = tuple(getattr(old_module, "__all__", ()))
        shared_exports = [
            name
            for name in old_exports
            if hasattr(new_module, name) and not (name.startswith("__") and name.endswith("__"))
        ]
        assert shared_exports, old_path
        name = shared_exports[0]
        assert getattr(old_module, name) is getattr(new_module, name)


def test_deleted_non_public_old_shim_import_paths_fail():
    for old_path in DELETED_OLD_SHIM_MODULES:
        sys.modules.pop(old_path, None)
        try:
            importlib.import_module(old_path)
        except ModuleNotFoundError as exc:
            assert exc.name == old_path
        else:  # pragma: no cover - failure path
            raise AssertionError(f"deleted shim unexpectedly imported: {old_path}")
