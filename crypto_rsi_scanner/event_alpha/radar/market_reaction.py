"""Market reaction and opportunity-lane metadata for Event Alpha research.

This module is pure and research-only. It classifies already-collected market,
derivatives, DEX/liquidity, supply, and source evidence into operator-facing
research lanes. It cannot route alerts, create trades, write live signal rows,
open paper positions, or create ``TRIGGERED_FADE``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from ... import event_market_units


class EventMarketState(str, Enum):
    NO_REACTION = "no_reaction"
    STEALTH_ACCUMULATION = "stealth_accumulation"
    CONFIRMED_BREAKOUT = "confirmed_breakout"
    LATE_MOMENTUM = "late_momentum"
    BLOWOFF_CROWDED = "blowoff_crowded"
    POST_EVENT_FADE_SETUP = "post_event_fade_setup"
    RISK_OFF_SELL_PRESSURE = "risk_off_sell_pressure"


class EventOpportunityType(str, Enum):
    EARLY_LONG_RESEARCH = "EARLY_LONG_RESEARCH"
    CONFIRMED_LONG_RESEARCH = "CONFIRMED_LONG_RESEARCH"
    FADE_SHORT_REVIEW = "FADE_SHORT_REVIEW"
    RISK_ONLY = "RISK_ONLY"
    UNCONFIRMED_RESEARCH = "UNCONFIRMED_RESEARCH"
    DIAGNOSTIC = "DIAGNOSTIC"


@dataclass(frozen=True)
class MarketStateSnapshot:
    return_5m: float | None = None
    return_15m: float | None = None
    return_1h: float | None = None
    return_4h: float | None = None
    return_24h: float | None = None
    relative_return_vs_btc: float | None = None
    relative_return_vs_eth: float | None = None
    relative_return_vs_sector: float | None = None
    volume_turnover_zscore: float | None = None
    volume_to_market_cap: float | None = None
    liquidity_usd: float | None = None
    spread_bps: float | None = None
    open_interest_delta: float | None = None
    funding_level: float | None = None
    funding_zscore: float | None = None
    liquidation_imbalance: float | None = None
    dex_volume_change: float | None = None
    dex_liquidity_change: float | None = None
    event_age_hours: float | None = None
    freshness_status: str | None = None
    source: str | None = None
    return_unit: str = event_market_units.RETURN_UNIT_PERCENT_POINTS
    source_return_unit: str = event_market_units.RETURN_UNIT_UNKNOWN
    threshold_unit: str = event_market_units.RETURN_UNIT_PERCENT_POINTS
    unit_warnings: tuple[str, ...] = ()
    observed_fields: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class MarketReactionResult:
    market_state_snapshot: MarketStateSnapshot
    market_state: str
    opportunity_type: str
    why_now: str
    what_confirms: tuple[str, ...] = ()
    what_invalidates: tuple[str, ...] = ()
    why_not_alertable: tuple[str, ...] = ()
    evidence_summary: tuple[str, ...] = ()
    source_requirements_met: bool = False
    market_requirements_met: bool = False
    fade_requirements_met: bool = False
    source_strength: str = "weak"
    warnings: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["market_state_snapshot"] = self.market_state_snapshot.to_dict()
        return data


@dataclass(frozen=True)
class MarketReactionInput:
    symbol: str | None = None
    coin_id: str | None = None
    row_type: str | None = None
    market_snapshot: Mapping[str, Any] | None = None
    derivatives_snapshot: Mapping[str, Any] | None = None
    dex_liquidity_snapshot: Mapping[str, Any] | None = None
    supply_snapshot: Mapping[str, Any] | None = None
    source_class: str | None = None
    source_pack: str | None = None
    impact_path_type: str | None = None
    playbook_type: str | None = None
    candidate_role: str | None = None
    evidence_specificity: str | None = None
    evidence_quality_score: float | None = None
    accepted_evidence_count: int | None = None
    accepted_reason_codes: tuple[str, ...] = ()
    evidence_acquisition_status: str | None = None
    final_route_after_quality_gate: str | None = None
    final_state_after_quality_gate: str | None = None
    diagnostic_row_count: int | None = None
    source_noise_control_count: int | None = None
    market_confirmation_level: str | None = None
    market_confirmation_score: float | None = None
    market_context_freshness_status: str | None = None
    event_age_hours: float | None = None
    catalyst_fresh: bool | None = None
    negative_catalyst: bool | None = None


def evaluate_market_reaction(data: MarketReactionInput | Mapping[str, Any] | None) -> MarketReactionResult:
    """Classify Event Alpha market reaction and research opportunity lane."""
    if data is None:
        data = MarketReactionInput()
    elif isinstance(data, Mapping):
        data = _input_from_mapping(data)
    snapshot = _build_snapshot(data)
    source_pack = _text(data.source_pack).casefold()
    impact = _text(data.impact_path_type or data.playbook_type).casefold()
    source_class = _text(data.source_class).casefold()
    source_strength = _source_strength(data)
    strong_source = source_strength in {"strong", "official_structured"}
    cryptopanic_only = _cryptopanic_only(data)
    negative = bool(data.negative_catalyst) or _negative_impact(impact, source_pack)
    narrative = _source_only_narrative(impact, source_pack)
    diagnostic = _diagnostic_context(data, impact, source_pack)
    market_state, market_reasons = _classify_market_state(snapshot, negative=negative, impact=impact)
    market_confirmed = market_state in {
        EventMarketState.STEALTH_ACCUMULATION.value,
        EventMarketState.CONFIRMED_BREAKOUT.value,
    } or _level_at_least(data.market_confirmation_level, data.market_confirmation_score, "moderate")
    market_sane = _liquidity_sane(snapshot)
    crowded = _has_crowding(snapshot)
    completed_move = _completed_move(snapshot, market_state)
    exhaustion = crowded or market_state == EventMarketState.LATE_MOMENTUM.value or _volume_exhausted(snapshot)
    fade_ready = completed_move and exhaustion
    source_ok_for_long = strong_source and not cryptopanic_only
    source_ok_for_fade = source_ok_for_long or (cryptopanic_only and not narrative)
    early_source_ok = source_ok_for_long and _fresh_enough(data, snapshot)
    negative_source_ok = strong_source or source_strength == "tagged_context"
    if (
        _source_pack_requires_structured_unlock(source_pack, impact)
        or _source_pack_requires_official_exchange(source_pack, impact)
    ) and source_strength != "official_structured":
        negative_source_ok = False

    reasons: list[str] = list(market_reasons)
    warnings: list[str] = []
    why_not: list[str] = []
    confirms: list[str] = []
    invalidates: list[str] = []
    evidence: list[str] = []

    if source_class:
        evidence.append(f"source_class={source_class}")
    if source_pack:
        evidence.append(f"source_pack={source_pack}")
    if data.accepted_evidence_count:
        evidence.append(f"accepted_evidence={data.accepted_evidence_count}")
    if snapshot.observed_fields:
        evidence.append(f"market_fields={snapshot.observed_fields}")

    if _source_pack_requires_official_exchange(source_pack, impact) and source_strength != "official_structured":
        why_not.append("official_exchange_source_required")
        reasons.append("source_pack_requires_official_exchange")
    if _source_pack_requires_structured_unlock(source_pack, impact) and source_strength != "official_structured":
        why_not.append("structured_unlock_source_required")
        reasons.append("source_pack_requires_structured_unlock")
    if cryptopanic_only and narrative:
        why_not.append("cryptopanic_only_narrative_not_confirmed")
        warnings.append("cryptopanic_only_narrative_capped")
    if not market_sane:
        why_not.append("liquidity_sanity_missing")
        reasons.append("liquidity_sanity_failed")

    opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if diagnostic:
        opportunity = EventOpportunityType.DIAGNOSTIC.value
        confirms.append("diagnostic/control row only")
        invalidates.append("not an operator-facing opportunity")
        why_not.append("diagnostic_or_sector_row")
    elif fade_ready and source_ok_for_fade:
        opportunity = EventOpportunityType.FADE_SHORT_REVIEW.value
        confirms.extend(("completed move already visible", "crowding/exhaustion metrics present"))
        invalidates.extend(("funding/OI cools off", "price consolidates without failed reclaim"))
    elif negative:
        if negative_source_ok:
            opportunity = EventOpportunityType.RISK_ONLY.value
            confirms.append("confirm downside catalyst and market reaction before any review")
            invalidates.append("source correction or no token-specific impact")
        else:
            opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
            why_not.append("risk_source_not_confirmed")
            confirms.append("needs stronger risk source confirmation")
            invalidates.append("source correction or no token-specific impact")
    elif source_ok_for_long and market_confirmed and market_sane:
        opportunity = EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
        confirms.extend(("source is strong", "fresh market confirmation is present"))
        invalidates.extend(("market reaction fades", "source evidence is corrected or denied"))
    elif early_source_ok and market_state == EventMarketState.NO_REACTION.value:
        opportunity = EventOpportunityType.EARLY_LONG_RESEARCH.value
        confirms.extend(("watch for volume/relative-strength breakout", "seek second independent source"))
        invalidates.extend(("no market reaction after catalyst window", "source evidence is stale or corrected"))
    else:
        opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
        if not strong_source:
            why_not.append("strong_source_missing")
        if cryptopanic_only and narrative:
            why_not.append("source_only_narrative_requires_market_confirmation")
        if data.evidence_acquisition_status in {"rejected_results_only", "no_results", "skipped_budget"}:
            why_not.append(f"evidence_acquisition_{data.evidence_acquisition_status}")
        if not market_confirmed and market_state == EventMarketState.NO_REACTION.value:
            why_not.append("market_reaction_missing")
        confirms.append("needs stronger source and/or market confirmation")
        invalidates.append("unsupported catalyst-to-token mechanism")

    if opportunity == EventOpportunityType.CONFIRMED_LONG_RESEARCH.value and (cryptopanic_only or not market_confirmed or not source_ok_for_long or not market_sane):
        opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("confirmed_long_requirements_not_met")
        warnings.append("confirmed_lane_capped")
    if opportunity == EventOpportunityType.FADE_SHORT_REVIEW.value and not (fade_ready and exhaustion):
        opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("fade_short_requires_move_and_crowding")
        warnings.append("fade_lane_capped")
    if opportunity == EventOpportunityType.EARLY_LONG_RESEARCH.value and not early_source_ok:
        opportunity = EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("early_long_requires_fresh_strong_source")
        warnings.append("early_lane_capped")

    why_now = _why_now(opportunity, market_state, source_strength, snapshot)
    return MarketReactionResult(
        market_state_snapshot=snapshot,
        market_state=market_state,
        opportunity_type=opportunity,
        why_now=why_now,
        what_confirms=tuple(dict.fromkeys(confirms or ("seek source and market confirmation",))),
        what_invalidates=tuple(dict.fromkeys(invalidates or ("source correction or stale catalyst",))),
        why_not_alertable=tuple(dict.fromkeys(why_not)),
        evidence_summary=tuple(dict.fromkeys(evidence)),
        source_requirements_met=bool(source_ok_for_long if opportunity in {EventOpportunityType.EARLY_LONG_RESEARCH.value, EventOpportunityType.CONFIRMED_LONG_RESEARCH.value} else source_ok_for_fade),
        market_requirements_met=bool(market_confirmed and market_sane),
        fade_requirements_met=bool(fade_ready and exhaustion),
        source_strength=source_strength,
        warnings=tuple(dict.fromkeys(warnings)),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _input_from_mapping(row: Mapping[str, Any]) -> MarketReactionInput:
    market = _mapping(row.get("market_snapshot") or row.get("latest_market_snapshot") or row.get("market") or row.get("market_state_snapshot"))
    derivatives = _mapping(row.get("derivatives_snapshot") or row.get("derivatives") or row.get("perp"))
    dex = _mapping(row.get("dex_liquidity_snapshot") or row.get("dex_liquidity") or row.get("dex"))
    supply = _mapping(row.get("supply_snapshot") or row.get("supply"))
    components = _mapping(row.get("latest_score_components") or row.get("score_components"))
    if components:
        market = {**_mapping(components.get("market_snapshot") or components.get("latest_market_snapshot") or components.get("market_state_snapshot")), **market}
        derivatives = {**_mapping(components.get("derivatives_snapshot") or components.get("derivatives")), **derivatives}
        dex = {**_mapping(components.get("dex_liquidity_snapshot") or components.get("dex_liquidity")), **dex}
        supply = {**_mapping(components.get("supply_snapshot") or components.get("supply")), **supply}
    return MarketReactionInput(
        symbol=_first_text(row, components, "symbol", "validated_symbol"),
        coin_id=_first_text(row, components, "coin_id", "validated_coin_id"),
        row_type=_first_text(row, components, "row_type", "snapshot_class"),
        market_snapshot=market,
        derivatives_snapshot=derivatives,
        dex_liquidity_snapshot=dex,
        supply_snapshot=supply,
        source_class=_first_text(row, components, "source_class"),
        source_pack=_first_text(row, components, "source_pack", "evidence_acquisition_source_pack"),
        impact_path_type=_first_text(row, components, "impact_path_type", "primary_impact_path"),
        playbook_type=_first_text(row, components, "playbook_type", "effective_playbook_type"),
        candidate_role=_first_text(row, components, "candidate_role"),
        evidence_specificity=_first_text(row, components, "evidence_specificity"),
        evidence_quality_score=_float(_first_value(row, components, "evidence_quality_score", "source_quality")),
        accepted_evidence_count=_int(_first_value(row, components, "accepted_evidence_count", "evidence_acquisition_accepted_count")),
        accepted_reason_codes=tuple(_list_values(_first_value(row, components, "accepted_evidence_reason_codes", "accepted_reason_codes"))),
        evidence_acquisition_status=_first_text(row, components, "evidence_acquisition_status", "acquisition_status"),
        final_route_after_quality_gate=_first_text(row, components, "final_route_after_quality_gate", "route", "tier"),
        final_state_after_quality_gate=_first_text(row, components, "final_state_after_quality_gate", "state"),
        diagnostic_row_count=_int(_first_value(row, components, "diagnostic_row_count", "hidden_diagnostic_count")),
        source_noise_control_count=_int(_first_value(row, components, "source_noise_control_count")),
        market_confirmation_level=_first_text(row, components, "market_confirmation_level", "market_reaction_confirmation"),
        market_confirmation_score=_float(_first_value(row, components, "market_confirmation_score")),
        market_context_freshness_status=_first_text(row, components, "market_context_freshness_status", "market_data_freshness"),
        event_age_hours=_float(_first_value(row, components, "event_age_hours", "event_age")),
        catalyst_fresh=_bool_or_none(_first_value(row, components, "catalyst_fresh", "event_fresh")),
        negative_catalyst=_bool_or_none(_first_value(row, components, "negative_catalyst", "risk_catalyst")),
    )


def _build_snapshot(data: MarketReactionInput) -> MarketStateSnapshot:
    market = _mapping(data.market_snapshot)
    derivatives = _mapping(data.derivatives_snapshot)
    dex = _mapping(data.dex_liquidity_snapshot)
    supply = _mapping(data.supply_snapshot)
    market_unit = event_market_units.infer_return_unit(
        market,
        default=event_market_units.RETURN_UNIT_FRACTION,
        keys=(
            "return_5m",
            "return_15m",
            "return_1h",
            "return_4h",
            "return_24h",
            "price_change_5m",
            "price_change_15m",
            "price_change_1h",
            "price_change_4h",
            "price_change_24h",
            "price_change_percentage_24h",
            "relative_return_vs_btc",
            "relative_return_vs_eth",
            "relative_return_vs_sector",
            "rel_return_btc",
            "rel_return_eth",
            "rel_return_sector",
            "relative_strength_vs_btc",
            "relative_strength_vs_eth",
            "relative_strength_vs_sector",
        ),
    )
    values = {
        "return_5m": _pct(_first(market, "return_5m", "price_change_5m"), unit_hint=market_unit),
        "return_15m": _pct(_first(market, "return_15m", "price_change_15m"), unit_hint=market_unit),
        "return_1h": _pct(_first(market, "return_1h", "price_change_1h"), unit_hint=market_unit),
        "return_4h": _pct(_first(market, "return_4h", "price_change_4h"), unit_hint=market_unit),
        "return_24h": _pct(_first(market, "return_24h", "price_change_24h", "price_change_percentage_24h"), unit_hint=market_unit),
        "relative_return_vs_btc": _pct(_first(market, "relative_return_vs_btc", "rel_return_btc", "relative_strength_vs_btc"), unit_hint=market_unit),
        "relative_return_vs_eth": _pct(_first(market, "relative_return_vs_eth", "rel_return_eth", "relative_strength_vs_eth"), unit_hint=market_unit),
        "relative_return_vs_sector": _pct(_first(market, "relative_return_vs_sector", "rel_return_sector", "relative_strength_vs_sector"), unit_hint=market_unit),
        "volume_turnover_zscore": _float(_first(market, "volume_turnover_zscore", "volume_zscore_24h", "volume_zscore", "volume_z")),
        "volume_to_market_cap": _float(_first(market, "volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")),
        "liquidity_usd": _float(_first(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd")),
        "spread_bps": _float(_first(market, "spread_bps", "bid_ask_spread_bps")),
        "open_interest_delta": _pct(_first(derivatives, "open_interest_delta", "open_interest_24h_change_pct", "oi_change_24h", "oi_delta")),
        "funding_level": _pct(_first(derivatives, "funding_level", "funding_rate_8h", "funding_rate", "funding")),
        "funding_zscore": _float(_first(derivatives, "funding_zscore", "funding_rate_zscore")),
        "liquidation_imbalance": _float(_first(derivatives, "liquidation_imbalance", "long_liquidation_imbalance", "liquidation_skew")),
        "dex_volume_change": _pct(_first(dex, "dex_volume_change", "dex_volume_24h_change_pct", "volume_change_24h")),
        "dex_liquidity_change": _pct(_first(dex, "dex_liquidity_change", "liquidity_change_24h", "pool_liquidity_change_pct")),
        "event_age_hours": data.event_age_hours,
    }
    if values["volume_to_market_cap"] is None:
        volume = _float(_first(market, "volume_24h", "spot_volume_24h", "total_volume"))
        mcap = _float(_first(market, "market_cap", "mcap"))
        if volume is not None and mcap and mcap > 0:
            values["volume_to_market_cap"] = volume / mcap
    observed = sum(1 for value in values.values() if value is not None)
    if data.event_age_hours is None:
        values["event_age_hours"] = _float(_first(market, "event_age_hours", "age_hours"))
    if values["event_age_hours"] is None:
        values["event_age_hours"] = _float(_first(supply, "event_age_hours"))
    return MarketStateSnapshot(
        **values,
        freshness_status=data.market_context_freshness_status or _first_text(market, {}, "market_context_freshness_status", "freshness_status"),
        source=_first_text(market, {}, "market_context_source", "source", "provider"),
        return_unit=event_market_units.RETURN_UNIT_PERCENT_POINTS,
        source_return_unit=market_unit,
        threshold_unit=event_market_units.RETURN_UNIT_PERCENT_POINTS,
        unit_warnings=event_market_units.validate_market_snapshot_units(
            {"return_unit": event_market_units.RETURN_UNIT_PERCENT_POINTS, **{key: values.get(key) for key in ("return_1h", "return_4h", "return_24h")}},
            market,
        ),
        observed_fields=observed,
    )


def _classify_market_state(snapshot: MarketStateSnapshot, *, negative: bool, impact: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    r1h = snapshot.return_1h or 0.0
    r4h = snapshot.return_4h or 0.0
    r24 = snapshot.return_24h or 0.0
    rel_btc = snapshot.relative_return_vs_btc or 0.0
    vol_z = snapshot.volume_turnover_zscore or 0.0
    v_mcap = snapshot.volume_to_market_cap or 0.0
    crowded = _has_crowding(snapshot)
    event_passed = snapshot.event_age_hours is not None and snapshot.event_age_hours >= 0
    if r24 <= -12 or (negative and r24 <= -5):
        reasons.append("downside_market_pressure")
        return EventMarketState.RISK_OFF_SELL_PRESSURE.value, reasons
    if event_passed and r24 >= 35 and crowded:
        reasons.extend(("post_event_move_complete", "crowding_present"))
        return EventMarketState.POST_EVENT_FADE_SETUP.value, reasons
    if (r24 >= 45 or r4h >= 25) and crowded:
        reasons.extend(("large_move", "crowding_present"))
        return EventMarketState.BLOWOFF_CROWDED.value, reasons
    if r24 >= 12 and (vol_z >= 2.0 or v_mcap >= 0.20 or rel_btc >= 8):
        reasons.append("price_volume_breakout")
        return EventMarketState.CONFIRMED_BREAKOUT.value, reasons
    if 2 <= r4h <= 15 and (vol_z >= 1.0 or rel_btc >= 3):
        reasons.append("quiet_relative_strength")
        return EventMarketState.STEALTH_ACCUMULATION.value, reasons
    if r24 >= 25 or r4h >= 18:
        reasons.append("late_price_momentum")
        return EventMarketState.LATE_MOMENTUM.value, reasons
    reasons.append("no_material_market_reaction")
    return EventMarketState.NO_REACTION.value, reasons


def _diagnostic_context(data: MarketReactionInput, impact: str, source_pack: str) -> bool:
    symbol = _text(data.symbol).casefold()
    coin_id = _text(data.coin_id).casefold()
    route = _text(data.final_route_after_quality_gate).casefold()
    state = _text(data.final_state_after_quality_gate).casefold()
    row_type = _text(data.row_type).casefold()
    text = f"{impact} {source_pack} {route} {state} {row_type}"
    return any((
        symbol == "sector",
        coin_id.startswith("sector") or coin_id in {"sports_fan_proxy", "market_anomaly", "unknown"},
        "source_noise" in text,
        "ticker_collision" in text,
        "diagnostic" in text,
        "ambiguous_control" in text,
        bool(data.source_noise_control_count and data.source_noise_control_count > 0 and route in {"store_only", "suppress_duplicate", "local_report"}),
    ))


def _source_strength(data: MarketReactionInput) -> str:
    source_class = _text(data.source_class).casefold()
    specificity = _text(data.evidence_specificity).casefold()
    reasons = {item.casefold() for item in data.accepted_reason_codes}
    score = data.evidence_quality_score or 0.0
    if source_class in {"official_project", "official_exchange", "structured_calendar", "structured_unlock", "tokenomist", "messari_intel"}:
        return "official_structured"
    if any(reason in reasons for reason in ("official_exchange_announcement", "official_project_source", "structured_unlock_evidence")):
        return "official_structured"
    if specificity in {"token_and_catalyst", "direct_token_mechanism"} and score >= 75:
        return "strong"
    if source_class == "cryptopanic_tagged" and "cryptopanic_currency_tag_match" in reasons:
        return "tagged_context"
    if score >= 75:
        return "strong"
    if score >= 55:
        return "medium"
    return "weak"


def _cryptopanic_only(data: MarketReactionInput) -> bool:
    source_class = _text(data.source_class).casefold()
    reasons = {item.casefold() for item in data.accepted_reason_codes}
    return source_class == "cryptopanic_tagged" or "cryptopanic_currency_tag_match" in reasons


def _source_only_narrative(impact: str, source_pack: str) -> bool:
    text = f"{impact} {source_pack}"
    return any(token in text for token in ("fan", "sports", "proxy", "preipo", "pre_ipo", "rwa", "political_meme"))


def _negative_impact(impact: str, source_pack: str) -> bool:
    text = f"{impact} {source_pack}"
    return any(token in text for token in ("unlock", "exploit", "security", "regulatory", "risk", "delisting", "supply"))


def _source_pack_requires_official_exchange(source_pack: str, impact: str) -> bool:
    text = f"{source_pack} {impact}"
    return "listing" in text or "perp" in text or "launchpool" in text


def _source_pack_requires_structured_unlock(source_pack: str, impact: str) -> bool:
    text = f"{source_pack} {impact}"
    return "unlock" in text or "supply" in text


def _has_crowding(snapshot: MarketStateSnapshot) -> bool:
    return any((
        snapshot.open_interest_delta is not None and snapshot.open_interest_delta >= 25,
        snapshot.funding_level is not None and abs(snapshot.funding_level) >= 0.05,
        snapshot.funding_zscore is not None and abs(snapshot.funding_zscore) >= 2,
        snapshot.liquidation_imbalance is not None and abs(snapshot.liquidation_imbalance) >= 1.5,
    ))


def _completed_move(snapshot: MarketStateSnapshot, market_state: str) -> bool:
    return any((
        market_state in {
            EventMarketState.BLOWOFF_CROWDED.value,
            EventMarketState.POST_EVENT_FADE_SETUP.value,
            EventMarketState.LATE_MOMENTUM.value,
        },
        snapshot.return_24h is not None and snapshot.return_24h >= 30,
        snapshot.return_4h is not None and snapshot.return_4h >= 20,
    ))


def _volume_exhausted(snapshot: MarketStateSnapshot) -> bool:
    return any((
        snapshot.volume_turnover_zscore is not None and snapshot.volume_turnover_zscore >= 4,
        snapshot.volume_to_market_cap is not None and snapshot.volume_to_market_cap >= 0.35,
    ))


def _liquidity_sane(snapshot: MarketStateSnapshot) -> bool:
    if snapshot.spread_bps is not None and snapshot.spread_bps > 150:
        return False
    if snapshot.liquidity_usd is not None and snapshot.liquidity_usd < 50_000:
        return False
    return True


def _fresh_enough(data: MarketReactionInput, snapshot: MarketStateSnapshot) -> bool:
    if data.catalyst_fresh is True:
        return True
    if data.catalyst_fresh is False:
        return False
    if snapshot.event_age_hours is None:
        return True
    return -72 <= snapshot.event_age_hours <= 24


def _level_at_least(level: str | None, score: float | None, threshold: str) -> bool:
    rank = {"none": 0, "missing": 0, "unknown": 0, "weak": 1, "moderate": 2, "strong": 3}
    if score is not None:
        if threshold == "moderate":
            return score >= 50
        if threshold == "strong":
            return score >= 75
    return rank.get(_text(level).casefold(), 0) >= rank.get(threshold, 0)


def _why_now(opportunity: str, market_state: str, source_strength: str, snapshot: MarketStateSnapshot) -> str:
    if opportunity == EventOpportunityType.EARLY_LONG_RESEARCH.value:
        return f"strong source with {market_state.replace('_', ' ')}; monitor before the move is crowded"
    if opportunity == EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return f"strong source plus {market_state.replace('_', ' ')}"
    if opportunity == EventOpportunityType.FADE_SHORT_REVIEW.value:
        return "move appears crowded/exhausted; review only for fade risk after deterministic gates"
    if opportunity == EventOpportunityType.UNCONFIRMED_RESEARCH.value:
        return f"interesting context, but confirmation is missing; market state is {market_state.replace('_', ' ')}"
    if opportunity == EventOpportunityType.DIAGNOSTIC.value:
        return "diagnostic/control context; keep out of default operator lanes"
    if opportunity == EventOpportunityType.RISK_ONLY.value:
        return f"credible risk catalyst with {market_state.replace('_', ' ')}"
    if snapshot.observed_fields == 0:
        return "insufficient market reaction data; keep as risk/local research"
    return f"{market_state.replace('_', ' ')} with {source_strength.replace('_', ' ')} source strength"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _first_value(row: Mapping[str, Any], components: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return value
        value = components.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _first_text(row: Mapping[str, Any], components: Mapping[str, Any], *keys: str) -> str | None:
    value = _first_value(row, components, *keys)
    text = str(value or "").strip()
    return text or None


def _list_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Mapping):
        return [str(key) for key, count in value.items() if count]
    try:
        return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]
    except TypeError:
        return [str(value).strip()] if str(value).strip() else []


def _float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _pct(value: object, *, unit_hint: str | None = None) -> float | None:
    if unit_hint:
        return event_market_units.normalize_return_percent_points(value, unit_hint)
    number = _float(value)
    if number is None:
        return None
    if abs(number) <= 3.0:
        return number * 100.0
    return number


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _text(value: object) -> str:
    return str(value or "").strip()
