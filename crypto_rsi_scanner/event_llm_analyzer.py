"""Research-only shadow LLM relationship analysis for event candidates."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from . import event_alerts
from .event_llm_models import (
    ASSET_ROLE_VALUES,
    RECOMMENDED_ALERT_ACTION_VALUES,
    RELATIONSHIP_TYPE_VALUES,
    EventLLMAnalysis,
    EventLLMAssetRelationship,
    EventLLMEvidenceQuote,
    EventLLMExternalCatalyst,
    EventLLMSourceQuality,
)
from .event_models import (
    DiscoveredEventFadeCandidate,
    EventAssetLink,
    EventDiscoveryResult,
    RawDiscoveredEvent,
)
from .event_resolver import clean_text, strip_publisher_suffix
from .llm_providers.base import LLMProviderResult, LLMRelationshipProvider

log = logging.getLogger(__name__)

LLM_ANALYSIS_SCHEMA_VERSION = "event_llm_analysis_v1"


class EventLLMValidationError(ValueError):
    """Raised when provider output is not a valid relationship analysis."""


@dataclass(frozen=True)
class EventLLMConfig:
    enabled: bool = False
    mode: str = "shadow"
    provider: str = "fixture"
    model: str | None = None
    max_candidates_per_run: int = 20
    min_prefilter_score: int = 45
    require_evidence_quotes: bool = True
    cache_path: Path | None = None
    prompt_version: str = "llm_proxy_context_v1"


@dataclass(frozen=True)
class EventLLMReportRow:
    candidate: DiscoveredEventFadeCandidate
    alert: event_alerts.EventAlertCandidate
    analysis: EventLLMAnalysis | None
    agreement: str
    warnings: tuple[str, ...] = ()


def analyze_event_candidates(
    result: EventDiscoveryResult,
    alerts: Iterable[event_alerts.EventAlertCandidate],
    provider: LLMRelationshipProvider,
    *,
    cfg: EventLLMConfig | None = None,
    now: datetime | None = None,
) -> list[EventLLMReportRow]:
    """Analyze event-alert candidates in shadow mode without changing alerts."""
    cfg = cfg or EventLLMConfig()
    del now  # reserved for future prompt/caching metadata
    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    links_by_event: dict[str, list[EventAssetLink]] = {}
    for link in result.links:
        links_by_event.setdefault(link.event_id, []).append(link)

    cache = _load_cache(cfg.cache_path)
    cache_changed = False
    rows: list[EventLLMReportRow] = []
    selected = [
        alert for alert in alerts
        if alert.opportunity_score >= cfg.min_prefilter_score
    ][: max(0, cfg.max_candidates_per_run)]
    for alert in selected:
        candidate = alert.discovery_candidate
        packet = build_evidence_packet(
            candidate,
            raw_by_id=raw_by_id,
            links=links_by_event.get(candidate.event.event_id, []),
            alert=alert,
            prompt_version=cfg.prompt_version,
        )
        warnings: list[str] = []
        raw: dict[str, Any] | None
        cache_key = _cache_key(packet, cfg.prompt_version)
        cached = cache.get(cache_key)
        if isinstance(cached, Mapping):
            raw = dict(cached)
        else:
            provider_result = provider.analyze_relationship(packet)
            raw = provider_result.raw
            if provider_result.warning:
                warnings.append(provider_result.warning)
            if raw is not None and cfg.cache_path is not None:
                cache[cache_key] = raw
                cache_changed = True
        analysis: EventLLMAnalysis | None = None
        if raw is not None:
            try:
                analysis = validate_llm_analysis(
                    raw,
                    packet,
                    provider_name=getattr(provider, "name", cfg.provider),
                    model=cfg.model,
                    prompt_version=cfg.prompt_version,
                    require_evidence_quotes=cfg.require_evidence_quotes,
                )
                warnings.extend(analysis.warnings)
            except EventLLMValidationError as exc:
                warnings.append(str(exc))
        rows.append(EventLLMReportRow(
            candidate=candidate,
            alert=alert,
            analysis=analysis,
            agreement=_agreement(candidate, analysis),
            warnings=tuple(dict.fromkeys(warnings)),
        ))
    if cache_changed:
        _write_cache(cfg.cache_path, cache)
    return rows


def build_evidence_packet(
    candidate: DiscoveredEventFadeCandidate,
    *,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    links: Iterable[EventAssetLink],
    alert: event_alerts.EventAlertCandidate | None = None,
    prompt_version: str = "llm_proxy_context_v1",
) -> dict[str, Any]:
    raw_events = [raw_by_id[raw_id] for raw_id in candidate.event.raw_ids if raw_id in raw_by_id]
    original_titles = tuple(raw.title for raw in raw_events if raw.title)
    raw_bodies = tuple(raw.body for raw in raw_events if raw.body)
    source_origins = _source_origins(raw_events)
    source_urls = tuple(url for raw in raw_events for url in (raw.source_url,) if url) or candidate.event.source_urls
    return {
        "schema_version": LLM_ANALYSIS_SCHEMA_VERSION,
        "prompt_version": prompt_version,
        "candidate_key": _candidate_key(candidate),
        "event": {
            "event_id": candidate.event.event_id,
            "event_name": candidate.event.event_name,
            "clean_title": strip_publisher_suffix(candidate.event.event_name),
            "original_titles": list(original_titles),
            "description": candidate.event.description or "",
            "event_type": candidate.event.event_type,
            "external_asset": candidate.event.external_asset,
            "event_time": candidate.event.event_time.isoformat() if candidate.event.event_time else None,
            "event_time_confidence": candidate.event.event_time_confidence,
            "event_time_source": candidate.event.event_time_source,
            "first_seen_time": candidate.event.first_seen_time.isoformat(),
            "source": candidate.event.source,
            "source_urls": list(source_urls),
            "source_origins": list(source_origins),
            "published_at": [_iso(raw.published_at) for raw in raw_events if raw.published_at],
            "fetched_at": [_iso(raw.fetched_at) for raw in raw_events],
            "raw_bodies": list(raw_bodies),
        },
        "asset": {
            "coin_id": candidate.asset.coin_id,
            "symbol": candidate.asset.symbol,
            "name": candidate.asset.name,
            "categories": list(candidate.asset.categories),
            "aliases": list(candidate.asset.aliases),
        },
        "resolver": {
            "selected_link": _link_payload(candidate.link, candidate),
            "candidate_assets": [_link_payload(link, candidate) for link in links],
        },
        "rule_classification": {
            "asset_role": candidate.classification.asset_role,
            "asset_role_confidence": candidate.classification.asset_role_confidence,
            "relationship_type": candidate.classification.relationship_type,
            "is_proxy_narrative": candidate.classification.is_proxy_narrative,
            "is_direct_beneficiary": candidate.classification.is_direct_beneficiary,
            "confidence": candidate.classification.confidence,
            "reason": candidate.classification.reason,
            "evidence": list(candidate.classification.evidence),
        },
        "external_catalyst": {
            "name": candidate.event.external_asset,
            "event_type": candidate.event.event_type,
            "event_time": candidate.event.event_time.isoformat() if candidate.event.event_time else None,
            "confidence": candidate.event.confidence,
        },
        "market": _market_summary(candidate),
        "derivatives": _derivatives_summary(candidate),
        "alert": _alert_summary(alert),
    }


def validate_llm_analysis(
    raw: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    provider_name: str,
    model: str | None,
    prompt_version: str,
    require_evidence_quotes: bool = True,
) -> EventLLMAnalysis:
    asset_role = _required_enum(raw, "asset_role", ASSET_ROLE_VALUES)
    relationship_type = _required_enum(raw, "relationship_type", RELATIONSHIP_TYPE_VALUES)
    action = _required_enum(raw, "recommended_alert_action", RECOMMENDED_ALERT_ACTION_VALUES)
    confidence = _clamp_float(raw.get("confidence"), field="confidence")
    reason = _required_text(raw, "reason")
    warnings = [str(w) for w in raw.get("warnings", []) if str(w).strip()]
    quotes = _verified_quotes(raw.get("evidence_quotes"), packet)
    external = _external_catalyst(raw.get("external_catalyst"), packet)
    source_quality = _source_quality(raw.get("source_quality"), packet)
    all_quotes = (*quotes, *external.evidence_quotes)
    missing_quotes = [quote for quote in all_quotes if not quote.found_in_source]
    if require_evidence_quotes and not all_quotes:
        warnings.append("missing evidence quotes; confidence clamped")
        confidence = min(confidence, 0.50)
    if missing_quotes:
        warnings.append("one or more evidence quotes were not found in source text; confidence clamped")
        confidence = min(confidence, 0.50)
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    asset = packet.get("asset") if isinstance(packet.get("asset"), Mapping) else {}
    relationship = EventLLMAssetRelationship(
        coin_id=str(asset.get("coin_id") or ""),
        symbol=str(asset.get("symbol") or ""),
        asset_role=asset_role,
        relationship_type=relationship_type,
        confidence=confidence,
        reason=reason,
        evidence_quotes=quotes,
    )
    return EventLLMAnalysis(
        schema_version=LLM_ANALYSIS_SCHEMA_VERSION,
        prompt_version=prompt_version,
        provider=provider_name,
        model=model,
        event_id=str(event.get("event_id") or ""),
        coin_id=relationship.coin_id,
        symbol=relationship.symbol,
        asset_relationship=relationship,
        external_catalyst=external,
        source_quality=source_quality,
        recommended_alert_action=action,
        confidence=confidence,
        evidence_quotes=all_quotes,
        warnings=tuple(dict.fromkeys(warnings)),
        raw_response=dict(raw),
    )


def format_llm_shadow_report(rows: Iterable[EventLLMReportRow]) -> str:
    rows = list(rows)
    out = [
        "=" * 78,
        "EVENT LLM SHADOW REPORT (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 78,
        f"Candidates analyzed: {len(rows)}",
        "",
    ]
    if not rows:
        out.append("No candidates passed the LLM prefilter.")
        return "\n".join(out)
    for row in rows:
        candidate = row.candidate
        analysis = row.analysis
        out.append(
            f"{row.agreement:<12} {candidate.asset.symbol}/{candidate.asset.coin_id} "
            f"score={row.alert.opportunity_score} rule_tier={row.alert.tier.value}"
        )
        out.append(f"  event: {candidate.event.event_name}")
        out.append(
            f"  rule: role={candidate.classification.asset_role} "
            f"rel={candidate.classification.relationship_type}"
        )
        if analysis is None:
            out.append("  llm: no valid analysis")
        else:
            out.append(
                f"  llm: role={analysis.asset_role} rel={analysis.relationship_type} "
                f"action={analysis.recommended_alert_action} conf={analysis.confidence:.2f}"
            )
            out.append(f"  llm reason: {analysis.asset_relationship.reason}")
            quote_text = "; ".join(
                f"{quote.source_field}: \"{quote.text}\""
                for quote in analysis.evidence_quotes[:3]
            )
            out.append(f"  llm evidence: {quote_text or 'none'}")
        if row.warnings:
            out.append("  warnings: " + "; ".join(row.warnings))
        out.append("")
    return "\n".join(out).rstrip()


def _required_enum(raw: Mapping[str, Any], field: str, allowed: frozenset[str]) -> str:
    value = str(raw.get(field) or "")
    if value not in allowed:
        raise EventLLMValidationError(f"invalid LLM {field}: {value or '<missing>'}")
    return value


def _required_text(raw: Mapping[str, Any], field: str) -> str:
    value = str(raw.get(field) or "").strip()
    if not value:
        raise EventLLMValidationError(f"missing LLM {field}")
    return value


def _clamp_float(value: object, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EventLLMValidationError(f"invalid LLM {field}: {value!r}") from exc
    return max(0.0, min(1.0, number))


def _verified_quotes(raw_quotes: object, packet: Mapping[str, Any]) -> tuple[EventLLMEvidenceQuote, ...]:
    if not isinstance(raw_quotes, list):
        return ()
    out: list[EventLLMEvidenceQuote] = []
    for item in raw_quotes:
        if not isinstance(item, Mapping):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        source_field = str(item.get("source_field") or "source_text")
        out.append(EventLLMEvidenceQuote(
            text=text,
            source_field=source_field,
            supports=str(item.get("supports") or ""),
            found_in_source=_quote_found(text, source_field, packet),
        ))
    return tuple(out)


def _external_catalyst(raw: object, packet: Mapping[str, Any]) -> EventLLMExternalCatalyst:
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    if not isinstance(raw, Mapping):
        raw = {}
    return EventLLMExternalCatalyst(
        name=raw.get("name") if raw.get("name") is not None else event.get("external_asset"),
        catalyst_type=str(raw.get("catalyst_type") or event.get("event_type") or "unknown"),
        event_time=raw.get("event_time") if raw.get("event_time") is not None else event.get("event_time"),
        confidence=_safe_confidence(raw.get("confidence"), event.get("event_time_confidence")),
        evidence_quotes=_verified_quotes(raw.get("evidence_quotes"), packet),
    )


def _source_quality(raw: object, packet: Mapping[str, Any]) -> EventLLMSourceQuality:
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    origins = event.get("source_origins") if isinstance(event.get("source_origins"), list) else []
    if not isinstance(raw, Mapping):
        raw = {}
    return EventLLMSourceQuality(
        source_origin=raw.get("source_origin") if raw.get("source_origin") is not None else (origins[0] if origins else None),
        source_confidence=_safe_confidence(raw.get("source_confidence"), 0.0),
        timing_quality=str(raw.get("timing_quality") or "unknown"),
        notes=str(raw.get("notes") or ""),
    )


def _safe_confidence(value: object, default: object) -> float:
    try:
        return max(0.0, min(1.0, float(value if value is not None else default)))
    except (TypeError, ValueError):
        return 0.0


def _quote_found(text: str, source_field: str, packet: Mapping[str, Any]) -> bool:
    needle = clean_text(text)
    if not needle:
        return False
    fields = _source_text_fields(packet)
    preferred = fields.get(source_field)
    if preferred and needle in clean_text(preferred):
        return True
    return any(needle in clean_text(value) for value in fields.values())


def _source_text_fields(packet: Mapping[str, Any]) -> dict[str, str]:
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    return {
        "event_name": str(event.get("event_name") or ""),
        "clean_title": str(event.get("clean_title") or ""),
        "description": str(event.get("description") or ""),
        "original_titles": " ".join(str(v) for v in event.get("original_titles", []) if v),
        "raw_bodies": " ".join(str(v) for v in event.get("raw_bodies", []) if v),
        "source_origin": " ".join(str(v) for v in event.get("source_origins", []) if v),
    }


def _link_payload(link: EventAssetLink, candidate: DiscoveredEventFadeCandidate) -> dict[str, Any]:
    return {
        "coin_id": link.coin_id,
        "symbol": link.symbol,
        "name": link.name,
        "link_confidence": link.link_confidence,
        "match_reason": link.match_reason,
        "evidence": list(link.evidence),
        "evidence_locations": {
            evidence: _evidence_locations(evidence, candidate)
            for evidence in link.evidence
        },
    }


def _evidence_locations(evidence: str, candidate: DiscoveredEventFadeCandidate) -> list[str]:
    needle = clean_text(evidence)
    locations: list[str] = []
    fields = {
        "event_name": candidate.event.event_name,
        "description": candidate.event.description or "",
        "external_asset": candidate.event.external_asset or "",
    }
    for field, value in fields.items():
        if needle and needle in clean_text(value):
            locations.append(field)
    return locations or ["unknown"]


def _market_summary(candidate: DiscoveredEventFadeCandidate) -> dict[str, Any]:
    market = candidate.fade_candidate.market if candidate.fade_candidate else None
    if market is None:
        return {}
    return {
        "price": market.price,
        "market_cap": market.market_cap,
        "volume_24h": market.volume_24h,
        "return_24h": market.return_24h,
        "return_72h": market.return_72h,
        "return_7d": market.return_7d,
        "volume_zscore_24h": market.volume_zscore_24h,
    }


def _derivatives_summary(candidate: DiscoveredEventFadeCandidate) -> dict[str, Any]:
    derivatives = candidate.fade_candidate.derivatives if candidate.fade_candidate else None
    if derivatives is None:
        return {}
    return {
        "perp_available": derivatives.perp_available,
        "open_interest_24h_change_pct": derivatives.open_interest_24h_change_pct,
        "open_interest_to_market_cap": derivatives.open_interest_to_market_cap,
        "funding_rate_8h": derivatives.funding_rate_8h,
        "perp_spot_volume_ratio": derivatives.perp_spot_volume_ratio,
        "long_short_ratio": derivatives.long_short_ratio,
    }


def _alert_summary(alert: event_alerts.EventAlertCandidate | None) -> dict[str, Any]:
    if alert is None:
        return {}
    return {
        "tier": alert.tier.value,
        "opportunity_score": alert.opportunity_score,
        "reason": alert.reason,
        "rejected_reason": alert.rejected_reason,
        "score_components": dict(alert.score_components),
    }


def _agreement(candidate: DiscoveredEventFadeCandidate, analysis: EventLLMAnalysis | None) -> str:
    if analysis is None:
        return "NO_ANALYSIS"
    role_agrees = candidate.classification.asset_role == analysis.asset_role
    rel_agrees = candidate.classification.relationship_type == analysis.relationship_type
    return "AGREE" if role_agrees and rel_agrees else "DISAGREE"


def _source_origins(raw_events: Iterable[RawDiscoveredEvent]) -> tuple[str, ...]:
    origins: list[str] = []
    seen: set[str] = set()
    for raw in raw_events:
        for origin in _raw_source_origins(raw):
            key = clean_text(origin)
            if not key or key in seen:
                continue
            seen.add(key)
            origins.append(origin)
    return tuple(origins or ("unknown_source_origin",))


def _raw_source_origins(raw: RawDiscoveredEvent) -> tuple[str, ...]:
    payload = raw.raw_json or {}
    raw_values = (
        payload.get("source_origin"),
        payload.get("source"),
        payload.get("publisher"),
        payload.get("domain"),
        _publisher_from_title(raw.title),
        _domain(raw.source_url),
        raw.provider,
    )
    return tuple(str(value) for value in raw_values if value)


def _publisher_from_title(title: str) -> str | None:
    if " - " not in title:
        return None
    publisher = title.rsplit(" - ", 1)[-1].strip()
    return publisher or None


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.removeprefix("www.") or None


def _candidate_key(candidate: DiscoveredEventFadeCandidate) -> str:
    return f"{candidate.event.event_id}:{candidate.asset.coin_id}"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def _cache_key(packet: Mapping[str, Any], prompt_version: str) -> str:
    encoded = json.dumps(
        {"prompt_version": prompt_version, "packet": packet},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cache(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return dict(raw) if isinstance(raw, Mapping) else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM analysis cache could not be read: %s", exc)
        return {}


def _write_cache(path: Path | None, cache: Mapping[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM analysis cache could not be written: %s", exc)
