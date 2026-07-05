# Event Alpha Shim Removal Candidates

Research artifact only. No shims are deleted by this report.

- generated_at: 2026-07-05T04:18:25.113679+00:00
- registry_entry_count: 0

Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create `TRIGGERED_FADE`. `TRIGGERED_FADE` belongs only to `event_fade.py` plus `proxy_fade`.

## Remove Now Candidates

- none

## Migrate Imports First

- none

## Keep Public Compatibility

- none

## Keep Safety Exception

- `crypto_rsi_scanner.event_fade` -> `` (intentionally_external; blockers: safety_boundary_triggered_fade_owner)

## Keep Until Next Major Refactor

- none
