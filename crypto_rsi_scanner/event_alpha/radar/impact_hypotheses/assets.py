"""Impact-hypothesis asset and query helpers."""

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



def _external_entities_for_event(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    text: str,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    if event.external_asset:
        rows.append({
            "name": str(event.external_asset).strip(),
            "source": "normalized_event",
            "entity_type": str(event.event_type or "external_catalyst"),
            "confidence": round(_bounded_confidence(event.confidence), 4),
        })
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
        raw_external = str(event_payload.get("external_asset") or payload.get("external_asset") or "").strip()
        if raw_external:
            rows.append({
                "name": raw_external,
                "source": raw.provider,
                "entity_type": str(event_payload.get("event_type") or payload.get("event_type") or event.event_type or ""),
                "confidence": round(_bounded_confidence(raw.source_confidence), 4),
            })
    for alias in sorted(_EXTERNAL_ENTITY_ALIASES):
        if _term_hit(text, alias):
            rows.append({
                "name": _display_external_entity(alias),
                "source": "source_text",
                "entity_type": "external_entity",
                "confidence": 0.70,
            })
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        key = clean_text(name)
        existing = by_name.get(key)
        if existing is None or _bounded_confidence(row.get("confidence")) > _bounded_confidence(existing.get("confidence")):
            by_name[key] = row
    return tuple(by_name.values())


def _display_external_entity(value: str) -> str:
    names = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "spacex": "SpaceX",
        "space x": "SpaceX",
        "databricks": "Databricks",
        "anduril": "Anduril",
        "figma": "Figma",
        "stripe": "Stripe",
        "fannie mae": "Fannie Mae",
        "freddie mac": "Freddie Mac",
        "nvidia": "Nvidia",
        "tesla": "Tesla",
    }
    return names.get(clean_text(value), str(value).strip())


def _split_suggested_assets(
    assets: Iterable[Mapping[str, Any]],
    *,
    external_entities: tuple[dict[str, Any], ...],
    text: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    external_terms = {
        clean_text(value)
        for row in external_entities
        for value in (row.get("name"), row.get("symbol"), row.get("coin_id"))
        if str(value or "").strip()
    }
    for asset in assets:
        row = dict(asset)
        reason = _candidate_rejection_reason(row, external_terms=external_terms, text=text)
        if reason:
            rejected.append({**row, "rejection_reason": reason, "validated": False})
        else:
            accepted.append(row)
    return _merge_asset_rows(tuple(accepted)), _merge_asset_rows(tuple(rejected))


def _candidate_rejection_reason(
    row: Mapping[str, Any],
    *,
    external_terms: set[str],
    text: str,
) -> str | None:
    values = {
        clean_text(value)
        for value in (row.get("name"), row.get("symbol"), row.get("coin_id"))
        if str(value or "").strip()
    }
    if values & external_terms:
        return "external_entity_not_crypto_candidate"
    symbol = str(row.get("symbol") or "").strip().upper()
    name = clean_text(row.get("name") or "")
    coin_id = clean_text(row.get("coin_id") or "")
    source_title = clean_text(row.get("source_title") or row.get("evidence") or "")
    if symbol == "BTC" and "bitcoin world" in source_title and "$btc" not in source_title and "btcusdt" not in source_title:
        return "publisher_source_name_not_asset_identity"
    if symbol == "PRIME" and "prime minister" in source_title:
        return "common_word_or_title_not_asset_identity"
    if symbol and symbol.casefold() in _GENERIC_NON_ASSET_TERMS:
        strong_terms = {clean_text(value) for value in (name, coin_id) if value}
        strong_terms.add(symbol.casefold() + "usdt")
        strong_terms.add("$" + symbol.casefold())
        if symbol == "HYPE":
            strong_terms.add("hyperliquid")
        if not any(_term_hit(text, term) for term in strong_terms if term and term != symbol.casefold()):
            return "generic_symbol_without_project_identity"
    if str(row.get("mention_type") or "") in {"publisher_or_source", "ordinary_word"}:
        return "source_noise_not_candidate_asset"
    return None


def _asset_knowledge_components(asset: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(asset or {})
    knowledge = event_identity.asset_knowledge_for(
        symbol=str(row.get("symbol") or ""),
        coin_id=str(row.get("coin_id") or ""),
        name=str(row.get("name") or ""),
        categories=row.get("categories") or (),
        aliases=row.get("aliases") or (),
        metadata=row,
    )
    identity_evidence = row.get("identity_evidence") or row.get("evidence") or row.get("source_title") or ()
    if isinstance(identity_evidence, str):
        identity_evidence = (identity_evidence,)
    return {
        "asset_name": knowledge.official_name,
        "asset_kind": knowledge.asset_kind,
        "asset_categories": list(knowledge.categories),
        "asset_aliases": list(knowledge.aliases[:8]),
        "role_capabilities": knowledge.role_capabilities.as_dict(),
        "role_source": str(row.get("role_source") or event_identity.ROLE_SOURCE_RESOLVER_EXACT),
        "asset_role_source": str(row.get("role_source") or event_identity.ROLE_SOURCE_RESOLVER_EXACT),
        "identity_confidence": _coerce_score(row.get("identity_confidence")),
        "identity_evidence": tuple(str(value) for value in identity_evidence if str(value)),
        "collision_risk": "high" if knowledge.common_word_collision_risk else "none",
    }


def _suggested_assets_by_event(
    events: Iterable[NormalizedEvent],
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    extraction_rows: Mapping[str, EventLLMExtractionReportRow],
) -> dict[str, tuple[dict[str, Any], ...]]:
    out: dict[str, tuple[dict[str, Any], ...]] = {}
    for event in events:
        rows: list[dict[str, Any]] = []
        for raw_id in event.raw_ids:
            row = extraction_rows.get(raw_id)
            extraction = row.extraction if row else None
            if extraction is None:
                continue
            for mention in extraction.crypto_asset_mentions:
                confidence = _bounded_confidence(mention.confidence)
                if confidence < 0.70:
                    continue
                if str(mention.mention_type or "") in {"publisher_or_source", "ordinary_word"}:
                    continue
                symbol = str(mention.symbol or "").strip().upper()
                coin_id = str(mention.coin_id or "").strip()
                name = str(mention.name or "").strip()
                contract = str(mention.contract_address or "").strip()
                if not any((symbol, coin_id, name, contract)):
                    continue
                rows.append({
                    "source": "llm_extraction",
                    "raw_id": raw_id,
                    "name": name,
                    "symbol": symbol,
                    "coin_id": coin_id,
                    "contract_address": contract,
                    "mention_type": str(mention.mention_type or ""),
                    "confidence": round(confidence, 4),
                    "evidence": " | ".join(quote.text for quote in mention.evidence_quotes[:3]),
                    "validated": False,
                })
        if rows:
            out[event.event_id] = _merge_asset_rows(tuple(rows))
    return out


def _validated_assets_by_event(result: EventDiscoveryResult) -> dict[str, tuple[dict[str, Any], ...]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for candidate in result.candidates:
        event = getattr(candidate, "event", None)
        asset = getattr(candidate, "asset", None)
        link = getattr(candidate, "link", None)
        if event is None or asset is None:
            continue
        link_confidence = _bounded_confidence(getattr(link, "link_confidence", 0.0))
        symbol = str(getattr(asset, "symbol", "") or "").strip().upper()
        coin_id = str(getattr(asset, "coin_id", "") or "").strip()
        if not symbol and not coin_id:
            continue
        out.setdefault(event.event_id, []).append({
            "source": "deterministic_resolver",
            "name": str(getattr(asset, "name", "") or "").strip(),
            "symbol": symbol,
            "coin_id": coin_id,
            "link_confidence": round(link_confidence, 4),
            "reason": str(getattr(link, "match_reason", "") or ""),
            "evidence": " | ".join(str(value) for value in getattr(link, "evidence", ())[:3]),
            "validated": True,
        })
    return {event_id: _merge_asset_rows(tuple(rows)) for event_id, rows in out.items()}


def _assets_from_asset_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    symbols: list[str] = []
    coin_ids: list[str] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip()
        if symbol:
            symbols.append(symbol)
        if coin_id:
            coin_ids.append(coin_id)
    return tuple(dict.fromkeys(symbols)), tuple(dict.fromkeys(coin_ids))


def _merge_asset_rows(*groups: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    by_key: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            data = {str(key): value for key, value in dict(row).items() if value not in (None, "", [], {})}
            symbol = str(data.get("symbol") or "").upper()
            coin_id = str(data.get("coin_id") or "")
            contract = str(data.get("contract_address") or "")
            key = "|".join((symbol, coin_id, contract, str(data.get("source") or "")))
            if not key.strip("|"):
                continue
            by_key.setdefault(key, data)
    return tuple(by_key.values())


def _candidate_source(
    taxonomy_symbols: tuple[str, ...],
    suggested_assets: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
) -> str:
    parts: list[str] = []
    if taxonomy_symbols:
        parts.append("taxonomy")
    if suggested_assets:
        parts.append("llm_extraction")
    if validated_assets:
        parts.append("deterministic_resolver")
    return ",".join(parts) or "none"


def _asset_label(asset: Mapping[str, Any]) -> str:
    symbol = str(asset.get("symbol") or "").upper()
    coin_id = str(asset.get("coin_id") or "")
    source = str(asset.get("source") or "")
    label = symbol or coin_id or str(asset.get("name") or "asset")
    if coin_id and coin_id != label:
        label = f"{label}/{coin_id}"
    if source:
        label = f"{label} ({source})"
    return label


def _default_search_queries(hypothesis: EventImpactHypothesis) -> tuple[str, ...]:
    return tuple(item["query"] for item in _default_search_query_details(hypothesis))


def _default_search_query_details(hypothesis: EventImpactHypothesis) -> tuple[dict[str, Any], ...]:
    queries: list[dict[str, Any]] = []
    external = hypothesis.external_asset or _external_from_category(hypothesis.impact_category)
    category = hypothesis.impact_category
    symbols = hypothesis.candidate_symbols
    if not symbols:
        if external:
            for suffix in (
                "crypto exposure",
                "tokenized stock crypto",
                "pre-IPO crypto",
                "prediction market token",
                "perp crypto",
                "synthetic exposure crypto",
                "crypto venue",
            ):
                queries.append({"query": f"{external} {suffix}", "query_type": "candidate_discovery"})
        discovery_terms = tuple(hypothesis.candidate_sectors or ()) or (category,)
        for term in discovery_terms[:4]:
            clean = str(term).replace("_", " ").strip()
            if external:
                queries.append({"query": f"{external} {clean} crypto", "query_type": "candidate_discovery"})
            else:
                queries.append({"query": f"{clean} crypto catalyst candidates", "query_type": "candidate_discovery"})
        return _dedupe_query_details(queries)
    for symbol in symbols[:8]:
        if category in {ImpactCategory.RWA_PREIPO_PROXY.value, ImpactCategory.TOKENIZED_STOCK_VENUE.value}:
            if external:
                queries.append({"query": f"{symbol} {external} exposure", "query_type": "candidate_validation"})
                queries.append({"query": f"{symbol} {external} pre-IPO", "query_type": "candidate_validation"})
                queries.append({"query": f"{symbol} {external} pre-IPO exposure", "query_type": "candidate_validation"})
                queries.append({"query": f"{symbol} tokenized stock {external}", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} synthetic exposure crypto", "query_type": "candidate_validation"})
        elif category == ImpactCategory.AI_IPO_PROXY.value:
            target = external or "OpenAI"
            queries.append({"query": f"{symbol} {target} exposure", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} {target} pre-IPO", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} {target} pre-IPO exposure", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} tokenized stock {target}", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} {target} perp", "query_type": "candidate_validation"})
        elif category == ImpactCategory.SPORTS_FAN_PROXY.value:
            queries.append({"query": f"{symbol} World Cup fan token", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} sports event prediction market", "query_type": "candidate_validation"})
        elif category == ImpactCategory.STABLECOIN_REGULATORY.value:
            queries.append({"query": f"{symbol} GENIUS Act stablecoin", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} stablecoin reserve regulation", "query_type": "candidate_validation"})
        elif category == ImpactCategory.PERP_VENUE_ATTENTION.value:
            queries.append({"query": f"{symbol} perp listing", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} futures listing", "query_type": "candidate_validation"})
        elif category == ImpactCategory.LISTING_LIQUIDITY_EVENT.value:
            queries.append({"query": f"{symbol} listing", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} Binance listing", "query_type": "candidate_validation"})
        elif category == ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value:
            queries.append({"query": f"{symbol} unlock", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} token vesting unlock", "query_type": "candidate_validation"})
        elif category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value:
            queries.append({"query": f"{symbol} exploit hack regulatory", "query_type": "candidate_validation"})
        elif category == ImpactCategory.PREDICTION_MARKET_INFRA.value:
            queries.append({"query": f"{symbol} prediction market oracle", "query_type": "candidate_validation"})
        elif category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
            queries.append({"query": f"{symbol} crypto catalyst", "query_type": "market_confirmation"})
    if external and category in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
        ImpactCategory.SPORTS_FAN_PROXY.value,
        ImpactCategory.POLITICAL_MEME_PROXY.value,
        ImpactCategory.PREDICTION_MARKET_INFRA.value,
        ImpactCategory.PERP_VENUE_ATTENTION.value,
    }:
        queries.extend(_candidate_discovery_query_details(external, hypothesis.candidate_sectors, category))
    return _dedupe_query_details(queries)


def _candidate_discovery_query_details(
    external: str,
    sectors: Iterable[str],
    category: str,
) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for suffix in (
        "crypto exposure",
        "tokenized stock crypto",
        "pre-IPO crypto",
        "prediction market token",
        "perp crypto",
        "synthetic exposure crypto",
        "crypto venue",
    ):
        queries.append({"query": f"{external} {suffix}", "query_type": "candidate_discovery"})
    discovery_terms = tuple(sectors or ()) or (category,)
    for term in discovery_terms[:4]:
        clean = str(term).replace("_", " ").strip()
        if clean:
            queries.append({"query": f"{external} {clean} crypto", "query_type": "candidate_discovery"})
    return queries


def _dedupe_query_details(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        out.setdefault(query, {
            "query": query,
            "query_type": str(row.get("query_type") or "candidate_validation"),
        })
    return tuple(out.values())


def _executed_queries_by_hypothesis(search_result: object) -> dict[str, tuple[dict[str, Any], ...]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for query in getattr(search_result, "queries", ()) or ():
        hypothesis_id = str(getattr(query, "anomaly_raw_id", "") or "")
        if not hypothesis_id:
            continue
        out.setdefault(hypothesis_id, []).append({
            "query": str(getattr(query, "query", "") or ""),
            "query_type": str(getattr(query, "query_type", "") or "candidate_validation"),
            "symbol": str(getattr(query, "symbol", "") or ""),
            "rank": int(getattr(query, "rank", 0) or 0),
            "score": int(getattr(query, "score", 0) or 0),
            "score_reasons": tuple(str(item) for item in getattr(query, "score_reasons", ()) or ()),
        })
    return {key: _merge_query_details(tuple(value)) for key, value in out.items()}


def _merge_query_details(*groups: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for item in group:
            if not isinstance(item, Mapping):
                continue
            query = str(item.get("query") or "").strip()
            if not query:
                continue
            qtype = str(item.get("query_type") or "candidate_validation")
            rows.setdefault((query, qtype), {str(key): value for key, value in dict(item).items()})
    return tuple(rows.values())


def _external_from_category(category: str) -> str | None:
    if category == ImpactCategory.AI_IPO_PROXY.value:
        return "OpenAI"
    if category == ImpactCategory.RWA_PREIPO_PROXY.value:
        return "SpaceX"
    return None
