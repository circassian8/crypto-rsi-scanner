"""Utility Commands commands from the legacy scanner service."""

from __future__ import annotations

from .runtime import *

def event_impact_hypotheses_report(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    since: str | None = None,
    include_api: bool = True,
) -> None:
    """Print stored Event Impact Hypothesis rows for a profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.impact_hypothesis_store_path)
    result = event_impact_hypothesis_store.load_impact_hypotheses(
        target_path,
        limit=limit,
        latest_run=latest_run,
        run_id=run_id,
        since=since,
        include_api=include_api,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    print(_event_alpha_context_block(context))
    stale_warning = _event_alpha_stale_quality_warning(context)
    print(event_impact_hypothesis_store.format_impact_hypotheses_store_report(
        result,
        watchlist_rows=[entry.__dict__ for entry in watchlist.entries],
        stale_quality_warning=stale_warning,
    ))

def event_impact_hypotheses_inbox(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print stored Event Impact Hypothesis rows that need operator review."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.impact_hypothesis_store_path)
    result = event_impact_hypothesis_store.load_impact_hypotheses(target_path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_impact_hypothesis_store.format_impact_hypotheses_inbox(result))

def event_incidents_report(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_api: bool = True,
    include_diagnostic: bool = False,
    include_raw: bool = False,
    include_external_context: bool = False,
) -> None:
    """Print stored canonical incident rows for a profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.incident_store_path)
    result = event_incident_store.load_incidents(
        target_path,
        limit=limit,
        latest_run=latest_run,
        run_id=run_id,
        include_api=include_api,
        include_diagnostic=include_diagnostic,
        include_raw=include_raw,
        include_external_context=include_external_context,
    )
    print(_event_alpha_context_block(context))
    print(event_incident_store.format_incidents_report(result))

def event_impact_hypothesis_smoke(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Run an offline smoke proving sector hypothesis validation stays RADAR-only."""
    import tempfile

    _setup_event_discovery_logging(verbose)
    now = _event_research_now(event_now) or datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="smoke-spacex-sector",
        provider="fixture_rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-sector",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "smoke-spacex-sector",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="smoke-spacex-sector",
    )
    validation = RawDiscoveredEvent(
        raw_id="smoke-velvet-validation",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.92,
        content_hash="smoke-velvet-validation",
    )
    normalized = NormalizedEvent(
        event_id="smoke-spacex-sector",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    discovery_result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(normalized,),
        links=(),
        classifications=(),
        candidates=(),
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (validation,)}
    )
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            discovery_result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            hypothesis_search_provider=provider,
            hypothesis_search_cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
                enabled=True,
                max_hypotheses=5,
                max_queries_per_hypothesis=4,
                min_confidence=0.50,
                min_result_confidence=0.50,
            ),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    entries = tuple(pipe.watchlist_result.entries if pipe.watchlist_result else ())
    velvet_radar = any(entry.symbol == "VELVET" and entry.state == event_watchlist.EventWatchlistState.RADAR.value for entry in entries)
    triggered = any(entry.state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for entry in entries)
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipe))
    print("")
    print("Event Impact Hypothesis smoke:")
    print(f"- sector_hypotheses={len(pipe.impact_hypotheses)}")
    print(f"- hypothesis_search_results={pipe.hypothesis_search_results}")
    print(f"- velvet_radar={str(velvet_radar).lower()}")
    print(f"- triggered_fade={str(triggered).lower()}")
    print("- research_only=true")
    if not velvet_radar or triggered:
        raise SystemExit(1)

def _record_dex_onchain_provider_health(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    result: event_dex_onchain_readiness.DexOnchainReadinessResult,
    run_id: str,
    now: datetime,
) -> None:
    cfg = _event_provider_health_config_from_runtime()
    for row in result.report.provider_rows:
        rows_written = row.normalized_rows_written + row.anomaly_rows_written + row.protocol_rows_written
        provider_role = "protocol_fundamentals" if row.family == "protocol_fundamentals" else "dex_onchain_liquidity"
        if row.fixture_parser_status == "pass" and rows_written > 0:
            event_provider_health.record_provider_success(
                row.provider_health_key,
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="enrichment",
                provider_service=row.provider,
                provider_role=provider_role,
            )
            continue
        event_provider_health.record_provider_failure(
            row.provider_health_key,
            f"dex_onchain_fixture_{row.fixture_parser_status or 'not_ready'}",
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_kind="enrichment",
            provider_service=row.provider,
            provider_role=provider_role,
        )

def _append_dex_onchain_run_ledger_row(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    dex_pool_state_count: int,
    dex_pool_anomaly_count: int,
    protocol_fundamental_count: int,
    warnings: Iterable[str] = (),
) -> None:
    row = {
        "schema_version": event_alpha_run_ledger.RUN_LEDGER_SCHEMA_VERSION,
        "row_type": "event_alpha_run",
        "run_id": run_id,
        "profile": context.profile,
        "run_mode": context.run_mode,
        "artifact_namespace": context.artifact_namespace,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "runtime_seconds": max(0.0, (finished_at - started_at).total_seconds()),
        "with_llm": False,
        "send_requested": False,
        "raw_events": 0,
        "market_anomalies": 0,
        "dex_pool_state_rows": int(dex_pool_state_count),
        "dex_pool_anomalies": int(dex_pool_anomaly_count),
        "protocol_fundamentals": int(protocol_fundamental_count),
        "catalyst_queries": 0,
        "catalyst_results_accepted": 0,
        "catalyst_results_rejected": 0,
        "extraction_rows": 0,
        "extraction_hints_applied": 0,
        "candidates": int(dex_pool_anomaly_count) + int(protocol_fundamental_count),
        "clusters": 0,
        "alerts": 0,
        "watchlist_entries": 0,
        "watchlist_escalations": 0,
        "routed": 0,
        "alertable": 0,
        "sent": False,
        "provider_fetch_count": 0,
        "provider_cache_hits": 0,
        "provider_cache_misses": 0,
        "llm_cache_hits": 0,
        "llm_cache_misses": 0,
        "llm_calls_attempted": 0,
        "llm_skipped_due_budget": 0,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "warnings": tuple(str(warning) for warning in warnings if str(warning)),
        "success": True,
        "failure": None,
    }
    context.run_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with context.run_ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))
        fh.write("\n")

def event_alpha_signal_quality_eval(
    path: str | None = None,
    verbose: bool = False,
) -> None:
    """Run the offline curated Event Alpha signal-quality benchmark."""
    _setup_event_discovery_logging(verbose)
    result = event_alpha_signal_quality.evaluate_signal_quality_cases(
        path or event_alpha_signal_quality.DEFAULT_SIGNAL_QUALITY_CASES_PATH
    )
    print(event_alpha_signal_quality.format_signal_quality_eval(result))
    if result.failed_cases:
        raise SystemExit(1)

def event_opportunity_audit_report(
    target: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
) -> None:
    """Print a single-candidate decision audit from local Event Alpha artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        include_api=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True)
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=True)
    incidents = event_incident_store.load_incidents(context.incident_store_path, limit=500, include_api=True)
    feedback = event_feedback.load_feedback(context.feedback_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    print(_event_alpha_context_block(context))
    print(event_opportunity_audit.format_opportunity_audit(
        target,
        hypotheses=hypotheses.rows,
        core_opportunity_rows=core_store.rows,
        watchlist_entries=watchlist.entries,
        alert_rows=alerts.rows,
        route_decisions=routed.decisions,
        incident_rows=incidents.rows,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        feedback_rows=feedback.records,
        profile=context.profile,
        include_diagnostics=include_diagnostics,
    ))

def _event_alpha_quality_artifacts(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> dict[str, Any]:
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        latest_run=True,
        include_api=True,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=True)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    missed = event_alpha_missed.load_missed_rows(context.missed_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    return {
        "hypotheses": hypotheses,
        "watchlist": watchlist,
        "alerts": alerts,
        "core_opportunities": core_opportunities,
        "feedback_rows": [record.__dict__ for record in feedback.records],
        "missed_rows": missed,
        "router": routed,
    }

def _event_alpha_raw_quality_rows(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "runs": event_alpha_quality_coverage.read_jsonl_rows(
            context.run_ledger_path,
            row_type="event_alpha_run",
        ),
        "hypotheses": event_alpha_quality_coverage.read_jsonl_rows(
            context.impact_hypothesis_store_path,
            row_type="event_impact_hypothesis",
        ),
        "watchlist": event_alpha_quality_coverage.read_jsonl_rows(
            context.watchlist_state_path,
            row_type="event_watchlist_state",
        ),
        "alerts": event_alpha_quality_coverage.read_jsonl_rows(
            context.alert_store_path,
            row_type="event_alpha_alert_snapshot",
        ),
    }

def _event_alpha_reference_quality_rows(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> list[dict[str, Any]]:
    namespace_dir = context.base_dir / "quality_validation"
    reference = event_alpha_artifacts.EventAlphaArtifactContext(
        profile="quality_validation",
        run_mode="test",
        artifact_namespace="quality_validation",
        base_dir=context.base_dir,
        namespace_dir=namespace_dir,
        run_ledger_path=namespace_dir / "event_alpha_runs.jsonl",
        alert_store_path=namespace_dir / "event_alpha_alerts.jsonl",
        notification_runs_path=namespace_dir / "event_alpha_notification_runs.jsonl",
        watchlist_state_path=namespace_dir / "event_watchlist_state.jsonl",
        feedback_path=namespace_dir / "event_alpha_feedback.jsonl",
        missed_path=namespace_dir / "event_alpha_missed.jsonl",
        priors_path=namespace_dir / "event_alpha_priors.json",
        provider_health_path=namespace_dir / "event_provider_health.json",
        daily_brief_path=namespace_dir / "event_alpha_daily_brief.md",
        impact_hypothesis_store_path=namespace_dir / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=namespace_dir / "event_core_opportunities.jsonl",
        incident_store_path=namespace_dir / "event_incidents.jsonl",
        evidence_acquisition_path=namespace_dir / "event_evidence_acquisition.jsonl",
        proposed_eval_cases_dir=namespace_dir / "proposed_eval_cases",
        research_cards_dir=namespace_dir / "research_cards",
        llm_budget_ledger_path=namespace_dir / "event_llm_budget.json",
        outcomes_path=namespace_dir / "event_alpha_outcomes.jsonl",
    )
    rows = _event_alpha_raw_quality_rows(reference)
    return [*rows["hypotheses"], *rows["watchlist"], *rows["alerts"]]

def _event_alpha_stale_quality_warning(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> str | None:
    rows = _event_alpha_raw_quality_rows(context)
    return event_alpha_quality_coverage.stale_quality_artifact_warning(
        [*rows["hypotheses"], *rows["watchlist"], *rows["alerts"]],
        reference_rows=_event_alpha_reference_quality_rows(context),
    )

def event_alpha_quality_review_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print signal-quality distribution and gap review for local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    result = event_alpha_quality_review.build_quality_review(
        profile=context.profile,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(
            context.core_opportunity_store_path,
            latest_run=True,
        ).rows,
        hypothesis_rows=artifacts["hypotheses"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        alert_rows=artifacts["alerts"].rows,
        stale_warning=_event_alpha_stale_quality_warning(context),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_quality_review.format_quality_review(result))

def event_alpha_quality_coverage_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_api_artifacts: bool = False,
) -> None:
    """Print fresh-run top-level quality-field coverage from raw artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    rows = _event_alpha_raw_quality_rows(context)
    result = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_rows=rows["runs"],
        hypothesis_rows=rows["hypotheses"],
        watchlist_rows=rows["watchlist"],
        alert_rows=rows["alerts"],
        reference_quality_rows=_event_alpha_reference_quality_rows(context),
        include_api=include_api_artifacts,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_quality_coverage.format_quality_coverage_report(result))
    if result.status == "BLOCKED":
        raise SystemExit(1)

def event_alpha_policy_simulate_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print threshold/policy simulation from local artifacts only."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    rows: list[dict[str, Any]] = []
    rows.extend(dict(row) for row in artifacts["hypotheses"].rows)
    rows.extend(_watchlist_entry_dict(entry) for entry in artifacts["watchlist"].entries)
    rows.extend(dict(row) for row in artifacts["alerts"].rows)
    result = event_alpha_policy_simulator.simulate_policy(
        rows,
        profile=context.profile,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_policy_simulator.format_policy_simulation(result))

def event_alpha_export_signal_quality_cases(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    out_path: str | None = None,
) -> None:
    """Export proposed signal-quality benchmark cases from local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    target = Path(out_path).expanduser() if out_path else context.namespace_dir / "proposed_signal_quality_cases.json"
    result = event_alpha_signal_quality_export.export_signal_quality_cases(
        target,
        alert_rows=[*artifacts["alerts"].rows, *artifacts["core_opportunities"].rows],
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_signal_quality_export.format_signal_quality_export_result(result))

def _watchlist_entry_dict(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    row = dict(getattr(entry, "__dict__", {}) or {})
    row["latest_score_components"] = dict(entry.latest_score_components or {})
    return row

def event_feedback_mark(
    target: str,
    label: str | None,
    *,
    notes: str | None = None,
    marked_by: str | None = None,
    path: str | None = None,
    allow_unmatched: bool = False,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Append one lightweight Event Alpha feedback row."""
    _setup_event_discovery_logging(verbose)
    if not label:
        print(f"Event feedback mark failed: --event-feedback-label is required ({', '.join(event_feedback.valid_labels())})")
        return
    if profile_name or artifact_namespace:
        try:
            context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
        except ValueError as exc:
            print(f"Event feedback mark failed: {exc}")
            return
    else:
        context = None
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    feedback_cfg = _event_feedback_config_from_runtime(path)
    context_rows: list[dict[str, Any]] = []
    card_paths: tuple[Path, ...] = ()
    if context is not None:
        try:
            alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path).rows
            cores = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows
            hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
                context.impact_hypothesis_store_path,
                limit=500,
                latest_run=True,
                include_api=True,
            ).rows
            context_rows = [*alerts, *cores, *hypotheses]
            card_paths = tuple(path for path in Path(context.research_cards_dir).glob("*.md") if path.name != "index.md")
        except Exception as exc:  # noqa: BLE001 - feedback marking should still allow manual unmatched rows.
            if verbose:
                print(f"Event feedback context warning: {exc}")
    try:
        record = event_feedback.mark_feedback(
            target,
            label,
            watchlist_entries=watchlist.entries,
            cfg=feedback_cfg,
            marked_by=marked_by or "human",
            notes=notes,
            allow_unmatched=allow_unmatched,
            context_rows=context_rows,
            card_paths=card_paths,
        )
    except ValueError as exc:
        print(f"Event feedback mark failed: {exc}")
        return
    print(event_feedback.format_feedback_record(record, path=feedback_cfg.path))

def event_feedback_shortcut(
    target: str,
    label: str,
    *,
    notes: str | None = None,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Append quick feedback from a shorthand CLI flag."""
    event_feedback_mark(
        target,
        label,
        notes=notes,
        marked_by="human",
        allow_unmatched=True,
        verbose=verbose,
        profile_name=profile_name,
        artifact_namespace=artifact_namespace,
    )

def event_feedback_report(
    path: str | None = None,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print lightweight Event Alpha feedback artifact rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    feedback_cfg = event_feedback.EventFeedbackConfig(
        path=_event_alpha_report_path(path, context.feedback_path)
    )
    result = event_feedback.load_feedback(feedback_cfg.path)
    print(_event_alpha_context_block(context))
    print(event_feedback.format_feedback_report(result))

def event_alpha_alerts_report(
    path: str | None = None,
    feedback_path: str | None = None,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print Event Alpha alert snapshot cohorts and outcome fields."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    store_cfg = event_alpha_alert_store.EventAlphaAlertStoreConfig(
        path=_event_alpha_report_path(path, context.alert_store_path),
        snapshot_policy=config.EVENT_ALPHA_SNAPSHOT_POLICY,
        sampled_controls_limit=config.EVENT_ALPHA_SNAPSHOT_SAMPLED_CONTROLS,
    )
    result = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    feedback_cfg = event_feedback.EventFeedbackConfig(
        path=_event_alpha_report_path(feedback_path, context.feedback_path)
    )
    feedback = event_feedback.load_feedback(feedback_cfg.path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    print(_event_alpha_context_block(context))
    print(event_alpha_alert_store.format_alert_snapshot_report(result, feedback_rows=feedback_rows))

def event_alpha_notification_inbox_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
    burn_in_review: bool = False,
) -> None:
    """Print unreviewed Event Alpha notification/card follow-up queues."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    result = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
        include_diagnostics=include_diagnostics,
    )
    print(event_alpha_notification_inbox.format_notification_inbox(result, burn_in_review=burn_in_review))

def event_alpha_feedback_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print artifact-only feedback-loop readiness for Event Alpha."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_llm_quality"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
    )
    result = event_alpha_feedback_readiness.build_feedback_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        inbox_result=inbox,
    )
    print(event_alpha_feedback_readiness.format_feedback_readiness(result))

def event_alpha_burn_in_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_burn_in_readiness_report(verbose, profile_name=profile_name, artifact_namespace=artifact_namespace)

def event_alpha_fill_outcomes(
    price_path: str,
    out_path: str,
    *,
    path: str | None = None,
    verbose: bool = False,
) -> None:
    """Fill Event Alpha alert snapshot outcomes from a local OHLCV price fixture."""
    _setup_event_discovery_logging(verbose)
    store_cfg = _event_alpha_alert_store_config_from_runtime(path)
    snapshots = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    result = event_alpha_alert_store.fill_alert_outcomes(
        snapshots.rows,
        price_path,
        out_path,
        source_path=store_cfg.path,
    )
    print(event_alpha_alert_store.format_outcome_fill_result(result))

def event_alpha_missed_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print missed-opportunity diagnostics from local Event Alpha artifacts."""
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
    market_rows = event_alpha_missed.load_market_rows(config.EVENT_DISCOVERY_UNIVERSE_PATH)
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    raw_events: tuple[RawDiscoveredEvent, ...] = ()
    if _event_discovery_paths_configured() or _event_alpha_inputs_configured():
        try:
            raw_events = tuple(_event_discovery_result_from_config().raw_events)
        except Exception as exc:  # noqa: BLE001 - report-only fail-soft guard
            print(f"Missed-opportunity raw event load warning: {exc}")
    result = event_alpha_missed.detect_missed_opportunities(
        market_rows,
        alert_rows=alerts.rows,
        watchlist_entries=watchlist.entries,
        raw_events=raw_events,
    )
    if result.rows:
        event_alpha_missed.write_missed_rows(config.EVENT_ALPHA_MISSED_PATH, result.rows)
    print(_event_alpha_context_block(context))
    print(event_alpha_missed.format_missed_report(result))
    if result.rows:
        print("")
        print(f"Missed-opportunity rows appended: {config.EVENT_ALPHA_MISSED_PATH}")

def event_alpha_calibration_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print calibration summaries from alert, feedback, outcome, and missed artifacts."""
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
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    feedback_cfg = _event_feedback_config_from_runtime()
    feedback = event_feedback.load_feedback(feedback_cfg.path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    print(_event_alpha_context_block(context))
    print(
        event_alpha_calibration.format_calibration_report(
            alerts.rows,
            feedback_rows=feedback_rows,
            missed_rows=missed_rows,
        )
    )

def event_source_reliability_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print source/provider reliability summaries from local artifacts."""
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
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=50)
    print(_event_alpha_context_block(context))
    print(
        event_source_reliability.format_source_reliability_report(
            alerts.rows,
            feedback_rows=feedback_rows,
            missed_rows=missed_rows,
            run_rows=runs.rows,
        )
    )

def event_alpha_burn_in_scorecard(
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print a multi-artifact burn-in scorecard for Event Alpha."""
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
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(config.EVENT_LLM_BUDGET_LEDGER_PATH)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        provider_health_rows=provider_rows,
        llm_budget_rows=budget_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        days=days,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_burn_in.format_burn_in_scorecard(scorecard))

def event_alpha_burn_in_checklist(
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print the operational burn-in acceptance checklist."""
    _setup_event_discovery_logging(verbose)
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist as event_alpha_burn_in_checklist

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
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(config.EVENT_LLM_BUDGET_LEDGER_PATH)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        provider_health_rows=provider_rows,
        llm_budget_rows=budget_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        days=days,
    )
    print(_event_alpha_context_block(context))
    print(checklist.format_burn_in_checklist(checklist.build_burn_in_checklist(scorecard)))

from .utility_calibration_exports import (
    _event_alpha_local_artifacts,
    event_alpha_calibration_export_priors,
    event_alpha_export_burn_in_pack,
    event_alpha_export_eval_cases_from_feedback,
    event_alpha_export_eval_cases_from_missed,
    event_alpha_priors_shadow_report,
    event_alpha_tuning_worksheet_report,
)
from .utility_research_cards import (
    _replay_policy_names,
    _router_config_from_profile,
    event_alpha_explain_last_run,
    event_alpha_prune_artifacts,
    event_alpha_replay_report,
    event_discovery_binance_listen,
    event_research_card_report,
    event_research_cards_write,
)

__all__ = (
    'event_impact_hypotheses_report',
    'event_impact_hypotheses_inbox',
    'event_incidents_report',
    'event_impact_hypothesis_smoke',
    '_record_dex_onchain_provider_health',
    '_append_dex_onchain_run_ledger_row',
    'event_alpha_signal_quality_eval',
    'event_opportunity_audit_report',
    '_event_alpha_quality_artifacts',
    '_event_alpha_raw_quality_rows',
    '_event_alpha_reference_quality_rows',
    '_event_alpha_stale_quality_warning',
    'event_alpha_quality_review_report',
    'event_alpha_quality_coverage_report',
    'event_alpha_policy_simulate_report',
    'event_alpha_export_signal_quality_cases',
    '_watchlist_entry_dict',
    'event_feedback_mark',
    'event_feedback_shortcut',
    'event_feedback_report',
    'event_alpha_alerts_report',
    'event_alpha_notification_inbox_report',
    'event_alpha_feedback_readiness_report',
    'event_alpha_burn_in_readiness_report',
    'event_alpha_fill_outcomes',
    'event_alpha_missed_report',
    'event_alpha_calibration_report',
    'event_source_reliability_report',
    '_event_alpha_local_artifacts',
    'event_alpha_burn_in_scorecard',
    'event_alpha_burn_in_checklist',
    'event_alpha_tuning_worksheet_report',
    'event_alpha_export_burn_in_pack',
    'event_alpha_calibration_export_priors',
    'event_alpha_priors_shadow_report',
    'event_alpha_export_eval_cases_from_feedback',
    'event_alpha_export_eval_cases_from_missed',
    'event_research_card_report',
    'event_research_cards_write',
    'event_alpha_explain_last_run',
    'event_alpha_replay_report',
    '_replay_policy_names',
    '_router_config_from_profile',
    'event_alpha_prune_artifacts',
    'event_discovery_binance_listen',
)
