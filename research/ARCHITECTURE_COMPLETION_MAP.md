# Architecture Completion Map

Static map of the behavior-preserving Event Alpha architecture. It records package ownership, compatibility cores, size gates, and safety boundaries.

- generated_at: `2026-07-10T05:24:55+00:00`
- status: `accepted`
- scanner.py lines: `90`
- scanner command bodies remaining: `0`
- cli service bind sites: `5`
- active shims: `0`
- active shim logic violations: `0`
- size gate status: `pass`
- production size gate status: `warning`
- production files over 1200 lines: `12`
- accepted production files over 1200 lines: `12`
- unresolved production files over 1200 lines: `0`
- production files over 1500 lines: `0`
- production files over 2000 lines: `0`
- production files over 3000 lines: `0`
- accepted class exceptions: `3`
- remaining class ownership debt: `0`
- multiple public class module status: `pass`
- test size gate status: `warning`
- api decomposition gate status: `pass`
- api files over 3000 lines: `0`
- transitional_named_files_remaining: `0`
- transitional_named_files_with_implementation: `0`
- compatibility_named_files_remaining: `0`
- old_path_internal_imports: `0`
- old_path_test_imports: `0`
- old_path_docs_references: `0`
- nonessential_shims_remaining: `0`
- retained_public_entrypoints: `0`
- deleted_shims_count: `124`
- canonical_import_coverage: `pass`
- event_fade_safety_exception_present: `True`
- scanner_entrypoint_exception_present: `True`
- verification status: `pass`

## Transitional Compatibility Cores

| path | lines | reason |
|---|---:|---|
| `crypto_rsi_scanner/cli/services/scanner_api.py` | 120 | Moved historical scanner command body; old root scanner is now a facade. |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py` | 91 | Preserves strict/WARN artifact doctor semantics while plugin migrations continue. |

## Known Remaining Blockers

- none

## Class Ownership Cleanup

- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_status: `pass`

## Safety Invariants

- research_only: `True`
- no_live_provider_calls_by_default: `True`
- no_live_telegram_sends: `True`
- no_trading_paper_or_execution_changes: `True`
- no_event_alpha_normal_rsi_signal_writes: `True`
- no_event_alpha_created_triggered_fade: `True`
- triggered_fade_source: `event_fade.py + proxy_fade only`
- no_secrets_in_artifacts: `True`
