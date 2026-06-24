"""Final research opportunity verdicts for Event Alpha hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from . import event_evidence_quality, event_impact_path_validator, event_market_confirmation


class OpportunityLevel(str, Enum):
    LOCAL_ONLY = "local_only"
    EXPLORATORY = "exploratory"
    VALIDATED_DIGEST = "validated_digest"
    WATCHLIST = "watchlist"
    HIGH_PRIORITY = "high_priority"


@dataclass(frozen=True)
class OpportunityVerdict:
    opportunity_score_final: float
    opportunity_level: str
    digest_eligible: bool
    watchlist_eligible: bool
    high_priority_eligible: bool
    verdict_reason_codes: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    manual_verification_items: tuple[str, ...]
    why_local_only: str | None = None
    why_not_watchlist: str | None = None
    score_components: Mapping[str, float] | None = None


def evaluate_opportunity(
    *,
    impact_path: event_impact_path_validator.ImpactPathValidation | None,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | None,
    evidence_quality: event_evidence_quality.EvidenceQualityResult | None,
    hypothesis: object | None = None,
    score_components: Mapping[str, Any] | None = None,
) -> OpportunityVerdict:
    """Combine path, market, evidence, timing, liquidity, and resolver confidence."""
    components = dict(score_components or getattr(hypothesis, "score_components", {}) or {})
    path_strength = str(getattr(impact_path, "impact_path_strength", "") or components.get("impact_path_strength") or "")
    path_type = str(getattr(impact_path, "impact_path_type", "") or components.get("impact_path_type") or "")
    role = str(getattr(impact_path, "candidate_role", "") or components.get("candidate_role") or "")
    evidence_specificity = str(getattr(evidence_quality, "evidence_specificity", "") or components.get("evidence_specificity") or "")
    source_class = str(getattr(evidence_quality, "source_class", "") or components.get("source_class") or "")
    category = str(getattr(hypothesis, "impact_category", "") or components.get("impact_category") or "")
    playbook = str(getattr(hypothesis, "playbook_hint", "") or components.get("playbook_type") or category)

    impact_score = _path_strength_score(path_strength)
    market_score = _score(getattr(market_confirmation, "market_confirmation_score", None), components.get("market_confirmation"))
    evidence_score = _score(getattr(evidence_quality, "evidence_quality_score", None), components.get("source_quality"))
    timing_score = _score(components.get("timing_event_window"), components.get("event_time_quality"), components.get("event_clarity"))
    liquidity_score = _score(components.get("liquidity_tradability"), components.get("liquidity"), components.get("tradability"), market_score)
    resolver_score = _score(
        components.get("llm_resolver_confidence"),
        components.get("validation_strength"),
        components.get("candidate_asset_strength"),
        components.get("llm_candidate_confidence"),
    )
    final_components = {
        "impact_path": impact_score,
        "market_confirmation": market_score,
        "evidence_quality": evidence_score,
        "timing_event_window": timing_score,
        "liquidity_tradability": liquidity_score,
        "llm_resolver_confidence": resolver_score,
    }
    score = (
        impact_score * 0.30
        + market_score * 0.25
        + evidence_score * 0.20
        + timing_score * 0.10
        + liquidity_score * 0.10
        + resolver_score * 0.05
    )
    reasons: list[str] = []
    missing: list[str] = []
    verify: list[str] = []

    hard_local = _hard_local_reason(path_type, role, evidence_specificity, source_class, components)
    if hard_local:
        return _verdict(
            score=min(score, 39.0),
            level=OpportunityLevel.LOCAL_ONLY.value,
            reason_codes=(hard_local,),
            missing=(hard_local,),
            verify=("confirm this is not source noise before reviewing further",),
            why_local_only=hard_local,
            why_not_watchlist=hard_local,
            components=final_components,
        )

    if path_type == event_impact_path_validator.ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value:
        reasons.append("generic_cooccurrence_cap")
        score = min(score, 49.0)
        missing.append("explained_token_impact_path")
        verify.append("find source text explaining why the catalyst affects the token")

    weak_macro = path_strength in {"weak", "none"} or path_type in {
        event_impact_path_validator.ImpactPathType.MACRO_ATTENTION_ONLY.value,
        event_impact_path_validator.ImpactPathType.TECHNOLOGY_RISK.value,
        event_impact_path_validator.ImpactPathType.MARKET_STRUCTURE_POLICY.value,
    }
    if weak_macro and market_score < 75:
        reasons.append("weak_macro_requires_strong_market_confirmation")
        score = min(score, 54.0)
        missing.append("strong_market_confirmation")
        verify.append("verify abnormal market reaction, not just policy/macro co-occurrence")

    direct_event = path_type in {
        event_impact_path_validator.ImpactPathType.DIRECT_TOKEN_EVENT.value,
        event_impact_path_validator.ImpactPathType.LISTING_LIQUIDITY_EVENT.value,
        event_impact_path_validator.ImpactPathType.UNLOCK_SUPPLY_EVENT.value,
        event_impact_path_validator.ImpactPathType.EXPLOIT_SECURITY_EVENT.value,
    } or "listing" in category or "unlock" in category or "security" in category
    proxy_event = role in {
        event_impact_path_validator.CandidateRole.PROXY_INSTRUMENT.value,
        event_impact_path_validator.CandidateRole.PROXY_VENUE.value,
    } or "proxy" in playbook

    if direct_event and evidence_score >= 75:
        reasons.append("direct_token_event_with_strong_evidence")
        score = max(score, 66.0)
    if direct_event and evidence_score >= 75 and market_score >= 50:
        reasons.append("direct_token_event_market_confirmed")
        score = max(score, 78.0)
    if proxy_event and path_strength in {"strong", "medium"} and evidence_score >= 65:
        reasons.append("proxy_impact_path_explained")
        score = max(score, 65.0)
    if proxy_event and market_score >= 50:
        reasons.append("proxy_market_attention_confirmed")
        score = max(score, 76.0)
    if market_score < 40:
        missing.append("market_confirmation")
        verify.append("check price, volume, OI/funding, and liquidity before treating as watchlist")
    if evidence_score < 60:
        missing.append("higher_quality_source")
        verify.append("find official, structured, or crypto-native evidence linking token and catalyst")
    if path_strength not in {"strong", "medium"}:
        missing.append("impact_path")
    if timing_score < 40:
        missing.append("event_window_or_timing")
        verify.append("confirm the event date/window and whether the catalyst has passed")

    if score >= 88 and market_score >= 65 and evidence_score >= 70 and not weak_macro:
        level = OpportunityLevel.HIGH_PRIORITY.value
    elif score >= 78 and market_score >= 50 and evidence_score >= 65 and path_strength in {"strong", "medium"}:
        level = OpportunityLevel.WATCHLIST.value
    elif score >= 65 and evidence_score >= 60 and impact_score >= 60:
        level = OpportunityLevel.VALIDATED_DIGEST.value
    elif score >= 45:
        level = OpportunityLevel.EXPLORATORY.value
    else:
        level = OpportunityLevel.LOCAL_ONLY.value

    why_local = None if level != OpportunityLevel.LOCAL_ONLY.value else (missing[0] if missing else "score_below_digest_threshold")
    why_not_watchlist = None if level in {OpportunityLevel.WATCHLIST.value, OpportunityLevel.HIGH_PRIORITY.value} else (
        missing[0] if missing else "score_or_confirmation_below_watchlist_threshold"
    )
    return _verdict(
        score=score,
        level=level,
        reason_codes=tuple(dict.fromkeys(reasons or ("scored_by_final_opportunity_model",))),
        missing=tuple(dict.fromkeys(missing)),
        verify=tuple(dict.fromkeys(verify or ("verify source, catalyst timing, market reaction, and liquidity",))),
        why_local_only=why_local,
        why_not_watchlist=why_not_watchlist,
        components=final_components,
    )


def _verdict(
    *,
    score: float,
    level: str,
    reason_codes: tuple[str, ...],
    missing: tuple[str, ...],
    verify: tuple[str, ...],
    why_local_only: str | None,
    why_not_watchlist: str | None,
    components: Mapping[str, float],
) -> OpportunityVerdict:
    score = round(max(0.0, min(100.0, score)), 2)
    return OpportunityVerdict(
        opportunity_score_final=score,
        opportunity_level=level,
        digest_eligible=level in {
            OpportunityLevel.VALIDATED_DIGEST.value,
            OpportunityLevel.WATCHLIST.value,
            OpportunityLevel.HIGH_PRIORITY.value,
        },
        watchlist_eligible=level in {OpportunityLevel.WATCHLIST.value, OpportunityLevel.HIGH_PRIORITY.value},
        high_priority_eligible=level == OpportunityLevel.HIGH_PRIORITY.value,
        verdict_reason_codes=reason_codes,
        missing_requirements=missing,
        manual_verification_items=verify,
        why_local_only=why_local_only,
        why_not_watchlist=why_not_watchlist,
        score_components={key: round(value, 2) for key, value in components.items()},
    )


def _hard_local_reason(
    path_type: str,
    role: str,
    evidence_specificity: str,
    source_class: str,
    components: Mapping[str, Any],
) -> str | None:
    text = " ".join(
        str(value or "")
        for value in (
            path_type,
            role,
            evidence_specificity,
            source_class,
            components.get("asset_role"),
            components.get("llm_asset_role"),
            *(components.get("warnings") or ()),
            *(components.get("rejection_reasons") or ()),
        )
    ).casefold()
    if "source_noise" in text:
        return "source_noise_hard_gate"
    if "ticker_collision" in text or "word_collision" in text:
        return "ticker_collision_hard_gate"
    return None


def _path_strength_score(strength: str) -> float:
    return {
        "strong": 95.0,
        "medium": 68.0,
        "weak": 35.0,
        "none": 0.0,
    }.get(str(strength or ""), 0.0)


def _score(*values: object) -> float:
    for value in values:
        if value in (None, ""):
            continue
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if 0.0 <= number <= 1.0:
            number *= 100.0
        return max(0.0, min(100.0, number))
    return 0.0
