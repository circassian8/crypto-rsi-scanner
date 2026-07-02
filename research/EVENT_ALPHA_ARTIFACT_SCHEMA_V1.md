# Event Alpha Artifact Schema V1

Schema v1 lives in
`crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py` and declares
`EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION = "event_alpha_schema_v1"`.

## Contract

Schema v1 is the current additive artifact contract for Event Alpha. Each
declared schema records required fields, optional fields, deprecated fields,
field types, enum fields, path fields, debug absolute path fields, timestamp
fields, safety fields, lineage fields, and secret-redaction fields.

The registry currently covers:

- `core_opportunity_v1`
- `integrated_radar_candidate_v1`
- `notification_delivery_v1`
- `integrated_notification_delivery_v1`
- `source_coverage_v1`
- `provider_readiness_v1`
- `provider_preflight_v1`
- `coinalyze_request_ledger_v1`
- `derivatives_state_snapshot_v1`
- `derivatives_crowding_candidate_v1`
- `fade_review_candidate_v1`
- `market_state_snapshot_v1`
- `market_anomaly_v1`
- `official_exchange_event_v1`
- `scheduled_catalyst_event_v1`
- `unlock_event_v1`
- `outcome_row_v1`
- `calibration_prior_v1`
- `namespace_status_v1`
- `run_ledger_v1`

## Stamping

New or touched writers should add `schema_id` when the schema is known. Numeric
legacy `schema_version` values are upgraded to `event_alpha_schema_v1`; legacy
writer-specific strings such as store or run-ledger versions are preserved for
compatibility and paired with `schema_id`.

Rows without `schema_id` still validate through filename inference or historical
`row_type` mapping. Filename inference takes precedence over `row_type` because
some legacy derivative rows reused the same row type in crowding and fade-review
artifacts.

## Validation

The helper surface is:

- `infer_schema_id_for_file`
- `validate_row_against_schema`
- `validate_artifact_file`
- `collect_schema_errors`
- `stamp_artifact_row`
- `stamp_artifact_rows`
- `stamp_artifact_payload`

Validation is intentionally lightweight and local. It checks required fields,
declared types, enums, non-debug absolute path leakage, guarded side-effect
flags/counts, `auto_apply=true`, and unredacted secret-looking fields.

## Path Rule

Operator artifact path fields are relative. Absolute paths are allowed only for
debug fields ending in `_abs_debug`.

## Safety Rule

Rows that can affect notifications, outcomes, or provider rehearsal surfaces
must carry explicit no-send/research-only fields where applicable. Schema
validation flags sent rows, RSI signal writes, trading/paper counts, nonzero
strict-alert/Telegram counts in guarded artifacts, and
`triggered_fade_created` claims when they appear.

## Secret Rule

Artifacts may name required env vars, but must not contain API-key, token,
authorization, or secret values. Redacted fields such as `redacted_headers`,
`token_redacted`, and `raw_payload_redacted` are allowed. Existing artifact
doctor secret-leak checks remain authoritative and run alongside schema checks.

## Freeze Policy

Future doctor checks that depend on artifact fields must update schema v1 first.
If a check relies on a new field, enum value, path field, safety flag, lineage
field, or timestamp, the schema declaration is the acceptance gate. Artifact
schema changes remain additive unless a migration is explicitly documented and
implemented.
