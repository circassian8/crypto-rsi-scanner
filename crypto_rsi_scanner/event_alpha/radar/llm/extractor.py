"""Research-only LLM extraction for raw event-discovery evidence."""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import crypto_rsi_scanner.event_alpha.radar.llm.budget as event_llm_budget
from .extraction_models import (
    ASSET_MENTION_TYPE_VALUES,
    CATALYST_TYPE_VALUES,
    EventLLMCryptoAssetMention,
    EventLLMEventDateHint,
    EventLLMExternalCatalystCandidate,
    EventLLMExtractionQuote,
    EventLLMFalsePositiveTerm,
    EventLLMRawEventExtraction,
)
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
from ..resolver import clean_text, strip_publisher_suffix
from ....llm_providers.base import (
    LLMExtractionProvider,
    LLMProviderResult,
    provider_batch_backoff_requested,
)

log = logging.getLogger(__name__)

LLM_EXTRACTION_SCHEMA_VERSION = "event_llm_extraction_v1"

_CATALYST_KEYWORDS = (
    "pre ipo",
    "pre-ipo",
    "ipo",
    "synthetic exposure",
    "tokenized stock",
    "stock token",
    "prediction market",
    "spacex",
    "openai",
    "anthropic",
    "world cup",
    "fan token",
    "election",
)
_DIRECT_EVENT_KEYWORDS = (
    "binance listing",
    "exchange listing",
    "listing",
    "perp listing",
    "futures listing",
    "unlock",
    "vesting",
    "airdrop",
    "tge",
    "exploit",
    "hack",
    "lawsuit",
    "sec ",
    "regulatory",
)
_MARKET_RECAP_PHRASES = (
    "market recap",
    "market roundup",
    "price recap",
    "weekly recap",
    "daily recap",
    "crypto prices today",
    "prices today",
)
_SOURCE_NOISE_PHRASES = (
    "bitcoin world",
    "kucoin source",
    "source highlights",
    "ripple effects",
    "ipo hype",
)


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
    max_calls_per_run: int = 0
    max_calls_per_day: int = 0
    max_estimated_cost_usd_per_day: float = 0.0
    max_parallel_calls: int = 1
    cache_ttl_hours: float = 0.0
    budget_ledger_path: Path | None = None
    estimated_cost_per_call_usd: float = 0.0
    deadline_at: datetime | None = None


@dataclass(frozen=True)
class EventLLMExtractionReportRow:
    raw_event: RawDiscoveredEvent
    extraction: EventLLMRawEventExtraction | None
    warnings: tuple[str, ...] = ()
    extraction_priority_score: int = 0
    extraction_priority_reasons: tuple[str, ...] = ()
    cache_status: str = "none"


@dataclass(frozen=True)
class RawEventExtractionPriority:
    score: int
    reason_codes: tuple[str, ...] = ()


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
    selected = _select_raw_events_for_extraction(raw_events, cfg.max_events_per_run)
    provider_name = str(getattr(provider, "name", cfg.provider))
    provider_model = getattr(provider, "model", cfg.model)
    calls_attempted = 0
    row_slots: list[EventLLMExtractionReportRow | None] = [None] * len(selected)
    pending: list[dict[str, Any]] = []
    budget = event_llm_budget.EventLLMBudgetRunTracker(
        cfg=event_llm_budget.EventLLMBudgetConfig(
            ledger_path=cfg.budget_ledger_path,
            estimated_cost_per_call_usd=cfg.estimated_cost_per_call_usd,
            max_calls_per_run=cfg.max_calls_per_run,
            max_calls_per_day=cfg.max_calls_per_day,
            max_estimated_cost_usd_per_day=cfg.max_estimated_cost_usd_per_day,
        ),
        provider=provider_name,
        model=str(provider_model or ""),
        prompt_version=cfg.prompt_version,
        call_kind="extractor",
    )
    for idx, (raw_event, priority) in enumerate(selected):
        packet = build_raw_event_packet(raw_event, prompt_version=cfg.prompt_version)
        warnings: list[str] = []
        cache_key = _cache_key(packet, cfg, provider_name, provider_model)
        cached = cache.get(cache_key)
        cache_status = "miss"
        if isinstance(cached, Mapping) and isinstance(cached.get("raw"), Mapping) and _cache_entry_fresh(cached, cfg):
            raw = dict(cached["raw"])
            cache_status = "hit"
            budget.record_cache_hit()
            row_slots[idx] = _extraction_report_row(
                raw_event=raw_event,
                priority=priority,
                raw=raw,
                packet=packet,
                warnings=warnings,
                cache_status=cache_status,
                provider_name=provider_name,
                provider_model=provider_model,
                cfg=cfg,
            )
        elif isinstance(cached, Mapping):
            budget.record_cache_miss()
            warnings.append(
                "LLM extraction cache entry ignored: old cache format"
                if not isinstance(cached.get("raw"), Mapping)
                else "LLM extraction cache entry expired"
            )
            pending.append({
                "idx": idx,
                "raw_event": raw_event,
                "priority": priority,
                "packet": packet,
                "cache_key": cache_key,
                "warnings": warnings,
            })
        else:
            budget.record_cache_miss()
            pending.append({
                "idx": idx,
                "raw_event": raw_event,
                "priority": priority,
                "packet": packet,
                "cache_key": cache_key,
                "warnings": warnings,
            })
    for job, provider_result, cache_status in _run_extraction_provider_jobs(
        pending,
        provider,
        cfg=cfg,
        budget=budget,
        calls_attempted_ref={"value": calls_attempted},
    ):
        raw = provider_result.raw
        warnings = list(job["warnings"])
        if provider_result.warning:
            warnings.append(provider_result.warning)
        if raw is not None and cfg.cache_path is not None:
            cache[job["cache_key"]] = _cache_entry(raw, job["packet"], provider_name, provider_model, cfg)
            cache_changed = True
        row_slots[job["idx"]] = _extraction_report_row(
            raw_event=job["raw_event"],
            priority=job["priority"],
            raw=raw,
            packet=job["packet"],
            warnings=warnings,
            cache_status=cache_status,
            provider_name=provider_name,
            provider_model=provider_model,
            cfg=cfg,
        )
    rows = [row for row in row_slots if row is not None]
    if cache_changed:
        _write_cache(cfg.cache_path, cache)
    budget_snapshot = budget.flush()
    if budget_snapshot.warning and rows:
        last = rows[-1]
        rows[-1] = EventLLMExtractionReportRow(
            raw_event=last.raw_event,
            extraction=last.extraction,
            warnings=tuple(dict.fromkeys((*last.warnings, budget_snapshot.warning))),
            extraction_priority_score=last.extraction_priority_score,
            extraction_priority_reasons=last.extraction_priority_reasons,
            cache_status=last.cache_status,
        )
    return rows


def _run_extraction_provider_jobs(
    jobs: list[dict[str, Any]],
    provider: LLMExtractionProvider,
    *,
    cfg: EventLLMExtractorConfig,
    budget: event_llm_budget.EventLLMBudgetRunTracker,
    calls_attempted_ref: dict[str, int],
) -> list[tuple[dict[str, Any], LLMProviderResult, str]]:
    """Run uncached extraction calls with bounded parallelism and ordered bookkeeping."""
    if not jobs:
        return []
    max_workers = max(1, int(cfg.max_parallel_calls or 1))
    results: list[tuple[dict[str, Any], LLMProviderResult, str]] = []
    next_idx = 0
    provider_backoff_warning: str | None = None

    def skip_job(job: dict[str, Any], cache_status: str, warning: str) -> None:
        if cache_status == "skipped_provider_backoff":
            budget.record_provider_backoff()
        else:
            budget.record_skipped()
        results.append((job, LLMProviderResult(warning=warning), cache_status))

    def next_submit_job() -> dict[str, Any] | None:
        nonlocal next_idx
        while next_idx < len(jobs):
            job = jobs[next_idx]
            next_idx += 1
            if provider_backoff_warning:
                skip_job(job, "skipped_provider_backoff", provider_backoff_warning)
                continue
            if _budget_exhausted(calls_attempted_ref["value"], cfg) or not budget.can_attempt():
                skip_job(job, "skipped_budget", budget.exhausted_warning())
                continue
            if _deadline_exhausted(cfg.deadline_at):
                skip_job(job, "skipped_runtime", _deadline_warning())
                continue
            calls_attempted_ref["value"] += 1
            budget.record_attempt()
            return job
        return None

    if max_workers <= 1:
        while True:
            job = next_submit_job()
            if job is None:
                break
            provider_result = _extract_raw_event(provider, job["packet"])
            budget.record_result(success=provider_result.raw is not None)
            results.append((job, provider_result, "miss"))
            if provider_batch_backoff_requested(provider_result):
                provider_backoff_warning = _provider_backoff_warning(provider_result)
        return results

    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as executor:
        futures = {}

        def fill_capacity() -> None:
            while len(futures) < max_workers:
                job = next_submit_job()
                if job is None:
                    break
                futures[executor.submit(_extract_raw_event, provider, job["packet"])] = job

        fill_capacity()
        while futures:
            for future in as_completed(list(futures)):
                job = futures.pop(future)
                try:
                    provider_result = future.result()
                except Exception as exc:  # noqa: BLE001 - providers should fail soft, but keep batch robust
                    log.warning("LLM extraction provider job failed: %s", exc)
                    provider_result = LLMProviderResult(warning=f"LLM extraction provider failed: {type(exc).__name__}")
                budget.record_result(success=provider_result.raw is not None)
                results.append((job, provider_result, "miss"))
                if provider_batch_backoff_requested(provider_result):
                    provider_backoff_warning = _provider_backoff_warning(provider_result)
                fill_capacity()
                break
    return results


def _provider_backoff_warning(result: LLMProviderResult) -> str:
    reason = result.error_class or "provider_failure"
    return f"LLM skipped: provider backoff active after {reason}"


def _extract_raw_event(provider: LLMExtractionProvider, packet: Mapping[str, Any]) -> LLMProviderResult:
    return provider.extract_raw_event(packet)


def _extraction_report_row(
    *,
    raw_event: RawDiscoveredEvent,
    priority: RawEventExtractionPriority,
    raw: Mapping[str, Any] | None,
    packet: Mapping[str, Any],
    warnings: Iterable[str],
    cache_status: str,
    provider_name: str,
    provider_model: object,
    cfg: EventLLMExtractorConfig,
) -> EventLLMExtractionReportRow:
    warning_list = list(warnings)
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
            warning_list.extend(extraction.warnings)
        except EventLLMExtractionValidationError as exc:
            warning_list.append(str(exc))
    return EventLLMExtractionReportRow(
        raw_event=raw_event,
        extraction=extraction,
        warnings=tuple(dict.fromkeys(warning_list)),
        extraction_priority_score=priority.score,
        extraction_priority_reasons=priority.reason_codes,
        cache_status=cache_status,
    )


def build_raw_event_packet(raw_event: RawDiscoveredEvent, *, prompt_version: str = "llm_raw_event_extraction_v1") -> dict[str, Any]:
    payload = raw_event.raw_json or {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    enrichment_payload = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    body = str(event_source_enrichment.enriched_text_for_llm(raw_event) or raw_event.body or "")
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
        "body": body,
        "source_enrichment": event_source_enrichment.source_enrichment_metadata(raw_event),
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


def score_raw_event_for_llm_extraction(
    raw_event: RawDiscoveredEvent,
    now: datetime | None = None,
) -> RawEventExtractionPriority:
    """Prioritize raw evidence before spending an LLM extraction budget."""
    observed = _as_utc(now or raw_event.fetched_at or datetime.now(timezone.utc))
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    text = clean_text(
        " ".join(str(item or "") for item in (
            raw_event.title,
            raw_event.body,
            event_payload.get("event_name"),
            event_payload.get("event_type"),
            event_payload.get("external_asset"),
            event_payload.get("description"),
        ))
    )
    score = 0.0
    reasons: list[str] = []

    source_conf = max(0.0, min(1.0, float(raw_event.source_confidence or 0.0)))
    if source_conf:
        source_points = source_conf * 25
        score += source_points
        reasons.append(f"source_confidence_{int(round(source_conf * 100))}")

    anomaly_score = _float_from_mapping(anomaly, "score")
    if raw_event.provider == "market_anomaly" or anomaly_score is not None:
        anomaly_points = min(35.0, max(0.0, float(anomaly_score or 0.0)) * 0.35)
        if anomaly_points:
            score += anomaly_points
            reasons.append(f"market_anomaly_{int(round(float(anomaly_score or 0.0)))}")

    published = raw_event.published_at or raw_event.fetched_at
    if published is not None:
        age_hours = max(0.0, (observed - _as_utc(published)).total_seconds() / 3600.0)
        if age_hours <= 24:
            score += 15
            reasons.append("fresh_24h")
        elif age_hours <= 72:
            score += 8
            reasons.append("fresh_72h")

    catalyst_hits = _keyword_hits(text, _CATALYST_KEYWORDS)
    if catalyst_hits:
        score += min(25, 8 + 4 * len(catalyst_hits))
        reasons.append("catalyst_keywords:" + ",".join(catalyst_hits[:4]))

    direct_hits = _keyword_hits(text, _DIRECT_EVENT_KEYWORDS)
    if direct_hits:
        score += min(14, 5 + 3 * len(direct_hits))
        reasons.append("direct_event_keywords:" + ",".join(direct_hits[:3]))

    symbol = _structured_symbol(payload, market)
    if symbol and (f"${symbol.lower()}" in text or symbol.lower() in text):
        score += 10
        reasons.append("structured_asset_mention")
    elif symbol:
        score += 5
        reasons.append("structured_asset_context")
    if _has_structured_asset_hint(payload):
        score += 8
        reasons.append("asset_hint")

    if _looks_like_market_recap(text):
        score -= 22
        reasons.append("market_recap_penalty")
    if _looks_like_source_noise(raw_event, text):
        score -= 28
        reasons.append("source_noise_penalty")
    if "no dated external catalyst" in text:
        score -= 8
        reasons.append("no_catalyst_disclaimer")

    return RawEventExtractionPriority(
        score=max(0, min(100, int(round(score)))),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _select_raw_events_for_extraction(
    raw_events: Iterable[RawDiscoveredEvent],
    limit: int,
) -> list[tuple[RawDiscoveredEvent, RawEventExtractionPriority]]:
    events = list(raw_events)
    if limit <= 0 or not events:
        return []
    observed = _selection_clock(events)
    seen_hashes: set[str] = set()
    scored: list[tuple[int, int, RawDiscoveredEvent, RawEventExtractionPriority]] = []
    for idx, raw in enumerate(events):
        priority = score_raw_event_for_llm_extraction(raw, now=observed)
        reasons = list(priority.reason_codes)
        score = priority.score
        duplicate_key = raw.content_hash or _raw_text_hash(raw)
        if duplicate_key in seen_hashes:
            score = max(0, score - 20)
            reasons.append("duplicate_content_penalty")
        else:
            seen_hashes.add(duplicate_key)
        adjusted = RawEventExtractionPriority(score=score, reason_codes=tuple(dict.fromkeys(reasons)))
        scored.append((adjusted.score, -idx, raw, adjusted))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(raw, priority) for _, _, raw, priority in scored[:limit]]


def _selection_clock(raw_events: Iterable[RawDiscoveredEvent]) -> datetime:
    timestamps = [raw.fetched_at for raw in raw_events if raw.fetched_at is not None]
    if not timestamps:
        return datetime.now(timezone.utc)
    return max(_as_utc(ts) for ts in timestamps)


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    hits = [keyword.strip() for keyword in keywords if keyword.strip() and keyword.strip() in text]
    return tuple(dict.fromkeys(hits))


def _float_from_mapping(payload: Mapping[str, Any], key: str) -> float | None:
    try:
        value = payload.get(key)
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _structured_symbol(payload: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    asset = payload.get("asset") if isinstance(payload.get("asset"), Mapping) else {}
    candidates = (
        market.get("symbol"),
        asset.get("symbol"),
        payload.get("symbol"),
    )
    for value in candidates:
        symbol = str(value or "").strip().lower()
        if symbol:
            return symbol
    return ""


def _has_structured_asset_hint(payload: Mapping[str, Any]) -> bool:
    asset = payload.get("asset") if isinstance(payload.get("asset"), Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    return bool(
        asset.get("coin_id")
        or asset.get("contract_address")
        or market.get("coin_id")
        or market.get("symbol")
        or payload.get("coin_id")
    )


def _looks_like_market_recap(text: str) -> bool:
    return any(phrase in text for phrase in _MARKET_RECAP_PHRASES)


def _looks_like_source_noise(raw_event: RawDiscoveredEvent, text: str) -> bool:
    clean_title = clean_text(raw_event.title)
    if any(phrase in clean_title for phrase in _SOURCE_NOISE_PHRASES):
        return True
    if "bitcoin world" in text and "bitcoin" not in clean_text(strip_publisher_suffix(raw_event.title)):
        return True
    return False


def _raw_text_hash(raw_event: RawDiscoveredEvent) -> str:
    return hashlib.sha256(
        "\n".join(str(part or "") for part in (raw_event.title, raw_event.body, raw_event.source_url)).encode("utf-8")
    ).hexdigest()


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
        out.append(
            f"  priority: {row.extraction_priority_score}/100"
            + (f" ({', '.join(row.extraction_priority_reasons)})" if row.extraction_priority_reasons else "")
        )
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
        if row.cache_status != "none":
            out.append(f"  cache: {row.cache_status}")
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


def _budget_exhausted(calls_attempted: int, cfg: EventLLMExtractorConfig) -> bool:
    caps = [cap for cap in (cfg.max_calls_per_run, cfg.max_calls_per_day) if cap and cap > 0]
    if not caps:
        return False
    return calls_attempted >= min(caps)


def _deadline_exhausted(deadline_at: datetime | None) -> bool:
    if deadline_at is None:
        return False
    deadline = _as_utc(deadline_at)
    return datetime.now(timezone.utc) >= deadline


def _deadline_warning() -> str:
    return "LLM extraction skipped: notification runtime deadline exhausted"


def _cache_entry_fresh(cached: Mapping[str, Any], cfg: EventLLMExtractorConfig) -> bool:
    ttl = float(cfg.cache_ttl_hours or 0.0)
    if ttl <= 0:
        return True
    analyzed_at = cached.get("analyzed_at")
    if not analyzed_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(analyzed_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0
    return age_hours <= ttl


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


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _source_origin(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
