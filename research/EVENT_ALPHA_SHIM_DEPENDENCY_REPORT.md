# Event Alpha Shim Dependency Report

Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-05T14:14:23.808324+00:00
- status: OK
- registry_entry_count: 0
- internal_import_reference_count: 0
- test_import_reference_count: 0
- makefile_reference_count: 0
- docs_reference_count: 0
- dynamic_import_reference_count: 0
- safe_to_remove_count: 0
- deleted_shims: 124
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 0
- active_shim_modules_with_implementation_logic: 0
- v3_gate_status: pass
- v3_auto_accept_ready: True
- include_runtime_artifacts: False
- cache_status: miss
- scan_duration_seconds: 1.2649
- scanned_source_files: 607
- scanned_doc_files: 45
- scanned_test_files: 29
- skipped_artifact_files: 1285
- skipped_large_files: 1
- skipped_dirs: 63

## Policy

- New implementation code must import new package paths, not old top-level Event Alpha shim paths.
- Old shims stay available during v1/v2 compatibility and may be removed only after zero internal references and an accepted removal release.
- `scanner.py` may remain a compatibility CLI entrypoint.
- `event_fade.py` remains intentionally outside Event Alpha; Event Alpha may write `FADE_SHORT_REVIEW` research but must not create `TRIGGERED_FADE`.

## Architecture V3 Shim Gates

| gate | value |
|---|---:|
| `nonessential_shims_remaining` | 0 |
| `old_path_internal_imports` | 0 |
| `old_path_test_imports` | 0 |
| `public_compatibility_shims` | 0 |
| `shim_removal_blockers` | 0 |
| `deleted_shims` | 124 |
| `old_path_docs_references` | 0 |
| `old_path_import_allowed_exceptions` | 0 |

## Registry Dependencies

| old module | new module | status | internal | tests | make | docs | dynamic | safe | action |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|

## Warnings

- none
