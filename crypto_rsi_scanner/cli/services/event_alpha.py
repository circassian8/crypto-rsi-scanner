"""Extracted Event Alpha CLI service bodies.

These functions are behavior-preserving moves from ``scanner.py``. They
bind scanner globals at runtime so existing helper/config lookups remain
compatible while the scanner module stays a thin entrypoint wrapper.
"""

from __future__ import annotations

from types import ModuleType
from typing import MutableMapping


_SERVICE_FUNCTION_NAMES = {
    "_cryptopanic_stats_for_pipeline_result",
    "event_alpha_cycle",
    "_event_alpha_notify_cycle_body",
    "event_alpha_notify_preview",
    "event_alpha_notify_preview_from_artifacts",
    "event_alpha_notify_go_no_go",
    "event_alpha_export_notification_pack",
    "event_alpha_status",
    "event_alpha_burn_in_readiness_report",
    "event_alpha_notify_fixture_smoke",
    "event_alpha_export_burn_in_pack",
    "event_alpha_daily_brief_report",
    "event_alpha_integrated_radar_cycle_report",
    "event_alpha_market_anomaly_scan_report",
    "event_alpha_official_exchange_report",
    "event_alpha_scheduled_catalyst_report",
    "event_alpha_derivatives_report",
    "event_alpha_replay_report",
    "_router_config_from_profile",
    "_event_catalyst_search_provider",
    "_event_evidence_acquisition_providers_from_runtime",
    "_send_event_alpha_routed_digest",
    "_write_event_fade_review_bundle",
    "_event_fade_review_bundle_manifest",
    "_event_fade_review_bundle_readme",
    "_event_fade_review_guide",
}


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module

def _cryptopanic_stats_for_pipeline_result(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    provider_health_path: str | Path,
) -> dict[str, Any]:
    """Summarize CryptoPanic usage without exposing the API token."""
    bind_scanner_globals(globals())
    acquisition = pipeline_result.evidence_acquisition_result
    accepted_keys: set[str] = set()
    rejected_keys: set[str] = set()
    results_seen = 0
    attempted = False
    provider_failures = 0
    if acquisition is not None:
        for result in acquisition.results:
            providers = {str(item).casefold() for item in getattr(result, "providers_used", ()) or ()}
            if "cryptopanic" in providers:
                attempted = True
            for query in getattr(result, "query_results", ()) or ():
                query_values = (
                    getattr(query, "provider_hint", ""),
                    getattr(query, "provider_used", ""),
                    getattr(query, "query", ""),
                )
                query_is_cryptopanic = any("cryptopanic" in str(value).casefold() for value in query_values)
                if query_is_cryptopanic:
                    attempted = True
                    results_seen += int(getattr(query, "results_seen", 0) or 0)
                    provider_failures += len(tuple(getattr(query, "provider_failures", ()) or ()))
                for item in getattr(query, "accepted_evidence", ()) or ():
                    if _mapping_mentions_cryptopanic(item):
                        accepted_keys.add(_cryptopanic_evidence_key(item))
                for item in getattr(query, "rejected_evidence", ()) or ():
                    if _mapping_mentions_cryptopanic(item):
                        rejected_keys.add(_cryptopanic_evidence_key(item))
            for item in getattr(result, "accepted_evidence", ()) or ():
                if _mapping_mentions_cryptopanic(item):
                    accepted_keys.add(_cryptopanic_evidence_key(item))
            for item in getattr(result, "rejected_evidence", ()) or ():
                if _mapping_mentions_cryptopanic(item):
                    rejected_keys.add(_cryptopanic_evidence_key(item))
            provider_failures += sum(
                1
                for item in getattr(result, "provider_failures", ()) or ()
                if "cryptopanic" in str(item).casefold()
            )
    rows = event_provider_health.load_provider_health(provider_health_path)
    statuses = [
        event_provider_health.provider_health_status(row)
        for key, row in rows.items()
        if "cryptopanic" in " ".join(
            str(value or "").casefold()
            for value in (
                key,
                row.get("provider"),
                row.get("provider_key"),
                row.get("provider_service"),
            )
        )
    ]
    raw_provider_status = "not_observed"
    if "backoff" in statuses:
        raw_provider_status = "backoff"
    elif "degraded" in statuses:
        raw_provider_status = "degraded"
    elif statuses:
        raw_provider_status = "healthy"
    usage = cryptopanic_provider.cryptopanic_usage_summary(
        _cryptopanic_request_ledger_path(),
        now=datetime.now(timezone.utc),
        weekly_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        daily_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
    )
    ledger_rows = _recent_cryptopanic_request_rows(_cryptopanic_request_ledger_path(), since=usage.last_request_at)
    normalized_keys = [
        str(row.get("normalized_request_key") or "").strip()
        for row in ledger_rows
        if str(row.get("normalized_request_key") or "").strip()
    ]
    duplicate_requests = max(0, len(normalized_keys) - len(set(normalized_keys)))
    invalid_currency_requests = sum(1 for row in ledger_rows if _cryptopanic_row_has_invalid_currencies(row))
    accepted = len(accepted_keys)
    rejected = len(rejected_keys)
    requests_used = int(usage.today_requests or 0)
    successful_requests = sum(
        1
        for row in ledger_rows
        if not str(row.get("error_class") or "").strip()
        and _status_code_ok(row.get("status_code"))
    )
    failed_requests = sum(
        1
        for row in ledger_rows
        if str(row.get("error_class") or "").strip()
        or _status_code_failed(row.get("status_code"))
    )
    provider_status = raw_provider_status
    stale_backoff_reconciled = False
    if successful_requests:
        provider_status = "degraded" if failed_requests else "healthy"
        stale_backoff_reconciled = raw_provider_status == "backoff"
    if requests_used > 0:
        attempted = True
        if provider_status == "not_observed" and usage.last_status_code:
            provider_status = "healthy" if int(usage.last_status_code) < 400 else "degraded"
    configured = bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN)
    skip_reason = None
    if not configured:
        skip_reason = "missing_api_key"
    elif not config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE and not config.EVENT_DISCOVERY_CRYPTOPANIC_PATH:
        skip_reason = "profile_disabled"
    elif not attempted:
        if provider_status == "backoff":
            skip_reason = "provider_backoff"
        elif provider_failures:
            skip_reason = "provider_error"
        elif acquisition is None or not acquisition.results:
            skip_reason = "no_eligible_candidates"
        else:
            skip_reason = "query_planner_skipped"
    return {
        "cryptopanic_configured": configured,
        "cryptopanic_attempted": attempted,
        "cryptopanic_requests_used": requests_used,
        "cryptopanic_request_cache_hits": 0,
        "cryptopanic_request_cache_misses": max(0, len(normalized_keys)),
        "cryptopanic_requests_deduped": duplicate_requests,
        "cryptopanic_invalid_currency_requests_skipped": invalid_currency_requests,
        "cryptopanic_results": max(results_seen, accepted + rejected),
        "cryptopanic_accepted_evidence": accepted,
        "cryptopanic_rejected_evidence": rejected,
        "cryptopanic_raw_provider_status": raw_provider_status,
        "cryptopanic_provider_status": provider_status,
        "cryptopanic_effective_provider_status": provider_status,
        "cryptopanic_successful_requests": successful_requests,
        "cryptopanic_failed_requests": failed_requests,
        "cryptopanic_stale_backoff_reconciled_after_success": stale_backoff_reconciled,
        "cryptopanic_skip_reason": skip_reason,
    }


def event_alpha_cycle(
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
) -> None:
    """Run one unified research-only Event Alpha cycle."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    profile = _apply_event_alpha_profile(profile_name)
    if profile is not None:
        with_llm = with_llm or profile.with_llm
        send = send or profile.send
    profile_for_run = (profile.name if profile else profile_name) or "default"
    run_mode = config.EVENT_ALPHA_RUN_MODE or "legacy"
    artifact_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha cycle inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    clock_status = _event_clock_status(event_now)
    now = _event_research_now(event_now)
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, profile_for_run)
    extraction_provider = None
    extraction_cfg = None
    catalyst_frame_provider = None
    catalyst_frame_cfg = None
    relationship_provider = None
    relationship_cfg = None
    if with_llm:
        extraction_cfg = _event_llm_extractor_config_from_runtime()
        extraction_provider = _event_llm_extraction_provider(extraction_cfg)
        catalyst_frame_cfg = _event_llm_catalyst_frame_config_from_runtime()
        catalyst_frame_provider = _event_llm_catalyst_frame_provider(catalyst_frame_cfg)
        relationship_cfg = _event_llm_config_from_runtime()
        relationship_provider = _event_llm_provider(relationship_cfg)
    catalyst_search_cfg = _event_catalyst_search_config_from_runtime()
    catalyst_search_provider = _event_catalyst_search_provider(catalyst_search_cfg)
    hypothesis_search_cfg = _event_impact_hypothesis_search_config_from_runtime()
    evidence_acquisition_cfg = _event_evidence_acquisition_config_from_runtime()
    evidence_acquisition_providers = _event_evidence_acquisition_providers_from_runtime(evidence_acquisition_cfg)
    alert_cfg = _event_alert_config_from_runtime()
    pipeline_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
            now=observed,
            raw_event_transform=raw_event_transform,
        ),
        alert_cfg=alert_cfg,
        now=now,
        with_llm=with_llm,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
        catalyst_frame_provider=catalyst_frame_provider,
        catalyst_frame_cfg=catalyst_frame_cfg,
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        hypothesis_search_provider=catalyst_search_provider,
        hypothesis_search_cfg=hypothesis_search_cfg,
        source_enrichment_cfg=_event_source_enrichment_config_from_runtime(),
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
        watchlist_cfg=_event_watchlist_config_from_runtime(),
        router_cfg=_event_alpha_router_config_from_runtime(),
        priors_cfg=_event_alpha_priors_config_from_runtime(),
        refresh_watchlist=True,
        route=True,
        watchlist_monitor_enabled=config.EVENT_WATCHLIST_MONITOR_ENABLED,
        watchlist_monitor_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
        watchlist_monitor_market_source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        watchlist_monitor_market_provider=_event_watchlist_market_provider_from_runtime(),
        watchlist_monitor_targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        watchlist_monitor_max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        watchlist_monitor_market_cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        watchlist_monitor_derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        watchlist_monitor_supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        watchlist_monitor_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        watchlist_monitor_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        watchlist_monitor_enrichment_max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
        watchlist_monitor_route_updates=config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES,
        near_miss_cfg=_event_near_miss_config_from_runtime(),
        near_miss_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
        near_miss_market_provider=_event_watchlist_market_provider_from_runtime()
        if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
        else None,
        near_miss_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        near_miss_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        evidence_acquisition_cfg=evidence_acquisition_cfg,
        evidence_acquisition_provider=evidence_acquisition_providers.get("default"),
        evidence_acquisition_providers_by_hint=evidence_acquisition_providers,
        evidence_acquisition_context={
            "run_id": run_id,
            "profile": profile_for_run,
            "run_mode": run_mode,
            "artifact_namespace": artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE,
        },
        send=send,
        send_callback=lambda decisions: _send_event_alpha_routed_digest(
            decisions,
            alert_cfg,
            now=now,
            profile=profile_for_run,
            clock_status=clock_status,
        ),
    )
    pipeline_result, hypothesis_store_result = _write_event_impact_hypotheses_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, incident_store_result = _write_event_incidents_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, core_store_result = _write_event_core_opportunities_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=(),
    )
    latest_core_rows = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
        run_id=run_id,
    ).rows
    event_evidence_acquisition.reconcile_acquisition_core_ids(
        config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
        latest_core_rows,
        run_id=run_id,
        profile=profile_for_run,
        artifact_namespace=artifact_namespace,
    )
    if config.EVENT_RESEARCH_CARDS_AUTO_WRITE and pipeline_result.router_result is not None:
        watch_cfg = _event_watchlist_config_from_runtime()
        watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
        card_write = event_research_cards.write_research_cards(
            config.EVENT_RESEARCH_CARDS_DIR,
            watchlist_entries=watchlist.entries,
            alert_rows=latest_core_rows,
            route_decisions=pipeline_result.router_result.decisions,
            selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
            limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
            now=now,
            lineage_context=_event_alpha_card_lineage_context(
                run_id=run_id,
                profile=profile_for_run,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
            ),
        )
        pipeline_result = replace(pipeline_result, research_card_paths=card_write.card_paths)
        event_core_opportunity_store.update_core_opportunity_card_links(
            _event_core_opportunity_store_config_from_runtime().path,
            card_write.card_paths,
            run_id=run_id,
        )
        latest_core_rows = event_core_opportunity_store.load_core_opportunities(
            _event_core_opportunity_store_config_from_runtime().path,
            latest_run=True,
            run_id=run_id,
        ).rows
        print(event_research_cards.format_card_write_result(card_write))
        print("")
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipeline_result))
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    if run_mode in event_alpha_artifacts.NON_OPERATIONAL_RUN_MODES:
        store_result = event_alpha_alert_store.blocked_alert_snapshot_write(
            cfg=store_cfg,
            now=now,
            reason="test_or_fixture_run",
        )
    else:
        store_result = event_alpha_alert_store.write_alert_snapshots(
            pipeline_result.alerts,
            cfg=store_cfg,
            now=now,
            router_result=pipeline_result.router_result,
            run_id=run_id,
            profile=profile_for_run,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            research_card_paths=pipeline_result.research_card_paths,
            core_opportunity_rows=latest_core_rows,
        )
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        run_ledger_path=str(_event_alpha_run_ledger_config_from_runtime().path),
        alert_store_path=str(store_cfg.path),
        watchlist_state_path=str(config.EVENT_WATCHLIST_STATE_PATH),
        research_cards_dir=str(config.EVENT_RESEARCH_CARDS_DIR),
        snapshot_write_attempted=store_result.attempted,
        snapshot_write_success=store_result.success,
        snapshot_rows_written=store_result.rows_written,
        snapshot_write_block_reason=store_result.block_reason,
    )
    print("")
    print(event_alpha_alert_store.format_alert_store_write_result(store_result))
    print(
        "Event impact hypotheses updated: "
        f"{hypothesis_store_result.path} rows={hypothesis_store_result.rows_written} "
        f"success={str(hypothesis_store_result.success).lower()}"
        + (f" block={hypothesis_store_result.block_reason}" if hypothesis_store_result.block_reason else "")
    )
    print(
        "Event incidents updated: "
        f"{incident_store_result.path} rows={incident_store_result.rows_written} "
        f"success={str(incident_store_result.success).lower()}"
        + (f" block={incident_store_result.block_reason}" if incident_store_result.block_reason else "")
    )
    print(event_core_opportunity_store.format_core_opportunity_store_write_result(core_store_result))
    pipeline_result = replace(
        pipeline_result,
        **_cryptopanic_stats_for_pipeline_result(
            pipeline_result,
            provider_health_path=_event_provider_health_config_from_runtime().path,
        ),
    )
    run_row = event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=_event_alpha_run_ledger_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        with_llm=with_llm,
        send_requested=send,
        notification_burn_in=bool(profile and profile.notification_burn_in),
        success=True,
    )
    print("")
    print(
        "Event Alpha run ledger updated: "
        f"{config.EVENT_ALPHA_RUN_LEDGER_PATH} run_id={run_row.get('run_id')}"
    )


def _event_alpha_notify_cycle_body(
    *,
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
    ignore_provider_backoff: bool = False,
    lock_holder: dict[str, object],
) -> None:
    """Run a day-1 Event Alpha notification burn-in cycle."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    profile = _apply_event_alpha_profile(selected_profile)
    previous_ignore_backoff = bool(config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF)
    ignore_backoff_for_run = bool(ignore_provider_backoff or config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF)
    config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF = ignore_backoff_for_run
    try:
        with_llm = with_llm or profile.with_llm
        profile_for_run = profile.name
        run_mode = config.EVENT_ALPHA_RUN_MODE or "notification_burn_in"
        artifact_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None
        if not _event_alpha_inputs_configured():
            print(
                "No Event Alpha notification inputs ready. Configure notify_no_key/notify_llm providers "
                "or run --event-alpha-notify-preview for readiness details."
            )
            return
        clock_status = _event_clock_status(event_now)
        now = _event_research_now(event_now)
        started_at = datetime.now(timezone.utc)
        run_id = event_alpha_run_ledger.run_id_for(started_at, profile_for_run)
        lock_context = _event_alpha_notify_context_from_runtime(profile_for_run)
        delivery_cfg = _event_alpha_notification_delivery_config_from_runtime(lock_context)
        pause_state = _event_alpha_notification_pause_state(lock_context)
        run_lock = event_alpha_run_lock.acquire_run_lock(
            lock_context,
            cfg=_event_alpha_run_lock_config_from_runtime(),
            run_id=run_id,
            profile=profile_for_run,
            namespace=artifact_namespace or lock_context.artifact_namespace,
            command="event-alpha-notify-cycle",
            now=started_at,
        )
        lock_holder["lock"] = run_lock
        if run_lock.skipped_due_to_active_lock:
            print(f"Event Alpha notify cycle skipped: {run_lock.status.message}.")
            _record_skipped_notification_run(
                profile_for_run,
                run_id=run_id,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
                started_at=started_at,
            )
            return
        if run_lock.stale_recovered:
            print(f"Warning: {event_alpha_run_lock.STALE_LOCK_RECOVERED_WARNING} ({run_lock.status.message}).")
        if pause_state.paused:
            print(f"Event Alpha notifications paused: {pause_state.reason} ({pause_state.source}).")
        budget = _notification_runtime_budget(started_at)
        pre_stage_warnings: list[str] = list(_event_alpha_notify_clock_warnings(clock_status))
        if ignore_backoff_for_run:
            pre_stage_warnings.append("provider_backoff_ignored_for_run")
        extraction_provider = None
        extraction_cfg = None
        catalyst_frame_provider = None
        catalyst_frame_cfg = None
        relationship_provider = None
        relationship_cfg = None
        llm_budget_warning = budget.warning_if_low("llm")
        effective_with_llm = with_llm
        if with_llm and llm_budget_warning:
            effective_with_llm = False
            pre_stage_warnings.append(llm_budget_warning)
        if effective_with_llm:
            llm_deadline_at = (
                started_at + timedelta(seconds=budget.max_seconds)
                if budget.max_seconds > 0
                else None
            )
            extraction_cfg = _event_llm_extractor_config_from_runtime()
            if llm_deadline_at is not None:
                extraction_cfg = replace(extraction_cfg, deadline_at=llm_deadline_at)
            extraction_provider = _event_llm_extraction_provider(extraction_cfg)
            catalyst_frame_cfg = _event_llm_catalyst_frame_config_from_runtime()
            if llm_deadline_at is not None:
                catalyst_frame_cfg = replace(catalyst_frame_cfg, deadline_at=llm_deadline_at)
            catalyst_frame_provider = _event_llm_catalyst_frame_provider(catalyst_frame_cfg)
            relationship_cfg = _event_llm_config_from_runtime()
            if llm_deadline_at is not None:
                relationship_cfg = replace(relationship_cfg, deadline_at=llm_deadline_at)
            relationship_provider = _event_llm_provider(relationship_cfg)
        alert_cfg = _event_alert_config_from_runtime()
        discovery_budget_warning = budget.warning_if_low("discovery")
        if discovery_budget_warning:
            pipeline_result = _empty_notification_pipeline_result(
                now=now,
                warning=discovery_budget_warning,
            )
        else:
            catalyst_budget_warning = budget.warning_if_low("catalyst_search")
            if catalyst_budget_warning:
                pre_stage_warnings.append(catalyst_budget_warning)
            catalyst_search_cfg = _event_catalyst_search_config_from_runtime(
                enabled_override=False if catalyst_budget_warning else None
            )
            catalyst_search_provider = None if catalyst_budget_warning else _event_catalyst_search_provider(catalyst_search_cfg)
            hypothesis_search_cfg = _event_impact_hypothesis_search_config_from_runtime(
                enabled_override=False if catalyst_budget_warning else None
            )
            evidence_acquisition_cfg = _event_evidence_acquisition_config_from_runtime()
            evidence_acquisition_providers = (
                {}
                if catalyst_budget_warning
                else _event_evidence_acquisition_providers_from_runtime(evidence_acquisition_cfg)
            )
            watchlist_budget_warning = budget.warning_if_low("watchlist_refresh")
            if watchlist_budget_warning:
                pre_stage_warnings.append(watchlist_budget_warning)
            try:
                pipeline_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
                    load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
                        now=observed,
                        raw_event_transform=raw_event_transform,
                    ),
                    alert_cfg=alert_cfg,
                    now=now,
                    with_llm=effective_with_llm,
                    extraction_provider=extraction_provider,
                    extraction_cfg=extraction_cfg,
                    catalyst_frame_provider=catalyst_frame_provider,
                    catalyst_frame_cfg=catalyst_frame_cfg,
                    catalyst_search_provider=catalyst_search_provider,
                    catalyst_search_cfg=catalyst_search_cfg,
                    hypothesis_search_provider=catalyst_search_provider,
                    hypothesis_search_cfg=hypothesis_search_cfg,
                    source_enrichment_cfg=_event_source_enrichment_config_from_runtime(),
                    relationship_provider=relationship_provider,
                    relationship_cfg=relationship_cfg,
                    watchlist_cfg=_event_watchlist_config_from_runtime(),
                    router_cfg=_event_alpha_router_config_from_runtime(),
                    priors_cfg=_event_alpha_priors_config_from_runtime(),
                    refresh_watchlist=not bool(watchlist_budget_warning),
                    route=True,
                    watchlist_monitor_enabled=(
                        config.EVENT_WATCHLIST_MONITOR_ENABLED and not bool(watchlist_budget_warning)
                    ),
                    watchlist_monitor_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
                    watchlist_monitor_market_source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
                    watchlist_monitor_market_provider=_event_watchlist_market_provider_from_runtime(),
                    watchlist_monitor_targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
                    watchlist_monitor_max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
                    watchlist_monitor_market_cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
                    watchlist_monitor_derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
                    watchlist_monitor_supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
                    watchlist_monitor_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
                    watchlist_monitor_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
                    watchlist_monitor_enrichment_max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
                    watchlist_monitor_route_updates=config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES,
                    near_miss_cfg=_event_near_miss_config_from_runtime(),
                    near_miss_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
                    near_miss_market_provider=_event_watchlist_market_provider_from_runtime()
                    if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
                    else None,
                    near_miss_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
                    near_miss_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
                    evidence_acquisition_cfg=evidence_acquisition_cfg,
                    evidence_acquisition_provider=evidence_acquisition_providers.get("default"),
                    evidence_acquisition_providers_by_hint=evidence_acquisition_providers,
                    evidence_acquisition_context={
                        "run_id": run_id,
                        "profile": profile_for_run,
                        "run_mode": run_mode,
                        "artifact_namespace": artifact_namespace or lock_context.artifact_namespace,
                    },
                    send=False,
                )
            except Exception as exc:  # noqa: BLE001 - notification burn-in must fail soft on provider/runtime errors
                if not config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS:
                    raise
                warning = f"notification_cycle_failed_soft: {type(exc).__name__}"
                log.warning("Event Alpha notification cycle failed soft: %s", exc)
                pipeline_result = _empty_notification_pipeline_result(now=now, warning=warning, cycle_completed=False)
            if _notification_runtime_budget_exhausted(started_at):
                pipeline_result = replace(
                    pipeline_result,
                    warnings=tuple(dict.fromkeys((
                        *pipeline_result.warnings,
                        "notification_runtime_budget_exhausted_after_pipeline",
                    ))),
                    partial_results=True,
                )
            if pre_stage_warnings:
                pipeline_result = replace(
                    pipeline_result,
                    warnings=tuple(dict.fromkeys((*pre_stage_warnings, *pipeline_result.warnings))),
                    partial_results=True,
                )
    finally:
        config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF = previous_ignore_backoff
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        partial_results=(
            pipeline_result.partial_results
            or _notification_warnings_indicate_partial(pipeline_result.warnings)
        ),
    )
    pipeline_result, hypothesis_store_result = _write_event_impact_hypotheses_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, incident_store_result = _write_event_incidents_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, core_store_result = _write_event_core_opportunities_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=(),
    )
    latest_core_rows = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
        run_id=run_id,
    ).rows
    event_evidence_acquisition.reconcile_acquisition_core_ids(
        config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
        latest_core_rows,
        run_id=run_id,
        profile=profile_for_run,
        artifact_namespace=artifact_namespace,
    )
    card_write = None
    if config.EVENT_RESEARCH_CARDS_AUTO_WRITE and pipeline_result.router_result is not None:
        watch_cfg = _event_watchlist_config_from_runtime()
        watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
        card_write = event_research_cards.write_research_cards(
            config.EVENT_RESEARCH_CARDS_DIR,
            watchlist_entries=watchlist.entries,
            alert_rows=latest_core_rows,
            route_decisions=pipeline_result.router_result.decisions,
            selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
            limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
            now=now,
            lineage_context=_event_alpha_card_lineage_context(
                run_id=run_id,
                profile=profile_for_run,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
            ),
        )
        pipeline_result = replace(pipeline_result, research_card_paths=card_write.card_paths)
        event_core_opportunity_store.update_core_opportunity_card_links(
            _event_core_opportunity_store_config_from_runtime().path,
            card_write.card_paths,
            run_id=run_id,
        )
        latest_core_rows = event_core_opportunity_store.load_core_opportunities(
            _event_core_opportunity_store_config_from_runtime().path,
            latest_run=True,
            run_id=run_id,
        ).rows
        print(event_research_cards.format_card_write_result(card_write))
        print("")
    storage = Storage(config.DB_PATH)
    try:
        notification_plan = event_alpha_notifications.build_notification_plan(
            pipeline_result.router_result.decisions if pipeline_result.router_result else [],
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile_for_run),
            now=now,
            include_health_heartbeat=True,
            core_opportunity_rows=latest_core_rows,
        )
    finally:
        storage.close()
    if pipeline_result.router_result is not None and notification_plan.all_decisions:
        pipeline_result = replace(
            pipeline_result,
            router_result=replace(
                pipeline_result.router_result,
                decisions=list(notification_plan.all_decisions),
            ),
        )
    send_result = event_alpha_pipeline.EventAlphaSendResult(
        requested=False,
        lane_items_attempted=notification_plan.lane_counts,
        lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
        would_send_items=notification_plan.would_send_count,
        heartbeat_due=notification_plan.heartbeat_due,
        cooldown_blocks=dict(notification_plan.blocked_by_lane),
        notification_scope=notification_plan.notification_scope,
        notification_scope_value=notification_plan.scope_value,
        block_reason="send not requested",
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_candidates=len(notification_plan.research_review_items),
        research_review_digest_would_send=notification_plan.lane_counts.get(
            event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
            0,
        ),
        research_review_digest_sent=0,
        research_review_digest_block_reason=notification_plan.blocked_by_lane.get(
            event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
        ),
    )
    clock_send_blocker = _event_alpha_notify_fixed_clock_blocker(clock_status)
    if send and clock_send_blocker:
        send_result = event_alpha_pipeline.EventAlphaSendResult(
            requested=True,
            attempted=False,
            items_attempted=notification_plan.would_send_count,
            items_delivered=0,
            block_reason=clock_send_blocker,
            lane_items_attempted=notification_plan.lane_counts,
            lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
            would_send_items=notification_plan.would_send_count,
            heartbeat_due=notification_plan.heartbeat_due,
            cooldown_blocks=dict(notification_plan.blocked_by_lane),
            notification_scope=notification_plan.notification_scope,
            notification_scope_value=notification_plan.scope_value,
            research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
            research_review_digest_candidates=len(notification_plan.research_review_items),
            research_review_digest_would_send=notification_plan.lane_counts.get(
                event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
                0,
            ),
            research_review_digest_sent=0,
            research_review_digest_block_reason=notification_plan.blocked_by_lane.get(
                event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
            ),
        )
        pipeline_result = replace(
            pipeline_result,
            warnings=tuple(dict.fromkeys((*pipeline_result.warnings, clock_send_blocker))),
            partial_results=True,
        )
        print(f"Event Alpha notify cycle send blocked: {clock_send_blocker}.")
    elif send:
        decisions = pipeline_result.router_result.decisions if pipeline_result.router_result else []
        send_result = _send_event_alpha_routed_digest(
            decisions,
            alert_cfg,
            now=now,
            profile=profile_for_run,
            pipeline_result=pipeline_result,
            card_path_by_alert_id=_card_paths_by_alert_id(
                pipeline_result.router_result.decisions if pipeline_result.router_result else [],
                pipeline_result.research_card_paths,
            ),
            include_health_heartbeat=True,
            clock_status=clock_status,
            delivery_cfg=delivery_cfg,
            run_id=run_id,
            namespace=artifact_namespace or lock_context.artifact_namespace,
            pause_state=pause_state,
            core_opportunity_rows=latest_core_rows,
        )
    else:
        print("Event Alpha notify cycle send not requested; pass --event-alert-send for guarded delivery or would-send accounting.")
    pipeline_result = replace(
        pipeline_result,
        send_requested=send_result.requested,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=dict(send_result.lane_items_attempted),
        send_lane_items_delivered=dict(send_result.lane_items_delivered),
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=dict(send_result.cooldown_blocks),
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
        notification_lock_acquired=run_lock.acquired,
        notification_stale_lock_recovered=run_lock.stale_recovered,
        notification_delivery_records_written=send_result.delivery_records_written,
        notification_deliveries_delivered=send_result.deliveries_delivered,
        notification_deliveries_partial_delivered=send_result.deliveries_partial_delivered,
        notification_deliveries_failed=send_result.deliveries_failed,
        notification_deliveries_skipped_duplicate=send_result.deliveries_skipped_duplicate,
        notification_deliveries_skipped_in_flight=send_result.deliveries_skipped_in_flight,
        notification_deliveries_blocked=send_result.deliveries_blocked,
        notification_burn_in=True,
    )
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipeline_result))
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_cfg.path)
    store_result = event_alpha_alert_store.write_alert_snapshots(
        pipeline_result.alerts,
        cfg=store_cfg,
        now=now,
        router_result=pipeline_result.router_result,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        delivery_rows=delivery_rows,
        research_card_paths=pipeline_result.research_card_paths,
        core_opportunity_rows=latest_core_rows,
    )
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        run_ledger_path=str(_event_alpha_run_ledger_config_from_runtime().path),
        alert_store_path=str(store_cfg.path),
        watchlist_state_path=str(config.EVENT_WATCHLIST_STATE_PATH),
        research_cards_dir=str(config.EVENT_RESEARCH_CARDS_DIR),
        snapshot_write_attempted=store_result.attempted,
        snapshot_write_success=store_result.success,
        snapshot_rows_written=store_result.rows_written,
        snapshot_write_block_reason=store_result.block_reason,
        notification_burn_in=True,
    )
    print("")
    print(event_alpha_alert_store.format_alert_store_write_result(store_result))
    print(
        "Event impact hypotheses updated: "
        f"{hypothesis_store_result.path} rows={hypothesis_store_result.rows_written} "
        f"success={str(hypothesis_store_result.success).lower()}"
        + (f" block={hypothesis_store_result.block_reason}" if hypothesis_store_result.block_reason else "")
    )
    print(
        "Event incidents updated: "
        f"{incident_store_result.path} rows={incident_store_result.rows_written} "
        f"success={str(incident_store_result.success).lower()}"
        + (f" block={incident_store_result.block_reason}" if incident_store_result.block_reason else "")
    )
    print(event_core_opportunity_store.format_core_opportunity_store_write_result(core_store_result))
    pipeline_result = replace(
        pipeline_result,
        **_cryptopanic_stats_for_pipeline_result(
            pipeline_result,
            provider_health_path=_event_provider_health_config_from_runtime().path,
        ),
    )
    run_row = event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=_event_alpha_run_ledger_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        with_llm=with_llm,
        send_requested=send,
        notification_burn_in=True,
        success=True,
    )
    notification_row = event_alpha_notification_runs.append_notification_run(
        pipeline_result,
        cfg=_event_alpha_notification_runs_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        plan=notification_plan,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
    )
    print("")
    print(
        "Event Alpha notification run ledger updated: "
        f"{config.EVENT_ALPHA_RUN_LEDGER_PATH} run_id={run_row.get('run_id')}"
    )
    print(
        "Event Alpha notification summary updated: "
        f"{config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH} run_id={notification_row.get('run_id')}"
    )
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    print("")
    print(format_event_alpha_notification_next_steps(
        profile=profile_for_run,
        provider_health_rows=provider_rows,
        result=pipeline_result,
        notification_row=notification_row,
    ))
    if delivery_cfg is not None and pipeline_result.notification_delivery_records_written:
        print(
            "Event Alpha notification deliveries recorded: "
            f"{pipeline_result.notification_deliveries_delivered} delivered, "
            f"{pipeline_result.notification_deliveries_partial_delivered} partial_delivered, "
            f"{pipeline_result.notification_deliveries_failed} failed, "
            f"{pipeline_result.notification_deliveries_blocked} blocked, "
            f"{pipeline_result.notification_deliveries_skipped_duplicate} skipped_duplicate, "
            f"{pipeline_result.notification_deliveries_skipped_in_flight} skipped_in_flight "
            f"({delivery_cfg.path})."
        )


def event_alpha_notify_preview(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Preview day-1 notification readiness and lane cooldown state."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = resolve_event_alpha_artifact_context_for_report(profile.name, config.EVENT_ALPHA_ARTIFACT_NAMESPACE or profile.name)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    provider = event_provider_status.build_event_discovery_provider_status(config)
    watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    clock_status = _event_clock_status()
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile.name),
            now=now,
            include_health_heartbeat=True,
            core_opportunity_rows=core_rows,
        )
    finally:
        storage.close()
    try:
        run_rows = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=50).rows
        latest_run = event_alpha_run_ledger.latest_run(run_rows, profile.name) or {}
        preview_result = _event_alpha_preview_summary_result(latest_run, plan=plan, profile=profile.name)
        delivery_cfg = event_alpha_notification_delivery.NotificationDeliveryConfig(
            event_alpha_notification_delivery.deliveries_path_for_context(context)
        )
        event_alpha_notification_delivery.rewrite_normalized_delivery_records(delivery_cfg.path)
        writer = event_alpha_notifications._DeliveryWriter(  # preview-only; does not append delivery rows.
            delivery_cfg,
            run_id=str(preview_result.get("run_id") or event_alpha_run_ledger.run_id_for(now, profile.name)),
            profile=profile.name,
            namespace=context.artifact_namespace,
            now=now,
        )
        send_guard_status = (
            "No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode."
            if not config.EVENT_ALERTS_ENABLED and (plan.would_send_count or plan.heartbeat_due)
            else ("Send guard enabled." if config.EVENT_ALERTS_ENABLED else "No-send rehearsal: send guard is disabled.")
        )
        event_alpha_notifications.write_notification_plan_preview(
            plan,
            writer=writer,
            profile=profile.name,
            cfg=_event_alpha_notification_config_from_runtime(profile.name),
            pipeline_result=preview_result,
            status=(
                event_alpha_notification_delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED
                if not config.EVENT_ALERTS_ENABLED
                else "would_send"
            ),
            send_guard_status=send_guard_status,
        )
    except Exception as exc:
        LOGGER.warning("Event Alpha notify preview file write skipped: %s", exc)
    print(event_alpha_notifications.format_preview(
        profile=profile.name,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or profile.name,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        provider_ready_event_sources=provider.ready_event_source_count,
        provider_ready_enrichment_sources=provider.ready_enrichment_count,
        llm_budget_status=_event_alpha_llm_budget_status(),
        plan=plan,
        card_auto_write=bool(config.EVENT_RESEARCH_CARDS_AUTO_WRITE),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        partial_results_allowed=bool(config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS),
        max_runtime_seconds=config.EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS,
        provider_timeout_seconds=config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS,
        fail_fast_on_dns=bool(config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS),
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        clock_status=clock_status,
    ))


def event_alpha_notify_preview_from_artifacts(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Regenerate notification preview and structured preview delivery rows from local artifacts only."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
        context = resolve_event_alpha_artifact_context_for_report(profile.name, artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or profile.name)
    except ValueError as exc:
        print(str(exc))
        return
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        notif_cfg = _event_alpha_notification_config_from_runtime(profile.name)
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=notif_cfg,
            now=now,
            include_health_heartbeat=True,
            core_opportunity_rows=core_rows,
        )
    finally:
        storage.close()
    run_rows = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=50).rows
    latest_run = event_alpha_run_ledger.latest_run(run_rows, profile.name) or {}
    preview_result = _event_alpha_preview_summary_result(latest_run, plan=plan, profile=profile.name)
    delivery_cfg = event_alpha_notification_delivery.NotificationDeliveryConfig(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    event_alpha_notification_delivery.rewrite_normalized_delivery_records(delivery_cfg.path)
    writer = event_alpha_notifications._DeliveryWriter(
        delivery_cfg,
        run_id=str(preview_result.get("run_id") or event_alpha_run_ledger.run_id_for(now, profile.name)),
        profile=profile.name,
        namespace=context.artifact_namespace,
        now=now,
    )
    send_guard_status = (
        "No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode."
        if not config.EVENT_ALERTS_ENABLED and (plan.would_send_count or plan.heartbeat_due)
        else ("Send guard enabled." if config.EVENT_ALERTS_ENABLED else "No-send rehearsal: send guard is disabled.")
    )
    event_alpha_notifications.write_notification_plan_preview(
        plan,
        writer=writer,
        profile=profile.name,
        cfg=notif_cfg,
        pipeline_result=preview_result,
        status=(
            event_alpha_notification_delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED
            if not config.EVENT_ALERTS_ENABLED
            else "would_send"
        ),
        send_guard_status=send_guard_status,
        record_delivery_rows=True,
        delivery_row_not_written_reason="preview_command",
    )
    print(_event_alpha_context_block(context))
    print("notification_preview_from_artifacts: true")
    print(f"notification_preview_path: {event_artifact_paths.artifact_display_path(writer.preview_path)}")
    print(f"delivery_rows_backfilled: {writer.counts.get('records', 0)}")
    print(
        "research_review_skip_telemetry: "
        f"eligible={plan.research_review_eligible_count} "
        f"rendered={len(plan.research_review_items)} "
        f"skipped={len(plan.research_review_skipped_items)}"
    )


def event_alpha_notify_go_no_go(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print a concise day-1 notification go/no-go decision."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "notify_no_key",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or context.profile
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
        routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile_name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    artifacts = _event_alpha_local_artifacts(run_limit=250, latest_alerts=False)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=core_rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=card_paths,
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        daily_brief_path=context.daily_brief_path,
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
        delivery_strict_scope="latest_run",
    )
    readiness = event_alpha_send_readiness.build_send_readiness(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        run_rows=artifacts["runs"].rows,
        core_opportunity_rows=core_rows,
        alert_rows=artifacts["alerts"].rows,
        delivery_rows=delivery_rows,
        artifact_doctor=doctor,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    latest_delivery_rows = [
        row for row in event_alpha_notification_delivery.latest_rows_by_delivery(delivery_rows)
        if not readiness.latest_run_id or str(row.get("run_id") or "") == readiness.latest_run_id
    ]
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    result = event_alpha_notification_go_no_go.build_go_no_go(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status=doctor.status,
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=clock_status,
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
        send_readiness=readiness,
        delivery_rows=latest_delivery_rows,
        delivery_history_rows=delivery_rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_go_no_go.format_go_no_go(result))


def event_alpha_export_notification_pack(
    out: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Export a redacted zip of notification artifacts and operator reports."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    runs = event_alpha_notification_runs.load_notification_runs(context.notification_runs_path, limit=200)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=False)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    daily_brief = ""
    try:
        daily_brief = context.daily_brief_path.read_text(encoding="utf-8")
    except OSError:
        daily_brief = ""
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    lock_status = event_alpha_run_lock.inspect_run_lock(context, stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES)
    storage = Storage(config.DB_PATH)
    try:
        plan = event_alpha_notifications.build_notification_plan(
            [],
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(context.profile),
            now=_event_research_now(),
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    pause_state = _event_alpha_notification_pause_state(context)
    go_no_go = event_alpha_notification_go_no_go.build_go_no_go(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status="not_run",
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=_event_clock_status(),
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
    )
    doctor = event_alpha_environment_doctor.build_environment_doctor(
        profile=context.profile,
        context=context,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        lock_path=event_alpha_run_lock.lock_path_for_context(context),
        delivery_ledger_path=delivery_path,
        notification_runs_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        telegram_chat_ids_present=bool(config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        llm_provider=config.EVENT_LLM_PROVIDER,
        llm_enabled=config.EVENT_LLM_ENABLED,
        llm_extractor_provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        llm_extractor_enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        openai_key_present=bool(config.OPENAI_API_KEY),
        clock_status=_event_clock_status(),
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        python_executable=sys.executable,
        working_directory=str(config.DATA_DIR),
    )
    slo = event_alpha_notification_slo.build_slo_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        provider_health_rows=provider_rows,
        now=datetime.now(timezone.utc),
    )
    result = event_alpha_notification_pack.export_notification_pack(
        out_path=out,
        context=context,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        alert_rows=alerts.rows,
        provider_health_rows=provider_rows,
        go_no_go_text=event_alpha_notification_go_no_go.format_go_no_go(go_no_go),
        environment_doctor_text=event_alpha_environment_doctor.format_environment_doctor(doctor),
        slo_text=event_alpha_notification_slo.format_slo_report(slo),
        daily_brief_text=daily_brief,
        cards_dir=context.research_cards_dir,
    )
    print(event_alpha_notification_pack.format_notification_pack_result(result))


def event_alpha_status(profile_name: str | None = None, verbose: bool = False) -> None:
    """Print profile-aware Event Alpha operational status."""
    bind_scanner_globals(globals())
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
            f"enabled={str(bool(config.EVENT_ALPHA_APPLY_PRIORS)).lower()} "
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


def event_alpha_burn_in_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print live-style no-send burn-in readiness from profile-scoped artifacts."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "live_burn_in_no_send"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=False)
    current_alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
    )
    feedback_readiness = event_alpha_feedback_readiness.build_feedback_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        inbox_result=inbox,
    )
    outcome_rows = [
        row for row in alerts.rows if any(
            row.get(field) not in (None, "")
            for field in (
                "primary_horizon_return",
                "return_1h",
                "return_4h",
                "return_24h",
                "return_72h",
                "return_7d",
                "max_favorable_excursion",
                "max_adverse_excursion",
                "mfe_mae_ratio",
                "direction_hit",
                "volatility_hit",
            )
        )
    ]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(
            context.impact_hypothesis_store_path,
            limit=500,
            latest_run=True,
            include_legacy=True,
        ).rows,
        core_opportunity_rows=core_opportunities.rows,
        watchlist_rows=watchlist.entries,
        incident_rows=event_incident_store.load_incidents(
            context.incident_store_path,
            limit=500,
            latest_run=True,
            include_legacy=True,
        ).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(
            context.evidence_acquisition_path
        ),
        card_paths=[str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)],
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        llm_budget_rows=event_alpha_burn_in.load_llm_budget_rows(context.llm_budget_ledger_path),
        delivery_rows=delivery_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        include_test_artifacts=False,
        include_legacy_artifacts=False,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    acquisition_rows = event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path)
    readiness = event_alpha_burn_in_readiness.build_burn_in_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_rows=runs.rows,
        provider_status=provider_report,
        artifact_doctor=doctor,
        feedback_readiness=feedback_readiness,
        core_opportunity_rows=core_store.rows,
        evidence_acquisition_rows=acquisition_rows,
        daily_brief_path=context.daily_brief_path,
    )
    print(_event_alpha_context_block(context))
    print(event_provider_status.format_event_discovery_provider_status(provider_report))
    print("")
    print(event_alpha_burn_in_readiness.format_burn_in_readiness(readiness))


def event_alpha_notify_fixture_smoke(
    verbose: bool = False,
    *,
    event_now: str | datetime | None = None,
) -> None:
    """Run a local fake-sender Event Alpha notification smoke."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    now = _event_research_now(event_now)
    fixture_profile = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE", "fixture") or "fixture")
    context = event_alpha_artifacts.context_from_profile(
        fixture_profile,
        run_mode="test",
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "fixture_notify_smoke",
    )
    if str(context.artifact_namespace or "").endswith("smoke"):
        shutil.rmtree(context.namespace_dir, ignore_errors=True)
    _apply_event_alpha_context_to_config(context)
    _normalize_profile_paths()
    no_send = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND", "0")).strip().lower() in {"1", "true", "yes", "on"}
    run_id = event_alpha_run_ledger.run_id_for(now, context.profile)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-spacex|velvet|proxy_attention",
        cluster_id="fixture-spacex|proxy_attention|2026-06-15",
        event_id="fixture-notify-velvet",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="venue_value_capture",
        external_asset="SpaceX",
        event_time=now.isoformat(),
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=2,
        highest_score=92,
        latest_score=92,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="VELVET offers SpaceX pre-IPO tokenized stock exposure",
        latest_source="CryptoPanic fixture",
        latest_playbook_type="proxy_attention",
        latest_rule_playbook_type="proxy_attention",
        latest_effective_playbook_type="proxy_attention",
        latest_playbook_score=92,
        latest_playbook_action="high_priority_watch",
        latest_market_snapshot={"price": 1.0, "return_24h": 0.42, "volume_zscore_24h": 5.2},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-velvet-spacex",
            "hypothesis_id": "hypothesis:fixture-velvet-spacex",
            "external_catalyst": 92,
            "market_move_volume": 88,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_venue",
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 91,
            "market_confirmation_score": 88,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
            "opportunity_score_final": 92,
            "opportunity_level": "high_priority",
        },
        incident_id="incident:fixture-spacex",
        hypothesis_id="hypothesis:fixture-velvet-spacex",
        should_alert=True,
        material_change_reasons=("fixture_notification_smoke",),
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="Fixture high-priority state escalation for notification smoke.",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
    )
    aave_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-aave-kraken|aave|strategic_investment",
        cluster_id="fixture-aave-kraken|strategic_investment|2026-06-15",
        event_id="fixture-notify-aave",
        coin_id="aave",
        symbol="AAVE",
        relationship_type="strategic_investment",
        external_asset="Kraken",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=2,
        highest_score=78,
        latest_score=78,
        latest_tier="WATCHLIST",
        latest_event_name="Kraken takes strategic stake in Aave ecosystem",
        latest_source="Crypto news fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=78,
        latest_playbook_action="watchlist",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-aave-kraken",
            "hypothesis_id": "hypothesis:fixture-aave-kraken",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "candidate_role": "direct_subject",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
        },
        incident_id="incident:fixture-aave-kraken",
        hypothesis_id="hypothesis:fixture-aave-kraken",
        should_alert=True,
        material_change_reasons=("fixture_notification_digest",),
    )
    aave_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=aave_entry,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        alertable=True,
        reason="Fixture accepted source evidence for strategic stake digest.",
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
    )
    core_source_row = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-velvet-spacex",
        "key": entry.key,
        "hypothesis_id": entry.hypothesis_id,
        "incident_id": entry.incident_id,
        "event_id": entry.event_id,
        "symbol": entry.symbol,
        "coin_id": entry.coin_id,
        "validated_symbol": entry.symbol,
        "validated_coin_id": entry.coin_id,
        "canonical_incident_name": entry.latest_event_name,
        "candidate_role": "proxy_venue",
        "impact_category": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "impact_path_reason": "venue_value_capture",
        "relationship_type": "venue_value_capture",
        "opportunity_level": "high_priority",
        "final_opportunity_level": "high_priority",
        "opportunity_score_final": 92,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 91,
        "market_confirmation_score": 88,
        "market_confirmation_level": "strong",
        "market_context_freshness_status": "fresh",
        "market_context_source": "fixture_market_context",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_evidence_count": 1,
        "acquisition_confirmation_status": "confirms",
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "accepted_evidence_samples": [
            {
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "provider": "cryptopanic_fixture",
                "source_url": "https://example.invalid/velvet-spacex",
            }
        ],
        "source_pack": "proxy_preipo_rwa_pack",
        "latest_source": "CryptoPanic fixture",
        "latest_source_title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
        "why_opportunity_visible": "Accepted tagged evidence validates the token/catalyst link.",
        "upgrade_requirements": ["verify accepted source evidence", "confirm market reaction remains organic"],
        "latest_market_snapshot": entry.latest_market_snapshot,
    }
    weak_btc_control = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-btc-rejected",
        "key": "fixture-strategy|bitcoin|strategic_context",
        "hypothesis_id": "hypothesis:fixture-btc-rejected",
        "incident_id": "incident:fixture-strategy-valuation",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "validated_symbol": "BTC",
        "validated_coin_id": "bitcoin",
        "canonical_incident_name": "Strategy valuation article mentions Bitcoin treasury holdings",
        "candidate_role": "treasury_context",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "medium",
        "impact_path_reason": "treasury_context",
        "opportunity_level": "local_only",
        "final_opportunity_level": "local_only",
        "opportunity_score_final": 44,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 88,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 2,
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "does_not_confirm",
        "source_pack": "strategic_investment_pack",
        "latest_source": "Strategy valuation fixture",
        "why_opportunity_visible": "Fixture control: broad treasury valuation context is not direct BTC confirmation.",
    }
    aave_core_source_row = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-aave-kraken",
        "key": aave_entry.key,
        "hypothesis_id": aave_entry.hypothesis_id,
        "incident_id": aave_entry.incident_id,
        "event_id": aave_entry.event_id,
        "symbol": aave_entry.symbol,
        "coin_id": aave_entry.coin_id,
        "validated_symbol": aave_entry.symbol,
        "validated_coin_id": aave_entry.coin_id,
        "canonical_incident_name": aave_entry.latest_event_name,
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "medium",
        "impact_path_reason": "strategic_investment",
        "relationship_type": "strategic_investment",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 78,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 86,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_evidence_count": 1,
        "acquisition_confirmation_status": "confirms",
        "accepted_evidence_reason_codes": ["direct_token_mechanism"],
        "accepted_evidence_samples": [
            {
                "title": "Kraken takes strategic stake in Aave ecosystem",
                "provider": "crypto_news_fixture",
                "source_url": "https://example.invalid/aave-kraken",
            }
        ],
        "source_pack": "strategic_investment_pack",
        "latest_source": "Crypto news fixture",
        "latest_source_title": "Kraken takes strategic stake in Aave ecosystem",
        "why_opportunity_visible": "Accepted direct source evidence validates the AAVE/Kraken relationship.",
        "upgrade_requirements": ["verify primary source", "wait for market confirmation"],
    }
    tao_control = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-tao-rejected",
        "key": "fixture-tao|bittensor|strategic_context",
        "hypothesis_id": "hypothesis:fixture-tao-rejected",
        "incident_id": "incident:fixture-tao-strategic",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "validated_symbol": "TAO",
        "validated_coin_id": "bittensor",
        "canonical_incident_name": "Broad AI infrastructure article mentions Bittensor without impact evidence",
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "weak",
        "impact_path_reason": "weak_cooccurrence_only",
        "opportunity_level": "local_only",
        "final_opportunity_level": "local_only",
        "opportunity_score_final": 38,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "broad_news",
        "evidence_specificity": "weak_cooccurrence",
        "evidence_quality_score": 40,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 1,
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "does_not_confirm",
        "source_pack": "strategic_investment_pack",
        "latest_source": "Broad AI fixture",
        "why_opportunity_visible": "Fixture control: broad AI/TAO co-occurrence is not validated impact evidence.",
    }
    doge_near_miss = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-doge-near-miss",
        "key": "fixture-doge|dogecoin|exploratory_meme_catalyst",
        "hypothesis_id": "hypothesis:fixture-doge-near-miss",
        "incident_id": "incident:fixture-doge-catalyst",
        "symbol": "DOGE",
        "coin_id": "dogecoin",
        "validated_symbol": "DOGE",
        "validated_coin_id": "dogecoin",
        "canonical_incident_name": "DOGE jumps on unconfirmed meme catalyst chatter",
        "candidate_role": "candidate_asset",
        "impact_category": "meme_attention",
        "impact_path_type": "meme_attention",
        "impact_path_strength": "medium",
        "impact_path_reason": "market_confirmation_without_source_confirmation",
        "relationship_type": "proxy_attention",
        "opportunity_level": "exploratory",
        "final_opportunity_level": "exploratory",
        "opportunity_score_final": 66,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "crypto_news",
        "evidence_specificity": "candidate_context",
        "evidence_quality_score": 58,
        "market_confirmation_score": 72,
        "market_confirmation_level": "moderate",
        "market_context_freshness_status": "fresh",
        "evidence_acquisition_status": "skipped_budget",
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "unresolved",
        "source_pack": "meme_attention_pack",
        "latest_source": "Meme catalyst fixture",
        "latest_source_title": "DOGE jumps on unconfirmed meme catalyst chatter",
        "why_opportunity_visible": "Strong fresh move with a possible catalyst clue, but no independent confirmation yet.",
        "why_not_watchlist": "missing independent source confirmation",
        "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
    }
    core_write = event_core_opportunity_store.write_core_opportunities(
        [core_source_row, aave_core_source_row, weak_btc_control, tao_control, doge_near_miss],
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(context.core_opportunity_store_path),
        now=now,
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    card_write = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=[entry, aave_entry],
        alert_rows=core_rows,
        route_decisions=[decision, aave_decision],
        now=now,
        lineage_context=_event_alpha_card_lineage_context(
            run_id=run_id,
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=context.artifact_namespace,
        ),
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_write.card_paths,
        run_id=run_id,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    core_by_id = {str(row.get("core_opportunity_id") or ""): row for row in core_rows}
    canonical_core = core_by_id.get("agg:fixture-velvet-spacex") or (core_rows[0] if core_rows else {})
    btc_core = core_by_id.get("agg:fixture-btc-rejected") or {}
    aave_core = core_by_id.get("agg:fixture-aave-kraken") or {}
    tao_core = core_by_id.get("agg:fixture-tao-rejected") or {}
    doge_core = core_by_id.get("agg:fixture-doge-near-miss") or {}
    snapshot_path = _write_fixture_alert_snapshot(
        context,
        entry=entry,
        decision=decision,
        run_id=run_id,
        observed_at=now,
        core_row=canonical_core,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=aave_entry,
        decision=aave_decision,
        run_id=run_id,
        observed_at=now,
        core_row=aave_core,
    )
    btc_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-strategy|bitcoin|strategic_context",
        cluster_id="fixture-strategy|strategic_context|2026-06-15",
        event_id="fixture-btc-rejected",
        coin_id="bitcoin",
        symbol="BTC",
        relationship_type="strategic_investment_or_valuation",
        external_asset="Strategy",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=44,
        latest_score=44,
        latest_tier="STORE_ONLY",
        latest_event_name="Strategy valuation article mentions Bitcoin treasury holdings",
        latest_source="Strategy valuation fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=44,
        latest_playbook_action="store_only",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-btc-rejected",
            "hypothesis_id": "hypothesis:fixture-btc-rejected",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "treasury_context",
            "candidate_role": "treasury_context",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "rejected_results_only",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "local_only",
            "opportunity_score_final": 44,
        },
        incident_id="incident:fixture-strategy-valuation",
        hypothesis_id="hypothesis:fixture-btc-rejected",
        should_alert=False,
        suppressed_reason="rejected_results_only_not_confirmation",
    )
    btc_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=btc_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture control: rejected-only strategic broad-asset context is local-only.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=btc_entry,
        decision=btc_decision,
        run_id=run_id,
        observed_at=now,
        core_row=btc_core,
    )
    tao_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-tao|bittensor|strategic_context",
        cluster_id="fixture-tao|strategic_context|2026-06-15",
        event_id="fixture-tao-rejected",
        coin_id="bittensor",
        symbol="TAO",
        relationship_type="strategic_investment_or_valuation",
        external_asset="AI infrastructure",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=38,
        latest_score=38,
        latest_tier="STORE_ONLY",
        latest_event_name="Broad AI infrastructure article mentions Bittensor without impact evidence",
        latest_source="Broad AI fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=38,
        latest_playbook_action="store_only",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-tao-rejected",
            "hypothesis_id": "hypothesis:fixture-tao-rejected",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "weak_cooccurrence_only",
            "candidate_role": "direct_subject",
            "source_class": "broad_news",
            "evidence_acquisition_status": "rejected_results_only",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "local_only",
            "opportunity_score_final": 38,
        },
        incident_id="incident:fixture-tao-strategic",
        hypothesis_id="hypothesis:fixture-tao-rejected",
        should_alert=False,
        suppressed_reason="rejected_results_only_not_confirmation",
    )
    tao_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=tao_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture control: rejected-only TAO context is local-only.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=tao_entry,
        decision=tao_decision,
        run_id=run_id,
        observed_at=now,
        core_row=tao_core,
    )
    doge_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-doge|dogecoin|exploratory_meme_catalyst",
        cluster_id="fixture-doge|meme_attention|2026-06-15",
        event_id="fixture-doge-near-miss",
        coin_id="dogecoin",
        symbol="DOGE",
        relationship_type="proxy_attention",
        external_asset="meme catalyst chatter",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=66,
        latest_score=66,
        latest_tier="STORE_ONLY",
        latest_event_name="DOGE jumps on unconfirmed meme catalyst chatter",
        latest_source="Meme catalyst fixture",
        latest_playbook_type="meme_attention",
        latest_rule_playbook_type="meme_attention",
        latest_effective_playbook_type="meme_attention",
        latest_playbook_score=66,
        latest_playbook_action="store_only",
        latest_market_snapshot={"return_24h": 0.31, "return_72h": 0.66, "volume_mcap": 0.22},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-doge-near-miss",
            "hypothesis_id": "hypothesis:fixture-doge-near-miss",
            "impact_path_type": "meme_attention",
            "impact_path_reason": "market_confirmation_without_source_confirmation",
            "candidate_role": "candidate_asset",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "skipped_budget",
            "accepted_evidence_count": 0,
            "market_confirmation_score": 72,
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
            "opportunity_level": "exploratory",
            "opportunity_score_final": 66,
            "why_not_watchlist": "missing independent source confirmation",
            "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
        },
        incident_id="incident:fixture-doge-catalyst",
        hypothesis_id="hypothesis:fixture-doge-near-miss",
        should_alert=False,
        suppressed_reason="missing independent source confirmation",
    )
    doge_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=doge_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture near-miss: strong move needs independent catalyst confirmation.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=doge_entry,
        decision=doge_decision,
        run_id=run_id,
        observed_at=now,
        core_row=doge_core,
    )
    fake_storage = _FixtureNotificationStorage()
    delivered_messages: list[str] = []
    notification_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=not no_send,
        mode="research_only",
        notification_scope=event_alpha_notifications.NOTIFICATION_SCOPE_NAMESPACE,
        profile_name=context.profile,
        artifact_namespace=context.artifact_namespace,
        daily_digest_cooldown_hours=0,
        instant_escalation_cooldown_hours=0,
        max_instant_per_day=10,
        health_heartbeat_enabled=False,
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_max_items=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MAX_ITEMS,
        research_review_digest_min_score=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE,
        research_review_digest_cooldown_hours=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_COOLDOWN_HOURS,
        research_review_digest_include_local_only=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_LOCAL_ONLY,
        research_review_digest_include_sector=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_SECTOR,
        research_review_digest_send_with_alerts=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS,
        allow_source_only_narrative_digest=config.EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST,
    )
    delivery_cfg = _event_alpha_notification_delivery_config_from_runtime(context)

    def _fake_sender(message: str) -> event_alpha_notification_sender.NotificationSendAttemptResult:
        delivered_messages.append(message)
        chunks = event_alpha_notification_sender.telegram_chunk_count(message)
        return event_alpha_notification_sender.NotificationSendAttemptResult(
            attempted=True,
            success=True,
            recipient_count=1,
            delivered_count=1,
            failed_count=0,
            chunk_count=chunks,
            delivered_chunks=chunks,
            failed_chunks=0,
            channel_summary={"channel": "fixture", "delivered_count": 1},
        )

    send_result = event_alpha_notifications.send_notifications(
        [decision, aave_decision, doge_decision] if config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED else [decision, aave_decision],
        storage=fake_storage,
        cfg=notification_cfg,
        send_fn=_fake_sender,
        now=now,
        profile=context.profile,
        card_path_by_alert_id=_card_paths_by_alert_id([decision], card_write.card_paths),
        core_opportunity_rows=core_rows,
        include_health_heartbeat=False,
        delivery_cfg=delivery_cfg,
        run_id=run_id,
        namespace=context.artifact_namespace,
    )
    snapshot_rows_written = 5
    pipeline_result = SimpleNamespace(
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
        router_result=event_alpha_router.EventAlphaRouterResult(
            state_path=context.watchlist_state_path,
            rows_read=1,
            decisions=[decision],
            enabled=True,
        ),
        alerts=(),
        warnings=(),
        clock_status=_event_clock_status(event_now),
        cycle_completed=True,
        partial_results=False,
        send_requested=True,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=send_result.lane_items_attempted,
        send_lane_items_delivered=send_result.lane_items_delivered,
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=send_result.cooldown_blocks,
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
        notification_burn_in=True,
        research_card_paths=card_write.card_paths,
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        core_opportunity_write_attempted=core_write.attempted,
        core_opportunity_write_success=core_write.success,
        core_opportunity_rows_written=core_write.rows_written,
        core_opportunity_write_block_reason=core_write.block_reason,
        run_ledger_path=str(context.run_ledger_path),
        alert_store_path=str(context.alert_store_path),
        watchlist_state_path=str(context.watchlist_state_path),
        research_cards_dir=str(context.research_cards_dir),
        snapshot_write_attempted=True,
        snapshot_write_success=True,
        snapshot_rows_written=snapshot_rows_written,
        snapshot_write_block_reason=None,
        notification_delivery_records_written=send_result.delivery_records_written,
        notification_deliveries_delivered=send_result.deliveries_delivered,
        notification_deliveries_partial_delivered=send_result.deliveries_partial_delivered,
        notification_deliveries_failed=send_result.deliveries_failed,
        notification_deliveries_skipped_duplicate=send_result.deliveries_skipped_duplicate,
        notification_deliveries_skipped_in_flight=send_result.deliveries_skipped_in_flight,
        notification_deliveries_blocked=send_result.deliveries_blocked,
    )
    event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(context.run_ledger_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        with_llm=False,
        send_requested=True,
        notification_burn_in=True,
    )
    notification_row = event_alpha_notification_runs.append_notification_run(
        pipeline_result,
        cfg=event_alpha_notification_runs.EventAlphaNotificationRunsConfig(context.notification_runs_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        telegram_ready=False,
        send_guard_enabled=False,
    )
    print(_event_alpha_context_block(context))
    print("\n".join([
        "=" * 76,
        "EVENT ALPHA NOTIFICATION FIXTURE SMOKE (fake sender)",
        "=" * 76,
        f"run_id: {run_id}",
        f"mode: {'no-send guarded preview' if no_send else 'fake sender'}",
        f"fake_sender_delivered: {len(delivered_messages)}",
        f"delivery_path: {event_artifact_paths.artifact_display_path(delivery_cfg.path)}",
        f"delivery_records_written: {send_result.delivery_records_written}",
        f"delivery_delivered: {send_result.deliveries_delivered}",
        f"delivery_partial_delivered: {send_result.deliveries_partial_delivered}",
        f"notification_run_path: {event_artifact_paths.artifact_display_path(context.notification_runs_path)}",
        f"notification_would_send: {notification_row.get('would_send_count')}",
        f"alert_snapshot_path: {event_artifact_paths.artifact_display_path(snapshot_path)}",
        f"core_opportunity_store_path: {event_artifact_paths.artifact_display_path(context.core_opportunity_store_path)}",
        f"core_opportunities_written: {core_write.rows_written}",
        f"research_card_count: {card_write.cards_written}",
        f"research_card_index: {event_artifact_paths.artifact_display_path(card_write.index_path)}",
        "feedback: make event-feedback-useful "
        f"FEEDBACK_TARGET='{canonical_core.get('core_opportunity_id') or decision.alert_id}'",
        "No live providers, Telegram sends, normal RSI alerts, paper trades, live DB rows, or execution were used.",
    ]))


def event_alpha_export_burn_in_pack(
    out_path: str,
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Write a clean Event Alpha burn-in review zip."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    from . import event_alpha_burn_in_checklist as checklist

    checklist_result = checklist.build_burn_in_checklist(scorecard)
    readiness = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    health = event_alpha_health_guard.evaluate_health_guard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(
            max_run_age_hours=config.EVENT_ALPHA_MAX_RUN_AGE_HOURS,
            max_success_age_hours=config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS,
            require_profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE,
        ),
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    cards_dir = Path(config.EVENT_RESEARCH_CARDS_DIR)
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or None,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        strict=bool(config.EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT),
    )
    router_result = event_alpha_router.route_watchlist(
        artifacts["watchlist"],
        cfg=_event_alpha_router_config_from_runtime(),
    )
    daily_brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        notification_runs=event_alpha_notification_runs.load_notification_runs(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH).rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH, limit=100).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
        watchlist_entries=artifacts["watchlist"].entries,
        router_result=router_result,
        provider_health_rows=artifacts["provider_rows"],
        artifact_namespace=artifact_namespace,
        run_mode=config.EVENT_ALPHA_RUN_MODE,
        run_ledger_path=config.EVENT_ALPHA_RUN_LEDGER_PATH,
        alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        clock_status=_event_clock_status(),
        generated_at=_event_research_now(),
    )
    calibration = event_alpha_calibration.format_calibration_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
    )
    source_reliability = event_source_reliability.format_source_reliability_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
    )
    tuning = event_alpha_tuning.format_tuning_worksheet(event_alpha_tuning.build_tuning_worksheet(
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
    ))
    result = event_alpha_burn_in_pack.export_burn_in_pack(
        out_path,
        daily_brief=daily_brief,
        burn_in_scorecard=event_alpha_burn_in.format_burn_in_scorecard(scorecard),
        burn_in_checklist=checklist.format_burn_in_checklist(checklist_result),
        v1_readiness=event_alpha_v1_readiness.format_v1_readiness_report(readiness),
        health_guard=event_alpha_health_guard.format_health_guard_report(health),
        artifact_doctor=event_alpha_artifact_doctor.format_artifact_doctor_report(doctor),
        source_reliability=source_reliability,
        calibration=calibration,
        missed="Run --event-alpha-missed-report before exporting if fresh missed rows are required.\n",
        tuning=tuning,
        priors_shadow="Run --event-alpha-priors-shadow-report separately when current provider inputs are configured.\n",
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        outcome_rows=artifacts["outcome_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cards_dir=config.EVENT_RESEARCH_CARDS_DIR,
        proposed_eval_dir=config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
        profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or None,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        date_range=f"{days}d",
    )
    print(event_alpha_burn_in_pack.format_burn_in_pack_result(result))


def event_alpha_daily_brief_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Write and print the daily Event Alpha operating brief."""
    bind_scanner_globals(globals())
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
    profile = event_alpha_profiles.get_profile(selected_profile) if selected_profile else None
    artifact_namespace = artifact_namespace or context.artifact_namespace
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=25)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=True,
    )
    event_core_opportunity_store.normalize_core_opportunity_store(
        context.core_opportunity_store_path,
        latest_run=True,
        now=datetime.now(timezone.utc),
    )
    event_alpha_notification_runs.normalize_notification_runs_after_cryptopanic_success(
        context.notification_runs_path,
        request_ledger_path=context.provider_health_path.with_name("cryptopanic_request_ledger.jsonl"),
    )
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=100,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
    router_result = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    )
    card_write = event_research_cards.write_research_cards(
        config.EVENT_RESEARCH_CARDS_DIR,
        watchlist_entries=watchlist.entries,
        alert_rows=[*alerts.rows, *hypotheses.rows, *core_store.rows],
        route_decisions=router_result.decisions,
        monitor_rows=monitor_result.rows,
        selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
        limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
        now=datetime.now(timezone.utc),
        lineage_context=_event_alpha_card_lineage_context(
            run_id=_latest_event_alpha_run_id(context.run_ledger_path),
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
        incident_rows=event_incident_store.load_incidents(context.incident_store_path, limit=100, include_legacy=True).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        market_anomaly_rows=event_market_anomaly_scanner.load_market_anomaly_rows(context.namespace_dir),
        official_exchange_candidate_rows=event_official_exchange.load_official_listing_candidates(context.namespace_dir),
        scheduled_catalyst_rows=event_scheduled_catalysts.load_scheduled_catalysts(context.namespace_dir),
        unlock_candidate_rows=event_scheduled_catalysts.load_unlock_candidates(context.namespace_dir),
        derivatives_state_rows=event_derivatives_crowding.load_derivatives_state(context.namespace_dir),
        fade_review_candidate_rows=event_derivatives_crowding.load_fade_review_candidates(context.namespace_dir),
        watchlist_entries=watchlist.entries,
        router_result=router_result,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        card_paths=card_write.card_paths,
        requested_profile=profile.name if profile else profile_name,
        artifact_namespace=artifact_namespace,
        run_mode=context.run_mode,
        run_ledger_path=context.run_ledger_path,
        alert_store_path=context.alert_store_path,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    result = event_alpha_daily_brief.write_daily_brief(
        config.EVENT_ALPHA_DAILY_BRIEF_PATH,
        markdown=markdown,
        card_paths=card_write.card_paths,
    )
    report = _event_alpha_context_block(context) + "\n" + event_alpha_daily_brief.format_daily_brief_result(result)
    if profile:
        report += f"\nprofile_applied: {profile.name}"
    print(report)


def event_alpha_integrated_radar_cycle_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    fixture: bool = False,
    input_mode: str | None = None,
    coinalyze_namespace: str | None = None,
) -> None:
    """Run the research-only integrated Event Alpha radar cycle and print a summary."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or ("fixture" if fixture else config.EVENT_ALPHA_PROFILE or "notify_llm_deep")
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=fixture,
        )
    except ValueError as exc:
        print(str(exc))
        return
    result = event_integrated_radar.run_integrated_radar_cycle(
        context=context,
        fixture=fixture,
        observed_at=_event_research_now(),
        input_mode=input_mode or event_integrated_radar.INPUT_MODE_AUTO,
        coinalyze_namespace=coinalyze_namespace,
    )
    print(_event_alpha_context_block(context))
    print(
        "integrated_radar_cycle: "
        f"candidates={result.candidates} cores={result.core_opportunity_rows_written} "
        f"cards={len(result.research_card_paths)} "
        f"preview={event_artifact_paths.artifact_display_path(result.notification_preview_path)}"
    )
    print(f"report: {event_artifact_paths.artifact_display_path(result.integrated_report_path)}")
    print("No Telegram sends, paper trades, normal RSI signal rows, execution, or Event Alpha TRIGGERED_FADE were created.")


def event_alpha_market_anomaly_scan_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    market_rows_path: str | None = None,
    asset_registry_path: str | None = None,
    coingecko_universe_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Run the research-only broad market anomaly scanner and write artifacts."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "fixture"
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, context.profile)
    path = Path(market_rows_path).expanduser() if market_rows_path else Path(config.EVENT_ALPHA_MARKET_ANOMALY_ROWS_PATH)
    rows = event_market_anomaly_scanner.load_market_rows(path)
    registry_path = Path(asset_registry_path).expanduser() if asset_registry_path else config.EVENT_ASSET_REGISTRY_PATH
    universe_path = (
        Path(coingecko_universe_path).expanduser()
        if coingecko_universe_path
        else config.EVENT_DISCOVERY_UNIVERSE_PATH
    )
    universe_rows = event_market_anomaly_scanner.load_coingecko_universe_rows(universe_path) if universe_path else []
    registry = event_asset_registry.build_asset_registry(
        fixture_path=registry_path,
        coingecko_universe_path=universe_path,
    )
    cfg = event_market_anomaly_scanner.MarketAnomalyScannerConfig(
        max_assets=int(getattr(config, "EVENT_ALPHA_MARKET_ANOMALY_MAX_ASSETS", config.EVENT_ANOMALY_MAX_ASSETS)),
        suspicious_liquidity_usd=float(getattr(config, "EVENT_ALPHA_MARKET_ANOMALY_SUSPICIOUS_LIQUIDITY_USD", 50_000.0)),
    )
    result = event_market_anomaly_scanner.run_market_anomaly_scan(
        market_rows=rows,
        namespace_dir=context.namespace_dir,
        cfg=cfg,
        observed_at=_event_research_now(),
        asset_registry=registry,
        coingecko_universe_rows=universe_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
    )
    finished_at = datetime.now(timezone.utc)
    _append_market_anomaly_run_ledger_row(
        context,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        raw_rows=len(rows),
        snapshot_count=result.snapshot_count,
        anomaly_count=result.anomaly_count,
        catalyst_search_queue_count=result.catalyst_search_queue_count,
    )
    print(_event_alpha_context_block(context))
    print(
        "market_anomaly_scan: "
        f"rows={len(rows)} snapshots={result.snapshot_count} anomalies={result.anomaly_count} "
        f"catalyst_search_queue={result.catalyst_search_queue_count} "
        f"snapshots_path={event_artifact_paths.artifact_display_path(result.snapshots_path)} "
        f"anomalies_path={event_artifact_paths.artifact_display_path(result.anomalies_path)} "
        f"queue_path={event_artifact_paths.artifact_display_path(result.catalyst_search_queue_path)} "
        f"report_path={event_artifact_paths.artifact_display_path(result.report_path)}"
    )
    print(event_market_anomaly_scanner.format_market_anomaly_report(
        result.anomalies,
        catalyst_search_queue=result.catalyst_search_queue,
        snapshot_count=result.snapshot_count,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    ))


def event_alpha_official_exchange_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    binance_path: str | None = None,
    bybit_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Run the research-only official exchange announcement normalizer."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "fixture"
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, context.profile)
    provider_paths = {
        "binance_announcements": Path(binance_path).expanduser() if binance_path else Path(config.EVENT_ALPHA_OFFICIAL_EXCHANGE_BINANCE_PATH),
        "bybit_announcements": Path(bybit_path).expanduser() if bybit_path else Path(config.EVENT_ALPHA_OFFICIAL_EXCHANGE_BYBIT_PATH),
    }
    result = event_official_exchange.run_official_exchange_scan(
        namespace_dir=context.namespace_dir,
        provider_paths=provider_paths,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        observed_at=_event_research_now(),
    )
    activation_report = event_official_exchange_activation.build_activation_report(
        namespace_dir=context.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        observed_at=_event_research_now(),
        no_send_rehearsal_by_provider={
            event_official_exchange_activation.PROVIDER_BYBIT_PUBLIC: True,
            event_official_exchange_activation.PROVIDER_BINANCE_PUBLIC_OR_FIXTURE: True,
            event_official_exchange_activation.PROVIDER_BINANCE_SIGNED_LISTENER: True,
        },
    )
    activation_json_path, activation_md_path = event_official_exchange_activation.write_activation_artifacts(
        activation_report,
        context.namespace_dir,
    )
    finished_at = datetime.now(timezone.utc)
    _record_official_exchange_provider_health(context, result=result, run_id=run_id, now=finished_at)
    _append_official_exchange_run_ledger_row(
        context,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        announcement_count=result.announcement_count,
        event_count=result.event_count,
        candidate_count=result.candidate_count,
        warnings=result.warnings,
    )
    print(_event_alpha_context_block(context))
    print(
        "official_exchange_scan: "
        f"announcements={result.announcement_count} events={result.event_count} candidates={result.candidate_count} "
        f"announcements_path={event_artifact_paths.artifact_display_path(result.announcements_path)} "
        f"events_path={event_artifact_paths.artifact_display_path(result.events_path)} "
        f"candidates_path={event_artifact_paths.artifact_display_path(result.candidates_path)} "
        f"report_path={event_artifact_paths.artifact_display_path(result.report_path)} "
        f"activation_json_path={event_artifact_paths.artifact_display_path(activation_json_path)} "
        f"activation_report_path={event_artifact_paths.artifact_display_path(activation_md_path)}"
    )
    print(event_official_exchange.format_official_exchange_report(
        result.events,
        result.candidates,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        warnings=result.warnings,
    ))


def event_alpha_scheduled_catalyst_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    tokenomist_path: str | None = None,
    messari_path: str | None = None,
    coinmarketcal_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Run the research-only scheduled catalyst/unlock normalizer."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "fixture"
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, context.profile)
    provider_paths = {
        "tokenomist": Path(tokenomist_path).expanduser() if tokenomist_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH),
        "messari_unlocks": Path(messari_path).expanduser() if messari_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH),
        "coinmarketcal": Path(coinmarketcal_path).expanduser() if coinmarketcal_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH),
    }
    preflight = event_unlock_calendar_preflight.build_preflight_report(
        namespace_dir=context.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        tokenomist_path=provider_paths["tokenomist"],
        messari_path=provider_paths["messari_unlocks"],
        coinmarketcal_path=provider_paths["coinmarketcal"],
        smoke_mode=include_test_artifacts,
        now=_event_research_now(),
    )
    event_unlock_calendar_preflight.write_preflight_artifacts(preflight, context.namespace_dir)
    result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
        namespace_dir=context.namespace_dir,
        provider_paths=provider_paths,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        observed_at=_event_research_now(),
    )
    finished_at = datetime.now(timezone.utc)
    _record_scheduled_catalyst_provider_health(context, result=result, run_id=run_id, now=finished_at)
    _append_scheduled_catalyst_run_ledger_row(
        context,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        scheduled_count=result.scheduled_count,
        unlock_count=result.unlock_count,
        warnings=result.warnings,
    )
    print(_event_alpha_context_block(context))
    print(
        "scheduled_catalyst_scan: "
        f"scheduled={result.scheduled_count} unlocks={result.unlock_count} "
        f"scheduled_path={event_artifact_paths.artifact_display_path(result.scheduled_path)} "
        f"unlock_path={event_artifact_paths.artifact_display_path(result.unlock_path)} "
        f"scheduled_report={event_artifact_paths.artifact_display_path(result.scheduled_report_path)} "
        f"unlock_report={event_artifact_paths.artifact_display_path(result.unlock_report_path)}"
    )
    print(event_scheduled_catalysts.format_scheduled_catalyst_report(
        result.scheduled_events,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        warnings=result.warnings,
    ))
    print(event_scheduled_catalysts.format_unlock_risk_report(
        result.unlock_candidates,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        warnings=result.warnings,
    ))


def event_alpha_derivatives_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    derivatives_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Run the research-only derivatives crowding/fade-review normalizer."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "fixture"
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, context.profile)
    path = Path(derivatives_path).expanduser() if derivatives_path else Path(config.EVENT_ALPHA_DERIVATIVES_CROWDING_PATH)
    result = event_derivatives_crowding.run_derivatives_crowding_scan(
        namespace_dir=context.namespace_dir,
        derivatives_path=path,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        observed_at=_event_research_now(),
    )
    finished_at = datetime.now(timezone.utc)
    _record_derivatives_provider_health(context, result=result, run_id=run_id, now=finished_at)
    _append_derivatives_run_ledger_row(
        context,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        derivatives_state_count=result.derivatives_state_count,
        evaluated_candidate_count=result.evaluated_candidate_count,
        fade_review_candidate_count=result.fade_review_candidate_count,
        warnings=result.warnings,
    )
    print(_event_alpha_context_block(context))
    print(
        "derivatives_crowding_scan: "
        f"state_rows={result.derivatives_state_count} candidates={result.evaluated_candidate_count} "
        f"fade_review={result.fade_review_candidate_count} "
        f"state_path={event_artifact_paths.artifact_display_path(result.derivatives_state_path)} "
        f"fade_path={event_artifact_paths.artifact_display_path(result.fade_review_candidates_path)} "
        f"report_path={event_artifact_paths.artifact_display_path(result.report_path)}"
    )
    print(event_derivatives_crowding.format_derivatives_crowding_report(
        state_rows=result.derivatives_state_rows,
        candidate_rows=result.candidate_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        warnings=result.warnings,
    ))


def event_alpha_replay_report(
    *,
    priors: bool = False,
    llm_advisory: bool = False,
    raw_events_path: str | None = None,
    market_rows_path: str | None = None,
    compare: str | None = None,
    replay_profile: str | None = None,
    replay_profile_alt: str | None = None,
    verbose: bool = False,
) -> None:
    """Replay Event Alpha local artifacts without provider calls or sends."""
    bind_scanner_globals(globals())
    _setup_event_discovery_logging(verbose)
    if replay_profile:
        _profile, error = _apply_event_alpha_report_profile(replay_profile)
        if error:
            print(error)
            return
    if raw_events_path:
        raw_events = event_alpha_replay.load_raw_events_jsonl(raw_events_path)
        market_rows = event_alpha_replay.load_market_rows(market_rows_path or config.EVENT_DISCOVERY_UNIVERSE_PATH)
        assets = [
            *event_discovery.load_discovery_assets(config.EVENT_DISCOVERY_ALIASES_PATH),
            *event_alpha_replay.assets_from_market_rows(market_rows),
        ]
        llm_cfg = _event_llm_config_from_runtime() if llm_advisory else None
        if compare and any(part.strip().lower() in {"llm", "llm_advisory"} for part in compare.split(",")):
            llm_cfg = _event_llm_config_from_runtime()
        llm_provider = _event_llm_provider(llm_cfg) if llm_cfg and llm_cfg.provider != "openai" else None
        priors_cfg = _event_alpha_priors_config_from_runtime()
        router_cfg = _event_alpha_router_config_from_runtime()
        if compare:
            result = event_alpha_replay.compare_replay_policies(
                raw_events=raw_events,
                assets=assets,
                market_rows=market_rows,
                policies=_replay_policy_names(compare),
                alert_cfg=_event_alert_config_from_runtime(),
                priors_cfg=priors_cfg,
                llm_provider=llm_provider,
                llm_cfg=llm_cfg,
                router_cfg=router_cfg,
                router_threshold_variant=event_alpha_router.EventAlphaRouterConfig(
                    enabled=router_cfg.enabled,
                    include_suppressed=router_cfg.include_suppressed,
                    daily_digest_enabled=router_cfg.daily_digest_enabled,
                    instant_enabled=router_cfg.instant_enabled,
                    max_digest_items=router_cfg.max_digest_items,
                    max_high_priority_per_day=router_cfg.max_high_priority_per_day,
                    per_key_cooldown_hours=0,
                    alert_on_score_jump=True,
                    score_jump_threshold=max(1, router_cfg.score_jump_threshold // 2),
                    alert_on_new_independent_source=router_cfg.alert_on_new_independent_source,
                    alert_on_event_time_upgrade=router_cfg.alert_on_event_time_upgrade,
                    alert_on_derivatives_crowding_upgrade=router_cfg.alert_on_derivatives_crowding_upgrade,
                    alert_on_cluster_confidence_upgrade=router_cfg.alert_on_cluster_confidence_upgrade,
                ),
                profile_variant_router_cfg=_router_config_from_profile(replay_profile_alt),
                now=_event_research_now(),
            )
            print(event_alpha_replay.format_replay_comparison_report(result))
            return
        if priors:
            priors_cfg = event_alpha_priors.EventAlphaPriorsConfig(
                enabled=True,
                path=priors_cfg.path,
                min_multiplier=priors_cfg.min_multiplier,
                max_multiplier=priors_cfg.max_multiplier,
            )
        result = event_alpha_replay.replay_from_raw_events(
            raw_events=raw_events,
            assets=assets,
            market_rows=market_rows,
            alert_cfg=_event_alert_config_from_runtime(),
            priors_cfg=priors_cfg,
            llm_provider=llm_provider,
            llm_cfg=llm_cfg,
            router_cfg=router_cfg,
            now=_event_research_now(),
        )
        print(event_alpha_replay.format_replay_report(result))
        return
    alerts = event_alpha_replay.load_jsonl_rows(config.EVENT_ALPHA_ALERT_STORE_PATH)
    watchlist_rows = event_alpha_replay.load_jsonl_rows(config.EVENT_WATCHLIST_STATE_PATH)
    result = event_alpha_replay.replay_from_artifacts(
        alert_rows=alerts,
        watchlist_rows=watchlist_rows,
        priors_enabled=priors,
        llm_advisory=llm_advisory,
    )
    print(event_alpha_replay.format_replay_report(result))


def _router_config_from_profile(profile_name: str | None) -> event_alpha_router.EventAlphaRouterConfig | None:
    bind_scanner_globals(globals())
    if not profile_name:
        return None
    try:
        profile = event_alpha_profiles.get_profile(profile_name)
    except ValueError:
        return None
    overrides = dict(profile.config_overrides)
    current = _event_alpha_router_config_from_runtime()
    return event_alpha_router.EventAlphaRouterConfig(
        enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_ENABLED", current.enabled)),
        include_suppressed=current.include_suppressed,
        daily_digest_enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_DAILY_DIGEST_ENABLED", current.daily_digest_enabled)),
        instant_enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_INSTANT_ENABLED", current.instant_enabled)),
        max_digest_items=int(overrides.get("EVENT_ALPHA_ROUTER_MAX_DIGEST_ITEMS", current.max_digest_items)),
        validated_hypothesis_digest_enabled=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED",
                current.validated_hypothesis_digest_enabled,
            )
        ),
        max_validated_hypothesis_digest_items=int(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MAX_ITEMS",
                overrides.get(
                    "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MAX_ITEMS",
                    current.max_validated_hypothesis_digest_items,
                ),
            )
        ),
        validated_hypothesis_min_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE",
                current.validated_hypothesis_min_score,
            )
        ),
        validated_hypothesis_min_opportunity_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE",
                current.validated_hypothesis_min_opportunity_score,
            )
        ),
        validated_hypothesis_min_final_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE",
                current.validated_hypothesis_min_final_score,
            )
        ),
        validated_hypothesis_require_external_or_direct_event=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_EXTERNAL_OR_DIRECT_EVENT",
                current.validated_hypothesis_require_external_or_direct_event,
            )
        ),
        validated_hypothesis_require_impact_path=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH",
                current.validated_hypothesis_require_impact_path,
            )
        ),
        weak_validated_local_only=bool(
            overrides.get(
                "EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY",
                current.weak_validated_local_only,
            )
        ),
        allow_weak_path_with_market_confirmation=bool(
            overrides.get(
                "EVENT_ALPHA_ALLOW_WEAK_PATH_WITH_MARKET_CONFIRMATION",
                current.allow_weak_path_with_market_confirmation,
            )
        ),
        block_generic_cooccurrence_digest=bool(
            overrides.get(
                "EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST",
                current.block_generic_cooccurrence_digest,
            )
        ),
        max_high_priority_per_day=int(
            overrides.get("EVENT_ALPHA_ROUTER_MAX_HIGH_PRIORITY_PER_DAY", current.max_high_priority_per_day)
        ),
        per_key_cooldown_hours=float(overrides.get("EVENT_ALPHA_ROUTER_PER_KEY_COOLDOWN_HOURS", current.per_key_cooldown_hours)),
        alert_on_score_jump=bool(overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_SCORE_JUMP", current.alert_on_score_jump)),
        score_jump_threshold=int(overrides.get("EVENT_ALPHA_ROUTER_SCORE_JUMP_THRESHOLD", current.score_jump_threshold)),
        alert_on_new_independent_source=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_NEW_INDEPENDENT_SOURCE", current.alert_on_new_independent_source)
        ),
        alert_on_event_time_upgrade=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_EVENT_TIME_UPGRADE", current.alert_on_event_time_upgrade)
        ),
        alert_on_derivatives_crowding_upgrade=bool(
            overrides.get(
                "EVENT_ALPHA_ROUTER_ALERT_ON_DERIVATIVES_CROWDING_UPGRADE",
                current.alert_on_derivatives_crowding_upgrade,
            )
        ),
        alert_on_cluster_confidence_upgrade=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_CLUSTER_CONFIDENCE_UPGRADE", current.alert_on_cluster_confidence_upgrade)
        ),
    )


def _event_catalyst_search_provider(
    search_cfg: event_catalyst_search.EventCatalystSearchConfig,
):
    bind_scanner_globals(globals())
    provider_names = tuple(
        name.strip().lower()
        for name in (search_cfg.providers or (search_cfg.provider,))
        if name and name.strip()
    )
    providers = []
    warnings: list[str] = []
    for provider_name in provider_names or ("fixture",):
        if provider_name == "fixture":
            providers.append(event_catalyst_search.FixtureCatalystSearchProvider(
                path=config.EVENT_CATALYST_SEARCH_FIXTURE_PATH,
            ))
        elif provider_name == "gdelt":
            providers.append(event_catalyst_search.GdeltCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_GDELT_PATH,
                live_enabled=config.EVENT_DISCOVERY_GDELT_LIVE,
                base_url=config.EVENT_DISCOVERY_GDELT_BASE_URL,
                max_records=config.EVENT_DISCOVERY_GDELT_MAX_RECORDS,
                timeout=config.EVENT_DISCOVERY_GDELT_TIMEOUT,
            ))
        elif provider_name in {"rss", "project_rss", "project_blog_rss"}:
            providers.append(event_catalyst_search.ProjectRssCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
                live_enabled=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
                feed_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
                timeout=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT,
            ))
        elif provider_name == "cryptopanic":
            providers.append(event_catalyst_search.CryptoPanicCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
                live_enabled=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
                api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
                base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
                plan=config.EVENT_DISCOVERY_CRYPTOPANIC_PLAN,
                public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
                following=config.EVENT_DISCOVERY_CRYPTOPANIC_FOLLOWING,
                filter_name=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
                currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
                regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
                kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
                timeout=config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT,
                request_ledger_path=_cryptopanic_request_ledger_path(),
                profile=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
                artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
                weekly_request_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
                requests_per_run_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT,
                requests_per_day_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
                min_seconds_between_requests=config.EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS,
                max_pages_per_query=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY,
                max_currencies_per_request=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST,
            ))
        elif provider_name == "polymarket":
            providers.append(event_catalyst_search.PolymarketCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
                base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
                limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
                timeout=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT,
            ))
        elif provider_name == "coinmarketcal":
            providers.append(event_catalyst_search.EventProviderCatalystSearchProvider(
                lambda query: CoinMarketCalProvider(config.EVENT_DISCOVERY_COINMARKETCAL_PATH),
                name="coinmarketcal",
                filter_by_query=True,
                max_fetches_per_search=1,
            ))
        elif provider_name == "tokenomist":
            providers.append(event_catalyst_search.EventProviderCatalystSearchProvider(
                lambda query: TokenomistProvider(config.EVENT_DISCOVERY_TOKENOMIST_PATH),
                name="tokenomist",
                filter_by_query=True,
                max_fetches_per_search=1,
            ))
        else:
            warnings.append(provider_name)
    if warnings:
        print(
            "Unknown event catalyst-search provider(s): "
            f"{', '.join(warnings)}. Known: fixture, gdelt, rss, cryptopanic, polymarket, coinmarketcal, tokenomist."
        )
    if not providers:
        return None
    health_cfg = _event_provider_health_config_from_runtime()
    providers = [
        provider
        if str(getattr(provider, "name", "")).lower() == "fixture"
        else event_provider_health.HealthCheckedProvider(provider, cfg=health_cfg)
        for provider in providers
    ]
    if len(providers) == 1:
        return providers[0]
    return event_catalyst_search.CompositeCatalystSearchProvider(providers)


def _event_evidence_acquisition_providers_from_runtime(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
):
    """Return source-pack provider dispatch for evidence acquisition."""
    bind_scanner_globals(globals())
    providers: dict[str, object | None] = {}
    fixture_provider = event_catalyst_search.FixtureCatalystSearchProvider(
        path=config.EVENT_CATALYST_SEARCH_FIXTURE_PATH,
    )
    if cfg.fixture_only:
        for key in (
            "default",
            "fixture",
            "cryptopanic",
            "project_blog_rss",
            "rss",
            "polymarket",
            "official_exchange",
            "binance_announcements",
            "bybit_announcements",
            "coinmarketcal",
            "tokenomist",
            "coinalyze",
            "sports_fixtures",
        ):
            providers[key] = fixture_provider
        return providers

    providers["default"] = fixture_provider
    providers["fixture"] = fixture_provider
    providers["cryptopanic"] = event_catalyst_search.CryptoPanicCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        live_enabled=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        plan=config.EVENT_DISCOVERY_CRYPTOPANIC_PLAN,
        public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
        following=config.EVENT_DISCOVERY_CRYPTOPANIC_FOLLOWING,
        filter_name=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
        currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
        regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
        kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
        timeout=min(config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT, cfg.timeout_seconds),
        request_ledger_path=_cryptopanic_request_ledger_path(),
        profile=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        weekly_request_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        requests_per_run_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT,
        requests_per_day_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
        min_seconds_between_requests=config.EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS,
        max_pages_per_query=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY,
        max_currencies_per_request=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST,
    )
    providers["project_blog_rss"] = event_catalyst_search.ProjectRssCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        live_enabled=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        feed_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        timeout=min(config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT, cfg.timeout_seconds),
    )
    providers["rss"] = providers["project_blog_rss"]
    providers["polymarket"] = event_catalyst_search.PolymarketCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        live_enabled=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
        limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
        timeout=min(config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT, cfg.timeout_seconds),
    )
    official_exchange = event_catalyst_search.CompositeCatalystSearchProvider((
        event_catalyst_search.EventProviderCatalystSearchProvider(
            lambda query: BinanceAnnouncementProvider(
                config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
                api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
                api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
                ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
                topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
                recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
                listen_seconds=min(config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS, cfg.timeout_seconds),
                max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
            ),
            name="binance_announcements",
            filter_by_query=True,
            max_fetches_per_search=1,
        ),
        event_catalyst_search.EventProviderCatalystSearchProvider(
            lambda query: BybitAnnouncementProvider(
                config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
                base_url=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
                locale=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
                announcement_type=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
                limit=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT,
                timeout=min(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT, cfg.timeout_seconds),
            ),
            name="bybit_announcements",
            filter_by_query=True,
            max_fetches_per_search=1,
        ),
    ))
    providers["official_exchange"] = official_exchange
    providers["binance_announcements"] = official_exchange
    providers["bybit_announcements"] = official_exchange
    providers["coinmarketcal"] = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: CoinMarketCalProvider(config.EVENT_DISCOVERY_COINMARKETCAL_PATH),
        name="coinmarketcal",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    providers["tokenomist"] = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: TokenomistProvider(config.EVENT_DISCOVERY_TOKENOMIST_PATH),
        name="tokenomist",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    providers["coinalyze"] = fixture_provider
    providers["sports_fixtures"] = fixture_provider
    return providers


def _send_event_alpha_routed_digest(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    cfg: event_alerts.EventAlertConfig,
    *,
    now: datetime | None = None,
    profile: str | None = None,
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult | None = None,
    card_path_by_alert_id: dict[str, str | Path] | None = None,
    include_health_heartbeat: bool = False,
    clock_status: dict[str, object] | None = None,
    delivery_cfg: event_alpha_notification_delivery.NotificationDeliveryConfig | None = None,
    run_id: str | None = None,
    namespace: str | None = None,
    pause_state: event_alpha_notification_pause.EventAlphaNotificationPauseState | None = None,
    core_opportunity_rows: Iterable[Mapping[str, object]] = (),
) -> event_alpha_pipeline.EventAlphaSendResult:
    bind_scanner_globals(globals())
    all_decisions = list(decisions)
    alertable = [decision for decision in all_decisions if decision.alertable]
    storage = Storage(config.DB_PATH)
    try:
        now = now or datetime.now(timezone.utc)
        notif_cfg = _event_alpha_notification_config_from_runtime(profile)
        notif_cfg = replace(notif_cfg, enabled=cfg.enabled, mode=cfg.mode)
        if not alertable and not include_health_heartbeat and not notif_cfg.exploratory_digest_enabled:
            print("Event Alpha routed alert sending skipped: no router-approved escalations.")
            return event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=False,
                block_reason="no router-approved escalations",
            )
        clock_blocker = _event_alpha_notify_fixed_clock_blocker(clock_status or _event_clock_status())
        if clock_blocker:
            plan = event_alpha_notifications.build_notification_plan(
                all_decisions,
                storage=storage,
                cfg=notif_cfg,
                now=now,
                include_health_heartbeat=include_health_heartbeat,
                core_opportunity_rows=core_opportunity_rows,
            )
            result = event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=False,
                items_attempted=plan.would_send_count,
                items_delivered=0,
                block_reason=clock_blocker,
                lane_items_attempted=plan.lane_counts,
                lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
                would_send_items=plan.would_send_count,
                heartbeat_due=plan.heartbeat_due,
                cooldown_blocks=dict(plan.blocked_by_lane),
                notification_scope=plan.notification_scope,
                notification_scope_value=plan.scope_value,
                research_review_digest_enabled=notif_cfg.research_review_digest_enabled,
                research_review_digest_candidates=len(plan.research_review_items),
                research_review_digest_would_send=plan.lane_counts.get(
                    event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
                    0,
                ),
                research_review_digest_sent=0,
                research_review_digest_block_reason=plan.blocked_by_lane.get(
                    event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
                ),
            )
            print(f"Event Alpha routed notifications would send {result.would_send_items} item(s); blocked: {clock_blocker}.")
            return result
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
        result = event_alpha_notifications.send_notifications(
            all_decisions,
            storage=storage,
            cfg=notif_cfg,
            now=now,
            profile=profile,
            pipeline_result=pipeline_result,
            card_path_by_alert_id=card_path_by_alert_id,
            core_opportunity_rows=core_opportunity_rows,
            include_health_heartbeat=include_health_heartbeat,
            delivery_cfg=delivery_cfg,
            run_id=run_id,
            namespace=namespace,
            pause_state=pause_state,
            send_fn=lambda message: send_telegram_structured(
                message,
                parse_mode="HTML",
                chat_ids=recipients,
            ),
        )
        if result.attempted and result.success:
            print(
                "Event Alpha routed Telegram notification(s) sent: "
                f"{result.items_delivered}/{result.items_attempted} item(s)."
            )
        elif result.attempted:
            print(
                "Event Alpha routed Telegram notification(s) attempted but not fully delivered: "
                f"{result.block_reason or 'unknown'}."
            )
        elif result.would_send_items:
            print(
                "Event Alpha routed notifications would send "
                f"{result.would_send_items} item(s); blocked: {result.block_reason or 'not due'}."
            )
        elif not alertable and not include_health_heartbeat:
            print("Event Alpha routed alert sending skipped: no router-approved escalations.")
        else:
            print(f"Event Alpha routed alert sending held: {result.block_reason or 'no due notifications'}.")
        return result
    finally:
        storage.close()


def _write_event_fade_review_bundle(
    *,
    source_rows: list[dict[str, Any]],
    sample_path: str,
    out_dir: str,
    limit: int | None,
    prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    overwrite_outcomes: bool,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    bind_scanner_globals(globals())
    bundle_dir = Path(out_dir).expanduser()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_sample = event_discovery.write_validation_sample(
        source_rows,
        bundle_dir / "validation_sample.jsonl",
    )
    review_rows = source_rows
    effective_prices_path = prices_path
    price_export_result: event_price_history.EventFadeOutcomePriceExportResult | None = None
    if auto_export_prices and not effective_prices_path:
        price_export_result = event_price_history.export_outcome_price_fixture(
            source_rows,
            bundle_dir / "outcome_prices.json",
            days=price_days,
            fixture_dir=price_fixture_dir,
            cache_dir=config.BACKTEST_CACHE_DIR,
            refresh_cache=refresh_price_cache,
            interval=price_interval,
        )
        effective_prices_path = str(price_export_result.out_path)

    fill_summary = "No price fixture supplied; outcome fields were not filled."
    fill_result: event_validation.ValidationOutcomeFillResult | None = None
    outcome_sample: Path | None = None
    if effective_prices_path:
        prices = event_validation.load_outcome_price_fixture(effective_prices_path)
        fill_result = event_validation.fill_validation_outcomes(
            source_rows,
            prices,
            overwrite=overwrite_outcomes,
        )
        review_rows = fill_result.rows
        outcome_sample = event_discovery.write_validation_sample(
            review_rows,
            bundle_dir / "validation_sample_with_outcomes.jsonl",
        )
        fill_summary = (
            f"Filled {fill_result.filled_rows}/{fill_result.triggered_rows} triggered row(s); "
            f"missing_history={fill_result.missing_history_rows}, "
            f"insufficient_history={fill_result.insufficient_history_rows}, "
            f"skipped_existing={fill_result.skipped_existing_rows}."
        )

    queue = event_validation.build_labeling_queue(review_rows, limit=limit)
    review = event_validation.review_validation_sample(review_rows)
    sample_summary = _event_fade_review_sample_summary(review_rows)
    template_rows = event_validation.build_review_template_rows(review_rows, limit=limit)
    balanced_template_rows = event_validation.build_balanced_review_template_rows(review_rows)
    bundle_warnings = tuple([_empty_review_bundle_message(sample_path)] if not review_rows else [])

    queue_path = bundle_dir / "labeling_queue.txt"
    packet_path = bundle_dir / "review_packet.md"
    balanced_packet_path = bundle_dir / "review_packet_balanced.md"
    template_path = bundle_dir / "review_template.csv"
    balanced_template_path = bundle_dir / "review_template_balanced.csv"
    report_path = bundle_dir / "review_report.txt"
    guide_path = bundle_dir / "review_guide.md"
    manifest_path = bundle_dir / "manifest.json"
    readme_path = bundle_dir / "README.md"

    queue_path.write_text(event_validation.format_labeling_queue(queue) + "\n", encoding="utf-8")
    packet_path.write_text(event_validation.format_review_packet(review_rows, limit=limit) + "\n", encoding="utf-8")
    balanced_packet_path.write_text(
        event_validation.format_balanced_review_packet(review_rows) + "\n",
        encoding="utf-8",
    )
    template_path.write_text(event_validation.format_review_template_csv(template_rows), encoding="utf-8")
    balanced_template_path.write_text(
        event_validation.format_review_template_csv(balanced_template_rows),
        encoding="utf-8",
    )
    report_path.write_text(event_validation.format_validation_review(review) + "\n", encoding="utf-8")
    guide_path.write_text(_event_fade_review_guide(), encoding="utf-8")
    manifest = _event_fade_review_bundle_manifest(
        sample_path=sample_path,
        prices_path=prices_path,
        overwrite_outcomes=overwrite_outcomes,
        copied_sample=copied_sample,
        price_export=price_export_result,
        outcome_sample=outcome_sample,
        queue_path=queue_path,
        packet_path=packet_path,
        balanced_packet_path=balanced_packet_path,
        template_path=template_path,
        balanced_template_path=balanced_template_path,
        balanced_template_rows=len(balanced_template_rows),
        report_path=report_path,
        guide_path=guide_path,
        readme_path=readme_path,
        source_rows=len(source_rows),
        review_rows=len(review_rows),
        queue=queue,
        review=review,
        sample_summary=sample_summary,
        limit=limit,
        fill_summary=fill_summary,
        fill_result=fill_result,
        effective_prices_path=effective_prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        warnings=bundle_warnings,
        generated_at=generated_at,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        _event_fade_review_bundle_readme(
            sample_path=sample_path,
            copied_sample=copied_sample,
            price_export=price_export_result,
            outcome_sample=outcome_sample,
            queue_path=queue_path,
            packet_path=packet_path,
            balanced_packet_path=balanced_packet_path,
            template_path=template_path,
            balanced_template_path=balanced_template_path,
            report_path=report_path,
            guide_path=guide_path,
            manifest_path=manifest_path,
            rows=len(review_rows),
            queue=queue,
            review=review,
            sample_summary=sample_summary,
            fill_summary=fill_summary,
            auto_export_prices=auto_export_prices,
            reviewed_path=reviewed_path,
            review_merge=review_merge,
            warnings=bundle_warnings,
        ),
        encoding="utf-8",
    )
    return {
        "bundle_dir": bundle_dir,
        "price_export": price_export_result,
        "outcome_sample": outcome_sample,
        "queue": queue,
        "rows": len(review_rows),
    }


def _event_fade_review_bundle_manifest(
    *,
    sample_path: str,
    prices_path: str | None,
    overwrite_outcomes: bool,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    balanced_template_rows: int,
    report_path: Path,
    guide_path: Path,
    readme_path: Path,
    source_rows: int,
    review_rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    limit: int | None,
    fill_summary: str,
    fill_result: event_validation.ValidationOutcomeFillResult | None,
    effective_prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    bind_scanner_globals(globals())
    files = {
        "readme": readme_path.name,
        "validation_sample": copied_sample.name,
        "labeling_queue": queue_path.name,
        "review_packet": packet_path.name,
        "review_packet_balanced": balanced_packet_path.name,
        "review_template": template_path.name,
        "review_template_balanced": balanced_template_path.name,
        "review_report": report_path.name,
        "review_guide": guide_path.name,
    }
    if price_export is not None:
        files["outcome_prices"] = price_export.out_path.name
    if outcome_sample is not None:
        files["validation_sample_with_outcomes"] = outcome_sample.name
    outcome_fill: dict[str, Any] = {
        "enabled": effective_prices_path is not None,
        "prices_path": effective_prices_path,
        "overwrite_outcomes": overwrite_outcomes,
        "summary": fill_summary,
    }
    if fill_result is not None:
        outcome_fill.update({
            "sample_rows": fill_result.sample_rows,
            "triggered_rows": fill_result.triggered_rows,
            "filled_rows": fill_result.filled_rows,
            "missing_history_rows": fill_result.missing_history_rows,
            "insufficient_history_rows": fill_result.insufficient_history_rows,
            "skipped_existing_rows": fill_result.skipped_existing_rows,
        })

    return {
        "bundle_version": 1,
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "source": {
            "sample_path": sample_path,
            "source_rows": source_rows,
            "review_rows": review_rows,
        },
        "warnings": list(warnings),
        "sample_summary": sample_summary,
        "files": files,
        "queue": {
            "limit": limit,
            "needed_rows": queue.needed_rows,
            "shown_rows": queue.shown_rows,
            "total_rows": queue.total_rows,
        },
        "balanced_review_template": {
            "rows": balanced_template_rows,
            "proxy_limit": event_validation.DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
            "control_limit": event_validation.DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
        },
        "review": {
            "promotion_ready": review.promotion_ready,
            "promotion_blockers": list(review.promotion_blockers),
            "reviewed_rows": review.reviewed_rows,
            "reviewed_proxy_candidates": review.reviewed_proxy_candidates,
            "reviewed_negative_controls": review.reviewed_negative_controls,
            "reviewed_proxy_event_types": review.reviewed_proxy_event_types,
            "min_proxy_event_types": review.min_proxy_event_types,
            "reviewed_proxy_source_providers": review.reviewed_proxy_source_providers,
            "min_proxy_source_providers": review.min_proxy_source_providers,
            "reviewed_proxy_source_origins": review.reviewed_proxy_source_origins,
            "triggered_reviewed": review.triggered_reviewed,
            "triggered_btc_risk_buckets": review.triggered_btc_risk_buckets,
            "min_trigger_btc_risk_buckets": review.min_trigger_btc_risk_buckets,
            "low_confidence_trigger_event_time_rows": review.low_confidence_trigger_event_time_rows,
            "missing_trigger_outcome_rows": review.missing_trigger_outcome_rows,
            "missing_event_time_baseline_rows": review.missing_event_time_baseline_rows,
            "missing_review_provenance_rows": review.missing_review_provenance_rows,
            "point_in_time_violation_rows": review.point_in_time_violation_rows,
            "post_decision_source_rows": review.post_decision_source_rows,
            "missing_source_timing_rows": review.missing_source_timing_rows,
            "next_sample_work": list(event_validation.validation_review_next_steps(review)),
        },
        "price_export": _event_fade_review_price_export_manifest(
            auto_export_prices=auto_export_prices,
            explicit_prices_path=prices_path,
            price_days=price_days,
            price_fixture_dir=price_fixture_dir,
            price_interval=price_interval,
            refresh_price_cache=refresh_price_cache,
            result=price_export,
        ),
        "outcome_fill": outcome_fill,
        "review_merge": _event_fade_review_merge_manifest(reviewed_path, review_merge),
    }


def _event_fade_review_bundle_readme(
    *,
    sample_path: str,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    report_path: Path,
    guide_path: Path,
    manifest_path: Path,
    rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    fill_summary: str,
    auto_export_prices: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
) -> str:
    bind_scanner_globals(globals())
    price_line = (
        f"- `{price_export.out_path.name}`: bundle-local OHLCV price fixture"
        if price_export is not None
        else "- No bundle-local price fixture was exported."
    )
    outcome_line = (
        f"- `{outcome_sample.name}`: sample with locally filled trigger/baseline outcomes"
        if outcome_sample is not None
        else "- No outcome-filled sample was written."
    )
    if review_merge is None:
        merge_line = "- No prior reviewed sample was merged."
    else:
        merge_line = (
            f"- Prior reviewed sample `{reviewed_path}` merged: "
            f"{review_merge.matched_rows} matched, "
            f"{review_merge.evidence_changed_rows} evidence-changed, "
            f"{review_merge.copied_fields} copied field(s)."
        )
    warning_lines = ["Warnings:", *(f"- {warning}" for warning in warnings), ""] if warnings else []
    return "\n".join([
        "# Event-Fade Validation Review Bundle",
        "",
        "Research-only: no alerts, live DB writes, paper trades, or orders.",
        "",
        f"Input sample: `{sample_path}`",
        f"Rows: {rows}",
        f"Rows needing labels/status/outcomes: {queue.needed_rows}",
        f"Rows shown in queue/template/packet: {queue.shown_rows}",
        "",
        "Sample summary:",
        *_event_fade_review_bundle_summary_lines(sample_summary),
        "",
        "Review gates:",
        *_event_fade_review_gate_lines(review),
        *warning_lines,
        f"Auto price export: {'yes' if auto_export_prices else 'no'}",
        f"Outcome fill: {fill_summary}",
        "Review merge:",
        merge_line,
        "",
        "Files:",
        f"- `{copied_sample.name}`: copied source validation sample",
        price_line,
        outcome_line,
        f"- `{queue_path.name}`: prioritized queue for missing labels/status/outcomes",
        f"- `{packet_path.name}`: human-readable evidence packet",
        f"- `{balanced_packet_path.name}`: human-readable evidence packet matching the balanced sidecar",
        f"- `{template_path.name}`: compact editable CSV sidecar",
        f"- `{balanced_template_path.name}`: gate-balanced editable CSV sidecar with proxy candidates and negative controls",
        f"- `{guide_path.name}`: label taxonomy, review provenance, and event-time review rules",
        f"- `{report_path.name}`: current review metrics and promotion blockers",
        f"- `{manifest_path.name}`: machine-readable bundle provenance and counts",
        "",
        "Suggested workflow:",
        "1. Read `review_guide.md` for label and timing rules.",
        "2. Read `review_packet_balanced.md` for evidence matching `review_template_balanced.csv`; use `review_packet.md` for strict priority rows.",
        "3. For fastest promotion-gate coverage, edit `review_template_balanced.csv`; for strict priority order, edit `review_template.csv`.",
        "4. Fill `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, any human event-time confirmation, and any missing outcomes. Use `external_asset`, `primary_source_url`, `source_search_url`, `source_date_hint`, `source_providers`, `primary_raw_title`, `review_prompt`, and `event_time_review_hint` as reviewer aids only.",
        "5. Dry-check the edited sidecar with `main.py --event-fade-check-review-template SAMPLE TEMPLATE`.",
        "6. Apply the checked sidecar with `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`.",
        "7. Run `main.py --event-fade-review-sample OUT` to inspect coverage and blockers.",
        "",
    ])


def _event_fade_review_guide() -> str:
    bind_scanner_globals(globals())
    return "\n".join([
        "# Event-Fade Review Guide",
        "",
        "Research-only: this guide is for labeling validation artifacts. It does not promote alerts, paper trades, or execution.",
        "",
        "## Label Rules",
        "",
        "Use exactly one `human_label` value per reviewed row:",
        "",
        "- `valid_proxy_fade`: the crypto asset is a true proxy instrument for a dated external catalyst, not the direct beneficiary, and the evidence would have been knowable before the decision time.",
        "- `false_positive`: the row looked proxy-like to the system but manual review says it is not a valid proxy-fade setup.",
        "- `direct_event`: the catalyst directly changes the asset's own listing, supply, emissions, protocol, utility, or structural demand.",
        "- `ambiguous`: the evidence is too weak, ticker-only, generic market chatter, or cannot be resolved to a clear proxy/direct relationship.",
        "",
        "Set `review_status=reviewed` only after checking the source evidence. Rows with labels but without `review_status=reviewed` do not count as reviewed evidence.",
        "",
        "Fill `reviewed_by` with the reviewer name or handle and `reviewed_at` with an ISO timestamp. These fields make copied labels auditable across refreshed samples, and missing provenance blocks promotion.",
        "",
        "## Proxy Criteria",
        "",
        "A valid proxy-fade candidate should have all of these:",
        "",
        "- a dated external catalyst or expiry",
        "- a crypto asset used as synthetic exposure, attention exposure, fan exposure, or prediction-market-style proxy",
        "- `is_direct_beneficiary=false`",
        "- source evidence available before the decision time",
        "",
        "Examples that should usually be `direct_event`: BTC/BTC ETF, ETH/ETH ETF, token unlocks, exchange listings, airdrops, TGEs, mainnet launches, and protocol upgrades.",
        "",
        "## Event-Time Confirmation",
        "",
        "If the machine `event_time` is blank, weak, or inferred from text, fill the separate human fields instead of editing `event_time`:",
        "",
        "- `human_event_time`: ISO timestamp for the catalyst, preferably UTC with an offset, for example `2026-06-20T13:30:00+00:00`",
        "- `human_event_time_source`: URL or title proving that timestamp",
        "- `human_event_time_confidence`: reviewer confidence from `0.0` to `1.0`; use `0.80` or higher only for explicit source evidence",
        "- `human_event_time_notes`: short note explaining how the timestamp was confirmed",
        "",
        "Validation metrics may use high-confidence `human_event_time` for review-only timing checks and event-time baselines, but it remains separate from the machine-discovered `event_time`.",
        "",
        "## Review Template Helper Columns",
        "",
        "`review_template.csv` and `review_template_balanced.csv` include reviewer-only helper columns:",
        "",
        "- `external_asset`: machine-extracted external catalyst identity; verify it against the source before using `valid_proxy_fade`",
        "- `primary_source_url`: first source URL to open for the row",
        "- `primary_source_origin`: first normalized publisher/origin",
        "- `primary_raw_title`: first raw source title",
        "- `source_search_url`: title/publisher search link for finding the canonical article when the primary source is a feed or Google News wrapper",
        "- `source_date_hint`: date-like phrases found in the source title or event name, such as a date range, event year, `today`, or `tonight`; use it only as a cue to verify explicit source timing",
        "- `source_providers`: discovery provider(s) that supplied the row, such as `project_blog_rss`, `gdelt`, or `prediction_market_events`",
        "- `review_prompt`: compact instruction for the queued review category",
        "- `event_time_review_hint`: whether the event time is missing, inferred/weak, or explicit/high-confidence",
        "",
        "These helper columns are not copied back into validation samples and do not affect evidence matching. The fields that count are still `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, `human_event_time*`, and required outcome fields.",
        "",
        "`review_template.csv` follows strict labeling-queue priority. `review_template_balanced.csv` is better for building the validation sample because it includes triggered rows, proxy candidates, and direct/ambiguous negative controls in one sidecar.",
        "Run `main.py --event-fade-check-review-template SAMPLE TEMPLATE` before applying an edited sidecar; it catches changed evidence, unmatched rows, missing provenance, unknown labels, missing outcomes, and valid proxy labels without explicit catalyst timing.",
        "",
        "## Outcome Fields",
        "",
        "For reviewed `SHORT_TRIGGERED` rows, fill or verify:",
        "",
        "- `max_adverse_excursion`",
        "- `max_favorable_excursion`",
        "- `post_event_return_72h`",
        "- `event_time_post_event_return_72h`",
        "",
        "Prefer locally filled 1h outcomes when available; daily outcomes are coarse and can hide intraday squeeze risk.",
        "",
        "## Promotion Reminder",
        "",
        "Do not promote event fade beyond local reports until the review report clears the proxy/control/trigger sample-size, source-diversity, timing, and outcome-quality gates.",
        "",
    ])
