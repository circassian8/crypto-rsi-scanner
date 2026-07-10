# Architecture Final Report

Research-only architecture gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-10T05:11:37+00:00`
- gate_status: `pass`
- compatibility_preserved: `True`
- old_module_paths_removed: `124`
- removed_shims_count: `124`
- retained_public_shims_count: `0`
- shim_dependency_report_cache_status: `miss`
- shim_dependency_include_runtime_artifacts: `False`
- shim_dependency_scan_duration_seconds: `1.1823`
- shim_dependency_skipped_artifact_files: `1486`
- shim_dependency_skipped_large_files: `1`
- v3_gate_status: `accepted_with_documented_exceptions`
- v3_auto_accept_ready: `False`

## Runtime Measurements

- standalone_runner_runtime_seconds: `11.191`
- pytest_runtime_seconds: `11.538`
- note: Runtimes are measured verification values supplied by the operator; null means not measured during report generation.

## Size Gates

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 90 | 90 | 0 | 0.0% | <2000 | `pass` |
| `tests/test_indicators.py` | 1665 | 1665 | 0 | 0.0% | <2000 | `pass` |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py` | 36 | 36 | 0 | 0.0% | <300 | `pass` |

## Organization Counts

- top_level_event_module_count: `1`
- active_shims: `0`
- partial_shims: `0`
- unmigrated_modules: `1`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `29`
- scanner_bind_scanner_globals_call_sites: `6`
- cli_service_bind_scanner_globals_call_sites: `5`
- cli_event_alpha_service_lines: `46`
- scanner_api_service_lines: `120`
- parser_build_parser_lines: `25`
- commands_event_alpha_handle_lines: `2`
- api_artifact_doctor_core_lines: `91`
- api_artifact_doctor_core_note: `Behavior-compatible doctor implementation preserved while public artifact_doctor.py is the small orchestrator.`
- large_event_alpha_split_line_counts: `{"core_opportunity_store_api": 50, "core_opportunity_store_wrapper": 14, "daily_brief_api": 82, "daily_brief_wrapper": 32, "evidence_acquisition_api": 50, "evidence_acquisition_wrapper": 14, "impact_hypotheses_api": 59, "impact_hypotheses_wrapper": 14, "integrated_radar_api": 86, "integrated_radar_wrapper": 32, "notifications_pipeline_core": 104, "notifications_pipeline_wrapper": 49, "research_cards_api": 85, "research_cards_wrapper": 14}`
- cli_flag_snapshot_path: `research/CLI_FLAG_SNAPSHOT.json`
- scanner_command_body_functions_remaining: `0`
- remaining_implementation_modules_by_package_target: `{}`
- intentionally_outside_event_alpha_modules: `["crypto_rsi_scanner.event_fade"]`
- class_ownership_report: `research/ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json`
- class_ownership_classes_over_limit: `3`
- class_ownership_functions_over_limit: `0`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- production_size_gate_status: `warning`
- production_files_over_1200_lines: `12`
- accepted_production_files_over_1200_lines: `12`
- unresolved_production_files_over_1200_lines: `0`
- production_files_over_1500_lines: `0`
- production_files_over_2000_lines: `0`
- production_files_over_3000_lines: `0`
- production_classes_over_limit: `3`
- production_functions_over_limit: `0`
- test_size_gate_status: `warning`
- test_files_over_1500_lines: `8`
- api_decomposition_gate_status: `pass`
- transitional_file_status: `OK`
- transitional_named_files_count: `0`
- transitional_named_files_remaining: `0`
- transitional_named_files_with_implementation: `0`
- transitional_named_dirs_count: `0`
- compatibility_named_files_remaining: `0`
- transitional_top_level_event_modules_count: `0`
- transitional_retained_public_shims_count: `0`
- retained_public_entrypoints: `0`
- event_fade_safety_exception_present: `True`
- scanner_entrypoint_exception_present: `True`
- public_compatibility_entrypoints_path: `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json`
- api_files_over_1500_lines: `0`
- api_files_over_3000_lines: `0`
- api_total_lines: `0`
- api_classes_over_limit: `0`
- api_functions_over_limit: `0`
- api_modules_with_multiple_public_classes: `0`

## Architecture V3 Finalization Gates

- v3_contract_path: `research/ARCHITECTURE_CONTRACT.md`
- v3_gate_status: `accepted_with_documented_exceptions`
- v3_auto_accept_ready: `False`
- v3_blockers: `[]`
- v3_accepted_exception_categories: `["class_exceptions_remaining", "production_files_over_1200_lines"]`

| gate | value | severity |
|---|---:|---|
| `nonessential_shims_remaining` | 0 | blocker |
| `old_path_internal_imports` | 0 | blocker |
| `old_path_test_imports` | 0 | blocker |
| `public_compatibility_shims` | 0 | informational |
| `shim_removal_blockers` | 0 | blocker |
| `deleted_shims` | 124 | informational |
| `production_files_over_1200_lines` | 12 | accepted_exception |
| `production_files_over_1500_lines` | 0 | blocker |
| `public_classes_not_in_own_module` | 0 | blocker |
| `class_exceptions_remaining` | 3 | accepted_exception |
| `functions_over_150_lines` | 0 | blocker |
| `old_path_docs_references` | 0 | blocker_unless_policy_scoped |
| `old_path_import_allowed_exceptions` | 0 | informational |

## Newly Migrated Modules

- `crypto_rsi_scanner.event_incident_graph`
- `crypto_rsi_scanner.event_identity`
- `crypto_rsi_scanner.event_graph`
- `crypto_rsi_scanner.event_resolver`
- `crypto_rsi_scanner.event_price_history`
- `crypto_rsi_scanner.event_catalyst_frame_validator`
- `crypto_rsi_scanner.event_anomaly_state`
- `crypto_rsi_scanner.event_anomaly_scanner`
- `crypto_rsi_scanner.event_market_units`
- `crypto_rsi_scanner.event_llm_budget`
- `crypto_rsi_scanner.event_llm_catalyst_frames_eval`
- `crypto_rsi_scanner.event_source_reliability`
- `crypto_rsi_scanner.event_cache`
- `crypto_rsi_scanner.event_alpha_explain`
- `crypto_rsi_scanner.event_alpha_quality_fields`
- `crypto_rsi_scanner.event_alpha_outcomes`
- `crypto_rsi_scanner.event_alpha_eval`
- `crypto_rsi_scanner.event_alpha_burn_in_checklist`
- `crypto_rsi_scanner.event_alpha_profiles`
- `crypto_rsi_scanner.event_alpha_v1_readiness`
- `crypto_rsi_scanner.event_alpha_preflight`
- `crypto_rsi_scanner.event_alpha_health_guard`
- `crypto_rsi_scanner.event_alpha_scheduler`
- `crypto_rsi_scanner.event_alpha_environment_doctor`
- `crypto_rsi_scanner.event_provider_status`
- `crypto_rsi_scanner.event_alpha_missed`
- `crypto_rsi_scanner.event_alpha_reason_text`
- `crypto_rsi_scanner.event_clock`
- `crypto_rsi_scanner.event_models`

## Production Size Gate

| path | lines |
|---|---:|
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1472 |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1431 |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1392 |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 |
| `crypto_rsi_scanner/config.py` | 1352 |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1239 |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1233 |
| `crypto_rsi_scanner/event_fade.py` | 1181 |
| `crypto_rsi_scanner/event_alpha/operations/daily_burn_in.py` | 1159 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 1155 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/builder.py` | 1145 |
| `crypto_rsi_scanner/event_alpha/operations/review_inbox.py` | 1138 |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1136 |
| `crypto_rsi_scanner/event_alpha/radar/market_confirmation.py` | 1135 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/registry.py` | 1126 |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/context_loading.py` | 1125 |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1123 |
| `crypto_rsi_scanner/cli/services/scanner_parts/rsi_scan.py` | 1103 |
| `crypto_rsi_scanner/cli/services/scanner_parts/utility_commands.py` | 1078 |
| `crypto_rsi_scanner/event_alpha/providers/dex_onchain_readiness.py` | 1078 |
| `crypto_rsi_scanner/event_alpha/notifications/delivery.py` | 1069 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1059 |
| `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py` | 1047 |
| `crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py` | 1044 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py` | 1035 |
| `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py` | 1033 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/merge_policy.py` | 1016 |
| `crypto_rsi_scanner/event_alpha/radar/llm/extractor.py` | 1002 |
| `crypto_rsi_scanner/event_alpha/radar/scheduled_catalysts.py` | 995 |
| `crypto_rsi_scanner/event_alpha/providers/source_registry.py` | 989 |
| `crypto_rsi_scanner/event_alpha/artifacts/alerts.py` | 987 |
| `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypothesis_store.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/incident_graph.py` | 976 |
| `crypto_rsi_scanner/event_alpha/radar/core_opportunities.py` | 973 |

## Accepted Production Files Over 1200 Lines

| path | lines | reason | revisit |
|---|---:|---|---|
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1472 | Static architecture report aggregator preserving compatibility aliases and existing gate counters. | Split when adding a new architecture report family or when report schema v2 removes historical aliases. |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1431 | Static deleted-shim/tombstone registry and report writer; large by design and non-behavioral. | When deleted-shim reporting can be split from old-import linting without changing gate output. |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 | Dense operator audit renderer with many cross-section helper dependencies. | When audit sections are split with golden Markdown fixture comparison. |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 | Verdict scoring and live-confirmation policy share many ordered caps and guardrails. | When verdict snapshots cover each opportunity level and cap reason. |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1392 | Historical CLI report compatibility binder with broad scanner-service monkeypatch expectations. | When config/report command bodies move to focused service modules. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | Route-gate decision logic is dense and behavior-critical for no-send notification eligibility. | When route-decision/gate snapshots cover every lane and quality-gate cap. |
| `crypto_rsi_scanner/config.py` | 1352 | Central environment/config contract; splitting risks import-time default and env-var behavior drift. | When a dedicated config-v2 migration freeze and env snapshot tests exist. |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 | Stable argparse flag bundle; splitting individual flag groups risks CLI default drift. | Next parser feature addition or when event-alpha flag groups can be snapshot-tested per submodule. |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 | Provider/cache enrichment flow is stable and below blocker threshold. | When adding a new enrichment source or cache policy. |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 | Legacy notification-plan compatibility core; no-send semantics are more important than churn. | When notification plan rows are covered by schema-level golden fixtures. |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1239 | Deterministic derivatives crowding evaluator with tightly coupled fixture smoke coverage. | When adding a new derivatives metric family or crowding class. |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1233 | Outcome maturation/report code is stable and below the blocker threshold. | When outcome performance views gain new sections. |

## Unresolved Production Files Over 1200 Lines

| path | lines |
|---|---:|
| none | 0 |

## Test Size Gate

| path | lines |
|---|---:|
| `tests/event_alpha/test_integrated_radar.py` | 6421 |
| `tests/event_alpha/test_provider_readiness.py` | 5379 |
| `tests/event_alpha/test_notifications.py` | 5002 |
| `tests/event_alpha/test_outcomes.py` | 4082 |
| `tests/event_alpha/test_artifact_doctor.py` | 4052 |
| `tests/event_alpha/test_source_coverage.py` | 2991 |
| `tests/event_alpha/test_namespace_lifecycle.py` | 1826 |
| `tests/test_indicators.py` | 1665 |
| `tests/event_alpha/test_burn_in_operations.py` | 1477 |
| `tests/event_alpha/test_market_surfaces.py` | 1450 |
| `tests/cli/test_make_targets.py` | 1407 |
| `tests/event_alpha/test_fade_review_workflows.py` | 1309 |
| `tests/event_alpha/test_core_opportunities.py` | 1282 |
| `tests/event_alpha/test_catalyst_frames.py` | 1127 |
| `tests/event_alpha/test_fade_validation.py` | 1081 |
| `tests/event_alpha/test_llm_radar.py` | 942 |
| `tests/event_alpha/test_claim_semantics.py` | 867 |
| `tests/event_alpha/test_artifact_schema.py` | 850 |
| `tests/event_alpha/_api_helpers.py` | 825 |
| `tests/event_alpha/test_core_reconciliation.py` | 786 |
| `tests/rsi/test_indicators_core.py` | 735 |
| `tests/event_alpha/test_incident_relevance.py` | 639 |
| `tests/rsi/test_backtest.py` | 562 |
| `tests/event_alpha/test_shim_registry.py` | 515 |
| `tests/rsi/test_paper_risk.py` | 466 |
| `tests/event_alpha/test_operator_identity.py` | 461 |
| `tests/event_alpha/test_burn_in_candidate_mode.py` | 376 |
| `tests/cli/test_parser.py` | 308 |
| `tests/rsi/test_security.py` | 224 |
| `tests/cli/test_event_alpha_command_registry.py` | 202 |
| `tests/rsi/test_backups.py` | 171 |
| `tests/cli/test_dispatch.py` | 169 |
| `tests/cli/test_dependency_ci.py` | 152 |
| `tests/cli/test_burn_in_make_targets.py` | 122 |
| `tests/event_alpha/test_integrated_merge_policy.py` | 115 |
| `tests/cli/test_event_alpha_operator_command_smoke.py` | 103 |
| `tests/cli/test_relative_import_integrity.py` | 88 |
| `tests/event_alpha/test_burn_in_contract_hermeticity.py` | 83 |
| `tests/cli/test_ops_command_smoke.py` | 76 |
| `tests/rsi/_api_helpers.py` | 68 |

## Class Ownership Cleanup

- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- multi_public_class_modules_count: `80`
- accepted_model_bundles_count: `79`
- unresolved_multi_class_modules_count: `0`
- modules_with_multiple_public_classes_revisit_condition: Register tiny model bundles explicitly or split behaviorful public classes before adding new multi-class production modules.

### Provider Class Split Status

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `BinanceAnnouncementProvider` | `crypto_rsi_scanner.event_providers.binance_announcements.provider` | 14 | below_threshold |  |
| `BybitAnnouncementProvider` | `crypto_rsi_scanner.event_providers.bybit_announcements.provider` | 14 | below_threshold |  |
| `CoinGeckoWatchlistMarketProvider` | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 30 | below_threshold | Revisit when watchlist market enrichment gains another provider implementation. |
| `CoinalyzeDerivativesProvider` | `crypto_rsi_scanner.derivatives_providers.coinalyze.core` | 54 | below_threshold |  |
| `CryptoPanicProvider` | `crypto_rsi_scanner.event_providers.cryptopanic.provider` | 29 | below_threshold |  |
| `GdeltProvider` | `crypto_rsi_scanner.event_providers.gdelt` | 14 | below_threshold | Revisit when adding a second GDELT mode or durable request ledger. |
| `OpenAILLMExtractionProvider` | `crypto_rsi_scanner.llm_providers.openai_extraction` | 28 | below_threshold |  |
| `OpenAILLMRelationshipProvider` | `crypto_rsi_scanner.llm_providers.openai_relationship` | 34 | below_threshold |  |
| `PredictionMarketEventsProvider` | `crypto_rsi_scanner.event_providers.prediction_market_events` | 14 | below_threshold | Revisit when Polymarket Gamma support grows beyond the current parser. |
| `ProjectBlogRssProvider` | `crypto_rsi_scanner.event_providers.project_blog_rss` | 11 | below_threshold | Revisit when project-blog sources get persistent request ledgers or richer feed classes. |

### Storage Mixin Exception Status

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `MigrationsMixin` | `crypto_rsi_scanner.storage_parts.migrations` | 88 | accepted_exception | Revisit only with explicit migration tests and backup/restore verification. |
| `SignalsMixin` | `crypto_rsi_scanner.storage_parts.signals` | 129 | accepted_exception | Revisit when storage schema v2 or a repository layer is introduced. |
| `WatchlistMixin` | `crypto_rsi_scanner.storage_parts.watchlist` | 89 | accepted_exception | Revisit when watchlist storage grows new tables or migrations. |

### Near-Threshold Production Files

| path | lines | status | revisit condition |
|---|---:|---|---|
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1472 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1431 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1392 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/config.py` | 1352 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |

## API Decomposition Gate

| path | lines |
|---|---:|

## Doctor Plugin Migration

- api_unregistered: `0`
- api_unregistered_target: `5`
- api_unregistered_status: `pass`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "operations": 33, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "secrets": 0, "source_coverage": 1, "stale_artifacts": 1}`
- migrated_this_run: `29`

### Remaining Unregistered Doctor Sites

| check | next plugin | reason |
|---|---|---|
| none | none | none |

## Namespace And CI

- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_architecture_report": 1, "active_fixture_smoke": 20, "active_integrated_smoke": 1, "active_live_rehearsal": 13, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`
- ci_static_safety: `pass`
- test_runtime_report_path: `research/test_runtime_report.json`

## Blockers

- none
## Compatibility And Code Removal

- dead_duplicate_code_removed: `False`
- note: Non-public top-level Event Alpha shims listed in research/EVENT_ALPHA_DELETED_SHIMS.json were removed after shim dependency and old-import reports proved they were unused internally.

## Deprecation Plan

| phase | status | policy |
|---|---|---|
| `v3_public_compatibility` | `current` | No flat Event Alpha public compatibility shims remain; scanner.py remains the historical CLI entrypoint and new work imports canonical package paths. |
| `deleted_import_tombstones` | `current` | Deleted old Event Alpha imports are allowed to fail; docs show canonical paths and tombstone tests cover deleted paths. |
| `v4_dev_warning` | `future` | Any future public compatibility bridge may warn in development mode only after an accepted compatibility-breaking migration and release notes. |
| `v4_removal` | `future` | Any future public old import bridge can be removed only through an explicit compatibility-breaking migration with full verification and release notes. |

## Safety Snapshot

- research_only: `True`
- no_send_rehearsal: `True`
- live_provider_calls_allowed: `False`
- telegram_sends: `0`
- trades_created: `0`
- paper_trades_created: `0`
- normal_rsi_signal_rows_written: `0`
- triggered_fade_created: `0`
