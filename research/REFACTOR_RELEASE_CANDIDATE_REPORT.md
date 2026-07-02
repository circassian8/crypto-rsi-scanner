# Refactor Release Candidate Report

- generated_at: `2026-07-02T18:39:48Z`
- status: `pending_with_documented_refactor_blockers`
- canonical_final_report: `research/REFACTOR_FINAL_REPORT.json`
- classification_report: `research/REMAINING_EVENT_MODULE_CLASSIFICATION.json`
- total_commands: `25`
- failed_commands: `0`

This is a research-only release-candidate report. The verification pass did not enable live provider calls, live Telegram sends, trading, paper trading, execution, normal RSI signal writes from Event Alpha, or Event Alpha-created `TRIGGERED_FADE`.

## Verification Results

| # | command | status | note |
|---:|---|---:|---|
| 1 | `python3 tests/test_indicators.py` | pass | 734/734 standalone tests |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py` | pass | 740/740 pytest tests |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | pass | source/test bytecode compile |
| 4 | `make test-pytest-safe PYTHON=python3` | pass | safe pytest target, external plugin autoload disabled |
| 5 | `make test-pytest-timed PYTHON=python3` | pass | wrote research/test_runtime_report.md/json |
| 6 | `make event-alpha-shim-report PYTHON=python3` | pass | active shim logic violations=0 |
| 7 | `make refactor-final-report PYTHON=python3` | pass | report generated with documented size/doctor blockers |
| 8 | `make event-alpha-namespace-lifecycle-report PYTHON=python3` | pass | unknown_namespace_count=0 |
| 9 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | pass | fixture smoke, no live calls |
| 10 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | pass | doctor OK |
| 11 | `make event-alpha-live-provider-readiness-smoke PYTHON=python3` | pass | live calls remain disabled |
| 12 | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | pass | fixture/no-call preflight |
| 13 | `make event-alpha-coinalyze-preflight PYTHON=python3` | pass | missing_config, no provider network calls |
| 14 | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | pass | no-send rehearsal, no side effects |
| 15 | `make event-alpha-market-anomaly-smoke PYTHON=python3` | pass | market anomaly smoke |
| 16 | `make event-alpha-official-exchange-smoke PYTHON=python3` | pass | official exchange smoke |
| 17 | `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` | pass | scheduled catalyst smoke |
| 18 | `make event-alpha-unlock-risk-smoke PYTHON=python3` | pass | unlock risk smoke |
| 19 | `make event-alpha-derivatives-smoke PYTHON=python3` | pass | derivatives smoke |
| 20 | `make event-alpha-fade-review-smoke PYTHON=python3` | pass | fade-review smoke |
| 21 | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | source coverage rendered |
| 22 | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | daily brief rendered |
| 23 | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | preview rendered, no send |
| 24 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | pass | WARN/no blockers |
| 25 | `make verify PYTHON=python3` | pass | standard repo verification passed |

## Runtime

- standalone_runner_runtime_seconds: `11.191`
- pytest_runtime_seconds: `11.538`
- pytest_plugin_autoload_disabled: `true`

## Size And Organization

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <6500 | blocked |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | pass |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | pass |
| `crypto_rsi_scanner/cli/services/event_alpha.py` | 3938 | 3938 | 0 | 0.0% | <1500 | blocked |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py` | 7145 | 6363 | 782 | 10.94% | <1500 | blocked |

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
- intentionally_outside_event_alpha_modules: `crypto_rsi_scanner.event_fade`

Migrated this run:
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

## Doctor And Namespace Coverage

- registered_checks: `53`
- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "source_coverage": 1, "stale_artifacts": 1}`
- namespace_count: `46`
- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`

## Safety Invariants

- research_only: `true`
- no_live_provider_calls_by_default: `true`
- no_live_telegram_sends: `true`
- no_trading_paper_or_execution_changes: `true`
- no_event_alpha_normal_rsi_signal_writes: `true`
- no_event_alpha_created_triggered_fade: `true`
- event_fade_remains_outside_event_alpha: `true`
- no_secrets_in_artifacts: `true`

## Known Remaining Blockers

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

## RC Verdict

Critical behavior and safety checks pass. This refactor continuation is pending final acceptance because scanner.py, cli/services/event_alpha.py, bind_scanner_globals reduction, and doctor legacy_unregistered targets remain documented blockers.
