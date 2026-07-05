# Event Alpha Radar North Star

Research-only architecture and burn-in operating contract. This document does not authorize live trading, Event Alpha paper trading, execution/order logic, normal RSI signal writes, Event Alpha-created `TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret handling changes.

- generated_at: `2026-07-05T19:40:13.395912+00:00`
- schema_version: `event_alpha_radar_north_star_v1`
- purpose: Align future Event Alpha work around a measurable crypto market radar and 30-day no-send burn-in contract.
- auto_apply_thresholds: `False`

## Radar Architecture

### asset_universe
- role: Defines the tradable asset universe and filters out quotes, sectors, themes, and proxy-only assets unless explicitly labeled.
- primary_artifacts: `event_asset_registry.json, event_instrument_resolution.jsonl`
- north_star_requirement: Every operator-visible opportunity should carry a canonical asset id or an explicit diagnostic reason.

### source_ingestion
- role: Collects official, structured, derivatives, market, protocol, and context evidence through fixture-first provider paths.
- primary_artifacts: `event_official_exchange_events.jsonl, event_evidence_acquisition.jsonl`
- north_star_requirement: Provider rows must preserve source URL, title/body evidence, published time, provider health, and no-live-default request posture.

### market_anomaly_scanner
- role: Finds broad market-first moves and creates catalyst-search queue items before promotion.
- primary_artifacts: `event_market_anomalies.jsonl, event_market_anomaly_catalyst_search_queue.jsonl`
- north_star_requirement: Market anomaly alone remains unconfirmed until structured or official evidence confirms the why-now.

### resolver
- role: Maps tickers, coin ids, exchange symbols, Coinalyze markets, and future contract/pool ids into canonical asset identity.
- primary_artifacts: `event_instrument_resolution.jsonl`
- north_star_requirement: Quote assets, simple BTC/ETH pair noise, and SECTOR/theme entities are capped or diagnostic by default.

### evidence_acquisition
- role: Targets missing source packs for near-misses and hypotheses without changing thresholds or routes automatically.
- primary_artifacts: `event_evidence_acquisition.jsonl`
- north_star_requirement: Evidence can upgrade research confidence only through deterministic source-pack sufficiency gates.

### market_state_builder
- role: Builds return, volume, liquidity, freshness, and relative-market context for candidates.
- primary_artifacts: `event_market_state.jsonl`
- north_star_requirement: Freshness and unit metadata must travel with state; stale state cannot promote fade-review or confirmed lanes.

### derivatives_crowding_layer
- role: Adds OI, funding, liquidations, long/short, basis, and perp/spot crowding evidence when provider artifacts exist.
- primary_artifacts: `event_derivatives_state.jsonl, event_derivatives_crowding_candidates.jsonl, event_fade_short_review_candidates.jsonl`
- north_star_requirement: Crowding warnings and fade-review evidence must be derived from deterministic derivatives state rows.

### opportunity_lane_classifier
- role: Assigns candidates to research lanes based on evidence, market state, derivatives, freshness, and source strength.
- primary_artifacts: `event_integrated_radar_candidates.jsonl, event_core_opportunities.jsonl`
- north_star_requirement: A lane is a research workflow label, not an instruction to trade.

### policy_routing_gates
- role: Applies quality, freshness, dedupe, source-strength, no-send, and safety blockers before any preview or delivery row.
- primary_artifacts: `event_alpha_notification_deliveries.jsonl`
- north_star_requirement: No route may bypass research-only/no-send guards, and Event Alpha never writes normal RSI rows or TRIGGERED_FADE.

### research_cards_notifications
- role: Produces operator-facing cards, daily brief sections, and guarded/no-send notification previews.
- primary_artifacts: `research_cards/, event_alpha_daily_brief.md, event_alpha_notification_preview.md`
- north_star_requirement: Copy must preserve research-only and not-a-trade-signal framing.

### outcome_tracker
- role: Matures rows with future market behavior labels for lane/source/provider usefulness analysis.
- primary_artifacts: `event_integrated_radar_outcomes.jsonl, event_radar_provider_performance.json`
- north_star_requirement: Outcomes measure future behavior; they do not auto-apply thresholds.

### human_labeling_inbox
- role: Focuses human review on active-learning gaps, near-misses, duplicates, source noise, and missing confirmation.
- primary_artifacts: `event_alpha_notification_inbox.md, event_alpha_feedback.jsonl`
- north_star_requirement: Labels are burn-in training evidence only and should shrink as provider/source yield improves.

### calibration_source_yield_loop
- role: Reports lane/provider/source-pack usefulness, noise, and maturation rates as recommendations-only priors.
- primary_artifacts: `event_integrated_radar_calibration_report.md, event_radar_performance_dashboard.md`
- north_star_requirement: All prior and threshold suggestions must carry auto_apply=false until a separate explicit decision changes policy.

## Opportunity Lanes

### EARLY_LONG_RESEARCH
- required_evidence:
  - fresh official/structured catalyst or strong accepted source-pack evidence
  - canonical tradable asset identity
  - market state is fresh enough to rule out stale promotion
- market_requirements:
  - move is not already fully completed
  - liquidity tier is not suspicious/illiquid
  - crowding is not extreme after the move
- what_confirms:
  - official listing/product/calendar/fundamental evidence appears
  - market reaction is early or orderly
  - source-pack sufficiency passes deterministic gates
- what_invalidates:
  - source is broad context only
  - asset match is ticker-only or theme/sector diagnostic
  - move is late with extreme crowding
- strict_blockers:
  - no source URL/title/time
  - simple BTC/ETH pair noise
  - low-liquidity suspicious move
  - stale market state
  - missing canonical id when resolver fixture has it
- outcome_labels:
  - continued
  - stalled
  - invalidated
  - confirmed_later
  - noise
- human_label_types:
  - useful
  - late
  - source_noise
  - duplicate
  - missing_confirmation
- provider_dependencies:
  - official exchange announcements
  - structured unlock/calendar
  - DEX/on-chain liquidity for DEX-native assets
  - protocol fundamentals when relevant
  - CryptoPanic/context only as support
- allowed_notification_route: research_review_digest or guarded no-send preview; strict send only after separate readiness approval

### CONFIRMED_LONG_RESEARCH
- required_evidence:
  - official or structured catalyst evidence
  - fresh market confirmation
  - canonical direct asset identity
  - source-pack sufficiency reason
- market_requirements:
  - liquidity sanity passes
  - market freshness is current
  - crowding warning is visible if derivatives show elevated crowding
- what_confirms:
  - official listing/perp/product/calendar evidence plus market response
  - structured source validates catalyst timing and asset
  - derivatives crowding is moderate or explicitly warned
- what_invalidates:
  - official source missing or stale
  - confirmed lane depends only on context/news
  - diagnostic/quote/theme entity is promoted
- strict_blockers:
  - confirmed without source plus market confirmation
  - CryptoPanic-only narrative promotion
  - crowding evidence hidden from card
  - no delivery ledger in live-call-allowed path
- outcome_labels:
  - continuation
  - failed_continuation
  - late_confirmation
  - noise
  - inconclusive
- human_label_types:
  - useful
  - late
  - missing_confirmation
  - duplicate
  - source_noise
- provider_dependencies:
  - Bybit/Binance official announcements
  - Coinalyze derivatives/OI/funding
  - structured calendar/unlock
  - DEX/protocol fundamentals when relevant
- allowed_notification_route: strict alert candidate only through guarded no-send rehearsal and send-readiness gates

### FADE_SHORT_REVIEW
- required_evidence:
  - completed move or event-passed state
  - deterministic crowding/exhaustion evidence
  - fresh derivatives state when derivatives are part of the proof
  - research-only disclaimer
- market_requirements:
  - move completion is visible
  - OI/funding/liquidation/perp-spot evidence indicates crowding or exhaustion
  - stale derivatives snapshots are blocked
- what_confirms:
  - crowding candidate and fade-review candidate share symbol/canonical id
  - event has passed or move has completed
  - card includes evidence and not-a-trade-signal wording
- what_invalidates:
  - no completed move
  - missing crowding evidence
  - stale derivatives state
  - normal RSI or TRIGGERED_FADE side effects
- strict_blockers:
  - FADE_SHORT_REVIEW missing crowding/exhaustion
  - stale derivatives snapshot promoted
  - triggered_fade_created > 0
  - normal_rsi_signal_rows_written > 0
  - missing research-only disclaimer
- outcome_labels:
  - exhaustion_followed
  - continued_squeeze
  - no_move
  - invalidated
  - inconclusive
- human_label_types:
  - useful
  - late
  - crowding_missing
  - duplicate
  - not_actionable
- provider_dependencies:
  - Coinalyze derivatives/OI/funding
  - market state builder
  - official/structured catalyst context
- allowed_notification_route: research-review/no-send preview only; never Event Alpha-created TRIGGERED_FADE

### RISK_ONLY
- required_evidence:
  - risk catalyst or deterioration evidence
  - structured source or strong source-pack evidence
  - explicit reason the row is not long research
- market_requirements:
  - risk context is fresh
  - low-liquidity suspicious moves remain diagnostic/risk-only
  - unlock/supply risk includes time and materiality metrics
- what_confirms:
  - unlock, delisting, security, regulatory, or fundamentals deterioration evidence is structured
  - market state supports risk framing
- what_invalidates:
  - missing event time
  - missing size/materiality metrics for unlock/supply risk
  - risk row promoted as early/confirmed long
- strict_blockers:
  - unlock promoted without structured source
  - unlock missing event time
  - missing size metrics promoted to risk/fade
  - delisting promoted as long research
- outcome_labels:
  - risk_validated
  - risk_failed
  - risk_too_late
  - noise
  - inconclusive
- human_label_types:
  - useful
  - late
  - source_noise
  - materiality_missing
  - duplicate
- provider_dependencies:
  - structured unlock/calendar
  - official exchange announcements
  - protocol fundamentals
  - market state builder
- allowed_notification_route: risk review section or no-send preview; not strict long alert

### UNCONFIRMED_RESEARCH
- required_evidence:
  - market anomaly, context, or weak catalyst evidence
  - explicit source plan or catalyst-search queue item
  - no_alert_until_evidence=true when anomaly-only
- market_requirements:
  - market move can be observed but does not prove catalyst identity
  - source gap is visible
  - low-confidence assets remain capped
- what_confirms:
  - official, structured, derivatives, DEX, protocol, or accepted source-pack evidence arrives
  - human label says useful and missing confirmation is later resolved
- what_invalidates:
  - no source plan
  - context-only source remains unsupported
  - duplicate/noise label
- strict_blockers:
  - promoted to confirmed without evidence
  - market anomaly without source plan
  - raw rejected/no-result evidence promoted
- outcome_labels:
  - later_confirmed
  - not_confirmed
  - noise
  - duplicate
  - inconclusive
- human_label_types:
  - useful
  - missing_confirmation
  - source_noise
  - duplicate
  - watch
- provider_dependencies:
  - catalyst search
  - CryptoPanic/context
  - RSS/GDELT context
  - official/structured follow-up packs
- allowed_notification_route: research-review digest only; no strict alert

### DIAGNOSTIC
- required_evidence:
  - reason row is not an opportunity
  - diagnostic/source-noise/quote/theme/proxy label
  - no visible default operator promotion
- market_requirements:
  - none required for opportunity promotion
  - diagnostic market state may be recorded for audit only
- what_confirms:
  - diagnostic reason remains accurate
  - row improves filters or source-quality rules
- what_invalidates:
  - diagnostic row appears as tradable opportunity
  - quote asset or SECTOR is visible as target asset
- strict_blockers:
  - DIAGNOSTIC included in main performance aggregate
  - diagnostic row visible in default operator section
  - quote asset misclassified as target
  - SECTOR visible as tradable
- outcome_labels:
  - true_noise
  - filter_gap
  - misclassified
  - duplicate
  - inconclusive
- human_label_types:
  - source_noise
  - duplicate
  - filter_gap
  - not_relevant
  - misclassified
- provider_dependencies:
  - resolver
  - source registry
  - artifact doctor
- allowed_notification_route: hidden by default; debug/audit only

## Human Labeling

- scope: `burn-in only`
- mode: `active-learning targeted review`
- labels_answer:
  - usefulness
  - lateness
  - source noise
  - duplication
  - missing confirmation
- outcomes_answer: future market behavior after the research row matures
- mature_system_goal: reduce labeling burden by using source-yield, near-miss, and outcome evidence to target only uncertain rows
- not_allowed:
  - manual labels do not auto-change thresholds
  - manual labels do not authorize sends, trades, paper trades, RSI writes, or TRIGGERED_FADE creation

## 30-Day Burn-In Contract

- duration_days: `30`
- min_live_no_send_cycles: `20`
- min_real_candidates: `300`
- min_human_labels: `150`
- min_labeled_near_misses: `50`
- min_outcome_rows: `100`
- auto_apply_thresholds: `False`
- no_auto_threshold_changes: `True`

### Promotion/Freeze Criteria

- EARLY_LONG_RESEARCH:
  - sufficient fresh source evidence and market sanity across burn-in samples
  - noise/late labels below reviewed-row tolerance
  - no strict blockers for stale market state or missing source plan
- CONFIRMED_LONG_RESEARCH:
  - continuation/outcome rate beats unconfirmed baseline with minimum samples
  - official/structured proof is present in cards and doctor checks
  - crowding warnings visible when derivatives are elevated
- FADE_SHORT_REVIEW:
  - exhaustion outcomes mature with crowding evidence present
  - no stale derivatives promotion
  - no Event Alpha-created TRIGGERED_FADE or normal RSI row side effects
- RISK_ONLY:
  - risk validation rate is useful and materiality fields are complete
  - risk rows do not leak into long lanes
- UNCONFIRMED_RESEARCH:
  - later-confirmation/noise rates identify useful source packs
  - unconfirmed rows stay out of strict alert routes
- DIAGNOSTIC:
  - diagnostic rows remain excluded from main performance aggregates
  - filter-gap labels feed recommendations only

### Freeze Criteria

- any lane has unresolved strict blockers
- auto_apply_thresholds is true
- minimum cycles/candidates/labels/outcomes are not met
- provider evidence is missing from cards or source coverage

## Source Activation Order

1. `coinalyze_derivatives_oi_funding`
2. `bybit_binance_official_announcements`
3. `structured_unlock_calendar`
4. `dex_onchain_liquidity`
5. `protocol_fundamentals`
6. `cryptopanic_context`
7. `rss_gdelt_context_only`

## Project-Health Doctor Contract

- north_star_document_missing: `warning`
- burn_in_contract_missing: `warning`
- auto_apply_thresholds_true: `blocker`

## Safety Invariants

- research_only: `True`
- no_live_trading: `True`
- no_event_alpha_paper_trading: `True`
- no_execution_order_logic: `True`
- no_event_alpha_rsi_signal_rows: `True`
- no_event_alpha_triggered_fade: `True`
- triggered_fade_source_boundary: `event_fade.py + proxy_fade only`
- telegram_sends_guarded: `True`
- no_live_provider_calls_by_default: `True`
- no_api_keys_in_tests: `True`
- no_secrets_printed_or_committed: `True`
