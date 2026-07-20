# Event Alpha Burn-In Contract

Research-only 30-day burn-in operating contract. This document does not authorize live trading, Event Alpha paper trading, execution/order logic, normal RSI signal writes, Event Alpha-created `TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret handling changes.

- generated_at: `2026-07-20T07:55:07.903007+00:00`
- schema_version: `event_alpha_burn_in_contract_v1`
- duration_days: `30`
- min_live_no_send_cycles: `20`
- min_real_candidates: `300`
- min_human_labels: `150`
- min_labeled_near_misses: `50`
- min_outcome_rows: `100`
- auto_apply_thresholds: `False`
- no_auto_threshold_changes: `True`
- candidate_count_authority: `canonical Event Alpha catalyst rows with burn_in_counted=true; decision_radar_live_observation_campaign_v2 rows are excluded`
- mock_fixture_replay_cache_or_preflight_counted: `False`

## Opportunity Lanes

### EARLY_LONG_RESEARCH
- allowed_notification_route: research_review_digest or guarded no-send preview; strict send only after separate readiness approval
- strict_blockers:
  - no source URL/title/time
  - simple BTC/ETH pair noise
  - low-liquidity suspicious move
  - stale market state
  - missing canonical id when resolver fixture has it
- machine_outcome_labels:
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

### CONFIRMED_LONG_RESEARCH
- allowed_notification_route: strict alert candidate only through guarded no-send rehearsal and send-readiness gates
- strict_blockers:
  - confirmed without source plus market confirmation
  - CryptoPanic-only narrative promotion
  - crowding evidence hidden from card
  - no delivery ledger in live-call-allowed path
- machine_outcome_labels:
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

### FADE_SHORT_REVIEW
- allowed_notification_route: research-review/no-send preview only; never Event Alpha-created TRIGGERED_FADE
- strict_blockers:
  - FADE_SHORT_REVIEW missing crowding/exhaustion
  - stale derivatives snapshot promoted
  - triggered_fade_created > 0
  - normal_rsi_signal_rows_written > 0
  - missing research-only disclaimer
- machine_outcome_labels:
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

### RISK_ONLY
- allowed_notification_route: risk review section or no-send preview; not strict long alert
- strict_blockers:
  - unlock promoted without structured source
  - unlock missing event time
  - missing size metrics promoted to risk/fade
  - delisting promoted as long research
- machine_outcome_labels:
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

### UNCONFIRMED_RESEARCH
- allowed_notification_route: research-review digest only; no strict alert
- strict_blockers:
  - promoted to confirmed without evidence
  - market anomaly without source plan
  - raw rejected/no-result evidence promoted
- machine_outcome_labels:
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

### DIAGNOSTIC
- allowed_notification_route: hidden by default; debug/audit only
- strict_blockers:
  - DIAGNOSTIC included in main performance aggregate
  - diagnostic row visible in default operator section
  - quote asset misclassified as target
  - SECTOR visible as tradable
- machine_outcome_labels:
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

## Promotion/Freeze Criteria

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

## Freeze Criteria

- any lane has unresolved strict blockers
- auto_apply_thresholds is true
- minimum cycles/candidates/labels/outcomes are not met
- provider evidence is missing from cards or source coverage

## Safety

- no_api_keys_in_tests: `True`
- no_event_alpha_paper_trading: `True`
- no_event_alpha_rsi_signal_rows: `True`
- no_event_alpha_triggered_fade: `True`
- no_execution_order_logic: `True`
- no_live_provider_calls_by_default: `True`
- no_live_telegram_sends: `True`
- no_live_trading: `True`
- no_secrets: `True`
- research_only: `True`
