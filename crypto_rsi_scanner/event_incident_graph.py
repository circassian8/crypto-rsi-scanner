"""Canonical incident graph for Event Alpha research.

This graph merges differently worded source rows that describe the same
incident. It is metadata only and cannot create candidates, alerts, trades, or
event-fade triggers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from . import event_claim_semantics
from .event_models import NormalizedEvent, RawDiscoveredEvent
from .event_resolver import clean_text


INCIDENT_GRAPH_SCHEMA_VERSION = "event_incident_graph_v1"
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
_GENERIC_SUBJECT_TOKENS = {
    "a",
    "about",
    "actions",
    "all",
    "an",
    "announcements",
    "any",
    "apps",
    "are",
    "best",
    "coin",
    "during",
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
    "here",
    "however",
    "it",
    "llm",
    "market",
    "need",
    "no",
    "non",
    "not",
    "note",
    "only",
    "seo",
    "that",
    "the",
    "this",
    "token",
    "when",
    "where",
    "will",
    "yes",
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


@dataclass(frozen=True)
class IncidentAssetRole:
    symbol: str | None
    coin_id: str | None
    role: str
    confidence: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class IncidentSubjectValidation:
    status: str
    normalized_subject: str | None
    fallback_source: str | None = None
    rejection_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalIncident:
    schema_version: str
    incident_id: str
    canonical_name: str
    event_archetype: str
    primary_subject: str | None
    affected_ecosystem: str | None
    first_seen_at: datetime
    last_updated_at: datetime
    raw_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    source_urls: tuple[str, ...]
    independent_source_domains: tuple[str, ...]
    claim_history: tuple[event_claim_semantics.EventClaim, ...] = ()
    current_cause_status: str = event_claim_semantics.CauseStatus.UNKNOWN.value
    conflicting_claims: tuple[str, ...] = ()
    linked_assets: tuple[IncidentAssetRole, ...] = ()
    subject_quality: str = "valid"
    subject_quality_reason: str | None = None
    diagnostic_only: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


def validate_incident_primary_subject(
    subject: str | None,
    context: object | None = None,
) -> IncidentSubjectValidation:
    """Validate or replace an incident primary subject before persistence."""
    normalized = _normalized_subject(subject)
    if normalized:
        return IncidentSubjectValidation(status="valid", normalized_subject=normalized)
    fallback, source = _subject_fallback_from_context(context)
    if fallback:
        return IncidentSubjectValidation(
            status="fallback_used",
            normalized_subject=fallback,
            fallback_source=source,
            rejection_reason="invalid_primary_subject_replaced",
            warnings=("incident_primary_subject_fallback_used",),
        )
    cleaned = clean_text(subject or "")
    status = "diagnostic_only" if _is_noise_subject(cleaned) else "invalid_subject"
    return IncidentSubjectValidation(
        status=status,
        normalized_subject=None,
        rejection_reason="garbage_or_missing_primary_subject",
        warnings=("incident_primary_subject_invalid",),
    )


def build_incidents(
    events: Iterable[NormalizedEvent],
    raw_by_id: dict[str, RawDiscoveredEvent],
) -> tuple[CanonicalIncident, ...]:
    grouped: dict[str, list[tuple[NormalizedEvent, tuple[RawDiscoveredEvent, ...]]]] = {}
    for event in events:
        raws = tuple(raw_by_id[raw_id] for raw_id in event.raw_ids if raw_id in raw_by_id)
        key = incident_key(event, raws)
        grouped.setdefault(key, []).append((event, raws))
    return tuple(_incident_from_group(key, rows) for key, rows in sorted(grouped.items()))


def incident_key(event: NormalizedEvent, raws: Iterable[RawDiscoveredEvent]) -> str:
    raws = tuple(raws)
    text = _combined_text(event, raws)
    claims = event_claim_semantics.extract_event_claims(raws)
    archetype = event_archetype(event, raws, claims=claims)
    bucket = _date_bucket(event, raws)
    if _is_market_anomaly_event(event, raws) or archetype == "market_dislocation_unknown":
        asset = _market_anomaly_asset(event, raws)
        identity = asset.get("coin_id") or asset.get("symbol") or asset.get("name") or "unknown"
        anomaly_type = asset.get("anomaly_type") or archetype or "market_anomaly"
        return "|".join((
            "market-anomaly",
            _slug(str(identity)),
            _slug(str(asset.get("symbol") or "")),
            _slug(str(anomaly_type)),
            bucket,
        ))
    subject = infer_primary_subject(event, raws, claims=claims)
    ecosystem = infer_affected_ecosystem(event, raws)
    named = _major_named_entities(text)
    identity = (
        _normalized_subject(subject)
        or (named[0] if named else None)
        or (event.external_asset if _valid_subject(event.external_asset) else None)
        or (event.event_name if _valid_subject(event.event_name) else None)
    )
    key_parts = (
        _slug(identity),
        _slug(archetype),
        _slug(ecosystem or ""),
        bucket,
    )
    return "|".join(key_parts)


def event_archetype(
    event: NormalizedEvent | None,
    raws: Iterable[RawDiscoveredEvent],
    *,
    claims: Iterable[event_claim_semantics.EventClaim] = (),
) -> str:
    text = clean_text(_combined_text(event, tuple(raws)))
    claims = tuple(claims)
    if event_claim_semantics.has_confirmed_claim(claims, "exploit"):
        return "exploit_security_event"
    if event_claim_semantics.has_ruled_out_claim(claims, "exploit") or event_claim_semantics.text_has_unknown_cause(text):
        return "market_dislocation_unknown"
    if any(claim.claim_type == "exploit" and claim.cause_status == event_claim_semantics.CauseStatus.SUSPECTED.value for claim in claims):
        return "alleged_security_event"
    if any(term in text for term in ("exploit", "hack", "breach", "attack", "security incident")):
        return "exploit_security_event"
    if any(term in text for term in ("listing", "listed on", "nasdaq", "public listing", "merger")):
        return "listing_liquidity_event"
    if any(term in text for term in ("unlock", "airdrop", "tge", "vesting")):
        return "unlock_supply_event"
    if any(term in text for term in ("pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure")):
        return "proxy_attention"
    if event is not None and event.event_type:
        return clean_text(event.event_type).replace(" ", "_") or "unknown"
    return "unknown"


def infer_primary_subject(
    event: NormalizedEvent | None,
    raws: Iterable[RawDiscoveredEvent],
    *,
    claims: Iterable[event_claim_semantics.EventClaim] = (),
) -> str | None:
    for claim in claims:
        candidate = _normalized_subject(claim.subject)
        if candidate:
            return candidate
    raws = tuple(raws)
    text = _combined_text(event, raws)
    subject = event_claim_semantics.infer_primary_subject(text)
    subject = _normalized_subject(subject)
    if subject:
        return subject
    if _is_market_anomaly_event(event, raws):
        asset = _market_anomaly_asset(event, raws)
        fallback = asset.get("symbol") or asset.get("name") or asset.get("coin_id")
        fallback_subject = _normalized_subject(str(fallback or ""))
        if asset.get("identity_source") == "market_payload" and fallback_subject:
            return fallback_subject
    if event is not None:
        fallback_subject = _normalized_subject(event.external_asset)
        if fallback_subject:
            return fallback_subject
        fallback_subject = _normalized_subject(event.event_name)
        if fallback_subject:
            return fallback_subject
    return None


def infer_affected_ecosystem(event: NormalizedEvent | None, raws: Iterable[RawDiscoveredEvent]) -> str | None:
    text = _combined_text(event, tuple(raws))
    ecosystem = event_claim_semantics.infer_affected_ecosystem(text)
    if ecosystem:
        return ecosystem
    cleaned = clean_text(text)
    for ecosystem_name in ("cardano", "thorchain", "zcash", "bitcoin", "ethereum", "solana"):
        if f"{ecosystem_name} ecosystem" in cleaned:
            return ecosystem_name.title()
    return None


def classify_candidate_role(
    *,
    text: str,
    symbol: str | None = None,
    coin_id: str | None = None,
    primary_subject: str | None = None,
    affected_ecosystem: str | None = None,
    impact_category: str | None = None,
) -> tuple[str, float, tuple[str, ...]]:
    cleaned = clean_text(text)
    sym = clean_text(symbol or "")
    cid = clean_text(coin_id or "")
    subject = clean_text(primary_subject or "")
    ecosystem = clean_text(affected_ecosystem or "")
    category = clean_text(impact_category or "")
    evidence: list[str] = []
    if subject and (
        subject in {sym, cid, cid.replace("-", " ")}
        or (sym and sym in subject)
        or (cid and (cid in subject or cid.replace("-", " ") in subject))
    ):
        evidence.append("candidate_named_as_primary_subject")
        return "direct_subject", 0.90, tuple(evidence)
    if category in {"rwa_preipo_proxy", "ai_ipo_proxy", "tokenized_stock_venue"}:
        if any(term in cleaned for term in ("venue", "lets users trade", "offers", "market", "tokenized stock", "pre ipo", "pre-ipo")):
            evidence.append("candidate_venue_or_proxy_product")
            return "proxy_venue", 0.86, tuple(evidence)
        evidence.append("candidate_proxy_attention")
        return "proxy_instrument", 0.76, tuple(evidence)
    if category == "sports_fan_proxy":
        evidence.append("fan_token_event")
        return "proxy_instrument", 0.82, tuple(evidence)
    if ecosystem and ecosystem in {cid, cid.replace("-", " "), sym}:
        if subject and subject not in {ecosystem, sym, cid, cid.replace("-", " ")}:
            evidence.append(f"third_party_subject_in_{affected_ecosystem}_ecosystem")
            return "ecosystem_affected_asset", 0.78, tuple(evidence)
    if ecosystem and ecosystem in cleaned and (sym in cleaned or cid.replace("-", " ") in cleaned):
        evidence.append("candidate_mentioned_as_ecosystem_asset")
        return "ecosystem_affected_asset", 0.68, tuple(evidence)
    if category == "prediction_market_infra":
        evidence.append("infrastructure_context")
        return "infrastructure_provider", 0.72, tuple(evidence)
    if category in {"stablecoin_regulatory", "security_or_regulatory_shock"}:
        evidence.append("macro_or_ecosystem_context")
        return "macro_affected_asset", 0.58, tuple(evidence)
    return "generic_mention", 0.40, ("no_specific_candidate_role_evidence",)


def _incident_from_group(
    key: str,
    rows: list[tuple[NormalizedEvent, tuple[RawDiscoveredEvent, ...]]],
) -> CanonicalIncident:
    events = [event for event, _ in rows]
    raws = tuple({raw.raw_id: raw for _, group in rows for raw in group}.values())
    claims = event_claim_semantics.extract_event_claims(raws)
    first_seen = min((event.first_seen_time for event in events), default=datetime.now(timezone.utc))
    last_updated = max((raw.fetched_at for raw in raws), default=first_seen)
    first_event = events[0]
    primary_subject = infer_primary_subject(first_event, raws, claims=claims)
    validation = validate_incident_primary_subject(primary_subject, {
        "event": first_event,
        "raws": raws,
    })
    primary_subject = validation.normalized_subject
    subject_quality, subject_quality_reason, diagnostic_only = _subject_quality_from_validation(
        validation,
        first_event,
        raws,
    )
    ecosystem = infer_affected_ecosystem(first_event, raws)
    archetype = event_archetype(first_event, raws, claims=claims)
    domains = _independent_domains(raws)
    urls = tuple(sorted({raw.source_url for raw in raws if raw.source_url}))
    status = event_claim_semantics.current_cause_status(claims, "exploit")
    conflicts = _conflicting_claims(claims)
    name = _canonical_name(primary_subject, archetype, ecosystem, event=first_event, raws=raws)
    linked_assets = _incident_linked_assets(first_event, raws, archetype)
    warnings = _incident_warnings_for_group(first_event, raws, archetype, primary_subject)
    if subject_quality != "valid":
        warnings = tuple(dict.fromkeys((*warnings, f"incident_primary_subject_{subject_quality}")))
    if validation.warnings:
        warnings = tuple(dict.fromkeys((*warnings, *validation.warnings)))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return CanonicalIncident(
        schema_version=INCIDENT_GRAPH_SCHEMA_VERSION,
        incident_id=f"incident:{digest}",
        canonical_name=name,
        event_archetype=archetype,
        primary_subject=primary_subject,
        affected_ecosystem=ecosystem,
        first_seen_at=first_seen,
        last_updated_at=last_updated,
        raw_ids=tuple(sorted({raw.raw_id for raw in raws})),
        event_ids=tuple(sorted({event.event_id for event in events})),
        source_urls=urls,
        independent_source_domains=domains,
        claim_history=claims,
        current_cause_status=status,
        conflicting_claims=conflicts,
        linked_assets=linked_assets,
        subject_quality=subject_quality,
        subject_quality_reason=subject_quality_reason,
        diagnostic_only=diagnostic_only,
        warnings=warnings,
    )


def _combined_text(event: NormalizedEvent | None, raws: tuple[RawDiscoveredEvent, ...]) -> str:
    parts: list[str] = []
    if event is not None:
        parts.extend([event.event_name, event.event_type, event.external_asset or "", event.description or ""])
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
        enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), dict) else {}
        parts.extend([raw.title, raw.body or "", str(payload.get("source_origin") or ""), str(enrichment.get("enriched_text") or "")])
    return " ".join(str(part or "") for part in parts)


def _date_bucket(event: NormalizedEvent, raws: tuple[RawDiscoveredEvent, ...]) -> str:
    dt = event.event_time or event.first_seen_time or next((raw.published_at or raw.fetched_at for raw in raws), None)
    if dt is None:
        return "unknown-date"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def _major_named_entities(text: str) -> tuple[str, ...]:
    names = re.findall(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b", str(text or ""))
    out: list[str] = []
    for name in names:
        cleaned = _normalized_subject(name)
        if not cleaned:
            continue
        if cleaned not in out:
            out.append(cleaned)
    return tuple(out)


def _independent_domains(raws: tuple[RawDiscoveredEvent, ...]) -> tuple[str, ...]:
    domains: list[str] = []
    for raw in raws:
        url = raw.source_url or ""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            domain = clean_text(raw.provider).replace(" ", ".")
        if domain and domain not in domains:
            domains.append(domain)
    return tuple(domains)


def _conflicting_claims(claims: tuple[event_claim_semantics.EventClaim, ...]) -> tuple[str, ...]:
    has_confirmed = event_claim_semantics.has_confirmed_claim(claims, "exploit")
    has_ruled_out = event_claim_semantics.has_ruled_out_claim(claims, "exploit")
    out: list[str] = []
    if has_confirmed and has_ruled_out:
        out.append("exploit_confirmed_and_ruled_out")
    if any(claim.polarity == event_claim_semantics.ClaimPolarity.RUMORED.value for claim in claims) and has_confirmed:
        out.append("rumor_later_confirmed")
    return tuple(out)


def _canonical_name(
    subject: str | None,
    archetype: str,
    ecosystem: str | None,
    *,
    event: NormalizedEvent | None = None,
    raws: tuple[RawDiscoveredEvent, ...] = (),
) -> str:
    if _is_market_anomaly_event(event, raws) or archetype == "market_dislocation_unknown":
        asset = _market_anomaly_asset(event, raws)
        label = str(
            asset.get("symbol")
            or asset.get("name")
            or asset.get("coin_id")
            or (subject if _valid_subject(subject) else None)
            or "Unknown asset"
        )
        if _is_market_anomaly_event(event, raws):
            return f"{label} market anomaly"
        return f"{label} market dislocation"
    parts = [subject or "Unknown subject", archetype.replace("_", " ")]
    if ecosystem and clean_text(ecosystem) != clean_text(subject or ""):
        parts.append(f"in {ecosystem}")
    return " · ".join(parts)


def _asset_named_near_subject(cleaned: str, symbol: str, coin_id: str, subject: str) -> bool:
    if not subject:
        return False
    pattern = re.escape(subject)
    window = re.search(rf".{{0,80}}{pattern}.{{0,80}}", cleaned)
    if not window:
        return False
    text = window.group(0)
    return bool((symbol and symbol in text) or (coin_id and (coin_id in text or coin_id.replace("-", " ") in text)))


def _slug(value: str | None) -> str:
    cleaned = clean_text(value or "")
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    return cleaned or "unknown"


def _valid_subject(value: str | None) -> bool:
    return _normalized_subject(value) is not None


def _normalized_subject(value: str | None) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip(" -:.,;|"))
    if not text:
        return None
    text = re.sub(r"^(The|A|An)\s+", "", text).strip()
    initial_cleaned = clean_text(text)
    replacement = _SUBJECT_REPLACEMENTS.get(initial_cleaned)
    if replacement:
        return replacement
    if _is_noise_subject(initial_cleaned):
        return None
    parts = text.split()
    while parts and clean_text(parts[0]) in {"the", "a", "an"}:
        parts.pop(0)
    while parts and clean_text(parts[-1]) in _TRAILING_GENERIC_TOKENS:
        parts.pop()
    text = " ".join(parts).strip(" -:.,;|")
    cleaned = clean_text(text)
    replacement = _SUBJECT_REPLACEMENTS.get(cleaned)
    if replacement:
        return replacement
    if _is_noise_subject(cleaned):
        return None
    if not cleaned or cleaned in {"bitcoin world", "crypto news", *_GENERIC_SUBJECTS}:
        return None
    tokens = cleaned.split()
    if all(token in _GENERIC_SUBJECT_TOKENS for token in tokens):
        return None
    if len(tokens) == 1 and tokens[0] in _GENERIC_SUBJECT_TOKENS:
        return None
    if len(text) < 3 and not text.isupper():
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


def _subject_quality(
    subject: str | None,
    event: NormalizedEvent | None,
    raws: tuple[RawDiscoveredEvent, ...],
) -> tuple[str, str | None, bool]:
    if _normalized_subject(subject):
        return "valid", "validated_primary_subject", False
    if _is_market_anomaly_event(event, raws):
        asset = _market_anomaly_asset(event, raws)
        if asset.get("identity_source") == "market_payload":
            return "fallback_used", "validated_market_anomaly_asset", False
    if event is not None and (_normalized_subject(event.external_asset) or _normalized_subject(event.event_name)):
        return "fallback_used", "validated_event_entity", False
    return "invalid", "generic_or_missing_primary_subject", True


def _subject_quality_from_validation(
    validation: IncidentSubjectValidation,
    event: NormalizedEvent | None,
    raws: tuple[RawDiscoveredEvent, ...],
) -> tuple[str, str | None, bool]:
    if validation.status == "valid":
        return "valid", "validated_primary_subject", False
    if validation.status == "fallback_used" and validation.normalized_subject:
        return "fallback_used", validation.fallback_source or "validated_fallback_subject", False
    if _is_market_anomaly_event(event, raws):
        asset = _market_anomaly_asset(event, raws)
        if asset.get("identity_source") == "market_payload":
            return "fallback_used", "validated_market_anomaly_asset", False
    return "invalid", validation.rejection_reason or "generic_or_missing_primary_subject", True


def _subject_fallback_from_context(context: object | None) -> tuple[str | None, str | None]:
    if context is None:
        return None, None
    values: list[tuple[str | None, str]] = []
    if isinstance(context, dict):
        event = context.get("event")
        values.extend(_subject_values_from_event(event))
        for key in (
            "validated_external_entity",
            "external_entity",
            "external_asset",
            "validated_symbol",
            "validated_coin_id",
            "symbol",
            "coin_id",
            "asset",
            "entity",
        ):
            value = context.get(key)
            if isinstance(value, dict):
                values.extend(_subject_values_from_asset(value, f"context:{key}"))
            else:
                values.append((str(value) if value is not None else None, f"context:{key}"))
    else:
        values.extend(_subject_values_from_event(context))
    for value, source in values:
        normalized = _normalized_subject(value)
        if normalized:
            return normalized, source
    return None, None


def _subject_values_from_event(event: object | None) -> list[tuple[str | None, str]]:
    if event is None:
        return []
    values: list[tuple[str | None, str]] = []
    values.append((getattr(event, "external_asset", None), "event_external_asset"))
    payload = getattr(event, "raw_json", None)
    if isinstance(payload, dict):
        for key in ("external_asset", "validated_external_entity", "symbol", "coin_id", "name"):
            values.append((str(payload.get(key)) if payload.get(key) is not None else None, f"raw_json:{key}"))
        market = payload.get("market")
        if isinstance(market, dict):
            values.extend(_subject_values_from_asset(market, "market_payload"))
    event_name = getattr(event, "event_name", None)
    if _event_name_can_be_subject(event_name):
        values.append((str(event_name), "event_name"))
    return values


def _subject_values_from_asset(asset: dict[str, object], source: str) -> list[tuple[str | None, str]]:
    return [
        (str(asset.get("name")) if asset.get("name") is not None else None, source + ":name"),
        (str(asset.get("symbol")) if asset.get("symbol") is not None else None, source + ":symbol"),
        (str(asset.get("coin_id")) if asset.get("coin_id") is not None else None, source + ":coin_id"),
        (str(asset.get("id")) if asset.get("id") is not None else None, source + ":id"),
    ]


def _event_name_can_be_subject(value: str | None) -> bool:
    cleaned = clean_text(value or "")
    if not cleaned:
        return False
    tokens = cleaned.split()
    if not tokens or tokens[0] in _GENERIC_SUBJECT_TOKENS or tokens[0] in _GENERIC_SUBJECTS:
        return False
    if _is_noise_subject(cleaned):
        return False
    return True


def _is_market_anomaly_event(event: NormalizedEvent | None, raws: tuple[RawDiscoveredEvent, ...]) -> bool:
    if event is not None and clean_text(event.event_type) == "market_anomaly":
        return True
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
        if raw.provider == "market_anomaly" or isinstance(payload.get("anomaly"), dict):
            return True
        event_payload = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        if clean_text(event_payload.get("event_type") or payload.get("event_type") or "") == "market_anomaly":
            return True
    return False


def _market_anomaly_asset(
    event: NormalizedEvent | None,
    raws: tuple[RawDiscoveredEvent, ...],
) -> dict[str, str]:
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
        market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
        event_payload = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        symbol = str(market.get("symbol") or payload.get("symbol") or "").strip().upper()
        coin_id = str(market.get("coin_id") or market.get("id") or payload.get("coin_id") or payload.get("id") or "").strip()
        name = str(market.get("name") or payload.get("name") or "").strip()
        if not name and coin_id:
            name = coin_id.replace("-", " ").title()
        anomaly_type = str(event_payload.get("event_type") or payload.get("event_type") or "market_anomaly")
        if symbol or coin_id or name:
            return {
                "symbol": symbol,
                "coin_id": coin_id,
                "name": name,
                "anomaly_type": anomaly_type,
                "identity_source": "market_payload",
            }
    if event is not None:
        name = str(event.external_asset or "").strip()
        symbol_match = re.match(r"\s*([A-Z0-9]{2,12})\s+market\s+anomaly\b", str(event.event_name or ""))
        symbol = symbol_match.group(1) if symbol_match else ""
        if symbol or name:
            return {
                "symbol": symbol,
                "coin_id": "",
                "name": name,
                "anomaly_type": clean_text(event.event_type) or "market_anomaly",
                "identity_source": "event_name",
            }
    return {"symbol": "", "coin_id": "", "name": "", "anomaly_type": "market_anomaly", "identity_source": "missing"}


def _incident_linked_assets(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    archetype: str,
) -> tuple[IncidentAssetRole, ...]:
    """Return direct incident asset roles known from canonical incident evidence."""
    if not (_is_market_anomaly_event(event, raws) or archetype == "market_dislocation_unknown"):
        return ()
    asset = _market_anomaly_asset(event, raws)
    if asset.get("identity_source") != "market_payload":
        return ()
    symbol = str(asset.get("symbol") or "").strip().upper() or None
    coin_id = str(asset.get("coin_id") or "").strip() or None
    name = str(asset.get("name") or "").strip()
    if not (symbol or coin_id or name):
        return ()
    return (
        IncidentAssetRole(
            symbol=symbol,
            coin_id=coin_id,
            role="direct_subject",
            confidence=0.90,
            evidence=("market_anomaly_validated_asset",),
        ),
    )


def _incident_warnings_for_group(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    archetype: str,
    primary_subject: str | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if _is_market_anomaly_event(event, raws) or archetype == "market_dislocation_unknown":
        asset = _market_anomaly_asset(event, raws)
        if asset.get("identity_source") != "market_payload":
            warnings.append("market_anomaly_missing_validated_asset")
        if primary_subject is not None and not _valid_subject(primary_subject):
            warnings.append("market_anomaly_generic_primary_subject_rejected")
    return tuple(dict.fromkeys(warnings))
