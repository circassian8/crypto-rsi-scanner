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

Each namespace status row should include:

- `namespace`
- `status`
- `profile`
- `created_at`
- `last_updated_at`
- `last_verified_at`
- `safe_for_send_readiness`
- `safe_for_burn_in_measurement`
- `safe_for_calibration`
- `superseded_by`
- `retention_policy`
- `archive_after_days`
- `prune_after_days`
- `reason`
- `current_doctor_status`
- `latest_run_id`
- `artifact_counts`
- `key_artifacts_present`
- `missing_key_artifacts`
- `readiness_required`
- `readiness_present`

## Commands

- `make event-alpha-namespace-lifecycle-report PYTHON=python3`
- `make event-alpha-list-active-namespaces PYTHON=python3`
- `make event-alpha-mark-known-stale-namespaces PYTHON=python3`
- `make event-alpha-mark-namespace-stale ARTIFACT_NAMESPACE=<namespace> PYTHON=python3`
- `make event-alpha-archive-stale-namespaces PYTHON=python3`

Archive output is a dry-run plan only in this milestone.

## Policy

Every new namespace needs an explicit status, retention policy, and
`safe_for_send_readiness` value. Do not rely on implicit namespace names for
send readiness, burn-in, or calibration decisions.

Research-only/no-trading/no-paper/no-send guards apply to every namespace.
Stale, archived, and quarantine namespaces are never send-ready. Fixture smoke
namespaces are validation artifacts, not burn-in or calibration sources.
Provider preflight/rehearsal namespaces are no-send/provider-readiness
artifacts. Active live rehearsal namespaces may be burn-in/calibration
candidates only after current doctor status and freshness checks are clean.

The old `notify_llm_deep` namespace is `stale_deprecated`. Stale namespaces are
auditable only with explicit include-stale behavior; otherwise artifact doctor
short-circuits stale namespaces so historical schema noise does not look like a
current regression.

## Doctor Rules

- Unknown namespace marker status => warning.
- Stale/archived/quarantine namespace with `safe_for_send_readiness=true` =>
  blocker.
- Active namespace older than retention without archive => warning.
- Namespace with strict doctor blockers and `safe_for_send_readiness=true` =>
  blocker.
- Missing lifecycle marker for a known active namespace should be fixed by
  running the lifecycle report or adding an explicit marker in tests.

## Adding A Namespace

1. Pick one lifecycle status from this document.
2. Declare the namespace purpose, profile, key artifacts, and retention policy.
3. Set `safe_for_send_readiness=false` unless it is an active live no-send
   rehearsal that has current doctor status `OK` or `WARN`.
4. Set burn-in/calibration booleans separately; send-readiness does not imply
   calibration readiness.
5. Add/update lifecycle tests and any doctor expectations.
6. Keep provider/smoke namespaces no-live and no-send by default.
