"""Deterministic policy helpers for Crypto Radar Decision Model v2.

The helpers in this module are pure: they normalize already-supplied research
evidence and derive presentation metadata without provider calls, writes, or
side effects.  Return values consumed by the decision model use percentage
points, while explicit source-unit metadata is validated before conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Iterable, Mapping

from . import market_units
from .decision_models import (
    CatalystStatus,
    DirectionalBias,
    MarketPhase,
    PreferredHorizon,
    RadarResearchRoute,
    SpreadStatus,
    ThesisOrigin,
    TradabilityStatus,
)


_ALLOWED_ORIGINS = {item.value for item in ThesisOrigin if item is not ThesisOrigin.MIXED}
_ALLOWED_PHASES = {item.value for item in MarketPhase}
_RETURN_FIELDS = frozenset(market_units.RETURN_KEYS)
_MAX_NORMALIZED_RETURN_PERCENT_POINTS = 300.0
_MAX_FRACTION_RETURN = _MAX_NORMALIZED_RETURN_PERCENT_POINTS / 100.0


@dataclass(frozen=True)
class TimingProfile:
    """Pure timing metadata derived from one normalized market snapshot."""

    market_phase: str
    urgency_score: float
    preferred_horizon: str
    expires_at: str | None
    chase_risk_score: float
    expired: bool
    stale: bool
    expiry_invalid: bool


def normalize_market_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize explicitly-unitized return fields to percentage points.

    A snapshot-wide ``return_unit`` applies unless a field is overridden by
    ``return_units`` (or its compatibility aliases).  Impossible fraction and
    percentage-point values fail closed through ``unit_warnings``; they are not
    silently guessed or scaled into model inputs.
    """

    out = dict(snapshot)
    existing_warnings = _texts(out.get("unit_warnings"))
    warnings: list[str] = list(existing_warnings)
    raw_overrides = next(
        (
            out.get(field)
            for field in ("return_units", "return_unit_by_field", "field_return_units")
            if field in out
        ),
        None,
    )
    overrides: Mapping[str, Any]
    if raw_overrides is None:
        overrides = {}
    elif isinstance(raw_overrides, Mapping):
        overrides = raw_overrides
    else:
        overrides = {}
        warnings.append("invalid_return_unit_metadata")

    for key in overrides:
        if str(key) not in _RETURN_FIELDS:
            warnings.append(f"unknown_return_unit_field:{key}")

    common_unit = _clean_return_unit(out.get("return_unit"))
    saw_return = False
    normalized_units: dict[str, str] = {}
    for field in market_units.RETURN_KEYS:
        if field not in out or out.get(field) in (None, ""):
            continue
        saw_return = True
        raw_value = _finite_number(out.get(field))
        unit = _clean_return_unit(overrides.get(field)) if field in overrides else common_unit
        if raw_value is None:
            warnings.append(f"invalid_return_value:{field}")
            out.pop(field, None)
            continue
        if unit is None:
            warnings.append(f"return_unit_missing:{field}")
            out.pop(field, None)
            continue
        if unit == market_units.RETURN_UNIT_FRACTION:
            if abs(raw_value) > _MAX_FRACTION_RETURN:
                warnings.append(f"implausible_fraction_return:{field}")
                out.pop(field, None)
                continue
            normalized = raw_value * 100.0
        else:
            normalized = raw_value
        if abs(normalized) > _MAX_NORMALIZED_RETURN_PERCENT_POINTS:
            warnings.append(f"implausible_normalized_return:{field}")
            out.pop(field, None)
            continue
        out[field] = normalized
        normalized_units[field] = market_units.RETURN_UNIT_PERCENT_POINTS

    if saw_return:
        if common_unit is not None:
            out["source_return_unit"] = common_unit
        out["return_unit"] = market_units.RETURN_UNIT_PERCENT_POINTS
        out["return_units"] = normalized_units
    if warnings:
        out["unit_warnings"] = list(dict.fromkeys(warnings))
    else:
        out.pop("unit_warnings", None)
    return out


def market_snapshot(data: Mapping[str, Any]) -> dict[str, Any]:
    """Merge nested snapshots only after each source is unit-normalized."""

    out: dict[str, Any] = {}
    warnings: list[str] = []
    for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        value = data.get(key)
        if isinstance(value, Mapping):
            normalized = normalize_market_snapshot(value)
            warnings.extend(_texts(normalized.get("unit_warnings")))
            out.update(normalized)
    if warnings:
        out["unit_warnings"] = list(dict.fromkeys(warnings))
    return out


def directional_bias(data: Mapping[str, Any]) -> str:
    """Derive directional research bias without using calendar context."""

    state = " ".join(
        str(data.get(field) or "")
        for field in (
            "anomaly_type", "market_anomaly_type", "market_state_class", "market_state",
            "market_anomaly_bucket", "anomaly_bucket",
        )
    )
    text = f"{state} {data.get('opportunity_type') or ''} {data.get('impact_path_type') or ''}".casefold()
    if any(term in text for term in ("post_event_fade", "blowoff", "late_momentum", "fade_short")):
        return DirectionalBias.FADE_SHORT_REVIEW.value
    if any(term in text for term in ("risk_off", "selloff", "risk_only", "unlock", "delisting", "exploit")):
        return DirectionalBias.RISK.value
    if any(term in text for term in ("confirmed_breakout", "high_liquidity_breakout", "stealth_accumulation", "early_long", "confirmed_long")):
        return DirectionalBias.LONG.value
    return DirectionalBias.NEUTRAL.value


def configured_route(route: str, reason: str, *, enabled: bool) -> tuple[str, str]:
    """Apply one route enablement flag without changing legacy lanes."""

    if enabled:
        return route, reason
    return RadarResearchRoute.DIAGNOSTIC.value, f"{route}_route_disabled"


def is_suspicious_illiquid(data: Mapping[str, Any]) -> bool:
    """Return true for deterministic suspicious-low-liquidity classifications."""

    text = " ".join(
        str(data.get(key) or "")
        for key in (
            "market_anomaly_bucket", "anomaly_bucket", "market_anomaly_type", "anomaly_type",
            "market_state_class", "dex_onchain_classification", "diagnostics_reason",
        )
    ).casefold()
    return any(
        term in text
        for term in ("low_liquidity_suspicious", "suspicious_illiquid", "suspicious_low_liquidity")
    )


def decision_warnings(
    data: Mapping[str, Any],
    *,
    catalyst: str,
    tradability: str,
    spread_status_value: str,
    blockers: tuple[str, ...],
    risk_components: Mapping[str, float],
) -> tuple[str, ...]:
    """Build stable research-only warnings for the public result."""

    warnings = ["Research idea only; not a trade instruction."]
    if catalyst == CatalystStatus.UNKNOWN.value:
        warnings.append(
            "Catalyst unknown: evidence confidence is lower and manipulation risk is higher; this is not an automatic hard block."
        )
    calendar_warning = str(data.get("calendar_context_warning") or "").strip()
    if calendar_warning:
        warnings.append(calendar_warning[:240])
    if tradability in {TradabilityStatus.POOR.value, TradabilityStatus.BLOCKED.value}:
        warnings.append("Tradability is poor or blocked; review liquidity, turnover, and spread before relying on the idea.")
    if spread_status_value == SpreadStatus.UNAVAILABLE.value:
        warnings.append("Spread is unavailable; the idea is dashboard-only until execution quality is verified.")
    elif spread_status_value == SpreadStatus.STALE.value:
        warnings.append("Spread evidence is stale; the idea is dashboard-only until execution quality is refreshed.")
    elif spread_status_value == SpreadStatus.VERIFIED_WIDE.value:
        warnings.append("Verified spread is too wide for research promotion under the configured execution-quality gate.")
    if is_suspicious_illiquid(data):
        warnings.append("Suspicious illiquid move: manipulation risk is high and promotion is blocked.")
    elif float(risk_components.get("manipulation_risk") or 0.0) >= 50.0:
        warnings.append(
            "Higher manipulation risk: manually review liquidity, spread, turnover, and venue concentration."
        )
    if blockers:
        warnings.append("One or more deterministic hard gates blocked actionable research routing.")
    return tuple(dict.fromkeys(warnings))


def review_copy(
    data: Mapping[str, Any],
    *,
    origin: str,
    bias: str,
    catalyst: str,
    timing: str,
    radar_route: str,
    blockers: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Build why/confirmation/invalidation copy for human research review."""

    state = _market_label(data).replace("_", " ") or "market change"
    why: list[str] = []
    confirms: list[str] = []
    invalidates: list[str] = []
    if origin == ThesisOrigin.MARKET_LED.value:
        why.append(f"Fresh market-led evidence shows {state}; catalyst search is enrichment, not a prerequisite.")
    elif origin == ThesisOrigin.CATALYST_LED.value:
        why.append(f"Catalyst and market context combine into a {timing.replace('_', ' ')} research thesis.")
    elif origin == ThesisOrigin.MACRO_LED.value:
        why.append("A scheduled macro window can change broad crypto risk even before asset-specific confirmation.")
    elif origin == ThesisOrigin.ONCHAIN_LED.value:
        why.append(f"On-chain or DEX evidence makes the {state} worth human review alongside market context.")
    elif origin == ThesisOrigin.DERIVATIVES_LED.value:
        why.append(f"Derivatives evidence makes the {state} worth human review without inventing a catalyst.")
    elif origin == ThesisOrigin.FUNDAMENTAL_LED.value:
        why.append(f"Protocol fundamentals make the {state} worth human review alongside observed market evidence.")
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
    return tuple(dict.fromkeys(why)), tuple(dict.fromkeys(confirms)), tuple(dict.fromkeys(invalidates))


def thesis_origin_values(
    data: Mapping[str, Any],
    sources: Iterable[Mapping[str, Any]],
    *,
    rsi_context_authoritative: bool = False,
) -> tuple[str, tuple[str, ...], str]:
    """Return primary, ordered contributing, and legacy-summary origins."""

    source_rows = tuple(row for row in sources if isinstance(row, Mapping))
    direct_values = [*_texts(data.get("source_origin")), *_texts(data.get("source_origins"))]
    for row in source_rows:
        direct_values.extend(_texts(row.get("_source_origin")))
        direct_values.extend(_texts(row.get("source_origin")))
        direct_values.extend(_texts(row.get("source_origins")))

    supporting_values = [
        *_texts(data.get("source_pack")),
        *_texts(data.get("source_packs")),
        *_texts(data.get("source_class")),
        *_texts(data.get("event_type")),
    ]
    for row in source_rows:
        supporting_values.extend(_texts(row.get("source_pack")))
        supporting_values.extend(_texts(row.get("source_class")))
        supporting_values.extend(_texts(row.get("event_type")))

    ordered: list[str] = []

    def add(value: str | None) -> None:
        if value in _ALLOWED_ORIGINS and value not in ordered:
            ordered.append(value)

    technical_context = any(
        data.get(field) not in (None, "", [], {}, ())
        for field in (
            "technical_context",
            "technical_setup_type",
        )
    ) or rsi_context_authoritative
    if technical_context:
        add(ThesisOrigin.TECHNICAL_LED.value)

    direct_origins = tuple(
        origin
        for raw in direct_values
        for origin in _origins_for_text(raw)
    )
    for origin in direct_origins:
        add(origin)
    for raw in supporting_values:
        for origin in _origins_for_text(raw):
            add(origin)

    if _has_structured_context(data, ("dex_state_snapshot", "onchain_state_snapshot", "supply_state_snapshot")):
        add(ThesisOrigin.ONCHAIN_LED.value)
    if _has_structured_context(data, ("derivatives_state_snapshot", "derivatives_snapshot")):
        add(ThesisOrigin.DERIVATIVES_LED.value)
    if _has_structured_context(data, ("fundamental_state_snapshot", "protocol_fundamentals")):
        add(ThesisOrigin.FUNDAMENTAL_LED.value)
    if _has_market_thesis(data):
        add(ThesisOrigin.MARKET_LED.value)

    if not ordered:
        if _has_market_snapshot(data):
            add(ThesisOrigin.MARKET_LED.value)
        else:
            return (
                ThesisOrigin.MIXED.value,
                (ThesisOrigin.MIXED.value,),
                ThesisOrigin.MIXED.value,
            )

    primary = ordered[0]
    if technical_context:
        primary = ThesisOrigin.TECHNICAL_LED.value
        ordered = [primary, *(item for item in ordered if item != primary)]
    elif direct_origins:
        primary = direct_origins[0]
        ordered = [primary, *(item for item in ordered if item != primary)]

    legacy = primary
    origin_set = set(direct_origins)
    if (
        ThesisOrigin.MARKET_LED.value in origin_set
        and ThesisOrigin.CATALYST_LED.value in origin_set
    ) or (
        ThesisOrigin.MACRO_LED.value in origin_set and len(origin_set) > 1
    ):
        legacy = ThesisOrigin.MIXED.value
    return primary, tuple(ordered), legacy


def spread_status(
    market: Mapping[str, Any],
    *,
    good_spread_bps: float,
    maximum_spread_bps: float,
) -> str:
    """Classify explicit spread evidence without inferring a verified quote."""

    freshness = str(
        market.get("spread_freshness_status")
        or market.get("order_book_freshness_status")
        or market.get("freshness_status")
        or ""
    ).strip().casefold()
    if freshness in {"stale", "expired", "invalid", "future"}:
        return SpreadStatus.STALE.value
    explicit = str(market.get("spread_status") or "").strip().casefold()
    if explicit == SpreadStatus.STALE.value:
        return SpreadStatus.STALE.value
    if explicit == SpreadStatus.UNAVAILABLE.value:
        return SpreadStatus.UNAVAILABLE.value
    spread = _first_finite_number(market, "spread_bps", "bid_ask_spread_bps")
    if spread is None:
        return SpreadStatus.UNAVAILABLE.value
    if spread < 0 or spread > maximum_spread_bps:
        return SpreadStatus.VERIFIED_WIDE.value
    if spread <= good_spread_bps:
        return SpreadStatus.VERIFIED_GOOD.value
    return SpreadStatus.VERIFIED_ACCEPTABLE.value


def timing_profile(data: Mapping[str, Any], market: Mapping[str, Any]) -> TimingProfile:
    """Derive deterministic urgency, phase, horizon, expiry, and chase risk."""

    phase = _derive_market_phase(data)
    scheduled = has_calendar_risk(data)
    state = _market_label(data)
    volume_z = _first_finite_number(
        market,
        "volume_zscore_24h",
        "volume_turnover_zscore",
        "turnover_zscore",
    )
    move = max(
        (
            abs(value)
            for value in (
                _first_finite_number(market, "return_1h"),
                _first_finite_number(market, "return_4h"),
                _first_finite_number(
                    market,
                    "relative_return_vs_btc_4h",
                    "relative_return_vs_btc",
                    "relative_return_vs_btc_24h",
                ),
            )
            if value is not None
        ),
        default=0.0,
    )
    urgency_base = {
        MarketPhase.EMERGING.value: 58.0,
        MarketPhase.BREAKOUT.value: 74.0,
        MarketPhase.ACCELERATION.value: 82.0,
        MarketPhase.ACTIVE.value: 64.0,
        MarketPhase.EXTENDED.value: 76.0,
        MarketPhase.EXHAUSTION.value: 72.0,
        MarketPhase.REVERSAL.value: 80.0,
    }[phase]
    urgency = urgency_base + min(10.0, max(0.0, (volume_z or 0.0) - 1.0) * 2.5) + min(8.0, move / 4.0)
    chase_base = {
        MarketPhase.EMERGING.value: 15.0,
        MarketPhase.BREAKOUT.value: 30.0,
        MarketPhase.ACCELERATION.value: 50.0,
        MarketPhase.ACTIVE.value: 35.0,
        MarketPhase.EXTENDED.value: 75.0,
        MarketPhase.EXHAUSTION.value: 90.0,
        MarketPhase.REVERSAL.value: 60.0,
    }[phase]
    chase = chase_base + min(10.0, move / 3.0)
    if scheduled:
        horizon = PreferredHorizon.SCHEDULED_WINDOW.value
    elif phase in {
        MarketPhase.ACCELERATION.value,
        MarketPhase.EXTENDED.value,
        MarketPhase.EXHAUSTION.value,
        MarketPhase.REVERSAL.value,
    } or any(term in state for term in ("selloff", "risk_off")):
        horizon = PreferredHorizon.INTRADAY.value
    elif phase == MarketPhase.EMERGING.value:
        horizon = PreferredHorizon.THREE_TO_SEVEN_DAYS.value
    else:
        horizon = PreferredHorizon.ONE_TO_THREE_DAYS.value

    anchor = _first_aware_timestamp(
        data,
        market,
        fields=("decision_evaluated_at", "evaluated_at", "generated_at", "observed_at", "captured_at", "as_of"),
    )
    explicit_expiry_present = data.get("expires_at") not in (None, "")
    explicit_expiry = _parse_aware_timestamp(data.get("expires_at"))
    expiry_invalid = explicit_expiry_present and explicit_expiry is None
    expiry = explicit_expiry
    if expiry is None and anchor is not None and not expiry_invalid:
        ttl_hours = {
            MarketPhase.EMERGING.value: 72,
            MarketPhase.BREAKOUT.value: 24,
            MarketPhase.ACCELERATION.value: 8,
            MarketPhase.ACTIVE.value: 24,
            MarketPhase.EXTENDED.value: 6,
            MarketPhase.EXHAUSTION.value: 3,
            MarketPhase.REVERSAL.value: 8,
        }[phase]
        expiry = anchor + timedelta(hours=ttl_hours)
    expired = str(data.get("expiry_status") or "").strip().casefold() == "expired"
    market_freshness = str(market.get("freshness_status") or "").strip().casefold()
    expired = expired or market_freshness == "expired"
    stale = market_freshness in {"stale", "invalid", "future"}
    if expiry is not None and anchor is not None and expiry <= anchor:
        expired = True
    return TimingProfile(
        market_phase=phase,
        urgency_score=round(_clamp(urgency), 2),
        preferred_horizon=horizon,
        expires_at=_format_timestamp(expiry) if expiry is not None else None,
        chase_risk_score=round(_clamp(chase), 2),
        expired=expired,
        stale=stale,
        expiry_invalid=expiry_invalid,
    )


def has_calendar_risk(data: Mapping[str, Any]) -> bool:
    """Return true only for attached calendar evidence or a valid schedule."""

    for field in (
        "unified_calendar_event",
        "calendar_event",
        "scheduled_catalyst_event",
        "unlock_event",
    ):
        if isinstance(data.get(field), Mapping) and bool(data.get(field)):
            return True
    nearby = data.get("nearby_calendar_events") or data.get("calendar_events")
    if isinstance(nearby, Iterable) and not isinstance(nearby, (str, bytes, Mapping)):
        if any(isinstance(item, Mapping) and bool(item) for item in nearby):
            return True
    return _parse_aware_timestamp(data.get("scheduled_at")) is not None


def timing_state_for_profile(profile: TimingProfile, *, scheduled: bool) -> str:
    """Map the richer phase contract back to the compatibility timing field."""

    if profile.expired or profile.stale:
        return "stale"
    if scheduled:
        return "scheduled"
    return {
        MarketPhase.EMERGING.value: "early",
        MarketPhase.BREAKOUT.value: "active",
        MarketPhase.ACCELERATION.value: "active",
        MarketPhase.ACTIVE.value: "active",
        MarketPhase.EXTENDED.value: "extended",
        MarketPhase.EXHAUSTION.value: "exhausted",
        MarketPhase.REVERSAL.value: "active",
    }[profile.market_phase]


def uses_market_lane(origin: str) -> bool:
    """Return whether an origin uses the market-led research enablement gate."""

    return origin in {
        ThesisOrigin.MARKET_LED.value,
        ThesisOrigin.TECHNICAL_LED.value,
        ThesisOrigin.DERIVATIVES_LED.value,
        ThesisOrigin.ONCHAIN_LED.value,
    }


def weighted_actionability(components: Mapping[str, float], *, origin: str) -> float:
    """Apply the origin-specific Decision v2 actionability weights."""

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
    elif origin in {ThesisOrigin.TECHNICAL_LED.value, ThesisOrigin.DERIVATIVES_LED.value}:
        weights = {
            "market_strength": 0.25,
            "volume_confirmation": 0.15,
            "relative_strength": 0.10,
            "liquidity_tradability": 0.15,
            "timing_freshness": 0.10,
            "asset_identity": 0.10,
            "derivatives_confirmation": 0.15,
        }
    elif origin == ThesisOrigin.ONCHAIN_LED.value:
        weights = {
            "market_strength": 0.25,
            "volume_confirmation": 0.20,
            "relative_strength": 0.10,
            "liquidity_tradability": 0.20,
            "timing_freshness": 0.10,
            "asset_identity": 0.10,
            "catalyst_evidence": 0.05,
        }
    elif origin == ThesisOrigin.FUNDAMENTAL_LED.value:
        weights = {
            "market_strength": 0.15,
            "volume_confirmation": 0.10,
            "relative_strength": 0.05,
            "liquidity_tradability": 0.15,
            "timing_freshness": 0.15,
            "asset_identity": 0.10,
            "catalyst_evidence": 0.30,
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
    total_weight = sum(weights.values())
    return _clamp(
        sum(float(components.get(key, 0.0)) * weight for key, weight in weights.items())
        / total_weight
    )


def apply_validated_rsi_adjustments(
    *,
    actionability: float,
    risk: float,
    actionability_delta: float,
    risk_delta: float,
    reasons: tuple[str, ...],
    action_components: dict[str, float],
    risk_components: dict[str, float],
    penalty_points: dict[str, float],
    blockers: tuple[str, ...],
) -> tuple[float, float]:
    """Apply adapter-validated bounded RSI deltas and expose their math."""

    if not reasons:
        return actionability, risk
    if actionability_delta > 0:
        action_components["rsi_technical_context_bonus_points"] = actionability_delta
    elif actionability_delta < 0:
        penalty_points["rsi_technical_context"] = abs(actionability_delta)
    risk_components["rsi_technical_context_adjustment"] = risk_delta
    adjusted_actionability = _clamp(actionability + actionability_delta)
    adjusted_risk = _clamp(risk + risk_delta)
    if blockers:
        adjusted_actionability = min(adjusted_actionability, 20.0)
        adjusted_risk = max(adjusted_risk, 85.0)
    return adjusted_actionability, adjusted_risk


def _origins_for_text(value: object) -> tuple[str, ...]:
    text = str(value or "").strip().casefold().replace("-", "_")
    if not text:
        return ()
    out: list[str] = []

    def add(origin: str) -> None:
        if origin not in out:
            out.append(origin)

    if any(term in text for term in ("dex", "onchain", "on_chain", "wallet", "liquidity_pool", "supply")):
        add(ThesisOrigin.ONCHAIN_LED.value)
    if any(term in text for term in ("derivative", "coinalyze", "funding", "open_interest", "perpetual")):
        add(ThesisOrigin.DERIVATIVES_LED.value)
    if any(term in text for term in ("protocol_fundamental", "fundamental", "protocol_revenue", "protocol_fee", "tvl")):
        add(ThesisOrigin.FUNDAMENTAL_LED.value)
    if any(term in text for term in ("technical", "rsi", "indicator")):
        add(ThesisOrigin.TECHNICAL_LED.value)
    if any(term in text for term in ("macro", "central_bank", "inflation", "employment", "fomc", "cpi", "pce", "gdp")):
        add(ThesisOrigin.MACRO_LED.value)
    if any(
        term in text
        for term in (
            "official_exchange",
            "official_project",
            "scheduled_catalyst",
            "structured_calendar",
            "structured_unlock",
            "unlock",
            "news",
            "regulatory",
            "external_catalyst",
            "prediction_market",
        )
    ):
        add(ThesisOrigin.CATALYST_LED.value)
    if any(term in text for term in ("market_anomaly", "market_state", "price_volume", "breakout")):
        add(ThesisOrigin.MARKET_LED.value)
    return tuple(out)


def _derive_market_phase(data: Mapping[str, Any]) -> str:
    text = " ".join(
        str(data.get(field) or "")
        for field in (
            "anomaly_type",
            "market_anomaly_type",
            "market_anomaly_bucket",
            "anomaly_bucket",
            "market_state_class",
            "market_state",
        )
    ).casefold()
    if any(term in text for term in ("blowoff", "exhaust", "post_event_fade")):
        return MarketPhase.EXHAUSTION.value
    if any(term in text for term in ("late_momentum", "extended")):
        return MarketPhase.EXTENDED.value
    if any(term in text for term in ("risk_off", "selloff", "reversal", "breakdown")):
        return MarketPhase.REVERSAL.value
    if "acceleration" in text:
        return MarketPhase.ACCELERATION.value
    if any(term in text for term in ("confirmed_breakout", "high_liquidity_breakout", "breakout")):
        return MarketPhase.BREAKOUT.value
    if any(term in text for term in ("stealth_accumulation", "emerging", "early", "no_reaction")):
        return MarketPhase.EMERGING.value
    return MarketPhase.ACTIVE.value


def _has_market_thesis(data: Mapping[str, Any]) -> bool:
    return bool(_market_label(data) or any(
        "market_anomaly" in str(value).casefold()
        for field in ("source_origin", "source_origins", "source_pack", "source_packs")
        for value in _texts(data.get(field))
    ))


def _has_market_snapshot(data: Mapping[str, Any]) -> bool:
    return any(isinstance(data.get(field), Mapping) and bool(data.get(field)) for field in (
        "latest_market_snapshot", "market_snapshot", "market_state_snapshot"
    ))


def _has_structured_context(data: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return any(isinstance(data.get(field), Mapping) and bool(data.get(field)) for field in fields)


def _market_label(data: Mapping[str, Any]) -> str:
    for field in (
        "market_anomaly_bucket",
        "anomaly_bucket",
        "market_anomaly_type",
        "anomaly_type",
        "market_state_class",
        "market_state",
    ):
        value = str(data.get(field) or "").strip().casefold()
        if value:
            return value
    return ""


def _clean_return_unit(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if text in {"fraction", "fractions", "decimal", "raw_fraction"}:
        return market_units.RETURN_UNIT_FRACTION
    if text in {"percent", "percentage", "percent_points", "percentage_points", "pct", "pct_points"}:
        return market_units.RETURN_UNIT_PERCENT_POINTS
    return None


def _first_finite_number(row: Mapping[str, Any], *fields: str) -> float | None:
    for field in fields:
        if field in row and row.get(field) not in (None, ""):
            value = _finite_number(row.get(field))
            if value is not None:
                return value
    return None


def _finite_number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _first_aware_timestamp(
    *rows: Mapping[str, Any],
    fields: tuple[str, ...],
) -> datetime | None:
    for field in fields:
        for row in rows:
            parsed = _parse_aware_timestamp(row.get(field))
            if parsed is not None:
                return parsed
    return None


def _parse_aware_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


__all__ = (
    "TimingProfile",
    "apply_validated_rsi_adjustments",
    "configured_route",
    "decision_warnings",
    "directional_bias",
    "has_calendar_risk",
    "normalize_market_snapshot",
    "market_snapshot",
    "is_suspicious_illiquid",
    "spread_status",
    "thesis_origin_values",
    "timing_profile",
    "timing_state_for_profile",
    "review_copy",
    "uses_market_lane",
    "weighted_actionability",
)
