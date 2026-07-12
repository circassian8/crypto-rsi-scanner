"""Result construction helpers for Crypto Radar Decision Model v2."""

from __future__ import annotations

from typing import Any, Mapping

from .decision_models import (
    DECISION_MODEL_VERSION,
    CatalystStatus,
    ConfidenceBand,
    DirectionalBias,
    RadarDecision,
    RadarResearchRoute,
    ThesisOrigin,
    TimingState,
    TradabilityStatus,
    actionability_score_cohort,
)


def build_decision_result(
    *, origin: str, bias: str, catalyst: str, confidence: str, timing: str,
    tradability: str, radar_route: str, route_reason: str, actionable: bool,
    actionability: float, evidence_confidence: float, risk: float,
    action_components: Mapping[str, float], evidence_components: Mapping[str, float],
    risk_components: Mapping[str, float], penalty_points: Mapping[str, float],
    blockers: tuple[str, ...], penalties: tuple[str, ...], missing: tuple[str, ...],
    warnings: tuple[str, ...], why_review: tuple[str, ...], confirms: tuple[str, ...],
    invalidates: tuple[str, ...],
) -> RadarDecision:
    """Build the immutable public result after evaluation is complete."""

    rounded_actionability = round(actionability, 2)
    return RadarDecision(
        decision_model_version=DECISION_MODEL_VERSION,
        decision_model_enabled=True,
        thesis_origin=origin,
        directional_bias=bias,
        catalyst_status=catalyst,
        confidence_band=confidence,
        timing_state=timing,
        tradability_status=tradability,
        radar_route=radar_route,
        radar_route_reason=route_reason,
        radar_actionable=actionable,
        actionability_score=rounded_actionability,
        evidence_confidence_score=round(evidence_confidence, 2),
        risk_score=round(risk, 2),
        actionability_score_components=_rounded_map(action_components),
        evidence_confidence_components=_rounded_map(evidence_components),
        risk_score_components=_rounded_map(risk_components),
        actionability_penalty_components=_rounded_map(penalty_points),
        decision_hard_blockers=blockers,
        decision_soft_penalties=penalties,
        decision_missing_data=missing,
        decision_warnings=warnings,
        why_still_worth_reviewing=why_review,
        radar_what_confirms=confirms,
        radar_what_invalidates=invalidates,
        actionability_score_cohort=actionability_score_cohort(rounded_actionability) or "0_24",
    )


def disabled_decision(data: Mapping[str, Any]) -> RadarDecision:
    """Return the stable diagnostic projection when v2 is disabled."""

    del data
    return RadarDecision(
        decision_model_version=DECISION_MODEL_VERSION,
        decision_model_enabled=False,
        thesis_origin=ThesisOrigin.MIXED.value,
        directional_bias=DirectionalBias.NEUTRAL.value,
        catalyst_status=CatalystStatus.UNKNOWN.value,
        confidence_band=ConfidenceBand.DIAGNOSTIC.value,
        timing_state=TimingState.STALE.value,
        tradability_status=TradabilityStatus.BLOCKED.value,
        radar_route=RadarResearchRoute.DIAGNOSTIC.value,
        radar_route_reason="decision_model_v2_disabled",
        radar_actionable=False,
        actionability_score=0.0,
        evidence_confidence_score=0.0,
        risk_score=100.0,
        actionability_score_components={},
        evidence_confidence_components={},
        risk_score_components={},
        actionability_penalty_components={},
        decision_hard_blockers=("decision_model_v2_disabled",),
        decision_soft_penalties=(),
        decision_missing_data=("decision_model_v2_disabled",),
        decision_warnings=("Research decision model disabled; candidate remains diagnostic.",),
        why_still_worth_reviewing=(),
        radar_what_confirms=(),
        radar_what_invalidates=(),
        actionability_score_cohort="0_24",
    )


def _rounded_map(values: Mapping[str, float]) -> dict[str, float]:
    return {key: round(float(value), 2) for key, value in values.items()}
