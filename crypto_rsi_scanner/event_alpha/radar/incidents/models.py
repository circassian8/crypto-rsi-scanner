"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (models)."""

from __future__ import annotations

import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent

INCIDENT_STORE_SCHEMA_VERSION = "event_incident_store_v1"
RELEVANCE_RAW_OBSERVATION = "raw_observation"
RELEVANCE_INCIDENT_CANDIDATE = "incident_candidate"
RELEVANCE_CANONICAL_INCIDENT = "canonical_incident"
RELEVANCE_LINKED_INCIDENT = "linked_incident"
RELEVANCE_ACTIVE_INCIDENT = "active_incident"
RELEVANCE_DIAGNOSTIC_ONLY = "diagnostic_only"
RELEVANCE_REJECTED_INCIDENT = "rejected_incident"
RELEVANCE_EXTERNAL_CONTEXT_ONLY = "external_context_only"
_VISIBLE_RELEVANCE_STATUSES = {
    RELEVANCE_INCIDENT_CANDIDATE,
    RELEVANCE_CANONICAL_INCIDENT,
    RELEVANCE_LINKED_INCIDENT,
    RELEVANCE_ACTIVE_INCIDENT,
}
_DIAGNOSTIC_RELEVANCE_STATUSES = {
    RELEVANCE_RAW_OBSERVATION,
    RELEVANCE_DIAGNOSTIC_ONLY,
    RELEVANCE_REJECTED_INCIDENT,
    RELEVANCE_EXTERNAL_CONTEXT_ONLY,
}
_RAW_RELEVANCE_STATUSES = {
    RELEVANCE_RAW_OBSERVATION,
    RELEVANCE_EXTERNAL_CONTEXT_ONLY,
}
_STRICT_DIAGNOSTIC_RELEVANCE_STATUSES = {
    RELEVANCE_DIAGNOSTIC_ONLY,
    RELEVANCE_REJECTED_INCIDENT,
}
_ACTIVE_WATCHLIST_STATES = {"WATCHLIST", "HIGH_PRIORITY", "EVENT_PASSED", "ARMED", "TRIGGERED_FADE"}
_DIRECT_CRYPTO_ARCHETYPES = {
    "exploit_security_event",
    "alleged_security_event",
    "listing_liquidity_event",
    "strategic_investment",
    "unlock_supply_event",
}
_EXTERNAL_CATALYST_ARCHETYPES = {
    "proxy_attention",
    "rwa_preipo_proxy",
    "ai_ipo_proxy",
    "tokenized_stock_venue",
    "sports_fan_proxy",
}
_EXTERNAL_CONTEXT_ARCHETYPES = {
    "political_event",
    "sports_event",
    "external_proxy_event",
    "prediction_market",
    "geopolitical_event",
}
@dataclass(frozen=True)
class EventIncidentStoreConfig:
    path: Path
    store_diagnostic: bool = False
    store_raw_observations: bool = False
@dataclass(frozen=True)
class IncidentLinkQuality:
    raw_link_count: int = 0
    qualified_link_count: int = 0
    qualified_hypothesis_count: int = 0
    qualified_watchlist_count: int = 0
    weak_link_count: int = 0
    quality_blocked_link_count: int = 0
    unknown_role_link_count: int = 0
    generic_sector_only_link_count: int = 0
    link_quality_reasons: tuple[str, ...] = ()
    link_quality_warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_link_count": self.raw_link_count,
            "qualified_link_count": self.qualified_link_count,
            "qualified_hypothesis_count": self.qualified_hypothesis_count,
            "qualified_watchlist_count": self.qualified_watchlist_count,
            "weak_link_count": self.weak_link_count,
            "quality_blocked_link_count": self.quality_blocked_link_count,
            "unknown_role_link_count": self.unknown_role_link_count,
            "generic_sector_only_link_count": self.generic_sector_only_link_count,
            "sector_only_link_count": self.generic_sector_only_link_count,
            "link_quality_reasons": self.link_quality_reasons,
            "link_quality_warnings": self.link_quality_warnings,
        }
@dataclass(frozen=True)
class EventIncidentStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None
@dataclass(frozen=True)
class EventIncidentStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    historical_rows_available: int = 0
    legacy_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)
