# Architecture Baseline

Static inventory and behavior-freeze contract for the Event Alpha architecture baseline.

This pass records current behavior and architecture before significant code movement. The generator reads repository files only; it does not invoke scanner/provider/runtime behavior.

## Safety Snapshot

- Static inventory only: `True`
- Behavior-changing code invoked: `False`
- Live provider calls allowed: `False`
- Telegram sends: `0`
- Trades created: `0`
- Paper trades created: `0`
- Normal RSI signal rows written: `0`
- Event Alpha TRIGGERED_FADE created: `0`

## Major File Line Counts

| file | lines |
|---|---:|
| `crypto_rsi_scanner/scanner.py` | 90 |
| `tests/test_indicators.py` | 913 |
| `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py` | 36 |

## Architecture Inventory

- Top-level `crypto_rsi_scanner/event_*.py` modules: `1`
- `crypto_rsi_scanner/event_alpha/` files: `445`
- `crypto_rsi_scanner/cli/` files: `60`
- `tests/` package files: `81`
- GitHub Actions workflows: `2`
- Event-related Makefile targets: `230`

### Event Alpha Package Files

- `crypto_rsi_scanner/event_alpha/MODULE_MAP.md`
- `crypto_rsi_scanner/event_alpha/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/models.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/outcomes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/reconciliation.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/serialization.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/snapshots.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alert_store/store.py`
- `crypto_rsi_scanner/event_alpha/artifacts/alerts.py`
- `crypto_rsi_scanner/event_alpha/artifacts/cache.py`
- `crypto_rsi_scanner/event_alpha/artifacts/context.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/api.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/builder.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/builder.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/diagnostics.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/market_anomalies.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/models.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/opportunity_lanes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/research_review.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/runtime.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/components/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/context.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/models.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/renderer.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/calibration.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/cards.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/derivatives.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/diagnostics.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/executive_summary.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/market_anomalies.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/official_exchange.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/opportunity_lanes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/outcomes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/readiness.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/research_review.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/scheduled_catalysts.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/sections/unlocks.py`
- `crypto_rsi_scanner/event_alpha/artifacts/explain.py`
- `crypto_rsi_scanner/event_alpha/artifacts/locks.py`
- `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py`
- `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit_matching.py`
- `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit_values.py`
- `crypto_rsi_scanner/event_alpha/artifacts/paths.py`
- `crypto_rsi_scanner/event_alpha/artifacts/reason_text.py`
- `crypto_rsi_scanner/event_alpha/artifacts/replay.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/api.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/diagnostics.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/evidence.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/index.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/market_state.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/models.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/outcomes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/renderer.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/runtime.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/components/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/index.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/lineage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/models.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/renderer.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/audit.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/derivatives.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/diagnostics.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/evidence.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/feedback.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/header.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/market_state.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/opportunity_lane.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/outcomes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/research_cards/sections/unlocks.py`
- `crypto_rsi_scanner/event_alpha/artifacts/retention.py`
- `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/base.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/calibration.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/core_opportunity.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/delivery.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/derivatives.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/fields.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/integrated_candidate.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/market.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/namespace.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/official_exchange.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/outcomes.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/provider_readiness.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/registry.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/run_ledger.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/scheduled_catalyst.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema/validators.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py`
- `crypto_rsi_scanner/event_alpha/cli/__init__.py`
- `crypto_rsi_scanner/event_alpha/config/__init__.py`
- `crypto_rsi_scanner/event_alpha/config/health_guard.py`
- `crypto_rsi_scanner/event_alpha/config/preflight.py`
- `crypto_rsi_scanner/event_alpha/config/profiles.py`
- `crypto_rsi_scanner/event_alpha/config/scheduler.py`
- `crypto_rsi_scanner/event_alpha/config/v1_readiness.py`
- `crypto_rsi_scanner/event_alpha/doctor/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/aggregation.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/context_loading.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/integrated_radar_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/namespace_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/notification_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/notification_delivery_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/outcome_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/provider_readiness_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/reporting.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/result_fields.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/result_models.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/runtime.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_parts/source_coverage_checks.py`
- `crypto_rsi_scanner/event_alpha/doctor/check_registry.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/_utils.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/integrated_radar.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/namespace.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/notifications.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/operations.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/outcomes.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/paths.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/provider_readiness.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/safety.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/secrets.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/doctor/checks/stale_artifacts.py`
- `crypto_rsi_scanner/event_alpha/doctor/consistency_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/context.py`
- `crypto_rsi_scanner/event_alpha/doctor/counters.py`
- `crypto_rsi_scanner/event_alpha/doctor/discovery.py`
- `crypto_rsi_scanner/event_alpha/doctor/environment.py`
- `crypto_rsi_scanner/event_alpha/doctor/execution.py`
- `crypto_rsi_scanner/event_alpha/doctor/issues.py`
- `crypto_rsi_scanner/event_alpha/doctor/namespace_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/report.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/blockers.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/integrated_radar.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/namespace.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/notifications.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/outcomes.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/paths.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/provider_readiness.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/registry.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/safety.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/schema.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/source_coverage.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/stale.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/summary.py`
- `crypto_rsi_scanner/event_alpha/doctor/report_sections/warnings.py`
- `crypto_rsi_scanner/event_alpha/doctor/result.py`
- `crypto_rsi_scanner/event_alpha/doctor/safety_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/schema_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/status.py`
- `crypto_rsi_scanner/event_alpha/namespace/__init__.py`
- `crypto_rsi_scanner/event_alpha/namespace/lifecycle.py`
- `crypto_rsi_scanner/event_alpha/namespace/status.py`
- `crypto_rsi_scanner/event_alpha/notifications/__init__.py`
- `crypto_rsi_scanner/event_alpha/notifications/candidate_selection.py`
- `crypto_rsi_scanner/event_alpha/notifications/checklist.py`
- `crypto_rsi_scanner/event_alpha/notifications/delivery.py`
- `crypto_rsi_scanner/event_alpha/notifications/delivery_writer.py`
- `crypto_rsi_scanner/event_alpha/notifications/final_check.py`
- `crypto_rsi_scanner/event_alpha/notifications/formatting.py`
- `crypto_rsi_scanner/event_alpha/notifications/go_no_go.py`
- `crypto_rsi_scanner/event_alpha/notifications/heartbeat.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/__init__.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/builder.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/feedback_targets.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/helpers.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/models.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/queue.py`
- `crypto_rsi_scanner/event_alpha/notifications/inbox/render.py`
- `crypto_rsi_scanner/event_alpha/notifications/message_rendering.py`
- `crypto_rsi_scanner/event_alpha/notifications/models.py`
- `crypto_rsi_scanner/event_alpha/notifications/pack.py`
- `crypto_rsi_scanner/event_alpha/notifications/pause.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_core.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/__init__.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/delivery_models.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/delivery_writer.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/heartbeat.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/message_renderer.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/preview_writer.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/research_review_selection.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/runtime.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/send_plan.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/utilities.py`
- `crypto_rsi_scanner/event_alpha/notifications/plan_builder.py`
- `crypto_rsi_scanner/event_alpha/notifications/preview_writer.py`
- `crypto_rsi_scanner/event_alpha/notifications/provider_status.py`
- `crypto_rsi_scanner/event_alpha/notifications/readiness.py`
- `crypto_rsi_scanner/event_alpha/notifications/recipient_check.py`
- `crypto_rsi_scanner/event_alpha/notifications/research_review_selection.py`
- `crypto_rsi_scanner/event_alpha/notifications/router.py`
- `crypto_rsi_scanner/event_alpha/notifications/router_rendering.py`
- `crypto_rsi_scanner/event_alpha/notifications/runs.py`
- `crypto_rsi_scanner/event_alpha/notifications/safety.py`
- `crypto_rsi_scanner/event_alpha/notifications/sender.py`
- `crypto_rsi_scanner/event_alpha/notifications/skip_telemetry.py`
- `crypto_rsi_scanner/event_alpha/notifications/slo.py`
- `crypto_rsi_scanner/event_alpha/notifications/watchlist_monitor.py`
- `crypto_rsi_scanner/event_alpha/operations/__init__.py`
- `crypto_rsi_scanner/event_alpha/operations/archive.py`
- `crypto_rsi_scanner/event_alpha/operations/candidate_mode_smoke.py`
- `crypto_rsi_scanner/event_alpha/operations/common.py`
- `crypto_rsi_scanner/event_alpha/operations/daily_burn_in.py`
- `crypto_rsi_scanner/event_alpha/operations/daily_burn_in_doctor.py`
- `crypto_rsi_scanner/event_alpha/operations/daily_burn_in_guardrails.py`
- `crypto_rsi_scanner/event_alpha/operations/daily_burn_in_plan.py`
- `crypto_rsi_scanner/event_alpha/operations/daily_burn_in_readiness.py`
- `crypto_rsi_scanner/event_alpha/operations/evidence_semantics.py`
- `crypto_rsi_scanner/event_alpha/operations/feedback_progress.py`
- `crypto_rsi_scanner/event_alpha/operations/measurement.py`
- `crypto_rsi_scanner/event_alpha/operations/namespace_policy.py`
- `crypto_rsi_scanner/event_alpha/operations/review_inbox.py`
- `crypto_rsi_scanner/event_alpha/operations/scorecard.py`
- `crypto_rsi_scanner/event_alpha/operations/source_yield.py`
- `crypto_rsi_scanner/event_alpha/outcomes/__init__.py`
- `crypto_rsi_scanner/event_alpha/outcomes/burn_in.py`
- `crypto_rsi_scanner/event_alpha/outcomes/burn_in_checklist.py`
- `crypto_rsi_scanner/event_alpha/outcomes/calibration.py`
- `crypto_rsi_scanner/event_alpha/outcomes/eval.py`
- `crypto_rsi_scanner/event_alpha/outcomes/feedback.py`
- `crypto_rsi_scanner/event_alpha/outcomes/feedback_labels.py`
- `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py`
- `crypto_rsi_scanner/event_alpha/outcomes/outcome_artifacts.py`
- `crypto_rsi_scanner/event_alpha/outcomes/policy_simulator.py`
- `crypto_rsi_scanner/event_alpha/outcomes/priors.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/__init__.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/case_eval.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/coverage.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/exports.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/models.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/reports.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality/scoring.py`
- `crypto_rsi_scanner/event_alpha/outcomes/quality_fields.py`
- `crypto_rsi_scanner/event_alpha/providers/__init__.py`
- `crypto_rsi_scanner/event_alpha/providers/bybit_announcements_preflight.py`
- `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py`
- `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight_ledger.py`
- `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight_report.py`
- `crypto_rsi_scanner/event_alpha/providers/cryptopanic.py`
- `crypto_rsi_scanner/event_alpha/providers/dex_onchain_readiness.py`
- `crypto_rsi_scanner/event_alpha/providers/health/__init__.py`
- `crypto_rsi_scanner/event_alpha/providers/health/base.py`
- `crypto_rsi_scanner/event_alpha/providers/health/derivatives_provider.py`
- `crypto_rsi_scanner/event_alpha/providers/health/event_provider.py`
- `crypto_rsi_scanner/event_alpha/providers/health/universe_provider.py`
- `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py`
- `crypto_rsi_scanner/event_alpha/providers/official_exchange.py`
- `crypto_rsi_scanner/event_alpha/providers/official_exchange_activation.py`
- `crypto_rsi_scanner/event_alpha/providers/provider_health.py`
- `crypto_rsi_scanner/event_alpha/providers/provider_health_core.py`
- `crypto_rsi_scanner/event_alpha/providers/source_packs.py`
- `crypto_rsi_scanner/event_alpha/providers/source_registry.py`
- `crypto_rsi_scanner/event_alpha/providers/source_reliability.py`
- `crypto_rsi_scanner/event_alpha/providers/unlock_calendar_preflight.py`
- `crypto_rsi_scanner/event_alpha/radar/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/anomaly_scanner.py`
- `crypto_rsi_scanner/event_alpha/radar/anomaly_state.py`
- `crypto_rsi_scanner/event_alpha/radar/asset_registry.py`
- `crypto_rsi_scanner/event_alpha/radar/canonical_asset.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_frame_validator.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_frames.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/executor.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/fixtures.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/identity.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/ledger.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/models.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/query_builder.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/report.py`
- `crypto_rsi_scanner/event_alpha/radar/catalyst_search/scoring.py`
- `crypto_rsi_scanner/event_alpha/radar/claim_semantics.py`
- `crypto_rsi_scanner/event_alpha/radar/classification.py`
- `crypto_rsi_scanner/event_alpha/radar/core/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/core/aggregation.py`
- `crypto_rsi_scanner/event_alpha/radar/core/card_links.py`
- `crypto_rsi_scanner/event_alpha/radar/core/evidence_fields.py`
- `crypto_rsi_scanner/event_alpha/radar/core/merge.py`
- `crypto_rsi_scanner/event_alpha/radar/core/models.py`
- `crypto_rsi_scanner/event_alpha/radar/core/path_fields.py`
- `crypto_rsi_scanner/event_alpha/radar/core/serialization.py`
- `crypto_rsi_scanner/event_alpha/radar/core/store.py`
- `crypto_rsi_scanner/event_alpha/radar/core/store_api.py`
- `crypto_rsi_scanner/event_alpha/radar/core/validators.py`
- `crypto_rsi_scanner/event_alpha/radar/core_opportunities.py`
- `crypto_rsi_scanner/event_alpha/radar/core_opportunity_store.py`
- `crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/api.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/loader.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/manual.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/models.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/providers.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/report.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/sample.py`
- `crypto_rsi_scanner/event_alpha/radar/discovery/snapshots.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/acquisition_api.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/executor.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/models.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/planner.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/providers.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/report.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/scoring.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/serialization.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/validators.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence/verdicts.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence_acquisition.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence_quality.py`
- `crypto_rsi_scanner/event_alpha/radar/graph.py`
- `crypto_rsi_scanner/event_alpha/radar/identity.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/api.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/assets.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/builder.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/candidates.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/family.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/generation.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/inbox.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/lineage.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/models.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/report.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/rules.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/scoring.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/store.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/validation.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_hypothesis_store.py`
- `crypto_rsi_scanner/event_alpha/radar/impact_path_validator.py`
- `crypto_rsi_scanner/event_alpha/radar/incident_graph.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/canonical.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/linkage.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/models.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/relevance.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/report.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/store.py`
- `crypto_rsi_scanner/event_alpha/radar/incidents/subject_quality.py`
- `crypto_rsi_scanner/event_alpha/radar/instrument_resolver.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/api.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/artifact_writer.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/context.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/cycle.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/family.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/inputs.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/manifest.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/merge.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/models.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/cycle.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/merge.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/merge_policy.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/models.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/report.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/runtime.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/sidecars.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/pipeline_parts/utilities.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/policy.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/report.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated/sidecars.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated_radar.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/analyzer.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/budget.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/catalyst_frames.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/catalyst_frames_eval.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/eval.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/evidence_planner.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/extract_eval.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/extraction_models.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/extractor.py`
- `crypto_rsi_scanner/event_alpha/radar/llm/models.py`
- `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py`
- `crypto_rsi_scanner/event_alpha/radar/market_confirmation.py`
- `crypto_rsi_scanner/event_alpha/radar/market_enrichment.py`
- `crypto_rsi_scanner/event_alpha/radar/market_reaction.py`
- `crypto_rsi_scanner/event_alpha/radar/market_state.py`
- `crypto_rsi_scanner/event_alpha/radar/market_units.py`
- `crypto_rsi_scanner/event_alpha/radar/missed.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/api.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/candidates.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/models.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/refresh.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/report.py`
- `crypto_rsi_scanner/event_alpha/radar/near_miss/utils.py`
- `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py`
- `crypto_rsi_scanner/event_alpha/radar/pipeline.py`
- `crypto_rsi_scanner/event_alpha/radar/pipeline_models.py`
- `crypto_rsi_scanner/event_alpha/radar/pipeline_report.py`
- `crypto_rsi_scanner/event_alpha/radar/playbooks.py`
- `crypto_rsi_scanner/event_alpha/radar/price_history.py`
- `crypto_rsi_scanner/event_alpha/radar/resolver.py`
- `crypto_rsi_scanner/event_alpha/radar/scheduled_catalysts.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/builder.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/models.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/provider_status.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/recommendations.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/report.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage/serialization.py`
- `crypto_rsi_scanner/event_alpha/radar/source_enrichment.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/api.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/models.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/outcomes.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/queue.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/report.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/review.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/sample.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/templates.py`
- `crypto_rsi_scanner/event_alpha/radar/validation/utils.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/api.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/builders.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/enrichment.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/market.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/models.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/quality_caps.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist/report.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist_enrichment.py`
- `crypto_rsi_scanner/event_alpha/radar/watchlist_market.py`
- `crypto_rsi_scanner/event_alpha/shim_cache.py`
- `crypto_rsi_scanner/event_alpha/shim_formatting.py`
- `crypto_rsi_scanner/event_alpha/shim_scan.py`
- `crypto_rsi_scanner/event_alpha/shims.py`

### CLI Package Files

- `crypto_rsi_scanner/cli/__init__.py`
- `crypto_rsi_scanner/cli/_scanner_bindings.py`
- `crypto_rsi_scanner/cli/commands_backtest.py`
- `crypto_rsi_scanner/cli/commands_event_alpha.py`
- `crypto_rsi_scanner/cli/commands_export.py`
- `crypto_rsi_scanner/cli/commands_maintenance.py`
- `crypto_rsi_scanner/cli/commands_paper.py`
- `crypto_rsi_scanner/cli/commands_provider_readiness.py`
- `crypto_rsi_scanner/cli/commands_rsi.py`
- `crypto_rsi_scanner/cli/dispatch.py`
- `crypto_rsi_scanner/cli/event_alpha_command_registry/__init__.py`
- `crypto_rsi_scanner/cli/event_alpha_command_registry/dispatch.py`
- `crypto_rsi_scanner/cli/event_alpha_command_registry/metadata.py`
- `crypto_rsi_scanner/cli/event_alpha_command_registry/models.py`
- `crypto_rsi_scanner/cli/main.py`
- `crypto_rsi_scanner/cli/parser.py`
- `crypto_rsi_scanner/cli/parser_backtest.py`
- `crypto_rsi_scanner/cli/parser_base.py`
- `crypto_rsi_scanner/cli/parser_event_alpha/__init__.py`
- `crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py`
- `crypto_rsi_scanner/cli/parser_export.py`
- `crypto_rsi_scanner/cli/parser_integrated_radar.py`
- `crypto_rsi_scanner/cli/parser_maintenance.py`
- `crypto_rsi_scanner/cli/parser_notifications.py`
- `crypto_rsi_scanner/cli/parser_paper.py`
- `crypto_rsi_scanner/cli/parser_provider_readiness.py`
- `crypto_rsi_scanner/cli/parser_rsi.py`
- `crypto_rsi_scanner/cli/services/__init__.py`
- `crypto_rsi_scanner/cli/services/event_alpha.py`
- `crypto_rsi_scanner/cli/services/event_alpha_fade_review.py`
- `crypto_rsi_scanner/cli/services/event_alpha_integrated.py`
- `crypto_rsi_scanner/cli/services/event_alpha_namespace.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/__init__.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/bindings.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/delivery_reports.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/final_check.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/fixture_smoke.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/fixture_smoke_data.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/go_no_go.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/pack_export.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py`
- `crypto_rsi_scanner/cli/services/event_alpha_notifications/send_readiness.py`
- `crypto_rsi_scanner/cli/services/event_alpha_outcomes.py`
- `crypto_rsi_scanner/cli/services/event_alpha_provider_preflights.py`
- `crypto_rsi_scanner/cli/services/event_alpha_reports.py`
- `crypto_rsi_scanner/cli/services/event_alpha_research.py`
- `crypto_rsi_scanner/cli/services/inventory.py`
- `crypto_rsi_scanner/cli/services/scanner_api.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/__init__.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/alerts.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/event_research.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/fade_review.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/provider_preflights.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/reports.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/rsi_scan.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/runtime.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/utility_calibration_exports.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/utility_commands.py`
- `crypto_rsi_scanner/cli/services/scanner_parts/utility_research_cards.py`

### Tests Package Files

- `tests/__init__.py`
- `tests/cli/__init__.py`
- `tests/cli/test_burn_in_make_targets.py`
- `tests/cli/test_dependency_ci.py`
- `tests/cli/test_dispatch.py`
- `tests/cli/test_event_alpha_command_registry.py`
- `tests/cli/test_event_alpha_operator_command_smoke.py`
- `tests/cli/test_make_targets.py`
- `tests/cli/test_ops_command_smoke.py`
- `tests/cli/test_parser.py`
- `tests/cli/test_relative_import_integrity.py`
- `tests/conftest.py`
- `tests/event_alpha/__init__.py`
- `tests/event_alpha/_api_helpers.py`
- `tests/event_alpha/conftest.py`
- `tests/event_alpha/test_alert_outcomes.py`
- `tests/event_alpha/test_artifact_schema.py`
- `tests/event_alpha/test_burn_in_candidate_mode.py`
- `tests/event_alpha/test_burn_in_contract_hermeticity.py`
- `tests/event_alpha/test_burn_in_operations.py`
- `tests/event_alpha/test_burn_in_outcomes.py`
- `tests/event_alpha/test_canonical_imports.py`
- `tests/event_alpha/test_catalyst_frames.py`
- `tests/event_alpha/test_catalyst_search.py`
- `tests/event_alpha/test_claim_semantics.py`
- `tests/event_alpha/test_core_opportunities.py`
- `tests/event_alpha/test_core_reconciliation.py`
- `tests/event_alpha/test_discovery_cache_reports.py`
- `tests/event_alpha/test_discovery_pipeline.py`
- `tests/event_alpha/test_doctor_core.py`
- `tests/event_alpha/test_doctor_notifications.py`
- `tests/event_alpha/test_doctor_provider_conflicts.py`
- `tests/event_alpha/test_doctor_quality.py`
- `tests/event_alpha/test_doctor_reconciliation.py`
- `tests/event_alpha/test_event_alert_ranking.py`
- `tests/event_alpha/test_evidence_acquisition.py`
- `tests/event_alpha/test_evidence_quality.py`
- `tests/event_alpha/test_exchange_universe_providers.py`
- `tests/event_alpha/test_fade_core.py`
- `tests/event_alpha/test_fade_review_workflows.py`
- `tests/event_alpha/test_fade_validation.py`
- `tests/event_alpha/test_feedback_calibration.py`
- `tests/event_alpha/test_impact_hypotheses.py`
- `tests/event_alpha/test_incident_relevance.py`
- `tests/event_alpha/test_integrated_merge_policy.py`
- `tests/event_alpha/test_llm_radar.py`
- `tests/event_alpha/test_market_data_providers.py`
- `tests/event_alpha/test_market_enrichment.py`
- `tests/event_alpha/test_market_surfaces.py`
- `tests/event_alpha/test_namespace_integrations.py`
- `tests/event_alpha/test_namespace_ledgers.py`
- `tests/event_alpha/test_namespace_profiles.py`
- `tests/event_alpha/test_news_providers.py`
- `tests/event_alpha/test_no_old_event_alpha_imports.py`
- `tests/event_alpha/test_notification_delivery.py`
- `tests/event_alpha/test_notification_inbox_rehearsals.py`
- `tests/event_alpha/test_notification_lanes.py`
- `tests/event_alpha/test_notification_operations.py`
- `tests/event_alpha/test_notification_planning.py`
- `tests/event_alpha/test_notification_readiness.py`
- `tests/event_alpha/test_notification_routing.py`
- `tests/event_alpha/test_operator_identity.py`
- `tests/event_alpha/test_operator_presentation.py`
- `tests/event_alpha/test_operator_workflows.py`
- `tests/event_alpha/test_playbooks_graph.py`
- `tests/event_alpha/test_provider_activation.py`
- `tests/event_alpha/test_quality_feedback.py`
- `tests/event_alpha/test_radar_pipeline.py`
- `tests/event_alpha/test_scheduled_catalyst_namespaces.py`
- `tests/event_alpha/test_shim_registry.py`
- `tests/event_alpha/test_source_coverage_reports.py`
- `tests/event_alpha/test_source_registry.py`
- `tests/event_alpha/test_watchlist_router.py`
- `tests/rsi/__init__.py`
- `tests/rsi/_api_helpers.py`
- `tests/rsi/test_backtest.py`
- `tests/rsi/test_backups.py`
- `tests/rsi/test_indicators_core.py`
- `tests/rsi/test_paper_risk.py`
- `tests/rsi/test_security.py`
- `tests/test_indicators.py`

### GitHub Actions Workflows

- `.github/workflows/event-alpha-smoke.yml`
- `.github/workflows/verify.yml`

### Event-Related Makefile Targets

- `event-alert-no-key-llm-report`
- `event-alert-no-key-report`
- `event-alert-no-key-send`
- `event-alpha-alerts-report`
- `event-alpha-archive-burn-in-evidence`
- `event-alpha-archive-stale-namespaces`
- `event-alpha-artifact-doctor`
- `event-alpha-burn-in-checklist`
- `event-alpha-burn-in-contract`
- `event-alpha-burn-in-llm`
- `event-alpha-burn-in-no-key`
- `event-alpha-burn-in-readiness`
- `event-alpha-burn-in-scorecard`
- `event-alpha-burn-in-weekly-measurement`
- `event-alpha-bybit-announcements-no-send-rehearsal`
- `event-alpha-bybit-announcements-preflight`
- `event-alpha-bybit-announcements-preflight-smoke`
- `event-alpha-calibration-export-priors`
- `event-alpha-calibration-report`
- `event-alpha-catalyst-frame-e2e-cycle`
- `event-alpha-catalyst-frame-validation-cycle`
- `event-alpha-coinalyze-no-send-rehearsal`
- `event-alpha-coinalyze-preflight`
- `event-alpha-coinalyze-preflight-smoke`
- `event-alpha-coinmarketcal-preflight`
- `event-alpha-cryptopanic-preflight`
- `event-alpha-cycle`
- `event-alpha-cycle-llm`
- `event-alpha-cycle-profile`
- `event-alpha-cycle-profile-send`
- `event-alpha-cycle-search`
- `event-alpha-cycle-search-llm`
- `event-alpha-cycle-send`
- `event-alpha-daily-brief`
- `event-alpha-daily-burn-in-readiness`
- `event-alpha-daily-live-no-send-burn-in`
- `event-alpha-daily-live-no-send-burn-in-candidate-mode-smoke`
- `event-alpha-daily-live-no-send-burn-in-candidate-mode-smoke-doctor`
- `event-alpha-daily-live-no-send-burn-in-plan`
- `event-alpha-daily-live-no-send-burn-in-smoke`
- `event-alpha-daily-llm-report`
- `event-alpha-daily-report`
- `event-alpha-daily-review-inbox`
- `event-alpha-daily-send`
- `event-alpha-day1-start`
- `event-alpha-day1-start-llm`
- `event-alpha-derivatives-report`
- `event-alpha-derivatives-smoke`
- `event-alpha-dex-onchain-readiness`
- `event-alpha-dex-onchain-readiness-smoke`
- `event-alpha-doctor-check-registry`
- `event-alpha-environment-doctor`
- `event-alpha-eval`
- `event-alpha-evidence-acquisition-smoke`
- `event-alpha-explain-last-run`
- `event-alpha-export-burn-in-pack`
- `event-alpha-export-eval-cases`
- `event-alpha-export-notification-pack`
- `event-alpha-export-signal-quality-cases`
- `event-alpha-fade-review-smoke`
- `event-alpha-feedback-progress`
- `event-alpha-feedback-readiness`
- `event-alpha-fill-outcomes`
- `event-alpha-frame-quality-loop`
- `event-alpha-generate-launchd`
- `event-alpha-health`
- `event-alpha-health-guard`
- `event-alpha-integrated-radar-calibration-export-priors`
- `event-alpha-integrated-radar-calibration-report`
- `event-alpha-integrated-radar-cycle`
- `event-alpha-integrated-radar-doctor`
- `event-alpha-integrated-radar-fill-outcomes`
- `event-alpha-integrated-radar-outcome-report`
- `event-alpha-integrated-radar-outcome-smoke`
- `event-alpha-integrated-radar-smoke`
- `event-alpha-launchd-template`
- `event-alpha-list-active-namespaces`
- `event-alpha-live-burn-in-no-send`
- `event-alpha-live-provider-readiness`
- `event-alpha-live-provider-readiness-smoke`
- `event-alpha-mark-known-stale-namespaces`
- `event-alpha-mark-namespace-stale`
- `event-alpha-market-anomaly-scan`
- `event-alpha-market-anomaly-smoke`
- `event-alpha-market-refresh-smoke`
- `event-alpha-messari-unlocks-preflight`
- `event-alpha-missed-report`
- `event-alpha-namespace-lifecycle-report`
- `event-alpha-near-miss-report`
- `event-alpha-no-key-report`
- `event-alpha-notification-checklist`
- `event-alpha-notification-deliveries-report`
- `event-alpha-notification-format-smoke`
- `event-alpha-notification-inbox`
- `event-alpha-notification-pause`
- `event-alpha-notification-retry-failed`
- `event-alpha-notification-runs-report`
- `event-alpha-notification-slo-report`
- `event-alpha-notify-cycle`
- `event-alpha-notify-fixture-smoke`
- `event-alpha-notify-go-no-go`
- `event-alpha-notify-llm`
- `event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal`
- `event-alpha-notify-llm-deep-fixture-rehearsal-artifacts`
- `event-alpha-notify-llm-deep-no-send-smoke`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal-fast`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate`
- `event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate`
- `event-alpha-notify-llm-deep-research-review-no-send-smoke`
- `event-alpha-notify-llm-deep-scheduled`
- `event-alpha-notify-llm-quality-frame-smoke`
- `event-alpha-notify-llm-quality-fresh-cycle`
- `event-alpha-notify-llm-quality-scheduled`
- `event-alpha-notify-llm-quality-validation-cycle`
- `event-alpha-notify-llm-scheduled`
- `event-alpha-notify-no-key`
- `event-alpha-notify-no-key-scheduled`
- `event-alpha-notify-preview`
- `event-alpha-notify-preview-from-artifacts`
- `event-alpha-notify-start-llm`
- `event-alpha-notify-start-no-key`
- `event-alpha-official-exchange-report`
- `event-alpha-official-exchange-smoke`
- `event-alpha-old-import-check`
- `event-alpha-open-items`
- `event-alpha-pause-notifications`
- `event-alpha-policy-simulate`
- `event-alpha-preflight`
- `event-alpha-priors-shadow-report`
- `event-alpha-provider-health-report`
- `event-alpha-provider-health-reset`
- `event-alpha-prune-artifacts`
- `event-alpha-prune-or-archive-stale-namespace`
- `event-alpha-quality-coverage-report`
- `event-alpha-quality-frame-live-smoke`
- `event-alpha-quality-live-smoke`
- `event-alpha-quality-loop`
- `event-alpha-quality-loop-llm`
- `event-alpha-quality-review`
- `event-alpha-quality-validation-cycle`
- `event-alpha-radar-north-star`
- `event-alpha-replay`
- `event-alpha-research-review-digest-smoke`
- `event-alpha-resume-notifications`
- `event-alpha-router-report`
- `event-alpha-runs-report`
- `event-alpha-scheduled-catalyst-report`
- `event-alpha-scheduled-catalyst-smoke`
- `event-alpha-scheduler-status`
- `event-alpha-send-go-no-go`
- `event-alpha-send-readiness`
- `event-alpha-send-test`
- `event-alpha-shim-dependency-report`
- `event-alpha-shim-report`
- `event-alpha-signal-quality-eval`
- `event-alpha-source-coverage-report`
- `event-alpha-source-yield-report`
- `event-alpha-status`
- `event-alpha-telegram-final-send-checklist`
- `event-alpha-telegram-no-send-final-check`
- `event-alpha-telegram-no-send-final-check-fast`
- `event-alpha-telegram-one-cycle-send-preflight`
- `event-alpha-telegram-post-send-audit`
- `event-alpha-telegram-recipient-check`
- `event-alpha-telegram-send-one-cycle`
- `event-alpha-telegram-send-readiness-final`
- `event-alpha-tokenomist-preflight`
- `event-alpha-tuning-worksheet`
- `event-alpha-unlock-risk-smoke`
- `event-alpha-v1-readiness`
- `event-alpha-weekly-review`
- `event-catalyst-search-fixture-report`
- `event-discovery-binance-listen`
- `event-discovery-refresh`
- `event-discovery-refresh-configured`
- `event-discovery-refresh-gdelt`
- `event-discovery-refresh-polymarket`
- `event-discovery-refresh-public-rss`
- `event-discovery-report`
- `event-discovery-runs`
- `event-discovery-status`
- `event-fade-apply-review-bundle`
- `event-fade-apply-review-template`
- `event-fade-auto-report`
- `event-fade-cache-review-bundle`
- `event-fade-check-review-bundle`
- `event-fade-check-review-template`
- `event-fade-configured-review-cycle`
- `event-fade-export-cache-sample`
- `event-fade-export-outcome-prices`
- `event-fade-export-review-template`
- `event-fade-export-sample`
- `event-fade-fill-outcomes`
- `event-fade-fill-review-bundle-outcomes`
- `event-fade-gdelt-review-cycle`
- `event-fade-labeling-queue`
- `event-fade-merge-sample`
- `event-fade-no-key-review-cycle`
- `event-fade-polymarket-review-cycle`
- `event-fade-public-rss-review-cycle`
- `event-fade-report`
- `event-fade-review-applied-bundle`
- `event-fade-review-bundle`
- `event-fade-review-cycle`
- `event-fade-review-packet`
- `event-fade-review-sample`
- `event-feedback-duplicate`
- `event-feedback-false-positive`
- `event-feedback-junk`
- `event-feedback-late`
- `event-feedback-needs-confirmation`
- `event-feedback-promising-source-type`
- `event-feedback-report`
- `event-feedback-source-noise`
- `event-feedback-useful`
- `event-feedback-watch`
- `event-impact-hypotheses-inbox`
- `event-impact-hypotheses-report`
- `event-impact-hypothesis-smoke`
- `event-incidents-report`
- `event-llm-eval`
- `event-llm-extract-eval`
- `event-opportunity-audit`
- `event-research-cards`
- `event-research-cards-write`
- `event-source-reliability-report`
- `event-watchlist-monitor`
- `event-watchlist-refresh`
- `event-watchlist-report`

## Namespace Inventory

- Base directory: `event_fade_cache`
- Namespace count: `52`
- Known stale namespaces: `notify_llm_deep`

| status | count |
|---|---:|
| `active_fixture_smoke` | 20 |
| `active_integrated_smoke` | 1 |
| `active_live_rehearsal` | 9 |
| `active_provider_preflight` | 5 |
| `active_provider_rehearsal` | 5 |
| `active_refactor_report` | 1 |
| `manual_review` | 4 |
| `quarantine` | 1 |
| `stale_deprecated` | 1 |
| `unknown` | 5 |

| namespace | status | stale | files | reason |
|---|---|---:|---:|---|
| `bybit_announcements_no_send_rehearsal` | `active_provider_rehearsal` | `False` | 5 | provider no-send rehearsal namespace |
| `bybit_announcements_preflight` | `active_provider_preflight` | `False` | 3 | provider preflight namespace |
| `bybit_announcements_preflight_smoke` | `active_fixture_smoke` | `False` | 3 | fixture smoke namespace |
| `catalyst_frame_e2e` | `unknown` | `False` | 7 | unclassified namespace |
| `catalyst_frame_validation` | `manual_review` | `False` | 7 | manual review or validation namespace |
| `coinalyze_no_send_rehearsal` | `active_provider_rehearsal` | `False` | 5 | provider no-send rehearsal namespace |
| `coinalyze_preflight` | `active_provider_preflight` | `False` | 3 | provider preflight namespace |
| `coinalyze_preflight_smoke` | `active_fixture_smoke` | `False` | 2 | fixture smoke namespace |
| `coinmarketcal_preflight` | `active_provider_preflight` | `False` | 3 | provider preflight namespace |
| `daily_burn_in_candidate_mode_smoke` | `active_fixture_smoke` | `False` | 20 | fixture smoke namespace |
| `daily_burn_in_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `derivatives_crowding_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `dex_onchain_readiness_smoke` | `active_fixture_smoke` | `False` | 10 | fixture smoke namespace |
| `evidence_acquisition_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `fade_review_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `fixture_notify_smoke` | `active_fixture_smoke` | `False` | 6 | fixture smoke namespace |
| `full_llm_live` | `active_live_rehearsal` | `False` | 1 | active no-send live rehearsal namespace |
| `integrated_radar_smoke` | `active_integrated_smoke` | `False` | 36 | current integrated radar smoke namespace |
| `live_burn_in_20260705` | `unknown` | `False` | 28 | unclassified namespace |
| `live_burn_in_20260706` | `unknown` | `False` | 28 | unclassified namespace |
| `live_burn_in_20260707` | `unknown` | `False` | 37 | unclassified namespace |
| `live_burn_in_20260709` | `unknown` | `False` | 31 | unclassified namespace |
| `live_burn_in_no_send` | `active_live_rehearsal` | `False` | 23 | active no-send live rehearsal namespace |
| `live_provider_readiness_smoke` | `active_fixture_smoke` | `False` | 2 | fixture smoke namespace |
| `market_anomaly_smoke` | `active_fixture_smoke` | `False` | 12 | fixture smoke namespace |
| `market_refresh_smoke` | `active_fixture_smoke` | `False` | 10 | fixture smoke namespace |
| `messari_unlocks_preflight` | `active_provider_preflight` | `False` | 3 | provider preflight namespace |
| `no_key_live` | `active_live_rehearsal` | `False` | 13 | active no-send live rehearsal namespace |
| `notification_format_smoke` | `active_fixture_smoke` | `False` | 6 | fixture smoke namespace |
| `notify_llm` | `active_live_rehearsal` | `False` | 11 | active no-send live rehearsal namespace |
| `notify_llm_deep` | `stale_deprecated` | `True` | 24 | pre-canonical notify_llm_deep artifacts; superseded by current rehearsal namespaces |
| `notify_llm_deep_cryptopanic_rehearsal` | `active_provider_rehearsal` | `False` | 31 | provider no-send rehearsal namespace |
| `notify_llm_deep_fixture_rehearsal` | `active_provider_rehearsal` | `False` | 7 | provider no-send rehearsal namespace |
| `notify_llm_deep_no_send_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `notify_llm_deep_rehearsal` | `active_provider_rehearsal` | `False` | 15 | provider no-send rehearsal namespace |
| `notify_llm_deep_research_review_smoke` | `active_fixture_smoke` | `False` | 10 | fixture smoke namespace |
| `notify_llm_quality` | `active_live_rehearsal` | `False` | 10 | active no-send live rehearsal namespace |
| `notify_llm_quality_frame` | `active_live_rehearsal` | `False` | 10 | active no-send live rehearsal namespace |
| `notify_llm_quality_frame_live_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `notify_llm_quality_fresh` | `active_live_rehearsal` | `False` | 10 | active no-send live rehearsal namespace |
| `notify_no_key` | `active_live_rehearsal` | `False` | 11 | active no-send live rehearsal namespace |
| `notify_no_key_format_preview` | `active_live_rehearsal` | `False` | 7 | active no-send live rehearsal namespace |
| `official_exchange_smoke` | `active_fixture_smoke` | `False` | 14 | fixture smoke namespace |
| `quality_validation` | `manual_review` | `False` | 7 | manual review or validation namespace |
| `research_review_digest_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `research_send` | `manual_review` | `False` | 1 | manual review or validation namespace |
| `scheduled_catalyst_smoke` | `active_fixture_smoke` | `False` | 11 | fixture smoke namespace |
| `shim_report` | `active_refactor_report` | `False` | 3 | refactor/report namespace |
| `source_enrichment` | `manual_review` | `False` | 170 | manual review or validation namespace |
| `tmp_nonexistent_cli_test` | `quarantine` | `False` | 3 | temporary test namespace; not part of active lifecycle |
| `tokenomist_preflight` | `active_provider_preflight` | `False` | 3 | provider preflight namespace |
| `unlock_risk_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |

## Behavior Freeze Contract

- CLI flags must remain compatible.
- Makefile targets must remain compatible.
- Old import paths must remain compatible.
- Artifact schema changes must be additive unless a migration is explicit.
- Doctor strict/WARN semantics must remain compatible.

## Artifact Contract

- Declared schema contract: `event_alpha_schema_v1`
- Schema module: `crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py`
- Doctor check registry module: `crypto_rsi_scanner/event_alpha/doctor/check_registry.py`
- Schema changes: `additive_only_unless_explicit_migration`

## Architecture Success Gates

| gate | target | current | status |
|---|---|---:|---|
| scanner.py reduced below 2000 lines by final phase | `<2000` | 90 | `baseline_recorded` |
| tests/test_indicators.py becomes umbrella runner below 2000 lines by final phase | `<2000` | 913 | `baseline_recorded` |
| event_alpha/doctor/artifact_doctor.py remains public orchestrator below 300 lines by final phase | `<300` | 36 | `baseline_recorded` |
| pytest-compatible test package exists | `exists` | true | `present` |
| schema v1 is the declared artifact contract | `exists` | true | `present` |
| every doctor check declares schema dependencies | `exists` | true | `present` |
| namespace lifecycle report exists and marks stale namespaces | `exists` | true | `present` |
| GitHub Actions runs make verify safely | `contains make verify PYTHON=python3` | true | `present` |

## GitHub Actions Safety

- `make verify PYTHON=python3` present: `True`
- Forbidden live/secret terms present: `[]`

## Machine-Readable Artifact

- `research/ARCHITECTURE_BASELINE.json` is the machine-readable companion for this report.
