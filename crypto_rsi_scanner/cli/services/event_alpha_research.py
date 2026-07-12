"""Event Alpha Research.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible through the public API bridge.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, MutableMapping

import crypto_rsi_scanner.event_alpha.artifacts.operator_state as _operator_state
import crypto_rsi_scanner.event_alpha.namespace.status as _namespace_status
from crypto_rsi_scanner.event_alpha.radar.llm.provider_runtime import build_shared_openai_inputs


_SERVICE_FUNCTION_NAMES = (
    'bind_scanner_globals',
    '_refresh_scanner_globals',
    '_cryptopanic_stats_for_pipeline_result',
    '_scanner_call',
    'event_alpha_cycle',
    '_router_config_from_profile',
    '_event_catalyst_search_provider',
    '_event_evidence_acquisition_providers_from_runtime',
    '_send_event_alpha_routed_digest',
    'event_impact_hypotheses_report',
    'event_impact_hypotheses_inbox',
    'event_incidents_report',
    'event_catalyst_search_report',
    'event_watchlist_report',
    'event_watchlist_refresh',
    'event_watchlist_monitor_report',
    'event_alpha_router_report',
    'event_alpha_near_miss_report',
    'event_opportunity_audit_report',
    'event_alpha_quality_review_report',
    'event_alpha_quality_coverage_report',
    'event_alpha_signal_quality_eval',
    'event_alpha_export_signal_quality_cases',
    'event_feedback_mark',
    'event_feedback_shortcut',
    'event_feedback_report',
    'event_alpha_alerts_report',
    'event_alpha_notification_inbox_report',
    'event_alpha_missed_report',
    'event_source_reliability_report',
    'event_alpha_burn_in_scorecard',
    'event_alpha_burn_in_checklist',
    'event_alpha_export_burn_in_pack',
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


def _cryptopanic_stats_for_pipeline_result(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    provider_health_path: str | Path,
) -> dict[str, Any]:
    """Summarize CryptoPanic usage without exposing the API token."""
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    mutation_context = _event_alpha_notify_context_from_runtime(profile_for_run)
    with event_alpha_run_lock.artifact_mutation_guard(
        mutation_context,
        profile=profile_for_run,
        namespace=artifact_namespace or mutation_context.artifact_namespace,
        command="event-alpha-cycle",
    ) as mutation_lock:
        if not mutation_lock.owned:
            print(f"Event Alpha cycle skipped: {mutation_lock.status.message}.")
            return
        _event_alpha_cycle_locked(with_llm=with_llm, send=send, event_now=event_now, profile=profile,
                                  profile_for_run=profile_for_run, run_mode=run_mode, artifact_namespace=artifact_namespace)

def _event_alpha_cycle_locked(*, with_llm: bool, send: bool, event_now: str | datetime | None,
                              profile: Any, profile_for_run: str, run_mode: str,
                              artifact_namespace: str | None) -> None:
    clock_status, now, started_at, run_id = _event_alpha_cycle_runtime(event_now, profile_for_run)
    alert_cfg = _event_alert_config_from_runtime()
    pipeline_result = _run_event_alpha_cycle_pipeline(
        now=now,
        with_llm=with_llm,
        send=send,
        alert_cfg=alert_cfg,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    (
        pipeline_result,
        latest_core_rows,
        hypothesis_store_result,
        incident_store_result,
        core_store_result,
    ) = _write_event_alpha_cycle_support_artifacts(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, latest_core_rows = _write_event_alpha_cycle_cards_if_enabled(
        pipeline_result,
        latest_core_rows,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipeline_result))
    pipeline_result, store_result = _write_event_alpha_cycle_alert_snapshots(
        pipeline_result,
        latest_core_rows,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        clock_status=clock_status,
    )
    _print_event_alpha_cycle_artifact_summary(
        store_result,
        hypothesis_store_result,
        incident_store_result,
        core_store_result,
    )
    pipeline_result = _attach_cycle_cryptopanic_stats(pipeline_result)
    run_row = _append_event_alpha_cycle_run_record(
        pipeline_result,
        profile=profile,
        profile_for_run=profile_for_run,
        started_at=started_at,
        with_llm=with_llm,
        send=send,
    )
    _print_event_alpha_cycle_run_ledger_summary(run_row)


def _event_alpha_cycle_runtime(event_now: str | datetime | None, profile: str) -> tuple[Any, datetime, datetime, str]:
    clock_status = _event_clock_status(event_now)
    now = _event_research_now(event_now)
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, profile)
    return clock_status, now, started_at, run_id


def _event_alpha_cycle_llm_inputs(with_llm: bool) -> dict[str, Any]:
    if not with_llm:
        return {}
    extraction_cfg = _event_llm_extractor_config_from_runtime()
    catalyst_frame_cfg = _event_llm_catalyst_frame_config_from_runtime()
    relationship_cfg = _event_llm_config_from_runtime()
    return build_shared_openai_inputs(
        extraction_cfg, catalyst_frame_cfg, relationship_cfg,
        extraction_factory=_event_llm_extraction_provider,
        catalyst_frame_factory=_event_llm_catalyst_frame_provider,
        relationship_factory=_event_llm_provider,
    )


def _run_event_alpha_cycle_pipeline(
    *,
    now: datetime,
    with_llm: bool,
    send: bool,
    alert_cfg: Any,
    clock_status: Any,
    run_id: str,
    profile: str,
    run_mode: str,
    artifact_namespace: str | None,
) -> Any:
    catalyst_search_cfg = _event_catalyst_search_config_from_runtime()
    catalyst_search_provider = _event_catalyst_search_provider(catalyst_search_cfg)
    evidence_acquisition_cfg = _event_evidence_acquisition_config_from_runtime()
    evidence_acquisition_providers = _event_evidence_acquisition_providers_from_runtime(evidence_acquisition_cfg)
    llm_inputs = _event_alpha_cycle_llm_inputs(with_llm)
    return event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
            now=observed,
            raw_event_transform=raw_event_transform,
        ),
        alert_cfg=alert_cfg,
        now=now,
        with_llm=with_llm,
        extraction_provider=llm_inputs.get("extraction_provider"),
        extraction_cfg=llm_inputs.get("extraction_cfg"),
        catalyst_frame_provider=llm_inputs.get("catalyst_frame_provider"),
        catalyst_frame_cfg=llm_inputs.get("catalyst_frame_cfg"),
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        hypothesis_search_provider=catalyst_search_provider,
        hypothesis_search_cfg=_event_impact_hypothesis_search_config_from_runtime(),
        source_enrichment_cfg=_event_source_enrichment_config_from_runtime(),
        relationship_provider=llm_inputs.get("relationship_provider"),
        relationship_cfg=llm_inputs.get("relationship_cfg"),
        watchlist_cfg=_event_watchlist_config_from_runtime(),
        router_cfg=_event_alpha_router_config_from_runtime(),
        priors_cfg=_event_alpha_priors_config_from_runtime(),
        refresh_watchlist=True,
        route=True,
        evidence_acquisition_cfg=evidence_acquisition_cfg,
        evidence_acquisition_provider=evidence_acquisition_providers.get("default"),
        evidence_acquisition_providers_by_hint=evidence_acquisition_providers,
        evidence_acquisition_context={
            "run_id": run_id,
            "profile": profile,
            "run_mode": run_mode,
            "artifact_namespace": artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE,
        },
        send=send,
        send_callback=lambda decisions: _send_event_alpha_routed_digest(
            decisions,
            alert_cfg,
            now=now,
            profile=profile,
            clock_status=clock_status,
        ),
        **_event_alpha_cycle_watchlist_monitor_kwargs(),
        **_event_alpha_cycle_near_miss_kwargs(),
    )


def _event_alpha_cycle_watchlist_monitor_kwargs() -> dict[str, Any]:
    return {
        "watchlist_monitor_enabled": config.EVENT_WATCHLIST_MONITOR_ENABLED,
        "watchlist_monitor_market_rows": _event_watchlist_monitor_market_rows_from_runtime(),
        "watchlist_monitor_market_source": config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        "watchlist_monitor_market_provider": _event_watchlist_market_provider_from_runtime(),
        "watchlist_monitor_targeted_lookup": config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        "watchlist_monitor_max_assets": config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        "watchlist_monitor_market_cache_ttl_seconds": config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        "watchlist_monitor_derivatives_source": config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        "watchlist_monitor_supply_source": config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        "watchlist_monitor_derivatives_rows": _event_watchlist_monitor_derivatives_rows_from_runtime(),
        "watchlist_monitor_supply_rows": _event_watchlist_monitor_supply_rows_from_runtime(),
        "watchlist_monitor_enrichment_max_assets": config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
        "watchlist_monitor_route_updates": config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES,
    }


def _event_alpha_cycle_near_miss_kwargs() -> dict[str, Any]:
    return {
        "near_miss_cfg": _event_near_miss_config_from_runtime(),
        "near_miss_market_rows": _event_watchlist_monitor_market_rows_from_runtime(),
        "near_miss_market_provider": (
            _event_watchlist_market_provider_from_runtime()
            if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
            else None
        ),
        "near_miss_derivatives_rows": _event_watchlist_monitor_derivatives_rows_from_runtime(),
        "near_miss_supply_rows": _event_watchlist_monitor_supply_rows_from_runtime(),
    }


def _write_event_alpha_cycle_support_artifacts(
    pipeline_result: Any,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str,
    artifact_namespace: str | None,
) -> tuple[Any, Any, Any, Any, Any]:
    pipeline_result, hypothesis_store_result = _write_event_impact_hypotheses_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, incident_store_result = _write_event_incidents_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, core_store_result = _write_event_core_opportunities_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile,
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
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    return pipeline_result, latest_core_rows, hypothesis_store_result, incident_store_result, core_store_result


def _write_event_alpha_cycle_cards_if_enabled(
    pipeline_result: Any,
    latest_core_rows: Any,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str,
    artifact_namespace: str | None,
) -> tuple[Any, Any]:
    if not config.EVENT_RESEARCH_CARDS_AUTO_WRITE or pipeline_result.router_result is None:
        return pipeline_result, latest_core_rows
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
            profile=profile,
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
    return pipeline_result, latest_core_rows


def _write_event_alpha_cycle_alert_snapshots(
    pipeline_result: Any,
    latest_core_rows: Any,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str,
    artifact_namespace: str | None,
    clock_status: Any,
) -> tuple[Any, Any]:
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
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            research_card_paths=pipeline_result.research_card_paths,
            core_opportunity_rows=latest_core_rows,
        )
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile,
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
    return pipeline_result, store_result


def _print_event_alpha_cycle_artifact_summary(
    store_result: Any,
    hypothesis_store_result: Any,
    incident_store_result: Any,
    core_store_result: Any,
) -> None:
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


def _attach_cycle_cryptopanic_stats(pipeline_result: Any) -> Any:
    return replace(
        pipeline_result,
        **_cryptopanic_stats_for_pipeline_result(
            pipeline_result,
            provider_health_path=_event_provider_health_config_from_runtime().path,
        ),
    )


def _append_event_alpha_cycle_run_record(
    pipeline_result: Any,
    *,
    profile: Any,
    profile_for_run: str,
    started_at: datetime,
    with_llm: bool,
    send: bool,
) -> dict[str, Any]:
    finished_at = datetime.now(timezone.utc)
    row = event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=_event_alpha_run_ledger_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=finished_at,
        with_llm=with_llm,
        send_requested=send,
        notification_burn_in=bool(profile and profile.notification_burn_in),
        success=True,
    )
    namespace_dir = Path(config.EVENT_ALPHA_RUN_LEDGER_PATH).expanduser().parent
    preview_path = namespace_dir / "event_alpha_notification_preview.md"
    if preview_path.exists():
        try:
            header = preview_path.read_text(encoding="utf-8", errors="replace")[:4096]
            if _operator_state.text_has_exact_run_id(header, row.get("run_id")):
                _operator_state.record_artifact(
                    namespace_dir,
                    run_id=str(row.get("run_id") or ""),
                    profile=profile_for_run,
                    artifact_namespace=str(row.get("artifact_namespace") or namespace_dir.name),
                    name="notification_preview",
                    path=preview_path,
                    updated_at=finished_at,
                )
                _namespace_status.refresh_namespace_status(
                    namespace_dir,
                    profile=profile_for_run,
                    artifact_namespace=str(row.get("artifact_namespace") or namespace_dir.name),
                    run_mode=str(row.get("run_mode") or ""),
                    now=finished_at,
                )
        except (OSError, ValueError):
            pass
    return row


def _print_event_alpha_cycle_run_ledger_summary(run_row: dict[str, Any]) -> None:
    print("")
    print(
        "Event Alpha run ledger updated: "
        f"{config.EVENT_ALPHA_RUN_LEDGER_PATH} run_id={run_row.get('run_id')}"
    )


def _router_config_from_profile(profile_name: str | None) -> event_alpha_router.EventAlphaRouterConfig | None:
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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
    _refresh_scanner_globals()
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


def event_impact_hypotheses_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_impact_hypotheses_report", *args, **kwargs)


def event_impact_hypotheses_inbox(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_impact_hypotheses_inbox", *args, **kwargs)


def event_incidents_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_incidents_report", *args, **kwargs)


def event_catalyst_search_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_catalyst_search_report", *args, **kwargs)


def event_watchlist_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_watchlist_report", *args, **kwargs)


def event_watchlist_refresh(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_watchlist_refresh", *args, **kwargs)


def event_watchlist_monitor_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_watchlist_monitor_report", *args, **kwargs)


def event_alpha_router_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_router_report", *args, **kwargs)


def event_alpha_near_miss_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_near_miss_report", *args, **kwargs)


def event_opportunity_audit_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_opportunity_audit_report", *args, **kwargs)


def event_alpha_quality_review_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_quality_review_report", *args, **kwargs)


def event_alpha_quality_coverage_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_quality_coverage_report", *args, **kwargs)


def event_alpha_signal_quality_eval(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_signal_quality_eval", *args, **kwargs)


def event_alpha_export_signal_quality_cases(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_export_signal_quality_cases", *args, **kwargs)


def event_feedback_mark(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_feedback_mark", *args, **kwargs)


def event_feedback_shortcut(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_feedback_shortcut", *args, **kwargs)


def event_feedback_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_feedback_report", *args, **kwargs)


def event_alpha_alerts_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_alerts_report", *args, **kwargs)


def event_alpha_notification_inbox_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_notification_inbox_report", *args, **kwargs)


def event_alpha_missed_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_missed_report", *args, **kwargs)


def event_source_reliability_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_source_reliability_report", *args, **kwargs)


def event_alpha_burn_in_scorecard(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_burn_in_scorecard", *args, **kwargs)


def event_alpha_burn_in_checklist(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_burn_in_checklist", *args, **kwargs)


def event_alpha_export_burn_in_pack(*args: Any, **kwargs: Any) -> Any:
    import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes

    return event_alpha_outcomes.event_alpha_export_burn_in_pack(*args, **kwargs)


__all__ = tuple(name for name in _SERVICE_FUNCTION_NAMES if name != 'bind_scanner_globals')
