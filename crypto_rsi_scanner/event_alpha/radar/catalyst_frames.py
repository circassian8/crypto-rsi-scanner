"""Main-catalyst frames for Event Alpha source evidence.

This module separates the event the article is primarily about from background
and corrective context. It is pure research metadata; it cannot create alerts,
trades, paper rows, normal RSI rows, or event-fade triggers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from ... import event_claim_semantics
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from ...event_resolver import clean_text


CATALYST_FRAME_SCHEMA_VERSION = "event_catalyst_frames_v1"

ROLE_MAIN = "main_catalyst"
ROLE_BACKGROUND = "background_context"
ROLE_HISTORICAL = "historical_context"
ROLE_NEGATED = "negated_claim"
ROLE_CORRECTIVE = "corrective_context"
ROLE_SIDE_NOTE = "side_note"
ROLE_MARKET_REACTION = "market_reaction"
ROLE_UNKNOWN = "unknown"

TYPE_STRATEGIC_INVESTMENT = "strategic_investment"
TYPE_ACQUISITION_OR_STAKE = "acquisition_or_stake"
TYPE_VALUATION_EVENT = "valuation_event"
TYPE_EXPLOIT_SECURITY = "exploit_security_event"
TYPE_PRIOR_EXPLOIT_CONTEXT = "prior_exploit_context"
TYPE_DENIED_EXPLOIT = "denied_or_negated_exploit"
TYPE_LISTING_LIQUIDITY = "listing_liquidity_event"
TYPE_UNLOCK_SUPPLY = "unlock_supply_event"
TYPE_MARKET_DISLOCATION = "market_dislocation_unknown"
TYPE_PROXY_ATTENTION = "proxy_attention"
TYPE_POLICY_CONTEXT = "policy_or_regulatory_context"
TYPE_GENERIC_CONTEXT = "generic_context"

_BACKGROUND_MARKERS = (
    "after the fallout from",
    "despite",
    "following",
    "amid",
    "in the wake of",
    "previously",
    "earlier",
    "since april",
    "fallout from",
    "unrelated to",
)
_NEGATED_SECURITY_PHRASES = (
    "not being hacked",
    "not hacked",
    "no exploit",
    "no hack",
    "without an exploit",
    "exploit ruled out",
    "hack ruled out",
    "ruled out exploit",
)


@dataclass(frozen=True)
class EventCatalystFrame:
    frame_id: str
    frame_type: str
    frame_role: str
    subject: str | None
    actor: str | None = None
    object: str | None = None
    affected_entities: tuple[str, ...] = ()
    affected_assets: tuple[str, ...] = ()
    event_archetype: str | None = None
    claim_polarity: str = event_claim_semantics.ClaimPolarity.UNKNOWN.value
    cause_status: str = event_claim_semantics.CauseStatus.UNKNOWN.value
    confidence: float = 0.0
    evidence_quote: str = ""
    source_raw_id: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None


def build_catalyst_frames(
    raw_events: Iterable[RawDiscoveredEvent],
    *,
    event: NormalizedEvent | None = None,
) -> tuple[EventCatalystFrame, ...]:
    """Extract deterministic catalyst/context frames from raw source rows."""
    frames: list[EventCatalystFrame] = []
    for raw in raw_events:
        frames.extend(_frames_from_raw(raw, event=event))
    if not frames and event is not None:
        frames.extend(_frames_from_text(
            " ".join(str(part or "") for part in (event.event_name, event.description, event.event_type)),
            title=event.event_name,
            raw=None,
            event=event,
        ))
    return tuple(_dedupe_frames(frames))


def select_main_catalyst_frame(
    frames: Iterable[EventCatalystFrame],
    source_context: object | None = None,
) -> tuple[EventCatalystFrame | None, tuple[EventCatalystFrame, ...]]:
    """Pick the main frame and keep all other frames as support/context."""
    rows = tuple(frames)
    if not rows:
        return None, ()
    ranked = sorted(rows, key=lambda frame: _frame_priority(frame, source_context), reverse=True)
    main = ranked[0]
    supporting = tuple(frame for frame in rows if frame.frame_id != main.frame_id)
    return main, supporting


def frame_summary(frames: Iterable[EventCatalystFrame]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "frame_id": frame.frame_id,
            "frame_type": frame.frame_type,
            "frame_role": frame.frame_role,
            "subject": frame.subject,
            "actor": frame.actor,
            "object": frame.object,
            "event_archetype": frame.event_archetype,
            "claim_polarity": frame.claim_polarity,
            "cause_status": frame.cause_status,
            "confidence": round(float(frame.confidence or 0.0), 4),
            "evidence_quote": frame.evidence_quote,
            "source_raw_id": frame.source_raw_id,
            "source_url": frame.source_url,
        }
        for frame in frames
    )


def _frames_from_raw(raw: RawDiscoveredEvent, *, event: NormalizedEvent | None) -> list[EventCatalystFrame]:
    title = str(raw.title or "")
    body = str(raw.body or "")
    frames: list[EventCatalystFrame] = []
    frames.extend(_validated_llm_frames_from_raw(raw))
    if title:
        frames.extend(_frames_from_text(title, title=title, raw=raw, event=event))
    for segment in (body, _enriched_text(raw)):
        if segment:
            frames.extend(_frames_from_text(segment, title=title, raw=raw, event=event))
    return frames


def _validated_llm_frames_from_raw(raw: RawDiscoveredEvent) -> list[EventCatalystFrame]:
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    validation = payload.get("llm_catalyst_frame_validation") if isinstance(payload.get("llm_catalyst_frame_validation"), dict) else {}
    raw_frames = validation.get("valid_frames") if isinstance(validation.get("valid_frames"), list) else []
    frames: list[EventCatalystFrame] = []
    for item in raw_frames:
        if not isinstance(item, dict):
            continue
        frame_type = str(item.get("frame_type") or "")
        frame_role = str(item.get("frame_role") or "")
        if not frame_type or not frame_role:
            continue
        quote = re.sub(r"\s+", " ", str(item.get("evidence_quote") or "")).strip()[:320]
        subject = _clean_subject(str(item.get("subject") or "")) if item.get("subject") else None
        frame_id = str(item.get("frame_id") or _frame_id(raw.raw_id, frame_type, frame_role, subject, quote))
        frames.append(EventCatalystFrame(
            frame_id=frame_id,
            frame_type=frame_type,
            frame_role=frame_role,
            subject=subject,
            actor=_clean_subject(str(item.get("actor") or "")) if item.get("actor") else None,
            object=str(item.get("object") or "") or None,
            affected_entities=tuple(str(value) for value in item.get("affected_entities") or () if str(value).strip()),
            affected_assets=tuple(str(value) for value in item.get("affected_assets") or () if str(value).strip()),
            event_archetype=str(item.get("event_archetype") or frame_type),
            claim_polarity=str(item.get("claim_polarity") or event_claim_semantics.ClaimPolarity.UNKNOWN.value),
            cause_status=str(item.get("cause_status") or event_claim_semantics.CauseStatus.UNKNOWN.value),
            confidence=max(0.0, min(1.0, float(item.get("confidence") or 0.0))),
            evidence_quote=quote,
            source_raw_id=raw.raw_id,
            source_url=raw.source_url,
            published_at=raw.published_at,
        ))
    return frames


def _frames_from_text(
    text: str,
    *,
    title: str,
    raw: RawDiscoveredEvent | None,
    event: NormalizedEvent | None,
) -> list[EventCatalystFrame]:
    frames: list[EventCatalystFrame] = []
    title_clean = clean_text(title)
    title_sentences = set(_sentence_keys(title))
    for sentence in _sentences(text):
        cleaned = clean_text(sentence)
        if not cleaned:
            continue
        in_title = _sentence_key(sentence) in title_sentences or clean_text(sentence) in title_clean
        frames.extend(_strategic_frames(sentence, cleaned, raw=raw, event=event, in_title=in_title))
        frames.extend(_listing_frames(sentence, cleaned, raw=raw, event=event, in_title=in_title))
        frames.extend(_unlock_frames(sentence, cleaned, raw=raw, event=event, in_title=in_title))
        frames.extend(_security_frames(sentence, cleaned, raw=raw, event=event, in_title=in_title))
        frames.extend(_proxy_policy_market_frames(sentence, cleaned, raw=raw, event=event, in_title=in_title))
    return frames


def _strategic_frames(
    sentence: str,
    cleaned: str,
    *,
    raw: RawDiscoveredEvent | None,
    event: NormalizedEvent | None,
    in_title: bool,
) -> list[EventCatalystFrame]:
    if not _any(cleaned, ("stake", "strategic investment", "investment", "valuation", "acquisition", "acquire", "buy")):
        return []
    if not _any(cleaned, ("stake", "valuation", "investment", "acquisition", "acquire", "buy")):
        return []
    actor, subject = _stake_actor_subject(sentence)
    subject = subject or _event_external_subject(event) or _last_named_entity(sentence)
    actor = actor or _first_named_entity(sentence)
    frame_type = TYPE_ACQUISITION_OR_STAKE if _any(cleaned, ("stake", "buy", "acquire", "acquisition")) else TYPE_STRATEGIC_INVESTMENT
    if "valuation" in cleaned and frame_type != TYPE_ACQUISITION_OR_STAKE:
        frame_type = TYPE_VALUATION_EVENT
    return [
        _frame(
            frame_type=frame_type,
            frame_role=ROLE_MAIN,
            subject=subject,
            actor=actor if actor != subject else None,
            object="strategic stake" if "stake" in cleaned else ("valuation" if "valuation" in cleaned else "investment"),
            event_archetype=TYPE_STRATEGIC_INVESTMENT,
            claim_polarity=event_claim_semantics.ClaimPolarity.ASSERTED.value,
            cause_status=event_claim_semantics.CauseStatus.CONFIRMED.value if in_title else event_claim_semantics.CauseStatus.UNKNOWN.value,
            confidence=0.92 if in_title else 0.78,
            evidence_quote=sentence,
            raw=raw,
        )
    ]


def _listing_frames(sentence: str, cleaned: str, *, raw: RawDiscoveredEvent | None, event: NormalizedEvent | None, in_title: bool) -> list[EventCatalystFrame]:
    if not _any(cleaned, ("listed on", "listing", "nasdaq", "public listing", "merger")):
        return []
    subject = _event_external_subject(event) or _first_named_entity(sentence)
    return [_frame(
        frame_type=TYPE_LISTING_LIQUIDITY,
        frame_role=ROLE_MAIN if in_title else ROLE_BACKGROUND,
        subject=subject,
        event_archetype=TYPE_LISTING_LIQUIDITY,
        claim_polarity=event_claim_semantics.ClaimPolarity.ASSERTED.value,
        cause_status=event_claim_semantics.CauseStatus.CONFIRMED.value,
        confidence=0.88 if in_title else 0.70,
        evidence_quote=sentence,
        raw=raw,
    )]


def _unlock_frames(sentence: str, cleaned: str, *, raw: RawDiscoveredEvent | None, event: NormalizedEvent | None, in_title: bool) -> list[EventCatalystFrame]:
    if not _any(cleaned, ("unlock", "vesting", "airdrop", "tge", "emission")):
        return []
    subject = _event_external_subject(event) or _first_named_entity(sentence)
    return [_frame(
        frame_type=TYPE_UNLOCK_SUPPLY,
        frame_role=ROLE_MAIN if in_title else ROLE_BACKGROUND,
        subject=subject,
        event_archetype=TYPE_UNLOCK_SUPPLY,
        claim_polarity=event_claim_semantics.ClaimPolarity.ASSERTED.value,
        cause_status=event_claim_semantics.CauseStatus.CONFIRMED.value,
        confidence=0.86 if in_title else 0.68,
        evidence_quote=sentence,
        raw=raw,
    )]


def _security_frames(sentence: str, cleaned: str, *, raw: RawDiscoveredEvent | None, event: NormalizedEvent | None, in_title: bool) -> list[EventCatalystFrame]:
    if not _any(cleaned, ("exploit", "hack", "hacked", "breach", "attack", "security incident")):
        return []
    frames: list[EventCatalystFrame] = []
    if _any(cleaned, _NEGATED_SECURITY_PHRASES):
        subject = _negated_security_subject(sentence) or _event_external_subject(event) or _first_named_entity(sentence)
        frames.append(_frame(
            frame_type=TYPE_DENIED_EXPLOIT,
            frame_role=ROLE_NEGATED,
            subject=subject,
            event_archetype=TYPE_MARKET_DISLOCATION,
            claim_polarity=event_claim_semantics.ClaimPolarity.NEGATED.value,
            cause_status=event_claim_semantics.CauseStatus.RULED_OUT.value,
            confidence=0.90,
            evidence_quote=sentence,
            raw=raw,
        ))
    background = _is_background_sentence(cleaned)
    event_subject = _event_external_subject(event)
    subject = (
        event_subject
        if event_subject and clean_text(event_subject) in cleaned and not background
        else _exploit_subject(sentence) or event_subject or _first_named_entity(sentence)
    )
    if subject and not (frames and clean_text(subject) == clean_text(frames[0].subject or "")):
        polarity, cause_status, confidence = _security_claim_state(cleaned, in_title=in_title, background=background)
        frames.append(_frame(
            frame_type=TYPE_PRIOR_EXPLOIT_CONTEXT if background else TYPE_EXPLOIT_SECURITY,
            frame_role=ROLE_BACKGROUND if background else ROLE_MAIN,
            subject=subject,
            event_archetype=TYPE_EXPLOIT_SECURITY,
            claim_polarity=polarity,
            cause_status=cause_status,
            confidence=confidence,
            evidence_quote=sentence,
            raw=raw,
        ))
    return frames


def _proxy_policy_market_frames(sentence: str, cleaned: str, *, raw: RawDiscoveredEvent | None, event: NormalizedEvent | None, in_title: bool) -> list[EventCatalystFrame]:
    negated_mention = (
        "does not mention" in cleaned
        or "not mention" in cleaned
        or "no crypto asset" in cleaned
        or "no token" in cleaned
        or "no market anomaly" in cleaned
        or "market anomaly is mentioned" in cleaned
    )
    if negated_mention:
        return []
    if not negated_mention and _any(cleaned, ("no clear trigger", "no known catalyst", "without a known cause", "market anomaly", "no exploit or announcement")):
        return [_frame(
            frame_type=TYPE_MARKET_DISLOCATION,
            frame_role=ROLE_MARKET_REACTION if in_title else ROLE_BACKGROUND,
            subject=_market_payload_subject(raw) or _event_external_subject(event) or _first_named_entity(sentence),
            event_archetype=TYPE_MARKET_DISLOCATION,
            claim_polarity=event_claim_semantics.ClaimPolarity.UNKNOWN.value,
            cause_status=event_claim_semantics.CauseStatus.UNKNOWN.value,
            confidence=0.64,
            evidence_quote=sentence,
            raw=raw,
        )]
    if _any(cleaned, ("pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure")) or (
        "prediction market" in cleaned
        and _any(cleaned, ("token", "coin", "meme", "fan token", "exposure", "venue", "value-capture", "value capture"))
    ):
        return [_frame(
            frame_type=TYPE_PROXY_ATTENTION,
            frame_role=ROLE_MAIN if in_title else ROLE_BACKGROUND,
            subject=_event_external_subject(event) or _first_named_entity(sentence),
            event_archetype=TYPE_PROXY_ATTENTION,
            claim_polarity=event_claim_semantics.ClaimPolarity.ASSERTED.value,
            cause_status=event_claim_semantics.CauseStatus.UNKNOWN.value,
            confidence=0.78 if in_title else 0.60,
            evidence_quote=sentence,
            raw=raw,
        )]
    if _any(cleaned, ("policy", "regulatory", "regulation", "cftc", "sec")):
        return [_frame(
            frame_type=TYPE_POLICY_CONTEXT,
            frame_role=ROLE_MAIN if in_title else ROLE_BACKGROUND,
            subject=_event_external_subject(event) or _first_named_entity(sentence),
            event_archetype=TYPE_POLICY_CONTEXT,
            claim_polarity=event_claim_semantics.ClaimPolarity.ASSERTED.value,
            cause_status=event_claim_semantics.CauseStatus.UNKNOWN.value,
            confidence=0.66 if in_title else 0.50,
            evidence_quote=sentence,
            raw=raw,
        )]
    return []


def _security_claim_state(cleaned: str, *, in_title: bool, background: bool) -> tuple[str, str, float]:
    if any(term in cleaned for term in ("rumor", "rumored", "rumoured", "unconfirmed")):
        return (
            event_claim_semantics.ClaimPolarity.RUMORED.value,
            event_claim_semantics.CauseStatus.SUSPECTED.value,
            0.58,
        )
    if any(term in cleaned for term in ("alleged", "allegedly", "suspected", "reportedly")):
        return (
            event_claim_semantics.ClaimPolarity.ALLEGED.value,
            event_claim_semantics.CauseStatus.SUSPECTED.value,
            0.64,
        )
    return (
        event_claim_semantics.ClaimPolarity.ASSERTED.value,
        event_claim_semantics.CauseStatus.CONFIRMED.value,
        0.62 if background else (0.90 if in_title else 0.78),
    )


def _frame(
    *,
    frame_type: str,
    frame_role: str,
    subject: str | None,
    evidence_quote: str,
    raw: RawDiscoveredEvent | None,
    actor: str | None = None,
    object: str | None = None,
    affected_entities: tuple[str, ...] = (),
    affected_assets: tuple[str, ...] = (),
    event_archetype: str | None = None,
    claim_polarity: str = event_claim_semantics.ClaimPolarity.UNKNOWN.value,
    cause_status: str = event_claim_semantics.CauseStatus.UNKNOWN.value,
    confidence: float = 0.0,
) -> EventCatalystFrame:
    quote = re.sub(r"\s+", " ", str(evidence_quote or "")).strip()[:320]
    normalized_subject = _clean_subject(subject)
    normalized_actor = _clean_subject(actor)
    frame_id = _frame_id(raw.raw_id if raw else None, frame_type, frame_role, normalized_subject, quote)
    return EventCatalystFrame(
        frame_id=frame_id,
        frame_type=frame_type,
        frame_role=frame_role,
        subject=normalized_subject,
        actor=normalized_actor,
        object=object,
        affected_entities=tuple(item for item in (normalized_subject, *affected_entities) if item),
        affected_assets=affected_assets,
        event_archetype=event_archetype or frame_type,
        claim_polarity=claim_polarity,
        cause_status=cause_status,
        confidence=max(0.0, min(1.0, float(confidence or 0.0))),
        evidence_quote=quote,
        source_raw_id=raw.raw_id if raw else None,
        source_url=raw.source_url if raw else None,
        published_at=raw.published_at if raw else None,
    )


def _frame_priority(frame: EventCatalystFrame, source_context: object | None) -> tuple[float, float, str]:
    role_score = {
        ROLE_MAIN: 100.0,
        ROLE_MARKET_REACTION: 70.0,
        ROLE_BACKGROUND: 30.0,
        ROLE_HISTORICAL: 25.0,
        ROLE_CORRECTIVE: 15.0,
        ROLE_NEGATED: 10.0,
        ROLE_SIDE_NOTE: 5.0,
        ROLE_UNKNOWN: 0.0,
    }.get(frame.frame_role, 0.0)
    type_score = {
        TYPE_ACQUISITION_OR_STAKE: 30.0,
        TYPE_STRATEGIC_INVESTMENT: 28.0,
        TYPE_VALUATION_EVENT: 26.0,
        TYPE_LISTING_LIQUIDITY: 24.0,
        TYPE_UNLOCK_SUPPLY: 23.0,
        TYPE_EXPLOIT_SECURITY: 22.0,
        TYPE_PROXY_ATTENTION: 20.0,
        TYPE_MARKET_DISLOCATION: 10.0,
        TYPE_PRIOR_EXPLOIT_CONTEXT: -10.0,
        TYPE_DENIED_EXPLOIT: -20.0,
    }.get(frame.frame_type, 0.0)
    if frame.frame_role == ROLE_NEGATED:
        type_score = min(type_score, -25.0)
    return (role_score + type_score + frame.confidence * 10.0, frame.confidence, frame.frame_id)


def _dedupe_frames(frames: list[EventCatalystFrame]) -> list[EventCatalystFrame]:
    by_key: dict[tuple[str, str, str, str], EventCatalystFrame] = {}
    for frame in frames:
        key = (frame.frame_type, frame.frame_role, clean_text(frame.subject or ""), clean_text(frame.evidence_quote))
        existing = by_key.get(key)
        if existing is None or frame.confidence > existing.confidence:
            by_key[key] = frame
    return list(by_key.values())


def _sentences(text: str) -> list[str]:
    source = re.sub(r"\s+", " ", str(text or "")).strip()
    if not source:
        return []
    return [part.strip(" -") for part in re.split(r"(?<=[.!?])\s+|[|]\s*", source) if part.strip(" -")]


def _sentence_keys(text: str) -> tuple[str, ...]:
    return tuple(_sentence_key(sentence) for sentence in _sentences(text))


def _sentence_key(sentence: str) -> str:
    return clean_text(sentence)[:160]


def _is_background_sentence(cleaned: str) -> bool:
    return any(marker in cleaned for marker in _BACKGROUND_MARKERS)


def _any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _stake_actor_subject(sentence: str) -> tuple[str | None, str | None]:
    patterns = (
        r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b.{0,80}?\b(?:buy|acquire|take|purchase)\b.{0,80}?\bstake\b.{0,80}?\b(?:in|of)\b(?:\s+\w+){0,5}?\s+\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b",
        r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b.{0,80}?\bstake\b.{0,80}?\b(?:in|of)\b(?:\s+\w+){0,5}?\s+\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, sentence)
        if match:
            return _clean_subject(match.group(1)), _clean_subject(match.group(2))
    return None, None


def _exploit_subject(sentence: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\s+(?:exploit|hack|breach|attack)\b", sentence)
    if match:
        return _clean_subject(match.group(1))
    claim_subject = event_claim_semantics.infer_primary_subject(sentence)
    return _clean_subject(claim_subject)


def _negated_security_subject(sentence: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b.{0,30}?\bnot\s+(?:being\s+)?hacked\b", sentence)
    if match:
        return _clean_subject(match.group(1))
    match = re.search(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b.{0,50}?\b(?:no exploit|no hack)\b", sentence)
    if match:
        return _clean_subject(match.group(1))
    return None


def _first_named_entity(text: str) -> str | None:
    names = re.findall(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b", str(text or ""))
    for name in names:
        cleaned = _clean_subject(name)
        if cleaned:
            return cleaned
    return None


def _last_named_entity(text: str) -> str | None:
    names = re.findall(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b", str(text or ""))
    for name in reversed(names):
        cleaned = _clean_subject(name)
        if cleaned:
            return cleaned
    return None


def _event_external_subject(event: NormalizedEvent | None) -> str | None:
    if event is None:
        return None
    return _clean_subject(event.external_asset) or _clean_subject(event.event_name)


def _market_payload_subject(raw: RawDiscoveredEvent | None) -> str | None:
    if raw is None:
        return None
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    if (
        raw.provider != "market_anomaly"
        and not isinstance(payload.get("anomaly"), dict)
        and clean_text(event_payload.get("event_type") or payload.get("event_type") or "") != "market_anomaly"
    ):
        return None
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
    for key in ("symbol", "name", "coin_id", "id"):
        value = market.get(key)
        subject = _clean_subject(str(value) if value is not None else None)
        if subject:
            return subject
    return None


def _clean_subject(value: str | None) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip(" -:.,;|"))
    if not text:
        return None
    text = re.sub(r"^(the|a|an)\s+", "", text, flags=re.I).strip()
    cleaned = clean_text(text)
    if cleaned in {"the", "a", "an", "no", "none", "unknown", "defi", "lender", "token", "coin", "market", "valuation", "stake", "april"}:
        return None
    if cleaned == "aave":
        return "Aave"
    if cleaned == "kelpdao":
        return "KelpDAO"
    return text or None


def _enriched_text(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), dict) else {}
    return str(enrichment.get("enriched_text") or "")


def _frame_id(raw_id: str | None, frame_type: str, frame_role: str, subject: str | None, quote: str) -> str:
    basis = "|".join((str(raw_id or ""), frame_type, frame_role, clean_text(subject or ""), clean_text(quote)[:160]))
    return "frame:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:14]
