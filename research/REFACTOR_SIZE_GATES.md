# Refactor Size Gates

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-04T19:34:25.396744+00:00`
- gate_status: `pass`
- baseline_present: `true`
- files_over_limit_count: `8`
- v3_gate_status: `pending`
- v3_auto_accept_ready: `False`
- production_files_over_1200_lines: `15`
- production_size_gate_status: `pass`
- production_files_over_1500_lines: `0`
- production_files_over_2000_lines: `0`
- production_files_over_3000_lines: `0`
- production_classes_over_limit: `14`
- production_functions_over_limit: `1`
- test_size_gate_status: `warning`
- test_files_over_1500_lines: `8`
- classes_over_limit_count: `14`
- functions_over_limit_count: `1`
- accepted_class_exceptions_count: `14`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_count: `82`
- modules_with_multiple_public_classes_status: `documented_advisory`
- new_violation_count: `0`
- moved_existing_violation_count: `15`
- legacy_decomposition_gate_status: `pass`
- legacy_files_over_1500_lines: `0`
- legacy_files_over_3000_lines: `0`
- legacy_total_lines: `4721`
- legacy_classes_over_limit: `3`
- legacy_functions_over_limit: `0`
- legacy_modules_with_multiple_public_classes: `2`

## Policy

- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.
- New file/function/class/module ownership violations are blockers.
- Refactor v3 targets production files below 1,200 lines.
- Refactor v3 treats production files over 1,500 lines as blockers unless explicitly accepted.
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

## Refactor V3 Gates

| gate | value | severity |
|---|---:|---|
| `nonessential_shims_remaining` | 0 | blocker |
| `old_path_internal_imports` | 0 | blocker |
| `old_path_test_imports` | 0 | blocker |
| `public_compatibility_shims` | 9 | informational |
| `shim_removal_blockers` | 0 | blocker |
| `deleted_shims` | 115 | informational |
| `production_files_over_1200_lines` | 15 | target_gap |
| `production_files_over_1500_lines` | 0 | blocker |
| `public_classes_not_in_own_module` | 82 | blocker |
| `class_exceptions_remaining` | 14 | blocker_until_reaccepted_for_v3 |
| `functions_over_150_lines` | 1 | blocker |
| `old_path_docs_references` | 0 | blocker_unless_policy_scoped |
| `old_path_import_allowed_exceptions` | 19 | informational |

## Moved Existing Violations

| current id | baseline id |
|---|---|
| `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store` |
| `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models` | `public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox.models` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox` |
| `public_classes:crypto_rsi_scanner.event_alpha.notifications.legacy.delivery_models` | `public_classes:crypto_rsi_scanner.event_alpha.notifications.pipeline_legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality.models` | `public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers` | `public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.core.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.core.legacy_store` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.legacy_acquisition` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.incidents.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.incidents` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.validation.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.validation.legacy` |
| `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.models` | `public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.legacy` |

## Legacy Decomposition Gate

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 905 |
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
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py` | 1498 |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1498 |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1487 |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1473 |
| `crypto_rsi_scanner/cli/services/legacy/utility_commands.py` | 1440 |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 |
| `crypto_rsi_scanner/cli/services/legacy/config_reports.py` | 1392 |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 |
| `crypto_rsi_scanner/config.py` | 1319 |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 |
| `crypto_rsi_scanner/event_alpha/notifications/legacy/plan_builder.py` | 1261 |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1239 |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1233 |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1223 |
| `crypto_rsi_scanner/event_fade.py` | 1181 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 1155 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py` | 1145 |
| `crypto_rsi_scanner/refactor_final_report.py` | 1145 |
| `crypto_rsi_scanner/event_alpha/radar/market_confirmation.py` | 1135 |
| `crypto_rsi_scanner/cli/services/legacy/rsi_scan.py` | 1103 |
| `crypto_rsi_scanner/event_alpha/providers/dex_onchain_readiness.py` | 1078 |
| `crypto_rsi_scanner/event_alpha/notifications/delivery.py` | 1069 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1059 |
| `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py` | 1047 |
| `crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py` | 1044 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py` | 1035 |
| `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py` | 1033 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py` | 1032 |
| `crypto_rsi_scanner/event_alpha/radar/llm/extractor.py` | 1002 |
| `crypto_rsi_scanner/event_alpha/radar/scheduled_catalysts.py` | 995 |
| `crypto_rsi_scanner/event_alpha/providers/source_registry.py` | 989 |
| `crypto_rsi_scanner/event_alpha/artifacts/alerts.py` | 987 |
| `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypothesis_store.py` | 980 |
| `crypto_rsi_scanner/event_alpha/radar/incident_graph.py` | 976 |
| `crypto_rsi_scanner/event_alpha/radar/core_opportunities.py` | 973 |
| `crypto_rsi_scanner/event_alpha/radar/evidence/executor.py` | 966 |
| `crypto_rsi_scanner/cli/services/legacy/reports.py` | 961 |
| `crypto_rsi_scanner/event_alpha/radar/identity.py` | 941 |

## Largest Test Files

| path | lines |
|---|---:|
| `tests/event_alpha/test_integrated_radar.py` | 16184 |
| `tests/event_alpha/test_provider_readiness.py` | 5357 |
| `tests/event_alpha/test_notifications.py` | 5002 |
| `tests/event_alpha/test_outcomes.py` | 4031 |
| `tests/event_alpha/test_artifact_doctor.py` | 3995 |
| `tests/event_alpha/test_source_coverage.py` | 2991 |
| `tests/event_alpha/test_namespace_lifecycle.py` | 1826 |
| `tests/test_indicators.py` | 1778 |
| `tests/cli/test_make_targets.py` | 1085 |
| `tests/event_alpha/_legacy_helpers.py` | 825 |
| `tests/event_alpha/test_artifact_schema.py` | 728 |
| `tests/rsi/test_indicators_core.py` | 694 |
| `tests/rsi/test_backtest.py` | 561 |
| `tests/rsi/test_paper_risk.py` | 379 |
| `tests/event_alpha/test_shim_registry.py` | 245 |
| `tests/cli/test_parser.py` | 243 |
| `tests/event_alpha/test_legacy_import_compatibility.py` | 170 |
| `tests/cli/test_event_alpha_command_registry.py` | 163 |
| `tests/cli/test_dispatch.py` | 129 |
| `tests/rsi/_legacy_helpers.py` | 68 |
| `tests/event_alpha/conftest.py` | 30 |
| `tests/conftest.py` | 13 |
| `tests/__init__.py` | 1 |
| `tests/cli/__init__.py` | 1 |
| `tests/event_alpha/__init__.py` | 1 |
| `tests/rsi/__init__.py` | 1 |

## Files Over 1500 Lines

| path | lines |
|---|---:|
| `tests/event_alpha/test_artifact_doctor.py` | 3995 |
| `tests/event_alpha/test_integrated_radar.py` | 16184 |
| `tests/event_alpha/test_namespace_lifecycle.py` | 1826 |
| `tests/event_alpha/test_notifications.py` | 5002 |
| `tests/event_alpha/test_outcomes.py` | 4031 |
| `tests/event_alpha/test_provider_readiness.py` | 5357 |
| `tests/event_alpha/test_source_coverage.py` | 2991 |
| `tests/test_indicators.py` | 1778 |

## Existing Violations

| category | id | lines/count |
|---|---|---:|
| `file_over_1500_lines` | `file:tests/event_alpha/test_artifact_doctor.py` | 3995 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_integrated_radar.py` | 16184 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_namespace_lifecycle.py` | 1826 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_notifications.py` | 5002 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_outcomes.py` | 4031 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_provider_readiness.py` | 5357 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_source_coverage.py` | 2991 |
| `file_over_1500_lines` | `file:tests/test_indicators.py` | 1778 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/client.py:CoinGeckoClient` | 115 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/asset_registry.py:CanonicalAsset` | 96 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_alpha/radar/watchlist_market.py:CoinGeckoWatchlistMarketProvider` | 116 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/binance_announcements/legacy.py:BinanceAnnouncementProvider` | 107 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/bybit_announcements/legacy.py:BybitAnnouncementProvider` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/cryptopanic/legacy.py:CryptoPanicProvider` | 340 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/gdelt.py:GdeltProvider` | 82 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/prediction_market_events.py:PredictionMarketEventsProvider` | 83 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/event_providers/project_blog_rss.py:ProjectBlogRssProvider` | 96 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/llm_providers/openai_provider.py:OpenAILLMRelationshipProvider` | 137 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/llm_providers/openai_provider.py:OpenAILLMExtractionProvider` | 78 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/migrations.py:MigrationsMixin` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/signals.py:SignalsMixin` | 129 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/watchlist.py:WatchlistMixin` | 89 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/refactor_final_report.py:build_refactor_final_report` | 157 |
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
| `public_classes_sharing_module` | `public_classes:crypto_rsi_scanner.event_alpha.shims` | 3 |
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
