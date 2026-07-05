# Event Alpha Shim Retirement Policy

This is a research/refactor policy. It does not change runtime behavior, call
providers, send Telegram messages, trade, paper trade, write normal RSI signal
rows, or create `TRIGGERED_FADE`.

## Policy

- No old top-level Event Alpha public compatibility shims remain. Deleted old
  Event Alpha imports are documented in
  `research/EVENT_ALPHA_DELETED_SHIMS.md/json`.
- Deleted old Event Alpha imports are tombstoned and are allowed to fail.
- New implementation code must import new package paths under
  `crypto_rsi_scanner.event_alpha.*` or `crypto_rsi_scanner.event_core.*`.
- Any future public compatibility bridge requires an explicit
  compatibility-breaking decision, release notes, and targeted tests.
- `scanner.py` may remain a compatibility CLI entrypoint.
- Public compatibility shims must be listed explicitly in the shim dependency
  report and in `research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`
  before they are retained; the current retained set is empty.
- A shim marked `active_shim` must contain only compatibility imports,
  `globals().update(...)`, `__all__`, comments, and a module docstring.
- Tests may keep targeted old-import tombstone coverage for deleted paths. New
  behavior tests should import the new package paths.
- Docs and runbooks should show canonical package paths; old paths may appear
  only when they clearly describe tombstoned paths or historical decisions.
- Artifact doctor warns if a deleted shim file is reintroduced.

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
