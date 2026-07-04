"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (linkage)."""

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

def _unqualified_persistence_reason(link_quality: IncidentLinkQuality) -> str | None:
    if link_quality.qualified_watchlist_count > 0:
        return "qualified_watchlist_link"
    if link_quality.qualified_hypothesis_count > 0:
        return "qualified_hypothesis_link"
    if link_quality.quality_blocked_link_count > 0:
        return "quality_blocked_link_only"
    if link_quality.unknown_role_link_count > 0:
        return "unknown_role_link_only"
    if link_quality.generic_sector_only_link_count > 0:
        return "sector_only_unqualified_link"
    if link_quality.weak_link_count > 0:
        return "weak_unqualified_watchlist_link"
    return None
def _hypotheses_by_incident(hypotheses: Iterable[object]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for item in hypotheses:
        incident_id = _value(_object_row(item), "incident_id")
        if incident_id:
            out.setdefault(incident_id, []).append(item)
    return out
def _has_active_watchlist_row(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        state = str(
            row.get("final_state_after_quality_gate")
            or row.get("state")
            or ""
        ).strip().upper()
        if state in _ACTIVE_WATCHLIST_STATES or bool(row.get("should_alert")):
            return True
    return False
def _strong_sector_hypothesis(row: Mapping[str, Any], *, incident: event_incident_graph.CanonicalIncident) -> bool:
    level = _first_text(row.get("opportunity_level")).casefold()
    impact = _first_text(row.get("impact_path_type"), row.get("impact_category")).casefold()
    role = _first_text(row.get("candidate_role")).casefold()
    evidence = _first_text(row.get("evidence_specificity")).casefold()
    if level not in {"validated_digest", "watchlist", "high_priority"}:
        return False
    if impact in _BAD_IMPACT_PATHS or evidence == "insufficient_data":
        return False
    if role in _BAD_LINK_ROLES:
        return False
    return incident.event_archetype in _EXTERNAL_CATALYST_ARCHETYPES | _DIRECT_CRYPTO_ARCHETYPES
def _has_explicit_material_update(
    rows: Iterable[Mapping[str, Any]],
    *,
    incident: event_incident_graph.CanonicalIncident,
) -> bool:
    for row in rows:
        if _link_row_quality(row, incident=incident, source="watchlist")["quality_blocked"]:
            continue
        if row.get("material_change_reasons"):
            return True
        if bool(row.get("state_changed") or row.get("escalation")) and _has_active_watchlist_row((row,)):
            return True
    return False
def _watchlist_by_incident(watchlist_rows: Iterable[Mapping[str, Any] | object]) -> dict[str, list[Mapping[str, Any] | object]]:
    out: dict[str, list[Mapping[str, Any] | object]] = {}
    for item in watchlist_rows:
        row = _object_row(item)
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        incident_id = _value(row, "incident_id") or _value(components, "incident_id")
        if incident_id:
            out.setdefault(incident_id, []).append(item)
    return out
def _linked_assets(
    h_rows: list[dict[str, Any]],
    w_rows: list[dict[str, Any]],
    *,
    incident: event_incident_graph.CanonicalIncident | None = None,
) -> tuple[dict[str, Any], ...]:
    assets: list[dict[str, Any]] = []
    if incident is not None:
        for asset in incident.linked_assets:
            if asset.symbol or asset.coin_id:
                assets.append({
                    "symbol": asset.symbol,
                    "coin_id": asset.coin_id,
                    "role": asset.role,
                    "role_confidence": asset.confidence,
                    "source": "incident",
                    "evidence": tuple(asset.evidence),
                })
    for row in h_rows:
        role = _value(row, "candidate_role")
        validated_asset = row.get("validated_asset") if isinstance(row.get("validated_asset"), Mapping) else {}
        symbol = _value(row, "validated_symbol") or _value(validated_asset, "symbol")
        coin_id = _value(row, "validated_coin_id") or _value(validated_asset, "coin_id")
        validated_identity = bool(symbol or coin_id or validated_asset.get("validated"))
        if not symbol:
            symbols = row.get("candidate_symbols") or ()
            symbol = str(symbols[0]).upper() if symbols else ""
        if not coin_id:
            coin_ids = row.get("candidate_coin_ids") or ()
            coin_id = str(coin_ids[0]) if coin_ids else ""
        if symbol or coin_id:
            if not validated_identity:
                role = _safe_unvalidated_incident_asset_role(row, role)
            role = _incident_asset_role(
                symbol=symbol,
                coin_id=coin_id,
                role=role or "unknown",
                incident=incident,
            )
            assets.append({
                "symbol": symbol,
                "coin_id": coin_id,
                "role": role or "unknown",
                "role_confidence": row.get("role_confidence"),
                "source": "hypothesis" if validated_identity else "hypothesis_candidate_suggestion",
            })
    for row in w_rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        symbol = _value(row, "symbol") or _value(components, "validated_symbol")
        coin_id = _value(row, "coin_id") or _value(components, "validated_coin_id")
        role = _value(row, "candidate_role") or _value(components, "candidate_role")
        if symbol or coin_id:
            role = _incident_asset_role(
                symbol=symbol,
                coin_id=coin_id,
                role=role or "unknown",
                incident=incident,
            )
            assets.append({
                "symbol": symbol,
                "coin_id": coin_id,
                "role": role or "unknown",
                "role_confidence": row.get("role_confidence") or components.get("role_confidence"),
                "source": "watchlist",
            })
    return tuple(_unique_dicts(assets, keys=("symbol", "coin_id", "role")))
def _safe_unvalidated_incident_asset_role(row: Mapping[str, Any], role: str) -> str:
    strong_roles = {
        "direct_subject",
        "ecosystem_affected_asset",
        "proxy_venue",
        "proxy_instrument",
    }
    if role not in strong_roles:
        return role or "candidate_suggestion"
    source = str(row.get("candidate_source") or "").casefold()
    assets = row.get("crypto_candidate_assets") or ()
    has_taxonomy = "taxonomy" in source or any(
        isinstance(asset, Mapping) and str(asset.get("source") or "").casefold() == "taxonomy"
        for asset in assets
    )
    return "taxonomy_candidate" if has_taxonomy else "candidate_suggestion"
def _asset_roles(linked_assets: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "symbol": asset.get("symbol"),
            "coin_id": asset.get("coin_id"),
            "role": asset.get("role"),
            "confidence": asset.get("role_confidence"),
        }
        for asset in linked_assets
    )
