# Project Health Naming Cleanup Report

Research artifact only. This static gate classifies remaining migration-era naming and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T11:39:39.491787+00:00`
- status: `OK`
- legacy_occurrences: `3153`
- legacy_named_files_remaining: `0`
- refactor_named_source_files_remaining: `0`

## Classification Counts

- CLI_backwards_compatibility_alias: `57`
- Makefile_target_to_update: `45`
- accepted_exception: `734`
- backwards_compatibility_alias: `143`
- current_tooling_name_to_rename: `110`
- historical_artifact_semantics: `1128`
- historical_reference_keep: `734`
- test_fixture_name: `196`
- test_reference_to_update: `6`

## Action Counts

- should_keep: `2992`
- should_rename: `161`

## Policy

- legacy_implementation_files: `not_allowed`
- cli_legacy_flags: `backwards-compatible aliases only`
- artifact_legacy_fields: `historical artifact row semantics; preserve compatibility`
- docs_legacy_wording: `allowed only for historical/refactor records or explicit artifact compatibility semantics`
- refactor_tooling_names: `not allowed for current source/import/help/runbook surfaces; allowed only as historical aliases`

## Blockers

- none
