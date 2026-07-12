"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
import crypto_rsi_scanner.event_alpha.artifacts.explain as event_alpha_explain
import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths
import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
import crypto_rsi_scanner.event_alpha.artifacts.run_counters as event_alpha_run_counters
import crypto_rsi_scanner.event_alpha.artifacts.operator_state as event_alpha_operator_state
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.radar.market_units as event_market_units
import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner
import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
import crypto_rsi_scanner.event_alpha.providers.source_reliability as event_source_reliability
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ... import reason_text as event_alpha_reason_text
from ... import research_cards as event_research_cards
from ....outcomes import calibration as event_alpha_calibration
from ....outcomes import feedback_eligibility as event_feedback_eligibility
from ....notifications import pipeline as event_alpha_notifications
from ....notifications import runs as event_alpha_notification_runs
from ....radar import derivatives_crowding as event_derivatives_crowding
from ....radar import scheduled_catalysts as event_scheduled_catalysts

__all__ = tuple(name for name in globals() if not name.startswith("__"))
