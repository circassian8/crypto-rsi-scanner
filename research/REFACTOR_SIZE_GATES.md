# Refactor Size Gates

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-05T03:24:07.991319+00:00`
- gate_status: `pass`
- baseline_present: `true`
- files_over_limit_count: `8`
- v3_gate_status: `accepted_with_documented_exceptions`
- v3_auto_accept_ready: `False`
- v3_blockers: `[]`
- production_files_over_1200_lines: `12`
- accepted_production_files_over_1200_lines: `12`
- unresolved_production_files_over_1200_lines: `0`
- production_size_gate_status: `warning`
- production_files_over_1500_lines: `0`
- production_files_over_2000_lines: `0`
- production_files_over_3000_lines: `0`
- production_classes_over_limit: `3`
- production_functions_over_limit: `0`
- test_size_gate_status: `warning`
- test_files_over_1500_lines: `8`
- classes_over_limit_count: `3`
- functions_over_limit_count: `0`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- multi_public_class_modules_count: `80`
- accepted_model_bundles_count: `79`
- unresolved_multi_class_modules_count: `0`
- new_violation_count: `0`
- moved_existing_violation_count: `0`
- legacy_decomposition_gate_status: `pass`
- legacy_files_over_1500_lines: `0`
- legacy_files_over_3000_lines: `0`
- legacy_total_lines: `3553`
- legacy_classes_over_limit: `0`
- legacy_functions_over_limit: `0`
- legacy_modules_with_multiple_public_classes: `1`

## Policy

- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.
- New file/function/class/module ownership violations are blockers.
- Refactor v3 targets production files below 1,200 lines.
- Production files over 1,200 lines are warnings and must either be split or documented.
- Refactor v3 treats production files over 1,500 lines as blockers unless explicitly accepted.
- Production files over 1,500 lines block refactor-complete status unless explicitly accepted.
- Production files over 2,000 lines remain a legacy continuity threshold.
- Production files over 3,000 lines are blockers.
- Test file size debt is tracked separately and does not block production refactor completion.
- Legacy implementation files over 1,500 lines are warnings.
- Legacy implementation files over 3,000 lines block refactor-complete status.
- New production modules with multiple public classes are blockers unless registered as accepted model bundles.
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
| `production_files_over_1200_lines` | 12 | accepted_exception |
| `production_files_over_1500_lines` | 0 | blocker |
| `public_classes_not_in_own_module` | 0 | blocker |
| `class_exceptions_remaining` | 3 | accepted_exception |
| `functions_over_150_lines` | 0 | blocker |
| `old_path_docs_references` | 0 | blocker_unless_policy_scoped |
| `old_path_import_allowed_exceptions` | 19 | informational |

## Moved Existing Violations

| current id | baseline id |
|---|---|

## Legacy Decomposition Gate

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_alpha/providers/provider_health_legacy.py` | 779 |
| `crypto_rsi_scanner/derivatives_providers/coinalyze/legacy.py` | 629 |
| `crypto_rsi_scanner/refactor_legacy_inventory.py` | 190 |
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 |
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
| `crypto_rsi_scanner/backtest_parts/legacy.py` | 44 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 16 |
| `crypto_rsi_scanner/event_providers/binance_announcements/legacy.py` | 12 |

## Largest Production Files

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py` | 1498 |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1436 |
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
| `crypto_rsi_scanner/refactor_final_report.py` | 1199 |
| `crypto_rsi_scanner/event_fade.py` | 1181 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 1155 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py` | 1145 |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1136 |
| `crypto_rsi_scanner/event_alpha/radar/market_confirmation.py` | 1135 |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1123 |
| `crypto_rsi_scanner/cli/services/legacy/rsi_scan.py` | 1103 |
| `crypto_rsi_scanner/cli/services/legacy/utility_commands.py` | 1096 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py` | 1079 |
| `crypto_rsi_scanner/event_alpha/providers/dex_onchain_readiness.py` | 1078 |
| `crypto_rsi_scanner/event_alpha/notifications/delivery.py` | 1069 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1059 |
| `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py` | 1047 |
| `crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py` | 1044 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py` | 1035 |
| `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py` | 1033 |
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

## Accepted Production Files Over 1200 Lines

| path | lines | reason | revisit |
|---|---:|---|---|
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py` | 1498 | Integrated radar merge policy is behavior-critical and close to the blocker threshold but unchanged. | When identity/source/market/derivatives merge golden fixtures can be compared before and after split. |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1436 | Static shim registry/data table; large by design and non-behavioral. | When another shim retirement pass removes retained public compatibility entries. |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 | Dense operator audit renderer with many cross-section helper dependencies. | When audit sections are split with golden Markdown fixture comparison. |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 | Verdict scoring and live-confirmation policy share many ordered caps and guardrails. | When verdict snapshots cover each opportunity level and cap reason. |
| `crypto_rsi_scanner/cli/services/legacy/config_reports.py` | 1392 | Legacy CLI report compatibility binder with broad scanner-service monkeypatch expectations. | When config/report command bodies move to canonical non-legacy service modules. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | Route-gate decision logic is dense and behavior-critical for no-send notification eligibility. | When route-decision/gate snapshots cover every lane and quality-gate cap. |
| `crypto_rsi_scanner/config.py` | 1319 | Central environment/config contract; splitting risks import-time default and env-var behavior drift. | When a dedicated config-v2 migration freeze and env snapshot tests exist. |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 | Provider/cache enrichment flow is stable and below blocker threshold. | When adding a new enrichment source or cache policy. |
| `crypto_rsi_scanner/event_alpha/notifications/legacy/plan_builder.py` | 1261 | Legacy notification-plan compatibility core; no-send semantics are more important than churn. | When notification plan rows are covered by schema-level golden fixtures. |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1239 | Deterministic derivatives crowding evaluator with tightly coupled fixture smoke coverage. | When adding a new derivatives metric family or crowding class. |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1233 | Outcome maturation/report code is stable and below the blocker threshold. | When outcome performance views gain new sections. |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1223 | Stable argparse flag bundle; splitting individual flag groups risks CLI default drift. | Next parser feature addition or when event-alpha flag groups can be snapshot-tested per submodule. |

## Unresolved Production Files Over 1200 Lines

| path | lines |
|---|---:|
| none | 0 |

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
| `tests/cli/test_make_targets.py` | 1225 |
| `tests/event_alpha/_legacy_helpers.py` | 825 |
| `tests/event_alpha/test_artifact_schema.py` | 743 |
| `tests/rsi/test_indicators_core.py` | 694 |
| `tests/rsi/test_backtest.py` | 561 |
| `tests/event_alpha/test_shim_registry.py` | 509 |
| `tests/rsi/test_paper_risk.py` | 379 |
| `tests/cli/test_parser.py` | 243 |
| `tests/event_alpha/test_legacy_import_compatibility.py` | 170 |
| `tests/cli/test_event_alpha_command_registry.py` | 163 |
| `tests/cli/test_dispatch.py` | 129 |
| `tests/cli/test_relative_import_integrity.py` | 88 |
| `tests/cli/test_ops_command_smoke.py` | 76 |
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
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/migrations.py:MigrationsMixin` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/signals.py:SignalsMixin` | 129 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/watchlist.py:WatchlistMixin` | 89 |
