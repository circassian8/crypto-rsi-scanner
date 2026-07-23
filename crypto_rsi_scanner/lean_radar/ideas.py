"""Create one operator-facing LeanIdea from one detected market setup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Mapping

from .models import LeanIdea, MarketFeatures, SetupDetection
from .scoring import score_setup


_HORIZON = {
    "market_breakout_long": "4h",
    "relative_strength_long": "4h",
    "pullback_or_mean_reversion": "4h_to_24h",
    "rapid_market_anomaly": "1h_to_4h",
    "exhaustion_or_fade_review": "1h_to_4h",
    "selloff_or_risk_warning": "1h_to_4h",
    "dashboard_watch": "4h_to_24h",
    "diagnostic": "diagnostic",
}
_TTL_HOURS = {
    "market_breakout_long": 4,
    "relative_strength_long": 6,
    "pullback_or_mean_reversion": 8,
    "rapid_market_anomaly": 1,
    "exhaustion_or_fade_review": 4,
    "selloff_or_risk_warning": 4,
    "dashboard_watch": 12,
    "diagnostic": 1,
}


def build_idea(
    features: MarketFeatures,
    detection: SetupDetection,
    *,
    catalyst_context: Mapping[str, object] | None = None,
) -> LeanIdea:
    snapshot = features.snapshot
    catalyst_status = _catalyst_status(catalyst_context)
    scored = score_setup(features, detection, catalyst_status=catalyst_status)
    created = datetime.fromisoformat(snapshot.observed_at.replace("Z", "+00:00"))
    expires = created + timedelta(hours=_TTL_HOURS[detection.idea_type])
    missing: list[str] = []
    if catalyst_status == "unknown":
        missing.append("Known catalyst or explanation")
    if snapshot.spread_bps is None:
        missing.append("Current Bybit spread and depth")
    if features.baseline_status != "warm":
        missing.append("Warm rolling volume baseline")
    if snapshot.rsi_14 is None:
        missing.append("Sufficient sparkline history for RSI")
    if features.benchmark_status != "ready":
        missing.append("Complete BTC and ETH relative context")
    route = str(scored["route"])
    identity = (
        f"{snapshot.canonical_asset_id}|{snapshot.bybit_instrument}|"
        f"{detection.idea_type}|{snapshot.observed_at}"
    )
    idea_id = "lean-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    risks = list(detection.risks)
    if catalyst_status == "unknown":
        risks.append("Unknown catalyst increases explanation and manipulation risk")
    if snapshot.spread_bps is None:
        risks.append("Execution quality is not observed; strongest urgency is capped")
    return LeanIdea(
        idea_id=idea_id,
        created_at=created.astimezone(timezone.utc).isoformat(),
        expires_at=expires.astimezone(timezone.utc).isoformat(),
        symbol=snapshot.symbol,
        canonical_asset_id=snapshot.canonical_asset_id,
        bybit_instrument=snapshot.bybit_instrument,
        horizon=_HORIZON[detection.idea_type],
        idea_type=detection.idea_type,
        directional_bias=detection.directional_bias,
        actionability_score=float(scored["actionability"]),
        confidence_score=float(scored["confidence"]),
        risk_score=float(scored["risk"]),
        urgency_score=float(scored["urgency"]),
        timing_state=detection.timing_state,
        market_phase=detection.market_phase,
        catalyst_status=catalyst_status,
        liquidity_status=features.liquidity_status,
        spread_status=(
            "unavailable"
            if snapshot.spread_bps is None
            else "extreme"
            if snapshot.spread_bps > 100
            else "wide"
            if snapshot.spread_bps > 50
            else "observed"
        ),
        data_quality=snapshot.data_quality,
        why_now=detection.why_now,
        supporting_facts=detection.supporting_facts,
        risks=tuple(risks),
        missing_information=tuple(missing),
        what_confirms=detection.what_confirms,
        what_invalidates=detection.what_invalidates,
        dashboard_route=route,
        telegram_route=route,
        source_context={
            "market_source_mode": snapshot.source_mode,
            "return_basis": snapshot.return_basis,
            "volume_signal_basis": features.volume_signal_basis,
            "baseline_status": features.baseline_status,
            "baseline_sample_count": features.baseline_sample_count,
        },
        calendar_context={},
        technical_context={
            "rsi_14": snapshot.rsi_14,
            "rsi_basis": snapshot.rsi_basis,
            "relative_btc_1h_pp": features.relative_btc_1h_pp,
            "relative_eth_1h_pp": features.relative_eth_1h_pp,
            "chase_risk_score": features.chase_risk_score,
        },
    )


def _catalyst_status(context: Mapping[str, object] | None) -> str:
    if not context:
        return "unknown"
    status = context.get("status")
    return status if status in {"known", "confirmed", "disproven"} else "unknown"


__all__ = ("build_idea",)
