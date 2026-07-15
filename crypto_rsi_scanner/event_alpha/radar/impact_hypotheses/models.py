"""Impact-hypothesis data models and enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping



class ImpactCategory(str, Enum):
    RWA_PREIPO_PROXY = "rwa_preipo_proxy"
    AI_IPO_PROXY = "ai_ipo_proxy"
    SPORTS_FAN_PROXY = "sports_fan_proxy"
    POLITICAL_MEME_PROXY = "political_meme_proxy"
    STABLECOIN_REGULATORY = "stablecoin_regulatory"
    TOKENIZED_STOCK_VENUE = "tokenized_stock_venue"
    PREDICTION_MARKET_INFRA = "prediction_market_infra"
    PERP_VENUE_ATTENTION = "perp_venue_attention"
    STRATEGIC_INVESTMENT_OR_VALUATION = "strategic_investment_or_valuation"
    UNLOCK_SUPPLY_PRESSURE = "unlock_supply_pressure"
    LISTING_LIQUIDITY_EVENT = "listing_liquidity_event"
    SECURITY_OR_REGULATORY_SHOCK = "security_or_regulatory_shock"
    MARKET_ANOMALY_UNKNOWN = "market_anomaly_unknown"


class HypothesisStatus(str, Enum):
    HYPOTHESIS = "hypothesis"
    VALIDATION_SEARCH_PENDING = "validation_search_pending"
    VALIDATION_EVIDENCE_FOUND = "validation_evidence_found"
    VALIDATED = "validated"
    REJECTED = "rejected"


class HypothesisScope(str, Enum):
    SECTOR = "sector"
    TOKEN = "token"
    VENUE = "venue"
    INFRASTRUCTURE = "infrastructure"


class ValidationStage(str, Enum):
    SECTOR_HYPOTHESIS = "sector_hypothesis"
    CANDIDATE_ASSETS_SUGGESTED = "candidate_assets_suggested"
    VALIDATION_SEARCH_PENDING = "validation_search_pending"
    SOURCE_MENTIONS_CANDIDATE = "source_mentions_candidate"
    IDENTITY_VALIDATED = "identity_validated"
    CATALYST_LINK_VALIDATED = "catalyst_link_validated"
    IMPACT_PATH_VALIDATED = "impact_path_validated"
    MARKET_CONFIRMED = "market_confirmed"
    PROMOTED_TO_RADAR = "promoted_to_radar"
    REJECTED = "rejected"


class ImpactPathReason(str, Enum):
    DIRECT_TOKEN_EVENT = "direct_token_event"
    VENUE_VALUE_CAPTURE = "venue_value_capture"
    FAN_TOKEN_EVENT = "fan_token_event"
    UNLOCK_SUPPLY_EVENT = "unlock_supply_event"
    LISTING_LIQUIDITY_EVENT = "listing_liquidity_event"
    STRATEGIC_INVESTMENT = "strategic_investment"
    EXPLOIT_SECURITY_EVENT = "exploit_security_event"
    ECOSYSTEM_SECURITY_EVENT = "ecosystem_security_event"
    CAUSE_UNKNOWN_MARKET_DISLOCATION = "cause_unknown_market_dislocation"
    ALLEGED_EXPLOIT_UNCONFIRMED = "alleged_exploit_unconfirmed"
    WEAK_COOCCURRENCE_ONLY = "weak_cooccurrence_only"
    GENERIC_POLICY_ONLY = "generic_policy_only"
    NO_VALUE_CAPTURE_EXPLAINED = "no_value_capture_explained"


@dataclass(frozen=True)
class _ImpactHypothesisIdentityFields:
    hypothesis_id: str
    event_cluster_id: str | None
    event_type: str
    external_asset: str | None
    impact_category: str
    candidate_sectors: tuple[str, ...]
    candidate_symbols: tuple[str, ...]
    candidate_coin_ids: tuple[str, ...] = ()
    suggested_candidate_assets: tuple[dict[str, Any], ...] = ()
    validated_candidate_assets: tuple[dict[str, Any], ...] = ()
    external_entities: tuple[dict[str, Any], ...] = ()
    crypto_candidate_assets: tuple[dict[str, Any], ...] = ()
    rejected_candidate_assets: tuple[dict[str, Any], ...] = ()
    candidate_source: str = "taxonomy"


@dataclass(frozen=True)
class _ImpactHypothesisValidationFields:
    hypothesis_scope: str = HypothesisScope.SECTOR.value
    direction_hint: str = "unknown"
    playbook_hint: str | None = None
    confidence: float = 0.0
    hypothesis_score: float = 0.0
    score_components: Mapping[str, float] = field(default_factory=dict)
    validation_stage: str = ValidationStage.SECTOR_HYPOTHESIS.value
    evidence_quotes: tuple[str, ...] = ()
    required_validation_steps: tuple[str, ...] = ()
    search_queries: tuple[str, ...] = ()
    search_query_details: tuple[dict[str, Any], ...] = ()
    generated_queries: tuple[dict[str, Any], ...] = ()
    executed_queries: tuple[dict[str, Any], ...] = ()
    status: str = HypothesisStatus.HYPOTHESIS.value
    warnings: tuple[str, ...] = ()
    source_raw_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    validation_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    rejected_validation_samples: tuple[dict[str, Any], ...] = ()
    why_not_promoted: tuple[str, ...] = ()
    impact_path_reason: str | None = None
    impact_path_type: str | None = None
    impact_path_strength: str | None = None
    candidate_role: str | None = None
    evidence_specificity_score: float | None = None
    required_evidence_met: bool | None = None
    market_confirmation_required: bool | None = None
    digest_eligible_by_impact_path: bool | None = None
    why_digest_ineligible: str | None = None
    opportunity_score_v2: float | None = None
    opportunity_score_components: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class _ImpactHypothesisMarketFields:
    evidence_quality_score: float | None = None
    source_class: str | None = None
    evidence_specificity: str | None = None
    evidence_quality_reasons: tuple[str, ...] = ()
    market_confirmation_score: float | None = None
    market_confirmation_level: str | None = None
    market_confirmation_reasons: tuple[str, ...] = ()
    market_confirmation_warnings: tuple[str, ...] = ()
    market_confirmation_missing_fields: tuple[str, ...] = ()
    market_confirmation_summary: str | None = None
    derivatives_confirmation_score: float | None = None
    derivatives_confirmation_level: str | None = None
    derivatives_confirmation_reasons: tuple[str, ...] = ()
    derivatives_freshness_status: str | None = None
    dex_liquidity_score: float | None = None
    dex_liquidity_level: str | None = None
    dex_liquidity_reasons: tuple[str, ...] = ()
    dex_freshness_status: str | None = None
    protocol_metrics_score: float | None = None
    protocol_metrics_level: str | None = None
    protocol_metrics_reasons: tuple[str, ...] = ()
    protocol_metrics_freshness_status: str | None = None
    market_context_source: str | None = None
    market_context_timestamp: str | None = None
    market_context_observed_at: str | None = None
    market_context_age_seconds: float | None = None
    market_context_age_hours: float | None = None
    market_context_stale: bool | None = None
    market_context_freshness_status: str | None = None
    market_context_freshness_cap_applied: bool | None = None
    market_context_data_quality: str | None = None
    market_context_snapshot: Mapping[str, Any] = field(default_factory=dict)
    market_reaction_confirmed: bool | None = None
    causal_mechanism_confirmed: bool | None = None


@dataclass(frozen=True)
class _ImpactHypothesisIncidentFields:
    incident_confidence: float | None = None
    incident_id: str | None = None
    incident_canonical_name: str | None = None
    incident_event_archetype: str | None = None
    incident_primary_subject: str | None = None
    incident_affected_ecosystem: str | None = None
    incident_cause_status: str | None = None
    incident_market_reaction_observed: bool | None = None
    incident_causal_mechanism_confirmed: bool | None = None
    incident_link_status: str | None = None
    incident_link_reason: str | None = None
    incident_relevance_status: str | None = None
    incident_relevance_score: float | None = None
    incident_relevance_reasons: tuple[str, ...] = ()
    incident_relevance_warnings: tuple[str, ...] = ()
    canonical_persistence_reason: str | None = None
    canonical_incident_name: str | None = None
    event_archetype: str | None = None
    primary_subject: str | None = None
    affected_entity: str | None = None
    affected_ecosystem: str | None = None
    role_confidence: float | None = None
    role_evidence: tuple[str, ...] = ()
    cause_status: str | None = None
    claim_polarities: tuple[str, ...] = ()
    claim_history: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class _ImpactHypothesisFrameFields:
    main_catalyst_frame_id: str | None = None
    main_frame_type: str | None = None
    main_frame_role: str | None = None
    main_frame_subject: str | None = None
    main_frame_actor: str | None = None
    main_frame_object: str | None = None
    main_frame_evidence_quote: str | None = None
    background_frame_ids: tuple[str, ...] = ()
    negated_frame_ids: tuple[str, ...] = ()
    corrective_frame_ids: tuple[str, ...] = ()
    frame_summary: tuple[dict[str, Any], ...] = ()
    background_context_summary: str | None = None
    rejected_impact_paths: tuple[str, ...] = ()
    rejected_impact_paths_from_background: tuple[str, ...] = ()
    selected_main_catalyst_reason: str | None = None
    rule_predicted_impact_path: str | None = None
    llm_predicted_main_frame_type: str | None = None
    frame_rule_disagreement: bool | None = None
    disagreement_resolution: str | None = None
    frame_required: bool = False
    frame_status: str | None = None
    frame_required_reason: str | None = None
    frame_gate_reason: str | None = None
    route_block_reason: str | None = None
    aggregated_candidate_id: str | None = None
    primary_impact_path: str | None = None
    supporting_categories: tuple[str, ...] = ()
    supporting_impact_paths: tuple[str, ...] = ()
    supporting_hypothesis_ids: tuple[str, ...] = ()
    supporting_evidence_quotes: tuple[str, ...] = ()
    supporting_hypothesis_count: int = 1


@dataclass(frozen=True)
class _ImpactHypothesisRoleVerdictFields:
    asset_role_source: str | None = None
    asset_kind: str | None = None
    role_source: str | None = None
    identity_confidence: float | None = None
    identity_evidence: tuple[str, ...] = ()
    collision_risk: str | None = None
    role_validation_failures: tuple[str, ...] = ()
    role_validation_warnings: tuple[str, ...] = ()
    role_capabilities: Mapping[str, bool] = field(default_factory=dict)
    independent_source_domains: tuple[str, ...] = ()
    independent_source_count: int | None = None
    independent_corroboration_count: int | None = None
    source_content_cluster_count: int | None = None
    source_independence: Mapping[str, Any] = field(default_factory=dict)
    source_independence_status: str = "unassessed"
    source_independence_errors: tuple[str, ...] = ()
    conflicting_claims: tuple[str, ...] = ()
    opportunity_score_final: float | None = None
    opportunity_level: str | None = None
    opportunity_verdict_reasons: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    manual_verification_items: tuple[str, ...] = ()
    why_local_only: str | None = None
    why_not_watchlist: str | None = None
    upgrade_requirements: tuple[str, ...] = ()
    downgrade_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ImpactHypothesisRefreshFields:
    market_refresh_attempted: bool | None = None
    market_refresh_success: bool | None = None
    market_refresh_provider: str | None = None
    market_refresh_error_class: str | None = None
    market_context_before: Mapping[str, Any] = field(default_factory=dict)
    market_context_after: Mapping[str, Any] = field(default_factory=dict)
    market_confirmation_before: float | None = None
    market_confirmation_after: float | None = None
    market_confirmation_before_refresh: float | None = None
    market_confirmation_after_refresh: float | None = None
    derivatives_refresh_attempted: bool | None = None
    derivatives_refresh_success: bool | None = None
    supply_refresh_attempted: bool | None = None
    supply_refresh_success: bool | None = None
    derivative_confirmation_reasons: tuple[str, ...] = ()
    supply_confirmation_reasons: tuple[str, ...] = ()
    evidence_refresh_attempted: bool | None = None
    evidence_refresh_results: tuple[dict[str, Any], ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    opportunity_level_before: str | None = None
    opportunity_level_after: str | None = None
    opportunity_score_before: float | None = None
    opportunity_score_after: float | None = None
    opportunity_level_before_refresh: str | None = None
    opportunity_level_after_refresh: str | None = None
    opportunity_score_before_refresh: float | None = None
    opportunity_score_after_refresh: float | None = None
    refresh_upgrade_status: str | None = None
    refresh_upgrade_reason: str | None = None
    upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class EventImpactHypothesis(
    _ImpactHypothesisRefreshFields,
    _ImpactHypothesisRoleVerdictFields,
    _ImpactHypothesisFrameFields,
    _ImpactHypothesisIncidentFields,
    _ImpactHypothesisMarketFields,
    _ImpactHypothesisValidationFields,
    _ImpactHypothesisIdentityFields,
):
    """Compatibility aggregate for Event Alpha impact-hypothesis fields."""
