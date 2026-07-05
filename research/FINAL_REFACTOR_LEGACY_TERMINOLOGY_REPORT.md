# Final Refactor Legacy Terminology Report

Research artifact only. This static gate classifies remaining uses of `legacy` and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.

- generated_at: `2026-07-05T10:06:09.811307+00:00`
- status: `OK`
- legacy_occurrences: `2129`
- legacy_named_files_remaining: `0`

## Classification Counts

- CLI_backwards_compatibility_alias: `57`
- accepted_exception: `723`
- historical_artifact_semantics: `1149`
- test_fixture_name: `200`

## Action Counts

- should_keep: `2129`

## Policy

- legacy_implementation_files: `not_allowed`
- cli_legacy_flags: `backwards-compatible aliases only`
- artifact_legacy_fields: `historical artifact row semantics; preserve compatibility`
- docs_legacy_wording: `allowed only for historical/refactor records or explicit artifact compatibility semantics`

## Blockers

- none
