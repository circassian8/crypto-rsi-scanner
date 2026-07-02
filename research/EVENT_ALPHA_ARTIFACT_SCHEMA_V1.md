# Event Alpha Artifact Schema V1

Schema v1 lives in
`crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py`.

## Policy

- Schema v1 is the canonical field registry for Event Alpha artifacts after
  this consolidation pass.
- Future doctor checks that depend on a field must reference a field declared
  in schema v1. If the field is missing, update the schema before adding the
  check.
- Future artifact writers should add `schema_id` and `schema_version` where
  feasible, while readers stay compatible with current row types and filenames.
- Deprecations are declared in schema first, counted by the schema doctor, and
  removed only after old artifacts are no longer needed.

## Required Schema IDs

The v1 registry includes CoreOpportunity, integrated radar candidates,
notification deliveries, source coverage, provider readiness/preflight,
Coinalyze request ledgers, derivatives state/crowding/fade-review rows, market
state/anomaly rows, official exchange events, scheduled catalysts, unlocks,
outcomes, calibration priors, namespace status, and run ledgers.

## Path Rule

Operator artifact path fields are relative. Absolute paths are allowed only for
debug fields ending in `_abs_debug`.

## Safety Rule

Rows that can affect notifications, outcomes, or provider rehearsal surfaces
must carry explicit no-send/research-only fields where applicable. Schema
validation flags sent rows, RSI signal writes, trading/paper counts, and
`triggered_fade_created` claims when they appear in guarded artifacts.

## Secret Rule

Schema fields may name env vars, but must not permit API-key or token values in
artifact rows. Existing artifact doctor secret-leak checks remain authoritative.
