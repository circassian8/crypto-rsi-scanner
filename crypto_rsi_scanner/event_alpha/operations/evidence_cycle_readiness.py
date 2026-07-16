"""Read-only readiness for a bounded Event Alpha evidence-acquisition cycle.

This module projects the effective profile/config state, deterministic evidence
planner catalog, current persisted plans, provider dispatch, and HTTP fan-out.
It never calls a provider, writes an artifact, sends a notification, or creates
authorization.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Any, Iterable, Mapping, Sequence

from ...event_providers import cryptopanic as cryptopanic_provider
from ..artifacts.context import context_from_profile, safe_path_label
from ..config.profiles import EventAlphaProfile, get_profile
from ..providers import provider_health_core
from ..providers import source_packs
from ..radar.evidence.provider_contract import (
    PLANNER_PROVIDER_HINTS,
    explicit_live_authorizations,
)
from ..radar.llm.evidence_planner import EvidencePlannerRequest, plan_evidence


CONTRACT_VERSION = "event_alpha_evidence_cycle_readiness_v1"
MAX_PERSISTED_PLAN_BYTES = 8 * 1024 * 1024
_BUDGET_ENV_CASTERS: Mapping[str, type] = {
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS": float,
    "EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST": int,
    "EVENT_DISCOVERY_GDELT_TIMEOUT": float,
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT": float,
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT": float,
    "EVENT_LLM_MAX_CALLS_PER_DAY": int,
    "EVENT_LLM_MAX_CALLS_PER_RUN": int,
    "EVENT_LLM_MAX_PARALLEL_CALLS": int,
}
_SETTING_NAMES = (
    "DATA_DIR",
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED",
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY",
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES",
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES",
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS",
    "EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF",
    "EVENT_ALPHA_RUN_MODE",
    "EVENT_CATALYST_SEARCH_FIXTURE_PATH",
    "EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY",
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY",
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET",
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE",
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
    "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE",
    "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH",
    "EVENT_DISCOVERY_COINMARKETCAL_PATH",
    "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
    "EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES",
    "EVENT_DISCOVERY_CRYPTOPANIC_LIVE",
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST",
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY",
    "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH",
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT",
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT",
    "EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT",
    "EVENT_DISCOVERY_GDELT_LIVE",
    "EVENT_DISCOVERY_GDELT_PATH",
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE",
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE",
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS",
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH",
    "EVENT_DISCOVERY_TOKENOMIST_PATH",
    "EVENT_LLM_ENABLED",
    "EVENT_LLM_EXTRACTOR_ENABLED",
    "EVENT_LLM_CATALYST_FRAMES_ENABLED",
    "EVENT_LLM_MAX_CALLS_PER_DAY",
    "EVENT_LLM_MAX_CALLS_PER_RUN",
    "EVENT_LLM_MAX_PARALLEL_CALLS",
    "EVENT_LLM_PROVIDER",
    "EVENT_LLM_EXTRACTOR_PROVIDER",
    "EVENT_LLM_CATALYST_FRAMES_PROVIDER",
    "OPENAI_API_KEY",
)
_CREDENTIAL_PRESENCE_SETTINGS = {
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY",
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET",
    "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
    "OPENAI_API_KEY",
}


from .evidence_cycle_readiness_models import (
    EvidenceCycleReadiness,
    EvidencePlannerCatalogRow,
    EvidenceProviderReadiness,
    PersistedEvidencePlanReadiness,
)

from .evidence_cycle_provider_readiness import (
    provider_readiness_rows,
    source_configuration_summary as summarize_source_configuration,
)
from .evidence_cycle_readiness_format import format_evidence_cycle_readiness
def build_evidence_cycle_readiness(
    *,
    profile: str = "notify_llm_quality",
    artifact_namespace: str | None = None,
    artifact_base_dir: str | Path | None = None,
    persisted_plan_path: str | Path | None = None,
    provider_health_path: str | Path | None = None,
    setting_overrides: Mapping[str, object] | None = None,
    authorization_environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> EvidenceCycleReadiness:
    """Build a no-write/no-network evidence-cycle readiness projection."""

    observed = _as_utc(now or datetime.now(timezone.utc))
    selected_profile = get_profile(profile)
    settings = _effective_settings(
        selected_profile,
        setting_overrides or {},
        authorization_environ=authorization_environ,
    )
    context = context_from_profile(
        selected_profile.name,
        run_mode=str(settings.get("EVENT_ALPHA_RUN_MODE") or "") or None,
        base_dir=artifact_base_dir,
        artifact_namespace=artifact_namespace,
    )
    fixture_only = bool(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY"))
    max_candidates = max(
        0, int(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES") or 0)
    )
    max_queries = max(
        0, int(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES") or 0)
    )
    catalog = _deterministic_planner_catalog()
    catalog_hint_counts = Counter(
        hint for row in catalog for hint in row.ordered_provider_hints
    )
    health_path = Path(provider_health_path or context.provider_health_path)
    health_rows = provider_health_core.load_provider_health(health_path)
    providers = provider_readiness_rows(
        settings,
        fixture_only=fixture_only,
        health_rows=health_rows,
        now=observed,
    )
    provider_by_hint = {row.provider_hint: row for row in providers}
    catalog_hints = set(catalog_hint_counts)
    missing_hints = tuple(sorted(catalog_hints - set(provider_by_hint)))
    fixture_fallback_hints = tuple(
        sorted(
            hint
            for hint in catalog_hints
            if not fixture_only
            and hint in provider_by_hint
            and provider_by_hint[hint].mapping_kind == "implicit_fixture_fallback"
        )
    )
    persisted = _persisted_plan_readiness(
        Path(persisted_plan_path or context.impact_hypothesis_store_path),
        provider_by_hint=provider_by_hint,
        max_queries=max_queries,
    )
    selected_provider_hints = (
        tuple(sorted((persisted.provider_hint_counts or {}).keys()))
        if persisted.provider_hint_counts is not None
        else None
    )
    selected_provider_hints_status = (
        "exact_latest_persisted_plan"
        if selected_provider_hints is not None
        else "not_materialized_candidate_dependent"
    )
    source_configuration_summary = summarize_source_configuration(providers)
    decision = _readiness_decision(
        settings=settings,
        selected_profile=selected_profile,
        fixture_only=fixture_only,
        max_candidates=max_candidates,
        max_queries=max_queries,
        catalog=catalog,
        catalog_hints=catalog_hints,
        provider_by_hint=provider_by_hint,
        providers=providers,
        persisted=persisted,
        missing_hints=missing_hints,
        fixture_fallback_hints=fixture_fallback_hints,
        now=observed,
    )
    return _assemble_readiness_report(
        observed=observed,
        selected_profile=selected_profile,
        context=context,
        settings=settings,
        fixture_only=fixture_only,
        max_candidates=max_candidates,
        max_queries=max_queries,
        catalog=catalog,
        catalog_hint_counts=catalog_hint_counts,
        persisted=persisted,
        selected_provider_hints=selected_provider_hints,
        selected_provider_hints_status=selected_provider_hints_status,
        providers=providers,
        source_configuration_summary=source_configuration_summary,
        missing_hints=missing_hints,
        fixture_fallback_hints=fixture_fallback_hints,
        decision=decision,
    )


def _readiness_decision(
    *,
    settings: Mapping[str, object],
    selected_profile: EventAlphaProfile,
    fixture_only: bool,
    max_candidates: int,
    max_queries: int,
    catalog: Sequence[EvidencePlannerCatalogRow],
    catalog_hints: set[str],
    provider_by_hint: Mapping[str, EvidenceProviderReadiness],
    providers: Sequence[EvidenceProviderReadiness],
    persisted: PersistedEvidencePlanReadiness,
    missing_hints: tuple[str, ...],
    fixture_fallback_hints: tuple[str, ...],
    now: datetime,
) -> dict[str, object]:
    blockers: list[str] = []
    if not bool(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED")):
        blockers.append("evidence_acquisition_disabled")
    if selected_profile.send:
        blockers.append("profile_requests_send")
    if max_candidates <= 0:
        blockers.append("max_candidates_must_be_positive")
    if max_queries <= 0:
        blockers.append("max_queries_must_be_positive")
    blockers.extend(f"planner_hint_missing_runtime_mapping:{hint}" for hint in missing_hints)
    blockers.extend(
        f"planner_hint_uses_implicit_fixture_fallback:{hint}"
        for hint in fixture_fallback_hints
    )
    selected_hints = (
        tuple(sorted((persisted.provider_hint_counts or {}).keys()))
        if persisted.provider_hint_counts is not None
        else None
    )
    selected_unready = tuple(
        hint
        for hint in selected_hints or ()
        if hint not in provider_by_hint or not provider_by_hint[hint].evidence_query_eligible
    )
    blockers.extend(f"selected_provider_not_ready:{hint}" for hint in selected_unready)
    eligible_hints = tuple(
        sorted(
            row.provider_hint
            for row in providers
            if row.evidence_query_eligible
            and row.acquisition_mode not in {"fixture", "fixture_stub"}
        )
    )
    if not fixture_only and not eligible_hints:
        blockers.append("no_current_evidence_provider_eligible")
    gaps = tuple(sorted(
        hint
        for hint in catalog_hints
        if hint in provider_by_hint
        and not provider_by_hint[hint].live_evidence_eligible
        and not fixture_only
    ))
    warnings = _readiness_warnings(gaps, persisted=persisted, providers=providers)
    evidence_acquisition_http_upper = _deterministic_evidence_acquisition_http_upper_bound(
        catalog,
        provider_by_hint=provider_by_hint,
        max_candidates=max_candidates,
        max_queries=max_queries,
    )
    cadence_status, cadence_permitted = _provider_cadence_status(
        settings,
        selected_hints=selected_hints or eligible_hints,
        provider_by_hint=provider_by_hint,
        now=now,
    )
    exact_nonempty_plan = bool(
        persisted.status == "exact_latest_persisted_run"
        and selected_hints
        and persisted.logical_query_count
    )
    bounded_catalog_plan = bool(
        eligible_hints
        and persisted.status
        in {
            "not_materialized_no_persisted_store",
            "not_materialized_empty_store",
            "not_materialized_for_latest_run",
            "exact_empty_latest_persisted_run",
        }
    )
    fresh_cycle_permitted = bool(
        not fixture_only
        and (exact_nonempty_plan or bounded_catalog_plan)
        and not blockers
        and not selected_unready
        and cadence_permitted
    )
    if fresh_cycle_permitted and exact_nonempty_plan:
        fresh_cycle_status = "permitted_exact_plan_authorization_health_and_cadence_ready"
    elif fresh_cycle_permitted:
        fresh_cycle_status = (
            "permitted_catalog_bound_authorization_health_and_cadence_ready"
        )
    elif fixture_only:
        fresh_cycle_status = "not_applicable_fixture_only"
    elif selected_unready:
        fresh_cycle_status = "not_permitted_selected_provider_not_ready"
    elif not eligible_hints:
        fresh_cycle_status = "not_permitted_no_current_evidence_provider_eligible"
    elif not cadence_permitted:
        fresh_cycle_status = f"not_permitted_{cadence_status}"
    elif not exact_nonempty_plan and not bounded_catalog_plan:
        fresh_cycle_status = "not_permitted_persisted_plan_state_unavailable"
    else:
        fresh_cycle_status = "not_permitted_readiness_blocked"
    status = _readiness_status(blockers, gaps, persisted)
    next_command, next_activity = _next_safe_step(
        selected_profile.name,
        fixture_only=fixture_only,
        fresh_cycle_permitted=fresh_cycle_permitted,
    )
    gdelt = provider_by_hint.get("gdelt")
    gdelt_fixed = bool(
        gdelt
        and gdelt.runtime_mapping == "GdeltCatalystSearchProvider"
        and gdelt.mapping_kind != "implicit_fixture_fallback"
    )
    return {
        "blockers": tuple(dict.fromkeys(blockers)),
        "gaps": gaps,
        "warnings": tuple(dict.fromkeys(warnings)),
        "evidence_acquisition_http_upper": evidence_acquisition_http_upper,
        "status": status,
        "next_command": next_command,
        "next_activity": next_activity,
        "gdelt_fixed": gdelt_fixed,
        "fresh_cycle_status": fresh_cycle_status,
        "fresh_cycle_permitted": fresh_cycle_permitted,
        "cadence_status": cadence_status,
    }


def _readiness_warnings(
    gaps: Sequence[str],
    *,
    persisted: PersistedEvidencePlanReadiness,
    providers: Sequence[EvidenceProviderReadiness],
) -> list[str]:
    warnings: list[str] = []
    if gaps:
        warnings.append(
            "some deterministic source packs depend on providers without current live evidence eligibility"
        )
    if persisted.status.startswith("not_materialized"):
        warnings.append(
            "next-cycle exact query counts are candidate-dependent and not yet materialized; they are not zero"
        )
    elif persisted.status not in {
        "exact_latest_persisted_run",
        "exact_empty_latest_persisted_run",
    }:
        warnings.append(f"persisted plan is not exact: {persisted.status}")
    if any(
        row.persisted_health_status in {"backoff", "degraded"}
        for row in providers
    ):
        warnings.append("persisted provider health contains degraded or backoff state")
    return warnings


def _readiness_status(
    blockers: Sequence[str],
    gaps: Sequence[str],
    persisted: PersistedEvidencePlanReadiness,
) -> str:
    if blockers:
        return "blocked"
    if gaps:
        return "ready_with_candidate_dependent_provider_gaps"
    if persisted.logical_query_count is None:
        return "ready_exact_plan_not_materialized"
    return "ready"


def _provider_cadence_status(
    settings: Mapping[str, object],
    *,
    selected_hints: tuple[str, ...] | None,
    provider_by_hint: Mapping[str, EvidenceProviderReadiness],
    now: datetime,
) -> tuple[str, bool]:
    if selected_hints is None:
        return "not_assessable_plan_not_materialized", False
    if not selected_hints:
        return "not_permitted_no_selected_evidence_queries", False
    selected_live = tuple(
        hint
        for hint in selected_hints
        if provider_by_hint.get(hint) is not None
        and provider_by_hint[hint].current_provider_call_eligibility
    )
    if "cryptopanic" in selected_live:
        usage = cryptopanic_provider.cryptopanic_usage_summary(
            settings.get("EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH"),
            now=now,
            weekly_limit=int(
                settings.get("EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT") or 0
            ),
            daily_soft_limit=int(
                settings.get(
                    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT"
                )
                or 0
            ),
        )
        if usage.remaining_weekly is not None and usage.remaining_weekly <= 0:
            return "cryptopanic_weekly_quota_exhausted", False
        if usage.remaining_daily_soft is not None and usage.remaining_daily_soft <= 0:
            return "cryptopanic_daily_soft_limit_reached", False
    if selected_live:
        return "eligible_bounded_provider_limits_rechecked_at_execution", True
    return "not_applicable_selected_sources_are_local_no_http", True


def _next_safe_step(
    profile: str,
    *,
    fixture_only: bool,
    fresh_cycle_permitted: bool,
) -> tuple[str, str]:
    if fixture_only:
        return (
            "make event-alpha-evidence-acquisition-smoke PYTHON=python3",
            "offline fixture reads only; zero HTTP provider requests",
        )
    if fresh_cycle_permitted:
        return (
            f"CONFIRM=1 make event-alpha-evidence-validation-cycle PROFILE={profile} PYTHON=python3",
            (
                "one bounded fresh no-send evidence cycle using only already-authorized "
                "providers, then source coverage, cards, brief, preview, and strict doctor"
            ),
        )
    return (
        f"make event-alpha-notify-preview PROFILE={profile} PYTHON=python3",
        "zero provider requests; artifact-backed no-send notification preview",
    )


def _assemble_readiness_report(
    *,
    observed: datetime,
    selected_profile: EventAlphaProfile,
    context: Any,
    settings: Mapping[str, object],
    fixture_only: bool,
    max_candidates: int,
    max_queries: int,
    catalog: tuple[EvidencePlannerCatalogRow, ...],
    catalog_hint_counts: Mapping[str, int],
    persisted: PersistedEvidencePlanReadiness,
    selected_provider_hints: tuple[str, ...] | None,
    selected_provider_hints_status: str,
    providers: tuple[EvidenceProviderReadiness, ...],
    source_configuration_summary: Mapping[str, tuple[str, ...]],
    missing_hints: tuple[str, ...],
    fixture_fallback_hints: tuple[str, ...],
    decision: Mapping[str, object],
) -> EvidenceCycleReadiness:
    gdelt_fixed = bool(decision["gdelt_fixed"])
    llm = _llm_readiness(settings)
    return EvidenceCycleReadiness(
        contract_version=CONTRACT_VERSION,
        checked_at=observed.isoformat(),
        status=str(decision["status"]),
        profile=selected_profile.name,
        profile_run_mode=str(settings.get("EVENT_ALPHA_RUN_MODE") or context.run_mode),
        profile_send_lane_policy=selected_profile.send_lane_policy,
        profile_requests_send=bool(selected_profile.send),
        artifact_namespace=context.artifact_namespace,
        acquisition_enabled=bool(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED")),
        fixture_only=fixture_only,
        max_candidates=max_candidates,
        max_logical_queries=max_queries,
        max_results_per_query=max(
            0, int(settings.get("EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY") or 0)
        ),
        timeout_seconds=max(
            0.0,
            float(settings.get("EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS") or 0),
        ),
        deterministic_catalog=catalog,
        deterministic_catalog_provider_hint_counts=dict(sorted(catalog_hint_counts.items())),
        deterministic_catalog_logical_query_count=sum(row.logical_query_count for row in catalog),
        deterministic_catalog_max_queries_per_candidate=max(
            (row.logical_query_count for row in catalog), default=0
        ),
        persisted_current_plan=persisted,
        selected_provider_hints_status=selected_provider_hints_status,
        selected_provider_hints=selected_provider_hints,
        provider_mapping=providers,
        source_configuration_summary=source_configuration_summary,
        mapping_missing_hints=missing_hints,
        mapping_fixture_fallback_hints=fixture_fallback_hints,
        gdelt_runtime_mapping_status=(
            "explicit_gated_gdelt_adapter" if gdelt_fixed else "missing_or_fixture_fallback"
        ),
        gdelt_runtime_mapping_defect_fixed=gdelt_fixed,
        evidence_acquisition_http_request_upper_bound=int(
            decision["evidence_acquisition_http_upper"]
        ),
        logical_queries_are_http_requests=False,
        blockers=tuple(decision["blockers"]),
        candidate_dependent_provider_gaps=tuple(decision["gaps"]),
        warnings=tuple(decision["warnings"]),
        fresh_validation_cycle_status=str(decision["fresh_cycle_status"]),
        fresh_validation_cycle_permitted=bool(decision["fresh_cycle_permitted"]),
        provider_cadence_status=str(decision["cadence_status"]),
        next_safe_command=str(decision["next_command"]),
        expected_provider_activity_for_next_command=str(decision["next_activity"]),
        authorization_boundary=(
            "readiness separates profile capability from already-present explicit environment "
            "authorization and observes only credential presence, local inputs, and persisted "
            "health; it never enables or mutates authorization"
        ),
        llm_profile_capability_enabled=bool(llm["profile_capability"]),
        llm_current_explicit_authorization=bool(llm["current_authorization"]),
        llm_provider=str(llm["provider"]),
        llm_credential_present=llm["credential_present"],
        llm_availability_status=str(llm["status"]),
        llm_stage_readiness=llm["stages"],
        llm_max_calls_per_run=max(
            0, int(settings.get("EVENT_LLM_MAX_CALLS_PER_RUN") or 0)
        ),
        llm_max_calls_per_day=max(
            0, int(settings.get("EVENT_LLM_MAX_CALLS_PER_DAY") or 0)
        ),
        llm_max_parallel_calls=max(
            0, int(settings.get("EVENT_LLM_MAX_PARALLEL_CALLS") or 0)
        ),
        llm_required_for_readiness=False,
        llm_required_for_evidence_execution=False,
        no_send_state="enforced_readiness_no_send",
        send_requested_by_readiness=False,
        telegram_configuration_inspected=False,
        readiness_contract_artifacts_produced=False,
        source_independence_contract_production=(
            "enabled_for_materialized_evidence_rows_candidate_dependent"
        ),
        source_independence_artifact_production=(
            "produced_by_a_writing_cycle_when_assessable_evidence_materializes_not_by_readiness"
        ),
        catalyst_attribution_contract_production=(
            "enabled_for_temporally_linked_catalyst_evidence_candidate_dependent"
        ),
        catalyst_attribution_artifact_production=(
            "produced_by_a_writing_cycle_when_linked_catalyst_evidence_materializes_not_by_readiness"
        ),
        credential_values_read=False,
        credential_presence_inspected=True,
        provider_call_planned_by_readiness=False,
        provider_call_attempted_by_readiness=False,
        authorization_created_or_mutated=False,
        telegram_send_attempted=False,
        network_called=False,
        writes_performed=False,
        research_only=True,
    )


def _effective_settings(
    profile: EventAlphaProfile,
    overrides: Mapping[str, object],
    *,
    authorization_environ: Mapping[str, str] | None,
) -> dict[str, object]:
    from ... import config

    values: dict[str, object] = {}
    for name in _SETTING_NAMES:
        value = getattr(config, name, None)
        values[name] = bool(value) if name in _CREDENTIAL_PRESENCE_SETTINGS else value
    for name, value in profile.config_overrides.items():
        if name not in values:
            continue
        caster = _BUDGET_ENV_CASTERS.get(name)
        raw = os.getenv(f"RSI_{name}") if caster is not None else None
        if raw not in (None, ""):
            try:
                value = caster(raw)
            except (TypeError, ValueError):
                pass
        values[name] = value
    values.update(overrides)
    for name in _CREDENTIAL_PRESENCE_SETTINGS:
        values[name] = bool(values.get(name))
    # Profiles describe capability. Only explicit, already-present environment
    # flags describe current authorization; test/config overrides cannot forge it.
    values["_CURRENT_EXPLICIT_LIVE_AUTHORIZATIONS"] = (
        explicit_live_authorizations(authorization_environ)
    )
    data_dir = Path(values.get("DATA_DIR") or config.DATA_DIR)
    for name, value in tuple(values.items()):
        if not name.endswith("_PATH") or value in (None, ""):
            continue
        path = Path(value).expanduser()
        values[name] = path if path.is_absolute() else data_dir / path
    urls = tuple(str(item).strip() for item in values.get("EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS") or () if str(item).strip())
    if not urls:
        urls = _read_url_list(values.get("EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH"))
    values["EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS"] = tuple(dict.fromkeys(urls))
    return values


def _llm_readiness(settings: Mapping[str, object]) -> dict[str, object]:
    authorizations = settings.get("_CURRENT_EXPLICIT_LIVE_AUTHORIZATIONS")
    stages = {
        "relationship": _llm_stage_readiness(
            settings,
            authorizations=authorizations,
            enabled_setting="EVENT_LLM_ENABLED",
            provider_setting="EVENT_LLM_PROVIDER",
        ),
        "extractor": _llm_stage_readiness(
            settings,
            authorizations=authorizations,
            enabled_setting="EVENT_LLM_EXTRACTOR_ENABLED",
            provider_setting="EVENT_LLM_EXTRACTOR_PROVIDER",
        ),
        "catalyst_frame": _llm_stage_readiness(
            settings,
            authorizations=authorizations,
            enabled_setting="EVENT_LLM_CATALYST_FRAMES_ENABLED",
            provider_setting="EVENT_LLM_CATALYST_FRAMES_PROVIDER",
        ),
    }
    enabled_stages = tuple(
        row for row in stages.values() if bool(row["profile_capability"])
    )
    live_stages = tuple(row for row in enabled_stages if row["provider"] != "fixture")
    available_live_stages = tuple(
        row for row in live_stages if row["status"] == "available_authorized_bounded"
    )
    if not enabled_stages:
        status = "disabled"
    elif not live_stages:
        status = "offline_fixture_available"
    elif len(available_live_stages) == len(live_stages):
        status = "available_authorized_bounded"
    elif available_live_stages:
        status = "partially_available_live_stages"
    elif all(
        row["status"] == "profile_capable_not_currently_authorized"
        for row in live_stages
    ):
        status = "profile_capable_not_currently_authorized"
    elif all(
        row["status"] == "explicitly_authorized_missing_credential"
        for row in live_stages
    ):
        status = "explicitly_authorized_missing_credential"
    else:
        status = "live_stages_not_fully_available"
    providers = tuple(dict.fromkeys(str(row["provider"]) for row in enabled_stages))
    openai_stages = tuple(row for row in enabled_stages if row["provider"] == "openai")
    return {
        "profile_capability": bool(enabled_stages),
        "current_authorization": any(
            bool(row["current_explicit_authorization"]) for row in enabled_stages
        ),
        "provider": providers[0] if len(providers) == 1 else "mixed",
        "credential_present": (
            all(bool(row["credential_present"]) for row in openai_stages)
            if openai_stages
            else None
        ),
        "status": status,
        "stages": stages,
    }


def _llm_stage_readiness(
    settings: Mapping[str, object],
    *,
    authorizations: object,
    enabled_setting: str,
    provider_setting: str,
) -> dict[str, object]:
    capability = bool(settings.get(enabled_setting))
    provider = str(settings.get(provider_setting) or "fixture").strip().casefold()
    current_authorization = bool(
        authorizations.get(enabled_setting)
        if isinstance(authorizations, Mapping)
        else False
    )
    credential_present = bool(settings.get("OPENAI_API_KEY")) if provider == "openai" else None
    if not capability:
        status = (
            "explicit_authorization_present_but_profile_capability_disabled"
            if current_authorization
            else "disabled"
        )
    elif provider == "fixture":
        status = "offline_fixture_available"
    elif provider != "openai":
        status = "unsupported_provider"
    elif not current_authorization:
        status = "profile_capable_not_currently_authorized"
    elif not credential_present:
        status = "explicitly_authorized_missing_credential"
    else:
        status = "available_authorized_bounded"
    return {
        "enabled_setting": enabled_setting,
        "provider_setting": provider_setting,
        "profile_capability": capability,
        "provider": provider,
        "current_explicit_authorization": current_authorization,
        "credential_present": credential_present,
        "status": status,
    }


def _deterministic_planner_catalog() -> tuple[EvidencePlannerCatalogRow, ...]:
    rows: list[EvidencePlannerCatalogRow] = []
    for pack_name in sorted(source_packs.SOURCE_PACKS):
        plan = plan_evidence(
            EvidencePlannerRequest(
                opportunity_id=f"readiness:{pack_name}",
                symbol="ASSET",
                coin_id="asset",
                event_name="candidate catalyst",
                external_asset="candidate catalyst",
                score=60.0,
                opportunity_level="validated_digest",
                source_pack=pack_name,
            )
        )
        queries = tuple(dict.fromkeys((*plan.query_plan, *plan.denial_searches)))
        hints = tuple(str(query.provider_hint).strip().lower() for query in queries)
        rows.append(
            EvidencePlannerCatalogRow(
                source_pack=pack_name,
                logical_query_count=len(queries),
                provider_hint_counts=dict(sorted(Counter(hints).items())),
                ordered_provider_hints=hints,
            )
        )
    return tuple(rows)


def _persisted_plan_readiness(
    path: Path,
    *,
    provider_by_hint: Mapping[str, EvidenceProviderReadiness],
    max_queries: int,
) -> PersistedEvidencePlanReadiness:
    rows, truncated, error = _read_bounded_jsonl(path)
    source_file = safe_path_label(path.name)
    if error == "missing":
        return PersistedEvidencePlanReadiness(
            status="not_materialized_no_persisted_store",
            scope="latest_persisted_run_in_namespace",
            source_file=source_file,
            latest_run_id=None,
            plan_count=None,
            logical_query_count=None,
            budgeted_logical_query_count_upper_bound=None,
            provider_hint_counts=None,
            budgeted_http_request_upper_bound=None,
            input_truncated=False,
            applies_to_next_cycle="candidate_dependent_unknown",
            note="No persisted candidate plan exists; the next-cycle count is unknown, not zero.",
        )
    if error:
        return PersistedEvidencePlanReadiness(
            status=f"unavailable_{error}",
            scope="latest_persisted_run_in_namespace",
            source_file=source_file,
            latest_run_id=None,
            plan_count=None,
            logical_query_count=None,
            budgeted_logical_query_count_upper_bound=None,
            provider_hint_counts=None,
            budgeted_http_request_upper_bound=None,
            input_truncated=truncated,
            applies_to_next_cycle="unknown",
            note="Persisted plan input could not be safely resolved.",
        )
    if not rows:
        return PersistedEvidencePlanReadiness(
            status="not_materialized_empty_store",
            scope="latest_persisted_run_in_namespace",
            source_file=source_file,
            latest_run_id=None,
            plan_count=None,
            logical_query_count=None,
            budgeted_logical_query_count_upper_bound=None,
            provider_hint_counts=None,
            budgeted_http_request_upper_bound=None,
            input_truncated=truncated,
            applies_to_next_cycle="candidate_dependent_unknown",
            note="The persisted store has no current rows; the next-cycle count is unknown, not zero.",
        )
    latest_run = str(rows[-1].get("run_id") or "").strip() or None
    current_rows = [
        row
        for row in rows
        if (str(row.get("run_id") or "").strip() or None) == latest_run
    ]
    if truncated and current_rows and current_rows[0] is rows[0]:
        return PersistedEvidencePlanReadiness(
            status="unavailable_current_run_truncated",
            scope="latest_persisted_run_in_namespace",
            source_file=source_file,
            latest_run_id=latest_run,
            plan_count=None,
            logical_query_count=None,
            budgeted_logical_query_count_upper_bound=None,
            provider_hint_counts=None,
            budgeted_http_request_upper_bound=None,
            input_truncated=True,
            applies_to_next_cycle="unknown",
            note="The bounded read may start inside the current run, so exact counts are unavailable.",
        )
    plans: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in current_rows:
        plan = _plan_from_row(row)
        if plan is None:
            continue
        identity = str(plan.get("evidence_plan_id") or "").strip() or json.dumps(
            plan, sort_keys=True, default=str
        )
        if identity in seen:
            continue
        seen.add(identity)
        plans.append(plan)
    if not plans:
        return PersistedEvidencePlanReadiness(
            status="not_materialized_for_latest_run",
            scope="latest_persisted_run_in_namespace",
            source_file=source_file,
            latest_run_id=latest_run,
            plan_count=None,
            logical_query_count=None,
            budgeted_logical_query_count_upper_bound=None,
            provider_hint_counts=None,
            budgeted_http_request_upper_bound=None,
            input_truncated=truncated,
            applies_to_next_cycle="candidate_dependent_unknown",
            note="Latest persisted rows contain no materialized acquisition plan; count is unknown, not zero.",
        )
    ordered_hints: list[str] = []
    for plan in plans:
        ordered_hints.extend(_provider_hints_from_plan(plan))
    count = len(ordered_hints)
    budgeted_hints = ordered_hints[: max(0, max_queries)]
    http_upper = sum(
        provider_by_hint.get(hint).http_request_fanout_max_per_logical_query
        if provider_by_hint.get(hint) is not None
        else 0
        for hint in budgeted_hints
    )
    return PersistedEvidencePlanReadiness(
        status="exact_empty_latest_persisted_run" if count == 0 else "exact_latest_persisted_run",
        scope="latest_persisted_run_in_namespace",
        source_file=source_file,
        latest_run_id=latest_run,
        plan_count=len(plans),
        logical_query_count=count,
        budgeted_logical_query_count_upper_bound=len(budgeted_hints),
        provider_hint_counts=dict(sorted(Counter(ordered_hints).items())),
        budgeted_http_request_upper_bound=http_upper,
        input_truncated=truncated,
        applies_to_next_cycle="candidate_selection_and_replanning_may_change",
        note="Counts are exact for the latest persisted run snapshot, not a promise about a future cycle.",
    )


def _plan_from_row(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = row.get("evidence_acquisition_plan")
    if isinstance(direct, Mapping):
        return direct
    for key in ("latest_score_components", "score_components"):
        components = row.get(key)
        if isinstance(components, Mapping) and isinstance(
            components.get("evidence_acquisition_plan"), Mapping
        ):
            return components["evidence_acquisition_plan"]
    return None


def _provider_hints_from_plan(plan: Mapping[str, Any]) -> tuple[str, ...]:
    seen: set[tuple[str, str, str, bool]] = set()
    hints: list[str] = []
    for key in (
        "evidence_query_plan",
        "evidence_official_searches",
        "evidence_denial_searches",
    ):
        rows = plan.get(key)
        if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, Mapping)):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            query = str(row.get("query") or "").strip()
            if not query:
                continue
            identity = (
                query,
                str(row.get("provider_hint") or "fixture").strip().lower(),
                str(row.get("purpose") or "source_pack_search").strip(),
                bool(row.get("must_validate_asset", True)),
            )
            if identity in seen:
                continue
            seen.add(identity)
            hints.append(identity[1])
    return tuple(hints)


def _deterministic_evidence_acquisition_http_upper_bound(
    catalog: Sequence[EvidencePlannerCatalogRow],
    *,
    provider_by_hint: Mapping[str, EvidenceProviderReadiness],
    max_candidates: int,
    max_queries: int,
) -> int:
    """Exact DP upper bound under candidate and logical-query caps."""

    if max_candidates <= 0 or max_queries <= 0:
        return 0
    costs = {
        hint: row.http_request_fanout_max_per_logical_query
        for hint, row in provider_by_hint.items()
    }
    states = {(0, 0): 0}
    best = 0
    for candidate_index in range(max_candidates):
        next_states = dict(states)
        for (_, used), value in states.items():
            for row in catalog:
                remaining = max_queries - used
                if remaining <= 0:
                    best = max(best, value)
                    continue
                prefix = row.ordered_provider_hints[:remaining]
                new_used = used + len(prefix)
                new_value = value + sum(costs.get(hint, 0) for hint in prefix)
                key = (candidate_index + 1, new_used)
                next_states[key] = max(next_states.get(key, -1), new_value)
                best = max(best, new_value)
        states = next_states
    return best


def _read_bounded_jsonl(
    path: Path,
    *,
    max_bytes: int = MAX_PERSISTED_PLAN_BYTES,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return [], False, "missing"
    except OSError:
        return [], False, "unsafe_or_unreadable"
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return [], False, "not_regular_file"
        size = int(info.st_size)
        start = max(0, size - max(1, int(max_bytes)))
        raw = os.pread(fd, size - start, start)
    except OSError:
        return [], False, "read_failed"
    finally:
        os.close(fd)
    truncated = start > 0
    if truncated:
        newline = raw.find(b"\n")
        raw = raw[newline + 1 :] if newline >= 0 else b""
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return [], truncated, "invalid_jsonl"
        if isinstance(row, Mapping):
            rows.append(dict(row))
    return rows, truncated, None


def _read_url_list(path_value: object) -> tuple[str, ...]:
    if path_value in (None, ""):
        return ()
    rows, error = _read_text_lines_no_follow(Path(path_value))
    if error:
        return ()
    return tuple(
        line.strip()
        for line in rows
        if line.strip() and not line.strip().startswith("#")
    )


def _read_text_lines_no_follow(path: Path) -> tuple[list[str], str | None]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError:
        return [], "unsafe_or_unreadable"
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            return [], "invalid_file"
        raw = os.read(fd, info.st_size)
    except OSError:
        return [], "read_failed"
    finally:
        os.close(fd)
    try:
        return raw.decode("utf-8").splitlines(), None
    except UnicodeDecodeError:
        return [], "invalid_utf8"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Event Alpha evidence-cycle readiness; no provider calls or writes."
    )
    parser.add_argument("--profile", default="notify_llm_quality")
    parser.add_argument("--artifact-namespace")
    parser.add_argument("--artifact-base-dir")
    parser.add_argument("--persisted-plan-path")
    parser.add_argument("--provider-health-path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--require-cycle-ready",
        action="store_true",
        help=(
            "guard a subsequent writing cycle: return nonzero unless the exact persisted "
            "plan, selected providers, authorization, health, and cadence are ready"
        ),
    )
    args = parser.parse_args(argv)
    report = build_evidence_cycle_readiness(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        artifact_base_dir=args.artifact_base_dir,
        persisted_plan_path=args.persisted_plan_path,
        provider_health_path=args.provider_health_path,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_evidence_cycle_readiness(report))
    if args.require_cycle_ready and not report.fresh_validation_cycle_permitted:
        return 2
    return 0


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
