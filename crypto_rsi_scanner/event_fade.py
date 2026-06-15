"""Pure sell-the-news event-fade research engine.

This module is deliberately side-effect free: no network, storage, notification,
or live-order behavior. It scores dated proxy-catalyst blowoffs and emits
alert-only state/signal objects that scanner/reporting code can surface later.
RSI is one confirmation layer, not the alpha by itself.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EVENT_TYPES = frozenset({
    "external_proxy_event",
    "ipo_proxy",
    "token_unlock",
    "airdrop",
    "tge",
    "exchange_listing",
    "perp_listing",
    "etf_approval",
    "etf_launch",
    "sports_event",
    "political_event",
    "reward_claim",
    "mainnet_launch",
    "other",
})

_PROXY_EVENT_TYPES = frozenset({
    "external_proxy_event",
    "ipo_proxy",
    "sports_event",
    "political_event",
})

_ACTIVE_STATES = frozenset({
    "BLOWOFF_RISK",
    "EVENT_PASSED",
    "ARMED",
    "TRIGGERED_SHORT",
    "MANAGING_POSITION",
})

_WEIGHTS = {
    "event_clarity": 0.20,
    "proxy_purity": 0.15,
    "pre_event_pump": 0.15,
    "derivatives_crowding": 0.15,
    "supply_pressure": 0.10,
    "liquidity_fragility": 0.10,
    "post_event_failure": 0.10,
    "narrative_climax": 0.05,
}


class FadeState(str, Enum):
    DISCOVERED = "DISCOVERED"
    WATCHLISTED = "WATCHLISTED"
    PRE_EVENT_HYPE = "PRE_EVENT_HYPE"
    BLOWOFF_RISK = "BLOWOFF_RISK"
    EVENT_PASSED = "EVENT_PASSED"
    ARMED = "ARMED"
    TRIGGERED_SHORT = "TRIGGERED_SHORT"
    MANAGING_POSITION = "MANAGING_POSITION"
    EXITED = "EXITED"
    INVALIDATED = "INVALIDATED"


class FadeSignalType(str, Enum):
    WATCHLIST = "WATCHLIST"
    ARMED = "ARMED"
    SHORT_TRIGGERED = "SHORT_TRIGGERED"
    INVALIDATED = "INVALIDATED"
    EXIT = "EXIT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class EventFadeConfig:
    enabled: bool = False
    mode: str = "alert_only"
    min_watchlist_score: int = 60
    min_armed_score: int = 75
    min_trigger_score: int = 80
    min_event_confidence: float = 0.80
    max_days_to_event: float = 7.0
    expire_hours_after_event: float = 72.0
    min_return_24h: float = 0.75
    min_return_7d: float = 1.50
    extreme_return_7d: float = 5.00
    min_volume_z: float = 3.0
    min_oi_change_24h: float = 0.30
    hot_funding_8h: float = 0.0005
    extreme_funding_8h: float = 0.0010
    min_perp_spot_volume_ratio: float = 5.0
    min_rsi_overbought_score: float = 60.0
    block_btc_strong_risk_on: bool = True
    max_spread_bps: float = 100.0
    min_depth_2pct_usd: float = 10_000.0
    default_risk_pct: float = 0.005
    max_risk_pct: float = 0.01
    max_leverage_hint: float = 2.0
    min_failure_checks: int = 2


@dataclass
class CatalystEvent:
    event_id: str
    coin_id: str | None
    symbol: str
    event_name: str
    event_type: str
    event_time: datetime | None
    first_seen_time: datetime | None = None
    source: str | None = None
    source_url: str | None = None
    confidence: float = 0.0
    external_asset: str | None = None
    is_proxy_narrative: bool = False
    is_direct_beneficiary: bool = False
    notes: str | None = None


@dataclass
class EventMarketSnapshot:
    symbol: str
    coin_id: str | None
    timestamp: datetime
    price: float
    volume_24h: float | None = None
    spot_volume_24h: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    circulating_supply: float | None = None
    total_supply: float | None = None
    max_supply: float | None = None
    return_1h: float | None = None
    return_4h: float | None = None
    return_24h: float | None = None
    return_72h: float | None = None
    return_7d: float | None = None
    distance_from_20d_ma: float | None = None
    volume_zscore_24h: float | None = None
    order_book_depth_1pct: float | None = None
    order_book_depth_2pct: float | None = None
    spread_bps: float | None = None


@dataclass
class EventDerivativesSnapshot:
    symbol: str
    timestamp: datetime
    perp_available: bool
    open_interest: float | None = None
    open_interest_24h_change_pct: float | None = None
    open_interest_to_market_cap: float | None = None
    funding_rate_8h: float | None = None
    funding_rate_percentile: float | None = None
    futures_volume_24h: float | None = None
    perp_spot_volume_ratio: float | None = None
    liquidations_24h: float | None = None
    long_short_ratio: float | None = None
    basis: float | None = None


@dataclass
class EventSupplyPressureSnapshot:
    symbol: str
    timestamp: datetime
    large_holder_exchange_inflow: bool | None = None
    cex_inflow_amount: float | None = None
    cex_inflow_pct_supply: float | None = None
    unlock_amount: float | None = None
    unlock_pct_circulating: float | None = None
    top_holder_concentration: float | None = None
    team_or_mm_wallet_activity: bool | None = None
    admin_or_mint_risk: bool | None = None
    notes: str | None = None


@dataclass
class EventRSISnapshot:
    symbol: str
    timestamp: datetime
    rsi_daily: float | None = None
    rsi_4h: float | None = None
    rsi_weekly: float | None = None
    rsi_5m: float | None = None
    rsi_15m: float | None = None
    rsi_1h: float | None = None
    btc_rsi_daily: float | None = None
    btc_rsi_4h: float | None = None
    btc_rsi_1h: float | None = None
    target_overbought_score: float = 0.0
    target_oversold_score: float = 0.0
    btc_risk_on_score: float = 0.0
    btc_risk_off_score: float = 0.0
    rsi_rollover_confirmed: bool = False
    bearish_rsi_divergence: bool | None = None


@dataclass
class EventTechnicalSnapshot:
    symbol: str
    timestamp: datetime
    event_vwap: float | None = None
    price_below_event_vwap: bool | None = None
    failed_reclaim_event_vwap: bool | None = None
    lower_high_confirmed: bool | None = None
    first_support_broken: bool | None = None
    post_event_high: float | None = None
    post_event_lower_high: float | None = None
    invalidation_level: float | None = None
    entry_reference_price: float | None = None


@dataclass
class FadeCandidate:
    symbol: str
    coin_id: str | None
    event: CatalystEvent
    market: EventMarketSnapshot
    derivatives: EventDerivativesSnapshot | None = None
    supply: EventSupplyPressureSnapshot | None = None
    rsi: EventRSISnapshot | None = None
    technical: EventTechnicalSnapshot | None = None
    state: FadeState = FadeState.DISCOVERED
    fade_score: int = 0
    component_scores: dict[str, int] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    invalidation_level: float | None = None
    suggested_entry_zone: tuple[float, float] | None = None
    suggested_take_profit_zones: list[float] | None = None
    max_risk_pct: float | None = None


@dataclass
class FadeSignal:
    symbol: str
    timestamp: datetime
    signal_type: FadeSignalType
    state: FadeState
    fade_score: int
    confidence: float
    reason_codes: list[str]
    warnings: list[str]
    entry_reference_price: float | None = None
    invalidation_level: float | None = None
    take_profit_zones: list[float] | None = None
    position_size_suggestion: dict | None = None


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    if not math.isfinite(float(value)):
        return 0
    return int(round(max(lo, min(hi, float(value)))))


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _num(value: object, default: float = 0.0) -> float:
    return float(value) if _finite(value) else default


def _return_fraction(value: object) -> float | None:
    """Normalize returns to decimal form; tolerate percent-like inputs."""
    if not _finite(value):
        return None
    v = float(value)
    return v / 100.0 if abs(v) > 10.0 else v


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_dt(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return _as_utc(datetime.fromisoformat(raw))
        except ValueError as exc:
            raise ValueError(f"invalid datetime {value!r}") from exc
    raise ValueError(f"invalid datetime {value!r}")


def _event_time_delta_days(event: CatalystEvent, now: datetime) -> float | None:
    event_time = _as_utc(event.event_time)
    if event_time is None:
        return None
    return (event_time - _as_utc(now)).total_seconds() / 86400.0


def score_event_clarity(event: CatalystEvent, now: datetime, cfg: EventFadeConfig) -> int:
    score = 0.0
    if event.event_time is not None:
        score += 30
    score += 30 * max(0.0, min(1.0, event.confidence))
    if event.source or event.source_url:
        score += 10
    if event.first_seen_time and event.event_time:
        score += 10 if _as_utc(event.first_seen_time) <= _as_utc(event.event_time) else -25
    delta = _event_time_delta_days(event, now)
    if delta is None:
        score -= 30
    elif 0 <= delta <= cfg.max_days_to_event:
        score += 20
    elif -cfg.expire_hours_after_event / 24.0 <= delta < 0:
        score += 18
    elif delta > cfg.max_days_to_event:
        score += 5
    else:
        score -= 25
    if event.event_type not in EVENT_TYPES:
        score -= 10
    return _clamp(score)


def score_proxy_purity(event: CatalystEvent) -> int:
    score = 0.0
    if event.is_proxy_narrative:
        score += 35
    if not event.is_direct_beneficiary:
        score += 25
    else:
        score -= 30
    if event.external_asset:
        score += 15
    if event.event_type in _PROXY_EVENT_TYPES:
        score += 25
    elif event.event_type in ("etf_approval", "etf_launch", "mainnet_launch"):
        score += 5
    return _clamp(score)


def score_pre_event_pump(market: EventMarketSnapshot, cfg: EventFadeConfig | None = None) -> int:
    cfg = cfg or EventFadeConfig()
    score = 0.0
    r24 = _return_fraction(market.return_24h)
    r72 = _return_fraction(market.return_72h)
    r7 = _return_fraction(market.return_7d)
    if r24 is not None:
        if r24 >= cfg.min_return_24h * 2:
            score += 40
        elif r24 >= cfg.min_return_24h:
            score += 30
        elif r24 >= cfg.min_return_24h * 0.4:
            score += 15
    if r72 is not None:
        if r72 >= cfg.min_return_7d * 1.33:
            score += 25
        elif r72 >= cfg.min_return_7d * 0.67:
            score += 18
        elif r72 >= cfg.min_return_7d * 0.33:
            score += 10
    if r7 is not None:
        if r7 >= cfg.extreme_return_7d:
            score += 35
        elif r7 >= cfg.min_return_7d * 1.33:
            score += 28
        elif r7 >= cfg.min_return_7d:
            score += 22
        elif r7 >= cfg.min_return_7d * 0.5:
            score += 12
    vz = _num(market.volume_zscore_24h, 0.0)
    if vz >= cfg.min_volume_z * 1.67:
        score += 25
    elif vz >= cfg.min_volume_z:
        score += 15
    dma = _return_fraction(market.distance_from_20d_ma)
    if dma is not None:
        if dma >= 1.0:
            score += 12
        elif dma >= 0.5:
            score += 7
    return _clamp(score)


def score_derivatives_crowding(
    derivatives: EventDerivativesSnapshot | None,
    cfg: EventFadeConfig | None = None,
) -> int:
    cfg = cfg or EventFadeConfig()
    if derivatives is None:
        return 50
    if not derivatives.perp_available:
        return 30
    score = 20.0
    oi = _return_fraction(derivatives.open_interest_24h_change_pct)
    if oi is not None:
        if oi >= cfg.min_oi_change_24h * 1.67:
            score += 30
        elif oi >= cfg.min_oi_change_24h:
            score += 20
    oi_mc = _num(derivatives.open_interest_to_market_cap, 0.0)
    if oi_mc >= 0.20:
        score += 20
    elif oi_mc >= 0.05:
        score += 10
    funding = _num(derivatives.funding_rate_8h, 0.0)
    if funding >= cfg.extreme_funding_8h:
        score += 25
    elif funding >= cfg.hot_funding_8h:
        score += 15
    ratio = _num(derivatives.perp_spot_volume_ratio, 0.0)
    if ratio >= cfg.min_perp_spot_volume_ratio * 4:
        score += 25
    elif ratio >= cfg.min_perp_spot_volume_ratio:
        score += 15
    ls = _num(derivatives.long_short_ratio, 0.0)
    if ls >= 2.0:
        score += 10
    elif ls >= 1.5:
        score += 6
    if _num(derivatives.basis, 0.0) > 0.02:
        score += 6
    return _clamp(score)


def score_supply_pressure(supply: EventSupplyPressureSnapshot | None) -> int:
    if supply is None:
        return 50
    score = 0.0
    if supply.large_holder_exchange_inflow:
        score += 25
    if supply.team_or_mm_wallet_activity:
        score += 20
    if supply.admin_or_mint_risk:
        score += 15
    cex_pct = _num(supply.cex_inflow_pct_supply, 0.0)
    if cex_pct >= 0.05:
        score += 25
    elif cex_pct >= 0.01:
        score += 15
    unlock_pct = _num(supply.unlock_pct_circulating, 0.0)
    if unlock_pct >= 0.10:
        score += 25
    elif unlock_pct >= 0.03:
        score += 15
    holder = _num(supply.top_holder_concentration, 0.0)
    if holder >= 0.60:
        score += 15
    elif holder >= 0.35:
        score += 8
    return _clamp(score)


def score_liquidity_fragility(
    market: EventMarketSnapshot,
    derivatives: EventDerivativesSnapshot | None,
) -> int:
    has_data = any(_finite(v) for v in (
        market.order_book_depth_1pct,
        market.order_book_depth_2pct,
        market.spread_bps,
        market.volume_24h,
        market.spot_volume_24h,
    )) or (derivatives is not None and _finite(derivatives.perp_spot_volume_ratio))
    if not has_data:
        return 50
    score = 0.0
    spread = _num(market.spread_bps, 0.0)
    if spread >= 300:
        score += 45
    elif spread >= 100:
        score += 30
    elif spread >= 50:
        score += 15
    d2 = _num(market.order_book_depth_2pct, 0.0)
    if d2 > 0:
        if d2 < 10_000:
            score += 40
        elif d2 < 50_000:
            score += 25
        volume = _num(market.spot_volume_24h, _num(market.volume_24h, 0.0))
        if volume > 0 and volume / d2 >= 1000:
            score += 25
        elif volume > 0 and volume / d2 >= 200:
            score += 12
    d1 = _num(market.order_book_depth_1pct, 0.0)
    if 0 < d1 < 5_000:
        score += 15
    ratio = _num(derivatives.perp_spot_volume_ratio if derivatives else None, 0.0)
    if ratio >= 20:
        score += 20
    elif ratio >= 5:
        score += 10
    return _clamp(score)


def score_post_event_failure(
    event: CatalystEvent,
    technical: EventTechnicalSnapshot | None,
    rsi: EventRSISnapshot | None,
    now: datetime,
) -> int:
    event_time = _as_utc(event.event_time)
    if event_time is None or _as_utc(now) <= event_time:
        return 0
    if technical is None:
        return 0
    score = 0.0
    if technical.price_below_event_vwap:
        score += 25
    if technical.failed_reclaim_event_vwap:
        score += 25
    if technical.lower_high_confirmed:
        score += 20
    if technical.first_support_broken:
        score += 20
    if rsi and rsi.rsi_rollover_confirmed:
        score += 10
    if rsi and rsi.bearish_rsi_divergence:
        score += 5
    return _clamp(score)


def score_narrative_climax(optional_data: Mapping[str, Any] | None = None) -> int:
    if not optional_data:
        return 50
    return _clamp(optional_data.get("narrative_climax_score", 50))


def calculate_fade_score(
    candidate: FadeCandidate,
    cfg: EventFadeConfig,
    now: datetime,
    narrative_data: Mapping[str, Any] | None = None,
) -> int:
    components = {
        "event_clarity": score_event_clarity(candidate.event, now, cfg),
        "proxy_purity": score_proxy_purity(candidate.event),
        "pre_event_pump": score_pre_event_pump(candidate.market, cfg),
        "derivatives_crowding": score_derivatives_crowding(candidate.derivatives, cfg),
        "supply_pressure": score_supply_pressure(candidate.supply),
        "liquidity_fragility": score_liquidity_fragility(candidate.market, candidate.derivatives),
        "post_event_failure": score_post_event_failure(candidate.event, candidate.technical, candidate.rsi, now),
        "narrative_climax": score_narrative_climax(narrative_data),
    }
    score = sum(components[name] * weight for name, weight in _WEIGHTS.items())
    candidate.component_scores = components
    candidate.fade_score = _clamp(score)
    candidate.reason_codes = reason_codes(candidate, cfg, now)
    candidate.warnings = warnings(candidate, cfg, now)
    candidate.invalidation_level = (
        candidate.technical.invalidation_level if candidate.technical else candidate.invalidation_level
    )
    candidate.max_risk_pct = cfg.max_risk_pct
    return candidate.fade_score


def reason_codes(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> list[str]:
    scores = candidate.component_scores
    out: list[str] = []
    if scores.get("event_clarity", 0) >= 70 and scores.get("proxy_purity", 0) >= 70:
        out.append("dated proxy catalyst")
    if scores.get("pre_event_pump", 0) >= 70:
        out.append("large pre-event pump")
    if scores.get("derivatives_crowding", 0) >= 60:
        out.append("derivatives crowding")
    if scores.get("liquidity_fragility", 0) >= 60:
        out.append("shallow liquidity")
    if scores.get("supply_pressure", 0) >= 60:
        out.append("supply/distribution pressure")
    if _event_time_delta_days(candidate.event, now) is not None and _event_time_delta_days(candidate.event, now) < 0:
        out.append("event has passed")
    if candidate.technical and candidate.technical.price_below_event_vwap:
        out.append("event VWAP lost")
    if candidate.technical and candidate.technical.failed_reclaim_event_vwap:
        out.append("failed reclaim detected")
    if candidate.rsi and candidate.rsi.rsi_rollover_confirmed:
        out.append("RSI rollover confirmed")
    if is_btc_regime_blocking_short(candidate, cfg):
        out.append("BTC risk-on blocks weak short")
    return out


def warnings(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> list[str]:
    out = ["alert-only mode; no live order placed"]
    if candidate.component_scores and not _eligible_from_scores(candidate, cfg):
        out.append("not an eligible proxy event-fade candidate")
    if candidate.derivatives is None:
        out.append("derivatives data missing")
    if candidate.supply is None:
        out.append("supply-pressure data missing")
    if candidate.technical is None:
        out.append("technical confirmation missing")
    if candidate.market.spread_bps is not None and candidate.market.spread_bps > cfg.max_spread_bps:
        out.append("spread too wide for clean execution")
    if (
        candidate.market.order_book_depth_2pct is not None
        and candidate.market.order_book_depth_2pct < cfg.min_depth_2pct_usd
    ):
        out.append("2pct book depth below risk threshold")
    delta = _event_time_delta_days(candidate.event, now)
    if delta is not None and delta < -cfg.expire_hours_after_event / 24.0:
        out.append("event window expired")
    return out


def _eligible_from_scores(candidate: FadeCandidate, cfg: EventFadeConfig) -> bool:
    return (
        candidate.event.confidence >= cfg.min_event_confidence
        and candidate.event.event_time is not None
        and candidate.event.is_proxy_narrative
        and not candidate.event.is_direct_beneficiary
        and candidate.component_scores.get("proxy_purity", 0) >= 70
        and candidate.component_scores.get("event_clarity", 0) >= 70
        and candidate.component_scores.get("pre_event_pump", 0) >= 60
    )


def is_event_fade_candidate(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> bool:
    if not candidate.component_scores:
        calculate_fade_score(candidate, cfg, now)
    return _eligible_from_scores(candidate, cfg)


def is_blowoff_structure(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> bool:
    if not candidate.component_scores:
        calculate_fade_score(candidate, cfg, now)
    rsi_ok = candidate.rsi is None or candidate.rsi.target_overbought_score >= cfg.min_rsi_overbought_score
    return (
        candidate.component_scores.get("pre_event_pump", 0) >= 70
        and candidate.component_scores.get("derivatives_crowding", 0) >= 60
        and rsi_ok
        and (
            candidate.component_scores.get("liquidity_fragility", 0) >= 60
            or candidate.component_scores.get("supply_pressure", 0) >= 60
        )
    )


def is_btc_regime_blocking_short(candidate: FadeCandidate, cfg: EventFadeConfig) -> bool:
    if not cfg.block_btc_strong_risk_on:
        return False
    risk_on = candidate.rsi.btc_risk_on_score if candidate.rsi else 0.0
    return risk_on >= 80.0 and candidate.fade_score < 90


def _liquidity_checks_pass(candidate: FadeCandidate, cfg: EventFadeConfig) -> bool:
    spread = candidate.market.spread_bps
    if spread is not None and spread > cfg.max_spread_bps:
        return False
    depth = candidate.market.order_book_depth_2pct
    if depth is not None and depth < cfg.min_depth_2pct_usd:
        return False
    return True


def is_post_event_failure(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> bool:
    event_time = _as_utc(candidate.event.event_time)
    if event_time is None or _as_utc(now) <= event_time:
        return False
    tech = candidate.technical
    if tech is None:
        return False
    checks = [
        tech.price_below_event_vwap,
        tech.failed_reclaim_event_vwap,
        tech.lower_high_confirmed,
        tech.first_support_broken,
    ]
    return (
        sum(1 for value in checks if value) >= cfg.min_failure_checks
        and (candidate.rsi is None or candidate.rsi.rsi_rollover_confirmed)
        and not is_btc_regime_blocking_short(candidate, cfg)
        and _liquidity_checks_pass(candidate, cfg)
        and tech.invalidation_level is not None
    )


def _event_expired(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> bool:
    delta = _event_time_delta_days(candidate.event, now)
    return delta is not None and delta < -cfg.expire_hours_after_event / 24.0


def _invalidated(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> bool:
    if _event_expired(candidate, cfg, now) and candidate.state not in (
        FadeState.TRIGGERED_SHORT,
        FadeState.MANAGING_POSITION,
        FadeState.EXITED,
    ):
        return True
    tech = candidate.technical
    if not tech or tech.invalidation_level is None:
        return False
    return (
        candidate.state.value in _ACTIVE_STATES
        and candidate.market.price > tech.invalidation_level
    )


def advance_fade_state(candidate: FadeCandidate, now: datetime, cfg: EventFadeConfig) -> FadeState:
    calculate_fade_score(candidate, cfg, now)
    if not is_event_fade_candidate(candidate, cfg, now):
        candidate.state = FadeState.DISCOVERED
        candidate.reason_codes = reason_codes(candidate, cfg, now)
        candidate.warnings = warnings(candidate, cfg, now)
        return candidate.state

    state = candidate.state
    for _ in range(10):
        previous = state
        candidate.state = state
        if _invalidated(candidate, cfg, now):
            state = FadeState.INVALIDATED
        elif state == FadeState.DISCOVERED:
            if candidate.event.event_time and candidate.event.confidence >= cfg.min_event_confidence:
                state = FadeState.WATCHLISTED
        elif state == FadeState.WATCHLISTED:
            volume_hot = _num(candidate.market.volume_zscore_24h, 0.0) >= cfg.min_volume_z
            if candidate.component_scores.get("pre_event_pump", 0) >= 60 and (
                volume_hot or candidate.component_scores.get("pre_event_pump", 0) >= 80
            ):
                state = FadeState.PRE_EVENT_HYPE
        elif state == FadeState.PRE_EVENT_HYPE:
            if is_blowoff_structure(candidate, cfg, now):
                state = FadeState.BLOWOFF_RISK
        elif state == FadeState.BLOWOFF_RISK:
            event_time = _as_utc(candidate.event.event_time)
            if event_time and _as_utc(now) > event_time:
                state = FadeState.EVENT_PASSED
        elif state == FadeState.EVENT_PASSED:
            if (
                candidate.fade_score >= cfg.min_armed_score
                and candidate.component_scores.get("post_event_failure", 0) >= 25
            ):
                state = FadeState.ARMED
        elif state == FadeState.ARMED:
            if candidate.fade_score >= cfg.min_trigger_score and is_post_event_failure(candidate, cfg, now):
                state = FadeState.TRIGGERED_SHORT
        if state == previous or state in (FadeState.INVALIDATED, FadeState.TRIGGERED_SHORT, FadeState.EXITED):
            break
    candidate.state = state
    candidate.reason_codes = reason_codes(candidate, cfg, now)
    candidate.warnings = warnings(candidate, cfg, now)
    return state


def signal_type_for_state(
    state: FadeState,
    fade_score: int,
    event_time: datetime | None,
    cfg: EventFadeConfig,
) -> FadeSignalType:
    if state == FadeState.INVALIDATED:
        return FadeSignalType.INVALIDATED
    if state == FadeState.EXITED:
        return FadeSignalType.EXIT
    if state == FadeState.TRIGGERED_SHORT:
        return FadeSignalType.SHORT_TRIGGERED
    if state in (FadeState.ARMED, FadeState.EVENT_PASSED) and fade_score >= cfg.min_armed_score:
        return FadeSignalType.ARMED
    if (
        state in (FadeState.WATCHLISTED, FadeState.PRE_EVENT_HYPE, FadeState.BLOWOFF_RISK)
        and fade_score >= cfg.min_watchlist_score
        and event_time is not None
    ):
        return FadeSignalType.WATCHLIST
    return FadeSignalType.NO_TRADE


def generate_fade_signal(candidate: FadeCandidate, cfg: EventFadeConfig, now: datetime) -> FadeSignal:
    state = advance_fade_state(candidate, now, cfg)
    signal_type = (
        signal_type_for_state(state, candidate.fade_score, candidate.event.event_time, cfg)
        if is_event_fade_candidate(candidate, cfg, now)
        else FadeSignalType.NO_TRADE
    )
    tech = candidate.technical
    return FadeSignal(
        symbol=candidate.symbol,
        timestamp=_as_utc(now),
        signal_type=signal_type,
        state=state,
        fade_score=candidate.fade_score,
        confidence=max(0.0, min(1.0, candidate.event.confidence)),
        reason_codes=list(candidate.reason_codes),
        warnings=list(candidate.warnings),
        entry_reference_price=tech.entry_reference_price if tech else None,
        invalidation_level=tech.invalidation_level if tech else candidate.invalidation_level,
        take_profit_zones=candidate.suggested_take_profit_zones,
        position_size_suggestion=None,
    )


def calculate_position_size(
    account_equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    max_leverage_hint: float,
    liquidity_depth_2pct: float | None = None,
) -> dict:
    warnings_out: list[str] = []
    if account_equity <= 0 or risk_pct <= 0 or entry_price <= 0 or stop_price <= 0:
        return {"valid": False, "warnings": ["invalid account, risk, entry, or stop"]}
    stop_distance = abs(stop_price - entry_price)
    if stop_distance <= 0:
        return {"valid": False, "warnings": ["stop price must differ from entry price"]}
    stop_distance_pct = stop_distance / entry_price
    risk_usd = account_equity * risk_pct
    position_units = risk_usd / stop_distance
    notional = position_units * entry_price
    leverage_hint = notional / account_equity
    if stop_distance_pct >= 0.50:
        warnings_out.append("stop distance is very wide")
    if leverage_hint > max_leverage_hint:
        warnings_out.append("implied leverage exceeds max hint")
    if liquidity_depth_2pct is not None and liquidity_depth_2pct > 0 and notional > liquidity_depth_2pct * 0.25:
        warnings_out.append("notional is large relative to visible 2pct depth")
    return {
        "valid": True,
        "risk_usd": risk_usd,
        "stop_distance_pct": stop_distance_pct,
        "position_units": position_units,
        "notional": notional,
        "leverage_hint": leverage_hint,
        "warnings": warnings_out,
    }


def anchored_vwap(
    prices: Sequence[float],
    volumes: Sequence[float],
    times: Sequence[datetime] | None = None,
    anchor_time: datetime | None = None,
    anchor_index: int = 0,
) -> float | None:
    if times is not None and anchor_time is not None:
        anchor = _as_utc(anchor_time)
        indices = [i for i, ts in enumerate(times) if _as_utc(ts) >= anchor]
    else:
        indices = list(range(max(0, int(anchor_index)), min(len(prices), len(volumes))))
    num = den = 0.0
    for i in indices:
        if _finite(prices[i]) and _finite(volumes[i]) and float(volumes[i]) > 0:
            num += float(prices[i]) * float(volumes[i])
            den += float(volumes[i])
    return None if den <= 0 else num / den


def price_below_level(price: float | None, level: float | None) -> bool:
    return _finite(price) and _finite(level) and float(price) < float(level)


def failed_reclaim(series: Sequence[float], level: float, lookback: int = 3) -> bool:
    vals = [float(v) for v in series[-max(1, lookback):] if _finite(v)]
    if len(vals) < 2:
        return False
    return max(vals) > level and vals[-1] < level


def lower_high_confirmed(highs_or_closes: Sequence[float], lookback: int = 5) -> bool:
    vals = [float(v) for v in highs_or_closes[-max(3, lookback):] if _finite(v)]
    if len(vals) < 3:
        return False
    peak_index = max(range(len(vals)), key=lambda i: vals[i])
    if peak_index >= len(vals) - 1:
        return False
    rebound = max(vals[peak_index + 1:])
    return rebound < vals[peak_index] and vals[-1] < rebound


def support_break_confirmed(series: Sequence[float], support_level: float) -> bool:
    vals = [float(v) for v in series if _finite(v)]
    return bool(vals) and vals[-1] < support_level and any(v >= support_level for v in vals[:-1])


def event_fade_feature_vector(
    candidate: FadeCandidate,
    cfg: EventFadeConfig | None = None,
    now: datetime | None = None,
) -> dict:
    cfg = cfg or EventFadeConfig()
    if not candidate.component_scores:
        calculate_fade_score(candidate, cfg, now or candidate.market.timestamp)
    scores = candidate.component_scores
    m = candidate.market
    d = candidate.derivatives
    r = candidate.rsi
    eligible = _eligible_from_scores(candidate, cfg)
    return {
        "event_type": candidate.event.event_type,
        "event_confidence": candidate.event.confidence,
        "proxy_score": scores.get("proxy_purity", 0),
        "event_clarity_score": scores.get("event_clarity", 0),
        "pre_event_pump_score": scores.get("pre_event_pump", 0),
        "derivatives_crowding_score": scores.get("derivatives_crowding", 0),
        "supply_pressure_score": scores.get("supply_pressure", 0),
        "liquidity_fragility_score": scores.get("liquidity_fragility", 0),
        "post_event_failure_score": scores.get("post_event_failure", 0),
        "fade_score": candidate.fade_score,
        "return_24h": m.return_24h,
        "return_7d": m.return_7d,
        "volume_zscore": m.volume_zscore_24h,
        "funding_rate_8h": d.funding_rate_8h if d else None,
        "oi_change_24h": d.open_interest_24h_change_pct if d else None,
        "perp_spot_volume_ratio": d.perp_spot_volume_ratio if d else None,
        "depth_2pct": m.order_book_depth_2pct,
        "spread_bps": m.spread_bps,
        "rsi_daily": r.rsi_daily if r else None,
        "rsi_4h": r.rsi_4h if r else None,
        "rsi_weekly": r.rsi_weekly if r else None,
        "rsi_rollover_confirmed": r.rsi_rollover_confirmed if r else None,
        "btc_risk_on_score": r.btc_risk_on_score if r else None,
        "eligible": eligible,
        "state": candidate.state.value,
        "signal_type": (
            signal_type_for_state(candidate.state, candidate.fade_score, candidate.event.event_time, cfg)
            if eligible
            else FadeSignalType.NO_TRADE
        ).value,
    }


def _event_from_dict(data: Mapping[str, Any]) -> CatalystEvent:
    if not isinstance(data, Mapping):
        raise ValueError("event entry must be an object")
    event_type = str(data.get("event_type") or "other")
    if event_type not in EVENT_TYPES:
        event_type = "other"
    return CatalystEvent(
        event_id=str(data.get("event_id") or ""),
        coin_id=data.get("coin_id"),
        symbol=str(data.get("symbol") or "").upper(),
        event_name=str(data.get("event_name") or ""),
        event_type=event_type,
        event_time=_parse_dt(data.get("event_time")),
        first_seen_time=_parse_dt(data.get("first_seen_time")),
        source=data.get("source"),
        source_url=data.get("source_url"),
        confidence=float(data.get("confidence") or 0.0),
        external_asset=data.get("external_asset"),
        is_proxy_narrative=bool(data.get("is_proxy_narrative")),
        is_direct_beneficiary=bool(data.get("is_direct_beneficiary")),
        notes=data.get("notes"),
    )


def _market_from_dict(data: Mapping[str, Any], event: CatalystEvent) -> EventMarketSnapshot:
    ts = _parse_dt(data.get("timestamp")) or event.first_seen_time or event.event_time or datetime.now(timezone.utc)
    return EventMarketSnapshot(
        symbol=str(data.get("symbol") or event.symbol).upper(),
        coin_id=data.get("coin_id", event.coin_id),
        timestamp=ts,
        price=float(data.get("price") or 0.0),
        volume_24h=data.get("volume_24h"),
        spot_volume_24h=data.get("spot_volume_24h"),
        market_cap=data.get("market_cap"),
        fdv=data.get("fdv"),
        circulating_supply=data.get("circulating_supply"),
        total_supply=data.get("total_supply"),
        max_supply=data.get("max_supply"),
        return_1h=data.get("return_1h"),
        return_4h=data.get("return_4h"),
        return_24h=data.get("return_24h"),
        return_72h=data.get("return_72h"),
        return_7d=data.get("return_7d"),
        distance_from_20d_ma=data.get("distance_from_20d_ma"),
        volume_zscore_24h=data.get("volume_zscore_24h"),
        order_book_depth_1pct=data.get("order_book_depth_1pct"),
        order_book_depth_2pct=data.get("order_book_depth_2pct"),
        spread_bps=data.get("spread_bps"),
    )


def _derivatives_from_dict(data: Mapping[str, Any] | None, event: CatalystEvent) -> EventDerivativesSnapshot | None:
    if not data:
        return None
    return EventDerivativesSnapshot(
        symbol=str(data.get("symbol") or event.symbol).upper(),
        timestamp=_parse_dt(data.get("timestamp")) or event.event_time or datetime.now(timezone.utc),
        perp_available=bool(data.get("perp_available")),
        open_interest=data.get("open_interest"),
        open_interest_24h_change_pct=data.get("open_interest_24h_change_pct"),
        open_interest_to_market_cap=data.get("open_interest_to_market_cap"),
        funding_rate_8h=data.get("funding_rate_8h"),
        funding_rate_percentile=data.get("funding_rate_percentile"),
        futures_volume_24h=data.get("futures_volume_24h"),
        perp_spot_volume_ratio=data.get("perp_spot_volume_ratio"),
        liquidations_24h=data.get("liquidations_24h"),
        long_short_ratio=data.get("long_short_ratio"),
        basis=data.get("basis"),
    )


def _supply_from_dict(data: Mapping[str, Any] | None, event: CatalystEvent) -> EventSupplyPressureSnapshot | None:
    if not data:
        return None
    return EventSupplyPressureSnapshot(
        symbol=str(data.get("symbol") or event.symbol).upper(),
        timestamp=_parse_dt(data.get("timestamp")) or event.event_time or datetime.now(timezone.utc),
        large_holder_exchange_inflow=data.get("large_holder_exchange_inflow"),
        cex_inflow_amount=data.get("cex_inflow_amount"),
        cex_inflow_pct_supply=data.get("cex_inflow_pct_supply"),
        unlock_amount=data.get("unlock_amount"),
        unlock_pct_circulating=data.get("unlock_pct_circulating"),
        top_holder_concentration=data.get("top_holder_concentration"),
        team_or_mm_wallet_activity=data.get("team_or_mm_wallet_activity"),
        admin_or_mint_risk=data.get("admin_or_mint_risk"),
        notes=data.get("notes"),
    )


def _rsi_from_dict(data: Mapping[str, Any] | None, event: CatalystEvent) -> EventRSISnapshot | None:
    if not data:
        return None
    return EventRSISnapshot(
        symbol=str(data.get("symbol") or event.symbol).upper(),
        timestamp=_parse_dt(data.get("timestamp")) or event.event_time or datetime.now(timezone.utc),
        rsi_daily=data.get("rsi_daily"),
        rsi_4h=data.get("rsi_4h"),
        rsi_weekly=data.get("rsi_weekly"),
        rsi_5m=data.get("rsi_5m"),
        rsi_15m=data.get("rsi_15m"),
        rsi_1h=data.get("rsi_1h"),
        btc_rsi_daily=data.get("btc_rsi_daily"),
        btc_rsi_4h=data.get("btc_rsi_4h"),
        btc_rsi_1h=data.get("btc_rsi_1h"),
        target_overbought_score=float(data.get("target_overbought_score") or 0.0),
        target_oversold_score=float(data.get("target_oversold_score") or 0.0),
        btc_risk_on_score=float(data.get("btc_risk_on_score") or 0.0),
        btc_risk_off_score=float(data.get("btc_risk_off_score") or 0.0),
        rsi_rollover_confirmed=bool(data.get("rsi_rollover_confirmed")),
        bearish_rsi_divergence=data.get("bearish_rsi_divergence"),
    )


def _technical_from_dict(data: Mapping[str, Any] | None, event: CatalystEvent) -> EventTechnicalSnapshot | None:
    if not data:
        return None
    return EventTechnicalSnapshot(
        symbol=str(data.get("symbol") or event.symbol).upper(),
        timestamp=_parse_dt(data.get("timestamp")) or event.event_time or datetime.now(timezone.utc),
        event_vwap=data.get("event_vwap"),
        price_below_event_vwap=data.get("price_below_event_vwap"),
        failed_reclaim_event_vwap=data.get("failed_reclaim_event_vwap"),
        lower_high_confirmed=data.get("lower_high_confirmed"),
        first_support_broken=data.get("first_support_broken"),
        post_event_high=data.get("post_event_high"),
        post_event_lower_high=data.get("post_event_lower_high"),
        invalidation_level=data.get("invalidation_level"),
        entry_reference_price=data.get("entry_reference_price"),
    )


def candidate_from_event(event: CatalystEvent, now: datetime | None = None) -> FadeCandidate:
    ts = _as_utc(now) or event.first_seen_time or event.event_time or datetime.now(timezone.utc)
    market = EventMarketSnapshot(event.symbol, event.coin_id, ts, price=0.0)
    return FadeCandidate(event.symbol, event.coin_id, event, market)


def load_event_fade_events(path: str | Path | None) -> list[CatalystEvent]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid event fade JSON {p}: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("event fade JSON must be a list")
    entries = [item.get("event", item) if isinstance(item, Mapping) else item for item in raw]
    return [_event_from_dict(item) for item in entries]


def load_event_fade_candidates(path: str | Path | None) -> list[FadeCandidate]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid event fade JSON {p}: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("event fade JSON must be a list")
    out: list[FadeCandidate] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("event fade entries must be objects")
        event_payload = item.get("event", item)
        event = _event_from_dict(event_payload)
        if "event" not in item:
            out.append(candidate_from_event(event))
            continue
        market = _market_from_dict(item.get("market") or {}, event)
        state = FadeState(str(item.get("state") or FadeState.DISCOVERED.value))
        out.append(FadeCandidate(
            symbol=market.symbol,
            coin_id=market.coin_id,
            event=event,
            market=market,
            derivatives=_derivatives_from_dict(item.get("derivatives"), event),
            supply=_supply_from_dict(item.get("supply"), event),
            rsi=_rsi_from_dict(item.get("rsi"), event),
            technical=_technical_from_dict(item.get("technical"), event),
            state=state,
        ))
    return out


def format_fade_report(candidates: Iterable[FadeCandidate], cfg: EventFadeConfig, now: datetime) -> str:
    rows = []
    for candidate in candidates:
        signal = generate_fade_signal(candidate, cfg, now)
        event_time = candidate.event.event_time.isoformat() if candidate.event.event_time else "unknown"
        rows.append(
            f"{candidate.symbol:<12} {signal.signal_type.value:<15} {signal.state.value:<15} "
            f"score={signal.fade_score:>3}/100 event={candidate.event.event_name} time={event_time}"
        )
        if signal.reason_codes:
            rows.append("  reasons: " + ", ".join(signal.reason_codes))
        if signal.invalidation_level is not None:
            rows.append(f"  invalidation: {signal.invalidation_level:g}")
        if signal.warnings:
            rows.append("  warnings: " + ", ".join(signal.warnings))
    if not rows:
        return "No event-fade candidates. Configure RSI_EVENT_FADE_EVENTS_PATH with local JSON fixtures."
    header = [
        "=" * 64,
        "EVENT FADE REPORT (alert-only; no orders placed)",
        "=" * 64,
    ]
    return "\n".join(header + rows)


def runtime_config(config_module: Any) -> EventFadeConfig:
    return EventFadeConfig(
        enabled=bool(getattr(config_module, "EVENT_FADE_ENABLED", False)),
        mode=str(getattr(config_module, "EVENT_FADE_MODE", "alert_only")),
        min_watchlist_score=int(getattr(config_module, "EVENT_FADE_MIN_WATCHLIST_SCORE", 60)),
        min_armed_score=int(getattr(config_module, "EVENT_FADE_MIN_ARMED_SCORE", 75)),
        min_trigger_score=int(getattr(config_module, "EVENT_FADE_MIN_TRIGGER_SCORE", 80)),
        min_event_confidence=float(getattr(config_module, "EVENT_FADE_MIN_EVENT_CONFIDENCE", 0.80)),
        max_days_to_event=float(getattr(config_module, "EVENT_FADE_MAX_DAYS_TO_EVENT", 7.0)),
        expire_hours_after_event=float(getattr(config_module, "EVENT_FADE_EXPIRE_HOURS_AFTER_EVENT", 72.0)),
        min_return_24h=float(getattr(config_module, "EVENT_FADE_MIN_RETURN_24H", 0.75)),
        min_return_7d=float(getattr(config_module, "EVENT_FADE_MIN_RETURN_7D", 1.50)),
        extreme_return_7d=float(getattr(config_module, "EVENT_FADE_EXTREME_RETURN_7D", 5.00)),
        min_volume_z=float(getattr(config_module, "EVENT_FADE_MIN_VOLUME_Z", 3.0)),
        min_oi_change_24h=float(getattr(config_module, "EVENT_FADE_MIN_OI_CHANGE_24H", 0.30)),
        hot_funding_8h=float(getattr(config_module, "EVENT_FADE_HOT_FUNDING_8H", 0.0005)),
        extreme_funding_8h=float(getattr(config_module, "EVENT_FADE_EXTREME_FUNDING_8H", 0.0010)),
        min_perp_spot_volume_ratio=float(getattr(config_module, "EVENT_FADE_MIN_PERP_SPOT_VOLUME_RATIO", 5.0)),
        min_rsi_overbought_score=float(getattr(config_module, "EVENT_FADE_MIN_RSI_OVERBOUGHT_SCORE", 60.0)),
        block_btc_strong_risk_on=bool(getattr(config_module, "EVENT_FADE_BLOCK_BTC_STRONG_RISK_ON", True)),
        max_spread_bps=float(getattr(config_module, "EVENT_FADE_MAX_SPREAD_BPS", 100.0)),
        min_depth_2pct_usd=float(getattr(config_module, "EVENT_FADE_MIN_DEPTH_2PCT_USD", 10_000.0)),
        default_risk_pct=float(getattr(config_module, "EVENT_FADE_DEFAULT_RISK_PCT", 0.005)),
        max_risk_pct=float(getattr(config_module, "EVENT_FADE_MAX_RISK_PCT", 0.01)),
        max_leverage_hint=float(getattr(config_module, "EVENT_FADE_MAX_LEVERAGE_HINT", 2.0)),
        min_failure_checks=int(getattr(config_module, "EVENT_FADE_MIN_FAILURE_CHECKS", 2)),
    )
