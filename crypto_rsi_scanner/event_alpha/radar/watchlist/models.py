"""Event Alpha watchlist models and constants."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import event_alerts, event_alpha_quality_fields, event_fade, event_graph


WATCHLIST_SCHEMA_VERSION = "event_watchlist_v1"


class EventWatchlistState(str, Enum):
    RAW_EVIDENCE = "RAW_EVIDENCE"
    HYPOTHESIS = "HYPOTHESIS"
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
    RADAR = "RADAR"
    WATCHLIST = "WATCHLIST"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    EVENT_PASSED = "EVENT_PASSED"
    ARMED = "ARMED"
    TRIGGERED_FADE = "TRIGGERED_FADE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


_STATE_RANK = {
    EventWatchlistState.RAW_EVIDENCE.value: 0,
    EventWatchlistState.HYPOTHESIS.value: 1,
    EventWatchlistState.QUALITY_BLOCKED.value: 1,
    EventWatchlistState.RADAR.value: 2,
    EventWatchlistState.WATCHLIST.value: 3,
    EventWatchlistState.HIGH_PRIORITY.value: 4,
    EventWatchlistState.EVENT_PASSED.value: 5,
    EventWatchlistState.ARMED.value: 6,
    EventWatchlistState.TRIGGERED_FADE.value: 7,
    EventWatchlistState.INVALIDATED.value: -1,
    EventWatchlistState.EXPIRED.value: -1,
}


@dataclass(frozen=True)
class EventWatchlistConfig:
    enabled: bool = False
    state_path: Path | None = None
    expire_hours_after_event: float = 72.0
    max_alert_history: int = 20


@dataclass(frozen=True)
class _EventWatchlistIdentityFields:
    schema_version: str
    row_type: str
    key: str
    cluster_id: str | None
    event_id: str
    coin_id: str
    symbol: str
    relationship_type: str
    external_asset: str | None
    event_time: str | None
    state: str
    previous_state: str | None
    first_seen_at: str
    last_seen_at: str


@dataclass(frozen=True)
class _EventWatchlistIncidentFields:
    incident_id: str | None = None
    hypothesis_id: str | None = None
    incident_canonical_name: str | None = None
    incident_primary_subject: str | None = None
    incident_affected_ecosystem: str | None = None
    incident_cause_status: str | None = None
    incident_market_reaction_observed: bool | None = None
    incident_causal_mechanism_confirmed: bool | None = None
    incident_link_status: str | None = None
    incident_link_reason: str | None = None
    requested_state_before_quality_gate: str | None = None
    final_state_after_quality_gate: str | None = None
    quality_state_block_reason: str | None = None
    state_quality_capped: bool = False
    first_radar_at: str | None = None
    first_watchlisted_at: str | None = None
    first_high_priority_at: str | None = None
    first_event_passed_at: str | None = None
    first_armed_at: str | None = None
    first_triggered_at: str | None = None
    first_invalidated_at: str | None = None
    first_expired_at: str | None = None


@dataclass(frozen=True)
class _EventWatchlistLatestFields:
    source_count: int = 0
    highest_score: int = 0
    latest_score: int = 0
    latest_tier: str = ""
    latest_event_name: str = ""
    latest_source: str = ""
    latest_playbook_type: str | None = None
    latest_rule_playbook_type: str | None = None
    latest_effective_playbook_type: str | None = None
    latest_llm_adjusted_playbook_type: str | None = None
    latest_playbook_score: int | None = None
    latest_playbook_action: str | None = None
    latest_llm_asset_role: str | None = None
    latest_llm_confidence: float | None = None
    latest_market_snapshot: dict[str, Any] = field(default_factory=dict)
    latest_score_components: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _EventWatchlistOpportunityFields:
    impact_path_type: str | None = None
    impact_path_strength: str | None = None
    candidate_role: str | None = None
    evidence_quality_score: float | None = None
    source_class: str | None = None
    evidence_specificity: str | None = None
    market_confirmation_score: float | None = None
    market_confirmation_level: str | None = None
    market_context_freshness_status: str | None = None
    market_context_age_hours: float | str | None = None
    market_context_stale: bool | None = None
    market_context_freshness_cap_applied: bool | None = None
    opportunity_score_final: float | None = None
    opportunity_level: str | None = None
    opportunity_verdict_reasons: list[str] = field(default_factory=list)
    why_local_only: str | None = None
    why_not_watchlist: str | None = None
    manual_verification_items: list[str] = field(default_factory=list)
    upgrade_requirements: list[str] = field(default_factory=list)
    downgrade_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _EventWatchlistChangeFields:
    alert_history: list[dict[str, Any]] = field(default_factory=list)
    state_changed: bool = False
    escalation: bool = False
    score_jump: int = 0
    source_count_increased: bool = False
    event_time_upgraded: bool = False
    derivatives_crowding_upgraded: bool = False
    cluster_confidence_upgraded: bool = False
    material_change_reasons: tuple[str, ...] = ()
    should_alert: bool = False
    suppressed_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventWatchlistEntry(
    _EventWatchlistChangeFields,
    _EventWatchlistOpportunityFields,
    _EventWatchlistLatestFields,
    _EventWatchlistIncidentFields,
    _EventWatchlistIdentityFields,
):
    pass


@dataclass(frozen=True)
class EventWatchlistRefreshResult:
    state_path: Path
    observed_at: str
    rows_written: int
    entries: list[EventWatchlistEntry]
    alert_entries: list[EventWatchlistEntry]


@dataclass(frozen=True)
class EventWatchlistReadResult:
    state_path: Path
    rows_read: int
    entries: list[EventWatchlistEntry]
    latest_only: bool
