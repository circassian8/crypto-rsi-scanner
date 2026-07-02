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
