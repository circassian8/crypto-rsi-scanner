"""Source-pack coverage dashboard for Event Alpha research artifacts.

This module is read-only. It summarizes configured provider coverage,
provider-health state, and evidence-acquisition outcomes by source pack so the
operator can see why strict Event Alpha gates stayed quiet without relaxing
those gates.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import event_provider_status
from ...event_providers import cryptopanic as cryptopanic_provider
from ..artifacts import paths as event_artifact_paths
from ..providers import bybit_announcements_preflight as event_bybit_announcements_preflight
from ..providers import coinalyze_preflight as event_coinalyze_preflight
from ..providers import dex_onchain_readiness as event_dex_onchain_readiness
from ..providers import official_exchange_activation as event_official_exchange_activation
from ..providers import provider_health as event_provider_health
from ..providers import source_packs as event_source_packs
from ..providers import unlock_calendar_preflight as event_unlock_calendar_preflight


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


def build_source_coverage_report(
    *,
    provider_status_report: event_provider_status.EventDiscoveryProviderStatus,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    profile: str = "default",
    artifact_namespace: str = "default",
    cryptopanic_request_ledger_path: str | Path | None = None,
    cryptopanic_weekly_limit: int = 600,
    cryptopanic_daily_soft_limit: int = 80,
    artifact_namespace_dir: str | Path | None = None,
    now: datetime | None = None,
) -> EventAlphaSourceCoverageReport:
    """Build source-pack coverage from readiness, health, and artifact rows."""
    observed = now or datetime.now(timezone.utc)
    raw_health_by_provider = _health_by_provider(provider_health_rows or {}, now=observed)
    health_by_provider = dict(raw_health_by_provider)
    configured = _configured_providers(provider_status_report, health_by_provider)
    acquisition = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    cryptopanic_stats = _cryptopanic_stats(
        configured=configured,
        health_by_provider=raw_health_by_provider,
        acquisition_rows=acquisition,
        request_ledger_path=cryptopanic_request_ledger_path,
        weekly_limit=cryptopanic_weekly_limit,
        daily_soft_limit=cryptopanic_daily_soft_limit,
        now=observed,
        raw_backoff_present=_raw_provider_backoff_present(provider_health_rows or {}, "cryptopanic"),
    )
    coinalyze_stats = _coinalyze_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
        health_by_provider=raw_health_by_provider,
    )
    bybit_stats = _bybit_announcements_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
        health_by_provider=raw_health_by_provider,
    )
    unlock_calendar_stats = _unlock_calendar_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
    )
    dex_onchain_stats = _dex_onchain_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
    )
    activation_stats = event_official_exchange_activation.activation_artifact_stats(
        artifact_namespace_dir if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    )
    cryptopanic_effectively_healthy = cryptopanic_stats["coverage_status"] in {
        "observed_healthy",
        "observed_partial_success",
    }
    bybit_effectively_healthy = bybit_stats["provider_health_status"] in {
        "observed_healthy",
        "observed_no_results",
        "observed_partial_success",
    }
    provider_status_overrides: dict[str, str] = {}
    if cryptopanic_stats["successful_requests"] or cryptopanic_effectively_healthy:
        provider_status_overrides["cryptopanic"] = (
            "degraded" if cryptopanic_stats["failed_requests"] else "healthy"
        )
        health_by_provider["cryptopanic"] = provider_status_overrides["cryptopanic"]
    if bybit_effectively_healthy:
        provider_status_overrides["bybit_announcements_public"] = "healthy"
        health_by_provider["bybit_announcements_public"] = "healthy"
        configured.add("bybit_announcements_public")
    for activation_row in activation_stats["rows"]:
        provider = str(activation_row.get("provider") or "")
        if not provider:
            continue
        if bool(activation_row.get("configured")):
            configured.add(provider)
        if event_official_exchange_activation.row_is_healthy(activation_row):
            provider_status_overrides[provider] = "healthy"
            health_by_provider[provider] = "healthy"
            configured.add(provider)
    for unlock_row in unlock_calendar_stats["provider_rows"]:
        provider = str(unlock_row.get("provider") or "")
        if not provider:
            continue
        if bool(unlock_row.get("configured")) or str(unlock_row.get("fixture_parser_status") or "") == "pass":
            configured.add(provider)
    for dex_row in dex_onchain_stats["provider_rows"]:
        provider = str(dex_row.get("provider") or "")
        if not provider:
            continue
        if bool(dex_row.get("configured")) or str(dex_row.get("fixture_parser_status") or "") == "pass":
            configured.add(provider)

    packs: list[EventAlphaSourceCoveragePack] = []
    for pack_name in SOURCE_COVERAGE_PACK_ORDER:
        pack = event_source_packs.get_source_pack(pack_name)
        preferred = tuple(dict.fromkeys(pack.preferred_providers))
        configured_for_pack = tuple(provider for provider in preferred if provider in configured or provider in health_by_provider)
        missing = tuple(provider for provider in preferred if provider not in configured_for_pack)
        healthy = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) == "healthy"
        )
        unknown = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) in {"unknown", "not_observed"}
        )
        degraded = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) in {"degraded", "backoff", "unavailable"}
        )
        pack_rows = [row for row in acquisition if str(row.get("source_pack") or "") == pack_name]
        accepted = sum(_accepted_count(row) for row in pack_rows)
        rejected_only = sum(1 for row in pack_rows if _status(row) == "rejected_results_only")
        skipped_budget = sum(1 for row in pack_rows if _status(row) == "skipped_budget")
        unavailable = sum(1 for row in pack_rows if _status(row) in {"provider_unavailable", "provider_backoff", "failed_soft", "skipped_config"})
        article_quality_counts = _article_quality_counts(pack_rows)
        blocked = _coverage_blocked_count(pack_name, pack_rows=pack_rows, core_rows=core_rows)
        absence_meaningful = _evidence_absence_meaningful(pack_name, healthy, degraded)
        coverage_status = _pack_coverage_status(
            configured_for_pack=configured_for_pack,
            missing=missing,
            healthy=healthy,
            unknown=unknown,
            degraded=degraded,
            provider_unavailable_count=unavailable,
        )
        coverage_gap_reason = _coverage_gap_reason(
            coverage_status=coverage_status,
            missing=missing,
            unknown=unknown,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
        )
        role_statuses = _provider_role_statuses_for_pack(
            provider_health_rows or {},
            preferred=preferred,
            unknown=unknown,
            now=observed,
            effective_status_overrides=provider_status_overrides,
        )
        recommended_actions = _pack_recommended_actions(
            pack_name,
            missing=missing,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
            satisfied_providers={"cryptopanic"} if cryptopanic_effectively_healthy else (),
        )
        packs.append(
            EventAlphaSourceCoveragePack(
                source_pack=pack_name,
                configured_providers=_sorted_tuple(configured_for_pack),
                missing_providers=_sorted_tuple(missing),
                healthy_providers=_sorted_tuple(healthy),
                unknown_or_unobserved_providers=_sorted_tuple(unknown),
                degraded_or_backoff_providers=_sorted_tuple(degraded),
                provider_coverage_status=coverage_status,
                provider_role_statuses=role_statuses,
                evidence_absence_meaningful=absence_meaningful,
                coverage_gap_reason=coverage_gap_reason,
                providers_missing_for_confirmation=_sorted_tuple(missing),
                providers_degraded_for_confirmation=_sorted_tuple(degraded),
                candidates_blocked_by_coverage_gap=blocked,
                accepted_evidence_count=accepted,
                rejected_only_count=rejected_only,
                skipped_budget_count=skipped_budget,
                provider_unavailable_count=unavailable,
                article_quality_counts=article_quality_counts,
                recommended_actions=recommended_actions,
            )
        )
    return EventAlphaSourceCoverageReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        packs=tuple(packs),
        provider_health_rows=len(provider_health_rows or {}),
        acquisition_rows=len(acquisition),
        core_rows=len(core_rows),
        cryptopanic_configured=cryptopanic_stats["configured"],
        cryptopanic_health_status=cryptopanic_stats["health_status"],
        cryptopanic_observed=cryptopanic_stats["observed"],
        cryptopanic_requests_used=cryptopanic_stats["requests_used"],
        cryptopanic_rolling_7d_requests=cryptopanic_stats["rolling_7d_requests"],
        cryptopanic_remaining_weekly=cryptopanic_stats["remaining_weekly"],
        cryptopanic_accepted_evidence=cryptopanic_stats["accepted"],
        cryptopanic_rejected_evidence=cryptopanic_stats["rejected"],
        cryptopanic_successful_requests=cryptopanic_stats["successful_requests"],
        cryptopanic_failed_requests=cryptopanic_stats["failed_requests"],
        cryptopanic_partial_success=cryptopanic_stats["partial_success"],
        cryptopanic_backoff_reconciled_after_success=cryptopanic_stats["backoff_reconciled_after_success"],
        cryptopanic_health_reason=cryptopanic_stats["health_reason"],
        cryptopanic_source_packs=tuple(cryptopanic_stats["source_packs"]),
        cryptopanic_not_used_reason=cryptopanic_stats["not_used_reason"],
        cryptopanic_coverage_status=cryptopanic_stats["coverage_status"],
        cryptopanic_recommendation=cryptopanic_stats["recommendation"],
        coinalyze_preflight_status=coinalyze_stats["preflight_status"],
        coinalyze_preflight_json_path=coinalyze_stats["preflight_json_path"],
        coinalyze_preflight_report_path=coinalyze_stats["preflight_report_path"],
        coinalyze_rehearsal_status=coinalyze_stats["rehearsal_status"],
        coinalyze_rehearsal_report_path=coinalyze_stats["rehearsal_report_path"],
        coinalyze_request_ledger_path=coinalyze_stats["request_ledger_path"],
        coinalyze_provider_health_status=coinalyze_stats["provider_health_status"],
        coinalyze_requests_used=int(coinalyze_stats["requests_used"]),
        coinalyze_snapshots_written=int(coinalyze_stats["snapshots_written"]),
        coinalyze_supported_metric_status=coinalyze_stats["supported_metric_status"],
        bybit_announcements_preflight_status=bybit_stats["preflight_status"],
        bybit_announcements_preflight_json_path=bybit_stats["preflight_json_path"],
        bybit_announcements_preflight_report_path=bybit_stats["preflight_report_path"],
        bybit_announcements_rehearsal_status=bybit_stats["rehearsal_status"],
        bybit_announcements_rehearsal_report_path=bybit_stats["rehearsal_report_path"],
        bybit_announcements_request_ledger_path=bybit_stats["request_ledger_path"],
        bybit_announcements_provider_health_status=bybit_stats["provider_health_status"],
        bybit_announcements_requests_used=int(bybit_stats["requests_used"]),
        bybit_announcements_official_events_written=int(bybit_stats["official_events_written"]),
        bybit_announcements_official_listing_candidates_written=int(bybit_stats["official_listing_candidates_written"]),
        unlock_calendar_preflight_status=str(unlock_calendar_stats["preflight_status"]),
        unlock_calendar_preflight_json_path=unlock_calendar_stats["preflight_json_path"],
        unlock_calendar_preflight_report_path=unlock_calendar_stats["preflight_report_path"],
        unlock_calendar_preflight_provider_rows=tuple(unlock_calendar_stats["provider_rows"]),
        dex_onchain_readiness_status=str(dex_onchain_stats["readiness_status"]),
        dex_onchain_readiness_json_path=dex_onchain_stats["readiness_json_path"],
        dex_onchain_readiness_report_path=dex_onchain_stats["readiness_report_path"],
        dex_onchain_readiness_provider_rows=tuple(dex_onchain_stats["provider_rows"]),
        dex_pool_state_rows=int(dex_onchain_stats["dex_pool_state_rows"]),
        dex_pool_anomaly_rows=int(dex_onchain_stats["dex_pool_anomaly_rows"]),
        protocol_fundamental_rows=int(dex_onchain_stats["protocol_fundamental_rows"]),
        official_exchange_activation_status=str(activation_stats["status"]),
        official_exchange_activation_json_path=activation_stats["json_path"],
        official_exchange_activation_report_path=activation_stats["report_path"],
        official_exchange_activation_provider_rows=tuple(activation_stats["rows"]),
    )


def format_source_coverage_report(report: EventAlphaSourceCoverageReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SOURCE COVERAGE (research-only)",
        "=" * 76,
        f"profile: {report.profile}",
        f"artifact_namespace: {report.artifact_namespace}",
        f"provider_health_rows: {report.provider_health_rows}",
        f"evidence_acquisition_rows: {report.acquisition_rows}",
        f"core_opportunity_rows: {report.core_rows}",
        "note: configured providers with no health row are unknown/not observed; do not infer they are healthy.",
        "",
        "CryptoPanic:",
        f"- configured: {str(report.cryptopanic_configured).lower()}",
        f"- health status: {report.cryptopanic_health_status}",
        f"- observed this run: {str(report.cryptopanic_observed).lower()}",
        f"- requests used today: {report.cryptopanic_requests_used}",
        f"- rolling 7-day requests: {report.cryptopanic_rolling_7d_requests}",
        f"- remaining weekly quota: {report.cryptopanic_remaining_weekly if report.cryptopanic_remaining_weekly is not None else 'unknown'}",
        f"- accepted evidence: {report.cryptopanic_accepted_evidence}",
        f"- rejected evidence: {report.cryptopanic_rejected_evidence}",
        f"- successful requests: {report.cryptopanic_successful_requests}",
        f"- failed requests: {report.cryptopanic_failed_requests}",
        f"- partial success: {str(report.cryptopanic_partial_success).lower()}",
        f"- stale backoff reconciled after success: {str(report.cryptopanic_backoff_reconciled_after_success).lower()}",
        f"- health reason: {report.cryptopanic_health_reason or 'none'}",
        f"- source packs contributed: {_join(report.cryptopanic_source_packs)}",
        f"- not-used reason: {report.cryptopanic_not_used_reason or 'none'}",
        f"- coverage status: {report.cryptopanic_coverage_status}",
        f"- recommendation: {report.cryptopanic_recommendation or 'none'}",
        "",
        "Source-pack coverage:",
    ]
    for pack in report.packs:
        lines.extend(
            [
                f"- {pack.source_pack}",
                f"  configured providers: {_join(pack.configured_providers)}",
                f"  missing providers: {_join(pack.missing_providers)}",
                f"  healthy providers: {_join(pack.healthy_providers)}",
                f"  unknown/not observed providers: {_join(pack.unknown_or_unobserved_providers)}",
                f"  degraded/backoff providers: {_join(pack.degraded_or_backoff_providers)}",
                f"  provider coverage status: {pack.provider_coverage_status}",
                f"  provider role health: {_join(pack.provider_role_statuses)}",
                f"  evidence absence meaningful: {str(pack.evidence_absence_meaningful).lower()}",
                f"  coverage gap reason: {pack.coverage_gap_reason or 'none'}",
                f"  providers missing for confirmation: {_join(pack.providers_missing_for_confirmation)}",
                f"  providers degraded for confirmation: {_join(pack.providers_degraded_for_confirmation)}",
                (
                    "  acquisition outcomes: "
                    f"accepted={pack.accepted_evidence_count} "
                    f"rejected_only={pack.rejected_only_count} "
                    f"skipped_budget={pack.skipped_budget_count} "
                    f"provider_unavailable={pack.provider_unavailable_count}"
                ),
                f"  article quality: {_join(pack.article_quality_counts)}",
                f"  candidates blocked by coverage gap: {pack.candidates_blocked_by_coverage_gap}",
                f"  recommended actions: {_join(pack.recommended_actions)}",
            ]
        )
    lines.extend(["", "Most useful next data source categories:"])
    for idx, category in enumerate(report.category_priorities, start=1):
        lines.extend([
            f"{idx}. {category.get('category')}",
            f"   providers: {_join(category.get('providers') or ())}",
            f"   enables: {_join(category.get('enabled_lanes') or ())}",
            f"   reason: {category.get('reason') or 'none'}",
        ])
    lines.extend(["", "Live-provider activation readiness:"])
    lines.append(f"- readiness report: {LIVE_PROVIDER_READINESS_MD}")
    lines.append(f"- readiness JSON: {LIVE_PROVIDER_READINESS_JSON}")
    if report.coinalyze_preflight_report_path and report.coinalyze_preflight_json_path:
        lines.append(f"- Coinalyze preflight: {report.coinalyze_preflight_status}")
        lines.append(f"- Coinalyze preflight report: {report.coinalyze_preflight_report_path}")
        lines.append(f"- Coinalyze preflight JSON: {report.coinalyze_preflight_json_path}")
        lines.append(f"- Coinalyze supported metric status: {_coinalyze_metric_status_line(report.coinalyze_supported_metric_status)}")
    else:
        lines.append("- Coinalyze preflight: not generated")
        lines.append(
            "- command: make event-alpha-coinalyze-preflight ARTIFACT_NAMESPACE="
            f"{report.artifact_namespace} PROFILE={report.profile} PYTHON=python3"
        )
    if report.coinalyze_rehearsal_report_path:
        lines.append(f"- Coinalyze rehearsal: {report.coinalyze_rehearsal_status}")
        lines.append(f"- Coinalyze rehearsal report: {report.coinalyze_rehearsal_report_path}")
        if report.coinalyze_request_ledger_path:
            lines.append(f"- Coinalyze request ledger: {report.coinalyze_request_ledger_path}")
        lines.append(f"- Coinalyze provider health: {report.coinalyze_provider_health_status}")
        lines.append(f"- Coinalyze supported metric status: {_coinalyze_metric_status_line(report.coinalyze_supported_metric_status)}")
        lines.append(
            f"- Coinalyze rehearsal counters: requests_used={report.coinalyze_requests_used} "
            f"snapshots_written={report.coinalyze_snapshots_written}"
        )
    else:
        lines.append("- Coinalyze rehearsal: not generated")
    if report.bybit_announcements_preflight_report_path and report.bybit_announcements_preflight_json_path:
        lines.append(f"- Bybit announcements preflight: {report.bybit_announcements_preflight_status}")
        lines.append(f"- Bybit announcements preflight report: {report.bybit_announcements_preflight_report_path}")
        lines.append(f"- Bybit announcements preflight JSON: {report.bybit_announcements_preflight_json_path}")
    else:
        lines.append("- Bybit announcements preflight: not generated")
        lines.append(
            "- command: make event-alpha-bybit-announcements-preflight ARTIFACT_NAMESPACE="
            f"{report.artifact_namespace} PROFILE={report.profile} PYTHON=python3"
        )
    if report.bybit_announcements_rehearsal_report_path:
        lines.append(f"- Bybit announcements rehearsal: {report.bybit_announcements_rehearsal_status}")
        lines.append(f"- Bybit announcements rehearsal report: {report.bybit_announcements_rehearsal_report_path}")
        if report.bybit_announcements_request_ledger_path:
            lines.append(f"- Bybit announcements request ledger: {report.bybit_announcements_request_ledger_path}")
        lines.append(f"- Bybit announcements provider health: {report.bybit_announcements_provider_health_status}")
        lines.append(
            f"- Bybit announcements rehearsal counters: requests_used={report.bybit_announcements_requests_used} "
            f"official_events_written={report.bybit_announcements_official_events_written} "
            f"official_listing_candidates_written={report.bybit_announcements_official_listing_candidates_written}"
        )
    else:
        lines.append("- Bybit announcements rehearsal: not generated")
    if report.unlock_calendar_preflight_report_path and report.unlock_calendar_preflight_json_path:
        lines.append(f"- Unlock/calendar preflight: {report.unlock_calendar_preflight_status}")
        lines.append(f"- Unlock/calendar preflight report: {report.unlock_calendar_preflight_report_path}")
        lines.append(f"- Unlock/calendar preflight JSON: {report.unlock_calendar_preflight_json_path}")
        if report.unlock_calendar_preflight_provider_rows:
            lines.append("- Unlock/calendar provider rows:")
            for row in report.unlock_calendar_preflight_provider_rows:
                lines.append(
                    "  - "
                    f"{row.get('provider') or 'unknown'} "
                    f"configured={str(bool(row.get('configured'))).lower()} "
                    f"fixture_parser_status={row.get('fixture_parser_status') or 'unknown'} "
                    f"live_call_allowed={str(bool(row.get('live_call_allowed'))).lower()} "
                    f"source_packs={_join(row.get('source_packs_enabled') or ())}"
                )
    else:
        lines.append("- Unlock/calendar preflight: not generated")
        lines.append(
            "- command: make event-alpha-tokenomist-preflight ARTIFACT_NAMESPACE="
            f"{report.artifact_namespace} PROFILE={report.profile} PYTHON=python3"
        )
    if report.dex_onchain_readiness_report_path and report.dex_onchain_readiness_json_path:
        lines.append(f"- DEX/on-chain readiness: {report.dex_onchain_readiness_status}")
        lines.append(f"- DEX/on-chain readiness report: {report.dex_onchain_readiness_report_path}")
        lines.append(f"- DEX/on-chain readiness JSON: {report.dex_onchain_readiness_json_path}")
        lines.append(
            f"- DEX/on-chain counters: pool_state={report.dex_pool_state_rows} "
            f"pool_anomalies={report.dex_pool_anomaly_rows} "
            f"protocol_fundamentals={report.protocol_fundamental_rows}"
        )
        if report.dex_onchain_readiness_provider_rows:
            lines.append("- DEX/on-chain provider rows:")
            for row in report.dex_onchain_readiness_provider_rows:
                lines.append(
                    "  - "
                    f"{row.get('provider') or 'unknown'} "
                    f"configured={str(bool(row.get('configured'))).lower()} "
                    f"fixture_parser_status={row.get('fixture_parser_status') or 'unknown'} "
                    f"live_call_allowed={str(bool(row.get('live_call_allowed'))).lower()} "
                    f"source_packs={_join(row.get('source_packs_enabled') or ())}"
                )
    else:
        lines.append("- DEX/on-chain readiness: not generated")
        lines.append(
            "- command: make event-alpha-dex-onchain-readiness-smoke ARTIFACT_NAMESPACE="
            f"{report.artifact_namespace} PROFILE={report.profile} PYTHON=python3"
        )
    lines.append(f"- Official exchange activation: {report.official_exchange_activation_status}")
    if report.official_exchange_activation_report_path:
        lines.append(f"- Official exchange activation report: {report.official_exchange_activation_report_path}")
    if report.official_exchange_activation_json_path:
        lines.append(f"- Official exchange activation JSON: {report.official_exchange_activation_json_path}")
    if report.official_exchange_activation_provider_rows:
        lines.append("- Official exchange activation provider rows:")
        for row in report.official_exchange_activation_provider_rows:
            lines.append(
                "  - "
                f"{row.get('provider') or 'unknown'} "
                f"mode={row.get('mode') or 'unknown'} "
                f"configured={str(bool(row.get('configured'))).lower()} "
                f"live_call_allowed={str(bool(row.get('live_call_allowed'))).lower()} "
                f"health={row.get('provider_health_status') or 'not_observed'} "
                f"announcements_seen={int(row.get('announcements_seen') or 0)} "
                f"official_events_written={int(row.get('official_events_written') or 0)} "
                f"listing_candidates_written={int(row.get('listing_candidates_written') or 0)} "
                f"risk_candidates_written={int(row.get('risk_candidates_written') or 0)}"
            )
    else:
        lines.append("- Official exchange activation provider rows: none")
    lines.extend(
        [
            "- command: make event-alpha-live-provider-readiness PROFILE="
            f"{report.profile} ARTIFACT_NAMESPACE={report.artifact_namespace}",
            "- next activation plan: use the ranked source categories above; rehearse no-send before enabling live calls.",
        ]
    )
    recs = _recommendation_lines(report)
    lines.extend(["", "Most useful next data source:"])
    lines.extend(recs)
    lines.append("")
    lines.append("No alerts, sends, trades, paper rows, normal RSI rows, or triggers were changed.")
    return "\n".join(lines)


def _coinalyze_artifact_stats(
    *,
    artifact_namespace_dir: str | Path | None,
    artifact_namespace: str,
    health_by_provider: Mapping[str, str],
) -> dict[str, Any]:
    base = Path(artifact_namespace_dir).expanduser() if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    preflight_json = base / event_coinalyze_preflight.PREFLIGHT_JSON
    preflight_md = base / event_coinalyze_preflight.PREFLIGHT_MD
    rehearsal_json = base / event_coinalyze_preflight.REHEARSAL_JSON
    rehearsal_md = base / event_coinalyze_preflight.REHEARSAL_MD
    ledger = base / event_coinalyze_preflight.REQUEST_LEDGER
    preflight_payload = _read_json(preflight_json)
    rehearsal_payload = _read_json(rehearsal_json)
    return {
        "preflight_status": str(preflight_payload.get("preflight_status") or "generated" if preflight_json.exists() else "not_generated"),
        "preflight_json_path": event_artifact_paths.artifact_display_path(preflight_json) if preflight_json.exists() else None,
        "preflight_report_path": event_artifact_paths.artifact_display_path(preflight_md) if preflight_md.exists() else None,
        "rehearsal_status": str(rehearsal_payload.get("status") or "generated" if rehearsal_json.exists() or rehearsal_md.exists() else "not_generated"),
        "rehearsal_report_path": event_artifact_paths.artifact_display_path(rehearsal_md) if rehearsal_md.exists() else None,
        "request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "provider_health_status": str(rehearsal_payload.get("provider_health_status") or health_by_provider.get("coinalyze") or "not_observed"),
        "requests_used": int(rehearsal_payload.get("requests_used") or 0),
        "snapshots_written": int(rehearsal_payload.get("snapshots_written") or 0),
        "supported_metric_status": _coinalyze_supported_metric_status(preflight_payload, rehearsal_payload),
    }


def _coinalyze_supported_metric_status(
    preflight_payload: Mapping[str, Any],
    rehearsal_payload: Mapping[str, Any],
) -> dict[str, str]:
    for payload in (rehearsal_payload, preflight_payload):
        status = payload.get("supported_metric_status")
        if isinstance(status, Mapping):
            return {str(key): str(value) for key, value in status.items() if str(key)}
    return {}


def _coinalyze_metric_status_line(status: Mapping[str, str] | None) -> str:
    if not status:
        return "none"
    metrics = (
        "open_interest",
        "funding_rate",
        "predicted_funding",
        "liquidations",
        "long_short_ratio",
        "basis",
        "perp_volume",
    )
    parts = [f"{metric}={status.get(metric)}" for metric in metrics if status.get(metric)]
    return ", ".join(parts) if parts else "none"


def _bybit_announcements_artifact_stats(
    *,
    artifact_namespace_dir: str | Path | None,
    artifact_namespace: str,
    health_by_provider: Mapping[str, str],
) -> dict[str, Any]:
    base = Path(artifact_namespace_dir).expanduser() if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    preflight_json = base / event_bybit_announcements_preflight.PREFLIGHT_JSON
    preflight_md = base / event_bybit_announcements_preflight.PREFLIGHT_MD
    rehearsal_json = base / event_bybit_announcements_preflight.REHEARSAL_JSON
    rehearsal_md = base / event_bybit_announcements_preflight.REHEARSAL_MD
    ledger = base / event_bybit_announcements_preflight.REQUEST_LEDGER
    preflight_payload = _read_json(preflight_json)
    rehearsal_payload = _read_json(rehearsal_json)
    return {
        "preflight_status": str(preflight_payload.get("preflight_status") or "generated" if preflight_json.exists() else "not_generated"),
        "preflight_json_path": event_artifact_paths.artifact_display_path(preflight_json) if preflight_json.exists() else None,
        "preflight_report_path": event_artifact_paths.artifact_display_path(preflight_md) if preflight_md.exists() else None,
        "rehearsal_status": str(rehearsal_payload.get("status") or "generated" if rehearsal_json.exists() or rehearsal_md.exists() else "not_generated"),
        "rehearsal_report_path": event_artifact_paths.artifact_display_path(rehearsal_md) if rehearsal_md.exists() else None,
        "request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "provider_health_status": str(
            rehearsal_payload.get("provider_health_status")
            or health_by_provider.get("bybit_announcements_public")
            or health_by_provider.get("bybit_announcements")
            or "not_observed"
        ),
        "requests_used": int(rehearsal_payload.get("requests_used") or 0),
        "official_events_written": int(rehearsal_payload.get("official_events_written") or 0),
        "official_listing_candidates_written": int(rehearsal_payload.get("official_listing_candidates_written") or 0),
    }


def _unlock_calendar_artifact_stats(
    *,
    artifact_namespace_dir: str | Path | None,
    artifact_namespace: str,
) -> dict[str, Any]:
    base = Path(artifact_namespace_dir).expanduser() if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    preflight_json = base / event_unlock_calendar_preflight.PREFLIGHT_JSON
    preflight_md = base / event_unlock_calendar_preflight.PREFLIGHT_MD
    preflight_payload = _read_json(preflight_json)
    provider_rows = preflight_payload.get("providers") or preflight_payload.get("provider_rows") or ()
    if not isinstance(provider_rows, Iterable) or isinstance(provider_rows, (str, bytes, Mapping)):
        provider_rows = ()
    return {
        "preflight_status": str(preflight_payload.get("preflight_status") or "generated" if preflight_json.exists() else "not_generated"),
        "preflight_json_path": event_artifact_paths.artifact_display_path(preflight_json) if preflight_json.exists() else None,
        "preflight_report_path": event_artifact_paths.artifact_display_path(preflight_md) if preflight_md.exists() else None,
        "provider_rows": tuple(dict(row) for row in provider_rows if isinstance(row, Mapping)),
    }


def _dex_onchain_artifact_stats(
    *,
    artifact_namespace_dir: str | Path | None,
    artifact_namespace: str,
) -> dict[str, Any]:
    base = Path(artifact_namespace_dir).expanduser() if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    readiness_json = base / event_dex_onchain_readiness.READINESS_JSON
    readiness_md = base / event_dex_onchain_readiness.READINESS_MD
    state_path = base / event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME
    anomaly_path = base / event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME
    protocol_path = base / event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME
    payload = _read_json(readiness_json)
    provider_rows = payload.get("providers") or payload.get("provider_rows") or ()
    if not isinstance(provider_rows, Iterable) or isinstance(provider_rows, (str, bytes, Mapping)):
        provider_rows = ()
    return {
        "readiness_status": str(payload.get("readiness_status") or "generated" if readiness_json.exists() else "not_generated"),
        "readiness_json_path": event_artifact_paths.artifact_display_path(readiness_json) if readiness_json.exists() else None,
        "readiness_report_path": event_artifact_paths.artifact_display_path(readiness_md) if readiness_md.exists() else None,
        "provider_rows": tuple(dict(row) for row in provider_rows if isinstance(row, Mapping)),
        "dex_pool_state_rows": int(payload.get("dex_pool_state_rows") or _count_jsonl_rows(state_path)),
        "dex_pool_anomaly_rows": int(payload.get("dex_pool_anomaly_rows") or _count_jsonl_rows(anomaly_path)),
        "protocol_fundamental_rows": int(payload.get("protocol_fundamental_rows") or _count_jsonl_rows(protocol_path)),
    }


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _namespace_dir(artifact_namespace: str) -> Path:
    base = Path(os.getenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    return base / str(artifact_namespace or "default")


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _configured_providers(
    provider_status_report: event_provider_status.EventDiscoveryProviderStatus,
    health_by_provider: Mapping[str, str],
) -> set[str]:
    out: set[str] = set(health_by_provider)
    for item in (*provider_status_report.sources, *provider_status_report.enrichment):
        alias = _READY_PROVIDER_ALIASES.get(item.name)
        if alias and item.ready:
            out.add(alias)
    return out


def _health_by_provider(rows: Mapping[str, Mapping[str, Any]], *, now: datetime) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, row in rows.items():
        alias = _provider_alias(row, fallback_key=str(key))
        if not alias:
            continue
        status = event_provider_health.provider_health_status(row, now=now)
        if status == "backoff":
            out[alias] = "backoff"
        elif status == "degraded":
            out.setdefault(alias, "degraded")
        else:
            out.setdefault(alias, "healthy")
    return out


def _provider_alias(row: Mapping[str, Any], *, fallback_key: str) -> str:
    candidates = (
        row.get("provider_service"),
        row.get("provider"),
        row.get("provider_key"),
        fallback_key,
    )
    joined = " ".join(str(item or "").casefold() for item in candidates)
    for token, alias in _HEALTH_PROVIDER_ALIASES.items():
        if token in joined:
            return alias
    return ""


def _provider_effective_status(provider: str, health_by_provider: Mapping[str, str]) -> str:
    return str(health_by_provider.get(provider) or "unknown")


def _provider_role_statuses_for_pack(
    rows: Mapping[str, Mapping[str, Any]],
    *,
    preferred: Iterable[str],
    unknown: Iterable[str] = (),
    now: datetime,
    effective_status_overrides: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    preferred_set = set(preferred)
    overrides = dict(effective_status_overrides or {})
    out: list[str] = []
    for key, row in sorted(rows.items()):
        alias = _provider_alias(row, fallback_key=str(key))
        if alias not in preferred_set:
            continue
        role = str(row.get("provider_role") or row.get("provider_kind") or "unclassified").strip() or "unclassified"
        status = overrides.get(alias) or event_provider_health.provider_health_status(row, now=now)
        out.append(f"{alias}:{role}={status}")
    for alias in sorted(set(unknown) & preferred_set):
        out.append(f"{alias}:not_observed=unknown")
    return tuple(dict.fromkeys(out))


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or row.get("evidence_acquisition_status") or "").strip()


def _accepted_count(row: Mapping[str, Any]) -> int:
    for key in ("accepted_evidence_count", "evidence_acquisition_accepted_count"):
        try:
            if row.get(key) not in (None, ""):
                return max(0, int(row.get(key) or 0))
        except (TypeError, ValueError):
            pass
    accepted = row.get("accepted_evidence")
    if isinstance(accepted, list):
        return len(accepted)
    if isinstance(accepted, tuple):
        return len(accepted)
    return 1 if accepted else 0


def _article_quality_counts(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        for evidence in (*_evidence_items(row.get("accepted_evidence")), *_evidence_items(row.get("rejected_evidence_samples") or row.get("rejected_evidence"))):
            enrichment = evidence.get("source_enrichment") if isinstance(evidence.get("source_enrichment"), Mapping) else {}
            status = str(enrichment.get("article_quality_status") or "").strip()
            if status:
                counts[status] = counts.get(status, 0) + 1
    return tuple(f"{key}={value}" for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _evidence_items(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _cryptopanic_stats(
    *,
    configured: set[str],
    health_by_provider: Mapping[str, str],
    acquisition_rows: Iterable[Mapping[str, Any]],
    request_ledger_path: str | Path | None = None,
    weekly_limit: int = 600,
    daily_soft_limit: int = 80,
    now: datetime | None = None,
    raw_backoff_present: bool = False,
) -> dict[str, Any]:
    accepted = 0
    rejected = 0
    observed = "cryptopanic" in health_by_provider
    source_packs: set[str] = set()
    provider_failures: set[str] = set()
    for row in acquisition_rows:
        row_has_cryptopanic = _row_mentions_cryptopanic(row)
        accepted_items = tuple(item for item in _evidence_items(row.get("accepted_evidence")) if _evidence_mentions_cryptopanic(item))
        rejected_items = tuple(item for item in _evidence_items(row.get("rejected_evidence_samples") or row.get("rejected_evidence")) if _evidence_mentions_cryptopanic(item))
        query_items = tuple(item for item in _evidence_items(row.get("queries")) if _evidence_mentions_cryptopanic(item))
        if row_has_cryptopanic or accepted_items or rejected_items or query_items:
            observed = True
            pack = str(row.get("source_pack") or "")
            if pack:
                source_packs.add(pack)
        accepted += len(accepted_items)
        rejected += len(rejected_items)
        for failure in row.get("provider_failures") or ():
            if "cryptopanic" in str(failure).casefold():
                provider_failures.add(str(failure))
    configured_flag = "cryptopanic" in configured
    health_status = _provider_effective_status("cryptopanic", health_by_provider)
    usage = cryptopanic_provider.cryptopanic_usage_summary(
        request_ledger_path,
        now=now or datetime.now(timezone.utc),
        weekly_limit=weekly_limit,
        daily_soft_limit=daily_soft_limit,
    )
    successful_requests = int(getattr(usage, "successful_requests", 0) or 0)
    failed_requests = int(getattr(usage, "failed_requests", 0) or 0)
    backoff_reconciled_after_success = bool(
        (health_status == "backoff" or raw_backoff_present) and (successful_requests or accepted > 0)
    )
    effective_health_status = health_status
    if successful_requests:
        effective_health_status = "partial_success" if failed_requests else "healthy"
    elif accepted > 0 and health_status in {"backoff", "degraded", "unavailable", "unknown"}:
        effective_health_status = "healthy"
    if usage.today_requests > 0:
        observed = True
    coverage_status = _cryptopanic_coverage_status(
        configured=configured_flag,
        observed=observed,
        health_status=effective_health_status,
        accepted=accepted,
        rejected=rejected,
        usage=usage,
    )
    reason = None
    if configured_flag and not observed:
        if health_status == "backoff":
            reason = "provider_backoff"
        elif health_status in {"degraded", "unavailable"}:
            reason = "provider_error"
        elif provider_failures:
            reason = "provider_error"
        elif not acquisition_rows:
            reason = "no_acquisition_rows"
        else:
            reason = "query_planner_skipped"
    elif not configured_flag:
        reason = "not_configured"
    health_reason = _cryptopanic_health_reason(
        coverage_status=coverage_status,
        raw_health_status=health_status,
        successful_requests=successful_requests,
        failed_requests=failed_requests,
        accepted=accepted,
        rejected=rejected,
        backoff_reconciled_after_success=backoff_reconciled_after_success,
    )
    return {
        "configured": configured_flag,
        "health_status": effective_health_status,
        "observed": observed,
        "requests_used": int(usage.today_requests),
        "rolling_7d_requests": int(usage.rolling_7d_requests),
        "remaining_weekly": usage.remaining_weekly,
        "accepted": accepted,
        "rejected": rejected,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "partial_success": bool(successful_requests and failed_requests),
        "backoff_reconciled_after_success": backoff_reconciled_after_success,
        "health_reason": health_reason,
        "source_packs": _sorted_tuple(source_packs),
        "not_used_reason": reason,
        "coverage_status": coverage_status,
        "recommendation": _cryptopanic_recommendation(coverage_status),
    }


def _raw_provider_backoff_present(
    rows: Mapping[str, Mapping[str, Any]],
    provider: str,
) -> bool:
    provider_l = str(provider or "").casefold()
    for key, row in rows.items():
        if not row.get("disabled_until"):
            continue
        values = (
            key,
            row.get("provider"),
            row.get("provider_key"),
            row.get("provider_service"),
        )
        if any(provider_l in str(value or "").casefold() for value in values):
            return True
    return False


def _cryptopanic_coverage_status(
    *,
    configured: bool,
    observed: bool,
    health_status: str,
    accepted: int,
    rejected: int,
    usage: cryptopanic_provider.CryptoPanicUsageSummary,
) -> str:
    if not configured:
        return "not_configured"
    last_error = str(usage.last_error_class or "").strip()
    if usage.remaining_weekly == 0:
        return "quota_exhausted"
    successful_requests = int(getattr(usage, "successful_requests", 0) or 0)
    failed_requests = int(getattr(usage, "failed_requests", 0) or 0)
    if successful_requests:
        if failed_requests:
            return "observed_partial_success"
        if accepted > 0:
            return "observed_healthy"
        return "observed_no_results"
    if last_error == "json_parse_error" or last_error == "empty_response":
        return "observed_parse_error"
    if last_error in {"rate_limited_or_forbidden", "auth_failed"}:
        return "observed_rate_limited"
    if health_status == "backoff":
        return "observed_backoff_without_success"
    if not observed:
        return "configured_not_observed"
    if accepted > 0:
        return "observed_healthy"
    if rejected > 0 or usage.today_requests > 0:
        return "observed_no_results"
    return "configured_not_observed"


def _cryptopanic_recommendation(status: str) -> str:
    return {
        "not_configured": "configure CryptoPanic token with RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
        "configured_not_observed": "run a CryptoPanic-enabled rehearsal or inspect provider selection",
        "observed_healthy": "no action; accepted CryptoPanic evidence is available",
        "observed_partial_success": "use accepted evidence; inspect failed CryptoPanic roles in the request ledger",
        "observed_no_results": "no matching token news found; inspect query/candidate terms, not provider credentials",
        "observed_parse_error": "inspect cryptopanic_request_ledger.jsonl body excerpt, content type, and endpoint shape",
        "observed_rate_limited": "wait for cooldown or reduce CryptoPanic request rate/quota usage",
        "observed_backoff_without_success": "wait for cooldown or reset provider backoff only after configuration changed",
        "quota_exhausted": "wait for quota reset or lower per-run request limits",
    }.get(status, "inspect CryptoPanic request ledger and provider health")


def _cryptopanic_health_reason(
    *,
    coverage_status: str,
    raw_health_status: str,
    successful_requests: int,
    failed_requests: int,
    accepted: int,
    rejected: int,
    backoff_reconciled_after_success: bool,
) -> str:
    if backoff_reconciled_after_success:
        return "stale_backoff_ignored_due_success"
    if successful_requests and failed_requests:
        return "successful_requests_with_failures"
    if successful_requests and accepted:
        return "successful_requests_with_accepted_evidence"
    if successful_requests:
        return "successful_requests_no_matching_evidence"
    if coverage_status == "observed_backoff_without_success" or raw_health_status == "backoff":
        return "provider_backoff_without_success"
    if rejected:
        return "observed_rejected_evidence_only"
    return coverage_status


def _row_mentions_cryptopanic(row: Mapping[str, Any]) -> bool:
    values: list[object] = [
        row.get("providers_used"),
        row.get("evidence_acquisition_providers_used"),
        row.get("provider_failures"),
        row.get("provider_coverage_gaps"),
    ]
    return any("cryptopanic" in str(value).casefold() for value in values)


def _evidence_mentions_cryptopanic(item: Mapping[str, Any]) -> bool:
    values = (
        item.get("provider"),
        item.get("provider_hint"),
        item.get("provider_used"),
        item.get("source_class"),
        item.get("source_url"),
        item.get("reason_codes"),
        item.get("currency_tags"),
        item.get("query"),
    )
    return any(
        "cryptopanic" in str(value).casefold()
        or str(value).casefold() == "cryptopanic_tagged"
        for value in values
    )


def _coverage_blocked_count(
    pack_name: str,
    *,
    pack_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
) -> int:
    blocked = 0
    for row in pack_rows:
        if _status(row) in _COVERAGE_GAP_STATUSES and _accepted_count(row) <= 0:
            blocked += 1
    for row in core_rows:
        if str(row.get("source_pack") or row.get("evidence_acquisition_source_pack") or "") != pack_name:
            continue
        reason_values = {
            str(row.get("live_confirmation_reason") or ""),
            str(row.get("source_pack_confirmation_status") or ""),
            str(row.get("source_coverage_gap") or ""),
            str(row.get("quality_gate_block_reason") or ""),
            str(row.get("why_not_promoted") or ""),
        }
        if reason_values & _COVERAGE_GAP_REASONS:
            blocked += 1
    return blocked


def _evidence_absence_meaningful(
    pack_name: str,
    healthy: Iterable[str],
    degraded: Iterable[str],
) -> bool:
    healthy_set = set(healthy)
    degraded_set = set(degraded)
    if not healthy_set:
        return False
    if healthy_set <= _BROAD_CONTEXT_PROVIDERS and degraded_set:
        return False
    pack = event_source_packs.get_source_pack(pack_name)
    preferred = set(pack.preferred_providers)
    return bool((healthy_set & preferred) & _HIGH_SPECIFICITY_PROVIDERS)


def _pack_coverage_status(
    *,
    configured_for_pack: Iterable[str],
    missing: Iterable[str],
    healthy: Iterable[str],
    unknown: Iterable[str],
    degraded: Iterable[str],
    provider_unavailable_count: int,
) -> str:
    configured_set = set(configured_for_pack)
    missing_set = set(missing)
    healthy_set = set(healthy)
    unknown_set = set(unknown)
    degraded_set = set(degraded)
    if provider_unavailable_count and not healthy_set:
        return "unavailable"
    if not configured_set:
        return "not_configured"
    if unknown_set and not healthy_set and not degraded_set:
        return "unknown"
    if degraded_set and not healthy_set:
        return "degraded"
    if healthy_set and not missing_set and not degraded_set and not provider_unavailable_count:
        return "partial" if unknown_set else "complete"
    if healthy_set:
        return "partial"
    return "unknown" if unknown_set else "unavailable"


def _coverage_gap_reason(
    *,
    coverage_status: str,
    missing: Iterable[str],
    unknown: Iterable[str],
    degraded: Iterable[str],
    blocked: int,
    skipped_budget: int,
    rejected_only: int,
    provider_unavailable: int,
) -> str | None:
    reasons: list[str] = []
    if coverage_status in {"not_configured", "degraded", "unavailable", "partial", "unknown"}:
        reasons.append(f"source_pack_coverage_{coverage_status}")
    missing_values = _sorted_tuple(missing)
    unknown_values = _sorted_tuple(unknown)
    degraded_values = _sorted_tuple(degraded)
    if missing_values:
        reasons.append("missing:" + ",".join(missing_values))
    if unknown_values:
        reasons.append("not_observed:" + ",".join(unknown_values))
    if degraded_values:
        reasons.append("degraded:" + ",".join(degraded_values))
    if skipped_budget:
        reasons.append("skipped_budget_not_confirmation")
    if rejected_only:
        reasons.append("rejected_results_only_not_confirmation")
    if provider_unavailable:
        reasons.append("provider_unavailable_not_confirmation")
    if blocked:
        reasons.append("candidates_blocked_by_coverage_gap")
    return ";".join(reasons) if reasons else None


def _recommendation_lines(report: EventAlphaSourceCoverageReport) -> list[str]:
    provider_missing_counts: dict[str, int] = {}
    provider_gap_counts: dict[str, int] = {}
    for pack in report.packs:
        gap_weight = max(1, pack.candidates_blocked_by_coverage_gap)
        for provider in pack.missing_providers:
            provider_missing_counts[provider] = provider_missing_counts.get(provider, 0) + gap_weight
        for provider in pack.degraded_or_backoff_providers:
            provider_gap_counts[provider] = provider_gap_counts.get(provider, 0) + gap_weight
    if not provider_missing_counts and not provider_gap_counts:
        return ["- coverage is currently sufficient for the tracked source packs"]
    combined = {
        provider: provider_missing_counts.get(provider, 0) + provider_gap_counts.get(provider, 0)
        for provider in set(provider_missing_counts) | set(provider_gap_counts)
    }
    top = sorted(
        combined,
        key=lambda item: (
            -_provider_lane_priority(item),
            -combined[item],
            item,
        ),
    )[:5]
    lines: list[str] = []
    for provider in top:
        reason = []
        if provider_missing_counts.get(provider):
            reason.append(f"missing_in_packs={provider_missing_counts[provider]}")
        if provider_gap_counts.get(provider):
            reason.append(f"degraded_or_backoff_in_packs={provider_gap_counts[provider]}")
        lines.append(f"- {provider}: " + ", ".join(reason))
    return lines


def _provider_lane_priority(provider: str) -> int:
    text = str(provider or "").casefold()
    if any(token in text for token in ("coinalyze", "futures", "derivatives", "funding")):
        return 760
    if any(token in text for token in ("binance", "bybit", "coinbase", "kucoin", "okx")):
        return 700
    if any(token in text for token in ("tokenomist", "coinmarketcal", "coindar", "messari")):
        return 600
    if any(token in text for token in ("geckoterminal", "arkham", "dune", "etherscan")):
        return 500
    if any(token in text for token in ("defillama",)):
        return 450
    if "cryptopanic" in text:
        return 350
    if any(token in text for token in ("rss", "gdelt", "project_blog")):
        return 100
    return 200


def _pack_recommended_actions(
    pack_name: str,
    *,
    missing: Iterable[str],
    degraded: Iterable[str],
    blocked: int,
    skipped_budget: int,
    rejected_only: int,
    provider_unavailable: int,
    satisfied_providers: Iterable[str] = (),
) -> tuple[str, ...]:
    actions: list[str] = []
    missing_set = set(missing)
    degraded_set = set(degraded)
    satisfied = set(satisfied_providers)
    if blocked or missing_set or degraded_set:
        for provider in sorted(missing_set):
            if provider in satisfied:
                continue
            actions.append(_provider_setup_action(provider, status="missing"))
        for provider in sorted(degraded_set):
            if provider in satisfied:
                continue
            actions.append(_provider_setup_action(provider, status="degraded"))
    if skipped_budget:
        actions.append("raise evidence-acquisition query/candidate budget for this source pack")
    if rejected_only:
        actions.append("inspect rejected evidence samples and add stricter query terms before trusting absence")
    if provider_unavailable:
        actions.append("run provider health report/reset before treating missing evidence as meaningful")
    if pack_name == "market_anomaly_pack" and "defillama" in missing_set:
        actions.append("add or enable DefiLlama-style protocol metrics before relying on market-anomaly confirmation")
    return tuple(dict.fromkeys(action for action in actions if action))


def _provider_setup_action(provider: str, *, status: str) -> str:
    prefix = "configure" if status == "missing" else "restore"
    if provider == "cryptopanic" and status != "missing":
        return "inspect CryptoPanic provider health, backoff/quota, and token-specific query quality"
    guidance = {
        "cryptopanic": "CryptoPanic token/news coverage with RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
        "gdelt": "GDELT broad-news coverage and provider backoff health",
        "project_blog_rss": "project/blog RSS feeds; quarantine feed-level 403s instead of the whole RSS provider",
        "binance_announcements_public_or_fixture": "official Binance fixture/public announcement parser coverage for listing/perp events; no API key required",
        "binance_announcements_signed_listener": "official Binance signed WebSocket listener coverage; requires explicit API key/secret and bounded listener runbook",
        "bybit_announcements_public": "official Bybit public announcement coverage for listing/perp events; no API key required",
        "coinmarketcal": "structured event calendar coverage",
        "tokenomist": "Tokenomist unlock/supply coverage",
        "messari_unlocks": "Messari structured unlock coverage",
        "sports_fixtures": "sports fixture coverage for fan-token packs",
        "polymarket": "Polymarket context coverage for external catalysts",
        "coinalyze": "Coinalyze derivatives/OI/funding coverage",
        "coingecko": "CoinGecko market/universe coverage",
        "defillama": "DefiLlama protocol TVL/revenue/context coverage",
        "etherscan": "Etherscan token-flow/supply coverage",
        "arkham": "Arkham labeled-wallet coverage",
        "dune": "Dune curated on-chain query coverage",
        "okx_announcements": "OKX official announcement coverage",
        "coinbase": "Coinbase official listing coverage",
    }
    detail = guidance.get(provider, f"{provider} coverage")
    return f"{prefix} {detail}"


def _sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(str(value) for value in values if str(value))))


def _join(values: Iterable[str]) -> str:
    items = _sorted_tuple(values)
    return ", ".join(items) if items else "none"
