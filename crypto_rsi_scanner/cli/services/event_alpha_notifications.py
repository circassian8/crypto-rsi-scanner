"""Event Alpha Notifications.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible during the refactor.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, MutableMapping


_SERVICE_FUNCTION_NAMES = (
    'bind_scanner_globals',
    '_event_alpha_notify_cycle_body',
    '_scanner_call',
    'event_alpha_notify_preview',
    'event_alpha_notify_preview_from_artifacts',
    'event_alpha_notify_go_no_go',
    'event_alpha_export_notification_pack',
    'event_alpha_notify_fixture_smoke',
    'event_alpha_send_readiness_report',
    'event_alpha_telegram_final_check_report',
    'event_alpha_notification_deliveries_report',
    'event_alpha_notification_runs_report',
)


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module


def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from ... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)


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


def event_alpha_send_readiness_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_send_readiness_report", *args, **kwargs)


def event_alpha_telegram_final_check_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_telegram_final_check_report", *args, **kwargs)


def event_alpha_notification_deliveries_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_notification_deliveries_report", *args, **kwargs)


def event_alpha_notification_runs_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_notification_runs_report", *args, **kwargs)


__all__ = tuple(name for name in _SERVICE_FUNCTION_NAMES if name != 'bind_scanner_globals')
