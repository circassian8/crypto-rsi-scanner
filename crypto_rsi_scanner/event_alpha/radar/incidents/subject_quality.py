"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (subject_quality)."""

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
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
from .models import *  # noqa: F403

def classify_incident_link_quality(
    incident: event_incident_graph.CanonicalIncident,
    linked_hypotheses: Iterable[Mapping[str, Any] | object] = (),
    linked_watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
) -> IncidentLinkQuality:
    """Summarize whether incident links are quality-qualified crypto links.

    This is artifact metadata only. It does not create candidates, alerts,
    notifications, trades, or event-fade triggers.
    """
    h_rows = [_object_row(item) for item in linked_hypotheses]
    w_rows = [_object_row(item) for item in linked_watchlist_rows]
    raw_link_count = len(h_rows) + len(w_rows)
    qualified_hypothesis = 0
    qualified_watchlist = 0
    quality_blocked = 0
    unknown_role = 0
    sector_only = 0
    reasons: list[str] = []
    warnings: list[str] = []

    for row in h_rows:
        result = _link_row_quality(row, incident=incident, source="hypothesis")
        if result["qualified"]:
            qualified_hypothesis += 1
            reasons.append("qualified_hypothesis_link")
        else:
            reasons.extend(result["reasons"])
            warnings.extend(result["warnings"])
            quality_blocked += int(result["quality_blocked"])
            unknown_role += int(result["unknown_role"])
            sector_only += int(result["sector_only"])
    for row in w_rows:
        result = _link_row_quality(row, incident=incident, source="watchlist")
        if result["qualified"]:
            qualified_watchlist += 1
            reasons.append("qualified_watchlist_link")
        else:
            reasons.extend(result["reasons"])
            warnings.extend(result["warnings"])
            quality_blocked += int(result["quality_blocked"])
            unknown_role += int(result["unknown_role"])
            sector_only += int(result["sector_only"])

    qualified = qualified_hypothesis + qualified_watchlist
    weak = max(0, raw_link_count - qualified)
    if raw_link_count == 0:
        reasons.append("no_incident_links")
    elif qualified == 0:
        if quality_blocked:
            reasons.append("quality_blocked_link_only")
        if unknown_role and unknown_role >= raw_link_count:
            reasons.append("unknown_role_link_only")
        if sector_only and sector_only >= raw_link_count:
            reasons.append("sector_only_unqualified_link")
        if not (quality_blocked or unknown_role or sector_only):
            reasons.append("weak_unqualified_link_only")
        warnings.append("incident_has_no_quality_qualified_crypto_link")

    return IncidentLinkQuality(
        raw_link_count=raw_link_count,
        qualified_link_count=qualified,
        qualified_hypothesis_count=qualified_hypothesis,
        qualified_watchlist_count=qualified_watchlist,
        weak_link_count=weak,
        quality_blocked_link_count=quality_blocked,
        unknown_role_link_count=unknown_role,
        generic_sector_only_link_count=sector_only,
        link_quality_reasons=tuple(dict.fromkeys(reasons)),
        link_quality_warnings=tuple(dict.fromkeys(warnings)),
    )
_BAD_LINK_STATES = {"QUALITY_BLOCKED", "STORE_ONLY", "LOCAL_ONLY", "RAW_EVIDENCE"}
_BAD_LINK_ROLES = {
    "unknown",
    "unknown_with_reason",
    "generic_mention",
    "source_noise",
    "ticker_word_collision",
    "sector_context",
    "ambiguous",
}
_BAD_IMPACT_PATHS = {"insufficient_data", "generic_cooccurrence_only"}
def _link_row_quality(
    row: Mapping[str, Any],
    *,
    incident: event_incident_graph.CanonicalIncident,
    source: str,
) -> dict[str, Any]:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    if not components and isinstance(row.get("score_components"), Mapping):
        components = row.get("score_components")
    merged = {**dict(components or {}), **dict(row)}
    validated_asset = merged.get("validated_asset") if isinstance(merged.get("validated_asset"), Mapping) else {}
    symbol = _first_text(
        merged.get("validated_symbol"),
        validated_asset.get("symbol"),
        merged.get("symbol"),
    ).upper()
    coin_id = _first_text(
        merged.get("validated_coin_id"),
        validated_asset.get("coin_id"),
        merged.get("coin_id"),
    ).casefold()
    role = _first_text(merged.get("candidate_role"), merged.get("asset_role"), merged.get("relationship_type")).casefold()
    impact = _first_text(merged.get("impact_path_type"), merged.get("impact_category")).casefold()
    evidence = _first_text(merged.get("evidence_specificity")).casefold()
    level = _first_text(merged.get("opportunity_level")).casefold()
    final_state = _first_text(merged.get("final_state_after_quality_gate"), merged.get("state")).upper()
    route = _first_text(merged.get("final_route_after_quality_gate"), merged.get("route")).upper()
    score = _float(merged.get("opportunity_score_final"))
    has_quality = any(
        key in merged and merged.get(key) not in (None, "", [], {})
        for key in (
            "opportunity_level",
            "impact_path_type",
            "candidate_role",
            "evidence_specificity",
            "opportunity_score_final",
        )
    )
    sector_only = _is_sector_identity(symbol=symbol, coin_id=coin_id) or (
        not (symbol or coin_id)
        and bool(merged.get("candidate_sectors") or merged.get("sectors"))
    )
    has_valid_asset = bool(symbol or coin_id) and not _is_sector_identity(symbol=symbol, coin_id=coin_id)
    strong_sector = _strong_sector_hypothesis(merged, incident=incident)
    unknown_role = bool(role in _BAD_LINK_ROLES or (not role and not strong_sector))
    quality_blocked = bool(
        merged.get("state_quality_capped")
        or final_state in _BAD_LINK_STATES
        or route in {"STORE_ONLY", "LOCAL_ONLY", "LOCAL_REPORT"}
        or level == "local_only"
        or impact in _BAD_IMPACT_PATHS
        or evidence == "insufficient_data"
        or (has_quality and score <= 0.0)
    )
    reasons: list[str] = []
    warnings: list[str] = []
    if quality_blocked:
        reasons.append("quality_blocked_link_only")
    if unknown_role:
        reasons.append("unknown_role_link_only")
    if sector_only and not strong_sector:
        reasons.append("sector_only_unqualified_link")
    if not has_valid_asset and not strong_sector:
        reasons.append("missing_validated_crypto_identity")

    qualified = bool(
        not quality_blocked
        and not unknown_role
        and (has_valid_asset or strong_sector)
        and (not has_quality or (level != "local_only" and impact not in _BAD_IMPACT_PATHS and evidence != "insufficient_data"))
    )
    if not qualified:
        reasons.append(f"weak_unqualified_{source}_link")
        warnings.append(f"{source}_link_not_quality_qualified")
    return {
        "qualified": qualified,
        "quality_blocked": quality_blocked,
        "unknown_role": unknown_role,
        "sector_only": bool(sector_only and not strong_sector),
        "reasons": tuple(dict.fromkeys(reasons)),
        "warnings": tuple(dict.fromkeys(warnings)),
    }
def _first_text(*values: Any) -> str:
    for value in values:
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""
def _has_crypto_asset_link(assets: Iterable[Mapping[str, Any]]) -> bool:
    for asset in assets:
        symbol = str(asset.get("symbol") or "").strip().upper()
        coin_id = str(asset.get("coin_id") or "").strip().casefold()
        role = str(asset.get("role") or "").strip()
        if not (symbol or coin_id):
            continue
        if symbol in {"SECTOR", "UNKNOWN"} or coin_id in {"sector", "unknown", "market_anomaly_unknown"}:
            continue
        if role in {"unknown", "unknown_with_reason", "generic_mention", "sector_context", "source_noise", "ticker_word_collision"}:
            continue
        return True
    return False
def _crypto_specific_text(
    text: str,
    *,
    incident: event_incident_graph.CanonicalIncident,
    assets: Iterable[Mapping[str, Any]],
) -> bool:
    cleaned = str(text or "").casefold()
    crypto_terms = (
        "crypto",
        "token",
        "coin",
        "blockchain",
        "defi",
        "perp",
        "perpetual",
        "binance",
        "bybit",
        "coinbase",
        "okx",
        "kucoin",
        "airdrop",
        "tge",
        "unlock",
        "tokenized stock",
        "pre-ipo exposure",
        "synthetic exposure",
        "bitcoin",
        "ethereum",
        "solana",
        "thorchain",
        "zcash",
        "rune",
        "chz",
        "usdt",
    )
    if any(term in cleaned for term in crypto_terms):
        return True
    for asset in assets:
        for key in ("symbol", "coin_id"):
            value = str(asset.get(key) or "").strip().casefold()
            if value and value not in {"sector", "unknown"} and value in cleaned:
                return True
    if incident.linked_assets:
        return _has_crypto_asset_link(
            {
                "symbol": asset.symbol,
                "coin_id": asset.coin_id,
                "role": asset.role,
            }
            for asset in incident.linked_assets
        )
    return False
def _high_quality_external_candidate(
    incident: event_incident_graph.CanonicalIncident,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    h_rows: Iterable[Mapping[str, Any]],
) -> bool:
    if h_rows:
        return True
    if incident.event_archetype not in _EXTERNAL_CATALYST_ARCHETYPES:
        return False
    confidences = [
        _float(raw_by_id[raw_id].source_confidence)
        for raw_id in incident.raw_ids
        if raw_id in raw_by_id
    ]
    return bool(confidences and max(confidences) >= 0.80)
_GARBAGE_INCIDENT_SUBJECTS = {
    "about",
    "actions",
    "all",
    "announcements",
    "any",
    "any us",
    "best prediction market apps",
    "bitcoin and mstr are",
    "during",
    "here",
    "however",
    "it",
    "llm",
    "need",
    "non",
    "not",
    "note",
    "only",
    "polymarket invite code sbwire",
    "polymarket referral code sbwire",
    "polymarket world cup volume",
    "when",
    "where",
    "will",
    "yes",
}
def _row_with_effective_subject_quality(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    validation = event_incident_graph.validate_incident_primary_subject(
        data.get("primary_subject"),
        {
            "external_asset": data.get("affected_ecosystem"),
        },
    )
    if validation.status == "fallback_used" and validation.normalized_subject:
        warnings = [str(item) for item in data.get("warnings") or () if str(item or "").strip()]
        warnings.extend(value for value in validation.warnings if value not in warnings)
        data["primary_subject"] = validation.normalized_subject
        data["incident_subject_quality"] = "fallback_used"
        data["incident_subject_quality_reason"] = validation.fallback_source or "garbage_primary_subject_fallback"
        data["warnings"] = tuple(dict.fromkeys(warnings))
        return data
    if validation.status == "valid" and not _is_garbage_incident_subject(data.get("primary_subject")):
        return data
    warnings = [str(item) for item in data.get("warnings") or () if str(item or "").strip()]
    if "incident_primary_subject_garbage_quarantined" not in warnings:
        warnings.append("incident_primary_subject_garbage_quarantined")
    data["diagnostic_only"] = True
    data["incident_subject_quality"] = "diagnostic_only"
    data["incident_subject_quality_reason"] = "garbage_primary_subject_quarantined"
    data["incident_relevance_status"] = RELEVANCE_DIAGNOSTIC_ONLY
    data["incident_relevance_score"] = 0.0
    data["incident_relevance_reasons"] = ("invalid_or_diagnostic_subject",)
    data["incident_relevance_warnings"] = ("incident_hidden_from_default_report",)
    data["canonical_persistence_reason"] = "diagnostic_subject_only"
    data["warnings"] = tuple(warnings)
    return data
def _ensure_existing_link_quality(data: dict[str, Any]) -> None:
    if "qualified_link_count" in data and "link_quality_reasons" in data:
        if "sector_only_link_count" not in data:
            data["sector_only_link_count"] = int(data.get("generic_sector_only_link_count") or 0)
        return
    summary = _link_quality_from_existing_row(data)
    data.setdefault("raw_link_count", summary.raw_link_count)
    data.setdefault("qualified_link_count", summary.qualified_link_count)
    data.setdefault("qualified_hypothesis_count", summary.qualified_hypothesis_count)
    data.setdefault("qualified_watchlist_count", summary.qualified_watchlist_count)
    data.setdefault("weak_link_count", summary.weak_link_count)
    data.setdefault("quality_blocked_link_count", summary.quality_blocked_link_count)
    data.setdefault("unknown_role_link_count", summary.unknown_role_link_count)
    data.setdefault("generic_sector_only_link_count", summary.generic_sector_only_link_count)
    data.setdefault("sector_only_link_count", summary.generic_sector_only_link_count)
    data.setdefault("link_quality_reasons", summary.link_quality_reasons)
    data.setdefault("link_quality_warnings", summary.link_quality_warnings)
def _link_quality_from_existing_row(row: Mapping[str, Any]) -> IncidentLinkQuality:
    linked_h = tuple(row.get("linked_hypothesis_ids") or ())
    linked_w = tuple(row.get("linked_watchlist_keys") or ())
    raw_count = len(linked_h) + len(linked_w)
    assets = [asset for asset in row.get("linked_assets") or () if isinstance(asset, Mapping)]
    if raw_count == 0 and assets:
        raw_count = len(assets)
    qualified = 0
    unknown_role = 0
    sector_only = 0
    for asset in assets:
        symbol = str(asset.get("symbol") or "").strip().upper()
        coin_id = str(asset.get("coin_id") or "").strip().casefold()
        role = str(asset.get("role") or "").strip().casefold()
        if _is_sector_identity(symbol=symbol, coin_id=coin_id):
            sector_only += 1
            continue
        if role in _BAD_LINK_ROLES or not role:
            unknown_role += 1
            continue
        qualified += 1
    quality_blocked = 0
    if row.get("state_quality_capped") or str(row.get("opportunity_level") or "").strip() == "local_only":
        quality_blocked = max(1, raw_count or 1)
    weak = max(0, raw_count - qualified)
    reasons: list[str] = []
    warnings: list[str] = []
    if qualified:
        if linked_w:
            reasons.append("qualified_watchlist_link")
        if linked_h:
            reasons.append("qualified_hypothesis_link")
    elif raw_count:
        if quality_blocked:
            reasons.append("quality_blocked_link_only")
        if unknown_role:
            reasons.append("unknown_role_link_only")
        if sector_only:
            reasons.append("sector_only_unqualified_link")
        if not (quality_blocked or unknown_role or sector_only):
            reasons.append("weak_unqualified_link_only")
        warnings.append("incident_has_no_quality_qualified_crypto_link")
    else:
        reasons.append("no_incident_links")
    return IncidentLinkQuality(
        raw_link_count=raw_count,
        qualified_link_count=qualified,
        qualified_hypothesis_count=qualified if linked_h and not linked_w else 0,
        qualified_watchlist_count=qualified if linked_w else 0,
        weak_link_count=weak,
        quality_blocked_link_count=quality_blocked,
        unknown_role_link_count=unknown_role,
        generic_sector_only_link_count=sector_only,
        link_quality_reasons=tuple(dict.fromkeys(reasons)),
        link_quality_warnings=tuple(dict.fromkeys(warnings)),
    )
def _object_row(item: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    data = dict(getattr(item, "__dict__", {}) or {})
    if hasattr(item, "latest_score_components"):
        data["latest_score_components"] = dict(getattr(item, "latest_score_components", {}) or {})
    return data
def _flatten_values(rows: Iterable[Mapping[str, Any]], key: str, *, fallback: str | None = None) -> list[str]:
    values: list[str] = []
    for row in rows:
        raw = row.get(key)
        if raw in (None, "", [], ()):
            raw = row.get(fallback) if fallback else None
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Mapping):
            text = raw.get("name") or raw.get("symbol") or raw.get("coin_id")
            if text not in (None, ""):
                values.append(str(text))
        elif isinstance(raw, IterableABC):
            for item in raw:
                if isinstance(item, Mapping):
                    text = item.get("name") or item.get("symbol") or item.get("coin_id")
                else:
                    text = item
                if text not in (None, ""):
                    values.append(str(text))
    return values
def _crypto_entities(h_rows: list[dict[str, Any]], w_rows: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for row in [*h_rows, *w_rows]:
        values.extend(_flatten_values((row,), "candidate_symbols"))
        for key in ("validated_symbol", "symbol", "coin_id", "validated_coin_id"):
            value = row.get(key)
            if value not in (None, ""):
                values.append(str(value))
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        for key in ("validated_symbol", "symbol", "coin_id", "validated_coin_id"):
            value = components.get(key)
            if value not in (None, ""):
                values.append(str(value))
    return values
def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, "", [], {}):
            continue
        text = str(value)
        if text not in out:
            out.append(text)
    return tuple(out)
def _unique_dicts(rows: Iterable[Mapping[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(str(row.get(part) or "") for part in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out
def _value(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return str(value).strip() if value not in (None, "", [], {}) else ""
def _float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0
def _iso(value: object) -> str | None:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(value) if value not in (None, "") else None
def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(child) for child in value]
    return value
