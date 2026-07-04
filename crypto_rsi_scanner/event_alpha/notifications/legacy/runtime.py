"""Day-1 notification helpers for Event Alpha research alerts.

This module owns delivery state only. It does not rank alerts, mutate
watchlist state, create trades, paper trade, or write normal RSI signal rows.
"""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
import re

from .. import delivery, sender
import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import paths as event_artifact_paths

LANE_DAILY_DIGEST = "daily_digest"
LANE_INSTANT_ESCALATION = "instant_escalation"
LANE_TRIGGERED_FADE = "triggered_fade"
LANE_RESEARCH_REVIEW_DIGEST = "research_review_digest"
LANE_EXPLORATORY_DIGEST = "exploratory_digest"
LANE_HEALTH_HEARTBEAT = "health_heartbeat"

LANES = (
    LANE_DAILY_DIGEST,
    LANE_INSTANT_ESCALATION,
    LANE_TRIGGERED_FADE,
    LANE_RESEARCH_REVIEW_DIGEST,
    LANE_EXPLORATORY_DIGEST,
    LANE_HEALTH_HEARTBEAT,
)

LAST_SENT_META_KEYS = {
    LANE_DAILY_DIGEST: "event_alpha_last_sent_daily_digest_at",
    LANE_INSTANT_ESCALATION: "event_alpha_last_sent_instant_escalation_at",
    LANE_TRIGGERED_FADE: "event_alpha_last_sent_triggered_fade_at",
    LANE_RESEARCH_REVIEW_DIGEST: "event_alpha_last_sent_research_review_digest_at",
    LANE_EXPLORATORY_DIGEST: "event_alpha_last_sent_exploratory_digest_at",
    LANE_HEALTH_HEARTBEAT: "event_alpha_last_sent_health_heartbeat_at",
}

NOTIFICATION_SCOPE_GLOBAL = "global"
NOTIFICATION_SCOPE_NAMESPACE = "namespace"
NOTIFICATION_SCOPE_PROFILE = "profile"
NOTIFICATION_SCOPES = (
    NOTIFICATION_SCOPE_GLOBAL,
    NOTIFICATION_SCOPE_NAMESPACE,
    NOTIFICATION_SCOPE_PROFILE,
)
