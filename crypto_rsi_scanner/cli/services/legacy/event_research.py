"""Event Research commands from the legacy scanner service."""

from __future__ import annotations

from .runtime import *

def _event_alerts_from_config(
    with_llm: bool = False,
    *,
    now: datetime | None = None,
) -> list[event_alerts.EventAlertCandidate]:
    cfg = _event_alert_config_from_runtime()
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=cfg, now=now)
    if with_llm:
        llm_cfg = _event_llm_config_from_runtime()
        provider = _event_llm_provider(llm_cfg)
        if provider is not None:
            rows = event_llm_analyzer.analyze_event_candidates(result, alerts, provider, cfg=llm_cfg)
            alerts = event_alerts.apply_llm_advisory(alerts, rows, cfg, enabled=llm_cfg.mode == "advisory")
    alerts = event_alpha_priors.apply_priors_to_alerts(
        alerts,
        cfg=_event_alpha_priors_config_from_runtime(),
        alert_cfg=cfg,
    )
    return alerts

def event_discovery_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only event-discovery radar from local fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    print(event_discovery.format_discovery_report(result))

def event_alert_report(
    verbose: bool = False,
    send: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print or explicitly send research-only event-discovery alert candidates."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    cfg = _event_alert_config_from_runtime()
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=cfg, now=now)
    if with_llm:
        llm_cfg = _event_llm_config_from_runtime()
        provider = _event_llm_provider(llm_cfg)
        if provider is not None:
            llm_rows = event_llm_analyzer.analyze_event_candidates(
                result,
                alerts,
                provider,
                cfg=llm_cfg,
            )
            alerts = event_alerts.apply_llm_advisory(
                alerts,
                llm_rows,
                cfg,
                enabled=llm_cfg.mode == "advisory",
            )
        if llm_cfg.mode not in {"shadow", "advisory"}:
            print(f"Event LLM mode {llm_cfg.mode!r} is not supported; use shadow or advisory.")
    alerts = event_alpha_priors.apply_priors_to_alerts(
        alerts,
        cfg=_event_alpha_priors_config_from_runtime(),
        alert_cfg=cfg,
    )
    print(event_alerts.format_event_alert_report(alerts))
    if send:
        _send_event_alert_digest(alerts, cfg, now=now)

def event_alpha_radar_report(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print the opt-in event alpha radar with market enrichment/anomalies."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha radar inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    alerts = _event_alerts_from_config(with_llm=with_llm, now=now)
    print(event_alerts.format_event_alert_report(alerts))

def _write_event_impact_hypotheses_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_impact_hypothesis_store.EventImpactHypothesisStoreWriteResult]:
    store_cfg = _event_impact_hypothesis_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    write_result = event_impact_hypothesis_store.write_impact_hypotheses(
        pipeline_result.impact_hypotheses,
        cfg=store_cfg,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        watchlist_rows=watchlist_rows,
    )
    updated = replace(
        pipeline_result,
        hypothesis_store_path=str(store_cfg.path),
        hypothesis_write_attempted=write_result.attempted,
        hypothesis_write_success=write_result.success,
        hypothesis_rows_written=write_result.rows_written,
        hypothesis_write_block_reason=write_result.block_reason,
    )
    return updated, write_result

def _write_event_incidents_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_incident_store.EventIncidentStoreWriteResult]:
    store_cfg = _event_incident_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    write_result = event_incident_store.write_incidents(
        pipeline_result.discovery_result,
        cfg=store_cfg,
        hypotheses=pipeline_result.impact_hypotheses,
        watchlist_rows=watchlist_rows,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    updated = replace(
        pipeline_result,
        incident_store_path=str(store_cfg.path),
        incident_write_attempted=write_result.attempted,
        incident_write_success=write_result.success,
        incident_rows_written=write_result.rows_written,
        incident_write_block_reason=write_result.block_reason,
    )
    return updated, write_result

def _write_event_core_opportunities_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
    card_paths: Iterable[str | Path] = (),
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_core_opportunity_store.EventCoreOpportunityStoreWriteResult]:
    store_cfg = _event_core_opportunity_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    route_decisions = tuple(pipeline_result.router_result.decisions) if pipeline_result.router_result else ()
    rows = [*route_decisions, *watchlist_rows, *pipeline_result.impact_hypotheses, *pipeline_result.alerts]
    write_result = event_core_opportunity_store.write_core_opportunities(
        rows,
        cfg=store_cfg,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=card_paths,
    )
    updated = replace(
        pipeline_result,
        core_opportunity_store_path=str(store_cfg.path),
        core_opportunity_write_attempted=write_result.attempted,
        core_opportunity_write_success=write_result.success,
        core_opportunity_rows_written=write_result.rows_written,
        core_opportunity_write_block_reason=write_result.block_reason,
    )
    return updated, write_result

def _cryptopanic_stats_for_pipeline_result(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    provider_health_path: str | Path,
) -> dict[str, Any]:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._cryptopanic_stats_for_pipeline_result(pipeline_result, provider_health_path=provider_health_path)

def _status_code_ok(value: Any) -> bool:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return False
    return 200 <= code < 400

def _status_code_failed(value: Any) -> bool:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return False
    return code >= 400

def _recent_cryptopanic_request_rows(path: str | Path | None, *, since: datetime | None = None) -> list[Mapping[str, Any]]:
    request_path = Path(path).expanduser() if path else None
    if request_path is None or not request_path.exists():
        return []
    rows: list[Mapping[str, Any]] = []
    try:
        for line in request_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                continue
            if since is not None:
                ts = _parse_datetime_utc(row.get("timestamp"))
                if ts is not None and ts < since:
                    continue
            rows.append(row)
    except (OSError, json.JSONDecodeError):
        return rows
    return rows

def _cryptopanic_row_has_invalid_currencies(row: Mapping[str, Any]) -> bool:
    currencies = str(row.get("currencies") or "").strip()
    if not currencies:
        return True
    for part in currencies.split(","):
        value = part.strip()
        if not value or value == "SECTOR" or value != value.upper() or "-" in value or "_" in value:
            return True
    return False

def _parse_datetime_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _mapping_mentions_cryptopanic(item: object) -> bool:
    if not isinstance(item, Mapping):
        return "cryptopanic" in str(item).casefold()
    values = (
        item.get("provider"),
        item.get("provider_hint"),
        item.get("provider_used"),
        item.get("source_class"),
        item.get("source_url"),
        item.get("reason_codes"),
        item.get("currency_tags"),
        item.get("query"),
    )
    return any(
        "cryptopanic" in str(value).casefold()
        or str(value).casefold() == "cryptopanic_tagged"
        for value in values
    )

def _cryptopanic_evidence_key(item: object) -> str:
    if isinstance(item, Mapping):
        for key in ("raw_id", "source_url", "url", "post_id", "id"):
            value = str(item.get(key) or "").strip()
            if value:
                return f"{key}:{value}"
        provider = str(item.get("provider") or item.get("provider_hint") or "cryptopanic").strip()
        title = str(item.get("title") or item.get("headline") or "").strip()
        reason_codes = ",".join(sorted(str(value) for value in item.get("reason_codes") or item.get("accepted_reason_codes") or ()))
        if provider or title or reason_codes:
            return f"{provider}:{title}:{reason_codes}"
    return json.dumps(_jsonable_for_key(item), sort_keys=True, separators=(",", ":"))

def _jsonable_for_key(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable_for_key(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable_for_key(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.replace(tzinfo=timezone.utc).isoformat()
    return value

def event_catalyst_search_report(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print research-only market-anomaly catalyst-search diagnostics."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-catalyst-search inputs ready. Enable RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 "
            "with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    catalyst_search_cfg = _event_catalyst_search_config_from_runtime(enabled_override=True)
    catalyst_search_provider = _event_catalyst_search_provider(catalyst_search_cfg)
    extraction_provider = None
    extraction_cfg = None
    relationship_provider = None
    relationship_cfg = None
    if with_llm:
        extraction_cfg = _event_llm_extractor_config_from_runtime()
        extraction_provider = _event_llm_extraction_provider(extraction_cfg)
        relationship_cfg = _event_llm_config_from_runtime()
        relationship_provider = _event_llm_provider(relationship_cfg)
    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
            now=observed,
            raw_event_transform=raw_event_transform,
        ),
        alert_cfg=_event_alert_config_from_runtime(),
        now=now,
        with_llm=with_llm,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
        watchlist_cfg=_event_watchlist_config_from_runtime(),
        router_cfg=_event_alpha_router_config_from_runtime(),
        priors_cfg=_event_alpha_priors_config_from_runtime(),
        refresh_watchlist=False,
        route=False,
        send=False,
    )
    print(event_catalyst_search.format_catalyst_search_report(result.catalyst_search_result))
    print("")
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(result))

def event_watchlist_refresh(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Append research-only Event Alpha Radar watchlist state."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    if not watch_cfg.enabled:
        print("Event watchlist refresh disabled. Set RSI_EVENT_WATCHLIST_ENABLED=1 for this research command.")
        return
    if not _event_alpha_inputs_configured():
        print(
            "No event-watchlist inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    alerts = _event_alerts_from_config(with_llm=with_llm, now=now)
    result = event_watchlist.refresh_watchlist(alerts, cfg=watch_cfg, now=now)
    print(event_watchlist.format_watchlist_refresh_result(result))

def event_watchlist_report(verbose: bool = False) -> None:
    """Print latest research-only Event Alpha Radar watchlist state."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    print(event_watchlist.format_watchlist_report(result))

def event_watchlist_monitor_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Refresh active watchlist rows from market state without new source evidence."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    read_result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    fixture_rows = _event_watchlist_monitor_market_rows_from_runtime()
    market_source = event_watchlist_market.market_rows_for_watchlist(
        read_result,
        source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        fixture_rows=fixture_rows,
        cycle_rows=fixture_rows,
        targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        targeted_provider=_event_watchlist_market_provider_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        now=_event_research_now(event_now),
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read_result,
        derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
    )
    result = event_watchlist_monitor.monitor_watchlist(
        read_result,
        market_rows=market_source.rows,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=_event_research_now(event_now),
    )
    if market_source.warnings:
        print("watchlist market warnings: " + "; ".join(market_source.warnings))
    if enrichment.warnings:
        print("watchlist enrichment warnings: " + "; ".join(enrichment.warnings))
    print(event_watchlist_monitor.format_watchlist_monitor_report(result))

def event_alpha_router_report(verbose: bool = False, profile_name: str | None = None) -> None:
    """Print artifact-only Event Alpha Radar route decisions from watchlist state."""
    _setup_event_discovery_logging(verbose)
    profile, error = _apply_event_alpha_report_profile(profile_name)
    if error:
        print(error)
        return
    watch_cfg = _event_watchlist_config_from_runtime()
    router_cfg = _event_alpha_router_config_from_runtime()
    read_result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    routed = event_alpha_router.route_watchlist(read_result, cfg=router_cfg)
    report = event_alpha_router.format_router_report(routed)
    if profile:
        report = report + f"\n\nprofile_applied: {profile.name}"
    print(report)

def event_alpha_near_miss_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    event_now: str | datetime | None = None,
) -> None:
    """Print near-promotion Event Alpha candidates from local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        latest_run=True,
        include_legacy=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    cfg = _event_near_miss_config_from_runtime()
    rows: list[Mapping[str, Any]] = []
    if core_store.rows:
        rows.extend(core_store.rows)
    else:
        rows.extend(hypotheses.rows)
        rows.extend(entry.__dict__ for entry in watchlist.entries)
    near = event_near_miss.detect_near_miss_rows(rows, route_decisions=routed.decisions, cfg=cfg)
    if core_store.rows:
        report_items = near
    else:
        refresh_result = event_near_miss.refresh_near_miss_hypotheses(
            _hypothesis_rows_as_objects(hypotheses.rows),
            cfg=cfg,
            market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
            targeted_market_provider=_event_watchlist_market_provider_from_runtime()
            if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
            else None,
            derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
            supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
            now=_event_research_now(event_now),
        )
        route_context = {item.hypothesis_id: item for item in near if item.hypothesis_id}
        report_items = tuple(
            replace(item, final_route_before=route_context[item.hypothesis_id].final_route_before)
            if item.hypothesis_id in route_context and not item.final_route_before
            else item
            for item in refresh_result.near_misses
        ) or near
    print(_event_alpha_context_block(context))
    if core_store.rows:
        print(f"canonical_core_store_rows: {len(core_store.rows)}")
    print(event_near_miss.format_near_miss_report(report_items, profile=context.profile))

def _hypothesis_rows_as_objects(rows: Iterable[Mapping[str, Any]]) -> tuple[SimpleNamespace, ...]:
    return tuple(SimpleNamespace(**dict(row)) for row in rows)

def event_llm_shadow_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only shadow LLM relationship analysis for event candidates."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    llm_cfg = _event_llm_config_from_runtime()
    if llm_cfg.mode not in {"shadow", "advisory"}:
        print("Event LLM analysis blocked: RSI_EVENT_LLM_MODE must be shadow or advisory.")
        return
    provider = _event_llm_provider(llm_cfg)
    if provider is None:
        return
    alert_cfg = _event_alert_config_from_runtime()
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=alert_cfg, now=now)
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=llm_cfg,
    )
    print(event_llm_analyzer.format_llm_shadow_report(rows))

def event_llm_extract_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only LLM raw-event extraction for discovery evidence."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    extractor_cfg = _event_llm_extractor_config_from_runtime()
    if extractor_cfg.mode not in {"shadow", "advisory"}:
        print("Event LLM extractor blocked: RSI_EVENT_LLM_EXTRACTOR_MODE must be shadow or advisory.")
        return
    provider = _event_llm_extraction_provider(extractor_cfg)
    if provider is None:
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    rows = event_llm_extractor.analyze_raw_events(
        result.raw_events,
        provider,
        cfg=extractor_cfg,
    )
    print(event_llm_extractor.format_llm_extract_report(rows))

__all__ = (
    '_event_alerts_from_config',
    'event_discovery_report',
    'event_alert_report',
    'event_alpha_radar_report',
    '_write_event_impact_hypotheses_for_run',
    '_write_event_incidents_for_run',
    '_write_event_core_opportunities_for_run',
    '_cryptopanic_stats_for_pipeline_result',
    '_status_code_ok',
    '_status_code_failed',
    '_recent_cryptopanic_request_rows',
    '_cryptopanic_row_has_invalid_currencies',
    '_parse_datetime_utc',
    '_mapping_mentions_cryptopanic',
    '_cryptopanic_evidence_key',
    '_jsonable_for_key',
    'event_catalyst_search_report',
    'event_watchlist_refresh',
    'event_watchlist_report',
    'event_watchlist_monitor_report',
    'event_alpha_router_report',
    'event_alpha_near_miss_report',
    '_hypothesis_rows_as_objects',
    'event_llm_shadow_report',
    'event_llm_extract_report',
)
