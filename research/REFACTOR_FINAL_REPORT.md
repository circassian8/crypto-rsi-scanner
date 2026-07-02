# Refactor Final Report

Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-02T18:39:16+00:00`
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
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <6500 | `blocked` |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | `pass` |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | `pass` |

## Organization Counts

- top_level_event_module_count: `125`
- active_shims: `95`
- partial_shims: `0`
- unmigrated_modules: `30`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `28`
- scanner_bind_scanner_globals_call_sites: `7`
- cli_service_bind_scanner_globals_call_sites: `26`
- cli_event_alpha_service_lines: `3938`
- scanner_command_body_functions_remaining: `105`
- remaining_implementation_modules_by_package_target: `{"artifacts": 3, "config": 5, "doctor": 1, "notifications": 1, "outcomes": 4, "providers": 1, "radar": 9, "radar_llm": 2, "shared_event_infra": 2, "shared_radar_infra": 1}`
- intentionally_outside_event_alpha_modules: `["crypto_rsi_scanner.event_fade"]`

## Newly Migrated Modules

- `crypto_rsi_scanner.event_validation`
- `crypto_rsi_scanner.event_discovery`
- `crypto_rsi_scanner.event_near_miss`
- `crypto_rsi_scanner.event_classification`
- `crypto_rsi_scanner.event_catalyst_frames`
- `crypto_rsi_scanner.event_claim_semantics`
- `crypto_rsi_scanner.event_playbooks`
- `crypto_rsi_scanner.event_impact_path_validator`
- `crypto_rsi_scanner.event_evidence_quality`
- `crypto_rsi_scanner.event_market_enrichment`
- `crypto_rsi_scanner.event_llm_extractor`
- `crypto_rsi_scanner.event_llm_analyzer`
- `crypto_rsi_scanner.event_llm_evidence_planner`
- `crypto_rsi_scanner.event_llm_catalyst_frames`
- `crypto_rsi_scanner.event_llm_extract_eval`
- `crypto_rsi_scanner.event_llm_eval`
- `crypto_rsi_scanner.event_llm_models`
- `crypto_rsi_scanner.event_llm_extraction_models`
- `crypto_rsi_scanner.event_alpha_alert_store`
- `crypto_rsi_scanner.event_alerts`
- `crypto_rsi_scanner.event_alpha_router`
- `crypto_rsi_scanner.event_alpha_pipeline`
- `crypto_rsi_scanner.event_watchlist`
- `crypto_rsi_scanner.event_watchlist_monitor`
- `crypto_rsi_scanner.event_watchlist_enrichment`
- `crypto_rsi_scanner.event_watchlist_market`
- `crypto_rsi_scanner.event_alpha_replay`
- `crypto_rsi_scanner.event_feedback`

## Doctor Plugin Migration

- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "source_coverage": 1, "stale_artifacts": 1}`
- migrated_this_run: `28`

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

- blocker_reason: event_alpha CLI service remains above the requested <1500 split target.
- next_migration_module: `crypto_rsi_scanner/cli/services/event_alpha_notifications.py, event_alpha_integrated.py, provider_preflights.py, reports.py, namespace.py, and outcomes.py`
- risk: Splitting service bodies before replacing scanner-bound globals can change CLI dispatch behavior or provider/send guardrails.

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
