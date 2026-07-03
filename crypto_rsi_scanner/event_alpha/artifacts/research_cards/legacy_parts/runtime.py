"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from ..... import (
    event_artifact_paths,
    event_alpha_router,
    event_core_opportunities,
    event_core_opportunity_store,
    event_graph,
    event_llm_evidence_planner,
    event_market_units,
    event_opportunity_verdict,
    event_source_packs,
    event_source_registry,
    event_watchlist,
    event_watchlist_monitor,
)
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
