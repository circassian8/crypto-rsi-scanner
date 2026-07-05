"""Research-card, replay, pruning, and listener utility commands."""

from __future__ import annotations

from .config_reports import (
    _apply_event_alpha_context_to_config,
    _event_alpha_alert_store_config_from_runtime,
    _event_alpha_card_lineage_context,
    _event_alpha_context_block,
    _event_alpha_retention_config_from_runtime,
    _event_alpha_router_config_from_runtime,
    _event_core_opportunity_store_config_from_runtime,
    _event_feedback_config_from_runtime,
    _event_research_now,
    _event_watchlist_config_from_runtime,
    _event_watchlist_monitor_result_from_runtime,
    _setup_event_discovery_logging,
    _latest_event_alpha_run_id,
    resolve_event_alpha_artifact_context_for_report,
)
from .runtime import *
from .utility_calibration_exports import _event_alpha_local_artifacts

def _scanner_compat_global(name: str, fallback: Any) -> Any:
    import sys

    for module_name in (
        "crypto_rsi_scanner.scanner",
        "crypto_rsi_scanner.cli.services.scanner_api",
    ):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        value = getattr(module, name, fallback)
        if value is not fallback:
            return value
    return fallback


def event_research_card_report(target: str | None, verbose: bool = False) -> None:
    """Print a Markdown research card for one Event Alpha watchlist/alert key."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path, latest_only=True)
    core_store = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    outcome_rows = _event_alpha_local_artifacts(run_limit=1, latest_alerts=False)["outcome_rows"]
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    if target:
        result = event_research_cards.render_research_card(
            target,
            watchlist_entries=watchlist.entries,
            alert_rows=[*core_store.rows, *alerts.rows],
            route_decisions=routed.decisions,
            monitor_rows=monitor_result.rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        )
        print(result.markdown)
        return
    print(
        event_research_cards.render_selected_cards(
            watchlist_entries=watchlist.entries,
            alert_rows=[*core_store.rows, *alerts.rows],
            route_decisions=routed.decisions,
            monitor_rows=monitor_result.rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        )
    )

def event_research_cards_write(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
) -> None:
    """Write selected Event Alpha research cards and index markdown files."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    _apply_event_alpha_context_to_config(context)
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        context.alert_store_path,
        latest_only=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True)
    feedback = event_feedback.load_feedback(context.feedback_path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    outcome_rows = _event_alpha_local_artifacts(run_limit=1, latest_alerts=False)["outcome_rows"]
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    result = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=watchlist.entries,
        alert_rows=[*core_store.rows, *alerts.rows],
        route_decisions=routed.decisions,
        monitor_rows=monitor_result.rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
        limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
        now=datetime.now(timezone.utc),
        lineage_context=_event_alpha_card_lineage_context(
            run_id=_latest_event_alpha_run_id(context.run_ledger_path),
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=context.artifact_namespace,
        ),
    )
    print(_event_alpha_context_block(context))
    print(event_research_cards.format_card_write_result(result))

def event_alpha_explain_last_run(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Explain why the latest Event Alpha cycle did or did not alert."""
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
    profile = event_alpha_profiles.get_profile(profile_name) if profile_name else None
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=100)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=True,
    )
    requested = profile.name if profile else profile_name
    report = event_alpha_explain.format_last_run_explanation(
        runs.rows,
        alert_rows=alerts.rows,
        requested_profile=requested,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    if profile:
        report += (
            f"\nprofile_adjusted_status: profile={profile.name} "
            f"router_enabled={str(bool(config.EVENT_ALPHA_ROUTER_ENABLED)).lower()} "
            f"watchlist_enabled={str(bool(config.EVENT_WATCHLIST_ENABLED)).lower()} "
            f"send_enabled={str(bool(config.EVENT_ALERTS_ENABLED)).lower()}"
        )
    print(_event_alpha_context_block(context))
    print(report)

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_replay_report(priors=priors, llm_advisory=llm_advisory, raw_events_path=raw_events_path, market_rows_path=market_rows_path, compare=compare, replay_profile=replay_profile, replay_profile_alt=replay_profile_alt, verbose=verbose)

def _replay_policy_names(value: str) -> tuple[str, ...]:
    aliases = {
        "llm": "llm_advisory",
        "threshold": "router_threshold_variant",
        "router": "router_threshold_variant",
        "profile": "profile_variant",
    }
    out: list[str] = []
    for part in str(value or "").split(","):
        name = part.strip().lower()
        if not name:
            continue
        out.append(aliases.get(name, name))
    return tuple(out or ["baseline"])

def _router_config_from_profile(profile_name: str | None) -> event_alpha_router.EventAlphaRouterConfig | None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._router_config_from_profile(profile_name)

def event_alpha_prune_artifacts(confirm: bool = False, verbose: bool = False) -> None:
    """Dry-run or confirm pruning of old Event Alpha research artifacts."""
    _setup_event_discovery_logging(verbose)
    result = event_alpha_retention.prune_event_alpha_artifacts(
        _event_alpha_retention_config_from_runtime(),
        confirm=confirm,
        now=datetime.now(timezone.utc),
    )
    print(event_alpha_retention.format_retention_report(result))

def event_discovery_binance_listen(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Listen briefly to Binance announcements and cache raw research evidence."""
    _setup_event_discovery_logging(verbose)
    if not config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE:
        print(
            "Binance announcement listener disabled. Set "
            "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1 and API credentials."
        )
        return
    now = _event_research_now(event_now)
    start = now - timedelta(hours=config.EVENT_DISCOVERY_LOOKBACK_HOURS)
    end = now + timedelta(days=config.EVENT_DISCOVERY_HORIZON_DAYS)
    provider_cls = _scanner_compat_global("BinanceAnnouncementProvider", BinanceAnnouncementProvider)
    provider = provider_cls(
        None,
        live_enabled=True,
        api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
        api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
        ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
        topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
        recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
        listen_seconds=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS,
        max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
    )
    raw_events = provider.fetch_events(start, end)
    result = EventDiscoveryResult(
        raw_events=tuple(raw_events),
        normalized_events=(),
        links=(),
        classifications=(),
        candidates=(),
    )
    write = event_cache.write_event_discovery_cache(result, config.EVENT_DISCOVERY_CACHE_DIR, observed_at=now)
    print(
        "Binance announcement cache listen: "
        f"seen={len(raw_events)}, "
        f"raw={write.raw_events_written}, "
        f"run={write.run_id}, dir={write.cache_dir}"
    )
