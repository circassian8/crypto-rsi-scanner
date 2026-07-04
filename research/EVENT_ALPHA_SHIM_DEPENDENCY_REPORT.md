# Event Alpha Shim Dependency Report

Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: 2026-07-04T19:07:08.148690+00:00
- status: OK
- registry_entry_count: 39
- internal_import_reference_count: 0
- test_import_reference_count: 50
- makefile_reference_count: 8
- docs_reference_count: 43
- dynamic_import_reference_count: 0
- safe_to_remove_count: 0
- deleted_shims: 85
- old_path_internal_imports: 0
- old_path_test_imports: 0
- old_path_docs_references: 0
- old_path_import_allowed_exceptions: 49
- active_shim_modules_with_implementation_logic: 0
- v3_gate_status: pending
- v3_auto_accept_ready: False

## Policy

- New implementation code must import new package paths, not old top-level Event Alpha shim paths.
- Old shims stay available during v1/v2 compatibility and may be removed only after zero internal references and an accepted removal release.
- `scanner.py` may remain a compatibility CLI entrypoint.
- `event_fade.py` remains intentionally outside Event Alpha; Event Alpha may write `FADE_SHORT_REVIEW` research but must not create `TRIGGERED_FADE`.

## Refactor V3 Shim Gates

| gate | value |
|---|---:|
| `nonessential_shims_remaining` | 26 |
| `old_path_internal_imports` | 0 |
| `old_path_test_imports` | 0 |
| `public_compatibility_shims` | 13 |
| `shim_removal_blockers` | 26 |
| `deleted_shims` | 85 |
| `old_path_docs_references` | 0 |
| `old_path_import_allowed_exceptions` | 49 |

## Registry Dependencies

| old module | new module | status | internal | tests | make | docs | dynamic | safe | action |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `crypto_rsi_scanner.event_alpha_source_coverage` | `crypto_rsi_scanner.event_alpha.radar.source_coverage` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | active_shim | 0 | 2 | 0 | 3 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_namespace_status` | `crypto_rsi_scanner.event_alpha.namespace.status` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_extract_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.extract_eval` | active_shim | 0 | 2 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_llm_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.eval` | active_shim | 0 | 2 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_incident_graph` | `crypto_rsi_scanner.event_alpha.radar.incident_graph` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_identity` | `crypto_rsi_scanner.event_alpha.radar.identity` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_graph` | `crypto_rsi_scanner.event_alpha.radar.graph` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_resolver` | `crypto_rsi_scanner.event_alpha.radar.resolver` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_price_history` | `crypto_rsi_scanner.event_alpha.radar.price_history` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_anomaly_state` | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_market_units` | `crypto_rsi_scanner.event_alpha.radar.market_units` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_budget` | `crypto_rsi_scanner.event_alpha.radar.llm.budget` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` | active_shim | 0 | 1 | 5 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_source_reliability` | `crypto_rsi_scanner.event_alpha.providers.source_reliability` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_cache` | `crypto_rsi_scanner.event_alpha.artifacts.cache` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_explain` | `crypto_rsi_scanner.event_alpha.artifacts.explain` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_quality_fields` | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_eval` | `crypto_rsi_scanner.event_alpha.outcomes.eval` | active_shim | 0 | 1 | 1 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_profiles` | `crypto_rsi_scanner.event_alpha.config.profiles` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | `crypto_rsi_scanner.event_alpha.config.v1_readiness` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_preflight` | `crypto_rsi_scanner.event_alpha.config.preflight` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_public_entrypoint |
| `crypto_rsi_scanner.event_alpha_health_guard` | `crypto_rsi_scanner.event_alpha.config.health_guard` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_scheduler` | `crypto_rsi_scanner.event_alpha.config.scheduler` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | `crypto_rsi_scanner.event_alpha.doctor.environment` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_provider_status` | `crypto_rsi_scanner.event_alpha.notifications.provider_status` | active_shim | 0 | 1 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_missed` | `crypto_rsi_scanner.event_alpha.radar.missed` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_alpha_reason_text` | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` | active_shim | 0 | 2 | 0 | 1 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_clock` | `crypto_rsi_scanner.event_core.clock` | active_shim | 0 | 3 | 0 | 2 | 0 | false | keep_until_v3 |
| `crypto_rsi_scanner.event_models` | `crypto_rsi_scanner.event_core.models` | active_shim | 0 | 3 | 0 | 2 | 0 | false | keep_until_v3 |

## Warnings

- none
