"""Static Event Alpha Radar North Star contract writer.

This module writes architecture and burn-in contract artifacts only. It does not
import scanner/runtime provider code, call providers, send notifications, write
RSI rows, create paper trades, or create Event Alpha TRIGGERED_FADE rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .radar_north_star_campaign import MARKET_NO_SEND_GENERATION, REVIEW_EXPORT_POLICY
from .radar_north_star_evidence import (
    CATALYST_ATTRIBUTION_POLICY,
    LLM_CATALYST_FRAME_BINDING_POLICY,
    SOURCE_AUTHORITY_POLICY,
    SOURCE_INDEPENDENCE_POLICY,
    append_source_independence_north_star,
)
from .radar_north_star_shadow import (
    PROTOCOL_V2_EPISODE_COVERAGE_FRONTIER_POLICY,
    SHADOW_ANOMALY_EPISODE_POLICY,
    SHADOW_TEMPORAL_SURPRISE_POLICY,
    append_shadow_policies_north_star,
)

REPORT_SCHEMA_VERSION = "event_alpha_radar_north_star_v1"
REPORT_JSON = "EVENT_ALPHA_RADAR_NORTH_STAR.json"
REPORT_MD = "EVENT_ALPHA_RADAR_NORTH_STAR.md"
BURN_IN_CONTRACT_JSON = "event_alpha_burn_in_contract.json"
BURN_IN_CONTRACT_MD = "event_alpha_burn_in_contract.md"
LANE_NAMES = (
    "EARLY_LONG_RESEARCH",
    "CONFIRMED_LONG_RESEARCH",
    "FADE_SHORT_REVIEW",
    "RISK_ONLY",
    "UNCONFIRMED_RESEARCH",
    "DIAGNOSTIC",
)
SOURCE_ACTIVATION_ORDER = (
    "coinalyze_derivatives_oi_funding",
    "bybit_binance_official_announcements",
    "structured_unlock_calendar",
    "dex_onchain_liquidity",
    "protocol_fundamentals",
    "cryptopanic_context",
    "rss_gdelt_context_only",
)
ARCHITECTURE_COMPONENTS: dict[str, dict[str, Any]] = {
    "asset_universe": {
        "role": "Defines the tradable asset universe and filters out quotes, sectors, themes, and proxy-only assets unless explicitly labeled.",
        "primary_artifacts": ["event_asset_registry.json", "event_instrument_resolution.jsonl"],
        "north_star_requirement": "Every operator-visible opportunity should carry a canonical asset id or an explicit diagnostic reason.",
    },
    "source_ingestion": {
        "role": "Collects official, structured, derivatives, market, protocol, and context evidence through fixture-first provider paths.",
        "primary_artifacts": ["event_official_exchange_events.jsonl", "event_evidence_acquisition.jsonl"],
        "north_star_requirement": "Provider rows must preserve source URL, title/body evidence, published time, provider health, and no-live-default request posture.",
    },
    "market_anomaly_scanner": {
        "role": "Finds broad market-first moves, evaluates market-led actionability, and creates catalyst-search enrichment queue items.",
        "primary_artifacts": ["event_market_anomalies.jsonl", "event_market_anomaly_catalyst_search_queue.jsonl"],
        "north_star_requirement": "A fresh, liquid, identity-safe anomaly may become actionable research without a known catalyst; unknown catalyst remains explicit and lowers evidence confidence.",
    },
    "resolver": {
        "role": "Maps tickers, coin ids, exchange symbols, Coinalyze markets, and future contract/pool ids into canonical asset identity.",
        "primary_artifacts": ["event_instrument_resolution.jsonl"],
        "north_star_requirement": "Quote assets, simple BTC/ETH pair noise, and SECTOR/theme entities are capped or diagnostic by default.",
    },
    "evidence_acquisition": {
        "role": "Targets missing source packs for near-misses and hypotheses without changing thresholds or routes automatically.",
        "primary_artifacts": ["event_evidence_acquisition.jsonl"],
        "north_star_requirement": "Evidence can upgrade research confidence only through deterministic source-pack sufficiency gates.",
    },
    "catalyst_attribution": {
        "role": "Binds one exact source to one exact anomaly and separates source-public time, claimed event time, semantic role, and causal eligibility before Decision-v2 catalyst confidence is assigned.",
        "primary_artifacts": [
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_integrated_radar_outcomes.jsonl",
        ],
        "north_star_requirement": "A retrospective, background, historical, reaction, corrective, or unclocked source may remain visible context but cannot become antecedent causal confirmation merely because it is official or accepted.",
    },
    "source_independence": {
        "role": "Separates raw updates, canonical origins, content clusters, independent evidence units, and additional corroborations so syndicated or mirrored copies cannot masquerade as confirmation.",
        "primary_artifacts": [
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_integrated_radar_outcomes.jsonl",
        ],
        "north_star_requirement": "Only a closed origin-aware near-duplicate contract may support current source-diversity bonuses; missing or invalid contracts fail closed without reinterpreting historical rows.",
    },
    "market_state_builder": {
        "role": "Builds return, volume, liquidity, freshness, relative-market context, explicit feature bases, bounded per-asset temporal baselines, and isolated post-scan robust-surprise shadow evidence.",
        "primary_artifacts": ["event_market_state.jsonl", "event_market_history.jsonl"],
        "north_star_requirement": "Freshness, unit, observation-id, warmup, and direct/proxy basis metadata must travel with state; stale state, proxy-only evidence, and unwarmed proxy anomaly inputs cannot be presented as urgent or actionable truth. Robust surprise stays post-scan, routing-ineligible, threshold-free shadow metadata until outcome evidence supports a separate decision.",
    },
    "market_provenance_v2": {
        "role": "Normalizes one closed market acquisition value, derives Decision Radar campaign eligibility/counting, and retains legacy burn-in fields as explicit compatibility metadata without accepting caller-asserted trust flags.",
        "primary_artifacts": [
            "event_market_no_send_request_ledger.json",
            "event_market_no_send_market_rows.json",
            "event_market_no_send_generation.json",
            "event_market_no_send_pilot_audit.json",
            "event_market_no_send_attempts.jsonl",
            "event_decision_radar_campaign_reservation.json",
        ],
        "north_star_requirement": "Only canonical crypto_radar_market_provenance_v2 live/no-send rows with explicit authorization, attempted and successful provider lineage, distinct fingerprinted request and source artifacts, generation identity, feature basis, and data quality may count in decision_radar_live_observation_campaign_v2; those rows never count in Event Alpha catalyst burn-in.",
    },
    "derivatives_crowding_layer": {
        "role": "Adds OI, funding, liquidations, long/short, basis, and perp/spot crowding evidence when provider artifacts exist.",
        "primary_artifacts": [
            "event_derivatives_state.jsonl",
            "event_derivatives_crowding_candidates.jsonl",
            "event_fade_short_review_candidates.jsonl",
        ],
        "north_star_requirement": "Crowding warnings and fade-review evidence must be derived from deterministic derivatives state rows.",
    },
    "opportunity_lane_classifier": {
        "role": "Assigns candidates to research lanes based on evidence, market state, derivatives, freshness, and source strength.",
        "primary_artifacts": ["event_integrated_radar_candidates.jsonl", "event_core_opportunities.jsonl"],
        "north_star_requirement": "A lane is a research workflow label, not an instruction to trade.",
    },
    "crypto_radar_decision_model_v2": {
        "role": "Stores one closed trader-facing Decision v2 projection on each integrated candidate and copies it to CoreOpportunity, cards, Decision preview, outcomes, review inbox, and dashboard without partial downstream re-evaluation; operator state stores exact aggregates and artifact fingerprints derived from that authority.",
        "primary_artifacts": [
            "event_integrated_radar_candidates.jsonl", "event_core_opportunities.jsonl",
            "event_decision_v2_notification_preview.md", "event_integrated_radar_outcomes.jsonl",
            "event_alpha_operator_state.json",
        ],
        "north_star_requirement": "Decision Radar routes are explicit research-only metadata. They are additive to Event Alpha catalyst lanes and never authorize delivery, paper trading, execution, RSI writes, or TRIGGERED_FADE.",
    },
    "policy_routing_gates": {
        "role": "Applies quality, freshness, dedupe, source-strength, no-send, and safety blockers before any preview or delivery row.",
        "primary_artifacts": ["event_alpha_notification_deliveries.jsonl"],
        "north_star_requirement": "No route may bypass research-only/no-send guards, and Event Alpha never writes normal RSI rows or TRIGGERED_FADE.",
    },
    "research_cards_notifications": {
        "role": "Produces Decision-first operator cards, daily brief sections, and guarded/no-send attention previews while retaining Catalyst Radar classification as a secondary compatibility section.",
        "primary_artifacts": ["research_cards/", "event_alpha_daily_brief.md", "event_decision_v2_notification_preview.md", "event_alpha_notification_preview.md"],
        "north_star_requirement": "Copy must preserve research-only and human-decision-required framing; notifications route attention and never execution.",
    },
    "outcome_tracker": {
        "role": "Creates one pending row for every current canonical Decision idea, then matures rows with future market behavior labels for route/origin/lane/source/provider usefulness analysis.",
        "primary_artifacts": ["event_integrated_radar_outcomes.jsonl", "event_radar_provider_performance.json"],
        "north_star_requirement": "Outcomes measure future behavior; they do not auto-apply thresholds.",
    },
    "human_labeling_inbox": {
        "role": "Focuses human review on active-learning gaps, near-misses, duplicates, source noise, and missing confirmation.",
        "primary_artifacts": ["event_alpha_notification_inbox.md", "event_alpha_feedback.jsonl"],
        "north_star_requirement": "Labels are burn-in training evidence only and should shrink as provider/source yield improves.",
    },
    "calibration_source_yield_loop": {
        "role": "Reports lane/provider/source-pack usefulness, noise, and maturation rates as recommendations-only priors.",
        "primary_artifacts": ["event_integrated_radar_calibration_report.md", "event_radar_performance_dashboard.md"],
        "north_star_requirement": "All prior and threshold suggestions must carry auto_apply=false until a separate explicit decision changes policy.",
    },
}

DECISION_MODEL_V2: dict[str, Any] = {
    "schema_version": "crypto_radar_decision_model_v2",
    "canonical_projection": {
        "schema_version": "crypto_radar_decision_projection_v1",
        "authority": "decision_model_values(raw_row) stored on the integrated candidate and copied downstream",
        "idempotent": True,
        "rendering_re_evaluates": False,
    },
    "enabled_by_default_for_research_preview": True,
    "legacy_opportunity_type_preserved": True,
    "legacy_alert_routes_preserved": True,
    "legacy_mixed_thesis_origin_is_compatibility_only": True,
    "old_artifacts_auto_promoted": False,
    "dimensions": {
        "primary_and_contributing_thesis_origins": [
            "market_led", "catalyst_led", "technical_led", "derivatives_led",
            "onchain_led", "fundamental_led", "macro_led",
        ],
        "legacy_thesis_origin": [
            "market_led", "catalyst_led", "technical_led", "derivatives_led",
            "onchain_led", "fundamental_led", "macro_led", "mixed",
        ],
        "directional_bias": ["long", "fade_short_review", "risk", "neutral"],
        "catalyst_status": ["confirmed", "plausible", "unknown", "not_required", "disproven"],
        "confidence_band": ["diagnostic", "exploratory", "actionable", "high_confidence"],
        "timing_state": ["early", "active", "extended", "exhausted", "scheduled", "stale"],
        "market_phase": ["emerging", "breakout", "acceleration", "active", "extended", "exhaustion", "reversal"],
        "tradability_status": ["good", "acceptable", "poor", "blocked"],
        "spread_status": ["verified_good", "verified_acceptable", "verified_wide", "unavailable", "stale"],
    },
    "decision_scores": [
        "actionability_score", "evidence_confidence_score", "risk_score",
        "urgency_score", "chase_risk_score",
    ],
    "operator_routes": [
        "dashboard_watch",
        "actionable_watch",
        "high_confidence_watch",
        "rapid_market_anomaly",
        "fade_exhaustion_review",
        "risk_watch",
        "calendar_risk",
        "diagnostic",
    ],
    "canonical_context": [
        "calendar event ids, categories, times or windows, time certainty, importance, and resolvable references",
        "explicit read-only RSI context and artifact references",
        "observation ids, source/provider lineage, evaluation timestamp, and safety attestations",
    ],
    "canonical_consistency": {
        "candidate_core_route_or_score_drift": "blocker",
        "card_projection_drift": "blocker",
        "preview_lane_drift": "blocker",
        "outcome_cohort_drift": "blocker",
        "dashboard_projection_drift": "blocker",
        "calendar_risk_without_attached_evidence": "blocker",
    },
    "hard_blockers": [
        "unresolved identity",
        "stale data",
        "invalid market units",
        "insufficient liquidity",
        "extreme spread",
        "suspicious illiquid move",
        "duplicate",
        "quote/theme/control entity",
        "secret/path/safety failure",
    ],
    "soft_penalties": [
        "unknown catalyst",
        "missing official source or article",
        "missing derivatives",
        "missing optional confirmation",
    ],
    "market_led_actionability": {
        "catalyst_required": False,
        "requires_fresh_market_snapshot": True,
        "requires_canonical_identity": True,
        "requires_adequate_liquidity": True,
        "requires_relative_move_or_stealth_accumulation": True,
        "requires_meaningful_volume_anomaly": True,
        "requires_verified_good_or_acceptable_spread_for_actionable_or_rapid": True,
        "unavailable_spread_may_reach_dashboard_watch_only": True,
        "invent_spread": False,
    },
    "market_data_quality_caps": {
        "missing_or_stale_spread_urgency_max": 55,
        "proxy_only_actionability_max": 64,
        "proxy_only_evidence_confidence_max": 55,
        "proxy_only_risk_min": 55,
        "proxy_only_urgency_max": 45,
        "cold_or_warming_baseline_evidence_confidence_max": 62,
        "cold_or_warming_baseline_risk_min": 48,
        "cold_or_warming_baseline_urgency_max": 45,
        "proxy_only_can_be_actionable_or_rapid": False,
    },
    "timing_contract": {
        "preferred_horizon_and_expires_at_are_canonical": True,
        "scheduled_evidence_may_raise_risk_and_shorten_expiry": True,
        "calendar_alone_creates_directional_bias": False,
        "stale_or_expired_idea_actionable": False,
    },
    "unit_contract": {
        "per_field_unit_metadata": True,
        "fraction_0_10_normalized_percent": 10.0,
        "percent_points_10_0_normalized_percent": 10.0,
        "fraction_10_0": "blocker",
        "incompatible_mixed_units": "blocker",
    },
}

PRODUCT_LAYERS: dict[str, Any] = {
    "catalyst_radar": {
        "name": "Event Alpha",
        "owns": [
            "catalyst discovery",
            "source-strength classification",
            "strict catalyst routes",
            "historical Event Alpha artifacts",
        ],
    },
    "decision_radar": {
        "name": "Crypto Decision Radar",
        "owns": [
            "canonical trader-facing Decision v2 projection",
            "operator routes",
            "Decision-first cards and preview",
            "local read-only dashboard",
        ],
        "primary_surface": "dashboard",
        "notifications_role": "route human attention, never execution",
    },
    "relationship": "additive",
    "unknown_catalyst_policy": "soft explanatory-confidence penalty and risk input, not a universal visibility blocker",
}

OPPORTUNITY_LANES: dict[str, dict[str, Any]] = {
    "EARLY_LONG_RESEARCH": {
        "required_evidence": [
            "fresh official/structured catalyst or strong accepted source-pack evidence",
            "canonical tradable asset identity",
            "market state is fresh enough to rule out stale promotion",
        ],
        "market_requirements": [
            "move is not already fully completed",
            "liquidity tier is not suspicious/illiquid",
            "crowding is not extreme after the move",
        ],
        "what_confirms": [
            "official listing/product/calendar/fundamental evidence appears",
            "market reaction is early or orderly",
            "source-pack sufficiency passes deterministic gates",
        ],
        "what_invalidates": [
            "source is broad context only",
            "asset match is ticker-only or theme/sector diagnostic",
            "move is late with extreme crowding",
        ],
        "allowed_notification_route": "research_review_digest or guarded no-send preview; strict send only after separate readiness approval",
        "strict_blockers": [
            "no source URL/title/time",
            "simple BTC/ETH pair noise",
            "low-liquidity suspicious move",
            "stale market state",
            "missing canonical id when resolver fixture has it",
        ],
        "outcome_labels": ["continued", "stalled", "invalidated", "confirmed_later", "noise"],
        "human_label_types": ["useful", "late", "source_noise", "duplicate", "missing_confirmation"],
        "provider_dependencies": [
            "official exchange announcements",
            "structured unlock/calendar",
            "DEX/on-chain liquidity for DEX-native assets",
            "protocol fundamentals when relevant",
            "CryptoPanic/context only as support",
        ],
    },
    "CONFIRMED_LONG_RESEARCH": {
        "required_evidence": [
            "official or structured catalyst evidence",
            "fresh market confirmation",
            "canonical direct asset identity",
            "source-pack sufficiency reason",
        ],
        "market_requirements": [
            "liquidity sanity passes",
            "market freshness is current",
            "crowding warning is visible if derivatives show elevated crowding",
        ],
        "what_confirms": [
            "official listing/perp/product/calendar evidence plus market response",
            "structured source validates catalyst timing and asset",
            "derivatives crowding is moderate or explicitly warned",
        ],
        "what_invalidates": [
            "official source missing or stale",
            "confirmed lane depends only on context/news",
            "diagnostic/quote/theme entity is promoted",
        ],
        "allowed_notification_route": "strict alert candidate only through guarded no-send rehearsal and send-readiness gates",
        "strict_blockers": [
            "confirmed without source plus market confirmation",
            "CryptoPanic-only narrative promotion",
            "crowding evidence hidden from card",
            "no delivery ledger in live-call-allowed path",
        ],
        "outcome_labels": ["continuation", "failed_continuation", "late_confirmation", "noise", "inconclusive"],
        "human_label_types": ["useful", "late", "missing_confirmation", "duplicate", "source_noise"],
        "provider_dependencies": [
            "Bybit/Binance official announcements",
            "Coinalyze derivatives/OI/funding",
            "structured calendar/unlock",
            "DEX/protocol fundamentals when relevant",
        ],
    },
    "FADE_SHORT_REVIEW": {
        "required_evidence": [
            "completed move or event-passed state",
            "deterministic crowding/exhaustion evidence",
            "fresh derivatives state when derivatives are part of the proof",
            "research-only disclaimer",
        ],
        "market_requirements": [
            "move completion is visible",
            "OI/funding/liquidation/perp-spot evidence indicates crowding or exhaustion",
            "stale derivatives snapshots are blocked",
        ],
        "what_confirms": [
            "crowding candidate and fade-review candidate share symbol/canonical id",
            "event has passed or move has completed",
            "card includes evidence and not-a-trade-signal wording",
        ],
        "what_invalidates": [
            "no completed move",
            "missing crowding evidence",
            "stale derivatives state",
            "normal RSI or TRIGGERED_FADE side effects",
        ],
        "allowed_notification_route": "research-review/no-send preview only; never Event Alpha-created TRIGGERED_FADE",
        "strict_blockers": [
            "FADE_SHORT_REVIEW missing crowding/exhaustion",
            "stale derivatives snapshot promoted",
            "triggered_fade_created > 0",
            "normal_rsi_signal_rows_written > 0",
            "missing research-only disclaimer",
        ],
        "outcome_labels": ["exhaustion_followed", "continued_squeeze", "no_move", "invalidated", "inconclusive"],
        "human_label_types": ["useful", "late", "crowding_missing", "duplicate", "not_actionable"],
        "provider_dependencies": ["Coinalyze derivatives/OI/funding", "market state builder", "official/structured catalyst context"],
    },
    "RISK_ONLY": {
        "required_evidence": [
            "risk catalyst or deterioration evidence",
            "structured source or strong source-pack evidence",
            "explicit reason the row is not long research",
        ],
        "market_requirements": [
            "risk context is fresh",
            "low-liquidity suspicious moves remain diagnostic/risk-only",
            "unlock/supply risk includes time and materiality metrics",
        ],
        "what_confirms": [
            "unlock, delisting, security, regulatory, or fundamentals deterioration evidence is structured",
            "market state supports risk framing",
        ],
        "what_invalidates": [
            "missing event time",
            "missing size/materiality metrics for unlock/supply risk",
            "risk row promoted as early/confirmed long",
        ],
        "allowed_notification_route": "risk review section or no-send preview; not strict long alert",
        "strict_blockers": [
            "unlock promoted without structured source",
            "unlock missing event time",
            "missing size metrics promoted to risk/fade",
            "delisting promoted as long research",
        ],
        "outcome_labels": ["risk_validated", "risk_failed", "risk_too_late", "noise", "inconclusive"],
        "human_label_types": ["useful", "late", "source_noise", "materiality_missing", "duplicate"],
        "provider_dependencies": ["structured unlock/calendar", "official exchange announcements", "protocol fundamentals", "market state builder"],
    },
    "UNCONFIRMED_RESEARCH": {
        "required_evidence": [
            "market anomaly, context, or weak catalyst evidence",
            "explicit source plan or catalyst-search queue item",
            "legacy strict-alert gate keeps no_alert_until_evidence=true when anomaly-only; v2 research previews are separate",
        ],
        "market_requirements": [
            "market move can be observed but does not prove catalyst identity",
            "source gap is visible",
            "low-confidence assets remain capped",
        ],
        "what_confirms": [
            "official, structured, derivatives, DEX, protocol, or accepted source-pack evidence arrives",
            "human label says useful and missing confirmation is later resolved",
        ],
        "what_invalidates": [
            "no source plan",
            "context-only source remains unsupported",
            "duplicate/noise label",
        ],
        "allowed_notification_route": "research-review digest only; no strict alert",
        "strict_blockers": [
            "promoted to confirmed without evidence",
            "market anomaly without source plan",
            "raw rejected/no-result evidence promoted",
        ],
        "outcome_labels": ["later_confirmed", "not_confirmed", "noise", "duplicate", "inconclusive"],
        "human_label_types": ["useful", "missing_confirmation", "source_noise", "duplicate", "watch"],
        "provider_dependencies": ["catalyst search", "CryptoPanic/context", "RSS/GDELT context", "official/structured follow-up packs"],
    },
    "DIAGNOSTIC": {
        "required_evidence": [
            "reason row is not an opportunity",
            "diagnostic/source-noise/quote/theme/proxy label",
            "no visible default operator promotion",
        ],
        "market_requirements": [
            "none required for opportunity promotion",
            "diagnostic market state may be recorded for audit only",
        ],
        "what_confirms": [
            "diagnostic reason remains accurate",
            "row improves filters or source-quality rules",
        ],
        "what_invalidates": [
            "diagnostic row appears as tradable opportunity",
            "quote asset or SECTOR is visible as target asset",
        ],
        "allowed_notification_route": "hidden by default; debug/audit only",
        "strict_blockers": [
            "DIAGNOSTIC included in main performance aggregate",
            "diagnostic row visible in default operator section",
            "quote asset misclassified as target",
            "SECTOR visible as tradable",
        ],
        "outcome_labels": ["true_noise", "filter_gap", "misclassified", "duplicate", "inconclusive"],
        "human_label_types": ["source_noise", "duplicate", "filter_gap", "not_relevant", "misclassified"],
        "provider_dependencies": ["resolver", "source registry", "artifact doctor"],
    },
}
HUMAN_LABELING_ROLE = {
    "scope": "burn-in only",
    "mode": "active-learning targeted review",
    "labels_answer": ["usefulness", "lateness", "source noise", "duplication", "missing confirmation"],
    "outcomes_answer": "future market behavior after the research row matures",
    "mature_system_goal": "reduce labeling burden by using source-yield, near-miss, and outcome evidence to target only uncertain rows",
    "not_allowed": [
        "manual labels do not auto-change thresholds",
        "manual labels do not authorize sends, trades, paper trades, RSI writes, or TRIGGERED_FADE creation",
    ],
}
EVIDENCE_CYCLE_OPERATOR_AUTHORITY: dict[str, Any] = {
    "readiness_target": "event-alpha-evidence-cycle-readiness",
    "guarded_cycle_target": "event-alpha-evidence-validation-cycle",
    "profile_capability_is_current_authorization": False,
    "current_authorization_source": "already-present explicit environment/.env flags only",
    "readiness_side_effects": {
        "provider_calls": 0,
        "network_calls": 0,
        "writes": 0,
        "sends": 0,
    },
    "live_fixture_fallback": False,
    "rejected_live_local_inputs": ["fixture", "test", "mock", "replay"],
    "unavailable_until_real_adapter": ["coinalyze", "sports_fixtures"],
    "provider_health": "existing persisted event_source backoff/circuit breaker",
    "llm_requirement": (
        "optional; relationship, extractor, and catalyst-frame OpenAI stages each need "
        "matching current explicit authorization plus credential presence; fixture LLM stays offline"
    ),
    "request_bound_scope": (
        "evidence-acquisition planner fan-out only; excludes discovery, market, enrichment, "
        "and LLM requests"
    ),
    "guarded_cycle_requirements": [
        "bounded readiness pass",
        "at least one currently eligible genuine source",
        "unique namespace",
        "no-send",
        "CONFIRM=1",
    ],
    "absent_authorization_behavior": (
        "blocked before writes with zero provider calls and an artifact-preview next command"
    ),
}
BURN_IN_CONTRACT = {
    "duration_days": 30,
    "min_live_no_send_cycles": 20,
    "min_real_candidates": 300,
    "min_human_labels": 150,
    "min_labeled_near_misses": 50,
    "min_outcome_rows": 100,
    "auto_apply_thresholds": False,
    "no_auto_threshold_changes": True,
    "candidate_count_authority": "canonical Event Alpha catalyst rows with burn_in_counted=true; decision_radar_live_observation_campaign_v2 rows are excluded",
    "mock_fixture_replay_cache_or_preflight_counted": False,
    "promotion_freeze_criteria": {
        "EARLY_LONG_RESEARCH": [
            "sufficient fresh source evidence and market sanity across burn-in samples",
            "noise/late labels below reviewed-row tolerance",
            "no strict blockers for stale market state or missing source plan",
        ],
        "CONFIRMED_LONG_RESEARCH": [
            "continuation/outcome rate beats unconfirmed baseline with minimum samples",
            "official/structured proof is present in cards and doctor checks",
            "crowding warnings visible when derivatives are elevated",
        ],
        "FADE_SHORT_REVIEW": [
            "exhaustion outcomes mature with crowding evidence present",
            "no stale derivatives promotion",
            "no Event Alpha-created TRIGGERED_FADE or normal RSI row side effects",
        ],
        "RISK_ONLY": [
            "risk validation rate is useful and materiality fields are complete",
            "risk rows do not leak into long lanes",
        ],
        "UNCONFIRMED_RESEARCH": [
            "later-confirmation/noise rates identify useful source packs",
            "unconfirmed rows stay out of strict alert routes",
        ],
        "DIAGNOSTIC": [
            "diagnostic rows remain excluded from main performance aggregates",
            "filter-gap labels feed recommendations only",
        ],
    },
    "freeze_criteria": [
        "any lane has unresolved strict blockers",
        "auto_apply_thresholds is true",
        "minimum cycles/candidates/labels/outcomes are not met",
        "provider evidence is missing from cards or source coverage",
    ],
}


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def build_north_star(*, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "event_alpha_radar_north_star",
        "generated_at": generated,
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "live_provider_calls_allowed_by_default": False,
        "api_keys_required_for_tests": False,
        "purpose": "Define Event Alpha as the additive Catalyst Radar beneath a canonical trader-facing Crypto Decision Radar while preserving the measurable 30-day no-send burn-in contract.",
        "architecture": deepcopy(ARCHITECTURE_COMPONENTS),
        "source_authority_policy": deepcopy(SOURCE_AUTHORITY_POLICY),
        "llm_catalyst_frame_binding_policy": deepcopy(LLM_CATALYST_FRAME_BINDING_POLICY),
        "evidence_cycle_operator_authority": deepcopy(EVIDENCE_CYCLE_OPERATOR_AUTHORITY),
        "catalyst_attribution_policy": deepcopy(CATALYST_ATTRIBUTION_POLICY),
        "source_independence_policy": deepcopy(SOURCE_INDEPENDENCE_POLICY),
        "shadow_temporal_surprise_policy": deepcopy(SHADOW_TEMPORAL_SURPRISE_POLICY),
        "shadow_anomaly_episode_policy": deepcopy(SHADOW_ANOMALY_EPISODE_POLICY),
        "protocol_v2_episode_coverage_frontier_policy": deepcopy(
            PROTOCOL_V2_EPISODE_COVERAGE_FRONTIER_POLICY
        ),
        "product_layers": deepcopy(PRODUCT_LAYERS),
        "decision_model_v2": deepcopy(DECISION_MODEL_V2),
        "market_no_send_generation": deepcopy(MARKET_NO_SEND_GENERATION),
        "review_export_policy": deepcopy(REVIEW_EXPORT_POLICY),
        "opportunity_lanes": deepcopy(OPPORTUNITY_LANES),
        "human_labeling": deepcopy(HUMAN_LABELING_ROLE),
        "burn_in_contract": deepcopy(BURN_IN_CONTRACT),
        "source_activation_order": list(SOURCE_ACTIVATION_ORDER),
        "project_health_doctor_checks": {
            "north_star_document_missing": "warning",
            "burn_in_contract_missing": "warning",
            "auto_apply_thresholds_true": "blocker",
        },
        "safety_invariants": {
            "research_only": True,
            "decision_support_requires_human": True,
            "dashboard_primary_notifications_attention_only": True,
            "no_live_trading": True,
            "no_event_alpha_paper_trading": True,
            "no_execution_order_logic": True,
            "no_event_alpha_rsi_signal_rows": True,
            "no_event_alpha_triggered_fade": True,
            "triggered_fade_source_boundary": "event_fade.py + proxy_fade only",
            "telegram_sends_guarded": True,
            "no_live_provider_calls_by_default": True,
            "no_provider_calls_without_existing_explicit_authorization": True,
            "no_api_keys_in_tests": True,
            "no_secrets_printed_or_committed": True,
            "preserve_historical_artifacts_without_silent_reinterpretation": True,
        },
    }


def write_north_star(
    *,
    root: str | Path | None = None,
    out_dir: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_north_star(generated_at=generated_at)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_north_star(payload), encoding="utf-8")
    write_burn_in_contract(root=repo_root, out_dir=target, generated_at=generated_at)
    return json_path, md_path, payload


def build_burn_in_contract(*, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": "event_alpha_burn_in_contract_v1",
        "row_type": "event_alpha_burn_in_contract",
        "generated_at": generated,
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        **deepcopy(BURN_IN_CONTRACT),
        "opportunity_lanes": deepcopy(OPPORTUNITY_LANES),
        "human_labeling": deepcopy(HUMAN_LABELING_ROLE),
        "source_activation_order": list(SOURCE_ACTIVATION_ORDER),
        "safety_invariants": {
            "research_only": True,
            "no_live_trading": True,
            "no_event_alpha_paper_trading": True,
            "no_execution_order_logic": True,
            "no_event_alpha_rsi_signal_rows": True,
            "no_event_alpha_triggered_fade": True,
            "no_live_telegram_sends": True,
            "no_live_provider_calls_by_default": True,
            "no_api_keys_in_tests": True,
            "no_secrets": True,
        },
    }


def write_burn_in_contract(
    *,
    root: str | Path | None = None,
    out_dir: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_burn_in_contract(generated_at=generated_at)
    json_path = target / BURN_IN_CONTRACT_JSON
    md_path = target / BURN_IN_CONTRACT_MD
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_burn_in_contract(payload), encoding="utf-8")
    return json_path, md_path, payload


def check_burn_in_contract(
    *,
    root: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the authored burn-in contract without rewriting it."""
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    json_path = target / BURN_IN_CONTRACT_JSON
    md_path = target / BURN_IN_CONTRACT_MD
    errors: list[str] = []
    payload: Mapping[str, Any] | None = None
    if not json_path.is_file():
        errors.append("burn_in_contract_json_missing")
    else:
        try:
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                payload = loaded
            else:
                errors.append("burn_in_contract_json_not_object")
        except (OSError, json.JSONDecodeError):
            errors.append("burn_in_contract_json_invalid")
    markdown: str | None = None
    if not md_path.is_file():
        errors.append("burn_in_contract_markdown_missing")
    else:
        try:
            markdown = md_path.read_text(encoding="utf-8")
        except OSError:
            errors.append("burn_in_contract_markdown_unreadable")
    if payload is not None:
        if payload.get("schema_version") != "event_alpha_burn_in_contract_v1":
            errors.append("burn_in_contract_schema_invalid")
        if payload.get("row_type") != "event_alpha_burn_in_contract":
            errors.append("burn_in_contract_row_type_invalid")
        if payload.get("auto_apply_thresholds") is not False:
            errors.append("burn_in_contract_auto_apply_not_false")
        lanes = payload.get("opportunity_lanes") if isinstance(payload.get("opportunity_lanes"), Mapping) else {}
        missing_lanes = [lane for lane in LANE_NAMES if lane not in lanes]
        if missing_lanes:
            errors.append("burn_in_contract_lanes_missing:" + ",".join(missing_lanes))
        for field in (
            "research_only",
            "no_send_rehearsal",
        ):
            if payload.get(field) is not True:
                errors.append(f"burn_in_contract_{field}_not_true")
        for field in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        ):
            if type(payload.get(field)) is not int or payload.get(field) != 0:
                errors.append(f"burn_in_contract_{field}_not_zero")
        if markdown is not None and markdown != format_burn_in_contract(payload):
            errors.append("burn_in_contract_markdown_out_of_sync")
    return {
        "valid": not errors,
        "json_path": json_path.as_posix(),
        "markdown_path": md_path.as_posix(),
        "schema_version": payload.get("schema_version") if payload is not None else None,
        "auto_apply_thresholds": payload.get("auto_apply_thresholds") if payload is not None else None,
        "errors": errors,
    }


def north_star_status(*, root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    research = repo_root / "research"
    json_path = research / REPORT_JSON
    md_path = research / REPORT_MD
    contract_json_path = research / BURN_IN_CONTRACT_JSON
    contract_md_path = research / BURN_IN_CONTRACT_MD
    status: dict[str, Any] = {
        "json_path": json_path.relative_to(repo_root).as_posix(),
        "markdown_path": md_path.relative_to(repo_root).as_posix(),
        "json_present": json_path.exists(),
        "markdown_present": md_path.exists(),
        "contract_json_path": contract_json_path.relative_to(repo_root).as_posix(),
        "contract_markdown_path": contract_md_path.relative_to(repo_root).as_posix(),
        "contract_json_present": contract_json_path.exists(),
        "contract_markdown_present": contract_md_path.exists(),
        "document_present": json_path.exists() and md_path.exists(),
        "burn_in_contract_present": False,
        "all_lanes_present": False,
        "missing_lanes": list(LANE_NAMES),
        "auto_apply_thresholds": None,
        "warnings": [],
        "blockers": [],
    }
    payload: Mapping[str, Any] = {}
    if json_path.exists():
        try:
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                payload = loaded
            else:
                status["warnings"].append({"check": "north_star_json_invalid", "path": status["json_path"]})
        except (OSError, json.JSONDecodeError):
            status["warnings"].append({"check": "north_star_json_invalid", "path": status["json_path"]})
    if not json_path.exists() or not md_path.exists():
        status["warnings"].append({"check": "north_star_document_missing", "path": "research"})
    burn_in = payload.get("burn_in_contract") if isinstance(payload.get("burn_in_contract"), Mapping) else {}
    separate_burn_in: Mapping[str, Any] = {}
    if contract_json_path.exists():
        try:
            loaded_contract = json.loads(contract_json_path.read_text(encoding="utf-8"))
            if isinstance(loaded_contract, Mapping):
                separate_burn_in = loaded_contract
            else:
                status["warnings"].append({"check": "burn_in_contract_json_invalid", "path": status["contract_json_path"]})
        except (OSError, json.JSONDecodeError):
            status["warnings"].append({"check": "burn_in_contract_json_invalid", "path": status["contract_json_path"]})
    lanes = payload.get("opportunity_lanes") if isinstance(payload.get("opportunity_lanes"), Mapping) else {}
    missing_lanes = [lane for lane in LANE_NAMES if lane not in lanes]
    status["burn_in_contract_present"] = bool(burn_in) and contract_json_path.exists() and contract_md_path.exists()
    status["all_lanes_present"] = not missing_lanes
    status["missing_lanes"] = missing_lanes
    status["auto_apply_thresholds"] = (
        separate_burn_in.get("auto_apply_thresholds")
        if separate_burn_in
        else burn_in.get("auto_apply_thresholds") if burn_in else None
    )
    if not burn_in or not contract_json_path.exists() or not contract_md_path.exists():
        status["warnings"].append({"check": "burn_in_contract_missing", "path": status["json_path"]})
    if missing_lanes:
        status["warnings"].append({"check": "north_star_lanes_missing", "missing_lanes": missing_lanes})
    if burn_in.get("auto_apply_thresholds") is True or separate_burn_in.get("auto_apply_thresholds") is True:
        status["blockers"].append({"check": "auto_apply_thresholds_true", "path": status["json_path"]})
    return status


def format_burn_in_contract(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Burn-In Contract",
        "",
        "Research-only 30-day burn-in operating contract. This document does not authorize live trading, Event Alpha paper trading, execution/order logic, normal RSI signal writes, Event Alpha-created `TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret handling changes.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- duration_days: `{payload.get('duration_days')}`",
        f"- min_live_no_send_cycles: `{payload.get('min_live_no_send_cycles')}`",
        f"- min_real_candidates: `{payload.get('min_real_candidates')}`",
        f"- min_human_labels: `{payload.get('min_human_labels')}`",
        f"- min_labeled_near_misses: `{payload.get('min_labeled_near_misses')}`",
        f"- min_outcome_rows: `{payload.get('min_outcome_rows')}`",
        f"- auto_apply_thresholds: `{payload.get('auto_apply_thresholds')}`",
        f"- no_auto_threshold_changes: `{payload.get('no_auto_threshold_changes')}`",
        f"- candidate_count_authority: `{payload.get('candidate_count_authority')}`",
        "- mock_fixture_replay_cache_or_preflight_counted: "
        f"`{payload.get('mock_fixture_replay_cache_or_preflight_counted')}`",
        "",
        "## Opportunity Lanes",
        "",
    ]
    lanes = payload.get("opportunity_lanes") if isinstance(payload.get("opportunity_lanes"), Mapping) else {}
    for lane_name in LANE_NAMES:
        lane = lanes.get(lane_name)
        if not isinstance(lane, Mapping):
            continue
        lines.append(f"### {lane_name}")
        lines.append(f"- allowed_notification_route: {lane.get('allowed_notification_route')}")
        lines.append("- strict_blockers:")
        for item in lane.get("strict_blockers", []):
            lines.append(f"  - {item}")
        lines.append("- machine_outcome_labels:")
        for item in lane.get("outcome_labels", []):
            lines.append(f"  - {item}")
        lines.append("- human_label_types:")
        for item in lane.get("human_label_types", []):
            lines.append(f"  - {item}")
        lines.append("")
    lines.extend(["## Promotion/Freeze Criteria", ""])
    criteria = payload.get("promotion_freeze_criteria") if isinstance(payload.get("promotion_freeze_criteria"), Mapping) else {}
    for lane_name in LANE_NAMES:
        lines.append(f"- {lane_name}:")
        for item in criteria.get(lane_name, []):
            lines.append(f"  - {item}")
    lines.extend(["", "## Freeze Criteria", ""])
    for item in payload.get("freeze_criteria", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Safety", ""])
    for key, value in sorted((payload.get("safety_invariants") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _append_decision_model_north_star(
    lines: list[str],
    decision: Mapping[str, Any],
) -> None:
    projection = (
        decision.get("canonical_projection")
        if isinstance(decision.get("canonical_projection"), Mapping)
        else {}
    )
    lines.extend([
        "## Crypto Radar Decision Model v2",
        "",
        f"- schema_version: `{decision.get('schema_version')}`",
        f"- canonical_projection_schema_version: `{projection.get('schema_version')}`",
        f"- canonical_authority: `{projection.get('authority')}`",
        f"- projection_idempotent: `{projection.get('idempotent')}`",
        f"- rendering_re_evaluates: `{projection.get('rendering_re_evaluates')}`",
        f"- enabled_by_default_for_research_preview: `{decision.get('enabled_by_default_for_research_preview')}`",
        f"- legacy_opportunity_type_preserved: `{decision.get('legacy_opportunity_type_preserved')}`",
        f"- legacy_alert_routes_preserved: `{decision.get('legacy_alert_routes_preserved')}`",
        f"- old_artifacts_auto_promoted: `{decision.get('old_artifacts_auto_promoted')}`",
        "- dimensions:",
    ])
    for key, values in (decision.get("dimensions") or {}).items():
        lines.append(f"  - {key}: {', '.join(str(value) for value in values)}")
    for title, field in (
        ("decision_scores", "decision_scores"),
        ("operator_routes", "operator_routes"),
        ("hard_blockers", "hard_blockers"),
        ("soft_penalties", "soft_penalties"),
    ):
        lines.append(f"- {title}:")
        for item in decision.get(field, []):
            lines.append(f"  - {item}")
    market_led = (
        decision.get("market_led_actionability")
        if isinstance(decision.get("market_led_actionability"), Mapping)
        else {}
    )
    lines.append("- market_led_actionability:")
    for key, value in market_led.items():
        lines.append(f"  - {key}: `{value}`")
    quality_caps = (
        decision.get("market_data_quality_caps")
        if isinstance(decision.get("market_data_quality_caps"), Mapping)
        else {}
    )
    lines.append("- market_data_quality_caps:")
    for key, value in quality_caps.items():
        lines.append(f"  - {key}: `{value}`")
    for title, field in (
        ("canonical_context", "canonical_context"),
        ("canonical_consistency", "canonical_consistency"),
        ("timing_contract", "timing_contract"),
        ("return_unit_contract", "unit_contract"),
    ):
        value = decision.get(field)
        lines.append(f"- {title}:")
        if isinstance(value, Mapping):
            for key, child in value.items():
                lines.append(f"  - {key}: `{child}`")
        else:
            for item in value or ():
                lines.append(f"  - {item}")


def _append_source_authority_north_star(lines: list[str], payload: Mapping[str, Any]) -> None:
    source_authority = (
        payload.get("source_authority_policy")
        if isinstance(payload.get("source_authority_policy"), Mapping)
        else {}
    )
    lines.extend(["## Catalyst Source Authority", ""])
    for key, value in source_authority.items():
        if isinstance(value, Mapping):
            lines.append(f"- {key}:")
            for child_key, child in value.items():
                lines.append(f"  - {child_key}: `{child}`")
        elif isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")


def _append_catalyst_frame_binding_north_star(lines: list[str], payload: Mapping[str, Any]) -> None:
    policy = (
        payload.get("llm_catalyst_frame_binding_policy")
        if isinstance(payload.get("llm_catalyst_frame_binding_policy"), Mapping)
        else {}
    )
    lines.extend(["## LLM Catalyst-Frame Source Binding", ""])
    for key, value in policy.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")


def _append_catalyst_attribution_north_star(
    lines: list[str], payload: Mapping[str, Any]
) -> None:
    policy = (
        payload.get("catalyst_attribution_policy")
        if isinstance(payload.get("catalyst_attribution_policy"), Mapping)
        else {}
    )
    lines.extend(["## Catalyst Attribution and Causal Timing", ""])
    for key, value in policy.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")


def _append_evidence_cycle_operator_authority(
    lines: list[str], payload: Mapping[str, Any]
) -> None:
    authority = (
        payload.get("evidence_cycle_operator_authority")
        if isinstance(payload.get("evidence_cycle_operator_authority"), Mapping)
        else {}
    )
    side_effects = (
        authority.get("readiness_side_effects")
        if isinstance(authority.get("readiness_side_effects"), Mapping)
        else {}
    )
    fixture_fallback = authority.get("live_fixture_fallback")
    fixture_fallback_display = "forbidden" if fixture_fallback is False else fixture_fallback
    lines.extend(
        [
            "## Evidence-Cycle Operator Authority",
            "",
            f"- readiness_target: `{authority.get('readiness_target')}`",
            f"- guarded_cycle_target: `{authority.get('guarded_cycle_target')}`",
            "- profile_capability_is_current_authorization: "
            f"`{authority.get('profile_capability_is_current_authorization')}`",
            f"- current_authorization_source: `{authority.get('current_authorization_source')}`",
            "- readiness_side_effects: `"
            f"provider_calls={side_effects.get('provider_calls')}, "
            f"network_calls={side_effects.get('network_calls')}, "
            f"writes={side_effects.get('writes')}, sends={side_effects.get('sends')}`",
            f"- live_fixture_fallback: `{fixture_fallback_display}`",
            "- rejected_live_local_inputs: `"
            + ", ".join(str(item) for item in authority.get("rejected_live_local_inputs", []))
            + "`",
            "- unavailable_until_real_adapter: `"
            + ", ".join(str(item) for item in authority.get("unavailable_until_real_adapter", []))
            + "`",
            f"- provider_health: `{authority.get('provider_health')}`",
            f"- LLM_requirement: `{authority.get('llm_requirement')}`",
            f"- request_bound_scope: `{authority.get('request_bound_scope')}`",
            "- guarded_cycle_requirements: `"
            + ", ".join(str(item) for item in authority.get("guarded_cycle_requirements", []))
            + "`",
            f"- absent_authorization_behavior: `{authority.get('absent_authorization_behavior')}`",
            "",
        ]
    )


def format_north_star(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Radar North Star — Catalyst Radar",
        "",
        "Research-only Catalyst Radar architecture and burn-in operating contract. Event Alpha is additive beneath the trader-facing Crypto Decision Radar. This document does not authorize live trading, Event Alpha paper trading, execution/order logic, normal RSI signal writes, Event Alpha-created `TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret handling changes.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- purpose: {payload.get('purpose')}",
        f"- auto_apply_thresholds: `{_burn_in(payload).get('auto_apply_thresholds')}`",
        "",
        "## Radar Architecture",
        "",
    ]
    architecture = payload.get("architecture") if isinstance(payload.get("architecture"), Mapping) else {}
    for key, row in architecture.items():
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"### {key}",
                f"- role: {row.get('role')}",
                f"- primary_artifacts: `{', '.join(str(item) for item in row.get('primary_artifacts', []))}`",
                f"- north_star_requirement: {row.get('north_star_requirement')}",
                "",
            ]
        )
    _append_source_authority_north_star(lines, payload)
    _append_catalyst_frame_binding_north_star(lines, payload)
    _append_catalyst_attribution_north_star(lines, payload)
    append_source_independence_north_star(lines, payload)
    append_shadow_policies_north_star(lines, payload)
    layers = payload.get("product_layers") if isinstance(payload.get("product_layers"), Mapping) else {}
    lines.extend(["## Product Layering", ""])
    for key, value in layers.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    decision = (
        payload.get("decision_model_v2")
        if isinstance(payload.get("decision_model_v2"), Mapping)
        else {}
    )
    _append_decision_model_north_star(lines, decision)
    lines.extend(
        [
            "",
            "## Decision-First Operator Surfaces",
            "",
            "- Primary preview: `event_decision_v2_notification_preview.md`",
            "- Sections: High-Confidence Ideas, Actionable Ideas, Rapid Market Anomalies, Dashboard Watch, Fade / Exhaustion Review, Risk Watch, and Calendar / Scheduled Risk.",
            "- Cards lead with Crypto Decision Radar and retain Catalyst Radar Classification as a secondary strict-catalyst section.",
            "- Dashboard is primary; notifications route attention; every surface remains research-only and human-decision-required.",
            "",
        ]
    )
    _append_evidence_cycle_operator_authority(lines, payload)
    lines.extend(["## Guarded Real/No-Send Market Generation", ""])
    market_generation = payload.get("market_no_send_generation") if isinstance(payload.get("market_no_send_generation"), Mapping) else {}
    for key, value in market_generation.items():
        if isinstance(value, Mapping):
            lines.append(f"- {key}:")
            for child_key, child in value.items():
                lines.append(f"  - {child_key}: `{child}`")
        elif isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"- {key}: `{value}`")
    export_policy = (
        payload.get("review_export_policy")
        if isinstance(payload.get("review_export_policy"), Mapping)
        else {}
    )
    lines.extend(["", "## Source + Artifacts Review Export", ""])
    for key, value in export_policy.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Opportunity Lanes", ""])
    lanes = payload.get("opportunity_lanes") if isinstance(payload.get("opportunity_lanes"), Mapping) else {}
    for lane_name in LANE_NAMES:
        lane = lanes.get(lane_name)
        if not isinstance(lane, Mapping):
            continue
        lines.append(f"### {lane_name}")
        for field in (
            "required_evidence",
            "market_requirements",
            "what_confirms",
            "what_invalidates",
            "strict_blockers",
            "outcome_labels",
            "human_label_types",
            "provider_dependencies",
        ):
            lines.append(f"- {field}:")
            for item in lane.get(field, []):
                lines.append(f"  - {item}")
        lines.append(f"- allowed_notification_route: {lane.get('allowed_notification_route')}")
        lines.append("")
    lines.extend(["## Human Labeling", ""])
    labeling = payload.get("human_labeling") if isinstance(payload.get("human_labeling"), Mapping) else {}
    lines.append(f"- scope: `{labeling.get('scope')}`")
    lines.append(f"- mode: `{labeling.get('mode')}`")
    lines.append("- labels_answer:")
    for item in labeling.get("labels_answer", []):
        lines.append(f"  - {item}")
    lines.append(f"- outcomes_answer: {labeling.get('outcomes_answer')}")
    lines.append(f"- mature_system_goal: {labeling.get('mature_system_goal')}")
    lines.append("- not_allowed:")
    for item in labeling.get("not_allowed", []):
        lines.append(f"  - {item}")
    lines.extend(["", "## 30-Day Burn-In Contract", ""])
    burn_in = _burn_in(payload)
    for field in (
        "duration_days",
        "min_live_no_send_cycles",
        "min_real_candidates",
        "min_human_labels",
        "min_labeled_near_misses",
        "min_outcome_rows",
        "auto_apply_thresholds",
        "no_auto_threshold_changes",
    ):
        lines.append(f"- {field}: `{burn_in.get(field)}`")
    lines.extend(
        [
            f"- candidate_count_authority: `{burn_in.get('candidate_count_authority')}`",
            "- mock_fixture_replay_cache_or_preflight_counted: "
            f"`{burn_in.get('mock_fixture_replay_cache_or_preflight_counted')}`",
        ]
    )
    lines.extend(["", "### Promotion/Freeze Criteria", ""])
    criteria = burn_in.get("promotion_freeze_criteria") if isinstance(burn_in.get("promotion_freeze_criteria"), Mapping) else {}
    for lane_name in LANE_NAMES:
        lines.append(f"- {lane_name}:")
        for item in criteria.get(lane_name, []):
            lines.append(f"  - {item}")
    lines.extend(["", "### Freeze Criteria", ""])
    for item in burn_in.get("freeze_criteria", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Source Activation Order", ""])
    for index, source in enumerate(payload.get("source_activation_order", []), start=1):
        lines.append(f"{index}. `{source}`")
    lines.extend(["", "## Project-Health Doctor Contract", ""])
    checks = payload.get("project_health_doctor_checks") if isinstance(payload.get("project_health_doctor_checks"), Mapping) else {}
    for check, severity in checks.items():
        lines.append(f"- {check}: `{severity}`")
    lines.extend(["", "## Safety Invariants", ""])
    invariants = payload.get("safety_invariants") if isinstance(payload.get("safety_invariants"), Mapping) else {}
    for key, value in invariants.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _burn_in(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    burn_in = payload.get("burn_in_contract")
    return burn_in if isinstance(burn_in, Mapping) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or validate the Event Alpha Radar North Star contract.")
    parser.add_argument("--out-dir", default="research")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--burn-in-contract-only", action="store_true")
    mode.add_argument("--check-burn-in-contract", action="store_true")
    args = parser.parse_args(argv)
    if args.check_burn_in_contract:
        status = check_burn_in_contract(out_dir=args.out_dir)
        print(status["json_path"])
        print(status["markdown_path"])
        print(f"schema_version={status['schema_version']}")
        print(f"auto_apply_thresholds={status['auto_apply_thresholds']}")
        if status["errors"]:
            print("burn_in_contract_check=failed:" + ",".join(status["errors"]), file=sys.stderr)
            return 1
        print("burn_in_contract_check=passed")
        print("No files, providers, Telegram sends, trades, paper trades, RSI rows, or Event Alpha TRIGGERED_FADE were changed.")
        return 0
    if args.burn_in_contract_only:
        json_path, md_path, payload = write_burn_in_contract(out_dir=args.out_dir)
        print(json_path)
        print(md_path)
        print(f"schema_version={payload['schema_version']}")
        print(f"auto_apply_thresholds={payload['auto_apply_thresholds']}")
        print("No providers, Telegram sends, trades, paper trades, RSI rows, or Event Alpha TRIGGERED_FADE were changed.")
        return 0
    json_path, md_path, payload = write_north_star(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"schema_version={payload['schema_version']}")
    print(f"lanes={len(payload['opportunity_lanes'])}")
    print(f"auto_apply_thresholds={payload['burn_in_contract']['auto_apply_thresholds']}")
    print("No providers, Telegram sends, trades, paper trades, RSI rows, or Event Alpha TRIGGERED_FADE were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
