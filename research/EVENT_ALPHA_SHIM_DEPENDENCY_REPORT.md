# Event Alpha Shim Dependency Report

Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-04T22:45:15.034950+00:00
- status: OK
- registry_entry_count: 9
- internal_import_reference_count: 0
- test_import_reference_count: 19
- makefile_reference_count: 0
- docs_reference_count: 11
- dynamic_import_reference_count: 0
- safe_to_remove_count: 0
- deleted_shims: 115
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 19
- active_shim_modules_with_implementation_logic: 0
- v3_gate_status: pass
- v3_auto_accept_ready: True

## Policy

- New implementation code must import new package paths, not old top-level Event Alpha shim paths.
- Old shims stay available during v1/v2 compatibility and may be removed only after zero internal references and an accepted removal release.
- `scanner.py` may remain a compatibility CLI entrypoint.
- `event_fade.py` remains intentionally outside Event Alpha; Event Alpha may write `FADE_SHORT_REVIEW` research but must not create `TRIGGERED_FADE`.

## Refactor V3 Shim Gates

| gate | value |
|---|---:|
| `nonessential_shims_remaining` | 0 |
| `old_path_internal_imports` | 0 |
| `old_path_test_imports` | 0 |
| `public_compatibility_shims` | 9 |
| `shim_removal_blockers` | 0 |
| `deleted_shims` | 115 |
| `old_path_docs_references` | 0 |
| `old_path_import_allowed_exceptions` | 19 |

## Registry Dependencies

| old module | new module | status | internal | tests | make | docs | dynamic | safe | action |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | active_shim | 0 | 3 | 0 | 3 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_public_entrypoint |

## Warnings

- none
