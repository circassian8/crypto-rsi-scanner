"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (builder)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
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


@dataclass(frozen=True)
class _SourceCoverageStats:
    cryptopanic: dict[str, Any]
    coinalyze: dict[str, Any]
    bybit: dict[str, Any]
    unlock_calendar: dict[str, Any]
    dex_onchain: dict[str, Any]
    activation: dict[str, Any]
    cryptopanic_effectively_healthy: bool
    bybit_effectively_healthy: bool


def _cryptopanic_run_context(
    *,
    exact_run_row: Mapping[str, Any] | None,
    provider_readiness_payload: Mapping[str, Any] | None,
    configured_fallback: bool | None,
) -> dict[str, Any]:
    """Resolve credential, selection, and permission as separate exact-run facts."""
    run = dict(exact_run_row or {})
    readiness = dict(provider_readiness_payload or {})
    run_id = str(run.get("run_id") or "").strip()
    readiness_run_id = str(readiness.get("run_id") or "").strip()
    readiness_is_exact = bool(readiness) and (
        not run_id or (bool(readiness_run_id) and readiness_run_id == run_id)
    )
    readiness_row: Mapping[str, Any] = {}
    if readiness_is_exact:
        for item in readiness.get("providers") or ():
            if not isinstance(item, Mapping):
                continue
            identity = " ".join(
                str(item.get(key) or "")
                for key in ("provider", "provider_name", "provider_health_key")
            ).casefold()
            if "cryptopanic" in identity:
                readiness_row = item
                break

    configured: bool | None = None
    if "cryptopanic_configured" in run:
        configured = bool(run.get("cryptopanic_configured"))
    elif "configured" in readiness_row:
        configured = bool(readiness_row.get("configured"))
    elif configured_fallback is not None:
        configured = bool(configured_fallback)

    skip_reason = str(run.get("cryptopanic_skip_reason") or "").strip() or None
    if "cryptopanic_selected_for_run" in run:
        selected_for_run = bool(run.get("cryptopanic_selected_for_run"))
    elif bool(run.get("cryptopanic_attempted")):
        selected_for_run = True
    elif skip_reason:
        selected_for_run = skip_reason != "profile_disabled"
    else:
        selected_for_run = bool(readiness_row.get("live_call_allowed"))

    if "cryptopanic_live_call_allowed" in run:
        live_call_allowed = bool(run.get("cryptopanic_live_call_allowed"))
    elif "live_call_allowed" in readiness_row:
        live_call_allowed = bool(readiness_row.get("live_call_allowed"))
    else:
        live_call_allowed = False

    return {
        "configured": configured,
        "selected_for_run": selected_for_run,
        "live_call_allowed": live_call_allowed,
        "not_used_reason": skip_reason,
        "readiness_lineage_exact": readiness_is_exact,
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
    exact_run_row: Mapping[str, Any] | None = None,
    provider_readiness_payload: Mapping[str, Any] | None = None,
    cryptopanic_configured_fallback: bool | None = None,
    near_miss_candidates: Iterable[object] = (),
    now: datetime | None = None,
) -> EventAlphaSourceCoverageReport:
    """Build source-pack coverage from readiness, health, and artifact rows."""
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("source coverage now must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    raw_health_by_provider = _health_by_provider(provider_health_rows or {}, now=observed)
    health_by_provider = dict(raw_health_by_provider)
    configured = _configured_providers(provider_status_report, health_by_provider)
    acquisition = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    cryptopanic_run_context = _cryptopanic_run_context(
        exact_run_row=exact_run_row,
        provider_readiness_payload=provider_readiness_payload,
        configured_fallback=cryptopanic_configured_fallback,
    )
    stats = _source_coverage_stats(
        artifact_namespace=artifact_namespace,
        artifact_namespace_dir=artifact_namespace_dir,
        configured=configured,
        health_by_provider=raw_health_by_provider,
        acquisition_rows=acquisition,
        cryptopanic_request_ledger_path=cryptopanic_request_ledger_path,
        cryptopanic_weekly_limit=cryptopanic_weekly_limit,
        cryptopanic_daily_soft_limit=cryptopanic_daily_soft_limit,
        provider_health_rows=provider_health_rows or {},
        cryptopanic_run_context=cryptopanic_run_context,
        now=observed,
    )
    if stats.cryptopanic["configured"]:
        configured.add("cryptopanic")
    provider_status_overrides = _source_coverage_provider_status_overrides(
        stats=stats,
        configured=configured,
        health_by_provider=health_by_provider,
    )
    packs = _build_source_coverage_packs(
        acquisition_rows=acquisition,
        core_rows=core_rows,
        configured=configured,
        health_by_provider=health_by_provider,
        provider_health_rows=provider_health_rows or {},
        provider_status_overrides=provider_status_overrides,
        cryptopanic_effectively_healthy=stats.cryptopanic_effectively_healthy,
        now=observed,
    )
    blocker_summary = _coverage_blocker_summary(
        core_rows,
        near_miss_candidates=near_miss_candidates,
    )
    return _source_coverage_report(
        profile=profile,
        artifact_namespace=artifact_namespace,
        generated_at=observed,
        packs=packs,
        provider_health_rows=provider_health_rows or {},
        acquisition_rows=acquisition,
        core_rows=core_rows,
        stats=stats,
        blocker_summary=blocker_summary,
    )


def _source_coverage_stats(
    *,
    artifact_namespace: str,
    artifact_namespace_dir: str | Path | None,
    configured: set[str],
    health_by_provider: Mapping[str, str],
    acquisition_rows: Iterable[Mapping[str, Any]],
    cryptopanic_request_ledger_path: str | Path | None,
    cryptopanic_weekly_limit: int,
    cryptopanic_daily_soft_limit: int,
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    cryptopanic_run_context: Mapping[str, Any],
    now: datetime,
) -> _SourceCoverageStats:
    cryptopanic = _cryptopanic_stats(
        configured=configured,
        health_by_provider=health_by_provider,
        acquisition_rows=acquisition_rows,
        request_ledger_path=cryptopanic_request_ledger_path,
        weekly_limit=cryptopanic_weekly_limit,
        daily_soft_limit=cryptopanic_daily_soft_limit,
        now=now,
        raw_backoff_present=_raw_provider_backoff_present(provider_health_rows, "cryptopanic"),
        configured_override=cryptopanic_run_context.get("configured"),
        selected_for_run=bool(cryptopanic_run_context.get("selected_for_run")),
        live_call_allowed=bool(cryptopanic_run_context.get("live_call_allowed")),
        run_not_used_reason=str(cryptopanic_run_context.get("not_used_reason") or "") or None,
    )
    coinalyze = _coinalyze_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
        health_by_provider=health_by_provider,
    )
    bybit = _bybit_announcements_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
        health_by_provider=health_by_provider,
    )
    unlock_calendar = _unlock_calendar_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
    )
    dex_onchain = _dex_onchain_artifact_stats(
        artifact_namespace_dir=artifact_namespace_dir,
        artifact_namespace=artifact_namespace,
    )
    activation = event_official_exchange_activation.activation_artifact_stats(
        artifact_namespace_dir if artifact_namespace_dir is not None else _namespace_dir(artifact_namespace)
    )
    return _SourceCoverageStats(
        cryptopanic=cryptopanic,
        coinalyze=coinalyze,
        bybit=bybit,
        unlock_calendar=unlock_calendar,
        dex_onchain=dex_onchain,
        activation=activation,
        cryptopanic_effectively_healthy=cryptopanic["coverage_status"] in {
            "observed_healthy",
            "observed_partial_success",
        },
        bybit_effectively_healthy=bybit["provider_health_status"] in {
            "observed_healthy",
            "observed_no_results",
            "observed_partial_success",
        },
    )


def _source_coverage_provider_status_overrides(
    *,
    stats: _SourceCoverageStats,
    configured: set[str],
    health_by_provider: dict[str, str],
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if stats.cryptopanic["successful_requests"] or stats.cryptopanic_effectively_healthy:
        overrides["cryptopanic"] = "degraded" if stats.cryptopanic["failed_requests"] else "healthy"
        health_by_provider["cryptopanic"] = overrides["cryptopanic"]
    if stats.bybit_effectively_healthy:
        overrides["bybit_announcements_public"] = "healthy"
        health_by_provider["bybit_announcements_public"] = "healthy"
        configured.add("bybit_announcements_public")
    _apply_activation_provider_status(stats.activation["rows"], configured, health_by_provider, overrides)
    _add_fixture_ready_providers(stats.unlock_calendar["provider_rows"], configured)
    _add_fixture_ready_providers(stats.dex_onchain["provider_rows"], configured)
    return overrides


def _apply_activation_provider_status(
    rows: Iterable[Mapping[str, Any]],
    configured: set[str],
    health_by_provider: dict[str, str],
    overrides: dict[str, str],
) -> None:
    for row in rows:
        provider = str(row.get("provider") or "")
        if not provider:
            continue
        if bool(row.get("configured")):
            configured.add(provider)
        if event_official_exchange_activation.row_is_healthy(row):
            overrides[provider] = "healthy"
            health_by_provider[provider] = "healthy"
            configured.add(provider)


def _add_fixture_ready_providers(rows: Iterable[Mapping[str, Any]], configured: set[str]) -> None:
    for row in rows:
        provider = str(row.get("provider") or "")
        if not provider:
            continue
        fixture_ready = str(row.get("fixture_parser_status") or "") == "pass"
        if bool(row.get("configured")) or fixture_ready:
            configured.add(provider)


def _build_source_coverage_packs(
    *,
    acquisition_rows: list[dict[str, Any]],
    core_rows: list[dict[str, Any]],
    configured: set[str],
    health_by_provider: Mapping[str, str],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    provider_status_overrides: Mapping[str, str],
    cryptopanic_effectively_healthy: bool,
    now: datetime,
) -> tuple[EventAlphaSourceCoveragePack, ...]:
    return tuple(
        _build_source_coverage_pack(
            pack_name,
            acquisition_rows=acquisition_rows,
            core_rows=core_rows,
            configured=configured,
            health_by_provider=health_by_provider,
            provider_health_rows=provider_health_rows,
            provider_status_overrides=provider_status_overrides,
            cryptopanic_effectively_healthy=cryptopanic_effectively_healthy,
            now=now,
        )
        for pack_name in SOURCE_COVERAGE_PACK_ORDER
    )


def _build_source_coverage_pack(
    pack_name: str,
    *,
    acquisition_rows: list[dict[str, Any]],
    core_rows: list[dict[str, Any]],
    configured: set[str],
    health_by_provider: Mapping[str, str],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    provider_status_overrides: Mapping[str, str],
    cryptopanic_effectively_healthy: bool,
    now: datetime,
) -> EventAlphaSourceCoveragePack:
    pack = event_source_packs.get_source_pack(pack_name)
    preferred = tuple(dict.fromkeys(pack.preferred_providers))
    configured_for_pack = tuple(
        provider for provider in preferred if provider in configured or provider in health_by_provider
    )
    missing = tuple(provider for provider in preferred if provider not in configured_for_pack)
    healthy = tuple(
        provider
        for provider in configured_for_pack
        if _provider_effective_status(provider, health_by_provider) == "healthy"
    )
    unknown = tuple(
        provider
        for provider in configured_for_pack
        if _provider_effective_status(provider, health_by_provider) in {"unknown", "not_observed"}
    )
    degraded = tuple(
        provider
        for provider in configured_for_pack
        if _provider_effective_status(provider, health_by_provider) in {"degraded", "backoff", "unavailable"}
    )
    pack_rows = [row for row in acquisition_rows if str(row.get("source_pack") or "") == pack_name]
    accepted = sum(_accepted_count(row) for row in pack_rows)
    rejected_only = sum(1 for row in pack_rows if _status(row) == "rejected_results_only")
    skipped_budget = sum(1 for row in pack_rows if _status(row) == "skipped_budget")
    unavailable = sum(
        1
        for row in pack_rows
        if _status(row) in {"provider_unavailable", "provider_backoff", "failed_soft", "skipped_config"}
    )
    blocked = _coverage_blocked_count(pack_name, pack_rows=pack_rows, core_rows=core_rows)
    coverage_status = _pack_coverage_status(
        configured_for_pack=configured_for_pack,
        missing=missing,
        healthy=healthy,
        unknown=unknown,
        degraded=degraded,
        provider_unavailable_count=unavailable,
    )
    return EventAlphaSourceCoveragePack(
        source_pack=pack_name,
        configured_providers=_sorted_tuple(configured_for_pack),
        missing_providers=_sorted_tuple(missing),
        healthy_providers=_sorted_tuple(healthy),
        unknown_or_unobserved_providers=_sorted_tuple(unknown),
        degraded_or_backoff_providers=_sorted_tuple(degraded),
        provider_coverage_status=coverage_status,
        provider_role_statuses=_provider_role_statuses_for_pack(
            provider_health_rows,
            preferred=preferred,
            unknown=unknown,
            now=now,
            effective_status_overrides=provider_status_overrides,
        ),
        evidence_absence_meaningful=_evidence_absence_meaningful(pack_name, healthy, degraded),
        coverage_gap_reason=_coverage_gap_reason(
            coverage_status=coverage_status,
            missing=missing,
            unknown=unknown,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
        ),
        providers_missing_for_confirmation=_sorted_tuple(missing),
        providers_degraded_for_confirmation=_sorted_tuple(degraded),
        candidates_blocked_by_coverage_gap=blocked,
        accepted_evidence_count=accepted,
        rejected_only_count=rejected_only,
        skipped_budget_count=skipped_budget,
        provider_unavailable_count=unavailable,
        article_quality_counts=_article_quality_counts(pack_rows),
        recommended_actions=_pack_recommended_actions(
            pack_name,
            missing=missing,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
            satisfied_providers={"cryptopanic"} if cryptopanic_effectively_healthy else (),
        ),
    )


def _source_coverage_report(
    *,
    profile: str,
    artifact_namespace: str,
    generated_at: datetime,
    packs: tuple[EventAlphaSourceCoveragePack, ...],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    acquisition_rows: list[dict[str, Any]],
    core_rows: list[dict[str, Any]],
    stats: _SourceCoverageStats,
    blocker_summary: Mapping[str, int],
) -> EventAlphaSourceCoverageReport:
    cryptopanic_stats = stats.cryptopanic
    coinalyze_stats = stats.coinalyze
    bybit_stats = stats.bybit
    unlock_calendar_stats = stats.unlock_calendar
    dex_onchain_stats = stats.dex_onchain
    activation_stats = stats.activation
    return EventAlphaSourceCoverageReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        generated_at=generated_at.isoformat(),
        packs=packs,
        provider_health_rows=len(provider_health_rows or {}),
        acquisition_rows=len(acquisition_rows),
        core_rows=len(core_rows),
        cryptopanic_configured=cryptopanic_stats["configured"],
        cryptopanic_selected_for_run=cryptopanic_stats["selected_for_run"],
        cryptopanic_live_call_allowed=cryptopanic_stats["live_call_allowed"],
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
        candidates_blocked_by_source_coverage=blocker_summary["candidates_blocked_by_source_coverage"],
        candidates_blocked_by_missing_strong_source=blocker_summary["candidates_blocked_by_missing_strong_source"],
        candidates_blocked_by_missing_official_source=blocker_summary["candidates_blocked_by_missing_official_source"],
        candidates_blocked_by_missing_structured_source=blocker_summary["candidates_blocked_by_missing_structured_source"],
        candidates_blocked_by_evidence_not_acquired=blocker_summary["candidates_blocked_by_evidence_not_acquired"],
        candidates_blocked_by_provider_unavailable=blocker_summary["candidates_blocked_by_provider_unavailable"],
        candidates_blocked_by_market_context=blocker_summary["candidates_blocked_by_market_context"],
        candidate_families_blocked_by_source_coverage=blocker_summary["candidate_families_blocked_by_source_coverage"],
        candidate_families_blocked_by_market_coverage=blocker_summary["candidate_families_blocked_by_market_coverage"],
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
def _namespace_dir(artifact_namespace: str) -> Path:
    base = Path(os.getenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    return base / str(artifact_namespace or "default")
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


def _coverage_blocker_summary(
    core_rows: Iterable[Mapping[str, Any]],
    *,
    near_miss_candidates: Iterable[object] = (),
) -> dict[str, int]:
    """Count explicit coverage blockers without treating missing evidence as proof."""
    strong: set[str] = set()
    official: set[str] = set()
    structured: set[str] = set()
    evidence_not_acquired: set[str] = set()
    provider_unavailable: set[str] = set()
    market_context: set[str] = set()
    source_families: set[tuple[str, str]] = set()
    market_families: set[tuple[str, str]] = set()
    core_family_by_id: dict[str, tuple[str, str]] = {}

    rows = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    for index, row in enumerate(rows):
        core_id = str(row.get("core_opportunity_id") or "").strip()
        identity = f"core:{core_id}" if core_id else f"row:{index}"
        family = _coverage_family_key(row)
        if core_id:
            core_family_by_id[core_id] = family
        reasons = set(_coverage_text_values(
            row.get("why_not_alertable"),
            row.get("missing_fields"),
            row.get("live_confirmation_missing_requirements"),
            row.get("upgrade_requirements"),
            row.get("source_pack_confirmation_status"),
            row.get("acquisition_confirmation_status"),
            row.get("acquisition_confirmation_reason"),
            row.get("no_upgrade_reason"),
        ))
        actions = set(_coverage_text_values(
            row.get("recommended_refresh_actions"),
            row.get("near_miss_actions"),
            row.get("recommended_actions"),
        ))
        source_unmet = any(
            row.get(key) is False
            for key in ("source_requirements_met", "opportunity_type_source_requirements_met")
        )
        pack = str(row.get("source_pack") or row.get("evidence_acquisition_source_pack") or "").casefold()
        official_missing = (
            any("official" in reason and ("required" in reason or "missing" in reason) for reason in reasons)
            or pack in {
                "official_exchange_listing_pack",
                "official_perp_listing_pack",
                "official_exchange_risk_pack",
                "listing_liquidity_pack",
                "perp_listing_squeeze_pack",
            }
            and source_unmet
        )
        structured_missing = (
            any(
                any(token in reason for token in ("structured_unlock", "structured_source", "calendar_source"))
                for reason in reasons
            )
            or pack == "unlock_supply_pack" and source_unmet
        )
        explicit_strong_missing = any(
            any(token in reason for token in (
                "strong_source_missing",
                "risk_source_not_confirmed",
                "source_pack_confirmation_missing",
                "source_pack_confirmation_status",
                "validated_catalyst",
                "direct_token_mechanism",
            ))
            for reason in reasons
        )
        source_gap = source_unmet or any(
            value in {"coverage_gap", "not_configured", "degraded", "unavailable", "partial"}
            for value in reasons
        ) or bool(actions & {"source_pack_search", "targeted_evidence_refresh", "official_source_search"})
        if official_missing:
            official.add(identity)
        if structured_missing:
            structured.add(identity)
        if not official_missing and not structured_missing and (explicit_strong_missing or source_gap):
            strong.add(identity)

        results = row.get("evidence_acquisition_results")
        result_status = str(results.get("status") or "") if isinstance(results, Mapping) else ""
        acquisition_status = str(
            row.get("evidence_acquisition_status")
            or row.get("acquisition_confirmation_status")
            or result_status
            or ""
        ).casefold()
        accepted = _accepted_count(row)
        if source_gap and accepted <= 0 and acquisition_status in {
            "",
            "not_executed",
            "coverage_gap",
            "skipped_config",
            "skipped_live_calls_disabled",
            "provider_unavailable",
            "provider_backoff",
            "failed_soft",
        }:
            evidence_not_acquired.add(identity)
        failures = _coverage_text_values(
            row.get("provider_failures"),
            row.get("evidence_acquisition_provider_failures"),
        )
        provider_coverage_status = str(
            row.get("provider_coverage_status")
            or row.get("source_pack_coverage_status")
            or ""
        ).casefold()
        if (
            failures
            or acquisition_status in {"provider_unavailable", "provider_backoff", "failed_soft"}
            or provider_coverage_status in {"degraded", "unavailable", "backoff"}
        ):
            provider_unavailable.add(identity)

        freshness = str(
            row.get("market_context_freshness_status")
            or row.get("integrated_market_freshness_status")
            or row.get("market_data_freshness")
            or ""
        ).casefold()
        market_blocked = (
            freshness in {"missing", "stale", "unknown"}
            if freshness
            else row.get("market_requirements_met") is False
        )
        if market_blocked:
            market_context.add(identity)
            market_families.add(family)
        if identity in strong or identity in official or identity in structured or identity in evidence_not_acquired or identity in provider_unavailable:
            source_families.add(family)

    source_ids = strong | official | structured | evidence_not_acquired | provider_unavailable
    _add_near_miss_coverage_blockers(
        near_miss_candidates,
        core_family_by_id=core_family_by_id,
        source_ids=source_ids,
        evidence_not_acquired=evidence_not_acquired,
        source_families=source_families,
    )

    return _coverage_blocker_counts((
        source_ids, strong, official, structured, evidence_not_acquired,
        provider_unavailable, market_context, source_families, market_families,
    ))


def _coverage_blocker_counts(groups: tuple[set[object], ...]) -> dict[str, int]:
    (source_ids, strong, official, structured, evidence_not_acquired,
     provider_unavailable, market_context, source_families, market_families) = groups
    return {
        "candidates_blocked_by_source_coverage": len(source_ids),
        "candidates_blocked_by_missing_strong_source": len(strong),
        "candidates_blocked_by_missing_official_source": len(official),
        "candidates_blocked_by_missing_structured_source": len(structured),
        "candidates_blocked_by_evidence_not_acquired": len(evidence_not_acquired),
        "candidates_blocked_by_provider_unavailable": len(provider_unavailable),
        "candidates_blocked_by_market_context": len(market_context),
        "candidate_families_blocked_by_source_coverage": len(source_families),
        "candidate_families_blocked_by_market_coverage": len(market_families),
    }


def _add_near_miss_coverage_blockers(
    near_miss_candidates: Iterable[object],
    *,
    core_family_by_id: Mapping[str, tuple[str, str]],
    source_ids: set[str],
    evidence_not_acquired: set[str],
    source_families: set[tuple[str, str]],
) -> None:
    for near in near_miss_candidates:
        actions = set(_coverage_text_values(_coverage_value(near, "recommended_refresh_actions")))
        if not actions & {"source_pack_search", "targeted_evidence_refresh", "official_source_search"}:
            continue
        core_id = str(_coverage_value(near, "core_opportunity_id") or "").strip()
        family = core_family_by_id.get(core_id) or _coverage_family_key({
            "coin_id": _coverage_value(near, "coin_id"),
            "symbol": _coverage_value(near, "symbol"),
            "source_pack": _coverage_value(near, "source_pack"),
        })
        identity = (
            f"core:{core_id}"
            if core_id
            else f"near:{_coverage_value(near, 'near_miss_id') or '|'.join(family)}"
        )
        source_ids.add(identity)
        evidence_not_acquired.add(identity)
        source_families.add(family)


def _coverage_family_key(row: Mapping[str, Any]) -> tuple[str, str]:
    asset = str(row.get("coin_id") or row.get("symbol") or row.get("core_opportunity_id") or "unknown").casefold()
    path = str(
        row.get("primary_impact_path")
        or row.get("impact_path_type")
        or row.get("source_pack")
        or "unknown"
    ).casefold()
    if path in {"venue_value_capture", "proxy_attention", "proxy_exposure"}:
        path = "proxy"
    return asset, path


def _coverage_text_values(*values: object) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, Mapping):
            out.extend(_coverage_text_values(*value.values()))
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            out.extend(_coverage_text_values(*value))
        else:
            text = str(value).strip().casefold()
            if text:
                out.append(text)
    return tuple(dict.fromkeys(out))


def _coverage_value(item: object, key: str) -> object:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


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
        return "skipped_live_calls_disabled"
    if degraded_set and not healthy_set:
        return "degraded"
    if healthy_set and not missing_set and not degraded_set and not provider_unavailable_count:
        return "partial" if unknown_set else "complete"
    if healthy_set:
        return "partial"
    return "skipped_live_calls_disabled" if unknown_set else "unavailable"
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
    if coverage_status in {"not_configured", "degraded", "unavailable", "partial", "unknown", "skipped_live_calls_disabled"}:
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
