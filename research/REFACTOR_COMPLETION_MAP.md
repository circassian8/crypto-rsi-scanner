# Refactor Completion Map

Static map of the behavior-preserving Event Alpha refactor. It records package ownership, compatibility cores, size gates, and safety boundaries.

- generated_at: `2026-07-04T04:16:54+00:00`
- status: `accepted`
- scanner.py lines: `90`
- scanner command bodies remaining: `0`
- cli service bind sites: `5`
- active shims: `124`
- active shim logic violations: `0`
- size gate status: `pass`
- production size gate status: `pass`
- production files over 2000 lines: `0`
- production files over 3000 lines: `0`
- test size gate status: `warning`
- legacy decomposition gate status: `pass`
- legacy files over 3000 lines: `0`
- verification status: `pass`

## Transitional Compatibility Cores

| path | lines | reason |
|---|---:|---|
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 | Moved historical scanner command body; old root scanner is now a facade. |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 95 | Preserves strict/WARN artifact doctor semantics while plugin migrations continue. |

## Known Remaining Blockers

- none

## Safety Invariants

- research_only: `True`
- no_live_provider_calls_by_default: `True`
- no_live_telegram_sends: `True`
- no_trading_paper_or_execution_changes: `True`
- no_event_alpha_normal_rsi_signal_writes: `True`
- no_event_alpha_created_triggered_fade: `True`
- triggered_fade_source: `event_fade.py + proxy_fade only`
- no_secrets_in_artifacts: `True`
