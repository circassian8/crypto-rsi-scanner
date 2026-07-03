# Refactor Final Report

Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-03T01:56:36+00:00`
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
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <5500 | `blocked` |
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
- cli_service_bind_scanner_globals_call_sites: `26`
- cli_event_alpha_service_lines: `46`
- parser_build_parser_lines: `25`
- commands_event_alpha_handle_lines: `2`
- cli_flag_snapshot_path: `research/CLI_FLAG_SNAPSHOT.json`
- scanner_command_body_functions_remaining: `105`
- remaining_implementation_modules_by_package_target: `{}`
- intentionally_outside_event_alpha_modules: `["crypto_rsi_scanner.event_fade"]`
- class_ownership_report: `research/REFACTOR_CLASS_OWNERSHIP_REPORT.json`
- class_ownership_classes_over_limit: `29`
- class_ownership_functions_over_limit: `64`

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

## Doctor Plugin Migration

- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "source_coverage": 1, "stale_artifacts": 1}`
- migrated_this_run: `29`

### Remaining Legacy-Unregistered Doctor Sites

| check | next plugin | reason |
|---|---|---|
| `missing_operational_run_rows` | `namespace.py or stale_artifacts.py` | Run-row absence drives strict doctor status and needs fixture coverage before registry migration. |
| `snapshot_availability_lineage_warnings` | `integrated_radar.py` | Snapshot availability distinguishes fixture, external, stale, and strict operational rows. |
| `orphan_alert_snapshot_run_ids` | `integrated_radar.py` | Alert snapshot lineage counters are compatibility-sensitive in strict and non-strict modes. |
| `legacy_alert_snapshot_lineage` | `stale_artifacts.py` | Legacy rows are intentionally tolerated in some scopes and blocked in others. |
| `feedback_without_matching_alert_snapshot` | `outcomes.py` | Feedback lineage severity depends on strict mode and latest-run filtering. |
| `outcomes_without_matching_alert_snapshot` | `outcomes.py` | Outcome lineage severity depends on strict mode and legacy artifact scope. |
| `mixed_artifact_namespaces` | `namespace.py` | Namespace-mixing behavior must preserve strict blocker versus warning semantics. |
| `multiple_artifact_namespaces_present` | `namespace.py` | Multiple namespaces are tolerated in audit modes but not strict current-run checks. |
| `multiple_profiles_present` | `namespace.py` | Profile-mixing is currently warning-only and should stay compatible. |
| `provider_health_missing_for_live_profile` | `provider_readiness.py` | Provider health rows are required only for selected live/burn-in profile families. |
| `llm_budget_rows_missing_for_llm_profile` | `provider_readiness.py` | Budget telemetry is warning-only for LLM profiles and must not block no-key paths. |
| `invalid_canonical_incident_rows` | `integrated_radar.py` | Incident linkage counters are shared with integrated-radar/card consistency checks. |
| `alertable_run_external_snapshot_path` | `paths.py` | External snapshot paths are blockers for operational rows but allowed for some fixture rows. |
| `fixture_snapshot_external_allowed` | `paths.py` | Fixture external snapshot rows remain warning-only under current doctor semantics. |
| `snapshot_availability_unknown_or_missing` | `integrated_radar.py` | Unknown or missing snapshot availability depends on run_mode and strictness. |

## Namespace And CI

- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`
- ci_static_safety: `pass`
- test_runtime_report_path: `research/test_runtime_report.json`

## Blockers

### `crypto_rsi_scanner/scanner.py`

- blocker_reason: scanner.py still contains many historical Event Alpha command bodies and runtime config adapters that were only partially routed through cli/dispatch.py.
- next_migration_module: `crypto_rsi_scanner/cli/commands_event_alpha.py plus service modules for remaining scanner-bound command bodies`
- risk: Broad scanner command extraction can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.

### `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`

- blocker_reason: legacy_unregistered doctor append sites remain above the requested <=5 target.
- next_migration_module: `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py`
- risk: Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.

### `crypto_rsi_scanner/cli/services/event_alpha.py`

- blocker_reason: cli service bind_scanner_globals call sites were not reduced by the requested 50%.
- next_migration_module: `Replace scanner-global dependencies in the split Event Alpha service modules with explicit imports and focused dispatch monkeypatch tests.`
- risk: Removing the runtime binding too early can break historical helper/config resolution for Makefile-backed commands.

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
