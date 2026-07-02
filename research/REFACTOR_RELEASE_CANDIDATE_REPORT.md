# Refactor Release Candidate Report

- generated_at: `2026-07-02T18:04:07Z`
- status: `accepted_with_documented_doctor_plugin_followup`
- canonical_final_report: `research/REFACTOR_FINAL_REPORT.json`
- test_runtime_report: `research/test_runtime_report.json`
- total_commands: `25`
- failed_commands: `0`

This is a research-only release-candidate report. The verification pass did not enable live provider calls, live Telegram sends, trading, paper trading, execution, normal RSI signal writes from Event Alpha, or Event Alpha-created `TRIGGERED_FADE`.

## Verification Results

| # | command | status | note |
|---:|---|---:|---|
| 1 | `python3 tests/test_indicators.py` | pass | 733/733 standalone tests |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py` | pass | 739/739 pytest tests |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | pass | source/test bytecode compile |
| 4 | `make test-pytest-safe PYTHON=python3` | pass | safe pytest target, external plugin autoload disabled |
| 5 | `make test-pytest-timed PYTHON=python3` | pass | wrote research/test_runtime_report.md/json |
| 6 | `make event-alpha-shim-report PYTHON=python3` | pass | active shim logic violations=0 |
| 7 | `make refactor-final-report PYTHON=python3` | pass | report generated; gate blocked only by documented doctor-plugin target |
| 8 | `make event-alpha-namespace-lifecycle-report PYTHON=python3` | pass | unknown_namespace_count=0 |
| 9 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | pass | fixture smoke, no live calls |
| 10 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | pass | doctor OK |
| 11 | `make event-alpha-live-provider-readiness-smoke PYTHON=python3` | pass | live calls remain disabled |
| 12 | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | pass | fixture/no-call preflight |
| 13 | `make event-alpha-coinalyze-preflight PYTHON=python3` | pass | missing_config, no provider network calls |
| 14 | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | pass | no-send rehearsal, no side effects |
| 15 | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | source coverage rendered |
| 16 | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | daily brief rendered |
| 17 | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | preview rendered, no send |
| 18 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | pass | WARN/no blockers |
| 19 | `make export-src-with-artifacts-smoke PYTHON=python3` | pass | zip timestamp validation passed |
| 20 | `make verify PYTHON=python3` | pass | standard repo verification passed |
| 21 | `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` | pass | scheduled catalyst smoke |
| 22 | `make event-alpha-unlock-risk-smoke PYTHON=python3` | pass | unlock risk smoke |
| 23 | `make event-alpha-derivatives-smoke PYTHON=python3` | pass | derivatives smoke |
| 24 | `make event-alpha-fade-review-smoke PYTHON=python3` | pass | fade-review smoke |
| 25 | `make event-alpha-official-exchange-smoke PYTHON=python3` | pass | official exchange smoke |

## Runtime

- standalone_runner_runtime_seconds: `10.761`
- pytest_runtime_seconds: `11.25`
- pytest_plugin_autoload_disabled: `true`

## Size And Organization

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <8000 | pass |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | pass |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | pass |

- package_doctor_implementation_lines: `6363`
- top_level_event_module_count: `125`
- active_shims: `67`
- partial_shims: `0`
- unmigrated_modules: `58`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `11`
- scanner_bind_scanner_globals_call_sites: `7`
- scanner_command_body_functions_remaining: `105`

Migrated this run:
- `crypto_rsi_scanner.event_alpha_artifact_doctor`
- `crypto_rsi_scanner.event_research_cards`
- `crypto_rsi_scanner.event_alpha_daily_brief`
- `crypto_rsi_scanner.event_derivatives_crowding`
- `crypto_rsi_scanner.event_scheduled_catalysts`
- `crypto_rsi_scanner.event_asset_registry`
- `crypto_rsi_scanner.event_instrument_resolver`
- `crypto_rsi_scanner.event_market_confirmation`
- `crypto_rsi_scanner.event_catalyst_search`
- `crypto_rsi_scanner.event_source_enrichment`
- `crypto_rsi_scanner.event_opportunity_audit`

## Doctor And Namespace Coverage

- registered_checks: `53`
- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- namespace_count: `46`
- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`

## CI Status

- workflow_configuration_safe: `true`
- pytest_disable_plugin_autoload: `true`
- verify workflow uses standalone tests, safe pytest, compileall, and `make verify`.
- Event Alpha smoke workflow remains `workflow_dispatch` only.

## Safety Invariants

- research_only: `true`
- no_live_provider_calls_by_default: `true`
- no_live_telegram_sends: `true`
- no_trading_paper_or_execution_changes: `true`
- no_event_alpha_normal_rsi_signal_writes: `true`
- no_event_alpha_created_triggered_fade: `true`
- no_secrets_in_artifacts: `true`

## Known Remaining Blockers

### `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`

- blocker_reason: legacy_unregistered doctor append sites remain above the requested <=5 target.
- next_migration_module: `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py`
- risk: Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.

## RC Verdict

Critical behavior and safety checks pass. Refactor continuation is accepted with one documented non-behavior blocker: legacy_unregistered doctor append sites remain above the <=5 target.
