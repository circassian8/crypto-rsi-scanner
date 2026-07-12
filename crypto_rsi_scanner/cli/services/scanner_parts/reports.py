"""Reports commands from the scanner service."""

from __future__ import annotations

from .runtime import *
from . import guarded_report_writes as _guarded_report_writes
from .config_reports import (
    _event_alpha_context_block, _event_alpha_report_context, _event_alpha_report_path,
    _event_clock_status, _event_provider_health_config_from_runtime,
    _event_research_now, _setup_event_discovery_logging,
    resolve_event_alpha_artifact_context_for_report,
)
from .utility_calibration_exports import _event_alpha_local_artifacts
from .operator_report_state import (
    ensure_operator_state_from_latest_run as _ensure_operator_state_from_latest_run,
    operator_revision_for_run as _operator_revision_for_run,
    record_operator_artifacts as _record_operator_artifacts,
    record_operator_doctor_result as _record_operator_doctor_result,
)
from ....event_alpha.artifacts import operator_state as _operator_state
from ....event_alpha.doctor import aggregation as _doctor_aggregation

def _run_operator_report_mutation(context: Any, command: str, skip_label: str, action: Callable[[], Any]) -> Any:
    with event_alpha_run_lock.artifact_mutation_guard(
        context, profile=context.profile, namespace=context.artifact_namespace, command=command
    ) as mutation_lock:
        if not mutation_lock.owned:
            print(_event_alpha_context_block(context))
            print(f"{skip_label}: {mutation_lock.status.message}")
            return None
        return action()

def event_alpha_status(profile_name: str | None = None, verbose: bool = False) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_status(profile_name, verbose)

def event_alpha_preflight_report(
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    send_requested: bool = False,
    verbose: bool = False,
) -> None:
    """Print profile-scoped Event Alpha preflight blockers before a run."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(event_alpha_preflight.format_preflight_report(
            event_alpha_preflight.EventAlphaPreflightResult(
                ready=False,
                profile=profile_name or "unknown",
                artifact_namespace=artifact_namespace or "unknown",
                run_mode=config.EVENT_ALPHA_RUN_MODE or "unknown",
                paths={},
                provider_ready_event_sources=0,
                provider_ready_enrichment_sources=0,
                blockers=(str(exc),),
                warnings=(),
                recommended_next_command=f"make event-alpha-status PROFILE={profile_name or 'no_key_live'}",
            )
        ))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    result = event_alpha_preflight.run_preflight(
        profile_name=profile_name,
        context=context,
        cfg=config,
        provider_status=provider_report,
        send_requested=send_requested,
        clock_status=clock_status,
    )
    print(event_alpha_preflight.format_preflight_report(result))

def event_alpha_runs_report(
    path: str | None = None,
    limit: int = 20,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print recent Event Alpha cycle run ledger rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    cfg = event_alpha_run_ledger.EventAlphaRunLedgerConfig(
        path=_event_alpha_report_path(path, context.run_ledger_path)
    )
    result = event_alpha_run_ledger.load_run_records(cfg.path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_alpha_run_ledger.format_run_ledger_report(result))

def event_alpha_source_coverage_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print source-pack coverage for Event Alpha research artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "no_key_live", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(context, "source-coverage-report", "source_coverage_report_skipped", lambda: _event_alpha_source_coverage_report_locked(context))


def _event_alpha_source_coverage_report_locked(context: Any) -> None:
    operator_run = _ensure_operator_state_from_latest_run(
        context,
        event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=50).rows,
    )
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    acquisition_rows = event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    readiness_path = context.namespace_dir / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON
    provider_readiness_payload: Mapping[str, Any] = {}
    if readiness_path.exists():
        try:
            parsed_readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parsed_readiness = {}
        if isinstance(parsed_readiness, Mapping):
            provider_readiness_payload = parsed_readiness
    near_miss_candidates = event_near_miss.detect_near_miss_rows(core_rows)
    report = event_alpha_source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        provider_health_rows=provider_rows,
        evidence_acquisition_rows=acquisition_rows,
        core_opportunity_rows=core_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        cryptopanic_request_ledger_path=context.provider_health_path.with_name("cryptopanic_request_ledger.jsonl"),
        cryptopanic_weekly_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        cryptopanic_daily_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
        artifact_namespace_dir=context.namespace_dir,
        exact_run_row=operator_run,
        provider_readiness_payload=provider_readiness_payload,
        cryptopanic_configured_fallback=bool(
            config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN
            or config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
        ),
        near_miss_candidates=near_miss_candidates,
    )
    event_alpha_run_ledger.reconcile_cryptopanic_counts(
        context.run_ledger_path,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_id=str((operator_run or {}).get("run_id") or "") or None,
        accepted_evidence=report.cryptopanic_accepted_evidence,
        rejected_evidence=report.cryptopanic_rejected_evidence,
        successful_requests=report.cryptopanic_successful_requests,
        failed_requests=report.cryptopanic_failed_requests,
        effective_provider_status=report.cryptopanic_health_status,
        stale_backoff_reconciled=report.cryptopanic_backoff_reconciled_after_success,
    )
    operator_run_id = str((operator_run or {}).get("run_id") or "") or None
    report_text = event_alpha_source_coverage.format_source_coverage_report(report)
    report_text = report_text.replace("profile:", f"run_id: {operator_run_id or 'none'}\nprofile:", 1)
    source_coverage_path = context.namespace_dir / "event_alpha_source_coverage.md"
    source_coverage_json_path = context.namespace_dir / "event_alpha_source_coverage.json"
    write_succeeded = False
    try:
        context.namespace_dir.mkdir(parents=True, exist_ok=True)
        source_coverage_path.write_text(report_text + "\n", encoding="utf-8")
        source_coverage_payload = dict(report.to_dict())
        source_coverage_payload["run_id"] = operator_run_id
        source_coverage_json_path.write_text(
            json.dumps(source_coverage_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_succeeded = True
    except OSError as exc:
        print(f"warning: source coverage artifact write failed: {exc}")
    _record_operator_artifacts(
        context,
        {
            "source_coverage_md": source_coverage_path,
            "source_coverage_json": source_coverage_json_path,
        },
        succeeded=write_succeeded,
        failure_reason="source_coverage_write_failed",
        run_row=operator_run,
    )
    print(_event_alpha_context_block(context))
    print(f"source_coverage_report_path: {event_artifact_paths.artifact_display_path(source_coverage_path)}")
    print(f"source_coverage_json_path: {event_artifact_paths.artifact_display_path(source_coverage_json_path)}")
    print(report_text)

def event_alpha_live_provider_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    smoke_mode: bool = False,
) -> None:
    """Write provider activation readiness artifacts without live provider calls."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(context, "live-provider-readiness-report", "live_provider_readiness_report_skipped", lambda: _event_alpha_live_provider_readiness_report_locked(context, smoke_mode=smoke_mode))


def _event_alpha_live_provider_readiness_report_locked(context: Any, *, smoke_mode: bool) -> None:
    operator_run = _ensure_operator_state_from_latest_run(
        context,
        event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=50).rows,
    )
    report = event_live_provider_readiness.build_readiness_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        smoke_mode=smoke_mode,
        run_id=str((operator_run or {}).get("run_id") or "") or None,
        now=_event_research_now(),
    )
    json_path, md_path = event_live_provider_readiness.write_readiness_artifacts(report, context.namespace_dir)
    _record_operator_artifacts(
        context,
        {
            "provider_readiness_json": json_path,
            "provider_readiness_md": md_path,
        },
        succeeded=True,
        run_row=operator_run,
    )
    print(_event_alpha_context_block(context))
    print(f"live_provider_readiness_json: {event_artifact_paths.artifact_display_path(json_path)}")
    print(f"live_provider_readiness_report: {event_artifact_paths.artifact_display_path(md_path)}")
    print(event_live_provider_readiness.format_readiness_report(report))

def event_alpha_unlock_calendar_preflight_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    provider: str | None = None,
    smoke_mode: bool = False,
    include_test_artifacts: bool = False,
) -> None:
    """Write structured unlock/calendar preflight artifacts without live calls."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "fixture",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(
        context,
        "unlock-calendar-preflight-report",
        "unlock_calendar_preflight_report_skipped",
        lambda: _guarded_report_writes.unlock_calendar_preflight(
            context,
            provider=provider,
            smoke_mode=smoke_mode,
        ),
    )

def event_alpha_dex_onchain_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    smoke_mode: bool = False,
    include_test_artifacts: bool = False,
) -> None:
    """Write DEX/on-chain/protocol fundamentals readiness artifacts without live calls."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "fixture",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(context, "dex-onchain-readiness-report", "dex_onchain_readiness_report_skipped", lambda: _event_alpha_dex_onchain_readiness_report_locked(context, smoke_mode=smoke_mode))


def _event_alpha_dex_onchain_readiness_report_locked(context: Any, *, smoke_mode: bool) -> None:
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, context.profile)
    result = event_dex_onchain_readiness.run_dex_onchain_readiness(
        namespace_dir=context.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        geckoterminal_path=config.EVENT_ALPHA_DEX_GECKOTERMINAL_PATH,
        coingecko_dex_path=config.EVENT_ALPHA_DEX_COINGECKO_PATH,
        defillama_path=config.EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH,
        smoke_mode=smoke_mode,
        allow_live_preflight=False,
        now=_event_research_now(),
    )
    finished_at = datetime.now(timezone.utc)
    _record_dex_onchain_provider_health(context, result=result, run_id=run_id, now=finished_at)
    _append_dex_onchain_run_ledger_row(
        context,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        dex_pool_state_count=result.report.dex_pool_state_rows,
        dex_pool_anomaly_count=result.report.dex_pool_anomaly_rows,
        protocol_fundamental_count=result.report.protocol_fundamental_rows,
        warnings=result.report.warnings,
    )
    print(_event_alpha_context_block(context))
    print(f"dex_onchain_readiness_json: {event_artifact_paths.artifact_display_path(result.readiness_json_path)}")
    print(f"dex_onchain_readiness_report: {event_artifact_paths.artifact_display_path(result.readiness_md_path)}")
    print(f"dex_pool_state_path: {event_artifact_paths.artifact_display_path(result.dex_pool_state_path)}")
    print(f"dex_pool_anomalies_path: {event_artifact_paths.artifact_display_path(result.dex_pool_anomalies_path)}")
    print(f"protocol_fundamentals_path: {event_artifact_paths.artifact_display_path(result.protocol_fundamentals_path)}")
    print(event_dex_onchain_readiness.format_readiness_report(result.report))

def event_alpha_v1_readiness_report(
    days: int = 30,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print v1 promotion readiness flags from local research artifacts."""
    _setup_event_discovery_logging(verbose)
    from crypto_rsi_scanner.event_alpha.operations import scorecard as event_alpha_contract_scorecard

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
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=500,
        latest_alerts=False,
    )
    _ensure_operator_state_from_latest_run(context, artifacts["runs"].rows)
    evaluation_now = _event_research_now()
    contract_scorecard = event_alpha_contract_scorecard.build_authoritative_scorecard(
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        now=evaluation_now,
    )
    result = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        candidate_rows=artifacts["candidate_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        days=days,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        now=evaluation_now,
        burn_in_contract_scorecard=contract_scorecard,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_v1_readiness.format_v1_readiness_report(result))

def event_alpha_health_guard_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print Event Alpha freshness/safety health guard status."""
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
    if profile_name and not config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE:
        config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE = profile_name
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=100,
        latest_alerts=True,
    )
    evaluation_now = _event_research_now()
    result = event_alpha_health_guard.evaluate_health_guard(
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
        include_api_artifacts=include_api_artifacts,
        now=evaluation_now,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_health_guard.format_health_guard_report(result))

def event_alpha_artifact_doctor_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
    strict: bool = False,
    strict_api: bool = False,
    delivery_strict_scope: str | None = None,
    include_stale_artifacts: bool = False,
    schema_only: bool = False,
    skip_api_checks: bool = False,
) -> None:
    """Print artifact lineage/namespace diagnostics for Event Alpha."""
    _setup_event_discovery_logging(verbose)
    doctor_strict = strict or bool(config.EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        if doctor_strict:
            raise SystemExit(1) from exc
        return
    result = _run_operator_report_mutation(
        context,
        "artifact-doctor-report",
        "artifact_doctor_report_skipped",
        lambda: _guarded_report_writes.artifact_doctor(
            context,
            profile_name=profile_name,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_api_artifacts=include_api_artifacts,
            doctor_strict=doctor_strict,
            strict_api=strict_api,
            delivery_strict_scope=delivery_strict_scope,
            include_stale_artifacts=include_stale_artifacts,
            schema_only=schema_only,
            skip_api_checks=skip_api_checks,
        ),
    )
    if isinstance(result, _guarded_report_writes.ArtifactDoctorExecution):
        doctor_result = result.result
        exact_revision_recorded = result.exact_revision_recorded
    else:
        doctor_result = result
        exact_revision_recorded = True if result is not None else None
    exact_revision_required = doctor_strict and not schema_only and not skip_api_checks
    if doctor_strict and (
        doctor_result is None
        or str(getattr(doctor_result, "status", "")).upper() == "BLOCKED"
        or bool(getattr(doctor_result, "blockers", ()))
        or exact_revision_required and exact_revision_recorded is not True
    ):
        raise SystemExit(1)


def event_alpha_daily_brief_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_daily_brief_report(verbose, profile_name, artifact_namespace=artifact_namespace, include_test_artifacts=include_test_artifacts, include_api_artifacts=include_api_artifacts)

def event_alpha_integrated_radar_cycle_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    fixture: bool = False,
    input_mode: str | None = None,
    coinalyze_namespace: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_integrated_radar_cycle_report(verbose, profile_name, artifact_namespace=artifact_namespace, fixture=fixture, input_mode=input_mode, coinalyze_namespace=coinalyze_namespace)

def event_alpha_integrated_radar_fill_outcomes_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Fill research-only integrated radar outcomes from local fixture/cache rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "fixture",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(context, "integrated-radar-fill-outcomes", "integrated_radar_fill_outcomes_skipped", lambda: _event_alpha_integrated_radar_fill_outcomes_report_locked(context))


def _event_alpha_integrated_radar_fill_outcomes_report_locked(context: Any) -> None:
    operator_run = _ensure_operator_state_from_latest_run(
        context,
        event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=50).rows,
    )
    evaluation_now = _event_research_now()
    rows = event_integrated_radar_outcomes.fill_integrated_radar_outcomes(
        context.namespace_dir,
        observed_at=evaluation_now,
    )
    performance = event_integrated_radar_outcomes.write_radar_performance_dashboard(
        (context.namespace_dir,),
        output_namespace_dir=context.namespace_dir,
        generated_at=evaluation_now,
    )
    candidate_rows = event_integrated_radar.load_integrated_candidates(context.namespace_dir)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    card_result = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=(),
        alert_rows=core_rows,
        include_all_alertable=True,
        limit=25,
        now=evaluation_now,
        candidate_rows=candidate_rows,
        outcome_rows=rows,
        lineage_context={
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
            "run_mode": context.run_mode,
        },
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_result.card_paths,
    )
    delivery_rows = event_integrated_radar.load_integrated_notification_deliveries(context.namespace_dir)
    operator_counters = event_alpha_run_counters.canonical_run_counters(operator_run)
    daily_brief_path = context.namespace_dir / event_integrated_radar.DAILY_BRIEF_FILENAME
    daily_brief_path.write_text(
        event_integrated_radar.format_integrated_daily_brief(
            candidate_rows,
            core_rows=core_rows,
            context=context,
            delivery_rows=delivery_rows,
            outcome_rows=rows,
            performance_snapshot=performance,
            source_coverage_path=context.namespace_dir / event_integrated_radar.SOURCE_COVERAGE_FILENAME,
            run_id=str((operator_run or {}).get("run_id") or "") or None,
            raw_events=operator_counters["raw_events"],
            cumulative_store_rows=operator_counters["cumulative_store_rows"],
            evaluated_at=evaluation_now,
        ),
        encoding="utf-8",
    )
    _record_operator_artifacts(
        context,
        {
            "research_cards": card_result.out_dir,
            "daily_brief": daily_brief_path,
        },
        succeeded=True,
        run_row=operator_run,
    )
    print(_event_alpha_context_block(context))
    print(
        "integrated_radar_outcomes_filled: "
        f"rows={len(rows)} "
        f"path={event_artifact_paths.artifact_display_path(context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME)}"
    )
    print(
        "radar_performance_dashboard: "
        f"path={event_artifact_paths.artifact_display_path(context.namespace_dir / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME)}"
    )
    print("Research-only outcome artifacts written. No trades, paper trades, normal RSI rows, or sends were created.")

def event_alpha_integrated_radar_outcome_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print the research-only integrated radar outcome report."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "fixture",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    rows = event_integrated_radar_outcomes.load_integrated_radar_outcomes(context.namespace_dir)
    candidates, core_rows = event_integrated_radar_outcomes.load_integrated_radar_outcome_authority(context.namespace_dir)
    print(_event_alpha_context_block(context))
    print(event_integrated_radar_outcomes.format_integrated_radar_outcome_report(
        rows, candidate_rows=candidates, core_rows=core_rows, evaluated_at=_event_research_now()))

def event_alpha_integrated_radar_calibration_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    export_priors: bool = False,
) -> None:
    """Print/export recommendation-only integrated radar calibration artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "fixture",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    _run_operator_report_mutation(
        context,
        "integrated-radar-calibration-report",
        "integrated_radar_calibration_report_skipped",
        lambda: _guarded_report_writes.integrated_radar_calibration(
            context,
            export_priors=export_priors,
        ),
    )

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_market_anomaly_scan_report(verbose, profile_name, artifact_namespace=artifact_namespace, market_rows_path=market_rows_path, asset_registry_path=asset_registry_path, coingecko_universe_path=coingecko_universe_path, include_test_artifacts=include_test_artifacts)

def _append_market_anomaly_run_ledger_row(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    raw_rows: int,
    snapshot_count: int,
    anomaly_count: int,
    catalyst_search_queue_count: int = 0,
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
        "market_rows": int(raw_rows),
        "market_state_snapshots": int(snapshot_count),
        "market_anomalies": int(anomaly_count),
        "catalyst_search_queue_items": int(catalyst_search_queue_count),
        "catalyst_queries": int(catalyst_search_queue_count),
        "catalyst_results_accepted": 0,
        "catalyst_results_rejected": 0,
        "extraction_rows": 0,
        "extraction_hints_applied": 0,
        "candidates": 0,
        "clusters": 0,
        "alerts": 0,
        "watchlist_entries": 0,
        "watchlist_escalations": 0,
        "routed": 0,
        "alertable": 0,
        "sent": False,
        "success": True,
        "failure": None,
        "warnings": (),
    }
    context.run_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with context.run_ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))
        fh.write("\n")

def event_alpha_official_exchange_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    binance_path: str | None = None,
    bybit_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_official_exchange_report(verbose, profile_name, artifact_namespace=artifact_namespace, binance_path=binance_path, bybit_path=bybit_path, include_test_artifacts=include_test_artifacts)

def _record_official_exchange_provider_health(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    result: event_official_exchange.OfficialExchangeScanResult,
    run_id: str,
    now: datetime,
) -> None:
    cfg = _event_provider_health_config_from_runtime()
    events_by_provider: dict[str, int] = {}
    for event in result.events:
        provider = str(event.get("provider") or "")
        if provider:
            events_by_provider[provider] = events_by_provider.get(provider, 0) + 1
    for provider in ("binance_announcements", "bybit_announcements"):
        if events_by_provider.get(provider, 0) > 0:
            event_provider_health.record_provider_success(
                provider,
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="event_source",
                provider_service=provider,
                provider_role="official_exchange_announcements",
            )
        else:
            event_provider_health.record_provider_failure(
                provider,
                "official_exchange_fixture_no_rows",
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="event_source",
                provider_service=provider,
                provider_role="official_exchange_announcements",
            )

def _append_official_exchange_run_ledger_row(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    announcement_count: int,
    event_count: int,
    candidate_count: int,
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
        "raw_events": int(announcement_count),
        "official_exchange_announcements": int(announcement_count),
        "official_exchange_events": int(event_count),
        "official_listing_candidates": int(candidate_count),
        "market_anomalies": 0,
        "catalyst_queries": 0,
        "catalyst_results_accepted": 0,
        "catalyst_results_rejected": 0,
        "extraction_rows": 0,
        "extraction_hints_applied": 0,
        "candidates": int(candidate_count),
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
        "warnings": tuple(str(warning) for warning in warnings if str(warning)),
        "success": True,
        "failure": None,
    }
    context.run_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with context.run_ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))
        fh.write("\n")

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_scheduled_catalyst_report(verbose, profile_name, artifact_namespace=artifact_namespace, tokenomist_path=tokenomist_path, messari_path=messari_path, coinmarketcal_path=coinmarketcal_path, include_test_artifacts=include_test_artifacts)

def event_alpha_derivatives_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    derivatives_path: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_derivatives_report(verbose, profile_name, artifact_namespace=artifact_namespace, derivatives_path=derivatives_path, include_test_artifacts=include_test_artifacts)

def _record_derivatives_provider_health(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    result: event_derivatives_crowding.DerivativesCrowdingScanResult,
    run_id: str,
    now: datetime,
) -> None:
    cfg = _event_provider_health_config_from_runtime()
    providers = {
        str(row.get("provider") or "coinalyze")
        for row in result.derivatives_state_rows
        if isinstance(row, dict)
    } or {"coinalyze"}
    for provider in sorted(providers):
        if result.derivatives_state_count > 0:
            event_provider_health.record_provider_success(
                provider,
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="enrichment",
                provider_service=provider,
                provider_role="derivatives_crowding",
            )
        else:
            event_provider_health.record_provider_failure(
                provider,
                "derivatives_crowding_fixture_no_rows",
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="enrichment",
                provider_service=provider,
                provider_role="derivatives_crowding",
            )

def _append_derivatives_run_ledger_row(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    derivatives_state_count: int,
    evaluated_candidate_count: int,
    fade_review_candidate_count: int,
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
        "derivatives_state_rows": int(derivatives_state_count),
        "fade_review_candidates": int(fade_review_candidate_count),
        "catalyst_queries": 0,
        "catalyst_results_accepted": 0,
        "catalyst_results_rejected": 0,
        "extraction_rows": 0,
        "extraction_hints_applied": 0,
        "candidates": int(evaluated_candidate_count),
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
        "warnings": tuple(str(warning) for warning in warnings if str(warning)),
        "success": True,
        "failure": None,
    }
    context.run_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with context.run_ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))
        fh.write("\n")

def _record_scheduled_catalyst_provider_health(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    result: event_scheduled_catalysts.ScheduledCatalystScanResult,
    run_id: str,
    now: datetime,
) -> None:
    cfg = _event_provider_health_config_from_runtime()
    provider_counts: dict[str, int] = {}
    for row in result.scheduled_events:
        provider = str(row.get("provider") or "")
        if provider:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
    roles = {
        "tokenomist": "structured_unlock_calendar",
        "coinmarketcal": "structured_event_calendar",
    }
    for provider, role in roles.items():
        if provider_counts.get(provider, 0) > 0:
            event_provider_health.record_provider_success(
                provider,
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="event_source",
                provider_service=provider,
                provider_role=role,
            )
        else:
            event_provider_health.record_provider_failure(
                provider,
                "scheduled_catalyst_fixture_no_rows",
                cfg=cfg,
                run_id=run_id,
                now=now,
                provider_kind="event_source",
                provider_service=provider,
                provider_role=role,
            )

def _append_scheduled_catalyst_run_ledger_row(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    scheduled_count: int,
    unlock_count: int,
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
        "raw_events": int(scheduled_count),
        "scheduled_catalysts": int(scheduled_count),
        "unlock_candidates": int(unlock_count),
        "market_anomalies": 0,
        "catalyst_queries": 0,
        "catalyst_results_accepted": 0,
        "catalyst_results_rejected": 0,
        "extraction_rows": 0,
        "extraction_hints_applied": 0,
        "candidates": int(scheduled_count + unlock_count),
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
        "warnings": tuple(str(warning) for warning in warnings if str(warning)),
        "success": True,
        "failure": None,
    }
    context.run_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with context.run_ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))
        fh.write("\n")

__all__ = (
    'event_alpha_status',
    'event_alpha_preflight_report',
    'event_alpha_runs_report',
    'event_alpha_source_coverage_report',
    'event_alpha_live_provider_readiness_report',
    'event_alpha_unlock_calendar_preflight_report',
    'event_alpha_dex_onchain_readiness_report',
    'event_alpha_v1_readiness_report',
    'event_alpha_health_guard_report',
    'event_alpha_artifact_doctor_report',
    'event_alpha_daily_brief_report',
    'event_alpha_integrated_radar_cycle_report',
    'event_alpha_integrated_radar_fill_outcomes_report',
    'event_alpha_integrated_radar_outcome_report',
    'event_alpha_integrated_radar_calibration_report',
    'event_alpha_market_anomaly_scan_report',
    '_append_market_anomaly_run_ledger_row',
    'event_alpha_official_exchange_report',
    '_record_official_exchange_provider_health',
    '_append_official_exchange_run_ledger_row',
    'event_alpha_scheduled_catalyst_report',
    'event_alpha_derivatives_report',
    '_record_derivatives_provider_health',
    '_append_derivatives_run_ledger_row',
    '_record_scheduled_catalyst_provider_health',
    '_append_scheduled_catalyst_run_ledger_row',
)
