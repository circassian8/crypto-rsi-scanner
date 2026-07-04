# Refactor Class Ownership Report

Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.

- generated_at: `2026-07-04T17:06:51.363916+00:00`
- public_class_count: `408`
- classes_over_limit_count: `14`
- functions_over_limit_count: `0`
- production_classes_over_limit: `14`
- production_functions_over_limit: `0`
- accepted_class_exceptions_count: `14`
- remaining_class_ownership_debt_count: `0`
- modules_with_multiple_public_classes_count: `82`
- modules_with_multiple_public_classes_status: `documented_advisory`
- legacy_decomposition_gate_status: `pass`
- legacy_classes_over_limit: `3`
- legacy_functions_over_limit: `0`
- legacy_modules_with_multiple_public_classes: `2`

## Policy

- Every public class over 75 lines should live in its own module unless documented as an exception.
- Multiple tiny value objects/enums may live in `models.py` only when documented.
- Internal helper classes over 75 lines should also be split or documented.
- `event_fade.py` remains outside Event Alpha; Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts but must not create `TRIGGERED_FADE`.

## Exceptions

- `crypto_rsi_scanner.event_core.models`: Shared event-research dataclass bundle. Multiple tiny value objects may remain together in models.py during v1.
- `crypto_rsi_scanner.event_fade`: Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade.

## Accepted Class Exceptions

| module | class | lines | category | owner note | revisit condition |
|---|---|---:|---|---|---|
| `crypto_rsi_scanner.client` | `CoinGeckoClient` | 115 | provider_client | Split only with dedicated CoinGecko client parity tests; this pass intentionally avoids provider behavior churn. | Revisit when adding a new CoinGecko endpoint family or changing async session/retry ownership. |
| `crypto_rsi_scanner.event_alpha.radar.asset_registry` | `CanonicalAsset` | 96 | data_model | Keep schema-adjacent identity fields together while canonical resolver contracts settle. | Revisit when schema v2 splits asset identity, venue symbols, and diagnostics into separate contracts. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | `CoinGeckoWatchlistMarketProvider` | 116 | provider_adapter | Provider activation safety is more important than shaving this adapter below 75 lines. | Revisit when watchlist market enrichment gains another provider implementation. |
| `crypto_rsi_scanner.event_providers.binance_announcements.legacy` | `BinanceAnnouncementProvider` | 107 | provider_adapter | Do not split further without signed-listener fixture parity and secret-redaction tests. | Revisit when Binance public rehearsal becomes a first-class activated provider path. |
| `crypto_rsi_scanner.event_providers.bybit_announcements.legacy` | `BybitAnnouncementProvider` | 79 | provider_adapter | Avoid touching Bybit request/normalization behavior outside provider-activation work. | Revisit when adding another Bybit announcement endpoint or response shape. |
| `crypto_rsi_scanner.event_providers.cryptopanic.legacy` | `CryptoPanicProvider` | 340 | provider_adapter | The package already has client/parser/request_ledger homes; moving the remaining class body should be its own provider parity pass. | Revisit when CryptoPanic live activation or request-ledger semantics change. |
| `crypto_rsi_scanner.event_providers.gdelt` | `GdeltProvider` | 82 | provider_adapter | Keep current timeout/429 behavior stable; public-provider noise is expected. | Revisit when adding a second GDELT mode or durable request ledger. |
| `crypto_rsi_scanner.event_providers.prediction_market_events` | `PredictionMarketEventsProvider` | 83 | provider_adapter | Split only when another prediction-market provider is added. | Revisit when Polymarket Gamma support grows beyond the current parser. |
| `crypto_rsi_scanner.event_providers.project_blog_rss` | `ProjectBlogRssProvider` | 96 | provider_adapter | Keep feed failure semantics stable unless adding a reusable RSS client layer. | Revisit when project-blog sources get persistent request ledgers or richer feed classes. |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMRelationshipProvider` | 137 | llm_provider | Do not alter LLM provider behavior during a refactor-only pass. | Revisit when adding a second live LLM backend or shared OpenAI transport abstraction. |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMExtractionProvider` | 78 | llm_provider | Keep quote-validation and no-live defaults stable. | Revisit with a broader OpenAI provider transport split. |
| `crypto_rsi_scanner.storage_parts.migrations` | `MigrationsMixin` | 88 | storage_mixin | DB schema behavior must not change in this cleanup pass. | Revisit only with explicit migration tests and backup/restore verification. |
| `crypto_rsi_scanner.storage_parts.signals` | `SignalsMixin` | 129 | storage_mixin | Avoid splitting storage write paths without SQLite roundtrip parity tests. | Revisit when storage schema v2 or a repository layer is introduced. |
| `crypto_rsi_scanner.storage_parts.watchlist` | `WatchlistMixin` | 89 | storage_mixin | No DB schema or paper/watchlist behavior changes in this refactor pass. | Revisit when watchlist storage grows new tables or migrations. |

## Provider Class Split Status

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `BinanceAnnouncementProvider` | `crypto_rsi_scanner.event_providers.binance_announcements.legacy` | 107 | accepted_exception | Revisit when Binance public rehearsal becomes a first-class activated provider path. |
| `BybitAnnouncementProvider` | `crypto_rsi_scanner.event_providers.bybit_announcements.legacy` | 79 | accepted_exception | Revisit when adding another Bybit announcement endpoint or response shape. |
| `CoinGeckoWatchlistMarketProvider` | `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 116 | accepted_exception | Revisit when watchlist market enrichment gains another provider implementation. |
| `CoinalyzeDerivativesProvider` | `crypto_rsi_scanner.derivatives_providers.coinalyze.legacy` | 54 | below_threshold |  |
| `CryptoPanicProvider` | `crypto_rsi_scanner.event_providers.cryptopanic.legacy` | 340 | accepted_exception | Revisit when CryptoPanic live activation or request-ledger semantics change. |
| `GdeltProvider` | `crypto_rsi_scanner.event_providers.gdelt` | 82 | accepted_exception | Revisit when adding a second GDELT mode or durable request ledger. |
| `OpenAILLMExtractionProvider` | `crypto_rsi_scanner.llm_providers.openai_provider` | 78 | accepted_exception | Revisit with a broader OpenAI provider transport split. |
| `OpenAILLMRelationshipProvider` | `crypto_rsi_scanner.llm_providers.openai_provider` | 137 | accepted_exception | Revisit when adding a second live LLM backend or shared OpenAI transport abstraction. |
| `PredictionMarketEventsProvider` | `crypto_rsi_scanner.event_providers.prediction_market_events` | 83 | accepted_exception | Revisit when Polymarket Gamma support grows beyond the current parser. |
| `ProjectBlogRssProvider` | `crypto_rsi_scanner.event_providers.project_blog_rss` | 96 | accepted_exception | Revisit when project-blog sources get persistent request ledgers or richer feed classes. |

## Storage Mixin Exceptions

| class | module | lines | status | revisit condition |
|---|---|---:|---|---|
| `MigrationsMixin` | `crypto_rsi_scanner.storage_parts.migrations` | 88 | accepted_exception | Revisit only with explicit migration tests and backup/restore verification. |
| `SignalsMixin` | `crypto_rsi_scanner.storage_parts.signals` | 129 | accepted_exception | Revisit when storage schema v2 or a repository layer is introduced. |
| `WatchlistMixin` | `crypto_rsi_scanner.storage_parts.watchlist` | 89 | accepted_exception | Revisit when watchlist storage grows new tables or migrations. |

## Near-Threshold Production Files

| path | lines | status | revisit condition |
|---|---:|---|---|
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py` | 1498 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/radar/pipeline.py` | 1487 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py` | 1473 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/cli/services/legacy/utility_commands.py` | 1440 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py` | 1404 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py` | 1395 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/cli/services/legacy/config_reports.py` | 1392 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/event_alpha/notifications/router.py` | 1387 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |
| `crypto_rsi_scanner/config.py` | 1319 | accepted_near_threshold | Revisit if the file crosses 1,500 lines or gains a new large class/function violation. |

## Legacy Implementation Cores

| path | lines |
|---|---:|
| `crypto_rsi_scanner/event_alpha/artifacts/schema/legacy.py` | 933 |
| `crypto_rsi_scanner/event_providers/cryptopanic/legacy.py` | 905 |
| `crypto_rsi_scanner/event_alpha/providers/provider_health_legacy.py` | 779 |
| `crypto_rsi_scanner/derivatives_providers/coinalyze/legacy.py` | 629 |
| `crypto_rsi_scanner/event_providers/binance_announcements/legacy.py` | 192 |
| `crypto_rsi_scanner/refactor_legacy_inventory.py` | 190 |
| `crypto_rsi_scanner/cli/services/scanner_legacy.py` | 120 |
| `crypto_rsi_scanner/event_providers/bybit_announcements/legacy.py` | 111 |
| `crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py` | 104 |
| `crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py` | 95 |
| `crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py` | 88 |
| `crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py` | 85 |
| `crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py` | 83 |
| `crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py` | 59 |
| `crypto_rsi_scanner/event_alpha/radar/validation/legacy.py` | 54 |
| `crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py` | 52 |
| `crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py` | 50 |
| `crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py` | 48 |

## Modules With Multiple Public Classes

| module | public classes | exception |
|---|---:|---|
| `crypto_rsi_scanner.backups` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.alert_store.models` | 4 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.alerts` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.cache` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.locks` | 3 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.replay` | 4 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models` | 2 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.retention` | 2 |  |
| `crypto_rsi_scanner.event_alpha.artifacts.run_ledger` | 2 |  |
| `crypto_rsi_scanner.event_alpha.config.health_guard` | 2 |  |
| `crypto_rsi_scanner.event_alpha.config.v1_readiness` | 2 |  |
| `crypto_rsi_scanner.event_alpha.doctor.environment` | 2 |  |
| `crypto_rsi_scanner.event_alpha.notifications.delivery` | 3 |  |
| `crypto_rsi_scanner.event_alpha.notifications.inbox.models` | 3 |  |
| `crypto_rsi_scanner.event_alpha.notifications.legacy.delivery_models` | 6 |  |
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
| `crypto_rsi_scanner.event_alpha.outcomes.quality.models` | 9 |  |
| `crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness` | 3 |  |
| `crypto_rsi_scanner.event_alpha.providers.live_provider_readiness` | 2 |  |
| `crypto_rsi_scanner.event_alpha.providers.official_exchange_activation` | 2 |  |
| `crypto_rsi_scanner.event_alpha.providers.provider_health_legacy` | 7 |  |
| `crypto_rsi_scanner.event_alpha.providers.source_registry` | 6 |  |
| `crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.anomaly_state` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.models` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers` | 8 |  |
| `crypto_rsi_scanner.event_alpha.radar.claim_semantics` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.core.models` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.core_opportunities` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.evidence.models` | 7 |  |
| `crypto_rsi_scanner.event_alpha.radar.evidence_quality` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.graph` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.identity` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.impact_path_validator` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.incident_graph` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.incidents.models` | 4 |  |
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
| `crypto_rsi_scanner.event_alpha.radar.near_miss.models` | 4 |  |
| `crypto_rsi_scanner.event_alpha.radar.opportunity_verdict` | 6 |  |
| `crypto_rsi_scanner.event_alpha.radar.pipeline` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.playbooks` | 3 |  |
| `crypto_rsi_scanner.event_alpha.radar.price_history` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.source_coverage.models` | 2 |  |
| `crypto_rsi_scanner.event_alpha.radar.source_enrichment` | 9 |  |
| `crypto_rsi_scanner.event_alpha.radar.validation.models` | 10 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist.models` | 5 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment` | 9 |  |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | 4 |  |
| `crypto_rsi_scanner.event_alpha.shims` | 3 |  |
| `crypto_rsi_scanner.event_core.models` | 7 | Shared event-research dataclass bundle. Multiple tiny value objects may remain together in models.py during v1. |
| `crypto_rsi_scanner.event_fade` | 11 | Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade. |
| `crypto_rsi_scanner.event_providers.base` | 2 |  |
| `crypto_rsi_scanner.event_providers.cryptopanic.legacy` | 5 |  |
| `crypto_rsi_scanner.llm_providers.base` | 5 |  |
| `crypto_rsi_scanner.llm_providers.fixture` | 4 |  |
| `crypto_rsi_scanner.llm_providers.openai_provider` | 2 |  |
| `crypto_rsi_scanner.ops` | 5 |  |

## Classes Over 75 Lines

| module | class | lines | public | accepted | exception |
|---|---|---:|---:|---:|---|
| `crypto_rsi_scanner.client` | `CoinGeckoClient` | 115 | true | true | Reusable async market-data client keeps rate-limit, retry, pagination, session, and fixture behavior in one public import contract. |
| `crypto_rsi_scanner.event_alpha.radar.asset_registry` | `CanonicalAsset` | 96 | true | true | Field-rich canonical identity value object; splitting fields from serialization would add indirection without reducing behavior risk. |
| `crypto_rsi_scanner.event_alpha.radar.watchlist_market` | `CoinGeckoWatchlistMarketProvider` | 116 | true | true | Fixture/live market enrichment adapter is below file-size gates and tightly coupled to request budgeting and no-live defaults. |
| `crypto_rsi_scanner.event_providers.binance_announcements.legacy` | `BinanceAnnouncementProvider` | 107 | true | true | Signed/public announcement compatibility core preserves old imports and WebSocket/fixture behavior. |
| `crypto_rsi_scanner.event_providers.bybit_announcements.legacy` | `BybitAnnouncementProvider` | 79 | true | true | Small HTTP announcement adapter is only slightly over the advisory class limit and already package-scoped. |
| `crypto_rsi_scanner.event_providers.cryptopanic.legacy` | `CryptoPanicProvider` | 340 | true | true | Compatibility class still owns request hygiene, token redaction, quota/ledger telemetry, parser normalization, and fixture/live no-call behavior. |
| `crypto_rsi_scanner.event_providers.gdelt` | `GdeltProvider` | 82 | true | true | No-key public provider is fail-soft and only slightly over the advisory limit. |
| `crypto_rsi_scanner.event_providers.prediction_market_events` | `PredictionMarketEventsProvider` | 83 | true | true | Small no-key prediction-market provider keeps fixture/live parsing in one stable adapter. |
| `crypto_rsi_scanner.event_providers.project_blog_rss` | `ProjectBlogRssProvider` | 96 | true | true | RSS/Atom adapter is tightly coupled to per-feed fail-soft behavior and source normalization. |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMRelationshipProvider` | 137 | true | true | OpenAI relationship provider keeps request assembly, timeout/error handling, and structured parsing together behind explicit opt-in gates. |
| `crypto_rsi_scanner.llm_providers.openai_provider` | `OpenAILLMExtractionProvider` | 78 | true | true | Small extraction provider is barely over the advisory threshold and shares safety semantics with the relationship provider. |
| `crypto_rsi_scanner.storage_parts.migrations` | `MigrationsMixin` | 88 | true | true | SQLite migration ownership is intentionally centralized to avoid untested schema drift. |
| `crypto_rsi_scanner.storage_parts.signals` | `SignalsMixin` | 129 | true | true | Signal persistence methods share schema assumptions, row serialization, and outcome lookup behavior. |
| `crypto_rsi_scanner.storage_parts.watchlist` | `WatchlistMixin` | 89 | true | true | Watchlist persistence methods are stable DB helpers and only slightly exceed the advisory limit. |

## Functions Over 150 Lines

| module | function | lines | public |
|---|---|---:|---:|
