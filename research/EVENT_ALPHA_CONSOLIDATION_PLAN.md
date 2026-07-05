# Event Alpha Consolidation Plan

This milestone creates compatibility surfaces first. It does not physically
move every Event Alpha module or rewrite `scanner.py` in one pass.

## Completed In This Slice

- Added `crypto_rsi_scanner/event_alpha/` package skeleton with wrappers for
  radar, artifacts, notifications, outcomes, providers, doctor, and namespace
  modules.
- Added `crypto_rsi_scanner/cli/` facade and command snapshot helpers.
- Added pytest package scaffolding while keeping `python3 tests/test_indicators.py`
  as the standalone runner.
- Declared artifact schema v1 and wired schema counters into the existing
  artifact doctor.
- Added namespace lifecycle inventory/reporting and dry-run stale archive plan.
- Added GitHub Actions for safe verification and manual Event Alpha smokes.

## V1 Package Map

- `event_alpha/providers`: provider readiness, activation, preflight,
  provider-health, source registry, and source packs.
- `event_alpha/radar`: integrated radar, market state/reaction/anomaly,
  evidence acquisition, CoreOpportunity rows, source coverage, verdicts,
  impact hypotheses, and incidents.
- `event_alpha/artifacts`: artifact context, paths, schema v1, run ledger,
  retention, and locks.
- `event_alpha/notifications`: no-send previews, delivery ledger,
  send-readiness, go/no-go, inbox, SLO, pack, pause, final check, sender, and
  formatting helpers.
- `event_alpha/outcomes`: outcomes, calibration, feedback, burn-in, quality,
  priors, and policy simulation.
- `event_alpha/doctor`: schema doctor, safety/consistency phases, check
  registry, plugin checks, reports, and compatibility doctor orchestration.
- `event_alpha/namespace`: namespace status and lifecycle reporting.
- `cli/`: parser, dispatch, and command-group modules.
- `project_health/`: permanent architecture and project-health tooling for
  baseline inventories, size gates, class ownership, API inventory,
  completion maps, transition/naming checks, and final architecture reports.

## Import And CLI Rules

- No retained old flat Event Alpha import paths remain as compatibility shims.
- Any future retained entrypoint must be documented in
  `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json` and mirrored in
  `research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json` with path,
  reason, expected lifetime, and owner note before it is restored.
- Deleted old imports are tombstoned and are allowed to fail; docs should show
  canonical package paths.
- New code should import new package paths.
- Old top-level shim modules must not be recreated without an explicit public
  compatibility decision.
- Tombstone tests cover deleted old paths, and artifact
  doctor warns if a deleted old shim path is reintroduced.
- Parser construction belongs in `cli/parser.py`.
- Dispatch belongs in `cli/dispatch.py`.
- Command bodies move behind `cli/commands_*.py` one group at a time.
- Architecture/project-health checks live under
  `crypto_rsi_scanner/project_health/` and use canonical `make architecture-*`
  targets. Removed old target aliases are not part of the current runbook
  surface.
- `scanner.py`, `main.py`, Make targets, flags, and defaults stay compatible
  until an explicit migration says otherwise.

## Test Rules

- New Event Alpha tests belong in `tests/event_alpha/`.
- New RSI/backtest/paper-risk tests belong in `tests/rsi/`.
- New parser/dispatch/Make/workflow tests belong in `tests/cli/`.
- `tests/test_indicators.py` is a compatibility umbrella and should not become
  the default home for new tests.

## Safety Invariants

Research-only/no-trading/no-paper/no-send guards are non-negotiable v1
invariants. Consolidation work must not add live trading, paper trading,
execution, normal RSI signal writes, live Telegram sends in tests, live provider
calls by default, API key printing, or Event Alpha-created `TRIGGERED_FADE`.

## How To Add A New Artifact Row

1. Update `event_alpha/artifacts/schema_v1.py`.
2. Add or update the writer.
3. Add schema/doctor validation.
4. Add fixture tests.
5. Update operator docs.

## How To Add A New Doctor Check

1. Declare schema field dependencies in the check registry.
2. Ensure those fields exist in schema v1.
3. Add fixture rows that fail and pass.
4. Add tests for strict/non-strict behavior.

## How To Add A New Namespace

1. Choose a lifecycle status.
2. Declare key artifacts and retention expectations.
3. Ensure send-readiness/burn-in/calibration safety is explicit.
4. Add doctor expectations and lifecycle tests.

## How To Add A Provider

1. Keep reusable provider adapters outside Event Alpha when they are reusable;
   place activation/preflight/readiness orchestration in `event_alpha/providers`.
2. Start with fixture/parser status and no-call preflight artifacts.
3. If live rehearsal is needed, require explicit allow flag, request ledger,
   request budget, no-send mode, redaction, and provider-health telemetry.
4. Wire source registry/source packs, source coverage, integrated radar loading,
   and artifact doctor checks.
5. Add deterministic tests proving no live calls by default and no
   sends/trades/paper/RSI/`TRIGGERED_FADE` side effects.

## How To Add A Radar Artifact

1. Define or extend schema v1 first.
2. Write through artifact path/context helpers under a namespace.
3. Attach source lineage, canonical identity, freshness, safety counters, and
   relative paths where applicable.
4. Update integrated radar, CoreOpportunity/card/daily-brief surfaces, source
   coverage, and doctor checks only as additive schema-backed changes.
5. Add `tests/event_alpha/` coverage.

## How To Add A Notification Lane

1. Add lane planning/rendering in `event_alpha/notifications`.
2. Preserve no-send preview behavior, structured skip telemetry, and delivery
   `status`/`status_detail`.
3. Keep real send paths guarded by explicit operator commands and final
   readiness checks.
4. Keep copy research-only and not a trade signal.
5. Add preview, delivery, final-check, and doctor tests.

## How To Add An Outcome Or Calibration Field

1. Update schema v1 before adding the field to writers/reports.
2. Register doctor dependencies for any checks that read the field.
3. Keep priors recommendation-only with `auto_apply=false`.
4. Add low-sample warnings where sample size can mislead.
5. Add outcome/calibration tests and update report docs.
