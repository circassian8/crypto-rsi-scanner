"""Pure market-confirmation scoring for Event Alpha research hypotheses.

This module turns already-collected market, derivatives, and supply evidence
into a bounded 0-100 confirmation score. It is metadata only: it cannot create
watchlist states, alerts, paper rows, live signal rows, or event-fade triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class MarketConfirmationLevel(str, Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class MarketConfirmationReason(str, Enum):
    PRICE_MOMENTUM = "price_momentum"
    VOLUME_EXPANSION = "volume_expansion"
    VOLUME_MCAP_SPIKE = "volume_mcap_spike"
    RELATIVE_STRENGTH_VS_BTC = "relative_strength_vs_btc"
    RELATIVE_STRENGTH_VS_SECTOR = "relative_strength_vs_sector"
    DERIVATIVES_CROWDING = "derivatives_crowding"
    FUNDING_HEATED = "funding_heated"
    OI_EXPANSION = "oi_expansion"
    LIQUIDITY_FRAGILITY = "liquidity_fragility"
    SUPPLY_PRESSURE = "supply_pressure"
    NO_MARKET_REACTION = "no_market_reaction"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class EventMarketConfirmationInput:
    market_snapshot: Mapping[str, Any] | None = None
    market_anomaly_row: Mapping[str, Any] | None = None
    watchlist_market_row: Mapping[str, Any] | None = None
    derivatives_snapshot: Mapping[str, Any] | None = None
    supply_snapshot: Mapping[str, Any] | None = None
    btc_context: Mapping[str, Any] | None = None
    sector_benchmark: Mapping[str, Any] | None = None
    event_time: datetime | str | None = None
    playbook_type: str | None = None
    impact_category: str | None = None


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


def evaluate_market_confirmation(
    data: EventMarketConfirmationInput | Mapping[str, Any] | None,
) -> EventMarketConfirmationResult:
    """Score visible market reaction for a research hypothesis."""
    if data is None:
        return _insufficient(("market_snapshot", "market_anomaly_row"))
    if isinstance(data, Mapping):
        data = EventMarketConfirmationInput(
            market_snapshot=_mapping(data.get("market") or data.get("market_snapshot") or data),
            market_anomaly_row=_mapping(data.get("anomaly") or data.get("market_anomaly")),
            derivatives_snapshot=_mapping(data.get("derivatives")),
            supply_snapshot=_mapping(data.get("supply")),
            btc_context=_mapping(data.get("btc_context")),
            sector_benchmark=_mapping(data.get("sector_benchmark")),
            playbook_type=str(data.get("playbook_type") or data.get("playbook") or ""),
            impact_category=str(data.get("impact_category") or ""),
        )

    market = _merge_mappings(data.market_snapshot, data.market_anomaly_row, data.watchlist_market_row)
    derivatives = _mapping(data.derivatives_snapshot)
    supply = _mapping(data.supply_snapshot)
    btc = _mapping(data.btc_context)
    sector = _mapping(data.sector_benchmark)
    playbook = str(data.playbook_type or data.impact_category or "").casefold()

    components: dict[str, float] = {}
    reasons: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []
    observed_fields = 0

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
    else:
        missing.append("large_price_move")

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

    rel_btc = _percent_value(_first(market, "relative_strength_vs_btc", "btc_relative_return"))
    if rel_btc is None and return_24h is not None:
        btc_return = _percent_value(_first(btc, "return_24h", "btc_return_24h"))
        if btc_return is not None:
            rel_btc = return_24h - btc_return
    if rel_btc is not None:
        observed_fields += 1
        if rel_btc >= 15:
            components["relative_strength_vs_btc"] = min(18.0, 6.0 + rel_btc * 0.45)
            reasons.append(MarketConfirmationReason.RELATIVE_STRENGTH_VS_BTC.value)

    rel_sector = _percent_value(_first(market, "relative_strength_vs_sector", "sector_relative_return"))
    if rel_sector is None and return_24h is not None:
        sector_return = _percent_value(_first(sector, "return_24h", "sector_return_24h"))
        if sector_return is not None:
            rel_sector = return_24h - sector_return
    if rel_sector is not None and rel_sector >= 15:
        observed_fields += 1
        components["relative_strength_vs_sector"] = min(15.0, 5.0 + rel_sector * 0.35)
        reasons.append(MarketConfirmationReason.RELATIVE_STRENGTH_VS_SECTOR.value)

    crowding = _score_like(_first(derivatives, "derivatives_crowding", "crowding_score"))
    oi_change = _percent_value(_first(derivatives, "open_interest_24h_change_pct", "oi_change_24h", "oi_24h_change"))
    funding = _percent_value(_first(derivatives, "funding_rate_8h", "funding_rate", "funding"))
    if crowding is not None:
        observed_fields += 1
        if crowding >= 50:
            components["derivatives_crowding"] = min(25.0, crowding * 0.25)
            reasons.append(MarketConfirmationReason.DERIVATIVES_CROWDING.value)
    if oi_change is not None:
        observed_fields += 1
        if oi_change >= 25:
            components["oi_expansion"] = min(20.0, 8.0 + oi_change * 0.25)
            reasons.append(MarketConfirmationReason.OI_EXPANSION.value)
    if funding is not None:
        observed_fields += 1
        if funding >= 0.05:
            components["funding_heated"] = min(12.0, 6.0 + funding * 30.0)
            reasons.append(MarketConfirmationReason.FUNDING_HEATED.value)

    liquidity_fragility = _score_like(_first(market, "liquidity_fragility", "thin_book_score"))
    if liquidity_fragility is not None and liquidity_fragility >= 50:
        observed_fields += 1
        components["liquidity_fragility"] = min(12.0, liquidity_fragility * 0.15)
        reasons.append(MarketConfirmationReason.LIQUIDITY_FRAGILITY.value)

    supply_pressure = _score_like(_first(supply, "supply_pressure", "unlock_pressure", "unlock_pressure_score"))
    if supply_pressure is not None:
        observed_fields += 1
        if supply_pressure >= 40:
            components["supply_pressure"] = min(18.0, supply_pressure * 0.22)
            reasons.append(MarketConfirmationReason.SUPPLY_PRESSURE.value)

    anomaly_score = _score_like(_first(market, "anomaly_score", "score"))
    if anomaly_score is not None:
        observed_fields += 1
        components["market_anomaly_score"] = min(25.0, anomaly_score * 0.25)

    raw_score = sum(components.values())
    if _market_anomaly_without_catalyst(playbook, data):
        raw_score = min(raw_score, 35.0)
        warnings.append("market_anomaly_without_confirmed_catalyst")

    if _playbook_needs_derivatives(playbook) and any(
        reason in reasons
        for reason in (
            MarketConfirmationReason.DERIVATIVES_CROWDING.value,
            MarketConfirmationReason.FUNDING_HEATED.value,
            MarketConfirmationReason.OI_EXPANSION.value,
        )
    ):
        raw_score += 8.0
    if _playbook_needs_supply(playbook) and MarketConfirmationReason.SUPPLY_PRESSURE.value in reasons:
        raw_score += 8.0
    if _playbook_needs_attention(playbook) and MarketConfirmationReason.PRICE_MOMENTUM.value in reasons and MarketConfirmationReason.VOLUME_EXPANSION.value in reasons:
        raw_score += 8.0

    score = max(0.0, min(100.0, raw_score))
    if observed_fields == 0:
        return _insufficient(tuple(dict.fromkeys(missing or ("market_snapshot", "derivatives_snapshot"))))
    if not reasons:
        reasons.append(MarketConfirmationReason.NO_MARKET_REACTION.value)
    data_quality = min(100.0, observed_fields * 16.0)
    if score > 50 and data_quality < 35:
        score = min(score, 50.0)
        warnings.append("market_confirmation_capped_by_sparse_data")
    level = _level(score)
    summary = _summary(level, score, reasons)
    return EventMarketConfirmationResult(
        market_confirmation_score=round(score, 2),
        level=level,
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        data_quality=round(data_quality, 2),
        missing_fields=tuple(dict.fromkeys(missing)),
        confirmation_summary=summary,
        score_components={key: round(value, 2) for key, value in components.items()},
    )


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


def _playbook_needs_attention(playbook: str) -> bool:
    return any(term in playbook for term in ("proxy", "fan", "political", "rwa", "ipo"))


def _playbook_needs_derivatives(playbook: str) -> bool:
    return any(term in playbook for term in ("perp", "squeeze", "listing", "proxy"))


def _playbook_needs_supply(playbook: str) -> bool:
    return any(term in playbook for term in ("unlock", "supply"))


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
