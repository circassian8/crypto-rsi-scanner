"""Impact-hypothesis validation helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
from ..llm.extractor import EventLLMExtractionReportRow
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from ..resolver import clean_text
from .. import incidents as event_incident_store
from .. import market_confirmation as event_market_confirmation
from .. import opportunity_verdict as event_opportunity_verdict
from .models import (
    EventImpactHypothesis,
    HypothesisScope,
    HypothesisStatus,
    ImpactCategory,
    ImpactPathReason,
    ValidationStage,
)



_VALIDATION_STAGE_RANK = {
    ValidationStage.SECTOR_HYPOTHESIS.value: 0,
    ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value: 1,
    ValidationStage.VALIDATION_SEARCH_PENDING.value: 2,
    ValidationStage.SOURCE_MENTIONS_CANDIDATE.value: 3,
    ValidationStage.IDENTITY_VALIDATED.value: 4,
    ValidationStage.CATALYST_LINK_VALIDATED.value: 5,
    ValidationStage.IMPACT_PATH_VALIDATED.value: 6,
    ValidationStage.MARKET_CONFIRMED.value: 7,
    ValidationStage.PROMOTED_TO_RADAR.value: 8,
    ValidationStage.REJECTED.value: -1,
}


def _validation_reason(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> tuple[str, str | None, str | None, str | None]:
    detail = _validation_detail(raw, hypothesis)
    return (
        str(detail.get("status") or "none"),
        str(detail.get("reason") or "") or None,
        str(detail.get("symbol") or "") or None,
        str(detail.get("coin_id") or "") or None,
    )


def _validation_detail(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> dict[str, Any]:
    text = clean_text(_raw_text(raw))
    if not text:
        return {"status": "none"}
    category_rejection = _category_validation_rejection(text, hypothesis)
    if category_rejection:
        return {
            "status": "rejected",
            "validation_stage": ValidationStage.REJECTED.value,
            "reason": category_rejection,
        }
    mentions_candidate = _text_mentions_candidate(text, hypothesis)
    mentions_catalyst = _text_mentions_catalyst(text, hypothesis)
    symbol_match = _identity_match_from_symbols(raw, hypothesis)
    symbol, coin_id = _matched_symbol_and_coin_id(raw, hypothesis) if symbol_match.matched else (None, None)
    if mentions_candidate and not symbol_match.matched and not mentions_catalyst:
        return {
            "status": "accepted",
            "validation_stage": ValidationStage.SOURCE_MENTIONS_CANDIDATE.value,
            "reason": "source_mentions_candidate_without_catalyst_link",
            "symbol": None,
            "coin_id": None,
        }
    if mentions_candidate and symbol_match.matched and not mentions_catalyst:
        return {
            "status": "accepted",
            "validation_stage": ValidationStage.IDENTITY_VALIDATED.value,
            "reason": f"{symbol_match.reason or 'identity_match'} validates candidate identity without catalyst link",
            "symbol": symbol,
            "coin_id": coin_id,
        }
    if mentions_catalyst and not mentions_candidate and not symbol_match.matched:
        return {
            "status": "rejected",
            "validation_stage": ValidationStage.REJECTED.value,
            "reason": "source_mentions_catalyst_without_candidate_asset",
        }
    if not mentions_catalyst:
        if mentions_candidate:
            return {
                "status": "rejected",
                "validation_stage": ValidationStage.REJECTED.value,
                "reason": "source mentions candidate context without the catalyst",
            }
        return {"status": "none"}
    if not symbol_match.matched:
        if mentions_candidate:
            return {
                "status": "rejected",
                "validation_stage": ValidationStage.REJECTED.value,
                "reason": symbol_match.reason or "candidate identity rejected",
            }
        return {"status": "none"}
    return {
        "status": "accepted",
        "validation_stage": ValidationStage.CATALYST_LINK_VALIDATED.value,
        "reason": f"{symbol_match.reason or 'identity_match'} links candidate to {hypothesis.external_asset or hypothesis.impact_category}",
        "symbol": symbol,
        "coin_id": coin_id,
    }


def _max_validation_stage(current: str, candidate: str) -> str:
    if candidate == ValidationStage.REJECTED.value:
        return current or candidate
    if _VALIDATION_STAGE_RANK.get(candidate, 0) > _VALIDATION_STAGE_RANK.get(current, 0):
        return candidate
    return current


def _sample_rejection_reason(reasons: Iterable[str]) -> str | None:
    for reason in reasons:
        if "rejected" in reason or "missing" in reason or "below_threshold" in reason or "penalty" in reason:
            return reason
    return None


def _first_reason_with(reasons: Iterable[str], needle: str) -> str | None:
    lowered = str(needle or "").casefold()
    for reason in reasons:
        if lowered and lowered in str(reason).casefold():
            return reason
    return None


def _impact_path_reason(
    raw: RawDiscoveredEvent,
    hypothesis: EventImpactHypothesis,
    *,
    symbol: str | None,
    coin_id: str | None,
) -> str | None:
    """Classify whether source evidence explains why the catalyst affects the asset."""
    text = clean_text(_raw_text(raw))
    if not text:
        return None
    category = str(hypothesis.impact_category or "")
    if _generic_policy_without_asset_path(text):
        return ImpactPathReason.GENERIC_POLICY_ONLY.value
    if not _asset_path_terms_present(text, symbol=symbol, coin_id=coin_id):
        return ImpactPathReason.WEAK_COOCCURRENCE_ONLY.value
    if category in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
    }:
        if _any_term_hit(text, ("exposure", "tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo", "trade")):
            return ImpactPathReason.VENUE_VALUE_CAPTURE.value
    if category == ImpactCategory.SPORTS_FAN_PROXY.value:
        if _any_term_hit(text, ("fan token", "world cup", "fixture", "kickoff", "team demand", "sports event")):
            return ImpactPathReason.FAN_TOKEN_EVENT.value
    if category == ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value:
        if _any_term_hit(text, ("unlock", "vesting", "airdrop", "tge", "emission", "claim")):
            return ImpactPathReason.UNLOCK_SUPPLY_EVENT.value
    if category in {ImpactCategory.LISTING_LIQUIDITY_EVENT.value, ImpactCategory.PERP_VENUE_ATTENTION.value}:
        if _any_term_hit(text, ("listing", "listed on", "nasdaq", "public listing", "merger", "trading pair", "perp", "futures")):
            return ImpactPathReason.LISTING_LIQUIDITY_EVENT.value
    if category == ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION.value:
        if _any_term_hit(text, ("stake", "strategic investment", "valuation", "acquisition", "acquire", "buy")):
            return ImpactPathReason.STRATEGIC_INVESTMENT.value
    if category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value:
        if _any_term_hit(text, ("exploit", "hack", "security incident", "attack", "breach", "resumes trading", "halted trading")):
            return ImpactPathReason.EXPLOIT_SECURITY_EVENT.value
        if _any_term_hit(text, ("lawsuit", "sec", "cftc", "regulatory", "regulation", "probe", "charges", "investigation")):
            return ImpactPathReason.DIRECT_TOKEN_EVENT.value
        return ImpactPathReason.GENERIC_POLICY_ONLY.value
    if category in {
        ImpactCategory.STABLECOIN_REGULATORY.value,
        ImpactCategory.PREDICTION_MARKET_INFRA.value,
        ImpactCategory.POLITICAL_MEME_PROXY.value,
    }:
        if _any_term_hit(text, ("reserve", "settlement", "oracle", "infrastructure", "prediction market", "meme token", "candidate token")):
            return ImpactPathReason.DIRECT_TOKEN_EVENT.value
    return ImpactPathReason.NO_VALUE_CAPTURE_EXPLAINED.value


def _asset_path_terms_present(text: str, *, symbol: str | None, coin_id: str | None) -> bool:
    terms = [symbol, coin_id, str(coin_id or "").replace("-", " ")]
    return any(_term_hit(text, term) for term in terms if str(term or "").strip())


def _generic_policy_without_asset_path(text: str) -> bool:
    policy = _any_term_hit(text, ("policy", "cftc", "regulatory", "regulation", "chair", "order", "government", "quantum"))
    broad = _any_term_hit(text, ("generally", "broad", "industry", "market", "crypto headlines", "technology risk", "quantum computing"))
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
    ))
    return policy and broad and not direct


def _impact_path_reason_is_strong(reason: str | None) -> bool:
    return str(reason or "") in {
        ImpactPathReason.DIRECT_TOKEN_EVENT.value,
        ImpactPathReason.VENUE_VALUE_CAPTURE.value,
        ImpactPathReason.FAN_TOKEN_EVENT.value,
        ImpactPathReason.UNLOCK_SUPPLY_EVENT.value,
        ImpactPathReason.LISTING_LIQUIDITY_EVENT.value,
        ImpactPathReason.EXPLOIT_SECURITY_EVENT.value,
    }


def _prefer_impact_path_reason(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    if _impact_path_reason_is_strong(candidate) and not _impact_path_reason_is_strong(current):
        return candidate
    return current


def _prefer_impact_validation(
    current: event_impact_path_validator.ImpactPathValidation | None,
    candidate: event_impact_path_validator.ImpactPathValidation | None,
) -> event_impact_path_validator.ImpactPathValidation | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    strength_rank = {
        "none": 0,
        "weak": 1,
        "medium": 2,
        "strong": 3,
    }
    candidate_key = (
        strength_rank.get(candidate.impact_path_strength, 0),
        float(candidate.opportunity_score_v2 or 0.0),
        float(candidate.evidence_specificity_score or 0.0),
    )
    current_key = (
        strength_rank.get(current.impact_path_strength, 0),
        float(current.opportunity_score_v2 or 0.0),
        float(current.evidence_specificity_score or 0.0),
    )
    return candidate if candidate_key > current_key else current


def _impact_validation_score_components(
    validation: event_impact_path_validator.ImpactPathValidation,
) -> dict[str, float]:
    components = dict(validation.opportunity_score_components or {})
    components["impact_path_strength"] = max(
        float(components.get("impact_path_strength") or 0.0),
        {
            "strong": 95.0,
            "medium": 68.0,
            "weak": 35.0,
            "none": 0.0,
        }.get(validation.impact_path_strength, 0.0),
    )
    components["evidence_specificity"] = float(validation.evidence_specificity_score or 0.0)
    components["opportunity_score_v2"] = float(validation.opportunity_score_v2 or 0.0)
    return components


def _impact_validation_metadata_components(
    validation: event_impact_path_validator.ImpactPathValidation,
) -> dict[str, Any]:
    return {
        "asset_kind": validation.asset_kind,
        "role_source": validation.role_source,
        "asset_role_source": validation.role_source,
        "identity_confidence": validation.identity_confidence,
        "identity_evidence": list(validation.identity_evidence or ()),
        "collision_risk": validation.collision_risk,
        "role_validation_failures": list(validation.role_validation_failures or ()),
        "role_validation_warnings": list(validation.role_validation_warnings or ()),
        "role_capabilities": dict(validation.role_capabilities or {}),
    }


def _refresh_impact_validation_score(
    validation: event_impact_path_validator.ImpactPathValidation,
    components: Mapping[str, float],
) -> event_impact_path_validator.ImpactPathValidation:
    opportunity = dict(validation.opportunity_score_components or {})
    opportunity["market_confirmation"] = max(
        float(opportunity.get("market_confirmation") or 0.0),
        _component_float(components, "market_confirmation"),
    )
    opportunity["timing_event_window"] = max(
        float(opportunity.get("timing_event_window") or 0.0),
        _component_float(components, "event_time_quality"),
        _component_float(components, "event_clarity"),
    )
    opportunity["liquidity_tradability"] = max(
        float(opportunity.get("liquidity_tradability") or 0.0),
        _component_float(components, "liquidity"),
        _component_float(components, "tradability"),
        _component_float(components, "market_confirmation"),
    )
    opportunity["llm_resolver_confidence"] = max(
        float(opportunity.get("llm_resolver_confidence") or 0.0),
        _component_float(components, "validation_strength"),
        _component_float(components, "llm_candidate_confidence"),
        _component_float(components, "candidate_asset_strength"),
    )
    score = event_impact_path_validator.calculate_opportunity_score_v2(opportunity)
    return replace(
        validation,
        opportunity_score_v2=round(score, 2),
        opportunity_score_components={key: round(value, 2) for key, value in opportunity.items()},
    )


def _component_float(components: Mapping[str, float], key: str) -> float:
    value = components.get(key)
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(100.0, number))


def _impact_validation_replace_kwargs(
    validation: event_impact_path_validator.ImpactPathValidation | None,
) -> dict[str, Any]:
    if validation is None:
        return {}
    return {
        "impact_path_type": validation.impact_path_type,
        "impact_path_strength": validation.impact_path_strength,
        "candidate_role": validation.candidate_role,
        "evidence_specificity_score": validation.evidence_specificity_score,
        "required_evidence_met": validation.required_evidence_met,
        "market_confirmation_required": validation.market_confirmation_required,
        "digest_eligible_by_impact_path": validation.digest_eligible_by_impact_path,
        "why_digest_ineligible": validation.why_digest_ineligible,
        "opportunity_score_v2": validation.opportunity_score_v2,
        "opportunity_score_components": dict(validation.opportunity_score_components or {}),
        "primary_subject": validation.primary_subject,
        "affected_entity": validation.affected_entity,
        "affected_ecosystem": validation.affected_ecosystem,
        "role_confidence": validation.role_confidence,
        "role_evidence": validation.role_evidence,
        "cause_status": validation.cause_status,
        "claim_polarities": validation.claim_polarities,
        "asset_kind": validation.asset_kind,
        "role_source": validation.role_source,
        "identity_confidence": validation.identity_confidence,
        "identity_evidence": validation.identity_evidence,
        "collision_risk": validation.collision_risk,
        "role_validation_failures": validation.role_validation_failures,
        "role_validation_warnings": validation.role_validation_warnings,
        "role_capabilities": dict(validation.role_capabilities or {}),
    }


def _quality_verdict_replace_kwargs(
    validation: event_impact_path_validator.ImpactPathValidation,
    *,
    impact_context: tuple[RawDiscoveredEvent, str | None, str | None] | None,
    hypothesis: EventImpactHypothesis,
    components: Mapping[str, float],
) -> dict[str, Any]:
    raw, symbol, coin_id = impact_context if impact_context is not None else (None, None, None)
    market_context = resolve_hypothesis_market_context(
        hypothesis,
        discovery_result=None,
        current_cycle_market_rows=(),
        active_watchlist_rows=(),
        targeted_provider=None,
        raw_event=raw,
        validated_coin_id=coin_id,
    )
    payload = raw.raw_json if raw is not None and isinstance(raw.raw_json, Mapping) else {}
    market_result = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=market_context.get("market_snapshot") or _payload_mapping(payload, "market", "market_snapshot"),
            market_anomaly_row=_payload_mapping(payload, "anomaly", "market_anomaly"),
            derivatives_snapshot=_payload_mapping(payload, "derivatives", "derivatives_snapshot"),
            dex_liquidity_snapshot=_payload_mapping(payload, "dex_liquidity", "dex_liquidity_snapshot", "dex"),
            protocol_metrics_snapshot=_payload_mapping(
                payload,
                "protocol_metrics",
                "protocol_metrics_snapshot",
                "defillama",
                "protocol",
            ),
            supply_snapshot=_payload_mapping(payload, "supply", "supply_snapshot"),
            btc_context=_payload_mapping(payload, "btc_context"),
            sector_benchmark=_payload_mapping(payload, "sector_benchmark"),
            playbook_type=hypothesis.playbook_hint or hypothesis.impact_category,
            impact_category=hypothesis.impact_category,
            market_context_observed_at=market_context.get("timestamp"),
            market_context_source=market_context.get("source"),
        )
    )
    evidence_result = event_evidence_quality.evaluate_evidence_quality(
        raw,
        hypothesis=hypothesis,
        symbol=symbol,
        coin_id=coin_id,
    )
    merged_components = dict(components)
    merged_components.update({
        "market_confirmation": max(
            _component_float(merged_components, "market_confirmation"),
            float(market_result.market_confirmation_score or 0.0),
        ),
        "source_quality": max(
            _component_float(merged_components, "source_quality"),
            float(evidence_result.evidence_quality_score or 0.0),
        ),
        "source_evidence_specificity": max(
            _component_float(merged_components, "source_evidence_specificity"),
            float(validation.evidence_specificity_score or 0.0),
        ),
        "timing_event_window": max(
            _component_float(merged_components, "timing_event_window"),
            _component_float(merged_components, "event_time_quality"),
            _component_float(merged_components, "event_clarity"),
        ),
        "liquidity_tradability": max(
            _component_float(merged_components, "liquidity_tradability"),
            _component_float(merged_components, "liquidity"),
            _component_float(merged_components, "tradability"),
            float(market_result.market_confirmation_score or 0.0),
        ),
        "llm_resolver_confidence": max(
            _component_float(merged_components, "llm_resolver_confidence"),
            _component_float(merged_components, "validation_strength"),
            _component_float(merged_components, "candidate_asset_strength"),
            _component_float(merged_components, "llm_candidate_confidence"),
        ),
    })
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=validation,
        market_confirmation=market_result,
        evidence_quality=evidence_result,
        hypothesis=hypothesis,
        score_components=merged_components,
    )
    upgrade_path = event_opportunity_verdict.explain_upgrade_path(
        verdict=verdict,
        impact_path=validation,
        market_confirmation=market_result,
        evidence_quality=evidence_result,
        components=merged_components,
    )
    return {
        "evidence_quality_score": evidence_result.evidence_quality_score,
        "source_class": evidence_result.source_class,
        "evidence_specificity": evidence_result.evidence_specificity,
        "evidence_quality_reasons": evidence_result.reason_codes,
        "market_confirmation_score": market_result.market_confirmation_score,
        "market_confirmation_level": market_result.level,
        "market_confirmation_reasons": market_result.reasons,
        "market_confirmation_warnings": market_result.warnings,
        "market_confirmation_missing_fields": market_result.missing_fields,
        "market_confirmation_summary": market_result.confirmation_summary,
        "derivatives_confirmation_score": market_result.derivatives_confirmation_score,
        "derivatives_confirmation_level": market_result.derivatives_confirmation_level,
        "derivatives_confirmation_reasons": market_result.derivatives_confirmation_reasons,
        "derivatives_freshness_status": market_result.derivatives_freshness_status,
        "dex_liquidity_score": market_result.dex_liquidity_score,
        "dex_liquidity_level": market_result.dex_liquidity_level,
        "dex_liquidity_reasons": market_result.dex_liquidity_reasons,
        "dex_freshness_status": market_result.dex_freshness_status,
        "protocol_metrics_score": market_result.protocol_metrics_score,
        "protocol_metrics_level": market_result.protocol_metrics_level,
        "protocol_metrics_reasons": market_result.protocol_metrics_reasons,
        "protocol_metrics_freshness_status": market_result.protocol_metrics_freshness_status,
        "market_context_source": market_context.get("source"),
        "market_context_timestamp": market_context.get("timestamp"),
        "market_context_observed_at": market_result.market_context_observed_at or market_context.get("timestamp"),
        "market_context_age_seconds": market_context.get("age_seconds"),
        "market_context_age_hours": market_result.market_context_age_hours,
        "market_context_stale": market_result.market_context_stale,
        "market_context_freshness_status": market_result.market_context_freshness_status,
        "market_context_freshness_cap_applied": market_result.freshness_cap_applied,
        "market_context_data_quality": market_context.get("data_quality"),
        "market_context_snapshot": dict(market_context.get("market_snapshot") or {}),
        "incident_market_reaction_observed": (
            market_result.level in {"observed", "weak", "moderate", "strong"}
            or bool(market_context.get("source"))
            or bool(market_context.get("market_snapshot"))
        ),
        "market_reaction_confirmed": market_result.level in {"weak", "moderate", "strong"},
        "causal_mechanism_confirmed": _causal_mechanism_confirmed(validation, hypothesis),
        "incident_causal_mechanism_confirmed": _causal_mechanism_confirmed(validation, hypothesis),
        "incident_confidence": _component_float(merged_components, "incident_confidence"),
        "opportunity_score_final": verdict.opportunity_score_final,
        "opportunity_level": verdict.opportunity_level,
        "opportunity_verdict_reasons": verdict.verdict_reason_codes,
        "missing_requirements": verdict.missing_requirements,
        "manual_verification_items": verdict.manual_verification_items,
        "why_local_only": verdict.why_local_only,
        "why_not_watchlist": verdict.why_not_watchlist,
        "upgrade_requirements": upgrade_path.upgrade_requirements,
        "downgrade_warnings": upgrade_path.downgrade_warnings,
    }
