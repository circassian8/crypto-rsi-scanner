# Event Alpha Old Import Check

Research artifact only. This lint-style check does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-18T14:38:55.169031+00:00
- status: OK
- registry_entry_count: 0
- deleted_shim_entry_count: 124
- old_path_check_entry_count: 124
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 0
- deleted_path_import_failure_checks: 0
- old_path_text_references: 64
- include_runtime_artifacts: False
- cache_status: miss
- scan_duration_seconds: 2.0967
- scanned_source_files: 878
- scanned_doc_files: 70
- scanned_test_files: 221
- skipped_artifact_files: 2780
- skipped_large_files: 4
- skipped_dirs: 67

## Policy

- Product code and ordinary tests must import canonical Event Alpha package paths.
- Old flat shim imports are allowed only in `tests/event_alpha/test_no_old_event_alpha_imports.py`, shim modules themselves, `scanner.py`, and entrypoints explicitly documented in `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`.
- `event_fade.py` remains intentionally outside Event Alpha and is not an old Event Alpha shim.

## Blockers

- none
