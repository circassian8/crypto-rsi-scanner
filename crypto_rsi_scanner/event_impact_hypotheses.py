"""Research-only impact hypotheses for Event Alpha Radar.

Hypotheses explain which crypto sectors/assets an external catalyst *might*
impact before direct asset validation exists. They are review evidence only:
they do not create alerts, paper trades, normal RSI rows, or event-fade
TRIGGERED_FADE signals.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_graph, event_identity
from .event_llm_extractor import EventLLMExtractionReportRow
from .event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from .event_resolver import clean_text


class ImpactCategory(str, Enum):
    RWA_PREIPO_PROXY = "rwa_preipo_proxy"
    AI_IPO_PROXY = "ai_ipo_proxy"
    SPORTS_FAN_PROXY = "sports_fan_proxy"
    POLITICAL_MEME_PROXY = "political_meme_proxy"
    STABLECOIN_REGULATORY = "stablecoin_regulatory"
    TOKENIZED_STOCK_VENUE = "tokenized_stock_venue"
    PREDICTION_MARKET_INFRA = "prediction_market_infra"
    PERP_VENUE_ATTENTION = "perp_venue_attention"
    UNLOCK_SUPPLY_PRESSURE = "unlock_supply_pressure"
    LISTING_LIQUIDITY_EVENT = "listing_liquidity_event"
    SECURITY_OR_REGULATORY_SHOCK = "security_or_regulatory_shock"
    MARKET_ANOMALY_UNKNOWN = "market_anomaly_unknown"


class HypothesisStatus(str, Enum):
    HYPOTHESIS = "hypothesis"
    VALIDATION_SEARCH_PENDING = "validation_search_pending"
    VALIDATION_EVIDENCE_FOUND = "validation_evidence_found"
    VALIDATED = "validated"
    REJECTED = "rejected"


class HypothesisScope(str, Enum):
    SECTOR = "sector"
    TOKEN = "token"
    VENUE = "venue"
    INFRASTRUCTURE = "infrastructure"


class ValidationStage(str, Enum):
    SECTOR_HYPOTHESIS = "sector_hypothesis"
    CANDIDATE_ASSETS_SUGGESTED = "candidate_assets_suggested"
    VALIDATION_SEARCH_PENDING = "validation_search_pending"
    SOURCE_MENTIONS_CANDIDATE = "source_mentions_candidate"
    IDENTITY_VALIDATED = "identity_validated"
    CATALYST_LINK_VALIDATED = "catalyst_link_validated"
    MARKET_CONFIRMED = "market_confirmed"
    PROMOTED_TO_RADAR = "promoted_to_radar"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EventImpactHypothesis:
    hypothesis_id: str
    event_cluster_id: str | None
    event_type: str
    external_asset: str | None
    impact_category: str
    candidate_sectors: tuple[str, ...]
    candidate_symbols: tuple[str, ...]
    candidate_coin_ids: tuple[str, ...] = ()
    suggested_candidate_assets: tuple[dict[str, Any], ...] = ()
    validated_candidate_assets: tuple[dict[str, Any], ...] = ()
    external_entities: tuple[dict[str, Any], ...] = ()
    crypto_candidate_assets: tuple[dict[str, Any], ...] = ()
    rejected_candidate_assets: tuple[dict[str, Any], ...] = ()
    candidate_source: str = "taxonomy"
    hypothesis_scope: str = HypothesisScope.SECTOR.value
    direction_hint: str = "unknown"
    playbook_hint: str | None = None
    confidence: float = 0.0
    hypothesis_score: float = 0.0
    score_components: Mapping[str, float] = field(default_factory=dict)
    validation_stage: str = ValidationStage.SECTOR_HYPOTHESIS.value
    evidence_quotes: tuple[str, ...] = ()
    required_validation_steps: tuple[str, ...] = ()
    search_queries: tuple[str, ...] = ()
    search_query_details: tuple[dict[str, Any], ...] = ()
    status: str = HypothesisStatus.HYPOTHESIS.value
    warnings: tuple[str, ...] = ()
    source_raw_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    validation_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    rejected_validation_samples: tuple[dict[str, Any], ...] = ()
    why_not_promoted: tuple[str, ...] = ()
    created_at: str | None = None


DEFAULT_TAXONOMY_PATH = Path("fixtures/event_discovery/event_impact_taxonomy.json")
_EXTERNAL_ENTITY_ALIASES = {
    "openai",
    "anthropic",
    "spacex",
    "space x",
    "stripe",
    "databricks",
    "anduril",
    "figma",
    "fannie mae",
    "freddie mac",
    "nvidia",
    "tesla",
}
_GENERIC_NON_ASSET_TERMS = {
    "hype",
    "open",
    "prime",
    "cash",
    "real",
    "just",
    "human",
    "humanity",
    "ai",
}
_PROMOTABLE_VALIDATION_STAGES = {
    ValidationStage.CATALYST_LINK_VALIDATED.value,
    ValidationStage.MARKET_CONFIRMED.value,
    ValidationStage.PROMOTED_TO_RADAR.value,
}

_CATEGORY_RULES: tuple[dict[str, Any], ...] = (
    {
        "category": ImpactCategory.AI_IPO_PROXY,
        "keywords": ("openai", "anthropic"),
        "secondary": ("pre ipo", "pre-ipo", "ipo", "exposure", "tokenized stock", "prediction market"),
        "sectors": ("ai_tokens", "tokenized_stock_venues", "prediction_markets"),
        "direction": "up_then_fade",
        "playbook": "ai_ipo_proxy",
    },
    {
        "category": ImpactCategory.RWA_PREIPO_PROXY,
        "keywords": ("spacex", "stripe", "databricks", "anduril", "figma", "pre ipo", "pre-ipo"),
        "secondary": ("tokenized stock", "synthetic exposure", "prediction market", "ipo", "exposure"),
        "sectors": ("tokenized_stock_venues", "prediction_markets", "rwa_tokens"),
        "direction": "up_then_fade",
        "playbook": "rwa_preipo_proxy",
    },
    {
        "category": ImpactCategory.TOKENIZED_STOCK_VENUE,
        "keywords": ("tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo"),
        "secondary": ("trade", "market", "venue", "exposure"),
        "sectors": ("tokenized_stock_venues", "perp_dex"),
        "direction": "up_then_fade",
        "playbook": "proxy_attention",
    },
    {
        "category": ImpactCategory.SPORTS_FAN_PROXY,
        "keywords": ("world cup", "champions league", "fixture", "kickoff", "fan token", "sports event"),
        "secondary": ("fan token", "prediction market", "sports", "team"),
        "sectors": ("fan_tokens", "prediction_markets"),
        "direction": "up_then_fade",
        "playbook": "fan_sports_event",
    },
    {
        "category": ImpactCategory.POLITICAL_MEME_PROXY,
        "keywords": ("election", "inauguration", "campaign", "debate", "vote", "political"),
        "secondary": ("meme", "prediction market", "polymarket", "ballot", "candidate"),
        "sectors": ("political_meme_tokens", "prediction_markets"),
        "direction": "up_then_fade",
        "playbook": "political_meme_event",
    },
    {
        "category": ImpactCategory.STABLECOIN_REGULATORY,
        "keywords": ("genius act", "stablecoin", "money market", "treasury reserve", "reserve fund"),
        "secondary": ("regulation", "bill", "senate", "house", "approval"),
        "sectors": ("stablecoin_rwa",),
        "direction": "volatility",
        "playbook": "direct_event",
    },
    {
        "category": ImpactCategory.PREDICTION_MARKET_INFRA,
        "keywords": ("prediction market", "polymarket", "resolution market"),
        "secondary": ("oracle", "settlement", "resolution", "infrastructure", "data provider", "chainlink", "uma", "pyth"),
        "sectors": ("prediction_markets", "oracle_infra"),
        "direction": "up",
        "playbook": "infrastructure_mention",
    },
    {
        "category": ImpactCategory.PERP_VENUE_ATTENTION,
        "keywords": ("perp listing", "futures listing", "perpetual", "perp market"),
        "secondary": ("listing", "launch", "exchange", "venue"),
        "sectors": ("perp_dex",),
        "direction": "volatility",
        "playbook": "perp_listing_squeeze",
    },
    {
        "category": ImpactCategory.UNLOCK_SUPPLY_PRESSURE,
        "keywords": ("unlock", "vesting", "airdrop", "tge", "emission"),
        "secondary": ("supply", "claim", "cliff", "token"),
        "sectors": ("direct_token_events",),
        "direction": "down",
        "playbook": "unlock_supply_pressure",
    },
    {
        "category": ImpactCategory.LISTING_LIQUIDITY_EVENT,
        "keywords": ("binance listing", "exchange listing", "coinbase listing", "spot listing", "listed on"),
        "secondary": ("trading pair", "liquidity", "launch", "market"),
        "sectors": ("direct_token_events",),
        "direction": "volatility",
        "playbook": "listing_volatility",
    },
    {
        "category": ImpactCategory.SECURITY_OR_REGULATORY_SHOCK,
        "keywords": ("exploit", "hack", "lawsuit", "sec", "cftc", "regulatory", "security incident"),
        "secondary": ("probe", "charges", "investigation", "attack"),
        "sectors": ("direct_token_events", "infrastructure_tokens"),
        "direction": "volatility",
        "playbook": "security_or_regulatory_shock",
    },
)


def load_impact_taxonomy(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load a local taxonomy fixture, returning an empty taxonomy on failure."""
    target = Path(path or DEFAULT_TAXONOMY_PATH).expanduser()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - fixture/config must fail soft.
        return {}
    sectors = raw.get("sectors", raw) if isinstance(raw, Mapping) else {}
    if not isinstance(sectors, Mapping):
        return {}
    return {
        str(name): dict(value)
        for name, value in sectors.items()
        if isinstance(value, Mapping)
    }


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
        matches = _matched_rules(text, event)
        if not matches and _is_market_anomaly(raws):
            matches = (_market_anomaly_rule(),)
        for rule in matches:
            out.append(_hypothesis_from_rule(
                event,
                raws,
                rule,
                cluster=clusters_by_event.get(event.event_id),
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


def validate_hypotheses_with_raw_events(
    hypotheses: Iterable[EventImpactHypothesis],
    raw_events: Iterable[RawDiscoveredEvent],
) -> tuple[EventImpactHypothesis, ...]:
    """Mark hypotheses that have explicit asset+catalyst validation evidence."""
    rows = tuple(raw_events)
    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        reasons: list[str] = []
        rejections: list[str] = []
        matched_symbols: list[str] = []
        matched_coin_ids: list[str] = []
        best_stage = hypothesis.validation_stage
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
            elif reason:
                rejections.append(reason)
        if reasons and best_stage in _PROMOTABLE_VALIDATION_STAGES:
            if _market_confirmation_score(rows) >= 70:
                best_stage = ValidationStage.MARKET_CONFIRMED.value
            merged_assets = tuple(
                {
                    "source": "hypothesis_search",
                    "symbol": symbol,
                    "coin_id": coin_id,
                    "reason": reason,
                    "validated": True,
                }
                for reason, symbol, coin_id in zip(reasons, matched_symbols, matched_coin_ids)
            )
            crypto_assets = _merge_asset_rows(hypothesis.crypto_candidate_assets, hypothesis.validated_candidate_assets, merged_assets)
            symbols, coin_ids = _assets_from_asset_rows(crypto_assets)
            components = dict(hypothesis.score_components or {})
            components["validation_strength"] = 95.0
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
            ))
        elif reasons:
            components = dict(hypothesis.score_components or {})
            components["validation_strength"] = max(float(components.get("validation_strength") or 0.0), 45.0)
            score = _weighted_hypothesis_score(components, hypothesis.impact_category)
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.VALIDATION_EVIDENCE_FOUND.value,
                validation_stage=best_stage,
                hypothesis_score=round(score, 2),
                confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
                score_components=components,
                validation_reasons=tuple(dict.fromkeys((*hypothesis.validation_reasons, *reasons))),
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
    for attr in ("rejected_result_events", "result_events"):
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
                "rejection_reason": _sample_rejection_reason(reasons),
                "identity_reason": _first_reason_with(reasons, "identity"),
                "catalyst_reason": _first_reason_with(reasons, "catalyst"),
            }
            samples_by_id.setdefault(hypothesis_id, []).append(sample)
    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        samples = samples_by_id.get(hypothesis.hypothesis_id, [])
        if samples:
            merged = tuple(dict.fromkeys(
                json.dumps(sample, sort_keys=True, separators=(",", ":"))
                for sample in (*hypothesis.rejected_validation_samples, *samples)
            ))
            parsed = tuple(json.loads(item) for item in merged[: max(0, max_samples_per_hypothesis)])
            out.append(replace(hypothesis, rejected_validation_samples=parsed))
        else:
            out.append(hypothesis)
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
        crypto_assets = _merge_asset_rows(hypothesis.crypto_candidate_assets, accepted)
        symbols, coin_ids = _assets_from_asset_rows(crypto_assets)
        components = dict(hypothesis.score_components or {})
        if not components and float(hypothesis.hypothesis_score or 0.0) > 0.0:
            base = max(0.0, min(100.0, float(hypothesis.hypothesis_score or 0.0)))
            components.update({
                "event_clarity": base,
                "source_quality": base,
                "catalyst_strength": base,
                "sector_relevance": base,
            })
        if accepted:
            components["candidate_asset_strength"] = max(
                float(components.get("candidate_asset_strength") or 0.0),
                min(100.0, 35.0 + len(accepted) * 14.0),
            )
        if rejected:
            components["candidate_discovery_rejected"] = max(
                float(components.get("candidate_discovery_rejected") or 0.0),
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


def _candidate_asset_from_discovery_raw(raw: RawDiscoveredEvent) -> dict[str, Any] | None:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    for key in ("candidate_asset", "asset", "market"):
        asset = payload.get(key) if isinstance(payload.get(key), Mapping) else {}
        row = _asset_row_from_mapping(asset, source="candidate_discovery_search", raw_id=raw.raw_id)
        if row:
            return row
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        try:
            confidence = float(mention.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.70:
            continue
        mention_type = clean_text(mention.get("mention_type"))
        if mention_type in {"publisher or source", "publisher_or_source", "ordinary word", "ordinary_word", "false positive"}:
            continue
        row = _asset_row_from_mapping(mention, source="candidate_discovery_search", raw_id=raw.raw_id)
        if row:
            row["confidence"] = round(max(0.0, min(1.0, confidence)), 4)
            return row
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
    try:
        confidence = float(asset.get("confidence") or 0.75)
    except (TypeError, ValueError):
        confidence = 0.75
    return {
        "source": source,
        "raw_id": raw_id,
        "name": name,
        "symbol": symbol,
        "coin_id": coin_id,
        "contract_address": contract,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "evidence": str(asset.get("evidence") or asset.get("evidence_quote") or ""),
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
    reasons: list[str] = []
    if (
        hypothesis.status == HypothesisStatus.VALIDATED.value
        and hypothesis.validation_stage in _PROMOTABLE_VALIDATION_STAGES
        and float(hypothesis.hypothesis_score or 0.0) >= 60.0
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
    counts: dict[str, int] = {}
    stages: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
        stages[item.validation_stage] = stages.get(item.validation_stage, 0) + 1
    rows.append("statuses: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    rows.append("validation_stages: " + ", ".join(f"{key}={value}" for key, value in sorted(stages.items())))
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
    rows.append("")
    for item in items[:20]:
        rows.append(
            f"{item.status:<26} stage={item.validation_stage} score={item.hypothesis_score:.1f} conf={item.confidence:.2f} "
            f"{item.impact_category} external={item.external_asset or 'unknown'}"
        )
        if item.external_entities:
            rows.append(
                "  external_entities: "
                + ", ".join(str(entity.get("name") or "") for entity in item.external_entities[:6])
            )
        rows.append(f"  sectors: {', '.join(item.candidate_sectors) or 'none'}")
        rows.append(f"  symbols: {', '.join(item.candidate_symbols) or 'none'}")
        rows.append(f"  candidate_source={item.candidate_source}")
        if item.crypto_candidate_assets:
            rows.append(
                "  crypto_candidates: "
                + ", ".join(_asset_label(asset) for asset in item.crypto_candidate_assets[:6])
            )
        if item.rejected_candidate_assets:
            rows.append(
                "  rejected_candidates: "
                + ", ".join(_asset_label(asset) for asset in item.rejected_candidate_assets[:6])
            )
        if item.suggested_candidate_assets:
            rows.append(
                "  suggested_assets: "
                + ", ".join(_asset_label(asset) for asset in item.suggested_candidate_assets[:6])
            )
        if item.validated_candidate_assets:
            rows.append(
                "  validated_assets: "
                + ", ".join(_asset_label(asset) for asset in item.validated_candidate_assets[:6])
            )
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
    return "\n".join(rows).rstrip()


def _hypothesis_from_rule(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    rule: Mapping[str, Any],
    *,
    cluster: event_graph.EventCluster | None,
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
    hypothesis_score = _weighted_hypothesis_score(score_components, category_value)
    confidence = max(0.0, min(1.0, round(hypothesis_score / 100.0, 4)))
    quotes = _evidence_quotes(text, (*rule.get("keywords", ()), *rule.get("secondary", ())))
    validation_stage = _initial_validation_stage(category_value, crypto_candidate_assets, validated_assets)
    status = (
        HypothesisStatus.VALIDATION_SEARCH_PENDING.value
        if category != ImpactCategory.MARKET_ANOMALY_UNKNOWN and crypto_candidate_assets
        else HypothesisStatus.HYPOTHESIS.value
    )
    if validated_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN:
        status = HypothesisStatus.VALIDATED.value
    candidate_source = _candidate_source(taxonomy_symbols, accepted_suggested, validated_assets)
    hypothesis = EventImpactHypothesis(
        hypothesis_id=_hypothesis_id(event, category_value, sectors, symbols),
        event_cluster_id=cluster.cluster_id if cluster else event_graph.cluster_id_for_event(event),
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
        validation_reasons=(
            ("resolver_validated_candidate_asset",) if validated_assets else ()
        ),
        created_at=now.isoformat(),
    )
    query_details = _default_search_query_details(hypothesis)
    hypothesis = replace(
        hypothesis,
        search_queries=tuple(str(item.get("query") or "") for item in query_details if item.get("query")),
        search_query_details=query_details,
    )
    return _with_promotion_diagnostics(hypothesis)


def _matched_rules(text: str, event: NormalizedEvent) -> tuple[Mapping[str, Any], ...]:
    event_type = clean_text(event.event_type or "")
    matches: list[Mapping[str, Any]] = []
    for rule in _CATEGORY_RULES:
        category = rule["category"]
        if _rule_matches(rule, text, event_type, category):
            matches.append(rule)
    return tuple(matches)


def _rule_matches(rule: Mapping[str, Any], text: str, event_type: str, category: ImpactCategory) -> bool:
    keywords = tuple(str(value) for value in rule.get("keywords", ()))
    secondary = tuple(str(value) for value in rule.get("secondary", ()))
    primary_hit = _any_term_hit(text, keywords)
    secondary_hit = _any_term_hit(text, secondary)

    if category == ImpactCategory.LISTING_LIQUIDITY_EVENT and _term_hit(event_type, "listing"):
        primary_hit = True
    if category == ImpactCategory.PERP_VENUE_ATTENTION and _term_hit(event_type, "perp"):
        primary_hit = True
    if category == ImpactCategory.UNLOCK_SUPPLY_PRESSURE and any(_term_hit(event_type, token) for token in ("unlock", "airdrop", "tge")):
        primary_hit = True

    if category == ImpactCategory.SPORTS_FAN_PROXY:
        return primary_hit and (_any_term_hit(text, ("fan token", "sports", "prediction market", "team", "fixture", "kickoff")) or _term_hit(event_type, "sports"))
    if category == ImpactCategory.POLITICAL_MEME_PROXY:
        political_context = primary_hit or _term_hit(event_type, "political")
        proxy_context = _any_term_hit(text, ("meme", "prediction market", "polymarket", "token", "coin"))
        return political_context and proxy_context
    if category == ImpactCategory.PREDICTION_MARKET_INFRA:
        return _any_term_hit(text, ("prediction market", "polymarket", "resolution market")) and _any_term_hit(
            text,
            ("oracle", "settlement", "resolution", "infrastructure", "data provider", "chainlink", "uma", "pyth"),
        )
    if category == ImpactCategory.STABLECOIN_REGULATORY:
        return _any_term_hit(text, ("stablecoin", "genius act", "money market", "treasury reserve", "reserve fund")) and _any_term_hit(
            text,
            ("regulation", "regulatory", "bill", "senate", "house", "approval", "reserve"),
        )
    if category in {
        ImpactCategory.AI_IPO_PROXY,
        ImpactCategory.RWA_PREIPO_PROXY,
        ImpactCategory.TOKENIZED_STOCK_VENUE,
    }:
        return primary_hit and secondary_hit
    if category in {
        ImpactCategory.LISTING_LIQUIDITY_EVENT,
        ImpactCategory.PERP_VENUE_ATTENTION,
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE,
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK,
    }:
        return primary_hit
    return primary_hit and secondary_hit


def _hypothesis_scope(category: str, text: str) -> str:
    if category == ImpactCategory.PREDICTION_MARKET_INFRA.value:
        return HypothesisScope.INFRASTRUCTURE.value
    if category in {
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
        ImpactCategory.PERP_VENUE_ATTENTION.value,
    }:
        return HypothesisScope.VENUE.value
    if category in {
        ImpactCategory.LISTING_LIQUIDITY_EVENT.value,
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value,
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value,
    } and _any_term_hit(text, ("token", "coin", "listed on", "trading pair", "unlock", "airdrop", "tge")):
        return HypothesisScope.TOKEN.value
    return HypothesisScope.SECTOR.value


def _market_anomaly_rule() -> Mapping[str, Any]:
    return {
        "category": ImpactCategory.MARKET_ANOMALY_UNKNOWN,
        "keywords": ("market anomaly", "no dated external catalyst"),
        "secondary": (),
        "sectors": (),
        "direction": "unknown",
        "playbook": "market_anomaly_unknown",
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
                "validated": False,
            })
    return _merge_asset_rows(tuple(rows))


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
            "confidence": round(max(0.0, min(1.0, float(event.confidence or 0.0))), 4),
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
                "confidence": round(max(0.0, min(1.0, float(raw.source_confidence or 0.0))), 4),
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
        if existing is None or float(row.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
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
                try:
                    confidence = float(mention.confidence or 0.0)
                except (TypeError, ValueError):
                    confidence = 0.0
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
                    "confidence": round(max(0.0, min(1.0, confidence)), 4),
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
        try:
            link_confidence = float(getattr(link, "link_confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            link_confidence = 0.0
        symbol = str(getattr(asset, "symbol", "") or "").strip().upper()
        coin_id = str(getattr(asset, "coin_id", "") or "").strip()
        if not symbol and not coin_id:
            continue
        out.setdefault(event.event_id, []).append({
            "source": "deterministic_resolver",
            "name": str(getattr(asset, "name", "") or "").strip(),
            "symbol": symbol,
            "coin_id": coin_id,
            "link_confidence": round(max(0.0, min(1.0, link_confidence)), 4),
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
                queries.append({"query": f"{symbol} {external} pre-IPO exposure", "query_type": "candidate_validation"})
                queries.append({"query": f"{symbol} tokenized stock {external}", "query_type": "candidate_validation"})
            queries.append({"query": f"{symbol} synthetic exposure crypto", "query_type": "candidate_validation"})
        elif category == ImpactCategory.AI_IPO_PROXY.value:
            target = external or "OpenAI"
            queries.append({"query": f"{symbol} {target} pre-IPO exposure", "query_type": "candidate_validation"})
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
    return _dedupe_query_details(queries)


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


def _external_from_category(category: str) -> str | None:
    if category == ImpactCategory.AI_IPO_PROXY.value:
        return "OpenAI"
    if category == ImpactCategory.RWA_PREIPO_PROXY.value:
        return "SpaceX"
    return None


def _validation_reason(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> tuple[str, str | None, str | None, str | None]:
    detail = _validation_detail(raw, hypothesis)
    return (
        str(detail.get("status") or "none"),
        str(detail.get("reason") or "") or None,
        str(detail.get("symbol") or "") or None,
        str(detail.get("coin_id") or "") or None,
    )


def _validation_detail(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> dict[str, Any]:
    text = clean_text(_raw_text(raw))
    if not text:
        return {"status": "none"}
    mentions_candidate = _text_mentions_candidate(text, hypothesis)
    mentions_catalyst = _text_mentions_catalyst(text, hypothesis)
    symbol_match = _identity_match_from_symbols(raw, hypothesis)
    symbol, coin_id = _matched_symbol_and_coin_id(raw, hypothesis) if symbol_match.matched else (None, None)
    if mentions_candidate and not symbol_match.matched and not mentions_catalyst:
        return {
            "status": "accepted",
            "validation_stage": ValidationStage.SOURCE_MENTIONS_CANDIDATE.value,
            "reason": "source_mentions_candidate_without_catalyst_link",
            "symbol": None,
            "coin_id": None,
        }
    if mentions_candidate and symbol_match.matched and not mentions_catalyst:
        return {
            "status": "accepted",
            "validation_stage": ValidationStage.IDENTITY_VALIDATED.value,
            "reason": f"{symbol_match.reason or 'identity_match'} validates candidate identity without catalyst link",
            "symbol": symbol,
            "coin_id": coin_id,
        }
    if mentions_catalyst and not mentions_candidate and not symbol_match.matched:
        return {
            "status": "rejected",
            "validation_stage": ValidationStage.REJECTED.value,
            "reason": "source_mentions_catalyst_without_candidate_asset",
        }
    if not mentions_catalyst:
        if mentions_candidate:
            return {
                "status": "rejected",
                "validation_stage": ValidationStage.REJECTED.value,
                "reason": "source mentions candidate context without the catalyst",
            }
        return {"status": "none"}
    if not symbol_match.matched:
        if mentions_candidate:
            return {
                "status": "rejected",
                "validation_stage": ValidationStage.REJECTED.value,
                "reason": symbol_match.reason or "candidate identity rejected",
            }
        return {"status": "none"}
    return {
        "status": "accepted",
        "validation_stage": ValidationStage.CATALYST_LINK_VALIDATED.value,
        "reason": f"{symbol_match.reason or 'identity_match'} links candidate to {hypothesis.external_asset or hypothesis.impact_category}",
        "symbol": symbol,
        "coin_id": coin_id,
    }


_VALIDATION_STAGE_RANK = {
    ValidationStage.SECTOR_HYPOTHESIS.value: 0,
    ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value: 1,
    ValidationStage.VALIDATION_SEARCH_PENDING.value: 2,
    ValidationStage.SOURCE_MENTIONS_CANDIDATE.value: 3,
    ValidationStage.IDENTITY_VALIDATED.value: 4,
    ValidationStage.CATALYST_LINK_VALIDATED.value: 5,
    ValidationStage.MARKET_CONFIRMED.value: 6,
    ValidationStage.PROMOTED_TO_RADAR.value: 7,
    ValidationStage.REJECTED.value: -1,
}


def _max_validation_stage(current: str, candidate: str) -> str:
    if candidate == ValidationStage.REJECTED.value:
        return current or candidate
    if _VALIDATION_STAGE_RANK.get(candidate, 0) > _VALIDATION_STAGE_RANK.get(current, 0):
        return candidate
    return current


def _sample_rejection_reason(reasons: Iterable[str]) -> str | None:
    for reason in reasons:
        if "rejected" in reason or "missing" in reason or "below_threshold" in reason or "penalty" in reason:
            return reason
    return None


def _first_reason_with(reasons: Iterable[str], needle: str) -> str | None:
    lowered = str(needle or "").casefold()
    for reason in reasons:
        if lowered and lowered in str(reason).casefold():
            return reason
    return None


def _identity_match_from_symbols(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> event_identity.IdentityMatchResult:
    strong = (raw.title, raw.body, _event_name(raw))
    for idx, symbol in enumerate(hypothesis.candidate_symbols):
        coin_id = hypothesis.candidate_coin_ids[idx] if idx < len(hypothesis.candidate_coin_ids) else None
        identity = event_identity.AssetIdentity(
            symbol=symbol,
            coin_id=coin_id,
            project_name=None,
            aliases=(coin_id.replace("-", " ") if coin_id else ""),
            is_common_word_symbol=symbol.upper() in event_identity.COMMON_WORD_SYMBOLS,
        )
        result = event_identity.match_asset_identity(
            identity,
            event_identity.IdentityEvidence(
                strong_content=tuple(str(item or "") for item in strong),
                url=raw.source_url,
                source_origin=(raw.provider,),
            ),
        )
        if result.matched or result.reason in {
            "common_word_identity_rejected",
            "identity_url_only_rejected",
            "identity_source_origin_rejected",
        }:
            return result
    return event_identity.IdentityMatchResult(False, event_identity.STRENGTH_NONE, None)


def _matched_symbol_and_coin_id(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> tuple[str | None, str | None]:
    strong = (raw.title, raw.body, _event_name(raw))
    for idx, symbol in enumerate(hypothesis.candidate_symbols):
        coin_id = hypothesis.candidate_coin_ids[idx] if idx < len(hypothesis.candidate_coin_ids) else None
        identity = event_identity.AssetIdentity(
            symbol=symbol,
            coin_id=coin_id,
            project_name=None,
            aliases=(coin_id.replace("-", " ") if coin_id else ""),
            is_common_word_symbol=symbol.upper() in event_identity.COMMON_WORD_SYMBOLS,
        )
        result = event_identity.match_asset_identity(
            identity,
            event_identity.IdentityEvidence(
                strong_content=tuple(str(item or "") for item in strong),
                url=raw.source_url,
                source_origin=(raw.provider,),
            ),
        )
        if result.matched:
            return symbol, coin_id
    return None, None


def _text_mentions_catalyst(text: str, hypothesis: EventImpactHypothesis) -> bool:
    external = clean_text(hypothesis.external_asset or "")
    if external and _term_hit(text, external):
        return True
    category_terms = {
        ImpactCategory.RWA_PREIPO_PROXY.value: ("pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure"),
        ImpactCategory.AI_IPO_PROXY.value: ("openai", "anthropic", "pre ipo", "pre-ipo"),
        ImpactCategory.SPORTS_FAN_PROXY.value: ("world cup", "fan token", "fixture", "kickoff", "sports event"),
        ImpactCategory.STABLECOIN_REGULATORY.value: ("genius act", "stablecoin", "reserve"),
        ImpactCategory.PREDICTION_MARKET_INFRA.value: ("prediction market", "oracle"),
        ImpactCategory.PERP_VENUE_ATTENTION.value: ("perp", "futures listing"),
        ImpactCategory.LISTING_LIQUIDITY_EVENT.value: ("listing", "listed on"),
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value: ("unlock", "vesting", "airdrop"),
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value: ("exploit", "hack", "lawsuit", "regulatory"),
    }.get(hypothesis.impact_category, ())
    return _any_term_hit(text, category_terms)


def _text_mentions_candidate(text: str, hypothesis: EventImpactHypothesis) -> bool:
    return _any_term_hit(text, hypothesis.candidate_symbols)


def _hypothesis_score_components(
    event: NormalizedEvent,
    rule: Mapping[str, Any],
    text: str,
    raws: tuple[RawDiscoveredEvent, ...],
    cluster: event_graph.EventCluster | None,
    *,
    crypto_candidate_assets: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
    suggested_assets: tuple[dict[str, Any], ...],
) -> dict[str, float]:
    source_conf = max((float(raw.source_confidence or 0.0) for raw in raws), default=float(event.confidence or 0.0))
    keyword_hits = sum(
        1 for keyword in (*rule.get("keywords", ()), *rule.get("secondary", ()))
        if _term_hit(text, str(keyword))
    )
    market_confirmation = _market_confirmation_score(raws)
    components = {
        "event_clarity": round(max(float(event.confidence or 0.0), source_conf) * 100, 2),
        "source_quality": round(source_conf * 100, 2),
        "catalyst_strength": round(min(100.0, 35.0 + keyword_hits * 12.0 + (15.0 if event.external_asset else 0.0)), 2),
        "sector_relevance": 80.0 if rule.get("sectors") else 35.0,
        "candidate_asset_strength": round(min(100.0, len(crypto_candidate_assets) * 18.0 + (35.0 if suggested_assets else 0.0)), 2),
        "validation_strength": 95.0 if validated_assets else 0.0,
        "market_confirmation": round(market_confirmation, 2),
        "cluster_confidence": round(max(0.0, min(100.0, float(getattr(cluster, "cluster_confidence", 0) or 0))), 2),
    }
    if event.event_time is not None:
        components["event_time_quality"] = round(max(0.0, min(100.0, float(event.event_time_confidence or 0.0) * 100)), 2)
    if suggested_assets:
        components["llm_candidate_confidence"] = round(max(float(row.get("confidence") or 0.0) for row in suggested_assets) * 100, 2)
    return components


def _weighted_hypothesis_score(components: Mapping[str, float], category: str) -> float:
    weights = {
        "event_clarity": 0.18,
        "source_quality": 0.12,
        "catalyst_strength": 0.18,
        "sector_relevance": 0.10,
        "candidate_asset_strength": 0.14,
        "validation_strength": 0.16,
        "market_confirmation": 0.08,
        "cluster_confidence": 0.04,
    }
    score = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        score += max(0.0, min(100.0, float(components.get(key) or 0.0))) * weight
        weight_sum += weight
    if components.get("event_time_quality") is not None:
        score += max(0.0, min(100.0, float(components.get("event_time_quality") or 0.0))) * 0.04
        weight_sum += 0.04
    if components.get("llm_candidate_confidence") is not None:
        score += max(0.0, min(100.0, float(components.get("llm_candidate_confidence") or 0.0))) * 0.05
        weight_sum += 0.05
    final = score / max(0.01, weight_sum)
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        final = min(final, 55.0)
    return max(0.0, min(100.0, final))


def _market_confirmation_score(raws: Iterable[RawDiscoveredEvent]) -> float:
    best = 0.0
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
        market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
        candidates = (
            ("anomaly_score", anomaly.get("score")),
            ("market_move_volume", market.get("market_move_volume")),
            ("volume_zscore_24h", market.get("volume_zscore_24h")),
            ("return_24h", market.get("return_24h")),
        )
        for key, value in candidates:
            try:
                number = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if key != "anomaly_score" and abs(number) <= 3.0:
                number *= 25.0
            best = max(best, number)
    return max(0.0, min(100.0, best))


def _initial_validation_stage(
    category: str,
    crypto_candidate_assets: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
) -> str:
    if validated_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ValidationStage.CATALYST_LINK_VALIDATED.value
    if crypto_candidate_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ValidationStage.VALIDATION_SEARCH_PENDING.value
    if crypto_candidate_assets:
        return ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value
    return ValidationStage.SECTOR_HYPOTHESIS.value


def _hypothesis_confidence(
    event: NormalizedEvent,
    rule: Mapping[str, Any],
    text: str,
    raws: tuple[RawDiscoveredEvent, ...],
    cluster: event_graph.EventCluster | None,
) -> float:
    source_conf = max((raw.source_confidence for raw in raws), default=event.confidence)
    score = 0.30 + 0.35 * max(float(event.confidence or 0.0), float(source_conf or 0.0))
    if event.external_asset:
        score += 0.08
    if event.event_time is not None:
        score += 0.06 * float(event.event_time_confidence or 0.0)
    keyword_hits = sum(1 for keyword in (*rule.get("keywords", ()), *rule.get("secondary", ())) if _term_hit(text, str(keyword)))
    score += min(0.16, keyword_hits * 0.035)
    if cluster is not None:
        score += min(0.12, max(0, cluster.cluster_confidence) / 1000)
    if rule.get("category") == ImpactCategory.MARKET_ANOMALY_UNKNOWN:
        score = min(score, 0.55)
    return max(0.0, min(1.0, round(score, 4)))


def _hypothesis_warnings(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    category: str,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not event.external_asset and category not in {
        ImpactCategory.LISTING_LIQUIDITY_EVENT.value,
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value,
        ImpactCategory.MARKET_ANOMALY_UNKNOWN.value,
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value,
    }:
        warnings.append("external catalyst inferred from source text only")
    if not raws:
        warnings.append("no raw source evidence attached")
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        warnings.append("no confirmed catalyst; keep store-only until source evidence appears")
    return tuple(warnings)


def _validation_steps(category: str) -> tuple[str, ...]:
    common = (
        "find independent source evidence that names a candidate asset",
        "validate candidate identity outside URL/source-origin fields",
        "confirm the source explicitly links candidate asset to catalyst or sector",
    )
    if category in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
    }:
        return (*common, "verify the asset is proxy venue/instrument rather than publisher noise")
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ("find independent catalyst evidence", "verify move is not purely liquidity/noise")
    return common


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


def _any_term_hit(text: str, terms: Iterable[str]) -> bool:
    return any(_term_hit(text, term) for term in terms)


def _term_hit(text: str, term: str) -> bool:
    source = clean_text(text)
    needle = clean_text(term)
    if not source or not needle:
        return False
    escaped = re.escape(needle).replace("\\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, source) is not None


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
        if current is None or item.confidence > current.confidence:
            by_key[item.hypothesis_id] = item
    return sorted(by_key.values(), key=lambda item: (item.status != HypothesisStatus.VALIDATED.value, -item.confidence, item.hypothesis_id))


def _hypothesis_id(
    event: NormalizedEvent,
    category: str,
    sectors: tuple[str, ...],
    symbols: tuple[str, ...],
) -> str:
    source = "|".join((
        event_graph.cluster_id_for_event(event),
        category,
        ",".join(sectors),
        ",".join(symbols[:8]),
    ))
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"hyp:{digest}"


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
