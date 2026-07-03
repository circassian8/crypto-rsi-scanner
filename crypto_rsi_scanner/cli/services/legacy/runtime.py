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
from .... import event_cache
from .... import event_discovery
from .... import event_alerts
from .... import event_alpha_artifact_doctor
from .... import event_alpha_artifacts
from .... import event_alpha_alert_store
from .... import event_alpha_daily_brief
from .... import event_alpha_explain
from .... import event_alpha_health_guard
from .... import event_alpha_cryptopanic
from .... import event_impact_hypothesis_store
from .... import event_incident_store
from .... import event_integrated_radar
from .... import event_live_provider_readiness
from .... import event_alpha_missed
from .... import event_alpha_namespace_status
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
from .... import event_alpha_pipeline
from .... import event_alpha_preflight
from .... import event_alpha_profiles
from .... import event_alpha_replay
from .... import event_alpha_retention
from .... import event_alpha_run_ledger
from .... import event_alpha_run_lock
from .... import event_alpha_router
from .... import event_alpha_source_coverage
from .... import event_alpha_scheduler
from .... import event_alpha_v1_readiness
from .... import event_alpha_environment_doctor
from .... import event_artifact_paths
from .... import event_asset_registry
from .... import event_source_reliability
from .... import event_catalyst_search
from .... import event_clock
from .... import event_bybit_announcements_preflight
from .... import event_coinalyze_preflight
from .... import event_core_opportunity_store
from .... import event_derivatives_crowding
from .... import event_dex_onchain_readiness
from .... import event_evidence_acquisition
from .... import event_feedback
from .... import event_llm_analyzer
from .... import event_llm_catalyst_frames
from .... import event_llm_extractor
from .... import event_market_anomaly_scanner
from .... import event_near_miss
from .... import event_official_exchange
from .... import event_official_exchange_activation
from .... import event_opportunity_audit
from .... import event_provider_health
from .... import event_provider_status
from .... import event_price_history
from .... import event_research_cards
from .... import event_scheduled_catalysts
from .... import event_source_enrichment
from .... import event_unlock_calendar_preflight
from .... import event_validation
from .... import event_watchlist
from .... import event_watchlist_enrichment
from .... import event_watchlist_market
from .... import event_watchlist_monitor
from ....event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
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
