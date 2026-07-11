"""Integrated Event Alpha radar cycle.

This module orchestrates existing research-only Event Alpha sidecars into one
fixture-friendly radar run. It writes local artifacts only: no Telegram sends,
paper trades, normal RSI signal rows, order logic, or event-fade triggers.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Mapping

from ..... import (
    config,
)
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ....artifacts import context as event_alpha_artifacts
from ....artifacts import locks as event_alpha_locks
from ....artifacts import research_cards as event_research_cards
from ....artifacts import paths as event_artifact_paths
from ....artifacts import run_ledger as event_alpha_run_ledger
from ....artifacts import schema_v1
from ....namespace import status as event_alpha_namespace_status
from ....providers import coinalyze_preflight as event_coinalyze_preflight
from ....providers import dex_onchain_readiness as event_dex_onchain_readiness
from ....providers import live_provider_readiness as event_live_provider_readiness
from ....providers import official_exchange as event_official_exchange
from ... import asset_registry as event_asset_registry
from ... import core_opportunity_store as event_core_opportunity_store
from ... import derivatives_crowding as event_derivatives_crowding
from ... import instrument_resolver as event_instrument_resolver
from ... import market_anomaly_scanner as event_market_anomaly_scanner
from ... import market_confirmation as event_market_confirmation
from ... import market_reaction as event_market_reaction
from ... import scheduled_catalysts as event_scheduled_catalysts
from ... import source_coverage as event_alpha_source_coverage


INTEGRATED_CANDIDATES_FILENAME = "event_integrated_radar_candidates.jsonl"
INTEGRATED_REPORT_FILENAME = "event_integrated_radar_report.md"
INTEGRATED_DELIVERIES_FILENAME = "event_integrated_radar_notification_deliveries.jsonl"
INTEGRATED_OUTCOMES_FILENAME = "event_integrated_radar_outcomes.jsonl"
INTEGRATED_OUTCOME_REPORT_FILENAME = "event_integrated_radar_outcome_report.md"
INTEGRATED_CALIBRATION_REPORT_FILENAME = "event_integrated_radar_calibration_report.md"
INTEGRATED_CALIBRATION_PRIORS_FILENAME = "event_integrated_radar_calibration_priors.json"
RADAR_PERFORMANCE_DASHBOARD_FILENAME = "event_radar_performance_dashboard.md"
RADAR_PROVIDER_PERFORMANCE_FILENAME = "event_radar_provider_performance.json"
NOTIFICATION_PREVIEW_FILENAME = "event_integrated_radar_notification_preview.md"
DAILY_BRIEF_FILENAME = "event_alpha_daily_brief.md"
SOURCE_COVERAGE_FILENAME = "event_alpha_source_coverage.md"
SOURCE_COVERAGE_JSON_FILENAME = "event_alpha_source_coverage.json"
INPUT_MANIFEST_FILENAME = "event_integrated_radar_input_manifest.json"
RESEARCH_DISCLAIMER = "Research-only. Not a trade signal, paper trade, live RSI signal, or execution."
INPUT_MODE_AUTO = "auto"
INPUT_MODE_RUN_SIDECARS = "run_sidecars"
INPUT_MODE_LOAD_EXISTING = "load_existing"
INPUT_MODES = {INPUT_MODE_AUTO, INPUT_MODE_RUN_SIDECARS, INPUT_MODE_LOAD_EXISTING}
COINALYZE_AUTO_NAMESPACE = "auto"
COINALYZE_EXTERNAL_SIDECARS = {
    "coinalyze_derivatives_state",
    "coinalyze_derivatives_crowding",
    "coinalyze_fade_review",
}

__all__ = tuple(name for name in globals() if not name.startswith("__"))
