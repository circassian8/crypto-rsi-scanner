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
import re
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
_COMPONENT_SPLIT = re.compile(r"[^a-z0-9]+")
_COMPONENT_NEGATIONS = frozenset({"no", "non", "not", "without"})
_ORIGIN_COMPONENT_TERMS = (
    (
        ThesisOrigin.ONCHAIN_LED.value,
        (
            "dex",
            "onchain",
            "on_chain",
            "wallet",
            "wallets",
            "liquidity_pool",
            "supply",
            "supplies",
        ),
    ),
    (
        ThesisOrigin.DERIVATIVES_LED.value,
        (
            "derivative",
            "derivatives",
            "coinalyze",
            "funding",
            "open_interest",
            "perpetual",
            "perpetuals",
        ),
    ),
    (
        ThesisOrigin.FUNDAMENTAL_LED.value,
        (
            "protocol_fundamental",
            "protocol_fundamentals",
            "fundamental",
            "fundamentals",
            "protocol_revenue",
            "protocol_fee",
            "protocol_fees",
            "tvl",
        ),
    ),
    (
        ThesisOrigin.TECHNICAL_LED.value,
        ("technical", "rsi", "indicator", "indicators"),
    ),
    (
        ThesisOrigin.MACRO_LED.value,
        (
            "macro",
            "central_bank",
            "inflation",
            "employment",
            "fomc",
            "cpi",
            "pce",
            "gdp",
        ),
    ),
    (
        ThesisOrigin.CATALYST_LED.value,
        (
            "official_exchange",
            "official_project",
            "scheduled_catalyst",
            "structured_calendar",
            "structured_unlock",
            "token_unlock",
            "cliff_unlock",
            "vesting_unlock",
            "unlock",
            "unlocks",
            "news",
            "regulatory",
            "external_catalyst",
            "prediction_market",
        ),
    ),
    (
        ThesisOrigin.MARKET_LED.value,
        ("market_anomaly", "market_state", "price_volume", "breakout"),
    ),
)
_DIRECTIONAL_BIAS_COMPONENT_TERMS = (
    (
        DirectionalBias.FADE_SHORT_REVIEW.value,
        ("post_event_fade", "blowoff", "late_momentum", "fade_short"),
    ),
    (
        DirectionalBias.RISK.value,
        (
            "risk_off",
            "selloff",
            "risk_only",
            "structured_unlock",
            "token_unlock",
            "cliff_unlock",
            "vesting_unlock",
            "unlock",
            "delisting",
            "exploit",
        ),
    ),
    (
        DirectionalBias.LONG.value,
        (
            "confirmed_breakout",
            "high_liquidity_breakout",
            "stealth_accumulation",
            "early_long",
            "confirmed_long",
        ),
    ),
)
_SUSPICIOUS_ILLIQUID_COMPONENT_TERMS = (
    "low_liquidity_suspicious",
    "suspicious_illiquid",
    "suspicious_low_liquidity",
)
_MARKET_PHASE_COMPONENT_TERMS = (
    (
        MarketPhase.EXHAUSTION.value,
        (
            "blowoff",
            "crowding_exhaustion",
            "exhaust",
            "exhausted",
            "exhaustion",
            "post_event_fade",
        ),
    ),
    (MarketPhase.EXTENDED.value, ("late_momentum", "extended", "overextended")),
    (
        MarketPhase.REVERSAL.value,
        ("risk_off", "selloff", "reversal", "breakdown"),
    ),
    (MarketPhase.ACCELERATION.value, ("acceleration",)),
    (
        MarketPhase.BREAKOUT.value,
        ("confirmed_breakout", "high_liquidity_breakout", "breakout"),
    ),
    (
        MarketPhase.EMERGING.value,
        ("stealth_accumulation", "emerging", "early", "no_reaction"),
    ),
)
_ALLOWED_PHASES = {item.value for item in MarketPhase}
_RETURN_FIELDS = frozenset(market_units.RETURN_KEYS)
_MAX_NORMALIZED_RETURN_PERCENT_POINTS = 300.0
_MAX_FRACTION_RETURN = _MAX_NORMALIZED_RETURN_PERCENT_POINTS / 100.0
_MARKET_CLASSIFICATION_FIELDS = (
    "market_anomaly_bucket",
    "anomaly_bucket",
    "market_anomaly_type",
    "anomaly_type",
    "market_state_class",
    "market_state",
)
_SOURCE_SCALAR_FIELDS = (
    "_source_origin",
    "source_origin",
    "source_pack",
    "source_class",
    "event_type",
)
_SOURCE_LIST_FIELDS = ("source_origins", "source_packs")
_CALENDAR_SINGLE_EVENT_FIELDS = (
    "unified_calendar_event",
    "calendar_event",
    "scheduled_catalyst_event",
    "unlock_event",
)
_CALENDAR_EVENT_LIST_FIELDS = (
    "calendar_evidence",
    "unified_calendar_context",
    "nearby_calendar_events",
    "calendar_events",
)
_CALENDAR_TIMESTAMP_FIELDS = (
    "scheduled_at",
    "event_start_time",
    "effective_time",
    "window_start",
    "window_end",
)
_CALENDAR_TEXT_FIELDS = (
    "calendar_event_id",
    "event_id",
    "evidence_reference",
    "event_kind",
    "category",
    "event_type",
    "source",
    "provider",
    "source_url",
)
_CALENDAR_ENUM_FIELDS = {
    "time_certainty": {"exact", "window", "estimated", "unknown"},
    "importance": {"low", "medium", "high", "critical", "unknown"},
}
_ONCHAIN_CONTEXT_FIELDS = (
    "dex_state_snapshot",
    "onchain_state_snapshot",
    "supply_state_snapshot",
)
_FUNDAMENTAL_CONTEXT_FIELDS = (
    "fundamental_state_snapshot",
    "protocol_fundamentals",
)
_DECISION_TEXT_CLAIM_FIELDS = (
    "opportunity_type",
    "candidate_role",
    "impact_path_type",
    "playbook_type",
    "effective_playbook_type",
    "diagnostics_reason",
    "calendar_context_warning",
    "run_mode",
    "profile",
    "data_mode",
    "data_acquisition_mode",
    "candidate_source_mode",
)
_TIMING_ANCHOR_FIELDS = (
    "decision_evaluated_at",
    "evaluated_at",
    "generated_at",
    "observed_at",
    "captured_at",
    "as_of",
)
_MARKET_FRESHNESS_FIELDS = (
    "spread_freshness_status",
    "order_book_freshness_status",
    "market_context_freshness_status",
    "freshness_status",
)
_ALLOWED_MARKET_FRESHNESS = {
    "fresh",
    "stale",
    "expired",
    "unknown",
    "missing",
    "unavailable",
    "invalid",
    "future",
    "fixture_allowed_stale",
}
_ALLOWED_INPUT_SPREAD_STATUSES = {
    *(item.value for item in SpreadStatus),
    "verified",
}


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
            for field in _RETURN_FIELDS:
                if (
                    field in value
                    and value.get(field) not in (None, "")
                    and field not in normalized
                ):
                    # Normalization rejected an explicitly supplied value.
                    # Remove any older snapshot value so malformed current
                    # evidence cannot expose a plausible earlier return.
                    out.pop(field, None)
            out.update(normalized)
    if warnings:
        out["unit_warnings"] = list(dict.fromkeys(warnings))
    return out


def market_snapshot_invalid(data: Mapping[str, Any]) -> bool:
    """Detect an explicit non-mapping market snapshot container."""

    return any(
        key in data
        and data.get(key) not in (None, "")
        and not isinstance(data.get(key), Mapping)
        for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot")
    )


def directional_bias(data: Mapping[str, Any]) -> str:
    """Derive directional research bias without using calendar context."""

    values = (
        *_market_classification_values(data),
        data.get("opportunity_type"),
        data.get("impact_path_type"),
    )
    for bias, terms in _DIRECTIONAL_BIAS_COMPONENT_TERMS:
        if has_unnegated_component_terms(values, terms):
            return bias
    return DirectionalBias.NEUTRAL.value


def configured_route(route: str, reason: str, *, enabled: bool) -> tuple[str, str]:
    """Apply one route enablement flag without changing legacy lanes."""

    if enabled:
        return route, reason
    return RadarResearchRoute.DIAGNOSTIC.value, f"{route}_route_disabled"


def is_suspicious_illiquid(data: Mapping[str, Any]) -> bool:
    """Return true for deterministic suspicious-low-liquidity classifications."""

    values = tuple(
        data.get(key)
        for key in (
            "market_anomaly_bucket", "anomaly_bucket", "market_anomaly_type", "anomaly_type",
            "market_state_class", "dex_onchain_classification", "diagnostics_reason",
        )
    )
    return has_unnegated_component_terms(
        values,
        _SUSPICIOUS_ILLIQUID_COMPONENT_TERMS,
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
    calendar_warning = _typed_text(data.get("calendar_context_warning"))
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
    direct_values = [
        *_source_scalar_values(data, "source_origin"),
        *_source_list_values(data, "source_origins"),
    ]
    for row in source_rows:
        direct_values.extend(_source_scalar_values(row, "_source_origin"))
        direct_values.extend(_source_scalar_values(row, "source_origin"))
        direct_values.extend(_source_list_values(row, "source_origins"))

    supporting_values = [
        *_source_scalar_values(data, "source_pack"),
        *_source_list_values(data, "source_packs"),
        *_source_scalar_values(data, "source_class"),
        *_source_scalar_values(data, "event_type"),
    ]
    for row in source_rows:
        supporting_values.extend(_source_scalar_values(row, "source_pack"))
        supporting_values.extend(_source_list_values(row, "source_packs"))
        supporting_values.extend(_source_scalar_values(row, "source_class"))
        supporting_values.extend(_source_scalar_values(row, "event_type"))

    ordered: list[str] = []

    def add(value: str | None) -> None:
        if value in _ALLOWED_ORIGINS and value not in ordered:
            ordered.append(value)

    technical_context = _has_technical_context(data) or rsi_context_authoritative
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

    if _has_structured_context(data, _ONCHAIN_CONTEXT_FIELDS):
        add(ThesisOrigin.ONCHAIN_LED.value)
    if _has_structured_context(data, ("derivatives_state_snapshot", "derivatives_snapshot")):
        add(ThesisOrigin.DERIVATIVES_LED.value)
    if _has_structured_context(data, _FUNDAMENTAL_CONTEXT_FIELDS):
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

    freshness_value: object = None
    for field in (
        "spread_freshness_status",
        "order_book_freshness_status",
        "freshness_status",
    ):
        if field in market and market.get(field) not in (None, ""):
            freshness_value = market.get(field)
            break
    freshness = _typed_text(freshness_value).casefold()
    if freshness in {"stale", "expired", "invalid", "future"}:
        return SpreadStatus.STALE.value
    if freshness not in {"fresh", "fixture_allowed_stale"}:
        return SpreadStatus.UNAVAILABLE.value
    explicit_claimed = (
        "spread_status" in market and market.get("spread_status") not in (None, "")
    )
    explicit = _typed_text(market.get("spread_status")).casefold()
    if explicit_claimed and explicit not in _ALLOWED_INPUT_SPREAD_STATUSES:
        return SpreadStatus.UNAVAILABLE.value
    if explicit == SpreadStatus.STALE.value:
        return SpreadStatus.STALE.value
    if explicit == SpreadStatus.UNAVAILABLE.value:
        return SpreadStatus.UNAVAILABLE.value
    if explicit == SpreadStatus.VERIFIED_WIDE.value:
        return SpreadStatus.VERIFIED_WIDE.value
    spread = _first_finite_number(market, "spread_bps", "bid_ask_spread_bps")
    if spread is None:
        return SpreadStatus.UNAVAILABLE.value
    if spread < 0 or spread > maximum_spread_bps:
        return SpreadStatus.VERIFIED_WIDE.value
    derived = (
        SpreadStatus.VERIFIED_GOOD.value
        if spread <= good_spread_bps
        else SpreadStatus.VERIFIED_ACCEPTABLE.value
    )
    if explicit == SpreadStatus.VERIFIED_ACCEPTABLE.value:
        return SpreadStatus.VERIFIED_ACCEPTABLE.value
    return derived


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
    } or has_unnegated_component_terms((state,), ("selloff", "risk_off")):
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
    expired = _typed_text(data.get("expiry_status")).casefold() == "expired"
    market_freshness = _typed_text(market.get("freshness_status")).casefold()
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

    for field in _CALENDAR_SINGLE_EVENT_FIELDS:
        if isinstance(data.get(field), Mapping) and bool(data.get(field)):
            return True
    for field in _CALENDAR_EVENT_LIST_FIELDS:
        nearby = data.get(field)
        if isinstance(nearby, (list, tuple)) and any(
            isinstance(item, Mapping) and bool(item) for item in nearby
        ):
            return True
    return _parse_aware_timestamp(data.get("scheduled_at")) is not None


def calendar_context_invalid(data: Mapping[str, Any]) -> bool:
    """Detect malformed explicit calendar containers and schedule timestamps."""

    for field in _CALENDAR_SINGLE_EVENT_FIELDS:
        if field not in data or data.get(field) in (None, "", {}):
            continue
        value = data.get(field)
        if not isinstance(value, Mapping) or _calendar_event_claims_invalid(value):
            return True
    for field in _CALENDAR_EVENT_LIST_FIELDS:
        if field not in data or data.get(field) in (None, "", [], ()):
            continue
        value = data.get(field)
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, Mapping)
            or not item
            or _calendar_event_claims_invalid(item)
            for item in value
        ):
            return True
        if field == "calendar_evidence" and any(
            not _typed_text(item.get("calendar_event_id"))
            and not _typed_text(item.get("evidence_reference"))
            for item in value
        ):
            return True
    if "scheduled_at" not in data or data.get("scheduled_at") in (None, ""):
        return False
    return _calendar_event_claims_invalid(data)


def origin_context_invalid(data: Mapping[str, Any]) -> bool:
    """Detect malformed context containers that can select a thesis origin."""

    if (
        "technical_context" in data
        and data.get("technical_context") not in (None, "", {})
        and not isinstance(data.get("technical_context"), Mapping)
    ):
        return True
    if (
        "technical_setup_type" in data
        and data.get("technical_setup_type") not in (None, "")
        and not _typed_text(data.get("technical_setup_type"))
    ):
        return True
    return any(
        field in data
        and data.get(field) not in (None, "", {})
        and not isinstance(data.get(field), Mapping)
        for field in (*_ONCHAIN_CONTEXT_FIELDS, *_FUNDAMENTAL_CONTEXT_FIELDS)
    )


def decision_text_claims_invalid(data: Mapping[str, Any]) -> bool:
    """Reject malformed text that controls routing or operator copy."""

    if any(
        field in data
        and data.get(field) not in (None, "")
        and not _typed_text(data.get(field))
        for field in _DECISION_TEXT_CLAIM_FIELDS
    ):
        return True
    if "directional_bias" in data and data.get("directional_bias") not in (
        None,
        "",
    ):
        return _typed_text(data.get("directional_bias")).casefold() not in {
            item.value for item in DirectionalBias
        }
    return False


def timing_context_invalid(
    data: Mapping[str, Any],
    market: Mapping[str, Any],
) -> bool:
    """Reject malformed explicit timing claims before expiry derivation."""

    if (
        "expiry_status" in data
        and data.get("expiry_status") not in (None, "")
        and not _typed_text(data.get("expiry_status"))
    ):
        return True
    return any(
        field in row
        and row.get(field) not in (None, "")
        and _parse_aware_timestamp(row.get(field)) is None
        for row in (data, market)
        for field in _TIMING_ANCHOR_FIELDS
    )


def market_execution_claims_invalid(market: Mapping[str, Any]) -> bool:
    """Reject malformed freshness/spread classifications before promotion."""

    for field in _MARKET_FRESHNESS_FIELDS:
        if field not in market or market.get(field) in (None, ""):
            continue
        value = _typed_text(market.get(field)).casefold()
        if not value or value not in _ALLOWED_MARKET_FRESHNESS:
            return True
    if "spread_status" in market and market.get("spread_status") not in (None, ""):
        value = _typed_text(market.get("spread_status")).casefold()
        if not value or value not in _ALLOWED_INPUT_SPREAD_STATUSES:
            return True
    return False


def fixture_freshness_provenance_invalid(
    data: Mapping[str, Any],
    *,
    freshness: str,
) -> bool:
    """Keep fixture-only stale tolerance out of live-style provenance."""

    if freshness != "fixture_allowed_stale":
        return False
    run_mode = _typed_text(data.get("run_mode")).casefold()
    profile = _typed_text(data.get("profile")).casefold()
    if run_mode not in {"fixture", "test", "replay"} or not profile:
        return True
    provenance = " ".join(
        _typed_text(data.get(field)).casefold()
        for field in (
            "profile",
            "data_mode",
            "data_acquisition_mode",
            "candidate_source_mode",
        )
    )
    return any(
        term in provenance
        for term in ("live", "operational", "burn_in", "notify", "research_send")
    )


def _calendar_event_timestamps_invalid(event: Mapping[str, Any]) -> bool:
    return any(
        field in event
        and event.get(field) not in (None, "")
        and _parse_aware_timestamp(event.get(field)) is None
        for field in _CALENDAR_TIMESTAMP_FIELDS
    )


def _calendar_event_claims_invalid(event: Mapping[str, Any]) -> bool:
    """Reject calendar metadata that would otherwise stringify into evidence."""

    if any(
        field in event
        and event.get(field) not in (None, "")
        and not _typed_text(event.get(field))
        for field in _CALENDAR_TEXT_FIELDS
    ):
        return True
    for field, allowed in _CALENDAR_ENUM_FIELDS.items():
        if field not in event or event.get(field) in (None, ""):
            continue
        value = _typed_text(event.get(field)).casefold()
        if not value or value not in allowed:
            return True
    if any(
        field in event
        and event.get(field) not in (None, "")
        and not isinstance(event.get(field), str)
        for field in _CALENDAR_TIMESTAMP_FIELDS
    ) or _calendar_event_timestamps_invalid(event):
        return True
    scheduled = next(
        (
            _parse_aware_timestamp(event.get(field))
            for field in ("scheduled_at", "event_start_time", "effective_time")
            if event.get(field) not in (None, "")
        ),
        None,
    )
    window_start = _parse_aware_timestamp(event.get("window_start"))
    window_end = _parse_aware_timestamp(event.get("window_end"))
    if window_start is not None and window_end is not None and window_end < window_start:
        return True
    certainty = _typed_text(event.get("time_certainty")).casefold()
    if certainty == "exact" and scheduled is None:
        return True
    if certainty == "window" and (window_start is None or window_end is None):
        return True
    return False


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
    parts = _component_parts(value)
    if not parts:
        return ()
    out: list[str] = []

    def add(origin: str) -> None:
        if origin not in out:
            out.append(origin)

    for origin, terms in _ORIGIN_COMPONENT_TERMS:
        if _has_unnegated_components(parts, terms):
            add(origin)
    return tuple(out)


def has_unnegated_component_terms(
    values: Iterable[object],
    terms: tuple[str, ...],
) -> bool:
    """Match closed normalized labels without substring or negation upgrades."""

    return any(
        _has_unnegated_components(_component_parts(value), terms)
        for value in values
    )


def _component_parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.strip():
        return ()
    return tuple(
        part
        for part in _COMPONENT_SPLIT.split(value.strip().casefold())
        if part
    )


def _has_unnegated_components(
    value_parts: tuple[str, ...],
    terms: tuple[str, ...],
) -> bool:
    matches: list[tuple[int, int]] = []
    for term in terms:
        term_parts = _component_parts(term)
        width = len(term_parts)
        for index in range(len(value_parts) - width + 1):
            if value_parts[index : index + width] == term_parts:
                matches.append((index, index + width))

    negated_matches = tuple(
        (start, end)
        for start, end in matches
        if start and value_parts[start - 1] in _COMPONENT_NEGATIONS
    )
    return any(
        not any(
            negated_start <= start and end <= negated_end
            for negated_start, negated_end in negated_matches
        )
        for start, end in matches
    )


def _derive_market_phase(data: Mapping[str, Any]) -> str:
    values = _market_classification_values(data)
    for phase, terms in _MARKET_PHASE_COMPONENT_TERMS:
        if has_unnegated_component_terms(values, terms):
            return phase
    return MarketPhase.ACTIVE.value


def _has_market_thesis(data: Mapping[str, Any]) -> bool:
    return bool(_market_label(data) or any(
        ThesisOrigin.MARKET_LED.value in _origins_for_text(value)
        for field in ("source_origin", "source_origins", "source_pack", "source_packs")
        for value in _texts(data.get(field))
    ))


def _has_market_snapshot(data: Mapping[str, Any]) -> bool:
    return any(isinstance(data.get(field), Mapping) and bool(data.get(field)) for field in (
        "latest_market_snapshot", "market_snapshot", "market_state_snapshot"
    ))


def _has_structured_context(data: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    for field in fields:
        if field not in data or data.get(field) in (None, "", {}):
            continue
        value = data.get(field)
        return isinstance(value, Mapping) and bool(value)
    return False


def _has_technical_context(data: Mapping[str, Any]) -> bool:
    if "technical_context" in data and data.get("technical_context") not in (None, "", {}):
        value = data.get("technical_context")
        return isinstance(value, Mapping) and bool(value)
    return bool(_typed_text(data.get("technical_setup_type")))


def _market_label(data: Mapping[str, Any]) -> str:
    for field in _MARKET_CLASSIFICATION_FIELDS:
        value = _typed_text(data.get(field)).casefold()
        if value:
            return value
    return ""


def market_label(data: Mapping[str, Any]) -> str:
    """Return the first typed market classification without coercing objects."""

    return _market_label(data)


def market_classification_invalid(data: Mapping[str, Any]) -> bool:
    """Detect an explicit non-text market-state classification claim."""

    return any(
        field in data
        and data.get(field) not in (None, "")
        and not _typed_text(data.get(field))
        for field in _MARKET_CLASSIFICATION_FIELDS
    )


def source_classification_invalid(
    data: Mapping[str, Any],
    sources: Iterable[Mapping[str, Any]] = (),
) -> bool:
    """Detect malformed fields that select Decision thesis-origin policy."""

    return any(
        _source_row_invalid(row)
        for row in (data, *(item for item in sources if isinstance(item, Mapping)))
    )


def _market_classification_values(data: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        value
        for field in _MARKET_CLASSIFICATION_FIELDS
        if (value := _typed_text(data.get(field)))
    )


def _typed_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _source_row_invalid(row: Mapping[str, Any]) -> bool:
    for field in _SOURCE_SCALAR_FIELDS:
        if field not in row or row.get(field) in (None, ""):
            continue
        if not _typed_text(row.get(field)):
            return True
    for field in _SOURCE_LIST_FIELDS:
        if field not in row or row.get(field) in (None, "", [], ()):
            continue
        value = row.get(field)
        if not isinstance(value, (list, tuple)) or any(
            not _typed_text(item) for item in value
        ):
            return True
    return False


def _source_scalar_values(row: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = _typed_text(row.get(field))
    return (value,) if value else ()


def _source_list_values(row: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = row.get(field)
    if not isinstance(value, (list, tuple)):
        return ()
    values = tuple(_typed_text(item) for item in value)
    return values if all(values) else ()


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
            # Preserve ordered field authority even when the selected value is
            # invalid.  Falling through would let a legacy alias conceal bad
            # canonical evidence and could make a blocked idea appear usable.
            return _finite_number(row.get(field))
    return None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
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
            if field not in row or row.get(field) in (None, ""):
                continue
            # Preserve ordered clock authority. An explicit malformed higher
            # clock must not borrow a lower alias and manufacture a plausible
            # expiry anchor.
            return _parse_aware_timestamp(row.get(field))
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
    "calendar_context_invalid",
    "configured_route",
    "decision_text_claims_invalid",
    "decision_warnings",
    "directional_bias",
    "fixture_freshness_provenance_invalid",
    "has_calendar_risk",
    "normalize_market_snapshot",
    "market_snapshot",
    "market_snapshot_invalid",
    "market_classification_invalid",
    "market_execution_claims_invalid",
    "market_label",
    "origin_context_invalid",
    "source_classification_invalid",
    "is_suspicious_illiquid",
    "spread_status",
    "thesis_origin_values",
    "timing_profile",
    "timing_context_invalid",
    "timing_state_for_profile",
    "review_copy",
    "uses_market_lane",
    "weighted_actionability",
)
