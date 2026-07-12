"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
import crypto_rsi_scanner.event_alpha.radar.market_units as event_market_units
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as event_feedback_eligibility
import crypto_rsi_scanner.event_alpha.outcomes.outcome_eligibility as event_outcome_eligibility
from ... import reason_text as event_alpha_reason_text

CARD_INDEX_GROUPS = (
    "Early Long Research Cards",
    "Confirmed Long Research Cards",
    "Fade / Short-Review Cards",
    "Risk Only Cards",
    "Unconfirmed Research Cards",
    "Core Opportunity Cards",
    "Near-Miss Cards",
    "Local-Only / Quality-Capped Cards",
    "Diagnostic / Source-Noise / Control Cards",
    "Legacy Cards",
)

__all__ = tuple(name for name in globals() if not name.startswith("__"))
