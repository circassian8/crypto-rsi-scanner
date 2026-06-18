"""Deterministic research playbooks for Event Alpha Radar candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from . import event_fade
from .event_classification import (
    ROLE_AMBIGUOUS,
    ROLE_DIRECT_BENEFICIARY,
    ROLE_INFRASTRUCTURE,
    ROLE_MENTIONED_ASSET,
    ROLE_PROXY_INSTRUMENT,
    ROLE_PROXY_VENUE,
    ROLE_TICKER_WORD_COLLISION,
)
from .event_models import DiscoveredEventFadeCandidate
from .event_resolver import SOURCE_PUBLISHER_NAMES, clean_text, is_market_recap_event


class EventPlaybookType(str, Enum):
    PROXY_FADE = "proxy_fade"
    PROXY_ATTENTION = "proxy_attention"
    LISTING_VOLATILITY = "listing_volatility"
    PERP_LISTING_SQUEEZE = "perp_listing_squeeze"
    UNLOCK_SUPPLY_PRESSURE = "unlock_supply_pressure"
    AIRDROP_TGE_SELL_PRESSURE = "airdrop_tge_sell_pressure"
    FAN_SPORTS_EVENT = "fan_sports_event"
    POLITICAL_MEME_EVENT = "political_meme_event"
    RWA_PREIPO_PROXY = "rwa_preipo_proxy"
    AI_IPO_PROXY = "ai_ipo_proxy"
    SECURITY_OR_REGULATORY_SHOCK = "security_or_regulatory_shock"
    DIRECT_EVENT = "direct_event"
    INFRASTRUCTURE_MENTION = "infrastructure_mention"
    MARKET_ANOMALY = "market_anomaly"
    MARKET_ANOMALY_UNKNOWN = "market_anomaly_unknown"
    SOURCE_NOISE_CONTROL = "source_noise_control"
    AMBIGUOUS_CONTROL = "ambiguous_control"


class EventPlaybookAction(str, Enum):
    STORE_ONLY = "store_only"
    RADAR_DIGEST = "radar_digest"
    WATCHLIST = "watchlist"
    HIGH_PRIORITY_WATCH = "high_priority_watch"
    TRIGGERED_FADE_ALLOWED = "triggered_fade_allowed"


@dataclass(frozen=True)
class EventPlaybookAssessment:
    playbook_type: str
    playbook_score: int
    recommended_action: str
    can_trigger_fade: bool
    max_research_tier: str
    reason: str
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    hypothesis: str = ""
    what_to_verify: tuple[str, ...] = ()
    timing_window: str = ""
    invalidation: str = ""
    expected_direction: str = "unknown"
    primary_horizon: str = "24h"
    success_metric: str = "manual"


def outcome_profile_for_playbook(playbook_type: str | EventPlaybookType | None) -> tuple[str, str, str]:
    """Return expected direction, primary horizon, and success metric for a playbook."""
    try:
        resolved = playbook_type if isinstance(playbook_type, EventPlaybookType) else EventPlaybookType(str(playbook_type))
    except (TypeError, ValueError):
        return "unknown", "24h", "manual"
    return _outcome_profile(resolved)


def assess_event_playbook(
    candidate: DiscoveredEventFadeCandidate,
    components: Mapping[str, int],
    *,
    rejected_reason: str | None = None,
) -> EventPlaybookAssessment:
    """Classify the candidate into a deterministic research playbook."""
    cls = candidate.classification
    event = candidate.event
    role = cls.asset_role
    relationship = cls.relationship_type
    signal_type = candidate.fade_signal.signal_type if candidate.fade_signal else event_fade.FadeSignalType.NO_TRADE

    if event.event_type == "market_anomaly" or event.source == "market_anomaly":
        return _assessment(
            EventPlaybookType.MARKET_ANOMALY_UNKNOWN,
            _market_anomaly_score(components),
            EventPlaybookAction.STORE_ONLY,
            False,
            "STORE_ONLY",
            "Market anomaly is catalyst-discovery evidence only until a dated external source is validated.",
            tuple(candidate.link.evidence),
            ("requires catalyst evidence",),
            hypothesis="The asset is moving unusually, but the catalyst is unknown.",
            what_to_verify=("find dated source evidence", "verify the asset identity is not a ticker collision"),
            timing_window="observe until a catalyst source is found or the anomaly fades",
            invalidation="No credible catalyst appears, or liquidity/volume normalizes.",
        )

    if _is_source_noise(candidate, rejected_reason):
        return _assessment(
            EventPlaybookType.SOURCE_NOISE_CONTROL,
            _control_score(components),
            EventPlaybookAction.STORE_ONLY,
            False,
            "STORE_ONLY",
            "Asset evidence appears to be publisher/source noise, a ticker word collision, or recap context.",
            (*cls.evidence, *(rejected_reason.split("; ") if rejected_reason else ())),
            hypothesis="This is likely not a tradable event-alpha relationship.",
            what_to_verify=("confirm the term is not the crypto asset", "keep as a negative-control row"),
            timing_window="store for QA only",
            invalidation="A primary source explicitly names the crypto asset as the event vehicle.",
        )

    if _is_proxy_fade_candidate(candidate, rejected_reason):
        score = _proxy_fade_score(components)
        return _assessment(
            EventPlaybookType.PROXY_FADE,
            score,
            _proxy_fade_action(score, signal_type),
            True,
            "TRIGGERED_FADE",
            "Dated proxy-instrument catalyst with deterministic event-fade eligibility.",
            (*cls.evidence, *cls.asset_role_evidence),
            hypothesis="A temporary proxy narrative may unwind after the dated catalyst passes.",
            what_to_verify=("confirm proxy instrument role", "confirm post-event failure and invalidation level"),
            timing_window="after catalyst time and failed reclaim/lower-high confirmation",
            invalidation="Proxy narrative persists or price reclaims the event VWAP/invalidation level.",
        )

    if role == ROLE_INFRASTRUCTURE or relationship == "proxy_context":
        return _assessment(
            EventPlaybookType.INFRASTRUCTURE_MENTION if role == ROLE_INFRASTRUCTURE else EventPlaybookType.AMBIGUOUS_CONTROL,
            _control_score(components),
            EventPlaybookAction.STORE_ONLY,
            False,
            "RADAR_DIGEST" if role == ROLE_INFRASTRUCTURE else "STORE_ONLY",
            (
                "Asset is infrastructure/context around the event, not the proxy instrument."
                if role == ROLE_INFRASTRUCTURE
                else "Proxy context exists, but the linked asset role is not fade-eligible."
            ),
            (*cls.evidence, *cls.asset_role_evidence),
            hypothesis="The asset may benefit indirectly as infrastructure/context, not as the event proxy.",
            what_to_verify=("verify whether the asset is infrastructure only", "check if another asset is the actual proxy"),
            timing_window="local review only until a direct catalyst relationship is proven",
            invalidation="The asset is only a background mention or data provider.",
        )

    specific = _specific_playbook(candidate)
    if specific is not None:
        playbook_type, reason, hypothesis, verify, timing, invalidation = specific
        score = _specific_playbook_score(playbook_type, components)
        return _assessment(
            playbook_type,
            score,
            _non_fade_action(score),
            False,
            "HIGH_PRIORITY_WATCH" if score >= 80 else "WATCHLIST" if score >= 65 else "RADAR_DIGEST",
            reason,
            (*cls.evidence, *cls.asset_role_evidence),
            hypothesis=hypothesis,
            what_to_verify=verify,
            timing_window=timing,
            invalidation=invalidation,
        )

    if cls.is_direct_beneficiary or role == ROLE_DIRECT_BENEFICIARY or relationship.startswith("direct_"):
        return _assessment(
            EventPlaybookType.DIRECT_EVENT,
            _control_score(components),
            EventPlaybookAction.STORE_ONLY,
            False,
            "STORE_ONLY",
            "Event directly affects the linked token/listing/supply/protocol; not a proxy-fade playbook.",
            cls.evidence,
            hypothesis="The event may create directional volatility, but it is not a proxy-fade setup.",
            what_to_verify=("identify event mechanics", "separate direct-event behavior from proxy-fade evidence"),
            timing_window="around event publication and first post-event trading sessions",
            invalidation="No measurable volume/price reaction or event was already priced in.",
        )

    if cls.is_proxy_narrative or relationship in {"proxy_attention", "proxy_exposure"} or role == ROLE_PROXY_VENUE:
        score = _proxy_attention_score(components)
        return _assessment(
            EventPlaybookType.PROXY_ATTENTION,
            score,
            _proxy_attention_action(score, components),
            False,
            "WATCHLIST",
            "Proxy narrative or proxy venue evidence needs more catalyst/timing/market confirmation before fade eligibility.",
            (*cls.evidence, *cls.asset_role_evidence),
            ("proxy venue is review-only by default",) if role == ROLE_PROXY_VENUE else (),
            hypothesis="A proxy narrative may be forming before enough timing/failure evidence exists.",
            what_to_verify=("confirm dated catalyst", "confirm the asset is proxy instrument rather than venue"),
            timing_window="pre-event monitoring until catalyst timing and market confirmation improve",
            invalidation="No dated catalyst emerges, or the linked asset is only infrastructure/venue noise.",
        )

    return _assessment(
        EventPlaybookType.AMBIGUOUS_CONTROL,
        _control_score(components),
        EventPlaybookAction.STORE_ONLY,
        False,
        "STORE_ONLY",
        "Candidate lacks a clear proxy, direct, infrastructure, or catalyst playbook.",
        tuple(candidate.link.evidence),
        hypothesis="The row is useful as review/control evidence but not actionable.",
        what_to_verify=("look for missing catalyst evidence", "reject if identity/catalyst stays ambiguous"),
        timing_window="store-only review",
        invalidation="No independent source supports the asset/catalyst relationship.",
    )


def _specific_playbook(
    candidate: DiscoveredEventFadeCandidate,
) -> tuple[EventPlaybookType, str, str, tuple[str, ...], str, str] | None:
    event = candidate.event
    text = clean_text(f"{event.event_name} {event.description or ''} {event.event_type}")
    external = clean_text(event.external_asset)
    if event.event_type == "perp_listing" or "perp" in text or "futures" in text:
        return (
            EventPlaybookType.PERP_LISTING_SQUEEZE,
            "Perp/futures listing can create early leverage and squeeze risk; not a proxy-fade trigger.",
            "New derivatives access may amplify volatility around the listing window.",
            ("confirm listing venue and contract launch time", "check funding/open-interest expansion"),
            "first hours to two days after perp market opens",
            "No OI/funding expansion or spot volume fades quickly.",
        )
    if event.event_type == "exchange_listing" or "listing" in text:
        return (
            EventPlaybookType.LISTING_VOLATILITY,
            "Exchange listing can create direct event volatility; not a proxy-fade trigger.",
            "Fresh venue access may create a listing pop/fade or liquidity regime change.",
            ("confirm spot listing details", "separate listing flow from external proxy narrative"),
            "announcement through first 24-72h of trading",
            "No material volume/price response after listing goes live.",
        )
    if event.event_type == "token_unlock" or "unlock" in text or "vesting" in text:
        return (
            EventPlaybookType.UNLOCK_SUPPLY_PRESSURE,
            "Unlock/vesting event may add supply pressure; not a proxy-fade trigger.",
            "New circulating supply may pressure price if liquidity is thin.",
            ("confirm unlock size vs circulating supply", "check exchange/team wallet flows"),
            "pre-unlock through 7d post-unlock",
            "Unlock is small, already hedged, or flows do not reach liquid venues.",
        )
    if event.event_type in {"airdrop", "tge"} or "airdrop" in text or "tge" in text:
        return (
            EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE,
            "Airdrop/TGE event may create recipient sell pressure; not a proxy-fade trigger.",
            "New claimable tokens may be sold into early liquidity.",
            ("confirm claim/TGE timing", "check float, recipient distribution, and exchange availability"),
            "claim/TGE window through first 72h",
            "Claim is delayed, illiquid, or recipients cannot sell freely.",
        )
    if event.event_type == "sports_event" or "world cup" in text or "match" in text or "fan token" in text:
        return (
            EventPlaybookType.FAN_SPORTS_EVENT,
            "Sports/fan-token narrative can create attention-driven event volatility.",
            "Fan-token demand may rise into the fixture and fade after attention peaks.",
            ("confirm team/token link", "confirm kickoff/event time and venue liquidity"),
            "pre-match buildup through post-match reaction",
            "Fan narrative broadens or the token has no direct fan-event attention.",
        )
    if event.event_type == "political_event" or "election" in text or "inauguration" in text:
        return (
            EventPlaybookType.POLITICAL_MEME_EVENT,
            "Political meme event can create attention-driven volatility.",
            "Narrative attention may peak around a dated political catalyst.",
            ("confirm event time", "confirm token is the meme/proxy vehicle"),
            "pre-event attention through first post-event session",
            "Narrative shifts away from the token or catalyst timing is weak.",
        )
    if "security" in text or "hack" in text or "exploit" in text or "sec " in text or "lawsuit" in text or "regulatory" in text:
        return (
            EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK,
            "Security/regulatory shock may create direct risk; not a proxy-fade trigger.",
            "Negative catalyst may change liquidity/risk premia quickly.",
            ("confirm primary-source incident/regulatory evidence", "check venue/liquidity availability"),
            "incident publication through first 24-72h",
            "Incident is false, contained, or unrelated to the linked asset.",
        )
    if event.event_type in {"ipo_proxy", "external_proxy_event"} or "pre ipo" in text or "pre-ipo" in text:
        if external in {"openai", "anthropic"} or "openai" in text or "anthropic" in text or " ai " in f" {text} ":
            return (
                EventPlaybookType.AI_IPO_PROXY,
                "AI IPO proxy narrative is a specialized proxy-attention/fade research sleeve.",
                "AI private-market attention may spill into a crypto proxy before the external catalyst expires.",
                ("confirm AI company catalyst", "confirm the asset is instrument/venue, not news noise"),
                "pre-catalyst buildup through post-catalyst failure confirmation",
                "No dated AI catalyst or no token-specific proxy evidence.",
            )
        return (
            EventPlaybookType.RWA_PREIPO_PROXY,
            "Pre-IPO/RWA proxy narrative is a specialized proxy-attention/fade research sleeve.",
            "Tokenized/pre-IPO exposure narrative may unwind after attention/catalyst expiry.",
            ("confirm external asset and proxy mechanics", "confirm post-event technical failure before fade"),
            "pre-catalyst buildup through post-catalyst failure confirmation",
            "Proxy mechanics are unproven or the external catalyst is not dated.",
        )
    return None


def _specific_playbook_score(playbook_type: EventPlaybookType, components: Mapping[str, int]) -> int:
    if playbook_type in {EventPlaybookType.RWA_PREIPO_PROXY, EventPlaybookType.AI_IPO_PROXY}:
        return _proxy_attention_score(components)
    if playbook_type in {EventPlaybookType.FAN_SPORTS_EVENT, EventPlaybookType.POLITICAL_MEME_EVENT}:
        return _proxy_attention_score(components)
    if playbook_type in {EventPlaybookType.UNLOCK_SUPPLY_PRESSURE, EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE}:
        return _clamp(
            components.get("asset_resolution", 0) * 0.25
            + components.get("event_time_quality", 0) * 0.20
            + components.get("market_move_volume", 0) * 0.25
            + components.get("source_quality", 0) * 0.15
            + components.get("classifier", 0) * 0.15
        )
    return _clamp(
        components.get("asset_resolution", 0) * 0.25
        + components.get("source_quality", 0) * 0.20
        + components.get("market_move_volume", 0) * 0.25
        + components.get("derivatives_crowding", 0) * 0.15
        + components.get("event_time_quality", 0) * 0.15
    )


def _non_fade_action(score: int) -> EventPlaybookAction:
    if score >= 80:
        return EventPlaybookAction.HIGH_PRIORITY_WATCH
    if score >= 65:
        return EventPlaybookAction.WATCHLIST
    if score >= 45:
        return EventPlaybookAction.RADAR_DIGEST
    return EventPlaybookAction.STORE_ONLY


def _is_proxy_fade_candidate(candidate: DiscoveredEventFadeCandidate, rejected_reason: str | None) -> bool:
    cls = candidate.classification
    event = candidate.event
    return bool(
        not rejected_reason
        and cls.is_proxy_narrative
        and not cls.is_direct_beneficiary
        and cls.asset_role == ROLE_PROXY_INSTRUMENT
        and cls.relationship_type == "proxy_exposure"
        and event.event_time is not None
        and event.event_time_confidence >= 0.80
    )


def _is_source_noise(candidate: DiscoveredEventFadeCandidate, rejected_reason: str | None) -> bool:
    cls = candidate.classification
    if cls.asset_role in {ROLE_TICKER_WORD_COLLISION, ROLE_MENTIONED_ASSET, ROLE_AMBIGUOUS}:
        return True
    evidence = {clean_text(item) for item in candidate.link.evidence}
    if evidence and evidence.issubset(SOURCE_PUBLISHER_NAMES):
        return True
    reason = rejected_reason or ""
    return "publisher/source-only" in reason or "ticker_word_collision" in reason or is_market_recap_event(candidate.event)


def _proxy_fade_score(components: Mapping[str, int]) -> int:
    return _clamp(
        components.get("proxy_relationship", 0) * 0.20
        + components.get("external_catalyst", 0) * 0.20
        + components.get("event_time_quality", 0) * 0.15
        + components.get("market_move_volume", 0) * 0.15
        + components.get("derivatives_crowding", 0) * 0.10
        + components.get("fade_score", 0) * 0.20
    )


def _proxy_attention_score(components: Mapping[str, int]) -> int:
    return _clamp(
        components.get("proxy_relationship", 0) * 0.30
        + components.get("external_catalyst", 0) * 0.25
        + components.get("market_move_volume", 0) * 0.15
        + components.get("source_quality", 0) * 0.15
        + components.get("novelty_freshness", 0) * 0.15
    )


def _market_anomaly_score(components: Mapping[str, int]) -> int:
    return _clamp(
        components.get("market_move_volume", 0) * 0.50
        + components.get("source_quality", 0) * 0.20
        + components.get("asset_resolution", 0) * 0.20
        + components.get("derivatives_crowding", 0) * 0.10
    )


def _control_score(components: Mapping[str, int]) -> int:
    return _clamp(
        components.get("asset_resolution", 0) * 0.35
        + components.get("source_quality", 0) * 0.35
        + components.get("classifier", 0) * 0.30
    )


def _proxy_fade_action(score: int, signal_type: event_fade.FadeSignalType) -> EventPlaybookAction:
    if signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED:
        return EventPlaybookAction.TRIGGERED_FADE_ALLOWED
    if score >= 80:
        return EventPlaybookAction.HIGH_PRIORITY_WATCH
    if score >= 65:
        return EventPlaybookAction.WATCHLIST
    return EventPlaybookAction.RADAR_DIGEST


def _proxy_attention_action(score: int, components: Mapping[str, int]) -> EventPlaybookAction:
    if score >= 70 and components.get("market_move_volume", 0) >= 40:
        return EventPlaybookAction.WATCHLIST
    if score >= 50:
        return EventPlaybookAction.RADAR_DIGEST
    return EventPlaybookAction.STORE_ONLY


def _assessment(
    playbook_type: EventPlaybookType,
    score: int,
    action: EventPlaybookAction,
    can_trigger_fade: bool,
    max_tier: str,
    reason: str,
    evidence: tuple[str, ...],
    warnings: tuple[str, ...] = (),
    hypothesis: str = "",
    what_to_verify: tuple[str, ...] = (),
    timing_window: str = "",
    invalidation: str = "",
) -> EventPlaybookAssessment:
    expected_direction, primary_horizon, success_metric = _outcome_profile(playbook_type)
    return EventPlaybookAssessment(
        playbook_type=playbook_type.value,
        playbook_score=_clamp(score),
        recommended_action=action.value,
        can_trigger_fade=can_trigger_fade,
        max_research_tier=max_tier,
        reason=reason,
        evidence=tuple(dict.fromkeys(str(item) for item in evidence if item)),
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if item)),
        hypothesis=hypothesis,
        what_to_verify=tuple(dict.fromkeys(str(item) for item in what_to_verify if item)),
        timing_window=timing_window,
        invalidation=invalidation,
        expected_direction=expected_direction,
        primary_horizon=primary_horizon,
        success_metric=success_metric,
    )


def _outcome_profile(playbook_type: EventPlaybookType) -> tuple[str, str, str]:
    if playbook_type == EventPlaybookType.PROXY_FADE:
        return "down", "72h", "mfe_mae"
    if playbook_type in {
        EventPlaybookType.UNLOCK_SUPPLY_PRESSURE,
        EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE,
        EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK,
    }:
        return "down", "72h", "direction_hit"
    if playbook_type in {
        EventPlaybookType.LISTING_VOLATILITY,
        EventPlaybookType.PERP_LISTING_SQUEEZE,
        EventPlaybookType.DIRECT_EVENT,
    }:
        return "volatility", "24h", "volatility"
    if playbook_type in {
        EventPlaybookType.PROXY_ATTENTION,
        EventPlaybookType.FAN_SPORTS_EVENT,
        EventPlaybookType.POLITICAL_MEME_EVENT,
        EventPlaybookType.RWA_PREIPO_PROXY,
        EventPlaybookType.AI_IPO_PROXY,
    }:
        return "up_then_fade", "72h", "mfe_mae"
    return "unknown", "24h", "manual"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, float(value)))))
