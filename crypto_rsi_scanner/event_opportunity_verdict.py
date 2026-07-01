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


@dataclass(frozen=True)
class OpportunityUpgradePath:
    upgrade_requirements: tuple[str, ...]
    downgrade_warnings: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class AcquisitionConfirmation:
    confirms_candidate: bool
    confirms_impact_path: bool
    status: str
    reason: str


@dataclass(frozen=True)
class LiveConfirmationVerdict:
    required: bool
    confirmed: bool
    status: str
    reason: str | None
    capped_level: str | None = None
    capped_score: float | None = None
    missing_requirements: tuple[str, ...] = ()
    manual_verification_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerdictAwareUpgradeDowngradeText:
    upgrade_text: str
    downgrade_text: str
    missing_evidence_text: str


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
    cause_status = str(
        getattr(impact_path, "cause_status", "")
        or getattr(hypothesis, "cause_status", "")
        or components.get("cause_status")
        or ""
    )
    claim_polarities = tuple(
        str(value)
        for value in (
            getattr(impact_path, "claim_polarities", ())
            or getattr(hypothesis, "claim_polarities", ())
            or components.get("claim_polarities")
            or ()
        )
        if str(value)
    )
    incident_confidence = _score(
        components.get("incident_confidence"),
        getattr(hypothesis, "incident_confidence", None),
    )
    market_reaction_confirmed = bool(
        components.get("market_reaction_confirmed")
        if components.get("market_reaction_confirmed") is not None
        else getattr(hypothesis, "market_reaction_confirmed", False)
    )
    causal_mechanism_confirmed = bool(
        components.get("causal_mechanism_confirmed")
        if components.get("causal_mechanism_confirmed") is not None
        else getattr(hypothesis, "causal_mechanism_confirmed", False)
    )

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
        "incident_confidence": incident_confidence,
        "market_reaction_confirmed": 100.0 if market_reaction_confirmed else 0.0,
        "causal_mechanism_confirmed": 100.0 if causal_mechanism_confirmed else 0.0,
    }
    market_freshness_status = str(getattr(market_confirmation, "market_context_freshness_status", "") or components.get("market_context_freshness_status") or "")
    market_freshness_cap_applied = bool(
        getattr(market_confirmation, "freshness_cap_applied", False)
        or components.get("freshness_cap_applied")
        or components.get("market_context_freshness_cap_applied")
    )
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
    incident_score_cap: float | None = None
    ecosystem_score_cap: float | None = None

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

    if cause_status == "ruled_out" and path_type == event_impact_path_validator.ImpactPathType.EXPLOIT_SECURITY_EVENT.value:
        return _verdict(
            score=min(score, 39.0),
            level=OpportunityLevel.LOCAL_ONLY.value,
            reason_codes=("incident_cause_ruled_out",),
            missing=("confirmed_causal_mechanism",),
            verify=("do not treat ruled-out exploit language as an exploit catalyst",),
            why_local_only="incident_cause_ruled_out",
            why_not_watchlist="incident_cause_ruled_out",
            components=final_components,
        )

    if cause_status in {"suspected", "unknown"} or any(value in {"rumored", "alleged", "uncertain"} for value in claim_polarities):
        if path_type == event_impact_path_validator.ImpactPathType.EXPLOIT_SECURITY_EVENT.value:
            reasons.append("unconfirmed_incident_cause_cap")
            incident_score_cap = 59.0
            missing.append("confirmed_incident_cause")
            verify.append("confirm whether the suspected incident cause was later confirmed or ruled out")

    if role == event_impact_path_validator.CandidateRole.ECOSYSTEM_AFFECTED_ASSET.value and not market_reaction_confirmed:
        reasons.append("ecosystem_asset_requires_market_reaction")
        ecosystem_score_cap = 64.0
        missing.append("ecosystem_market_reaction_confirmation")
        verify.append("verify contagion into the affected ecosystem asset, not only the third-party incident")

    weak_macro = path_strength in {"weak", "none"} or path_type in {
        event_impact_path_validator.ImpactPathType.MACRO_ATTENTION_ONLY.value,
        event_impact_path_validator.ImpactPathType.TECHNOLOGY_RISK.value,
        event_impact_path_validator.ImpactPathType.MARKET_STRUCTURE_POLICY.value,
    }
    if weak_macro and market_score < 75:
        reasons.append("weak_macro_requires_strong_market_confirmation")
        score = min(score, 54.0)
        missing.append("needs_strong_market_confirmation")
        verify.append("verify abnormal market reaction, not just policy/macro co-occurrence")

    direct_event = path_type in {
        event_impact_path_validator.ImpactPathType.DIRECT_TOKEN_EVENT.value,
        event_impact_path_validator.ImpactPathType.STRATEGIC_INVESTMENT_OR_VALUATION.value,
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
    if (
        direct_event
        and role == event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value
        and cause_status == "confirmed"
        and incident_confidence >= 65
    ):
        reasons.append("confirmed_direct_incident")
        score = max(score, 72.0)
    if (
        direct_event
        and role == event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value
        and causal_mechanism_confirmed
        and market_reaction_confirmed
    ):
        reasons.append("confirmed_causal_incident_with_market_reaction")
        score = max(score, 80.0)
    if proxy_event and path_strength in {"strong", "medium"} and evidence_score >= 65:
        reasons.append("proxy_impact_path_explained")
        score = max(score, 65.0)
    if proxy_event and market_score >= 50:
        reasons.append("proxy_market_attention_confirmed")
        score = max(score, 76.0)
    if incident_score_cap is not None:
        score = min(score, incident_score_cap)
    if ecosystem_score_cap is not None:
        score = min(score, ecosystem_score_cap)
    if market_score < 40:
        missing.append("market_confirmation")
        verify.append("check price, volume, OI/funding, and liquidity before treating as watchlist")
    if market_freshness_status in {"stale", "missing", "unknown"} or market_freshness_cap_applied:
        reasons.append(
            {
                "stale": "market_context_stale_capped",
                "missing": "market_context_missing",
                "unknown": "market_context_unknown_timestamp",
            }.get(market_freshness_status, "market_context_stale_capped")
        )
        missing.append("needs_fresh_market_confirmation")
        verify.append("refresh market context before watchlist/high-priority treatment")
    if evidence_score < 60:
        missing.append("higher_quality_source")
        verify.append("find official, structured, or crypto-native evidence linking token and catalyst")
    if path_strength not in {"strong", "medium"}:
        missing.append(_impact_path_missing_reason(path_type, role, market_score))
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

    if (
        market_freshness_status in {"stale", "missing", "unknown"}
        or market_freshness_cap_applied
    ) and level in {OpportunityLevel.WATCHLIST.value, OpportunityLevel.HIGH_PRIORITY.value}:
        reasons.append("market_context_freshness_watchlist_cap")
        missing.append("needs_fresh_market_confirmation")
        verify.append("run a targeted market refresh before treating this as watchlist/high-priority")
        level = OpportunityLevel.VALIDATED_DIGEST.value if score >= 65 and evidence_score >= 60 and impact_score >= 60 else OpportunityLevel.EXPLORATORY.value

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


def live_confirmation_required(
    *,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> bool:
    """Return true when promoted research opportunities need live confirmation.

    Fixture/test/replay profiles are intentionally exempt so offline evals can
    prove deterministic behavior. Live-style burn-in/no-send/research-send
    profiles require independent source, acquisition, or fresh-market support
    before a scored row may remain validated digest or above.
    """
    profile_text = str(profile or "").strip().casefold()
    mode_text = str(run_mode or "").strip().casefold()
    namespace_text = str(artifact_namespace or "").strip().casefold()
    fixture_profiles = {
        "fixture",
        "quality_validation",
        "catalyst_frame_validation",
        "catalyst_frame_e2e",
        "notify_llm_quality_frame",
        "market_refresh_smoke",
        "evidence_acquisition_smoke",
    }
    if profile_text in fixture_profiles or mode_text in {"test", "fixture", "replay"}:
        return False
    live_markers = (
        "live",
        "notify",
        "research_send",
        "burn_in",
        "no_send",
        "operational",
    )
    return (
        mode_text in {"notification_burn_in", "burn_in", "operational"}
        or any(marker in profile_text for marker in live_markers)
        or any(marker in namespace_text for marker in live_markers)
    )


def classify_acquisition_confirmation(row: Mapping[str, Any] | None) -> AcquisitionConfirmation:
    """Classify whether acquisition evidence confirms a live candidate."""
    data = dict(row or {})
    nested = data.get("evidence_acquisition_results")
    if not isinstance(nested, Mapping):
        nested = {}
    status = str(
        data.get("evidence_acquisition_status")
        or data.get("acquisition_status")
        or data.get("source_acquisition_status")
        or nested.get("status")
        or data.get("acquisition_evidence_status")
        or ""
    ).strip()
    accepted_count = _count_value(
        data.get("evidence_acquisition_accepted_count"),
        data.get("accepted_evidence_count"),
        nested.get("accepted"),
        data.get("accepted_evidence"),
        data.get("evidence_acquisition_accepted_evidence"),
    )
    rejected_count = _count_value(
        data.get("evidence_acquisition_rejected_count"),
        data.get("rejected_evidence_count"),
        nested.get("rejected"),
        data.get("rejected_evidence"),
        data.get("rejected_evidence_samples"),
        data.get("evidence_acquisition_rejected_samples"),
    )
    if accepted_count > 0 or status == "accepted_evidence_found":
        return AcquisitionConfirmation(True, True, "confirms", "accepted_evidence_found")
    if status == "rejected_results_only" or rejected_count > 0:
        return AcquisitionConfirmation(False, False, "does_not_confirm", "rejected_results_only_not_confirmation")
    if status == "no_results":
        return AcquisitionConfirmation(False, False, "does_not_confirm", "no_results_not_confirmation")
    if status == "skipped_budget":
        return AcquisitionConfirmation(False, False, "unresolved", "skipped_budget_not_confirmation")
    if status in {"provider_unavailable", "provider_backoff", "skipped_config", "not_configured", "failed_soft"}:
        return AcquisitionConfirmation(False, False, "coverage_gap", f"{status}_not_confirmation")
    if status in {"planned", "not_executed", ""}:
        return AcquisitionConfirmation(False, False, "coverage_gap", "evidence_acquisition_not_executed")
    return AcquisitionConfirmation(False, False, "unresolved", "evidence_acquisition_not_confirming")


def apply_live_confirmation_policy(
    row: Mapping[str, Any],
    *,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    allow_sector_digest: bool = False,
    allow_source_only_narrative_digest: bool = False,
) -> LiveConfirmationVerdict:
    """Return a live/no-send promotion cap for one canonical opportunity row.

    The LLM/provider layer never creates trades or event-fade triggers; this
    policy only decides whether a research artifact may stay validated digest or
    above in live-style profiles.
    """
    data = dict(row)
    required = live_confirmation_required(
        profile=profile or data.get("profile"),
        run_mode=run_mode or data.get("run_mode"),
        artifact_namespace=artifact_namespace or data.get("artifact_namespace"),
    )
    level = str(data.get("final_opportunity_level") or data.get("opportunity_level") or "").strip()
    if not required or level not in {
        OpportunityLevel.VALIDATED_DIGEST.value,
        OpportunityLevel.WATCHLIST.value,
        OpportunityLevel.HIGH_PRIORITY.value,
    }:
        return LiveConfirmationVerdict(required=required, confirmed=True, status="not_required", reason=None)
    acquisition = classify_acquisition_confirmation(data)
    if _is_sector_only_row(data) and not allow_sector_digest:
        return _live_cap(data, "sector_only_digest_not_allowed", acquisition)
    if _source_only_narrative_without_market_confirmation(
        data,
        acquisition,
        allow_source_only_narrative_digest=allow_source_only_narrative_digest,
    ):
        return _live_cap(data, "source_only_narrative_without_market_confirmation", acquisition)
    if acquisition.confirms_candidate and acquisition.confirms_impact_path:
        return LiveConfirmationVerdict(required=True, confirmed=True, status="confirmed", reason="accepted_evidence_found")
    confirmation_reason = _strong_live_confirmation_reason(data)
    if confirmation_reason:
        return LiveConfirmationVerdict(required=True, confirmed=True, status="confirmed", reason=confirmation_reason)
    if _broad_context_only(data):
        return _live_cap(data, "broad_or_prediction_market_context_not_confirmation", acquisition)
    return _live_cap(data, acquisition.reason or "live_confirmation_missing", acquisition)


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


def _impact_path_missing_reason(path_type: str, role: str, market_score: float) -> str:
    """Return a blocker that says what is missing, not positive evidence."""
    weak_context = path_type in {
        event_impact_path_validator.ImpactPathType.MACRO_ATTENTION_ONLY.value,
        event_impact_path_validator.ImpactPathType.TECHNOLOGY_RISK.value,
        event_impact_path_validator.ImpactPathType.MARKET_STRUCTURE_POLICY.value,
        event_impact_path_validator.ImpactPathType.GENERIC_COOCCURRENCE_ONLY.value,
        event_impact_path_validator.ImpactPathType.UNKNOWN.value,
        "",
    } or role in {
        event_impact_path_validator.CandidateRole.GENERIC_MENTION.value,
        event_impact_path_validator.CandidateRole.MACRO_AFFECTED_ASSET.value,
        "",
    }
    if market_score >= 75:
        return "weak_impact_path_despite_market_confirmation" if weak_context else "impact_path_not_strong_enough"
    if weak_context:
        return "missing_direct_impact_path"
    return "impact_path_not_strong_enough"


def explain_upgrade_path(
    *,
    verdict: OpportunityVerdict | Mapping[str, Any] | None = None,
    impact_path: event_impact_path_validator.ImpactPathValidation | Mapping[str, Any] | None = None,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | Mapping[str, Any] | None = None,
    evidence_quality: event_evidence_quality.EvidenceQualityResult | Mapping[str, Any] | None = None,
    components: Mapping[str, Any] | None = None,
) -> OpportunityUpgradePath:
    """Explain how a research candidate could improve or invalidate.

    The output is diagnostic text only. It does not mutate thresholds, routes,
    alerts, paper rows, live storage, or event-fade eligibility.
    """
    data = dict(components or {})
    data.update(_object_mapping("verdict", verdict))
    data.update(_object_mapping("impact_path", impact_path))
    data.update(_object_mapping("market", market_confirmation))
    data.update(_object_mapping("evidence", evidence_quality))

    level = str(data.get("opportunity_level") or data.get("verdict_opportunity_level") or "")
    path_type = str(data.get("impact_path_type") or data.get("impact_path_impact_path_type") or "")
    path_strength = str(data.get("impact_path_strength") or data.get("impact_path_impact_path_strength") or "")
    role = str(data.get("candidate_role") or data.get("impact_path_candidate_role") or "")
    evidence_specificity = str(data.get("evidence_specificity") or data.get("evidence_evidence_specificity") or "")
    source_class = str(data.get("source_class") or data.get("evidence_source_class") or "")
    market_level = str(data.get("market_confirmation_level") or data.get("level") or data.get("market_level") or "")
    market_score = _score(data.get("market_confirmation_score"), data.get("market_market_confirmation_score"), data.get("market_confirmation"))
    evidence_score = _score(data.get("evidence_quality_score"), data.get("evidence_evidence_quality_score"), data.get("source_quality"))
    timing_score = _score(data.get("timing_event_window"), data.get("event_time_quality"), data.get("event_clarity"))
    derivatives_score = _score(data.get("derivatives_crowding"), data.get("derivatives"), data.get("oi_expansion"))
    supply_score = _score(data.get("supply_pressure"), data.get("unlock_pressure"))
    text = " ".join(str(value or "") for value in (level, path_type, path_strength, role, evidence_specificity, source_class, data)).casefold()

    upgrades: list[str] = []
    downgrades: list[str] = []
    if "source_noise" in text:
        upgrades.append("blocked_by_source_noise")
        downgrades.append("source_low_quality")
    if "ticker_collision" in text or "word_collision" in text:
        upgrades.append("needs_identity_validation")
        downgrades.append("token_identity_ambiguous")
    if "generic_cooccurrence" in text:
        upgrades.append("blocked_by_generic_cooccurrence")
        upgrades.append("needs_direct_token_mechanism")
        downgrades.append("no_value_capture")
    if path_strength not in {"strong", "medium"}:
        upgrades.append("needs_direct_token_mechanism")
    if role in {"generic_mention", "macro_affected_asset", ""} and path_type in {
        "technology_risk",
        "market_structure_policy",
        "macro_attention_only",
        "generic_cooccurrence_only",
        "",
    }:
        upgrades.append("needs_catalyst_link")
    if market_score < 50 or market_level in {"", "none", "weak"}:
        upgrades.append("needs_market_confirmation")
        downgrades.append("market_reaction_absent")
    freshness_status = str(data.get("market_context_freshness_status") or data.get("market_market_context_freshness_status") or "")
    if freshness_status in {"stale", "missing", "unknown"} or bool(data.get("freshness_cap_applied") or data.get("market_freshness_cap_applied")):
        upgrades.append("needs_fresh_market_confirmation")
        downgrades.append("market_context_stale")
    if evidence_score < 65:
        upgrades.append("needs_higher_quality_source")
        downgrades.append("source_low_quality")
    if timing_score < 40:
        upgrades.append("needs_event_time")
    if any(term in text for term in ("proxy", "perp", "listing", "venue")) and derivatives_score < 40:
        upgrades.append("needs_derivatives_confirmation")
    if any(term in text for term in ("unlock", "supply", "airdrop", "tge")) and supply_score < 40:
        upgrades.append("needs_supply_confirmation")
    if _score(data.get("opportunity_score_final"), data.get("verdict_opportunity_score_final")) < 65:
        upgrades.append("blocked_by_low_score")
    if any(term in text for term in ("stale", "expired")):
        downgrades.append("event_stale")
    if any(term in text for term in ("disputed", "conflict", "contradict")):
        downgrades.append("catalyst_disputed")
        downgrades.append("conflicting_evidence")
    if _score(data.get("liquidity_tradability"), data.get("liquidity"), data.get("tradability")) < 25:
        downgrades.append("liquidity_too_thin")
    if not upgrades and level in {"watchlist", "high_priority"}:
        upgrades.append("monitor_for_stronger_market_confirmation")
    if not downgrades:
        downgrades.append("conflicting_evidence")
    upgrades = list(dict.fromkeys(upgrades))
    downgrades = list(dict.fromkeys(downgrades))
    summary = (
        "upgrade=" + ", ".join(upgrades[:4])
        + " · downgrade=" + ", ".join(downgrades[:4])
    )
    return OpportunityUpgradePath(
        upgrade_requirements=tuple(upgrades),
        downgrade_warnings=tuple(downgrades),
        summary=summary,
    )


def build_verdict_aware_upgrade_downgrade_text(
    components: Mapping[str, Any] | None = None,
) -> VerdictAwareUpgradeDowngradeText:
    """Return operator copy that respects the final opportunity verdict.

    This is presentation-only. It prevents canonical promoted opportunities
    from rendering stale support-row gate blockers in primary card/audit text.
    """
    data = dict(components or {})
    level = str(
        data.get("final_opportunity_level")
        or data.get("opportunity_level")
        or data.get("verdict_opportunity_level")
        or ""
    ).strip().casefold()
    route = str(data.get("final_route_after_quality_gate") or data.get("route") or "").upper()
    if level == OpportunityLevel.HIGH_PRIORITY.value or "HIGH_PRIORITY" in route:
        return VerdictAwareUpgradeDowngradeText(
            upgrade_text=(
                "Already high priority; further upgrade would require sustained fresh market "
                "confirmation, stronger source corroboration, or derivatives/liquidity support."
            ),
            downgrade_text=(
                "Source correction or denial, invalid exposure/value-capture claim, fading market "
                "confirmation, drying liquidity, or stale catalyst timing."
            ),
            missing_evidence_text="No primary hard-gate blocker remains for this high-priority research opportunity.",
        )
    if level == OpportunityLevel.WATCHLIST.value or "WATCHLIST" in route:
        return VerdictAwareUpgradeDowngradeText(
            upgrade_text=(
                "Could upgrade to high priority with fresh stronger market confirmation, "
                "derivatives/liquidity confirmation, or a second independent high-quality source."
            ),
            downgrade_text=(
                "Source correction or denial, failed catalyst-to-token mechanism, weak market "
                "follow-through, or deteriorating liquidity."
            ),
            missing_evidence_text="Watchlist candidate; remaining gaps are confirmation depth, not basic eligibility.",
        )
    if level == OpportunityLevel.VALIDATED_DIGEST.value or "RESEARCH_DIGEST" in route:
        return VerdictAwareUpgradeDowngradeText(
            upgrade_text=(
                "Could upgrade to watchlist with fresh price/volume reaction, official or second-source "
                "confirmation, or derivatives/supply confirmation."
            ),
            downgrade_text=(
                "Source correction, catalyst-link rejection, absent market reaction, or stale market context."
            ),
            missing_evidence_text="Validated digest candidate; needs stronger market or corroborating evidence for watchlist.",
        )
    if level == OpportunityLevel.EXPLORATORY.value:
        return VerdictAwareUpgradeDowngradeText(
            upgrade_text=(
                "Needs validated catalyst link, deterministic asset identity, direct token mechanism, "
                "or stronger market confirmation depending on the missing fields."
            ),
            downgrade_text=(
                "Treat as local research if catalyst evidence remains source-thin, ambiguous, or unsupported by market reaction."
            ),
            missing_evidence_text="Exploratory candidate; primary gaps must be resolved before promotion.",
        )
    return VerdictAwareUpgradeDowngradeText(
        upgrade_text=(
            "Needs validated catalyst evidence, deterministic asset identity, a direct token mechanism, "
            "and market confirmation before promotion."
        ),
        downgrade_text=(
            "Keep local-only if the item remains generic co-occurrence, source noise, or market move without a catalyst."
        ),
        missing_evidence_text="Local-only candidate; primary eligibility evidence is still missing.",
    )


def _object_mapping(prefix: str, value: object | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    out: dict[str, Any] = {}
    for key in (
        "opportunity_score_final",
        "opportunity_level",
        "impact_path_type",
        "impact_path_strength",
        "candidate_role",
        "market_confirmation_score",
        "level",
        "market_context_freshness_status",
        "market_context_age_hours",
        "freshness_cap_applied",
        "derivatives_confirmation_score",
        "derivatives_confirmation_level",
        "derivatives_confirmation_reasons",
        "derivatives_freshness_status",
        "dex_liquidity_score",
        "dex_liquidity_level",
        "dex_liquidity_reasons",
        "dex_freshness_status",
        "protocol_metrics_score",
        "protocol_metrics_level",
        "protocol_metrics_reasons",
        "protocol_metrics_freshness_status",
        "evidence_quality_score",
        "source_class",
        "evidence_specificity",
    ):
        if hasattr(value, key):
            out[key] = getattr(value, key)
            out[f"{prefix}_{key}"] = getattr(value, key)
    return out


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


def _live_cap(
    data: Mapping[str, Any],
    reason: str,
    acquisition: AcquisitionConfirmation,
) -> LiveConfirmationVerdict:
    current_score = _score(data.get("final_opportunity_score"), data.get("opportunity_score_final"))
    sector = _is_sector_only_row(data)
    generic = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip() in {
        "",
        "unknown",
        "insufficient_data",
        "generic_cooccurrence_only",
        "macro_attention_only",
        "technology_risk",
        "market_structure_policy",
    }
    if sector or generic or current_score < 45:
        level = OpportunityLevel.LOCAL_ONLY.value
        score_cap = 44.0
    else:
        level = OpportunityLevel.EXPLORATORY.value
        score_cap = 64.0
    missing = (
        reason,
        "accepted_source_pack_evidence_or_fresh_market_confirmation",
    )
    verify = (
        "find accepted source-pack evidence, official/structured evidence, or fresh market confirmation before digest promotion",
    )
    if acquisition.status == "coverage_gap":
        verify = (
            "resolve source-pack coverage before treating this live candidate as validated",
        )
    return LiveConfirmationVerdict(
        required=True,
        confirmed=False,
        status="missing",
        reason=reason,
        capped_level=level,
        capped_score=min(current_score or score_cap, score_cap),
        missing_requirements=missing,
        manual_verification_items=verify,
    )


def _strong_live_confirmation_reason(data: Mapping[str, Any]) -> str | None:
    source_class = str(data.get("source_class") or "").strip()
    source_classes = {
        source_class,
        *(
            str(value)
            for value in _as_values(data.get("source_classes"))
            if str(value or "").strip()
        ),
    }
    evidence_score = _score(data.get("evidence_quality_score"), data.get("post_refresh_evidence_quality_score"))
    market_score = _score(data.get("market_confirmation_score"), data.get("market_confirmation_after"))
    market_level = str(data.get("market_confirmation_level") or "").strip()
    freshness = str(data.get("market_context_freshness_status") or data.get("market_data_freshness") or "").strip()
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip()
    impact_strength = str(data.get("impact_path_strength") or "").strip()
    reason_codes = {
        str(value)
        for value in (
            *_as_values(data.get("accepted_evidence_reason_codes")),
            *_as_values(data.get("source_registry_reasons")),
            *_as_values(data.get("reason_codes")),
        )
        if str(value or "").strip()
    }
    official_or_structured = {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
    }
    if source_classes.intersection(official_or_structured) and evidence_score >= 65:
        return "official_or_structured_source_confirmation"
    if (
        "cryptopanic_tagged" in source_classes or "cryptopanic_currency_tag_match" in reason_codes
    ) and not _narrative_source_pack(data) and not _cryptopanic_tag_only_cannot_confirm_direct_path(data):
        return "cryptopanic_tagged_token_catalyst_confirmation"
    if (
        market_score >= 75
        and (market_level in {"strong", "confirmed"} or market_score >= 85)
        and freshness in {"fresh", "fixture_allowed_stale"}
        and _non_generic_impact_path(impact_path, impact_strength)
    ):
        return "fresh_market_confirmation"
    if (
        evidence_score >= 85
        and source_class not in {"", "broad_news", "prediction_market", "seo_or_affiliate", "social_or_unknown", "insufficient_data"}
        and _non_generic_impact_path(impact_path, impact_strength)
    ):
        if _strategic_broad_asset_context_only(data):
            return None
        return "strong_direct_original_source_evidence"
    if (
        impact_path in {"direct_token_event", "listing_liquidity_event", "unlock_supply_event", "exploit_security_event"}
        and source_class not in {"", "broad_news", "prediction_market", "seo_or_affiliate", "social_or_unknown", "insufficient_data"}
        and evidence_score >= 70
    ):
        if impact_path == "unlock_supply_event" and not _has_official_or_structured_evidence(data):
            return None
        if _cryptopanic_tag_only_cannot_confirm_direct_path(data):
            return None
        return "explicit_deterministic_direct_event_source"
    return None


def _source_only_narrative_without_market_confirmation(
    data: Mapping[str, Any],
    acquisition: AcquisitionConfirmation,
    *,
    allow_source_only_narrative_digest: bool,
) -> bool:
    """Return true for narrative-pack rows where one news source is not enough.

    Token-tagged CryptoPanic evidence is valuable context, but for fan-token,
    pre-IPO/RWA proxy, and political-meme narratives it should not be the sole
    reason a live-style row stays validated digest or higher. Those rows need
    official/structured corroboration, a second accepted source, or fresh market
    confirmation unless the operator explicitly opts in.
    """
    if allow_source_only_narrative_digest or not _narrative_source_pack(data):
        return False
    if _has_official_or_structured_evidence(data):
        return False
    accepted_count = _count_value(
        data.get("evidence_acquisition_accepted_count"),
        data.get("accepted_evidence_count"),
        data.get("accepted_evidence"),
        data.get("evidence_acquisition_accepted_evidence"),
    )
    if accepted_count >= 2:
        return False
    if _has_fresh_market_confirmation(data):
        return False
    if accepted_count > 0 or acquisition.confirms_candidate:
        return True
    reason_codes = {
        str(value)
        for value in (
            *_as_values(data.get("accepted_evidence_reason_codes")),
            *_as_values(data.get("accepted_reason_codes")),
            *_as_values(data.get("source_registry_reasons")),
            *_as_values(data.get("reason_codes")),
        )
        if str(value or "").strip()
    }
    return "cryptopanic_currency_tag_match" in {item.casefold() for item in reason_codes}


def _narrative_source_pack(data: Mapping[str, Any]) -> bool:
    if str(data.get("source_pack") or "").strip().casefold() in {
        "fan_sports_pack",
        "proxy_preipo_rwa_pack",
        "political_meme_pack",
    }:
        return True
    return _has_narrative_or_proxy_semantics(data)


def _has_narrative_or_proxy_semantics(data: Mapping[str, Any]) -> bool:
    values = _lower_values(
        data,
        "supporting_categories",
        "supporting_impact_paths",
        "impact_category",
        "impact_path_type",
        "primary_impact_path",
        "impact_path_reason",
        "playbook_type",
        "effective_playbook_type",
        "latest_playbook_type",
        "relationship_type",
        "candidate_role",
    )
    narrative_tokens = {
        "sports_fan_proxy",
        "fan_sports_proxy",
        "fan_token_attention",
        "fan_token_event",
        "fan_token",
        "sports_proxy",
        "proxy_attention",
        "proxy_exposure",
        "proxy_instrument",
        "proxy_venue",
        "venue_value_capture",
        "rwa_preipo_proxy",
        "rwa_preipo",
        "preipo_proxy",
        "pre_ipo_proxy",
        "tokenized_stock_venue",
        "political_meme",
        "political_meme_proxy",
        "meme_attention",
    }
    if values.intersection(narrative_tokens):
        return True
    text = _lower_text_blob(
        data,
        "canonical_incident_name",
        "incident_canonical_name",
        "latest_event_name",
        "event_name",
        "latest_source_title",
        "source_title",
        "why_opportunity_visible",
        "final_verdict_reason",
    )
    return any(
        term in text
        for term in (
            "fan token",
            "world cup",
            "champions league",
            "proxy narrative",
            "pre-ipo",
            "pre ipo",
            "tokenized stock",
            "synthetic exposure",
            "political meme",
            "election meme",
        )
    )


def _has_official_or_structured_evidence(data: Mapping[str, Any]) -> bool:
    source_classes = _lower_values(data, "source_class", "source_classes")
    reason_codes = _lower_values(
        data,
        "accepted_evidence_reason_codes",
        "accepted_reason_codes",
        "source_registry_reasons",
        "reason_codes",
    )
    provider_counts = {
        str(key or "").strip().casefold()
        for key in (
            data.get("accepted_provider_counts").keys()
            if isinstance(data.get("accepted_provider_counts"), Mapping)
            else ()
        )
    }
    official_or_structured = {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    if source_classes.intersection(official_or_structured):
        return True
    if provider_counts.intersection({"tokenomist", "coinmarketcal", "binance_announcements", "bybit_announcements"}):
        return True
    return bool(
        reason_codes.intersection(
            {
                "official_project_source",
                "official_exchange_announcement",
                "official_exchange_identity_match",
                "structured_unlock_evidence",
                "structured_calendar_evidence",
                "tokenomist_unlock_match",
                "unlock_schedule_match",
                "direct_token_unlock_fact",
            }
        )
    )


def _cryptopanic_tag_only_cannot_confirm_direct_path(data: Mapping[str, Any]) -> bool:
    source_classes = _lower_values(data, "source_class", "source_classes")
    reason_codes = _lower_values(
        data,
        "accepted_evidence_reason_codes",
        "accepted_reason_codes",
        "source_registry_reasons",
        "reason_codes",
    )
    cryptopanic_tagged = "cryptopanic_tagged" in source_classes or "cryptopanic_currency_tag_match" in reason_codes
    if not cryptopanic_tagged:
        return False
    if _has_narrative_or_proxy_semantics(data):
        return True
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip().casefold()
    if impact_path == "unlock_supply_event" and not _has_official_or_structured_evidence(data):
        return True
    return False


def _has_fresh_market_confirmation(data: Mapping[str, Any]) -> bool:
    market_score = _score(
        data.get("market_confirmation_score"),
        data.get("market_confirmation_after"),
        data.get("market_move_volume"),
    )
    market_level = str(
        data.get("market_confirmation_level")
        or data.get("market_confirmation")
        or data.get("market_reaction_confirmation")
        or ""
    ).strip().casefold()
    freshness = str(
        data.get("market_context_freshness_status")
        or data.get("market_data_freshness")
        or data.get("market_freshness_status")
        or ""
    ).strip().casefold()
    fresh_context = freshness in {"fresh", "fixture_allowed_stale"}
    return fresh_context and (market_score >= 40 or market_level in {"moderate", "strong", "confirmed", "fresh"})


def _lower_values(data: Mapping[str, Any], *keys: str) -> set[str]:
    out: set[str] = set()
    for key in keys:
        for value in _as_values(data.get(key)):
            text = str(value or "").strip().casefold()
            if text:
                out.add(text)
    return out


def _lower_text_blob(data: Mapping[str, Any], *keys: str) -> str:
    return " ".join(
        str(data.get(key) or "")
        for key in keys
        if str(data.get(key) or "").strip()
    ).casefold()


def _non_generic_impact_path(path: str, strength: str) -> bool:
    if strength in {"strong", "medium"} and path not in {"", "unknown", "insufficient_data"}:
        return True
    return path not in {
        "",
        "unknown",
        "insufficient_data",
        "generic_cooccurrence_only",
        "macro_attention_only",
        "technology_risk",
        "market_structure_policy",
    }


def _strategic_broad_asset_context_only(data: Mapping[str, Any]) -> bool:
    """Return true for broad-asset treasury/valuation context, not token impact.

    A crypto-news article about Strategy/MSTR, ETF/company equity valuation,
    market structure, or treasury discounts can mention BTC/ETH/SOL directly
    without proving that the asset itself is the affected subject. Accepted
    source-pack evidence or fresh market confirmation can still validate those
    rows through the normal live-confirmation paths.
    """
    symbol = str(data.get("symbol") or data.get("validated_symbol") or "").strip().upper()
    coin_id = str(data.get("coin_id") or data.get("validated_coin_id") or "").strip().casefold()
    broad_asset = symbol in {"BTC", "ETH", "SOL"} or coin_id in {"bitcoin", "ethereum", "solana"}
    if not broad_asset:
        return False
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip().casefold()
    impact_reason = str(data.get("impact_path_reason") or data.get("primary_impact_path_reason") or "").strip().casefold()
    event_archetype = str(data.get("event_archetype") or data.get("main_frame_type") or "").strip().casefold()
    strategic = any(
        token in {impact_path, impact_reason, event_archetype}
        for token in {
            "strategic_investment",
            "strategic_investment_or_valuation",
            "valuation_event",
            "treasury_context",
            "external_equity_proxy_context",
        }
    )
    if not strategic:
        return False
    text = " ".join(
        str(value or "")
        for value in (
            data.get("canonical_incident_name"),
            data.get("incident_canonical_name"),
            data.get("latest_event_name"),
            data.get("event_name"),
            data.get("latest_source_title"),
            data.get("source_title"),
            data.get("latest_source"),
            data.get("source"),
            data.get("why_opportunity_visible"),
            data.get("final_verdict_reason"),
        )
    ).casefold()
    context_terms = (
        "strategy",
        "microstrategy",
        "mstr",
        "treasury",
        "holdings",
        "valuation",
        "discount",
        "premium",
        "public company",
        "equity valuation",
        "shares",
        "stock",
        "cme",
        "sec",
        "cftc",
        "market structure",
    )
    if not any(term in text for term in context_terms):
        return False
    direct_terms = (
        "protocol upgrade",
        "network upgrade",
        "bitcoin etf approved",
        "ethereum etf approved",
        "solana etf approved",
        "spot bitcoin etf",
        "spot ethereum etf",
        "spot solana etf",
        "listing",
        "unlock",
        "exploit",
    )
    return not any(term in text for term in direct_terms)


def _is_sector_only_row(data: Mapping[str, Any]) -> bool:
    symbol = str(data.get("symbol") or data.get("validated_symbol") or "").strip().upper()
    coin_id = str(data.get("coin_id") or data.get("validated_coin_id") or "").strip().casefold()
    if symbol == "SECTOR":
        return True
    return coin_id in {
        "sports_fan_proxy",
        "political_meme_proxy",
        "ai_ipo_proxy",
        "rwa_preipo_proxy",
        "market_anomaly",
        "sector",
    }


def _broad_context_only(data: Mapping[str, Any]) -> bool:
    source_class = str(data.get("source_class") or "").strip()
    if source_class not in {"prediction_market", "broad_news"}:
        return False
    acquisition = classify_acquisition_confirmation(data)
    if acquisition.confirms_candidate:
        return False
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip()
    specificity = str(data.get("evidence_specificity") or "").strip()
    direct_mechanism = specificity in {"direct_token_mechanism", "official_direct_event", "specific"}
    return not (direct_mechanism and _non_generic_impact_path(impact_path, str(data.get("impact_path_strength") or "")))


def _count_value(*values: object) -> int:
    for value in values:
        if value in (None, "", (), [], {}):
            continue
        if isinstance(value, Mapping):
            return len(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 1
        try:
            if isinstance(value, (list, tuple, set)):
                return len(value)
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return 0


def _as_values(value: object) -> tuple[object, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, Mapping):
        return tuple(value.values())
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)
