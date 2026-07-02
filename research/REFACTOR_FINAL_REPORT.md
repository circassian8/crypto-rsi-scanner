# Refactor Final Report

Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-02T18:02:08+00:00`
- gate_status: `blocked`
- compatibility_preserved: `True`
- old_module_paths_removed: `0`

## Runtime Measurements

- standalone_runner_runtime_seconds: `10.761`
- pytest_runtime_seconds: `11.25`
- note: Runtimes are measured verification values supplied by the operator; null means not measured during report generation.

## Size Gates

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <8000 | `pass` |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | `pass` |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | `pass` |

## Organization Counts

- top_level_event_module_count: `125`
- active_shims: `67`
- partial_shims: `0`
- unmigrated_modules: `58`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `11`
- scanner_bind_scanner_globals_call_sites: `7`
- scanner_command_body_functions_remaining: `105`

## Doctor Plugin Migration

- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- plugin_check_counts: `{"integrated_radar": 0, "namespace": 0, "notifications": 0, "outcomes": 0, "paths": 0, "provider_readiness": 0, "safety": 0, "source_coverage": 0, "stale_artifacts": 0}`
- migrated_this_run: `11`

## Namespace And CI

- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`
- ci_static_safety: `pass`
- test_runtime_report_path: `research/test_runtime_report.json`

## Blockers

### `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`

- blocker_reason: legacy_unregistered doctor append sites remain above the requested <=5 target.
- next_migration_module: `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py`
- risk: Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.

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
