# Project Health Naming Cleanup Report

Research artifact only. This static gate classifies remaining migration-era naming and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T13:29:24.402663+00:00`
- status: `OK`
- legacy_occurrences: `1799`
- legacy_named_files_remaining: `0`
- refactor_named_source_files_remaining: `0`

## Classification Counts

- CLI_backwards_compatibility_alias: `57`
- accepted_exception: `599`
- backwards_compatibility_alias: `15`
- historical_artifact_semantics: `433`
- historical_reference_keep: `527`
- test_fixture_name: `168`

## Action Counts

- should_keep: `1799`

## Policy

- legacy_implementation_files: `not_allowed`
- cli_legacy_flags: `backwards-compatible aliases only`
- artifact_legacy_fields: `historical artifact row semantics; preserve compatibility`
- docs_legacy_wording: `allowed only for historical/refactor records or explicit artifact compatibility semantics`
- refactor_tooling_names: `not allowed for current source/import/help/runbook surfaces; allowed only as historical aliases`

## Blockers

- none
