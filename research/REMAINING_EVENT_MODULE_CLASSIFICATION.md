# Remaining Event Module Classification

Research-only refactor inventory. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-02T18:30:45+00:00`
- module_count: `58`
- recommended_status_counts: `{"active_shim": 28, "intentionally_outside_event_alpha": 1, "not_migrated": 29}`
- likely_package_home_counts: `{"artifacts": 6, "config": 5, "doctor": 1, "intentionally_outside_event_alpha": 1, "notifications": 3, "outcomes": 5, "providers": 1, "radar": 23, "radar_llm": 10, "shared_event_infra": 2, "shared_radar_infra": 1}`

## Policy

- Not every top-level `event_*.py` module belongs under `crypto_rsi_scanner/event_alpha/`.
- `event_fade.py` remains intentionally outside Event Alpha because `TRIGGERED_FADE` must only come from `event_fade.py` + `proxy_fade`.
- Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but it must not create `TRIGGERED_FADE`.
- Old import paths remain compatibility shims during v1 migration.

## Safe Migration Batches

### completed_this_pass_radar
- `crypto_rsi_scanner.event_validation`
- `crypto_rsi_scanner.event_discovery`
- `crypto_rsi_scanner.event_watchlist`
- `crypto_rsi_scanner.event_near_miss`
- `crypto_rsi_scanner.event_alpha_pipeline`
- `crypto_rsi_scanner.event_impact_path_validator`
- `crypto_rsi_scanner.event_classification`
- `crypto_rsi_scanner.event_catalyst_frames`
- `crypto_rsi_scanner.event_playbooks`
- `crypto_rsi_scanner.event_claim_semantics`
- `crypto_rsi_scanner.event_watchlist_enrichment`
- `crypto_rsi_scanner.event_watchlist_market`
- `crypto_rsi_scanner.event_evidence_quality`
- `crypto_rsi_scanner.event_market_enrichment`

### completed_this_pass_radar_llm
- `crypto_rsi_scanner.event_llm_extractor`
- `crypto_rsi_scanner.event_llm_analyzer`
- `crypto_rsi_scanner.event_llm_evidence_planner`
- `crypto_rsi_scanner.event_llm_catalyst_frames`
- `crypto_rsi_scanner.event_llm_eval`
- `crypto_rsi_scanner.event_llm_extract_eval`
- `crypto_rsi_scanner.event_llm_models`
- `crypto_rsi_scanner.event_llm_extraction_models`

### completed_this_pass_artifacts_notifications_outcomes
- `crypto_rsi_scanner.event_alpha_alert_store`
- `crypto_rsi_scanner.event_alpha_router`
- `crypto_rsi_scanner.event_alerts`
- `crypto_rsi_scanner.event_feedback`
- `crypto_rsi_scanner.event_alpha_replay`
- `crypto_rsi_scanner.event_watchlist_monitor`

### next_identity_graph_profiles
- `crypto_rsi_scanner.event_incident_graph`
- `crypto_rsi_scanner.event_identity`
- `crypto_rsi_scanner.event_alpha_profiles`
- `crypto_rsi_scanner.event_graph`
- `crypto_rsi_scanner.event_resolver`

### intentionally_outside_event_alpha
- `crypto_rsi_scanner.event_fade`

## Module Rows

| module | lines | home | priority | risk | old import users | recommended status | safety flags | proposed path |
|---|---:|---|---|---|---:|---|---|---|
| `crypto_rsi_scanner.event_validation` | 2821 | radar | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.validation` |
| `crypto_rsi_scanner.event_discovery` | 1887 | radar | completed_this_pass | low | 28 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.discovery` |
| `crypto_rsi_scanner.event_watchlist` | 1828 | radar | completed_this_pass | medium | 34 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.watchlist` |
| `crypto_rsi_scanner.event_alpha_alert_store` | 1630 | artifacts | completed_this_pass | medium | 15 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.alert_store` |
| `crypto_rsi_scanner.event_alpha_router` | 1413 | notifications | completed_this_pass | medium | 29 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.notifications.router` |
| `crypto_rsi_scanner.event_near_miss` | 1341 | radar | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.near_miss` |
| `crypto_rsi_scanner.event_alpha_pipeline` | 1267 | radar | completed_this_pass | medium | 9 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.pipeline` |
| `crypto_rsi_scanner.event_fade` | 1181 | intentionally_outside_event_alpha | do_not_move_this_pass | high | 18 | intentionally_outside_event_alpha | shared, execution_adjacent, outside_event_alpha | `crypto_rsi_scanner.event_fade` |
| `crypto_rsi_scanner.event_llm_extractor` | 1002 | radar_llm | completed_this_pass | low | 12 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.extractor` |
| `crypto_rsi_scanner.event_alerts` | 985 | artifacts | completed_this_pass | medium | 17 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.alerts` |
| `crypto_rsi_scanner.event_incident_graph` | 975 | radar | high | medium | 5 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.incident_graph` |
| `crypto_rsi_scanner.event_identity` | 941 | radar | high | medium | 7 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.identity` |
| `crypto_rsi_scanner.event_alpha_profiles` | 935 | config | high | medium | 10 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.profiles` |
| `crypto_rsi_scanner.event_llm_analyzer` | 828 | radar_llm | completed_this_pass | low | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` |
| `crypto_rsi_scanner.event_impact_path_validator` | 790 | radar | completed_this_pass | low | 7 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` |
| `crypto_rsi_scanner.event_feedback` | 771 | outcomes | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` |
| `crypto_rsi_scanner.event_alpha_replay` | 685 | artifacts | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.replay` |
| `crypto_rsi_scanner.event_llm_evidence_planner` | 657 | radar_llm | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` |
| `crypto_rsi_scanner.event_classification` | 607 | radar | completed_this_pass | low | 6 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.classification` |
| `crypto_rsi_scanner.event_catalyst_frames` | 595 | radar | completed_this_pass | low | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.catalyst_frames` |
| `crypto_rsi_scanner.event_playbooks` | 553 | radar | completed_this_pass | low | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.playbooks` |
| `crypto_rsi_scanner.event_llm_catalyst_frames` | 532 | radar_llm | completed_this_pass | low | 9 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` |
| `crypto_rsi_scanner.event_claim_semantics` | 486 | radar | completed_this_pass | low | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.claim_semantics` |
| `crypto_rsi_scanner.event_alpha_missed` | 477 | radar | medium | medium | 6 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.missed` |
| `crypto_rsi_scanner.event_provider_status` | 446 | notifications | medium | medium | 16 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.notifications.provider_status` |
| `crypto_rsi_scanner.event_watchlist_monitor` | 421 | notifications | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` |
| `crypto_rsi_scanner.event_cache` | 415 | artifacts | medium | medium | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.cache` |
| `crypto_rsi_scanner.event_graph` | 410 | radar | medium | medium | 8 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.graph` |
| `crypto_rsi_scanner.event_resolver` | 379 | radar | medium | medium | 31 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.resolver` |
| `crypto_rsi_scanner.event_price_history` | 356 | radar | medium | medium | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.price_history` |
| `crypto_rsi_scanner.event_watchlist_enrichment` | 339 | radar | completed_this_pass | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` |
| `crypto_rsi_scanner.event_watchlist_market` | 319 | radar | completed_this_pass | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` |
| `crypto_rsi_scanner.event_alpha_v1_readiness` | 317 | config | medium | low | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.v1_readiness` |
| `crypto_rsi_scanner.event_evidence_quality` | 284 | radar | completed_this_pass | low | 8 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.evidence_quality` |
| `crypto_rsi_scanner.event_market_enrichment` | 280 | radar | completed_this_pass | low | 10 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.market_enrichment` |
| `crypto_rsi_scanner.event_catalyst_frame_validator` | 257 | radar | medium | medium | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator` |
| `crypto_rsi_scanner.event_anomaly_state` | 254 | radar | medium | low | 2 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_state` |
| `crypto_rsi_scanner.event_alpha_quality_fields` | 254 | outcomes | medium | medium | 13 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.quality_fields` |
| `crypto_rsi_scanner.event_alpha_preflight` | 241 | config | medium | medium | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.preflight` |
| `crypto_rsi_scanner.event_alpha_health_guard` | 234 | config | medium | medium | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.health_guard` |
| `crypto_rsi_scanner.event_llm_budget` | 227 | radar_llm | medium | medium | 6 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.budget` |
| `crypto_rsi_scanner.event_source_reliability` | 222 | providers | medium | medium | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.providers.source_reliability` |
| `crypto_rsi_scanner.event_alpha_outcomes` | 198 | outcomes | medium | medium | 6 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts` |
| `crypto_rsi_scanner.event_alpha_environment_doctor` | 191 | doctor | low | low | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.doctor.environment` |
| `crypto_rsi_scanner.event_alpha_scheduler` | 176 | config | low | low | 2 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.config.scheduler` |
| `crypto_rsi_scanner.event_llm_eval` | 162 | radar_llm | completed_this_pass | low | 3 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.eval` |
| `crypto_rsi_scanner.event_alpha_eval` | 158 | outcomes | low | low | 2 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.eval` |
| `crypto_rsi_scanner.event_market_units` | 153 | shared_radar_infra | low | low | 6 | not_migrated | shared | `crypto_rsi_scanner.event_alpha.radar.market_units` |
| `crypto_rsi_scanner.event_llm_extract_eval` | 150 | radar_llm | completed_this_pass | low | 3 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.extract_eval` |
| `crypto_rsi_scanner.event_anomaly_scanner` | 150 | radar | low | low | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.anomaly_scanner` |
| `crypto_rsi_scanner.event_alpha_burn_in_checklist` | 149 | outcomes | low | low | 5 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist` |
| `crypto_rsi_scanner.event_llm_catalyst_frames_eval` | 141 | radar_llm | low | low | 0 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval` |
| `crypto_rsi_scanner.event_alpha_explain` | 122 | artifacts | low | low | 3 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.explain` |
| `crypto_rsi_scanner.event_models` | 117 | shared_event_infra | low | medium | 54 | not_migrated | shared | `crypto_rsi_scanner.event_alpha.radar.models` |
| `crypto_rsi_scanner.event_clock` | 114 | shared_event_infra | low | low | 3 | not_migrated | shared | `crypto_rsi_scanner.event_alpha.config.clock` |
| `crypto_rsi_scanner.event_llm_models` | 112 | radar_llm | completed_this_pass | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.models` |
| `crypto_rsi_scanner.event_alpha_reason_text` | 109 | artifacts | low | low | 4 | not_migrated | event_alpha_only | `crypto_rsi_scanner.event_alpha.artifacts.reason_text` |
| `crypto_rsi_scanner.event_llm_extraction_models` | 96 | radar_llm | completed_this_pass | low | 5 | active_shim | event_alpha_only | `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` |
