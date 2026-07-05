"""Event Alpha Integrated.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible through the public API bridge.
"""

from __future__ import annotations

from types import ModuleType
from typing import MutableMapping


_SERVICE_FUNCTION_NAMES = ('bind_scanner_globals', '_refresh_scanner_globals', 'event_alpha_integrated_radar_cycle_report', 'event_alpha_market_anomaly_scan_report', 'event_alpha_official_exchange_report', 'event_alpha_scheduled_catalyst_report', 'event_alpha_derivatives_report', 'event_alpha_replay_report')


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module


def _refresh_scanner_globals() -> ModuleType:
    return bind_scanner_globals(globals())


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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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


__all__ = tuple(name for name in _SERVICE_FUNCTION_NAMES if name != 'bind_scanner_globals')
