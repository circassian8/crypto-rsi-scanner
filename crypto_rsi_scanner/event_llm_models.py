"""Structured models for shadow LLM event-relationship analysis.

These models are intentionally separate from event-fade scoring and event-alert
tiering. LLM analysis is advisory research metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventLLMAssetRole(str, Enum):
    PROXY_INSTRUMENT = "proxy_instrument"
    PROXY_VENUE = "proxy_venue"
    INFRASTRUCTURE = "infrastructure"
    DIRECT_BENEFICIARY = "direct_beneficiary"
    MENTIONED_ASSET = "mentioned_asset"
    SOURCE_NOISE = "source_noise"
    TICKER_WORD_COLLISION = "ticker_word_collision"
    AMBIGUOUS = "ambiguous"


class EventLLMRelationshipType(str, Enum):
    PROXY_EXPOSURE = "proxy_exposure"
    PROXY_ATTENTION = "proxy_attention"
    DIRECT_LISTING = "direct_listing"
    DIRECT_UNLOCK = "direct_unlock"
    DIRECT_PROTOCOL_EVENT = "direct_protocol_event"
    INFRASTRUCTURE_PROVIDER = "infrastructure_provider"
    GENERIC_MENTION = "generic_mention"
    PUBLISHER_SUFFIX_FALSE_POSITIVE = "publisher_suffix_false_positive"
    WORD_COLLISION_FALSE_POSITIVE = "word_collision_false_positive"
    UNRELATED = "unrelated"
    AMBIGUOUS = "ambiguous"


class EventLLMRecommendedAlertAction(str, Enum):
    STORE_ONLY = "store_only"
    RADAR_DIGEST = "radar_digest"
    WATCHLIST = "watchlist"
    HIGH_PRIORITY_WATCH = "high_priority_watch"
    TRIGGERED_FADE_NOT_SET_BY_LLM = "triggered_fade_not_set_by_llm"


ASSET_ROLE_VALUES = frozenset(role.value for role in EventLLMAssetRole)
RELATIONSHIP_TYPE_VALUES = frozenset(rel.value for rel in EventLLMRelationshipType)
RECOMMENDED_ALERT_ACTION_VALUES = frozenset(action.value for action in EventLLMRecommendedAlertAction)


@dataclass(frozen=True)
class EventLLMEvidenceQuote:
    text: str
    source_field: str
    supports: str = ""
    found_in_source: bool = True


@dataclass(frozen=True)
class EventLLMSourceQuality:
    source_origin: str | None
    source_confidence: float
    timing_quality: str = "unknown"
    notes: str = ""


@dataclass(frozen=True)
class EventLLMExternalCatalyst:
    name: str | None
    catalyst_type: str
    event_time: str | None = None
    confidence: float = 0.0
    evidence_quotes: tuple[EventLLMEvidenceQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMAssetRelationship:
    coin_id: str
    symbol: str
    asset_role: str
    relationship_type: str
    confidence: float
    reason: str
    evidence_quotes: tuple[EventLLMEvidenceQuote, ...] = ()


@dataclass(frozen=True)
class EventLLMAnalysis:
    schema_version: str
    prompt_version: str
    provider: str
    model: str | None
    event_id: str
    coin_id: str
    symbol: str
    asset_relationship: EventLLMAssetRelationship
    external_catalyst: EventLLMExternalCatalyst
    source_quality: EventLLMSourceQuality
    recommended_alert_action: str
    confidence: float
    evidence_quotes: tuple[EventLLMEvidenceQuote, ...] = ()
    warnings: tuple[str, ...] = ()
    raw_response: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def asset_role(self) -> str:
        return self.asset_relationship.asset_role

    @property
    def relationship_type(self) -> str:
        return self.asset_relationship.relationship_type
