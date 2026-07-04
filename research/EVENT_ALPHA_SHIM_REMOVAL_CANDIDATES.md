# Event Alpha Shim Removal Candidates

Research artifact only. No shims are deleted by this report.

- generated_at: 2026-07-04T19:54:58.468970+00:00
- registry_entry_count: 9

Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create `TRIGGERED_FADE`. `TRIGGERED_FADE` belongs only to `event_fade.py` plus `proxy_fade`.

## Remove Now Candidates

- none

## Migrate Imports First

- none

## Keep Public Compatibility

- `crypto_rsi_scanner.event_alpha_artifacts` -> `crypto_rsi_scanner.event_alpha.artifacts.context` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_artifact_paths` -> `crypto_rsi_scanner.event_alpha.artifacts.paths` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_run_ledger` -> `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_retention` -> `crypto_rsi_scanner.event_alpha.artifacts.retention` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_run_lock` -> `crypto_rsi_scanner.event_alpha.artifacts.locks` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_artifact_doctor` -> `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_profiles` -> `crypto_rsi_scanner.event_alpha.config.profiles` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_v1_readiness` -> `crypto_rsi_scanner.event_alpha.config.v1_readiness` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)
- `crypto_rsi_scanner.event_alpha_preflight` -> `crypto_rsi_scanner.event_alpha.config.preflight` (keep_public_entrypoint; blockers: test_import_references, artifact_doc_references)

## Keep Safety Exception

- `crypto_rsi_scanner.event_fade` -> `` (intentionally_external; blockers: safety_boundary_triggered_fade_owner)

## Keep Until Next Major Refactor

- none
