"""Pure Crypto Radar Decision Model v2 for Event Alpha research candidates.

The model is deliberately additive.  It does not replace the historical
``opportunity_type`` or notification/watchlist routes, and it cannot send,
trade, paper trade, write normal RSI rows, or create event-fade triggers.  Its
lower-case ``radar_route`` is an operator-facing research grouping only.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from . import decision_catalyst_policy
from . import decision_policy
from .decision_market_quality import (
    _apply_market_quality_score_caps,
    _market_quality_allows_actionable,
    _market_quality_metadata,
    _market_quality_warnings,
    _quality_adjusted_urgency,
)
from .decision_safety import decision_safety_blockers
from .decision_results import build_decision_result, disabled_decision
from .rsi_technical_context import validated_rsi_score_adjustments
from .decision_models import (
    DECISION_MODEL_VERSION, CatalystStatus, ConfidenceBand, DirectionalBias, RadarDecision,
    RadarDecisionConfig, RadarResearchRoute, SpreadStatus, ThesisOrigin, TimingState,
    TradabilityStatus,
)


def evaluate_radar_decision(
    candidate: Mapping[str, Any],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    cfg: RadarDecisionConfig | None = None,
) -> RadarDecision:
    """Evaluate one integrated candidate without mutating it or causing I/O."""

    return _evaluate_radar_decision(candidate, source_rows=source_rows, cfg=cfg)


def _evaluate_radar_decision(
    candidate: Mapping[str, Any],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    cfg: RadarDecisionConfig | None = None,
) -> RadarDecision:
    """Private implementation kept separate from the stable public API."""

    cfg = cfg or RadarDecisionConfig()
    data = dict(candidate)
    sources = tuple(dict(row) for row in source_rows if isinstance(row, Mapping))
    if not cfg.enabled:
        return disabled_decision(data)

    market = decision_policy.market_snapshot(data)
    bias = decision_policy.directional_bias(data)
    rsi_actionability_delta, rsi_risk_delta, rsi_reasons = validated_rsi_score_adjustments(data)
    explicit_bias = str(data.get("directional_bias") or "").strip().casefold()
    if not explicit_bias or explicit_bias != bias:
        rsi_actionability_delta, rsi_risk_delta, rsi_reasons = 0.0, 0.0, ()
    primary_origin, origins, origin = decision_policy.thesis_origin_values(
        data,
        sources,
        rsi_context_authoritative=bool(rsi_reasons),
    )
    catalyst = decision_catalyst_policy.catalyst_status(data, sources)
    timing_profile = decision_policy.timing_profile(data, market)
    calendar_risk = decision_policy.has_calendar_risk(data)
    timing = decision_policy.timing_state_for_profile(
        timing_profile,
        scheduled=calendar_risk,
    )
    if _freshness(data, market) in {"stale", "expired", "invalid", "future"}:
        timing = TimingState.STALE.value
    missing = _missing_data(data, market)
    spread = decision_policy.spread_status(
        market,
        good_spread_bps=cfg.good_spread_bps,
        maximum_spread_bps=cfg.maximum_spread_bps,
    )
    blockers = _hard_blockers(
        data,
        market,
        sources=sources,
        origin=primary_origin,
        spread_status=spread,
        timing_profile=timing_profile,
        cfg=cfg,
    )
    tradability = _tradability_status(
        market,
        blockers,
        spread_status=spread,
        cfg=cfg,
    )
    market_led_gate = _market_led_actionability_gate(
        data,
        market,
        origin=primary_origin,
        cfg=cfg,
    )
    market_quality_gate = _market_quality_allows_actionable(market)
    urgency = _quality_adjusted_urgency(
        timing_profile.urgency_score,
        market=market,
        spread_status=spread,
    )

    (
        action_components,
        evidence_components,
        risk_components,
        penalties,
        penalty_points,
        actionability,
        evidence_confidence,
        risk,
    ) = _score_candidate(
        data=data, market=market, origin=primary_origin, catalyst=catalyst,
        timing=timing, tradability=tradability, spread=spread, missing=missing,
        blockers=blockers, cfg=cfg, rsi_actionability_delta=rsi_actionability_delta,
        rsi_risk_delta=rsi_risk_delta, rsi_reasons=rsi_reasons,
    )
    actionability, evidence_confidence, risk, penalties = _apply_market_quality_score_caps(
        market,
        actionability=actionability,
        evidence_confidence=evidence_confidence,
        risk=risk,
        action_components=action_components,
        evidence_components=evidence_components,
        risk_components=risk_components,
        penalties=penalties,
        penalty_points=penalty_points,
    )

    actionable, confidence, radar_route, route_reason = _resolve_route(
        data=data, origin=primary_origin, bias=bias, catalyst=catalyst,
        actionability=actionability, evidence_confidence=evidence_confidence,
        risk=risk, urgency=urgency, calendar_risk=calendar_risk,
        market_led_gate=market_led_gate, market_quality_gate=market_quality_gate,
        tradability=tradability, spread=spread, blockers=blockers, origins=origins,
        cfg=cfg,
    )
    warnings = decision_policy.decision_warnings(
        data,
        catalyst=catalyst,
        tradability=tradability,
        spread_status_value=spread,
        blockers=blockers,
        risk_components=risk_components,
    )
    attribution_warning = decision_catalyst_policy.attribution_warning(data, sources)
    if attribution_warning:
        warnings = tuple(dict.fromkeys((*warnings, attribution_warning)))
    if rsi_reasons:
        warnings = tuple(dict.fromkeys((*warnings, (
            "Validated RSI technical context adjusted research scores: "
            f"actionability={rsi_actionability_delta:+.2f}; risk={rsi_risk_delta:+.2f}."
        ))))
    quality_warnings = _market_quality_warnings(market, spread_status=spread)
    if quality_warnings:
        warnings = tuple(dict.fromkeys((*warnings, *quality_warnings)))
    why_review, confirms, invalidates = decision_policy.review_copy(
        data,
        origin=primary_origin,
        bias=bias,
        catalyst=catalyst,
        timing=timing,
        radar_route=radar_route,
        blockers=blockers,
    )
    return build_decision_result(
        origin=origin, primary_origin=primary_origin, origins=origins, bias=bias,
        catalyst=catalyst, confidence=confidence,
        timing=timing, tradability=tradability, spread=spread, radar_route=radar_route,
        route_reason=route_reason, actionable=actionable, actionability=actionability,
        evidence_confidence=evidence_confidence, risk=risk,
        urgency=urgency, market_phase=timing_profile.market_phase,
        preferred_horizon=timing_profile.preferred_horizon,
        expires_at=timing_profile.expires_at, chase_risk=timing_profile.chase_risk_score,
        action_components=action_components, evidence_components=evidence_components,
        risk_components=risk_components, penalty_points=penalty_points,
        blockers=blockers, penalties=penalties, missing=missing, warnings=warnings,
        why_review=why_review, confirms=confirms,
        invalidates=invalidates,
    )


def _score_candidate(
    *,
    data: Mapping[str, Any], market: Mapping[str, Any], origin: str,
    catalyst: str, timing: str, tradability: str, spread: str,
    missing: tuple[str, ...], blockers: tuple[str, ...], cfg: RadarDecisionConfig,
    rsi_actionability_delta: float, rsi_risk_delta: float,
    rsi_reasons: tuple[str, ...],
) -> tuple[
    dict[str, float], dict[str, float], dict[str, float], tuple[str, ...],
    dict[str, float], float, float, float,
]:
    action_components = _actionability_components(
        data, market, catalyst=catalyst, timing=timing, cfg=cfg,
    )
    evidence_components = _evidence_components(data, market, catalyst=catalyst)
    risk_components = _risk_components(
        data, market, catalyst=catalyst, timing=timing, missing=missing,
        blockers=blockers, cfg=cfg,
    )
    penalties, penalty_points = _soft_penalties(
        data, market, origin=origin, catalyst=catalyst, timing=timing,
        tradability=tradability, spread_status=spread, missing=missing, cfg=cfg,
    )
    actionability, evidence_confidence, risk = _aggregate_scores(
        action_components=action_components, evidence_components=evidence_components,
        risk_components=risk_components, penalty_points=penalty_points,
        origin=origin, blockers=blockers,
    )
    actionability, risk = decision_policy.apply_validated_rsi_adjustments(
        actionability=actionability, risk=risk,
        actionability_delta=rsi_actionability_delta, risk_delta=rsi_risk_delta,
        reasons=rsi_reasons, action_components=action_components,
        risk_components=risk_components, penalty_points=penalty_points,
        blockers=blockers,
    )
    return (
        action_components, evidence_components, risk_components, penalties,
        penalty_points, actionability, evidence_confidence, risk,
    )


def _resolve_route(
    *,
    data: Mapping[str, Any], origin: str, bias: str, catalyst: str,
    actionability: float, evidence_confidence: float, risk: float, urgency: float,
    calendar_risk: bool, market_led_gate: bool, market_quality_gate: bool,
    tradability: str, spread: str, blockers: tuple[str, ...], origins: tuple[str, ...],
    cfg: RadarDecisionConfig,
) -> tuple[bool, str, str, str]:
    lane_enabled = cfg.market_led_enabled if decision_policy.uses_market_lane(origin) else cfg.catalyst_led_enabled
    actionable = bool(
        lane_enabled
        and not blockers
        and market_led_gate
        and market_quality_gate
        and tradability in {TradabilityStatus.GOOD.value, TradabilityStatus.ACCEPTABLE.value}
        and spread in {SpreadStatus.VERIFIED_GOOD.value, SpreadStatus.VERIFIED_ACCEPTABLE.value}
        and actionability >= cfg.actionability_threshold
    )
    confidence = _confidence_band(
        actionability, evidence_confidence, risk, catalyst=catalyst,
        actionable=actionable, blockers=blockers, cfg=cfg,
    )
    radar_route, route_reason = _radar_route(
        data, origin=origin, bias=bias, catalyst=catalyst, confidence=confidence,
        actionability=actionability, urgency=urgency, calendar_risk=calendar_risk,
        actionable=actionable, blockers=blockers, origins=origins,
        market_quality_gate=market_quality_gate, cfg=cfg,
    )
    if radar_route in {
        RadarResearchRoute.DASHBOARD_WATCH.value,
        RadarResearchRoute.RISK_WATCH.value,
        RadarResearchRoute.CALENDAR_RISK.value,
        RadarResearchRoute.DIAGNOSTIC.value,
    }:
        actionable = False
        confidence = _confidence_band(
            actionability, evidence_confidence, risk, catalyst=catalyst,
            actionable=False, blockers=blockers, cfg=cfg,
        )
    return actionable, confidence, radar_route, route_reason


def reevaluate_radar_decision_fields(
    candidate: Mapping[str, Any],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    cfg: RadarDecisionConfig | None = None,
) -> dict[str, Any]:
    """Return a fresh v2 projection after final identity/quality mutations."""

    return evaluate_radar_decision(candidate, source_rows=source_rows, cfg=cfg).to_dict()


def _aggregate_scores(
    *,
    action_components: Mapping[str, float],
    evidence_components: Mapping[str, float],
    risk_components: Mapping[str, float],
    penalty_points: Mapping[str, float],
    origin: str,
    blockers: tuple[str, ...],
) -> tuple[float, float, float]:
    actionability = decision_policy.weighted_actionability(
        action_components,
        origin=origin,
    ) - sum(penalty_points.values())
    if blockers:
        actionability = min(actionability, 20.0)
    evidence_confidence = _weighted_score(
        evidence_components,
        {
            "source_authority": 0.30,
            "source_specificity": 0.20,
            "catalyst_clarity": 0.25,
            "asset_identity": 0.15,
            "market_data_quality": 0.10,
        },
    )
    risk = _weighted_score(
        risk_components,
        {
            "manipulation_risk": 0.30,
            "staleness_risk": 0.20,
            "extension_risk": 0.15,
            "catalyst_uncertainty_risk": 0.15,
            "crowding_risk": 0.10,
            "data_gap_risk": 0.10,
        },
    )
    risk += float(risk_components.get("calendar_risk_adjustment") or 0.0)
    if blockers:
        risk = max(risk, 85.0)
    return _clamp(actionability), evidence_confidence, _clamp(risk)


def _hard_blockers(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    sources: tuple[Mapping[str, Any], ...],
    origin: str,
    spread_status: str,
    timing_profile: decision_policy.TimingProfile,
    cfg: RadarDecisionConfig,
) -> tuple[str, ...]:
    blockers = list(decision_safety_blockers(data, sources))
    symbol = str(data.get("symbol") or data.get("validated_symbol") or "").strip().upper()
    canonical = str(data.get("canonical_asset_id") or data.get("coin_id") or "").strip().casefold()
    resolver = str(data.get("instrument_resolver_status") or "").strip().casefold()
    if not symbol or symbol == "UNKNOWN" or not canonical or canonical == "unknown":
        blockers.append("canonical_asset_identity_missing")
    if resolver.startswith("unresolved"):
        blockers.append("canonical_asset_identity_unresolved")
    if resolver != "resolved" or data.get("instrument_identity_trusted") is not True:
        blockers.append("canonical_asset_identity_untrusted")
    if data.get("is_tradable_asset") is False:
        blockers.append("asset_not_tradable")
    if bool(data.get("is_theme_or_sector")) or symbol == "SECTOR":
        blockers.append("theme_or_sector_control")
    if bool(data.get("is_quote_asset")) or bool(data.get("quote_asset_excluded")):
        blockers.append("quote_asset_control")
    if _is_source_noise_or_control(data):
        blockers.append("source_noise_or_control")

    freshness = _freshness(data, market)
    run_mode = str(data.get("run_mode") or "").casefold()
    if freshness in {"stale", "expired", "invalid", "future"} or (
        freshness == "fixture_allowed_stale" and run_mode not in {"fixture", "test", "replay"}
    ):
        blockers.append("market_data_stale")
    elif decision_policy.uses_market_lane(origin) and freshness not in {
        "fresh",
        "fixture_allowed_stale",
    }:
        blockers.append("market_data_freshness_unverified")

    return_unit = str(market.get("return_unit") or "").strip().casefold()
    unit_warnings = _texts(market.get("unit_warnings"))
    has_return_values = any(
        _first_number(market, field) is not None
        for field in (
            "return_1h", "return_4h", "return_24h", "return_7d",
            "relative_return_vs_btc", "relative_return_vs_btc_4h",
            "relative_return_vs_btc_24h",
        )
    )
    if has_return_values and not return_unit:
        blockers.append("market_return_unit_missing")
    elif return_unit and return_unit not in {"percent_points", "percentage_points"}:
        blockers.append("invalid_market_return_unit")
    if any(item.startswith("return_unit_missing:") for item in unit_warnings):
        blockers.append("market_return_unit_missing")
    if unit_warnings:
        blockers.append("invalid_market_return_units")
    if timing_profile.expiry_invalid:
        blockers.append("idea_expiry_invalid")
    if timing_profile.expired:
        blockers.append("idea_expired")

    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    if liquidity is not None and liquidity < cfg.minimum_liquidity_usd:
        blockers.append("liquidity_below_minimum")
    if spread_status == SpreadStatus.VERIFIED_WIDE.value:
        blockers.append("spread_above_maximum")
    if decision_policy.is_suspicious_illiquid(data):
        blockers.append("suspicious_illiquid_move")
    if _is_duplicate(data):
        blockers.append("duplicate_family_suppressed")
    return tuple(dict.fromkeys(blockers))


def _tradability_status(
    market: Mapping[str, Any],
    blockers: tuple[str, ...],
    *,
    spread_status: str,
    cfg: RadarDecisionConfig,
) -> str:
    if blockers:
        return TradabilityStatus.BLOCKED.value
    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    if liquidity is None:
        return TradabilityStatus.POOR.value
    if liquidity < cfg.minimum_liquidity_usd:
        return TradabilityStatus.POOR.value
    if spread_status == SpreadStatus.VERIFIED_GOOD.value and liquidity >= cfg.good_liquidity_usd:
        return TradabilityStatus.GOOD.value
    if spread_status in {
        SpreadStatus.VERIFIED_GOOD.value,
        SpreadStatus.VERIFIED_ACCEPTABLE.value,
        SpreadStatus.UNAVAILABLE.value,
        SpreadStatus.STALE.value,
    }:
        return TradabilityStatus.ACCEPTABLE.value
    return TradabilityStatus.POOR.value


def _market_led_actionability_gate(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    origin: str,
    cfg: RadarDecisionConfig,
) -> bool:
    """Require the prompt's observable market-led evidence before promotion."""

    if origin != ThesisOrigin.MARKET_LED.value:
        return True
    freshness = _freshness(data, market)
    if freshness not in {"fresh", "fixture_allowed_stale"}:
        return False
    volume_z = _first_number(
        market,
        "volume_zscore_24h",
        "volume_turnover_zscore",
        "turnover_zscore",
    )
    volume_mcap = _first_number(
        market,
        "volume_to_market_cap",
        "volume_mcap",
        "volume_mcap_ratio",
    )
    meaningful_volume = bool(
        (volume_z is not None and volume_z >= cfg.minimum_volume_zscore)
        or (
            volume_mcap is not None
            and volume_mcap >= cfg.minimum_volume_to_market_cap
        )
    )
    state = _market_label(data)
    relative = _first_number(
        market,
        "relative_return_vs_btc_4h",
        "relative_return_vs_btc",
        "relative_return_vs_btc_24h",
    )
    strong_relative_or_structure = bool(
        state
        in {
            "high_liquidity_breakout",
            "confirmed_breakout",
            "stealth_accumulation",
        }
        or (relative is not None and abs(relative) >= 3.0)
    )
    return meaningful_volume and strong_relative_or_structure


def _actionability_components(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    catalyst: str,
    timing: str,
    cfg: RadarDecisionConfig,
) -> dict[str, float]:
    state = _market_label(data)
    market_strength = {
        "high_liquidity_breakout": 94.0,
        "confirmed_breakout": 92.0,
        "stealth_accumulation": 86.0,
        "late_momentum_needs_crowding_check": 76.0,
        "late_momentum": 74.0,
        "blowoff_crowded": 72.0,
        "post_event_fade_setup": 78.0,
        "selloff_risk": 72.0,
        "risk_off_sell_pressure": 70.0,
        "no_reaction": 38.0,
    }.get(state, 50.0)
    volume_z = _first_number(market, "volume_zscore_24h", "volume_turnover_zscore", "turnover_zscore")
    volume_mcap = _first_number(market, "volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")
    volume = 25.0
    if volume_z is not None:
        volume = max(volume, min(100.0, 40.0 + volume_z * 16.0))
    if volume_mcap is not None:
        volume = max(volume, min(100.0, 35.0 + volume_mcap * 180.0))
    relative = _first_number(
        market,
        "relative_return_vs_btc_4h",
        "relative_return_vs_btc",
        "relative_return_vs_btc_24h",
    )
    relative_score = 40.0 if relative is None else _clamp(50.0 + relative * 3.0)
    liquidity_score = _liquidity_score(market, cfg=cfg)
    timing_score = {
        TimingState.EARLY.value: 88.0,
        TimingState.ACTIVE.value: 90.0,
        TimingState.EXTENDED.value: 58.0,
        TimingState.EXHAUSTED.value: 48.0,
        TimingState.SCHEDULED.value: 82.0,
        TimingState.STALE.value: 0.0,
    }[timing]
    canonical = str(data.get("canonical_asset_id") or data.get("coin_id") or "").strip()
    resolver = _number(data.get("instrument_resolver_confidence"))
    identity_score = _clamp((resolver * 100.0) if resolver is not None and resolver <= 1 else (resolver or (88.0 if canonical else 0.0)))
    catalyst_score = {
        CatalystStatus.CONFIRMED.value: 96.0,
        CatalystStatus.PLAUSIBLE.value: 70.0,
        CatalystStatus.UNKNOWN.value: 42.0,
        CatalystStatus.NOT_REQUIRED.value: 60.0,
        CatalystStatus.DISPROVEN.value: 5.0,
    }[catalyst]
    derivatives_score = _derivatives_score(data)
    return {
        "market_strength": market_strength,
        "volume_confirmation": volume,
        "relative_strength": relative_score,
        "liquidity_tradability": liquidity_score,
        "timing_freshness": timing_score,
        "asset_identity": identity_score,
        "catalyst_evidence": catalyst_score,
        "derivatives_confirmation": derivatives_score,
    }


def _evidence_components(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    catalyst: str,
) -> dict[str, float]:
    source_strength = str(data.get("source_strength") or "").casefold()
    source_class = str(data.get("source_class") or "").casefold()
    authority = {
        "official_structured": 96.0,
        "strong": 84.0,
        "medium": 68.0,
        "tagged_context": 55.0,
        "weak": 38.0,
    }.get(source_strength, 94.0 if source_class.startswith("official") else 32.0)
    source_url, source_title = _catalyst_source_fields(data)
    if not source_url:
        authority = min(authority, 62.0)
    accepted = _number(data.get("accepted_evidence_count")) or 0.0
    specificity = 92.0 if catalyst == CatalystStatus.CONFIRMED.value else 72.0 if accepted > 0 else 42.0
    if not source_title:
        specificity = min(specificity, 58.0)
    catalyst_clarity = {
        CatalystStatus.CONFIRMED.value: 96.0,
        CatalystStatus.PLAUSIBLE.value: 72.0,
        CatalystStatus.UNKNOWN.value: 35.0,
        CatalystStatus.NOT_REQUIRED.value: 62.0,
        CatalystStatus.DISPROVEN.value: 0.0,
    }[catalyst]
    canonical = str(data.get("canonical_asset_id") or data.get("coin_id") or "").strip()
    resolver = _number(data.get("instrument_resolver_confidence"))
    identity = _clamp((resolver * 100.0) if resolver is not None and resolver <= 1 else (resolver or (88.0 if canonical else 0.0)))
    observed = sum(
        _first_number(market, *keys) is not None
        for keys in (
            ("return_4h",),
            ("return_24h",),
            ("volume_zscore_24h", "volume_turnover_zscore"),
            ("liquidity_usd",),
            ("spread_bps",),
        )
    )
    freshness = _freshness(data, market)
    market_quality = min(100.0, 35.0 + observed * 11.0)
    if freshness in {"fresh", "fixture_allowed_stale"}:
        market_quality = min(100.0, market_quality + 10.0)
    elif freshness in {"stale", "expired", "invalid", "future"}:
        market_quality = min(market_quality, 10.0)
    return {
        "source_authority": authority,
        "source_specificity": specificity,
        "catalyst_clarity": catalyst_clarity,
        "asset_identity": identity,
        "market_data_quality": market_quality,
    }


def _risk_components(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    catalyst: str,
    timing: str,
    missing: tuple[str, ...],
    blockers: tuple[str, ...],
    cfg: RadarDecisionConfig,
) -> dict[str, float]:
    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    spread = _first_number(market, "spread_bps", "bid_ask_spread_bps")
    manipulation = 20.0
    if liquidity is None:
        manipulation = max(manipulation, 55.0)
    elif liquidity < cfg.good_liquidity_usd:
        manipulation = max(manipulation, 42.0)
    if spread is None:
        manipulation = max(manipulation, 35.0)
    elif spread > cfg.good_spread_bps:
        manipulation = max(manipulation, min(100.0, 35.0 + spread / 2.0))
    if decision_policy.is_suspicious_illiquid(data):
        manipulation = 100.0
    freshness = _freshness(data, market)
    staleness = 10.0 if freshness in {"fresh", "fixture_allowed_stale"} else 45.0 if not freshness or freshness == "unknown" else 100.0
    extension = {
        TimingState.EARLY.value: 15.0,
        TimingState.ACTIVE.value: 25.0,
        TimingState.EXTENDED.value: 75.0,
        TimingState.EXHAUSTED.value: 90.0,
        TimingState.SCHEDULED.value: 25.0,
        TimingState.STALE.value: 100.0,
    }[timing]
    catalyst_risk = {
        CatalystStatus.CONFIRMED.value: 10.0,
        CatalystStatus.PLAUSIBLE.value: 35.0,
        CatalystStatus.UNKNOWN.value: 65.0,
        CatalystStatus.NOT_REQUIRED.value: 25.0,
        CatalystStatus.DISPROVEN.value: 100.0,
    }[catalyst]
    crowding = 75.0 if _has_crowding(data) else 25.0
    data_gap = min(100.0, len(missing) * 14.0)
    if blockers:
        data_gap = max(data_gap, 80.0)
    calendar_adjustment = _number(data.get("calendar_risk_score_adjustment")) or 0.0
    calendar_adjustment = max(0.0, min(25.0, calendar_adjustment))
    return {
        "manipulation_risk": manipulation,
        "staleness_risk": staleness,
        "extension_risk": extension,
        "catalyst_uncertainty_risk": catalyst_risk,
        "crowding_risk": crowding,
        "data_gap_risk": data_gap,
        "calendar_risk_adjustment": calendar_adjustment,
    }


def _soft_penalties(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    origin: str,
    catalyst: str,
    timing: str,
    tradability: str,
    spread_status: str,
    missing: tuple[str, ...],
    cfg: RadarDecisionConfig,
) -> tuple[tuple[str, ...], dict[str, float]]:
    penalties: list[str] = []
    points: dict[str, float] = {}
    if catalyst == CatalystStatus.UNKNOWN.value:
        penalties.append("catalyst_unknown_soft_penalty")
        points["catalyst_unknown"] = 6.0 if origin == ThesisOrigin.MARKET_LED.value else 12.0
    elif catalyst == CatalystStatus.DISPROVEN.value:
        penalties.append("catalyst_disproven_penalty")
        points["catalyst_disproven"] = 30.0
    if catalyst in {CatalystStatus.CONFIRMED.value, CatalystStatus.PLAUSIBLE.value}:
        if "catalyst_source_url" in missing:
            penalties.append("official_source_url_missing")
            points["official_source_url_missing"] = 10.0
        if "catalyst_source_title" in missing:
            penalties.append("catalyst_article_title_missing")
            points["catalyst_article_title_missing"] = 6.0
    if tradability == TradabilityStatus.POOR.value:
        penalties.append("tradability_data_or_depth_insufficient")
        points["tradability_poor"] = 15.0
    if spread_status == SpreadStatus.UNAVAILABLE.value:
        penalties.append("spread_unavailable_dashboard_only")
        points["spread_unavailable"] = 8.0
    elif spread_status == SpreadStatus.STALE.value:
        penalties.append("spread_stale_dashboard_only")
        points["spread_stale"] = 10.0
    volume_z = _first_number(market, "volume_zscore_24h", "volume_turnover_zscore", "turnover_zscore")
    volume_mcap = _first_number(market, "volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")
    if volume_z is None and volume_mcap is None:
        penalties.append("market_turnover_unverified")
        points["market_turnover_unverified"] = 18.0
    elif not (
        (volume_z is not None and volume_z >= cfg.minimum_volume_zscore)
        or (volume_mcap is not None and volume_mcap >= cfg.minimum_volume_to_market_cap)
    ):
        penalties.append("market_turnover_weak")
        points["market_turnover_weak"] = 12.0
    if origin == ThesisOrigin.MARKET_LED.value and not _market_led_actionability_gate(
        data,
        market,
        origin=origin,
        cfg=cfg,
    ):
        penalties.append("market_led_confirmation_gate_incomplete")
        points["market_led_confirmation_incomplete"] = 12.0
    if timing == TimingState.EXTENDED.value:
        penalties.append("move_extended")
        points["move_extended"] = 8.0
    elif timing == TimingState.EXHAUSTED.value:
        penalties.append("move_exhausted")
        points["move_exhausted"] = 10.0
    if _derivatives_score(data) <= 30.0 and decision_policy.directional_bias(data) == DirectionalBias.FADE_SHORT_REVIEW.value:
        penalties.append("derivatives_confirmation_missing_for_fade_review")
        points["fade_derivatives_missing"] = 8.0
    return tuple(dict.fromkeys(penalties)), points


def _confidence_band(
    actionability: float,
    evidence: float,
    risk: float,
    *,
    catalyst: str,
    actionable: bool,
    blockers: tuple[str, ...],
    cfg: RadarDecisionConfig,
) -> str:
    if blockers:
        return ConfidenceBand.DIAGNOSTIC.value
    if (
        actionable
        and evidence >= cfg.high_confidence_evidence_threshold
        and risk <= 45
        and actionability >= cfg.high_confidence_threshold
    ):
        return ConfidenceBand.HIGH_CONFIDENCE.value
    if actionable:
        return ConfidenceBand.ACTIONABLE.value
    if actionability >= 45:
        return ConfidenceBand.EXPLORATORY.value
    return ConfidenceBand.DIAGNOSTIC.value


def _radar_route(
    data: Mapping[str, Any],
    *,
    origin: str,
    bias: str,
    catalyst: str,
    confidence: str,
    actionability: float,
    urgency: float,
    calendar_risk: bool,
    actionable: bool,
    blockers: tuple[str, ...],
    origins: tuple[str, ...],
    market_quality_gate: bool,
    cfg: RadarDecisionConfig,
) -> tuple[str, str]:
    if blockers:
        return RadarResearchRoute.DIAGNOSTIC.value, "hard_gate_blocked_research_promotion"
    if decision_policy.uses_market_lane(origin) and not cfg.market_led_enabled:
        return RadarResearchRoute.DIAGNOSTIC.value, "market_led_route_disabled"
    if not decision_policy.uses_market_lane(origin) and not cfg.catalyst_led_enabled:
        return RadarResearchRoute.DIAGNOSTIC.value, "catalyst_led_route_disabled"
    if calendar_risk:
        return decision_policy.configured_route(
            RadarResearchRoute.CALENDAR_RISK.value,
            "attached_calendar_or_scheduled_risk_research",
            enabled=cfg.calendar_risk_route_enabled,
        )
    if bias == DirectionalBias.RISK.value:
        return decision_policy.configured_route(
            RadarResearchRoute.RISK_WATCH.value,
            "unscheduled_downside_risk_research",
            enabled=cfg.risk_watch_route_enabled,
        )
    if bias == DirectionalBias.FADE_SHORT_REVIEW.value:
        if _has_crowding(data):
            return decision_policy.configured_route(
                RadarResearchRoute.FADE_EXHAUSTION_REVIEW.value,
                "extended_move_with_crowding_evidence",
                enabled=cfg.fade_exhaustion_route_enabled,
            )
        if (
            actionable
            and actionability >= cfg.rapid_anomaly_actionability_threshold
            and urgency >= cfg.rapid_anomaly_urgency_threshold
        ):
            return decision_policy.configured_route(
                RadarResearchRoute.RAPID_MARKET_ANOMALY.value,
                "late_move_needs_rapid_crowding_review",
                enabled=cfg.rapid_anomaly_route_enabled,
            )
        if actionability >= cfg.dashboard_watch_threshold:
            return decision_policy.configured_route(
                RadarResearchRoute.DASHBOARD_WATCH.value,
                "late_move_below_rapid_research_gate",
                enabled=cfg.dashboard_watch_route_enabled,
            )
        return RadarResearchRoute.DIAGNOSTIC.value, "below_dashboard_watch_threshold"
    if not actionable:
        if actionability >= cfg.dashboard_watch_threshold:
            if not market_quality_gate:
                return decision_policy.configured_route(
                    RadarResearchRoute.DASHBOARD_WATCH.value,
                    "market_data_quality_limited_to_dashboard",
                    enabled=cfg.dashboard_watch_route_enabled,
                )
            return decision_policy.configured_route(
                RadarResearchRoute.DASHBOARD_WATCH.value,
                "useful_research_below_actionable_push_gate",
                enabled=cfg.dashboard_watch_route_enabled,
            )
        return RadarResearchRoute.DIAGNOSTIC.value, "below_dashboard_watch_threshold"
    if (
        confidence == ConfidenceBand.HIGH_CONFIDENCE.value
        and catalyst == CatalystStatus.CONFIRMED.value
        and any(
            contributor in {
                ThesisOrigin.CATALYST_LED.value,
                ThesisOrigin.FUNDAMENTAL_LED.value,
            }
            for contributor in origins
        )
    ):
        return decision_policy.configured_route(
            RadarResearchRoute.HIGH_CONFIDENCE_WATCH.value,
            "confirmed_catalyst_and_high_confidence_scores",
            enabled=cfg.high_confidence_route_enabled,
        )
    state = _market_label(data)
    if state in {"confirmed_breakout", "high_liquidity_breakout", "stealth_accumulation"}:
        return decision_policy.configured_route(
            RadarResearchRoute.ACTIONABLE_WATCH.value,
            "fresh_market_led_long_research",
            enabled=cfg.actionable_watch_route_enabled,
        )
    return decision_policy.configured_route(
        RadarResearchRoute.ACTIONABLE_WATCH.value,
        "configured_research_actionability_gate_passed",
        enabled=cfg.actionable_watch_route_enabled,
    )


def _missing_data(data: Mapping[str, Any], market: Mapping[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    checks = {
        "market_return_4h": _first_number(market, "return_4h"),
        "market_return_24h": _first_number(market, "return_24h"),
        "volume_anomaly": _first_number(market, "volume_zscore_24h", "volume_turnover_zscore", "turnover_zscore"),
        "liquidity_usd": _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd"),
        "spread_bps": _first_number(market, "spread_bps", "bid_ask_spread_bps"),
        "market_freshness": _freshness(data, market) or None,
        "derivatives_confirmation": data.get("derivatives_state_snapshot") or data.get("derivatives_snapshot"),
    }
    for name, value in checks.items():
        if value in (None, "", [], {}, ()):
            missing.append(name)
    source_url, source_title = _catalyst_source_fields(data)
    if not source_url:
        missing.append("catalyst_source_url")
    if not source_title:
        missing.append("catalyst_source_title")
    return tuple(dict.fromkeys(missing))


def _catalyst_source_fields(data: Mapping[str, Any]) -> tuple[str, str]:
    url = str(data.get("latest_source_url") or "").strip()
    title = str(data.get("latest_source_title") or data.get("event_name") or "").strip()
    for field in ("official_exchange_event", "scheduled_catalyst_event", "unlock_event"):
        nested = data.get(field)
        if not isinstance(nested, Mapping):
            continue
        url = url or str(nested.get("source_url") or nested.get("url") or "").strip()
        title = title or str(nested.get("title") or nested.get("event_name") or "").strip()
    return url, title


def _market_label(data: Mapping[str, Any]) -> str:
    for key in ("market_anomaly_bucket", "anomaly_bucket", "market_anomaly_type", "anomaly_type", "market_state_class", "market_state"):
        value = str(data.get(key) or "").strip().casefold()
        if value:
            return value
    return ""


def _specific_market_label(data: Mapping[str, Any]) -> str:
    for key in ("anomaly_type", "market_anomaly_type", "market_state_class", "market_state"):
        value = str(data.get(key) or "").strip().casefold()
        if value:
            return value
    return ""


def _freshness(data: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    for value in (
        data.get("integrated_market_freshness_status"),
        data.get("market_context_freshness_status"),
        market.get("market_context_freshness_status"),
        market.get("freshness_status"),
    ):
        text = str(value or "").strip().casefold()
        if text:
            return text
    return ""


def _liquidity_score(market: Mapping[str, Any], *, cfg: RadarDecisionConfig) -> float:
    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    spread = _first_number(market, "spread_bps", "bid_ask_spread_bps")
    if liquidity is None:
        return 25.0
    if liquidity < cfg.minimum_liquidity_usd:
        score = 5.0
    elif liquidity >= cfg.good_liquidity_usd:
        score = 92.0
    else:
        span = max(1.0, cfg.good_liquidity_usd - cfg.minimum_liquidity_usd)
        score = 62.0 + 25.0 * (liquidity - cfg.minimum_liquidity_usd) / span
    if spread is None:
        return max(0.0, score - 8.0)
    if spread > cfg.maximum_spread_bps:
        return min(score, 5.0)
    if spread > cfg.good_spread_bps:
        score -= min(25.0, (spread - cfg.good_spread_bps) / 5.0)
    return _clamp(score)


def _derivatives_score(data: Mapping[str, Any]) -> float:
    snapshot = data.get("derivatives_state_snapshot") or data.get("derivatives_snapshot")
    if not isinstance(snapshot, Mapping):
        return 30.0
    freshness = str(
        data.get("coinalyze_freshness_status")
        or snapshot.get("derivatives_snapshot_freshness_status")
        or snapshot.get("freshness_status")
        or ""
    ).casefold()
    score = 78.0 if freshness in {"fresh", "fixture_allowed_stale"} else 48.0
    if _has_crowding(data):
        score = max(score, 85.0)
    return score


def _has_crowding(data: Mapping[str, Any]) -> bool:
    if str(data.get("crowding_class") or "").casefold() in {"moderate", "high", "extreme"}:
        return True
    if _texts(data.get("crowding_exhaustion_evidence")):
        return True
    snapshot = data.get("derivatives_state_snapshot") or data.get("derivatives_snapshot")
    if not isinstance(snapshot, Mapping):
        return False
    oi = _first_number(snapshot, "open_interest_delta_4h", "open_interest_delta_24h", "open_interest_delta")
    funding_z = _first_number(snapshot, "funding_zscore", "funding_rate_zscore")
    return bool((oi is not None and abs(oi) >= 25) or (funding_z is not None and abs(funding_z) >= 2))


def _is_source_noise_or_control(data: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(data.get(key) or "")
        for key in (
            "opportunity_type",
            "candidate_role",
            "impact_path_type",
            "playbook_type",
            "effective_playbook_type",
            "diagnostics_reason",
        )
    ).casefold()
    return any(
        term in text
        for term in (
            "source_noise",
            "ambiguous_control",
            "theme_or_sector",
            "quote_asset",
        )
    )


def _is_duplicate(data: Mapping[str, Any]) -> bool:
    route = str(data.get("final_route_after_quality_gate") or data.get("route") or "").upper()
    return bool(
        data.get("duplicate_suppressed")
        or data.get("is_duplicate")
        or data.get("suppressed_duplicate")
        or route == "SUPPRESS_DUPLICATE"
    )


def _weighted_score(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return 0.0
    return _clamp(sum(float(values.get(key, 0.0)) * weight for key, weight in weights.items()) / total_weight)


def _first_number(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in row or row.get(key) in (None, ""):
            continue
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _texts(value: object) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(key) for key, enabled in value.items() if enabled]
    try:
        return [str(item) for item in value if str(item or "")]  # type: ignore[union-attr]
    except TypeError:
        return [str(value)]


def _rounded_map(values: Mapping[str, float]) -> dict[str, float]:
    return {key: round(float(value), 2) for key, value in values.items()}


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


__all__ = (
    "DECISION_MODEL_VERSION", "CatalystStatus", "ConfidenceBand", "DirectionalBias",
    "RadarDecision", "RadarDecisionConfig", "RadarResearchRoute", "SpreadStatus",
    "ThesisOrigin", "TimingState", "TradabilityStatus", "evaluate_radar_decision",
    "reevaluate_radar_decision_fields",
)
