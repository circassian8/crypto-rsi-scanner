# Event Alpha Module Map

This map records the intended package home for existing top-level modules.
Top-level imports remain supported until a later migration removes shims.

## Shim Registry

`crypto_rsi_scanner.event_alpha.shims` is the checked-in shim registry and audit
tool. It reads this module map and emits one row per compatibility module with:

- `old_module`
- `new_module`
- `shim_status`
- `allowed_exports`

Statuses:

- `active_shim`: the old module is a compatibility wrapper only. It may contain
  a docstring, imports, `globals().update(...)`, `__all__`, and comments. New
  implementation logic belongs in the new package path.
- `partial_shim`: the old module is a known migration bridge and may still
  contain legacy implementation logic until a later phase.
- `not_migrated`: the module has not been moved yet and should not be judged by
  active-shim source rules.

Current phase:

- Mapped modules are `active_shim` unless a future row is explicitly marked as a
  temporary migration bridge in `crypto_rsi_scanner.event_alpha.shims`.
- `crypto_rsi_scanner.event_alpha_artifact_doctor` is now an active
  compatibility shim; the implementation lives in
  `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`.
- `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` is the small public
  orchestrator/export surface. Behavior-compatible legacy internals are
  preserved in `crypto_rsi_scanner.event_alpha.doctor.legacy_artifact_doctor`
  until individual checks are migrated into focused doctor plugins.
- Large internal Event Alpha modules now follow the same wrapper/core pattern:
  public wrappers remain at `notifications.pipeline`,
  `artifacts.research_cards`, `artifacts.daily_brief`,
  `radar.integrated_radar`, `radar.impact_hypotheses`,
  `radar.core_opportunity_store`, and `radar.evidence_acquisition`; behavior
  cores are preserved as `pipeline_legacy`, `research_cards.legacy`,
  `daily_brief.legacy`, `integrated.legacy`, `impact_hypotheses.legacy`,
  `core.legacy_store`, and `evidence.legacy_acquisition`.
- Medium radar and provider adapters now use package homes with compatibility
  cores: `radar.validation`, `radar.discovery`, `radar.watchlist`,
  `radar.near_miss`, `event_providers.cryptopanic`,
  `derivatives_providers.coinalyze`, `event_providers.bybit_announcements`,
  `event_providers.binance_announcements`, and `event_alpha.providers.health`.
  New logic should land in their focused `models`, `provider`, `client`,
  `parser`, `loader`, `entries`, `review`, or `report` modules rather than in
  the legacy cores.
- Shared refactor facades follow the same rule outside the top-level
  `event_*.py` shim registry: `storage.py` owns only the public `Storage`
  facade over `storage_parts/`, `backtest.py` owns the historical backtest
  facade over `backtest_parts/`, and `event_alpha/artifacts/schema_v1.py` owns
  compatibility exports over `event_alpha/artifacts/schema/`.

Run `make event-alpha-shim-report PYTHON=python3` to write
`event_alpha_shim_report.json` and `event_alpha_shim_report.md` under the
`shim_report` Event Alpha artifact namespace. Artifact doctor warns if an
`active_shim` module contains implementation logic.

| Compatibility module | Implementation package path | Layer |
|---|---|---|
| `crypto_rsi_scanner.event_integrated_radar` | `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | radar |
| `crypto_rsi_scanner.event_market_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | radar |
| `crypto_rsi_scanner.event_market_state` | `crypto_rsi_scanner.event_alpha.radar.market_state` | radar |
| `crypto_rsi_scanner.event_market_reaction` | `crypto_rsi_scanner.event_alpha.radar.market_reaction` | radar |
| `crypto_rsi_scanner.event_core_opportunities` | `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | radar |
| `crypto_rsi_scanner.event_core_opportunity_store` | `crypto_rsi_scanner.event_alpha.radar.core_opportunity_store` | radar |
| `crypto_rsi_scanner.event_evidence_acquisition` | `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | radar |
| `crypto_rsi_scanner.event_alpha_source_coverage` | `crypto_rsi_scanner.event_alpha.radar.source_coverage` | radar |
| `crypto_rsi_scanner.event_opportunity_verdict` | `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | radar |
| `crypto_rsi_scanner.event_impact_hypotheses` | `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | radar |
| `crypto_rsi_scanner.event_impact_hypothesis_store` | `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | radar |
| `crypto_rsi_scanner.event_incident_store` | `crypto_rsi_scanner.event_alpha.radar.incidents` | radar |
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | artifacts |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | artifacts |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | artifacts |
| `crypto_rsi_scanner.event_research_cards` | `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | artifacts |
| `crypto_rsi_scanner.event_alpha_daily_brief` | `crypto_rsi_scanner.event_alpha.artifacts.daily_brief` | artifacts |
| `crypto_rsi_scanner.event_opportunity_audit` | `crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit` | artifacts |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | doctor |
| `crypto_rsi_scanner.event_alpha_namespace_status` | `crypto_rsi_scanner.event_alpha.namespace.status` | namespace |
| `crypto_rsi_scanner.event_alpha_notifications` | `crypto_rsi_scanner.event_alpha.notifications.pipeline` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_delivery` | `crypto_rsi_scanner.event_alpha.notifications.delivery` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_sender` | `crypto_rsi_scanner.event_alpha.notifications.sender` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_runs` | `crypto_rsi_scanner.event_alpha.notifications.runs` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_go_no_go` | `crypto_rsi_scanner.event_alpha.notifications.go_no_go` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_checklist` | `crypto_rsi_scanner.event_alpha.notifications.checklist` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_inbox` | `crypto_rsi_scanner.event_alpha.notifications.inbox` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_pack` | `crypto_rsi_scanner.event_alpha.notifications.pack` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_pause` | `crypto_rsi_scanner.event_alpha.notifications.pause` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_slo` | `crypto_rsi_scanner.event_alpha.notifications.slo` | notifications |
| `crypto_rsi_scanner.event_alpha_send_readiness` | `crypto_rsi_scanner.event_alpha.notifications.readiness` | notifications |
| `crypto_rsi_scanner.event_alpha_telegram_final_check` | `crypto_rsi_scanner.event_alpha.notifications.final_check` | notifications |
| `crypto_rsi_scanner.event_alpha_telegram_recipient_check` | `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | notifications |
| `crypto_rsi_scanner.event_integrated_radar_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes` | outcomes |
| `crypto_rsi_scanner.event_alpha_calibration` | `crypto_rsi_scanner.event_alpha.outcomes.calibration` | outcomes |
| `crypto_rsi_scanner.event_alpha_eval_export` | `crypto_rsi_scanner.event_alpha.outcomes.feedback` | outcomes |
| `crypto_rsi_scanner.event_alpha_feedback_readiness` | `crypto_rsi_scanner.event_alpha.outcomes.feedback` | outcomes |
| `crypto_rsi_scanner.event_alpha_burn_in` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | outcomes |
| `crypto_rsi_scanner.event_alpha_burn_in_readiness` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | outcomes |
| `crypto_rsi_scanner.event_alpha_burn_in_pack` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | outcomes |
| `crypto_rsi_scanner.event_alpha_quality_review` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | outcomes |
| `crypto_rsi_scanner.event_alpha_quality_coverage` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | outcomes |
| `crypto_rsi_scanner.event_alpha_signal_quality` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | outcomes |
| `crypto_rsi_scanner.event_alpha_signal_quality_export` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | outcomes |
| `crypto_rsi_scanner.event_alpha_tuning` | `crypto_rsi_scanner.event_alpha.outcomes.quality` | outcomes |
| `crypto_rsi_scanner.event_alpha_priors` | `crypto_rsi_scanner.event_alpha.outcomes.priors` | outcomes |
| `crypto_rsi_scanner.event_alpha_policy_simulator` | `crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | outcomes |
| `crypto_rsi_scanner.event_alpha_cryptopanic` | `crypto_rsi_scanner.event_alpha.providers.cryptopanic` | providers |
| `crypto_rsi_scanner.event_official_exchange` | `crypto_rsi_scanner.event_alpha.providers.official_exchange` | providers |
| `crypto_rsi_scanner.event_official_exchange_activation` | `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | providers |
| `crypto_rsi_scanner.event_coinalyze_preflight` | `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | providers |
| `crypto_rsi_scanner.event_live_provider_readiness` | `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | providers |
| `crypto_rsi_scanner.event_provider_health` | `crypto_rsi_scanner.event_alpha.providers.provider_health` | providers |
| `crypto_rsi_scanner.event_source_registry` | `crypto_rsi_scanner.event_alpha.providers.source_registry` | providers |
| `crypto_rsi_scanner.event_source_packs` | `crypto_rsi_scanner.event_alpha.providers.source_packs` | providers |
| `crypto_rsi_scanner.event_bybit_announcements_preflight` | `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | providers |
| `crypto_rsi_scanner.event_unlock_calendar_preflight` | `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | providers |
| `crypto_rsi_scanner.event_dex_onchain_readiness` | `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | providers |
| `crypto_rsi_scanner.event_derivatives_crowding` | `crypto_rsi_scanner.event_alpha.radar.derivatives_crowding` | radar |
| `crypto_rsi_scanner.event_scheduled_catalysts` | `crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts` | radar |
| `crypto_rsi_scanner.event_asset_registry` | `crypto_rsi_scanner.event_alpha.radar.asset_registry` | radar |
| `crypto_rsi_scanner.event_instrument_resolver` | `crypto_rsi_scanner.event_alpha.radar.instrument_resolver` | radar |
| `crypto_rsi_scanner.event_market_confirmation` | `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | radar |
| `crypto_rsi_scanner.event_catalyst_search` | `crypto_rsi_scanner.event_alpha.radar.catalyst_search` | radar |
| `crypto_rsi_scanner.event_source_enrichment` | `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | radar |
| `crypto_rsi_scanner.event_validation` | `crypto_rsi_scanner.event_alpha.radar.validation` | radar |
| `crypto_rsi_scanner.event_discovery` | `crypto_rsi_scanner.event_alpha.radar.discovery` | radar |
| `crypto_rsi_scanner.event_near_miss` | `crypto_rsi_scanner.event_alpha.radar.near_miss` | radar |
| `crypto_rsi_scanner.event_classification` | `crypto_rsi_scanner.event_alpha.radar.classification` | radar |
| `crypto_rsi_scanner.event_catalyst_frames` | `crypto_rsi_scanner.event_alpha.radar.catalyst_frames` | radar |
| `crypto_rsi_scanner.event_claim_semantics` | `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | radar |
| `crypto_rsi_scanner.event_playbooks` | `crypto_rsi_scanner.event_alpha.radar.playbooks` | radar |
| `crypto_rsi_scanner.event_impact_path_validator` | `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | radar |
| `crypto_rsi_scanner.event_evidence_quality` | `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | radar |
| `crypto_rsi_scanner.event_market_enrichment` | `crypto_rsi_scanner.event_alpha.radar.market_enrichment` | radar |
| `crypto_rsi_scanner.event_llm_extractor` | `crypto_rsi_scanner.event_alpha.radar.llm.extractor` | radar_llm |
| `crypto_rsi_scanner.event_llm_analyzer` | `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | radar_llm |
| `crypto_rsi_scanner.event_llm_evidence_planner` | `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | radar_llm |
| `crypto_rsi_scanner.event_llm_catalyst_frames` | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | radar_llm |
| `crypto_rsi_scanner.event_llm_extract_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.extract_eval` | radar_llm |
| `crypto_rsi_scanner.event_llm_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.eval` | radar_llm |
| `crypto_rsi_scanner.event_llm_models` | `crypto_rsi_scanner.event_alpha.radar.llm.models` | radar_llm |
| `crypto_rsi_scanner.event_llm_extraction_models` | `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | radar_llm |
| `crypto_rsi_scanner.event_alpha_alert_store` | `crypto_rsi_scanner.event_alpha.artifacts.alert_store` | artifacts |
| `crypto_rsi_scanner.event_alerts` | `crypto_rsi_scanner.event_alpha.artifacts.alerts` | artifacts |
| `crypto_rsi_scanner.event_alpha_router` | `crypto_rsi_scanner.event_alpha.notifications.router` | notifications |
| `crypto_rsi_scanner.event_alpha_pipeline` | `crypto_rsi_scanner.event_alpha.radar.pipeline` | radar |
| `crypto_rsi_scanner.event_watchlist` | `crypto_rsi_scanner.event_alpha.radar.watchlist` | radar |
| `crypto_rsi_scanner.event_watchlist_monitor` | `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | notifications |
| `crypto_rsi_scanner.event_watchlist_enrichment` | `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | radar |
| `crypto_rsi_scanner.event_watchlist_market` | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | radar |
| `crypto_rsi_scanner.event_alpha_replay` | `crypto_rsi_scanner.event_alpha.artifacts.replay` | artifacts |
| `crypto_rsi_scanner.event_feedback` | `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | outcomes |
| `crypto_rsi_scanner.event_incident_graph` | `crypto_rsi_scanner.event_alpha.radar.incident_graph` | radar |
| `crypto_rsi_scanner.event_identity` | `crypto_rsi_scanner.event_alpha.radar.identity` | radar |
| `crypto_rsi_scanner.event_graph` | `crypto_rsi_scanner.event_alpha.radar.graph` | radar |
| `crypto_rsi_scanner.event_resolver` | `crypto_rsi_scanner.event_alpha.radar.resolver` | radar |
| `crypto_rsi_scanner.event_price_history` | `crypto_rsi_scanner.event_alpha.radar.price_history` | radar |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` | radar |
| `crypto_rsi_scanner.event_anomaly_state` | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | radar |
| `crypto_rsi_scanner.event_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` | radar |
| `crypto_rsi_scanner.event_market_units` | `crypto_rsi_scanner.event_alpha.radar.market_units` | radar |
| `crypto_rsi_scanner.event_llm_budget` | `crypto_rsi_scanner.event_alpha.radar.llm.budget` | radar_llm |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` | radar_llm |
| `crypto_rsi_scanner.event_source_reliability` | `crypto_rsi_scanner.event_alpha.providers.source_reliability` | providers |
| `crypto_rsi_scanner.event_cache` | `crypto_rsi_scanner.event_alpha.artifacts.cache` | artifacts |
| `crypto_rsi_scanner.event_alpha_explain` | `crypto_rsi_scanner.event_alpha.artifacts.explain` | artifacts |
| `crypto_rsi_scanner.event_alpha_quality_fields` | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` | outcomes |
| `crypto_rsi_scanner.event_alpha_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` | outcomes |
| `crypto_rsi_scanner.event_alpha_eval` | `crypto_rsi_scanner.event_alpha.outcomes.eval` | outcomes |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` | outcomes |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | config |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | config |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | config |
| `crypto_rsi_scanner.event_alpha_health_guard` | `crypto_rsi_scanner.event_alpha.config.health_guard` | config |
| `crypto_rsi_scanner.event_alpha_scheduler` | `crypto_rsi_scanner.event_alpha.config.scheduler` | config |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | `crypto_rsi_scanner.event_alpha.doctor.environment` | doctor |
| `crypto_rsi_scanner.event_provider_status` | `crypto_rsi_scanner.event_alpha.notifications.provider_status` | notifications |
| `crypto_rsi_scanner.event_alpha_missed` | `crypto_rsi_scanner.event_alpha.radar.missed` | radar |
| `crypto_rsi_scanner.event_alpha_reason_text` | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` | artifacts |
| `crypto_rsi_scanner.event_clock` | `crypto_rsi_scanner.event_core.clock` | event_core |
| `crypto_rsi_scanner.event_models` | `crypto_rsi_scanner.event_core.models` | event_core |
