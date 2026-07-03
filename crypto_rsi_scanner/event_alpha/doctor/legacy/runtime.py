"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlsplit

from .... import event_alpha_alert_store, event_alpha_artifacts, event_alpha_namespace_status, event_alpha_notification_inbox, event_alpha_quality_fields, event_alpha_router, event_alpha_source_coverage, event_artifact_paths, event_bybit_announcements_preflight, event_coinalyze_preflight, event_core_opportunities, event_core_opportunity_store, event_dex_onchain_readiness, event_integrated_radar, event_live_provider_readiness, event_market_anomaly_scanner, event_market_units, event_official_exchange, event_official_exchange_activation, event_opportunity_verdict, event_unlock_calendar_preflight, event_watchlist
from .... import event_alpha_notification_delivery as _delivery
from ...artifacts import research_cards as event_research_cards
from .. import (
    check_registry,
    consistency_doctor,
    namespace_doctor,
    report as doctor_report,
    safety_doctor,
    schema_doctor,
)
from ..checks import (
    integrated_radar as doctor_integrated_radar_checks,
    notifications as doctor_notification_checks,
    outcomes as doctor_outcome_checks,
    paths as doctor_path_checks,
    provider_readiness as doctor_provider_readiness_checks,
    source_coverage as doctor_source_coverage_checks,
)
from ...radar import derivatives_crowding as event_derivatives_crowding
from ...radar import instrument_resolver as event_instrument_resolver
from ...radar import scheduled_catalysts as event_scheduled_catalysts
from ... import shims as event_alpha_shims

STALE_PRE_CANONICAL_NOTIFICATION_WARNING = (
    "This namespace contains pre-canonical notification delivery rows. Do not use it "
    "for send-readiness. Run notify_llm_deep_rehearsal or fixture final check."
)

_GARBAGE_INCIDENT_SUBJECTS = {
    "about",
    "actions",
    "all",
    "announcements",
    "any",
    "any us",
    "best prediction market apps",
    "bitcoin and mstr are",
    "during",
    "here",
    "however",
    "it",
    "llm",
    "need",
    "non",
    "not",
    "note",
    "only",
    "polymarket invite code sbwire",
    "polymarket referral code sbwire",
    "polymarket world cup volume",
    "when",
    "where",
    "will",
    "yes",
}

__all__ = tuple(name for name in globals() if not name.startswith("__"))
