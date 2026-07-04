"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (models)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from .... import event_provider_status
from ....event_providers import cryptopanic as cryptopanic_provider
from ...artifacts import paths as event_artifact_paths
from ...providers import bybit_announcements_preflight as event_bybit_announcements_preflight
from ...providers import coinalyze_preflight as event_coinalyze_preflight
from ...providers import dex_onchain_readiness as event_dex_onchain_readiness
from ...providers import official_exchange_activation as event_official_exchange_activation
from ...providers import provider_health as event_provider_health
from ...providers import source_packs as event_source_packs
from ...providers import unlock_calendar_preflight as event_unlock_calendar_preflight

SOURCE_COVERAGE_PACK_ORDER = (
    "official_exchange_listing_pack",
    "official_perp_listing_pack",
    "official_exchange_risk_pack",
    "proxy_preipo_rwa_pack",
    "strategic_investment_pack",
    "security_shock_pack",
    "listing_liquidity_pack",
    "fan_sports_pack",
    "market_anomaly_pack",
    "dex_liquidity_pack",
    "unlock_supply_pack",
    "perp_listing_squeeze_pack",
)
_READY_PROVIDER_ALIASES = {
    "binance_announcements": "binance_announcements_public_or_fixture",
    "binance_announcements_public_or_fixture": "binance_announcements_public_or_fixture",
    "binance_announcements_signed_listener": "binance_announcements_signed_listener",
    "bybit_announcements": "bybit_announcements_public",
    "bybit_announcements_public": "bybit_announcements_public",
    "coinmarketcal_calendar": "coinmarketcal",
    "coinmarketcal": "coinmarketcal",
    "tokenomist_unlocks": "tokenomist",
    "tokenomist_supply": "tokenomist",
    "tokenomist": "tokenomist",
    "messari_unlocks": "messari_unlocks",
    "cryptopanic_news": "cryptopanic",
    "gdelt_news": "gdelt",
    "project_blog_rss": "project_blog_rss",
    "sports_fixtures": "sports_fixtures",
    "prediction_market_events": "polymarket",
    "coinalyze_derivatives": "coinalyze",
    "coingecko_universe": "coingecko",
    "geckoterminal": "geckoterminal",
    "coingecko_dex": "coingecko_dex",
    "defillama_tvl_fees_revenue": "defillama_tvl_fees_revenue",
}
_HEALTH_PROVIDER_ALIASES = {
    "binance_announcements_signed_listener": "binance_announcements_signed_listener",
    "signed_listener": "binance_announcements_signed_listener",
    "binance": "binance_announcements_public_or_fixture",
    "bybit": "bybit_announcements_public",
    "cryptopanic": "cryptopanic",
    "gdelt": "gdelt",
    "rss": "project_blog_rss",
    "project_blog_rss": "project_blog_rss",
    "polymarket": "polymarket",
    "coinalyze": "coinalyze",
    "coingecko": "coingecko",
    "tokenomist": "tokenomist",
    "messari_unlocks": "messari_unlocks",
    "messari": "messari_unlocks",
    "coinmarketcal": "coinmarketcal",
    "coinmarketcal": "coinmarketcal",
    "sports_fixtures": "sports_fixtures",
    "defillama": "defillama",
    "defillama_tvl_fees_revenue": "defillama_tvl_fees_revenue",
    "geckoterminal": "geckoterminal",
    "coingecko_dex": "coingecko_dex",
}
_HIGH_SPECIFICITY_PROVIDERS = {
    "binance_announcements_public_or_fixture",
    "binance_announcements_signed_listener",
    "bybit_announcements_public",
    "coinmarketcal",
    "tokenomist",
    "messari_unlocks",
    "cryptopanic",
    "project_blog_rss",
    "coinalyze",
    "coingecko",
    "defillama",
    "defillama_tvl_fees_revenue",
    "geckoterminal",
    "coingecko_dex",
}
_BROAD_CONTEXT_PROVIDERS = {"gdelt", "polymarket"}
_COVERAGE_GAP_STATUSES = {
    "skipped_budget",
    "no_results",
    "rejected_results_only",
    "provider_unavailable",
    "provider_backoff",
    "failed_soft",
    "skipped_config",
}
_COVERAGE_GAP_REASONS = {
    "live_confirmation_missing",
    "evidence_acquisition_not_confirming",
    "source_pack_confirmation_missing",
    "sector_only_digest_not_allowed",
    "rejected_results_only_not_confirmation",
    "skipped_budget_not_confirmation",
    "no_results_not_confirmation",
    "provider_unavailable_not_confirmation",
    "source_pack_confirmation_missing",
}
SOURCE_COVERAGE_CATEGORY_PRIORITIES: tuple[dict[str, Any], ...] = (
    {
        "category": "Derivatives/OI/funding",
        "providers": ("coinalyze",),
        "enabled_lanes": ("FADE_SHORT_REVIEW", "CONFIRMED_LONG_RESEARCH", "perp_listing_squeeze_pack"),
        "reason": "enables fade/short-review crowding checks and confirmed-long crowding warnings",
    },
    {
        "category": "Official exchange announcements",
        "providers": (
            "bybit_announcements_public",
            "binance_announcements_public_or_fixture",
            "binance_announcements_signed_listener",
            "okx_announcements",
            "coinbase",
        ),
        "enabled_lanes": ("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "listing/perp/risk packs"),
        "reason": "validates listing, perp, delisting, launchpool, and exchange-specific catalyst identity",
    },
    {
        "category": "Structured unlock/calendar",
        "providers": ("tokenomist", "messari_unlocks", "coinmarketcal"),
        "enabled_lanes": ("RISK_ONLY", "EARLY_LONG_RESEARCH", "scheduled catalyst monitoring"),
        "reason": "separates dated unlock/supply risk from generic news co-occurrence",
    },
    {
        "category": "DEX/on-chain liquidity",
        "providers": ("geckoterminal", "coingecko_dex"),
        "enabled_lanes": ("market anomaly confirmation", "DEX-native moves"),
        "reason": "confirms whether market anomalies have real DEX liquidity and turnover support",
    },
    {
        "category": "Protocol fundamentals",
        "providers": ("defillama_tvl_fees_revenue", "defillama", "project official metrics"),
        "enabled_lanes": ("strategic investment", "protocol fundamentals", "risk review"),
        "reason": "adds non-price context for protocol-specific catalysts",
    },
    {
        "category": "Context/news",
        "providers": ("cryptopanic", "rss", "gdelt"),
        "enabled_lanes": ("research review", "contextual catalyst discovery"),
        "reason": "discovers narratives, but cannot alone unlock strict confirmed lanes",
    },
)
LIVE_PROVIDER_READINESS_JSON = "event_live_provider_activation_readiness.json"
LIVE_PROVIDER_READINESS_MD = "event_live_provider_activation_readiness.md"
@dataclass(frozen=True)
class EventAlphaSourceCoveragePack:
    source_pack: str
    configured_providers: tuple[str, ...]
    missing_providers: tuple[str, ...]
    healthy_providers: tuple[str, ...]
    unknown_or_unobserved_providers: tuple[str, ...]
    degraded_or_backoff_providers: tuple[str, ...]
    provider_coverage_status: str
    provider_role_statuses: tuple[str, ...]
    evidence_absence_meaningful: bool
    coverage_gap_reason: str | None = None
    providers_missing_for_confirmation: tuple[str, ...] = ()
    providers_degraded_for_confirmation: tuple[str, ...] = ()
    candidates_blocked_by_coverage_gap: int = 0
    accepted_evidence_count: int = 0
    rejected_only_count: int = 0
    skipped_budget_count: int = 0
    provider_unavailable_count: int = 0
    article_quality_counts: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_pack": self.source_pack,
            "configured_providers": list(self.configured_providers),
            "missing_providers": list(self.missing_providers),
            "healthy_providers": list(self.healthy_providers),
            "unknown_or_unobserved_providers": list(self.unknown_or_unobserved_providers),
            "degraded_or_backoff_providers": list(self.degraded_or_backoff_providers),
            "provider_coverage_status": self.provider_coverage_status,
            "source_pack_coverage_status": self.provider_coverage_status,
            "provider_role_statuses": list(self.provider_role_statuses),
            "evidence_absence_meaningful": self.evidence_absence_meaningful,
            "coverage_gap_reason": self.coverage_gap_reason,
            "source_coverage_gap_reason": self.coverage_gap_reason,
            "providers_missing_for_confirmation": list(self.providers_missing_for_confirmation),
            "providers_degraded_for_confirmation": list(self.providers_degraded_for_confirmation),
            "candidates_blocked_by_coverage_gap": self.candidates_blocked_by_coverage_gap,
            "accepted_evidence_count": self.accepted_evidence_count,
            "rejected_only_count": self.rejected_only_count,
            "skipped_budget_count": self.skipped_budget_count,
            "provider_unavailable_count": self.provider_unavailable_count,
            "article_quality_counts": list(self.article_quality_counts),
            "recommended_actions": list(self.recommended_actions),
        }
@dataclass(frozen=True)
class EventAlphaSourceCoverageReport:
    profile: str
    artifact_namespace: str
    packs: tuple[EventAlphaSourceCoveragePack, ...]
    provider_health_rows: int = 0
    acquisition_rows: int = 0
    core_rows: int = 0
    cryptopanic_configured: bool = False
    cryptopanic_health_status: str = "not_observed"
    cryptopanic_observed: bool = False
    cryptopanic_requests_used: int = 0
    cryptopanic_rolling_7d_requests: int = 0
    cryptopanic_remaining_weekly: int | None = None
    cryptopanic_accepted_evidence: int = 0
    cryptopanic_rejected_evidence: int = 0
    cryptopanic_successful_requests: int = 0
    cryptopanic_failed_requests: int = 0
    cryptopanic_partial_success: bool = False
    cryptopanic_backoff_reconciled_after_success: bool = False
    cryptopanic_health_reason: str | None = None
    cryptopanic_source_packs: tuple[str, ...] = ()
    cryptopanic_not_used_reason: str | None = None
    cryptopanic_coverage_status: str = "not_configured"
    cryptopanic_recommendation: str | None = None
    coinalyze_preflight_status: str = "not_generated"
    coinalyze_preflight_json_path: str | None = None
    coinalyze_preflight_report_path: str | None = None
    coinalyze_rehearsal_status: str = "not_generated"
    coinalyze_rehearsal_report_path: str | None = None
    coinalyze_request_ledger_path: str | None = None
    coinalyze_provider_health_status: str = "not_observed"
    coinalyze_requests_used: int = 0
    coinalyze_snapshots_written: int = 0
    coinalyze_supported_metric_status: Mapping[str, str] | None = None
    bybit_announcements_preflight_status: str = "not_generated"
    bybit_announcements_preflight_json_path: str | None = None
    bybit_announcements_preflight_report_path: str | None = None
    bybit_announcements_rehearsal_status: str = "not_generated"
    bybit_announcements_rehearsal_report_path: str | None = None
    bybit_announcements_request_ledger_path: str | None = None
    bybit_announcements_provider_health_status: str = "not_observed"
    bybit_announcements_requests_used: int = 0
    bybit_announcements_official_events_written: int = 0
    bybit_announcements_official_listing_candidates_written: int = 0
    unlock_calendar_preflight_status: str = "not_generated"
    unlock_calendar_preflight_json_path: str | None = None
    unlock_calendar_preflight_report_path: str | None = None
    unlock_calendar_preflight_provider_rows: tuple[Mapping[str, Any], ...] = ()
    dex_onchain_readiness_status: str = "not_generated"
    dex_onchain_readiness_json_path: str | None = None
    dex_onchain_readiness_report_path: str | None = None
    dex_onchain_readiness_provider_rows: tuple[Mapping[str, Any], ...] = ()
    dex_pool_state_rows: int = 0
    dex_pool_anomaly_rows: int = 0
    protocol_fundamental_rows: int = 0
    official_exchange_activation_status: str = "not_generated"
    official_exchange_activation_json_path: str | None = None
    official_exchange_activation_report_path: str | None = None
    official_exchange_activation_provider_rows: tuple[Mapping[str, Any], ...] = ()
    category_priorities: tuple[Mapping[str, Any], ...] = SOURCE_COVERAGE_CATEGORY_PRIORITIES

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "provider_health_rows": self.provider_health_rows,
            "acquisition_rows": self.acquisition_rows,
            "core_rows": self.core_rows,
            "cryptopanic_configured": self.cryptopanic_configured,
            "cryptopanic_health_status": self.cryptopanic_health_status,
            "cryptopanic_observed": self.cryptopanic_observed,
            "cryptopanic_requests_used": self.cryptopanic_requests_used,
            "cryptopanic_rolling_7d_requests": self.cryptopanic_rolling_7d_requests,
            "cryptopanic_remaining_weekly": self.cryptopanic_remaining_weekly,
            "cryptopanic_accepted_evidence": self.cryptopanic_accepted_evidence,
            "cryptopanic_rejected_evidence": self.cryptopanic_rejected_evidence,
            "cryptopanic_successful_requests": self.cryptopanic_successful_requests,
            "cryptopanic_failed_requests": self.cryptopanic_failed_requests,
            "cryptopanic_partial_success": self.cryptopanic_partial_success,
            "cryptopanic_backoff_reconciled_after_success": self.cryptopanic_backoff_reconciled_after_success,
            "cryptopanic_health_reason": self.cryptopanic_health_reason,
            "cryptopanic_source_packs": list(self.cryptopanic_source_packs),
            "cryptopanic_not_used_reason": self.cryptopanic_not_used_reason,
            "cryptopanic_coverage_status": self.cryptopanic_coverage_status,
            "cryptopanic_recommendation": self.cryptopanic_recommendation,
            "coinalyze_preflight_status": self.coinalyze_preflight_status,
            "coinalyze_preflight_json_path": self.coinalyze_preflight_json_path,
            "coinalyze_preflight_report_path": self.coinalyze_preflight_report_path,
            "coinalyze_rehearsal_status": self.coinalyze_rehearsal_status,
            "coinalyze_rehearsal_report_path": self.coinalyze_rehearsal_report_path,
            "coinalyze_request_ledger_path": self.coinalyze_request_ledger_path,
            "coinalyze_provider_health_status": self.coinalyze_provider_health_status,
            "coinalyze_requests_used": self.coinalyze_requests_used,
            "coinalyze_snapshots_written": self.coinalyze_snapshots_written,
            "coinalyze_supported_metric_status": dict(self.coinalyze_supported_metric_status or {}),
            "bybit_announcements_preflight_status": self.bybit_announcements_preflight_status,
            "bybit_announcements_preflight_json_path": self.bybit_announcements_preflight_json_path,
            "bybit_announcements_preflight_report_path": self.bybit_announcements_preflight_report_path,
            "bybit_announcements_rehearsal_status": self.bybit_announcements_rehearsal_status,
            "bybit_announcements_rehearsal_report_path": self.bybit_announcements_rehearsal_report_path,
            "bybit_announcements_request_ledger_path": self.bybit_announcements_request_ledger_path,
            "bybit_announcements_provider_health_status": self.bybit_announcements_provider_health_status,
            "bybit_announcements_requests_used": self.bybit_announcements_requests_used,
            "bybit_announcements_official_events_written": self.bybit_announcements_official_events_written,
            "bybit_announcements_official_listing_candidates_written": self.bybit_announcements_official_listing_candidates_written,
            "unlock_calendar_preflight_status": self.unlock_calendar_preflight_status,
            "unlock_calendar_preflight_json_path": self.unlock_calendar_preflight_json_path,
            "unlock_calendar_preflight_report_path": self.unlock_calendar_preflight_report_path,
            "unlock_calendar_preflight_provider_rows": [
                dict(row) for row in self.unlock_calendar_preflight_provider_rows
            ],
            "dex_onchain_readiness_status": self.dex_onchain_readiness_status,
            "dex_onchain_readiness_json_path": self.dex_onchain_readiness_json_path,
            "dex_onchain_readiness_report_path": self.dex_onchain_readiness_report_path,
            "dex_onchain_readiness_provider_rows": [
                dict(row) for row in self.dex_onchain_readiness_provider_rows
            ],
            "dex_pool_state_rows": self.dex_pool_state_rows,
            "dex_pool_anomaly_rows": self.dex_pool_anomaly_rows,
            "protocol_fundamental_rows": self.protocol_fundamental_rows,
            "official_exchange_activation_status": self.official_exchange_activation_status,
            "official_exchange_activation_json_path": self.official_exchange_activation_json_path,
            "official_exchange_activation_report_path": self.official_exchange_activation_report_path,
            "official_exchange_activation_provider_rows": [
                dict(row) for row in self.official_exchange_activation_provider_rows
            ],
            "category_priorities": [
                {
                    "category_priority_rank": idx + 1,
                    "category": str(item.get("category") or ""),
                    "providers": list(item.get("providers") or ()),
                    "enabled_lanes": list(item.get("enabled_lanes") or ()),
                    "reason": str(item.get("reason") or ""),
                }
                for idx, item in enumerate(self.category_priorities)
            ],
            "live_provider_activation_readiness_artifacts": {
                "json": LIVE_PROVIDER_READINESS_JSON,
                "markdown": LIVE_PROVIDER_READINESS_MD,
                "note": "write with make event-alpha-live-provider-readiness before enabling live providers",
            },
            "packs": [pack.to_dict() for pack in self.packs],
        }
