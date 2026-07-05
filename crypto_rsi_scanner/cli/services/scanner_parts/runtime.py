from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
import pandas as pd

log = logging.getLogger("crypto_rsi_scanner.scanner")

from .... import config
from ....client import CoinGeckoClient
from ....indicators import (
    adaptive_thresholds,
    annualized_vol,
    btc_correlation,
    conviction_adjustment,
    conviction_score,
    decide_flag,
    detect_divergence,
    rsi_rate_of_change,
    rsi_z_score,
    trend_regime,
    volume_ratio,
    wilder_rsi,
)
from ....signal_registry import market_alignment, regime_note, setup_for
from ....state_features import (
    breadth_snapshot,
    cross_sectional_ranks,
    dollar_volume_20,
    falling_knife_score,
    liquidity_bucket,
    pct_return,
    rank_bucket,
    realized_vol,
    realized_vol_series,
    rolling_beta,
    rolling_multi_beta,
    trailing_percentile,
    volatility_state,
    volume_price_state,
    volume_z_score,
)
from ....notifications import notify_all, send_telegram, send_telegram_structured
from ....storage import Storage
from ....universe import (
    candidate_count,
    filter_markets_with_audit,
    format_audit,
    format_exclusions,
    write_audit,
)
from .... import outcomes
from .... import telegram
from .... import heartbeat
from .... import macro
from .... import paper
from .... import event_fade
import crypto_rsi_scanner.event_alpha.artifacts.cache as event_cache
import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
import crypto_rsi_scanner.event_alpha.artifacts.explain as event_alpha_explain
import crypto_rsi_scanner.event_alpha.config.health_guard as event_alpha_health_guard
import crypto_rsi_scanner.event_alpha.providers.cryptopanic as event_alpha_cryptopanic
import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store
import crypto_rsi_scanner.event_alpha.radar.incidents as event_incident_store
import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
import crypto_rsi_scanner.event_alpha.providers.live_provider_readiness as event_live_provider_readiness
import crypto_rsi_scanner.event_alpha.radar.missed as event_alpha_missed
import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
from ....event_alpha.namespace import lifecycle as event_alpha_namespace_lifecycle
from ....event_alpha.notifications import checklist as event_alpha_notification_checklist
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery
from ....event_alpha.notifications import final_check as event_alpha_telegram_final_check
from ....event_alpha.notifications import go_no_go as event_alpha_notification_go_no_go
from ....event_alpha.notifications import inbox as event_alpha_notification_inbox
from ....event_alpha.notifications import pack as event_alpha_notification_pack
from ....event_alpha.notifications import pause as event_alpha_notification_pause
from ....event_alpha.notifications import pipeline as event_alpha_notifications
from ....event_alpha.notifications import readiness as event_alpha_send_readiness
from ....event_alpha.notifications import recipient_check as event_alpha_telegram_recipient_check
from ....event_alpha.notifications import runs as event_alpha_notification_runs
from ....event_alpha.notifications import sender as event_alpha_notification_sender
from ....event_alpha.notifications import slo as event_alpha_notification_slo
from ....event_alpha.outcomes import burn_in as event_alpha_burn_in
from ....event_alpha.outcomes import burn_in as event_alpha_burn_in_pack
from ....event_alpha.outcomes import burn_in as event_alpha_burn_in_readiness
from ....event_alpha.outcomes import calibration as event_alpha_calibration
from ....event_alpha.outcomes import feedback as event_alpha_eval_export
from ....event_alpha.outcomes import feedback as event_alpha_feedback_readiness
from ....event_alpha.outcomes import integrated_radar_outcomes as event_integrated_radar_outcomes
from ....event_alpha.outcomes import policy_simulator as event_alpha_policy_simulator
from ....event_alpha.outcomes import priors as event_alpha_priors
from ....event_alpha.outcomes import quality as event_alpha_quality_coverage
from ....event_alpha.outcomes import quality as event_alpha_quality_review
from ....event_alpha.outcomes import quality as event_alpha_signal_quality
from ....event_alpha.outcomes import quality as event_alpha_signal_quality_export
from ....event_alpha.outcomes import quality as event_alpha_tuning
import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
import crypto_rsi_scanner.event_alpha.config.preflight as event_alpha_preflight
import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles
import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention
import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
import crypto_rsi_scanner.event_alpha.artifacts.locks as event_alpha_run_lock
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
import crypto_rsi_scanner.event_alpha.config.scheduler as event_alpha_scheduler
import crypto_rsi_scanner.event_alpha.config.v1_readiness as event_alpha_v1_readiness
import crypto_rsi_scanner.event_alpha.doctor.environment as event_alpha_environment_doctor
import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths
import crypto_rsi_scanner.event_alpha.radar.asset_registry as event_asset_registry
import crypto_rsi_scanner.event_alpha.providers.source_reliability as event_source_reliability
import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
import crypto_rsi_scanner.event_core.clock as event_clock
import crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight as event_bybit_announcements_preflight
import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding
import crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness as event_dex_onchain_readiness
import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback
import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange
import crypto_rsi_scanner.event_alpha.providers.official_exchange_activation as event_official_exchange_activation
import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
import crypto_rsi_scanner.event_alpha.radar.price_history as event_price_history
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as event_scheduled_catalysts
import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
import crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight as event_unlock_calendar_preflight
import crypto_rsi_scanner.event_alpha.radar.validation as event_validation
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment as event_watchlist_enrichment
import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market
import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
from ....event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from ....event_providers.binance_announcements import BinanceAnnouncementProvider
from ....event_providers.bybit_announcements import BybitAnnouncementProvider
from ....event_providers.coinmarketcal import CoinMarketCalProvider
from ....event_providers import cryptopanic as cryptopanic_provider
from ....llm_providers.fixture import (
    FixtureLLMCatalystFrameProvider,
    FixtureLLMExtractionProvider,
    FixtureLLMRelationshipProvider,
)
from ....llm_providers.openai_provider import OpenAILLMExtractionProvider, OpenAILLMRelationshipProvider

__all__ = tuple(name for name in globals() if not name.startswith("__"))
