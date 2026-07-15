"""Cycle helpers for integrated radar."""

from __future__ import annotations

from ... import decision_model as event_radar_decision_model
from ...decision_model_surfaces import decision_model_values
from .runtime import *
from .sidecars import _candidate_seed_sidecars, _loaded_sidecar_manifest_state, _load_rsi_signal_context_result, _market_anomaly_receipt_manifest_state, _rsi_sidecar_manifest_state

@dataclass(frozen=True)
class _IntegratedCycleStart:
    namespace_dir: Path
    wall_started: datetime
    research_observed_at: datetime
    mode: str
    run_id: str

@dataclass(frozen=True)
class _IntegratedCycleInputs:
    sidecars: dict[str, tuple[dict[str, Any], ...]]
    input_manifest: tuple[dict[str, Any], ...]
    asset_registry: tuple[event_asset_registry.CanonicalAsset, ...]
    sidecar_resolution_rows: tuple[dict[str, Any], ...]

@dataclass(frozen=True)
class _IntegratedCandidateArtifacts:
    candidates: tuple[dict[str, Any], ...]
    resolution_rows: tuple[dict[str, Any], ...]
    manifest_path: Path
    candidates_path: Path
    report_path: Path
    asset_registry_path: Path
    instrument_resolution_path: Path
    asset_resolution_report_path: Path
    targeted_market_refresh_result: Any | None
    calendar_normalization: event_unified_calendar.UnifiedCalendarNormalizationResult

@dataclass(frozen=True)
class _IntegratedOperatorArtifacts:
    core_result: Any
    core_rows: tuple[dict[str, Any], ...]
    cumulative_core_rows: int
    card_result: Any
    readiness_json_path: Path
    readiness_md_path: Path
    source_coverage_path: Path
    source_coverage_json_path: Path
    source_coverage_report: Any
    delivery_path: Path
    delivery_rows: tuple[dict[str, Any], ...]
    daily_brief_path: Path
    preview_path: Path
    decision_v2_preview_path: Path
    unified_calendar_path: Path
    unified_calendar_preview_path: Path
    unified_calendar_rows: tuple[dict[str, Any], ...]
    unified_calendar_normalization: Mapping[str, Any]

@dataclass(frozen=True)
class _IntegratedCalendarArtifacts:
    path: Path
    preview_path: Path
    rows: tuple[dict[str, Any], ...]
    normalization: Mapping[str, Any]

@dataclass(frozen=True)
class _IntegratedCoverageArtifacts:
    readiness_json_path: Path
    readiness_md_path: Path
    source_coverage_path: Path
    source_coverage_json_path: Path
    source_coverage_report: Any

@dataclass(frozen=True)
class _IntegratedPresentationArtifacts:
    delivery_path: Path
    delivery_rows: tuple[dict[str, Any], ...]
    daily_brief_path: Path
    preview_path: Path
    decision_v2_preview_path: Path

def run_integrated_radar_cycle(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool = False,
    observed_at: datetime | str | None = None,
    input_mode: str = INPUT_MODE_AUTO,
    coinalyze_namespace: str | None = None,
    targeted_market_provider: object | None = None,
    calendar_source_rows: Iterable[Mapping[str, Any]] | None = None,
    market_anomaly_scan_result: event_market_anomaly_scanner.MarketAnomalyScanResult | None = None,
) -> EventIntegratedRadarResult:
    """Run one integrated research-only radar cycle and write artifacts."""
    with event_alpha_locks.artifact_mutation_guard(
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        command="integrated-radar-cycle",
    ) as mutation_lock:
        if not mutation_lock.owned:
            raise RuntimeError(f"integrated radar cycle blocked: {mutation_lock.status.message}")
        return _run_integrated_radar_cycle_locked(
            context=context,
            fixture=fixture,
            observed_at=observed_at,
            input_mode=input_mode,
            coinalyze_namespace=coinalyze_namespace,
            targeted_market_provider=targeted_market_provider,
            market_anomaly_scan_result=market_anomaly_scan_result,
            calendar_source_rows=(
                None
                if calendar_source_rows is None
                else tuple(
                    dict(row)
                    for row in calendar_source_rows
                    if isinstance(row, Mapping)
                )
            ),
        )

def _run_integrated_radar_cycle_locked(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
    observed_at: datetime | str | None,
    input_mode: str,
    coinalyze_namespace: str | None,
    targeted_market_provider: object | None,
    market_anomaly_scan_result: event_market_anomaly_scanner.MarketAnomalyScanResult | None,
    calendar_source_rows: tuple[dict[str, Any], ...] | None,
) -> EventIntegratedRadarResult:
    start = _integrated_cycle_start(
        context=context,
        fixture=fixture,
        observed_at=observed_at,
        input_mode=input_mode,
    )
    inputs = _integrated_cycle_inputs(
        start,
        context=context,
        fixture=fixture,
        coinalyze_namespace=coinalyze_namespace,
        market_anomaly_scan_result=market_anomaly_scan_result,
        calendar_source_rows=calendar_source_rows,
    )
    candidate_artifacts = _write_integrated_candidate_artifacts(
        start,
        inputs,
        context=context,
        fixture=fixture,
        targeted_market_provider=targeted_market_provider,
        calendar_source_rows=calendar_source_rows,
    )
    operator_artifacts = _write_integrated_operator_artifacts(
        start,
        inputs,
        candidate_artifacts,
        context=context,
        fixture=fixture,
    )
    finished = datetime.now(timezone.utc)
    result = _integrated_cycle_result(
        start,
        inputs,
        candidate_artifacts,
        operator_artifacts,
        context=context,
        finished=finished,
    )
    event_alpha_run_ledger.append_run_record(
        result,
        cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=context.run_ledger_path),
        profile=context.profile,
        started_at=start.wall_started,
        finished_at=finished,
        with_llm=False,
        send_requested=False,
        notification_burn_in=context.run_mode == "notification_burn_in",
        success=True,
    )
    return result

def _integrated_cycle_start(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
    observed_at: datetime | str | None,
    input_mode: str,
) -> _IntegratedCycleStart:
    wall_started = datetime.now(timezone.utc)
    research_observed_at = _as_utc(_parse_time(observed_at) or wall_started)
    mode = _normalize_input_mode(input_mode)
    namespace_dir = Path(context.namespace_dir)
    namespace_dir.mkdir(parents=True, exist_ok=True)
    if fixture:
        _clear_namespace(namespace_dir)
        namespace_dir.mkdir(parents=True, exist_ok=True)
    return _IntegratedCycleStart(
        namespace_dir=namespace_dir,
        wall_started=wall_started,
        research_observed_at=research_observed_at,
        mode=mode,
        run_id=event_alpha_run_ledger.run_id_for(research_observed_at, context.profile),
    )

def _integrated_cycle_inputs(
    start: _IntegratedCycleStart,
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
    coinalyze_namespace: str | None,
    market_anomaly_scan_result: event_market_anomaly_scanner.MarketAnomalyScanResult | None,
    calendar_source_rows: tuple[dict[str, Any], ...] | None,
) -> _IntegratedCycleInputs:
    sidecars, input_manifest = _run_or_load_sidecars(
        namespace_dir=start.namespace_dir,
        fixture=fixture,
        observed_at=start.research_observed_at,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
        input_mode=start.mode,
        coinalyze_namespace=coinalyze_namespace,
        calendar_source_injected=calendar_source_rows is not None,
        market_anomaly_scan_result=market_anomaly_scan_result,
    )
    asset_registry = _build_integrated_asset_registry(sidecars)
    sidecars, sidecar_resolution_rows = event_instrument_resolver.resolve_sidecar_mapping(
        sidecars,
        asset_registry,
        generated_at=start.research_observed_at,
    )
    return _IntegratedCycleInputs(
        sidecars=sidecars,
        input_manifest=input_manifest,
        asset_registry=asset_registry,
        sidecar_resolution_rows=sidecar_resolution_rows,
    )

def _write_integrated_candidate_artifacts(
    start: _IntegratedCycleStart,
    inputs: _IntegratedCycleInputs,
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
    targeted_market_provider: object | None,
    calendar_source_rows: tuple[dict[str, Any], ...] | None,
) -> _IntegratedCandidateArtifacts:
    manifest_path = start.namespace_dir / INPUT_MANIFEST_FILENAME
    _write_json(manifest_path, _input_manifest_document(
        inputs.input_manifest,
        run_id=start.run_id,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        input_mode=start.mode,
        wall_started_at=start.wall_started,
        research_observed_at=start.research_observed_at,
    ))
    candidate_sidecars = _candidate_seed_sidecars(inputs.sidecars, injected_calendar=calendar_source_rows is not None)
    candidates = build_integrated_candidates(
        sidecar_rows=candidate_sidecars,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
        observed_at=start.research_observed_at,
        asset_registry=inputs.asset_registry,
    )
    refresh_enabled = event_targeted_market_refresh.targeted_refresh_enabled(
        explicit_enabled=bool(config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED),
    )
    provider = targeted_market_provider
    if provider is None and refresh_enabled:
        provider = event_targeted_market_refresh.runtime_targeted_market_provider()
    refresh_result = event_targeted_market_refresh.run_targeted_market_refresh(
        candidates,
        namespace_dir=start.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
        provider=provider,
        cfg=event_targeted_market_refresh.EventNearMissConfig(
            enabled=True,
            near_threshold_points=config.EVENT_ALPHA_NEAR_MISS_THRESHOLD_POINTS,
            market_refresh_enabled=refresh_enabled,
            max_market_refresh_assets=min(20, int(config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_MAX_ASSETS or 20)),
            market_refresh_timeout_seconds=config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_TIMEOUT_SECONDS,
        ),
        enabled=refresh_enabled,
        now=start.research_observed_at,
    )
    if refresh_result.snapshot_rows:
        refreshed_sidecars = event_targeted_market_refresh.apply_targeted_market_refresh_to_sidecars(
            candidate_sidecars,
            refresh_result,
        )
        candidates = build_integrated_candidates(
            sidecar_rows=refreshed_sidecars,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=context.run_mode,
            run_id=start.run_id,
            observed_at=start.research_observed_at,
            asset_registry=inputs.asset_registry,
        )
    candidates = event_targeted_market_refresh.annotate_targeted_market_refresh_candidates(
        candidates,
        refresh_result,
    )
    candidates, candidate_resolution_rows = event_instrument_resolver.resolve_rows(
        candidates,
        inputs.asset_registry,
        source_name="integrated_candidate",
        generated_at=start.research_observed_at,
    )
    calendar_context = _integrated_unified_calendar_normalization(
        start, inputs, context=context, fixture=fixture,
        calendar_source_rows=calendar_source_rows,
    )
    candidates = event_unified_calendar.overlay_calendar_context_rows(
        candidates,
        calendar_context.rows,
        now=start.research_observed_at,
    )
    decision_cfg = event_radar_decision_model.RadarDecisionConfig.from_runtime(config)
    projected_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        evaluated = {
            **candidate,
            **event_radar_decision_model.reevaluate_radar_decision_fields(
                candidate,
                cfg=decision_cfg,
            ),
        }
        projection = decision_model_values(evaluated)
        if projection:
            evaluated["decision_projection"] = projection
        projected_candidates.append(evaluated)
    candidates = tuple(projected_candidates)
    candidates_path = start.namespace_dir / INTEGRATED_CANDIDATES_FILENAME
    _write_jsonl(candidates_path, candidates)
    # Establish truthful pending outcome coverage immediately.  Import here to
    # keep the radar API and outcomes reader from forming an import cycle.
    from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes

    integrated_radar_outcomes.write_integrated_radar_outcome_placeholders(
        start.namespace_dir,
        candidates,
        observed_at=start.research_observed_at,
    )
    asset_registry_path = event_asset_registry.write_asset_registry_artifact(
        inputs.asset_registry,
        start.namespace_dir,
        generated_at=start.research_observed_at,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
    )
    resolution_rows = (*inputs.sidecar_resolution_rows, *candidate_resolution_rows)
    instrument_resolution_path, asset_resolution_report_path = event_instrument_resolver.write_resolution_artifacts(
        start.namespace_dir,
        inputs.asset_registry,
        resolution_rows,
        generated_at=start.research_observed_at,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
    )
    report_path = start.namespace_dir / INTEGRATED_REPORT_FILENAME
    report_path.write_text(format_integrated_radar_report(
        candidates, context=context, input_manifest=inputs.input_manifest,
    ), encoding="utf-8")
    return _IntegratedCandidateArtifacts(
        candidates=candidates,
        resolution_rows=resolution_rows,
        manifest_path=manifest_path,
        candidates_path=candidates_path,
        report_path=report_path,
        asset_registry_path=asset_registry_path,
        instrument_resolution_path=instrument_resolution_path,
        asset_resolution_report_path=asset_resolution_report_path,
        targeted_market_refresh_result=refresh_result,
        calendar_normalization=calendar_context,
    )


def _write_integrated_operator_artifacts(
    start: _IntegratedCycleStart,
    inputs: _IntegratedCycleInputs,
    candidate_artifacts: _IntegratedCandidateArtifacts,
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
) -> _IntegratedOperatorArtifacts:
    candidates = candidate_artifacts.candidates
    core_result, core_read = _write_integrated_core_store(
        start,
        candidates,
        context=context,
    )
    calendar = _write_integrated_calendar_artifacts(
        start,
        candidate_artifacts.calendar_normalization,
    )
    card_result, core_read = _write_integrated_research_cards(
        start,
        core_rows=core_read.rows,
        context=context,
    )
    core_rows = core_read.rows
    coverage = _write_integrated_coverage_artifacts(
        start,
        candidates=candidates,
        core_rows=core_rows,
        input_manifest=inputs.input_manifest,
        context=context,
        fixture=fixture,
    )
    presentation = _write_integrated_presentations(
        start,
        inputs,
        candidates,
        core_rows=core_rows,
        cumulative_store_rows=core_read.total_rows_read,
        source_coverage_path=coverage.source_coverage_path,
        context=context,
    )
    return _IntegratedOperatorArtifacts(
        core_result=core_result,
        core_rows=core_rows,
        cumulative_core_rows=core_read.total_rows_read,
        card_result=card_result,
        readiness_json_path=coverage.readiness_json_path,
        readiness_md_path=coverage.readiness_md_path,
        source_coverage_path=coverage.source_coverage_path,
        source_coverage_json_path=coverage.source_coverage_json_path,
        source_coverage_report=coverage.source_coverage_report,
        delivery_path=presentation.delivery_path,
        delivery_rows=presentation.delivery_rows,
        daily_brief_path=presentation.daily_brief_path,
        preview_path=presentation.preview_path,
        decision_v2_preview_path=presentation.decision_v2_preview_path,
        unified_calendar_path=calendar.path,
        unified_calendar_preview_path=calendar.preview_path,
        unified_calendar_rows=calendar.rows,
        unified_calendar_normalization=calendar.normalization,
    )

def _write_integrated_core_store(
    start: _IntegratedCycleStart,
    candidates: tuple[dict[str, Any], ...],
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> tuple[Any, Any]:
    core_result = event_core_opportunity_store.write_core_opportunities(
        candidates,
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(
            path=context.core_opportunity_store_path
        ),
        now=start.research_observed_at,
        run_id=start.run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
    core_read = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    return core_result, core_read

def _write_integrated_calendar_artifacts(
    start: _IntegratedCycleStart,
    normalization: event_unified_calendar.UnifiedCalendarNormalizationResult,
) -> _IntegratedCalendarArtifacts:
    rows = tuple(normalization.rows)
    path = event_unified_calendar.write_unified_calendar_artifact(
        start.namespace_dir / event_unified_calendar.UNIFIED_CALENDAR_FILENAME,
        rows,
    )
    preview_path = start.namespace_dir / event_unified_calendar.UNIFIED_CALENDAR_PREVIEW_FILENAME
    preview_path.write_text(
        event_unified_calendar.format_unified_calendar_preview(rows),
        encoding="utf-8",
    )
    return _IntegratedCalendarArtifacts(
        path=path,
        preview_path=preview_path,
        rows=rows,
        normalization=normalization.telemetry.to_dict(),
    )

def _write_integrated_research_cards(
    start: _IntegratedCycleStart,
    *,
    core_rows: tuple[dict[str, Any], ...],
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> tuple[Any, Any]:
    card_result = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=(),
        alert_rows=core_rows,
        include_all_alertable=True,
        limit=25,
        now=start.research_observed_at,
        lineage_context={
            "run_id": start.run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
            "run_mode": context.run_mode,
        },
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_result.card_paths,
        run_id=start.run_id,
    )
    core_read = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    return card_result, core_read

def _write_integrated_coverage_artifacts(
    start: _IntegratedCycleStart,
    *,
    candidates: tuple[dict[str, Any], ...],
    core_rows: tuple[dict[str, Any], ...],
    input_manifest: tuple[dict[str, Any], ...],
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
) -> _IntegratedCoverageArtifacts:
    readiness_report = event_live_provider_readiness.build_readiness_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        smoke_mode=fixture,
        run_id=start.run_id,
        now=start.research_observed_at,
    )
    readiness_json_path, readiness_md_path = event_live_provider_readiness.write_readiness_artifacts(
        readiness_report,
        start.namespace_dir,
    )
    coverage_report = _build_integrated_source_coverage_report(
        start,
        candidates=candidates,
        core_rows=core_rows,
        context=context,
        readiness_payload=readiness_report.to_dict(),
    )
    coverage_path = start.namespace_dir / SOURCE_COVERAGE_FILENAME
    coverage_path.write_text(
        f"run_id: {start.run_id}\n"
        + event_alpha_source_coverage.format_source_coverage_report(coverage_report).rstrip()
        + "\n\n"
        + format_integrated_source_coverage(
            candidates,
            run_id=start.run_id,
            readiness_json_path=readiness_json_path,
            readiness_md_path=readiness_md_path,
        ),
        encoding="utf-8",
    )
    coverage_json_path = start.namespace_dir / SOURCE_COVERAGE_JSON_FILENAME
    coverage_payload = format_integrated_source_coverage_json(
        candidates,
        run_id=start.run_id,
        input_manifest=input_manifest,
        readiness_json_path=readiness_json_path,
        readiness_md_path=readiness_md_path,
    )
    coverage_payload.update(coverage_report.to_dict())
    coverage_payload.update({
        "run_id": start.run_id,
        "source": "integrated_radar",
        "candidate_count": len(candidates),
    })
    _write_json(coverage_json_path, coverage_payload)
    return _IntegratedCoverageArtifacts(
        readiness_json_path=readiness_json_path,
        readiness_md_path=readiness_md_path,
        source_coverage_path=coverage_path,
        source_coverage_json_path=coverage_json_path,
        source_coverage_report=coverage_report,
    )


def _write_integrated_presentations(
    start: _IntegratedCycleStart,
    inputs: _IntegratedCycleInputs,
    candidates: tuple[dict[str, Any], ...],
    *,
    core_rows: tuple[dict[str, Any], ...],
    cumulative_store_rows: int,
    source_coverage_path: Path,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> _IntegratedPresentationArtifacts:
    delivery_path = start.namespace_dir / INTEGRATED_DELIVERIES_FILENAME
    preview_path = start.namespace_dir / NOTIFICATION_PREVIEW_FILENAME
    decision_v2_preview_path = start.namespace_dir / DECISION_V2_PREVIEW_FILENAME
    delivery_rows = build_integrated_notification_delivery_rows(
        candidates,
        core_rows=core_rows,
        context=context,
        run_id=start.run_id,
        generated_at=start.research_observed_at,
        send_guard_enabled=False,
        preview_path=preview_path,
    )
    _write_jsonl(delivery_path, delivery_rows)
    raw_events = sum(len(rows) for rows in inputs.sidecars.values())
    daily_brief_path = start.namespace_dir / DAILY_BRIEF_FILENAME
    daily_brief_path.write_text(
        format_integrated_daily_brief(
            candidates,
            core_rows=core_rows,
            context=context,
            input_manifest=inputs.input_manifest,
            delivery_rows=delivery_rows,
            source_coverage_path=source_coverage_path,
            run_id=start.run_id,
            raw_events=raw_events,
            cumulative_store_rows=cumulative_store_rows,
            evaluated_at=start.research_observed_at,
        ),
        encoding="utf-8",
    )
    preview_path.write_text(
        format_integrated_notification_preview_from_deliveries(
            delivery_rows,
            candidates=candidates,
            core_rows=core_rows,
            context=context,
            run_id=start.run_id,
            raw_events=raw_events,
            cumulative_store_rows=cumulative_store_rows,
        ),
        encoding="utf-8",
    )
    decision_v2_preview_path.write_text(
        format_decision_v2_notification_preview_from_deliveries(
            delivery_rows,
            candidates=candidates,
            core_rows=core_rows,
            context=context,
            run_id=start.run_id,
            raw_events=raw_events,
            cumulative_store_rows=cumulative_store_rows,
        ),
        encoding="utf-8",
    )
    return _IntegratedPresentationArtifacts(
        delivery_path=delivery_path,
        delivery_rows=delivery_rows,
        daily_brief_path=daily_brief_path,
        preview_path=preview_path,
        decision_v2_preview_path=decision_v2_preview_path,
    )


def _integrated_unified_calendar_normalization(
    start: _IntegratedCycleStart,
    inputs: _IntegratedCycleInputs,
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool,
    calendar_source_rows: tuple[dict[str, Any], ...] | None = None,
) -> event_unified_calendar.UnifiedCalendarNormalizationResult:
    source_rows: list[Any] = list(
        inputs.sidecars.get("scheduled_catalyst", ())
        if calendar_source_rows is None
        else calendar_source_rows
    )
    if fixture and config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH.exists():
        source_rows.extend(
            event_unified_calendar.load_unified_calendar_fixture_raw_rows(
                config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH
            )
        )
    return event_unified_calendar.normalize_unified_calendar_rows_with_telemetry(
        source_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
        observed_at=start.research_observed_at.isoformat(),
    )


def _build_integrated_source_coverage_report(
    start: _IntegratedCycleStart,
    *,
    candidates: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    readiness_payload: Mapping[str, Any],
) -> event_alpha_source_coverage.EventAlphaSourceCoverageReport:
    cryptopanic_configured = any(
        bool(row.get("configured"))
        for row in readiness_payload.get("providers") or ()
        if isinstance(row, Mapping)
        and "cryptopanic" in " ".join(
            str(row.get(key) or "")
            for key in ("provider", "provider_name", "provider_health_key")
        ).casefold()
    )
    exact_run_stub = {
        "run_id": start.run_id,
        "cryptopanic_configured": cryptopanic_configured,
        "cryptopanic_selected_for_run": False,
        "cryptopanic_live_call_allowed": False,
        "cryptopanic_attempted": False,
        "cryptopanic_skip_reason": "profile_disabled",
    }
    return event_alpha_source_coverage.build_source_coverage_report(
        provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        evidence_acquisition_rows=(),
        core_opportunity_rows=core_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        cryptopanic_request_ledger_path=start.namespace_dir / "cryptopanic_request_ledger.jsonl",
        artifact_namespace_dir=start.namespace_dir,
        exact_run_row=exact_run_stub,
        provider_readiness_payload=readiness_payload,
        near_miss_candidates=candidates,
        now=start.research_observed_at,
    )


def _integrated_cycle_result(
    start: _IntegratedCycleStart,
    inputs: _IntegratedCycleInputs,
    candidate_artifacts: _IntegratedCandidateArtifacts,
    operator_artifacts: _IntegratedOperatorArtifacts,
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    finished: datetime,
) -> EventIntegratedRadarResult:
    candidates = candidate_artifacts.candidates
    delivery_rows = operator_artifacts.delivery_rows
    lane_due = Counter(str(row.get("lane") or "unknown") for row in delivery_rows if row.get("would_send"))
    lane_empty = Counter(str(row.get("lane") or "unknown") for row in delivery_rows if not row.get("would_send"))
    rendered_items = sum(_int(row.get("rendered_item_count")) for row in delivery_rows)
    eligible_items = sum(_int(row.get("eligible_item_count")) for row in delivery_rows)
    skipped_items = sum(_int(row.get("skipped_item_count")) for row in delivery_rows)
    skip_reasons: Counter[str] = Counter()
    for row in delivery_rows:
        for item in row.get("skipped_items") or ():
            if isinstance(item, Mapping):
                skip_reasons[str(item.get("reason") or "unknown")] += 1
    sidecar_counts = _sidecar_count_summary(inputs.sidecars)
    operator_absolute_paths = sum(
        1
        for path in (
            candidate_artifacts.report_path,
            operator_artifacts.daily_brief_path,
            operator_artifacts.preview_path,
            operator_artifacts.decision_v2_preview_path,
            operator_artifacts.source_coverage_path,
            operator_artifacts.unified_calendar_path,
            operator_artifacts.unified_calendar_preview_path,
            *operator_artifacts.card_result.card_paths,
        )
        if _artifact_has_absolute_operator_path(path)
    )
    return EventIntegratedRadarResult(
        namespace_dir=start.namespace_dir,
        run_id=start.run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
        started_at=start.wall_started,
        finished_at=finished,
        research_observed_at=start.research_observed_at,
        wall_started_at=start.wall_started,
        wall_finished_at=finished,
        raw_events=sum(len(rows) for rows in inputs.sidecars.values()),
        market_anomalies=sidecar_counts["market_anomalies"],
        unified_calendar_rows=len(operator_artifacts.unified_calendar_rows),
        unified_calendar_normalization=dict(
            operator_artifacts.unified_calendar_normalization
        ),
        market_state_snapshots=(
            candidate_artifacts.targeted_market_refresh_result.persisted_snapshot_rows
            if candidate_artifacts.targeted_market_refresh_result else 0
        ),
        official_exchange_events=sidecar_counts["official_exchange_events"],
        official_listing_candidates=sidecar_counts["official_listing_candidates"],
        scheduled_catalysts=sidecar_counts["scheduled_catalysts"],
        unlock_candidates=sidecar_counts["unlock_candidates"],
        derivatives_state_rows=sidecar_counts["derivatives_state_rows"],
        derivatives_crowding_candidates=sidecar_counts["derivatives_crowding_candidates"],
        fade_review_candidates=sidecar_counts["fade_review_candidates"],
        dex_pool_state_rows=sidecar_counts["dex_pool_state_rows"],
        dex_pool_anomaly_rows=sidecar_counts["dex_pool_anomaly_rows"],
        protocol_fundamental_rows=sidecar_counts["protocol_fundamental_rows"],
        asset_registry_assets=len(inputs.asset_registry),
        instrument_resolution_rows=len(candidate_artifacts.resolution_rows),
        integrated_candidates=len(candidates),
        candidates=len(candidates),
        core_opportunity_rows_written=operator_artifacts.core_result.rows_written,
        core_opportunity_write_attempted=operator_artifacts.core_result.attempted,
        core_opportunity_write_success=operator_artifacts.core_result.success,
        core_opportunity_write_block_reason=operator_artifacts.core_result.block_reason,
        research_card_paths=operator_artifacts.card_result.card_paths,
        research_cards_dir=str(context.research_cards_dir),
        integrated_candidates_path=candidate_artifacts.candidates_path,
        integrated_report_path=candidate_artifacts.report_path,
        daily_brief_path=operator_artifacts.daily_brief_path,
        notification_preview_path=operator_artifacts.preview_path,
        decision_v2_notification_preview_path=operator_artifacts.decision_v2_preview_path,
        integrated_delivery_path=operator_artifacts.delivery_path,
        run_ledger_path=str(context.run_ledger_path),
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        input_manifest_path=candidate_artifacts.manifest_path,
        source_coverage_json_path=operator_artifacts.source_coverage_json_path,
        source_coverage_path=operator_artifacts.source_coverage_path,
        live_provider_readiness_json_path=operator_artifacts.readiness_json_path,
        live_provider_readiness_report_path=operator_artifacts.readiness_md_path,
        unified_calendar_path=operator_artifacts.unified_calendar_path,
        unified_calendar_preview_path=operator_artifacts.unified_calendar_preview_path,
        asset_registry_path=candidate_artifacts.asset_registry_path,
        instrument_resolution_path=candidate_artifacts.instrument_resolution_path,
        asset_resolution_report_path=candidate_artifacts.asset_resolution_report_path,
        send_lane_items_attempted=dict(lane_due),
        send_lane_items_delivered={lane: 0 for lane in lane_due},
        send_would_send_items=sum(lane_due.values()),
        research_review_digest_enabled=False,
        research_review_digest_candidates=0,
        research_review_digest_would_send=0,
        snapshot_rows_written=(
            candidate_artifacts.targeted_market_refresh_result.refreshed_assets
            if candidate_artifacts.targeted_market_refresh_result else 0
        ),
        strict_alerts=0,
        alertable_decisions=0,
        candidate_events=len(candidates),
        research_candidates=len(candidates),
        source_alert_snapshots=0,
        raw_source_candidates=len(candidates),
        current_generation_core_rows=len(operator_artifacts.core_rows),
        current_generation_visible_core_rows=len(
            event_core_opportunities.visible_core_opportunities(operator_artifacts.core_rows)
        ),
        cumulative_store_rows=operator_artifacts.cumulative_core_rows,
        cards_written=operator_artifacts.card_result.cards_written,
        research_cards_written=operator_artifacts.card_result.cards_written,
        preview_rendered_items=rendered_items,
        preview_eligible_items=eligible_items,
        preview_skipped_items=skipped_items,
        preview_skip_reason_counts=dict(skip_reasons),
        integrated_delivery_rows=len(delivery_rows),
        integrated_lanes_rendered=dict(lane_due),
        integrated_lanes_empty=dict(lane_empty),
        operator_absolute_path_count=operator_absolute_paths,
        source_coverage_json_path_rel=event_artifact_paths.artifact_relpath(operator_artifacts.source_coverage_json_path),
        source_coverage_md_path_rel=event_artifact_paths.artifact_relpath(operator_artifacts.source_coverage_path),
        cryptopanic_configured=operator_artifacts.source_coverage_report.cryptopanic_configured,
        cryptopanic_attempted=False,
        cryptopanic_provider_status=operator_artifacts.source_coverage_report.cryptopanic_health_status,
        cryptopanic_skip_reason=(
            "profile_disabled"
            if operator_artifacts.source_coverage_report.cryptopanic_configured
            else "missing_config"
        ),
        warnings=tuple(dict.fromkeys((
            *_integrated_warnings(candidates),
            *(candidate_artifacts.targeted_market_refresh_result.warnings if candidate_artifacts.targeted_market_refresh_result else ()),
        ))),
        decision_model_version=event_radar_decision_model.DECISION_MODEL_VERSION,
        decision_model_v2_enabled=bool(config.EVENT_ALPHA_DECISION_MODEL_V2_ENABLED),
        decision_model_v2_row_count=sum(
            1
            for row in operator_artifacts.core_rows
            if row.get("decision_model_enabled") is True
            and row.get("decision_model_version") == event_radar_decision_model.DECISION_MODEL_VERSION
        ),
    )

def _build_integrated_asset_registry(
    sidecar_rows: Mapping[str, Iterable[Mapping[str, Any]]],
) -> tuple[event_asset_registry.CanonicalAsset, ...]:
    official_rows: list[Mapping[str, Any]] = []
    coinalyze_rows: list[Mapping[str, Any]] = []
    for origin, rows in sidecar_rows.items():
        materialized = [row for row in rows if isinstance(row, Mapping)]
        if origin in {"official_exchange"}:
            official_rows.extend(materialized)
        if origin in COINALYZE_EXTERNAL_SIDECARS or origin == "coinalyze":
            coinalyze_rows.extend(materialized)
        if origin in {"market_anomaly", "scheduled_catalyst", "unlock", "dex_pool_state", "dex_pool_anomaly", "protocol_fundamentals"}:
            official_rows.extend(materialized)
    return event_asset_registry.build_asset_registry(
        fixture_path=config.EVENT_ASSET_REGISTRY_PATH,
        coingecko_universe_path=config.EVENT_DISCOVERY_UNIVERSE_PATH,
        official_exchange_rows=official_rows,
        coinalyze_rows=coinalyze_rows,
    )

def build_integrated_candidates(
    *,
    sidecar_rows: Mapping[str, Iterable[Mapping[str, Any]]],
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: datetime | str | None = None,
    asset_registry: Iterable[event_asset_registry.CanonicalAsset] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Merge sidecar rows into one candidate per canonical family."""
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat()
    if asset_registry is None:
        asset_registry = _build_integrated_asset_registry(sidecar_rows)
        sidecar_rows, _resolution_rows = event_instrument_resolver.resolve_sidecar_mapping(
            sidecar_rows,
            asset_registry,
            generated_at=observed,
        )
    rsi_context_index = _unique_rsi_context_index(
        sidecar_rows.get("rsi_signal_context", ())
    )
    coinalyze_index = _coinalyze_match_index(sidecar_rows)
    coinalyze_seen_by_family: dict[str, set[str]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for origin, rows in sidecar_rows.items():
        if (
            origin in COINALYZE_EXTERNAL_SIDECARS
            or origin in {"coinalyze", "rsi_signal_context"}
        ):
            continue
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            row["_source_origin"] = origin
            key = _candidate_family_key(row)
            family = grouped.setdefault(key, [])
            family.append(row)
            for match in _matching_coinalyze_rows(row, coinalyze_index):
                match_id = _coinalyze_match_id(match)
                seen = coinalyze_seen_by_family.setdefault(key, set())
                if match_id in seen:
                    continue
                seen.add(match_id)
                family.append(match)
    decision_cfg = event_radar_decision_model.RadarDecisionConfig.from_runtime(config)
    merged: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        rows = _family_rows_with_catalyst_attributions(rows)
        candidate = _merge_family(
            key,
            rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed,
        )
        identity = _exact_rsi_asset_identity(candidate)
        artifact = rsi_context_index.get(identity) if identity is not None else None
        if artifact is not None:
            candidate = event_rsi_technical_context.apply_rsi_technical_context(
                candidate,
                artifact,
                evaluated_at=observed,
            )
            candidate.update(
                event_radar_decision_model.reevaluate_radar_decision_fields(
                    candidate,
                    source_rows=rows,
                    cfg=decision_cfg,
                )
            )
        merged.append(candidate)
    return tuple(sorted(merged, key=_candidate_sort_key, reverse=True))

def _unique_rsi_context_index(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Return only unambiguous RSI rows with an exact symbol/coin-id pair."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        identity = _exact_rsi_asset_identity(row, require_explicit_pair=True)
        if identity is not None:
            grouped.setdefault(identity, []).append(dict(row))
    return {
        identity: matches[0]
        for identity, matches in grouped.items()
        if len(matches) == 1
    }


def _exact_rsi_asset_identity(
    row: Mapping[str, Any],
    *,
    require_explicit_pair: bool = False,
) -> tuple[str, str] | None:
    """Extract one internally coherent canonical RSI asset identity.

    Both the canonical symbol and coin id are required.  Multiple conflicting
    aliases, missing halves, and resolver/raw mismatches fail closed instead of
    allowing ticker-only context to influence a different asset.
    """

    explicit_symbols = {
        str(row.get(field)).strip().upper()
        for field in ("symbol", "asset_symbol")
        if row.get(field) not in (None, "")
    }
    explicit_coin_ids = {
        str(row.get(field)).strip().casefold()
        for field in ("coin_id", "asset_coin_id")
        if row.get(field) not in (None, "")
    }
    if require_explicit_pair and (
        len(explicit_symbols) != 1 or len(explicit_coin_ids) != 1
    ):
        return None

    symbols = {
        str(row.get(field)).strip().upper()
        for field in (
            "symbol",
            "validated_symbol",
            "asset_symbol",
            "asset_registry_symbol",
        )
        if row.get(field) not in (None, "")
    }
    coin_ids = {
        str(row.get(field)).strip().casefold()
        for field in (
            "coin_id",
            "validated_coin_id",
            "asset_coin_id",
            "asset_registry_coin_id",
        )
        if row.get(field) not in (None, "")
    }
    if len(symbols) != 1 or len(coin_ids) != 1:
        return None
    symbol = next(iter(symbols))
    coin_id = next(iter(coin_ids))
    if not symbol or not coin_id:
        return None
    return symbol, coin_id


def _run_or_load_sidecars(
    *,
    namespace_dir: Path,
    fixture: bool,
    observed_at: datetime,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    run_id: str,
    input_mode: str,
    coinalyze_namespace: str | None,
    calendar_source_injected: bool = False,
    market_anomaly_scan_result: event_market_anomaly_scanner.MarketAnomalyScanResult | None = None,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], tuple[dict[str, Any], ...]]:
    if market_anomaly_scan_result is not None and (fixture or input_mode == INPUT_MODE_RUN_SIDECARS):
        raise RuntimeError("market_anomaly_completion_receipt_invalid:input_mode")
    rsi_path = config.EVENT_ALPHA_RSI_SIGNAL_CONTEXT_PATH
    rsi_rows, rsi_valid = _load_rsi_signal_context_result(rsi_path)
    rsi_mode, rsi_configured, rsi_warnings = _rsi_sidecar_manifest_state(
        rsi_rows, path=rsi_path, parse_valid=rsi_valid)
    if fixture:
        rows = _run_fixture_sidecars(
            namespace_dir=namespace_dir,
            observed_at=observed_at,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        )
        rows["rsi_signal_context"] = rsi_rows
        manifest = tuple(
            _manifest_item(
                sidecar_name=name,
                mode=rsi_mode if name == "rsi_signal_context" else "ran_fixture",
                namespace_dir=namespace_dir,
                rows=value,
                configured=rsi_configured if name == "rsi_signal_context" else True,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
                warnings=rsi_warnings if name == "rsi_signal_context" else (),
            )
            for name, value in rows.items()
        )
        return _with_coinalyze_sidecar(
            rows,
            manifest,
            namespace_dir=namespace_dir,
            coinalyze_namespace=coinalyze_namespace,
            observed_at=observed_at,
        )
    if input_mode == INPUT_MODE_RUN_SIDECARS:
        rows = {
            "market_anomaly": (),
            "official_exchange": (),
            "scheduled_catalyst": (),
            "unlock": (),
            "derivatives": (),
            "dex_pool_state": (),
            "dex_pool_anomaly": (),
            "protocol_fundamentals": (),
            "rsi_signal_context": rsi_rows,
        }
        manifest = tuple(
            _manifest_item(
                sidecar_name=name,
                mode=rsi_mode if name == "rsi_signal_context" else "skipped_provider_unavailable",
                namespace_dir=namespace_dir,
                rows=value,
                configured=rsi_configured if name == "rsi_signal_context" else False,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
                warnings=rsi_warnings if name == "rsi_signal_context" else (
                    "configured sidecar execution is not enabled in this research-only integrated path",
                ),
            )
            for name, value in rows.items()
        )
        return _with_coinalyze_sidecar(
            rows,
            manifest,
            namespace_dir=namespace_dir,
            coinalyze_namespace=coinalyze_namespace,
            observed_at=observed_at,
        )
    rows = {
        "market_anomaly": tuple(event_market_anomaly_scanner.load_market_anomaly_rows(namespace_dir)),
        "official_exchange": _official_exchange_integration_rows(
            event_official_exchange.load_official_exchange_events(namespace_dir),
            event_official_exchange.load_official_listing_candidates(namespace_dir),
        ),
        "scheduled_catalyst": tuple(event_scheduled_catalysts.load_scheduled_catalysts(namespace_dir)),
        "unlock": tuple(event_scheduled_catalysts.load_unlock_candidates(namespace_dir)),
        "derivatives": tuple(event_derivatives_crowding.load_derivatives_candidates(namespace_dir)),
        "dex_pool_state": tuple(event_dex_onchain_readiness.load_dex_pool_state(namespace_dir)),
        "dex_pool_anomaly": tuple(event_dex_onchain_readiness.load_dex_pool_anomalies(namespace_dir)),
        "protocol_fundamentals": tuple(event_dex_onchain_readiness.load_protocol_fundamentals(namespace_dir)),
        "rsi_signal_context": rsi_rows,
    }
    manifest_rows: list[dict[str, Any]] = []
    for name, value in rows.items():
        if name == "market_anomaly" and market_anomaly_scan_result is not None:
            mode, configured, warnings = _market_anomaly_receipt_manifest_state(
                namespace_dir,
                value,
                receipt=market_anomaly_scan_result,
                expected_namespace=artifact_namespace,
                expected_run_id=run_id,
            )
        elif name == "scheduled_catalyst" and calendar_source_injected:
            mode, configured, warnings = (
                "loaded_existing" if value else "completed_empty", True, ())
        else:
            mode, configured, warnings = _loaded_sidecar_manifest_state(
                namespace_dir, name, value, rsi_context_path=rsi_path,
                rsi_context_valid=rsi_valid,
            )
        manifest_rows.append(
            _manifest_item(
                sidecar_name=name,
                mode=mode,
                namespace_dir=namespace_dir,
                rows=value,
                configured=configured,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
                warnings=warnings,
            )
        )
    return _with_coinalyze_sidecar(
        rows, tuple(manifest_rows), namespace_dir=namespace_dir,
        coinalyze_namespace=coinalyze_namespace, observed_at=observed_at,
    )
__all__ = (
    'run_integrated_radar_cycle',
    '_build_integrated_asset_registry',
    'build_integrated_candidates',
    '_run_or_load_sidecars',
)
