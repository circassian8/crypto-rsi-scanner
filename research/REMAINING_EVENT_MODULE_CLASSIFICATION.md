# Remaining Event Module Classification

Research-only refactor inventory. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-03T01:53:28+00:00`
- module_count: `30`
- recommended_status_counts: `{"active_shim": 29, "intentionally_outside_event_alpha": 1, "not_migrated": 0, "partial_shim": 0}`
- likely_package_home_counts: `{"artifacts": 3, "config": 5, "doctor": 1, "intentionally_outside_event_alpha": 1, "notifications": 1, "outcomes": 4, "providers": 1, "radar": 9, "radar_llm": 2, "shared_event_infra": 2, "shared_radar_infra": 1}`

## Policy

- Not every top-level `event_*.py` module belongs under `crypto_rsi_scanner/event_alpha/`.
- `event_fade.py` remains intentionally outside Event Alpha because `TRIGGERED_FADE` must only come from `event_fade.py` + `proxy_fade`.
- Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but it must not create `TRIGGERED_FADE`.
- `event_clock.py` and `event_models.py` now live in the neutral `crypto_rsi_scanner/event_core/` package with active compatibility shims.
- Old import paths remain compatibility shims during v1 migration.

## Safe Migration Batches

### completed_prior_batch
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

### completed_final_event_alpha_batch
- `crypto_rsi_scanner.event_alpha_missed`
- `crypto_rsi_scanner.event_alpha_reason_text`

### completed_event_core_decision
- `crypto_rsi_scanner.event_clock`
- `crypto_rsi_scanner.event_models`

### intentionally_outside_event_alpha
- `crypto_rsi_scanner.event_fade`

## Module Rows

| module | lines | home | priority | risk | old import users | recommended status | safety flags | proposed path |
|---|---:|---|---|---|---:|---|---|---|
| `crypto_rsi_scanner.event_incident_graph` | 19 | radar | completed_prior_batch | medium | 9 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.incident_graph` |
| `crypto_rsi_scanner.event_identity` | 19 | radar | completed_prior_batch | medium | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.identity` |
| `crypto_rsi_scanner.event_graph` | 19 | radar | completed_prior_batch | medium | 12 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.graph` |
| `crypto_rsi_scanner.event_resolver` | 19 | radar | completed_prior_batch | medium | 34 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.resolver` |
| `crypto_rsi_scanner.event_price_history` | 19 | radar | completed_prior_batch | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.price_history` |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | 19 | radar | completed_prior_batch | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` |
| `crypto_rsi_scanner.event_anomaly_state` | 19 | radar | completed_prior_batch | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` |
| `crypto_rsi_scanner.event_anomaly_scanner` | 19 | radar | completed_prior_batch | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` |
| `crypto_rsi_scanner.event_market_units` | 19 | shared_radar_infra | completed_prior_batch | low | 9 | active_shim | shared | `crypto_rsi_scanner.event_alpha.radar.market_units` |
| `crypto_rsi_scanner.event_llm_budget` | 19 | radar_llm | completed_prior_batch | medium | 12 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.budget` |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | 19 | radar_llm | completed_prior_batch | low | 4 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` |
| `crypto_rsi_scanner.event_source_reliability` | 19 | providers | completed_prior_batch | medium | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.providers.source_reliability` |
| `crypto_rsi_scanner.event_cache` | 19 | artifacts | completed_prior_batch | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.cache` |
| `crypto_rsi_scanner.event_alpha_explain` | 19 | artifacts | completed_prior_batch | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.explain` |
| `crypto_rsi_scanner.event_alpha_quality_fields` | 19 | outcomes | completed_prior_batch | medium | 17 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` |
| `crypto_rsi_scanner.event_alpha_outcomes` | 19 | outcomes | completed_prior_batch | medium | 11 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` |
| `crypto_rsi_scanner.event_alpha_eval` | 19 | outcomes | completed_prior_batch | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.eval` |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | 19 | outcomes | completed_prior_batch | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` |
| `crypto_rsi_scanner.event_alpha_profiles` | 19 | config | completed_prior_batch | medium | 14 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.profiles` |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | 19 | config | completed_prior_batch | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.v1_readiness` |
| `crypto_rsi_scanner.event_alpha_preflight` | 19 | config | completed_prior_batch | medium | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.preflight` |
| `crypto_rsi_scanner.event_alpha_health_guard` | 19 | config | completed_prior_batch | medium | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.health_guard` |
| `crypto_rsi_scanner.event_alpha_scheduler` | 19 | config | completed_prior_batch | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.scheduler` |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | 19 | doctor | completed_prior_batch | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.doctor.environment` |
| `crypto_rsi_scanner.event_provider_status` | 19 | notifications | completed_prior_batch | medium | 21 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.notifications.provider_status` |
| `crypto_rsi_scanner.event_alpha_missed` | 19 | radar | completed_final_event_alpha_batch | medium | 9 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.missed` |
| `crypto_rsi_scanner.event_alpha_reason_text` | 19 | artifacts | completed_final_event_alpha_batch | low | 4 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` |
| `crypto_rsi_scanner.event_clock` | 19 | shared_event_infra | completed_event_core_decision | low | 8 | active_shim | shared | `crypto_rsi_scanner.event_core.clock` |
| `crypto_rsi_scanner.event_models` | 19 | shared_event_infra | completed_event_core_decision | medium | 54 | active_shim | shared | `crypto_rsi_scanner.event_core.models` |
| `crypto_rsi_scanner.event_fade` | 1181 | intentionally_outside_event_alpha | do_not_move | high | 48 | intentionally_outside_event_alpha | shared, execution_adjacent, outside_event_alpha | `crypto_rsi_scanner.event_fade` |
