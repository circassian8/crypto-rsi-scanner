"""Alerts commands from the scanner service."""

from __future__ import annotations

from .runtime import *

def event_alpha_notify_cycle(
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
    ignore_provider_backoff: bool = False,
) -> None:
    """Run a day-1 Event Alpha notification cycle, guaranteeing lock release.

    The cycle body acquires the per-profile run lock and stores it in
    ``lock_holder``; this wrapper releases it in a ``finally`` so any exception
    in card writing, sending, snapshot/ledger writes, or report formatting still
    releases the lock (best-effort).
    """
    lock_holder: dict[str, object] = {}
    try:
        _event_alpha_notify_cycle_body(
            verbose=verbose,
            with_llm=with_llm,
            send=send,
            event_now=event_now,
            profile_name=profile_name,
            ignore_provider_backoff=ignore_provider_backoff,
            lock_holder=lock_holder,
        )
    finally:
        mutation_lock = lock_holder.get("mutation_lock")
        if mutation_lock is not None:
            event_alpha_run_lock.release_run_lock(mutation_lock)
        run_lock = lock_holder.get("lock")
        if run_lock is not None:
            event_alpha_run_lock.release_run_lock(run_lock)

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_alpha_notify_cycle_body(verbose=verbose, with_llm=with_llm, send=send, event_now=event_now, profile_name=profile_name, ignore_provider_backoff=ignore_provider_backoff, lock_holder=lock_holder)

def _record_skipped_notification_run(
    profile: str,
    *,
    run_id: str,
    run_mode: str,
    artifact_namespace: str | None,
    started_at: datetime,
) -> dict[str, object]:
    """Record a research-only notification-run row for a cycle skipped by an active lock."""
    skipped = SimpleNamespace(
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        notification_skipped_due_to_active_lock=True,
        notification_lock_acquired=False,
        warnings=("notification_cycle_skipped_active_lock",),
        cycle_completed=False,
    )
    return event_alpha_notification_runs.append_notification_run(
        skipped,
        cfg=_event_alpha_notification_runs_config_from_runtime(),
        profile=profile,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
    )

def event_alpha_notify_preview(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_notify_preview(verbose, profile_name=profile_name)

def event_alpha_notify_preview_from_artifacts(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_notify_preview_from_artifacts(verbose, profile_name=profile_name, artifact_namespace=artifact_namespace)

def _event_alpha_preview_summary_result(
    latest_run: Mapping[str, object],
    *,
    plan: event_alpha_notifications.EventAlphaNotificationPlan,
    profile: str,
) -> dict[str, object]:
    """Return a preview-safe run summary with canonical counter scopes."""
    data = dict(latest_run or {})
    data["profile"] = data.get("profile") or profile
    data["cycle_completed"] = bool(data.get("cycle_completed", bool(latest_run)))
    data["preview_rendered_items"] = (
        sum(_event_alpha_preview_int(value) for value in plan.lane_counts.values())
        + int(bool(plan.heartbeat_due))
    )
    counters = event_alpha_run_counters.canonical_run_counters(data)
    send_state = event_alpha_run_counters.canonical_send_state(data)
    data["counter_schema_version"] = event_alpha_run_counters.COUNTER_SCHEMA_VERSION
    data.update(counters)
    data.update(event_alpha_run_counters.deprecated_counter_aliases(counters))
    data.update(send_state)
    data["send_lane_items_attempted"] = dict(plan.lane_counts)
    data["send_lane_items_delivered"] = {lane: 0 for lane in event_alpha_notifications.LANES}
    data["send_would_send_items"] = int(plan.would_send_count or 0)
    data["send_heartbeat_due"] = bool(plan.heartbeat_due)
    data["send_heartbeat_sent"] = False
    data.setdefault("artifact_doctor_status", "not_run")
    return data

def _event_alpha_preview_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def event_alpha_notify_go_no_go(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_notify_go_no_go(verbose, profile_name=profile_name, artifact_namespace=artifact_namespace, include_test_artifacts=include_test_artifacts, include_api_artifacts=include_api_artifacts)

def event_alpha_environment_doctor_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print scheduled notification environment readiness for one profile."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    result = event_alpha_environment_doctor.build_environment_doctor(
        profile=profile,
        context=context,
        provider_status=event_provider_status.build_event_discovery_provider_status(config),
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        lock_path=event_alpha_run_lock.lock_path_for_context(context),
        delivery_ledger_path=event_alpha_notification_delivery.deliveries_path_for_context(context),
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
    print(event_alpha_environment_doctor.format_environment_doctor(result))

def event_alpha_pause_notifications(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    reason: str | None = None,
) -> None:
    """Write a namespace-scoped notification pause file."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", None)
    except ValueError as exc:
        print(str(exc))
        return
    state = event_alpha_notification_pause.write_pause_state(
        context,
        reason=reason or "operator pause",
        now=datetime.now(timezone.utc),
    )
    print(event_alpha_notification_pause.format_pause_state(state, action="pause"))

def event_alpha_resume_notifications(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    confirm: bool = False,
) -> None:
    """Clear the namespace-scoped notification pause file when confirmed."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", None)
    except ValueError as exc:
        print(str(exc))
        return
    if not confirm:
        state = _event_alpha_notification_pause_state(context)
        print(event_alpha_notification_pause.format_pause_state(state, action="resume-refused"))
        print("Resume refused: pass --confirm to clear the pause file.")
        return
    state = event_alpha_notification_pause.clear_pause_state(context, confirm=True)
    print(event_alpha_notification_pause.format_pause_state(state, action="resume"))

def _event_alpha_health_guard_status_for_context(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    profile_name: str | None,
) -> str:
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=100,
        latest_alerts=True,
    )
    result = event_alpha_health_guard.evaluate_health_guard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(
            max_run_age_hours=config.EVENT_ALPHA_MAX_RUN_AGE_HOURS,
            max_success_age_hours=config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS,
            require_profile=profile_name or config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE,
        ),
        artifact_namespace=context.artifact_namespace,
        now=_event_research_now(),
    )
    return result.status

def event_alpha_scheduler_status_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print scheduler-facing run freshness, lock, and target status."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = _event_alpha_report_context(profile.name, None)
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=100)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    make_text = (config.DATA_DIR / "Makefile").read_text(encoding="utf-8") if (config.DATA_DIR / "Makefile").exists() else ""
    target_exists = event_alpha_scheduler.scheduled_command(profile.name).split()[-1] + ":" in make_text
    result = event_alpha_scheduler.build_scheduler_status(
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        run_rows=runs.rows,
        delivery_rows=deliveries,
        lock_status=lock_status,
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        health_guard_status=_event_alpha_health_guard_status_for_context(context=context, profile_name=profile.name),
        scheduled_target_exists=target_exists,
        now=datetime.now(timezone.utc),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_scheduler.format_scheduler_status(result))

def event_alpha_generate_launchd(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    out: str | None = None,
) -> None:
    """Write a dry-run launchd plist template for scheduled notification runs."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    text = event_alpha_scheduler.generate_launchd_plist(
        profile=profile.name,
        repo_path=config.DATA_DIR,
        python_path=sys.executable,
    )
    if out:
        path = Path(out).expanduser()
        if not path.is_absolute():
            path = config.DATA_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Event Alpha launchd template written: {path}")
    else:
        print(text.rstrip())

def event_alpha_notification_slo_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
) -> None:
    """Print SLO-style notification freshness and delivery health."""
    _ = include_diagnostics
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    runs = event_alpha_notification_runs.load_notification_runs(context.notification_runs_path, limit=100)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    result = event_alpha_notification_slo.build_slo_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        now=datetime.now(timezone.utc),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_slo.format_slo_report(result))

def event_alpha_export_notification_pack(
    out: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_export_notification_pack(out, verbose=verbose, profile_name=profile_name, artifact_namespace=artifact_namespace)

def _event_alpha_llm_budget_status() -> str:
    return (
        f"provider={config.EVENT_LLM_PROVIDER}/{config.EVENT_LLM_EXTRACTOR_PROVIDER} "
        f"max_candidates={config.EVENT_LLM_MAX_CANDIDATES_PER_RUN} "
        f"max_extract_events={config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN} "
        f"max_run={config.EVENT_LLM_MAX_CALLS_PER_RUN} max_day={config.EVENT_LLM_MAX_CALLS_PER_DAY} "
        f"parallel={config.EVENT_LLM_MAX_PARALLEL_CALLS} "
        f"max_cost_day={config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY:g} "
        f"cache_ttl_hours={config.EVENT_LLM_CACHE_TTL_HOURS:g}"
    )

def event_alpha_notification_checklist_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print day-1 notification startup readiness without sending."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    preflight = event_alpha_preflight.run_preflight(
        profile_name=profile.name,
        context=context,
        cfg=config,
        provider_status=provider_status,
        send_requested=True,
        clock_status=clock_status,
    )
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
        routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile.name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=250,
        latest_alerts=False,
    )
    cards_dir = context.research_cards_dir
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=artifacts["core_opportunities"].rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        market_anomaly_rows=event_market_anomaly_scanner.load_market_anomaly_rows(context.namespace_dir),
        official_exchange_candidate_rows=event_official_exchange.load_official_listing_candidates(context.namespace_dir),
        scheduled_catalyst_rows=event_scheduled_catalysts.load_scheduled_catalysts(context.namespace_dir),
        unlock_candidate_rows=event_scheduled_catalysts.load_unlock_candidates(context.namespace_dir),
        derivatives_state_rows=event_derivatives_crowding.load_derivatives_state(context.namespace_dir),
        fade_review_candidate_rows=event_derivatives_crowding.load_derivatives_candidates(context.namespace_dir),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        llm_budget_rows=artifacts["budget_rows"],
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        artifact_namespace_dir=context.namespace_dir,
        inspected_alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
        outcomes_path=context.outcomes_path,
        integrated_candidate_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME
        ),
        integrated_outcomes_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        ),
        notification_preview_path=(
            event_alpha_notification_delivery.notification_preview_path_for_context(context)
        ),
        run_ledger_path=context.run_ledger_path,
        strict=False,
        evaluated_at=now,
    )
    result = event_alpha_notification_checklist.build_notification_checklist(
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        provider_status=provider_status,
        provider_health_rows=artifacts["provider_rows"],
        plan=plan,
        llm_budget_status=_event_alpha_llm_budget_status(),
        card_auto_write=bool(config.EVENT_RESEARCH_CARDS_AUTO_WRITE),
        artifact_doctor_status=doctor.status,
        clock_status=clock_status,
        preflight_blockers=preflight.blockers,
        preflight_warnings=preflight.warnings,
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
    )
    print(event_alpha_notification_checklist.format_notification_checklist(result))

def event_alpha_send_test(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    ignore_notification_pause: bool = False,
) -> None:
    """Send one guarded research-only heartbeat without running the radar."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    if pause_state.paused and not ignore_notification_pause:
        print(f"Refusing Event Alpha test send: notifications paused ({pause_state.reason}).")
        return
    if not config.EVENT_ALERTS_ENABLED:
        print("Refusing Event Alpha test send: set RSI_EVENT_ALERTS_ENABLED=1 to opt in.")
        return
    if config.EVENT_ALERT_MODE != "research_only":
        print("Refusing Event Alpha test send: RSI_EVENT_ALERT_MODE must remain research_only.")
        return
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS):
        print("Refusing Event Alpha test send: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS are required.")
        return
    clock_blocker = _event_alpha_notify_fixed_clock_blocker(_event_clock_status())
    if clock_blocker:
        print(f"Refusing Event Alpha test send: {clock_blocker}.")
        return
    sent = send_telegram(
        event_alpha_notifications.format_health_heartbeat(profile=profile.name),
        parse_mode="HTML",
        chat_ids=config.TELEGRAM_CHAT_IDS,
    )
    if sent:
        print("Event Alpha research-only test heartbeat sent.")
    else:
        print("Event Alpha research-only test heartbeat was not delivered.")

def event_alpha_telegram_recipient_check_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Send a guarded one-message diagnostic to each Telegram recipient."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    storage = Storage(config.DB_PATH)
    try:
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
    finally:
        storage.close()
    result = event_alpha_telegram_recipient_check.run_recipient_check(
        recipients,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED and config.EVENT_ALERT_MODE == "research_only"),
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        profile=profile.name,
        send_one=lambda message, chat_id: send_telegram_structured(
            message,
            parse_mode=None,
            chat_ids=[chat_id],
        ),
    )
    print(event_alpha_telegram_recipient_check.format_recipient_check(result))

def _card_paths_by_alert_id(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    card_paths: Iterable[Path],
) -> dict[str, str]:
    by_stem = {Path(path).stem: str(path) for path in card_paths}
    out: dict[str, str] = {}
    for decision in decisions:
        path = by_stem.get(decision.card_id)
        if path is None:
            candidate = Path(config.EVENT_RESEARCH_CARDS_DIR) / f"{decision.card_id}.md"
            path = str(candidate)
        out[decision.alert_id] = path
    return out

class _FixtureNotificationStorage:
    def __init__(self) -> None:
        self.meta: dict[str, str] = {}

    def get_meta(self, key: str) -> str | None:
        return self.meta.get(key)

    def set_meta(self, key: str, value: str) -> None:
        self.meta[key] = value

def _write_fixture_alert_snapshot(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    entry: event_watchlist.EventWatchlistEntry,
    decision: event_alpha_router.EventAlphaRouteDecision,
    run_id: str,
    observed_at: datetime,
    core_row: Mapping[str, Any] | None = None,
) -> Path:
    path = context.alert_store_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    core = dict(core_row or {})
    score_components = dict(entry.latest_score_components)
    core_id = str(core.get("core_opportunity_id") or score_components.get("core_opportunity_id") or "").strip()
    if core_id:
        score_components.setdefault("core_opportunity_id", core_id)
    row = {
        "schema_version": event_alpha_alert_store.ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_at.isoformat()}|{entry.key}",
        "alert_key": entry.key,
        "alert_id": decision.alert_id,
        "card_id": decision.card_id,
        "cluster_id": entry.cluster_id,
        "observed_at": observed_at.isoformat(),
        "run_id": run_id,
        "profile": context.profile,
        "run_mode": context.run_mode,
        "artifact_namespace": context.artifact_namespace,
        "event_id": entry.event_id,
        "event_name": entry.latest_event_name,
        "event_type": "fixture_notification_smoke",
        "event_time": entry.event_time,
        "external_asset": entry.external_asset,
        "asset_coin_id": entry.coin_id,
        "asset_symbol": entry.symbol,
        "asset_name": entry.symbol,
        "relationship_type": entry.relationship_type,
        "asset_role": "proxy_instrument",
        "source": entry.latest_source,
        "source_count": entry.source_count,
        "tier": entry.latest_tier,
        "opportunity_score": entry.latest_score,
        "score_components": score_components,
        "playbook_type": entry.latest_playbook_type,
        "rule_playbook_type": entry.latest_rule_playbook_type,
        "effective_playbook_type": entry.latest_effective_playbook_type,
        "playbook_score": entry.latest_playbook_score,
        "playbook_action": entry.latest_playbook_action,
        "expected_direction": "review_only",
        "primary_horizon": "manual",
        "success_metric": "manual_feedback",
        "market_price": entry.latest_market_snapshot.get("price"),
        "return_24h_at_alert": entry.latest_market_snapshot.get("return_24h"),
        "volume_zscore_24h": entry.latest_market_snapshot.get("volume_zscore_24h"),
        "route": decision.route.value,
        "route_alertable": decision.alertable,
        "route_reason": decision.reason,
        "reason": decision.reason,
        "core_opportunity_id": core_id or None,
        "feedback_target": core_id or decision.alert_id,
        "feedback_target_type": "core_opportunity_id" if core_id else "alert_id",
        "final_opportunity_level": core.get("final_opportunity_level") or core.get("opportunity_level") or "high_priority",
        "opportunity_level": core.get("final_opportunity_level") or core.get("opportunity_level") or "high_priority",
        "opportunity_score_final": core.get("opportunity_score_final") or entry.latest_score,
        "final_route_after_quality_gate": core.get("final_route_after_quality_gate") or decision.route.value,
        "final_tier_after_quality_gate": core.get("final_tier_after_quality_gate") or decision.route.value,
        "alertable_after_quality_gate": bool(core.get("alertable_after_quality_gate", decision.alertable)),
        "final_state_after_quality_gate": core.get("final_state_after_quality_gate") or entry.state,
        "impact_path_type": core.get("impact_path_type") or entry.impact_path_type or entry.relationship_type,
        "candidate_role": core.get("candidate_role") or entry.candidate_role or "proxy_venue",
        "impact_path_strength": core.get("impact_path_strength") or entry.impact_path_strength or "strong",
        "source_class": core.get("source_class") or entry.source_class,
        "evidence_specificity": core.get("evidence_specificity") or entry.evidence_specificity,
        "evidence_quality_score": core.get("evidence_quality_score") or entry.evidence_quality_score,
        "market_confirmation_score": core.get("market_confirmation_score") if core.get("market_confirmation_score") is not None else entry.market_confirmation_score,
        "market_confirmation_level": core.get("market_confirmation_level") or entry.market_confirmation_level,
        "market_context_freshness_status": core.get("market_context_freshness_status") or entry.market_context_freshness_status,
        "market_context_age_hours": core.get("market_context_age_hours") if core.get("market_context_age_hours") is not None else 0,
        "market_context_stale": bool(core.get("market_context_stale", False)),
        "market_context_freshness_cap_applied": bool(core.get("market_context_freshness_cap_applied", False)),
        "evidence_acquisition_status": core.get("evidence_acquisition_status"),
        "acquisition_confirmation_status": core.get("acquisition_confirmation_status"),
        "accepted_evidence_count": (
            core.get("accepted_evidence_count")
            if core.get("accepted_evidence_count") is not None
            else core.get("evidence_acquisition_accepted_count")
        ),
        "source_pack": core.get("source_pack"),
        "opportunity_verdict_reasons": core.get("opportunity_verdict_reasons") or core.get("verdict_reason_codes") or ["fixture_notification_smoke"],
        "why_local_only": core.get("why_local_only") or ("not_local_only" if decision.alertable else "rejected_results_only_not_confirmation"),
        "why_not_watchlist": core.get("why_not_watchlist") or ("already_high_priority" if decision.alertable else "accepted_confirmation_missing"),
        "manual_verification_items": core.get("manual_verification_items") or ["review the local fixture card before acting"],
        "upgrade_requirements": core.get("upgrade_requirements") or [],
        "downgrade_warnings": core.get("downgrade_warnings") or ["conflicting_evidence"],
        "verify": ["fixture smoke confirms fake-sender notification plumbing only"],
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    return path

def event_alpha_notify_fixture_smoke(
    verbose: bool = False,
    *,
    event_now: str | datetime | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_notify_fixture_smoke(verbose, event_now=event_now)

def event_alpha_send_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print final read-only readiness before enabling real Event Alpha sends."""
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
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=500,
        latest_alerts=False,
    )
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    evaluation_now = _event_research_now()
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
        include_api_artifacts=include_api_artifacts,
        artifact_namespace_dir=context.namespace_dir,
        inspected_alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
        outcomes_path=context.outcomes_path,
        integrated_candidate_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME
        ),
        integrated_outcomes_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        ),
        notification_preview_path=(
            event_alpha_notification_delivery.notification_preview_path_for_context(context)
        ),
        run_ledger_path=context.run_ledger_path,
        strict=True,
        delivery_strict_scope="latest_run",
        evaluated_at=evaluation_now,
    )
    result = event_alpha_send_readiness.build_send_readiness(
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
        include_api_artifacts=include_api_artifacts,
        preview_path=event_alpha_notification_delivery.notification_preview_path_for_context(
            context
        ),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_send_readiness.format_send_readiness(result))

def event_alpha_telegram_final_check_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print a compact final no-send/send readiness summary for Telegram."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "notify_llm_deep",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1) from exc
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or context.profile
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=500,
        latest_alerts=False,
    )
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    evaluation_now = _event_research_now()
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
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        artifact_namespace_dir=context.namespace_dir,
        inspected_alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
        outcomes_path=context.outcomes_path,
        integrated_candidate_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME
        ),
        integrated_outcomes_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        ),
        notification_preview_path=(
            event_alpha_notification_delivery.notification_preview_path_for_context(context)
        ),
        run_ledger_path=context.run_ledger_path,
        strict=True,
        delivery_strict_scope="latest_run",
        evaluated_at=evaluation_now,
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
        include_api_artifacts=include_api_artifacts,
        preview_path=event_alpha_notification_delivery.notification_preview_path_for_context(
            context
        ),
    )
    latest_delivery_rows = [
        row for row in event_alpha_notification_delivery.latest_rows_by_delivery(delivery_rows)
        if not readiness.latest_run_id or str(row.get("run_id") or "") == readiness.latest_run_id
    ]
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    go_result = event_alpha_notification_go_no_go.build_go_no_go(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=event_provider_health.load_provider_health(
            context.provider_health_path
        ),
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status=doctor.status,
        cooldown_status={},
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=_event_clock_status(),
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
        send_readiness=readiness,
        delivery_rows=latest_delivery_rows,
        delivery_history_rows=delivery_rows,
    )
    result = event_alpha_telegram_final_check.build_final_check(
        go_no_go_result=go_result,
        doctor_status=doctor.status,
        doctor_blockers=doctor.blockers,
        doctor_warnings=doctor.warnings,
        delivery_rows=delivery_rows,
        core_rows=core_rows,
    )
    print(event_alpha_telegram_final_check.format_final_check(result))
    if result.status == event_alpha_notification_go_no_go.RECOMMEND_NOT_READY:
        raise SystemExit(1)

__all__ = (
    'event_alpha_notify_cycle',
    '_event_alpha_notify_cycle_body',
    '_record_skipped_notification_run',
    'event_alpha_notify_preview',
    'event_alpha_notify_preview_from_artifacts',
    '_event_alpha_preview_summary_result',
    '_event_alpha_preview_int',
    'event_alpha_notify_go_no_go',
    'event_alpha_environment_doctor_report',
    'event_alpha_pause_notifications',
    'event_alpha_resume_notifications',
    '_event_alpha_health_guard_status_for_context',
    'event_alpha_scheduler_status_report',
    'event_alpha_generate_launchd',
    'event_alpha_notification_slo_report',
    'event_alpha_export_notification_pack',
    '_event_alpha_llm_budget_status',
    'event_alpha_notification_checklist_report',
    'event_alpha_send_test',
    'event_alpha_telegram_recipient_check_report',
    '_card_paths_by_alert_id',
    '_FixtureNotificationStorage',
    '_write_fixture_alert_snapshot',
    'event_alpha_notify_fixture_smoke',
    'event_alpha_send_readiness_report',
    'event_alpha_telegram_final_check_report',
)
