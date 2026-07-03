"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..... import (
    event_alpha_alert_store,
    event_alpha_artifacts,
    event_alpha_explain,
    event_artifact_paths,
    event_coinalyze_preflight,
    event_core_opportunities,
    event_core_opportunity_store,
    event_evidence_acquisition,
    event_near_miss,
    event_alpha_run_ledger,
    event_alpha_router,
    event_alpha_source_coverage,
    event_opportunity_verdict,
    event_market_units,
    event_market_anomaly_scanner,
    event_official_exchange,
    event_source_packs,
    event_source_registry,
    event_source_reliability,
    event_watchlist,
)
from ... import reason_text as event_alpha_reason_text
from ... import research_cards as event_research_cards
from ....outcomes import calibration as event_alpha_calibration
from ....notifications import pipeline as event_alpha_notifications
from ....notifications import runs as event_alpha_notification_runs
from ....radar import derivatives_crowding as event_derivatives_crowding
from ....radar import scheduled_catalysts as event_scheduled_catalysts

__all__ = tuple(name for name in globals() if not name.startswith("__"))
