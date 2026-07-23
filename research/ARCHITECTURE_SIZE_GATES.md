# Architecture Size Inventory

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-23T04:07:52.712478+00:00`
- gate_status: `pass`
- enforcement_status: `quantitative_limits_advisory_only`
- blocking_scope: `non_size_module_ownership_only`
- baseline_present: `true`
- files_over_limit_count: `21`
- v3_gate_status: `pass`
- v3_auto_accept_ready: `True`
- v3_blockers: `[]`
- production_files_over_1200_lines: `45`
- accepted_production_files_over_1200_lines: `25`
- unresolved_production_files_over_1200_lines: `20`
- production_size_gate_status: `advisory`
- production_files_over_1500_lines: `12`
- production_files_over_2000_lines: `5`
- production_files_over_3000_lines: `1`
- production_classes_over_limit: `8`
- production_functions_over_limit: `40`
- test_size_gate_status: `advisory`
- test_files_over_1500_lines: `9`
- classes_over_limit_count: `8`
- functions_over_limit_count: `40`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `5`
- modules_with_multiple_public_classes_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- multi_public_class_modules_count: `85`
- accepted_model_bundles_count: `84`
- unresolved_multi_class_modules_count: `0`
- new_violation_count: `66`
- moved_existing_violation_count: `0`
- api_decomposition_gate_status: `advisory`
- api_files_over_1500_lines: `0`
- api_files_over_3000_lines: `0`
- api_total_lines: `0`
- api_classes_over_limit: `0`
- api_functions_over_limit: `0`
- api_modules_with_multiple_public_classes: `0`

## Policy

- File, function, and class line counts are advisory measurements only.
- Historical 1,200/1,500/2,000/3,000-line references remain solely for trend comparison.
- Quantitative growth never blocks development, architecture cleanliness, or release.
- Test and transitional implementation sizes are likewise advisory.
- New production modules with multiple public classes are blockers unless registered as accepted model bundles.
- Baseline refresh is optional and exists only for an explicit trend snapshot.

## New Violations

| category | id | lines/count |
|---|---|---:|
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py` | 2741 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py` | 2484 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/dashboard/campaign_page.py` | 1886 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality.py` | 1888 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py` | 1715 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1986 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py` | 1546 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py` | 4059 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1539 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1720 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/market_history.py` | 2234 |
| `file_over_1500_lines` | `file:crypto_rsi_scanner/event_alpha/radar/market_shadow_surprise.py` | 2369 |
| `file_over_1500_lines` | `file:tests/cli/test_make_targets.py` | 1576 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_burn_in_operations.py` | 1549 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_decision_model_v2.py` | 3021 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_impact_hypotheses.py` | 1588 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_market_history.py` | 1660 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_market_no_send.py` | 1504 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_market_observation_campaign.py` | 2327 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_market_shadow_surprise.py` | 1980 |
| `file_over_1500_lines` | `file:tests/event_alpha/test_market_surfaces.py` | 1984 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/lean_radar/dashboard.py:LeanRadarDashboardApp` | 79 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/lean_radar/models.py:MarketSnapshot` | 78 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/lean_radar/models.py:LeanIdea` | 104 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/lean_radar/models.py:LeanOutcome` | 123 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/lean_radar/store.py:LeanRadarStore` | 945 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/schema/decision_model.py:_validate_closed_projection` | 194 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py:_validate_return_interval_overlap` | 163 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py:_validate_return_feature_consistency` | 183 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py:_validate_input_trace` | 166 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py:_project_shadow_surprise_feature` | 161 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py:_project_control_regime_generation_audit` | 183 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_cost_residual.py:model_bybit_residual_execution_cost_sensitivity_scenario` | 195 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_fee.py:model_bybit_visible_book_taker_fee_scenario` | 166 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_funding.py:model_bybit_funding_settlement_scenario` | 169 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_funding.py:model_bybit_funding_interval_scenario` | 204 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_latency.py:model_bybit_decision_price_latency_scenario` | 177 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality.py:model_bybit_visible_book_round_trip` | 226 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/empirical_replay_core.py:_evaluate_observation` | 154 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2_progress.py:validate_current_progress` | 153 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2_progress.py:format_current_progress` | 319 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/execution_quality_readiness.py:build_execution_quality_readiness` | 168 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/execution_quality_readiness.py:_impact_cost_lines` | 246 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py:point_in_time_control_market_regime` | 170 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py:control_market_regime_input_diagnostic_valid` | 165 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py:build_campaign_report` | 171 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_regime_audit.py:build_control_regime_generation_audit` | 229 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_regime_audit.py:validate_control_regime_generation_audit` | 197 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py:format_campaign_report` | 154 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py:_shadow_surprise_audit_section` | 154 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:build_campaign_shadow_surprise_audit` | 209 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:validate_campaign_shadow_surprise_audit` | 167 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:_feature_coverage` | 195 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:_asset_feature_variation` | 185 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:_return_sampling_timing_summary` | 269 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:_validate_asset_feature_variation` | 153 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py:_validate_return_sampling_timing_summary` | 183 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/market_shadow_surprise.py:evaluate_shadow_temporal_surprise` | 161 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/market_state.py:snapshot_from_market_row` | 175 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_hypothesis_latest_score_components` | 153 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_row` | 160 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/lean_radar/cli.py:run` | 203 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/lean_radar/dashboard_data.py:load_dashboard_state` | 151 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/lean_radar/health.py:refresh_system_health` | 193 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/lean_radar/scan.py:run_scan` | 246 |
| `function_over_150_lines` | `function:crypto_rsi_scanner/lean_radar/universe.py:build_universe` | 181 |

## Architecture Gates

| gate | value | severity |
|---|---:|---|
| `nonessential_shims_remaining` | 0 | blocker |
| `old_path_internal_imports` | 0 | blocker |
| `old_path_test_imports` | 0 | blocker |
| `public_compatibility_shims` | 0 | informational |
| `shim_removal_blockers` | 0 | blocker |
| `deleted_shims` | 124 | informational |
| `production_files_over_1200_lines` | 45 | advisory |
| `production_files_over_1500_lines` | 12 | advisory |
| `public_classes_not_in_own_module` | 0 | blocker |
| `class_exceptions_remaining` | 3 | advisory |
| `functions_over_150_lines` | 40 | advisory |
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
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py` | 4059 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py` | 2741 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py` | 2484 |
| `crypto_rsi_scanner/event_alpha/radar/market_shadow_surprise.py` | 2369 |
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 2234 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1986 |
| `crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality.py` | 1888 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_page.py` | 1886 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1720 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py` | 1715 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py` | 1546 |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1539 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_controls.py` | 1498 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_outcomes.py` | 1492 |
| `crypto_rsi_scanner/event_alpha/operations/execution_quality_readiness.py` | 1485 |
| `crypto_rsi_scanner/event_alpha/operations/daily_operations.py` | 1484 |
| `crypto_rsi_scanner/event_alpha/radar/decision_model.py` | 1480 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_regime_audit.py` | 1469 |
| `crypto_rsi_scanner/event_alpha/radar/decision_model_surfaces.py` | 1462 |
| `crypto_rsi_scanner/config.py` | 1450 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_research_reports.py` | 1449 |
| `crypto_rsi_scanner/event_alpha/radar/decision_policy.py` | 1416 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_analysis.py` | 1410 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py` | 1397 |
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1392 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_policy_lab.py` | 1389 |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1371 |
| `crypto_rsi_scanner/event_alpha/operations/decision_review_timing.py` | 1337 |
| `crypto_rsi_scanner/event_alpha/dashboard/system_pages.py` | 1333 |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1313 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send.py` | 1310 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_review.py` | 1300 |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 |
| `crypto_rsi_scanner/project_health/radar_north_star.py` | 1283 |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1278 |
| `crypto_rsi_scanner/event_alpha/dashboard/calendar_page.py` | 1264 |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1263 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2_progress.py` | 1244 |

## Accepted Production Files Over 1200 Lines

| path | lines | reason | revisit |
|---|---:|---|---|
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 2234 | Pure temporal baseline evaluator keeps cadence, return anchors, and feature evidence in one closed calculation path. | When adding another baseline family or changing the observation-spacing contract. |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1986 | Canonical campaign aggregation reconciles attempts, generations, outcomes, publication receipts, and current authority without provider activity. | When the campaign report schema changes or another campaign family needs the same aggregation primitives. |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1539 | Closed official-calendar acquisition keeps per-source authorization, immutable bytes, partial-coverage receipts, and validation in one fail-closed boundary. | Revisit when adding another source or status family and cohesion or review evidence supports a split. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_controls.py` | 1498 | Pure outcome-blind control, benchmark, and missed-move selection freezes point-in-time eligibility before joining future outcomes. | Revisit when another control or benchmark family creates a cohesive boundary, with selection-digest parity tests in place. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_outcomes.py` | 1492 | Pure partition-bounded episode and path outcome calculation keeps fixed-start grouping, horizons, expiry, and benchmark alignment under one frozen protocol. | Revisit when intraday outcomes, another horizon family, or a schema revision creates a cohesive new boundary. |
| `crypto_rsi_scanner/event_alpha/operations/daily_operations.py` | 1484 | Daily Operations is the single fail-closed transaction boundary for readiness, generation, doctor, publication, restart, rollback, and terminal receipts. | Revisit before another scheduler shares the transaction phases or cohesion becomes unclear. |
| `crypto_rsi_scanner/config.py` | 1450 | Central environment/config contract; splitting risks import-time default and env-var behavior drift. | When a dedicated config-v2 migration freeze and env snapshot tests exist. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_research_reports.py` | 1449 | Closed seven-file research-report projection centralizes exact run bindings, cross-report validation, anchored reads, bounded summaries, and byte-stable rendering. | Split when report schema v2 or another report family is introduced, preserving whole-bundle and byte-for-byte validation fixtures. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_analysis.py` | 1410 | Pure descriptive episode analysis keeps fixed cohort, cost, monotonicity, operator-burden, and failure classification semantics together under one frozen protocol. | Split when the analysis schema changes or another cohort family is added, using digest-stable replay fixtures before moving helpers. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py` | 1397 | Read-once calendar snapshot validation keeps provenance, source coverage, secret checks, freshness, and publication projection in one security boundary. | When the live calendar container schema changes or a second publication format is introduced. |
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1392 | Static architecture report aggregator preserving compatibility aliases and existing gate counters. | Split when adding a new architecture report family or when report schema v2 removes historical aliases. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_policy_lab.py` | 1389 | Pure frozen shadow-policy, recommendation-seal, final-test, and chronological walk-forward evaluation with no production-policy mutation path. | Revisit when another scenario family or recommendation-seal/walk-forward schema change creates a cohesive new boundary. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | Route-gate decision logic is dense and behavior-critical for no-send notification eligibility. | When route-decision/gate snapshots cover every lane and quality-gate cap. |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1371 | Historical CLI report compatibility binder with broad scanner-service monkeypatch expectations. | When config/report command bodies move to focused service modules. |
| `crypto_rsi_scanner/event_alpha/dashboard/system_pages.py` | 1333 | The read-only health surface reconciles exact authority, maintenance, provider, request-ledger, and evidence-layer status without runtime inspection. | When health sections have independent golden render fixtures or the system-page contract reaches v2. |
| `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py` | 1313 | Provider/cache enrichment flow is a cohesive behavior-critical boundary. | When adding a new enrichment source or cache policy. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send.py` | 1310 | Safety-critical no-send generation orchestrator owns one bounded provider call and fail-closed publication assembly. | When adding another live-safe market provider or changing the generation transaction boundary. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_review.py` | 1300 | Pure bounded targeted-review selection keeps outcome-aware categories, evidence bindings, deterministic ranking, and queue finalization in one policy-neutral path. | Split when another review category family or feedback-ledger integration is proposed, with frozen queue-digest fixtures first. |
| `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py` | 1285 | Stable argparse flag bundle; splitting individual flag groups risks CLI default drift. | Next parser feature addition or when event-alpha flag groups can be snapshot-tested per submodule. |
| `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py` | 1278 | Deterministic derivatives crowding evaluator with tightly coupled fixture smoke coverage. | When adding a new derivatives metric family or crowding class. |
| `crypto_rsi_scanner/event_alpha/dashboard/calendar_page.py` | 1264 | The read-only calendar page keeps coverage, receipt, temporal, filter, and event-card truth in one server-rendered surface. | When the calendar page gains a new interaction family and has byte-stable page-section fixtures. |
| `crypto_rsi_scanner/event_alpha/shims.py` | 1263 | Static deleted-shim/tombstone registry and report writer; large by design and non-behavioral. | When deleted-shim reporting can be split from old-import linting without changing gate output. |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py` | 1261 | Legacy notification-plan compatibility core; no-send semantics are more important than churn. | When notification plan rows are covered by schema-level golden fixtures. |
| `crypto_rsi_scanner/event_alpha/artifacts/operator_state.py` | 1235 | Canonical operator-state hashing and exact revision ownership remain centralized and fail closed. | When operator-state schema v2 can split digest policy from revision persistence with byte-stable fixtures. |
| `crypto_rsi_scanner/event_alpha/dashboard/render.py` | 1204 | Central escaped dashboard route renderer preserves shared candidate filtering, exact authority badges, and fail-closed response layout across the read-only surface. | Split the remaining candidate and authority helpers when a dashboard interaction family changes, using page-level golden render fixtures. |

## Unresolved Production Files Over 1200 Lines

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py` | 4059 |
| `crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py` | 2741 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py` | 2484 |
| `crypto_rsi_scanner/event_alpha/radar/market_shadow_surprise.py` | 2369 |
| `crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality.py` | 1888 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_page.py` | 1886 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1720 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py` | 1715 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py` | 1546 |
| `crypto_rsi_scanner/event_alpha/operations/execution_quality_readiness.py` | 1485 |
| `crypto_rsi_scanner/event_alpha/radar/decision_model.py` | 1480 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_regime_audit.py` | 1469 |
| `crypto_rsi_scanner/event_alpha/radar/decision_model_surfaces.py` | 1462 |
| `crypto_rsi_scanner/event_alpha/radar/decision_policy.py` | 1416 |
| `crypto_rsi_scanner/event_alpha/operations/decision_review_timing.py` | 1337 |
| `crypto_rsi_scanner/project_health/radar_north_star.py` | 1283 |
| `crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2_progress.py` | 1244 |
| `crypto_rsi_scanner/event_alpha/dashboard/today_page.py` | 1240 |
| `crypto_rsi_scanner/event_fade.py` | 1232 |
| `crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality_capture.py` | 1222 |

## Largest Test Files

| path | lines |
|---|---:|
| `tests/event_alpha/test_decision_model_v2.py` | 3021 |
| `tests/event_alpha/test_market_observation_campaign.py` | 2327 |
| `tests/event_alpha/test_market_surfaces.py` | 1984 |
| `tests/event_alpha/test_market_shadow_surprise.py` | 1980 |
| `tests/event_alpha/test_market_history.py` | 1660 |
| `tests/event_alpha/test_impact_hypotheses.py` | 1588 |
| `tests/cli/test_make_targets.py` | 1576 |
| `tests/event_alpha/test_burn_in_operations.py` | 1549 |
| `tests/event_alpha/test_market_no_send.py` | 1504 |
| `tests/event_alpha/test_operator_state.py` | 1499 |
| `tests/event_alpha/test_radar_dashboard.py` | 1485 |
| `tests/event_alpha/test_artifact_schema.py` | 1482 |
| `tests/event_alpha/test_catalyst_frames.py` | 1480 |
| `tests/event_alpha/test_operator_workflows.py` | 1464 |
| `tests/event_alpha/test_provider_activation.py` | 1452 |
| `tests/event_alpha/test_core_opportunities.py` | 1431 |
| `tests/event_alpha/test_namespace_integrations.py` | 1422 |
| `tests/event_alpha/test_dashboard_campaign_operator_actions.py` | 1415 |
| `tests/event_alpha/test_evidence_acquisition.py` | 1405 |
| `tests/event_alpha/test_bybit_liquidation_capture.py` | 1369 |
| `tests/event_alpha/test_watchlist_router.py` | 1361 |
| `tests/event_alpha/test_fade_review_workflows.py` | 1319 |
| `tests/event_alpha/test_doctor_notifications.py` | 1298 |
| `tests/event_alpha/test_burn_in_outcomes.py` | 1289 |
| `tests/event_alpha/test_catalyst_search.py` | 1270 |
| `tests/event_alpha/test_tokenomist_v5_capture.py` | 1247 |
| `tests/event_alpha/test_daily_operations.py` | 1230 |
| `tests/event_alpha/test_decision_review_timing.py` | 1210 |
| `tests/event_alpha/test_news_providers.py` | 1210 |
| `tests/event_alpha/test_doctor_provider_conflicts.py` | 1206 |
| `tests/event_alpha/test_discovery_pipeline.py` | 1182 |
| `tests/event_alpha/test_execution_quality_readiness.py` | 1182 |
| `tests/event_alpha/test_market_observation_campaign_episodes.py` | 1178 |
| `tests/event_alpha/test_radar_pipeline.py` | 1167 |
| `tests/event_alpha/test_empirical_research_reports.py` | 1138 |
| `tests/event_alpha/test_notification_inbox_rehearsals.py` | 1120 |
| `tests/event_alpha/test_evidence_quality.py` | 1096 |
| `tests/event_alpha/test_fade_validation.py` | 1081 |
| `tests/event_alpha/test_feedback_calibration.py` | 1069 |
| `tests/event_alpha/test_dashboard_readiness.py` | 1068 |

## Files Over 1500 Lines

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/artifacts/schema/market_shadow_surprise.py` | 2741 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_operator_actions.py` | 2484 |
| `crypto_rsi_scanner/event_alpha/dashboard/campaign_page.py` | 1886 |
| `crypto_rsi_scanner/event_alpha/operations/bybit_execution_quality.py` | 1888 |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_features.py` | 1715 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1986 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_render.py` | 1546 |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign_shadow_surprise.py` | 4059 |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1539 |
| `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py` | 1720 |
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 2234 |
| `crypto_rsi_scanner/event_alpha/radar/market_shadow_surprise.py` | 2369 |
| `tests/cli/test_make_targets.py` | 1576 |
| `tests/event_alpha/test_burn_in_operations.py` | 1549 |
| `tests/event_alpha/test_decision_model_v2.py` | 3021 |
| `tests/event_alpha/test_impact_hypotheses.py` | 1588 |
| `tests/event_alpha/test_market_history.py` | 1660 |
| `tests/event_alpha/test_market_no_send.py` | 1504 |
| `tests/event_alpha/test_market_observation_campaign.py` | 2327 |
| `tests/event_alpha/test_market_shadow_surprise.py` | 1980 |
| `tests/event_alpha/test_market_surfaces.py` | 1984 |

## Existing Violations

| category | id | lines/count |
|---|---|---:|
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/migrations.py:MigrationsMixin` | 88 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/signals.py:SignalsMixin` | 129 |
| `class_over_75_lines` | `class:crypto_rsi_scanner/storage_parts/watchlist.py:WatchlistMixin` | 89 |
