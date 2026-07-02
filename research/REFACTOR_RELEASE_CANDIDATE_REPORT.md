# Refactor Release Candidate Report

- generated_at: `2026-07-02T16:45:53Z`
- status: `accepted_with_noncritical_followups`
- command_set: `post_refactor_regression_gauntlet`
- total_commands: `26`
- failed_commands: `0`
- measured_command_seconds: `85.66`

This is a research-only release-candidate report. The verification pass did not
enable live provider calls, live Telegram sends, trading, paper trading,
execution, normal RSI signal writes from Event Alpha, or Event Alpha-created
`TRIGGERED_FADE`.

## Verification Results

| # | command | status | seconds |
|---:|---|---:|---:|
| 1 | `python3 tests/test_indicators.py` | pass | 13.65 |
| 2 | `python3 -m pytest` | pass | 13.80 |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | pass | 0.05 |
| 4 | `make test-pytest PYTHON=python3` | pass | 14.06 |
| 5 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | pass | 1.55 |
| 6 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | pass | 0.74 |
| 7 | `make event-alpha-integrated-radar-outcome-smoke PYTHON=python3` | pass | 2.97 |
| 8 | `make event-alpha-integrated-radar-outcome-report PYTHON=python3` | pass | 0.64 |
| 9 | `make event-alpha-integrated-radar-calibration-report PYTHON=python3` | pass | 0.61 |
| 10 | `make event-alpha-live-provider-readiness-smoke PYTHON=python3` | pass | 0.62 |
| 11 | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | pass | 0.62 |
| 12 | `make event-alpha-coinalyze-preflight PYTHON=python3` | pass | 0.64 |
| 13 | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | pass | 0.61 |
| 14 | `make event-alpha-market-anomaly-smoke PYTHON=python3` | pass | 2.45 |
| 15 | `make event-alpha-official-exchange-smoke PYTHON=python3` | pass | 2.45 |
| 16 | `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` | pass | 2.45 |
| 17 | `make event-alpha-unlock-risk-smoke PYTHON=python3` | pass | 1.85 |
| 18 | `make event-alpha-derivatives-smoke PYTHON=python3` | pass | 1.84 |
| 19 | `make event-alpha-fade-review-smoke PYTHON=python3` | pass | 1.84 |
| 20 | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 0.63 |
| 21 | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 3.75 |
| 22 | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 0.70 |
| 23 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | pass | 1.19 |
| 24 | `make event-alpha-namespace-lifecycle-report PYTHON=python3` | pass | 0.69 |
| 25 | `make event-alpha-mark-known-stale-namespaces PYTHON=python3` | pass | 0.61 |
| 26 | `make verify PYTHON=python3` | pass | 14.65 |

Additional compatibility check:

- `/usr/bin/python3 -m compileall -q crypto_rsi_scanner tests`: pass. This
  catches the Python 3.11 syntax class used by GitHub Actions.

## Size And Organization

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 11267 | 2106 | 15.75% | <4000 | blocked |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | pass |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 6359 | 786 | 11.00% | <1500 | blocked |

Organization counts:

- top_level_event_module_count: `125`
- migrated_modules_tracked_by_shims: `57`
- active_shims: `56`
- partial_shims: `1`
- unmigrated_modules: `68`
- active_shim_modules_with_implementation_logic: `0`

## Schema And Doctor Coverage

Doctor-invoking gauntlet commands validated `328` schema row-checks across
fixture, provider, integrated radar, derivatives, fade-review, and rehearsal
namespaces. All schema counters were zero for validation failures:

- schema_validation_errors: `0`
- missing_required_fields: `0`
- invalid_enum_fields: `0`
- invalid_path_fields: `0`
- invalid_safety_fields: `0`
- deprecated_field_usage: `0`

Doctor registry coverage stayed stable:

- registered_checks: `53`
- legacy_unregistered: `15`
- legacy_unregistered_baseline: `15`

Doctor statuses in the gauntlet:

- integrated radar smoke/doctor/outcome: `OK`, no blockers, no warnings.
- derivatives and fade-review smokes: `OK`, no blockers, no warnings.
- market anomaly, official exchange, scheduled catalyst, and unlock-risk smokes:
  `WARN`, no blockers; warnings were isolated fixture/source-coverage or
  readiness-context gaps.
- `notify_llm_deep_cryptopanic_rehearsal` strict artifact doctor: `WARN`, no
  blockers; warnings were known quality-capped/incident-linkage review items.

## Namespace Lifecycle

Namespace registry:

- namespace_count: `46`
- safe_for_send_readiness_count: `0`
- status_counts: `active_fixture_smoke=18`, `active_integrated_smoke=1`,
  `active_live_rehearsal=9`, `active_provider_preflight=5`,
  `active_provider_rehearsal=5`, `stale_deprecated=1`, `unknown=7`

`make event-alpha-mark-known-stale-namespaces` marked `notify_llm_deep` as
`stale_deprecated`, not safe for send-readiness, burn-in measurement, or
calibration.

## CI Status

Workflow configuration is present and safe:

- `.github/workflows/verify.yml` runs standalone tests, full pytest, compileall,
  and `make verify` with `RSI_EVENT_ALERTS_ENABLED=0`.
- `.github/workflows/event-alpha-smoke.yml` is `workflow_dispatch` only and runs
  fixture/no-call Event Alpha smoke targets.
- Full pytest includes the workflow guard test that blocks secret-looking env
  values, live allow flags, and live-send targets.

Remote GitHub Actions observation before this RC commit:

- Latest pushed `Verify` run for `3855cf6b` failed on Python 3.11 syntax in
  `crypto_rsi_scanner/event_alpha/providers/official_exchange.py`.
- This RC fixes that parser incompatibility by splitting the nested f-string
  digest input before formatting.
- Local `/usr/bin/python3` compileall now passes, covering the failed CI syntax
  class. The next pushed commit should be watched for the remote `Verify` result.

## Safety Invariants

- no_live_provider_calls_by_default: confirmed
- no_live_telegram_sends: confirmed
- no_trading_paper_or_execution_changes: confirmed
- no_event_alpha_normal_rsi_signal_writes: confirmed
- no_event_alpha_created_triggered_fade: confirmed
- no_secrets_in_artifacts: confirmed by doctor/preflight checks

Evidence:

- Coinalyze preflight reported `No provider network calls were performed by this
  preflight`.
- Live provider readiness smoke asserted `"live_calls_allowed": false`.
- Coinalyze no-send rehearsal reported `telegram_sends=0`, `trades_created=0`,
  `paper_trades_created=0`, `normal_rsi_signal_rows_written=0`, and
  `triggered_fade_created=0`.
- Daily brief/source coverage/doctor outputs reported no alert, send, trade,
  paper, live DB, execution, normal RSI, or trigger changes.

## Known Remaining Blockers

No critical RC blockers remain after the local gauntlet and Python 3.11 syntax
fix.

Non-critical refactor follow-ups remain:

- `scanner.py` is still above the final target. Next migration module:
  `crypto_rsi_scanner/cli/commands_event_alpha.py` plus service modules for
  remaining scanner-bound command bodies. Risk: CLI defaults, Make target
  behavior, provider guardrails, and research-only side-effect gates.
- `event_alpha_artifact_doctor.py` is still above the final target. Next
  migration modules:
  `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py`, `namespace.py`,
  `stale_artifacts.py`, and focused legacy counter plugins. Risk: strict/WARN
  semantics, report counter names, and stale namespace handling.
- Remote CI should be observed after the RC commit because the previous pushed
  run failed before the Python 3.11 compatibility fix.

## RC Verdict

Event Alpha refactor v1 is accepted for resuming provider activation work, with
the remaining size-reduction work tracked as non-critical follow-up and remote
CI to be watched after push.
