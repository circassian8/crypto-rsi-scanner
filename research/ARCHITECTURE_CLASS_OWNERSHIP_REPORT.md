# Architecture Class Ownership Report

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-18T09:49:55.724595+00:00`
- public_class_count: `493`
- classes_over_limit_count: `3`
- functions_over_limit_count: `0`
- production_classes_over_limit: `3`
- production_functions_over_limit: `0`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`
- v3_gate_status: `accepted_with_documented_exceptions`
- v3_auto_accept_ready: `False`
- v3_blockers: `[]`
- public_classes_not_in_own_module: `0`
- class_exceptions_remaining: `3`
- functions_over_150_lines: `0`
- modules_with_multiple_public_classes_count: `0`
- modules_with_multiple_public_classes_status: `pass`
- multi_public_class_modules_count: `84`
- accepted_model_bundles_count: `83`
- unresolved_multi_class_modules_count: `0`
- api_decomposition_gate_status: `pass`
- api_classes_over_limit: `0`
- api_functions_over_limit: `0`
- api_modules_with_multiple_public_classes: `0`

## Policy

- Every public class over 75 lines should live in its own module unless documented as an exception.
- Multiple tiny value objects/enums/protocol DTOs may live together only when registered as accepted model bundles.
- Internal helper classes over 75 lines should also be split or documented.
- Architecture policy expects public classes to live in their own modules unless the module is a documented model bundle.
- Architecture policy treats documented class exceptions as accepted exceptions; unaccepted class debt remains pending or blocked.
- `event_fade.py` remains outside Event Alpha; Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts but must not create `TRIGGERED_FADE`.

## Architecture Gates

| gate | value | severity |
|---|---:|---|
| `nonessential_shims_remaining` | 0 | blocker |
| `old_path_internal_imports` | 0 | blocker |
| `old_path_test_imports` | 0 | blocker |
| `public_compatibility_shims` | 0 | informational |
| `shim_removal_blockers` | 0 | blocker |
| `deleted_shims` | 124 | informational |
| `production_files_over_1200_lines` | 25 | accepted_exception |
| `production_files_over_1500_lines` | 0 | blocker |
| `public_classes_not_in_own_module` | 0 | blocker |
| `class_exceptions_remaining` | 3 | accepted_exception |
| `functions_over_150_lines` | 0 | blocker |
| `old_path_docs_references` | 0 | blocker_unless_policy_scoped |
| `old_path_import_allowed_exceptions` | 0 | informational |

## Exceptions

- `crypto_rsi_scanner.event_fade`: Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade.

## Accepted Class Exceptions

| module | class | lines | category | owner note | revisit condition |
|---|---|---:|---|---|---|
| `crypto_rsi_scanner.storage_parts.migrations` | `MigrationsMixin` | 88 | storage_mixin | DB schema behavior must not change in this cleanup pass. | Revisit only with explicit migration tests and backup/restore verification. |
| `crypto_rsi_scanner.storage_parts.signals` | `SignalsMixin` | 129 | storage_mixin | Avoid splitting storage write paths without SQLite roundtrip parity tests. | Revisit when storage schema v2 or a repository layer is introduced. |
| `crypto_rsi_scanner.storage_parts.watchlist` | `WatchlistMixin` | 89 | storage_mixin | No DB schema or paper/watchlist behavior changes in this architecture-maintenance pass. | Revisit when watchlist storage grows new tables or migrations. |

## Provider Class Split Status

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `BinanceAnnouncementProvider` | `crypto_rsi_scanner.event_providers.binance_announcements.provider` | 14 | below_threshold |  |
| `BybitAnnouncementProvider` | `crypto_rsi_scanner.event_providers.bybit_announcements.provider` | 14 | below_threshold |  |
| `CoinGeckoWatchlistMarketProvider` | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 36 | below_threshold | Revisit when watchlist market enrichment gains another provider implementation. |
| `CoinalyzeDerivativesProvider` | `crypto_rsi_scanner.derivatives_providers.coinalyze.core` | 54 | below_threshold |  |
| `CryptoPanicProvider` | `crypto_rsi_scanner.event_providers.cryptopanic.provider` | 29 | below_threshold |  |
| `GdeltProvider` | `crypto_rsi_scanner.event_providers.gdelt` | 14 | below_threshold | Revisit when adding a second GDELT mode or durable request ledger. |
| `OpenAILLMExtractionProvider` | `crypto_rsi_scanner.llm_providers.openai_extraction` | 30 | below_threshold |  |
| `OpenAILLMRelationshipProvider` | `crypto_rsi_scanner.llm_providers.openai_relationship` | 36 | below_threshold |  |
| `PredictionMarketEventsProvider` | `crypto_rsi_scanner.event_providers.prediction_market_events` | 14 | below_threshold | Revisit when Polymarket Gamma support grows beyond the current parser. |
| `ProjectBlogRssProvider` | `crypto_rsi_scanner.event_providers.project_blog_rss` | 11 | below_threshold | Revisit when project-blog sources get persistent request ledgers or richer feed classes. |

## Storage Mixin Exceptions

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `MigrationsMixin` | `crypto_rsi_scanner.storage_parts.migrations` | 88 | accepted_exception | Revisit only with explicit migration tests and backup/restore verification. |
| `SignalsMixin` | `crypto_rsi_scanner.storage_parts.signals` | 129 | accepted_exception | Revisit when storage schema v2 or a repository layer is introduced. |
| `WatchlistMixin` | `crypto_rsi_scanner.storage_parts.watchlist` | 89 | accepted_exception | Revisit when watchlist storage grows new tables or migrations. |

## Near-Threshold Production Files

| path | lines | status | revisit condition |
|---|---:|---|---|
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_controls.py` | 1498 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_outcomes.py` | 1492 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/radar/market_history.py` | 1467 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py` | 1466 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/daily_operations.py` | 1465 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/config.py` | 1450 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_research_reports.py` | 1449 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py` | 1432 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/project_health/architecture_report.py` | 1411 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_replay_analysis.py` | 1410 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py` | 1397 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_policy_lab.py` | 1389 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py` | 1371 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/market_no_send.py` | 1305 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/operations/empirical_review.py` | 1300 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |

## API Implementation Cores

| path | lines |
|---|---:|

## Accepted Model Bundles

| module | classes | max class lines | accepted | reason |
|---|---:|---:|---:|---|
| `crypto_rsi_scanner.backups` | 3 | 31 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | 4 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 | 59 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 | 11 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 | 24 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 | 16 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards.components.models` | 2 | 5 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 | 17 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 | 4 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.config.health_guard` | 2 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 | 13 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.dashboard.models` | 4 | 47 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.doctor.environment` | 2 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 | 50 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.inbox.models` | 3 | 57 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline_parts.delivery_models` | 6 | 37 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.provider_status` | 2 | 21 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | 2 | 9 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.router` | 5 | 24 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.runs` | 2 | 4 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | 2 | 21 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.operations.market_no_send_models` | 7 | 59 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | 3 | 30 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback` | 2 | 36 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | 4 | 57 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | 2 | 9 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.priors` | 4 | 11 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.quality.models` | 9 | 9 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 | 53 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 2 | 74 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 | 61 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 | 53 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 | 45 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.provider_health_core` | 7 | 75 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 | 47 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 | 49 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 | 15 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.calendar.models` | 3 | 39 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.models` | 7 | 22 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers` | 8 | 52 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 | 12 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.core.models` | 7 | 62 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 | 57 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.decision_models` | 12 | 47 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.evidence.models` | 7 | 61 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.graph` | 3 | 27 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.identity` | 6 | 29 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models` | 6 | 14 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 | 27 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 | 44 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.incidents.models` | 4 | 26 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | 3 | 18 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.budget` | 3 | 71 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | 5 | 25 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | 7 | 44 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | 8 | 13 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.extractor` | 4 | 17 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.models` | 8 | 24 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | 2 | 20 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | 4 | 31 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_reaction` | 5 | 35 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.missed` | 2 | 21 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.near_miss.models` | 4 | 53 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 | 12 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.pipeline_models` | 2 | 28 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 | 18 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.price_history` | 2 | 9 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage.models` | 2 | 45 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 | 37 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.validation.models` | 10 | 60 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist.models` | 5 | 12 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | 9 | 13 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 4 | 36 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.shims` | 2 | 17 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_core.models` | 7 | 17 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_providers.base` | 2 | 5 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.llm_providers.base` | 5 | 7 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.llm_providers.fixture` | 4 | 54 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.ops` | 5 | 12 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.project_health.class_ownership` | 2 | 10 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.signal_registry` | 2 | 7 | true | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |

## Unresolved Multi-Class Modules

| module | public classes | max class lines | reason |
|---|---:|---:|---|
| none | 0 | 0 | all current multi-class modules are registered or explicitly excepted |

## Multi-Public-Class Module Inventory

| module | public classes | max class lines | resolution | reason |
|---|---:|---:|---|---|
| `crypto_rsi_scanner.backups` | 3 | 31 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | 4 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 | 59 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 | 11 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 | 24 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 | 16 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards.components.models` | 2 | 5 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 | 17 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 | 4 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.config.health_guard` | 2 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 | 13 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.dashboard.models` | 4 | 47 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.doctor.environment` | 2 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 | 50 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.inbox.models` | 3 | 57 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.pipeline_parts.delivery_models` | 6 | 37 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.provider_status` | 2 | 21 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.recipient_check` | 2 | 9 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.router` | 5 | 24 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.runs` | 2 | 4 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor` | 2 | 21 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.operations.market_no_send_models` | 7 | 59 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.burn_in` | 3 | 30 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback` | 2 | 36 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.feedback_labels` | 4 | 57 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.policy_simulator` | 2 | 9 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.priors` | 4 | 11 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.outcomes.quality.models` | 9 | 9 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 | 53 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 2 | 74 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 | 61 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 | 53 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 | 45 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.provider_health_core` | 7 | 75 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 | 47 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 | 49 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 | 15 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.calendar.models` | 3 | 39 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.models` | 7 | 22 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers` | 8 | 52 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 | 12 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.core.models` | 7 | 62 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 | 57 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.decision_models` | 12 | 47 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.evidence.models` | 7 | 61 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.graph` | 3 | 27 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.identity` | 6 | 29 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models` | 6 | 14 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 | 27 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 | 44 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.incidents.models` | 4 | 26 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.analyzer` | 3 | 18 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.budget` | 3 | 71 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames` | 5 | 25 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner` | 7 | 44 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.extraction_models` | 8 | 13 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.extractor` | 4 | 17 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.llm.models` | 8 | 24 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner` | 2 | 20 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_confirmation` | 4 | 31 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.market_reaction` | 5 | 35 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.missed` | 2 | 21 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.near_miss.models` | 4 | 53 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 | 12 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.pipeline_models` | 2 | 28 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 | 18 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.price_history` | 2 | 9 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage.models` | 2 | 45 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 | 37 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.validation.models` | 10 | 60 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist.models` | 5 | 12 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | 9 | 13 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 4 | 36 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_alpha.shims` | 2 | 17 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_core.models` | 7 | 17 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.event_fade` | 11 | 25 | module_exception | Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade. |
| `crypto_rsi_scanner.event_providers.base` | 2 | 5 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.llm_providers.base` | 5 | 7 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.llm_providers.fixture` | 4 | 54 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.ops` | 5 | 12 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.project_health.class_ownership` | 2 | 10 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |
| `crypto_rsi_scanner.signal_registry` | 2 | 7 | accepted_model_bundle | Small public DTO/enum/protocol/result bundle kept together as one stable import contract; all classes remain below the class-size limit. |

## Classes Over 75 Lines

| module | class | lines | public | accepted | exception |
|---|---|---:|---:|---:|---|
| `crypto_rsi_scanner.storage_parts.migrations` | `MigrationsMixin` | 88 | true | true | SQLite migration ownership is intentionally centralized to avoid untested schema drift. |
| `crypto_rsi_scanner.storage_parts.signals` | `SignalsMixin` | 129 | true | true | Signal persistence methods share schema assumptions, row serialization, and outcome lookup behavior. |
| `crypto_rsi_scanner.storage_parts.watchlist` | `WatchlistMixin` | 89 | true | true | Watchlist persistence methods are stable DB helpers and only slightly exceed the advisory limit. |

## Functions Over 150 Lines

| module | function | lines | public |
|---|---|---:|---:|
