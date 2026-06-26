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

from . import (
    event_claim_semantics,
    event_evidence_quality,
    event_graph,
    event_identity,
    event_incident_graph,
    event_incident_store,
    event_impact_path_validator,
    event_market_confirmation,
    event_opportunity_verdict,
)
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
    IMPACT_PATH_VALIDATED = "impact_path_validated"
    MARKET_CONFIRMED = "market_confirmed"
    PROMOTED_TO_RADAR = "promoted_to_radar"
    REJECTED = "rejected"


class ImpactPathReason(str, Enum):
    DIRECT_TOKEN_EVENT = "direct_token_event"
    VENUE_VALUE_CAPTURE = "venue_value_capture"
    FAN_TOKEN_EVENT = "fan_token_event"
    UNLOCK_SUPPLY_EVENT = "unlock_supply_event"
    LISTING_LIQUIDITY_EVENT = "listing_liquidity_event"
    EXPLOIT_SECURITY_EVENT = "exploit_security_event"
    ECOSYSTEM_SECURITY_EVENT = "ecosystem_security_event"
    CAUSE_UNKNOWN_MARKET_DISLOCATION = "cause_unknown_market_dislocation"
    ALLEGED_EXPLOIT_UNCONFIRMED = "alleged_exploit_unconfirmed"
    WEAK_COOCCURRENCE_ONLY = "weak_cooccurrence_only"
    GENERIC_POLICY_ONLY = "generic_policy_only"
    NO_VALUE_CAPTURE_EXPLAINED = "no_value_capture_explained"


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
    generated_queries: tuple[dict[str, Any], ...] = ()
    executed_queries: tuple[dict[str, Any], ...] = ()
    status: str = HypothesisStatus.HYPOTHESIS.value
    warnings: tuple[str, ...] = ()
    source_raw_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    validation_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    rejected_validation_samples: tuple[dict[str, Any], ...] = ()
    why_not_promoted: tuple[str, ...] = ()
    impact_path_reason: str | None = None
    impact_path_type: str | None = None
    impact_path_strength: str | None = None
    candidate_role: str | None = None
    evidence_specificity_score: float | None = None
    required_evidence_met: bool | None = None
    market_confirmation_required: bool | None = None
    digest_eligible_by_impact_path: bool | None = None
    why_digest_ineligible: str | None = None
    opportunity_score_v2: float | None = None
    opportunity_score_components: Mapping[str, float] = field(default_factory=dict)
    evidence_quality_score: float | None = None
    source_class: str | None = None
    evidence_specificity: str | None = None
    evidence_quality_reasons: tuple[str, ...] = ()
    market_confirmation_score: float | None = None
    market_confirmation_level: str | None = None
    market_confirmation_reasons: tuple[str, ...] = ()
    market_confirmation_warnings: tuple[str, ...] = ()
    market_confirmation_missing_fields: tuple[str, ...] = ()
    market_confirmation_summary: str | None = None
    market_context_source: str | None = None
    market_context_timestamp: str | None = None
    market_context_age_seconds: float | None = None
    market_context_data_quality: str | None = None
    market_context_snapshot: Mapping[str, Any] = field(default_factory=dict)
    market_reaction_confirmed: bool | None = None
    causal_mechanism_confirmed: bool | None = None
    incident_confidence: float | None = None
    incident_id: str | None = None
    incident_canonical_name: str | None = None
    incident_event_archetype: str | None = None
    incident_primary_subject: str | None = None
    incident_affected_ecosystem: str | None = None
    incident_cause_status: str | None = None
    incident_market_reaction_observed: bool | None = None
    incident_causal_mechanism_confirmed: bool | None = None
    incident_link_status: str | None = None
    incident_link_reason: str | None = None
    incident_relevance_status: str | None = None
    incident_relevance_score: float | None = None
    incident_relevance_reasons: tuple[str, ...] = ()
    incident_relevance_warnings: tuple[str, ...] = ()
    canonical_persistence_reason: str | None = None
    canonical_incident_name: str | None = None
    event_archetype: str | None = None
    primary_subject: str | None = None
    affected_entity: str | None = None
    affected_ecosystem: str | None = None
    role_confidence: float | None = None
    role_evidence: tuple[str, ...] = ()
    cause_status: str | None = None
    claim_polarities: tuple[str, ...] = ()
    claim_history: tuple[dict[str, Any], ...] = ()
    independent_source_domains: tuple[str, ...] = ()
    conflicting_claims: tuple[str, ...] = ()
    opportunity_score_final: float | None = None
    opportunity_level: str | None = None
    opportunity_verdict_reasons: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    manual_verification_items: tuple[str, ...] = ()
    why_local_only: str | None = None
    why_not_watchlist: str | None = None
    upgrade_requirements: tuple[str, ...] = ()
    downgrade_warnings: tuple[str, ...] = ()
    market_refresh_attempted: bool | None = None
    market_refresh_success: bool | None = None
    market_confirmation_before: float | None = None
    market_confirmation_after: float | None = None
    derivatives_refresh_attempted: bool | None = None
    derivatives_refresh_success: bool | None = None
    supply_refresh_attempted: bool | None = None
    supply_refresh_success: bool | None = None
    derivative_confirmation_reasons: tuple[str, ...] = ()
    supply_confirmation_reasons: tuple[str, ...] = ()
    evidence_refresh_attempted: bool | None = None
    evidence_refresh_results: tuple[dict[str, Any], ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    opportunity_level_before: str | None = None
    opportunity_level_after: str | None = None
    opportunity_score_before: float | None = None
    opportunity_score_after: float | None = None
    upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
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
    ValidationStage.IMPACT_PATH_VALIDATED.value,
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
        "secondary": (
            "oracle",
            "settlement",
            "resolution",
            "infrastructure",
            "data provider",
            "chainlink",
            "uma",
            "pyth",
            "arbitrum",
            "ethereum",
            "smart contract",
            "platform",
        ),
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
        "keywords": (
            "binance listing",
            "exchange listing",
            "coinbase listing",
            "spot listing",
            "listed on",
            "nasdaq listing",
            "public listing",
            "ipo listing",
        ),
        "secondary": ("trading pair", "liquidity", "launch", "market"),
        "sectors": ("direct_token_events",),
        "direction": "volatility",
        "playbook": "listing_volatility",
    },
    {
        "category": ImpactCategory.SECURITY_OR_REGULATORY_SHOCK,
        "keywords": (
            "exploit",
            "hack",
            "lawsuit",
            "sec",
            "cftc",
            "regulatory",
            "security incident",
            "quantum",
            "quantum computing",
            "technology risk",
            "policy shock",
        ),
        "secondary": ("probe", "charges", "investigation", "attack", "risk", "policy"),
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
    incidents = event_incident_graph.build_incidents(result.normalized_events, raw_by_id)
    incidents_by_event = {
        event_id: incident
        for incident in incidents
        for event_id in incident.event_ids
    }
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
        incident = incidents_by_event.get(event.event_id)
        matches = _matched_rules(text, event, raws=raws)
        if not matches and _is_market_anomaly(raws):
            matches = (_market_anomaly_rule(),)
        for rule in matches:
            out.append(_hypothesis_from_rule(
                event,
                raws,
                rule,
                cluster=clusters_by_event.get(event.event_id),
                incident=incident,
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
        impact_path_reason: str | None = hypothesis.impact_path_reason
        impact_validation: event_impact_path_validator.ImpactPathValidation | None = None
        impact_context: tuple[RawDiscoveredEvent, str | None, str | None] | None = None
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
                path_validation = event_impact_path_validator.validate_impact_path(
                    raw,
                    hypothesis,
                    symbol=symbol,
                    coin_id=coin_id,
                    score_components=hypothesis.score_components,
                )
                path_reason = path_validation.impact_path_reason
                preferred = _prefer_impact_validation(impact_validation, path_validation)
                if preferred is path_validation:
                    impact_context = (raw, symbol, coin_id)
                impact_validation = preferred
                if path_reason:
                    impact_path_reason = _prefer_impact_path_reason(impact_path_reason, path_reason)
                    if path_validation.required_evidence_met:
                        best_stage = _max_validation_stage(best_stage, ValidationStage.IMPACT_PATH_VALIDATED.value)
            elif reason:
                rejections.append(reason)
        if reasons and best_stage in _PROMOTABLE_VALIDATION_STAGES:
            if (
                _market_confirmation_score(rows) >= 70
                and best_stage in {
                    ValidationStage.IMPACT_PATH_VALIDATED.value,
                    ValidationStage.MARKET_CONFIRMED.value,
                    ValidationStage.PROMOTED_TO_RADAR.value,
                }
            ):
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
            if impact_path_reason:
                components["impact_path_strength"] = 85.0 if _impact_path_reason_is_strong(impact_path_reason) else 35.0
            quality_kwargs = {}
            if impact_validation is not None:
                components.update(_impact_validation_score_components(impact_validation))
                impact_validation = _refresh_impact_validation_score(impact_validation, components)
                components.update(_impact_validation_score_components(impact_validation))
                quality_kwargs = _quality_verdict_replace_kwargs(
                    impact_validation,
                    impact_context=impact_context,
                    hypothesis=hypothesis,
                    components=components,
                )
                components.update(_quality_score_components(quality_kwargs))
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
                impact_path_reason=impact_path_reason,
                **_impact_validation_replace_kwargs(impact_validation),
                **quality_kwargs,
            ))
        elif reasons:
            components = dict(hypothesis.score_components or {})
            quality_kwargs = {}
            components["validation_strength"] = max(float(components.get("validation_strength") or 0.0), 45.0)
            if impact_path_reason:
                components["impact_path_strength"] = 85.0 if _impact_path_reason_is_strong(impact_path_reason) else 35.0
            if impact_validation is not None:
                components.update(_impact_validation_score_components(impact_validation))
                impact_validation = _refresh_impact_validation_score(impact_validation, components)
                components.update(_impact_validation_score_components(impact_validation))
                quality_kwargs = _quality_verdict_replace_kwargs(
                    impact_validation,
                    impact_context=impact_context,
                    hypothesis=hypothesis,
                    components=components,
                )
                components.update(_quality_score_components(quality_kwargs))
            score = _weighted_hypothesis_score(components, hypothesis.impact_category)
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.VALIDATION_EVIDENCE_FOUND.value,
                validation_stage=best_stage,
                hypothesis_score=round(score, 2),
                confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
                score_components=components,
                validation_reasons=tuple(dict.fromkeys((*hypothesis.validation_reasons, *reasons))),
                impact_path_reason=impact_path_reason,
                **_impact_validation_replace_kwargs(impact_validation),
                **quality_kwargs,
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
    for attr in ("rejected_result_events",):
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
                "result_score": int(getattr(result, "result_score", 0) or 0),
                "rejection_reason": _sample_rejection_reason(reasons),
                "identity_reason": _first_reason_with(reasons, "identity"),
                "catalyst_reason": _first_reason_with(reasons, "catalyst"),
            }
            samples_by_id.setdefault(hypothesis_id, []).append(sample)
    executed_by_id = _executed_queries_by_hypothesis(search_result)
    out: list[EventImpactHypothesis] = []
    for hypothesis in hypotheses:
        samples = samples_by_id.get(hypothesis.hypothesis_id, [])
        executed_queries = executed_by_id.get(hypothesis.hypothesis_id, ())
        if samples:
            merged = tuple(dict.fromkeys(
                json.dumps(sample, sort_keys=True, separators=(",", ":"))
                for sample in (*hypothesis.rejected_validation_samples, *samples)
            ))
            parsed = tuple(json.loads(item) for item in merged[: max(0, max_samples_per_hypothesis)])
            out.append(replace(
                hypothesis,
                rejected_validation_samples=parsed,
                executed_queries=_merge_query_details(hypothesis.executed_queries, executed_queries),
            ))
        else:
            out.append(replace(
                hypothesis,
                executed_queries=_merge_query_details(hypothesis.executed_queries, executed_queries),
            ) if executed_queries else hypothesis)
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
                reasons = tuple(str(value) for value in getattr(result, "result_score_reasons", ()) or ())
                asset = {
                    **asset,
                    "discovery_query": str(getattr(query, "query", "") or ""),
                    "query_type": "candidate_discovery",
                    "result_score": int(getattr(result, "result_score", 0) or 0),
                    "result_score_reasons": reasons[:8],
                    "source_url": str(getattr(raw, "source_url", "") or ""),
                    "discovered_terms": tuple(_candidate_discovered_terms(asset, raw)),
                    "funnel_stage": "candidate_discovery_result",
                    "converted_to_candidate": False,
                    "converted_to_radar": False,
                }
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
        accepted = tuple({
            **asset,
            "accepted": True,
            "rejected": False,
            "resolver_result": "accepted",
            "funnel_stage": "resolver_accepted_candidate",
            "converted_to_candidate": True,
            "converted_to_radar": False,
        } for asset in accepted)
        rejected = tuple({
            **asset,
            "accepted": False,
            "rejected": True,
            "resolver_result": "rejected",
            "funnel_stage": "resolver_rejected_candidate",
            "converted_to_candidate": False,
            "converted_to_radar": False,
            "rejection_reason": asset.get("rejection_reason") or asset.get("identity_rejection_reason") or "identity_validation_failed",
        } for asset in rejected)
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
        "source_title": str(asset.get("source_title") or asset.get("title") or ""),
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
        if item.impact_path_reason:
            rows.append(f"  impact_path_reason: {item.impact_path_reason}")
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
    return "\n".join(rows).rstrip()


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
    claim_rows = event_claim_semantics.extract_event_claims(raws)
    incident = incident or _incident_for_single_event(event, raws)
    if incident is not None:
        score_components.update(_incident_score_components(incident))
        category_value = _category_from_incident(category_value, incident)
        if category_value == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
            rule = {**dict(rule), "category": ImpactCategory.MARKET_ANOMALY_UNKNOWN, "playbook": "market_anomaly_unknown", "direction": "unknown"}
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
        validation_reasons=(
            ("resolver_validated_candidate_asset",) if validated_assets else ()
        ),
        incident_confidence=_optional_score(score_components.get("incident_confidence")) if incident else None,
        incident_id=incident.incident_id if incident else None,
        incident_canonical_name=incident.canonical_name if incident else None,
        incident_event_archetype=incident.event_archetype if incident else None,
        incident_primary_subject=incident.primary_subject if incident else None,
        incident_affected_ecosystem=incident.affected_ecosystem if incident else None,
        incident_cause_status=incident.current_cause_status if incident else None,
        incident_market_reaction_observed=_incident_market_reaction_observed(incident, raws) if incident else None,
        incident_causal_mechanism_confirmed=(
            incident.current_cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value
            if incident
            else None
        ),
        incident_link_status="linked" if incident else "no_incident",
        incident_link_reason=None if incident else "no_canonical_incident_for_event_evidence",
        canonical_incident_name=incident.canonical_name if incident else None,
        event_archetype=incident.event_archetype if incident else None,
        primary_subject=incident.primary_subject if incident else None,
        affected_entity=incident.primary_subject if incident else None,
        affected_ecosystem=incident.affected_ecosystem if incident else None,
        cause_status=incident.current_cause_status if incident else event_claim_semantics.current_cause_status(claim_rows, "exploit"),
        claim_polarities=tuple(dict.fromkeys(claim.polarity for claim in claim_rows)),
        claim_history=tuple(_claim_to_row(claim) for claim in claim_rows[:12]),
        independent_source_domains=incident.independent_source_domains if incident else (),
        conflicting_claims=incident.conflicting_claims if incident else (),
        created_at=now.isoformat(),
    )
    if incident:
        hypothesis = replace(hypothesis, **_incident_relevance_replace_kwargs(incident, raws, hypothesis))
    if validated_assets and raws:
        asset = validated_assets[0]
        validation = event_impact_path_validator.validate_impact_path(
            raws[0],
            hypothesis,
            symbol=str(asset.get("symbol") or (symbols[0] if symbols else "")),
            coin_id=str(asset.get("coin_id") or (coin_ids[0] if coin_ids else "")),
            score_components=score_components,
        )
        updated_components = dict(score_components)
        updated_components.update(_impact_validation_score_components(validation))
        validation = _refresh_impact_validation_score(validation, updated_components)
        updated_components.update(_impact_validation_score_components(validation))
        quality_kwargs = _quality_verdict_replace_kwargs(
            validation,
            impact_context=(raws[0], str(asset.get("symbol") or (symbols[0] if symbols else "")), str(asset.get("coin_id") or (coin_ids[0] if coin_ids else ""))),
            hypothesis=hypothesis,
            components=updated_components,
        )
        updated_components.update(_quality_score_components(quality_kwargs))
        stage = validation_stage
        if validation.required_evidence_met:
            stage = _max_validation_stage(stage, ValidationStage.IMPACT_PATH_VALIDATED.value)
        score = _weighted_hypothesis_score(updated_components, category_value)
        hypothesis = replace(
            hypothesis,
            validation_stage=stage,
            hypothesis_score=round(score, 2),
            confidence=max(0.0, min(1.0, round(score / 100.0, 4))),
            score_components=updated_components,
            impact_path_reason=validation.impact_path_reason,
            **_impact_validation_replace_kwargs(validation),
            **quality_kwargs,
        )
        hypothesis = _with_incident_aliases(hypothesis)
    query_details = _default_search_query_details(hypothesis)
    hypothesis = replace(
        hypothesis,
        search_queries=tuple(str(item.get("query") or "") for item in query_details if item.get("query")),
        search_query_details=query_details,
        generated_queries=query_details,
    )
    return _with_promotion_diagnostics(_with_incident_aliases(hypothesis))


def _matched_rules(
    text: str,
    event: NormalizedEvent,
    *,
    raws: tuple[RawDiscoveredEvent, ...] = (),
) -> tuple[Mapping[str, Any], ...]:
    event_type = clean_text(event.event_type or "")
    matches: list[Mapping[str, Any]] = []
    claims = event_claim_semantics.extract_event_claims(raws) if raws else event_claim_semantics.claims_from_text(text)
    security_ruled_out = event_claim_semantics.has_ruled_out_claim(claims, "exploit")
    security_confirmed = event_claim_semantics.has_confirmed_claim(claims, "exploit")
    unknown_cause = event_claim_semantics.text_has_unknown_cause(text)
    for rule in _CATEGORY_RULES:
        category = rule["category"]
        if (
            category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK
            and (security_ruled_out or unknown_cause)
            and not security_confirmed
        ):
            continue
        if _rule_matches(rule, text, event_type, category):
            matches.append(rule)
    if (security_ruled_out or unknown_cause) and not security_confirmed and _market_dislocation_text(text):
        matches = [rule for rule in matches if rule.get("category") != ImpactCategory.SECURITY_OR_REGULATORY_SHOCK]
        matches.append(_market_anomaly_rule())
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
        if _any_term_hit(text, ("tokenized stock", "tokenized equity", "synthetic exposure")):
            return False
        if _any_term_hit(text, ("quantum", "quantum computing", "technology risk")) and _any_term_hit(text, ("bitcoin", "btc")):
            return False
        if (
            _any_term_hit(text, ("prediction market", "polymarket"))
            and _any_term_hit(text, ("arbitrum", "ethereum", "oracle", "settlement", "infrastructure", "platform"))
            and not _any_term_hit(text, ("election", "inauguration", "campaign", "debate", "vote", "ballot", "candidate", "meme"))
        ):
            return False
        political_context = _has_political_context(text) or _term_hit(event_type, "political")
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


def _market_dislocation_text(text: str) -> bool:
    cleaned = clean_text(text)
    return any(
        term in cleaned
        for term in (
            "crash",
            "crashes",
            "plunge",
            "plunges",
            "dumps",
            "selloff",
            "market anomaly",
            "no clear trigger",
            "cause unknown",
            "no exploit or announcement",
        )
    )


def _incident_for_single_event(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
) -> event_incident_graph.CanonicalIncident | None:
    incidents = event_incident_graph.build_incidents((event,), {raw.raw_id: raw for raw in raws})
    return incidents[0] if incidents else None


def _category_from_incident(category: str, incident: event_incident_graph.CanonicalIncident) -> str:
    if incident.event_archetype == "market_dislocation_unknown":
        return ImpactCategory.MARKET_ANOMALY_UNKNOWN.value
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
    category_rejection = _category_validation_rejection(text, hypothesis)
    if category_rejection:
        return {
            "status": "rejected",
            "validation_stage": ValidationStage.REJECTED.value,
            "reason": category_rejection,
        }
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
    ValidationStage.IMPACT_PATH_VALIDATED.value: 6,
    ValidationStage.MARKET_CONFIRMED.value: 7,
    ValidationStage.PROMOTED_TO_RADAR.value: 8,
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


def _impact_path_reason(
    raw: RawDiscoveredEvent,
    hypothesis: EventImpactHypothesis,
    *,
    symbol: str | None,
    coin_id: str | None,
) -> str | None:
    """Classify whether source evidence explains why the catalyst affects the asset."""
    text = clean_text(_raw_text(raw))
    if not text:
        return None
    category = str(hypothesis.impact_category or "")
    if _generic_policy_without_asset_path(text):
        return ImpactPathReason.GENERIC_POLICY_ONLY.value
    if not _asset_path_terms_present(text, symbol=symbol, coin_id=coin_id):
        return ImpactPathReason.WEAK_COOCCURRENCE_ONLY.value
    if category in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
    }:
        if _any_term_hit(text, ("exposure", "tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo", "trade")):
            return ImpactPathReason.VENUE_VALUE_CAPTURE.value
    if category == ImpactCategory.SPORTS_FAN_PROXY.value:
        if _any_term_hit(text, ("fan token", "world cup", "fixture", "kickoff", "team demand", "sports event")):
            return ImpactPathReason.FAN_TOKEN_EVENT.value
    if category == ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value:
        if _any_term_hit(text, ("unlock", "vesting", "airdrop", "tge", "emission", "claim")):
            return ImpactPathReason.UNLOCK_SUPPLY_EVENT.value
    if category in {ImpactCategory.LISTING_LIQUIDITY_EVENT.value, ImpactCategory.PERP_VENUE_ATTENTION.value}:
        if _any_term_hit(text, ("listing", "listed on", "nasdaq", "public listing", "merger", "trading pair", "perp", "futures")):
            return ImpactPathReason.LISTING_LIQUIDITY_EVENT.value
    if category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value:
        if _any_term_hit(text, ("exploit", "hack", "security incident", "attack", "breach", "resumes trading", "halted trading")):
            return ImpactPathReason.EXPLOIT_SECURITY_EVENT.value
        if _any_term_hit(text, ("lawsuit", "sec", "cftc", "regulatory", "regulation", "probe", "charges", "investigation")):
            return ImpactPathReason.DIRECT_TOKEN_EVENT.value
        return ImpactPathReason.GENERIC_POLICY_ONLY.value
    if category in {
        ImpactCategory.STABLECOIN_REGULATORY.value,
        ImpactCategory.PREDICTION_MARKET_INFRA.value,
        ImpactCategory.POLITICAL_MEME_PROXY.value,
    }:
        if _any_term_hit(text, ("reserve", "settlement", "oracle", "infrastructure", "prediction market", "meme token", "candidate token")):
            return ImpactPathReason.DIRECT_TOKEN_EVENT.value
    return ImpactPathReason.NO_VALUE_CAPTURE_EXPLAINED.value


def _asset_path_terms_present(text: str, *, symbol: str | None, coin_id: str | None) -> bool:
    terms = [symbol, coin_id, str(coin_id or "").replace("-", " ")]
    return any(_term_hit(text, term) for term in terms if str(term or "").strip())


def _generic_policy_without_asset_path(text: str) -> bool:
    policy = _any_term_hit(text, ("policy", "cftc", "regulatory", "regulation", "chair", "order", "government", "quantum"))
    broad = _any_term_hit(text, ("generally", "broad", "industry", "market", "crypto headlines", "technology risk", "quantum computing"))
    direct = _any_term_hit(text, (
        "exploit",
        "hack",
        "listing",
        "listed on",
        "unlock",
        "airdrop",
        "tge",
        "fan token",
        "tokenized stock",
        "synthetic exposure",
    ))
    return policy and broad and not direct


def _impact_path_reason_is_strong(reason: str | None) -> bool:
    return str(reason or "") in {
        ImpactPathReason.DIRECT_TOKEN_EVENT.value,
        ImpactPathReason.VENUE_VALUE_CAPTURE.value,
        ImpactPathReason.FAN_TOKEN_EVENT.value,
        ImpactPathReason.UNLOCK_SUPPLY_EVENT.value,
        ImpactPathReason.LISTING_LIQUIDITY_EVENT.value,
        ImpactPathReason.EXPLOIT_SECURITY_EVENT.value,
    }


def _prefer_impact_path_reason(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    if _impact_path_reason_is_strong(candidate) and not _impact_path_reason_is_strong(current):
        return candidate
    return current


def _prefer_impact_validation(
    current: event_impact_path_validator.ImpactPathValidation | None,
    candidate: event_impact_path_validator.ImpactPathValidation | None,
) -> event_impact_path_validator.ImpactPathValidation | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    strength_rank = {
        "none": 0,
        "weak": 1,
        "medium": 2,
        "strong": 3,
    }
    candidate_key = (
        strength_rank.get(candidate.impact_path_strength, 0),
        float(candidate.opportunity_score_v2 or 0.0),
        float(candidate.evidence_specificity_score or 0.0),
    )
    current_key = (
        strength_rank.get(current.impact_path_strength, 0),
        float(current.opportunity_score_v2 or 0.0),
        float(current.evidence_specificity_score or 0.0),
    )
    return candidate if candidate_key > current_key else current


def _impact_validation_score_components(
    validation: event_impact_path_validator.ImpactPathValidation,
) -> dict[str, float]:
    components = dict(validation.opportunity_score_components or {})
    components["impact_path_strength"] = max(
        float(components.get("impact_path_strength") or 0.0),
        {
            "strong": 95.0,
            "medium": 68.0,
            "weak": 35.0,
            "none": 0.0,
        }.get(validation.impact_path_strength, 0.0),
    )
    components["evidence_specificity"] = float(validation.evidence_specificity_score or 0.0)
    components["opportunity_score_v2"] = float(validation.opportunity_score_v2 or 0.0)
    return components


def _refresh_impact_validation_score(
    validation: event_impact_path_validator.ImpactPathValidation,
    components: Mapping[str, float],
) -> event_impact_path_validator.ImpactPathValidation:
    opportunity = dict(validation.opportunity_score_components or {})
    opportunity["market_confirmation"] = max(
        float(opportunity.get("market_confirmation") or 0.0),
        _component_float(components, "market_confirmation"),
    )
    opportunity["timing_event_window"] = max(
        float(opportunity.get("timing_event_window") or 0.0),
        _component_float(components, "event_time_quality"),
        _component_float(components, "event_clarity"),
    )
    opportunity["liquidity_tradability"] = max(
        float(opportunity.get("liquidity_tradability") or 0.0),
        _component_float(components, "liquidity"),
        _component_float(components, "tradability"),
        _component_float(components, "market_confirmation"),
    )
    opportunity["llm_resolver_confidence"] = max(
        float(opportunity.get("llm_resolver_confidence") or 0.0),
        _component_float(components, "validation_strength"),
        _component_float(components, "llm_candidate_confidence"),
        _component_float(components, "candidate_asset_strength"),
    )
    score = event_impact_path_validator.calculate_opportunity_score_v2(opportunity)
    return replace(
        validation,
        opportunity_score_v2=round(score, 2),
        opportunity_score_components={key: round(value, 2) for key, value in opportunity.items()},
    )


def _component_float(components: Mapping[str, float], key: str) -> float:
    try:
        return max(0.0, min(100.0, float(components.get(key) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _impact_validation_replace_kwargs(
    validation: event_impact_path_validator.ImpactPathValidation | None,
) -> dict[str, Any]:
    if validation is None:
        return {}
    return {
        "impact_path_type": validation.impact_path_type,
        "impact_path_strength": validation.impact_path_strength,
        "candidate_role": validation.candidate_role,
        "evidence_specificity_score": validation.evidence_specificity_score,
        "required_evidence_met": validation.required_evidence_met,
        "market_confirmation_required": validation.market_confirmation_required,
        "digest_eligible_by_impact_path": validation.digest_eligible_by_impact_path,
        "why_digest_ineligible": validation.why_digest_ineligible,
        "opportunity_score_v2": validation.opportunity_score_v2,
        "opportunity_score_components": dict(validation.opportunity_score_components or {}),
        "primary_subject": validation.primary_subject,
        "affected_entity": validation.affected_entity,
        "affected_ecosystem": validation.affected_ecosystem,
        "role_confidence": validation.role_confidence,
        "role_evidence": validation.role_evidence,
        "cause_status": validation.cause_status,
        "claim_polarities": validation.claim_polarities,
    }


def _quality_verdict_replace_kwargs(
    validation: event_impact_path_validator.ImpactPathValidation,
    *,
    impact_context: tuple[RawDiscoveredEvent, str | None, str | None] | None,
    hypothesis: EventImpactHypothesis,
    components: Mapping[str, float],
) -> dict[str, Any]:
    raw, symbol, coin_id = impact_context if impact_context is not None else (None, None, None)
    market_context = resolve_hypothesis_market_context(
        hypothesis,
        discovery_result=None,
        current_cycle_market_rows=(),
        active_watchlist_rows=(),
        targeted_provider=None,
        raw_event=raw,
        validated_coin_id=coin_id,
    )
    payload = raw.raw_json if raw is not None and isinstance(raw.raw_json, Mapping) else {}
    market_result = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=market_context.get("market_snapshot") or _payload_mapping(payload, "market", "market_snapshot"),
            market_anomaly_row=_payload_mapping(payload, "anomaly", "market_anomaly"),
            derivatives_snapshot=_payload_mapping(payload, "derivatives", "derivatives_snapshot"),
            supply_snapshot=_payload_mapping(payload, "supply", "supply_snapshot"),
            btc_context=_payload_mapping(payload, "btc_context"),
            sector_benchmark=_payload_mapping(payload, "sector_benchmark"),
            playbook_type=hypothesis.playbook_hint or hypothesis.impact_category,
            impact_category=hypothesis.impact_category,
        )
    )
    evidence_result = event_evidence_quality.evaluate_evidence_quality(
        raw,
        hypothesis=hypothesis,
        symbol=symbol,
        coin_id=coin_id,
    )
    merged_components = dict(components)
    merged_components.update({
        "market_confirmation": max(
            _component_float(merged_components, "market_confirmation"),
            float(market_result.market_confirmation_score or 0.0),
        ),
        "source_quality": max(
            _component_float(merged_components, "source_quality"),
            float(evidence_result.evidence_quality_score or 0.0),
        ),
        "source_evidence_specificity": max(
            _component_float(merged_components, "source_evidence_specificity"),
            float(validation.evidence_specificity_score or 0.0),
        ),
        "timing_event_window": max(
            _component_float(merged_components, "timing_event_window"),
            _component_float(merged_components, "event_time_quality"),
            _component_float(merged_components, "event_clarity"),
        ),
        "liquidity_tradability": max(
            _component_float(merged_components, "liquidity_tradability"),
            _component_float(merged_components, "liquidity"),
            _component_float(merged_components, "tradability"),
            float(market_result.market_confirmation_score or 0.0),
        ),
        "llm_resolver_confidence": max(
            _component_float(merged_components, "llm_resolver_confidence"),
            _component_float(merged_components, "validation_strength"),
            _component_float(merged_components, "candidate_asset_strength"),
            _component_float(merged_components, "llm_candidate_confidence"),
        ),
    })
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=validation,
        market_confirmation=market_result,
        evidence_quality=evidence_result,
        hypothesis=hypothesis,
        score_components=merged_components,
    )
    upgrade_path = event_opportunity_verdict.explain_upgrade_path(
        verdict=verdict,
        impact_path=validation,
        market_confirmation=market_result,
        evidence_quality=evidence_result,
        components=merged_components,
    )
    return {
        "evidence_quality_score": evidence_result.evidence_quality_score,
        "source_class": evidence_result.source_class,
        "evidence_specificity": evidence_result.evidence_specificity,
        "evidence_quality_reasons": evidence_result.reason_codes,
        "market_confirmation_score": market_result.market_confirmation_score,
        "market_confirmation_level": market_result.level,
        "market_confirmation_reasons": market_result.reasons,
        "market_confirmation_warnings": market_result.warnings,
        "market_confirmation_missing_fields": market_result.missing_fields,
        "market_confirmation_summary": market_result.confirmation_summary,
        "market_context_source": market_context.get("source"),
        "market_context_timestamp": market_context.get("timestamp"),
        "market_context_age_seconds": market_context.get("age_seconds"),
        "market_context_data_quality": market_context.get("data_quality"),
        "market_context_snapshot": dict(market_context.get("market_snapshot") or {}),
        "incident_market_reaction_observed": (
            market_result.level in {"observed", "weak", "moderate", "strong"}
            or bool(market_context.get("source"))
            or bool(market_context.get("market_snapshot"))
        ),
        "market_reaction_confirmed": market_result.level in {"weak", "moderate", "strong"},
        "causal_mechanism_confirmed": _causal_mechanism_confirmed(validation, hypothesis),
        "incident_causal_mechanism_confirmed": _causal_mechanism_confirmed(validation, hypothesis),
        "incident_confidence": _component_float(merged_components, "incident_confidence"),
        "opportunity_score_final": verdict.opportunity_score_final,
        "opportunity_level": verdict.opportunity_level,
        "opportunity_verdict_reasons": verdict.verdict_reason_codes,
        "missing_requirements": verdict.missing_requirements,
        "manual_verification_items": verdict.manual_verification_items,
        "why_local_only": verdict.why_local_only,
        "why_not_watchlist": verdict.why_not_watchlist,
        "upgrade_requirements": upgrade_path.upgrade_requirements,
        "downgrade_warnings": upgrade_path.downgrade_warnings,
    }


def resolve_hypothesis_market_context(
    hypothesis: object,
    discovery_result: object | None = None,
    current_cycle_market_rows: Iterable[Mapping[str, Any]] = (),
    active_watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    targeted_provider: object | None = None,
    *,
    raw_event: RawDiscoveredEvent | None = None,
    validated_coin_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve market context for a hypothesis using a deterministic fallback order."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    coin_id = clean_text(
        validated_coin_id
        or _first_asset_value(getattr(hypothesis, "validated_candidate_assets", ()) or (), "coin_id")
        or (getattr(hypothesis, "candidate_coin_ids", ()) or ("",))[0]
    )
    symbol = clean_text(
        _first_asset_value(getattr(hypothesis, "validated_candidate_assets", ()) or (), "symbol")
        or (getattr(hypothesis, "candidate_symbols", ()) or ("",))[0]
    )
    if raw_event is not None:
        snapshot = _market_snapshot_from_raw(raw_event)
        if snapshot:
            return _market_context_row(snapshot, source="candidate_event_market_snapshot", now=observed)
    for raw in getattr(discovery_result, "raw_events", ()) or ():
        if not isinstance(raw, RawDiscoveredEvent):
            continue
        if _raw_matches_asset(raw, coin_id=coin_id, symbol=symbol):
            snapshot = _market_snapshot_from_raw(raw)
            if snapshot:
                return _market_context_row(snapshot, source="discovery_candidate_market_snapshot", now=observed)
    for row in current_cycle_market_rows:
        if _row_matches_asset(row, coin_id=coin_id, symbol=symbol):
            return _market_context_row(dict(row), source="current_cycle_market_row", now=observed)
    for row in active_watchlist_rows:
        data = row if isinstance(row, Mapping) else getattr(row, "__dict__", {}) or {}
        if not _row_matches_asset(data, coin_id=coin_id, symbol=symbol):
            continue
        snapshot = data.get("latest_market_snapshot") if isinstance(data.get("latest_market_snapshot"), Mapping) else {}
        if snapshot:
            return _market_context_row(dict(snapshot), source="active_watchlist_market_snapshot", now=observed)
    if targeted_provider is not None and coin_id:
        try:
            rows = targeted_provider.fetch_market_rows((coin_id,))  # type: ignore[attr-defined]
        except Exception:
            rows = ()
        for row in rows or ():
            if isinstance(row, Mapping) and _row_matches_asset(row, coin_id=coin_id, symbol=symbol):
                return _market_context_row(dict(row), source="targeted_market_lookup", now=observed)
    return {
        "market_snapshot": {},
        "source": "missing",
        "timestamp": None,
        "age_seconds": None,
        "data_quality": "missing",
        "missing_fields": ("market_snapshot", "current_cycle_market_row", "targeted_market_lookup"),
    }


def _market_snapshot_from_raw(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    snapshot = dict(market)
    for key, value in anomaly.items():
        snapshot.setdefault(key, value)
    return {key: value for key, value in snapshot.items() if value not in (None, "", [], {})}


def _market_context_row(snapshot: Mapping[str, Any], *, source: str, now: datetime) -> dict[str, Any]:
    timestamp = (
        snapshot.get("timestamp")
        or snapshot.get("market_timestamp")
        or snapshot.get("observed_at")
        or snapshot.get("fetched_at")
    )
    age = _age_seconds(timestamp, now)
    quality = "fresh" if age is None or age <= 6 * 3600 else "stale"
    return {
        "market_snapshot": dict(snapshot),
        "source": source,
        "timestamp": str(timestamp) if timestamp not in (None, "") else None,
        "age_seconds": age,
        "data_quality": quality,
        "missing_fields": tuple(_market_missing_fields(snapshot)),
    }


def _market_missing_fields(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    if not any(key in snapshot for key in ("return_24h", "price_change_24h", "price_change_percentage_24h")):
        missing.append("return_24h")
    if not any(key in snapshot for key in ("volume_zscore_24h", "volume_zscore")):
        missing.append("volume_zscore_24h")
    if not any(key in snapshot for key in ("volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")):
        missing.append("volume_to_market_cap")
    return tuple(missing)


def _age_seconds(timestamp: Any, now: datetime) -> float | None:
    if timestamp in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = _as_utc(parsed)
    return max(0.0, (now - parsed).total_seconds())


def _raw_matches_asset(raw: RawDiscoveredEvent, *, coin_id: str, symbol: str) -> bool:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    return _row_matches_asset(market, coin_id=coin_id, symbol=symbol)


def _row_matches_asset(row: Mapping[str, Any], *, coin_id: str, symbol: str) -> bool:
    values = {
        clean_text(row.get("coin_id") or row.get("id") or ""),
        clean_text(row.get("symbol") or ""),
        clean_text(row.get("asset_symbol") or ""),
    }
    return bool((coin_id and coin_id in values) or (symbol and symbol in values))


def _first_asset_value(rows: Iterable[Mapping[str, Any]], key: str) -> str | None:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def _causal_mechanism_confirmed(
    validation: event_impact_path_validator.ImpactPathValidation,
    hypothesis: EventImpactHypothesis,
) -> bool:
    if validation.impact_path_type == event_impact_path_validator.ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value:
        return False
    if validation.cause_status == event_claim_semantics.CauseStatus.RULED_OUT.value:
        return False
    if validation.cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value:
        return True
    return validation.impact_path_strength in {"strong", "medium"} and validation.impact_path_reason not in {
        "cause_unknown_market_dislocation",
        "alleged_exploit_unconfirmed",
        "weak_cooccurrence_only",
        "generic_policy_only",
    }


def _quality_score_components(values: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    mapping = {
        "evidence_quality_score": "evidence_quality_score",
        "source_class": "source_class",
        "evidence_specificity": "evidence_specificity",
        "market_confirmation_score": "market_confirmation_score",
        "market_confirmation_level": "market_confirmation_level",
        "market_context_source": "market_context_source",
        "market_context_timestamp": "market_context_timestamp",
        "market_context_age_seconds": "market_context_age_seconds",
        "market_context_data_quality": "market_context_data_quality",
        "incident_market_reaction_observed": "incident_market_reaction_observed",
        "market_reaction_confirmed": "market_reaction_confirmed",
        "causal_mechanism_confirmed": "causal_mechanism_confirmed",
        "incident_causal_mechanism_confirmed": "incident_causal_mechanism_confirmed",
        "incident_confidence": "incident_confidence",
        "opportunity_score_final": "opportunity_score_final",
        "opportunity_level": "opportunity_level",
        "why_local_only": "why_local_only",
        "why_not_watchlist": "why_not_watchlist",
    }
    for source_key, target_key in mapping.items():
        value = values.get(source_key)
        if value not in (None, "", [], {}):
            out[target_key] = value
    out["market_confirmation"] = max(
        _coerce_score(out.get("market_confirmation_score")),
        _coerce_score(values.get("market_confirmation_score")),
    )
    out["source_quality"] = max(
        _coerce_score(out.get("evidence_quality_score")),
        _coerce_score(values.get("evidence_quality_score")),
    )
    for key in (
        "market_confirmation_reasons",
        "market_confirmation_warnings",
        "market_confirmation_missing_fields",
        "evidence_quality_reasons",
        "opportunity_verdict_reasons",
        "missing_requirements",
        "manual_verification_items",
        "role_evidence",
        "claim_polarities",
    ):
        value = values.get(key)
        if value:
            out[key] = list(value) if not isinstance(value, str) else [value]
    return out


def _payload_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _coerce_score(value: object) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _optional_score(value: object) -> float | None:
    score = _coerce_score(value)
    return score if score > 0 else None


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
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value: (
            "exploit",
            "hack",
            "lawsuit",
            "regulatory",
            "quantum",
            "technology risk",
            "policy shock",
        ),
    }.get(hypothesis.impact_category, ())
    return _any_term_hit(text, category_terms)


def _text_mentions_candidate(text: str, hypothesis: EventImpactHypothesis) -> bool:
    return _any_term_hit(text, hypothesis.candidate_symbols)


def _category_validation_rejection(text: str, hypothesis: EventImpactHypothesis) -> str | None:
    category = str(hypothesis.impact_category or "")
    if category == ImpactCategory.POLITICAL_MEME_PROXY.value and not _has_political_context(text):
        if _any_term_hit(text, ("prediction market", "polymarket", "arbitrum", "ethereum", "tokenized equity")):
            return "political_context_missing_for_prediction_market_validation"
    if category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value and not _has_security_or_regulatory_context(text):
        if _any_term_hit(text, ("nasdaq listing", "public listing", "ipo listing", "listed on", "miner listing")):
            return "security_or_regulatory_context_missing_for_listing_validation"
    return None


def _has_political_context(text: str) -> bool:
    return _any_term_hit(text, (
        "election",
        "inauguration",
        "campaign",
        "debate",
        "vote",
        "political",
        "ballot",
        "candidate",
        "president",
        "senate",
        "congress",
        "trump",
    ))


def _has_security_or_regulatory_context(text: str) -> bool:
    return _any_term_hit(text, (
        "exploit",
        "hack",
        "lawsuit",
        "sec",
        "cftc",
        "regulatory",
        "regulation",
        "quantum",
        "quantum computing",
        "technology risk",
        "policy shock",
        "security incident",
        "probe",
        "charges",
        "investigation",
        "attack",
        "breach",
    ))


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
    if components.get("impact_path_strength") is not None:
        score += max(0.0, min(100.0, float(components.get("impact_path_strength") or 0.0))) * 0.08
        weight_sum += 0.08
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
        if current is None:
            by_key[item.hypothesis_id] = item
            continue
        merged = _merge_duplicate_hypotheses(current, item)
        by_key[item.hypothesis_id] = merged
    return sorted(by_key.values(), key=lambda item: (item.status != HypothesisStatus.VALIDATED.value, -item.confidence, item.hypothesis_id))


def _merge_duplicate_hypotheses(
    current: EventImpactHypothesis,
    item: EventImpactHypothesis,
) -> EventImpactHypothesis:
    winner = item if item.confidence > current.confidence else current
    other = current if winner is item else item
    components = dict(other.score_components or {})
    components.update(dict(winner.score_components or {}))
    components["incident_source_update_count"] = float(len(set((*current.source_raw_ids, *item.source_raw_ids))))
    incident_confidence = max(
        _coerce_score(current.incident_confidence),
        _coerce_score(item.incident_confidence),
        _coerce_score(components.get("incident_confidence")),
    )
    if incident_confidence:
        components["incident_confidence"] = incident_confidence
    incident_observed = bool(current.incident_market_reaction_observed or item.incident_market_reaction_observed)
    incident_causal = bool(current.incident_causal_mechanism_confirmed or item.incident_causal_mechanism_confirmed)
    return replace(
        winner,
        incident_confidence=incident_confidence or winner.incident_confidence,
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
        warnings=tuple(dict.fromkeys((*current.warnings, *item.warnings, "incident_evidence_update"))),
        claim_history=tuple({json.dumps(row, sort_keys=True): row for row in (*current.claim_history, *item.claim_history)}.values()),
        independent_source_domains=tuple(dict.fromkeys((*current.independent_source_domains, *item.independent_source_domains))),
        conflicting_claims=tuple(dict.fromkeys((*current.conflicting_claims, *item.conflicting_claims))),
        score_components=components,
    )


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
