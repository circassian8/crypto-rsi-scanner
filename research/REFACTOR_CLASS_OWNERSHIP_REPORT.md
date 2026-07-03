# Refactor Class Ownership Report

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-03T01:56:32.337628+00:00`
- public_class_count: `397`
- classes_over_limit_count: `29`
- functions_over_limit_count: `64`
- modules_with_multiple_public_classes_count: `81`

## Policy

- Every public class over 75 lines should live in its own module unless documented as an exception.
- Multiple tiny value objects/enums may live in `models.py` only when documented.
- Internal helper classes over 75 lines should also be split or documented.
- `event_fade.py` remains outside Event Alpha; Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts but must not create `TRIGGERED_FADE`.

## Exceptions

- `crypto_rsi_scanner.event_core.models`: Shared event-research dataclass bundle. Multiple tiny value objects may remain together in models.py during v1.
- `crypto_rsi_scanner.event_fade`: Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade.

## Modules With Multiple Public Classes

| module | public classes | exception |
|---|---:|---|
| `crypto_rsi_scanner.backups` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.alert_store` | 4 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | 2 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 |  |
| `crypto_rsi_scanner.event_alpha.config.health_guard` | 2 |  |
| `crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 |  |
| `crypto_rsi_scanner.event_alpha.doctor.environment` | 2 |  |
| `crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 |  |
| `crypto_rsi_scanner.event_alpha.notifications.inbox` | 3 |  |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline` | 6 |  |
| `crypto_rsi_scanner.event_alpha.notifications.provider_status` | 2 |  |
| `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | 2 |  |
| `crypto_rsi_scanner.event_alpha.notifications.router` | 5 |  |
| `crypto_rsi_scanner.event_alpha.notifications.runs` | 2 |  |
| `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | 2 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | 3 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback` | 2 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | 4 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | 2 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.priors` | 4 |  |
| `crypto_rsi_scanner.event_alpha.outcomes.quality` | 9 |  |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 |  |
| `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 |  |
| `crypto_rsi_scanner.event_alpha.providers.provider_health` | 7 |  |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 |  |
| `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search` | 15 |  |
| `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunity_store` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.graph` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.identity` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.incidents` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.budget` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | 5 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | 8 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.extractor` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.models` | 8 |  |
| `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.market_reaction` | 5 |  |
| `crypto_rsi_scanner.event_alpha.radar.missed` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.near_miss` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.pipeline` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.price_history` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 |  |
| `crypto_rsi_scanner.event_alpha.radar.validation` | 10 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist` | 5 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | 9 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 4 |  |
| `crypto_rsi_scanner.event_alpha.shims` | 2 |  |
| `crypto_rsi_scanner.event_core.models` | 7 | Shared event-research dataclass bundle. Multiple tiny value objects may remain together in models.py during v1. |
| `crypto_rsi_scanner.event_fade` | 11 | Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade. |
| `crypto_rsi_scanner.event_providers.base` | 2 |  |
| `crypto_rsi_scanner.event_providers.cryptopanic` | 5 |  |
| `crypto_rsi_scanner.llm_providers.base` | 5 |  |
| `crypto_rsi_scanner.llm_providers.fixture` | 4 |  |
| `crypto_rsi_scanner.llm_providers.openai_provider` | 2 |  |
| `crypto_rsi_scanner.ops` | 5 |  |
| `crypto_rsi_scanner.refactor_class_ownership_report` | 2 |  |

## Classes Over 75 Lines

| module | class | lines | public | exception |
|---|---|---:|---:|---|
| `crypto_rsi_scanner.client` | `CoinGeckoClient` | 115 | true |  |
| `crypto_rsi_scanner.derivatives_providers.coinalyze` | `CoinalyzeDerivativesProvider` | 189 | true |  |
| `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | `EventAlphaArtifactDoctorResult` | 402 | true |  |
| `crypto_rsi_scanner.event_alpha.notifications.delivery` | `NotificationDeliveryRecord` | 123 | true |  |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline` | `_DeliveryWriter` | 534 | false |  |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | `BybitAnnouncementsRehearsalReport` | 79 | true |  |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | `CoinalyzeRehearsalReport` | 102 | true |  |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | `LiveProviderReadinessProvider` | 99 | true |  |
| `crypto_rsi_scanner.event_alpha.providers.provider_health` | `HealthCheckedEventProvider` | 78 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.asset_registry` | `CanonicalAsset` | 96 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search` | `FixtureCatalystSearchProvider` | 79 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search` | `EventProviderCatalystSearchProvider` | 88 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | `EvidenceAcquisitionResult` | 120 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | `EventImpactHypothesis` | 191 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | `EventIntegratedRadarResult` | 88 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.llm.budget` | `EventLLMBudgetRunTracker` | 95 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.pipeline` | `EventAlphaPipelineResult` | 245 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage` | `EventAlphaSourceCoverageReport` | 143 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist` | `EventWatchlistEntry` | 85 | true |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | `CoinGeckoWatchlistMarketProvider` | 116 | true |  |
| `crypto_rsi_scanner.event_providers.binance_announcements` | `BinanceAnnouncementProvider` | 107 | true |  |
| `crypto_rsi_scanner.event_providers.bybit_announcements` | `BybitAnnouncementProvider` | 79 | true |  |
| `crypto_rsi_scanner.event_providers.cryptopanic` | `CryptoPanicProvider` | 372 | true |  |
| `crypto_rsi_scanner.event_providers.gdelt` | `GdeltProvider` | 82 | true |  |
| `crypto_rsi_scanner.event_providers.prediction_market_events` | `PredictionMarketEventsProvider` | 83 | true |  |
| `crypto_rsi_scanner.event_providers.project_blog_rss` | `ProjectBlogRssProvider` | 96 | true |  |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMRelationshipProvider` | 137 | true |  |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMExtractionProvider` | 78 | true |  |
| `crypto_rsi_scanner.storage` | `Storage` | 453 | true |  |

## Functions Over 150 Lines

| module | function | lines | public |
|---|---|---:|---:|
| `crypto_rsi_scanner.backtest` | `walk_coin` | 153 | true |
| `crypto_rsi_scanner.backtest` | `main` | 227 | true |
| `crypto_rsi_scanner.cli.event_alpha_command_registry` | `dispatch_event_alpha_command` | 809 | true |
| `crypto_rsi_scanner.cli.parser_event_alpha` | `add_event_alpha_args` | 1190 | true |
| `crypto_rsi_scanner.cli.services.event_alpha_fade_review` | `_write_event_fade_review_bundle` | 164 | false |
| `crypto_rsi_scanner.cli.services.event_alpha_notifications` | `_event_alpha_notify_cycle_body` | 513 | false |
| `crypto_rsi_scanner.cli.services.event_alpha_notifications` | `event_alpha_notify_fixture_smoke` | 732 | true |
| `crypto_rsi_scanner.cli.services.event_alpha_outcomes` | `event_alpha_export_burn_in_pack` | 159 | true |
| `crypto_rsi_scanner.cli.services.event_alpha_research` | `event_alpha_cycle` | 251 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.alert_store` | `_snapshot_from_route_decision` | 168 | false |
| `crypto_rsi_scanner.event_alpha.artifacts.daily_brief` | `build_daily_brief` | 884 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.locks` | `acquire_run_lock` | 174 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit` | `format_opportunity_audit` | 227 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | `render_research_card` | 220 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | `_core_score_components` | 168 | false |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards` | `_impact_hypothesis_lines` | 223 | false |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | `format_run_ledger_report` | 159 | true |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | `_run_record` | 219 | false |
| `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | `diagnose_artifacts` | 1335 | true |
| `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | `_integrated_radar_artifact_conflicts` | 218 | false |
| `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | `_notification_delivery_conflicts` | 251 | false |
| `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` | `format_artifact_doctor_report` | 462 | true |
| `crypto_rsi_scanner.event_alpha.notifications.go_no_go` | `build_go_no_go` | 159 | true |
| `crypto_rsi_scanner.event_alpha.notifications.inbox` | `build_notification_inbox` | 186 | true |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline` | `select_research_review_candidates_with_diagnostics` | 156 | true |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline` | `write_notification_plan_preview` | 190 | true |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline` | `send_notifications` | 406 | true |
| `crypto_rsi_scanner.event_alpha.notifications.provider_status` | `build_event_discovery_provider_status` | 229 | true |
| `crypto_rsi_scanner.event_alpha.notifications.readiness` | `build_send_readiness` | 193 | true |
| `crypto_rsi_scanner.event_alpha.notifications.router` | `_route_entry` | 220 | false |
| `crypto_rsi_scanner.event_alpha.outcomes.quality` | `evaluate_signal_quality_case` | 211 | true |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | `run_no_send_rehearsal` | 160 | true |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | `run_no_send_rehearsal` | 194 | true |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | `_provider_rows` | 429 | false |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | `source_descriptor_for` | 246 | true |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | `assess_source` | 158 | true |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunity_store` | `_row_from_core_opportunity` | 406 | false |
| `crypto_rsi_scanner.event_alpha.radar.derivatives_crowding` | `normalize_derivatives_state` | 166 | true |
| `crypto_rsi_scanner.event_alpha.radar.discovery` | `run_manual_discovery` | 244 | true |
| `crypto_rsi_scanner.event_alpha.radar.discovery` | `load_discovery_events` | 183 | true |
| `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | `_execute_request` | 167 | false |
| `crypto_rsi_scanner.event_alpha.radar.evidence_acquisition` | `_validate_raw_result` | 170 | false |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | `validate_hypotheses_with_raw_events` | 152 | true |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | `format_impact_hypothesis_report` | 158 | true |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses` | `_hypothesis_from_rule` | 199 | false |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | `validate_impact_path` | 181 | true |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | `_classify_path` | 271 | false |
| `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | `run_integrated_radar_cycle` | 288 | true |
| `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | `format_integrated_daily_brief` | 154 | true |
| `crypto_rsi_scanner.event_alpha.radar.integrated_radar` | `_merge_family` | 245 | false |
| `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | `evaluate_market_confirmation` | 281 | true |
| `crypto_rsi_scanner.event_alpha.radar.near_miss` | `_refresh_one_hypothesis` | 276 | false |
| `crypto_rsi_scanner.event_alpha.radar.near_miss` | `_candidate_from_row` | 158 | false |
| `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | `evaluate_opportunity` | 245 | true |
| `crypto_rsi_scanner.event_alpha.radar.pipeline` | `run_event_alpha_pipeline` | 244 | true |
| `crypto_rsi_scanner.event_alpha.radar.pipeline` | `run_event_alpha_operating_cycle` | 347 | true |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage` | `build_source_coverage_report` | 238 | true |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage` | `format_source_coverage_report` | 200 | true |
| `crypto_rsi_scanner.event_alpha.radar.validation` | `review_validation_sample` | 280 | true |
| `crypto_rsi_scanner.event_alpha.radar.watchlist` | `_entry_from_alert` | 199 | false |
| `crypto_rsi_scanner.event_alpha.radar.watchlist` | `_entry_from_hypothesis` | 352 | false |
| `crypto_rsi_scanner.event_alpha.radar.watchlist` | `_entry_from_row` | 164 | false |
| `crypto_rsi_scanner.event_providers.cryptopanic` | `CryptoPanicProvider._fetch_live_events` | 158 | false |
| `crypto_rsi_scanner.refactor_final_report` | `build_refactor_final_report` | 161 | true |
