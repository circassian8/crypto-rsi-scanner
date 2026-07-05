# Event Alpha Old Import Check

Research artifact only. This lint-style check does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-05T04:18:23.602803+00:00
- status: OK
- registry_entry_count: 0
- deleted_shim_entry_count: 124
- old_path_check_entry_count: 124
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 0
- deleted_path_import_failure_checks: 0
- old_path_text_references: 3
- include_runtime_artifacts: False
- cache_status: hit
- scan_duration_seconds: 1.3132
- scanned_source_files: 604
- scanned_doc_files: 31
- scanned_test_files: 29
- skipped_artifact_files: 1285
- skipped_large_files: 0
- skipped_dirs: 62

## Policy

- Product code and ordinary tests must import canonical Event Alpha package paths.
- Old flat shim imports are allowed only in `tests/event_alpha/test_no_old_event_alpha_imports.py`, shim modules themselves, `scanner.py`, and documented public compatibility wrappers.
- `event_fade.py` remains intentionally outside Event Alpha and is not an old Event Alpha shim.

## Blockers

- none
