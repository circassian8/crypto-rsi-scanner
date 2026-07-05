# Event Alpha Module Map

This map records retained top-level compatibility modules. Event Alpha flat
shims removed in refactor v3 deletion passes are recorded in
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

- Refactor v3 finalization has no retained flat Event Alpha compatibility
  shims in this active registry.
- Deleted old imports are tombstoned: deleted import paths are allowed to fail,
  docs should show canonical package paths, and tests verify that deleted old
  paths stay deleted.
- `scanner.py` remains the public CLI entrypoint wrapper, outside this Event
  Alpha shim registry.
- `event_fade.py` remains intentionally outside Event Alpha and must not be
  moved into the Event Alpha package.
- `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` is the small public
  orchestrator/export surface. Behavior-compatible internals are
  preserved in `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_core`
  until individual checks are migrated into focused doctor plugins.
- Large internal Event Alpha modules now follow the same wrapper/core pattern:
  public wrappers remain at `notifications.pipeline`,
  `artifacts.research_cards`, `artifacts.daily_brief`,
  `radar.integrated_radar`, `radar.impact_hypotheses`,
  `radar.core_opportunity_store`, and `radar.evidence_acquisition`; their
  behavior-compatible cores live under package-local `*_core`, `api`, or
  focused implementation modules.
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
  compatibility facade, `cli/services/scanner_api.py` is the measured
  transitional core for historical scanner command bodies, and new command
  logic belongs in focused `cli/services/` or `cli/commands_*.py` modules.

Run `make event-alpha-shim-report PYTHON=python3` to write
`event_alpha_shim_report.json` and `event_alpha_shim_report.md` under the
`shim_report` Event Alpha artifact namespace. With no active flat shims, the
registry should report zero active entries.

| Compatibility module | Implementation package path | Layer |
|---|---|---|
| none | none | none |
