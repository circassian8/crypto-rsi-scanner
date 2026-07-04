# Remaining Event Module Classification

Research-only inventory. Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create `TRIGGERED_FADE`; that remains owned by `event_fade.py` plus `proxy_fade`.

- generated_at: 2026-07-04T19:22:48+00:00
- module_count: 10
- active_shim: 9
- intentionally_outside_event_alpha: 1
- not_migrated: 0

## Modules

| Module | Status | Package home | New path |
|---|---|---|---|
| `crypto_rsi_scanner.event_alpha_artifacts` | active_shim | artifacts | `crypto_rsi_scanner.event_alpha.artifacts.context` |
| `crypto_rsi_scanner.event_artifact_paths` | active_shim | artifacts | `crypto_rsi_scanner.event_alpha.artifacts.paths` |
| `crypto_rsi_scanner.event_alpha_run_ledger` | active_shim | artifacts | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` |
| `crypto_rsi_scanner.event_alpha_retention` | active_shim | artifacts | `crypto_rsi_scanner.event_alpha.artifacts.retention` |
| `crypto_rsi_scanner.event_alpha_run_lock` | active_shim | artifacts | `crypto_rsi_scanner.event_alpha.artifacts.locks` |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | active_shim | doctor | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` |
| `crypto_rsi_scanner.event_alpha_profiles` | active_shim | config | `crypto_rsi_scanner.event_alpha.config.profiles` |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | active_shim | config | `crypto_rsi_scanner.event_alpha.config.v1_readiness` |
| `crypto_rsi_scanner.event_alpha_preflight` | active_shim | config | `crypto_rsi_scanner.event_alpha.config.preflight` |
| `crypto_rsi_scanner.event_fade` | intentionally_outside_event_alpha | intentionally_outside_event_alpha | `crypto_rsi_scanner.event_fade` |
