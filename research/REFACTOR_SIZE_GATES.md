# Refactor Size Gates

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-04T03:29:01.048453+00:00`
- gate_status: `pass`
- baseline_present: `true`
- files_over_limit_count: `8`
- production_size_gate_status: `pass`
- production_files_over_1500_lines: `0`
- production_files_over_2000_lines: `0`
- production_files_over_3000_lines: `0`
- production_classes_over_limit: `22`
- production_functions_over_limit: `49`
- test_size_gate_status: `warning`
- test_files_over_1500_lines: `8`
- classes_over_limit_count: `22`
- functions_over_limit_count: `49`
- modules_with_multiple_public_classes_count: `82`
- new_violation_count: `0`
- moved_existing_violation_count: `52`
- legacy_decomposition_gate_status: `pass`
- legacy_files_over_1500_lines: `0`
- legacy_files_over_3000_lines: `0`
- legacy_total_lines: `4704`
- legacy_classes_over_limit: `3`
- legacy_functions_over_limit: `1`
- legacy_modules_with_multiple_public_classes: `2`

## Policy

- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.
- New file/function/class/module ownership violations are blockers.
- Production files over 1,500 lines are warnings.
- Production files over 2,000 lines block refactor-complete status unless explicitly exempted.
- Production files over 3,000 lines are blockers.
- Test file size debt is tracked separately and does not block production refactor completion.
- Legacy implementation files over 1,500 lines are warnings.
- Legacy implementation files over 3,000 lines block refactor-complete status.
- Baseline updates require the explicit `make refactor-size-baseline-update` target.

## New Violations

| category | id | lines/count |
|---|---|---:|

## Moved Existing Violations

| current id | baseline id |
|---|---|
| `class:crypto_rsi_scanner/event_alpha/doctor/legacy/result_models.py:EventAlphaArtifactDoctorResult` | `class:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:EventAlphaArtifactDoctorResult` |
| `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:EventProviderCatalystSearchProvider` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:EventProviderCatalystSearchProvider` |
| `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:FixtureCatalystSearchProvider` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:FixtureCatalystSearchProvider` |
| `class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/models.py:EventImpactHypothesis` | `class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:EventImpactHypothesis` |
| `class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/models.py:EventIntegratedRadarResult` | `class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:EventIntegratedRadarResult` |
| `class:crypto_rsi_scanner/event_alpha/radar/source_coverage/models.py:EventAlphaSourceCoverageReport` | `class:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:EventAlphaSourceCoverageReport` |
| `class:crypto_rsi_scanner/event_alpha/radar/watchlist/models.py:EventWatchlistEntry` | `class:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:EventWatchlistEntry` |
| `function:crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py:_event_alpha_notify_cycle_body` | `function:crypto_rsi_scanner/cli/services/event_alpha_notifications.py:_event_alpha_notify_cycle_body` |
| `function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py:build_daily_brief` | `function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py:build_daily_brief` |
| `function:crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py:diagnose_artifacts` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:diagnose_artifacts` |
| `function:crypto_rsi_scanner/event_alpha/doctor/legacy/notification_delivery_checks.py:_notification_delivery_conflicts` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_notification_delivery_conflicts` |
| `function:crypto_rsi_scanner/event_alpha/doctor/legacy/provider_readiness_checks.py:_integrated_radar_artifact_conflicts` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_integrated_radar_artifact_conflicts` |
| `function:crypto_rsi_scanner/event_alpha/doctor/legacy/reporting.py:format_artifact_doctor_report` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:format_artifact_doctor_report` |
| `function:crypto_rsi_scanner/event_alpha/notifications/inbox/builder.py:build_notification_inbox` | `function:crypto_rsi_scanner/event_alpha/notifications/inbox.py:build_notification_inbox` |
| `function:crypto_rsi_scanner/event_alpha/notifications/legacy/preview_writer.py:write_notification_plan_preview` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:write_notification_plan_preview` |
| `function:crypto_rsi_scanner/event_alpha/notifications/legacy/research_review_selection.py:select_research_review_candidates_with_diagnostics` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:select_research_review_candidates_with_diagnostics` |
| `function:crypto_rsi_scanner/event_alpha/notifications/legacy/send_plan.py:send_notifications` | `function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:send_notifications` |
| `function:crypto_rsi_scanner/event_alpha/outcomes/quality/case_eval.py:evaluate_signal_quality_case` | `function:crypto_rsi_scanner/event_alpha/outcomes/quality.py:evaluate_signal_quality_case` |
| `function:crypto_rsi_scanner/event_alpha/radar/core/serialization.py:_row_from_core_opportunity` | `function:crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py:_row_from_core_opportunity` |
| `function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:load_discovery_events` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:load_discovery_events` |
| `function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:run_manual_discovery` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:run_manual_discovery` |
| `function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_execute_request` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_execute_request` |
| `function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_validate_raw_result` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_validate_raw_result` |
| `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/builder.py:_hypothesis_from_rule` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:_hypothesis_from_rule` |
| `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/generation.py:validate_hypotheses_with_raw_events` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:validate_hypotheses_with_raw_events` |
| `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/report.py:format_impact_hypothesis_report` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:format_impact_hypothesis_report` |
| `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/cycle.py:run_integrated_radar_cycle` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:run_integrated_radar_cycle` |
| `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py:_merge_family` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:_merge_family` |
| `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/report.py:format_integrated_daily_brief` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:format_integrated_daily_brief` |
| `function:crypto_rsi_scanner/event_alpha/radar/near_miss/candidates.py:_candidate_from_row` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_candidate_from_row` |
| `function:crypto_rsi_scanner/event_alpha/radar/near_miss/refresh.py:_refresh_one_hypothesis` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_refresh_one_hypothesis` |
| `function:crypto_rsi_scanner/event_alpha/radar/source_coverage/builder.py:build_source_coverage_report` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:build_source_coverage_report` |
| `function:crypto_rsi_scanner/event_alpha/radar/source_coverage/provider_status.py:format_source_coverage_report` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:format_source_coverage_report` |
| `function:crypto_rsi_scanner/event_alpha/radar/validation/review.py:review_validation_sample` | `function:crypto_rsi_scanner/event_alpha/radar/validation/legacy.py:review_validation_sample` |
| `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_alert` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_alert` |
| `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_hypothesis` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_hypothesis` |
| `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_row` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_row` |
| `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store` |
| `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox.models` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox` |

## Legacy Decomposition Gate

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 888 |
| `crypto_rsi_scanner/event_alpha/providers/provider_health_legacy.py` | 779 |
| `crypto_rsi_scanner/derivatives_providers/coinalyze/legacy.py` | 629 |
| `crypto_rsi_scanner/event_providers/binance_announcements/legacy.py` | 192 |
| `crypto_rsi_scanner/refactor_legacy_inventory.py` | 190 |
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 |
| `crypto_rsi_scanner/event_providers/bybit_announcements/legacy.py` | 111 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py` | 104 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 95 |
| `crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py` | 88 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py` | 85 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py` | 83 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py` | 59 |
| `crypto_rsi_scanner/event_alpha/radar/validation/legacy.py` | 54 |
| `crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py` | 52 |
| `crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py` | 48 |

## Largest Production Files

| path | lines |
|---|---:|
| `crypto_rsi_scanner/cli/services/legacy/utility_commands.py` | 1440 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py` | 1428 |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1413 |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1400 |
| `crypto_rsi_scanner/cli/services/legacy/config_reports.py` | 1392 |
| `crypto_rsi_scanner/config.py` | 1319 |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1267 |
| `crypto_rsi_scanner/event_alpha/notifications/legacy/plan_builder.py` | 1261 |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1249 |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1247 |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1233 |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1222 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py` | 1203 |
| `crypto_rsi_scanner/event_fade.py` | 1181 |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1171 |
| `crypto_rsi_scanner/cli/services/legacy/rsi_scan.py` | 1103 |
| `crypto_rsi_scanner/event_alpha/providers/dex_onchain_readiness.py` | 1078 |
| `crypto_rsi_scanner/event_alpha/notifications/delivery.py` | 1069 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1059 |
| `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py` | 1033 |
| `crypto_rsi_scanner/event_alpha/radar/llm/extractor.py` | 1002 |
| `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py` | 997 |
| `crypto_rsi_scanner/event_alpha/radar/scheduled_catalysts.py` | 995 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 994 |
| `crypto_rsi_scanner/event_alpha/artifacts/alerts.py` | 985 |
| `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypothesis_store.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/incident_graph.py` | 975 |
| `crypto_rsi_scanner/event_alpha/radar/core_opportunities.py` | 970 |
| `crypto_rsi_scanner/cli/services/legacy/reports.py` | 961 |
| `crypto_rsi_scanner/refactor_final_report.py` | 951 |
| `crypto_rsi_scanner/event_alpha/providers/source_registry.py` | 941 |
| `crypto_rsi_scanner/event_alpha/radar/identity.py` | 941 |
| `crypto_rsi_scanner/event_alpha/config/profiles.py` | 935 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_alpha/radar/market_confirmation.py` | 924 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py` | 918 |
| `crypto_rsi_scanner/event_alpha/providers/official_exchange.py` | 913 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 888 |

## Largest Test Files

| path | lines |
|---|---:|
| `tests/event_alpha/test_integrated_radar.py` | 16084 |
| `tests/event_alpha/test_provider_readiness.py` | 5373 |
| `tests/event_alpha/test_notifications.py` | 5037 |
| `tests/event_alpha/test_outcomes.py` | 4041 |
| `tests/event_alpha/test_artifact_doctor.py` | 3981 |
| `tests/event_alpha/test_source_coverage.py` | 2988 |
| `tests/event_alpha/test_namespace_lifecycle.py` | 1813 |
| `tests/test_indicators.py` | 1771 |
| `tests/cli/test_make_targets.py` | 1014 |
| `tests/event_alpha/_legacy_helpers.py` | 819 |
| `tests/event_alpha/test_artifact_schema.py` | 734 |
| `tests/rsi/test_indicators_core.py` | 694 |
| `tests/rsi/test_backtest.py` | 561 |
| `tests/rsi/test_paper_risk.py` | 379 |
| `tests/cli/test_parser.py` | 243 |
| `tests/event_alpha/test_shim_registry.py` | 204 |
| `tests/cli/test_event_alpha_command_registry.py` | 163 |
| `tests/cli/test_dispatch.py` | 129 |
| `tests/rsi/_legacy_helpers.py` | 67 |
| `tests/event_alpha/conftest.py` | 30 |
| `tests/conftest.py` | 13 |
| `tests/__init__.py` | 1 |
| `tests/cli/__init__.py` | 1 |
| `tests/event_alpha/__init__.py` | 1 |
| `tests/rsi/__init__.py` | 1 |

## Files Over 1500 Lines

| path | lines |
|---|---:|
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
| `file_over_1500_lines` | `file:tests/event_alpha/test_artifact_doctor.py` | 3981 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_integrated_radar.py` | 16084 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_namespace_lifecycle.py` | 1813 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_notifications.py` | 5037 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_outcomes.py` | 4041 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_provider_readiness.py` | 5373 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_source_coverage.py` | 2988 |
| `file_over_1500_lines` | `file:tests/test_indicators.py` | 1771 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/client.py:CoinGeckoClient` | 115 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/doctor/legacy/result_models.py:EventAlphaArtifactDoctorResult` | 402 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/asset_registry.py:CanonicalAsset` | 96 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:FixtureCatalystSearchProvider` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:EventProviderCatalystSearchProvider` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/models.py:EventImpactHypothesis` | 191 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/models.py:EventIntegratedRadarResult` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/pipeline.py:EventAlphaPipelineResult` | 245 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/source_coverage/models.py:EventAlphaSourceCoverageReport` | 143 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/watchlist/models.py:EventWatchlistEntry` | 85 |
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
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py:_event_alpha_notify_cycle_body` | 513 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/cli/services/event_alpha_research.py:event_alpha_cycle` | 251 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py:build_daily_brief` | 884 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py:format_opportunity_audit` | 227 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py:diagnose_artifacts` | 1335 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy/notification_delivery_checks.py:_notification_delivery_conflicts` | 251 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy/provider_readiness_checks.py:_integrated_radar_artifact_conflicts` | 218 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/doctor/legacy/reporting.py:format_artifact_doctor_report` | 462 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/go_no_go.py:build_go_no_go` | 159 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/inbox/builder.py:build_notification_inbox` | 186 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/legacy/preview_writer.py:write_notification_plan_preview` | 190 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/legacy/research_review_selection.py:select_research_review_candidates_with_diagnostics` | 156 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/legacy/send_plan.py:send_notifications` | 406 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/provider_status.py:build_event_discovery_provider_status` | 229 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/readiness.py:build_send_readiness` | 193 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/notifications/router.py:_route_entry` | 220 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/outcomes/quality/case_eval.py:evaluate_signal_quality_case` | 211 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py:run_no_send_rehearsal` | 160 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py:run_no_send_rehearsal` | 194 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/source_registry.py:source_descriptor_for` | 246 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/providers/source_registry.py:assess_source` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/core/serialization.py:_row_from_core_opportunity` | 406 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py:normalize_derivatives_state` | 166 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:run_manual_discovery` | 244 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:load_discovery_events` | 183 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_execute_request` | 167 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_validate_raw_result` | 170 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/builder.py:_hypothesis_from_rule` | 199 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/generation.py:validate_hypotheses_with_raw_events` | 152 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/report.py:format_impact_hypothesis_report` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py:validate_impact_path` | 181 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py:_classify_path` | 271 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/cycle.py:run_integrated_radar_cycle` | 288 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py:_merge_family` | 245 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/report.py:format_integrated_daily_brief` | 154 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/market_confirmation.py:evaluate_market_confirmation` | 281 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/candidates.py:_candidate_from_row` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/near_miss/refresh.py:_refresh_one_hypothesis` | 276 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py:evaluate_opportunity` | 245 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/pipeline.py:run_event_alpha_pipeline` | 244 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/pipeline.py:run_event_alpha_operating_cycle` | 347 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage/builder.py:build_source_coverage_report` | 238 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/source_coverage/provider_status.py:format_source_coverage_report` | 200 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/validation/review.py:review_validation_sample` | 280 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_alert` | 199 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_hypothesis` | 352 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_row` | 164 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_providers/cryptopanic/legacy.py:CryptoPanicProvider._fetch_live_events` | 158 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/refactor_final_report.py:build_refactor_final_report` | 223 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.backups` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.config.health_guard` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.doctor.environment` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox.models` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.legacy.delivery_models` | 6 |
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
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality.models` | 9 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.provider_health_legacy` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.models` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers` | 8 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.core.models` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.models` | 7 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.graph` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.identity` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.incidents.models` | 4 |
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
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.models` | 4 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.pipeline` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.price_history` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage.models` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.validation.models` | 10 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.models` | 5 |
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
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.ops` | 5 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.refactor_class_ownership_report` | 2 |
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.signal_registry` | 2 |
