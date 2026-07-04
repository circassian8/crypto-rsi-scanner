"""Impact-hypothesis report rendering."""

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
    event_catalyst_frames,
    event_claim_semantics,
    event_evidence_quality,
    event_graph,
    event_identity,
    event_incident_graph,
    event_impact_path_validator,
    event_llm_catalyst_frames,
)
from ....event_llm_extractor import EventLLMExtractionReportRow
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from ....event_resolver import clean_text
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



def format_impact_hypothesis_report(hypotheses: Iterable[EventImpactHypothesis]) -> str:
    rows = [
        "=" * 76,
        "EVENT IMPACT HYPOTHESES (research-only; not alerts or trade signals)",
        "=" * 76,
    ]
    items = list(hypotheses)
    rows.append(f"hypotheses: {len(items)}")
    if not items:
        rows.append("")
        rows.append("No impact hypotheses.")
        return "\n".join(rows)
    rows.extend(_impact_hypothesis_summary_lines(items))
    rows.append("")
    for item in items[:20]:
        rows.extend(_impact_hypothesis_detail_lines(item))
    return "\n".join(rows).rstrip()


def _impact_hypothesis_summary_lines(items: list[EventImpactHypothesis]) -> list[str]:
    rows: list[str] = []
    counts: dict[str, int] = {}
    stages: dict[str, int] = {}
    path_reasons: dict[str, int] = {}
    path_types: dict[str, int] = {}
    path_strengths: dict[str, int] = {}
    opportunity_levels: dict[str, int] = {}
    market_levels: dict[str, int] = {}
    source_classes: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
        stages[item.validation_stage] = stages.get(item.validation_stage, 0) + 1
        if item.impact_path_reason:
            path_reasons[item.impact_path_reason] = path_reasons.get(item.impact_path_reason, 0) + 1
        if item.impact_path_type:
            path_types[item.impact_path_type] = path_types.get(item.impact_path_type, 0) + 1
        if item.impact_path_strength:
            path_strengths[item.impact_path_strength] = path_strengths.get(item.impact_path_strength, 0) + 1
        if item.opportunity_level:
            opportunity_levels[item.opportunity_level] = opportunity_levels.get(item.opportunity_level, 0) + 1
        if item.market_confirmation_level:
            market_levels[item.market_confirmation_level] = market_levels.get(item.market_confirmation_level, 0) + 1
        if item.source_class:
            source_classes[item.source_class] = source_classes.get(item.source_class, 0) + 1
    rows.append("statuses: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    rows.append("validation_stages: " + ", ".join(f"{key}={value}" for key, value in sorted(stages.items())))
    if path_reasons:
        rows.append("impact_path_reasons: " + ", ".join(f"{key}={value}" for key, value in sorted(path_reasons.items())))
    if path_types:
        rows.append("impact_path_types: " + ", ".join(f"{key}={value}" for key, value in sorted(path_types.items())))
    if path_strengths:
        rows.append("impact_path_strengths: " + ", ".join(f"{key}={value}" for key, value in sorted(path_strengths.items())))
    if opportunity_levels:
        rows.append("opportunity_levels: " + ", ".join(f"{key}={value}" for key, value in sorted(opportunity_levels.items())))
    if market_levels:
        rows.append("market_confirmation_levels: " + ", ".join(f"{key}={value}" for key, value in sorted(market_levels.items())))
    if source_classes:
        rows.append("source_classes: " + ", ".join(f"{key}={value}" for key, value in sorted(source_classes.items())))
    rows.extend(_candidate_discovery_funnel_lines(items))
    why_counts: dict[str, int] = {}
    for item in items:
        for reason in item.why_not_promoted:
            why_counts[reason] = why_counts.get(reason, 0) + 1
    if why_counts:
        rows.append("why_not_promoted: " + ", ".join(f"{key}={value}" for key, value in sorted(why_counts.items())))
    categories: dict[str, int] = {}
    for item in items:
        categories[item.impact_category] = categories.get(item.impact_category, 0) + 1
    rows.append("categories: " + ", ".join(f"{key}={value}" for key, value in sorted(categories.items())))
    return rows


def _impact_hypothesis_detail_lines(item: EventImpactHypothesis) -> list[str]:
    rows = [
        f"{item.status:<26} stage={item.validation_stage} score={item.hypothesis_score:.1f} conf={item.confidence:.2f} "
        f"{item.impact_category} external={item.external_asset or 'unknown'}"
    ]
    if item.external_entities:
        rows.append(
            "  external_entities: "
            + ", ".join(str(entity.get("name") or "") for entity in item.external_entities[:6])
        )
    rows.append(f"  sectors: {', '.join(item.candidate_sectors) or 'none'}")
    rows.append(f"  symbols: {', '.join(item.candidate_symbols) or 'none'}")
    rows.append(f"  candidate_source={item.candidate_source}")
    rows.extend(_impact_hypothesis_asset_lines(item))
    rows.append(
        f"  direction={item.direction_hint} playbook={item.playbook_hint or 'unknown'} "
        f"cluster={item.event_cluster_id or 'none'}"
    )
    if item.evidence_quotes:
        rows.append("  evidence: " + " | ".join(item.evidence_quotes[:3]))
    if item.search_queries:
        query_labels = [
            f"{detail.get('query_type') or 'candidate_validation'}:{detail.get('query')}"
            for detail in item.search_query_details[:4]
        ] or list(item.search_queries[:4])
        rows.append("  queries: " + " | ".join(query_labels))
    if item.validation_reasons:
        rows.append("  validated: " + "; ".join(item.validation_reasons[:3]))
    if item.impact_path_reason:
        rows.append(f"  impact_path_reason: {item.impact_path_reason}")
    rows.extend(_impact_hypothesis_verdict_lines(item))
    if item.manual_verification_items:
        rows.append("  verify_next: " + "; ".join(item.manual_verification_items[:3]))
    if item.why_digest_ineligible:
        rows.append(f"  why_digest_ineligible: {item.why_digest_ineligible}")
    if item.rejection_reasons:
        rows.append("  rejected: " + "; ".join(item.rejection_reasons[:3]))
    rejected_samples = tuple(
        sample for sample in item.rejected_validation_samples
        if not bool(sample.get("accepted")) or sample.get("rejection_reason")
    )
    if rejected_samples:
        sample = rejected_samples[0]
        rows.append(
            "  rejected_validation_sample: "
            f"{sample.get('query_type') or 'unknown'} {sample.get('candidate_symbol') or 'SECTOR'} "
            f"{sample.get('rejection_reason') or 'none'}"
        )
    if item.why_not_promoted:
        rows.append("  why_not_promoted: " + "; ".join(item.why_not_promoted[:4]))
    if item.warnings:
        rows.append("  warnings: " + "; ".join(item.warnings[:3]))
    return rows


def _impact_hypothesis_asset_lines(item: EventImpactHypothesis) -> list[str]:
    rows: list[str] = []
    for label, assets in (
        ("crypto_candidates", item.crypto_candidate_assets),
        ("rejected_candidates", item.rejected_candidate_assets),
        ("suggested_assets", item.suggested_candidate_assets),
        ("validated_assets", item.validated_candidate_assets),
    ):
        if assets:
            rows.append("  " + label + ": " + ", ".join(_asset_label(asset) for asset in assets[:6]))
    return rows


def _impact_hypothesis_verdict_lines(item: EventImpactHypothesis) -> list[str]:
    rows: list[str] = []
    if item.impact_path_type or item.impact_path_strength or item.opportunity_score_v2 is not None:
        rows.append(
            "  impact_path: "
            f"type={item.impact_path_type or 'unknown'} "
            f"role={item.candidate_role or 'unknown'} "
            f"strength={item.impact_path_strength or 'unknown'} "
            f"specificity={item.evidence_specificity_score if item.evidence_specificity_score is not None else 'n/a'} "
            f"score_v2={item.opportunity_score_v2 if item.opportunity_score_v2 is not None else 'n/a'} "
            f"digest_eligible={str(bool(item.digest_eligible_by_impact_path)).lower()}"
        )
    if item.opportunity_score_final is not None or item.opportunity_level:
        rows.append(
            "  opportunity_verdict: "
            f"level={item.opportunity_level or 'unknown'} "
            f"score_final={item.opportunity_score_final if item.opportunity_score_final is not None else 'n/a'} "
            f"market={item.market_confirmation_level or 'unknown'}"
            f"/{item.market_confirmation_score if item.market_confirmation_score is not None else 'n/a'} "
            f"evidence={item.source_class or 'unknown'}"
            f"/{item.evidence_specificity or 'unknown'}"
            f"/{item.evidence_quality_score if item.evidence_quality_score is not None else 'n/a'}"
        )
    if item.why_local_only or item.why_not_watchlist:
        rows.append(
            f"  opportunity_blocks: local={item.why_local_only or 'none'} "
            f"watchlist={item.why_not_watchlist or 'none'}"
        )
    return rows


def _candidate_discovery_funnel_lines(items: Iterable[EventImpactHypothesis]) -> list[str]:
    rows = list(items)
    executed = sum(
        1
        for item in rows
        for query in item.executed_queries
        if str(query.get("query_type") or "") == "candidate_discovery"
    )
    discovered = sum(
        len(tuple(item.crypto_candidate_assets or ())) + len(tuple(item.rejected_candidate_assets or ()))
        for item in rows
    )
    accepted = sum(
        1
        for item in rows
        for asset in item.crypto_candidate_assets
        if isinstance(asset, Mapping) and str(asset.get("source") or "").startswith("candidate_discovery")
    )
    rejected = sum(
        1
        for item in rows
        for asset in item.rejected_candidate_assets
        if isinstance(asset, Mapping) and str(asset.get("source") or "").startswith("candidate_discovery")
    )
    validated = sum(
        1
        for item in rows
        if item.status == HypothesisStatus.VALIDATED.value and item.validated_candidate_assets
    )
    promoted = sum(
        1
        for item in rows
        if item.status == HypothesisStatus.VALIDATED.value
        and item.opportunity_level in {"validated_digest", "watchlist", "high_priority"}
    )
    if not any((executed, discovered, accepted, rejected, validated, promoted)):
        return []
    return [
        "candidate_discovery_funnel: "
        f"executed_queries={executed}, discovered_terms={discovered}, "
        f"resolver_accepted={accepted}, resolver_rejected={rejected}, "
        f"validated={validated}, promoted={promoted}"
    ]
