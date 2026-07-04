"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (executor)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse
from .... import event_identity
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_providers.cryptopanic import CryptoPanicProvider, normalize_cryptopanic_currency_code
from ....event_providers.gdelt import GdeltProvider
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ....event_resolver import clean_text
from .models import *  # noqa: F403

def run_catalyst_search(
    raw_events: Iterable[RawDiscoveredEvent],
    provider: CatalystSearchProvider,
    *,
    cfg: EventCatalystSearchConfig | None = None,
    now: datetime | None = None,
) -> CatalystSearchRunResult:
    """Search for source evidence around market anomalies and attach results."""
    cfg = cfg or EventCatalystSearchConfig()
    if not cfg.enabled:
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            skip_reasons={"profile_disabled": 1},
        )
    observed = _as_utc(now or datetime.now(timezone.utc))
    raw_event_rows = tuple(raw_events)
    all_anomalies = _market_anomaly_events(raw_event_rows)
    anomalies = _eligible_anomalies(raw_event_rows, cfg)
    queries = _queries_for_anomalies(anomalies, cfg)
    skip_reasons = _catalyst_search_skip_reasons(all_anomalies, anomalies, queries, cfg)
    anomaly_by_id = {raw.raw_id: raw for raw in anomalies}
    warnings: list[str] = []
    try:
        provider_result = provider.search(
            queries,
            max_results_per_query=cfg.max_results_per_query,
            now=observed,
        )
        warnings.extend(provider_result.warnings)
        provider_events = provider_result.result_events
        provider_rejected = list(provider_result.rejected_result_events)
        skip_reasons = _merge_reason_counts(
            skip_reasons,
            getattr(provider_result, "skip_reasons", {}) or {},
            _skip_reasons_from_warnings(provider_result.warnings),
        )
    except Exception as exc:  # noqa: BLE001
        provider_reason = "provider_backoff" if "backoff" in str(exc).casefold() else "provider_unavailable"
        return CatalystSearchRunResult(
            provider=getattr(provider, "name", cfg.provider),
            queries=queries,
            warnings=(f"catalyst search provider failed: {exc}",),
            query_count=len(queries),
            skip_reasons=_merge_reason_counts(skip_reasons, {provider_reason: 1}),
        )
    accepted_results: list[SearchResultEvent] = []
    rejected_results: list[SearchResultEvent] = list(provider_rejected)
    seen_content: set[str] = set()
    threshold = _confidence_threshold(cfg.min_result_confidence)
    for result in provider_events:
        anomaly = anomaly_by_id.get(result.query.anomaly_raw_id)
        score = score_search_result(result.raw_event, result.query, anomaly, now=observed)
        reasons = list(score.reason_codes)
        content_key = result.raw_event.content_hash or _content_hash(result.raw_event.raw_json or {})
        if content_key in seen_content:
            score = CatalystSearchScore(max(0, score.score - 25), (*score.reason_codes, "duplicate_content_penalty"))
            reasons = list(score.reason_codes)
        else:
            seen_content.add(content_key)
        if cfg.require_live_source and _is_fixture_source(result.raw_event, provider_name=getattr(provider, "name", "")):
            reasons.append("fixture_source_rejected")
            rejected_results.append(replace(
                result,
                result_score=score.score,
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        scored = replace(
            result,
            raw_event=_annotate_scored_result(result.raw_event, score.score, reasons),
            result_score=score.score,
            result_score_reasons=tuple(dict.fromkeys(reasons)),
            accepted=score.score >= threshold,
        )
        if scored.accepted:
            accepted_results.append(scored)
        else:
            rejected_results.append(scored)
    grouped: dict[str, list[RawDiscoveredEvent]] = {}
    for result in accepted_results:
        grouped.setdefault(result.query.anomaly_raw_id, []).append(result.raw_event)
    attached: list[RawDiscoveredEvent] = []
    for anomaly in anomalies:
        attached.extend(attach_search_results_to_anomaly(anomaly, grouped.get(anomaly.raw_id, ())))
    return CatalystSearchRunResult(
        provider=getattr(provider, "name", cfg.provider),
        queries=queries,
        result_events=tuple(accepted_results),
        rejected_result_events=tuple(rejected_results),
        attached_raw_events=tuple(attached),
        warnings=tuple(dict.fromkeys(warnings)),
        provider_fetch_count=provider_result.provider_fetch_count,
        provider_cache_hits=provider_result.provider_cache_hits,
        provider_cache_misses=provider_result.provider_cache_misses,
        query_count=len(queries),
        result_count=len(accepted_results),
        rejected_count=len(rejected_results),
        skip_reasons=skip_reasons,
    )
def run_hypothesis_search(
    hypotheses: Iterable[object],
    provider: CatalystSearchProvider,
    *,
    cfg: EventImpactHypothesisSearchConfig | None = None,
    now: datetime | None = None,
) -> CatalystSearchRunResult:
    """Search for asset-validation evidence around impact hypotheses.

    This is separate from market-anomaly catalyst search: accepted rows are
    source evidence for validating sector/venue/infrastructure hypotheses, not
    attachments to market anomaly parents.
    """
    cfg = cfg or EventImpactHypothesisSearchConfig()
    provider_name = getattr(provider, "name", "hypothesis_search")
    if not cfg.enabled:
        return CatalystSearchRunResult(provider=provider_name, skip_reasons={"profile_disabled": 1})
    observed = _as_utc(now or datetime.now(timezone.utc))
    eligible = _eligible_hypotheses(hypotheses, cfg)
    queries = _queries_for_hypotheses(eligible, cfg)
    hypothesis_by_id = {str(getattr(item, "hypothesis_id", "") or ""): item for item in tuple(hypotheses)}
    skip_reasons = _hypothesis_search_skip_reasons(tuple(hypotheses), eligible, queries, cfg)
    warnings: list[str] = []
    try:
        provider_result = provider.search(
            queries,
            max_results_per_query=cfg.max_results_per_query,
            now=observed,
        )
        warnings.extend(provider_result.warnings)
        provider_events = provider_result.result_events
        provider_rejected = list(provider_result.rejected_result_events)
        skip_reasons = _merge_reason_counts(
            skip_reasons,
            getattr(provider_result, "skip_reasons", {}) or {},
            _skip_reasons_from_warnings(provider_result.warnings),
        )
    except Exception as exc:  # noqa: BLE001 - research providers must fail soft.
        provider_reason = "provider_backoff" if "backoff" in str(exc).casefold() else "provider_unavailable"
        return CatalystSearchRunResult(
            provider=provider_name,
            queries=queries,
            warnings=(f"hypothesis search provider failed: {exc}",),
            query_count=len(queries),
            skip_reasons=_merge_reason_counts(skip_reasons, {provider_reason: 1}),
        )

    accepted_results: list[SearchResultEvent] = []
    rejected_results: list[SearchResultEvent] = list(provider_rejected)
    result_skip_reasons: dict[str, int] = {}
    threshold = _confidence_threshold(cfg.min_result_confidence)
    seen_content: set[str] = set()
    for result in provider_events:
        score = score_search_result(result.raw_event, result.query, None, now=observed)
        reasons = list(score.reason_codes)
        content_key = result.raw_event.content_hash or _content_hash(result.raw_event.raw_json or {})
        if content_key in seen_content:
            score = CatalystSearchScore(max(0, score.score - 25), (*score.reason_codes, "duplicate_content_penalty"))
            reasons = list(score.reason_codes)
        else:
            seen_content.add(content_key)
        hypothesis = hypothesis_by_id.get(result.query.anomaly_raw_id)
        query_type = str(getattr(result.query, "query_type", "") or "candidate_validation")
        catalyst_ok = _result_mentions_hypothesis_catalyst(result.raw_event, hypothesis)
        if not catalyst_ok:
            reasons.append("result_catalyst_missing")
            result_skip_reasons["result_catalyst_missing"] = result_skip_reasons.get("result_catalyst_missing", 0) + 1
            rejected_results.append(replace(
                result,
                result_score=min(score.score, 45),
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        identity_ok = result_mentions_anomaly_identity(result.raw_event, result.query, None)
        if query_type == "candidate_discovery":
            asset_ok = _candidate_discovery_asset_present(result.raw_event)
            if not asset_ok:
                reasons.append("candidate_discovery_asset_missing")
                result_skip_reasons["candidate_discovery_asset_missing"] = result_skip_reasons.get("candidate_discovery_asset_missing", 0) + 1
                rejected_results.append(replace(
                    result,
                    result_score=min(score.score, 45),
                    result_score_reasons=tuple(dict.fromkeys(reasons)),
                    accepted=False,
                ))
                continue
        elif cfg.require_validated_identity and not identity_ok:
            reasons.append("result_identity_rejected")
            result_skip_reasons["result_identity_rejected"] = result_skip_reasons.get("result_identity_rejected", 0) + 1
            rejected_results.append(replace(
                result,
                result_score=min(score.score, 45),
                result_score_reasons=tuple(dict.fromkeys(reasons)),
                accepted=False,
            ))
            continue
        scored = replace(
            result,
            raw_event=_annotate_hypothesis_search_result(result.raw_event, score.score, reasons, result.query),
            result_score=score.score,
            result_score_reasons=tuple(dict.fromkeys(reasons)),
            accepted=score.score >= threshold,
        )
        if scored.accepted:
            accepted_results.append(scored)
        else:
            result_skip_reasons["result_score_below_threshold"] = result_skip_reasons.get("result_score_below_threshold", 0) + 1
            rejected_results.append(scored)
    return CatalystSearchRunResult(
        provider=provider_name,
        queries=queries,
        result_events=tuple(accepted_results),
        rejected_result_events=tuple(rejected_results),
        warnings=tuple(dict.fromkeys(warnings)),
        provider_fetch_count=provider_result.provider_fetch_count,
        provider_cache_hits=provider_result.provider_cache_hits,
        provider_cache_misses=provider_result.provider_cache_misses,
        query_count=len(queries),
        result_count=len(accepted_results),
        rejected_count=len(rejected_results),
        skip_reasons=_merge_reason_counts(skip_reasons, result_skip_reasons),
    )
def attach_search_results_to_anomaly(
    raw_event: RawDiscoveredEvent,
    result_events: Iterable[RawDiscoveredEvent],
) -> tuple[RawDiscoveredEvent, ...]:
    """Attach manually supplied source events to an anomaly with provenance.

    The returned rows are still raw event evidence. They must pass normal
    normalization, asset resolution, classification, and playbook tiering before
    they can become research alerts.
    """
    queries = generate_search_queries_for_anomaly(raw_event)
    annotated_parent = _annotate_raw_event(
        raw_event,
        {
            "market_anomaly_catalyst_search": {
                "role": "parent_anomaly",
                "queries": list(queries),
                "research_only": True,
                "live_fetch": False,
            }
        },
    )
    parent_ref = {
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "title": raw_event.title,
        "symbol": _event_symbol(raw_event),
    }
    attached = [
        _annotate_raw_event(
            event,
            {
                "market_anomaly_catalyst_search": {
                    "role": "attached_source_evidence",
                    "parent": parent_ref,
                    "queries": list(queries),
                    "research_only": True,
                    "live_fetch": False,
                }
            },
        )
        for event in result_events
    ]
    return (annotated_parent, *attached)
