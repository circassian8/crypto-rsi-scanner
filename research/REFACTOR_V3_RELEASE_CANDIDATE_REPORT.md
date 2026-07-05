# Refactor V3 Release Candidate Report

Research-only release-candidate report. This report does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created `TRIGGERED_FADE`.

- generated_at: `2026-07-05T10:04:58.393472+00:00`
- acceptance_status: `accepted`
- critical_gate_status: `pass`
- commands_passed: `17/17`
- duration_seconds_total: `817.924`

## Critical Gates

| gate | status |
|---|---:|
| `all_commands_passed` | `pass` |
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
| `doctor_registry_api_unregistered_zero` | `pass` |
| `namespace_unknown_zero` | `pass` |
| `shim_dependency_status_ok` | `pass` |
| `legacy_file_retirement_ok` | `pass` |
| `legacy_named_files_zero` | `pass` |
| `legacy_named_files_with_implementation_zero` | `pass` |
| `compatibility_named_files_zero` | `pass` |
| `retained_public_entrypoints_zero` | `pass` |
| `event_fade_safety_exception_present` | `pass` |
| `scanner_entrypoint_exception_present` | `pass` |

## Accepted Warnings

| item | value |
|---|---:|
| `production_files_over_1200_lines` | `13` |
| `accepted_class_exceptions_count` | `3` |
| `refactor_final_v3_gate_status` | `accepted_with_documented_exceptions` |
| `refactor_final_v3_auto_accept_blockers` | `[]` |
| `refactor_final_v3_blockers` | `[]` |

## Event Module And Shim Status

- top_level_event_module_count: `1`
- retained_public_shims_count: `0`
- retained_public_entrypoints: `0`
- deleted_shims_count: `124`
- legacy_named_files_remaining: `0`
- legacy_named_files_with_implementation: `0`
- compatibility_named_files_remaining: `0`
- event_fade_safety_exception_present: `True`
- scanner_entrypoint_exception_present: `True`
- public_compatibility_entrypoints_path: `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json`
- old_path_internal_imports: `0`
- old_path_test_imports: `0`
- old_path_docs_references: `0`

Top-level implementation modules:
- `crypto_rsi_scanner.event_fade`

Retained public shims:
- none

## Size And Ownership

- production_files_over_1500_lines: `0`
- production_files_over_1200_lines: `13`
- unresolved_production_files_over_1200_lines: `0`
- functions_over_150_lines: `0`
- classes_over_75_lines: `None`
- accepted_class_exceptions_count: `3`
- model_bundles_count: `79`
- unresolved_multi_class_modules_count: `0`

## Test Results

| # | command | status | seconds |
|---:|---|---:|---:|
| 1 | `python3 tests/test_indicators.py` | `pass` | `192.42` |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | `pass` | `197.551` |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | `pass` | `0.058` |
| 4 | `make refactor-transitional-file-check PYTHON=python3` | `pass` | `0.052` |
| 5 | `make refactor-legacy-file-check PYTHON=python3` | `pass` | `0.049` |
| 6 | `make refactor-legacy-terminology-check PYTHON=python3` | `pass` | `0.246` |
| 7 | `make event-alpha-old-import-check PYTHON=python3` | `pass` | `1.459` |
| 8 | `make event-alpha-shim-dependency-report PYTHON=python3` | `pass` | `1.459` |
| 9 | `make refactor-size-gates PYTHON=python3` | `pass` | `1.309` |
| 10 | `make refactor-class-ownership-report PYTHON=python3` | `pass` | `1.12` |
| 11 | `make refactor-final-report PYTHON=python3` | `pass` | `1.626` |
| 12 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | `pass` | `6.049` |
| 13 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | `pass` | `4.95` |
| 14 | `make event-alpha-notification-format-smoke PYTHON=python3` | `pass` | `6.509` |
| 15 | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | `pass` | `7.152` |
| 16 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | `pass` | `6.273` |
| 17 | `make verify PYTHON=python3` | `pass` | `389.639` |

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
