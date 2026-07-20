"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (canonical)."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
from crypto_rsi_scanner.event_alpha.radar.source_independence import (
    validate_source_independence_container,
    validated_source_independence_container,
)
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
from .models import *  # noqa: F403
from .relevance import _incident_flag_true

def _row_from_incident(
    incident: event_incident_graph.CanonicalIncident,
    *,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    observed_at: str,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
    hypotheses: Iterable[object],
    watchlist_rows: Iterable[Mapping[str, Any] | object],
) -> dict[str, Any]:
    h_rows = [_object_row(item) for item in hypotheses]
    w_rows = [_object_row(item) for item in watchlist_rows]
    linked_assets = _linked_assets(h_rows, w_rows, incident=incident)
    market = _incident_market_context(h_rows, w_rows, incident=incident, raw_by_id=raw_by_id)
    claim_history = [_claim_summary(claim) for claim in incident.claim_history[:12]]
    source_urls = tuple(sorted({raw_by_id[raw_id].source_url for raw_id in incident.raw_ids if raw_id in raw_by_id and raw_by_id[raw_id].source_url}))
    current_polarities = tuple(dict.fromkeys(
        str(claim.polarity) for claim in incident.claim_history if str(claim.polarity)
    ))
    subject_validation = event_incident_graph.validate_incident_primary_subject(
        incident.primary_subject,
        {
            "external_asset": incident.affected_ecosystem,
        },
    )
    diagnostic_only = bool(incident.diagnostic_only and not h_rows and not w_rows)
    subject_quality = "diagnostic_only" if diagnostic_only else incident.subject_quality
    primary_subject = incident.primary_subject
    subject_quality_reason = incident.subject_quality_reason
    subject_warnings = tuple(incident.warnings)
    if subject_validation.status == "fallback_used" and subject_validation.normalized_subject:
        primary_subject = subject_validation.normalized_subject
        subject_quality = "fallback_used"
        subject_quality_reason = subject_validation.fallback_source or "incident_store_subject_fallback"
        subject_warnings = tuple(dict.fromkeys((*subject_warnings, *subject_validation.warnings)))
    elif subject_validation.status in {"invalid_subject", "diagnostic_only", "external_context_only"}:
        primary_subject = subject_validation.normalized_subject
        subject_quality = "diagnostic_only"
        subject_quality_reason = subject_validation.rejection_reason or "garbage_primary_subject_quarantined"
        diagnostic_only = True
        subject_warnings = tuple(dict.fromkeys((*subject_warnings, *subject_validation.warnings)))
    relevance = classify_incident_relevance(
        incident,
        raw_by_id=raw_by_id,
        hypotheses=h_rows,
        watchlist_rows=w_rows,
        linked_assets=linked_assets,
        market=market,
        diagnostic_only=diagnostic_only,
        subject_quality=subject_quality,
    )
    relevance_status = str(relevance["incident_relevance_status"])
    diagnostic_only = bool(diagnostic_only or relevance_status in _STRICT_DIAGNOSTIC_RELEVANCE_STATUSES)
    source_independence_fields = _incident_source_independence_row_fields(incident)
    if diagnostic_only and subject_quality == "valid":
        subject_quality = "diagnostic_only"
    hidden_by_default = _status_hidden_by_default(relevance_status) or diagnostic_only
    row = {
        "schema_version": INCIDENT_STORE_SCHEMA_VERSION,
        "row_type": "event_incident",
        "observed_at": observed_at,
        "run_id": run_id,
        "profile": profile or "default",
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "incident_id": incident.incident_id,
        "canonical_name": incident.canonical_name,
        "event_archetype": incident.event_archetype,
        "primary_subject": primary_subject,
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
        "frame_summary": tuple(incident.frame_summary),
        "background_context_summary": incident.background_context_summary,
        "rule_predicted_impact_path": incident.rule_predicted_impact_path,
        "llm_predicted_main_frame_type": incident.llm_predicted_main_frame_type,
        "frame_rule_disagreement": incident.frame_rule_disagreement,
        "disagreement_resolution": incident.disagreement_resolution,
        "selected_main_catalyst_reason": incident.selected_main_catalyst_reason,
        "incident_subject_quality": subject_quality,
        "incident_subject_quality_reason": subject_quality_reason,
        "diagnostic_only": diagnostic_only,
        "incident_relevance_status": relevance["incident_relevance_status"],
        "incident_relevance_score": relevance["incident_relevance_score"],
        "incident_relevance_reasons": relevance["incident_relevance_reasons"],
        "incident_relevance_warnings": relevance["incident_relevance_warnings"],
        "canonical_persistence_reason": relevance["canonical_persistence_reason"],
        "raw_link_count": relevance["raw_link_count"],
        "qualified_link_count": relevance["qualified_link_count"],
        "qualified_hypothesis_count": relevance["qualified_hypothesis_count"],
        "qualified_watchlist_count": relevance["qualified_watchlist_count"],
        "weak_link_count": relevance["weak_link_count"],
        "quality_blocked_link_count": relevance["quality_blocked_link_count"],
        "unknown_role_link_count": relevance["unknown_role_link_count"],
        "generic_sector_only_link_count": relevance["generic_sector_only_link_count"],
        "link_quality_reasons": relevance["link_quality_reasons"],
        "link_quality_warnings": relevance["link_quality_warnings"],
        "diagnostic_hidden_by_default": hidden_by_default,
        "raw_observation": relevance_status == RELEVANCE_RAW_OBSERVATION,
        "external_context_only": relevance_status == RELEVANCE_EXTERNAL_CONTEXT_ONLY,
        "external_context_hidden_by_default": relevance_status == RELEVANCE_EXTERNAL_CONTEXT_ONLY,
        "affected_ecosystem": incident.affected_ecosystem,
        "external_entities": _unique(_flatten_values(h_rows, "external_entities", fallback="external_asset")),
        "crypto_entities": _unique(_crypto_entities(h_rows, w_rows)),
        "first_seen_at": _iso(incident.first_seen_at),
        "last_updated_at": _iso(incident.last_updated_at),
        "current_cause_status": incident.current_cause_status,
        "current_claim_polarities": current_polarities,
        "claim_history": claim_history,
        "conflicting_claims": tuple(incident.conflicting_claims),
        "source_raw_ids": tuple(incident.raw_ids),
        "source_event_ids": tuple(incident.event_ids),
        "source_urls": source_urls[:12],
        "source_domains": tuple(incident.source_domains),
        "source_domain_count": len(incident.source_domains),
        **source_independence_fields,
        "source_update_count": len(incident.raw_ids),
        "linked_hypothesis_ids": _unique(row.get("hypothesis_id") for row in h_rows),
        "linked_watchlist_keys": _unique(row.get("key") for row in w_rows),
        "linked_assets": linked_assets,
        "asset_roles": _asset_roles(linked_assets),
        "material_update_reasons": _unique(_flatten_values(w_rows, "material_change_reasons")),
        "market_reaction_observed": market["market_reaction_observed"],
        "market_reaction_confirmed": market["market_reaction_confirmed"],
        "market_reaction_level": market["market_reaction_level"],
        "causal_mechanism_confirmed": market["causal_mechanism_confirmed"],
        "market_context_source": market["market_context_source"],
        "market_context_asset": market["market_context_asset"],
        "market_context_age": market["market_context_age"],
        "incident_confidence": _incident_confidence(incident, h_rows, market),
        "warnings": tuple(dict.fromkeys([
            *subject_warnings,
            *_incident_warnings(incident, market),
            *relevance["incident_relevance_warnings"],
        ])),
    }
    return row


def _incident_source_independence_row_fields(
    incident: event_incident_graph.CanonicalIncident,
) -> dict[str, Any]:
    contract = _validated_source_independence(incident)
    container = _incident_source_independence_container(incident)
    errors = list(
        dict.fromkeys(
            (*incident.source_independence_errors, *validate_source_independence_container(container))
        )
    )
    return {
        "independent_source_domains": tuple(incident.independent_source_domains),
        "independent_source_domain_count": len(incident.independent_source_domains),
        "independent_source_count": int(
            contract.get("independent_evidence_count") or 0
        ),
        "independent_corroboration_count": int(
            contract.get("independent_corroboration_count") or 0
        ),
        "source_content_cluster_count": int(
            contract.get("content_cluster_count") or 0
        ),
        "source_independence": contract,
        "source_independence_errors": errors,
        "source_independence_status": (
            "assessed" if contract else "rejected" if errors else "unassessed"
        ),
    }


def _incident_source_text(
    incident: event_incident_graph.CanonicalIncident,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
) -> str:
    parts = [incident.canonical_name, incident.event_archetype, incident.primary_subject or "", incident.affected_ecosystem or ""]
    for raw_id in incident.raw_ids:
        raw = raw_by_id.get(raw_id)
        if raw is None:
            continue
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        parts.extend([
            raw.provider,
            raw.title,
            raw.body or "",
            str(payload.get("source_origin") or ""),
            str(payload.get("impact_category") or ""),
        ])
    return " ".join(str(part or "") for part in parts)
def _incident_asset_role(
    *,
    symbol: str,
    coin_id: str,
    role: str,
    incident: event_incident_graph.CanonicalIncident | None,
) -> str:
    if incident is None or incident.event_archetype != "market_dislocation_unknown":
        return role
    clean_symbol = str(symbol or "").strip().casefold()
    clean_coin = str(coin_id or "").strip().casefold()
    if clean_symbol == "sector" or clean_coin in {"market_anomaly_unknown", "sector", "unknown"}:
        return "sector_context"
    return role
def _material_reason_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in row.get("material_update_reasons") or ():
            key = str(reason or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts
def _incident_market_context(
    h_rows: list[dict[str, Any]],
    w_rows: list[dict[str, Any]],
    *,
    incident: event_incident_graph.CanonicalIncident | None = None,
    raw_by_id: Mapping[str, RawDiscoveredEvent] | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in [*h_rows, *w_rows]:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        merged = {**dict(components), **row}
        if merged.get("market_reaction_confirmed") is not None or merged.get("market_context_source"):
            candidates.append(merged)
    if incident is not None and raw_by_id is not None:
        for raw_id in incident.raw_ids:
            raw = raw_by_id.get(raw_id)
            payload = raw.raw_json if raw is not None and isinstance(raw.raw_json, Mapping) else {}
            market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
            anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
            if not market and not anomaly:
                continue
            candidates.append({
                "market_reaction_confirmed": False,
                "causal_mechanism_confirmed": False,
                "market_context_source": "raw_market_anomaly_snapshot" if anomaly else "raw_market_snapshot",
                "market_context_asset": market.get("symbol") or market.get("coin_id") or market.get("id"),
                "market_confirmation_level": "observed",
                "market_confirmation_score": _raw_market_confirmation_score(
                    anomaly,
                    market,
                ),
            })
    if not candidates:
        return {
            "market_reaction_observed": False,
            "market_reaction_confirmed": False,
            "market_reaction_level": "insufficient_data",
            "causal_mechanism_confirmed": False,
            "market_context_source": None,
            "market_context_asset": None,
            "market_context_age": None,
        }
    best = sorted(
        candidates,
        key=lambda row: _bounded_market_confirmation_score(
            row.get("market_confirmation_score")
        ),
        reverse=True,
    )[0]
    reaction_observed = any(
        _incident_flag_true(row.get("market_reaction_confirmed"))
        or bool(row.get("market_context_source"))
        or _bounded_market_confirmation_score(
            row.get("market_confirmation_score")
        ) > 0
        or str(row.get("market_confirmation_level") or "").casefold() in {"weak", "moderate", "strong"}
        for row in candidates
    )
    return {
        "market_reaction_observed": reaction_observed,
        "market_reaction_confirmed": any(
            _incident_flag_true(row.get("market_reaction_confirmed"))
            for row in candidates
        ),
        "market_reaction_level": _value(best, "market_confirmation_level") or "unknown",
        "causal_mechanism_confirmed": any(
            _incident_flag_true(row.get("causal_mechanism_confirmed"))
            for row in candidates
        ),
        "market_context_source": _value(best, "market_context_source"),
        "market_context_asset": _value(best, "market_context_asset") or _value(best, "validated_symbol") or _value(best, "symbol") or _value(best, "coin_id"),
        "market_context_age": _nonnegative_finite(
            best.get("market_context_age_seconds")
        ),
    }


def _raw_market_confirmation_score(
    anomaly: Mapping[str, Any],
    market: Mapping[str, Any],
) -> float:
    """Return one raw context score without hiding explicit invalid evidence."""

    for source, field in ((anomaly, "score"), (market, "anomaly_score")):
        if field not in source:
            continue
        value = source.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        return _bounded_market_confirmation_score(value)
    return 1.0


def _bounded_market_confirmation_score(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 100.0:
        return 0.0
    return parsed


def _nonnegative_finite(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def _incident_confidence(
    incident: event_incident_graph.CanonicalIncident,
    h_rows: list[dict[str, Any]],
    market: Mapping[str, Any],
) -> float:
    source_independence = _validated_source_independence(incident)
    independent_evidence = int(source_independence.get("independent_evidence_count") or 0)
    score = 35.0 + independent_evidence * 28.0
    if incident.current_cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value:
        score += 12.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.SUSPECTED.value:
        score -= 5.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.RULED_OUT.value:
        score -= 8.0
    if market.get("market_reaction_confirmed"):
        score += 5.0
    if market.get("causal_mechanism_confirmed"):
        score += 10.0
    if any(row.get("conflicting_claims") for row in h_rows) or incident.conflicting_claims:
        score -= 10.0
    return round(max(0.0, min(100.0, score)), 2)


def _validated_source_independence(
    incident: event_incident_graph.CanonicalIncident,
) -> dict[str, Any]:
    return validated_source_independence_container(
        _incident_source_independence_container(incident)
    )


def _incident_source_independence_container(
    incident: event_incident_graph.CanonicalIncident,
) -> dict[str, Any]:
    errors = list(incident.source_independence_errors)
    contract = incident.source_independence
    status = "rejected" if errors else "assessed" if contract else "unassessed"
    return {
        "source_independence": contract,
        "source_independence_status": status,
        "source_independence_errors": errors,
        "independent_source_count": incident.independent_source_count,
        "independent_corroboration_count": incident.independent_corroboration_count,
        "source_content_cluster_count": incident.source_content_cluster_count,
    }
def _incident_warnings(
    incident: event_incident_graph.CanonicalIncident,
    market: Mapping[str, Any],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if incident.conflicting_claims:
        warnings.append("conflicting_claims_present")
    if market.get("market_reaction_confirmed") and incident.current_cause_status in {"unknown", "ruled_out"}:
        warnings.append("market_reaction_without_confirmed_cause")
    if incident.current_cause_status == "confirmed" and not market.get("market_context_source"):
        warnings.append("confirmed_cause_missing_market_context")
    return tuple(warnings)
def _claim_summary(claim: event_claim_semantics.EventClaim) -> dict[str, Any]:
    return {
        "claim_type": claim.claim_type,
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "polarity": claim.polarity,
        "cause_status": claim.cause_status,
        "confidence": claim.confidence,
        "evidence_quote": claim.evidence_quote,
    }
