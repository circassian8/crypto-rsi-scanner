# Event Alpha Radar North Star — Catalyst Radar

Research-only Catalyst Radar architecture and burn-in operating contract. Event Alpha is additive beneath the trader-facing Crypto Decision Radar. This document does not authorize live trading, Event Alpha paper trading, execution/order logic, normal RSI signal writes, Event Alpha-created `TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret handling changes.

- generated_at: `2026-07-13T18:57:37.808371+00:00`
- schema_version: `event_alpha_radar_north_star_v1`
- purpose: Define Event Alpha as the additive Catalyst Radar beneath a canonical trader-facing Crypto Decision Radar while preserving the measurable 30-day no-send burn-in contract.
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
- role: Finds broad market-first moves, evaluates market-led actionability, and creates catalyst-search enrichment queue items.
- primary_artifacts: `event_market_anomalies.jsonl, event_market_anomaly_catalyst_search_queue.jsonl`
- north_star_requirement: A fresh, liquid, identity-safe anomaly may become actionable research without a known catalyst; unknown catalyst remains explicit and lowers evidence confidence.

### resolver
- role: Maps tickers, coin ids, exchange symbols, Coinalyze markets, and future contract/pool ids into canonical asset identity.
- primary_artifacts: `event_instrument_resolution.jsonl`
- north_star_requirement: Quote assets, simple BTC/ETH pair noise, and SECTOR/theme entities are capped or diagnostic by default.

### evidence_acquisition
- role: Targets missing source packs for near-misses and hypotheses without changing thresholds or routes automatically.
- primary_artifacts: `event_evidence_acquisition.jsonl`
- north_star_requirement: Evidence can upgrade research confidence only through deterministic source-pack sufficiency gates.

### market_state_builder
- role: Builds return, volume, liquidity, freshness, relative-market context, explicit feature bases, and bounded per-asset temporal baselines for candidates.
- primary_artifacts: `event_market_state.jsonl, event_market_history.jsonl`
- north_star_requirement: Freshness, unit, observation-id, warmup, and direct/proxy basis metadata must travel with state; stale state, proxy-only evidence, and unwarmed proxy anomaly inputs cannot be presented as urgent or actionable truth.

### market_provenance_v2
- role: Normalizes one closed market acquisition value, derives Decision Radar campaign eligibility/counting, and retains legacy burn-in fields as explicit compatibility metadata without accepting caller-asserted trust flags.
- primary_artifacts: `event_market_no_send_request_ledger.json, event_market_no_send_market_rows.json, event_market_no_send_generation.json, event_market_no_send_pilot_audit.json, event_market_no_send_attempts.jsonl, event_decision_radar_campaign_reservation.json`
- north_star_requirement: Only canonical crypto_radar_market_provenance_v2 live/no-send rows with explicit authorization, attempted and successful provider lineage, distinct fingerprinted request and source artifacts, generation identity, feature basis, and data quality may count in decision_radar_live_observation_campaign_v2; those rows never count in Event Alpha catalyst burn-in.

### derivatives_crowding_layer
- role: Adds OI, funding, liquidations, long/short, basis, and perp/spot crowding evidence when provider artifacts exist.
- primary_artifacts: `event_derivatives_state.jsonl, event_derivatives_crowding_candidates.jsonl, event_fade_short_review_candidates.jsonl`
- north_star_requirement: Crowding warnings and fade-review evidence must be derived from deterministic derivatives state rows.

### opportunity_lane_classifier
- role: Assigns candidates to research lanes based on evidence, market state, derivatives, freshness, and source strength.
- primary_artifacts: `event_integrated_radar_candidates.jsonl, event_core_opportunities.jsonl`
- north_star_requirement: A lane is a research workflow label, not an instruction to trade.

### crypto_radar_decision_model_v2
- role: Stores one closed trader-facing Decision v2 projection on each integrated candidate and copies it to CoreOpportunity, cards, Decision preview, outcomes, review inbox, and dashboard without partial downstream re-evaluation; operator state stores exact aggregates and artifact fingerprints derived from that authority.
- primary_artifacts: `event_integrated_radar_candidates.jsonl, event_core_opportunities.jsonl, event_decision_v2_notification_preview.md, event_integrated_radar_outcomes.jsonl, event_alpha_operator_state.json`
- north_star_requirement: Decision Radar routes are explicit research-only metadata. They are additive to Event Alpha catalyst lanes and never authorize delivery, paper trading, execution, RSI writes, or TRIGGERED_FADE.

### policy_routing_gates
- role: Applies quality, freshness, dedupe, source-strength, no-send, and safety blockers before any preview or delivery row.
- primary_artifacts: `event_alpha_notification_deliveries.jsonl`
- north_star_requirement: No route may bypass research-only/no-send guards, and Event Alpha never writes normal RSI rows or TRIGGERED_FADE.

### research_cards_notifications
- role: Produces Decision-first operator cards, daily brief sections, and guarded/no-send attention previews while retaining Catalyst Radar classification as a secondary compatibility section.
- primary_artifacts: `research_cards/, event_alpha_daily_brief.md, event_decision_v2_notification_preview.md, event_alpha_notification_preview.md`
- north_star_requirement: Copy must preserve research-only and human-decision-required framing; notifications route attention and never execution.

### outcome_tracker
- role: Creates one pending row for every current canonical Decision idea, then matures rows with future market behavior labels for route/origin/lane/source/provider usefulness analysis.
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

## Product Layering

- catalyst_radar: `{'name': 'Event Alpha', 'owns': ['catalyst discovery', 'source-strength classification', 'strict catalyst routes', 'historical Event Alpha artifacts']}`
- decision_radar: `{'name': 'Crypto Decision Radar', 'owns': ['canonical trader-facing Decision v2 projection', 'operator routes', 'Decision-first cards and preview', 'local read-only dashboard'], 'primary_surface': 'dashboard', 'notifications_role': 'route human attention, never execution'}`
- relationship: `additive`
- unknown_catalyst_policy: `soft explanatory-confidence penalty and risk input, not a universal visibility blocker`

## Crypto Radar Decision Model v2

- schema_version: `crypto_radar_decision_model_v2`
- canonical_projection_schema_version: `crypto_radar_decision_projection_v1`
- canonical_authority: `decision_model_values(raw_row) stored on the integrated candidate and copied downstream`
- projection_idempotent: `True`
- rendering_re_evaluates: `False`
- enabled_by_default_for_research_preview: `True`
- legacy_opportunity_type_preserved: `True`
- legacy_alert_routes_preserved: `True`
- old_artifacts_auto_promoted: `False`
- dimensions:
  - primary_and_contributing_thesis_origins: market_led, catalyst_led, technical_led, derivatives_led, onchain_led, fundamental_led, macro_led
  - legacy_thesis_origin: market_led, catalyst_led, technical_led, derivatives_led, onchain_led, fundamental_led, macro_led, mixed
  - directional_bias: long, fade_short_review, risk, neutral
  - catalyst_status: confirmed, plausible, unknown, not_required, disproven
  - confidence_band: diagnostic, exploratory, actionable, high_confidence
  - timing_state: early, active, extended, exhausted, scheduled, stale
  - market_phase: emerging, breakout, acceleration, active, extended, exhaustion, reversal
  - tradability_status: good, acceptable, poor, blocked
  - spread_status: verified_good, verified_acceptable, verified_wide, unavailable, stale
- decision_scores:
  - actionability_score
  - evidence_confidence_score
  - risk_score
  - urgency_score
  - chase_risk_score
- operator_routes:
  - dashboard_watch
  - actionable_watch
  - high_confidence_watch
  - rapid_market_anomaly
  - fade_exhaustion_review
  - risk_watch
  - calendar_risk
  - diagnostic
- hard_blockers:
  - unresolved identity
  - stale data
  - invalid market units
  - insufficient liquidity
  - extreme spread
  - suspicious illiquid move
  - duplicate
  - quote/theme/control entity
  - secret/path/safety failure
- soft_penalties:
  - unknown catalyst
  - missing official source or article
  - missing derivatives
  - missing optional confirmation
- market_led_actionability:
  - catalyst_required: `False`
  - requires_fresh_market_snapshot: `True`
  - requires_canonical_identity: `True`
  - requires_adequate_liquidity: `True`
  - requires_relative_move_or_stealth_accumulation: `True`
  - requires_meaningful_volume_anomaly: `True`
  - requires_verified_good_or_acceptable_spread_for_actionable_or_rapid: `True`
  - unavailable_spread_may_reach_dashboard_watch_only: `True`
  - invent_spread: `False`
- market_data_quality_caps:
  - missing_or_stale_spread_urgency_max: `55`
  - proxy_only_actionability_max: `64`
  - proxy_only_evidence_confidence_max: `55`
  - proxy_only_risk_min: `55`
  - proxy_only_urgency_max: `45`
  - cold_or_warming_baseline_evidence_confidence_max: `62`
  - cold_or_warming_baseline_risk_min: `48`
  - cold_or_warming_baseline_urgency_max: `45`
  - proxy_only_can_be_actionable_or_rapid: `False`
- canonical_context:
  - calendar event ids, categories, times or windows, time certainty, importance, and resolvable references
  - explicit read-only RSI context and artifact references
  - observation ids, source/provider lineage, evaluation timestamp, and safety attestations
- canonical_consistency:
  - candidate_core_route_or_score_drift: `blocker`
  - card_projection_drift: `blocker`
  - preview_lane_drift: `blocker`
  - outcome_cohort_drift: `blocker`
  - dashboard_projection_drift: `blocker`
  - calendar_risk_without_attached_evidence: `blocker`
- timing_contract:
  - preferred_horizon_and_expires_at_are_canonical: `True`
  - scheduled_evidence_may_raise_risk_and_shorten_expiry: `True`
  - calendar_alone_creates_directional_bias: `False`
  - stale_or_expired_idea_actionable: `False`
- return_unit_contract:
  - per_field_unit_metadata: `True`
  - fraction_0_10_normalized_percent: `10.0`
  - percent_points_10_0_normalized_percent: `10.0`
  - fraction_10_0: `blocker`
  - incompatible_mixed_units: `blocker`

## Decision-First Operator Surfaces

- Primary preview: `event_decision_v2_notification_preview.md`
- Sections: High-Confidence Ideas, Actionable Ideas, Rapid Market Anomalies, Dashboard Watch, Fade / Exhaustion Review, Risk Watch, and Calendar / Scheduled Risk.
- Cards lead with Crypto Decision Radar and retain Catalyst Radar Classification as a secondary strict-catalyst section.
- Dashboard is primary; notifications route attention; every surface remains research-only and human-decision-required.

## Guarded Real/No-Send Market Generation

- targets: radar-market-no-send-readiness, radar-market-no-send, radar-market-no-send-smoke, radar-market-campaign-report
- default_namespace: `radar_market_no_send`
- provider: `coingecko`
- run_mode: `operational`
- measurement_program:
  - name: `decision_radar_live_observation_campaign_v2`
  - event_alpha_catalyst_burn_in: `separate_not_aggregated`
  - campaign_report_target: `radar-market-campaign-report`
  - campaign_report_schema: `decision_radar_live_observation_campaign_report_v2`
  - campaign_report_provider_calls: `0`
  - historical_market_provenance_adapter: `read_only_no_rewrite`
- authorization:
  - existing_explicit_environment_flag: `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1`
  - inferred_from_cache: `False`
  - created_or_modified_by_application: `False`
  - absent_behavior: `safe blocked result, no provider call, bounded local no-send attempt/audit/campaign-report evidence, pointer unchanged`
  - eligible_invocation_live_request_max: `1`
- provenance_contract:
  - schema_version: `crypto_radar_market_provenance_v2`
  - contract_version: `2`
  - data_acquisition_modes: `['live_provider', 'mocked_fixture', 'artifact_replay', 'preflight_only', 'cache_replay']`
  - candidate_source_modes: `['live_no_send', 'mocked_fixture', 'artifact_replay', 'preflight_only']`
  - decision_radar_campaign_counting_is_derived: `True`
  - event_alpha_catalyst_burn_in_counted: `False`
  - decision_market_rows_counted_in_event_alpha_catalyst_burn_in: `False`
  - legacy_burn_in_fields: `read_only_compatibility_false_for_new_campaign_rows`
  - mock_or_fixture_may_validate_mechanics: `True`
  - mock_or_fixture_decision_campaign_counted: `False`
  - historical_flat_rows_silently_reclassified: `False`
- provenance_fields: data_acquisition_mode, candidate_source_mode, provider, provider_call_attempted, provider_call_succeeded, live_provider_authorized, request_ledger_path, request_ledger_sha256, provider_source_artifact, provider_source_artifact_sha256, provider_generation_id, cache_status, provenance_contract_valid, measurement_program, decision_radar_campaign_eligible, decision_radar_campaign_counted, decision_radar_campaign_reason, burn_in_eligible, burn_in_counted, burn_in_reason, feature_basis, data_quality, validation_errors
- temporal_baseline:
  - generation_snapshot_artifact: `event_market_history.jsonl`
  - shared_live_cache: `radar_market_history_cache/event_market_history.jsonl`
  - fixture_and_mock_cache_scope: `generation-local only; never seeds live history`
  - authoritative_namespace_mutation: `forbidden; use a new generation namespace backed by the bounded shared cache`
  - schema_id: `event_alpha.market_history_observation`
  - schema_version: `1`
  - default_limits: `{'max_history_age_days': 45, 'max_observations_per_asset': 256, 'min_baseline_observations': 8, 'max_current_age_hours': 6, 'future_tolerance_minutes': 5}`
  - cadence_policy: `{'configuration': 'RSI_DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES', 'default_minimum_observation_spacing_minutes': 60, 'too_close_observation_status': 'too_close', 'too_close_observations_retained': True, 'too_close_observations_count_in_baseline': False, 'rapid_cycles_advance_warmup': False, 'next_eligible_observation_at_reported': True, 'stable_base_root_receipt': 'event_decision_radar_campaign_reservation.json', 'state_directory_replacement_resets_spacing': False}`
  - feature_readiness_groups: `['volume', 'turnover', 'volatility', 'returns_1h', 'returns_4h', 'returns_24h', 'btc_eth_relative']`
  - required_feature_groups_must_all_be_warm: `True`
  - warmup_requires_feature_sample_and_horizon_coverage: `True`
  - baseline_excludes_current_observation: `True`
  - direct_provider_fields_preserved: `True`
  - only_explicit_proxy_fields_may_be_replaced: `True`
  - derived_evidence: `['1h/4h/24h returns in percent points', 'turnover and volume z-scores', 'return volatility', 'BTC and ETH relative returns', 'observation ids and baseline bounds']`
- outcome_policy:
  - pending_placeholder_per_canonical_decision_candidate: `True`
  - candidate_outcome_count_mismatch: `publication blocker`
  - cohort_drift: `blocker`
  - campaign_outcome_ledger: `radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl`
  - refresh_uses_local_artifacts_only: `True`
  - refresh_provider_calls: `0`
  - automatic_threshold_or_route_changes: `False`
- pilot_audit_artifacts: event_market_no_send_latest_attempt.json, event_market_no_send_pilot_audit.json, event_market_no_send_pilot_audit.md
- exact_attempt_policy:
  - doctor_and_publish_require_latest_cli_receipt_manifest_match: `True`
  - blocked_attempt_may_reuse_older_complete_manifest: `False`
  - provider_health_artifact: `event_provider_health.json`
  - provider_errors_persisted_as_safe_classes_only: `True`
  - bounded_attempt_ledger: `event_market_no_send_attempts.jsonl`
  - stable_provider_call_reservation: `event_decision_radar_campaign_reservation.json`
  - provider_call_reserved_before_network_boundary: `True`
- request_telemetry:
  - allowed_fields: `['endpoint_path', 'request_started_at', 'request_ended_at', 'duration_ms', 'http_status', 'result_count', 'retry_count', 'error_class', 'cache_behavior', 'live_provider_authorized', 'no_send']`
  - forbidden_content: `['query parameters', 'headers', 'tokens', 'raw response bodies', 'raw exception text', 'recipient identifiers']`
  - provider_health_must_reconcile: `True`
- market_context_lineage:
  - canonical_fields: `['source', 'observed_at', 'freshness_status', 'market_snapshot_id']`
  - copied_to: `['candidate', 'CoreOpportunity', 'card', 'preview', 'outcome', 'daily brief', 'dashboard']`
  - downstream_re_evaluation: `False`
  - lineage_drift: `strict doctor blocker`
- defaults:
  - research_only: `True`
  - no_sends: `True`
  - no_trades: `True`
  - no_paper_trades: `True`
  - no_normal_rsi_writes: `True`
  - no_triggered_fade: `True`
- dashboard_pointer_policy:
  - fixture_or_mock_generation_eligible: `False`
  - pointer_changes_on_blocked_failed_stale_or_untrusted_generation: `False`
  - current_authoritative_namespace_is_immutable: `True`
  - required_checks: `['real live-safe data mode', 'complete operator state', 'valid exact fingerprints', 'matching canonical counts', 'current run revision and operator-state binding', 'fresh full strict doctor with zero blockers']`
  - stable_authority_digest: `{'excluded_clock_only_fields': ['updated_at', 'doctor.verified_at'], 'unchanged_doctor_rerun_changes_pointer_identity': False, 'substantive_doctor_or_artifact_drift': 'blocker'}`
  - monotonic_authority_history: `{'fields': ['ever_authoritative', 'first_authoritative_at'], 'separate_from_current_pointer_readiness': True, 're_audit_erases_historical_authority': False}`

## Source + Artifacts Review Export

- target: `export-src-with-artifacts`
- fixed_utc_entry_timestamp: `True`
- default_timestamp: `1980-01-01T00:00:00Z`
- source_date_epoch: `honored only when wall-clock-safe`
- source_and_research_input_mtimes_mutated: `False`
- descriptor_anchored_symlink_toctou_checks_preserved: `True`
- configured_secret_scanning_preserved: `True`
- future_mtime_or_make_clock_skew_allowed: `False`

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
  - legacy strict-alert gate keeps no_alert_until_evidence=true when anomaly-only; v2 research previews are separate
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
- candidate_count_authority: `canonical Event Alpha catalyst rows with burn_in_counted=true; decision_radar_live_observation_campaign_v2 rows are excluded`
- mock_fixture_replay_cache_or_preflight_counted: `False`

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
- decision_support_requires_human: `True`
- dashboard_primary_notifications_attention_only: `True`
- no_live_trading: `True`
- no_event_alpha_paper_trading: `True`
- no_execution_order_logic: `True`
- no_event_alpha_rsi_signal_rows: `True`
- no_event_alpha_triggered_fade: `True`
- triggered_fade_source_boundary: `event_fade.py + proxy_fade only`
- telegram_sends_guarded: `True`
- no_live_provider_calls_by_default: `True`
- no_provider_calls_without_existing_explicit_authorization: `True`
- no_api_keys_in_tests: `True`
- no_secrets_printed_or_committed: `True`
- preserve_historical_artifacts_without_silent_reinterpretation: `True`
