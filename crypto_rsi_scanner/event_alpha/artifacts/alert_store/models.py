"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (models)."""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery

ALERT_STORE_SCHEMA_VERSION = "event_alpha_alert_snapshot_v1"
SNAPSHOT_CURRENT_CLEAN = "current_clean"
SNAPSHOT_QUALITY_GATED_LOCAL = "quality_gated_local"
SNAPSHOT_LEGACY_CONFLICT = "legacy_conflict"
SNAPSHOT_MISSING_FINAL_ROUTE = "missing_final_route"
SNAPSHOT_STALE_PRE_QUALITY_GATE = "stale_pre_quality_gate"
SNAPSHOT_CORE_RECONCILED = "core_reconciled"
SNAPSHOT_MISSING_CORE = "missing_core"
SNAPSHOT_CLASS_CANONICAL_CORE = "canonical_core_snapshot"
SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT = "diagnostic_support_snapshot"
SNAPSHOT_CLASS_LEGACY = "legacy_snapshot"
SNAPSHOT_CLASS_EXTERNAL = "external_snapshot"
SNAPSHOT_CLASS_ORPHAN = "orphan_snapshot"
LEGACY_CONFLICT_CLASSIFICATIONS = {
    SNAPSHOT_LEGACY_CONFLICT,
    SNAPSHOT_MISSING_FINAL_ROUTE,
    SNAPSHOT_STALE_PRE_QUALITY_GATE,
}
@dataclass(frozen=True)
class EventAlphaAlertStoreConfig:
    path: Path
    snapshot_policy: str = "all"
    sampled_controls_limit: int = 25
@dataclass(frozen=True)
class EventAlphaAlertStoreWriteResult:
    path: Path
    observed_at: str
    rows_written: int
    attempted: bool = True
    success: bool = True
    block_reason: str | None = None
@dataclass(frozen=True)
class EventAlphaAlertStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
@dataclass(frozen=True)
class EventAlphaOutcomeFillResult:
    source_path: Path
    price_path: Path
    out_path: Path
    rows_read: int
    rows_written: int
    rows_with_outcomes: int
    missing_price_rows: int
    interval: str | None
    price_source: str | None
