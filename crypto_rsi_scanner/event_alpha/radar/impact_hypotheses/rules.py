"""Impact-hypothesis taxonomy and rule matching helpers."""

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
        "category": ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION,
        "keywords": (
            "strategic investment",
            "stake",
            "valuation",
            "acquisition",
            "acquire",
            "buy",
        ),
        "secondary": ("valuation", "stake", "investment", "talks", "confidence", "capital"),
        "sectors": ("direct_token_events", "defi_tokens"),
        "direction": "up",
        "playbook": "direct_event",
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


def _matched_rules(
    text: str,
    event: NormalizedEvent,
    *,
    raws: tuple[RawDiscoveredEvent, ...] = (),
) -> tuple[Mapping[str, Any], ...]:
    event_type = clean_text(event.event_type or "")
    matches: list[Mapping[str, Any]] = []
    frames = event_catalyst_frames.build_catalyst_frames(raws, event=event) if raws else ()
    main_frame, _supporting_frames = event_catalyst_frames.select_main_catalyst_frame(frames, event)
    claims = event_claim_semantics.extract_event_claims(raws) if raws else event_claim_semantics.claims_from_text(text)
    security_ruled_out = event_claim_semantics.has_ruled_out_claim(claims, "exploit")
    security_confirmed = event_claim_semantics.has_confirmed_claim(claims, "exploit")
    unknown_cause = event_claim_semantics.text_has_unknown_cause(text)
    for rule in _CATEGORY_RULES:
        category = rule["category"]
        if (
            category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK
            and main_frame is not None
            and main_frame.event_archetype not in {
                "exploit_security_event",
                "market_dislocation_unknown",
                "policy_or_regulatory_context",
            }
        ):
            continue
        if (
            category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK
            and (security_ruled_out or unknown_cause)
            and not security_confirmed
        ):
            continue
        if (
            category == ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION
            and main_frame is not None
            and main_frame.event_archetype == event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT
        ):
            matches.append(rule)
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
        ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION,
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
        ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION.value,
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value,
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value,
    } and _any_term_hit(text, ("token", "coin", "listed on", "trading pair", "unlock", "airdrop", "tge", "stake", "valuation", "investment")):
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
