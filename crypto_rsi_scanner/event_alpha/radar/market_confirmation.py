"""Pure market-confirmation scoring for Event Alpha research hypotheses.

This module turns already-collected market, derivatives, and supply evidence
into a bounded 0-100 confirmation score. It is metadata only: it cannot create
watchlist states, alerts, paper rows, live signal rows, or event-fade triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from ... import config


class MarketConfirmationLevel(str, Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class MarketConfirmationReason(str, Enum):
    PRICE_MOMENTUM = "price_momentum"
    UPSIDE_ATTENTION_REACTION = "upside_attention_reaction"
    DOWNSIDE_REACTION = "downside_reaction"
    VOLUME_EXPANSION = "volume_expansion"
    VOLUME_MCAP_SPIKE = "volume_mcap_spike"
    RELATIVE_STRENGTH_VS_BTC = "relative_strength_vs_btc"
    RELATIVE_STRENGTH_VS_SECTOR = "relative_strength_vs_sector"
    DERIVATIVES_CROWDING = "derivatives_crowding"
    FUNDING_HEATED = "funding_heated"
    OI_EXPANSION = "oi_expansion"
    LIQUIDATIONS_SPIKE = "liquidations_spike"
    LONG_SHORT_CROWDING = "long_short_crowding"
    FUTURES_VOLUME_EXPANSION = "futures_volume_expansion"
    DEX_LIQUIDITY_SANE = "dex_liquidity_sane"
    DEX_VOLUME_SPIKE = "dex_volume_spike"
    NEW_DEX_POOL_DETECTED = "new_dex_pool_detected"
    DEX_LIQUIDITY_FRAGILE = "dex_liquidity_fragile"
    PROTOCOL_TVL_GROWTH = "protocol_tvl_growth"
    PROTOCOL_TVL_OUTFLOW = "protocol_tvl_outflow"
    PROTOCOL_FEES_GROWTH = "protocol_fees_growth"
    PROTOCOL_VOLUME_EXPANSION = "protocol_volume_expansion"
    LIQUIDITY_FRAGILITY = "liquidity_fragility"
    SUPPLY_PRESSURE = "supply_pressure"
    NO_MARKET_REACTION = "no_market_reaction"
    INSUFFICIENT_DATA = "insufficient_data"
    MARKET_CONTEXT_FRESH = "market_context_fresh"
    MARKET_CONTEXT_STALE_CAPPED = "market_context_stale_capped"
    FIXTURE_MARKET_CONTEXT_ALLOWED = "fixture_market_context_allowed"
    MARKET_CONTEXT_MISSING = "market_context_missing"
    MARKET_CONTEXT_UNKNOWN_TIMESTAMP = "market_context_unknown_timestamp"


@dataclass(frozen=True)
class EventMarketConfirmationInput:
    market_snapshot: Mapping[str, Any] | None = None
    market_anomaly_row: Mapping[str, Any] | None = None
    watchlist_market_row: Mapping[str, Any] | None = None
    derivatives_snapshot: Mapping[str, Any] | None = None
    dex_liquidity_snapshot: Mapping[str, Any] | None = None
    protocol_metrics_snapshot: Mapping[str, Any] | None = None
    supply_snapshot: Mapping[str, Any] | None = None
    btc_context: Mapping[str, Any] | None = None
    sector_benchmark: Mapping[str, Any] | None = None
    event_time: datetime | str | None = None
    playbook_type: str | None = None
    impact_category: str | None = None
    now: datetime | str | None = None
    market_context_observed_at: datetime | str | None = None
    market_context_source: str | None = None
    market_context_max_age_hours: float | None = None
    allow_stale_fixture_market_context: bool | None = None
    stale_cap_level: str | None = None


@dataclass(frozen=True)
class EventMarketConfirmationResult:
    market_confirmation_score: float
    level: str
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    data_quality: float = 0.0
    missing_fields: tuple[str, ...] = ()
    confirmation_summary: str = ""
    score_components: Mapping[str, float] = field(default_factory=dict)
    market_context_observed_at: str | None = None
    market_context_age_seconds: float | None = None
    market_context_age_hours: float | None = None
    market_context_stale: bool = False
    market_context_freshness_status: str = ""
    market_context_source: str | None = None
    freshness_cap_applied: bool = False
    derivatives_confirmation_score: float = 0.0
    derivatives_confirmation_level: str = MarketConfirmationLevel.NONE.value
    derivatives_confirmation_reasons: tuple[str, ...] = ()
    derivatives_freshness_status: str = "missing"
    dex_liquidity_score: float = 0.0
    dex_liquidity_level: str = MarketConfirmationLevel.NONE.value
    dex_liquidity_reasons: tuple[str, ...] = ()
    dex_freshness_status: str = "missing"
    protocol_metrics_score: float = 0.0
    protocol_metrics_level: str = MarketConfirmationLevel.NONE.value
    protocol_metrics_reasons: tuple[str, ...] = ()
    protocol_metrics_freshness_status: str = "missing"


@dataclass(frozen=True)
class _MarketConfirmationContext:
    data: EventMarketConfirmationInput
    market: Mapping[str, Any]
    derivatives: Mapping[str, Any]
    dex: Mapping[str, Any]
    protocol: Mapping[str, Any]
    supply: Mapping[str, Any]
    btc: Mapping[str, Any]
    sector: Mapping[str, Any]
    playbook: str
    freshness: Mapping[str, Any]
    derivatives_freshness: Mapping[str, Any]
    dex_freshness: Mapping[str, Any]
    protocol_freshness: Mapping[str, Any]


@dataclass(frozen=True)
class _SupplementalConfirmation:
    derivative_components: dict[str, float]
    derivative_reasons: list[str]
    derivative_score: float
    dex_components: dict[str, float]
    dex_reasons: list[str]
    dex_score: float
    dex_illiquid: bool
    protocol_components: dict[str, float]
    protocol_reasons: list[str]
    protocol_score: float


def evaluate_market_confirmation(
    data: EventMarketConfirmationInput | Mapping[str, Any] | None,
) -> EventMarketConfirmationResult:
    """Score visible market reaction for a research hypothesis."""
    if data is None:
        return _insufficient(("market_snapshot", "market_anomaly_row"))
    if isinstance(data, Mapping):
        data = _input_from_mapping(data)
    context = _market_confirmation_context(data)

    components: dict[str, float] = {}
    reasons: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []
    observed_fields = _apply_primary_market_components(context, components, reasons, missing)
    supplemental, supplemental_observed = _apply_supplemental_market_components(
        context,
        components,
        reasons,
        warnings,
        missing,
    )
    observed_fields += supplemental_observed
    observed_fields += _apply_market_anomaly_score(context.market, components)

    raw_score = sum(components.values())
    if _market_anomaly_without_catalyst(context.playbook, data):
        raw_score = min(raw_score, 35.0)
        warnings.append("market_anomaly_without_confirmed_catalyst")

    raw_score = _apply_playbook_score_adjustments(raw_score, context, supplemental, reasons, warnings, missing)

    score = max(0.0, min(100.0, raw_score))
    if observed_fields == 0:
        return _insufficient_with_freshness(
            tuple(dict.fromkeys(missing or ("market_snapshot", "derivatives_snapshot"))),
            context.freshness,
        )
    if not reasons:
        reasons.append(MarketConfirmationReason.NO_MARKET_REACTION.value)
    data_quality = min(100.0, observed_fields * 16.0)
    if score > 50 and data_quality < 35:
        score = min(score, 50.0)
        warnings.append("market_confirmation_capped_by_sparse_data")
    score = _apply_market_freshness_cap(score, data, context.freshness, reasons, warnings, missing)
    level = _level(score)
    summary = _summary(level, score, reasons)
    return _market_confirmation_result(
        score=score,
        level=level,
        reasons=reasons,
        warnings=warnings,
        data_quality=data_quality,
        missing=missing,
        summary=summary,
        components=components,
        context=context,
        supplemental=supplemental,
    )


def _input_from_mapping(data: Mapping[str, Any]) -> EventMarketConfirmationInput:
    return EventMarketConfirmationInput(
        market_snapshot=_mapping(data.get("market") or data.get("market_snapshot") or data),
        market_anomaly_row=_mapping(data.get("anomaly") or data.get("market_anomaly")),
        watchlist_market_row=_mapping(data.get("watchlist_market") or data.get("watchlist_market_row")),
        derivatives_snapshot=_mapping(data.get("derivatives") or data.get("derivatives_snapshot")),
        dex_liquidity_snapshot=_mapping(data.get("dex_liquidity") or data.get("dex_liquidity_snapshot") or data.get("dex")),
        protocol_metrics_snapshot=_mapping(
            data.get("protocol_metrics")
            or data.get("protocol_metrics_snapshot")
            or data.get("defillama")
            or data.get("protocol")
        ),
        supply_snapshot=_mapping(data.get("supply")),
        btc_context=_mapping(data.get("btc_context")),
        sector_benchmark=_mapping(data.get("sector_benchmark")),
        playbook_type=str(data.get("playbook_type") or data.get("playbook") or ""),
        impact_category=str(data.get("impact_category") or ""),
        now=data.get("now"),
        market_context_observed_at=data.get("market_context_observed_at") or data.get("market_context_timestamp"),
        market_context_source=str(data.get("market_context_source") or "") or None,
        market_context_max_age_hours=_float(data.get("market_context_max_age_hours"))
        or config.EVENT_MARKET_CONTEXT_MAX_AGE_HOURS,
        allow_stale_fixture_market_context=bool(
            data.get("allow_stale_fixture_market_context")
            if data.get("allow_stale_fixture_market_context") is not None
            else config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE
        ),
        stale_cap_level=str(data.get("stale_cap_level") or "") or None,
    )


def _market_confirmation_context(data: EventMarketConfirmationInput) -> _MarketConfirmationContext:
    market = _merge_mappings(data.market_snapshot, data.market_anomaly_row, data.watchlist_market_row)
    derivatives = _mapping(data.derivatives_snapshot)
    dex = _mapping(data.dex_liquidity_snapshot)
    protocol = _mapping(data.protocol_metrics_snapshot)
    return _MarketConfirmationContext(
        data=data,
        market=market,
        derivatives=derivatives,
        dex=dex,
        protocol=protocol,
        supply=_mapping(data.supply_snapshot),
        btc=_mapping(data.btc_context),
        sector=_mapping(data.sector_benchmark),
        playbook=str(data.playbook_type or data.impact_category or "").casefold(),
        freshness=_market_context_freshness(data, market),
        derivatives_freshness=_snapshot_freshness(data, derivatives, family="derivatives"),
        dex_freshness=_snapshot_freshness(data, dex, family="dex"),
        protocol_freshness=_snapshot_freshness(data, protocol, family="protocol"),
    )


def _apply_primary_market_components(
    context: _MarketConfirmationContext,
    components: dict[str, float],
    reasons: list[str],
    missing: list[str],
) -> int:
    observed_fields = 0
    market = context.market
    return_24h = _percent_value(_first(market, "return_24h", "price_change_24h", "price_change_percentage_24h"))
    return_72h = _percent_value(_first(market, "return_72h", "price_change_72h", "return_3d"))
    return_7d = _percent_value(_first(market, "return_7d", "price_change_7d", "price_change_percentage_7d"))
    momentum = 0.0
    if return_24h is not None:
        observed_fields += 1
        if abs(return_24h) >= 25:
            momentum = max(momentum, min(45.0, 20.0 + abs(return_24h) * 0.35))
    if return_72h is not None:
        observed_fields += 1
        if abs(return_72h) >= 50:
            momentum = max(momentum, min(45.0, 25.0 + abs(return_72h) * 0.25))
    if return_7d is not None:
        observed_fields += 1
        if abs(return_7d) >= 80:
            momentum = max(momentum, min(40.0, 20.0 + abs(return_7d) * 0.15))
    if momentum:
        components["price_momentum"] = momentum
        reasons.append(MarketConfirmationReason.PRICE_MOMENTUM.value)
        if return_24h is not None:
            if return_24h > 0 and _playbook_needs_attention(context.playbook):
                components["upside_attention_reaction"] = min(10.0, 3.0 + return_24h * 0.10)
                reasons.append(MarketConfirmationReason.UPSIDE_ATTENTION_REACTION.value)
            if return_24h < 0 and _playbook_needs_downside(context.playbook):
                components["downside_reaction"] = min(14.0, 4.0 + abs(return_24h) * 0.16)
                reasons.append(MarketConfirmationReason.DOWNSIDE_REACTION.value)
    else:
        missing.append("large_price_move")
        if return_24h is not None and return_24h <= -15 and _playbook_needs_downside(context.playbook):
            components["downside_reaction"] = min(14.0, 4.0 + abs(return_24h) * 0.16)
            reasons.append(MarketConfirmationReason.DOWNSIDE_REACTION.value)
    observed_fields += _apply_volume_components(market, components, reasons, missing)
    observed_fields += _apply_relative_strength_components(context, return_24h, components, reasons)
    return observed_fields


def _apply_volume_components(
    market: Mapping[str, Any],
    components: dict[str, float],
    reasons: list[str],
    missing: list[str],
) -> int:
    observed_fields = 0
    volume_z = _float(_first(market, "volume_zscore_24h", "volume_zscore", "volume_z"))
    if volume_z is not None:
        observed_fields += 1
        if volume_z > 2:
            components["volume_expansion"] = min(30.0, 12.0 + volume_z * 6.0)
            reasons.append(MarketConfirmationReason.VOLUME_EXPANSION.value)
    else:
        missing.append("volume_zscore")
    volume_mcap = _float(_first(market, "volume_to_market_cap", "volume_mcap", "volume_mcap_ratio"))
    if volume_mcap is None:
        volume = _float(_first(market, "volume_24h", "spot_volume_24h", "total_volume"))
        market_cap = _float(_first(market, "market_cap", "mcap"))
        if volume is not None and market_cap and market_cap > 0:
            volume_mcap = volume / market_cap
    if volume_mcap is not None:
        observed_fields += 1
        if volume_mcap >= 0.20:
            components["volume_mcap_spike"] = min(25.0, 8.0 + volume_mcap * 45.0)
            reasons.append(MarketConfirmationReason.VOLUME_MCAP_SPIKE.value)
    else:
        missing.append("volume_mcap")
    return observed_fields


def _apply_relative_strength_components(
    context: _MarketConfirmationContext,
    return_24h: float | None,
    components: dict[str, float],
    reasons: list[str],
) -> int:
    observed_fields = 0
    rel_btc = _percent_value(_first(context.market, "relative_strength_vs_btc", "btc_relative_return"))
    if rel_btc is None and return_24h is not None:
        btc_return = _percent_value(_first(context.btc, "return_24h", "btc_return_24h"))
        if btc_return is not None:
            rel_btc = return_24h - btc_return
    if rel_btc is not None:
        observed_fields += 1
        if rel_btc >= 15:
            components["relative_strength_vs_btc"] = min(18.0, 6.0 + rel_btc * 0.45)
            reasons.append(MarketConfirmationReason.RELATIVE_STRENGTH_VS_BTC.value)
    rel_sector = _percent_value(_first(context.market, "relative_strength_vs_sector", "sector_relative_return"))
    if rel_sector is None and return_24h is not None:
        sector_return = _percent_value(_first(context.sector, "return_24h", "sector_return_24h"))
        if sector_return is not None:
            rel_sector = return_24h - sector_return
    if rel_sector is not None and rel_sector >= 15:
        observed_fields += 1
        components["relative_strength_vs_sector"] = min(15.0, 5.0 + rel_sector * 0.35)
        reasons.append(MarketConfirmationReason.RELATIVE_STRENGTH_VS_SECTOR.value)
    return observed_fields


def _apply_supplemental_market_components(
    context: _MarketConfirmationContext,
    components: dict[str, float],
    reasons: list[str],
    warnings: list[str],
    missing: list[str],
) -> tuple[_SupplementalConfirmation, int]:
    observed_fields = 0
    derivative_components, derivative_reasons, derivative_observed = _derivatives_components(context.derivatives)
    observed_fields += _apply_fresh_or_missing_components(
        "derivatives",
        context.derivatives_freshness,
        derivative_components,
        derivative_reasons,
        derivative_observed,
        context.playbook,
        components,
        reasons,
        warnings,
        missing,
    )
    observed_fields += _apply_liquidity_and_supply_components(context, components, reasons)
    dex_components, dex_reasons, dex_observed, dex_illiquid = _dex_components(context.dex)
    observed_fields += _apply_fresh_or_missing_components(
        "dex",
        context.dex_freshness,
        dex_components,
        dex_reasons,
        dex_observed,
        context.playbook,
        components,
        reasons,
        warnings,
        missing,
    )
    protocol_components, protocol_reasons, protocol_observed = _protocol_components(context.protocol, playbook=context.playbook)
    observed_fields += _apply_fresh_or_missing_components(
        "protocol",
        context.protocol_freshness,
        protocol_components,
        protocol_reasons,
        protocol_observed,
        context.playbook,
        components,
        reasons,
        warnings,
        missing,
    )
    return (
        _SupplementalConfirmation(
            derivative_components=derivative_components,
            derivative_reasons=derivative_reasons,
            derivative_score=_sub_confirmation_score(derivative_components),
            dex_components=dex_components,
            dex_reasons=dex_reasons,
            dex_score=_sub_confirmation_score(dex_components),
            dex_illiquid=dex_illiquid,
            protocol_components=protocol_components,
            protocol_reasons=protocol_reasons,
            protocol_score=_sub_confirmation_score(protocol_components),
        ),
        observed_fields,
    )


def _apply_fresh_or_missing_components(
    family: str,
    freshness: Mapping[str, Any],
    family_components: dict[str, float],
    family_reasons: list[str],
    observed: int,
    playbook: str,
    components: dict[str, float],
    reasons: list[str],
    warnings: list[str],
    missing: list[str],
) -> int:
    if freshness["status"] in {"fresh", "fixture_allowed_stale"}:
        components.update(family_components)
        reasons.extend(family_reasons)
    elif observed:
        warnings.append(f"{family}_context_{freshness['status']}")
        if _playbook_needs_family(playbook, family):
            missing.append(f"needs_fresh_{_family_missing_label(family)}_confirmation")
    elif _playbook_needs_family(playbook, family):
        missing.append(f"{_family_missing_label(family)}_provider_coverage")
    return observed if observed else 0


def _apply_liquidity_and_supply_components(
    context: _MarketConfirmationContext,
    components: dict[str, float],
    reasons: list[str],
) -> int:
    observed_fields = 0
    liquidity_fragility = _score_like(_first(context.market, "liquidity_fragility", "thin_book_score"))
    if liquidity_fragility is not None and liquidity_fragility >= 50:
        observed_fields += 1
        components["liquidity_fragility"] = min(12.0, liquidity_fragility * 0.15)
        reasons.append(MarketConfirmationReason.LIQUIDITY_FRAGILITY.value)
    supply_pressure = _score_like(_first(context.supply, "supply_pressure", "unlock_pressure", "unlock_pressure_score"))
    if supply_pressure is not None:
        observed_fields += 1
        if supply_pressure >= 40:
            components["supply_pressure"] = min(18.0, supply_pressure * 0.22)
            reasons.append(MarketConfirmationReason.SUPPLY_PRESSURE.value)
    return observed_fields


def _apply_market_anomaly_score(market: Mapping[str, Any], components: dict[str, float]) -> int:
    anomaly_score = _score_like(_first(market, "anomaly_score", "score"))
    if anomaly_score is None:
        return 0
    components["market_anomaly_score"] = min(25.0, anomaly_score * 0.25)
    return 1


def _apply_playbook_score_adjustments(
    raw_score: float,
    context: _MarketConfirmationContext,
    supplemental: _SupplementalConfirmation,
    reasons: list[str],
    warnings: list[str],
    missing: list[str],
) -> float:
    if _playbook_needs_derivatives(context.playbook) and any(
        reason in reasons
        for reason in (
            MarketConfirmationReason.DERIVATIVES_CROWDING.value,
            MarketConfirmationReason.FUNDING_HEATED.value,
            MarketConfirmationReason.OI_EXPANSION.value,
            MarketConfirmationReason.FUTURES_VOLUME_EXPANSION.value,
        )
    ):
        raw_score += 8.0
    if _playbook_needs_supply(context.playbook) and MarketConfirmationReason.SUPPLY_PRESSURE.value in reasons:
        raw_score += 8.0
    if (
        _playbook_needs_attention(context.playbook)
        and MarketConfirmationReason.PRICE_MOMENTUM.value in reasons
        and MarketConfirmationReason.VOLUME_EXPANSION.value in reasons
    ):
        raw_score += 8.0
    if _playbook_needs_attention(context.playbook) and supplemental.dex_score >= 50:
        raw_score += 6.0
    if _playbook_needs_protocol_metrics(context.playbook) and supplemental.protocol_score >= 50:
        raw_score += 7.0
    if supplemental.dex_illiquid and _playbook_needs_liquidity(context.playbook):
        raw_score = min(raw_score, 74.0)
        warnings.append("dex_liquidity_sanity_cap")
        missing.append("liquidity_sanity")
    return raw_score


def _apply_market_freshness_cap(
    score: float,
    data: EventMarketConfirmationInput,
    freshness: Mapping[str, Any],
    reasons: list[str],
    warnings: list[str],
    missing: list[str],
) -> float:
    if freshness["status"] == "fresh":
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_FRESH.value)
    elif freshness["status"] == "fixture_allowed_stale":
        reasons.append(MarketConfirmationReason.FIXTURE_MARKET_CONTEXT_ALLOWED.value)
        warnings.append("fixture_market_context_allowed_stale")
    elif freshness["status"] == "stale":
        score = min(score, _cap_score_for_level(data.stale_cap_level or config.EVENT_MARKET_CONTEXT_STALE_CAP_LEVEL))
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_STALE_CAPPED.value)
        warnings.append("market_context_stale_capped")
        if "needs_fresh_market_confirmation" not in missing:
            missing.append("needs_fresh_market_confirmation")
    elif freshness["status"] == "missing":
        score = min(score, _cap_score_for_level("none"))
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_MISSING.value)
        warnings.append("market_context_missing")
        missing.append("market_context_missing")
        missing.append("needs_fresh_market_confirmation")
    elif freshness["status"] == "unknown":
        score = min(score, _cap_score_for_level(data.stale_cap_level or config.EVENT_MARKET_CONTEXT_STALE_CAP_LEVEL))
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_UNKNOWN_TIMESTAMP.value)
        warnings.append("market_context_unknown_timestamp")
        missing.append("market_context_unknown_timestamp")
        missing.append("needs_fresh_market_confirmation")
    return score


def _market_confirmation_result(
    *,
    score: float,
    level: str,
    reasons: list[str],
    warnings: list[str],
    data_quality: float,
    missing: list[str],
    summary: str,
    components: dict[str, float],
    context: _MarketConfirmationContext,
    supplemental: _SupplementalConfirmation,
) -> EventMarketConfirmationResult:
    return _with_freshness(EventMarketConfirmationResult(
        market_confirmation_score=round(score, 2),
        level=level,
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        data_quality=round(data_quality, 2),
        missing_fields=tuple(dict.fromkeys(missing)),
        confirmation_summary=summary,
        score_components={key: round(value, 2) for key, value in components.items()},
        freshness_cap_applied=context.freshness["status"] in {"stale", "missing", "unknown"},
        derivatives_confirmation_score=round(supplemental.derivative_score, 2),
        derivatives_confirmation_level=_level(supplemental.derivative_score),
        derivatives_confirmation_reasons=tuple(dict.fromkeys(supplemental.derivative_reasons)),
        derivatives_freshness_status=str(context.derivatives_freshness.get("status") or "missing"),
        dex_liquidity_score=round(supplemental.dex_score, 2),
        dex_liquidity_level=_level(supplemental.dex_score),
        dex_liquidity_reasons=tuple(dict.fromkeys(supplemental.dex_reasons)),
        dex_freshness_status=str(context.dex_freshness.get("status") or "missing"),
        protocol_metrics_score=round(supplemental.protocol_score, 2),
        protocol_metrics_level=_level(supplemental.protocol_score),
        protocol_metrics_reasons=tuple(dict.fromkeys(supplemental.protocol_reasons)),
        protocol_metrics_freshness_status=str(context.protocol_freshness.get("status") or "missing"),
    ), context.freshness)


def _insufficient(missing: tuple[str, ...]) -> EventMarketConfirmationResult:
    return EventMarketConfirmationResult(
        market_confirmation_score=0.0,
        level=MarketConfirmationLevel.NONE.value,
        reasons=(MarketConfirmationReason.INSUFFICIENT_DATA.value,),
        warnings=("insufficient_market_data",),
        data_quality=0.0,
        missing_fields=missing,
        confirmation_summary="insufficient market data",
    )


def _insufficient_with_freshness(missing: tuple[str, ...], freshness: Mapping[str, Any]) -> EventMarketConfirmationResult:
    result = _insufficient(missing)
    reasons = list(result.reasons)
    warnings = list(result.warnings)
    missing_fields = list(result.missing_fields)
    status = str(freshness.get("status") or "unknown")
    if status == "fresh":
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_FRESH.value)
    elif status == "fixture_allowed_stale":
        reasons.append(MarketConfirmationReason.FIXTURE_MARKET_CONTEXT_ALLOWED.value)
        warnings.append("fixture_market_context_allowed_stale")
    elif status == "stale":
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_STALE_CAPPED.value)
        warnings.append("market_context_stale_capped")
        missing_fields.append("needs_fresh_market_confirmation")
    elif status == "missing":
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_MISSING.value)
        warnings.append("market_context_missing")
        missing_fields.append("market_context_missing")
        missing_fields.append("needs_fresh_market_confirmation")
    else:
        reasons.append(MarketConfirmationReason.MARKET_CONTEXT_UNKNOWN_TIMESTAMP.value)
        warnings.append("market_context_unknown_timestamp")
        missing_fields.append("market_context_unknown_timestamp")
        missing_fields.append("needs_fresh_market_confirmation")
    return _with_freshness(
        EventMarketConfirmationResult(
            market_confirmation_score=result.market_confirmation_score,
            level=result.level,
            reasons=tuple(dict.fromkeys(reasons)),
            warnings=tuple(dict.fromkeys(warnings)),
            data_quality=result.data_quality,
            missing_fields=tuple(dict.fromkeys(missing_fields)),
            confirmation_summary=result.confirmation_summary,
            score_components=result.score_components,
            freshness_cap_applied=status in {"stale", "missing", "unknown"},
        ),
        freshness,
    )


def _with_freshness(
    result: EventMarketConfirmationResult,
    freshness: Mapping[str, Any],
) -> EventMarketConfirmationResult:
    return EventMarketConfirmationResult(
        market_confirmation_score=result.market_confirmation_score,
        level=result.level,
        reasons=result.reasons,
        warnings=result.warnings,
        data_quality=result.data_quality,
        missing_fields=result.missing_fields,
        confirmation_summary=result.confirmation_summary,
        score_components=result.score_components,
        market_context_observed_at=freshness.get("observed_at"),
        market_context_age_seconds=_round_optional(freshness.get("age_seconds")),
        market_context_age_hours=_round_optional(freshness.get("age_hours")),
        market_context_stale=bool(freshness.get("stale")),
        market_context_freshness_status=str(freshness.get("status") or "unknown"),
        market_context_source=str(freshness.get("source") or "") or None,
        freshness_cap_applied=bool(result.freshness_cap_applied or freshness.get("cap_applied")),
        derivatives_confirmation_score=result.derivatives_confirmation_score,
        derivatives_confirmation_level=result.derivatives_confirmation_level,
        derivatives_confirmation_reasons=result.derivatives_confirmation_reasons,
        derivatives_freshness_status=result.derivatives_freshness_status,
        dex_liquidity_score=result.dex_liquidity_score,
        dex_liquidity_level=result.dex_liquidity_level,
        dex_liquidity_reasons=result.dex_liquidity_reasons,
        dex_freshness_status=result.dex_freshness_status,
        protocol_metrics_score=result.protocol_metrics_score,
        protocol_metrics_level=result.protocol_metrics_level,
        protocol_metrics_reasons=result.protocol_metrics_reasons,
        protocol_metrics_freshness_status=result.protocol_metrics_freshness_status,
    )


def _level(score: float) -> str:
    if score >= 75:
        return MarketConfirmationLevel.STRONG.value
    if score >= 50:
        return MarketConfirmationLevel.MODERATE.value
    if score >= 25:
        return MarketConfirmationLevel.WEAK.value
    return MarketConfirmationLevel.NONE.value


def _summary(level: str, score: float, reasons: list[str]) -> str:
    label = ", ".join(reason.replace("_", " ") for reason in reasons[:3]) or "no market reaction"
    return f"{level} market confirmation ({score:.0f}/100): {label}"


def _market_context_freshness(data: EventMarketConfirmationInput, market: Mapping[str, Any]) -> dict[str, Any]:
    source = str(
        data.market_context_source
        or _first(market, "market_context_source", "watchlist_market_source", "source", "provider")
        or ""
    ).strip()
    observed_raw = (
        data.market_context_observed_at
        or _first(
            market,
            "market_context_observed_at",
            "market_context_timestamp",
            "timestamp",
            "market_timestamp",
            "observed_at",
            "fetched_at",
            "updated_at",
        )
    )
    now = _parse_datetime(data.now) or datetime.now(timezone.utc)
    now = _as_utc(now)
    if not market:
        return {
            "status": "missing",
            "source": source or "missing",
            "observed_at": None,
            "age_seconds": None,
            "age_hours": None,
            "stale": False,
            "cap_applied": True,
        }
    observed = _parse_datetime(observed_raw)
    if observed is None:
        return {
            "status": "unknown",
            "source": source or "unknown",
            "observed_at": None,
            "age_seconds": None,
            "age_hours": None,
            "stale": False,
            "cap_applied": True,
        }
    observed = _as_utc(observed)
    age_seconds = max(0.0, (now - observed).total_seconds())
    max_age_hours = (
        data.market_context_max_age_hours
        if data.market_context_max_age_hours is not None
        else config.EVENT_MARKET_CONTEXT_MAX_AGE_HOURS
    )
    max_age = max(0.0, float(max_age_hours or 0.0)) * 3600.0
    stale = max_age > 0 and age_seconds > max_age
    fixture_like = _fixture_like_source(source, market)
    allow_stale_fixture = (
        data.allow_stale_fixture_market_context
        if data.allow_stale_fixture_market_context is not None
        else config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE
    )
    if stale and fixture_like and allow_stale_fixture:
        status = "fixture_allowed_stale"
    elif stale:
        status = "stale"
    else:
        status = "fresh"
    return {
        "status": status,
        "source": source or ("fixture" if fixture_like else "market_context"),
        "observed_at": observed.isoformat(),
        "age_seconds": age_seconds,
        "age_hours": age_seconds / 3600.0,
        "stale": stale,
        "cap_applied": status in {"stale", "missing", "unknown"},
    }


def _snapshot_freshness(
    data: EventMarketConfirmationInput,
    row: Mapping[str, Any],
    *,
    family: str,
) -> dict[str, Any]:
    source = str(
        _first(
            row,
            f"{family}_context_source",
            f"{family}_source",
            "source",
            "provider",
            "provider_name",
        )
        or ""
    ).strip()
    if not row:
        return {
            "status": "missing",
            "source": source or "missing",
            "observed_at": None,
            "age_seconds": None,
            "age_hours": None,
            "stale": False,
            "cap_applied": True,
        }
    observed_raw = _first(
        row,
        f"{family}_context_observed_at",
        f"{family}_timestamp",
        "timestamp",
        "observed_at",
        "fetched_at",
        "updated_at",
    )
    now = _as_utc(_parse_datetime(data.now) or datetime.now(timezone.utc))
    observed = _parse_datetime(observed_raw)
    fixture_like = _fixture_like_source(source, row)
    allow_stale_fixture = (
        data.allow_stale_fixture_market_context
        if data.allow_stale_fixture_market_context is not None
        else config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE
    )
    if observed is None:
        if fixture_like and allow_stale_fixture:
            return {
                "status": "fixture_allowed_stale",
                "source": source or "fixture",
                "observed_at": None,
                "age_seconds": None,
                "age_hours": None,
                "stale": False,
                "cap_applied": False,
            }
        return {
            "status": "unknown",
            "source": source or "unknown",
            "observed_at": None,
            "age_seconds": None,
            "age_hours": None,
            "stale": False,
            "cap_applied": True,
        }
    observed = _as_utc(observed)
    age_seconds = max(0.0, (now - observed).total_seconds())
    max_age_hours = (
        data.market_context_max_age_hours
        if data.market_context_max_age_hours is not None
        else config.EVENT_MARKET_CONTEXT_MAX_AGE_HOURS
    )
    max_age = max(0.0, float(max_age_hours or 0.0)) * 3600.0
    stale = max_age > 0 and age_seconds > max_age
    if stale and fixture_like and allow_stale_fixture:
        status = "fixture_allowed_stale"
    elif stale:
        status = "stale"
    else:
        status = "fresh"
    return {
        "status": status,
        "source": source or ("fixture" if fixture_like else f"{family}_context"),
        "observed_at": observed.isoformat(),
        "age_seconds": age_seconds,
        "age_hours": age_seconds / 3600.0,
        "stale": stale,
        "cap_applied": status in {"stale", "missing", "unknown"},
    }


def _derivatives_components(row: Mapping[str, Any]) -> tuple[dict[str, float], list[str], int]:
    components: dict[str, float] = {}
    reasons: list[str] = []
    observed = 0
    crowding = _score_like(_first(row, "derivatives_crowding", "crowding_score", "open_interest_crowding"))
    oi_change = _percent_value(_first(row, "open_interest_24h_change_pct", "open_interest_change", "oi_change_24h", "oi_24h_change"))
    funding = _percent_value(_first(row, "funding_rate_8h", "funding_rate", "funding"))
    liquidations = _float(_first(row, "liquidations_24h", "liquidation_volume", "liquidation_volume_24h"))
    long_short = _float(_first(row, "long_short_ratio", "long_short"))
    futures_volume = _float(_first(row, "futures_volume_24h", "perp_volume_24h", "derivatives_volume_24h"))
    if crowding is not None:
        observed += 1
        if crowding >= 50:
            components["derivatives_crowding"] = min(25.0, crowding * 0.25)
            reasons.append(MarketConfirmationReason.DERIVATIVES_CROWDING.value)
    if oi_change is not None:
        observed += 1
        if oi_change >= 25:
            components["oi_expansion"] = min(20.0, 8.0 + oi_change * 0.25)
            reasons.append(MarketConfirmationReason.OI_EXPANSION.value)
    if funding is not None:
        observed += 1
        if abs(funding) >= 0.05:
            components["funding_heated"] = min(12.0, 6.0 + abs(funding) * 30.0)
            reasons.append(MarketConfirmationReason.FUNDING_HEATED.value)
    if liquidations is not None:
        observed += 1
        if liquidations >= 1_000_000:
            components["liquidations_spike"] = min(14.0, 5.0 + liquidations / 1_000_000.0)
            reasons.append(MarketConfirmationReason.LIQUIDATIONS_SPIKE.value)
    if long_short is not None:
        observed += 1
        if long_short >= 1.8 or long_short <= 0.55:
            components["long_short_crowding"] = min(10.0, 4.0 + abs(long_short - 1.0) * 5.0)
            reasons.append(MarketConfirmationReason.LONG_SHORT_CROWDING.value)
    if futures_volume is not None:
        observed += 1
        if futures_volume >= 5_000_000:
            components["futures_volume_expansion"] = min(14.0, 4.0 + futures_volume / 2_000_000.0)
            reasons.append(MarketConfirmationReason.FUTURES_VOLUME_EXPANSION.value)
    return components, reasons, observed


def _dex_components(row: Mapping[str, Any]) -> tuple[dict[str, float], list[str], int, bool]:
    components: dict[str, float] = {}
    reasons: list[str] = []
    observed = 0
    pool_liquidity = _float(_first(row, "pool_liquidity_usd", "liquidity_usd", "reserve_usd"))
    dex_volume = _float(_first(row, "dex_volume_24h", "volume_24h", "pool_volume_24h"))
    volume_z = _float(_first(row, "dex_volume_zscore_24h", "volume_zscore_24h", "volume_zscore"))
    pool_age = _float(_first(row, "pool_age_hours", "age_hours"))
    price_impact = _percent_value(_first(row, "price_impact_2pct", "price_impact", "spread_bps"))
    new_pool = bool(row.get("new_pool") or row.get("new_pool_detected"))
    illiquid = False
    if pool_liquidity is not None:
        observed += 1
        if pool_liquidity >= 250_000:
            components["dex_liquidity_sane"] = min(16.0, 6.0 + pool_liquidity / 150_000.0)
            reasons.append(MarketConfirmationReason.DEX_LIQUIDITY_SANE.value)
        elif pool_liquidity < 100_000:
            illiquid = True
            components["dex_liquidity_fragile"] = 4.0
            reasons.append(MarketConfirmationReason.DEX_LIQUIDITY_FRAGILE.value)
    if dex_volume is not None:
        observed += 1
        if dex_volume >= 250_000:
            components["dex_volume_spike"] = min(18.0, 6.0 + dex_volume / 150_000.0)
            reasons.append(MarketConfirmationReason.DEX_VOLUME_SPIKE.value)
    if volume_z is not None:
        observed += 1
        if volume_z >= 2.5:
            components["dex_volume_zscore"] = min(14.0, 5.0 + volume_z * 3.0)
            if MarketConfirmationReason.DEX_VOLUME_SPIKE.value not in reasons:
                reasons.append(MarketConfirmationReason.DEX_VOLUME_SPIKE.value)
    if pool_age is not None:
        observed += 1
        if pool_age <= 72:
            components["new_dex_pool"] = 8.0
            reasons.append(MarketConfirmationReason.NEW_DEX_POOL_DETECTED.value)
    if new_pool:
        observed += 1
        components["new_dex_pool"] = max(components.get("new_dex_pool", 0.0), 8.0)
        reasons.append(MarketConfirmationReason.NEW_DEX_POOL_DETECTED.value)
    if price_impact is not None:
        observed += 1
        if price_impact >= 5 or price_impact >= 500:
            illiquid = True
            components["dex_liquidity_fragile"] = max(components.get("dex_liquidity_fragile", 0.0), 5.0)
            if MarketConfirmationReason.DEX_LIQUIDITY_FRAGILE.value not in reasons:
                reasons.append(MarketConfirmationReason.DEX_LIQUIDITY_FRAGILE.value)
    return components, reasons, observed, illiquid


def _protocol_components(row: Mapping[str, Any], *, playbook: str) -> tuple[dict[str, float], list[str], int]:
    components: dict[str, float] = {}
    reasons: list[str] = []
    observed = 0
    tvl_change = _percent_value(_first(row, "tvl_change_24h_pct", "tvl_24h_change_pct", "tvl_change"))
    fees_change = _percent_value(_first(row, "fees_change_24h_pct", "revenue_change_24h_pct", "fees_change"))
    protocol_volume = _float(_first(row, "protocol_dex_volume_24h", "dex_volume_24h", "volume_24h"))
    volume_change = _percent_value(_first(row, "protocol_volume_change_24h_pct", "dex_volume_change_24h_pct"))
    tvl = _float(_first(row, "tvl", "tvl_usd", "total_value_locked"))
    fees = _float(_first(row, "fees_24h", "revenue_24h", "protocol_revenue_24h"))
    if tvl is not None:
        observed += 1
    if fees is not None:
        observed += 1
    if tvl_change is not None:
        observed += 1
        if tvl_change >= 8 and not _playbook_needs_downside(playbook):
            components["protocol_tvl_growth"] = min(18.0, 6.0 + tvl_change * 0.35)
            reasons.append(MarketConfirmationReason.PROTOCOL_TVL_GROWTH.value)
        if tvl_change <= -8 and _playbook_needs_downside(playbook):
            components["protocol_tvl_outflow"] = min(20.0, 8.0 + abs(tvl_change) * 0.35)
            reasons.append(MarketConfirmationReason.PROTOCOL_TVL_OUTFLOW.value)
    if fees_change is not None:
        observed += 1
        if fees_change >= 15:
            components["protocol_fees_growth"] = min(16.0, 5.0 + fees_change * 0.25)
            reasons.append(MarketConfirmationReason.PROTOCOL_FEES_GROWTH.value)
    if protocol_volume is not None:
        observed += 1
        if protocol_volume >= 5_000_000:
            components["protocol_volume_expansion"] = min(14.0, 4.0 + protocol_volume / 2_000_000.0)
            reasons.append(MarketConfirmationReason.PROTOCOL_VOLUME_EXPANSION.value)
    if volume_change is not None:
        observed += 1
        if volume_change >= 25:
            components["protocol_volume_change"] = min(12.0, 4.0 + volume_change * 0.20)
            if MarketConfirmationReason.PROTOCOL_VOLUME_EXPANSION.value not in reasons:
                reasons.append(MarketConfirmationReason.PROTOCOL_VOLUME_EXPANSION.value)
    return components, reasons, observed


def _sub_confirmation_score(components: Mapping[str, float]) -> float:
    return max(0.0, min(100.0, sum(max(0.0, float(value or 0.0)) for value in components.values()) * 1.6))


def _cap_score_for_level(level: str) -> float:
    normalized = str(level or "").strip().casefold()
    if normalized == MarketConfirmationLevel.NONE.value:
        return 24.0
    if normalized == MarketConfirmationLevel.MODERATE.value:
        return 74.0
    if normalized == MarketConfirmationLevel.STRONG.value:
        return 100.0
    return 49.0


def _fixture_like_source(source: str, market: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            source,
            market.get("market_context_source"),
            market.get("source"),
            market.get("provider"),
            market.get("fixture"),
        )
    ).casefold()
    return any(term in text for term in ("fixture", "test", "replay", "e2e"))


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _round_optional(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, 4)


def _playbook_needs_attention(playbook: str) -> bool:
    return any(term in playbook for term in ("proxy", "fan", "political", "rwa", "ipo"))


def _playbook_needs_derivatives(playbook: str) -> bool:
    return any(term in playbook for term in ("perp", "squeeze", "listing", "proxy"))


def _playbook_needs_supply(playbook: str) -> bool:
    return any(term in playbook for term in ("unlock", "supply"))


def _playbook_needs_liquidity(playbook: str) -> bool:
    return any(term in playbook for term in ("proxy", "market_anomaly", "microcap", "meme", "dex", "rwa", "ipo"))


def _playbook_needs_protocol_metrics(playbook: str) -> bool:
    return any(term in playbook for term in ("strategic", "protocol", "defi", "security", "exploit", "rune", "aave"))


def _playbook_needs_downside(playbook: str) -> bool:
    return any(term in playbook for term in ("unlock", "supply", "security", "exploit", "regulatory", "shock", "fade"))


def _playbook_needs_family(playbook: str, family: str) -> bool:
    if family == "derivatives":
        return _playbook_needs_derivatives(playbook)
    if family == "dex":
        return _playbook_needs_liquidity(playbook)
    if family == "protocol":
        return _playbook_needs_protocol_metrics(playbook)
    return False


def _family_missing_label(family: str) -> str:
    return {
        "derivatives": "derivatives",
        "dex": "dex_liquidity",
        "protocol": "protocol_metrics",
    }.get(family, family)


def _market_anomaly_without_catalyst(playbook: str, data: EventMarketConfirmationInput) -> bool:
    if "market_anomaly_unknown" in playbook or "market anomaly" in playbook:
        return True
    anomaly = _mapping(data.market_anomaly_row)
    if not anomaly:
        return False
    text = " ".join(str(anomaly.get(key) or "") for key in ("event_type", "relationship_type", "catalyst", "reason"))
    return "catalyst" not in text.casefold()


def _merge_mappings(*rows: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows:
        merged.update(_mapping(row))
    return merged


def _mapping(row: object) -> dict[str, Any]:
    return dict(row) if isinstance(row, Mapping) else {}


def _first(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number


def _percent_value(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if abs(number) <= 3.0:
        return number * 100.0
    return number


def _score_like(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return number * 100.0
    return max(0.0, min(100.0, number))
