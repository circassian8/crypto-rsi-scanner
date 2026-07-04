# Event Alpha Old Import Check

Research artifact only. This lint-style check does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-04T22:22:51.829334+00:00
- status: OK
- registry_entry_count: 9
- deleted_shim_entry_count: 115
- old_path_check_entry_count: 124
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 19
- deleted_path_import_failure_checks: 115
- old_path_text_references: 165

## Policy

- Product code and ordinary tests must import canonical Event Alpha package paths.
- Old flat shim imports are allowed only in `tests/event_alpha/test_legacy_import_compatibility.py`, shim modules themselves, `scanner.py`, and documented public compatibility wrappers.
- `event_fade.py` remains intentionally outside Event Alpha and is not an old Event Alpha shim.

## Blockers

- none
