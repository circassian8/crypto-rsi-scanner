"""Cycle helpers for integrated radar."""

from __future__ import annotations

from .runtime import *


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


@dataclass(frozen=True)
class _IntegratedOperatorArtifacts:
    core_result: Any
    core_rows: tuple[dict[str, Any], ...]
    card_result: Any
    readiness_json_path: Path
    readiness_md_path: Path
    source_coverage_path: Path
    source_coverage_json_path: Path
    delivery_path: Path
    delivery_rows: tuple[dict[str, Any], ...]
    daily_brief_path: Path
    preview_path: Path


def run_integrated_radar_cycle(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool = False,
    observed_at: datetime | str | None = None,
    input_mode: str = INPUT_MODE_AUTO,
    coinalyze_namespace: str | None = None,
) -> EventIntegratedRadarResult:
    """Run one integrated research-only radar cycle and write artifacts."""
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
    )
    candidate_artifacts = _write_integrated_candidate_artifacts(
        start,
        inputs,
        context=context,
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
    candidates = build_integrated_candidates(
        sidecar_rows=inputs.sidecars,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=start.run_id,
        observed_at=start.research_observed_at,
        asset_registry=inputs.asset_registry,
    )
    candidates, candidate_resolution_rows = event_instrument_resolver.resolve_rows(
        candidates,
        inputs.asset_registry,
        source_name="integrated_candidate",
        generated_at=start.research_observed_at,
    )
    candidates_path = start.namespace_dir / INTEGRATED_CANDIDATES_FILENAME
    _write_jsonl(candidates_path, candidates)
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
    report_path.write_text(
        format_integrated_radar_report(candidates, context=context, input_manifest=inputs.input_manifest),
        encoding="utf-8",
    )
    return _IntegratedCandidateArtifacts(
        candidates=candidates,
        resolution_rows=resolution_rows,
        manifest_path=manifest_path,
        candidates_path=candidates_path,
        report_path=report_path,
        asset_registry_path=asset_registry_path,
        instrument_resolution_path=instrument_resolution_path,
        asset_resolution_report_path=asset_resolution_report_path,
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
    core_result = event_core_opportunity_store.write_core_opportunities(
        candidates,
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=context.core_opportunity_store_path),
        now=start.research_observed_at,
        run_id=start.run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
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
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    readiness_report = event_live_provider_readiness.build_readiness_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        smoke_mode=fixture,
        now=start.research_observed_at,
    )
    readiness_json_path, readiness_md_path = event_live_provider_readiness.write_readiness_artifacts(
        readiness_report,
        start.namespace_dir,
    )
    source_coverage_path = start.namespace_dir / SOURCE_COVERAGE_FILENAME
    source_coverage_path.write_text(
        format_integrated_source_coverage(
            candidates,
            readiness_json_path=readiness_json_path,
            readiness_md_path=readiness_md_path,
        ),
        encoding="utf-8",
    )
    source_coverage_json_path = start.namespace_dir / SOURCE_COVERAGE_JSON_FILENAME
    _write_json(
        source_coverage_json_path,
        format_integrated_source_coverage_json(
            candidates,
            input_manifest=inputs.input_manifest,
            readiness_json_path=readiness_json_path,
            readiness_md_path=readiness_md_path,
        ),
    )
    delivery_path = start.namespace_dir / INTEGRATED_DELIVERIES_FILENAME
    delivery_rows = build_integrated_notification_delivery_rows(
        candidates,
        core_rows=core_rows,
        context=context,
        run_id=start.run_id,
        generated_at=start.research_observed_at,
        send_guard_enabled=False,
    )
    _write_jsonl(delivery_path, delivery_rows)
    daily_brief_path = start.namespace_dir / DAILY_BRIEF_FILENAME
    daily_brief_path.write_text(
        format_integrated_daily_brief(
            candidates,
            core_rows=core_rows,
            context=context,
            input_manifest=inputs.input_manifest,
            delivery_rows=delivery_rows,
            source_coverage_path=source_coverage_path,
        ),
        encoding="utf-8",
    )
    preview_path = start.namespace_dir / NOTIFICATION_PREVIEW_FILENAME
    preview_path.write_text(
        format_integrated_notification_preview_from_deliveries(
            delivery_rows,
            candidates=candidates,
            core_rows=core_rows,
            context=context,
        ),
        encoding="utf-8",
    )
    return _IntegratedOperatorArtifacts(
        core_result=core_result,
        core_rows=core_rows,
        card_result=card_result,
        readiness_json_path=readiness_json_path,
        readiness_md_path=readiness_md_path,
        source_coverage_path=source_coverage_path,
        source_coverage_json_path=source_coverage_json_path,
        delivery_path=delivery_path,
        delivery_rows=delivery_rows,
        daily_brief_path=daily_brief_path,
        preview_path=preview_path,
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
            operator_artifacts.source_coverage_path,
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
        market_state_snapshots=sidecar_counts["market_state_snapshots"],
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
        integrated_delivery_path=operator_artifacts.delivery_path,
        run_ledger_path=str(context.run_ledger_path),
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        input_manifest_path=candidate_artifacts.manifest_path,
        source_coverage_json_path=operator_artifacts.source_coverage_json_path,
        source_coverage_path=operator_artifacts.source_coverage_path,
        asset_registry_path=candidate_artifacts.asset_registry_path,
        instrument_resolution_path=candidate_artifacts.instrument_resolution_path,
        asset_resolution_report_path=candidate_artifacts.asset_resolution_report_path,
        send_lane_items_attempted=dict(lane_due),
        send_lane_items_delivered={lane: 0 for lane in lane_due},
        send_would_send_items=sum(lane_due.values()),
        research_review_digest_enabled=False,
        research_review_digest_candidates=0,
        research_review_digest_would_send=0,
        snapshot_rows_written=len(candidates),
        strict_alerts=0,
        alertable_decisions=0,
        research_candidates=len(candidates),
        raw_source_candidates=len(candidates),
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
        warnings=tuple(_integrated_warnings(candidates)),
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
    coinalyze_index = _coinalyze_match_index(sidecar_rows)
    coinalyze_seen_by_family: dict[str, set[str]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for origin, rows in sidecar_rows.items():
        if origin in COINALYZE_EXTERNAL_SIDECARS or origin == "coinalyze":
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
    merged = [
        _merge_family(
            key,
            rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed,
        )
        for key, rows in grouped.items()
    ]
    return tuple(sorted(merged, key=_candidate_sort_key, reverse=True))

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
) -> tuple[dict[str, tuple[dict[str, Any], ...]], tuple[dict[str, Any], ...]]:
    if fixture:
        rows = _run_fixture_sidecars(
            namespace_dir=namespace_dir,
            observed_at=observed_at,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        )
        manifest = tuple(
            _manifest_item(
                sidecar_name=name,
                mode="ran_fixture",
                namespace_dir=namespace_dir,
                rows=value,
                configured=True,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
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
        }
        manifest = tuple(
            _manifest_item(
                sidecar_name=name,
                mode="skipped_provider_unavailable",
                namespace_dir=namespace_dir,
                rows=value,
                configured=False,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
                warnings=("configured sidecar execution is not enabled in this research-only integrated path",),
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
    derivatives_rows = tuple(event_derivatives_crowding.load_derivatives_candidates(namespace_dir))
    derivatives_mode, derivatives_configured, derivatives_warnings = _derivatives_manifest_mode(namespace_dir, derivatives_rows)
    rows = {
        "market_anomaly": tuple(event_market_anomaly_scanner.load_market_anomaly_rows(namespace_dir)),
        "official_exchange": _official_exchange_integration_rows(
            event_official_exchange.load_official_exchange_events(namespace_dir),
            event_official_exchange.load_official_listing_candidates(namespace_dir),
        ),
        "scheduled_catalyst": tuple(event_scheduled_catalysts.load_scheduled_catalysts(namespace_dir)),
        "unlock": tuple(event_scheduled_catalysts.load_unlock_candidates(namespace_dir)),
        "derivatives": derivatives_rows,
        "dex_pool_state": tuple(event_dex_onchain_readiness.load_dex_pool_state(namespace_dir)),
        "dex_pool_anomaly": tuple(event_dex_onchain_readiness.load_dex_pool_anomalies(namespace_dir)),
        "protocol_fundamentals": tuple(event_dex_onchain_readiness.load_protocol_fundamentals(namespace_dir)),
    }
    manifest = tuple(
        _manifest_item(
            sidecar_name=name,
            mode=derivatives_mode if name == "derivatives" else "loaded_existing" if value else "skipped_missing_config",
            namespace_dir=namespace_dir,
            rows=value,
            configured=derivatives_configured if name == "derivatives" else bool(value),
            sidecar_research_observed_at=observed_at,
            wall_started_at=datetime.now(timezone.utc),
            wall_finished_at=datetime.now(timezone.utc),
            warnings=derivatives_warnings if name == "derivatives" else () if value else (f"{name} sidecar artifact missing or empty",),
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

__all__ = (
    'run_integrated_radar_cycle',
    '_build_integrated_asset_registry',
    'build_integrated_candidates',
    '_run_or_load_sidecars',
)
