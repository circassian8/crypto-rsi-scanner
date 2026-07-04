"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (query_builder)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse
from .... import event_identity
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_providers.cryptopanic import CryptoPanicProvider, normalize_cryptopanic_currency_code
from ....event_providers.gdelt import GdeltProvider
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ....event_resolver import clean_text
from .models import *  # noqa: F403

def _cryptopanic_currencies_for_query(query: SearchQuery, configured: object = None) -> str:
    if configured not in (None, ""):
        return str(configured)
    code = normalize_cryptopanic_currency_code(
        query.symbol,
        query.coin_id,
        query.aliases,
        identity_validated=bool(query.symbol and query.coin_id),
    )
    return code or ""
def generate_search_queries_for_anomaly(raw_market_anomaly_event: RawDiscoveredEvent) -> tuple[str, ...]:
    """Return deterministic review queries for a market-anomaly raw event."""
    identity = _identity_for_raw_event(raw_market_anomaly_event)
    symbol = identity.symbol
    if not symbol:
        return ()
    queries: list[str] = [template.format(symbol=symbol) for template in QUERY_TEMPLATES]
    if identity.project_name:
        queries.extend((
            f"{identity.project_name} crypto catalyst",
            f"{identity.project_name} Binance listing",
            f"{identity.project_name} token unlock",
            f"{identity.project_name} synthetic exposure",
        ))
    for alias in identity.aliases[:4]:
        if alias and alias.casefold() not in {symbol.casefold(), (identity.project_name or "").casefold()}:
            queries.append(f"{alias} crypto catalyst")
    queries.extend((
        f"{symbol}USDT Binance listing",
        f"{symbol}-USDT perp listing",
    ))
    for address in identity.contract_addresses[:2]:
        queries.append(f"{address} crypto catalyst")
    return tuple(dict.fromkeys(query for query in queries if query.strip()))
def generate_search_queries_for_hypothesis(hypothesis: object) -> tuple[str, ...]:
    """Return targeted validation queries for an Event Alpha impact hypothesis.

    The hypothesis object is intentionally duck-typed to avoid making catalyst
    search depend on hypothesis generation. Results still need resolver and
    identity validation before they can promote anything beyond review evidence.
    """
    return tuple(item.query for item in generate_search_query_specs_for_hypothesis(hypothesis))
def generate_search_query_specs_for_hypothesis(hypothesis: object) -> tuple[HypothesisSearchQuerySpec, ...]:
    """Return typed validation/discovery query specs for an impact hypothesis."""
    category = str(getattr(hypothesis, "impact_category", "") or "")
    external = str(getattr(hypothesis, "external_asset", "") or "").strip()
    symbols = tuple(str(symbol).strip().upper() for symbol in getattr(hypothesis, "candidate_symbols", ()) or () if str(symbol).strip())
    sectors = tuple(str(sector) for sector in getattr(hypothesis, "candidate_sectors", ()) or ())
    out: list[HypothesisSearchQuerySpec] = []
    for symbol in symbols[:8]:
        if external and category in {"rwa_preipo_proxy", "tokenized_stock_venue"}:
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} {external} exposure"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO exposure"),
                HypothesisSearchQuerySpec(f"{symbol} tokenized stock {external}"),
                HypothesisSearchQuerySpec(f"{symbol} {external} prediction market"),
            ))
        elif external and category == "ai_ipo_proxy":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} {external} exposure"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO"),
                HypothesisSearchQuerySpec(f"{symbol} {external} pre-IPO exposure"),
                HypothesisSearchQuerySpec(f"{symbol} tokenized stock {external}"),
                HypothesisSearchQuerySpec(f"{symbol} {external} perp"),
                HypothesisSearchQuerySpec(f"{symbol} AI IPO proxy"),
            ))
        elif category == "sports_fan_proxy":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} World Cup fan token"),
                HypothesisSearchQuerySpec(f"{symbol} sports event prediction market"),
            ))
        elif category == "stablecoin_regulatory":
            out.extend((
                HypothesisSearchQuerySpec(f"{symbol} GENIUS Act stablecoin"),
                HypothesisSearchQuerySpec(f"{symbol} stablecoin reserve regulation"),
            ))
        elif category == "listing_liquidity_event":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} listing"), HypothesisSearchQuerySpec(f"{symbol} Binance listing")))
        elif category == "unlock_supply_pressure":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} unlock"), HypothesisSearchQuerySpec(f"{symbol} token vesting unlock")))
        elif category == "perp_venue_attention":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} perp listing"), HypothesisSearchQuerySpec(f"{symbol} futures listing")))
        elif category == "prediction_market_infra":
            out.extend((HypothesisSearchQuerySpec(f"{symbol} prediction market oracle"), HypothesisSearchQuerySpec(f"{symbol} polymarket infrastructure")))
        elif category == "security_or_regulatory_shock":
            out.append(HypothesisSearchQuerySpec(f"{symbol} exploit hack regulatory"))
        else:
            qtype = "market_confirmation" if category == "market_anomaly_unknown" else "candidate_validation"
            out.append(HypothesisSearchQuerySpec(f"{symbol} crypto catalyst", qtype))
    if external and category in {
        "rwa_preipo_proxy",
        "ai_ipo_proxy",
        "tokenized_stock_venue",
        "sports_fan_proxy",
        "political_meme_proxy",
        "prediction_market_infra",
        "perp_venue_attention",
    }:
        out.extend(HypothesisSearchQuerySpec(query, "candidate_discovery") for query in _candidate_discovery_queries(external, sectors, category))
    elif not out:
        discovery_terms: list[str] = []
        for sector in sectors[:4]:
            clean = sector.replace("_", " ")
            if external:
                discovery_terms.append(f"{external} {clean} crypto")
            else:
                discovery_terms.append(f"{clean} crypto catalyst candidates")
        out.extend(HypothesisSearchQuerySpec(query, "candidate_discovery") for query in discovery_terms)
    deduped: dict[str, HypothesisSearchQuerySpec] = {}
    for item in out:
        query = str(item.query or "").strip()
        if query:
            deduped.setdefault(query, HypothesisSearchQuerySpec(query, item.query_type))
    return tuple(deduped.values())
def _candidate_discovery_queries(external: str, sectors: Iterable[str], category: str) -> tuple[str, ...]:
    sector_rows = tuple(sectors)
    discovery_terms: list[str] = [
        f"{external} crypto exposure",
        f"{external} tokenized stock crypto",
        f"{external} pre-IPO crypto",
        f"{external} prediction market token",
        f"{external} perp crypto",
        f"{external} synthetic exposure crypto",
        f"{external} crypto venue",
    ]
    for sector in sector_rows[:4]:
        clean = str(sector).replace("_", " ").strip()
        if clean:
            discovery_terms.append(f"{external} {clean} crypto")
    if not sector_rows:
        discovery_terms.append(f"{external} {category.replace('_', ' ')} crypto")
    return tuple(discovery_terms)
def generate_search_query_objects_for_anomaly(
    raw_market_anomaly_event: RawDiscoveredEvent,
    *,
    max_queries: int | None = None,
) -> tuple[SearchQuery, ...]:
    identity = _identity_for_raw_event(raw_market_anomaly_event)
    symbol = identity.symbol
    queries = generate_search_queries_for_anomaly(raw_market_anomaly_event)
    if max_queries is not None:
        queries = queries[: max(0, max_queries)]
    out: list[SearchQuery] = []
    for idx, query in enumerate(queries):
        base = SearchQuery(
            anomaly_raw_id=raw_market_anomaly_event.raw_id,
            query=query,
            symbol=symbol,
            rank=idx + 1,
            query_type="market_confirmation",
            coin_id=identity.coin_id,
            project_name=identity.project_name,
            aliases=identity.aliases,
            contract_addresses=identity.contract_addresses,
            is_common_word_symbol=identity.is_common_word_symbol,
            identity_terms=identity.identity_terms,
        )
        score = score_search_query(base, raw_market_anomaly_event)
        out.append(replace(base, score=score.score, score_reasons=score.reason_codes))
    return tuple(out)
def score_search_query(query: SearchQuery, anomaly: RawDiscoveredEvent | None = None) -> CatalystSearchScore:
    """Score a generated search query before using provider budget."""
    payload = anomaly.raw_json if anomaly is not None and isinstance(anomaly.raw_json, Mapping) else {}
    anomaly_payload = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    try:
        anomaly_score = float(anomaly_payload.get("score") or 0.0)
    except (TypeError, ValueError):
        anomaly_score = 0.0
    text = clean_text(query.query)
    score = 15 + min(35, anomaly_score * 0.35)
    reasons = [f"anomaly_score_{int(round(anomaly_score))}"] if anomaly_score else []
    if query.symbol and query.symbol.casefold() in text:
        score += 10
        reasons.append("symbol_in_query")
    catalyst_hits = _weighted_term_hits(text, CATALYST_TERM_WEIGHTS)
    if catalyst_hits:
        score += min(35, sum(CATALYST_TERM_WEIGHTS[hit] for hit in catalyst_hits))
        reasons.append("catalyst_terms:" + ",".join(catalyst_hits[:4]))
    if "why up" in text:
        score -= 8
        reasons.append("generic_why_up_penalty")
    return CatalystSearchScore(max(0, min(100, int(round(score)))), tuple(dict.fromkeys(reasons)))
def _eligible_anomalies(
    raw_events: Iterable[RawDiscoveredEvent],
    cfg: EventCatalystSearchConfig,
) -> tuple[RawDiscoveredEvent, ...]:
    candidates: list[tuple[float, RawDiscoveredEvent]] = []
    for raw in raw_events:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
        try:
            score = float(anomaly.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if raw.provider == "market_anomaly" and score >= cfg.min_anomaly_score:
            candidates.append((score, raw))
    candidates.sort(key=lambda item: (item[0], item[1].raw_id), reverse=True)
    return tuple(raw for _, raw in candidates[: max(0, cfg.max_anomalies)])
def _market_anomaly_events(raw_events: Iterable[RawDiscoveredEvent]) -> tuple[RawDiscoveredEvent, ...]:
    out: list[RawDiscoveredEvent] = []
    for raw in raw_events:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        if raw.provider == "market_anomaly" or isinstance(payload.get("anomaly"), Mapping):
            out.append(raw)
    return tuple(out)
def _queries_for_anomalies(
    anomalies: Iterable[RawDiscoveredEvent],
    cfg: EventCatalystSearchConfig,
) -> tuple[SearchQuery, ...]:
    out: list[SearchQuery] = []
    for anomaly in anomalies:
        out.extend(generate_search_query_objects_for_anomaly(
            anomaly,
            max_queries=cfg.max_queries_per_anomaly,
        ))
    return tuple(out)
def _eligible_hypotheses(
    hypotheses: Iterable[object],
    cfg: EventImpactHypothesisSearchConfig,
) -> tuple[object, ...]:
    candidates: list[tuple[float, str, object]] = []
    for hypothesis in hypotheses:
        try:
            confidence = float(getattr(hypothesis, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        status = str(getattr(hypothesis, "status", "") or "")
        if status == "validated":
            continue
        if confidence < cfg.min_confidence:
            continue
        if not tuple(getattr(hypothesis, "candidate_symbols", ()) or ()) and not (
            str(getattr(hypothesis, "external_asset", "") or "").strip()
            or tuple(getattr(hypothesis, "candidate_sectors", ()) or ())
        ):
            continue
        candidates.append((confidence, str(getattr(hypothesis, "hypothesis_id", "") or ""), hypothesis))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(item[2] for item in candidates[: max(0, cfg.max_hypotheses)])
def _queries_for_hypotheses(
    hypotheses: Iterable[object],
    cfg: EventImpactHypothesisSearchConfig,
) -> tuple[SearchQuery, ...]:
    out: list[SearchQuery] = []
    discovery_count = 0
    for hypothesis in hypotheses:
        all_specs = generate_search_query_specs_for_hypothesis(hypothesis)
        validation_specs = [spec for spec in all_specs if spec.query_type != "candidate_discovery"]
        discovery_specs = [spec for spec in all_specs if spec.query_type == "candidate_discovery"]
        specs = validation_specs[: max(0, cfg.max_queries_per_hypothesis)]
        if cfg.candidate_discovery_enabled and discovery_count < max(0, cfg.max_candidate_discovery_queries):
            room = max(0, cfg.max_candidate_discovery_queries - discovery_count)
            selected = discovery_specs[:room]
            specs = [*specs, *selected]
            discovery_count += len(selected)
        base_queries = tuple(spec.query for spec in specs)
        identity_by_query = _hypothesis_query_identities(hypothesis, base_queries)
        for idx, spec in enumerate(specs):
            query_text = spec.query
            identity = identity_by_query.get(query_text) or _HypothesisIdentity(symbol="SECTOR")
            base = SearchQuery(
                anomaly_raw_id=str(getattr(hypothesis, "hypothesis_id", "") or "hypothesis"),
                query=query_text,
                symbol=identity.symbol,
                rank=idx + 1,
                query_type=spec.query_type,
                coin_id=identity.coin_id,
                project_name=identity.project_name,
                aliases=identity.aliases,
                contract_addresses=identity.contract_addresses,
                is_common_word_symbol=identity.symbol.upper() in COMMON_WORD_SYMBOLS,
                identity_terms=identity.identity_terms,
            )
            score = score_search_query(base, None)
            out.append(replace(base, score=score.score, score_reasons=score.reason_codes))
    return tuple(out)
def _hypothesis_query_identities(hypothesis: object, query_texts: Iterable[str]) -> dict[str, _HypothesisIdentity]:
    symbols = tuple(str(symbol).strip().upper() for symbol in getattr(hypothesis, "candidate_symbols", ()) or () if str(symbol).strip())
    coin_ids = tuple(str(coin_id).strip() for coin_id in getattr(hypothesis, "candidate_coin_ids", ()) or () if str(coin_id).strip())
    out: dict[str, _HypothesisIdentity] = {}
    for query in query_texts:
        query_clean = clean_text(query)
        for idx, symbol in enumerate(symbols):
            if not symbol:
                continue
            coin_id = coin_ids[idx] if idx < len(coin_ids) else None
            symbol_pattern = rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])"
            coin_text = clean_text(coin_id or "")
            if re.search(symbol_pattern, query_clean) or (coin_text and coin_text in query_clean):
                out[query] = _HypothesisIdentity(
                    symbol=symbol,
                    coin_id=coin_id,
                    project_name=coin_id.replace("-", " ").title() if coin_id else None,
                    aliases=(coin_id.replace("-", " ") if coin_id else ""),
                )
                break
    return out
def _raw_event_matches_query(raw: RawDiscoveredEvent, query: SearchQuery) -> bool:
    if result_mentions_anomaly_identity(raw, query, None):
        return True
    text = clean_text(" ".join(str(part or "") for part in (raw.title, raw.body, raw.source_url)))
    if not text:
        return False
    symbol = query.symbol.casefold()
    if symbol and not query.is_common_word_symbol and _case_sensitive_symbol_in_source(raw, query.symbol):
        return True
    query_terms = [
        term for term in clean_text(query.query).split()
        if len(term) >= 4 and term not in {"crypto", "token", "why"}
    ]
    return any(term in text for term in query_terms)
def _query_identity(query: SearchQuery, anomaly: RawDiscoveredEvent | None = None) -> _AnomalyIdentity:
    if query.identity_terms or query.coin_id or query.project_name or query.aliases or query.contract_addresses:
        return _AnomalyIdentity(
            symbol=query.symbol.upper(),
            coin_id=query.coin_id,
            project_name=query.project_name,
            aliases=tuple(query.aliases),
            contract_addresses=tuple(query.contract_addresses),
        )
    if anomaly is not None:
        return _identity_for_raw_event(anomaly)
    return _AnomalyIdentity(symbol=query.symbol.upper(), coin_id=query.coin_id)
