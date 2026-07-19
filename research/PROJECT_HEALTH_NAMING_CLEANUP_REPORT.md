# Project Health Naming Cleanup Report

Research artifact only. This static gate classifies remaining migration-era naming and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-19T03:09:54.073378+00:00`
- status: `OK`
- legacy_occurrences: `2648`
- legacy_named_files_remaining: `0`
- refactor_named_source_files_remaining: `0`
- active_refactor_reports_remaining: `0`
- north_star_document_present: `True`
- north_star_burn_in_contract_present: `True`
- north_star_auto_apply_thresholds: `False`
- validation_loop_status: `pass`
- validation_loop_missing_module_count: `0`
- validation_loop_review_dispatch_artifact_only: `True`

## Classification Counts

- CLI_backwards_compatibility_alias: `48`
- accepted_exception: `786`
- backwards_compatibility_alias: `15`
- historical_artifact_semantics: `747`
- historical_reference_keep: `565`
- test_fixture_name: `487`

## Action Counts

- should_keep: `2648`

## Policy

- legacy_implementation_files: `not_allowed`
- cli_legacy_flags: `deprecated hidden backwards-compatible aliases only`
- artifact_legacy_fields: `historical artifact row semantics; preserve compatibility`
- docs_legacy_wording: `allowed only for historical/refactor records or explicit artifact compatibility semantics`
- refactor_tooling_names: `not allowed for current source/import/help/runbook surfaces; allowed only as historical aliases`
- refactor_report_files: `active root/research refactor-era reports are not allowed; archived copies under research/archive/refactor_history are historical records`
- event_alpha_radar_north_star: `missing North Star docs or burn-in contract are warnings; auto_apply_thresholds=true is a blocker`
- event_alpha_validation_loop: `burn-in operating Make targets must point at real artifact-only modules, keep alerts disabled by default, and standalone review dispatch must not fall through to the default scan`

## Warnings

- none

## Blockers

- none
