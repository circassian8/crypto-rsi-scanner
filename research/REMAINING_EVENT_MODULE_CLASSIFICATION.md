# Remaining Event Module Classification

Research-only refactor inventory. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-02T18:54:51+00:00`
- module_count: `30`
- recommended_status_counts: `{"active_shim": 25, "intentionally_outside_event_alpha": 1, "not_migrated": 4}`
- likely_package_home_counts: `{"artifacts": 3, "config": 5, "doctor": 1, "intentionally_outside_event_alpha": 1, "notifications": 1, "outcomes": 4, "providers": 1, "radar": 9, "radar_llm": 2, "shared_event_infra": 2, "shared_radar_infra": 1}`

## Policy

- Not every top-level `event_*.py` module belongs under `crypto_rsi_scanner/event_alpha/`.
- `event_fade.py` remains intentionally outside Event Alpha because `TRIGGERED_FADE` must only come from `event_fade.py` + `proxy_fade`.
- Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but it must not create `TRIGGERED_FADE`.
- `event_clock.py` and `event_models.py` are shared event infrastructure and need a neutral package decision before movement.
- Old import paths remain compatibility shims during v1 migration.

## Safe Migration Batches

### completed_this_pass
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

### next_small_batch
- `crypto_rsi_scanner.event_alpha_missed`
- `crypto_rsi_scanner.event_alpha_reason_text`

### shared_event_core_decision
- `crypto_rsi_scanner.event_clock`
- `crypto_rsi_scanner.event_models`

### intentionally_outside_event_alpha
- `crypto_rsi_scanner.event_fade`

## Module Rows

| module | lines | home | priority | risk | old import users | recommended status | safety flags | proposed path |
|---|---:|---|---|---|---:|---|---|---|
| `crypto_rsi_scanner.event_incident_graph` | 0 | radar | completed_this_pass | medium | 9 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.incident_graph` |
| `crypto_rsi_scanner.event_identity` | 0 | radar | completed_this_pass | medium | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.identity` |
| `crypto_rsi_scanner.event_graph` | 0 | radar | completed_this_pass | medium | 12 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.graph` |
| `crypto_rsi_scanner.event_resolver` | 0 | radar | completed_this_pass | medium | 34 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.resolver` |
| `crypto_rsi_scanner.event_price_history` | 0 | radar | completed_this_pass | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.price_history` |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | 0 | radar | completed_this_pass | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` |
| `crypto_rsi_scanner.event_anomaly_state` | 0 | radar | completed_this_pass | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` |
| `crypto_rsi_scanner.event_anomaly_scanner` | 0 | radar | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` |
| `crypto_rsi_scanner.event_market_units` | 0 | shared_radar_infra | completed_this_pass | low | 9 | active_shim | shared | `crypto_rsi_scanner.event_alpha.radar.market_units` |
| `crypto_rsi_scanner.event_llm_budget` | 0 | radar_llm | completed_this_pass | medium | 12 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.budget` |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | 0 | radar_llm | completed_this_pass | low | 4 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` |
| `crypto_rsi_scanner.event_source_reliability` | 0 | providers | completed_this_pass | medium | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.providers.source_reliability` |
| `crypto_rsi_scanner.event_cache` | 0 | artifacts | completed_this_pass | medium | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.cache` |
| `crypto_rsi_scanner.event_alpha_explain` | 0 | artifacts | completed_this_pass | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.explain` |
| `crypto_rsi_scanner.event_alpha_quality_fields` | 0 | outcomes | completed_this_pass | medium | 17 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` |
| `crypto_rsi_scanner.event_alpha_outcomes` | 0 | outcomes | completed_this_pass | medium | 11 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` |
| `crypto_rsi_scanner.event_alpha_eval` | 0 | outcomes | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.eval` |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | 0 | outcomes | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` |
| `crypto_rsi_scanner.event_alpha_profiles` | 0 | config | completed_this_pass | medium | 14 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.profiles` |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | 0 | config | completed_this_pass | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.v1_readiness` |
| `crypto_rsi_scanner.event_alpha_preflight` | 0 | config | completed_this_pass | medium | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.preflight` |
| `crypto_rsi_scanner.event_alpha_health_guard` | 0 | config | completed_this_pass | medium | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.health_guard` |
| `crypto_rsi_scanner.event_alpha_scheduler` | 0 | config | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.scheduler` |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | 0 | doctor | completed_this_pass | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.doctor.environment` |
| `crypto_rsi_scanner.event_provider_status` | 0 | notifications | completed_this_pass | medium | 21 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.notifications.provider_status` |
| `crypto_rsi_scanner.event_alpha_missed` | 477 | radar | next_candidate | medium | 9 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.missed` |
| `crypto_rsi_scanner.event_alpha_reason_text` | 109 | artifacts | next_candidate | low | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` |
| `crypto_rsi_scanner.event_clock` | 114 | shared_event_infra | defer_shared_decision | low | 8 | not_migrated | shared | `crypto_rsi_scanner.event_core.clock` |
| `crypto_rsi_scanner.event_models` | 117 | shared_event_infra | defer_shared_decision | medium | 54 | not_migrated | shared | `crypto_rsi_scanner.event_core.models` |
| `crypto_rsi_scanner.event_fade` | 1181 | intentionally_outside_event_alpha | do_not_move | high | 48 | intentionally_outside_event_alpha | shared, execution_adjacent, outside_event_alpha | `crypto_rsi_scanner.event_fade` |
