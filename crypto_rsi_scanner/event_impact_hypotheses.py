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
from dataclasses import dataclass, replace
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
    candidate_source: str = "taxonomy"
    hypothesis_scope: str = HypothesisScope.SECTOR.value
    direction_hint: str = "unknown"
    playbook_hint: str | None = None
    confidence: float = 0.0
    evidence_quotes: tuple[str, ...] = ()
    required_validation_steps: tuple[str, ...] = ()
    search_queries: tuple[str, ...] = ()
    status: str = HypothesisStatus.HYPOTHESIS.value
    warnings: tuple[str, ...] = ()
    source_raw_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    validation_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    created_at: str | None = None


DEFAULT_TAXONOMY_PATH = Path("fixtures/event_discovery/event_impact_taxonomy.json")

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
        for raw in rows:
            status, reason, symbol, coin_id = _validation_reason(raw, hypothesis)
            if status == "accepted" and reason:
                reasons.append(reason)
                if symbol:
                    matched_symbols.append(symbol)
                if coin_id:
                    matched_coin_ids.append(coin_id)
            elif reason:
                rejections.append(reason)
        if reasons:
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.VALIDATED.value,
                hypothesis_scope=HypothesisScope.TOKEN.value,
                candidate_symbols=tuple(dict.fromkeys(matched_symbols)) or hypothesis.candidate_symbols,
                candidate_coin_ids=tuple(dict.fromkeys(matched_coin_ids)) or hypothesis.candidate_coin_ids,
                validated_candidate_assets=_merge_asset_rows(
                    hypothesis.validated_candidate_assets,
                    tuple(
                        {
                            "source": "hypothesis_search",
                            "symbol": symbol,
                            "reason": reason,
                        }
                        for reason, symbol in zip(reasons, matched_symbols)
                    ),
                ),
                validation_reasons=tuple(dict.fromkeys((*hypothesis.validation_reasons, *reasons))),
            ))
        elif rejections:
            out.append(replace(
                hypothesis,
                status=HypothesisStatus.REJECTED.value,
                rejection_reasons=tuple(dict.fromkeys((*hypothesis.rejection_reasons, *rejections))),
            ))
        else:
            out.append(hypothesis)
    return tuple(out)


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
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    rows.append("statuses: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    categories: dict[str, int] = {}
    for item in items:
        categories[item.impact_category] = categories.get(item.impact_category, 0) + 1
    rows.append("categories: " + ", ".join(f"{key}={value}" for key, value in sorted(categories.items())))
    rows.append("")
    for item in items[:20]:
        rows.append(
            f"{item.status:<26} conf={item.confidence:.2f} "
            f"{item.impact_category} external={item.external_asset or 'unknown'}"
        )
        rows.append(f"  sectors: {', '.join(item.candidate_sectors) or 'none'}")
        rows.append(f"  symbols: {', '.join(item.candidate_symbols) or 'none'}")
        rows.append(f"  candidate_source={item.candidate_source}")
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
            rows.append("  queries: " + " | ".join(item.search_queries[:4]))
        if item.validation_reasons:
            rows.append("  validated: " + "; ".join(item.validation_reasons[:3]))
        if item.rejection_reasons:
            rows.append("  rejected: " + "; ".join(item.rejection_reasons[:3]))
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
    taxonomy_symbols, taxonomy_coin_ids = _assets_from_taxonomy(sectors, taxonomy)
    suggestion_symbols, suggestion_coin_ids = _assets_from_asset_rows(suggested_assets)
    validated_symbols, validated_coin_ids = _assets_from_asset_rows(validated_assets)
    symbols = tuple(dict.fromkeys((*validated_symbols, *taxonomy_symbols, *suggestion_symbols)))
    coin_ids = tuple(dict.fromkeys((*validated_coin_ids, *taxonomy_coin_ids, *suggestion_coin_ids)))
    scope = _hypothesis_scope(category_value, text)
    if validated_assets:
        scope = HypothesisScope.TOKEN.value
    confidence = _hypothesis_confidence(event, rule, text, raws, cluster)
    quotes = _evidence_quotes(text, (*rule.get("keywords", ()), *rule.get("secondary", ())))
    status = (
        HypothesisStatus.VALIDATION_SEARCH_PENDING.value
        if category != ImpactCategory.MARKET_ANOMALY_UNKNOWN and symbols
        else HypothesisStatus.HYPOTHESIS.value
    )
    if validated_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN:
        status = HypothesisStatus.VALIDATED.value
    candidate_source = _candidate_source(taxonomy_symbols, suggested_assets, validated_assets)
    hypothesis = EventImpactHypothesis(
        hypothesis_id=_hypothesis_id(event, category_value, sectors, symbols),
        event_cluster_id=cluster.cluster_id if cluster else event_graph.cluster_id_for_event(event),
        event_type=str(event.event_type or "unknown"),
        external_asset=event.external_asset,
        impact_category=category_value,
        candidate_sectors=sectors,
        candidate_symbols=symbols,
        candidate_coin_ids=coin_ids,
        suggested_candidate_assets=suggested_assets,
        validated_candidate_assets=validated_assets,
        candidate_source=candidate_source,
        hypothesis_scope=scope,
        direction_hint=str(rule.get("direction") or "unknown"),
        playbook_hint=str(rule.get("playbook") or ""),
        confidence=confidence,
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
    return replace(hypothesis, search_queries=_default_search_queries(hypothesis))


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
    queries: list[str] = []
    external = hypothesis.external_asset or _external_from_category(hypothesis.impact_category)
    category = hypothesis.impact_category
    symbols = hypothesis.candidate_symbols or ("crypto",)
    for symbol in symbols[:8]:
        if category in {ImpactCategory.RWA_PREIPO_PROXY.value, ImpactCategory.TOKENIZED_STOCK_VENUE.value}:
            if external:
                queries.append(f"{symbol} {external} pre-IPO exposure")
                queries.append(f"{symbol} tokenized stock {external}")
            queries.append(f"{symbol} synthetic exposure crypto")
        elif category == ImpactCategory.AI_IPO_PROXY.value:
            target = external or "OpenAI"
            queries.append(f"{symbol} {target} pre-IPO exposure")
            queries.append(f"{symbol} {target} perp")
        elif category == ImpactCategory.SPORTS_FAN_PROXY.value:
            queries.append(f"{symbol} World Cup fan token")
            queries.append(f"{symbol} sports event prediction market")
        elif category == ImpactCategory.STABLECOIN_REGULATORY.value:
            queries.append(f"{symbol} GENIUS Act stablecoin")
            queries.append(f"{symbol} stablecoin reserve regulation")
        elif category == ImpactCategory.PERP_VENUE_ATTENTION.value:
            queries.append(f"{symbol} perp listing")
            queries.append(f"{symbol} futures listing")
        elif category == ImpactCategory.LISTING_LIQUIDITY_EVENT.value:
            queries.append(f"{symbol} listing")
            queries.append(f"{symbol} Binance listing")
        elif category == ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value:
            queries.append(f"{symbol} unlock")
            queries.append(f"{symbol} token vesting unlock")
        elif category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value:
            queries.append(f"{symbol} exploit hack regulatory")
        elif category == ImpactCategory.PREDICTION_MARKET_INFRA.value:
            queries.append(f"{symbol} prediction market oracle")
    return tuple(dict.fromkeys(query for query in queries if query.strip()))


def _external_from_category(category: str) -> str | None:
    if category == ImpactCategory.AI_IPO_PROXY.value:
        return "OpenAI"
    if category == ImpactCategory.RWA_PREIPO_PROXY.value:
        return "SpaceX"
    return None


def _validation_reason(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> tuple[str, str | None, str | None, str | None]:
    text = clean_text(_raw_text(raw))
    if not text:
        return "none", None, None, None
    if not _text_mentions_catalyst(text, hypothesis):
        return (
            "rejected",
            "source mentions candidate context without the catalyst" if _text_mentions_candidate(text, hypothesis) else None,
            None,
            None,
        )
    symbol_match = _identity_match_from_symbols(raw, hypothesis)
    if not symbol_match.matched:
        if _text_mentions_candidate(text, hypothesis):
            return "rejected", symbol_match.reason or "candidate identity rejected", None, None
        return "none", None, None, None
    symbol, coin_id = _matched_symbol_and_coin_id(raw, hypothesis)
    return (
        "accepted",
        f"{symbol_match.reason or 'identity_match'} links candidate to {hypothesis.external_asset or hypothesis.impact_category}",
        symbol,
        coin_id,
    )


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
