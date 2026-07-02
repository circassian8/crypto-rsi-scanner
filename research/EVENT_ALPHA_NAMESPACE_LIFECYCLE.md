# Event Alpha Namespace Lifecycle

Namespace lifecycle reporting lives in
`crypto_rsi_scanner/event_alpha/namespace/lifecycle.py`.

## Statuses

- `active_live_rehearsal`
- `active_fixture_smoke`
- `active_provider_preflight`
- `active_provider_rehearsal`
- `active_integrated_smoke`
- `stale_deprecated`
- `archived`
- `quarantine`
- `unknown`

## Artifacts

- `event_alpha_namespace_registry.json`
- `event_alpha_namespace_lifecycle_report.md`
- per-namespace `event_alpha_namespace_status.json`

## Commands

- `make event-alpha-namespace-lifecycle-report PYTHON=python3`
- `make event-alpha-list-active-namespaces PYTHON=python3`
- `make event-alpha-archive-stale-namespaces PYTHON=python3`
- `make event-alpha-mark-known-stale-namespaces PYTHON=python3`

Archive output is a dry-run plan only in this milestone.

## Policy

Stale namespaces are never send-ready. Fixture smoke namespaces are validation
artifacts, not burn-in or calibration sources. Provider preflight/rehearsal
namespaces are no-send/provider-readiness artifacts. Active live rehearsal
namespaces may be burn-in/calibration candidates only after current doctor
status and freshness checks are clean.
