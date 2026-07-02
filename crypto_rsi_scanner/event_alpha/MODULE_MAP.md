# Event Alpha Module Map

This map records the intended package home for existing top-level modules.
Top-level imports remain supported until a later migration removes shims.

| Compatibility module | Implementation package path | Layer |
|---|---|---|
| `crypto_rsi_scanner.event_integrated_radar` | `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | radar |
| `crypto_rsi_scanner.event_market_anomaly_scanner` | `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | radar |
| `crypto_rsi_scanner.event_market_state` | `crypto_rsi_scanner.event_alpha.radar.market_state` | radar |
| `crypto_rsi_scanner.event_market_reaction` | `crypto_rsi_scanner.event_alpha.radar.market_reaction` | radar |
| `crypto_rsi_scanner.event_core_opportunities` | `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | radar |
| `crypto_rsi_scanner.event_core_opportunity_store` | `crypto_rsi_scanner.event_alpha.radar.core_opportunity_store` | radar |
| `crypto_rsi_scanner.event_evidence_acquisition` | `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | radar |
| `crypto_rsi_scanner.event_alpha_source_coverage` | `crypto_rsi_scanner.event_alpha.radar.source_coverage` | radar |
| `crypto_rsi_scanner.event_opportunity_verdict` | `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | radar |
| `crypto_rsi_scanner.event_impact_hypotheses` | `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | radar |
| `crypto_rsi_scanner.event_impact_hypothesis_store` | `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | radar |
| `crypto_rsi_scanner.event_incident_store` | `crypto_rsi_scanner.event_alpha.radar.incidents` | radar |
| `crypto_rsi_scanner.event_alpha_artifacts` | `crypto_rsi_scanner.event_alpha.artifacts.context` | artifacts |
| `crypto_rsi_scanner.event_artifact_paths` | `crypto_rsi_scanner.event_alpha.artifacts.paths` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_ledger` | `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | artifacts |
| `crypto_rsi_scanner.event_alpha_retention` | `crypto_rsi_scanner.event_alpha.artifacts.retention` | artifacts |
| `crypto_rsi_scanner.event_alpha_run_lock` | `crypto_rsi_scanner.event_alpha.artifacts.locks` | artifacts |
| `crypto_rsi_scanner.event_alpha_artifact_doctor` | `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | doctor |
| `crypto_rsi_scanner.event_alpha_namespace_status` | `crypto_rsi_scanner.event_alpha.namespace.status` | namespace |
| `crypto_rsi_scanner.event_alpha_notifications` | `crypto_rsi_scanner.event_alpha.notifications.pipeline` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_delivery` | `crypto_rsi_scanner.event_alpha.notifications.delivery` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_sender` | `crypto_rsi_scanner.event_alpha.notifications.sender` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_runs` | `crypto_rsi_scanner.event_alpha.notifications.runs` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_go_no_go` | `crypto_rsi_scanner.event_alpha.notifications.go_no_go` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_checklist` | `crypto_rsi_scanner.event_alpha.notifications.checklist` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_inbox` | `crypto_rsi_scanner.event_alpha.notifications.inbox` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_pack` | `crypto_rsi_scanner.event_alpha.notifications.pack` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_pause` | `crypto_rsi_scanner.event_alpha.notifications.pause` | notifications |
| `crypto_rsi_scanner.event_alpha_notification_slo` | `crypto_rsi_scanner.event_alpha.notifications.slo` | notifications |
| `crypto_rsi_scanner.event_alpha_send_readiness` | `crypto_rsi_scanner.event_alpha.notifications.readiness` | notifications |
| `crypto_rsi_scanner.event_alpha_telegram_final_check` | `crypto_rsi_scanner.event_alpha.notifications.final_check` | notifications |
| `crypto_rsi_scanner.event_alpha_telegram_recipient_check` | `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | notifications |
| `crypto_rsi_scanner.event_integrated_radar_outcomes` | `crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes` | outcomes |
| `crypto_rsi_scanner.event_alpha_calibration` | `crypto_rsi_scanner.event_alpha.outcomes.calibration` | outcomes |
| `crypto_rsi_scanner.event_alpha_cryptopanic` | `crypto_rsi_scanner.event_alpha.providers.cryptopanic` | providers |
| `crypto_rsi_scanner.event_official_exchange` | `crypto_rsi_scanner.event_alpha.providers.official_exchange` | providers |
| `crypto_rsi_scanner.event_official_exchange_activation` | `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | providers |
| `crypto_rsi_scanner.event_coinalyze_preflight` | `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | providers |
| `crypto_rsi_scanner.event_live_provider_readiness` | `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | providers |
| `crypto_rsi_scanner.event_provider_health` | `crypto_rsi_scanner.event_alpha.providers.provider_health` | providers |
| `crypto_rsi_scanner.event_source_registry` | `crypto_rsi_scanner.event_alpha.providers.source_registry` | providers |
| `crypto_rsi_scanner.event_source_packs` | `crypto_rsi_scanner.event_alpha.providers.source_packs` | providers |
| `crypto_rsi_scanner.event_bybit_announcements_preflight` | `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | providers |
| `crypto_rsi_scanner.event_unlock_calendar_preflight` | `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | providers |
| `crypto_rsi_scanner.event_dex_onchain_readiness` | `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | providers |
