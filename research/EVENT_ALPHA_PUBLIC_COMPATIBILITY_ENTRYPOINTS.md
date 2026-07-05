# Event Alpha Public Compatibility Entrypoints

Research artifact only. This inventory does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T04:30:00+00:00`
- retained_public_shims_count: `0`
- Generic public compatibility manifest: `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`
- removed_shims_count: `124`

## Tombstone Policy

- Deleted old imports are allowed to fail.
- Documentation should show the new canonical package path.
- No flat Event Alpha public compatibility entrypoints remain.
- Artifact doctor warns if a deleted old shim path is reintroduced as a file.
- `scanner.py` remains the public CLI entrypoint wrapper.
- `event_fade.py` remains intentionally outside Event Alpha and owns `TRIGGERED_FADE` with `proxy_fade`.

## Retained Entrypoints

- none
