"""Structured models for research-only LLM raw-event extraction.

The extractor proposes catalysts, crypto asset mentions, and source-noise terms
from raw event evidence. These models are evidence metadata only; deterministic
resolver/classifier/event-fade gates still decide candidates and alerts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventLLMAssetMentionType(str, Enum):
    PROJECT_OR_TOKEN = "project_or_token"
    TICKER_SYMBOL = "ticker_symbol"
    CONTRACT_ADDRESS = "contract_address"
    PUBLISHER_OR_SOURCE = "publisher_or_source"
    ORDINARY_WORD = "ordinary_word"
    AMBIGUOUS = "ambiguous"


class EventLLMCatalystType(str, Enum):
    IPO_PROXY = "ipo_proxy"
    SPORTS_EVENT = "sports_event"
    PREDICTION_MARKET = "prediction_market"
    EXCHANGE_EVENT = "exchange_event"
    DIRECT_TOKEN_EVENT = "direct_token_event"
    PRODUCT_EVENT = "product_event"
    MARKET_ANOMALY = "market_anomaly"
    UNKNOWN = "unknown"


ASSET_MENTION_TYPE_VALUES = frozenset(item.value for item in EventLLMAssetMentionType)
CATALYST_TYPE_VALUES = frozenset(item.value for item in EventLLMCatalystType)


@dataclass(frozen=True)
class EventLLMExtractionQuote:
    text: str
    source_field: str
    supports: str
    found_in_source: bool = False


@dataclass(frozen=True)
class EventLLMExternalCatalystCandidate:
    name: str | None
    catalyst_type: str
    event_time: str | None
    event_time_confidence: float
    confidence: float
    evidence_quotes: tuple[EventLLMExtractionQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMCryptoAssetMention:
    name: str | None
    symbol: str | None
    coin_id: str | None
    contract_address: str | None
    mention_type: str
    confidence: float
    evidence_quotes: tuple[EventLLMExtractionQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMFalsePositiveTerm:
    text: str
    reason: str
    confidence: float
    evidence_quotes: tuple[EventLLMExtractionQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMEventDateHint:
    text: str
    parsed_event_time: str | None
    confidence: float
    evidence_quotes: tuple[EventLLMExtractionQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMRawEventExtraction:
    schema_version: str
    provider: str
    model: str | None
    prompt_version: str
    raw_id: str
    confidence: float
    external_catalysts: tuple[EventLLMExternalCatalystCandidate, ...]
    crypto_asset_mentions: tuple[EventLLMCryptoAssetMention, ...]
    false_positive_terms: tuple[EventLLMFalsePositiveTerm, ...] = ()
    event_date_hints: tuple[EventLLMEventDateHint, ...] = ()
    suggested_followup_queries: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
