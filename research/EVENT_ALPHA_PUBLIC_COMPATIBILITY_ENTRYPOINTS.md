# Event Alpha Public Compatibility Entrypoints

Research artifact only. This inventory does not call providers, send Telegram
messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T00:00:00+00:00`
- retained_public_shims_count: `9`
- removed_shims_count: `115`

## Tombstone Policy

- Deleted old imports are allowed to fail.
- Documentation should show the new canonical package path.
- Compatibility tests cover retained public entrypoints only.
- Artifact doctor warns if a deleted old shim path is reintroduced as a file.
- `scanner.py` remains the public CLI entrypoint wrapper.
- `event_fade.py` remains intentionally outside Event Alpha and owns
  `TRIGGERED_FADE` with `proxy_fade`.

## Retained Entrypoints

| path | new path | reason | expected lifetime | owner note |
|---|---|---|---|---|
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | Historical artifact-context helper import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.artifacts.context`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | Historical artifact-path helper import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.artifacts.paths`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | Historical run-ledger helper import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.artifacts.run_ledger`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | Historical artifact-retention helper import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.artifacts.retention`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | Historical run-lock helper import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.artifacts.locks`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | Historical artifact-doctor import and entrypoint path retained for public compatibility while the implementation lives under `event_alpha/doctor`. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | Historical Event Alpha profile import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.config.profiles`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | Historical Event Alpha v1-readiness import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.config.v1_readiness`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | Historical Event Alpha preflight import path retained for external scripts, older operator snippets, and public import compatibility. | Retain through the v3 public compatibility period; revisit only in a documented v4/deprecation release. | New code must import `crypto_rsi_scanner.event_alpha.config.preflight`. Keep the old module as an active shim only; deletion requires an accepted compatibility-breaking decision and updated compatibility tests. |
