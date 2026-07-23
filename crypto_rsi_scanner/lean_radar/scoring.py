"""Transparent four-score projection for Lean Crypto Radar."""

from __future__ import annotations

from .models import MarketFeatures, SetupDetection


_ACTION_BASE = {
    "market_breakout_long": 70.0,
    "relative_strength_long": 65.0,
    "pullback_or_mean_reversion": 62.0,
    "rapid_market_anomaly": 78.0,
    "exhaustion_or_fade_review": 60.0,
    "selloff_or_risk_warning": 70.0,
    "dashboard_watch": 45.0,
    "diagnostic": 0.0,
}
_URGENCY_BASE = {
    "market_breakout_long": 68.0,
    "relative_strength_long": 58.0,
    "pullback_or_mean_reversion": 48.0,
    "rapid_market_anomaly": 85.0,
    "exhaustion_or_fade_review": 62.0,
    "selloff_or_risk_warning": 78.0,
    "dashboard_watch": 35.0,
    "diagnostic": 0.0,
}


def score_setup(
    features: MarketFeatures,
    detection: SetupDetection,
    *,
    catalyst_status: str = "unknown",
) -> dict[str, object]:
    snapshot = features.snapshot
    actionability = _ACTION_BASE[detection.idea_type]
    actionability += (detection.strength - 50.0) * 0.18
    confidence = 68.0 if features.baseline_status == "warm" else 56.0
    confidence += 4.0 if snapshot.rsi_14 is not None else 0.0
    confidence += 4.0 if features.benchmark_status == "ready" else 0.0
    risk = 38.0 + features.chase_risk_score * 0.28
    urgency = _URGENCY_BASE[detection.idea_type]
    urgency += max(0.0, detection.strength - 60.0) * 0.15

    if catalyst_status == "unknown":
        confidence -= 8.0
        risk += 10.0
    elif catalyst_status in {"known", "confirmed"}:
        confidence += 6.0
    if features.baseline_status != "warm":
        risk += 8.0
    if features.liquidity_status != "adequate":
        actionability = 0.0
        confidence = min(confidence, 35.0)
        risk = max(risk, 85.0)
        urgency = min(urgency, 20.0)
    if snapshot.spread_bps is None:
        confidence = min(confidence - 8.0, 60.0)
        risk += 8.0
        urgency = min(urgency, 55.0)
    elif snapshot.spread_bps > 50:
        confidence -= 10.0
        risk += 15.0
        urgency = min(urgency, 50.0)
    if detection.diagnostic_only:
        actionability = 0.0
        confidence = min(confidence, 25.0)
        risk = max(risk, 90.0)
        urgency = 0.0

    scores = {
        "actionability": _bounded(actionability),
        "confidence": _bounded(confidence),
        "risk": _bounded(risk),
        "urgency": _bounded(urgency),
    }
    scores["route"] = _route(scores, detection)
    return scores


def _route(scores: dict[str, object], detection: SetupDetection) -> str:
    if detection.diagnostic_only:
        return "diagnostic_hidden"
    if detection.idea_type in {"calendar_risk"}:
        return "risk_calendar"
    actionability = float(scores["actionability"])
    urgency = float(scores["urgency"])
    if actionability >= 70 and urgency >= 70:
        return "urgent_review"
    if actionability >= 58 or detection.idea_type in {
        "exhaustion_or_fade_review",
        "selloff_or_risk_warning",
    }:
        return "watchlist"
    if actionability >= 45:
        return "daily_digest"
    return "dashboard_only"


def _bounded(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 1)


__all__ = ("score_setup",)
