# Refactor V3 Contract

Research-only, behavior-preserving finalization contract. This document does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created TRIGGERED_FADE.

- generated_at: `2026-07-05T04:18:29.412050+00:00`
- schema_version: `refactor_v3_contract_v1`
- purpose: Move from accepted refactor v2 compatibility shims to fully finished refactor v3.
- feature_policy: Behavior-preserving refactor only; do not add product features.

## Compatibility Boundaries

- `old_event_alpha_shim_paths`: Temporary compatibility paths. Remove old top-level Event Alpha shims unless explicitly retained as public compatibility entrypoints.
- `new_imports`: New code must import new package paths only.
- `scanner_py`: scanner.py remains a public CLI entrypoint compatibility wrapper.
- `event_fade_py`: event_fade.py remains intentionally outside Event Alpha. TRIGGERED_FADE must only come from event_fade.py plus proxy_fade.

## Size And Ownership Gates

- `production_module_target_lines_lt`: 1200
- `production_file_blocker_lines_gt`: 1500
- `production_file_blocker_policy`: Production files over 1,500 lines are blockers unless explicitly accepted.
- `function_blocker_lines_gt`: 150
- `function_blocker_policy`: Functions over 150 lines are blockers unless explicitly accepted.
- `class_blocker_lines_gt`: 75
- `class_blocker_policy`: Classes over 75 lines should be split or explicitly accepted.
- `public_classes`: Public classes should live in their own modules.
- `multiple_public_classes`: Modules with multiple public classes should be reduced to model bundles only, with explicit documentation.

## V3 Gate Names

- `nonessential_shims_remaining`
- `old_path_internal_imports`
- `old_path_test_imports`
- `public_compatibility_shims`
- `shim_removal_blockers`
- `deleted_shims`
- `production_files_over_1200_lines`
- `production_files_over_1500_lines`
- `public_classes_not_in_own_module`
- `class_exceptions_remaining`
- `functions_over_150_lines`
- `old_path_docs_references`
- `old_path_import_allowed_exceptions`

## Public Entrypoints

- `crypto_rsi_scanner/scanner.py`: Historical CLI/module entrypoint compatibility.

## Intentional Exceptions

- `crypto_rsi_scanner/event_fade.py`: Safety boundary for event-fade research and TRIGGERED_FADE ownership; do not move into Event Alpha.

## Auto-Accept

- v3 auto-accept requires all v3 gates and documented exceptions to be clear. Accepted/documented target gaps report accepted_with_documented_exceptions; nonessential shims or unaccepted exceptions keep v3 pending or blocked.
