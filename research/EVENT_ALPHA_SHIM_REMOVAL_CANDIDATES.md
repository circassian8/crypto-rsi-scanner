# Event Alpha Shim Removal Candidates

Research artifact only. No shims are deleted by this report.

- generated_at: 2026-07-04T19:07:08.148690+00:00
- registry_entry_count: 39

Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create `TRIGGERED_FADE`. `TRIGGERED_FADE` belongs only to `event_fade.py` plus `proxy_fade`.

## Remove Now Candidates

- none

## Migrate Imports First

- none

## Keep Public Compatibility

- `crypto_rsi_scanner.event_alpha_artifacts` -> `crypto_rsi_scanner.event_alpha.artifacts.context` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_artifact_paths` -> `crypto_rsi_scanner.event_alpha.artifacts.paths` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_run_ledger` -> `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_retention` -> `crypto_rsi_scanner.event_alpha.artifacts.retention` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_run_lock` -> `crypto_rsi_scanner.event_alpha.artifacts.locks` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_artifact_doctor` -> `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_llm_extract_eval` -> `crypto_rsi_scanner.event_alpha.radar.llm.extract_eval` (keep_public_entrypoint; blockers: test_import_references, makefile_references)
- `crypto_rsi_scanner.event_llm_eval` -> `crypto_rsi_scanner.event_alpha.radar.llm.eval` (keep_public_entrypoint; blockers: test_import_references, makefile_references)
- `crypto_rsi_scanner.event_llm_catalyst_frames_eval` -> `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` (keep_public_entrypoint; blockers: test_import_references, makefile_references)
- `crypto_rsi_scanner.event_alpha_eval` -> `crypto_rsi_scanner.event_alpha.outcomes.eval` (keep_public_entrypoint; blockers: test_import_references, makefile_references)
- `crypto_rsi_scanner.event_alpha_profiles` -> `crypto_rsi_scanner.event_alpha.config.profiles` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_v1_readiness` -> `crypto_rsi_scanner.event_alpha.config.v1_readiness` (keep_public_entrypoint; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_preflight` -> `crypto_rsi_scanner.event_alpha.config.preflight` (keep_public_entrypoint; blockers: test_import_references)

## Keep Safety Exception

- `crypto_rsi_scanner.event_fade` -> `` (intentionally_external; blockers: safety_boundary_triggered_fade_owner)

## Keep Until Next Major Refactor

- `crypto_rsi_scanner.event_alpha_source_coverage` -> `crypto_rsi_scanner.event_alpha.radar.source_coverage` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_namespace_status` -> `crypto_rsi_scanner.event_alpha.namespace.status` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_incident_graph` -> `crypto_rsi_scanner.event_alpha.radar.incident_graph` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_identity` -> `crypto_rsi_scanner.event_alpha.radar.identity` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_graph` -> `crypto_rsi_scanner.event_alpha.radar.graph` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_resolver` -> `crypto_rsi_scanner.event_alpha.radar.resolver` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_price_history` -> `crypto_rsi_scanner.event_alpha.radar.price_history` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_catalyst_frame_validator` -> `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_anomaly_state` -> `crypto_rsi_scanner.event_alpha.radar.anomaly_state` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_anomaly_scanner` -> `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_market_units` -> `crypto_rsi_scanner.event_alpha.radar.market_units` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_llm_budget` -> `crypto_rsi_scanner.event_alpha.radar.llm.budget` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_source_reliability` -> `crypto_rsi_scanner.event_alpha.providers.source_reliability` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_cache` -> `crypto_rsi_scanner.event_alpha.artifacts.cache` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_explain` -> `crypto_rsi_scanner.event_alpha.artifacts.explain` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_quality_fields` -> `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_outcomes` -> `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_burn_in_checklist` -> `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_health_guard` -> `crypto_rsi_scanner.event_alpha.config.health_guard` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_scheduler` -> `crypto_rsi_scanner.event_alpha.config.scheduler` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_environment_doctor` -> `crypto_rsi_scanner.event_alpha.doctor.environment` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_provider_status` -> `crypto_rsi_scanner.event_alpha.notifications.provider_status` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_missed` -> `crypto_rsi_scanner.event_alpha.radar.missed` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_alpha_reason_text` -> `crypto_rsi_scanner.event_alpha.artifacts.reason_text` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_clock` -> `crypto_rsi_scanner.event_core.clock` (keep_until_v3; blockers: test_import_references)
- `crypto_rsi_scanner.event_models` -> `crypto_rsi_scanner.event_core.models` (keep_until_v3; blockers: test_import_references)
