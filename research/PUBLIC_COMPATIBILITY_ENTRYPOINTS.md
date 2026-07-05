# Public Compatibility Entrypoints

Research artifact only. This report does not call providers, send Telegram
messages, trade, paper trade, write RSI signal rows, or create
`TRIGGERED_FADE`.

- generated_at: `2026-07-05T04:30:00+00:00`
- retained_public_entrypoints_count: `0`
- retained_public_shims_count: `0`
- removed_shims_count: `124`
- Event Alpha-specific mirror:
  `research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`

## Retained Old Entrypoints

- none

No old flat Event Alpha public compatibility entrypoints remain. Deleted old
imports are allowed to fail; docs and code should use canonical package paths.

## Intentional Non-Shim Entrypoints

- `crypto_rsi_scanner.scanner`: public CLI entrypoint wrapper; not an Event Alpha
  flat shim.
- `crypto_rsi_scanner.event_fade`: intentionally outside Event Alpha and owns
  `TRIGGERED_FADE` with `proxy_fade`.
