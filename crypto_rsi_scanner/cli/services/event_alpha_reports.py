"""Event Alpha Reports.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible through the public API bridge.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Mapping, MutableMapping

from ...event_alpha.artifacts import locks as _artifact_locks
from ...event_alpha.artifacts import operator_state as _operator_state
from ...event_alpha.namespace import status as _namespace_status


_SERVICE_FUNCTION_NAMES = (
    'bind_scanner_globals',
    '_refresh_scanner_globals',
    '_scanner_call',
    'event_alpha_status',
    'event_alpha_daily_brief_report',
    'event_alpha_source_coverage_report',
    'event_alpha_artifact_doctor_report',
    'event_alpha_runs_report',
    'event_alpha_preflight_report',
    'event_alpha_environment_doctor_report',
    'event_alpha_health_guard_report',
    'event_alpha_v1_readiness_report',
)


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module


def _refresh_scanner_globals() -> ModuleType:
    return bind_scanner_globals(globals())


def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from ... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)


def event_alpha_status(profile_name: str | None = None, verbose: bool = False) -> None:
    """Print profile-aware Event Alpha operational status."""
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    try:
        profile = _apply_event_alpha_profile(profile_name)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    lines = [
        "=" * 76,
        "EVENT ALPHA STATUS (research-only; profile-aware)",
        "=" * 76,
        f"profile: {(profile.name if profile else profile_name) or 'default'}",
        f"artifact_namespace: {config.EVENT_ALPHA_ARTIFACT_NAMESPACE or 'legacy/default'}",
        f"run_mode: {config.EVENT_ALPHA_RUN_MODE or 'legacy'}",
        f"artifact_base_dir: {config.EVENT_ALPHA_ARTIFACT_BASE_DIR}",
        _event_alpha_clock_line(clock_status),
        f"send requested by profile: {str(bool(profile and profile.send)).lower()}",
        f"send enabled env: {str(bool(config.EVENT_ALERTS_ENABLED)).lower()}",
        f"LLM relationship: provider={config.EVENT_LLM_PROVIDER} mode={config.EVENT_LLM_MODE} enabled={str(bool(config.EVENT_LLM_ENABLED)).lower()}",
        (
            "LLM extractor: "
            f"provider={config.EVENT_LLM_EXTRACTOR_PROVIDER} mode={config.EVENT_LLM_EXTRACTOR_MODE} "
            f"enabled={str(bool(config.EVENT_LLM_EXTRACTOR_ENABLED)).lower()}"
        ),
        (
            "LLM catalyst frames: "
            f"provider={config.EVENT_LLM_CATALYST_FRAMES_PROVIDER} "
            f"enabled={str(bool(config.EVENT_LLM_CATALYST_FRAMES_ENABLED)).lower()} "
            f"max_rows={config.EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN} "
            f"only_ambiguous={str(bool(config.EVENT_LLM_CATALYST_FRAMES_ONLY_AMBIGUOUS)).lower()}"
        ),
        (
            "LLM budget: "
            f"max_candidates={config.EVENT_LLM_MAX_CANDIDATES_PER_RUN} "
            f"max_extract_events={config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN} "
            f"max_run={config.EVENT_LLM_MAX_CALLS_PER_RUN} max_day={config.EVENT_LLM_MAX_CALLS_PER_DAY} "
            f"parallel={config.EVENT_LLM_MAX_PARALLEL_CALLS} "
            f"max_cost_day={config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY:g} "
            f"timeouts={config.EVENT_LLM_OPENAI_TIMEOUT:g}/{config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT:g}s "
            f"cache_ttl_hours={config.EVENT_LLM_CACHE_TTL_HOURS:g} "
            f"ledger={config.EVENT_LLM_BUDGET_LEDGER_PATH}"
        ),
        f"catalyst providers: {', '.join(config.EVENT_CATALYST_SEARCH_PROVIDERS) or 'none'}",
        (
            "source_enrichment: "
            f"enabled={str(bool(config.EVENT_SOURCE_ENRICHMENT_ENABLED)).lower()} "
            f"max_rows={config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN} "
            f"timeout={config.EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS:g}s "
            f"cache={config.EVENT_SOURCE_ENRICHMENT_CACHE_DIR}"
        ),
        f"watchlist_state_path: {config.EVENT_WATCHLIST_STATE_PATH}",
        (
            "watchlist_monitor: "
            f"enabled={str(bool(config.EVENT_WATCHLIST_MONITOR_ENABLED)).lower()} "
            f"route_updates={str(bool(config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES)).lower()} "
            f"market_source={config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE} "
            f"derivatives_source={config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE} "
            f"supply_source={config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE} "
            f"targeted={str(bool(config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP)).lower()} "
            f"max_assets={config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS} "
            f"enrichment_max_assets={config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS} "
            f"cache_ttl={config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS}s "
            f"market_path={config.EVENT_WATCHLIST_MONITOR_MARKET_PATH or config.EVENT_DISCOVERY_UNIVERSE_PATH or 'cycle'}"
        ),
        f"alert_store_path: {config.EVENT_ALPHA_ALERT_STORE_PATH}",
        f"run_ledger_path: {config.EVENT_ALPHA_RUN_LEDGER_PATH}",
        f"impact_hypothesis_store_path: {config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH}",
        (
            "health_guard: "
            f"max_run_age_hours={config.EVENT_ALPHA_MAX_RUN_AGE_HOURS:g} "
            f"max_success_age_hours={config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS:g} "
            f"require_profile={config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or 'none'}"
        ),
        f"missed_path: {config.EVENT_ALPHA_MISSED_PATH}",
        (
            "calibration_priors: "
            "runtime_apply_allowed=false "
            f"compatibility_flag={str(bool(config.EVENT_ALPHA_APPLY_PRIORS)).lower()} "
            f"path={config.EVENT_ALPHA_PRIORS_PATH} "
            f"bounds={config.EVENT_ALPHA_PRIORS_MIN_MULTIPLIER:g}-{config.EVENT_ALPHA_PRIORS_MAX_MULTIPLIER:g}"
        ),
        (
            "provider_health: "
            f"path={config.EVENT_PROVIDER_HEALTH_PATH} "
            f"max_failures={config.EVENT_PROVIDER_MAX_CONSECUTIVE_FAILURES} "
            f"backoff_minutes={config.EVENT_PROVIDER_BACKOFF_MINUTES:g} "
            f"fail_fast_dns={str(bool(config.EVENT_PROVIDER_FAIL_FAST_ON_DNS)).lower()}"
        ),
        f"daily_brief_path: {config.EVENT_ALPHA_DAILY_BRIEF_PATH}",
    ]
    if profile:
        lines.append("artifact policy:")
        for key, value in event_alpha_profiles.artifact_policy(profile).items():
            lines.append(f"  {key}={value}")
    lines.extend([
        "",
        event_provider_status.format_event_discovery_provider_status(provider_report),
        "",
        event_provider_health.format_provider_health_report(
            event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
        ),
    ])
    print("\n".join(lines))


def event_alpha_daily_brief_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Write and print the daily Event Alpha operating brief."""
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name
    if not selected_profile:
        selected_profile = _latest_event_alpha_profile_from_runs()
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    with _artifact_locks.artifact_mutation_guard(
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        command="daily-brief-report",
    ) as mutation_lock:
        if not mutation_lock.owned:
            print(_event_alpha_context_block(context))
            print(f"daily_brief_report_skipped: {mutation_lock.status.message}")
            return
        _event_alpha_daily_brief_report_locked(
            context,
            selected_profile=selected_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_api_artifacts=include_api_artifacts,
        )


def _event_alpha_daily_brief_report_locked(
    context: Any,
    *,
    selected_profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> None:
    profile = event_alpha_profiles.get_profile(selected_profile) if selected_profile else None
    artifact_namespace = artifact_namespace or context.artifact_namespace
    evaluation_now = _event_research_now()
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=25)
    operator_run = _ensure_daily_operator_state(context, runs.rows)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        context.alert_store_path,
        latest_only=True,
        core_opportunity_store_path=context.core_opportunity_store_path,
    )
    event_core_opportunity_store.normalize_core_opportunity_store(
        context.core_opportunity_store_path,
        latest_run=True,
        now=evaluation_now,
    )
    event_alpha_notification_runs.normalize_notification_runs_after_cryptopanic_success(
        context.notification_runs_path,
        request_ledger_path=context.provider_health_path.with_name("cryptopanic_request_ledger.jsonl"),
    )
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=100,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    missed_rows = event_alpha_missed.load_missed_rows(context.missed_path)
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    router_result = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(
        watchlist,
        now=evaluation_now,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    )
    card_write = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=watchlist.entries,
        alert_rows=[*alerts.rows, *hypotheses.rows, *core_store.rows],
        route_decisions=router_result.decisions,
        monitor_rows=monitor_result.rows,
        selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
        limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
        now=evaluation_now,
        lineage_context=_event_alpha_card_lineage_context(
            run_id=str((operator_run or {}).get("run_id") or "") or None,
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=artifact_namespace,
        ),
    )
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        core_opportunity_rows=core_store.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        notification_runs=event_alpha_notification_runs.load_notification_runs(context.notification_runs_path).rows,
        hypothesis_rows=hypotheses.rows,
        incident_rows=event_incident_store.load_incidents(context.incident_store_path, limit=100, include_api=True).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        market_anomaly_rows=event_market_anomaly_scanner.load_market_anomaly_rows(context.namespace_dir),
        official_exchange_candidate_rows=event_official_exchange.load_official_listing_candidates(context.namespace_dir),
        scheduled_catalyst_rows=event_scheduled_catalysts.load_scheduled_catalysts(context.namespace_dir),
        unlock_candidate_rows=event_scheduled_catalysts.load_unlock_candidates(context.namespace_dir),
        derivatives_state_rows=event_derivatives_crowding.load_derivatives_state(context.namespace_dir),
        fade_review_candidate_rows=event_derivatives_crowding.load_fade_review_candidates(context.namespace_dir),
        watchlist_entries=watchlist.entries,
        router_result=router_result,
        provider_health_rows=event_provider_health.load_provider_health(
            context.provider_health_path
        ),
        card_paths=card_write.card_paths,
        requested_profile=profile.name if profile else profile_name,
        artifact_namespace=artifact_namespace,
        run_mode=context.run_mode,
        run_ledger_path=context.run_ledger_path,
        alert_store_path=context.alert_store_path,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        generated_at=evaluation_now,
    )
    result = event_alpha_daily_brief.write_daily_brief(
        context.daily_brief_path,
        markdown=markdown,
        card_paths=card_write.card_paths,
    )
    _record_daily_brief_operator_state(context, result, card_write, run_row=operator_run)
    report = _event_alpha_context_block(context) + "\n" + event_alpha_daily_brief.format_daily_brief_result(result)
    if profile:
        report += f"\nprofile_applied: {profile.name}"
    print(report)


def _record_daily_brief_operator_state(
    context: Any,
    brief_result: Any,
    card_write: Any,
    *,
    run_row: Mapping[str, Any] | None,
) -> None:
    if run_row is None:
        return
    loaded = _operator_state.load_operator_state(context.namespace_dir)
    state = dict(loaded.state or {}) if loaded.valid else {}
    if not _operator_state.state_matches_run(
        state,
        run_row,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    ):
        return
    run_id = str(run_row.get("run_id") or "")
    try:
        _operator_state.record_artifact(
            context.namespace_dir,
            run_id=run_id,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            name="research_cards",
            path=card_write.out_dir,
            count=int(card_write.cards_written),
        )
        _operator_state.record_artifact(
            context.namespace_dir,
            run_id=run_id,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            name="daily_brief",
            path=brief_result.path,
        )
        _namespace_status.refresh_namespace_status(
            context.namespace_dir,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=str(run_row.get("run_mode") or context.run_mode),
        )
    except (OSError, ValueError):
        return


def _ensure_daily_operator_state(context: Any, run_rows: Any) -> dict[str, Any] | None:
    latest = _operator_state.latest_matching_run(
        run_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    )
    if latest is None:
        return None
    try:
        state = _operator_state.begin_run_if_newer(
            context.namespace_dir,
            latest,
            run_ledger_path=context.run_ledger_path,
        )
        if not _operator_state.state_matches_run(
            state,
            latest,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
        ):
            return None
        _namespace_status.refresh_namespace_status(
            context.namespace_dir,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=str(latest.get("run_mode") or context.run_mode),
        )
    except (OSError, ValueError):
        return None
    return latest


def event_alpha_source_coverage_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_source_coverage_report", *args, **kwargs)


def event_alpha_artifact_doctor_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_artifact_doctor_report", *args, **kwargs)


def event_alpha_runs_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_runs_report", *args, **kwargs)


def event_alpha_preflight_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_preflight_report", *args, **kwargs)


def event_alpha_environment_doctor_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_environment_doctor_report", *args, **kwargs)


def event_alpha_health_guard_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_health_guard_report", *args, **kwargs)


def event_alpha_v1_readiness_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_v1_readiness_report", *args, **kwargs)


__all__ = tuple(
    name
    for name in _SERVICE_FUNCTION_NAMES
    if name != 'bind_scanner_globals' and not name.startswith('_')
)
