# Architecture Size Gates

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-15T09:37:42.341562+00:00`
- gate_status: `pass`
- baseline_present: `true`
- files_over_limit_count: `0`
- v3_gate_status: `accepted_with_documented_exceptions`
- v3_auto_accept_ready: `False`
- v3_blockers: `[]`
- production_files_over_1200_lines: `18`
- accepted_production_files_over_1200_lines: `18`
- unresolved_production_files_over_1200_lines: `0`
- production_size_gate_status: `warning`
- production_files_over_1500_lines: `0`
- production_files_over_2000_lines: `0`
- production_files_over_3000_lines: `0`
- production_classes_over_limit: `3`
- production_functions_over_limit: `0`
- test_size_gate_status: `pass`
- test_files_over_1500_lines: `0`
- classes_over_limit_count: `3`
- functions_over_limit_count: `0`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- multi_public_class_modules_count: `84`
- accepted_model_bundles_count: `83`
- unresolved_multi_class_modules_count: `0`
- new_violation_count: `0`
- moved_existing_violation_count: `0`
- api_decomposition_gate_status: `pass`
- api_files_over_1500_lines: `0`
- api_files_over_3000_lines: `0`
- api_total_lines: `0`
- api_classes_over_limit: `0`
- api_functions_over_limit: `0`
- api_modules_with_multiple_public_classes: `0`

## Policy

- Existing violations from `research/ARCHITECTURE_SIZE_BASELINE.json` are warnings.
- New file/function/class/module ownership violations are blockers.
- Architecture health targets production files below 1,200 lines.
- Production files over 1,200 lines are warnings and must either be split or documented.
- Architecture health treats production files over 1,500 lines as blockers unless explicitly accepted.
- Production files over 1,500 lines block architecture-complete status unless explicitly accepted.
- Production files over 2,000 lines remain a continuity threshold.
- Production files over 3,000 lines are blockers.
- Test file size debt is tracked separately and does not block architecture-complete status.
- Transitional implementation files over 1,500 lines are warnings.
- Transitional implementation files over 3,000 lines block architecture-complete status.
- New production modules with multiple public classes are blockers unless registered as accepted model bundles.
- Baseline updates require the explicit `make architecture-size-baseline-update` target.

## New Violations

| category | id | lines/count |
|---|---|---:|

## Architecture Gates

| gate | value | severity |
|---|---:|---|
| `nonessential_shims_remaining` | 0 | blocker |
| `old_path_internal_imports` | 0 | blocker |
| `old_path_test_imports` | 0 | blocker |
| `public_compatibility_shims` | 0 | informational |
| `shim_removal_blockers` | 0 | blocker |
| `deleted_shims` | 124 | informational |
| `production_files_over_1200_lines` | 18 | accepted_exception |
| `production_files_over_1500_lines` | 0 | blocker |
| `public_classes_not_in_own_module` | 0 | blocker |
| `class_exceptions_remaining` | 3 | accepted_exception |
| `functions_over_150_lines` | 0 | blocker |
| `old_path_docs_references` | 0 | blocker_unless_policy_scoped |
| `old_path_import_allowed_exceptions` | 0 | informational |

## Moved Existing Violations

| current id | baseline id |
|---|---|

## API Decomposition Gate

| path | lines |
|---|---:|

## Largest Production Files

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1496 |
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 1467 |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1466 |
| `crypto_rsi_scanner/event_alpha/operations/daily_operations.py` | 1465 |
| `crypto_rsi_scanner/config.py` | 1450 |
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1411 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py` | 1397 |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1338 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send.py` | 1305 |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 |
| `crypto_rsi_scanner/event_alpha/dashboard/calendar_page.py` | 1264 |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1263 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1247 |
| `crypto_rsi_scanner/event_alpha/dashboard/system_pages.py` | 1242 |
| `crypto_rsi_scanner/event_alpha/artifacts/operator_state.py` | 1231 |
| `crypto_rsi_scanner/event_alpha/dashboard/public_access.py` | 1200 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/cycle.py` | 1200 |
| `crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py` | 1199 |
| `crypto_rsi_scanner/cli/services/event_alpha_research.py` | 1199 |
| `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py` | 1198 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/report.py` | 1198 |
| `crypto_rsi_scanner/project_health/radar_north_star.py` | 1198 |
| `crypto_rsi_scanner/event_alpha/dashboard/render.py` | 1196 |
| `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py` | 1189 |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1187 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/registry.py` | 1185 |
| `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py` | 1181 |
| `crypto_rsi_scanner/event_fade.py` | 1181 |
| `crypto_rsi_scanner/event_alpha/outcomes/decision_episode_scorecard.py` | 1180 |
| `crypto_rsi_scanner/cli/services/scanner_parts/utility_commands.py` | 1176 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/builder.py` | 1176 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1175 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_episodes.py` | 1168 |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1168 |
| `crypto_rsi_scanner/event_alpha/dashboard/loader.py` | 1160 |
| `crypto_rsi_scanner/event_alpha/operations/review_inbox.py` | 1156 |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1149 |

## Accepted Production Files Over 1200 Lines

| path | lines | reason | revisit |
|---|---:|---|---|
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1496 | Canonical campaign aggregation reconciles attempts, generations, outcomes, publication receipts, and current authority without provider activity. | When the campaign report schema changes or another campaign family needs the same aggregation primitives. |
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 1467 | Pure temporal baseline evaluator keeps cadence, return anchors, and feature evidence in one closed calculation path. | When adding another baseline family or changing the observation-spacing contract. |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1466 | Closed official-calendar acquisition keeps per-source authorization, immutable bytes, partial-coverage receipts, and validation in one fail-closed boundary. | Split before adding another source or status family, and before any growth crosses the 1,500-line blocker. |
| `crypto_rsi_scanner/event_alpha/operations/daily_operations.py` | 1465 | Daily Operations is the single fail-closed transaction boundary for readiness, generation, doctor, publication, restart, rollback, and terminal receipts. | Split before any further lifecycle phase or growth approaches the 1,500-line blocker, and before another scheduler shares the transaction phases. |
| `crypto_rsi_scanner/config.py` | 1450 | Central environment/config contract; splitting risks import-time default and env-var behavior drift. | When a dedicated config-v2 migration freeze and env snapshot tests exist. |
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1411 | Static architecture report aggregator preserving compatibility aliases and existing gate counters. | Split when adding a new architecture report family or when report schema v2 removes historical aliases. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py` | 1397 | Read-once calendar snapshot validation keeps provenance, source coverage, secret checks, freshness, and publication projection in one security boundary. | When the live calendar container schema changes or a second publication format is introduced. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | Route-gate decision logic is dense and behavior-critical for no-send notification eligibility. | When route-decision/gate snapshots cover every lane and quality-gate cap. |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1338 | Historical CLI report compatibility binder with broad scanner-service monkeypatch expectations. | When config/report command bodies move to focused service modules. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send.py` | 1305 | Safety-critical no-send generation orchestrator owns one bounded provider call and fail-closed publication assembly. | When adding another live-safe market provider or changing the generation transaction boundary. |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 | Stable argparse flag bundle; splitting individual flag groups risks CLI default drift. | Next parser feature addition or when event-alpha flag groups can be snapshot-tested per submodule. |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1275 | Provider/cache enrichment flow is stable and below blocker threshold. | When adding a new enrichment source or cache policy. |
| `crypto_rsi_scanner/event_alpha/dashboard/calendar_page.py` | 1264 | The read-only calendar page keeps coverage, receipt, temporal, filter, and event-card truth in one server-rendered surface. | When the calendar page gains a new interaction family and has byte-stable page-section fixtures. |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1263 | Static deleted-shim/tombstone registry and report writer; large by design and non-behavioral. | When deleted-shim reporting can be split from old-import linting without changing gate output. |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 | Legacy notification-plan compatibility core; no-send semantics are more important than churn. | When notification plan rows are covered by schema-level golden fixtures. |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1247 | Deterministic derivatives crowding evaluator with tightly coupled fixture smoke coverage. | When adding a new derivatives metric family or crowding class. |
| `crypto_rsi_scanner/event_alpha/dashboard/system_pages.py` | 1242 | The read-only health surface reconciles exact authority, maintenance, provider, request-ledger, and evidence-layer status without runtime inspection. | When health sections have independent golden render fixtures or the system-page contract reaches v2. |
| `crypto_rsi_scanner/event_alpha/artifacts/operator_state.py` | 1231 | Canonical operator-state hashing and exact revision ownership remain centralized and fail closed. | When operator-state schema v2 can split digest policy from revision persistence with byte-stable fixtures. |

## Unresolved Production Files Over 1200 Lines

| path | lines |
|---|---:|
| none | 0 |

## Largest Test Files

| path | lines |
|---|---:|
| `tests/cli/test_make_targets.py` | 1500 |
| `tests/event_alpha/test_operator_state.py` | 1499 |
| `tests/event_alpha/test_burn_in_operations.py` | 1497 |
| `tests/event_alpha/test_market_no_send.py` | 1492 |
| `tests/event_alpha/test_market_surfaces.py` | 1483 |
| `tests/event_alpha/test_radar_dashboard.py` | 1461 |
| `tests/event_alpha/test_operator_workflows.py` | 1459 |
| `tests/event_alpha/test_provider_activation.py` | 1452 |
| `tests/event_alpha/test_catalyst_frames.py` | 1430 |
| `tests/event_alpha/test_artifact_schema.py` | 1427 |
| `tests/event_alpha/test_namespace_integrations.py` | 1421 |
| `tests/event_alpha/test_core_opportunities.py` | 1407 |
| `tests/event_alpha/test_fade_review_workflows.py` | 1309 |
| `tests/event_alpha/test_doctor_notifications.py` | 1298 |
| `tests/event_alpha/test_burn_in_outcomes.py` | 1289 |
| `tests/event_alpha/test_catalyst_search.py` | 1270 |
| `tests/event_alpha/test_evidence_acquisition.py` | 1214 |
| `tests/event_alpha/test_decision_model_v2.py` | 1210 |
| `tests/event_alpha/test_news_providers.py` | 1210 |
| `tests/event_alpha/test_watchlist_router.py` | 1207 |
| `tests/event_alpha/test_market_observation_campaign.py` | 1192 |
| `tests/event_alpha/test_daily_operations.py` | 1107 |
| `tests/event_alpha/test_radar_pipeline.py` | 1088 |
| `tests/event_alpha/test_fade_validation.py` | 1081 |
| `tests/event_alpha/test_feedback_calibration.py` | 1069 |
| `tests/event_alpha/test_notification_inbox_rehearsals.py` | 1068 |
| `tests/event_alpha/test_llm_radar.py` | 1040 |
| `tests/event_alpha/test_quality_feedback.py` | 1040 |
| `tests/test_indicators.py` | 1028 |
| `tests/event_alpha/test_market_observation_campaign_episodes.py` | 1022 |
| `tests/event_alpha/test_discovery_pipeline.py` | 993 |
| `tests/event_alpha/test_doctor_provider_conflicts.py` | 979 |
| `tests/event_alpha/test_notification_operations.py` | 925 |
| `tests/event_alpha/test_impact_hypotheses.py` | 920 |
| `tests/event_alpha/test_evidence_quality.py` | 918 |
| `tests/event_alpha/test_notification_routing.py` | 895 |
| `tests/event_alpha/test_official_macro_calendar_acquisition.py` | 890 |
| `tests/event_alpha/test_dashboard_readiness.py` | 883 |
| `tests/event_alpha/test_claim_semantics.py` | 867 |
| `tests/event_alpha/test_burn_in_candidate_mode.py` | 859 |

## Files Over 1500 Lines

| path | lines |
|---|---:|

## Existing Violations

| category | id | lines/count |
|---|---|---:|
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/migrations.py:MigrationsMixin` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/signals.py:SignalsMixin` | 129 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/watchlist.py:WatchlistMixin` | 89 |
