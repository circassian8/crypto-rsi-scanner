"""Shared data models for event-fade discovery research.

These models describe event discovery evidence and classification. They are
separate from ``event_fade.py`` so discovery can fetch, normalize, resolve, and
classify without adding side effects to the pure fade scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .event_fade import FadeCandidate, FadeSignal


@dataclass(frozen=True)
class RawDiscoveredEvent:
    raw_id: str
    provider: str
    fetched_at: datetime
    published_at: datetime | None
    source_url: str | None
    title: str
    body: str | None
    raw_json: dict[str, Any] | None
    source_confidence: float
    content_hash: str


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    raw_ids: tuple[str, ...]
    event_name: str
    event_type: str
    event_time: datetime | None
    event_time_confidence: float
    first_seen_time: datetime
    source: str
    source_urls: tuple[str, ...]
    external_asset: str | None
    description: str | None
    confidence: float


@dataclass(frozen=True)
class DiscoveredAsset:
    coin_id: str
    symbol: str
    name: str
    market_cap: float | None = None
    volume_24h: float | None = None
    price: float | None = None
    categories: tuple[str, ...] = ()
    contract_addresses: dict[str, str] = field(default_factory=dict)
    source: str = "manual_alias"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAssetLink:
    event_id: str
    coin_id: str
    symbol: str
    name: str
    link_confidence: float
    match_reason: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class EventClassification:
    event_id: str
    coin_id: str
    is_proxy_narrative: bool
    is_direct_beneficiary: bool
    relationship_type: str
    confidence: float
    classifier_version: str
    reason: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveredEventFadeCandidate:
    event: NormalizedEvent
    asset: DiscoveredAsset
    link: EventAssetLink
    classification: EventClassification
    fade_candidate: FadeCandidate | None
    fade_signal: FadeSignal | None
    data_quality: dict[str, Any]


@dataclass(frozen=True)
class EventDiscoveryResult:
    raw_events: tuple[RawDiscoveredEvent, ...]
    normalized_events: tuple[NormalizedEvent, ...]
    links: tuple[EventAssetLink, ...]
    classifications: tuple[EventClassification, ...]
    candidates: tuple[DiscoveredEventFadeCandidate, ...]
