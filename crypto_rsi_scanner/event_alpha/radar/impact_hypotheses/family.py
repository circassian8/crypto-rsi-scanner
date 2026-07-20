"""Impact-hypothesis text, identity, and family aggregation helpers."""

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
import crypto_rsi_scanner.event_alpha.radar.source_independence as event_source_independence
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



def _event_text(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    extraction_rows: Mapping[str, EventLLMExtractionReportRow],
) -> str:
    parts: list[str] = [event.event_name, event.event_type, event.external_asset or "", event.description or ""]
    for raw in raws:
        parts.append(_raw_text(raw))
        row = extraction_rows.get(raw.raw_id)
        extraction = row.extraction if row else None
        if extraction is None:
            continue
        for catalyst in extraction.external_catalysts:
            parts.extend((catalyst.name or "", catalyst.catalyst_type))
            parts.extend(quote.text for quote in catalyst.evidence_quotes)
        for mention in extraction.crypto_asset_mentions:
            parts.extend((mention.name or "", mention.symbol or "", mention.coin_id or "", mention.mention_type))
            parts.extend(quote.text for quote in mention.evidence_quotes)
    return clean_text(" ".join(str(part or "") for part in parts))


def _raw_text(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    parts = [
        raw.title,
        raw.body,
        event_payload.get("event_name"),
        event_payload.get("event_type"),
        event_payload.get("external_asset"),
        event_payload.get("description"),
    ]
    return " ".join(str(part or "") for part in parts)


def _evidence_quotes(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    quotes: list[str] = []
    original = str(text or "")
    for term in terms:
        needle = clean_text(term)
        if not needle or needle not in original:
            continue
        idx = original.find(needle)
        start = max(0, idx - 55)
        end = min(len(original), idx + len(needle) + 65)
        quote = original[start:end].strip()
        if quote:
            quotes.append(quote)
    return tuple(dict.fromkeys(quotes[:4]))


def _event_name(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event_payload.get("event_name") or payload.get("event_name") or "")


def _event_id_from_raw(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    return str(event_payload.get("event_id") or payload.get("event_id") or raw.raw_id)


def _is_market_anomaly(raws: Iterable[RawDiscoveredEvent]) -> bool:
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        if raw.provider == "market_anomaly" or isinstance(payload.get("anomaly"), Mapping):
            return True
    return False


def _normalized_from_market_anomaly(raw: RawDiscoveredEvent, now: datetime) -> NormalizedEvent:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    symbol = str(market.get("symbol") or payload.get("symbol") or raw.title or "market anomaly")
    return NormalizedEvent(
        event_id=f"hypothesis-{raw.raw_id}",
        raw_ids=(raw.raw_id,),
        event_name=f"{symbol} market anomaly",
        event_type="market_anomaly",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=raw.fetched_at or now,
        source=raw.provider,
        source_urls=(raw.source_url,) if raw.source_url else (),
        external_asset=None,
        description=raw.body or raw.title,
        confidence=max(0.0, min(1.0, float(raw.source_confidence or 0.0))),
    )


def _dedupe_hypotheses(items: Iterable[EventImpactHypothesis]) -> list[EventImpactHypothesis]:
    by_key: dict[str, EventImpactHypothesis] = {}
    for item in items:
        current = by_key.get(item.hypothesis_id)
        if current is None:
            by_key[item.hypothesis_id] = item
            continue
        merged = _merge_duplicate_hypotheses(current, item)
        by_key[item.hypothesis_id] = merged
    aggregated = _aggregate_validated_hypotheses(by_key.values())
    return sorted(aggregated, key=lambda item: (item.status != HypothesisStatus.VALIDATED.value, -item.confidence, item.hypothesis_id))


def _aggregate_validated_hypotheses(items: Iterable[EventImpactHypothesis]) -> list[EventImpactHypothesis]:
    grouped: dict[str, EventImpactHypothesis] = {}
    passthrough: list[EventImpactHypothesis] = []
    for item in items:
        key = _validated_hypothesis_aggregation_key(item)
        if key is None:
            passthrough.append(item)
            continue
        current = grouped.get(key)
        grouped[key] = item if current is None else _merge_aggregated_hypotheses(current, item)
    return [*passthrough, *grouped.values()]


def _validated_hypothesis_aggregation_key(item: EventImpactHypothesis) -> str | None:
    if item.status != HypothesisStatus.VALIDATED.value:
        return None
    asset = _validated_asset_key(item)
    if not asset:
        return None
    incident = item.incident_id or item.event_cluster_id
    if not incident:
        return None
    role = item.candidate_role or "unknown"
    family = _impact_path_family(item.impact_path_type or item.impact_path_reason or item.impact_category)
    return "|".join((incident, asset, role, family))


def _validated_asset_key(item: EventImpactHypothesis) -> str | None:
    for row in item.validated_candidate_assets:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip()
        if symbol or coin_id:
            return coin_id or symbol
    symbols = tuple(str(value).strip().upper() for value in item.candidate_symbols if str(value).strip())
    coin_ids = tuple(str(value).strip() for value in item.candidate_coin_ids if str(value).strip())
    if item.validation_stage in _PROMOTABLE_VALIDATION_STAGES and (symbols or coin_ids):
        return coin_ids[0] if coin_ids else symbols[0]
    return None


def _impact_path_family(value: str | None) -> str:
    text = clean_text(value or "")
    if any(term in text for term in ("proxy", "venue", "preipo", "pre ipo", "tokenized", "value capture", "exposure")):
        return "proxy_value_capture"
    if any(term in text for term in ("exploit", "security")):
        return "security"
    if any(term in text for term in ("listing", "liquidity")):
        return "listing_liquidity"
    if any(term in text for term in ("investment", "valuation", "stake", "acquisition")):
        return "strategic_investment"
    return text or "unknown"


def _merge_aggregated_hypotheses(
    current: EventImpactHypothesis,
    item: EventImpactHypothesis,
) -> EventImpactHypothesis:
    winner = item if (
        float(item.opportunity_score_final or item.hypothesis_score or 0.0),
        float(item.confidence or 0.0),
    ) > (
        float(current.opportunity_score_final or current.hypothesis_score or 0.0),
        float(current.confidence or 0.0),
    ) else current
    other = current if winner is item else item
    aggregate_id = _aggregated_candidate_id(winner)
    supporting_ids = tuple(dict.fromkeys((
        *(current.supporting_hypothesis_ids or (current.hypothesis_id,)),
        *(item.supporting_hypothesis_ids or (item.hypothesis_id,)),
    )))
    supporting_categories = tuple(dict.fromkeys((
        *(current.supporting_categories or (current.impact_category,)),
        *(item.supporting_categories or (item.impact_category,)),
    )))
    supporting_impact_paths = tuple(dict.fromkeys(
        path for path in (
            *(current.supporting_impact_paths or (current.impact_path_type,)),
            *(item.supporting_impact_paths or (item.impact_path_type,)),
        )
        if path
    ))
    supporting_quotes = tuple(dict.fromkeys((
        *current.supporting_evidence_quotes,
        *current.evidence_quotes,
        *item.supporting_evidence_quotes,
        *item.evidence_quotes,
    )))[:12]
    components = dict(other.score_components or {})
    components.update(dict(winner.score_components or {}))
    components.update({
        "aggregated_candidate_id": aggregate_id,
        "supporting_hypothesis_count": float(len(supporting_ids)),
        "supporting_categories": supporting_categories,
        "supporting_impact_paths": supporting_impact_paths,
    })
    independence_fields, independence_warning = _matching_source_independence(current, item)
    _replace_independence_components(components, independence_fields)
    return replace(
        winner,
        aggregated_candidate_id=aggregate_id,
        primary_impact_path=winner.primary_impact_path or winner.impact_path_type or winner.impact_path_reason or winner.impact_category,
        supporting_categories=supporting_categories,
        supporting_impact_paths=supporting_impact_paths,
        supporting_hypothesis_ids=supporting_ids,
        supporting_evidence_quotes=supporting_quotes,
        supporting_hypothesis_count=len(supporting_ids),
        source_raw_ids=tuple(dict.fromkeys((*current.source_raw_ids, *item.source_raw_ids))),
        source_event_ids=tuple(dict.fromkeys((*current.source_event_ids, *item.source_event_ids))),
        evidence_quotes=tuple(dict.fromkeys((*current.evidence_quotes, *item.evidence_quotes))),
        validation_reasons=tuple(dict.fromkeys((*current.validation_reasons, *item.validation_reasons))),
        warnings=tuple(dict.fromkeys((
            *current.warnings,
            *item.warnings,
            "aggregated_validated_hypothesis",
            *((independence_warning,) if independence_warning else ()),
        ))),
        **independence_fields,
        score_components=components,
    )


def _aggregated_candidate_id(item: EventImpactHypothesis) -> str:
    key = _validated_hypothesis_aggregation_key(item) or item.hypothesis_id
    return "agg:" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _merge_duplicate_hypotheses(
    current: EventImpactHypothesis,
    item: EventImpactHypothesis,
) -> EventImpactHypothesis:
    winner = item if item.confidence > current.confidence else current
    other = current if winner is item else item
    components = dict(other.score_components or {})
    components.update(dict(winner.score_components or {}))
    independence_fields, independence_warning = _matching_source_independence(current, item)
    _replace_independence_components(components, independence_fields)
    components["incident_source_update_count"] = float(len(set((*current.source_raw_ids, *item.source_raw_ids))))
    incident_confidence = max(
        _coerce_score(current.incident_confidence),
        _coerce_score(item.incident_confidence),
        _coerce_score(components.get("incident_confidence")),
    )
    if incident_confidence:
        components["incident_confidence"] = incident_confidence
    else:
        components.pop("incident_confidence", None)
    incident_observed = bool(current.incident_market_reaction_observed or item.incident_market_reaction_observed)
    incident_causal = bool(current.incident_causal_mechanism_confirmed or item.incident_causal_mechanism_confirmed)
    return replace(
        winner,
        incident_confidence=incident_confidence or None,
        incident_canonical_name=winner.incident_canonical_name or winner.canonical_incident_name,
        incident_event_archetype=winner.incident_event_archetype or winner.event_archetype,
        incident_primary_subject=winner.incident_primary_subject or winner.primary_subject,
        incident_affected_ecosystem=winner.incident_affected_ecosystem or winner.affected_ecosystem,
        incident_cause_status=winner.incident_cause_status or winner.cause_status,
        incident_market_reaction_observed=incident_observed,
        incident_causal_mechanism_confirmed=incident_causal,
        incident_link_status=winner.incident_link_status or other.incident_link_status,
        incident_link_reason=winner.incident_link_reason or other.incident_link_reason,
        source_raw_ids=tuple(dict.fromkeys((*current.source_raw_ids, *item.source_raw_ids))),
        source_event_ids=tuple(dict.fromkeys((*current.source_event_ids, *item.source_event_ids))),
        evidence_quotes=tuple(dict.fromkeys((*current.evidence_quotes, *item.evidence_quotes))),
        validation_reasons=tuple(dict.fromkeys((*current.validation_reasons, *item.validation_reasons))),
        rejection_reasons=tuple(dict.fromkeys((*current.rejection_reasons, *item.rejection_reasons))),
        warnings=tuple(dict.fromkeys((
            *current.warnings,
            *item.warnings,
            "incident_evidence_update",
            *((independence_warning,) if independence_warning else ()),
        ))),
        claim_history=tuple({json.dumps(row, sort_keys=True): row for row in (*current.claim_history, *item.claim_history)}.values()),
        **independence_fields,
        conflicting_claims=tuple(dict.fromkeys((*current.conflicting_claims, *item.conflicting_claims))),
        score_components=components,
    )


def _matching_source_independence(
    current: EventImpactHypothesis,
    item: EventImpactHypothesis,
) -> tuple[dict[str, Any], str | None]:
    scope_ids = {
        str(value).strip()
        for hypothesis in (current, item)
        for value in (hypothesis.incident_id or hypothesis.event_cluster_id,)
        if str(value or "").strip()
    }
    if len(scope_ids) > 1:
        return _source_independence_merge_result(
            "rejected", ("source_independence_scope_mismatch",)
        ), "source_independence_merge_rejected"

    contracts: list[dict[str, Any]] = []
    unassessed = False
    for hypothesis in (current, item):
        errors = _bounded_source_independence_errors(
            hypothesis.source_independence_errors
        )
        if errors:
            return _source_independence_merge_result(
                "rejected", errors
            ), "source_independence_merge_rejected"
        status = str(hypothesis.source_independence_status or "").strip().casefold()
        if status == "rejected":
            return _source_independence_merge_result(
                "rejected", ("source_independence_upstream_rejected",)
            ), "source_independence_merge_rejected"
        if status == "unassessed":
            if hypothesis.source_independence not in ({}, None):
                return _source_independence_merge_result(
                    "rejected", ("source_independence_status_contract_mismatch",)
                ), "source_independence_merge_rejected"
            unassessed = True
            continue
        if status != "assessed":
            return _source_independence_merge_result(
                "rejected", ("source_independence_status_invalid",)
            ), "source_independence_merge_rejected"
        value = hypothesis.source_independence
        if not isinstance(value, Mapping):
            return _source_independence_merge_result(
                "rejected", ("source_independence_contract_invalid",)
            ), "source_independence_merge_rejected"
        validation_errors = (
            event_source_independence.validate_source_independence_contract(value)
        )
        if validation_errors:
            return _source_independence_merge_result(
                "rejected", validation_errors
            ), "source_independence_merge_rejected"
        expected = (
            (hypothesis.independent_source_count, value.get("independent_evidence_count")),
            (
                hypothesis.independent_corroboration_count,
                value.get("independent_corroboration_count"),
            ),
            (
                hypothesis.source_content_cluster_count,
                value.get("content_cluster_count"),
            ),
        )
        if any(
            type(observed) is not int
            or type(contract_value) is not int
            or observed != contract_value
            for observed, contract_value in expected
        ):
            return _source_independence_merge_result(
                "rejected", ("source_independence_hypothesis_alias_mismatch",)
            ), "source_independence_merge_rejected"
        contracts.append(dict(value))
    if unassessed or not contracts:
        return _source_independence_merge_result(
            "unassessed"
        ), "source_independence_merge_unassessed"
    try:
        contract = event_source_independence.combine_source_independence_contracts(
            contracts
        )
    except (TypeError, ValueError):
        return _source_independence_merge_result(
            "rejected", ("source_independence_contract_union_failed",)
        ), "source_independence_merge_rejected"
    return _source_independence_merge_result("assessed", contract=contract), None


def _source_independence_merge_result(
    status: str,
    errors: Iterable[object] = (),
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status != "assessed" or not isinstance(contract, Mapping):
        return {
            "independent_source_domains": (),
            "source_independence": {},
            "source_independence_status": status,
            "source_independence_errors": _bounded_source_independence_errors(
                errors
            ),
            "independent_source_count": None,
            "independent_corroboration_count": None,
            "source_content_cluster_count": None,
        }
    return {
        "independent_source_domains": _independent_domains(contract),
        "source_independence": dict(contract),
        "source_independence_status": "assessed",
        "source_independence_errors": (),
        "independent_source_count": contract["independent_evidence_count"],
        "independent_corroboration_count": contract[
            "independent_corroboration_count"
        ],
        "source_content_cluster_count": contract["content_cluster_count"],
    }


def _independent_domains(contract: Mapping[str, Any]) -> tuple[str, ...]:
    documents = {
        str(row.get("document_id") or ""): row
        for row in contract.get("documents", ())
        if isinstance(row, Mapping)
    }
    return tuple(dict.fromkeys(
        str(documents[document_id].get("canonical_origin") or "")
        for value in contract.get("independent_representative_ids", ())
        for document_id in (str(value or ""),)
        if document_id in documents
        and str(documents[document_id].get("canonical_origin") or "")
    ))


def _bounded_source_independence_errors(value: object) -> tuple[str, ...]:
    values = (value,) if isinstance(value, str) else value
    if not isinstance(values, Iterable):
        return ()
    return tuple(dict.fromkeys(
        str(error).strip()[:160]
        for error in values
        if str(error).strip()
    ))[:16]


def _replace_independence_components(
    components: dict[str, Any],
    fields: Mapping[str, Any],
) -> None:
    for key in (
        "source_independence",
        "source_independence_status",
        "source_independence_errors",
        "independent_source_count",
        "independent_corroboration_count",
        "source_content_cluster_count",
    ):
        components.pop(key, None)
    components["source_independence"] = dict(
        fields.get("source_independence") or {}
    )
    components["source_independence_status"] = str(
        fields.get("source_independence_status") or "unassessed"
    )
    components["source_independence_errors"] = list(
        fields.get("source_independence_errors") or ()
    )
    for key in (
        "independent_source_count",
        "independent_corroboration_count",
        "source_content_cluster_count",
    ):
        if fields.get(key) is not None:
            components[key] = float(fields[key])


def _hypothesis_id(
    event: NormalizedEvent,
    category: str,
    sectors: tuple[str, ...],
    symbols: tuple[str, ...],
    *,
    incident_id: str | None = None,
) -> str:
    source = "|".join((
        incident_id or event_graph.cluster_id_for_event(event),
        category,
        ",".join(sectors),
        ",".join(symbols[:8]),
    ))
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"hyp:{digest}"


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
