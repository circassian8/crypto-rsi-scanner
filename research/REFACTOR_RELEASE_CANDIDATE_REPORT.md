# Refactor Release Candidate Report

- generated_at: `2026-07-02T19:08:45Z`
- status: `pending_with_documented_refactor_blockers`
- canonical_final_report: `research/REFACTOR_FINAL_REPORT.json`
- classification_report: `research/REMAINING_EVENT_MODULE_CLASSIFICATION.json`
- total_commands: `24`
- failed_commands: `0`
- verification_elapsed_seconds: `73.066`

This is a research-only release-candidate report. The verification pass did not enable live provider calls, live Telegram sends, trading, paper trading, execution, normal RSI signal writes from Event Alpha, or Event Alpha-created `TRIGGERED_FADE`.

## Verification Results

| # | command | status | elapsed | note |
|---:|---|---:|---:|---|
| 1 | `python3 tests/test_indicators.py` | pass | 11.515s | 734/734 standalone tests |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | pass | 11.847s | 740/740 pytest tests |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | pass | 0.035s | pass |
| 4 | `make test-pytest-safe PYTHON=python3` | pass | 12.073s | 740/740 pytest tests |
| 5 | `make event-alpha-shim-report PYTHON=python3` | pass | 0.057s | pass |
| 6 | `make refactor-final-report PYTHON=python3` | pass | 0.138s | pass |
| 7 | `make event-alpha-namespace-lifecycle-report PYTHON=python3` | pass | 0.697s | pass |
| 8 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | pass | 1.534s | pass |
| 9 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | pass | 0.733s | pass |
| 10 | `make event-alpha-live-provider-readiness-smoke PYTHON=python3` | pass | 0.625s | pass |
| 11 | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | pass | 0.628s | pass |
| 12 | `make event-alpha-coinalyze-preflight PYTHON=python3` | pass | 0.608s | pass |
| 13 | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | pass | 0.61s | pass |
| 14 | `make event-alpha-market-anomaly-smoke PYTHON=python3` | pass | 2.462s | pass |
| 15 | `make event-alpha-official-exchange-smoke PYTHON=python3` | pass | 2.485s | pass |
| 16 | `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` | pass | 2.444s | pass |
| 17 | `make event-alpha-unlock-risk-smoke PYTHON=python3` | pass | 1.852s | pass |
| 18 | `make event-alpha-derivatives-smoke PYTHON=python3` | pass | 1.839s | pass |
| 19 | `make event-alpha-fade-review-smoke PYTHON=python3` | pass | 1.844s | pass |
| 20 | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 0.63s | pass |
| 21 | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 3.648s | pass |
| 22 | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | pass | 0.744s | pass |
| 23 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | pass | 1.241s | pass |
| 24 | `make verify PYTHON=python3` | pass | 12.775s | 734/734 standalone tests |

## Size And Organization

| file | baseline lines | current lines | reduced by | reduction | target | status |
|---|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner/scanner.py` | 13373 | 7744 | 5629 | 42.09% | <6500 | blocked |
| `tests/test_indicators.py` | 42498 | 1771 | 40727 | 95.83% | <2000 | pass |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 | 19 | 7126 | 99.73% | <100 | pass |
| `crypto_rsi_scanner/cli/services/event_alpha.py` | n/a | 46 | n/a | n/a | <1500 | n/a |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py` | n/a | 6363 | n/a | n/a | <1500 | n/a |

- top_level_event_module_count: `125`
- active_shims: `120`
- partial_shims: `0`
- unmigrated_modules: `5`
- active_shim_modules_with_implementation_logic: `0`
- migrated_modules_this_run_count: `25`
- scanner_bind_scanner_globals_call_sites: `7`
- cli_service_bind_scanner_globals_call_sites: `26`
- cli_event_alpha_service_lines: `46`
- scanner_command_body_functions_remaining: `105`
- remaining_implementation_modules_by_package_target: `{"artifacts": 1, "radar": 1, "shared_event_infra": 2}`
- intentionally_outside_event_alpha_modules: `crypto_rsi_scanner.event_fade`
- shared_event_infra_modules: ``

### CLI Service File Line Counts

| file | lines |
|---|---:|
| `crypto_rsi_scanner/cli/services/event_alpha.py` | 46 |
| `crypto_rsi_scanner/cli/services/event_alpha_fade_review.py` | 488 |
| `crypto_rsi_scanner/cli/services/event_alpha_integrated.py` | 474 |
| `crypto_rsi_scanner/cli/services/event_alpha_namespace.py` | 50 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` | 1668 |
| `crypto_rsi_scanner/cli/services/event_alpha_outcomes.py` | 318 |
| `crypto_rsi_scanner/cli/services/event_alpha_provider_preflights.py` | 71 |
| `crypto_rsi_scanner/cli/services/event_alpha_reports.py` | 291 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 851 |

## Migrated This Run

- `crypto_rsi_scanner.event_incident_graph`
- `crypto_rsi_scanner.event_identity`
- `crypto_rsi_scanner.event_graph`
- `crypto_rsi_scanner.event_resolver`
- `crypto_rsi_scanner.event_price_history`
- `crypto_rsi_scanner.event_catalyst_frame_validator`
- `crypto_rsi_scanner.event_anomaly_state`
- `crypto_rsi_scanner.event_anomaly_scanner`
- `crypto_rsi_scanner.event_market_units`
- `crypto_rsi_scanner.event_llm_budget`
- `crypto_rsi_scanner.event_llm_catalyst_frames_eval`
- `crypto_rsi_scanner.event_source_reliability`
- `crypto_rsi_scanner.event_cache`
- `crypto_rsi_scanner.event_alpha_explain`
- `crypto_rsi_scanner.event_alpha_quality_fields`
- `crypto_rsi_scanner.event_alpha_outcomes`
- `crypto_rsi_scanner.event_alpha_eval`
- `crypto_rsi_scanner.event_alpha_burn_in_checklist`
- `crypto_rsi_scanner.event_alpha_profiles`
- `crypto_rsi_scanner.event_alpha_v1_readiness`
- `crypto_rsi_scanner.event_alpha_preflight`
- `crypto_rsi_scanner.event_alpha_health_guard`
- `crypto_rsi_scanner.event_alpha_scheduler`
- `crypto_rsi_scanner.event_alpha_environment_doctor`
- `crypto_rsi_scanner.event_provider_status`

## Doctor And Namespace Coverage

- registered_checks: `None`
- legacy_unregistered: `15`
- legacy_unregistered_target: `5`
- legacy_unregistered_status: `documented_blocker`
- plugin_check_counts: `{"integrated_radar": 3, "namespace": 1, "notifications": 1, "outcomes": 1, "paths": 1, "provider_readiness": 2, "safety": 1, "source_coverage": 1, "stale_artifacts": 1}`
- namespace_count: `None`
- unknown_namespace_count: `None`
- namespace_status_counts: `null`

### Remaining Legacy-Unregistered Doctor Sites

| check | next plugin | reason |
|---|---|---|
| `missing_operational_run_rows` | `namespace.py or stale_artifacts.py` | Run-row absence drives strict doctor status and needs fixture coverage before registry migration. |
| `snapshot_availability_lineage_warnings` | `integrated_radar.py` | Snapshot availability distinguishes fixture, external, stale, and strict operational rows. |
| `orphan_alert_snapshot_run_ids` | `integrated_radar.py` | Alert snapshot lineage counters are compatibility-sensitive in strict and non-strict modes. |
| `legacy_alert_snapshot_lineage` | `stale_artifacts.py` | Legacy rows are intentionally tolerated in some scopes and blocked in others. |
| `feedback_without_matching_alert_snapshot` | `outcomes.py` | Feedback lineage severity depends on strict mode and latest-run filtering. |
| `outcomes_without_matching_alert_snapshot` | `outcomes.py` | Outcome lineage severity depends on strict mode and legacy artifact scope. |
| `mixed_artifact_namespaces` | `namespace.py` | Namespace-mixing behavior must preserve strict blocker versus warning semantics. |
| `multiple_artifact_namespaces_present` | `namespace.py` | Multiple namespaces are tolerated in audit modes but not strict current-run checks. |
| `multiple_profiles_present` | `namespace.py` | Profile-mixing is currently warning-only and should stay compatible. |
| `provider_health_missing_for_live_profile` | `provider_readiness.py` | Provider health rows are required only for selected live/burn-in profile families. |
| `llm_budget_rows_missing_for_llm_profile` | `provider_readiness.py` | Budget telemetry is warning-only for LLM profiles and must not block no-key paths. |
| `invalid_canonical_incident_rows` | `integrated_radar.py` | Incident linkage counters are shared with integrated-radar/card consistency checks. |
| `alertable_run_external_snapshot_path` | `paths.py` | External snapshot paths are blockers for operational rows but allowed for some fixture rows. |
| `fixture_snapshot_external_allowed` | `paths.py` | Fixture external snapshot rows remain warning-only under current doctor semantics. |
| `snapshot_availability_unknown_or_missing` | `integrated_radar.py` | Unknown or missing snapshot availability depends on run_mode and strictness. |

## Safety Invariants

- research_only: `true`
- no_live_provider_calls_by_default: `true`
- no_live_telegram_sends: `true`
- no_trading_paper_or_execution_changes: `true`
- no_event_alpha_normal_rsi_signal_writes: `true`
- no_event_alpha_created_triggered_fade: `true`
- triggered_fade_source: `event_fade.py + proxy_fade only`
- event_fade_remains_outside_event_alpha: `true`
- no_secrets_in_artifacts: `true`

## Known Remaining Blockers

### `crypto_rsi_scanner/scanner.py`

- blocker_reason: scanner.py still contains many historical Event Alpha command bodies and runtime config adapters that were only partially routed through cli/dispatch.py.
- next_migration_module: `crypto_rsi_scanner/cli/commands_event_alpha.py plus service modules for remaining scanner-bound command bodies`
- risk: Broad scanner command extraction can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.

### `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`

- blocker_reason: legacy_unregistered doctor append sites remain above the requested <=5 target.
- next_migration_module: `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py`
- risk: Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.

### `crypto_rsi_scanner/cli/services/event_alpha.py`

- blocker_reason: cli service bind_scanner_globals call sites were not reduced by the requested 50%.
- next_migration_module: `Replace scanner-global dependencies in the split Event Alpha service modules with explicit imports and focused dispatch monkeypatch tests.`
- risk: Removing the runtime binding too early can break historical helper/config resolution for Makefile-backed commands.

## RC Verdict

Critical behavior and safety checks pass. This continuation remains pending final refactor acceptance because scanner size, Event Alpha service bind-site reduction, and doctor legacy-unregistered targets are documented blockers.
