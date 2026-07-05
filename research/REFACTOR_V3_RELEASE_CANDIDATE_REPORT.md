# Refactor V3 Release Candidate Report

Research-only release-candidate report. This report does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created `TRIGGERED_FADE`.

- generated_at: `2026-07-05T03:16:24+00:00`
- acceptance_status: `accepted`
- critical_gate_status: `pass`
- commands_passed: `26/26`
- duration_seconds_total: `1400.36`

## Critical Gates

| gate | status |
|---|---:|
| `all_commands_passed` | `pass` |
| `refactor_completion_map_accepted` | `pass` |
| `refactor_final_has_no_blockers` | `pass` |
| `only_event_fade_top_level_implementation` | `pass` |
| `nonessential_shims_remaining_zero` | `pass` |
| `old_path_internal_imports_zero` | `pass` |
| `old_path_test_imports_zero` | `pass` |
| `old_path_docs_references_zero` | `pass` |
| `production_files_over_1500_zero` | `pass` |
| `unresolved_production_files_over_1200_zero` | `pass` |
| `functions_over_150_zero` | `pass` |
| `oversized_classes_are_accepted` | `pass` |
| `unresolved_multi_class_modules_zero` | `pass` |
| `doctor_registry_legacy_unregistered_zero` | `pass` |
| `namespace_unknown_zero` | `pass` |
| `shim_dependency_status_ok` | `pass` |
| `old_import_check_status_ok` | `pass` |

## Accepted Warnings

| item | value |
|---|---:|
| `production_files_over_1200_lines` | `12` |
| `accepted_production_files_over_1200_lines` | `12` |
| `classes_over_75_lines` | `3` |
| `accepted_class_exceptions_count` | `3` |
| `refactor_final_v3_gate_status` | `accepted_with_documented_exceptions` |
| `refactor_final_v3_auto_accept_blockers` | `[]` |
| `refactor_final_v3_blockers` | `[]` |
| `refactor_final_v3_accepted_exception_categories` | `['class_exceptions_remaining', 'production_files_over_1200_lines']` |

## Event Module And Shim Status

- top_level_event_module_count: `10`
- retained_public_shims_count: `9`
- deleted_shims_count: `115`
- old_path_internal_imports: `0`
- old_path_test_imports: `0`
- old_path_docs_references: `0`

Top-level implementation modules:
- `crypto_rsi_scanner.event_fade`: Intentional safety boundary outside Event Alpha; owns TRIGGERED_FADE with proxy_fade.

Retained public shims:
- `crypto_rsi_scanner.event_alpha_artifacts` -> `crypto_rsi_scanner.event_alpha.artifacts.context`
- `crypto_rsi_scanner.event_artifact_paths` -> `crypto_rsi_scanner.event_alpha.artifacts.paths`
- `crypto_rsi_scanner.event_alpha_run_ledger` -> `crypto_rsi_scanner.event_alpha.artifacts.run_ledger`
- `crypto_rsi_scanner.event_alpha_retention` -> `crypto_rsi_scanner.event_alpha.artifacts.retention`
- `crypto_rsi_scanner.event_alpha_run_lock` -> `crypto_rsi_scanner.event_alpha.artifacts.locks`
- `crypto_rsi_scanner.event_alpha_artifact_doctor` -> `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`
- `crypto_rsi_scanner.event_alpha_profiles` -> `crypto_rsi_scanner.event_alpha.config.profiles`
- `crypto_rsi_scanner.event_alpha_v1_readiness` -> `crypto_rsi_scanner.event_alpha.config.v1_readiness`
- `crypto_rsi_scanner.event_alpha_preflight` -> `crypto_rsi_scanner.event_alpha.config.preflight`

## Size And Ownership

- production_files_over_1500_lines: `0`
- production_files_over_1200_lines: `12`
- unresolved_production_files_over_1200_lines: `0`
- functions_over_150_lines: `0`
- classes_over_75_lines: `3`
- accepted_class_exceptions_count: `3`
- model_bundles_count: `79`
- unresolved_multi_class_modules_count: `0`

Accepted class exceptions:
- `crypto_rsi_scanner.storage_parts.migrations.MigrationsMixin` (88 lines): SQLite migration ownership is intentionally centralized to avoid untested schema drift.
- `crypto_rsi_scanner.storage_parts.signals.SignalsMixin` (129 lines): Signal persistence methods share schema assumptions, row serialization, and outcome lookup behavior.
- `crypto_rsi_scanner.storage_parts.watchlist.WatchlistMixin` (89 lines): Watchlist persistence methods are stable DB helpers and only slightly exceed the advisory limit.

## Doctor And Namespace

- doctor legacy_unregistered: `0`
- doctor legacy_unregistered_status: `pass`
- namespace_count: `46`
- unknown_namespace_count: `0`
- namespace_status_counts: `{"active_fixture_smoke": 18, "active_integrated_smoke": 1, "active_live_rehearsal": 9, "active_provider_preflight": 5, "active_provider_rehearsal": 5, "active_refactor_report": 1, "manual_review": 5, "quarantine": 1, "stale_deprecated": 1}`

## Test Results

| # | command | status | seconds |
|---:|---|---:|---:|
| 1 | `python3 tests/test_indicators.py` | `pass` | `249.4` |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | `pass` | `252.71` |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | `pass` | `0.06` |
| 4 | `make test-pytest-safe PYTHON=python3` | `pass` | `266.8` |
| 5 | `make refactor-size-gates PYTHON=python3` | `pass` | `4.08` |
| 6 | `make refactor-class-ownership-report PYTHON=python3` | `pass` | `1.14` |
| 7 | `make refactor-completion-map PYTHON=python3` | `pass` | `94.98` |
| 8 | `make refactor-final-report PYTHON=python3` | `pass` | `29.38` |
| 9 | `make event-alpha-shim-report PYTHON=python3` | `pass` | `0.04` |
| 10 | `make event-alpha-shim-dependency-report PYTHON=python3` | `pass` | `24.93` |
| 11 | `make event-alpha-old-import-check PYTHON=python3` | `pass` | `22.21` |
| 12 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | `pass` | `26.64` |
| 13 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | `pass` | `25.66` |
| 14 | `make event-alpha-notification-format-smoke PYTHON=python3` | `pass` | `27.45` |
| 15 | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | `pass` | `28.12` |
| 16 | `make event-alpha-evidence-acquisition-smoke PYTHON=python3` | `pass` | `29.4` |
| 17 | `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` | `pass` | `29.77` |
| 18 | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | `pass` | `0.71` |
| 19 | `make event-alpha-coinalyze-preflight PYTHON=python3` | `pass` | `0.7` |
| 20 | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | `pass` | `0.68` |
| 21 | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | `pass` | `0.69` |
| 22 | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | `pass` | `4.59` |
| 23 | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | `pass` | `1.27` |
| 24 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | `pass` | `27.65` |
| 25 | `make backtest-costs PYTHON=python3` | `pass` | `0.58` |
| 26 | `make verify PYTHON=python3` | `pass` | `250.72` |

## Safety Invariants

| invariant | confirmed |
|---|---:|
| `research_only` | `true` |
| `no_live_trading_added` | `true` |
| `no_paper_trading_behavior_changes` | `true` |
| `no_execution_or_order_logic_changes` | `true` |
| `no_event_alpha_rsi_signal_writes` | `true` |
| `no_event_alpha_triggered_fade` | `true` |
| `event_fade_remains_outside_event_alpha` | `true` |
| `no_live_provider_calls_by_default` | `true` |
| `no_live_telegram_sends` | `true` |
| `no_secrets_committed` | `true` |

## Failures

- none
