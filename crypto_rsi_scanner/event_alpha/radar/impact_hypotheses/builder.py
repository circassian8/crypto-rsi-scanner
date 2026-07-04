"""Impact-hypothesis construction helpers."""

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



def _hypothesis_from_rule(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    rule: Mapping[str, Any],
    *,
    cluster: event_graph.EventCluster | None,
    incident: event_incident_graph.CanonicalIncident | None = None,
    taxonomy: Mapping[str, Mapping[str, Any]],
    text: str,
    now: datetime,
    suggested_assets: tuple[dict[str, Any], ...] = (),
    validated_assets: tuple[dict[str, Any], ...] = (),
) -> EventImpactHypothesis:
    category = rule["category"]
    category_value = category.value if isinstance(category, ImpactCategory) else str(category)
    sectors = tuple(str(value) for value in rule.get("sectors", ()) if str(value))
    external_entities = _external_entities_for_event(event, raws, text)
    taxonomy_assets = _asset_rows_from_taxonomy(sectors, taxonomy)
    accepted_suggested, rejected_suggested = _split_suggested_assets(
        suggested_assets,
        external_entities=external_entities,
        text=text,
    )
    crypto_candidate_assets = _merge_asset_rows(taxonomy_assets, accepted_suggested, validated_assets)
    symbols, coin_ids = _assets_from_asset_rows(crypto_candidate_assets)
    taxonomy_symbols, _taxonomy_coin_ids = _assets_from_asset_rows(taxonomy_assets)
    scope = _hypothesis_scope(category_value, text)
    if validated_assets:
        scope = HypothesisScope.TOKEN.value
    score_components = _hypothesis_score_components(
        event,
        rule,
        text,
        raws,
        cluster,
        crypto_candidate_assets=crypto_candidate_assets,
        validated_assets=validated_assets,
        suggested_assets=accepted_suggested,
    )
    score_components.update(
        _asset_knowledge_components(
            validated_assets[0]
            if validated_assets
            else (crypto_candidate_assets[0] if crypto_candidate_assets else None)
        )
    )
    claim_rows = event_claim_semantics.extract_event_claims(raws)
    incident = incident or _incident_for_single_event(event, raws)
    if incident is not None:
        score_components.update(_incident_score_components(incident))
        score_components.update(_incident_frame_components(incident))
        category_value = _category_from_incident(category_value, incident)
        if category_value == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
            rule = {**dict(rule), "category": ImpactCategory.MARKET_ANOMALY_UNKNOWN, "playbook": "market_anomaly_unknown", "direction": "unknown"}
    hypothesis_score = _weighted_hypothesis_score(score_components, category_value)
    confidence = max(0.0, min(1.0, round(hypothesis_score / 100.0, 4)))
    quotes = _evidence_quotes(text, (*rule.get("keywords", ()), *rule.get("secondary", ())))
    validation_stage = _initial_validation_stage(category_value, crypto_candidate_assets, validated_assets)
    frame_gate = _frame_gate_metadata(raws, category_value=category_value, incident=incident)
    score_components.update(frame_gate)
    status = (
        HypothesisStatus.VALIDATION_SEARCH_PENDING.value
        if category != ImpactCategory.MARKET_ANOMALY_UNKNOWN and crypto_candidate_assets
        else HypothesisStatus.HYPOTHESIS.value
    )
    if validated_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN:
        status = HypothesisStatus.VALIDATED.value
    candidate_source = _candidate_source(taxonomy_symbols, accepted_suggested, validated_assets)
    hypothesis = _base_hypothesis_from_rule(
        event,
        raws,
        rule,
        cluster=cluster,
        incident=incident,
        now=now,
        category_value=category_value,
        sectors=sectors,
        symbols=symbols,
        coin_ids=coin_ids,
        external_entities=external_entities,
        crypto_candidate_assets=crypto_candidate_assets,
        accepted_suggested=accepted_suggested,
        rejected_suggested=rejected_suggested,
        validated_assets=validated_assets,
        candidate_source=candidate_source,
        scope=scope,
        confidence=confidence,
        hypothesis_score=hypothesis_score,
        score_components=score_components,
        validation_stage=validation_stage,
        quotes=quotes,
        status=status,
        frame_gate=frame_gate,
        claim_rows=claim_rows,
    )
    if incident:
        hypothesis = replace(hypothesis, **_incident_relevance_replace_kwargs(incident, raws, hypothesis))
    if validated_assets and raws:
        hypothesis = _with_validated_asset_impact_validation(
            hypothesis,
            raws,
            validated_assets=validated_assets,
            symbols=symbols,
            coin_ids=coin_ids,
            score_components=score_components,
            validation_stage=validation_stage,
            category_value=category_value,
        )
    return _with_search_query_diagnostics(hypothesis)


def _base_hypothesis_from_rule(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    rule: Mapping[str, Any],
    *,
    cluster: event_graph.EventCluster | None,
    incident: event_incident_graph.CanonicalIncident | None,
    now: datetime,
    category_value: str,
    sectors: tuple[str, ...],
    symbols: tuple[str, ...],
    coin_ids: tuple[str, ...],
    external_entities: tuple[str, ...],
    crypto_candidate_assets: tuple[dict[str, Any], ...],
    accepted_suggested: tuple[dict[str, Any], ...],
    rejected_suggested: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
    candidate_source: str,
    scope: str,
    confidence: float,
    hypothesis_score: float,
    score_components: dict[str, Any],
    validation_stage: str,
    quotes: tuple[str, ...],
    status: str,
    frame_gate: Mapping[str, Any],
    claim_rows: tuple[Any, ...],
) -> EventImpactHypothesis:
    return EventImpactHypothesis(
        hypothesis_id=_hypothesis_id(event, category_value, sectors, symbols, incident_id=incident.incident_id if incident else None),
        event_cluster_id=incident.incident_id if incident else (cluster.cluster_id if cluster else event_graph.cluster_id_for_event(event)),
        event_type=str(event.event_type or "unknown"),
        external_asset=event.external_asset,
        impact_category=category_value,
        candidate_sectors=sectors,
        candidate_symbols=symbols,
        candidate_coin_ids=coin_ids,
        suggested_candidate_assets=accepted_suggested,
        validated_candidate_assets=validated_assets,
        external_entities=external_entities,
        crypto_candidate_assets=crypto_candidate_assets,
        rejected_candidate_assets=rejected_suggested,
        candidate_source=candidate_source,
        hypothesis_scope=scope,
        direction_hint=str(rule.get("direction") or "unknown"),
        playbook_hint=str(rule.get("playbook") or ""),
        confidence=confidence,
        hypothesis_score=round(hypothesis_score, 2),
        score_components=score_components,
        validation_stage=validation_stage,
        evidence_quotes=quotes,
        required_validation_steps=_validation_steps(category_value),
        status=status,
        warnings=_hypothesis_warnings(event, raws, category_value),
        source_raw_ids=tuple(raw.raw_id for raw in raws),
        source_event_ids=(event.event_id,),
        validation_reasons=(("resolver_validated_candidate_asset",) if validated_assets else ()),
        **_incident_hypothesis_kwargs(incident, raws, claim_rows, score_components),
        **_frame_gate_hypothesis_kwargs(frame_gate),
        created_at=now.isoformat(),
    )


def _incident_hypothesis_kwargs(
    incident: event_incident_graph.CanonicalIncident | None,
    raws: tuple[RawDiscoveredEvent, ...],
    claim_rows: tuple[Any, ...],
    score_components: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "incident_confidence": _optional_score(score_components.get("incident_confidence")) if incident else None,
        "incident_id": incident.incident_id if incident else None,
        "incident_canonical_name": incident.canonical_name if incident else None,
        "incident_event_archetype": incident.event_archetype if incident else None,
        "incident_primary_subject": incident.primary_subject if incident else None,
        "incident_affected_ecosystem": incident.affected_ecosystem if incident else None,
        "incident_cause_status": incident.current_cause_status if incident else None,
        "incident_market_reaction_observed": _incident_market_reaction_observed(incident, raws) if incident else None,
        "incident_causal_mechanism_confirmed": (
            incident.current_cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value
            if incident
            else None
        ),
        "incident_link_status": "linked" if incident else "no_incident",
        "incident_link_reason": None if incident else "no_canonical_incident_for_event_evidence",
        "canonical_incident_name": incident.canonical_name if incident else None,
        "event_archetype": incident.event_archetype if incident else None,
        "primary_subject": incident.primary_subject if incident else None,
        "affected_entity": incident.primary_subject if incident else None,
        "affected_ecosystem": incident.affected_ecosystem if incident else None,
        "cause_status": incident.current_cause_status if incident else event_claim_semantics.current_cause_status(claim_rows, "exploit"),
        "claim_polarities": tuple(dict.fromkeys(claim.polarity for claim in claim_rows)),
        "claim_history": tuple(_claim_to_row(claim) for claim in claim_rows[:12]),
        "main_catalyst_frame_id": incident.main_catalyst_frame_id if incident else None,
        "main_frame_type": incident.main_frame_type if incident else None,
        "main_frame_role": incident.main_frame_role if incident else None,
        "main_frame_subject": incident.main_frame_subject if incident else None,
        "main_frame_actor": incident.main_frame_actor if incident else None,
        "main_frame_object": incident.main_frame_object if incident else None,
        "main_frame_evidence_quote": incident.main_frame_evidence_quote if incident else None,
        "background_frame_ids": incident.background_frame_ids if incident else (),
        "negated_frame_ids": incident.negated_frame_ids if incident else (),
        "corrective_frame_ids": incident.corrective_frame_ids if incident else (),
        "frame_summary": tuple(dict(item) for item in incident.frame_summary) if incident else (),
        "background_context_summary": incident.background_context_summary if incident else None,
        "rejected_impact_paths": _rejected_impact_paths_from_frames(incident) if incident else (),
        "rejected_impact_paths_from_background": _rejected_impact_paths_from_frames(incident) if incident else (),
        "selected_main_catalyst_reason": incident.selected_main_catalyst_reason if incident else None,
        "rule_predicted_impact_path": incident.rule_predicted_impact_path if incident else None,
        "llm_predicted_main_frame_type": incident.llm_predicted_main_frame_type if incident else None,
        "frame_rule_disagreement": incident.frame_rule_disagreement if incident else None,
        "disagreement_resolution": incident.disagreement_resolution if incident else None,
        "independent_source_domains": incident.independent_source_domains if incident else (),
        "conflicting_claims": incident.conflicting_claims if incident else (),
    }


def _frame_gate_hypothesis_kwargs(frame_gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "frame_required": bool(frame_gate.get("frame_required")),
        "frame_status": str(frame_gate.get("frame_status") or "") or None,
        "frame_required_reason": str(frame_gate.get("frame_required_reason") or "") or None,
        "frame_gate_reason": str(frame_gate.get("frame_gate_reason") or "") or None,
        "route_block_reason": str(frame_gate.get("route_block_reason") or "") or None,
        "primary_impact_path": str(frame_gate.get("primary_impact_path") or "") or None,
        "asset_role_source": str(frame_gate.get("asset_role_source") or "") or None,
    }


def _with_validated_asset_impact_validation(
    hypothesis: EventImpactHypothesis,
    raws: tuple[RawDiscoveredEvent, ...],
    *,
    validated_assets: tuple[dict[str, Any], ...],
    symbols: tuple[str, ...],
    coin_ids: tuple[str, ...],
    score_components: Mapping[str, Any],
    validation_stage: str,
    category_value: str,
) -> EventImpactHypothesis:
    asset = validated_assets[0]
    symbol = str(asset.get("symbol") or (symbols[0] if symbols else ""))
    coin_id = str(asset.get("coin_id") or (coin_ids[0] if coin_ids else ""))
    validation = event_impact_path_validator.validate_impact_path(
        raws[0],
        hypothesis,
        symbol=symbol,
        coin_id=coin_id,
        score_components=score_components,
    )
    updated_components = dict(score_components)
    updated_components.update(_impact_validation_score_components(validation))
    updated_components.update(_impact_validation_metadata_components(validation))
    validation = _refresh_impact_validation_score(validation, updated_components)
    updated_components.update(_impact_validation_score_components(validation))
    updated_components.update(_impact_validation_metadata_components(validation))
    quality_kwargs = _quality_verdict_replace_kwargs(
        validation,
        impact_context=(raws[0], symbol, coin_id),
        hypothesis=hypothesis,
        components=updated_components,
    )
    updated_components.update(_quality_score_components(quality_kwargs))
    stage = validation_stage
    if validation.required_evidence_met:
        stage = _max_validation_stage(stage, ValidationStage.IMPACT_PATH_VALIDATED.value)
    score = _weighted_hypothesis_score(updated_components, category_value)
    return _with_incident_aliases(replace(
        hypothesis,
        validation_stage=stage,
        hypothesis_score=round(score, 2),
        confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
        score_components=updated_components,
        impact_path_reason=validation.impact_path_reason,
        **_impact_validation_replace_kwargs(validation),
        **quality_kwargs,
    ))


def _with_search_query_diagnostics(hypothesis: EventImpactHypothesis) -> EventImpactHypothesis:
    query_details = _default_search_query_details(hypothesis)
    hypothesis = replace(
        hypothesis,
        search_queries=tuple(str(item.get("query") or "") for item in query_details if item.get("query")),
        search_query_details=query_details,
        generated_queries=query_details,
    )
    return _with_promotion_diagnostics(_with_incident_aliases(hypothesis))


def _incident_for_single_event(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
) -> event_incident_graph.CanonicalIncident | None:
    incidents = event_incident_graph.build_incidents((event,), {raw.raw_id: raw for raw in raws})
    return incidents[0] if incidents else None


def _category_from_incident(category: str, incident: event_incident_graph.CanonicalIncident) -> str:
    if incident.event_archetype == "market_dislocation_unknown":
        return ImpactCategory.MARKET_ANOMALY_UNKNOWN.value
    if incident.event_archetype == event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT:
        return ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION.value
    return category


def _incident_score_components(incident: event_incident_graph.CanonicalIncident) -> dict[str, float]:
    components: dict[str, float] = {
        "incident_confidence": min(100.0, 35.0 + len(incident.raw_ids) * 12.0 + len(incident.independent_source_domains) * 18.0),
        "independent_source_count": float(len(incident.independent_source_domains)),
    }
    if incident.current_cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value:
        components["causal_mechanism_confirmed"] = 85.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.SUSPECTED.value:
        components["causal_mechanism_confirmed"] = 35.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.RULED_OUT.value:
        components["causal_mechanism_confirmed"] = 0.0
    return components


def _incident_frame_components(incident: event_incident_graph.CanonicalIncident) -> dict[str, Any]:
    return {
        "main_catalyst_frame_id": incident.main_catalyst_frame_id,
        "main_frame_type": incident.main_frame_type,
        "main_frame_role": incident.main_frame_role,
        "main_frame_subject": incident.main_frame_subject,
        "main_frame_actor": incident.main_frame_actor,
        "main_frame_object": incident.main_frame_object,
        "main_frame_evidence_quote": incident.main_frame_evidence_quote,
        "background_frame_ids": tuple(incident.background_frame_ids),
        "negated_frame_ids": tuple(incident.negated_frame_ids),
        "corrective_frame_ids": tuple(incident.corrective_frame_ids),
        "background_context_summary": incident.background_context_summary,
        "frame_summary": tuple(incident.frame_summary),
        "selected_event_archetype": incident.event_archetype,
        "background_frame_count": float(len(incident.background_frame_ids)),
        "negated_frame_count": float(len(incident.negated_frame_ids)),
        "corrective_frame_count": float(len(incident.corrective_frame_ids)),
        "rejected_impact_paths": _rejected_impact_paths_from_frames(incident),
        "rejected_impact_paths_from_background": _rejected_impact_paths_from_frames(incident),
        "selected_main_catalyst_reason": incident.selected_main_catalyst_reason,
        "rule_predicted_impact_path": incident.rule_predicted_impact_path,
        "llm_predicted_main_frame_type": incident.llm_predicted_main_frame_type,
        "frame_rule_disagreement": incident.frame_rule_disagreement,
        "disagreement_resolution": incident.disagreement_resolution,
    }


def _frame_gate_metadata(
    raws: tuple[RawDiscoveredEvent, ...],
    *,
    category_value: str,
    incident: event_incident_graph.CanonicalIncident | None,
) -> dict[str, Any]:
    required_reasons: list[str] = []
    statuses: list[str] = []
    skip_reasons: list[str] = []
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        required, reason = event_llm_catalyst_frames.frame_requirement_for_raw(raw)
        if bool(payload.get("catalyst_frame_required")) or required:
            required_reasons.append(str(payload.get("catalyst_frame_required_reason") or reason or "catalyst_frame_required"))
        status = str(payload.get("catalyst_frame_status") or "").strip()
        if status:
            statuses.append(status)
        skip = str(payload.get("catalyst_frame_skip_reason") or "").strip()
        if skip:
            skip_reasons.append(skip)
    main_type = incident.main_frame_type if incident else None
    deterministic_sufficient = _deterministic_frame_sufficient(incident, category_value=category_value)
    required = bool(required_reasons)
    if any(status == "validated" for status in statuses):
        status = "validated"
    elif any(status == "unresolved" for status in statuses):
        status = "unresolved"
    elif required and deterministic_sufficient:
        status = "deterministic_frame_sufficient"
    elif required:
        status = "missing_required_frame_analysis"
    else:
        status = "not_required"
    block_reason = None
    if required and status == "unresolved":
        block_reason = "catalyst_frame_unresolved"
    elif required and status == "missing_required_frame_analysis":
        block_reason = "catalyst_frame_missing"
    return {
        "frame_required": required,
        "frame_status": status,
        "frame_required_reason": required_reasons[0] if required_reasons else None,
        "frame_skip_reasons": tuple(dict.fromkeys(skip_reasons)),
        "frame_gate_reason": block_reason,
        "route_block_reason": block_reason,
        "primary_impact_path": main_type,
        "asset_role_source": "validated_asset" if incident is not None else "unknown",
    }


def _deterministic_frame_sufficient(
    incident: event_incident_graph.CanonicalIncident | None,
    *,
    category_value: str,
) -> bool:
    if incident is None:
        return False
    main_type = str(incident.main_frame_type or "")
    main_role = str(incident.main_frame_role or "")
    if main_role not in {event_catalyst_frames.ROLE_MAIN, event_catalyst_frames.ROLE_MARKET_REACTION}:
        return False
    if main_type in {
        event_catalyst_frames.TYPE_ACQUISITION_OR_STAKE,
        event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT,
        event_catalyst_frames.TYPE_VALUATION_EVENT,
        event_catalyst_frames.TYPE_LISTING_LIQUIDITY,
        event_catalyst_frames.TYPE_UNLOCK_SUPPLY,
    }:
        return True
    if main_type == event_catalyst_frames.TYPE_EXPLOIT_SECURITY:
        return (
            str(incident.current_cause_status or "") == event_claim_semantics.CauseStatus.CONFIRMED.value
            and not incident.frame_rule_disagreement
        )
    if main_type == event_catalyst_frames.TYPE_PROXY_ATTENTION and category_value in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
    }:
        return True
    return False


def _apply_frame_route_cap(hypothesis: EventImpactHypothesis) -> EventImpactHypothesis:
    block = str(hypothesis.route_block_reason or hypothesis.frame_gate_reason or "").strip()
    if not block:
        return hypothesis
    if hypothesis.status != HypothesisStatus.VALIDATED.value:
        return hypothesis
    if hypothesis.opportunity_level in {"local_only", "exploratory"}:
        return hypothesis
    current_score = _optional_score(hypothesis.opportunity_score_final)
    capped_score = min(current_score if current_score is not None else float(hypothesis.hypothesis_score or 0.0), 54.0)
    components = dict(hypothesis.score_components or {})
    components["frame_gate_route_blocked"] = 1.0
    components["route_block_reason"] = block
    return replace(
        hypothesis,
        opportunity_score_final=round(capped_score, 2),
        opportunity_level="exploratory",
        why_local_only=block,
        why_not_watchlist=block,
        route_block_reason=block,
        score_components=components,
        warnings=tuple(dict.fromkeys((*hypothesis.warnings, f"catalyst_frame_route_blocked:{block}"))),
    )


def _rejected_impact_paths_from_frames(incident: event_incident_graph.CanonicalIncident | None) -> tuple[str, ...]:
    if incident is None:
        return ()
    out: list[str] = []
    for frame in incident.frame_summary:
        if not isinstance(frame, Mapping):
            continue
        frame_type = str(frame.get("frame_type") or "")
        role = str(frame.get("frame_role") or "")
        subject = str(frame.get("subject") or "unknown")
        if role in {"background_context", "historical_context"} and frame_type:
            out.append(f"{frame_type}:background_for:{subject}")
            out.append("background_context_not_primary_catalyst")
            if role == "historical_context":
                out.append("historical_context_only")
        if role == "negated_claim" and frame_type:
            out.append(f"{frame_type}:negated_for:{subject}")
            out.append("negated_claim_blocks_impact_path")
        if role == "corrective_context" and frame_type:
            out.append(f"{frame_type}:corrective_for:{subject}")
            out.append("negated_claim_blocks_impact_path")
    if any(
        isinstance(frame, Mapping)
        and str(frame.get("frame_role") or "") == "main_catalyst"
        for frame in incident.frame_summary
    ) and any(
        isinstance(frame, Mapping)
        and str(frame.get("frame_role") or "") in {"background_context", "historical_context"}
        for frame in incident.frame_summary
    ):
        out.append("main_catalyst_selected_over_background")
    return tuple(dict.fromkeys(out))


def _incident_market_reaction_observed(
    incident: event_incident_graph.CanonicalIncident | None,
    raws: Iterable[RawDiscoveredEvent],
) -> bool:
    if incident is not None and incident.event_archetype == "market_dislocation_unknown":
        return True
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        if isinstance(payload.get("market"), Mapping) and payload.get("market"):
            return True
        if isinstance(payload.get("anomaly"), Mapping) and payload.get("anomaly"):
            return True
    return False


def _with_incident_aliases(hypothesis: EventImpactHypothesis) -> EventImpactHypothesis:
    """Populate durable incident_* aliases while preserving legacy field names."""
    canonical = hypothesis.incident_canonical_name or hypothesis.canonical_incident_name
    archetype = hypothesis.incident_event_archetype or hypothesis.event_archetype
    subject = hypothesis.incident_primary_subject or hypothesis.primary_subject
    ecosystem = hypothesis.incident_affected_ecosystem or hypothesis.affected_ecosystem
    cause = hypothesis.incident_cause_status or hypothesis.cause_status
    observed = hypothesis.incident_market_reaction_observed
    if observed is None and hypothesis.market_reaction_confirmed is not None:
        observed = bool(hypothesis.market_reaction_confirmed)
    causal = hypothesis.incident_causal_mechanism_confirmed
    if causal is None and hypothesis.causal_mechanism_confirmed is not None:
        causal = bool(hypothesis.causal_mechanism_confirmed)
    return replace(
        hypothesis,
        incident_canonical_name=canonical,
        incident_event_archetype=archetype,
        incident_primary_subject=subject,
        incident_affected_ecosystem=ecosystem,
        incident_cause_status=cause,
        incident_market_reaction_observed=observed,
        incident_causal_mechanism_confirmed=causal,
        incident_link_status=hypothesis.incident_link_status or ("linked" if hypothesis.incident_id else "no_incident"),
        incident_link_reason=(
            hypothesis.incident_link_reason
            or (None if hypothesis.incident_id else "no_canonical_incident_for_event_evidence")
        ),
        incident_relevance_status=hypothesis.incident_relevance_status,
        incident_relevance_score=hypothesis.incident_relevance_score,
        incident_relevance_reasons=hypothesis.incident_relevance_reasons,
        incident_relevance_warnings=hypothesis.incident_relevance_warnings,
        canonical_persistence_reason=hypothesis.canonical_persistence_reason,
        canonical_incident_name=hypothesis.canonical_incident_name or canonical,
        event_archetype=hypothesis.event_archetype or archetype,
        primary_subject=hypothesis.primary_subject or subject,
        affected_ecosystem=hypothesis.affected_ecosystem or ecosystem,
        cause_status=hypothesis.cause_status or cause,
    )


def _incident_relevance_replace_kwargs(
    incident: event_incident_graph.CanonicalIncident,
    raws: tuple[RawDiscoveredEvent, ...],
    hypothesis: EventImpactHypothesis,
) -> dict[str, Any]:
    relevance = event_incident_store.classify_incident_relevance(
        incident,
        raw_by_id={raw.raw_id: raw for raw in raws},
        hypotheses=(hypothesis,),
        watchlist_rows=(),
    )
    return {
        "incident_relevance_status": str(relevance.get("incident_relevance_status") or ""),
        "incident_relevance_score": _optional_score(relevance.get("incident_relevance_score")),
        "incident_relevance_reasons": tuple(str(item) for item in relevance.get("incident_relevance_reasons") or ()),
        "incident_relevance_warnings": tuple(str(item) for item in relevance.get("incident_relevance_warnings") or ()),
        "canonical_persistence_reason": str(relevance.get("canonical_persistence_reason") or "") or None,
    }


def _claim_to_row(claim: event_claim_semantics.EventClaim) -> dict[str, Any]:
    return {
        "claim_type": claim.claim_type,
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "polarity": claim.polarity,
        "cause_status": claim.cause_status,
        "confidence": claim.confidence,
        "evidence_quote": claim.evidence_quote,
        "source_raw_id": claim.source_raw_id,
        "source_url": claim.source_url,
        "published_at": claim.published_at.isoformat() if hasattr(claim.published_at, "isoformat") else claim.published_at,
    }


def _assets_from_taxonomy(
    sector_names: Iterable[str],
    taxonomy: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    symbols: list[str] = []
    coin_ids: list[str] = []
    for sector in sector_names:
        row = taxonomy.get(sector) or {}
        for asset in row.get("assets") or ():
            if not isinstance(asset, Mapping):
                continue
            symbol = str(asset.get("symbol") or "").strip().upper()
            coin_id = str(asset.get("coin_id") or "").strip()
            if symbol:
                symbols.append(symbol)
            if coin_id:
                coin_ids.append(coin_id)
    return tuple(dict.fromkeys(symbols)), tuple(dict.fromkeys(coin_ids))


def _asset_rows_from_taxonomy(
    sector_names: Iterable[str],
    taxonomy: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for sector in sector_names:
        row = taxonomy.get(sector) or {}
        for asset in row.get("assets") or ():
            if not isinstance(asset, Mapping):
                continue
            symbol = str(asset.get("symbol") or "").strip().upper()
            coin_id = str(asset.get("coin_id") or "").strip()
            name = str(asset.get("name") or "").strip()
            if not any((symbol, coin_id, name)):
                continue
            rows.append({
                "source": "taxonomy",
                "sector": str(sector),
                "name": name,
                "symbol": symbol,
                "coin_id": coin_id,
                "role_source": event_identity.ROLE_SOURCE_TAXONOMY_CANDIDATE,
                "identity_confidence": 35.0,
                "identity_evidence": ("taxonomy candidate",),
                "validated": False,
            })
    return _merge_asset_rows(tuple(rows))


from .generation import generate_impact_hypotheses, validate_hypotheses_with_raw_events
