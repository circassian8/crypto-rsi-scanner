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
    DIRECT_EVENT = "direct_event"
    INFRASTRUCTURE_MENTION = "infrastructure_mention"
    MARKET_ANOMALY = "market_anomaly"
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
            EventPlaybookType.MARKET_ANOMALY,
            _market_anomaly_score(components),
            EventPlaybookAction.STORE_ONLY,
            False,
            "STORE_ONLY",
            "Market anomaly is catalyst-discovery evidence only until a dated external source is validated.",
            tuple(candidate.link.evidence),
            ("requires catalyst evidence",),
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
        )

    return _assessment(
        EventPlaybookType.AMBIGUOUS_CONTROL,
        _control_score(components),
        EventPlaybookAction.STORE_ONLY,
        False,
        "STORE_ONLY",
        "Candidate lacks a clear proxy, direct, infrastructure, or catalyst playbook.",
        tuple(candidate.link.evidence),
    )


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
) -> EventPlaybookAssessment:
    return EventPlaybookAssessment(
        playbook_type=playbook_type.value,
        playbook_score=_clamp(score),
        recommended_action=action.value,
        can_trigger_fade=can_trigger_fade,
        max_research_tier=max_tier,
        reason=reason,
        evidence=tuple(dict.fromkeys(str(item) for item in evidence if item)),
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if item)),
    )


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, float(value)))))
