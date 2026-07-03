# Refactor Size Gates

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-03T03:10:30.805060+00:00`
- gate_status: `pass`
- baseline_present: `true`
- files_over_limit_count: `27`
- classes_over_limit_count: `31`
- functions_over_limit_count: `64`
- modules_with_multiple_public_classes_count: `81`
- new_violation_count: `0`
- moved_existing_violation_count: `1`

## Policy

- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.
- New file/function/class/module ownership violations are blockers.
- Baseline updates require the explicit `make refactor-size-baseline-update` target.

## New Violations

| category | id | lines/count |
|---|---|---:|

## Moved Existing Violations

| current id | baseline id |
|---|---|
| `file:crypto_rsi_scanner/cli/services/scanner_legacy.py` | `file:crypto_rsi_scanner/scanner.py` |

## Files Over 1500 Lines

| path | lines |
|---|---:|
| `crypto_rsi_scanner/backtest_parts/legacy.py` | 2174 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` | 1709 |
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 7744 |
| `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` | 1630 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py` | 3080 |
| `crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py` | 3416 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 6363 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py` | 4326 |
| `crypto_rsi_scanner/event_alpha/outcomes/quality.py` | 2403 |
| `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` | 2009 |
| `crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py` | 2607 |
| `crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py` | 1887 |
| `crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py` | 2045 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py` | 3758 |
| `crypto_rsi_scanner/event_alpha/radar/incidents.py` | 1967 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py` | 3401 |
| `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` | 1538 |
| `crypto_rsi_scanner/event_alpha/radar/validation/legacy.py` | 2821 |
| `crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py` | 1828 |
| `tests/event_alpha/test_artifact_doctor.py` | 3981 |
| `tests/event_alpha/test_integrated_radar.py` | 16084 |
| `tests/event_alpha/test_namespace_lifecycle.py` | 1813 |
| `tests/event_alpha/test_notifications.py` | 5037 |
| `tests/event_alpha/test_outcomes.py` | 4041 |
| `tests/event_alpha/test_provider_readiness.py` | 5373 |
| `tests/event_alpha/test_source_coverage.py` | 2988 |
| `tests/test_indicators.py` | 1771 |

## Existing Violations

| category | id | lines/count |
|---|---|---:|
| `file_over_1500_lines` | `file:crypto_rsi_scanner/backtest_parts/legacy.py` | 2174 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/cli/services/event_alpha_notifications.py` | 1709 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/cli/services/scanner_legacy.py` | 7744 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` | 1630 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py` | 3080 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py` | 3416 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 6363 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py` | 4326 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/outcomes/quality.py` | 2403 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` | 2009 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py` | 2607 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py` | 1887 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py` | 2045 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py` | 3758 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/incidents.py` | 1967 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py` | 3401 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/source_coverage.py` | 1538 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/validation/legacy.py` | 2821 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py` | 1828 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_artifact_doctor.py` | 3981 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_integrated_radar.py` | 16084 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_namespace_lifecycle.py` | 1813 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_notifications.py` | 5037 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_outcomes.py` | 4041 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_provider_readiness.py` | 5373 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_source_coverage.py` | 2988 |
| `file_over_1500_lines` | `file:tests/test_indicators.py` | 1771 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/client.py:CoinGeckoClient` | 115 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/derivatives_providers/coinalyze/legacy.py:CoinalyzeDerivativesProvider` | 189 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:EventAlphaArtifactDoctorResult` | 402 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/notifications/delivery.py:NotificationDeliveryRecord` | 123 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:_DeliveryWriter` | 534 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py:BybitAnnouncementsRehearsalReport` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py:CoinalyzeRehearsalReport` | 102 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py:LiveProviderReadinessProvider` | 99 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/providers/provider_health_legacy.py:HealthCheckedEventProvider` | 78 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/asset_registry.py:CanonicalAsset` | 96 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:FixtureCatalystSearchProvider` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:EventProviderCatalystSearchProvider` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:EvidenceAcquisitionResult` | 120 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:EventImpactHypothesis` | 191 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:EventIntegratedRadarResult` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/llm/budget.py:EventLLMBudgetRunTracker` | 95 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/pipeline.py:EventAlphaPipelineResult` | 245 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:EventAlphaSourceCoverageReport` | 143 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:EventWatchlistEntry` | 85 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/watchlist_market.py:CoinGeckoWatchlistMarketProvider` | 116 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/binance_announcements/legacy.py:BinanceAnnouncementProvider` | 107 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/bybit_announcements/legacy.py:BybitAnnouncementProvider` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/cryptopanic/legacy.py:CryptoPanicProvider` | 372 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/gdelt.py:GdeltProvider` | 82 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/prediction_market_events.py:PredictionMarketEventsProvider` | 83 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/project_blog_rss.py:ProjectBlogRssProvider` | 96 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/llm_providers/openai_provider.py:OpenAILLMRelationshipProvider` | 137 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/llm_providers/openai_provider.py:OpenAILLMExtractionProvider` | 78 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/migrations.py:MigrationsMixin` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/signals.py:SignalsMixin` | 129 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/watchlist.py:WatchlistMixin` | 89 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/backtest_parts/legacy.py:walk_coin` | 153 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/backtest_parts/legacy.py:main` | 227 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/event_alpha_command_registry.py:dispatch_event_alpha_command` | 809 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/parser_event_alpha.py:add_event_alpha_args` | 1190 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_fade_review.py:_write_event_fade_review_bundle` | 164 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_notifications.py:_event_alpha_notify_cycle_body` | 513 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_notifications.py:event_alpha_notify_fixture_smoke` | 732 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_outcomes.py:event_alpha_export_burn_in_pack` | 159 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_research.py:event_alpha_cycle` | 251 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/alert_store.py:_snapshot_from_route_decision` | 168 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py:build_daily_brief` | 884 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/locks.py:acquire_run_lock` | 174 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py:format_opportunity_audit` | 227 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:render_research_card` | 220 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:_core_score_components` | 168 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:_impact_hypothesis_lines` | 223 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py:format_run_ledger_report` | 159 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py:_run_record` | 219 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:diagnose_artifacts` | 1335 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_integrated_radar_artifact_conflicts` | 218 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_notification_delivery_conflicts` | 251 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:format_artifact_doctor_report` | 462 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/go_no_go.py:build_go_no_go` | 159 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/inbox.py:build_notification_inbox` | 186 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:select_research_review_candidates_with_diagnostics` | 156 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:write_notification_plan_preview` | 190 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:send_notifications` | 406 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/provider_status.py:build_event_discovery_provider_status` | 229 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/readiness.py:build_send_readiness` | 193 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/router.py:_route_entry` | 220 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/outcomes/quality.py:evaluate_signal_quality_case` | 211 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py:run_no_send_rehearsal` | 160 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py:run_no_send_rehearsal` | 194 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py:_provider_rows` | 429 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/source_registry.py:source_descriptor_for` | 246 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/source_registry.py:assess_source` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py:_row_from_core_opportunity` | 406 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py:normalize_derivatives_state` | 166 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:run_manual_discovery` | 244 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:load_discovery_events` | 183 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_execute_request` | 167 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_validate_raw_result` | 170 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:validate_hypotheses_with_raw_events` | 152 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:format_impact_hypothesis_report` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:_hypothesis_from_rule` | 199 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py:validate_impact_path` | 181 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py:_classify_path` | 271 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:run_integrated_radar_cycle` | 288 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:format_integrated_daily_brief` | 154 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:_merge_family` | 245 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/market_confirmation.py:evaluate_market_confirmation` | 281 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_refresh_one_hypothesis` | 276 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_candidate_from_row` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py:evaluate_opportunity` | 245 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/pipeline.py:run_event_alpha_pipeline` | 244 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/pipeline.py:run_event_alpha_operating_cycle` | 347 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:build_source_coverage_report` | 238 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:format_source_coverage_report` | 200 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/validation/legacy.py:review_validation_sample` | 280 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_alert` | 199 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_hypothesis` | 352 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_row` | 164 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_providers/cryptopanic/legacy.py:CryptoPanicProvider._fetch_live_events` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/refactor_final_report.py:build_refactor_final_report` | 172 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.backups` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.config.health_guard` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.doctor.environment` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.pipeline_legacy` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.provider_status` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.recipient_check` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.router` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.runs` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.burn_in` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.feedback` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.priors` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality` | 9 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.provider_health_legacy` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search` | 15 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.core.legacy_store` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.legacy_acquisition` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.graph` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.identity` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.legacy` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.incidents` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.budget` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | 8 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.extractor` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.llm.models` | 8 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.market_confirmation` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.market_reaction` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.missed` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.legacy` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.pipeline` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.price_history` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.validation.legacy` | 10 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.legacy` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | 9 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.shims` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_core.models` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_fade` | 11 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_providers.base` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_providers.cryptopanic.legacy` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.llm_providers.base` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.llm_providers.fixture` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.llm_providers.openai_provider` | 2 |
