# Event Alpha Module Map

This map records the intended package home for retained top-level compatibility
modules. Non-public shims removed in refactor v3 deletion passes are recorded in
`research/EVENT_ALPHA_DELETED_SHIMS.md/json` instead of this active map.

## Shim Registry

`crypto_rsi_scanner.event_alpha.shims` is the checked-in shim registry and audit
tool. It reads this module map and emits one row per compatibility module with:

- `old_module`
- `new_module`
- `shim_status`
- `allowed_exports`

Statuses:

- `active_shim`: the old module is a compatibility wrapper only. It may contain
  a docstring, imports, `globals().update(...)`, `__all__`, and comments. New
  implementation logic belongs in the new package path.
- `partial_shim`: the old module is a known migration bridge and may still
  contain legacy implementation logic until a later phase.
- `not_migrated`: the module has not been moved yet and should not be judged by
  active-shim source rules.

Current phase:

- Mapped modules are retained compatibility shims. They are `active_shim` unless
  a future row is explicitly marked as a temporary migration bridge in
  `crypto_rsi_scanner.event_alpha.shims`.
- The first v3 deletion pass removed non-public shims that had no internal,
  Makefile, script, dynamic, or artifact-documentation references and were only
  exercised by the dedicated legacy import compatibility test.
- The second v3 deletion pass removed the remaining non-public shims after
  Makefile entrypoints and compatibility tests were moved to canonical package
  paths. This active map now lists only retained public compatibility wrappers.
- `crypto_rsi_scanner.event_alpha_artifact_doctor` is now an active
  compatibility shim; the implementation lives in
  `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`.
- `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` is the small public
  orchestrator/export surface. Behavior-compatible legacy internals are
  preserved in `crypto_rsi_scanner.event_alpha.doctor.legacy_artifact_doctor`
  until individual checks are migrated into focused doctor plugins.
- Large internal Event Alpha modules now follow the same wrapper/core pattern:
  public wrappers remain at `notifications.pipeline`,
  `artifacts.research_cards`, `artifacts.daily_brief`,
  `radar.integrated_radar`, `radar.impact_hypotheses`,
  `radar.core_opportunity_store`, and `radar.evidence_acquisition`; behavior
  cores are preserved as `pipeline_legacy`, `research_cards.legacy`,
  `daily_brief.legacy`, `integrated.legacy`, `impact_hypotheses.legacy`,
  `core.legacy_store`, and `evidence.legacy_acquisition`.
- Medium radar and provider adapters now use package homes with compatibility
  cores: `radar.validation`, `radar.discovery`, `radar.watchlist`,
  `radar.near_miss`, `event_providers.cryptopanic`,
  `derivatives_providers.coinalyze`, `event_providers.bybit_announcements`,
  `event_providers.binance_announcements`, and `event_alpha.providers.health`.
  New logic should land in their focused `models`, `provider`, `client`,
  `parser`, `loader`, `entries`, `review`, or `report` modules rather than in
  the legacy cores.
- Shared refactor facades follow the same rule outside the top-level
  `event_*.py` shim registry: `storage.py` owns only the public `Storage`
  facade over `storage_parts/`, `backtest.py` owns the historical backtest
  facade over `backtest_parts/`, and `event_alpha/artifacts/schema_v1.py` owns
  compatibility exports over `event_alpha/artifacts/schema/`.
- CLI refactor facades follow the same rule: `scanner.py` is a root
  compatibility facade, `cli/services/scanner_legacy.py` is the measured
  transitional core for historical scanner command bodies, and new command
  logic belongs in focused `cli/services/` or `cli/commands_*.py` modules.

Run `make event-alpha-shim-report PYTHON=python3` to write
`event_alpha_shim_report.json` and `event_alpha_shim_report.md` under the
`shim_report` Event Alpha artifact namespace. Artifact doctor warns if an
`active_shim` module contains implementation logic.

| Compatibility module | Implementation package path | Layer |
|---|---|---|
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | artifacts |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | artifacts |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | artifacts |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | doctor |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | config |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | config |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | config |
