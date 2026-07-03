# Refactor Final Report

Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-03T14:43:56+00:00`
- gate_status: `blocked`
- compatibility_preserved: `True`
- old_module_paths_removed: `0`

## Runtime Measurements

- standalone_runner_runtime_seconds: `11.191`
- pytest_runtime_seconds: `11.538`
- note: Runtimes are measured verification values supplied by the operator; null means not measured during report generation.

## Size Gates

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 90 | 13283 | 99.33% | <2000 | `pass` |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | `pass` |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | `pass` |

## Organization Counts

- top_level_event_module_count: `125`
- active_shims: `124`
- partial_shims: `0`
- unmigrated_modules: `1`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `29`
- scanner_bind_scanner_globals_call_sites: `7`
- cli_service_bind_scanner_globals_call_sites: `6`
- cli_event_alpha_service_lines: `46`
- scanner_legacy_service_lines: `120`
- parser_build_parser_lines: `25`
- commands_event_alpha_handle_lines: `2`
- legacy_artifact_doctor_core_lines: `95`
- legacy_artifact_doctor_core_note: Behavior-compatible doctor implementation preserved while public artifact_doctor.py is the small orchestrator.
- large_event_alpha_split_line_counts: `{"core_opportunity_store_legacy": 2607, "core_opportunity_store_wrapper": 14, "daily_brief_legacy": 85, "daily_brief_wrapper": 32, "evidence_acquisition_legacy": 2045, "evidence_acquisition_wrapper": 14, "impact_hypotheses_legacy": 3758, "impact_hypotheses_wrapper": 14, "integrated_radar_legacy": 83, "integrated_radar_wrapper": 32, "notifications_pipeline_legacy": 104, "notifications_pipeline_wrapper": 49, "research_cards_legacy": 88, "research_cards_wrapper": 14}`
- cli_flag_snapshot_path: `research/CLI_FLAG_SNAPSHOT.json`
- scanner_command_body_functions_remaining: `0`
- remaining_implementation_modules_by_package_target: `{}`
- intentionally_outside_event_alpha_modules: `["crypto_rsi_scanner.event_fade"]`
- class_ownership_report: `research/REFACTOR_CLASS_OWNERSHIP_REPORT.json`
- class_ownership_classes_over_limit: `31`
- class_ownership_functions_over_limit: `64`
- legacy_decomposition_gate_status: `blocked`
- legacy_files_over_1500_lines: `7`
- legacy_files_over_3000_lines: `1`
- legacy_total_lines: `22652`
- legacy_classes_over_limit: `8`
- legacy_functions_over_limit: `17`
- legacy_modules_with_multiple_public_classes: `8`

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

## Legacy Decomposition Gate

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py` | 3758 |
| `crypto_rsi_scanner/event_alpha/radar/validation/legacy.py` | 2821 |
| `crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py` | 2607 |
| `crypto_rsi_scanner/backtest_parts/legacy.py` | 2174 |
| `crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py` | 2045 |
| `crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py` | 1887 |
| `crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py` | 1828 |
| `crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py` | 1341 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 888 |
| `crypto_rsi_scanner/event_alpha/providers/provider_health_legacy.py` | 769 |
| `crypto_rsi_scanner/derivatives_providers/coinalyze/legacy.py` | 533 |
| `crypto_rsi_scanner/event_providers/binance_announcements/legacy.py` | 192 |
| `crypto_rsi_scanner/refactor_legacy_inventory.py` | 190 |
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 |
| `crypto_rsi_scanner/event_providers/bybit_announcements/legacy.py` | 111 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py` | 104 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 95 |
| `crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py` | 88 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py` | 85 |

## Doctor Plugin Migration

- legacy_unregistered: `0`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `pass`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "secrets": 0, "source_coverage": 1, "stale_artifacts": 1}`
- migrated_this_run: `29`

### Remaining Legacy-Unregistered Doctor Sites

| check | next plugin | reason |
|---|---|---|
| none | none | none |

## Namespace And CI

- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`
- ci_static_safety: `pass`
- test_runtime_report_path: `research/test_runtime_report.json`

## Blockers

### `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py`

- blocker_reason: Legacy implementation core remains over 3,000 lines; wrappers are not enough to mark the refactor complete.
- next_migration_module: `focused legacy decomposition modules for this file`
- risk: Moving too much at once can change CLI, doctor, notification, card, brief, or radar semantics.

## Compatibility And Code Removal

- dead_duplicate_code_removed: `False`
- note: No obviously dead duplicate top-level Event Alpha code was removed in this pass; old module paths remain available until shim reports and import tests prove retirement is safe.

## Deprecation Plan

| phase | status | policy |
|---|---|---|
| `v1` | `current` | Old top-level Event Alpha imports remain active compatibility shims; new work imports new package paths. |
| `v2` | `future` | Old imports may warn in development mode only after old/new import tests, Make targets, and operator docs prove compatibility. |
| `v3` | `future` | Old imports can be removed only through an explicit compatibility-breaking migration with full verification and release notes. |

## Safety Snapshot

- research_only: `True`
- no_send_rehearsal: `True`
- live_provider_calls_allowed: `False`
- telegram_sends: `0`
- trades_created: `0`
- paper_trades_created: `0`
- normal_rsi_signal_rows_written: `0`
- triggered_fade_created: `0`
