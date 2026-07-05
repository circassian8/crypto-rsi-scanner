"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (relevance)."""

from __future__ import annotations

import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
from .models import *  # noqa: F403

def classify_incident_relevance(
    incident: event_incident_graph.CanonicalIncident,
    *,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    hypotheses: Iterable[Mapping[str, Any] | object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    linked_assets: Iterable[Mapping[str, Any]] = (),
    market: Mapping[str, Any] | None = None,
    diagnostic_only: bool | None = None,
    subject_quality: str | None = None,
) -> dict[str, Any]:
    """Classify whether an incident is operationally crypto-relevant.

    This is metadata only. It controls local incident artifact visibility and
    doctor warnings; it cannot create candidates, alerts, trades, or fades.
    """
    h_rows = [_object_row(item) for item in hypotheses]
    w_rows = [_object_row(item) for item in watchlist_rows]
    assets = [dict(asset) for asset in linked_assets if isinstance(asset, Mapping)]
    market = dict(market or {})
    link_quality = classify_incident_link_quality(incident, h_rows, w_rows)
    text = _incident_source_text(incident, raw_by_id)
    market_like = (
        incident.event_archetype in {"market_dislocation_unknown", "market_anomaly"}
        or "market anomaly" in str(incident.canonical_name or "").casefold()
    )
    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0

    if diagnostic_only or str(subject_quality or incident.subject_quality or "") in {"invalid", "diagnostic_only"}:
        return {
            "incident_relevance_status": RELEVANCE_DIAGNOSTIC_ONLY,
            "incident_relevance_score": 0.0,
            "incident_relevance_reasons": ("invalid_or_diagnostic_subject",),
            "incident_relevance_warnings": ("incident_hidden_from_default_report",),
            "canonical_persistence_reason": "diagnostic_subject_only",
            **link_quality.as_dict(),
        }

    if h_rows:
        reasons.append("linked_to_event_impact_hypothesis")
        score += 45.0
    if w_rows:
        reasons.append("linked_to_watchlist_row")
        score += 35.0
    if _has_active_watchlist_row(w_rows):
        reasons.append("active_watchlist_lifecycle_state")
        score += 20.0
    if _has_crypto_asset_link(assets):
        reasons.append("linked_to_validated_crypto_candidate")
        score += 22.0
    if market_like or bool(market.get("market_reaction_observed")):
        reasons.append("market_dislocation_or_market_reaction")
        score += 25.0
    if incident.event_archetype in _DIRECT_CRYPTO_ARCHETYPES and _crypto_specific_text(text, incident=incident, assets=assets):
        reasons.append(f"crypto_specific_{incident.event_archetype}")
        score += 20.0
    elif incident.event_archetype in _DIRECT_CRYPTO_ARCHETYPES:
        reasons.append(f"incident_candidate_{incident.event_archetype}")
        score += 12.0
    if incident.event_archetype in _EXTERNAL_CATALYST_ARCHETYPES:
        if h_rows or _has_crypto_asset_link(assets) or _crypto_specific_text(text, incident=incident, assets=assets):
            reasons.append(f"crypto_linked_external_catalyst:{incident.event_archetype}")
            score += 18.0
        else:
            reasons.append(f"external_catalyst_candidate:{incident.event_archetype}")
            score += 10.0
    if _crypto_specific_text(text, incident=incident, assets=assets):
        reasons.append("crypto_specific_source_evidence")
        score += 12.0
    if _high_quality_external_candidate(incident, raw_by_id, h_rows):
        reasons.append("high_quality_external_catalyst_with_candidate_context")
        score += 10.0

    reasons.extend(link_quality.link_quality_reasons)
    warnings.extend(link_quality.link_quality_warnings)

    has_qualified_link = link_quality.qualified_link_count > 0
    has_valid_crypto_specific_link = _has_crypto_asset_link(assets) and link_quality.unknown_role_link_count < max(1, link_quality.raw_link_count)
    has_material_update = _has_explicit_material_update(w_rows, incident=incident)

    if has_qualified_link and (link_quality.qualified_watchlist_count > 0 or link_quality.qualified_hypothesis_count > 0):
        status = RELEVANCE_ACTIVE_INCIDENT
        persistence = "qualified_watchlist_link" if link_quality.qualified_watchlist_count > 0 else "qualified_hypothesis_link"
        score = max(score, 90.0 if link_quality.qualified_watchlist_count > 0 else 84.0)
    elif has_material_update:
        status = RELEVANCE_ACTIVE_INCIDENT
        persistence = "explicit_active_material_update"
        score = max(score, 86.0)
    elif has_valid_crypto_specific_link:
        status = RELEVANCE_LINKED_INCIDENT
        persistence = "valid_crypto_specific_link"
        score = max(score, 74.0)
    elif (
        _has_crypto_asset_link(assets)
        or market_like
        or bool(market.get("market_reaction_observed"))
        or (
            incident.event_archetype in _DIRECT_CRYPTO_ARCHETYPES
            and _crypto_specific_text(text, incident=incident, assets=assets)
        )
    ):
        status = RELEVANCE_CANONICAL_INCIDENT
        persistence = (
            "market_dislocation"
            if market_like or bool(market.get("market_reaction_observed"))
            else "crypto_specific_incident"
        )
        score = max(score, 68.0)
    elif incident.event_archetype in _EXTERNAL_CATALYST_ARCHETYPES or incident.event_archetype in _DIRECT_CRYPTO_ARCHETYPES:
        status = RELEVANCE_INCIDENT_CANDIDATE
        persistence = _unqualified_persistence_reason(link_quality) or "recognized_research_catalyst_candidate"
        score = max(score, 52.0)
    elif _is_external_context_incident(incident, text):
        status = RELEVANCE_EXTERNAL_CONTEXT_ONLY
        persistence = _unqualified_persistence_reason(link_quality) or "external_context_without_crypto_link"
        score = min(max(score, 28.0), 40.0)
        warnings.append("incident_hidden_from_default_report")
        reasons.append("external_context_without_crypto_hypothesis_watchlist_asset_or_market_link")
    else:
        status = RELEVANCE_RAW_OBSERVATION
        persistence = _unqualified_persistence_reason(link_quality) or "raw_observation_without_crypto_link"
        score = min(score, 35.0)
        warnings.append("incident_hidden_from_default_report")
        if not reasons:
            reasons.append("no_crypto_hypothesis_watchlist_asset_or_market_link")
    if status == RELEVANCE_INCIDENT_CANDIDATE and link_quality.raw_link_count > 0 and link_quality.qualified_link_count <= 0:
        score = min(max(score, 52.0), 60.0)

    return {
        "incident_relevance_status": status,
        "incident_relevance_score": round(max(0.0, min(100.0, score)), 2),
        "incident_relevance_reasons": tuple(dict.fromkeys(reasons)),
        "incident_relevance_warnings": tuple(dict.fromkeys(warnings)),
        "canonical_persistence_reason": persistence,
        **link_quality.as_dict(),
    }
def _debug_allows_diagnostic(*, profile: str | None, run_mode: str | None) -> bool:
    mode = str(run_mode or "").strip().casefold()
    prof = str(profile or "").strip().casefold()
    return mode in {"test", "fixture", "replay"} or prof in {"fixture", "quality_validation"}
def _should_persist_incident_row(
    row: Mapping[str, Any],
    *,
    store_diagnostic: bool,
    store_raw_observations: bool,
) -> bool:
    status = str(row.get("incident_relevance_status") or "").strip()
    if status in _VISIBLE_RELEVANCE_STATUSES:
        return True
    if status in _RAW_RELEVANCE_STATUSES:
        return bool(store_raw_observations)
    if bool(row.get("diagnostic_only")) or status in _STRICT_DIAGNOSTIC_RELEVANCE_STATUSES:
        return bool(store_diagnostic)
    return True
def _is_diagnostic_relevance(row: Mapping[str, Any]) -> bool:
    return _is_hidden_relevance(
        row,
        include_diagnostic=False,
        include_raw=False,
        include_external_context=False,
    )
def _is_hidden_relevance(
    row: Mapping[str, Any],
    *,
    include_diagnostic: bool,
    include_raw: bool,
    include_external_context: bool,
) -> bool:
    status = str(row.get("incident_relevance_status") or "").strip()
    if _is_strict_diagnostic_relevance(row):
        return not include_diagnostic
    if status == RELEVANCE_RAW_OBSERVATION:
        return not include_raw
    if status == RELEVANCE_EXTERNAL_CONTEXT_ONLY:
        return not include_external_context
    return False
def _is_strict_diagnostic_relevance(row: Mapping[str, Any]) -> bool:
    status = str(row.get("incident_relevance_status") or "").strip()
    return bool(row.get("diagnostic_only")) or status in _STRICT_DIAGNOSTIC_RELEVANCE_STATUSES
def _is_raw_observation_relevance(row: Mapping[str, Any]) -> bool:
    return str(row.get("incident_relevance_status") or "").strip() == RELEVANCE_RAW_OBSERVATION
def _is_external_context_relevance(row: Mapping[str, Any]) -> bool:
    return str(row.get("incident_relevance_status") or "").strip() == RELEVANCE_EXTERNAL_CONTEXT_ONLY
def _status_hidden_by_default(status: str) -> bool:
    return status in _DIAGNOSTIC_RELEVANCE_STATUSES
def _is_operational_canonical_relevance(row: Mapping[str, Any]) -> bool:
    return str(row.get("incident_relevance_status") or "") in {
        RELEVANCE_CANONICAL_INCIDENT,
        RELEVANCE_LINKED_INCIDENT,
        RELEVANCE_ACTIVE_INCIDENT,
    }
def _is_external_context_incident(incident: event_incident_graph.CanonicalIncident, text: str) -> bool:
    archetype = str(incident.event_archetype or "").strip()
    if archetype in _EXTERNAL_CONTEXT_ARCHETYPES:
        return True
    lowered = str(text or "").casefold()
    external_terms = (
        "polymarket",
        "prediction market",
        "election",
        "world cup",
        "champions league",
        "geopolitical",
        "putin",
        "trump",
        "macron",
        "netanyahu",
        "annexation",
        "ceasefire",
        "hamas",
        "next james bond",
    )
    crypto_terms = (
        "tokenized stock",
        "pre-ipo",
        "crypto venue",
        "fan token",
        "perp",
        "futures",
        "airdrop",
        "unlock",
        "listing",
        "exploit",
    )
    return any(term in lowered for term in external_terms) and not any(term in lowered for term in crypto_terms)
def _api_external_context_text(text: str) -> bool:
    lowered = str(text or "").casefold()
    external_terms = (
        "annexation",
        "benjamin netanyahu",
        "hamas",
        "israel",
        "macron",
        "next james bond",
        "putin",
        "trump",
        "world cup",
    )
    return any(term in lowered for term in external_terms)
def _is_sector_identity(*, symbol: str, coin_id: str) -> bool:
    symbol_key = symbol.upper()
    coin_key = coin_id.casefold()
    if symbol_key in {"SECTOR", "UNKNOWN"}:
        return True
    if not symbol_key and coin_key in {"", "sector", "unknown", "market_anomaly_unknown"}:
        return True
    return coin_key in {
        "sector",
        "unknown",
        "market_anomaly_unknown",
        "sports_fan_proxy",
        "political_meme_proxy",
        "ai_ipo_proxy",
        "rwa_preipo_proxy",
        "tokenized_stock_venue",
        "prediction_market_infra",
    }
def _row_with_effective_relevance(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    status = str(data.get("incident_relevance_status") or "").strip()
    if status:
        _ensure_existing_link_quality(data)
        if status in {RELEVANCE_ACTIVE_INCIDENT, RELEVANCE_LINKED_INCIDENT} and int(data.get("qualified_link_count") or 0) <= 0:
            status, reason = _downgraded_relevance_for_unqualified_links(data)
            data["incident_relevance_status"] = status
            data["canonical_persistence_reason"] = reason
            reasons = [str(item) for item in data.get("incident_relevance_reasons") or () if str(item or "").strip()]
            if reason not in reasons:
                reasons.append(reason)
            data["incident_relevance_reasons"] = tuple(reasons)
            warnings = [str(item) for item in data.get("incident_relevance_warnings") or () if str(item or "").strip()]
            if "incident_link_not_quality_qualified" not in warnings:
                warnings.append("incident_link_not_quality_qualified")
            data["incident_relevance_warnings"] = tuple(warnings)
            if status in _RAW_RELEVANCE_STATUSES:
                data["incident_relevance_score"] = min(_float(data.get("incident_relevance_score")), 40.0)
            else:
                data["incident_relevance_score"] = min(_float(data.get("incident_relevance_score")), 60.0)
        data["raw_observation"] = status == RELEVANCE_RAW_OBSERVATION
        data["external_context_only"] = status == RELEVANCE_EXTERNAL_CONTEXT_ONLY
        data["external_context_hidden_by_default"] = status == RELEVANCE_EXTERNAL_CONTEXT_ONLY
        data["diagnostic_hidden_by_default"] = _is_diagnostic_relevance(data)
        return data
    diagnostic = bool(data.get("diagnostic_only")) or str(data.get("incident_subject_quality") or "") == "diagnostic_only"
    linked_h = bool(data.get("linked_hypothesis_ids"))
    linked_w = bool(data.get("linked_watchlist_keys"))
    market_observed = bool(data.get("market_reaction_observed") or data.get("market_reaction_confirmed"))
    archetype = str(data.get("event_archetype") or "")
    assets = data.get("linked_assets") or ()
    source_text = " ".join(str(data.get(key) or "") for key in (
        "canonical_name",
        "event_archetype",
        "primary_subject",
        "affected_ecosystem",
    ))
    if diagnostic:
        status = RELEVANCE_DIAGNOSTIC_ONLY
        reason = "legacy_diagnostic_subject"
    elif linked_w:
        status = RELEVANCE_ACTIVE_INCIDENT
        reason = "legacy_linked_watchlist"
    elif linked_h:
        status = RELEVANCE_LINKED_INCIDENT
        reason = "legacy_linked_hypothesis"
    elif market_observed or archetype == "market_dislocation_unknown" or _has_crypto_asset_link(
        asset for asset in assets if isinstance(asset, Mapping)
    ):
        status = RELEVANCE_CANONICAL_INCIDENT
        reason = "legacy_crypto_or_market_relevance"
    elif archetype in _EXTERNAL_CATALYST_ARCHETYPES or archetype in _DIRECT_CRYPTO_ARCHETYPES:
        status = RELEVANCE_INCIDENT_CANDIDATE
        reason = "legacy_recognized_research_catalyst_candidate"
    elif archetype in _EXTERNAL_CONTEXT_ARCHETYPES or _api_external_context_text(source_text):
        status = RELEVANCE_EXTERNAL_CONTEXT_ONLY
        reason = "legacy_external_context_without_crypto_link"
    else:
        status = RELEVANCE_RAW_OBSERVATION
        reason = "legacy_raw_observation_without_crypto_link"
    data["incident_relevance_status"] = status
    data.setdefault(
        "incident_relevance_score",
        0.0 if diagnostic else (35.0 if status in _RAW_RELEVANCE_STATUSES else 60.0),
    )
    data.setdefault("incident_relevance_reasons", (reason,))
    data.setdefault("incident_relevance_warnings", () if not diagnostic else ("incident_hidden_from_default_report",))
    data.setdefault("canonical_persistence_reason", reason)
    data.setdefault("raw_observation", status == RELEVANCE_RAW_OBSERVATION)
    data.setdefault("external_context_only", status == RELEVANCE_EXTERNAL_CONTEXT_ONLY)
    data.setdefault("external_context_hidden_by_default", status == RELEVANCE_EXTERNAL_CONTEXT_ONLY)
    data.setdefault("diagnostic_hidden_by_default", _is_diagnostic_relevance(data))
    _ensure_existing_link_quality(data)
    if status in {RELEVANCE_ACTIVE_INCIDENT, RELEVANCE_LINKED_INCIDENT} and int(data.get("qualified_link_count") or 0) <= 0:
        status, reason = _downgraded_relevance_for_unqualified_links(data)
        data["incident_relevance_status"] = status
        data["canonical_persistence_reason"] = reason
        reasons = [str(item) for item in data.get("incident_relevance_reasons") or () if str(item or "").strip()]
        if reason not in reasons:
            reasons.append(reason)
        data["incident_relevance_reasons"] = tuple(reasons)
        warnings = [str(item) for item in data.get("incident_relevance_warnings") or () if str(item or "").strip()]
        if "incident_link_not_quality_qualified" not in warnings:
            warnings.append("incident_link_not_quality_qualified")
        data["incident_relevance_warnings"] = tuple(warnings)
        if status in _RAW_RELEVANCE_STATUSES:
            data["incident_relevance_score"] = min(_float(data.get("incident_relevance_score")), 40.0)
        else:
            data["incident_relevance_score"] = min(_float(data.get("incident_relevance_score")), 60.0)
        data["raw_observation"] = status == RELEVANCE_RAW_OBSERVATION
        data["external_context_only"] = status == RELEVANCE_EXTERNAL_CONTEXT_ONLY
        data["external_context_hidden_by_default"] = status == RELEVANCE_EXTERNAL_CONTEXT_ONLY
        data["diagnostic_hidden_by_default"] = _is_diagnostic_relevance(data)
    return data
def _downgraded_relevance_for_unqualified_links(row: Mapping[str, Any]) -> tuple[str, str]:
    archetype = str(row.get("event_archetype") or "")
    source_text = " ".join(str(row.get(key) or "") for key in (
        "canonical_name",
        "event_archetype",
        "primary_subject",
        "affected_ecosystem",
    ))
    reason = _api_unqualified_reason(row)
    if archetype in _EXTERNAL_CONTEXT_ARCHETYPES or _api_external_context_text(source_text):
        return RELEVANCE_EXTERNAL_CONTEXT_ONLY, reason or "external_context_without_crypto_link"
    if archetype in _EXTERNAL_CATALYST_ARCHETYPES or archetype in _DIRECT_CRYPTO_ARCHETYPES:
        return RELEVANCE_INCIDENT_CANDIDATE, reason or "recognized_research_catalyst_candidate"
    if bool(row.get("market_reaction_observed") or row.get("market_reaction_confirmed")) or archetype == "market_dislocation_unknown":
        return RELEVANCE_CANONICAL_INCIDENT, "market_dislocation"
    return RELEVANCE_RAW_OBSERVATION, reason or "raw_observation_without_crypto_link"
def _api_unqualified_reason(row: Mapping[str, Any]) -> str | None:
    if int(row.get("quality_blocked_link_count") or 0) > 0:
        return "quality_blocked_link_only"
    if int(row.get("unknown_role_link_count") or 0) > 0:
        return "unknown_role_link_only"
    if int(row.get("generic_sector_only_link_count") or 0) > 0:
        return "sector_only_unqualified_link"
    if int(row.get("weak_link_count") or 0) > 0:
        return "weak_unqualified_watchlist_link"
    return None
def _is_garbage_incident_subject(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    text = " ".join(text.replace("-", " ").replace("_", " ").split())
    if not text:
        return False
    if text in _GARBAGE_INCIDENT_SUBJECTS:
        return True
    if "invite code" in text or "referral code" in text:
        return True
    if text.startswith("best ") and text.endswith(" apps"):
        return True
    if text.endswith(" are") and " and " in text:
        return True
    return False
