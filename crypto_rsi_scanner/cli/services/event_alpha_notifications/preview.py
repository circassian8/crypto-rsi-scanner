"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (preview)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping
from .bindings import *  # noqa: F403

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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
