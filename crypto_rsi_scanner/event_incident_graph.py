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
    "no",
    "none",
    "unknown",
    "unclear",
    "n/a",
    "na",
    "market",
    "catalyst",
    "event",
    "token",
    "coin",
}


@dataclass(frozen=True)
class IncidentAssetRole:
    symbol: str | None
    coin_id: str | None
    role: str
    confidence: float
    evidence: tuple[str, ...] = ()


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
    warnings: tuple[str, ...] = field(default_factory=tuple)


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
    identity = subject or (named[0] if named else None) or event.external_asset or event.event_name
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
        if _valid_subject(claim.subject):
            return claim.subject
    raws = tuple(raws)
    text = _combined_text(event, raws)
    subject = event_claim_semantics.infer_primary_subject(text)
    if _valid_subject(subject):
        return subject
    if _is_market_anomaly_event(event, raws):
        asset = _market_anomaly_asset(event, raws)
        fallback = asset.get("symbol") or asset.get("name") or asset.get("coin_id")
        if _valid_subject(str(fallback or "")):
            return str(fallback)
    if event is not None:
        if _valid_subject(event.external_asset):
            return event.external_asset
        if _valid_subject(event.event_name):
            return event.event_name
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
    ecosystem = infer_affected_ecosystem(first_event, raws)
    archetype = event_archetype(first_event, raws, claims=claims)
    domains = _independent_domains(raws)
    urls = tuple(sorted({raw.source_url for raw in raws if raw.source_url}))
    status = event_claim_semantics.current_cause_status(claims, "exploit")
    conflicts = _conflicting_claims(claims)
    name = _canonical_name(primary_subject, archetype, ecosystem, event=first_event, raws=raws)
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
        linked_assets=(),
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
        cleaned = name.strip()
        if clean_text(cleaned) in {"the", "a", "an", "bitcoin world", "crypto news", *_GENERIC_SUBJECTS}:
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
        label = str(asset.get("symbol") or asset.get("name") or asset.get("coin_id") or subject or "Unknown asset")
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
    cleaned = clean_text(value or "")
    return bool(cleaned and cleaned not in _GENERIC_SUBJECTS)


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
            }
    return {"symbol": "", "coin_id": "", "name": "", "anomaly_type": "market_anomaly"}
