"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (provider_status)."""

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
from .models import *  # noqa: F403

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
