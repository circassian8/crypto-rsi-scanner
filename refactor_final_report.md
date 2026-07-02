# Refactor Final Report

Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-02T16:36:57+00:00`
- gate_status: `blocked`
- compatibility_preserved: `True`
- old_module_paths_removed: `0`

## Runtime Measurements

- standalone_runner_runtime_seconds: `13.73`
- pytest_runtime_seconds: `13.76`
- note: Runtimes are measured verification values supplied by the operator; null means not measured during report generation.

## Size Gates

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 11267 | 2106 | 15.75% | <4000 | `blocked` |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | `pass` |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 6359 | 786 | 11.0% | <1500 | `blocked` |

## Organization Counts

- top_level_event_module_count: `125`
- active_shims: `56`
- partial_shims: `1`
- unmigrated_modules: `68`
- active_shim_modules_with_implementation_logic: `0`

## Blockers

### `crypto_rsi_scanner/scanner.py`

- blocker_reason: scanner.py still contains many historical Event Alpha command bodies and runtime config adapters that were only partially routed through cli/dispatch.py.
- next_migration_module: `crypto_rsi_scanner/cli/commands_event_alpha.py plus service modules for remaining scanner-bound command bodies`
- risk: Broad scanner command extraction can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.

### `crypto_rsi_scanner/event_alpha_artifact_doctor.py`

- blocker_reason: event_alpha_artifact_doctor.py still owns the large compatibility result dataclass, legacy counters, and remaining imperative checks while plugin migration continues.
- next_migration_module: `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py, namespace.py, stale_artifacts.py, and focused legacy counter plugins`
- risk: Doctor extraction can silently change strict/WARN semantics, report counter names, or stale namespace handling if compatibility tests do not pin output.

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
