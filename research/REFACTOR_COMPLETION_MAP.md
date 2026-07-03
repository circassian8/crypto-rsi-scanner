# Refactor Completion Map

Static map of the behavior-preserving Event Alpha refactor. It records package ownership, compatibility cores, size gates, and safety boundaries.

- generated_at: `2026-07-03T14:44:05+00:00`
- status: `pending_with_blockers`
- scanner.py lines: `90`
- scanner command bodies remaining: `0`
- cli service bind sites: `6`
- active shims: `124`
- active shim logic violations: `0`
- size gate status: `pass`
- legacy decomposition gate status: `blocked`
- legacy files over 3000 lines: `1`
- verification status: `not_run`

## Transitional Compatibility Cores

| path | lines | reason |
|---|---:|---|
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 | Moved historical scanner command body; old root scanner is now a facade. |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 95 | Preserves strict/WARN artifact doctor semantics while plugin migrations continue. |

## Known Remaining Blockers

- `refactor_final_gate`: refactor final report has blocking line or organization gates
- `legacy_decomposition_gate`: legacy implementation files over 3,000 lines remain
- `verification_not_recorded`: release-candidate verification results were not supplied

## Safety Invariants

- research_only: `True`
- no_live_provider_calls_by_default: `True`
- no_live_telegram_sends: `True`
- no_trading_paper_or_execution_changes: `True`
- no_event_alpha_normal_rsi_signal_writes: `True`
- no_event_alpha_created_triggered_fade: `True`
- triggered_fade_source: `event_fade.py + proxy_fade only`
- no_secrets_in_artifacts: `True`
