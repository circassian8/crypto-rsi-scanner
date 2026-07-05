# Event Alpha Final Shim Status

Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-05T03:23:54.336596+00:00
- removed_shims_count: 115
- retained_public_shims_count: 9
- nonessential_shims_remaining: 0
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 19

## Policy

Only explicitly retained public compatibility entrypoints remain. Non-public old Event Alpha shim paths are expected to fail import after deletion.

## Retained Public Shims

- `crypto_rsi_scanner.event_alpha_artifacts` -> `crypto_rsi_scanner.event_alpha.artifacts.context`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_artifact_paths` -> `crypto_rsi_scanner.event_alpha.artifacts.paths`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_run_ledger` -> `crypto_rsi_scanner.event_alpha.artifacts.run_ledger`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_retention` -> `crypto_rsi_scanner.event_alpha.artifacts.retention`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_run_lock` -> `crypto_rsi_scanner.event_alpha.artifacts.locks`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_artifact_doctor` -> `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_profiles` -> `crypto_rsi_scanner.event_alpha.config.profiles`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_v1_readiness` -> `crypto_rsi_scanner.event_alpha.config.v1_readiness`: public CLI/Make/import compatibility retained during v1/v2.
- `crypto_rsi_scanner.event_alpha_preflight` -> `crypto_rsi_scanner.event_alpha.config.preflight`: public CLI/Make/import compatibility retained during v1/v2.
