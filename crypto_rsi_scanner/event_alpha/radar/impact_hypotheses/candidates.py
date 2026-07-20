"""Impact-hypothesis candidate extraction helpers."""

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



def _candidate_asset_from_discovery_raw(raw: RawDiscoveredEvent) -> dict[str, Any] | None:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    title_body = " ".join(str(value or "") for value in (raw.title, raw.body))
    for key in ("candidate_asset", "asset", "market"):
        asset = payload.get(key) if isinstance(payload.get(key), Mapping) else {}
        row = _asset_row_from_mapping(asset, source="candidate_discovery_search", raw_id=raw.raw_id)
        if row:
            row.setdefault("source_title", raw.title)
            return row
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        confidence = _bounded_confidence(mention.get("confidence"))
        if confidence < 0.70:
            continue
        mention_type = clean_text(mention.get("mention_type"))
        if mention_type in {"publisher or source", "publisher_or_source", "ordinary word", "ordinary_word", "false positive"}:
            continue
        row = _asset_row_from_mapping(mention, source="candidate_discovery_search", raw_id=raw.raw_id)
        if row:
            row["confidence"] = round(confidence, 4)
            row.setdefault("source_title", raw.title)
            return row
    fallback = _candidate_asset_from_text(title_body, raw_id=raw.raw_id, title=raw.title)
    if fallback:
        return fallback
    return None


def _candidate_discovered_terms(asset: Mapping[str, Any], raw: RawDiscoveredEvent) -> tuple[str, ...]:
    terms: list[str] = []
    for key in ("symbol", "coin_id", "name", "contract_address"):
        value = str(asset.get(key) or "").strip()
        if value:
            terms.append(value)
    title = str(getattr(raw, "title", "") or "")
    if title:
        terms.append(title[:120])
    return tuple(dict.fromkeys(terms))


def _candidate_asset_from_text(text: str, *, raw_id: str, title: str) -> dict[str, Any] | None:
    clean = clean_text(text)
    if "velvet" in clean and any(term in clean for term in ("pre ipo", "pre-ipo", "spacex", "exposure", "crypto venue")):
        return {
            "source": "candidate_discovery_search",
            "raw_id": raw_id,
            "name": "Velvet",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "confidence": 0.82,
            "evidence": title,
            "source_title": title,
            "identity_reason": "explicit_project_name_with_proxy_context",
            "candidate_role_hint": "proxy_venue",
            "validated": False,
        }
    match = re.search(r"(?<![A-Z0-9])\$([A-Z]{2,10})(?![A-Z0-9])", text)
    if match:
        symbol = match.group(1).upper()
        return {
            "source": "candidate_discovery_search",
            "raw_id": raw_id,
            "symbol": symbol,
            "coin_id": symbol.lower(),
            "confidence": 0.72,
            "evidence": title,
            "source_title": title,
            "identity_reason": "cashtag_in_source_text",
            "validated": False,
        }
    match = re.search(r"(?<![A-Z0-9])([A-Z]{2,10})USDT(?![A-Z0-9])", text)
    if match:
        symbol = match.group(1).upper()
        return {
            "source": "candidate_discovery_search",
            "raw_id": raw_id,
            "symbol": symbol,
            "coin_id": symbol.lower(),
            "confidence": 0.76,
            "evidence": title,
            "source_title": title,
            "identity_reason": "explicit_trading_pair_in_source_text",
            "validated": False,
        }
    return None


def _asset_row_from_mapping(
    asset: Mapping[str, Any],
    *,
    source: str,
    raw_id: str,
) -> dict[str, Any] | None:
    symbol = str(asset.get("symbol") or asset.get("asset_symbol") or "").strip().upper()
    coin_id = str(asset.get("coin_id") or asset.get("id") or asset.get("asset_coin_id") or "").strip()
    name = str(asset.get("name") or asset.get("project_name") or "").strip()
    contract = str(asset.get("contract_address") or asset.get("address") or "").strip()
    if not any((symbol, coin_id, name, contract)):
        return None
    raw_confidence = asset.get("confidence")
    confidence = (
        0.75
        if raw_confidence is None or raw_confidence == ""
        else _bounded_confidence(raw_confidence)
    )
    return {
        "source": source,
        "raw_id": raw_id,
        "name": name,
        "symbol": symbol,
        "coin_id": coin_id,
        "contract_address": contract,
        "confidence": round(confidence, 4),
        "evidence": str(asset.get("evidence") or asset.get("evidence_quote") or ""),
        "source_title": str(asset.get("source_title") or asset.get("title") or ""),
        "role_source": str(asset.get("role_source") or event_identity.ROLE_SOURCE_LLM_SUGGESTION),
        "identity_confidence": round(confidence * 100.0, 2),
        "identity_evidence": tuple(str(value) for value in (asset.get("evidence") or asset.get("evidence_quote") or "", asset.get("title") or "") if str(value)),
        "validated": False,
    }


def _append_candidate_source(current: str, addition: str) -> str:
    parts = [part.strip() for part in str(current or "").replace("|", ",").split(",") if part.strip()]
    if addition not in parts:
        parts.append(addition)
    return ",".join(parts) or addition


def _with_promotion_diagnostics(
    hypothesis: EventImpactHypothesis,
    *,
    search_result: object | None = None,
) -> EventImpactHypothesis:
    hypothesis = _apply_frame_route_cap(hypothesis)
    reasons: list[str] = []
    path_digest_eligible = bool(getattr(hypothesis, "digest_eligible_by_impact_path", False))
    path_strength = str(getattr(hypothesis, "impact_path_strength", "") or "")
    path_type = str(getattr(hypothesis, "impact_path_type", "") or "")
    if (
        hypothesis.status == HypothesisStatus.VALIDATED.value
        and hypothesis.validation_stage in _PROMOTABLE_VALIDATION_STAGES
        and float(hypothesis.hypothesis_score or 0.0) >= 60.0
        and (
            path_digest_eligible
            or path_strength == "strong"
            or hypothesis.validation_stage != ValidationStage.CATALYST_LINK_VALIDATED.value
            or _impact_path_reason_is_strong(hypothesis.impact_path_reason)
        )
        and hypothesis.opportunity_level not in {"local_only", "exploratory"}
    ):
        return replace(hypothesis, why_not_promoted=())
    if not hypothesis.crypto_candidate_assets and not hypothesis.validated_candidate_assets:
        reasons.append("no_candidate_assets")
    samples = tuple(sample for sample in hypothesis.rejected_validation_samples if isinstance(sample, Mapping))
    if hypothesis.search_queries and not samples and not hypothesis.validation_reasons:
        reasons.append("no_validation_search_results")
    if samples and all(str(sample.get("query_type") or "") == "candidate_discovery" for sample in samples):
        reasons.append("candidate_discovery_only")
    if hypothesis.crypto_candidate_assets and not hypothesis.validated_candidate_assets and hypothesis.validation_stage not in _PROMOTABLE_VALIDATION_STAGES:
        reasons.append("candidate_identity_not_validated")
    if hypothesis.validation_stage not in _PROMOTABLE_VALIDATION_STAGES and hypothesis.impact_category != ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        reasons.append("catalyst_link_missing")
    if hypothesis.validation_stage in {
        ValidationStage.CATALYST_LINK_VALIDATED.value,
        ValidationStage.IDENTITY_VALIDATED.value,
    } and float((hypothesis.score_components or {}).get("market_confirmation") or 0.0) < 40.0:
        reasons.append("market_confirmation_missing")
    if (
        hypothesis.status == HypothesisStatus.VALIDATED.value
        and hypothesis.validation_stage == ValidationStage.CATALYST_LINK_VALIDATED.value
        and not path_digest_eligible
        and not _impact_path_reason_is_strong(hypothesis.impact_path_reason)
    ):
        reason = (
            hypothesis.why_digest_ineligible
            or hypothesis.impact_path_reason
            or ImpactPathReason.NO_VALUE_CAPTURE_EXPLAINED.value
        )
        reasons.append(f"impact_path_not_validated:{reason}")
    if path_type == "generic_cooccurrence_only":
        reasons.append("generic_cooccurrence_only")
    if hypothesis.why_digest_ineligible:
        reasons.append(str(hypothesis.why_digest_ineligible))
    if hypothesis.opportunity_level in {"local_only", "exploratory"}:
        reasons.append(f"opportunity_level:{hypothesis.opportunity_level}")
    if hypothesis.why_local_only:
        reasons.append(str(hypothesis.why_local_only))
    if hypothesis.why_not_watchlist:
        reasons.append(str(hypothesis.why_not_watchlist))
    warnings = tuple(str(item) for item in (*hypothesis.warnings, *(getattr(search_result, "warnings", ()) or ())) if str(item))
    if any("backoff" in warning.casefold() for warning in warnings):
        reasons.append("provider_backoff")
    if any("budget" in warning.casefold() for warning in warnings):
        reasons.append("llm_budget_exhausted")
    if float(hypothesis.hypothesis_score or 0.0) < 60.0:
        reasons.append("score_below_promotion_threshold")
    if hypothesis.rejection_reasons and not reasons:
        reasons.append("candidate_identity_not_validated")
    return replace(hypothesis, why_not_promoted=tuple(dict.fromkeys(reasons)))
