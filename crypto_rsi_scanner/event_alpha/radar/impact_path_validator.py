"""Pure impact-path validation for Event Alpha hypotheses.

This layer answers a narrower question than the resolver/classifier: does the
source explain *why* a catalyst could affect the candidate token, venue, or
sector? It is research-only metadata and cannot create alerts, trades, paper
rows, or event-fade triggers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from ... import event_catalyst_frames, event_claim_semantics, event_identity, event_incident_graph
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ...event_resolver import clean_text


class ImpactPathType(str, Enum):
    DIRECT_TOKEN_EVENT = "direct_token_event"
    STRATEGIC_INVESTMENT_OR_VALUATION = "strategic_investment_or_valuation"
    LISTING_LIQUIDITY_EVENT = "listing_liquidity_event"
    UNLOCK_SUPPLY_EVENT = "unlock_supply_event"
    EXPLOIT_SECURITY_EVENT = "exploit_security_event"
    VENUE_VALUE_CAPTURE = "venue_value_capture"
    PROXY_ATTENTION = "proxy_attention"
    FAN_TOKEN_ATTENTION = "fan_token_attention"
    REGULATORY_POLICY_EXPOSURE = "regulatory_policy_exposure"
    MARKET_STRUCTURE_POLICY = "market_structure_policy"
    TECHNOLOGY_RISK = "technology_risk"
    MACRO_ATTENTION_ONLY = "macro_attention_only"
    MARKET_DISLOCATION_UNKNOWN = "market_dislocation_unknown"
    GENERIC_COOCCURRENCE_ONLY = "generic_cooccurrence_only"
    UNKNOWN = "unknown"


class CandidateRole(str, Enum):
    DIRECT_SUBJECT = "direct_subject"
    ECOSYSTEM_AFFECTED_ASSET = "ecosystem_affected_asset"
    PROXY_INSTRUMENT = "proxy_instrument"
    PROXY_VENUE = "proxy_venue"
    INFRASTRUCTURE_PROVIDER = "infrastructure_provider"
    ECOSYSTEM_BENEFICIARY = "ecosystem_beneficiary"
    COMPETITOR_BENEFICIARY = "competitor_beneficiary"
    MACRO_AFFECTED_ASSET = "macro_affected_asset"
    GENERIC_MENTION = "generic_mention"


class ImpactPathStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    NONE = "none"


@dataclass(frozen=True)
class ImpactPathValidation:
    impact_path_type: str
    impact_path_strength: str
    candidate_role: str
    evidence_specificity_score: float
    required_evidence_met: bool
    market_confirmation_required: bool
    digest_eligible_by_impact_path: bool
    why_digest_ineligible: str | None
    impact_path_reason: str
    opportunity_score_v2: float
    opportunity_score_components: Mapping[str, float] = field(default_factory=dict)
    primary_subject: str | None = None
    affected_entity: str | None = None
    affected_ecosystem: str | None = None
    role_confidence: float | None = None
    role_evidence: tuple[str, ...] = ()
    cause_status: str | None = None
    claim_polarities: tuple[str, ...] = ()
    asset_kind: str | None = None
    role_source: str | None = None
    identity_confidence: float | None = None
    identity_evidence: tuple[str, ...] = ()
    collision_risk: str | None = None
    role_validation_failures: tuple[str, ...] = ()
    role_validation_warnings: tuple[str, ...] = ()
    role_capabilities: Mapping[str, bool] = field(default_factory=dict)


_DIRECT_EVENT_CATEGORIES = {
    "listing_liquidity_event",
    "strategic_investment_or_valuation",
    "unlock_supply_pressure",
    "security_or_regulatory_shock",
    "stablecoin_regulatory",
}
_PROXY_CATEGORIES = {
    "rwa_preipo_proxy",
    "ai_ipo_proxy",
    "tokenized_stock_venue",
    "sports_fan_proxy",
    "political_meme_proxy",
}
_INFRA_CATEGORIES = {"prediction_market_infra"}
_ImpactClassification = tuple[str, str, str, str]


@dataclass(frozen=True)
class _ImpactPathContext:
    text: str
    claims: tuple[event_claim_semantics.EventClaim, ...]
    main_frame: event_catalyst_frames.EventCatalystFrame | None
    supporting_frames: tuple[event_catalyst_frames.EventCatalystFrame, ...]
    primary_subject: str | None
    affected_ecosystem: str | None
    cause_status: str | None


def validate_impact_path(
    raw: RawDiscoveredEvent | None,
    hypothesis: object,
    *,
    symbol: str | None = None,
    coin_id: str | None = None,
    score_components: Mapping[str, float] | None = None,
) -> ImpactPathValidation:
    """Classify source specificity, candidate role, and impact path strength."""
    context = _impact_path_context(raw)
    category = str(getattr(hypothesis, "impact_category", "") or "")
    external = clean_text(getattr(hypothesis, "external_asset", "") or "")
    components = dict(score_components or getattr(hypothesis, "score_components", {}) or {})
    market_confirmation, llm_resolver, event_window, liquidity, specificity = _impact_score_inputs(
        raw,
        components,
        context.text,
        category,
        symbol=symbol,
        coin_id=coin_id,
    )
    path_type, role, strength, reason = _classify_path(
        context.text,
        category,
        symbol=symbol,
        coin_id=coin_id,
        external=external,
        specificity=specificity,
        market_confirmation=market_confirmation,
        claims=context.claims,
        primary_subject=context.primary_subject,
        affected_ecosystem=context.affected_ecosystem,
        main_frame=context.main_frame,
        supporting_frames=context.supporting_frames,
    )
    role, role_confidence, role_evidence = _refine_candidate_role(
        role,
        text=context.text,
        symbol=symbol,
        coin_id=coin_id,
        category=category,
        primary_subject=context.primary_subject,
        affected_ecosystem=context.affected_ecosystem,
    )
    role_validation = _validate_refined_asset_role(
        components,
        context.text,
        role,
        llm_resolver=llm_resolver,
        impact_category=category,
        impact_path_type=path_type,
        market_confirmation=market_confirmation,
        role_evidence=role_evidence,
        symbol=symbol,
        coin_id=coin_id,
    )
    path_type, role, strength, reason, role_confidence, role_evidence = _apply_role_validation_result(
        path_type,
        role,
        strength,
        reason,
        role_confidence,
        role_evidence,
        role_validation,
    )
    required_evidence_met, market_confirmation_required, digest_eligible, why_digest_ineligible = _impact_path_digest_policy(
        path_type,
        strength,
        reason,
        role_validation=role_validation,
        market_confirmation=market_confirmation,
    )
    opportunity_components = _opportunity_score_components(
        strength,
        specificity=specificity,
        market_confirmation=market_confirmation,
        event_window=event_window,
        liquidity=liquidity,
        llm_resolver=llm_resolver,
        identity_confidence=role_validation.identity_confidence,
    )
    opportunity_score = calculate_opportunity_score_v2(opportunity_components)
    return ImpactPathValidation(
        impact_path_type=path_type,
        impact_path_strength=strength,
        candidate_role=role,
        evidence_specificity_score=round(specificity, 2),
        required_evidence_met=required_evidence_met,
        market_confirmation_required=market_confirmation_required,
        digest_eligible_by_impact_path=digest_eligible,
        why_digest_ineligible=why_digest_ineligible,
        impact_path_reason=reason or path_type,
        opportunity_score_v2=round(opportunity_score, 2),
        opportunity_score_components={key: round(value, 2) for key, value in opportunity_components.items()},
        primary_subject=context.primary_subject,
        affected_entity=context.primary_subject,
        affected_ecosystem=context.affected_ecosystem,
        role_confidence=role_confidence,
        role_evidence=role_evidence,
        cause_status=context.cause_status,
        claim_polarities=tuple(dict.fromkeys(claim.polarity for claim in context.claims)),
        asset_kind=role_validation.asset_kind,
        role_source=role_validation.role_source,
        identity_confidence=role_validation.identity_confidence,
        identity_evidence=role_validation.identity_evidence,
        collision_risk=role_validation.collision_risk,
        role_validation_failures=role_validation.failures,
        role_validation_warnings=role_validation.warnings,
        role_capabilities=role_validation.role_capabilities.as_dict(),
    )


def _impact_path_context(raw: RawDiscoveredEvent | None) -> _ImpactPathContext:
    text = clean_text(_raw_text(raw) if raw is not None else "")
    claims = event_claim_semantics.extract_event_claims((raw,)) if raw is not None else ()
    frames = event_catalyst_frames.build_catalyst_frames((raw,) if raw is not None else ())
    main_frame, supporting_frames = event_catalyst_frames.select_main_catalyst_frame(frames, raw)
    primary_subject = (
        main_frame.subject
        if main_frame is not None and main_frame.subject
        else event_incident_graph.infer_primary_subject(None, (raw,) if raw is not None else (), claims=claims)
    )
    affected_ecosystem = event_incident_graph.infer_affected_ecosystem(None, (raw,) if raw is not None else ())
    cause_status = (
        main_frame.cause_status
        if main_frame is not None
        and main_frame.frame_type != event_catalyst_frames.TYPE_PRIOR_EXPLOIT_CONTEXT
        else event_claim_semantics.current_cause_status(claims, "exploit")
    )
    if (
        main_frame is not None
        and main_frame.frame_type == event_catalyst_frames.TYPE_MARKET_DISLOCATION
        and any(frame.frame_role == event_catalyst_frames.ROLE_NEGATED for frame in supporting_frames)
    ):
        cause_status = event_claim_semantics.CauseStatus.RULED_OUT.value
    return _ImpactPathContext(
        text=text,
        claims=claims,
        main_frame=main_frame,
        supporting_frames=supporting_frames,
        primary_subject=primary_subject,
        affected_ecosystem=affected_ecosystem,
        cause_status=cause_status,
    )


def _impact_score_inputs(
    raw: RawDiscoveredEvent | None,
    components: Mapping[str, float],
    text: str,
    category: str,
    *,
    symbol: str | None,
    coin_id: str | None,
) -> tuple[float, float, float, float, float]:
    market_confirmation = _component_score(components, "market_confirmation")
    if raw is not None:
        market_confirmation = max(market_confirmation, _market_confirmation_score((raw,)))
    llm_resolver = max(
        _component_score(components, "validation_strength"),
        _component_score(components, "llm_candidate_confidence"),
        _component_score(components, "candidate_asset_strength"),
    )
    event_window = max(
        _component_score(components, "event_time_quality"),
        _component_score(components, "event_clarity"),
    )
    liquidity = max(
        _component_score(components, "liquidity"),
        _component_score(components, "tradability"),
        min(100.0, market_confirmation),
    )
    specificity = _evidence_specificity_score(raw, text, category, symbol=symbol, coin_id=coin_id)
    return market_confirmation, llm_resolver, event_window, liquidity, specificity


def _validate_refined_asset_role(
    components: Mapping[str, float],
    text: str,
    role: str,
    *,
    llm_resolver: float,
    impact_category: str,
    impact_path_type: str,
    market_confirmation: float,
    role_evidence: tuple[str, ...],
    symbol: str | None,
    coin_id: str | None,
) -> event_identity.AssetRoleValidation:
    role_source = str(
        components.get("role_source")
        or components.get("asset_role_source")
        or components.get("resolver_role_source")
        or event_identity.ROLE_SOURCE_RESOLVER_EXACT
    )
    knowledge = event_identity.asset_knowledge_for(
        symbol=symbol,
        coin_id=coin_id,
        name=components.get("asset_name") if isinstance(components, Mapping) else None,
        categories=components.get("asset_categories") or (),
        aliases=components.get("asset_aliases") or (),
    )
    identity_confidence = max(
        llm_resolver,
        _component_score(components, "identity_confidence"),
        _component_score(components, "resolver_identity_confidence"),
    )
    return event_identity.validate_asset_role(
        knowledge,
        role,
        impact_category=impact_category,
        impact_path_type=impact_path_type,
        role_source=role_source,
        source_text=text,
        market_confirmation=market_confirmation,
        identity_confidence=identity_confidence if identity_confidence > 0 else None,
        identity_evidence=(*role_evidence, symbol or "", coin_id or ""),
    )


def _apply_role_validation_result(
    path_type: str,
    role: str,
    strength: str,
    reason: str,
    role_confidence: float | None,
    role_evidence: tuple[str, ...],
    role_validation: event_identity.AssetRoleValidation,
) -> tuple[str, str, str, str, float | None, tuple[str, ...]]:
    if role_validation.accepted:
        return path_type, role, strength, reason, role_confidence, role_evidence
    role = role_validation.final_role
    role_confidence = min(float(role_confidence or 0.0), 0.45)
    role_evidence = tuple(dict.fromkeys((*role_evidence, *role_validation.failures)))
    if "broad_macro_asset_context_only" in role_validation.failures:
        return (
            ImpactPathType.MACRO_ATTENTION_ONLY.value,
            role,
            ImpactPathStrength.WEAK.value,
            "broad_macro_asset_context_only",
            role_confidence,
            role_evidence,
        )
    if "taxonomy_candidate_not_affected_asset" in role_validation.failures:
        return (
            ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
            role,
            ImpactPathStrength.NONE.value,
            "taxonomy_candidate_not_affected_asset",
            role_confidence,
            role_evidence,
        )
    if "stable_or_wrapped_asset_not_market_anomaly_candidate" in role_validation.failures:
        return (
            ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
            role,
            ImpactPathStrength.NONE.value,
            "stable_or_wrapped_asset_not_market_anomaly_candidate",
            role_confidence,
            role_evidence,
        )
    strength = ImpactPathStrength.WEAK.value if strength != ImpactPathStrength.NONE.value else strength
    return path_type, role, strength, role_validation.failures[0], role_confidence, role_evidence


def _impact_path_digest_policy(
    path_type: str,
    strength: str,
    reason: str,
    *,
    role_validation: event_identity.AssetRoleValidation,
    market_confirmation: float,
) -> tuple[bool, bool, bool, str | None]:
    required_evidence_met = strength in {ImpactPathStrength.STRONG.value, ImpactPathStrength.MEDIUM.value}
    market_confirmation_required = strength == ImpactPathStrength.MEDIUM.value
    digest_eligible = strength == ImpactPathStrength.STRONG.value or (
        strength == ImpactPathStrength.MEDIUM.value and market_confirmation >= 40.0
    )
    why_digest_ineligible = None
    if path_type == ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value:
        digest_eligible = False
        why_digest_ineligible = "generic_cooccurrence_only"
    elif not role_validation.accepted:
        digest_eligible = False
        why_digest_ineligible = role_validation.failures[0] if role_validation.failures else "asset_role_validation_failed"
    elif strength in {ImpactPathStrength.WEAK.value, ImpactPathStrength.NONE.value}:
        why_digest_ineligible = reason or "weak_impact_path"
    elif market_confirmation_required and market_confirmation < 40.0:
        digest_eligible = False
        why_digest_ineligible = "medium_impact_path_requires_market_confirmation"
    return required_evidence_met, market_confirmation_required, digest_eligible, why_digest_ineligible


def _opportunity_score_components(
    strength: str,
    *,
    specificity: float,
    market_confirmation: float,
    event_window: float,
    liquidity: float,
    llm_resolver: float,
    identity_confidence: float,
) -> dict[str, float]:
    return {
        "impact_path_strength": _strength_score(strength),
        "source_evidence_specificity": specificity,
        "market_confirmation": market_confirmation,
        "timing_event_window": event_window,
        "liquidity_tradability": liquidity,
        "llm_resolver_confidence": llm_resolver,
        "identity_confidence": identity_confidence,
    }


def calculate_opportunity_score_v2(components: Mapping[str, float]) -> float:
    """Weighted v2 score for validated impact hypotheses."""
    weights = {
        "impact_path_strength": 0.25,
        "source_evidence_specificity": 0.20,
        "market_confirmation": 0.20,
        "timing_event_window": 0.15,
        "liquidity_tradability": 0.10,
        "llm_resolver_confidence": 0.10,
    }
    score = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        score += max(0.0, min(100.0, float(components.get(key) or 0.0))) * weight
        weight_sum += weight
    return max(0.0, min(100.0, score / max(0.01, weight_sum)))


def _classify_path(
    text: str,
    category: str,
    *,
    symbol: str | None,
    coin_id: str | None,
    external: str,
    specificity: float,
    market_confirmation: float,
    claims: tuple[event_claim_semantics.EventClaim, ...] = (),
    primary_subject: str | None = None,
    affected_ecosystem: str | None = None,
    main_frame: event_catalyst_frames.EventCatalystFrame | None = None,
    supporting_frames: tuple[event_catalyst_frames.EventCatalystFrame, ...] = (),
) -> _ImpactClassification:
    asset_present = _asset_terms_present(text, symbol=symbol, coin_id=coin_id)
    asset_matches_main_subject = _subject_matches_asset(main_frame.subject if main_frame else None, symbol=symbol, coin_id=coin_id)
    negated_direct_security = any(
        frame.frame_role == event_catalyst_frames.ROLE_NEGATED
        and _subject_matches_asset(frame.subject, symbol=symbol, coin_id=coin_id)
        for frame in supporting_frames
    )
    classification = _classify_frame_or_guardrail_path(
        text,
        category,
        symbol=symbol,
        coin_id=coin_id,
        specificity=specificity,
        asset_present=asset_present,
        asset_matches_main_subject=asset_matches_main_subject,
        negated_direct_security=negated_direct_security,
        main_frame=main_frame,
    )
    if classification is not None:
        return classification
    classification = _classify_proxy_path(
        text,
        category,
        external=external,
        specificity=specificity,
        market_confirmation=market_confirmation,
        asset_present=asset_present,
    )
    if classification is not None:
        return classification
    classification = _classify_direct_category_path(
        text,
        category,
        specificity=specificity,
        asset_present=asset_present,
    )
    if classification is not None:
        return classification
    if category == "security_or_regulatory_shock":
        return _classify_security_or_regulatory_path(
            text,
            claims,
            symbol=symbol,
            coin_id=coin_id,
            market_confirmation=market_confirmation,
            asset_present=asset_present,
            asset_matches_main_subject=asset_matches_main_subject,
            negated_direct_security=negated_direct_security,
            primary_subject=primary_subject,
            affected_ecosystem=affected_ecosystem,
            main_frame=main_frame,
        )
    return _classify_infra_stable_or_fallback_path(text, category, asset_present=asset_present)


def _classify_frame_or_guardrail_path(
    text: str,
    category: str,
    *,
    symbol: str | None,
    coin_id: str | None,
    specificity: float,
    asset_present: bool,
    asset_matches_main_subject: bool,
    negated_direct_security: bool,
    main_frame: event_catalyst_frames.EventCatalystFrame | None,
) -> _ImpactClassification | None:
    if main_frame is not None and main_frame.frame_type in {
        event_catalyst_frames.TYPE_ACQUISITION_OR_STAKE,
        event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT,
        event_catalyst_frames.TYPE_VALUATION_EVENT,
    }:
        strength = ImpactPathStrength.STRONG.value if (asset_present or asset_matches_main_subject) and specificity >= 65 else ImpactPathStrength.MEDIUM.value
        return (
            ImpactPathType.STRATEGIC_INVESTMENT_OR_VALUATION.value,
            CandidateRole.DIRECT_SUBJECT.value if (asset_present or asset_matches_main_subject) else CandidateRole.GENERIC_MENTION.value,
            strength,
            "strategic_investment",
        )
    if negated_direct_security and category == "security_or_regulatory_shock":
        return (
            ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value,
            CandidateRole.DIRECT_SUBJECT.value if (asset_present or asset_matches_main_subject) else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.WEAK.value,
            "direct_exploit_negated",
        )
    if category == "market_anomaly_unknown" and (
        event_claim_semantics.text_has_unknown_cause(text)
        or _any_term_hit(text, ("crash", "crashes", "plunge", "plunges", "dumps", "selloff", "market anomaly"))
    ):
        return (
            ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value,
            CandidateRole.DIRECT_SUBJECT.value if asset_present else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.WEAK.value,
            "cause_unknown_market_dislocation",
        )
    if _generic_policy_without_specific_path(text):
        if _any_term_hit(text, ("cftc", "perp", "perps", "perpetual", "futures", "market structure")):
            path_type = ImpactPathType.MARKET_STRUCTURE_POLICY.value
        else:
            path_type = ImpactPathType.TECHNOLOGY_RISK.value if _any_term_hit(text, ("quantum", "cryptography")) else ImpactPathType.MACRO_ATTENTION_ONLY.value
        return (
            path_type,
            CandidateRole.MACRO_AFFECTED_ASSET.value if asset_present else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.WEAK.value,
            "generic_policy_only",
        )
    if not asset_present and symbol:
        return (
            ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
            CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.NONE.value,
            "candidate_not_named_in_strong_evidence",
        )
    return None


def _classify_proxy_path(
    text: str,
    category: str,
    *,
    external: str,
    specificity: float,
    market_confirmation: float,
    asset_present: bool,
) -> _ImpactClassification | None:
    if category in {"rwa_preipo_proxy", "ai_ipo_proxy", "tokenized_stock_venue"}:
        if _any_term_hit(text, ("offers", "lets users trade", "trade", "listed", "market", "venue")) and _any_term_hit(
            text,
            ("exposure", "tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo", "prediction market"),
        ):
            return (
                ImpactPathType.VENUE_VALUE_CAPTURE.value,
                CandidateRole.PROXY_VENUE.value,
                ImpactPathStrength.STRONG.value,
                "venue_value_capture",
            )
        if external and _any_term_hit(text, ("exposure", "pre ipo", "pre-ipo", "tokenized")):
            return (
                ImpactPathType.PROXY_ATTENTION.value,
                CandidateRole.PROXY_INSTRUMENT.value,
                ImpactPathStrength.MEDIUM.value,
                "proxy_attention",
            )

    if category == "sports_fan_proxy":
        if _any_term_hit(text, ("fan token", "world cup", "match", "fixture", "kickoff", "team demand", "sports event")):
            strength = ImpactPathStrength.STRONG.value if specificity >= 70 or market_confirmation >= 40 else ImpactPathStrength.MEDIUM.value
            return (
                ImpactPathType.FAN_TOKEN_ATTENTION.value,
                CandidateRole.PROXY_INSTRUMENT.value,
                strength,
                "fan_token_event",
            )

    if category == "political_meme_proxy" and asset_present:
        if _any_term_hit(text, ("meme exposure", "political meme proxy", "election event", "campaign event", "inauguration")):
            strength = ImpactPathStrength.STRONG.value if specificity >= 70 or market_confirmation >= 40 else ImpactPathStrength.MEDIUM.value
            return (
                ImpactPathType.PROXY_ATTENTION.value,
                CandidateRole.PROXY_INSTRUMENT.value,
                strength,
                "political_meme_event",
            )
    return None


def _classify_direct_category_path(
    text: str,
    category: str,
    *,
    specificity: float,
    asset_present: bool,
) -> _ImpactClassification | None:
    if category == "strategic_investment_or_valuation" and _any_term_hit(
        text,
        ("stake", "strategic investment", "valuation", "acquisition", "acquire", "buy"),
    ):
        return (
            ImpactPathType.STRATEGIC_INVESTMENT_OR_VALUATION.value,
            CandidateRole.DIRECT_SUBJECT.value if asset_present else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.STRONG.value if asset_present and specificity >= 65 else ImpactPathStrength.MEDIUM.value,
            "strategic_investment",
        )

    if category == "unlock_supply_pressure" and _any_term_hit(text, ("unlock", "vesting", "airdrop", "tge", "emission", "claim")):
        return (
            ImpactPathType.UNLOCK_SUPPLY_EVENT.value,
            CandidateRole.DIRECT_SUBJECT.value,
            ImpactPathStrength.STRONG.value,
            "unlock_supply_event",
        )

    if category in {"listing_liquidity_event", "perp_venue_attention"} and _any_term_hit(
        text,
        ("listing", "listed on", "binance", "coinbase", "nasdaq", "public listing", "merger", "trading pair", "perp", "futures"),
    ):
        return (
            ImpactPathType.LISTING_LIQUIDITY_EVENT.value,
            CandidateRole.DIRECT_SUBJECT.value,
            ImpactPathStrength.STRONG.value,
            "listing_liquidity_event",
        )
    return None


def _classify_security_or_regulatory_path(
    text: str,
    claims: tuple[event_claim_semantics.EventClaim, ...],
    *,
    symbol: str | None,
    coin_id: str | None,
    market_confirmation: float,
    asset_present: bool,
    asset_matches_main_subject: bool,
    negated_direct_security: bool,
    primary_subject: str | None,
    affected_ecosystem: str | None,
    main_frame: event_catalyst_frames.EventCatalystFrame | None,
) -> _ImpactClassification:
    if main_frame is not None and main_frame.frame_type not in {
        event_catalyst_frames.TYPE_EXPLOIT_SECURITY,
        event_catalyst_frames.TYPE_PRIOR_EXPLOIT_CONTEXT,
        event_catalyst_frames.TYPE_DENIED_EXPLOIT,
        event_catalyst_frames.TYPE_MARKET_DISLOCATION,
        event_catalyst_frames.TYPE_POLICY_CONTEXT,
    }:
        return (
            ImpactPathType.STRATEGIC_INVESTMENT_OR_VALUATION.value
            if main_frame.event_archetype == event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT
            else ImpactPathType.DIRECT_TOKEN_EVENT.value,
            CandidateRole.DIRECT_SUBJECT.value if (asset_present or asset_matches_main_subject) else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.MEDIUM.value,
            str(main_frame.frame_type or "main_catalyst_not_security"),
        )
    exploit_confirmed = event_claim_semantics.has_confirmed_claim(claims, "exploit")
    exploit_ruled_out = event_claim_semantics.has_ruled_out_claim(claims, "exploit")
    exploit_suspected = any(
        claim.claim_type == "exploit"
        and claim.cause_status == event_claim_semantics.CauseStatus.SUSPECTED.value
        for claim in claims
    )
    if (exploit_ruled_out and not exploit_confirmed) or (
        event_claim_semantics.text_has_unknown_cause(text)
        and not exploit_confirmed
    ):
        return (
            ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value,
            CandidateRole.DIRECT_SUBJECT.value if asset_present else CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.WEAK.value,
            "cause_unknown_market_dislocation",
        )
    if exploit_suspected and not exploit_confirmed:
        role = _security_role(text, symbol=symbol, coin_id=coin_id, primary_subject=primary_subject, affected_ecosystem=affected_ecosystem)
        return (
            ImpactPathType.EXPLOIT_SECURITY_EVENT.value,
            role,
            ImpactPathStrength.WEAK.value,
            "alleged_exploit_unconfirmed",
        )
    if _any_term_hit(text, ("exploit", "hack", "security incident", "attack", "breach", "resumes trading", "halted trading")):
        if negated_direct_security:
            return (
                ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value,
                CandidateRole.DIRECT_SUBJECT.value if (asset_present or asset_matches_main_subject) else CandidateRole.GENERIC_MENTION.value,
                ImpactPathStrength.WEAK.value,
                "direct_exploit_negated",
            )
        role = _security_role(text, symbol=symbol, coin_id=coin_id, primary_subject=primary_subject, affected_ecosystem=affected_ecosystem)
        strength = ImpactPathStrength.STRONG.value if role == CandidateRole.DIRECT_SUBJECT.value else (
            ImpactPathStrength.MEDIUM.value if market_confirmation >= 40 else ImpactPathStrength.WEAK.value
        )
        return (
            ImpactPathType.EXPLOIT_SECURITY_EVENT.value,
            role,
            strength,
            "exploit_security_event" if role == CandidateRole.DIRECT_SUBJECT.value else "ecosystem_security_event",
        )
    if _any_term_hit(text, ("quantum", "cryptography", "technology risk")):
        return (
            ImpactPathType.TECHNOLOGY_RISK.value,
            CandidateRole.MACRO_AFFECTED_ASSET.value,
            ImpactPathStrength.WEAK.value,
            "generic_policy_only",
        )
    if _any_term_hit(text, ("lawsuit", "sec", "cftc", "regulatory", "regulation", "probe", "charges", "investigation")):
        if _any_term_hit(text, ("against", "charges", "lawsuit", "probe", "investigation")) and asset_present:
            return (
                ImpactPathType.REGULATORY_POLICY_EXPOSURE.value,
                CandidateRole.DIRECT_SUBJECT.value,
                ImpactPathStrength.MEDIUM.value,
                "direct_token_event",
            )
        return (
            ImpactPathType.MARKET_STRUCTURE_POLICY.value,
            CandidateRole.MACRO_AFFECTED_ASSET.value,
            ImpactPathStrength.WEAK.value,
            "generic_policy_only",
        )
    return (
        ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
        CandidateRole.GENERIC_MENTION.value,
        ImpactPathStrength.WEAK.value if asset_present else ImpactPathStrength.NONE.value,
        "weak_cooccurrence_only" if asset_present else "no_value_capture_explained",
    )


def _classify_infra_stable_or_fallback_path(
    text: str,
    category: str,
    *,
    asset_present: bool,
) -> _ImpactClassification:
    if category == "prediction_market_infra":
        if _any_term_hit(text, ("oracle", "settlement", "resolution", "infrastructure", "data provider", "powers", "secures")):
            return (
                ImpactPathType.DIRECT_TOKEN_EVENT.value,
                CandidateRole.INFRASTRUCTURE_PROVIDER.value,
                ImpactPathStrength.MEDIUM.value,
                "direct_token_event",
            )
        return (
            ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
            CandidateRole.GENERIC_MENTION.value,
            ImpactPathStrength.WEAK.value,
            "generic_cooccurrence_only",
        )

    if category == "stablecoin_regulatory":
        if _any_term_hit(text, ("reserve", "issuer", "stablecoin", "treasury", "bill")):
            return (
                ImpactPathType.REGULATORY_POLICY_EXPOSURE.value,
                CandidateRole.ECOSYSTEM_BENEFICIARY.value if asset_present else CandidateRole.MACRO_AFFECTED_ASSET.value,
                ImpactPathStrength.MEDIUM.value if asset_present else ImpactPathStrength.WEAK.value,
                "direct_token_event" if asset_present else "generic_policy_only",
            )

    if category in _PROXY_CATEGORIES and asset_present:
        return (
            ImpactPathType.PROXY_ATTENTION.value,
            CandidateRole.PROXY_INSTRUMENT.value,
            ImpactPathStrength.WEAK.value,
            "weak_cooccurrence_only",
        )
    if category in _DIRECT_EVENT_CATEGORIES and asset_present:
        return (
            ImpactPathType.DIRECT_TOKEN_EVENT.value,
            CandidateRole.DIRECT_SUBJECT.value,
            ImpactPathStrength.WEAK.value,
            "no_value_capture_explained",
        )
    if category in _INFRA_CATEGORIES and asset_present:
        return (
            ImpactPathType.DIRECT_TOKEN_EVENT.value,
            CandidateRole.INFRASTRUCTURE_PROVIDER.value,
            ImpactPathStrength.WEAK.value,
            "no_value_capture_explained",
        )
    return (
        ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
        CandidateRole.GENERIC_MENTION.value,
        ImpactPathStrength.WEAK.value if asset_present else ImpactPathStrength.NONE.value,
        "weak_cooccurrence_only" if asset_present else "no_value_capture_explained",
    )


def _subject_matches_asset(subject: str | None, *, symbol: str | None, coin_id: str | None) -> bool:
    cleaned = clean_text(subject or "")
    if not cleaned:
        return False
    candidates = {
        clean_text(symbol or ""),
        clean_text(coin_id or ""),
        clean_text(str(coin_id or "").replace("-", " ")),
    }
    return cleaned in candidates or any(value and value in cleaned for value in candidates)


def _refine_candidate_role(
    role: str,
    *,
    text: str,
    symbol: str | None,
    coin_id: str | None,
    category: str,
    primary_subject: str | None,
    affected_ecosystem: str | None,
) -> tuple[str, float, tuple[str, ...]]:
    if role in {
        CandidateRole.PROXY_INSTRUMENT.value,
        CandidateRole.PROXY_VENUE.value,
        CandidateRole.INFRASTRUCTURE_PROVIDER.value,
        CandidateRole.MACRO_AFFECTED_ASSET.value,
    }:
        return role, 0.82, ("deterministic_playbook_role_preserved",)
    refined, confidence, evidence = event_incident_graph.classify_candidate_role(
        text=text,
        symbol=symbol,
        coin_id=coin_id,
        primary_subject=primary_subject,
        affected_ecosystem=affected_ecosystem,
        impact_category=category,
    )
    if role == CandidateRole.DIRECT_SUBJECT.value and refined in {
        CandidateRole.MACRO_AFFECTED_ASSET.value,
        CandidateRole.GENERIC_MENTION.value,
    }:
        return role, 0.78, ("asset_named_as_security_subject",)
    if refined != CandidateRole.GENERIC_MENTION.value:
        return refined, confidence, evidence
    return role, 0.50 if role != CandidateRole.GENERIC_MENTION.value else confidence, evidence


def _security_role(
    text: str,
    *,
    symbol: str | None,
    coin_id: str | None,
    primary_subject: str | None,
    affected_ecosystem: str | None,
) -> str:
    role, _confidence, _evidence = event_incident_graph.classify_candidate_role(
        text=text,
        symbol=symbol,
        coin_id=coin_id,
        primary_subject=primary_subject,
        affected_ecosystem=affected_ecosystem,
        impact_category="security_or_regulatory_shock",
    )
    if role == CandidateRole.ECOSYSTEM_AFFECTED_ASSET.value:
        return role
    return CandidateRole.DIRECT_SUBJECT.value if _asset_terms_present(text, symbol=symbol, coin_id=coin_id) else CandidateRole.GENERIC_MENTION.value


def _evidence_specificity_score(
    raw: RawDiscoveredEvent | None,
    text: str,
    category: str,
    *,
    symbol: str | None,
    coin_id: str | None,
) -> float:
    score = 0.0
    if raw is not None:
        try:
            score = max(score, float(raw.source_confidence or 0.0) * 100)
        except (TypeError, ValueError):
            pass
        provider = clean_text(raw.provider)
        origin = clean_text(str((raw.raw_json or {}).get("source_origin") if isinstance(raw.raw_json, Mapping) else ""))
        if any(term in provider or term in origin for term in ("project", "official", "binance", "bybit", "coinmarketcal", "tokenomist")):
            score = max(score, 80.0)
        if "cryptopanic" in provider:
            score = max(score, 70.0)
        if "gdelt" in provider:
            score = max(score, 55.0)
        if "polymarket" in provider:
            score = max(score, 45.0)
    if _asset_terms_present(text, symbol=symbol, coin_id=coin_id):
        score += 12.0
    if _any_term_hit(text, ("offers", "lets users trade", "listed", "unlocked", "exploit", "hack", "resumes trading", "fan token", "tokenized stock", "synthetic exposure", "trading pair", "stake", "strategic investment", "valuation", "acquisition")):
        score += 18.0
    if category in _DIRECT_EVENT_CATEGORIES and _any_term_hit(text, ("listing", "unlock", "exploit", "hack", "airdrop", "tge")):
        score += 12.0
    if _generic_policy_without_specific_path(text):
        score = min(score, 45.0)
    if "polymarket" in text and not _asset_terms_present(text, symbol=symbol, coin_id=coin_id):
        score = min(score, 40.0)
    return max(0.0, min(100.0, score))


def _asset_terms_present(text: str, *, symbol: str | None, coin_id: str | None) -> bool:
    terms = [symbol, coin_id, str(coin_id or "").replace("-", " ")]
    if symbol:
        terms.extend((f"${symbol}", f"{symbol}usdt"))
    return any(_term_hit(text, str(term)) for term in terms if str(term or "").strip())


def _generic_policy_without_specific_path(text: str) -> bool:
    policy = _any_term_hit(text, ("policy", "cftc", "regulatory", "regulation", "chair", "order", "government", "quantum", "cryptography"))
    broad = _any_term_hit(text, ("generally", "broad", "industry", "market", "crypto headlines", "technology risk", "quantum computing", "macro"))
    direct = _any_term_hit(text, (
        "exploit",
        "hack",
        "listing",
        "listed on",
        "unlock",
        "airdrop",
        "tge",
        "fan token",
        "tokenized stock",
        "synthetic exposure",
        "offers exposure",
        "lets users trade",
    ))
    return policy and broad and not direct


def _strength_score(strength: str) -> float:
    return {
        ImpactPathStrength.STRONG.value: 95.0,
        ImpactPathStrength.MEDIUM.value: 68.0,
        ImpactPathStrength.WEAK.value: 35.0,
        ImpactPathStrength.NONE.value: 0.0,
    }.get(str(strength or ""), 0.0)


def _component_score(components: Mapping[str, float], key: str) -> float:
    try:
        return max(0.0, min(100.0, float(components.get(key) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _market_confirmation_score(raws: Iterable[RawDiscoveredEvent]) -> float:
    best = 0.0
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
        market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
        for key, value in (
            ("anomaly_score", anomaly.get("score")),
            ("market_move_volume", market.get("market_move_volume")),
            ("volume_zscore_24h", market.get("volume_zscore_24h")),
            ("return_24h", market.get("return_24h")),
        ):
            try:
                number = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if key != "anomaly_score" and abs(number) <= 3.0:
                number *= 25.0
            best = max(best, abs(number))
    return max(0.0, min(100.0, best))


def _raw_text(raw: RawDiscoveredEvent | None) -> str:
    if raw is None:
        return ""
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    parts: list[Any] = [
        raw.title,
        raw.body,
        payload.get("source_origin"),
        event_payload.get("event_name"),
        event_payload.get("event_type"),
        event_payload.get("external_asset"),
        event_payload.get("description"),
    ]
    for key in ("external_catalysts", "crypto_asset_mentions"):
        values = extraction.get(key) if isinstance(extraction.get(key), list) else []
        for row in values:
            if not isinstance(row, Mapping):
                continue
            parts.extend(row.get(field) for field in ("name", "symbol", "coin_id", "mention_type", "evidence_quote"))
            quotes = row.get("evidence_quotes") if isinstance(row.get("evidence_quotes"), list) else []
            for quote in quotes:
                if isinstance(quote, Mapping):
                    parts.append(quote.get("text"))
                else:
                    parts.append(quote)
    return " ".join(str(part or "") for part in parts)


def _any_term_hit(text: str, terms: Iterable[str]) -> bool:
    return any(_term_hit(text, term) for term in terms)


def _term_hit(text: str, term: str) -> bool:
    source = clean_text(text)
    needle = clean_text(term)
    if not source or not needle:
        return False
    escaped = re.escape(needle).replace("\\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, source) is not None
