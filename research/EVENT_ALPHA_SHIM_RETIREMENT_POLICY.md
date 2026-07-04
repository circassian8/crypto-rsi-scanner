# Event Alpha Shim Retirement Policy

This is a research/refactor policy. It does not change runtime behavior, call
providers, send Telegram messages, trade, paper trade, write normal RSI signal
rows, or create `TRIGGERED_FADE`.

## Policy

- Old top-level Event Alpha modules are temporary compatibility shims during the
  v1/v2 migration.
- New implementation code must import new package paths under
  `crypto_rsi_scanner.event_alpha.*` or `crypto_rsi_scanner.event_core.*`.
- Old shims may be removed only after the dependency report shows zero internal
  import references and one accepted refactor release has passed with the new
  package paths.
- `scanner.py` may remain a compatibility CLI entrypoint.
- Public compatibility shims must be listed explicitly in the shim dependency
  report before they are retained.
- A shim marked `active_shim` must contain only compatibility imports,
  `globals().update(...)`, `__all__`, comments, and a module docstring.
- Tests may keep targeted old-import compatibility coverage until the declared
  removal phase. New behavior tests should import the new package paths.
- Docs and runbooks may mention old paths only when they clearly describe them
  as compatibility or deprecated paths.

## Safety Boundary

`event_fade.py` remains intentionally outside Event Alpha. Event Alpha can
produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create
`TRIGGERED_FADE`. `TRIGGERED_FADE` belongs only to `event_fade.py` plus
`proxy_fade`.

## Removal Gate

A shim can be considered for removal when all of these are true:

- `internal_import_references` is empty.
- Makefile and CLI entrypoint references are absent, or the entrypoint has an
  explicitly approved replacement.
- Compatibility tests either move to the new path or are retired in a declared
  removal phase.
- Docs no longer point users to old paths except as historical/deprecated notes.
- `make event-alpha-shim-report` has zero active-shim implementation logic.
- `make event-alpha-shim-dependency-report` lists the shim as a removal
  candidate.
- The full safe verification set passes with no live calls, sends, trading,
  paper trading, Event Alpha RSI writes, or Event Alpha-created
  `TRIGGERED_FADE`.
