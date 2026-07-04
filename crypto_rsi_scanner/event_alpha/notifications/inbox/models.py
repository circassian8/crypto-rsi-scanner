"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (models)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
from .... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_router,
    event_core_opportunities,
    event_watchlist,
)
from ...artifacts import research_cards as event_research_cards
from ...radar import core_opportunity_store as event_core_opportunity_store
from .. import delivery
from .. import pipeline as event_alpha_notifications

_INBOX_LEGACY_CONFLICT_CLASSIFICATIONS = {
    event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT,
    event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
}
@dataclass(frozen=True)
class EventAlphaNotificationInboxItem:
    alert_id: str
    alert_key: str
    symbol: str
    coin_id: str
    run_id: str
    tier: str
    playbook: str
    card_path: str
    sent: bool
    would_send: bool
    blocked_by_guard: bool
    delivery_state: str
    reviewed: bool
    reason: str
    final_route_after_quality_gate: str = ""
    final_tier_after_quality_gate: str = ""
    quality_gate_block_reason: str = ""
    alertable_after_quality_gate: bool = True
    snapshot_quality_classification: str = ""
    item_type: str = "core_opportunity"
    is_diagnostic: bool = False
    core_opportunity_id: str = ""
    feedback_target: str = ""
    feedback_target_type: str = ""
    final_state_after_quality_gate: str = ""
    opportunity_level: str = ""
@dataclass(frozen=True)
class EventAlphaReviewQueueItem:
    category: str
    rank_score: float
    symbol: str
    coin_id: str
    tier: str
    route: str
    reason: str
    card_basename: str
    feedback_target: str
    source_item: EventAlphaNotificationInboxItem
@dataclass(frozen=True)
class EventAlphaNotificationInboxResult:
    profile: str
    artifact_namespace: str
    notification_runs_path: Path
    alert_store_path: Path
    feedback_path: Path
    research_cards_dir: Path
    outcomes_path: Path | None
    notification_runs_read: int
    alert_rows_read: int
    feedback_rows_read: int
    research_cards_read: int
    outcome_rows_read: int
    sent_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    partial_delivered_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_blocked_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    weak_validated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    quality_gated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    legacy_quality_conflicts: tuple[EventAlphaNotificationInboxItem, ...]
    research_review_without_feedback: tuple[EventAlphaNotificationInboxItem, ...] = ()
    exploratory_without_feedback: tuple[EventAlphaNotificationInboxItem, ...] = ()
    high_priority_unreviewed: tuple[EventAlphaNotificationInboxItem, ...] = ()
    triggered_fade_unreviewed: tuple[EventAlphaNotificationInboxItem, ...] = ()
    heartbeat_only_runs: tuple[dict[str, Any], ...] = ()
    duplicate_or_in_flight_runs: tuple[dict[str, Any], ...] = ()
    provider_degraded_runs: tuple[dict[str, Any], ...] = ()
    canonical_review_items: tuple[EventAlphaNotificationInboxItem, ...] = ()
    diagnostic_review_items_hidden: tuple[EventAlphaNotificationInboxItem, ...] = ()
    diagnostic_review_items: tuple[EventAlphaNotificationInboxItem, ...] = ()
    canonical_review_items_with_cards: int = 0
    canonical_review_items_with_feedback_targets: int = 0
    diagnostic_review_items_with_feedback_targets: int = 0
    include_diagnostics: bool = False
