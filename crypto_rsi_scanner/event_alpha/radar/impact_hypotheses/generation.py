"""Impact-hypothesis generation and validation orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
from ..llm.extractor import EventLLMExtractionReportRow
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from ..resolver import clean_text
from .. import incidents as event_incident_store
from .. import market_confirmation as event_market_confirmation
from .. import opportunity_verdict as event_opportunity_verdict
from .models import (
    EventImpactHypothesis,
    HypothesisScope,
    HypothesisStatus,
    ImpactCategory,
    ImpactPathReason,
    ValidationStage,
)



def generate_impact_hypotheses(
    result: EventDiscoveryResult,
    *,
    raw_events: Iterable[RawDiscoveredEvent] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    extraction_rows: Iterable[EventLLMExtractionReportRow] = (),
    taxonomy: Mapping[str, Mapping[str, Any]] | None = None,
    taxonomy_path: str | Path | None = None,
    now: datetime | None = None,
) -> tuple[EventImpactHypothesis, ...]:
    """Generate deterministic research-only impact hypotheses."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    raw_by_id = {raw.raw_id: raw for raw in (*result.raw_events, *tuple(raw_events))}
    incidents = event_incident_graph.build_incidents(result.normalized_events, raw_by_id)
    incidents_by_event = {
        event_id: incident
        for incident in incidents
        for event_id in incident.event_ids
    }
    clusters_by_event = {
        event_id: cluster
        for cluster in (tuple(clusters) or event_graph.build_event_clusters(result))
        for event_id in cluster.event_ids
    }
    extractions_by_raw = {
        row.raw_event.raw_id: row
        for row in extraction_rows
        if getattr(row, "raw_event", None) is not None
    }
    suggested_assets_by_event = _suggested_assets_by_event(result.normalized_events, raw_by_id, extractions_by_raw)
    validated_assets_by_event = _validated_assets_by_event(result)
    sector_taxonomy = dict(load_impact_taxonomy(taxonomy_path) if taxonomy is None else taxonomy)
    out: list[EventImpactHypothesis] = []

    for event in result.normalized_events:
        raws = tuple(raw_by_id[raw_id] for raw_id in event.raw_ids if raw_id in raw_by_id)
        text = _event_text(event, raws, extractions_by_raw)
        incident = incidents_by_event.get(event.event_id)
        matches = _matched_rules(text, event, raws=raws)
        if not matches and _is_market_anomaly(raws):
            matches = (_market_anomaly_rule(),)
        for rule in matches:
            out.append(_hypothesis_from_rule(
                event,
                raws,
                rule,
                cluster=clusters_by_event.get(event.event_id),
                incident=incident,
                taxonomy=sector_taxonomy,
                text=text,
                now=observed,
                suggested_assets=suggested_assets_by_event.get(event.event_id, ()),
                validated_assets=validated_assets_by_event.get(event.event_id, ()),
            ))

    raw_event_ids = {event.event_id for event in result.normalized_events}
    for raw in raw_by_id.values():
        raw_event_id = _event_id_from_raw(raw)
        if raw_event_id in raw_event_ids:
            continue
        if not _is_market_anomaly((raw,)):
            continue
        event = _normalized_from_market_anomaly(raw, observed)
        out.append(_hypothesis_from_rule(
            event,
            (raw,),
            _market_anomaly_rule(),
            cluster=None,
            taxonomy=sector_taxonomy,
            text=_raw_text(raw),
            now=observed,
            suggested_assets=(),
            validated_assets=(),
        ))

    return tuple(_dedupe_hypotheses(out))


@dataclass(frozen=True)
class _HypothesisValidationMatches:
    reasons: list[str]
    rejections: list[str]
    matched_symbols: list[str]
    matched_coin_ids: list[str]
    best_stage: str
    impact_path_reason: str | None
    impact_validation: event_impact_path_validator.ImpactPathValidation | None
    impact_context: tuple[RawDiscoveredEvent, str | None, str | None] | None


def _collect_hypothesis_validation_matches(
    hypothesis: EventImpactHypothesis,
    rows: tuple[RawDiscoveredEvent, ...],
) -> _HypothesisValidationMatches:
    reasons: list[str] = []
    rejections: list[str] = []
    matched_symbols: list[str] = []
    matched_coin_ids: list[str] = []
    best_stage = hypothesis.validation_stage
    impact_path_reason: str | None = hypothesis.impact_path_reason
    impact_validation: event_impact_path_validator.ImpactPathValidation | None = None
    impact_context: tuple[RawDiscoveredEvent, str | None, str | None] | None = None
    for raw in rows:
        detail = _validation_detail(raw, hypothesis)
        status = str(detail.get("status") or "none")
        reason = str(detail.get("reason") or "")
        symbol = str(detail.get("symbol") or "") or None
        coin_id = str(detail.get("coin_id") or "") or None
        stage = str(detail.get("validation_stage") or "")
        if stage:
            best_stage = _max_validation_stage(best_stage, stage)
        if status == "accepted" and reason:
            reasons.append(reason)
            if symbol:
                matched_symbols.append(symbol)
            matched_coin_ids.append(coin_id or "")
            path_validation = event_impact_path_validator.validate_impact_path(
                raw,
                hypothesis,
                symbol=symbol,
                coin_id=coin_id,
                score_components=hypothesis.score_components,
            )
            path_reason = path_validation.impact_path_reason
            preferred = _prefer_impact_validation(impact_validation, path_validation)
            if preferred is path_validation:
                impact_context = (raw, symbol, coin_id)
            impact_validation = preferred
            if path_reason:
                impact_path_reason = _prefer_impact_path_reason(impact_path_reason, path_reason)
                if path_validation.required_evidence_met:
                    best_stage = _max_validation_stage(best_stage, ValidationStage.IMPACT_PATH_VALIDATED.value)
        elif reason:
            rejections.append(reason)
    return _HypothesisValidationMatches(
        reasons=reasons,
        rejections=rejections,
        matched_symbols=matched_symbols,
        matched_coin_ids=matched_coin_ids,
        best_stage=best_stage,
        impact_path_reason=impact_path_reason,
        impact_validation=impact_validation,
        impact_context=impact_context,
    )


def validate_hypotheses_with_raw_events(
    hypotheses: Iterable[EventImpactHypothesis],
    raw_events: Iterable[RawDiscoveredEvent],
) -> tuple[EventImpactHypothesis, ...]:
    """Mark hypotheses that have explicit asset+catalyst validation evidence."""
    rows = tuple(raw_events)
    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        matches = _collect_hypothesis_validation_matches(hypothesis, rows)
        reasons = matches.reasons
        rejections = matches.rejections
        matched_symbols = matches.matched_symbols
        matched_coin_ids = matches.matched_coin_ids
        best_stage = matches.best_stage
        impact_path_reason = matches.impact_path_reason
        impact_validation = matches.impact_validation
        impact_context = matches.impact_context
        if reasons and best_stage in _PROMOTABLE_VALIDATION_STAGES:
            if (
                _market_confirmation_score(rows) >= 70
                and best_stage in {
                    ValidationStage.IMPACT_PATH_VALIDATED.value,
                    ValidationStage.MARKET_CONFIRMED.value,
                    ValidationStage.PROMOTED_TO_RADAR.value,
                }
            ):
                best_stage = ValidationStage.MARKET_CONFIRMED.value
            merged_assets = tuple(
                {
                    "source": "hypothesis_search",
                    "symbol": symbol,
                    "coin_id": coin_id,
                    "reason": reason,
                    "validated": True,
                    "role_source": event_identity.ROLE_SOURCE_RESOLVER_EXACT,
                    "identity_confidence": 95.0,
                    "identity_evidence": (reason,),
                }
                for reason, symbol, coin_id in zip(reasons, matched_symbols, matched_coin_ids)
            )
            crypto_assets = _merge_asset_rows(hypothesis.crypto_candidate_assets, hypothesis.validated_candidate_assets, merged_assets)
            symbols, coin_ids = _assets_from_asset_rows(crypto_assets)
            components = dict(hypothesis.score_components or {})
            components.update(_asset_knowledge_components(merged_assets[0] if merged_assets else (crypto_assets[0] if crypto_assets else None)))
            components["validation_strength"] = 95.0
            if impact_path_reason:
                components["impact_path_strength"] = 85.0 if _impact_path_reason_is_strong(impact_path_reason) else 35.0
            quality_kwargs = {}
            if impact_validation is not None:
                components.update(_impact_validation_score_components(impact_validation))
                components.update(_impact_validation_metadata_components(impact_validation))
                impact_validation = _refresh_impact_validation_score(impact_validation, components)
                components.update(_impact_validation_score_components(impact_validation))
                components.update(_impact_validation_metadata_components(impact_validation))
                quality_kwargs = _quality_verdict_replace_kwargs(
                    impact_validation,
                    impact_context=impact_context,
                    hypothesis=hypothesis,
                    components=components,
                )
                components.update(_quality_score_components(quality_kwargs))
            if best_stage == ValidationStage.MARKET_CONFIRMED.value:
                components["market_confirmation"] = max(float(components.get("market_confirmation") or 0.0), 70.0)
            score = _weighted_hypothesis_score(components, hypothesis.impact_category)
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.VALIDATED.value,
                validation_stage=best_stage,
                hypothesis_scope=HypothesisScope.TOKEN.value,
                candidate_symbols=symbols or tuple(dict.fromkeys(matched_symbols)) or hypothesis.candidate_symbols,
                candidate_coin_ids=coin_ids or tuple(value for value in dict.fromkeys(matched_coin_ids) if value) or hypothesis.candidate_coin_ids,
                validated_candidate_assets=_merge_asset_rows(hypothesis.validated_candidate_assets, merged_assets),
                crypto_candidate_assets=crypto_assets,
                hypothesis_score=round(score, 2),
                confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
                score_components=components,
                validation_reasons=tuple(dict.fromkeys((*hypothesis.validation_reasons, *reasons))),
                impact_path_reason=impact_path_reason,
                **_impact_validation_replace_kwargs(impact_validation),
                **quality_kwargs,
            ))
        elif reasons:
            components = dict(hypothesis.score_components or {})
            quality_kwargs = {}
            components["validation_strength"] = max(float(components.get("validation_strength") or 0.0), 45.0)
            if impact_path_reason:
                components["impact_path_strength"] = 85.0 if _impact_path_reason_is_strong(impact_path_reason) else 35.0
            if impact_validation is not None:
                components.update(_impact_validation_score_components(impact_validation))
                impact_validation = _refresh_impact_validation_score(impact_validation, components)
                components.update(_impact_validation_score_components(impact_validation))
                quality_kwargs = _quality_verdict_replace_kwargs(
                    impact_validation,
                    impact_context=impact_context,
                    hypothesis=hypothesis,
                    components=components,
                )
                components.update(_quality_score_components(quality_kwargs))
            score = _weighted_hypothesis_score(components, hypothesis.impact_category)
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.VALIDATION_EVIDENCE_FOUND.value,
                validation_stage=best_stage,
                hypothesis_score=round(score, 2),
                confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
                score_components=components,
                validation_reasons=tuple(dict.fromkeys((*hypothesis.validation_reasons, *reasons))),
                impact_path_reason=impact_path_reason,
                **_impact_validation_replace_kwargs(impact_validation),
                **quality_kwargs,
            ))
        elif rejections:
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.REJECTED.value,
                validation_stage=ValidationStage.REJECTED.value,
                rejection_reasons=tuple(dict.fromkeys((*hypothesis.rejection_reasons, *rejections))),
            ))
        else:
            out.append(hypothesis)
    return tuple(_with_promotion_diagnostics(item) for item in out)


def attach_hypothesis_search_samples(
    hypotheses: Iterable[EventImpactHypothesis],
    search_result: object,
    *,
    max_samples_per_hypothesis: int = 5,
) -> tuple[EventImpactHypothesis, ...]:
    """Attach capped accepted/rejected validation-search evidence samples."""
    samples_by_id: dict[str, list[dict[str, Any]]] = {}
    for attr in ("rejected_result_events",):
        for result in getattr(search_result, attr, ()) or ():
            query = getattr(result, "query", None)
            raw = getattr(result, "raw_event", None)
            if query is None or raw is None:
                continue
            hypothesis_id = str(getattr(query, "anomaly_raw_id", "") or "")
            if not hypothesis_id:
                continue
            reasons = tuple(str(value) for value in getattr(result, "result_score_reasons", ()) or ())
            sample = {
                "accepted": bool(getattr(result, "accepted", False)),
                "query": str(getattr(query, "query", "") or ""),
                "query_type": str(getattr(query, "query_type", "") or "candidate_validation"),
                "result_title": str(getattr(raw, "title", "") or "")[:240],
                "source": str(getattr(raw, "provider", "") or ""),
                "source_url": str(getattr(raw, "source_url", "") or ""),
                "candidate_symbol": str(getattr(query, "symbol", "") or ""),
                "score": int(getattr(result, "result_score", 0) or 0),
                "result_score": int(getattr(result, "result_score", 0) or 0),
                "rejection_reason": _sample_rejection_reason(reasons),
                "identity_reason": _first_reason_with(reasons, "identity"),
                "catalyst_reason": _first_reason_with(reasons, "catalyst"),
            }
            samples_by_id.setdefault(hypothesis_id, []).append(sample)
    executed_by_id = _executed_queries_by_hypothesis(search_result)
    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        samples = samples_by_id.get(hypothesis.hypothesis_id, [])
        executed_queries = executed_by_id.get(hypothesis.hypothesis_id, ())
        if samples:
            merged = tuple(dict.fromkeys(
                json.dumps(sample, sort_keys=True, separators=(",", ":"))
                for sample in (*hypothesis.rejected_validation_samples, *samples)
            ))
            parsed = tuple(json.loads(item) for item in merged[: max(0, max_samples_per_hypothesis)])
            out.append(replace(
                hypothesis,
                rejected_validation_samples=parsed,
                executed_queries=_merge_query_details(hypothesis.executed_queries, executed_queries),
            ))
        else:
            out.append(replace(
                hypothesis,
                executed_queries=_merge_query_details(hypothesis.executed_queries, executed_queries),
            ) if executed_queries else hypothesis)
    out = list(_apply_candidate_discovery_results(out, search_result))
    return tuple(_with_promotion_diagnostics(item, search_result=search_result) for item in out)


def _apply_candidate_discovery_results(
    hypotheses: Iterable[EventImpactHypothesis],
    search_result: object,
) -> tuple[EventImpactHypothesis, ...]:
    """Use candidate-discovery results as suggestions, never as validation."""
    discovery_assets: dict[str, list[dict[str, Any]]] = {}
    for attr in ("result_events", "rejected_result_events"):
        for result in getattr(search_result, attr, ()) or ():
            query = getattr(result, "query", None)
            raw = getattr(result, "raw_event", None)
            if query is None or raw is None:
                continue
            if str(getattr(query, "query_type", "") or "") != "candidate_discovery":
                continue
            hypothesis_id = str(getattr(query, "anomaly_raw_id", "") or "")
            if not hypothesis_id:
                continue
            asset = _candidate_asset_from_discovery_raw(raw)
            if asset:
                reasons = tuple(str(value) for value in getattr(result, "result_score_reasons", ()) or ())
                asset = {
                    **asset,
                    "discovery_query": str(getattr(query, "query", "") or ""),
                    "query_type": "candidate_discovery",
                    "result_score": int(getattr(result, "result_score", 0) or 0),
                    "result_score_reasons": reasons[:8],
                    "source_url": str(getattr(raw, "source_url", "") or ""),
                    "discovered_terms": tuple(_candidate_discovered_terms(asset, raw)),
                    "funnel_stage": "candidate_discovery_result",
                    "converted_to_candidate": False,
                    "converted_to_radar": False,
                }
                discovery_assets.setdefault(hypothesis_id, []).append(asset)

    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        assets = tuple(discovery_assets.get(hypothesis.hypothesis_id, ()))
        if not assets:
            out.append(hypothesis)
            continue
        accepted, rejected = _split_suggested_assets(
            assets,
            external_entities=hypothesis.external_entities,
            text=" ".join((hypothesis.external_asset or "", *hypothesis.evidence_quotes)),
        )
        accepted = tuple({
            **asset,
            "accepted": True,
            "rejected": False,
            "resolver_result": "accepted",
            "funnel_stage": "resolver_accepted_candidate",
            "converted_to_candidate": True,
            "converted_to_radar": False,
        } for asset in accepted)
        rejected = tuple({
            **asset,
            "accepted": False,
            "rejected": True,
            "resolver_result": "rejected",
            "funnel_stage": "resolver_rejected_candidate",
            "converted_to_candidate": False,
            "converted_to_radar": False,
            "rejection_reason": asset.get("rejection_reason") or asset.get("identity_rejection_reason") or "identity_validation_failed",
        } for asset in rejected)
        crypto_assets = _merge_asset_rows(hypothesis.crypto_candidate_assets, accepted)
        symbols, coin_ids = _assets_from_asset_rows(crypto_assets)
        components = dict(hypothesis.score_components or {})
        base = _coerce_score(hypothesis.hypothesis_score)
        if not components and base > 0.0:
            components.update({
                "event_clarity": base,
                "source_quality": base,
                "catalyst_strength": base,
                "sector_relevance": base,
            })
        if accepted:
            components["candidate_asset_strength"] = max(
                _coerce_score(components.get("candidate_asset_strength")),
                min(100.0, 35.0 + len(accepted) * 14.0),
            )
        if rejected:
            components["candidate_discovery_rejected"] = max(
                _coerce_score(components.get("candidate_discovery_rejected")),
                float(len(rejected)),
            )
        score = _weighted_hypothesis_score(components, hypothesis.impact_category)
        stage = hypothesis.validation_stage
        status = hypothesis.status
        if accepted and stage in {
            ValidationStage.SECTOR_HYPOTHESIS.value,
            ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value,
        }:
            stage = ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value
            status = HypothesisStatus.VALIDATION_SEARCH_PENDING.value
        out.append(replace(
            hypothesis,
            candidate_symbols=symbols or hypothesis.candidate_symbols,
            candidate_coin_ids=coin_ids or hypothesis.candidate_coin_ids,
            suggested_candidate_assets=_merge_asset_rows(hypothesis.suggested_candidate_assets, accepted),
            crypto_candidate_assets=crypto_assets,
            rejected_candidate_assets=_merge_asset_rows(hypothesis.rejected_candidate_assets, rejected),
            candidate_source=_append_candidate_source(hypothesis.candidate_source, "candidate_discovery_search") if accepted else hypothesis.candidate_source,
            validation_stage=stage,
            status=status,
            score_components=components,
            hypothesis_score=round(score, 2),
            confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
        ))
    return tuple(out)
