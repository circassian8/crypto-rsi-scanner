"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlsplit

import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths
import crypto_rsi_scanner.event_alpha.artifacts.run_counters as event_alpha_run_counters
import crypto_rsi_scanner.event_alpha.artifacts.operator_state as event_alpha_operator_state
import crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight as event_bybit_announcements_preflight
import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
import crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness as event_dex_onchain_readiness
import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
import crypto_rsi_scanner.event_alpha.providers.live_provider_readiness as event_live_provider_readiness
import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.market_units as event_market_units
import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange
import crypto_rsi_scanner.event_alpha.providers.official_exchange_activation as event_official_exchange_activation
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight as event_unlock_calendar_preflight
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.notifications.delivery as _delivery
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
    operations as doctor_operations_checks,
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
