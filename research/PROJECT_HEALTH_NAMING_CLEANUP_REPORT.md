# Project Health Naming Cleanup Report

Research artifact only. This static gate classifies remaining migration-era naming and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T14:28:10.640706+00:00`
- status: `OK`
- legacy_occurrences: `1855`
- legacy_named_files_remaining: `0`
- refactor_named_source_files_remaining: `0`
- active_refactor_reports_remaining: `0`

## Classification Counts

- CLI_backwards_compatibility_alias: `48`
- accepted_exception: `638`
- backwards_compatibility_alias: `15`
- historical_artifact_semantics: `429`
- historical_reference_keep: `548`
- test_fixture_name: `177`

## Action Counts

- should_keep: `1855`

## Policy

- legacy_implementation_files: `not_allowed`
- cli_legacy_flags: `deprecated hidden backwards-compatible aliases only`
- artifact_legacy_fields: `historical artifact row semantics; preserve compatibility`
- docs_legacy_wording: `allowed only for historical/refactor records or explicit artifact compatibility semantics`
- refactor_tooling_names: `not allowed for current source/import/help/runbook surfaces; allowed only as historical aliases`
- refactor_report_files: `active root/research refactor-era reports are not allowed; archived copies under research/archive/refactor_history are historical records`

## Blockers

- none
