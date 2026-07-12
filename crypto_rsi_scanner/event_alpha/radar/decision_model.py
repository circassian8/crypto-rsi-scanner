"""Pure Crypto Radar Decision Model v2 for Event Alpha research candidates.

The model is deliberately additive.  It does not replace the historical
``opportunity_type`` or notification/watchlist routes, and it cannot send,
trade, paper trade, write normal RSI rows, or create event-fade triggers.  Its
lower-case ``radar_route`` is an operator-facing research grouping only.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .decision_safety import has_unredacted_secret, has_unsafe_operator_path, has_unsafe_side_effect
from .decision_results import build_decision_result, disabled_decision
from .decision_models import (
    DECISION_MODEL_VERSION, CatalystStatus, ConfidenceBand, DirectionalBias, RadarDecision,
    RadarDecisionConfig, RadarResearchRoute, ThesisOrigin, TimingState, TradabilityStatus,
    actionability_score_cohort,
)


def evaluate_radar_decision(
    candidate: Mapping[str, Any],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    cfg: RadarDecisionConfig | None = None,
) -> RadarDecision:
    """Evaluate one integrated candidate without mutating it or causing I/O."""

    cfg = cfg or RadarDecisionConfig()
    data = dict(candidate)
    sources = tuple(dict(row) for row in source_rows if isinstance(row, Mapping))
    if not cfg.enabled:
        return disabled_decision(data)

    market = _market_snapshot(data)
    origin = _thesis_origin(data, sources)
    catalyst = _catalyst_status(data, sources)
    bias = _directional_bias(data)
    timing = _timing_state(data, market)
    missing = _missing_data(data, market)
    blockers = _hard_blockers(data, market, sources=sources, origin=origin, cfg=cfg)
    tradability = _tradability_status(market, blockers, cfg=cfg)
    market_led_gate = _market_led_actionability_gate(
        data,
        market,
        origin=origin,
        cfg=cfg,
    )

    action_components = _actionability_components(
        data,
        market,
        catalyst=catalyst,
        timing=timing,
        cfg=cfg,
    )
    evidence_components = _evidence_components(data, market, catalyst=catalyst)
    risk_components = _risk_components(
        data,
        market,
        catalyst=catalyst,
        timing=timing,
        missing=missing,
        blockers=blockers,
        cfg=cfg,
    )
    penalties, penalty_points = _soft_penalties(
        data,
        market,
        origin=origin,
        catalyst=catalyst,
        timing=timing,
        tradability=tradability,
        missing=missing,
        cfg=cfg,
    )
    actionability, evidence_confidence, risk = _aggregate_scores(
        action_components=action_components,
        evidence_components=evidence_components,
        risk_components=risk_components,
        penalty_points=penalty_points,
        origin=origin,
        blockers=blockers,
    )

    lane_enabled = (
        cfg.market_led_enabled
        if origin in {ThesisOrigin.MARKET_LED.value, ThesisOrigin.TECHNICAL_LED.value}
        else cfg.catalyst_led_enabled
    )
    actionable = bool(
        lane_enabled
        and not blockers
        and market_led_gate
        and tradability in {TradabilityStatus.GOOD.value, TradabilityStatus.ACCEPTABLE.value}
        and actionability >= cfg.actionability_threshold
    )
    confidence = _confidence_band(
        actionability,
        evidence_confidence,
        risk,
        catalyst=catalyst,
        actionable=actionable,
        blockers=blockers,
        cfg=cfg,
    )
    radar_route, route_reason = _radar_route(
        data,
        origin=origin,
        bias=bias,
        catalyst=catalyst,
        confidence=confidence,
        timing=timing,
        actionable=actionable,
        blockers=blockers,
        cfg=cfg,
    )
    if radar_route == RadarResearchRoute.DIAGNOSTIC.value and route_reason.endswith("_route_disabled"):
        actionable = False
        confidence = _confidence_band(
            actionability,
            evidence_confidence,
            risk,
            catalyst=catalyst,
            actionable=False,
            blockers=blockers,
            cfg=cfg,
        )
    warnings = _decision_warnings(
        data,
        catalyst=catalyst,
        tradability=tradability,
        blockers=blockers,
        risk_components=risk_components,
    )
    why_review, confirms, invalidates = _review_copy(
        data,
        origin=origin,
        bias=bias,
        catalyst=catalyst,
        timing=timing,
        radar_route=radar_route,
        blockers=blockers,
    )
    return build_decision_result(
        origin=origin, bias=bias, catalyst=catalyst, confidence=confidence,
        timing=timing, tradability=tradability, radar_route=radar_route,
        route_reason=route_reason, actionable=actionable, actionability=actionability,
        evidence_confidence=evidence_confidence, risk=risk,
        action_components=action_components, evidence_components=evidence_components,
        risk_components=risk_components, penalty_points=penalty_points,
        blockers=blockers, penalties=penalties, missing=missing, warnings=warnings,
        why_review=why_review, confirms=confirms,
        invalidates=invalidates,
    )


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
    actionability = _weighted_actionability(action_components, origin=origin) - sum(penalty_points.values())
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
    if blockers:
        risk = max(risk, 85.0)
    return _clamp(actionability), evidence_confidence, risk


def _thesis_origin(data: Mapping[str, Any], sources: tuple[Mapping[str, Any], ...]) -> str:
    origins = _texts(data.get("source_origins"))
    origins.extend(_texts(data.get("source_origin")))
    origins.extend(str(row.get("_source_origin") or "") for row in sources)
    packs = _texts(data.get("source_packs")) + _texts(data.get("source_pack"))
    packs.extend(str(row.get("source_pack") or "") for row in sources)
    classes = _texts(data.get("source_class"))
    classes.extend(str(row.get("source_class") or "") for row in sources)
    text = " ".join((*origins, *packs, *classes, str(data.get("event_type") or ""))).casefold()
    has_market = "market_anomaly" in text
    has_macro = any(term in text for term in ("macro", "central_bank", "inflation", "employment"))
    has_catalyst = any(
        term in text
        for term in ("official_exchange", "official_project", "scheduled_catalyst", "unlock", "news", "regulatory")
    ) or isinstance(data.get("official_exchange_event"), Mapping) or isinstance(data.get("scheduled_catalyst_event"), Mapping)
    has_technical = any(term in text for term in ("derivatives", "dex_", "protocol_fundamentals", "technical"))
    if not (has_market or has_macro or has_catalyst or has_technical):
        has_market = str(data.get("market_state_class") or "") in {
            "confirmed_breakout",
            "stealth_accumulation",
            "late_momentum",
            "blowoff_crowded",
            "risk_off_sell_pressure",
        }
    if has_macro and (has_market or has_catalyst or has_technical):
        return ThesisOrigin.MIXED.value
    if has_macro:
        return ThesisOrigin.MACRO_LED.value
    if has_market and has_catalyst:
        return ThesisOrigin.MIXED.value
    if has_catalyst:
        return ThesisOrigin.CATALYST_LED.value
    if has_market:
        return ThesisOrigin.MARKET_LED.value
    if has_technical:
        return ThesisOrigin.TECHNICAL_LED.value
    return ThesisOrigin.MIXED.value


def _catalyst_status(data: Mapping[str, Any], sources: tuple[Mapping[str, Any], ...]) -> str:
    explicit = str(data.get("catalyst_status") or "").strip().casefold()
    if explicit in {item.value for item in CatalystStatus}:
        return explicit
    text = _row_text(data, sources)
    if bool(data.get("catalyst_disproven")) or str(data.get("cause_status") or "") == "ruled_out" or any(
        term in text for term in ("source correction", "official denial", "catalyst_disproven")
    ):
        return CatalystStatus.DISPROVEN.value
    official = (
        isinstance(data.get("official_exchange_event"), Mapping)
        or str(data.get("source_class") or "") in {"official_exchange", "official_project", "structured_calendar", "structured_unlock"}
        or str(data.get("source_strength") or "") == "official_structured"
        or "official_exchange" in text
    )
    accepted = _number(data.get("accepted_evidence_count")) or 0.0
    source_lane_text = " ".join(
        (
            *_texts(data.get("source_origin")),
            *_texts(data.get("source_origins")),
            *_texts(data.get("source_class")),
            *_texts(data.get("source_pack")),
            *(str(row.get("_source_origin") or "") for row in sources),
            *(str(row.get("source_class") or "") for row in sources),
            *(str(row.get("source_pack") or "") for row in sources),
        )
    ).casefold()
    catalyst_specific_source = any(
        token in source_lane_text
        for token in (
            "official_exchange",
            "official_project",
            "scheduled_catalyst",
            "structured_calendar",
            "structured_unlock",
            "unlock",
            "news",
            "cryptopanic",
            "gdelt",
            "rss",
            "project_blog",
            "regulatory",
            "external_catalyst",
            "prediction_market",
        )
    )
    if official and (accepted > 0 or isinstance(data.get("official_exchange_event"), Mapping)):
        return CatalystStatus.CONFIRMED.value
    if (accepted > 0 and catalyst_specific_source) or (
        data.get("latest_source_url")
        and catalyst_specific_source
    ):
        return CatalystStatus.PLAUSIBLE.value
    if bool(data.get("catalyst_not_required")):
        return CatalystStatus.NOT_REQUIRED.value
    return CatalystStatus.UNKNOWN.value


def _directional_bias(data: Mapping[str, Any]) -> str:
    state = " ".join(dict.fromkeys((_specific_market_label(data), _market_label(data))))
    opportunity = str(data.get("opportunity_type") or "").upper()
    text = f"{state} {opportunity} {data.get('impact_path_type') or ''}".casefold()
    if any(term in text for term in ("post_event_fade", "blowoff", "late_momentum", "fade_short")):
        return DirectionalBias.FADE_SHORT_REVIEW.value
    if any(term in text for term in ("risk_off", "selloff", "risk_only", "unlock", "delisting", "exploit")):
        return DirectionalBias.RISK.value
    if any(term in text for term in ("confirmed_breakout", "high_liquidity_breakout", "stealth_accumulation", "early_long", "confirmed_long")):
        return DirectionalBias.LONG.value
    return DirectionalBias.NEUTRAL.value


def _timing_state(data: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    freshness = _freshness(data, market)
    if freshness in {"stale", "expired", "invalid", "future"}:
        return TimingState.STALE.value
    if isinstance(data.get("scheduled_catalyst_event"), Mapping) or bool(data.get("scheduled_at")):
        return TimingState.SCHEDULED.value
    state = _specific_market_label(data) or _market_label(data)
    if any(term in state for term in ("post_event_fade", "blowoff")):
        return TimingState.EXHAUSTED.value
    if "late_momentum" in state:
        return TimingState.EXTENDED.value
    if any(term in state for term in ("stealth_accumulation", "no_reaction")):
        return TimingState.EARLY.value
    return TimingState.ACTIVE.value


def _hard_blockers(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    sources: tuple[Mapping[str, Any], ...],
    origin: str,
    cfg: RadarDecisionConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
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
    elif origin == ThesisOrigin.MARKET_LED.value and freshness not in {
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
    if unit_warnings:
        blockers.append("invalid_market_return_units")

    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    spread = _first_number(market, "spread_bps", "bid_ask_spread_bps")
    if liquidity is not None and liquidity < cfg.minimum_liquidity_usd:
        blockers.append("liquidity_below_minimum")
    if spread is not None and spread > cfg.maximum_spread_bps:
        blockers.append("spread_above_maximum")
    if _is_suspicious_illiquid(data):
        blockers.append("suspicious_illiquid_move")
    if _is_duplicate(data):
        blockers.append("duplicate_family_suppressed")
    safety_rows = (data, *sources)
    if any(has_unsafe_side_effect(row) for row in safety_rows):
        blockers.append("research_safety_invariant_failed")
    if any(has_unredacted_secret(row) for row in safety_rows):
        blockers.append("secret_safety_failed")
    if any(has_unsafe_operator_path(row) for row in safety_rows):
        blockers.append("operator_path_safety_failed")
    return tuple(dict.fromkeys(blockers))


def _tradability_status(
    market: Mapping[str, Any],
    blockers: tuple[str, ...],
    *,
    cfg: RadarDecisionConfig,
) -> str:
    if blockers:
        return TradabilityStatus.BLOCKED.value
    liquidity = _first_number(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")
    spread = _first_number(market, "spread_bps", "bid_ask_spread_bps")
    if liquidity is None:
        return TradabilityStatus.POOR.value
    if spread is None:
        return TradabilityStatus.POOR.value
    if liquidity >= cfg.good_liquidity_usd and spread <= cfg.good_spread_bps:
        return TradabilityStatus.GOOD.value
    if liquidity >= cfg.minimum_liquidity_usd and spread <= cfg.maximum_spread_bps:
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


def _weighted_actionability(components: Mapping[str, float], *, origin: str) -> float:
    if origin == ThesisOrigin.MARKET_LED.value:
        weights = {
            "market_strength": 0.30,
            "volume_confirmation": 0.20,
            "relative_strength": 0.10,
            "liquidity_tradability": 0.15,
            "timing_freshness": 0.10,
            "asset_identity": 0.10,
            "catalyst_evidence": 0.05,
        }
    elif origin == ThesisOrigin.TECHNICAL_LED.value:
        weights = {
            "market_strength": 0.25,
            "volume_confirmation": 0.15,
            "relative_strength": 0.10,
            "liquidity_tradability": 0.15,
            "timing_freshness": 0.10,
            "asset_identity": 0.10,
            "derivatives_confirmation": 0.15,
        }
    elif origin == ThesisOrigin.MACRO_LED.value:
        weights = {
            "market_strength": 0.15,
            "volume_confirmation": 0.05,
            "liquidity_tradability": 0.10,
            "timing_freshness": 0.25,
            "asset_identity": 0.10,
            "catalyst_evidence": 0.30,
            "derivatives_confirmation": 0.05,
        }
    else:
        weights = {
            "market_strength": 0.20,
            "volume_confirmation": 0.10,
            "liquidity_tradability": 0.15,
            "timing_freshness": 0.15,
            "asset_identity": 0.10,
            "catalyst_evidence": 0.25,
            "derivatives_confirmation": 0.05,
        }
    return _weighted_score(components, weights)


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
    if _is_suspicious_illiquid(data):
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
    return {
        "manipulation_risk": manipulation,
        "staleness_risk": staleness,
        "extension_risk": extension,
        "catalyst_uncertainty_risk": catalyst_risk,
        "crowding_risk": crowding,
        "data_gap_risk": data_gap,
    }


def _soft_penalties(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    origin: str,
    catalyst: str,
    timing: str,
    tradability: str,
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
    if _derivatives_score(data) <= 30.0 and _directional_bias(data) == DirectionalBias.FADE_SHORT_REVIEW.value:
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
        and evidence >= 85
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
    timing: str,
    actionable: bool,
    blockers: tuple[str, ...],
    cfg: RadarDecisionConfig,
) -> tuple[str, str]:
    if blockers:
        return RadarResearchRoute.DIAGNOSTIC.value, "hard_gate_blocked_research_promotion"
    if origin in {ThesisOrigin.MARKET_LED.value, ThesisOrigin.TECHNICAL_LED.value} and not cfg.market_led_enabled:
        return RadarResearchRoute.DIAGNOSTIC.value, "market_led_route_disabled"
    if origin not in {ThesisOrigin.MARKET_LED.value, ThesisOrigin.TECHNICAL_LED.value} and not cfg.catalyst_led_enabled:
        return RadarResearchRoute.DIAGNOSTIC.value, "catalyst_led_route_disabled"
    if timing == TimingState.SCHEDULED.value or bias == DirectionalBias.RISK.value:
        return _configured_route(
            RadarResearchRoute.CALENDAR_RISK.value,
            "scheduled_or_downside_risk_research",
            enabled=cfg.calendar_risk_route_enabled,
        )
    if bias == DirectionalBias.FADE_SHORT_REVIEW.value:
        if _has_crowding(data):
            return _configured_route(
                RadarResearchRoute.FADE_EXHAUSTION_REVIEW.value,
                "extended_move_with_crowding_evidence",
                enabled=cfg.fade_exhaustion_route_enabled,
            )
        return _configured_route(
            RadarResearchRoute.RAPID_MARKET_ANOMALY.value,
            "late_move_needs_rapid_crowding_review",
            enabled=cfg.rapid_anomaly_route_enabled,
        )
    if not actionable:
        return RadarResearchRoute.DIAGNOSTIC.value, "below_configured_actionability_gate"
    if (
        confidence == ConfidenceBand.HIGH_CONFIDENCE.value
        and catalyst == CatalystStatus.CONFIRMED.value
        and origin in {ThesisOrigin.CATALYST_LED.value, ThesisOrigin.MIXED.value}
    ):
        return _configured_route(
            RadarResearchRoute.HIGH_CONFIDENCE_WATCH.value,
            "confirmed_catalyst_and_high_confidence_scores",
            enabled=cfg.high_confidence_route_enabled,
        )
    state = _market_label(data)
    if state in {"confirmed_breakout", "high_liquidity_breakout", "stealth_accumulation"}:
        return _configured_route(
            RadarResearchRoute.ACTIONABLE_WATCH.value,
            "fresh_market_led_long_research",
            enabled=cfg.actionable_watch_route_enabled,
        )
    return _configured_route(
        RadarResearchRoute.ACTIONABLE_WATCH.value,
        "configured_research_actionability_gate_passed",
        enabled=cfg.actionable_watch_route_enabled,
    )


def _configured_route(route: str, reason: str, *, enabled: bool) -> tuple[str, str]:
    if enabled:
        return route, reason
    return RadarResearchRoute.DIAGNOSTIC.value, f"{route}_route_disabled"


def _decision_warnings(
    data: Mapping[str, Any],
    *,
    catalyst: str,
    tradability: str,
    blockers: tuple[str, ...],
    risk_components: Mapping[str, float],
) -> tuple[str, ...]:
    warnings = ["Research idea only; not a trade instruction."]
    if catalyst == CatalystStatus.UNKNOWN.value:
        warnings.append(
            "Catalyst unknown: evidence confidence is lower and manipulation risk is higher; this is not an automatic hard block."
        )
    if tradability in {TradabilityStatus.POOR.value, TradabilityStatus.BLOCKED.value}:
        warnings.append("Tradability is poor or blocked; review liquidity, turnover, and spread before relying on the idea.")
    if _is_suspicious_illiquid(data):
        warnings.append("Suspicious illiquid move: manipulation risk is high and promotion is blocked.")
    elif float(risk_components.get("manipulation_risk") or 0.0) >= 50.0:
        warnings.append(
            "Higher manipulation risk: manually review liquidity, spread, turnover, and venue concentration."
        )
    if blockers:
        warnings.append("One or more deterministic hard gates blocked actionable research routing.")
    return tuple(dict.fromkeys(warnings))


def _review_copy(
    data: Mapping[str, Any],
    *,
    origin: str,
    bias: str,
    catalyst: str,
    timing: str,
    radar_route: str,
    blockers: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    state = _market_label(data).replace("_", " ") or "market change"
    why: list[str] = []
    confirms: list[str] = []
    invalidates: list[str] = []
    if origin == ThesisOrigin.MARKET_LED.value:
        why.append(f"Fresh market-led evidence shows {state}; catalyst search is enrichment, not a prerequisite.")
    elif origin in {ThesisOrigin.CATALYST_LED.value, ThesisOrigin.MIXED.value}:
        why.append(f"Catalyst and market context combine into a {timing.replace('_', ' ')} research thesis.")
    elif origin == ThesisOrigin.MACRO_LED.value:
        why.append("A scheduled macro window can change broad crypto risk even before asset-specific confirmation.")
    else:
        why.append(f"Technical/derivatives evidence makes the {state} worth human review.")
    if catalyst == CatalystStatus.UNKNOWN.value:
        why.append("The catalyst is unknown, so evidence confidence is discounted rather than hard-blocked.")
    if blockers:
        why.append("Diagnostic evidence remains useful even though hard gates prevent actionable promotion.")
    elif radar_route != RadarResearchRoute.DIAGNOSTIC.value:
        why.append(f"Research route: {radar_route.replace('_', ' ')}.")

    if bias == DirectionalBias.LONG.value:
        confirms.extend(("fresh volume and relative-strength follow-through", "liquidity and spread remain within configured limits"))
        invalidates.extend(("breakout or relative strength fails", "volume anomaly fades without follow-through"))
    elif bias == DirectionalBias.FADE_SHORT_REVIEW.value:
        confirms.extend(("fresh derivatives crowding or exhaustion evidence", "failed reclaim after the extended move"))
        invalidates.extend(("funding and open interest normalize", "price consolidates without failure"))
    elif bias == DirectionalBias.RISK.value:
        confirms.extend(("downside catalyst or sell-pressure evidence strengthens", "risk window and affected assets remain current"))
        invalidates.extend(("source correction or event cancellation", "market absorbs the risk without adverse reaction"))
    else:
        confirms.append("fresh identity, market, liquidity, and source evidence")
        invalidates.append("stale data, identity conflict, or deteriorating tradability")
    if catalyst == CatalystStatus.UNKNOWN.value:
        confirms.append("a credible catalyst source would raise evidence confidence but is not required for market-led review")
    invalidates.extend(("market snapshot becomes stale", "liquidity or spread breaches a hard gate"))
    return (
        tuple(dict.fromkeys(why)),
        tuple(dict.fromkeys(confirms)),
        tuple(dict.fromkeys(invalidates)),
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


def _market_snapshot(data: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        value = data.get(key)
        if isinstance(value, Mapping):
            out.update(dict(value))
    return out


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


def _is_suspicious_illiquid(data: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(data.get(key) or "")
        for key in (
            "market_anomaly_bucket",
            "anomaly_bucket",
            "market_anomaly_type",
            "anomaly_type",
            "market_state_class",
            "dex_onchain_classification",
            "diagnostics_reason",
        )
    ).casefold()
    return any(term in text for term in ("low_liquidity_suspicious", "suspicious_illiquid", "suspicious_low_liquidity"))


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


def _row_text(data: Mapping[str, Any], sources: tuple[Mapping[str, Any], ...]) -> str:
    values: list[str] = []
    for row in (data, *sources):
        for key in (
            "source_class",
            "source_pack",
            "source_strength",
            "event_type",
            "title",
            "event_name",
            "reason_codes",
            "warnings",
        ):
            values.extend(_texts(row.get(key)))
    return " ".join(values).casefold()


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
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
    "RadarDecision", "RadarDecisionConfig", "RadarResearchRoute", "ThesisOrigin",
    "TimingState", "TradabilityStatus", "evaluate_radar_decision",
    "reevaluate_radar_decision_fields",
)
