# Event Alpha Shim Dependency Report

Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-04T17:06:49.096644+00:00
- status: OK
- registry_entry_count: 124
- internal_import_reference_count: 0
- test_import_reference_count: 127
- makefile_reference_count: 8
- docs_reference_count: 128
- dynamic_import_reference_count: 0
- safe_to_remove_count: 0
- active_shim_modules_with_implementation_logic: 0

## Policy

- New implementation code must import new package paths, not old top-level Event Alpha shim paths.
- Old shims stay available during v1/v2 compatibility and may be removed only after zero internal references and an accepted removal release.
- `scanner.py` may remain a compatibility CLI entrypoint.
- `event_fade.py` remains intentionally outside Event Alpha; Event Alpha may write `FADE_SHORT_REVIEW` research but must not create `TRIGGERED_FADE`.

## Registry Dependencies

| old module | new module | status | internal | tests | make | docs | dynamic | safe | action |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner.event_integrated_radar` | `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_state` | `crypto_rsi_scanner.event_alpha.radar.market_state` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_reaction` | `crypto_rsi_scanner.event_alpha.radar.market_reaction` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_core_opportunities` | `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_core_opportunity_store` | `crypto_rsi_scanner.event_alpha.radar.core_opportunity_store` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_evidence_acquisition` | `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_source_coverage` | `crypto_rsi_scanner.event_alpha.radar.source_coverage` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_opportunity_verdict` | `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_impact_hypotheses` | `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_impact_hypothesis_store` | `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_incident_store` | `crypto_rsi_scanner.event_alpha.radar.incidents` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_research_cards` | `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_daily_brief` | `crypto_rsi_scanner.event_alpha.artifacts.daily_brief` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_opportunity_audit` | `crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | active_shim | 0 | 1 | 0 | 3 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_namespace_status` | `crypto_rsi_scanner.event_alpha.namespace.status` | active_shim | 0 | 0 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notifications` | `crypto_rsi_scanner.event_alpha.notifications.pipeline` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_delivery` | `crypto_rsi_scanner.event_alpha.notifications.delivery` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_sender` | `crypto_rsi_scanner.event_alpha.notifications.sender` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_runs` | `crypto_rsi_scanner.event_alpha.notifications.runs` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_go_no_go` | `crypto_rsi_scanner.event_alpha.notifications.go_no_go` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_checklist` | `crypto_rsi_scanner.event_alpha.notifications.checklist` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_inbox` | `crypto_rsi_scanner.event_alpha.notifications.inbox` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_pack` | `crypto_rsi_scanner.event_alpha.notifications.pack` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_pause` | `crypto_rsi_scanner.event_alpha.notifications.pause` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_notification_slo` | `crypto_rsi_scanner.event_alpha.notifications.slo` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_send_readiness` | `crypto_rsi_scanner.event_alpha.notifications.readiness` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_telegram_final_check` | `crypto_rsi_scanner.event_alpha.notifications.final_check` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_telegram_recipient_check` | `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_integrated_radar_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_calibration` | `crypto_rsi_scanner.event_alpha.outcomes.calibration` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_eval_export` | `crypto_rsi_scanner.event_alpha.outcomes.feedback` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_feedback_readiness` | `crypto_rsi_scanner.event_alpha.outcomes.feedback` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_burn_in` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_burn_in_readiness` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_burn_in_pack` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_quality_review` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_quality_coverage` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_signal_quality` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_signal_quality_export` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_tuning` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_priors` | `crypto_rsi_scanner.event_alpha.outcomes.priors` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_policy_simulator` | `crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_cryptopanic` | `crypto_rsi_scanner.event_alpha.providers.cryptopanic` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_official_exchange` | `crypto_rsi_scanner.event_alpha.providers.official_exchange` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_official_exchange_activation` | `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_coinalyze_preflight` | `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_live_provider_readiness` | `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_provider_health` | `crypto_rsi_scanner.event_alpha.providers.provider_health` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_source_registry` | `crypto_rsi_scanner.event_alpha.providers.source_registry` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_source_packs` | `crypto_rsi_scanner.event_alpha.providers.source_packs` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_bybit_announcements_preflight` | `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_unlock_calendar_preflight` | `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_dex_onchain_readiness` | `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_derivatives_crowding` | `crypto_rsi_scanner.event_alpha.radar.derivatives_crowding` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_scheduled_catalysts` | `crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_asset_registry` | `crypto_rsi_scanner.event_alpha.radar.asset_registry` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_instrument_resolver` | `crypto_rsi_scanner.event_alpha.radar.instrument_resolver` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_confirmation` | `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_catalyst_search` | `crypto_rsi_scanner.event_alpha.radar.catalyst_search` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_source_enrichment` | `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_validation` | `crypto_rsi_scanner.event_alpha.radar.validation` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_discovery` | `crypto_rsi_scanner.event_alpha.radar.discovery` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_near_miss` | `crypto_rsi_scanner.event_alpha.radar.near_miss` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_classification` | `crypto_rsi_scanner.event_alpha.radar.classification` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_catalyst_frames` | `crypto_rsi_scanner.event_alpha.radar.catalyst_frames` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_claim_semantics` | `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_playbooks` | `crypto_rsi_scanner.event_alpha.radar.playbooks` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_impact_path_validator` | `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_evidence_quality` | `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_enrichment` | `crypto_rsi_scanner.event_alpha.radar.market_enrichment` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_extractor` | `crypto_rsi_scanner.event_alpha.radar.llm.extractor` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_analyzer` | `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_evidence_planner` | `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_catalyst_frames` | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_extract_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.extract_eval` | active_shim | 0 | 2 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_llm_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.eval` | active_shim | 0 | 2 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_llm_models` | `crypto_rsi_scanner.event_alpha.radar.llm.models` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_extraction_models` | `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_alert_store` | `crypto_rsi_scanner.event_alpha.artifacts.alert_store` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alerts` | `crypto_rsi_scanner.event_alpha.artifacts.alerts` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_router` | `crypto_rsi_scanner.event_alpha.notifications.router` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_pipeline` | `crypto_rsi_scanner.event_alpha.radar.pipeline` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_watchlist` | `crypto_rsi_scanner.event_alpha.radar.watchlist` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_watchlist_monitor` | `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_watchlist_enrichment` | `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_watchlist_market` | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_replay` | `crypto_rsi_scanner.event_alpha.artifacts.replay` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_feedback` | `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_incident_graph` | `crypto_rsi_scanner.event_alpha.radar.incident_graph` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_identity` | `crypto_rsi_scanner.event_alpha.radar.identity` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_graph` | `crypto_rsi_scanner.event_alpha.radar.graph` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_resolver` | `crypto_rsi_scanner.event_alpha.radar.resolver` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_price_history` | `crypto_rsi_scanner.event_alpha.radar.price_history` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_anomaly_state` | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_units` | `crypto_rsi_scanner.event_alpha.radar.market_units` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_budget` | `crypto_rsi_scanner.event_alpha.radar.llm.budget` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` | active_shim | 0 | 1 | 5 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_source_reliability` | `crypto_rsi_scanner.event_alpha.providers.source_reliability` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_cache` | `crypto_rsi_scanner.event_alpha.artifacts.cache` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_explain` | `crypto_rsi_scanner.event_alpha.artifacts.explain` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_quality_fields` | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_eval` | `crypto_rsi_scanner.event_alpha.outcomes.eval` | active_shim | 0 | 1 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_health_guard` | `crypto_rsi_scanner.event_alpha.config.health_guard` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_scheduler` | `crypto_rsi_scanner.event_alpha.config.scheduler` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | `crypto_rsi_scanner.event_alpha.doctor.environment` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_provider_status` | `crypto_rsi_scanner.event_alpha.notifications.provider_status` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_missed` | `crypto_rsi_scanner.event_alpha.radar.missed` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_reason_text` | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_clock` | `crypto_rsi_scanner.event_core.clock` | active_shim | 0 | 3 | 0 | 2 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_models` | `crypto_rsi_scanner.event_core.models` | active_shim | 0 | 3 | 0 | 2 | 0 | false | keep_until_v3 |

## Warnings

- none
