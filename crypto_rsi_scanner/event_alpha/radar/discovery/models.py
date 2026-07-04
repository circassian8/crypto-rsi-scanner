"""Event discovery configuration and schema constants."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
from ....derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
from ..classification import classify_event_asset
from crypto_rsi_scanner.event_core.models import (
    DiscoveredAsset,
    DiscoveredEventFadeCandidate,
    EventAssetLink,
    EventClassification,
    EventDiscoveryResult,
    NormalizedEvent,
    RawDiscoveredEvent,
)
from ....event_providers.binance_announcements import BinanceAnnouncementProvider
from ....event_providers.bybit_announcements import BybitAnnouncementProvider
from ....event_providers.coinmarketcal import CoinMarketCalProvider
from ....event_providers.coingecko_universe import CoinGeckoUniverseProvider
from ....event_providers.cryptopanic import CryptoPanicProvider
from ....event_providers.external_ipo import ExternalIpoProvider
from ....event_providers.gdelt import DEFAULT_GDELT_QUERY, GdeltProvider
from ....event_providers.manual_json import ManualJsonEventProvider, parse_datetime
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ....event_providers.sports_fixtures import SportsFixturesProvider
from ....event_providers.tokenomist import TokenomistProvider
from ..resolver import clean_text, load_asset_aliases, resolve_event_assets
from ....supply_providers.arkham import ArkhamSupplyProvider
from ....supply_providers.dune import DuneSupplyProvider
from ....supply_providers.etherscan import EtherscanSupplyProvider
from ....supply_providers.tokenomist import TokenomistSupplyProvider


log = logging.getLogger(__name__)


VALIDATION_SAMPLE_SCHEMA_VERSION = "event_fade_validation_sample_v1"


VALIDATION_SAMPLE_FIELDS = (
    "schema_version",
    "exported_at",
    "row_type",
    "event_id",
    "raw_ids",
    "raw_providers",
    "raw_titles",
    "raw_content_hashes",
    "event_name",
    "event_type",
    "external_asset",
    "event_time",
    "event_time_confidence",
    "event_time_source",
    "first_seen_time",
    "raw_published_at",
    "raw_fetched_at",
    "published_at_min",
    "published_at_max",
    "fetched_at_min",
    "fetched_at_max",
    "source",
    "source_urls",
    "source_count",
    "asset_coin_id",
    "asset_symbol",
    "asset_name",
    "asset_role",
    "asset_role_confidence",
    "asset_role_reason",
    "asset_role_evidence",
    "link_confidence",
    "match_reason",
    "link_evidence",
    "relationship_type",
    "is_proxy_narrative",
    "is_direct_beneficiary",
    "classifier_confidence",
    "classifier_version",
    "classification_reason",
    "classification_evidence",
    "fade_state",
    "signal_type",
    "fade_score",
    "signal_confidence",
    "eligible",
    "reason_codes",
    "warnings",
    "component_scores",
    "data_quality",
    "missing_data",
    "price",
    "market_cap",
    "volume_24h",
    "spot_volume_24h",
    "return_24h",
    "return_72h",
    "return_7d",
    "volume_zscore_24h",
    "spread_bps",
    "order_book_depth_2pct",
    "perp_available",
    "open_interest",
    "open_interest_24h_change_pct",
    "open_interest_to_market_cap",
    "funding_rate_8h",
    "funding_rate_percentile",
    "futures_volume_24h",
    "perp_spot_volume_ratio",
    "liquidations_24h",
    "long_short_ratio",
    "basis",
    "large_holder_exchange_inflow",
    "cex_inflow_amount",
    "cex_inflow_pct_supply",
    "unlock_amount",
    "unlock_pct_circulating",
    "top_holder_concentration",
    "team_or_mm_wallet_activity",
    "admin_or_mint_risk",
    "rsi_daily",
    "rsi_4h",
    "rsi_weekly",
    "target_overbought_score",
    "btc_risk_on_score",
    "rsi_rollover_confirmed",
    "bearish_rsi_divergence",
    "event_vwap",
    "price_below_event_vwap",
    "failed_reclaim_event_vwap",
    "lower_high_confirmed",
    "first_support_broken",
    "post_event_high",
    "post_event_lower_high",
    "entry_reference_price",
    "invalidation_level",
    "trigger_observed_at",
    "first_seen_at",
    "first_watchlisted_at",
    "first_armed_at",
    "first_triggered_at",
    "last_seen_at",
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_24h",
    "post_event_return_72h",
    "post_event_return_7d",
    "event_time_entry_price",
    "event_time_max_adverse_excursion",
    "event_time_max_favorable_excursion",
    "event_time_post_event_return_24h",
    "event_time_post_event_return_72h",
    "event_time_post_event_return_7d",
    "outcome_price_interval",
    "outcome_price_source",
    "human_event_time",
    "human_event_time_source",
    "human_event_time_confidence",
    "human_event_time_notes",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "human_label",
    "human_notes",
)


@dataclass(frozen=True)
class EventDiscoveryConfig:
    min_link_confidence: float = 0.80
    min_classifier_confidence: float = 0.80
    min_event_time_confidence: float = 0.80
    allow_proxy_venue_trigger: bool = False
    lookback_hours: int = 72
    horizon_days: int = 14
