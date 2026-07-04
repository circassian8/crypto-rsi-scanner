"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (identity)."""

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

def _candidate_discovery_asset_present(raw_event: RawDiscoveredEvent) -> bool:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    for key in ("candidate_asset", "asset", "market"):
        value = payload.get(key)
        if not isinstance(value, Mapping):
            continue
        if any(str(value.get(field) or "").strip() for field in ("symbol", "asset_symbol", "coin_id", "id", "name", "project_name", "contract_address", "address")):
            return True
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        mention_type = clean_text(mention.get("mention_type"))
        if mention_type in {"publisher or source", "publisher_or_source", "ordinary word", "ordinary_word", "false positive"}:
            continue
        try:
            confidence = float(mention.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.70:
            continue
        if any(str(mention.get(field) or "").strip() for field in ("symbol", "coin_id", "name", "contract_address")):
            return True
    return False
def _result_mentions_hypothesis_catalyst(raw_event: RawDiscoveredEvent, hypothesis: object | None) -> bool:
    """Return true when a hypothesis-search result still mentions the catalyst context."""
    if hypothesis is None:
        return True
    text = clean_text(" ".join(str(part or "") for part in (
        raw_event.title,
        raw_event.body,
        _event_payload_value(raw_event, "event_name"),
        _event_payload_value(raw_event, "event_type"),
        _event_payload_value(raw_event, "external_asset"),
        _event_payload_value(raw_event, "description"),
    )))
    if not text:
        return False
    external = clean_text(getattr(hypothesis, "external_asset", "") or "")
    if external and _text_contains_term(text, external):
        return True
    category = str(getattr(hypothesis, "impact_category", "") or "")
    terms_by_category = {
        "rwa_preipo_proxy": ("pre ipo", "pre-ipo", "spacex", "tokenized stock", "synthetic exposure"),
        "ai_ipo_proxy": ("openai", "anthropic", "pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure"),
        "tokenized_stock_venue": ("tokenized stock", "stock token", "synthetic exposure", "pre ipo", "pre-ipo"),
        "sports_fan_proxy": ("world cup", "champions league", "fan token", "sports", "fixture", "kickoff"),
        "political_meme_proxy": ("election", "inauguration", "campaign", "debate", "political"),
        "stablecoin_regulatory": ("genius act", "stablecoin", "reserve", "regulation", "regulatory"),
        "prediction_market_infra": ("prediction market", "polymarket", "oracle", "resolution"),
        "perp_venue_attention": ("perp", "perpetual", "futures listing"),
        "unlock_supply_pressure": ("unlock", "vesting", "airdrop", "tge"),
        "listing_liquidity_event": ("listing", "listed on", "binance", "coinbase", "bybit"),
        "security_or_regulatory_shock": ("exploit", "hack", "lawsuit", "regulatory", "sec", "cftc"),
        "market_anomaly_unknown": ("catalyst", "listing", "unlock", "airdrop", "exploit", "partnership"),
    }.get(category, tuple(CATALYST_TERM_WEIGHTS))
    return any(_text_contains_term(text, term) for term in terms_by_category)
def _annotate_hypothesis_search_result(
    raw_event: RawDiscoveredEvent,
    score: int,
    reasons: Iterable[str],
    query: SearchQuery,
) -> RawDiscoveredEvent:
    return _annotate_raw_event(
        raw_event,
        {
            "impact_hypothesis_search": {
                "role": "validation_source_evidence",
                "hypothesis_id": query.anomaly_raw_id,
                "query": query.query,
                "query_type": query.query_type,
                "symbol": query.symbol,
                "score": score,
                "reasons": list(reasons),
                "research_only": True,
            }
        },
    )
def _confidence_threshold(value: float) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.50
    if number <= 1.0:
        number *= 100.0
    return max(0, min(100, int(round(number))))
def result_mentions_anomaly_identity(
    raw_event: RawDiscoveredEvent,
    query: SearchQuery,
    anomaly: RawDiscoveredEvent | None,
) -> bool:
    """Return true when a search result names the anomaly asset, not just a catalyst."""
    return _identity_match_reason(raw_event, query, anomaly) not in {
        None,
        "common_word_identity_rejected",
        "identity_url_only_rejected",
        "identity_source_origin_rejected",
    }
def _identity_match_reason(
    raw_event: RawDiscoveredEvent,
    query: SearchQuery,
    anomaly: RawDiscoveredEvent | None = None,
) -> str | None:
    identity = _query_identity(query, anomaly)
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    strong_fields = (
        raw_event.title,
        raw_event.body,
        _event_name(raw_event),
        event_payload.get("description"),
    )
    result = event_identity.match_asset_identity(
        _shared_identity(identity),
        event_identity.IdentityEvidence(
            strong_content=tuple(str(field or "") for field in strong_fields),
            llm_quotes=(
                event_identity.validated_llm_identity_quotes(payload, strong_fields)
                or ((identity.symbol,) if _llm_extraction_mentions_identity(raw_event, identity) else ())
            ),
            url=str(raw_event.source_url or ""),
            source_origin=(_source_origin_text(raw_event),),
        ),
    )
    return result.reason
def _shared_identity(identity: _AnomalyIdentity) -> event_identity.AssetIdentity:
    return event_identity.AssetIdentity(
        symbol=identity.symbol.upper(),
        coin_id=identity.coin_id,
        project_name=identity.project_name,
        aliases=tuple(identity.aliases),
        contract_addresses=tuple(identity.contract_addresses),
        is_common_word_symbol=identity.is_common_word_symbol,
        identity_terms=tuple(identity.identity_terms),
    )
def _identity_for_raw_event(raw: RawDiscoveredEvent) -> _AnomalyIdentity:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    asset = payload.get("asset") if isinstance(payload.get("asset"), Mapping) else {}
    anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    symbol = _event_symbol(raw)
    coin_id = _first_text(
        market.get("coin_id"),
        asset.get("coin_id"),
        payload.get("coin_id"),
        market.get("id"),
        asset.get("id"),
    )
    project_name = _first_text(
        market.get("name"),
        asset.get("name"),
        payload.get("name"),
        anomaly.get("name"),
    )
    aliases = _tuple_texts(
        market.get("aliases"),
        asset.get("aliases"),
        payload.get("aliases"),
        project_name,
        coin_id.replace("-", " ") if coin_id else None,
    )
    contracts = _contract_addresses(
        market.get("contract_addresses"),
        asset.get("contract_addresses"),
        payload.get("contract_addresses"),
        market.get("contract_address"),
        asset.get("contract_address"),
        payload.get("contract_address"),
    )
    return _AnomalyIdentity(
        symbol=symbol,
        coin_id=coin_id,
        project_name=project_name,
        aliases=aliases,
        contract_addresses=contracts,
    )
def _contract_addresses(*values: object) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            iterable = value.values()
        elif isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = (value,)
        for item in iterable:
            text = str(item or "").strip()
            if text:
                out.append(text.casefold())
    return tuple(dict.fromkeys(out))
def _token_context_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    lower = symbol.casefold()
    return any(
        phrase in text
        for phrase in (
            f"{lower} token",
            f"{lower} coin",
            f"{lower} crypto",
            f"token {lower}",
            f"coin {lower}",
        )
    )
def _contract_in_url_path(source_url: str, address: str) -> bool:
    if not source_url or not address or not _looks_contract_address(address):
        return False
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return False
    path = parsed.path or ""
    query = parsed.query or ""
    address_l = address.casefold()
    if address_l in query.casefold():
        return False
    return address_l in path.casefold()
def _looks_contract_address(address: str) -> bool:
    text = str(address or "").strip()
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", text))
def _source_origin_text(raw_event: RawDiscoveredEvent) -> str:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    values = [
        payload.get("source_origin"),
        payload.get("publisher"),
        payload.get("source_name"),
        payload.get("provider_name"),
        raw_event.provider,
    ]
    if raw_event.source_url:
        try:
            values.append(urlparse(raw_event.source_url).netloc)
        except ValueError:
            pass
    return " ".join(str(value or "") for value in values)
def _identity_in_source_origin(identity: _AnomalyIdentity, origin_text: str) -> bool:
    if not origin_text:
        return False
    symbol = identity.symbol.casefold()
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?![a-z0-9])", origin_text):
        return True
    for term in identity.identity_terms:
        normalized = clean_text(term)
        if normalized and normalized in origin_text:
            return True
    return False
def _identity_in_url_only(identity: _AnomalyIdentity, source_url: str, url_text: str) -> bool:
    if not source_url or not url_text:
        return False
    symbol = identity.symbol.casefold()
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?:usdt)?(?![a-z0-9])", url_text):
        return True
    for term in identity.identity_terms:
        normalized = clean_text(term)
        if normalized and normalized in url_text:
            return True
    for address in identity.contract_addresses:
        if address and address.casefold() in source_url.casefold() and not _contract_in_url_path(source_url, address):
            return True
    return False
def _llm_extraction_mentions_identity(raw_event: RawDiscoveredEvent, identity: _AnomalyIdentity) -> bool:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    extraction = payload.get("llm_extraction") if isinstance(payload.get("llm_extraction"), Mapping) else {}
    mentions = extraction.get("crypto_asset_mentions") if isinstance(extraction.get("crypto_asset_mentions"), list) else []
    symbol = identity.symbol.casefold()
    coin_id = (identity.coin_id or "").casefold()
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
        if mention_type in {"publisher", "source noise", "ordinary word", "false positive"}:
            continue
        mention_coin = str(
            mention.get("resolved_coin_id")
            or mention.get("coin_id")
            or mention.get("asset_coin_id")
            or ""
        ).casefold()
        mention_symbol = str(mention.get("symbol") or "").casefold()
        resolver_validated = bool(
            mention.get("resolver_validated")
            or (coin_id and mention_coin == coin_id)
            or (symbol and mention_symbol == symbol)
        )
        if not (resolver_validated and ((coin_id and mention_coin == coin_id) or (symbol and mention_symbol == symbol))):
            continue
        quotes = mention.get("evidence_quotes")
        if isinstance(quotes, list) and quotes:
            source_text = " ".join(str(part or "") for part in (raw_event.title, raw_event.body, _event_name(raw_event)))
            if not any(
                isinstance(quote, Mapping)
                and str(quote.get("text") or "").strip()
                and str(quote.get("text") or "").strip() in source_text
                for quote in quotes
            ):
                continue
        return True
    return False
def _annotate_raw_event(raw: RawDiscoveredEvent, extra: Mapping[str, Any]) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    payload.update(extra)
    return replace(raw, raw_json=payload, content_hash=_content_hash(payload))
