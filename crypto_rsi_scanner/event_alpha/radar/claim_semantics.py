"""Claim semantics for Event Alpha causal evidence.

This module is deliberately deterministic and side-effect free. It annotates
high-impact source statements with polarity/cause status so keyword scanners do
not turn "no exploit" into a confirmed exploit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from ...event_models import RawDiscoveredEvent
from ...event_resolver import clean_text


CLAIM_SEMANTICS_SCHEMA_VERSION = "event_claim_semantics_v1"


class ClaimPolarity(str, Enum):
    ASSERTED = "asserted"
    NEGATED = "negated"
    UNCERTAIN = "uncertain"
    ALLEGED = "alleged"
    RUMORED = "rumored"
    DISPUTED = "disputed"
    DENIED = "denied"
    RULED_OUT = "ruled_out"
    UNKNOWN = "unknown"


class CauseStatus(str, Enum):
    CONFIRMED = "confirmed"
    SUSPECTED = "suspected"
    UNKNOWN = "unknown"
    RULED_OUT = "ruled_out"


@dataclass(frozen=True)
class EventClaim:
    claim_type: str
    subject: str | None
    predicate: str
    object: str | None
    polarity: str
    cause_status: str
    confidence: float
    evidence_quote: str
    source_raw_id: str | None = None
    source_url: str | None = None
    published_at: object | None = None


_SECURITY_TERMS = ("exploit", "hack", "hacked", "breach", "attack", "security incident")
_ANNOUNCEMENT_TERMS = ("announcement", "clear trigger", "catalyst")
_LOSS_RE = re.compile(r"\b(?:loses|lost|drained|stolen|stole|exploit(?:ed)?|hack(?:ed)?)\b.{0,80}?(?:\$?\d+(?:\.\d+)?\s?(?:m|million|bn|billion)|funds|wallet)", re.I)
_UNKNOWN_CAUSE_PHRASES = (
    "no dated external catalyst has been validated",
    "no catalyst confirmed",
    "no clear trigger",
    "no known catalyst",
    "no explanation yet",
    "without a known cause",
    "without clear trigger",
    "cause unknown",
    "unknown cause",
    "no catalyst",
    "no announcement",
    "no exploit or announcement",
    "no independent catalyst source",
    "no independent catalyst",
)
_ABSENCE_OF_VALIDATED_CATALYST_PHRASES = (
    "no dated external catalyst has been validated",
    "no catalyst confirmed",
    "no clear trigger",
    "no known catalyst",
    "no explanation yet",
    "without a known cause",
    "no exploit or announcement to explain",
    "no exploit or announcement explains",
    "no independent catalyst source",
    "no independent catalyst",
)
_GENERIC_SUBJECTS = {
    "about",
    "actions",
    "all",
    "announcements",
    "any",
    "any us",
    "best prediction market apps",
    "bitcoin and mstr are",
    "during",
    "here",
    "llm",
    "need",
    "no",
    "non",
    "not",
    "note",
    "none",
    "unknown",
    "unclear",
    "n/a",
    "na",
    "however",
    "it",
    "only",
    "openai this",
    "seo",
    "polymarket invite code sbwire",
    "polymarket referral code sbwire",
    "the",
    "this",
    "that",
    "when",
    "where",
    "will",
    "yes",
    "market",
    "catalyst",
    "event",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "token",
    "coin",
}
_SUBJECT_REPLACEMENTS = {
    "openai this": "OpenAI",
    "polymarket world cup volume": "World Cup",
}
_TRAILING_GENERIC_TOKENS = {
    "this",
    "that",
    "event",
    "catalyst",
    "market",
    "token",
    "coin",
    "announcement",
    "announcements",
    "volume",
}


def extract_event_claims(raw_events: Iterable[RawDiscoveredEvent]) -> tuple[EventClaim, ...]:
    """Extract deterministic claim rows from source title/body evidence."""
    out: list[EventClaim] = []
    for raw in raw_events:
        text = _raw_text(raw)
        if not text:
            continue
        out.extend(_claims_from_text(text, raw=raw))
    return tuple(out)


def claims_from_text(text: str) -> tuple[EventClaim, ...]:
    """Convenience wrapper for tests and pure classifiers."""
    return tuple(_claims_from_text(text, raw=None))


def current_cause_status(claims: Iterable[EventClaim], claim_type: str | None = None) -> str:
    """Return the latest/highest-priority cause status for the claim stream."""
    filtered = [claim for claim in claims if claim_type is None or claim.claim_type == claim_type]
    if not filtered:
        return CauseStatus.UNKNOWN.value
    latest = filtered[-1]
    if latest.cause_status == CauseStatus.RULED_OUT.value:
        return CauseStatus.RULED_OUT.value
    if latest.cause_status == CauseStatus.CONFIRMED.value:
        return CauseStatus.CONFIRMED.value
    if any(claim.cause_status == CauseStatus.CONFIRMED.value for claim in filtered):
        return CauseStatus.CONFIRMED.value
    if any(claim.cause_status == CauseStatus.SUSPECTED.value for claim in filtered):
        return CauseStatus.SUSPECTED.value
    return latest.cause_status or CauseStatus.UNKNOWN.value


def has_confirmed_claim(claims: Iterable[EventClaim], claim_type: str) -> bool:
    return any(
        claim.claim_type == claim_type
        and claim.polarity == ClaimPolarity.ASSERTED.value
        and claim.cause_status == CauseStatus.CONFIRMED.value
        for claim in claims
    )


def has_ruled_out_claim(claims: Iterable[EventClaim], claim_type: str) -> bool:
    return any(
        claim.claim_type == claim_type
        and claim.polarity in {
            ClaimPolarity.NEGATED.value,
            ClaimPolarity.DENIED.value,
            ClaimPolarity.RULED_OUT.value,
        }
        for claim in claims
    )


def text_has_unknown_cause(text: str) -> bool:
    cleaned = clean_text(text)
    return any(phrase in cleaned for phrase in _UNKNOWN_CAUSE_PHRASES)


def _claims_from_text(text: str, *, raw: RawDiscoveredEvent | None) -> list[EventClaim]:
    claims: list[EventClaim] = []
    sentences = _sentences(text)
    for sentence in sentences:
        cleaned = clean_text(sentence)
        if not cleaned:
            continue
        subject = infer_primary_subject(sentence)
        if any(term in cleaned for term in _SECURITY_TERMS):
            if "suspected" in cleaned and "ruled out" in cleaned:
                claims.append(EventClaim(
                    claim_type="exploit",
                    subject=subject,
                    predicate="security_incident",
                    object=None,
                    polarity=ClaimPolarity.ALLEGED.value,
                    cause_status=CauseStatus.SUSPECTED.value,
                    confidence=_claim_confidence(ClaimPolarity.ALLEGED.value),
                    evidence_quote=sentence.strip()[:280],
                    source_raw_id=raw.raw_id if raw else None,
                    source_url=raw.source_url if raw else None,
                    published_at=raw.published_at if raw else None,
                ))
                claims.append(EventClaim(
                    claim_type="exploit",
                    subject=subject,
                    predicate="security_incident",
                    object=None,
                    polarity=ClaimPolarity.RULED_OUT.value,
                    cause_status=CauseStatus.RULED_OUT.value,
                    confidence=_claim_confidence(ClaimPolarity.RULED_OUT.value),
                    evidence_quote=sentence.strip()[:280],
                    source_raw_id=raw.raw_id if raw else None,
                    source_url=raw.source_url if raw else None,
                    published_at=raw.published_at if raw else None,
                ))
                continue
            polarity, cause = _security_polarity(cleaned)
            claims.append(EventClaim(
                claim_type="exploit",
                subject=subject,
                predicate="security_incident",
                object=None,
                polarity=polarity,
                cause_status=cause,
                confidence=_claim_confidence(polarity),
                evidence_quote=sentence.strip()[:280],
                source_raw_id=raw.raw_id if raw else None,
                source_url=raw.source_url if raw else None,
                published_at=raw.published_at if raw else None,
            ))
        if _has_absence_of_validated_catalyst(cleaned):
            claims.append(EventClaim(
                claim_type="absence_of_validated_catalyst",
                subject=subject,
                predicate="has_no_validated_catalyst",
                object=None,
                polarity=ClaimPolarity.UNKNOWN.value,
                cause_status=CauseStatus.UNKNOWN.value,
                confidence=_claim_confidence(ClaimPolarity.UNKNOWN.value),
                evidence_quote=sentence.strip()[:280],
                source_raw_id=raw.raw_id if raw else None,
                source_url=raw.source_url if raw else None,
                published_at=raw.published_at if raw else None,
            ))
            continue
        if any(term in cleaned for term in _ANNOUNCEMENT_TERMS) or text_has_unknown_cause(cleaned):
            polarity, cause = _cause_polarity(cleaned)
            claims.append(EventClaim(
                claim_type="catalyst_cause",
                subject=subject,
                predicate="explains_market_move",
                object=None,
                polarity=polarity,
                cause_status=cause,
                confidence=_claim_confidence(polarity),
                evidence_quote=sentence.strip()[:280],
                source_raw_id=raw.raw_id if raw else None,
                source_url=raw.source_url if raw else None,
                published_at=raw.published_at if raw else None,
            ))
    return claims


def infer_primary_subject(text: str) -> str | None:
    """Infer the named subject most likely being acted on in the sentence."""
    source = str(text or "").strip()
    if not source:
        return None
    # Prefer possessive/project names before high-impact terms.
    possessive = re.search(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})'s\b.{0,60}\b(?:token|wallet|protocol|bridge|market|venue)\b", source)
    if possessive:
        return _clean_subject(possessive.group(1))
    direct = re.search(
        r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b.{0,80}\b(?:was|is|gets|faces|suffers|lost|loses|resumes|halted|exploit|hack|breach)",
        source,
    )
    if direct:
        candidate = _clean_subject(direct.group(1))
        if candidate:
            return candidate
    loss = _LOSS_RE.search(source)
    if loss:
        before = source[: loss.start()]
        names = re.findall(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b", before)
        if names:
            return _clean_subject(names[-1])
    names = re.findall(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b", source)
    for name in names:
        candidate = _clean_subject(name)
        if candidate:
            return candidate
    return None


def infer_affected_ecosystem(text: str) -> str | None:
    source = str(text or "")
    patterns = (
        r"\b(?:in|on|across|within)\s+the\s+([A-Z][A-Za-z0-9]+)\s+ecosystem\b",
        r"\b(?:in|on|across|within)\s+([A-Z][A-Za-z0-9]+)\s+ecosystem\b",
        r"\b([A-Z][A-Za-z0-9]+)\s+wallet\b",
    )
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return _clean_subject(match.group(1))
    return None


def _security_polarity(cleaned: str) -> tuple[str, str]:
    if any(phrase in cleaned for phrase in (
        "no exploit",
        "no evidence of exploit",
        "without an exploit",
        "not being hacked",
        "not hacked",
        "not hack",
        "exploit ruled out",
        "hack ruled out",
        "ruled out exploit",
        "ruled out a hack",
    )):
        return ClaimPolarity.NEGATED.value, CauseStatus.RULED_OUT.value
    if any(phrase in cleaned for phrase in ("denies exploit", "denied exploit", "team denies", "denies hack", "denied hack")):
        return ClaimPolarity.DENIED.value, CauseStatus.RULED_OUT.value
    if any(phrase in cleaned for phrase in ("disputed", "contested")):
        return ClaimPolarity.DISPUTED.value, CauseStatus.SUSPECTED.value
    if any(phrase in cleaned for phrase in ("rumor", "rumoured", "rumored", "unconfirmed")):
        return ClaimPolarity.RUMORED.value, CauseStatus.SUSPECTED.value
    if any(phrase in cleaned for phrase in ("allegedly", "alleged", "reportedly", "suspected", "initially suspected")):
        return ClaimPolarity.ALLEGED.value, CauseStatus.SUSPECTED.value
    if any(term in cleaned for term in ("exploit", "hack", "hacked", "breach", "attack", "security incident")):
        return ClaimPolarity.ASSERTED.value, CauseStatus.CONFIRMED.value
    return ClaimPolarity.UNKNOWN.value, CauseStatus.UNKNOWN.value


def _cause_polarity(cleaned: str) -> tuple[str, str]:
    if text_has_unknown_cause(cleaned):
        return ClaimPolarity.UNKNOWN.value, CauseStatus.UNKNOWN.value
    if any(phrase in cleaned for phrase in ("no announcement", "without announcement", "no catalyst")):
        return ClaimPolarity.NEGATED.value, CauseStatus.UNKNOWN.value
    return ClaimPolarity.ASSERTED.value, CauseStatus.CONFIRMED.value


def _has_absence_of_validated_catalyst(cleaned: str) -> bool:
    return any(phrase in cleaned for phrase in _ABSENCE_OF_VALIDATED_CATALYST_PHRASES)


def _claim_confidence(polarity: str) -> float:
    return {
        ClaimPolarity.ASSERTED.value: 0.86,
        ClaimPolarity.NEGATED.value: 0.88,
        ClaimPolarity.RULED_OUT.value: 0.90,
        ClaimPolarity.DENIED.value: 0.82,
        ClaimPolarity.ALLEGED.value: 0.64,
        ClaimPolarity.RUMORED.value: 0.58,
        ClaimPolarity.UNCERTAIN.value: 0.50,
        ClaimPolarity.UNKNOWN.value: 0.45,
    }.get(str(polarity or ""), 0.50)


def _raw_text(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), dict) else {}
    return " ".join(
        str(part or "")
        for part in (
            raw.title,
            raw.body,
            enrichment.get("enriched_text"),
        )
    )


def _sentences(text: str) -> list[str]:
    source = re.sub(r"\s+", " ", str(text or "")).strip()
    if not source:
        return []
    parts = re.split(r"(?<=[.!?])\s+|[|]\s*", source)
    return [part.strip() for part in parts if part.strip()]


def _clean_subject(value: str | None) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip(" -:.,;|"))
    if not text:
        return None
    text = re.sub(r"^(The|A|An)\s+", "", text).strip()
    initial_cleaned = clean_text(text)
    if initial_cleaned in _SUBJECT_REPLACEMENTS:
        return _SUBJECT_REPLACEMENTS[initial_cleaned]
    if _is_noise_subject(initial_cleaned):
        return None
    parts = text.split()
    while parts and clean_text(parts[-1]) in _TRAILING_GENERIC_TOKENS:
        parts.pop()
    text = " ".join(parts).strip(" -:.,;|")
    lowered = clean_text(text)
    if lowered in _SUBJECT_REPLACEMENTS:
        return _SUBJECT_REPLACEMENTS[lowered]
    stop = {
        "the",
        "a",
        "an",
        "about",
        "actions",
        "all",
        "announcements",
        "any",
        "during",
        "here",
        "however",
        "it",
        "llm",
        "meme",
        "need",
        "not",
        "non",
        "note",
        "only",
        "this",
        "that",
        "token",
        "protocol",
        "team",
        "report",
        "source",
        "seo",
        "bitcoin world",
        "crypto",
    }
    if lowered in stop or lowered in _GENERIC_SUBJECTS or _is_noise_subject(lowered):
        return None
    if clean_text(text) in _GENERIC_SUBJECTS:
        return None
    return text or None


def _is_noise_subject(cleaned: str) -> bool:
    if not cleaned:
        return True
    if cleaned in _GENERIC_SUBJECTS:
        return True
    if "invite code" in cleaned or "referral code" in cleaned:
        return True
    if cleaned.startswith("best ") and cleaned.endswith(" apps"):
        return True
    if cleaned.endswith(" are") and " and " in cleaned:
        return True
    return False
