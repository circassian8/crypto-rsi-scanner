# Architecture Transitional File Report

Research artifact only. This static gate checks migration-era file names and flat Event Alpha modules. It does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-19T09:58:18.185335+00:00`
- status: `OK`
- transitional_named_files_count: `0`
- transitional_named_files_remaining: `0`
- transitional_named_files_with_implementation: `0`
- transitional_named_dirs_count: `0`
- compatibility_named_files_remaining: `0`
- top_level_event_modules_count: `0`
- retained_public_shims_count: `0`
- retained_public_entrypoints: `0`
- deleted_shims_count: `124`
- nonessential_shims_remaining: `0`
- event_fade_safety_exception_present: `True`
- scanner_entrypoint_exception_present: `True`

## Allowed Exceptions

- `crypto_rsi_scanner/event_fade.py`: Intentional safety boundary: TRIGGERED_FADE remains owned only by event_fade.py plus proxy_fade.

## Blockers

- none
