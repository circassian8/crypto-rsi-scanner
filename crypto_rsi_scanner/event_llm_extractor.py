"""Research-only LLM extraction for raw event-discovery evidence."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .event_llm_extraction_models import (
    ASSET_MENTION_TYPE_VALUES,
    CATALYST_TYPE_VALUES,
    EventLLMCryptoAssetMention,
    EventLLMEventDateHint,
    EventLLMExternalCatalystCandidate,
    EventLLMExtractionQuote,
    EventLLMFalsePositiveTerm,
    EventLLMRawEventExtraction,
)
from .event_models import RawDiscoveredEvent
from .event_resolver import clean_text, strip_publisher_suffix
from .llm_providers.base import LLMExtractionProvider

log = logging.getLogger(__name__)

LLM_EXTRACTION_SCHEMA_VERSION = "event_llm_extraction_v1"


class EventLLMExtractionValidationError(ValueError):
    """Raised when provider output is not a valid raw-event extraction."""


@dataclass(frozen=True)
class EventLLMExtractorConfig:
    enabled: bool = False
    mode: str = "shadow"
    provider: str = "fixture"
    model: str | None = None
    max_events_per_run: int = 50
    require_evidence_quotes: bool = True
    cache_path: Path | None = None
    prompt_version: str = "llm_raw_event_extraction_v1"


@dataclass(frozen=True)
class EventLLMExtractionReportRow:
    raw_event: RawDiscoveredEvent
    extraction: EventLLMRawEventExtraction | None
    warnings: tuple[str, ...] = ()


def analyze_raw_events(
    raw_events: Iterable[RawDiscoveredEvent],
    provider: LLMExtractionProvider,
    *,
    cfg: EventLLMExtractorConfig | None = None,
) -> list[EventLLMExtractionReportRow]:
    """Extract catalyst/asset/source-noise metadata from raw events."""
    cfg = cfg or EventLLMExtractorConfig()
    cache = _load_cache(cfg.cache_path)
    cache_changed = False
    rows: list[EventLLMExtractionReportRow] = []
    selected = list(raw_events)[: max(0, cfg.max_events_per_run)]
    provider_name = str(getattr(provider, "name", cfg.provider))
    provider_model = getattr(provider, "model", cfg.model)
    for raw_event in selected:
        packet = build_raw_event_packet(raw_event, prompt_version=cfg.prompt_version)
        warnings: list[str] = []
        cache_key = _cache_key(packet, cfg, provider_name, provider_model)
        cached = cache.get(cache_key)
        if isinstance(cached, Mapping) and isinstance(cached.get("raw"), Mapping):
            raw = dict(cached["raw"])
        elif isinstance(cached, Mapping):
            warnings.append("LLM extraction cache entry ignored: old cache format")
            provider_result = provider.extract_raw_event(packet)
            raw = provider_result.raw
            if provider_result.warning:
                warnings.append(provider_result.warning)
            if raw is not None and cfg.cache_path is not None:
                cache[cache_key] = _cache_entry(raw, packet, provider_name, provider_model, cfg)
                cache_changed = True
        else:
            provider_result = provider.extract_raw_event(packet)
            raw = provider_result.raw
            if provider_result.warning:
                warnings.append(provider_result.warning)
            if raw is not None and cfg.cache_path is not None:
                cache[cache_key] = _cache_entry(raw, packet, provider_name, provider_model, cfg)
                cache_changed = True
        extraction: EventLLMRawEventExtraction | None = None
        if raw is not None:
            try:
                extraction = validate_llm_extraction(
                    raw,
                    packet,
                    provider_name=provider_name,
                    model=provider_model,
                    prompt_version=cfg.prompt_version,
                    require_evidence_quotes=cfg.require_evidence_quotes,
                )
                warnings.extend(extraction.warnings)
            except EventLLMExtractionValidationError as exc:
                warnings.append(str(exc))
        rows.append(EventLLMExtractionReportRow(raw_event=raw_event, extraction=extraction, warnings=tuple(dict.fromkeys(warnings))))
    if cache_changed:
        _write_cache(cfg.cache_path, cache)
    return rows


def build_raw_event_packet(raw_event: RawDiscoveredEvent, *, prompt_version: str = "llm_raw_event_extraction_v1") -> dict[str, Any]:
    payload = raw_event.raw_json or {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    source_origin = _source_origin(raw_event.source_url) or raw_event.provider
    return {
        "schema_version": LLM_EXTRACTION_SCHEMA_VERSION,
        "prompt_version": prompt_version,
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "source_url": raw_event.source_url,
        "source_origin": source_origin,
        "published_at": _iso(raw_event.published_at),
        "fetched_at": _iso(raw_event.fetched_at),
        "title": raw_event.title,
        "clean_title": strip_publisher_suffix(raw_event.title),
        "body": raw_event.body or "",
        "source_confidence": raw_event.source_confidence,
        "content_hash": raw_event.content_hash,
        "event_payload": {
            "event_name": event_payload.get("event_name") or payload.get("event_name"),
            "event_type": event_payload.get("event_type") or payload.get("event_type"),
            "external_asset": event_payload.get("external_asset") or payload.get("external_asset"),
            "event_time": event_payload.get("event_time") or payload.get("event_time"),
            "description": event_payload.get("description") or payload.get("description"),
        },
    }


def validate_llm_extraction(
    raw: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    provider_name: str,
    model: str | None,
    prompt_version: str,
    require_evidence_quotes: bool = True,
) -> EventLLMRawEventExtraction:
    confidence = _clamp_float(raw.get("confidence"), field="confidence")
    warnings = [str(w) for w in raw.get("warnings", []) if str(w).strip()]
    catalysts = tuple(_external_catalyst(item, packet) for item in _required_list(raw, "external_catalysts"))
    mentions = tuple(_asset_mention(item, packet) for item in _required_list(raw, "crypto_asset_mentions"))
    false_terms = tuple(_false_positive_term(item, packet) for item in _optional_list(raw, "false_positive_terms"))
    date_hints = tuple(_event_date_hint(item, packet) for item in _optional_list(raw, "event_date_hints"))
    followups = tuple(str(item).strip() for item in _optional_list(raw, "suggested_followup_queries") if str(item).strip())
    all_quotes = tuple(
        quote
        for collection in (
            *(item.evidence_quotes for item in catalysts),
            *(item.evidence_quotes for item in mentions),
            *(item.evidence_quotes for item in false_terms),
            *(item.evidence_quotes for item in date_hints),
        )
        for quote in collection
    )
    missing_quotes = [quote for quote in all_quotes if not quote.found_in_source]
    if require_evidence_quotes and not all_quotes:
        warnings.append("missing evidence quotes; confidence clamped")
        confidence = min(confidence, 0.50)
    if missing_quotes:
        warnings.append("one or more evidence quotes were not found in source text; confidence clamped")
        confidence = min(confidence, 0.50)
    return EventLLMRawEventExtraction(
        schema_version=LLM_EXTRACTION_SCHEMA_VERSION,
        provider=provider_name,
        model=model,
        prompt_version=prompt_version,
        raw_id=str(packet.get("raw_id") or ""),
        confidence=confidence,
        external_catalysts=catalysts,
        crypto_asset_mentions=mentions,
        false_positive_terms=false_terms,
        event_date_hints=date_hints,
        suggested_followup_queries=followups,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def enrich_raw_events_with_extractions(
    raw_events: Iterable[RawDiscoveredEvent],
    rows: Iterable[EventLLMExtractionReportRow],
    *,
    min_confidence: float = 0.70,
) -> tuple[RawDiscoveredEvent, ...]:
    """Return raw events with extraction metadata appended for resolver research.

    This does not validate assets by itself. It only exposes extracted terms in
    the raw evidence text so the deterministic resolver can match them against a
    known asset universe/alias set.
    """
    extraction_by_raw = {
        row.raw_event.raw_id: row.extraction
        for row in rows
        if row.extraction is not None and row.extraction.confidence >= min_confidence
    }
    out: list[RawDiscoveredEvent] = []
    for raw in raw_events:
        extraction = extraction_by_raw.get(raw.raw_id)
        if extraction is None:
            out.append(raw)
            continue
        payload = dict(raw.raw_json or {})
        payload["llm_extraction"] = _extraction_payload(extraction)
        hints = _resolver_hint_text(extraction, min_confidence=min_confidence)
        body = raw.body or ""
        if hints:
            body = f"{body}\n\nLLM extracted research hints: {hints}".strip()
            payload = _append_resolver_hints_to_payload(payload, hints)
        out.append(replace(raw, body=body, raw_json=payload))
    return tuple(out)


def format_llm_extract_report(rows: Iterable[EventLLMExtractionReportRow]) -> str:
    rows = list(rows)
    out = [
        "=" * 76,
        "EVENT LLM RAW EXTRACTION REPORT (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 76,
        f"Raw events analyzed: {len(rows)}",
        "",
    ]
    if not rows:
        out.append("No raw events passed the extractor input limit.")
        return "\n".join(out)
    for row in rows:
        extraction = row.extraction
        out.append(f"{row.raw_event.raw_id} · {row.raw_event.provider}")
        out.append(f"  title: {row.raw_event.title}")
        if extraction is None:
            out.append("  extraction: unavailable")
        else:
            out.append(f"  confidence: {extraction.confidence:.2f}")
            if extraction.external_catalysts:
                out.append("  catalysts: " + "; ".join(
                    f"{item.name or 'unknown'} ({item.catalyst_type}, conf={item.confidence:.2f})"
                    for item in extraction.external_catalysts
                ))
            if extraction.crypto_asset_mentions:
                out.append("  asset mentions: " + "; ".join(
                    f"{item.name or item.symbol or 'unknown'}"
                    f"{('/' + item.symbol) if item.symbol and item.name else ''}"
                    f" ({item.mention_type}, conf={item.confidence:.2f})"
                    for item in extraction.crypto_asset_mentions
                ))
            if extraction.false_positive_terms:
                out.append("  false-positive terms: " + "; ".join(
                    f"{item.text} ({item.reason})" for item in extraction.false_positive_terms
                ))
            if extraction.suggested_followup_queries:
                out.append("  follow-up: " + "; ".join(extraction.suggested_followup_queries[:3]))
        for warning in row.warnings:
            out.append(f"  warning: {warning}")
        out.append("")
    return "\n".join(out).rstrip()


def _external_catalyst(raw: object, packet: Mapping[str, Any]) -> EventLLMExternalCatalystCandidate:
    if not isinstance(raw, Mapping):
        raise EventLLMExtractionValidationError("external_catalysts entries must be objects")
    catalyst_type = _enum_value(raw, "catalyst_type", CATALYST_TYPE_VALUES)
    return EventLLMExternalCatalystCandidate(
        name=_optional_text(raw.get("name")),
        catalyst_type=catalyst_type,
        event_time=_optional_text(raw.get("event_time")),
        event_time_confidence=_clamp_float(raw.get("event_time_confidence", 0.0), field="event_time_confidence"),
        confidence=_clamp_float(raw.get("confidence"), field="catalyst confidence"),
        evidence_quotes=_verified_quotes(raw.get("evidence_quotes"), packet),
    )


def _asset_mention(raw: object, packet: Mapping[str, Any]) -> EventLLMCryptoAssetMention:
    if not isinstance(raw, Mapping):
        raise EventLLMExtractionValidationError("crypto_asset_mentions entries must be objects")
    mention_type = _enum_value(raw, "mention_type", ASSET_MENTION_TYPE_VALUES)
    return EventLLMCryptoAssetMention(
        name=_optional_text(raw.get("name")),
        symbol=_optional_text(raw.get("symbol")),
        coin_id=_optional_text(raw.get("coin_id")),
        contract_address=_optional_text(raw.get("contract_address")),
        mention_type=mention_type,
        confidence=_clamp_float(raw.get("confidence"), field="asset mention confidence"),
        evidence_quotes=_verified_quotes(raw.get("evidence_quotes"), packet),
    )


def _false_positive_term(raw: object, packet: Mapping[str, Any]) -> EventLLMFalsePositiveTerm:
    if not isinstance(raw, Mapping):
        raise EventLLMExtractionValidationError("false_positive_terms entries must be objects")
    return EventLLMFalsePositiveTerm(
        text=_required_text(raw, "text"),
        reason=_required_text(raw, "reason"),
        confidence=_clamp_float(raw.get("confidence"), field="false positive confidence"),
        evidence_quotes=_verified_quotes(raw.get("evidence_quotes"), packet),
    )


def _event_date_hint(raw: object, packet: Mapping[str, Any]) -> EventLLMEventDateHint:
    if not isinstance(raw, Mapping):
        raise EventLLMExtractionValidationError("event_date_hints entries must be objects")
    return EventLLMEventDateHint(
        text=_required_text(raw, "text"),
        parsed_event_time=_optional_text(raw.get("parsed_event_time")),
        confidence=_clamp_float(raw.get("confidence"), field="event date confidence"),
        evidence_quotes=_verified_quotes(raw.get("evidence_quotes"), packet),
    )


def _verified_quotes(raw_quotes: object, packet: Mapping[str, Any]) -> tuple[EventLLMExtractionQuote, ...]:
    if raw_quotes is None:
        return ()
    if not isinstance(raw_quotes, list):
        raise EventLLMExtractionValidationError("evidence_quotes must be a list")
    source_text = clean_text(_source_text(packet))
    out: list[EventLLMExtractionQuote] = []
    for item in raw_quotes:
        if not isinstance(item, Mapping):
            raise EventLLMExtractionValidationError("evidence quote entries must be objects")
        text = _required_text(item, "text")
        out.append(EventLLMExtractionQuote(
            text=text,
            source_field=str(item.get("source_field") or ""),
            supports=str(item.get("supports") or ""),
            found_in_source=bool(text and clean_text(text) in source_text),
        ))
    return tuple(out)


def _required_list(raw: Mapping[str, Any], field: str) -> list[Any]:
    value = raw.get(field)
    if not isinstance(value, list):
        raise EventLLMExtractionValidationError(f"missing LLM extraction {field}")
    return value


def _optional_list(raw: Mapping[str, Any], field: str) -> list[Any]:
    value = raw.get(field, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise EventLLMExtractionValidationError(f"invalid LLM extraction {field}")
    return value


def _enum_value(raw: Mapping[str, Any], field: str, allowed: frozenset[str]) -> str:
    value = str(raw.get(field) or "")
    if value not in allowed:
        raise EventLLMExtractionValidationError(f"invalid LLM extraction {field}: {value or '<missing>'}")
    return value


def _required_text(raw: Mapping[str, Any], field: str) -> str:
    value = str(raw.get(field) or "").strip()
    if not value:
        raise EventLLMExtractionValidationError(f"missing LLM extraction {field}")
    return value


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clamp_float(value: object, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise EventLLMExtractionValidationError(f"invalid LLM extraction {field}: {value!r}") from exc
    return max(0.0, min(1.0, parsed))


def _source_text(packet: Mapping[str, Any]) -> str:
    payload = packet.get("event_payload") if isinstance(packet.get("event_payload"), Mapping) else {}
    parts = [
        packet.get("title"),
        packet.get("clean_title"),
        packet.get("body"),
        packet.get("source_origin"),
        payload.get("event_name"),
        payload.get("description"),
        payload.get("external_asset"),
    ]
    return "\n".join(str(part) for part in parts if part)


def _resolver_hint_text(extraction: EventLLMRawEventExtraction, *, min_confidence: float) -> str:
    hints: list[str] = []
    for mention in extraction.crypto_asset_mentions:
        if mention.confidence < min_confidence:
            continue
        if mention.mention_type in {"publisher_or_source", "ordinary_word"}:
            continue
        label = " ".join(value for value in (mention.name, mention.symbol, mention.coin_id) if value)
        if label:
            hints.append(label)
    catalysts = [item.name for item in extraction.external_catalysts if item.name and item.confidence >= min_confidence]
    return "; ".join(dict.fromkeys([*hints, *catalysts]))


def _extraction_payload(extraction: EventLLMRawEventExtraction) -> dict[str, Any]:
    return {
        "schema_version": extraction.schema_version,
        "provider": extraction.provider,
        "model": extraction.model,
        "prompt_version": extraction.prompt_version,
        "confidence": extraction.confidence,
        "external_catalysts": [
            {
                "name": item.name,
                "catalyst_type": item.catalyst_type,
                "event_time": item.event_time,
                "event_time_confidence": item.event_time_confidence,
                "confidence": item.confidence,
            }
            for item in extraction.external_catalysts
        ],
        "crypto_asset_mentions": [
            {
                "name": item.name,
                "symbol": item.symbol,
                "coin_id": item.coin_id,
                "contract_address": item.contract_address,
                "mention_type": item.mention_type,
                "confidence": item.confidence,
            }
            for item in extraction.crypto_asset_mentions
        ],
        "false_positive_terms": [
            {"text": item.text, "reason": item.reason, "confidence": item.confidence}
            for item in extraction.false_positive_terms
        ],
        "event_date_hints": [
            {"text": item.text, "parsed_event_time": item.parsed_event_time, "confidence": item.confidence}
            for item in extraction.event_date_hints
        ],
        "suggested_followup_queries": list(extraction.suggested_followup_queries),
        "warnings": list(extraction.warnings),
    }


def _append_resolver_hints_to_payload(payload: dict[str, Any], hints: str) -> dict[str, Any]:
    """Append resolver hints to structured descriptions used by normalization."""
    out = dict(payload)
    event_payload = out.get("event")
    if isinstance(event_payload, Mapping):
        event_copy = dict(event_payload)
        event_copy["description"] = _append_hints_text(event_copy.get("description"), hints)
        out["event"] = event_copy
    else:
        out["description"] = _append_hints_text(out.get("description"), hints)
    return out


def _append_hints_text(value: object, hints: str) -> str:
    base = str(value or "").strip()
    suffix = f"LLM extracted research hints: {hints}"
    return f"{base}\n\n{suffix}".strip() if base else suffix


def _cache_key(
    packet: Mapping[str, Any],
    cfg: EventLLMExtractorConfig,
    provider_name: str,
    provider_model: object,
) -> str:
    payload = {
        "provider": provider_name,
        "model": provider_model,
        "prompt_version": cfg.prompt_version,
        "schema_version": LLM_EXTRACTION_SCHEMA_VERSION,
        "packet_hash": _packet_hash(packet),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _cache_entry(
    raw: Mapping[str, Any],
    packet: Mapping[str, Any],
    provider_name: str,
    provider_model: object,
    cfg: EventLLMExtractorConfig,
) -> dict[str, Any]:
    return {
        "schema_version": LLM_EXTRACTION_SCHEMA_VERSION,
        "provider": provider_name,
        "model": provider_model,
        "prompt_version": cfg.prompt_version,
        "packet_hash": _packet_hash(packet),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "raw": dict(raw),
    }


def _packet_hash(packet: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _load_cache(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM extraction cache could not be read: %s", exc)
        return {}


def _write_cache(path: Path | None, cache: Mapping[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, sort_keys=True, indent=2, default=str), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM extraction cache could not be written: %s", exc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _source_origin(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
