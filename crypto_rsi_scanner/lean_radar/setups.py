"""Deterministic first-pass setup detection for the lean product."""

from __future__ import annotations

from .models import MarketFeatures, SetupDetection


EXTREME_SPREAD_BPS = 100.0


def detect_setup(features: MarketFeatures) -> SetupDetection | None:
    row = features.snapshot
    return_1h = row.return_1h_pp
    return_24h = row.return_24h_pp
    relative_1h = _outperformance_against_both(
        features.relative_btc_1h_pp, features.relative_eth_1h_pp
    )
    relative_24h = _outperformance_against_both(
        features.relative_btc_24h_pp, features.relative_eth_24h_pp
    )
    expanded = _volume_expanded(features)

    if features.freshness_status != "fresh":
        return _diagnostic(
            "Market snapshot is stale or has an invalid clock",
            risk="Stale data cannot support an operator idea",
        )
    if return_1h is None and return_24h is None:
        return _diagnostic(
            "Minimum return context is unavailable",
            risk="The move cannot be timed from current data",
        )
    if features.liquidity_status != "adequate" and abs(return_24h or 0.0) >= 12:
        return _diagnostic(
            "Large move is occurring with insufficient liquidity",
            risk="Low-liquidity move may be manipulation or a bad print",
        )
    if row.spread_bps is not None and row.spread_bps > EXTREME_SPREAD_BPS:
        return _diagnostic(
            "Known Bybit spread is extreme",
            risk=f"Observed spread is {row.spread_bps:.1f} bps",
        )
    if (return_24h or 0.0) <= -12:
        return SetupDetection(
            idea_type="selloff_or_risk_warning",
            directional_bias="risk",
            timing_state="active",
            market_phase="selloff",
            strength=min(100.0, abs(return_24h or 0.0) * 4.0),
            why_now=(f"Price is down {abs(return_24h or 0.0):.1f}% over 24h",),
            supporting_facts=_facts(features),
            risks=("Downside may be market-wide or continue before stabilizing",),
            what_confirms=("Downside expands with continued relative weakness",),
            what_invalidates=("Price reclaims the failed range with improving breadth",),
        )
    if (
        (abs(return_1h or 0.0) >= 5 or abs(return_24h or 0.0) >= 18)
        and expanded
    ):
        bias = "long" if (return_1h or return_24h or 0.0) > 0 else "risk"
        return SetupDetection(
            idea_type="rapid_market_anomaly",
            directional_bias=bias,
            timing_state="look_now",
            market_phase="acceleration",
            strength=min(
                100.0,
                max(abs(return_1h or 0.0) * 12, abs(return_24h or 0.0) * 4),
            ),
            why_now=("Price acceleration and unusual activity are occurring together",),
            supporting_facts=_facts(features),
            risks=("Catalyst is unknown and a rapid move can reverse abruptly",),
            what_confirms=("The move holds while volume and relative strength stay elevated",),
            what_invalidates=("Price fully retraces the acceleration range",),
        )
    if (return_24h or 0.0) >= 15 or (row.rsi_14 or 0.0) >= 80:
        return SetupDetection(
            idea_type="exhaustion_or_fade_review",
            directional_bias="short_review",
            timing_state="late",
            market_phase="extended",
            strength=min(100.0, max((return_24h or 0.0) * 4, (row.rsi_14 or 50) - 20)),
            why_now=("Momentum is extended enough to review for exhaustion",),
            supporting_facts=_facts(features),
            risks=("Strong trends can remain overextended; this is not a short instruction",),
            what_confirms=("Momentum fails and price loses the latest support shelf",),
            what_invalidates=("Price consolidates tightly and resumes with healthy volume",),
        )
    if (
        row.rsi_14 is not None
        and row.rsi_14 <= 30
        and (return_24h or 0.0) <= -6
        and (features.relative_btc_24h_pp or 0.0) > -12
    ):
        return SetupDetection(
            idea_type="pullback_or_mean_reversion",
            directional_bias="long_review",
            timing_state="forming",
            market_phase="pullback",
            strength=min(100.0, (30 - row.rsi_14) * 3 + abs(return_24h or 0.0) * 3),
            why_now=("RSI and the recent drawdown are in a reviewable pullback zone",),
            supporting_facts=_facts(features),
            risks=("Oversold conditions can persist in a true breakdown",),
            what_confirms=("Price stops making lows and reclaims short-term resistance",),
            what_invalidates=("A fresh low arrives with worsening relative strength",),
        )
    if (
        (return_1h or 0.0) >= 3
        and (return_24h or 0.0) >= 8
        and (row.rsi_14 is None or row.rsi_14 < 78)
    ):
        return SetupDetection(
            idea_type="market_breakout_long",
            directional_bias="long",
            timing_state="active",
            market_phase="breakout",
            strength=min(
                100.0,
                (return_1h or 0.0) * 10 + max(0.0, relative_24h or 0.0) * 3,
            ),
            why_now=("Multi-horizon strength is active without the exhaustion rule firing",),
            supporting_facts=_facts(features),
            risks=("Breakout may fail if volume or relative strength fades",),
            what_confirms=("Price holds above the prior range on continued participation",),
            what_invalidates=("Price closes back inside the prior range",),
        )
    if features.benchmark_status == "ready" and (
        (relative_24h or 0.0) >= 5 or (relative_1h or 0.0) >= 2
    ):
        return SetupDetection(
            idea_type="relative_strength_long",
            directional_bias="long",
            timing_state="watch_now",
            market_phase="leadership",
            strength=min(
                100.0,
                max(relative_24h or 0.0, (relative_1h or 0.0) * 2) * 8,
            ),
            why_now=("The asset is outperforming both market benchmarks",),
            supporting_facts=_facts(features),
            risks=("Relative leadership can fade if the broader market reverses",),
            what_confirms=("Relative strength persists through the next consolidation",),
            what_invalidates=("Relative performance falls back below BTC and ETH",),
        )
    if expanded or abs(return_24h or 0.0) >= 5:
        return SetupDetection(
            idea_type="dashboard_watch",
            directional_bias="neutral",
            timing_state="developing",
            market_phase="attention",
            strength=min(70.0, abs(return_24h or 0.0) * 5 + (15 if expanded else 0)),
            why_now=("Market activity is notable but not yet a stronger setup",),
            supporting_facts=_facts(features),
            risks=("Evidence is incomplete or the move is not differentiated enough",),
            what_confirms=("Volume, relative strength, or structure strengthens",),
            what_invalidates=("Activity normalizes without follow-through",),
        )
    return None


def _volume_expanded(features: MarketFeatures) -> bool:
    if features.volume_zscore is not None:
        return features.volume_zscore >= 2.0
    return (features.turnover_cross_section_zscore or 0.0) >= 1.5


def _facts(features: MarketFeatures) -> tuple[str, ...]:
    row = features.snapshot
    facts: list[str] = []
    if row.return_1h_pp is not None:
        facts.append(f"1h return {row.return_1h_pp:+.1f}%")
    if row.return_24h_pp is not None:
        facts.append(f"24h return {row.return_24h_pp:+.1f}%")
    if row.rsi_14 is not None:
        facts.append(f"Sparkline RSI {row.rsi_14:.0f}")
    if features.volume_zscore is not None:
        facts.append(f"Volume baseline z-score {features.volume_zscore:+.1f}")
    elif features.turnover_cross_section_zscore is not None:
        facts.append(
            f"Cold-baseline turnover proxy z-score {features.turnover_cross_section_zscore:+.1f}"
        )
    return tuple(facts[:4])


def _diagnostic(why: str, *, risk: str) -> SetupDetection:
    return SetupDetection(
        idea_type="diagnostic",
        directional_bias="neutral",
        timing_state="blocked",
        market_phase="unavailable",
        strength=0.0,
        why_now=(why,),
        supporting_facts=(),
        risks=(risk,),
        what_confirms=("Fresh, liquid, unit-valid market evidence becomes available",),
        what_invalidates=("The underlying data remains invalid or unavailable",),
        diagnostic_only=True,
    )


def _outperformance_against_both(
    left: float | None,
    right: float | None,
) -> float | None:
    values = [value for value in (left, right) if value is not None]
    return min(values) if len(values) == 2 else values[0] if values else None


__all__ = ("EXTREME_SPREAD_BPS", "detect_setup")
