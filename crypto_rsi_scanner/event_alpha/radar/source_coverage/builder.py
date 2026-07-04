"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (builder)."""

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
