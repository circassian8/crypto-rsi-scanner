"""Context Loading for the artifact doctor."""

from __future__ import annotations

from ...artifacts import json_lines as artifact_json_lines
from .runtime import *
from .result_fields import build_api_doctor_result

def diagnose_artifacts(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any] | object] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    incident_rows: Iterable[Mapping[str, Any] | object] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    market_anomaly_rows: Iterable[Mapping[str, Any]] | None = None,
    official_exchange_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    scheduled_catalyst_rows: Iterable[Mapping[str, Any]] | None = None,
    unlock_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    derivatives_state_rows: Iterable[Mapping[str, Any]] | None = None,
    fade_review_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    card_paths: Iterable[str | Path] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    source_coverage_report_path: str | Path | None = None,
    daily_brief_path: str | Path | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
    inspected_alert_store_path: str | Path | None = None,
    run_ledger_path: str | Path | None = None,
    strict: bool = False,
    strict_api: bool = False,
    delivery_strict_scope: str | None = None,
    include_stale_artifacts: bool = False,
    schema_only: bool = False,
    skip_api_checks: bool = False,
) -> EventAlphaArtifactDoctorResult:
    """Diagnose cross-artifact lineage, mode, and profile/namespace cleanliness."""
    ctx = _build_doctor_context(locals())
    if ctx.short_circuit_result is not None:
        return ctx.short_circuit_result
    ctx.status = "BLOCKED" if ctx.blockers else ("WARN" if ctx.warnings else "OK")
    return build_api_doctor_result(ctx)


def _build_doctor_context(options: Mapping[str, Any]) -> SimpleNamespace:
    ctx = _load_doctor_context_inputs(options)
    if ctx.short_circuit_result is not None:
        return ctx
    _apply_namespace_profile_checks(ctx)
    _attach_core_card_context(ctx)
    _attach_artifact_conflict_context(ctx)
    _attach_notification_context(ctx)
    _attach_quality_incident_context(ctx)
    return ctx


def _merge_context(ctx: SimpleNamespace, values: Mapping[str, Any]) -> None:
    for name, value in values.items():
        if name in {"ctx", "values"}:
            continue
        setattr(ctx, name, value)


def _load_doctor_context_inputs(options: Mapping[str, Any]) -> SimpleNamespace:
    ctx = SimpleNamespace(**options)
    ctx.short_circuit_result = None
    loaded = _load_and_filter_doctor_artifacts(options)
    ctx.loaded = loaded
    ctx.runs = loaded.runs
    ctx.alerts = loaded.alerts
    ctx.feedback = loaded.feedback
    ctx.outcomes = loaded.outcomes
    ctx.hypotheses = loaded.hypotheses
    ctx.core_rows = loaded.core_rows
    ctx.watchlist = loaded.watchlist
    ctx.incidents = loaded.incidents
    ctx.acquisition_rows = loaded.acquisition_rows
    ctx.market_anomalies = loaded.market_anomalies
    ctx.official_exchange_candidates = loaded.official_exchange_candidates
    ctx.scheduled_catalysts = loaded.scheduled_catalysts
    ctx.unlock_candidates = loaded.unlock_candidates
    ctx.derivatives_state = loaded.derivatives_state
    ctx.fade_review_candidates = loaded.fade_review_candidates
    ctx.burn_in_scorecard = loaded.burn_in_scorecard
    ctx.source_yield_report = loaded.source_yield_report
    ctx.daily_review_inbox = loaded.daily_review_inbox
    ctx.daily_burn_in_run = loaded.daily_burn_in_run
    ctx.candidate_mode_manifest = loaded.candidate_mode_manifest
    ctx.burn_in_namespace_policy = loaded.burn_in_namespace_policy
    ctx.burn_in_archive_manifest = loaded.burn_in_archive_manifest
    ctx.dex_pool_state = loaded.dex_pool_state
    ctx.dex_pool_anomalies = loaded.dex_pool_anomalies
    ctx.protocol_fundamentals = loaded.protocol_fundamentals
    ctx.integrated_candidates = loaded.integrated_candidates
    ctx.outcome_evidence_jsonl_diagnostics = loaded.outcome_evidence_jsonl_diagnostics
    ctx.raw_api = loaded.raw_api
    ctx.integrated_manifest_path = loaded.integrated_manifest_path
    ctx.integrated_source_coverage_json_path = loaded.integrated_source_coverage_json_path
    ctx.integrated_delivery_path = loaded.integrated_delivery_path
    ctx.integrated_outcomes_path = loaded.integrated_outcomes_path
    ctx.namespace_dir = _artifact_namespace_dir(
        ctx.inspected_alert_store_path,
        ctx.source_coverage_report_path,
        ctx.daily_brief_path,
        ctx.integrated_outcomes_path,
    )
    ctx.namespace_phase = namespace_doctor.inspect_namespace(
        ctx.namespace_dir,
        include_stale_artifacts=ctx.include_stale_artifacts,
    )
    if ctx.namespace_phase.short_circuit:
        phase_status = "BLOCKED" if ctx.namespace_phase.blockers else "STALE"
        ctx.short_circuit_result = _phase_only_doctor_result(
            status=phase_status,
            profile=ctx.profile,
            artifact_namespace=ctx.artifact_namespace,
            runs=ctx.runs,
            alerts=ctx.alerts,
            feedback=ctx.feedback,
            outcomes=ctx.outcomes,
            card_paths=ctx.card_paths,
            namespace_phase=ctx.namespace_phase,
            schema_result=schema_doctor.SchemaDoctorResult(),
            strict=ctx.strict,
            strict_api=ctx.strict_api,
            schema_only=ctx.schema_only,
            legacy_checks_skipped=True,
            blockers=ctx.namespace_phase.blockers,
            warnings=ctx.namespace_phase.warnings,
        )
        return ctx
    ctx.schema_result = schema_doctor.validate_namespace_artifacts(ctx.namespace_phase.namespace_dir)
    ctx.safety_result = safety_doctor.validate_schema_safety(
        ctx.schema_result,
        strict=ctx.strict,
        schema_only=ctx.schema_only,
    )
    if ctx.schema_only or ctx.skip_api_checks:
        phase_blockers = list(ctx.namespace_phase.blockers)
        phase_blockers.extend(ctx.safety_result.blockers)
        phase_warnings = list(ctx.namespace_phase.warnings)
        phase_warnings.extend(ctx.safety_result.warnings)
        if ctx.schema_result.schema_validation_errors:
            message = check_registry.format_check_message(
                "schema.validation_errors",
                f"schema_validation_errors={ctx.schema_result.schema_validation_errors}",
            )
            (phase_blockers if ctx.schema_only or ctx.strict else phase_warnings).append(message)
        consistency_phase = consistency_doctor.skipped_result()
        phase_blockers.extend(consistency_phase.blockers)
        phase_warnings.extend(consistency_phase.warnings)
        status = "BLOCKED" if phase_blockers else ("WARN" if phase_warnings else "OK")
        ctx.short_circuit_result = _phase_only_doctor_result(
            status=status,
            profile=ctx.profile,
            artifact_namespace=ctx.artifact_namespace,
            runs=ctx.runs,
            alerts=ctx.alerts,
            feedback=ctx.feedback,
            outcomes=ctx.outcomes,
            card_paths=ctx.card_paths,
            namespace_phase=ctx.namespace_phase,
            schema_result=ctx.schema_result,
            strict=ctx.strict,
            strict_api=ctx.strict_api,
            schema_only=ctx.schema_only,
            legacy_checks_skipped=True,
            blockers=phase_blockers,
            warnings=phase_warnings,
        )
        return ctx
    ctx.blockers = []
    ctx.warnings = []
    ctx.blockers.extend(ctx.namespace_phase.blockers)
    ctx.warnings.extend(ctx.namespace_phase.warnings)
    ctx.blockers.extend(ctx.safety_result.blockers)
    ctx.warnings.extend(ctx.safety_result.warnings)
    _attach_shim_dependency_warnings(ctx)
    run_snapshot_context = _inspect_run_snapshot_context(
        runs=ctx.runs,
        alerts=ctx.alerts,
        feedback=ctx.feedback,
        outcomes=ctx.outcomes,
        inspected_alert_store_path=ctx.inspected_alert_store_path,
        include_test_artifacts=ctx.include_test_artifacts,
        delivery_strict_scope=ctx.delivery_strict_scope,
        strict=ctx.strict,
    )
    ctx.blockers.extend(run_snapshot_context.blockers)
    ctx.warnings.extend(run_snapshot_context.warnings)
    ctx.run_snapshot_context = run_snapshot_context
    ctx.matching_snapshot_runs = run_snapshot_context.matching_snapshot_runs
    ctx.missing_snapshot_runs = run_snapshot_context.missing_snapshot_runs
    ctx.external_snapshot_runs = run_snapshot_context.external_snapshot_runs
    ctx.latest_run_id = run_snapshot_context.latest_run_id
    ctx.latest_run = run_snapshot_context.latest_run
    ctx.effective_delivery_scope = run_snapshot_context.effective_delivery_scope
    return ctx


def _attach_shim_dependency_warnings(ctx: SimpleNamespace) -> None:
    active_shim_logic_count, active_shim_logic_modules = event_alpha_shims.active_shim_violation_summary()
    ctx.active_shim_logic_count = active_shim_logic_count
    ctx.active_shim_logic_modules = active_shim_logic_modules
    if active_shim_logic_count:
        modules = ", ".join(active_shim_logic_modules[:5])
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.active_shim_contains_logic",
                "active_shim_modules_with_implementation_logic="
                f"{active_shim_logic_count}"
                + (f" modules={modules}" if modules else ""),
            )
        )
    shim_internal_import_count, safe_to_remove_shim_count, old_import_modules = (
        event_alpha_shims.shim_dependency_warning_summary()
    )
    (
        ctx.old_path_internal_imports,
        ctx.old_path_test_imports,
        ctx.old_path_docs_references,
        ctx.old_path_import_allowed_exceptions,
    ) = event_alpha_shims.old_import_check_counter_summary()
    if shim_internal_import_count:
        modules = ", ".join(old_import_modules[:5])
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.old_shim_internal_import",
                f"old_shim_internal_import_references={shim_internal_import_count}"
                + (f" modules={modules}" if modules else ""),
            )
        )
    if ctx.old_path_test_imports:
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.old_shim_internal_import",
                f"old_path_test_imports={ctx.old_path_test_imports}",
            )
        )
    if ctx.old_path_docs_references:
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.old_shim_internal_import",
                f"old_path_docs_references={ctx.old_path_docs_references}",
            )
        )
    scan_health = event_alpha_shims.shim_scan_health_summary()
    ctx.shim_scan_health = scan_health
    scan_duration = float(scan_health.get("scan_duration_seconds") or 0.0)
    scanned_artifacts = int(scan_health.get("scanned_artifact_files") or 0)
    include_runtime_artifacts = bool(scan_health.get("include_runtime_artifacts"))
    if (not include_runtime_artifacts and scanned_artifacts) or include_runtime_artifacts:
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.shim_scan_runtime_artifacts",
                "include_runtime_artifacts="
                f"{include_runtime_artifacts} scanned_artifact_files={scanned_artifacts}",
            )
        )
    if scan_duration > event_alpha_shims.shim_scan.SHIM_SCAN_DURATION_WARNING_SECONDS:
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.shim_scan_slow",
                f"shim_scan_duration_seconds={scan_duration:.4f}",
            )
        )
    if not scan_health.get("scan_accounting_present"):
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.shim_scan_incomplete_accounting",
                "shim_dependency_report_missing_scan_accounting",
            )
        )
    reintroduced = _reintroduced_deleted_shim_modules()
    if reintroduced:
        modules = ", ".join(reintroduced[:5])
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.deleted_shim_reintroduced",
                f"deleted_shim_paths_reintroduced={len(reintroduced)}"
                + (f" modules={modules}" if modules else ""),
            )
        )
    if safe_to_remove_shim_count:
        ctx.warnings.append(
            check_registry.format_check_message(
                "paths.safe_to_remove_shim_retained",
                f"safe_to_remove_shims_still_present={safe_to_remove_shim_count}",
            )
        )


def _reintroduced_deleted_shim_modules() -> tuple[str, ...]:
    repo_root = event_artifact_paths.repo_root()
    modules: list[str] = []
    for entry in event_alpha_shims.deleted_shim_entries(root=repo_root):
        path = repo_root / Path(*entry.old_module.split(".")).with_suffix(".py")
        if path.exists():
            modules.append(entry.old_module)
    return tuple(modules)


def _apply_namespace_profile_checks(ctx: SimpleNamespace) -> None:
    runs, alerts, feedback, outcomes = ctx.runs, ctx.alerts, ctx.feedback, ctx.outcomes
    namespaces = {event_alpha_artifacts.row_namespace(row) for row in (*runs, *alerts, *feedback, *outcomes)}
    profiles = {event_alpha_artifacts.row_profile(row) for row in (*runs, *alerts, *feedback, *outcomes)}
    if ctx.artifact_namespace and any(ns not in {ctx.artifact_namespace, "legacy"} for ns in namespaces):
        ctx.blockers.append("mixed artifact namespaces after filtering")
    elif len(namespaces - {"legacy"}) > 1:
        (ctx.blockers if ctx.strict else ctx.warnings).append("multiple artifact namespaces present")
    if ctx.profile and any(item not in {ctx.profile, "default"} for item in profiles):
        ctx.warnings.append("rows from multiple profiles are present")
    if ctx.provider_health_rows is not None and ctx.profile in {"no_key_live", "api_live", "full_llm_live", "research_send"}:
        if not ctx.provider_health_rows:
            message = "provider health rows missing for live/burn-in profile"
            (ctx.blockers if ctx.strict else ctx.warnings).append(message)
    if ctx.profile in {"full_llm_live", "no_key_llm"} and not list(ctx.llm_budget_rows):
        ctx.warnings.append("LLM budget rows missing for LLM profile")
    ctx.namespaces = namespaces
    ctx.profiles = profiles


def _attach_core_card_context(ctx: SimpleNamespace) -> None:
    alerts = ctx.alerts
    acquisition_rows = ctx.acquisition_rows
    core_rows = ctx.core_rows
    hypotheses = ctx.hypotheses
    watchlist = ctx.watchlist
    card_file_paths = [Path(path) for path in ctx.card_paths]
    research_card_paths = [path for path in card_file_paths if path.name != "index.md"]
    daily_brief_card_names = _daily_brief_card_names(ctx.daily_brief_path)
    card_count = len(research_card_paths)
    index_present = any(path.name == "index.md" for path in card_file_paths)
    cards_missing_lineage = sum(1 for path in research_card_paths if not event_research_cards.card_has_current_lineage(path))
    cards_missing_feedback_target = sum(1 for path in research_card_paths if not event_research_cards.card_feedback_target(path))
    card_group_map = event_research_cards.card_index_group_map(research_card_paths)
    card_core_ids = {value for path in research_card_paths for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_paths_by_core_id = {
        value: path
        for path in research_card_paths
        for value in (event_research_cards.card_core_opportunity_id(path),)
        if value
    }
    card_feedback_targets = {value for path in research_card_paths for value in (event_research_cards.card_feedback_target(path),) if value}
    visible_core = (
        event_core_opportunity_store.core_opportunities_from_rows(core_rows)
        if core_rows
        else event_core_opportunities.visible_core_opportunities([*watchlist, *alerts, *hypotheses])
    )
    visible_core_ids = {item.core_opportunity_id for item in visible_core}
    visible_core_by_id = {item.core_opportunity_id: item for item in visible_core}
    normalized_core_rows_by_id = {
        item.core_opportunity_id: dict(item.primary_row)
        for item in visible_core
        if item.core_opportunity_id
    }
    store_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows
        if str(row.get("core_opportunity_id") or "").strip()
    }
    core_rows_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows
        if str(row.get("core_opportunity_id") or "").strip()
    }
    core_store_available = bool(store_core_ids)
    visible_missing_store_rows = len(visible_core_ids - store_core_ids) if core_store_available else len(visible_core_ids)
    duplicate_store_rows = max(0, len(core_rows) - len(store_core_ids))
    store_rows_missing_card_path = sum(
        1
        for row in core_rows
        if not str(row.get("card_path") or row.get("research_card_path") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in card_paths_by_core_id
    )
    visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids)
    visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
    )
    core_card_paths = [
        path for path in research_card_paths
        if (card_group_map.get(path) or event_research_cards.card_index_group(path)) == "Core Opportunity Cards"
    ]
    core_cards_missing_store = sum(
        1
        for path in core_card_paths
        if event_research_cards.card_core_opportunity_id(path) not in store_core_ids
    )
    visible_core_cards_missing_store = core_cards_missing_store
    orphan_core_cards = core_cards_missing_store
    card_group_mismatches = sum(
        1
        for path in research_card_paths
        if (not daily_brief_card_names or path.name in daily_brief_card_names)
        and path in card_group_map
        and _expected_card_group_for_store_core(
            visible_core_by_id.get(str(event_research_cards.card_core_opportunity_id(path) or ""))
        ) not in {None, card_group_map[path]}
    )
    diagnostic_fake_core = sum(
        1
        for row in alerts
        if (bool(row.get("is_diagnostic_snapshot")) or event_core_opportunities.row_is_diagnostic(row))
        and str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id_status") or "") not in {"diagnostic_support", "canonical"}
    )
    snapshot_core_missing_store = sum(
        1
        for row in alerts
        if str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in store_core_ids
        and not bool(row.get("is_diagnostic_snapshot"))
    )
    acquisition_core_missing_store = sum(
        1
        for row in acquisition_rows
        if str(row.get("core_opportunity_id") or "").strip()
        and str(row.get("core_opportunity_id") or "").strip() not in store_core_ids
        and str(row.get("core_opportunity_id_status") or "") not in {"diagnostic_support", "canonical"}
    )
    card_primary_mismatches = _card_primary_mismatches(research_card_paths, normalized_core_rows_by_id)
    card_acquisition_mismatches = _card_acquisition_count_mismatches(research_card_paths, normalized_core_rows_by_id, acquisition_rows)
    card_source_pack_mismatches = _card_source_pack_mismatches(research_card_paths, normalized_core_rows_by_id, acquisition_rows)
    card_support_blockers = _card_primary_section_contains_support_row_blockers(research_card_paths, normalized_core_rows_by_id)
    card_upgrade_inconsistent = _card_upgrade_text_inconsistent_with_final_level(research_card_paths, normalized_core_rows_by_id)
    card_market_missing = _card_market_confirmation_missing_but_core_has_market_confirmation(research_card_paths, normalized_core_rows_by_id)
    card_source_unknown = _card_latest_source_unknown_but_accepted_evidence_exists(research_card_paths, normalized_core_rows_by_id, acquisition_rows)
    _merge_context(ctx, locals())


def _attach_artifact_conflict_context(ctx: SimpleNamespace) -> None:
    acquisition_rows = ctx.acquisition_rows
    alerts = ctx.alerts
    core_rows = ctx.core_rows
    daily_brief_path = ctx.daily_brief_path
    delivery_rows = ctx.delivery_rows
    fade_review_candidates = ctx.fade_review_candidates
    incidents = ctx.incidents
    integrated_candidates = ctx.integrated_candidates
    integrated_delivery_path = ctx.integrated_delivery_path
    integrated_manifest_path = ctx.integrated_manifest_path
    integrated_outcomes_path = ctx.integrated_outcomes_path
    integrated_source_coverage_json_path = ctx.integrated_source_coverage_json_path
    market_anomalies = ctx.market_anomalies
    namespace_dir = ctx.namespace_dir
    official_exchange_candidates = ctx.official_exchange_candidates
    protocol_fundamentals = ctx.protocol_fundamentals
    research_card_paths = ctx.research_card_paths
    scheduled_catalysts = ctx.scheduled_catalysts
    source_coverage_report_path = ctx.source_coverage_report_path
    runs = ctx.runs
    feedback = ctx.feedback
    outcomes = ctx.outcomes
    hypotheses = ctx.hypotheses
    watchlist = ctx.watchlist
    derivatives_state = ctx.derivatives_state
    dex_pool_state = ctx.dex_pool_state
    dex_pool_anomalies = ctx.dex_pool_anomalies
    unlock_candidates = ctx.unlock_candidates
    audit_impact_mismatch = 0
    audit_source_pack_mismatch = 0
    market_freshness_contradictions = sum(1 for row in core_rows if _core_row_has_market_freshness_contradiction(row))
    promoted_core_in_weak = _promoted_core_rows_that_are_weak(core_rows)
    core_route_conflicts = _core_route_conflicts_with_opportunity_level(core_rows)
    live_confirmation_conflicts = _live_confirmation_conflicts(core_rows, profile=ctx.profile, artifact_namespace=ctx.artifact_namespace)
    raw_core_conflicts = _raw_core_live_confirmation_conflicts(core_rows, profile=ctx.profile, artifact_namespace=ctx.artifact_namespace)
    opportunity_lane_conflicts = _opportunity_lane_conflicts(core_rows)
    market_anomaly_conflicts = _market_anomaly_artifact_conflicts(market_anomalies)
    official_exchange_conflicts = _official_exchange_artifact_conflicts(official_exchange_candidates)
    scheduled_conflicts = _scheduled_catalyst_artifact_conflicts((*scheduled_catalysts, *unlock_candidates))
    derivatives_conflicts = _derivatives_crowding_artifact_conflicts((*derivatives_state, *fade_review_candidates))
    operator_dir = (
        Path(ctx.inspected_alert_store_path).parent
        if ctx.inspected_alert_store_path is not None
        else (Path(source_coverage_report_path).parent if source_coverage_report_path is not None else None)
    )
    preview_path = (
        operator_dir / event_integrated_radar.NOTIFICATION_PREVIEW_FILENAME
        if operator_dir is not None
        else None
    )
    if preview_path is not None and not preview_path.exists():
        legacy_preview = operator_dir / "event_alpha_notification_preview.md" if operator_dir is not None else None
        if legacy_preview is not None and legacy_preview.exists():
            try:
                legacy_preview_text = legacy_preview.read_text(encoding="utf-8", errors="replace")
            except OSError:
                legacy_preview_text = ""
            if "Integrated Radar Preview" in legacy_preview_text:
                preview_path = legacy_preview
    integrated_conflicts = _integrated_radar_artifact_conflicts(
        integrated_candidates,
        core_rows=core_rows,
        research_card_paths=research_card_paths,
        daily_brief_path=daily_brief_path,
        manifest_path=integrated_manifest_path,
        source_coverage_json_path=integrated_source_coverage_json_path,
        delivery_path=integrated_delivery_path,
        outcome_path=integrated_outcomes_path,
        preview_path=preview_path,
    )
    _attach_outcome_evidence_jsonl_diagnostics(ctx)
    namespace_status = event_alpha_namespace_status.load_namespace_status(namespace_dir)
    structured_path_conflicts = _structured_operator_path_conflicts(
        (*runs, *alerts, *feedback, *outcomes, *hypotheses, *core_rows, *watchlist, *incidents, *acquisition_rows,
         *market_anomalies, *official_exchange_candidates, *scheduled_catalysts, *unlock_candidates, *derivatives_state,
         *fade_review_candidates, *dex_pool_state, *dex_pool_anomalies, *protocol_fundamentals, *integrated_candidates,
         *delivery_rows)
    )
    if namespace_dir is not None:
        structured_path_conflicts = max(
            structured_path_conflicts,
            _structured_operator_path_file_conflicts(namespace_dir),
        )
    integrated_conflicts["operator_structured_path_absolute"] = max(
        int(integrated_conflicts.get("operator_structured_path_absolute", 0)),
        int(structured_path_conflicts),
    )
    source_coverage_conflicts = _source_coverage_metadata_conflicts((*core_rows, *acquisition_rows))
    source_coverage_report_conflicts = _source_coverage_report_conflicts(source_coverage_report_path)
    live_provider_readiness_conflicts = _live_provider_readiness_conflicts(namespace_dir)
    coinalyze_preflight_conflicts = event_coinalyze_preflight.artifact_conflicts(namespace_dir)
    bybit_announcements_conflicts = event_bybit_announcements_preflight.artifact_conflicts(namespace_dir)
    unlock_calendar_conflicts = event_unlock_calendar_preflight.artifact_conflicts(namespace_dir)
    dex_onchain_conflicts = event_dex_onchain_readiness.artifact_conflicts(namespace_dir)
    official_exchange_activation_conflicts = event_official_exchange_activation.artifact_conflicts(namespace_dir)
    instrument_resolution_conflicts = event_instrument_resolver.artifact_conflicts(namespace_dir)
    cryptopanic_conflicts = _cryptopanic_artifact_conflicts(
        acquisition_rows=acquisition_rows,
        core_rows=core_rows,
        research_card_paths=research_card_paths,
        source_coverage_report_path=source_coverage_report_path,
        run_rows=runs,
    )
    evidence_count_mismatches = _evidence_count_mismatches(acquisition_rows)
    acquisition_final_conflicts = _evidence_acquisition_final_field_conflicts(acquisition_rows)
    visible_sector_cores = _visible_sector_core_without_config(core_rows)
    duplicate_proxy_cores = _duplicate_proxy_core_rows(core_rows)
    daily_brief_conflicts = _daily_brief_consistency_conflicts(
        daily_brief_path,
        runs=runs,
        core_rows=core_rows,
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        source_coverage_report_path=source_coverage_report_path,
        profile=ctx.profile,
        artifact_namespace=ctx.artifact_namespace,
    )
    upgrade_high_priority = 0
    _merge_context(ctx, locals())


def _attach_notification_context(ctx: SimpleNamespace) -> None:
    alerts = ctx.alerts
    card_file_paths = ctx.card_file_paths
    card_core_ids = ctx.card_core_ids
    card_feedback_targets = ctx.card_feedback_targets
    core_rows = ctx.core_rows
    core_rows_by_id = ctx.core_rows_by_id
    delivery_rows = ctx.delivery_rows
    feedback = ctx.feedback
    hypotheses = ctx.hypotheses
    latest_run = (
        event_alpha_operator_state.enrich_run_row_from_core_store(ctx.namespace_dir, ctx.latest_run)
        if ctx.latest_run and ctx.namespace_dir is not None
        else ctx.latest_run
    )
    latest_run_id = ctx.latest_run_id
    normalized_core_rows_by_id = ctx.normalized_core_rows_by_id
    store_core_ids = ctx.store_core_ids
    visible_core = ctx.visible_core
    watchlist = ctx.watchlist
    fresh_visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids and _core_has_fresh_rows(item))
    fresh_visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
        and _core_has_fresh_rows(item)
    )
    snapshots_missing_core = sum(1 for row in alerts if _alert_snapshot_should_have_core_id(row) and not str(row.get("core_opportunity_id") or "").strip())
    snapshots_missing_feedback = sum(
        1 for row in alerts
        if _alert_snapshot_should_have_core_id(row)
        and not _alert_snapshot_is_diagnostic(row)
        and not _alert_has_feedback_target(row)
    )
    diagnostic_snapshots_missing_feedback = sum(1 for row in alerts if _alert_snapshot_is_diagnostic(row) and not _alert_has_feedback_target(row))
    review_cards_dir = card_file_paths[0].parent if card_file_paths else None
    review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        ctx.profile,
        ctx.artifact_namespace,
        include_diagnostics=True,
        notification_runs=ctx.runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    default_review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        ctx.profile,
        ctx.artifact_namespace,
        include_diagnostics=False,
        notification_runs=ctx.runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    inbox_core_missing_card = sum(1 for item in review_items if not item.is_diagnostic and item.core_opportunity_id and not item.card_path)
    inbox_core_alert_target = sum(
        1 for item in review_items
        if not item.is_diagnostic
        and item.core_opportunity_id
        and item.feedback_target
        and item.feedback_target != item.core_opportunity_id
        and item.feedback_target.startswith("ea:")
    )
    inbox_diag_visible_default = sum(1 for item in default_review_items if item.is_diagnostic)
    audit_primary_not_canonical = _audit_primary_snapshot_not_canonical_when_canonical_exists(alerts, store_core_ids)
    _merge_context(ctx, locals())
    doctor_check_context = SimpleNamespace(**vars(ctx))
    doctor_integrated_radar_checks.apply_core_card_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_provider_readiness_checks.apply_structured_artifact_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_integrated_radar_checks.apply_integrated_artifact_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_path_checks.apply_integrated_path_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_source_coverage_checks.apply_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_provider_readiness_checks.apply_preflight_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_integrated_radar_checks.apply_identity_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    doctor_operations_checks.apply_checks(doctor_check_context, ctx.blockers, ctx.warnings)
    research_review_enabled_but_lane_missing = 0
    research_review_candidates_without_delivery = 0
    if latest_run:
        rr_enabled = bool(latest_run.get("research_review_digest_enabled"))
        rr_candidates = _as_int(latest_run.get("research_review_digest_candidates"))
        rr_would_send = _as_int(latest_run.get("research_review_digest_would_send"))
        latest_lanes = {
            str(row.get("lane") or "")
            for row in delivery_rows
            if isinstance(row, Mapping) and latest_run_id and str(row.get("run_id") or "") == str(latest_run_id)
        }
        if rr_enabled and (rr_candidates or rr_would_send) and "research_review_digest" not in latest_lanes:
            research_review_enabled_but_lane_missing = 1
            if rr_candidates:
                research_review_candidates_without_delivery = 1
    delivery_summary = _delivery.summarize_delivery_rows([row for row in delivery_rows if isinstance(row, Mapping)])
    delivery_conflicts = _notification_delivery_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        core_rows_by_id=core_rows_by_id,
        latest_run_id=latest_run_id,
        strict_scope=ctx.effective_delivery_scope,
    )
    preview_conflicts = _notification_preview_consistency_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        latest_run=latest_run,
        core_rows=core_rows,
        latest_run_id=latest_run_id,
    )
    daily_brief_operator_conflicts = _daily_brief_operator_semantic_conflicts(
        ctx.daily_brief_path,
        latest_run=latest_run,
    )
    _merge_context(ctx, locals())
    doctor_notification_checks.apply_checks(SimpleNamespace(**vars(ctx)), ctx.blockers, ctx.warnings)


def _attach_quality_incident_context(ctx: SimpleNamespace) -> None:
    alerts = ctx.alerts
    core_rows = ctx.core_rows
    hypotheses = ctx.hypotheses
    incidents = ctx.incidents
    runs = ctx.runs
    watchlist = ctx.watchlist
    quality = _quality_missing_summary(hypotheses=hypotheses, watchlist=watchlist, alerts=alerts)
    fresh_missing = (
        quality["fresh_hypothesis_rows_missing_top_level_quality"]
        + quality["fresh_watchlist_rows_missing_top_level_quality"]
        + quality["fresh_alert_rows_missing_top_level_quality"]
    )
    route_conflict_alerts = _latest_run_rows(alerts, runs)
    route_conflicts = _alertable_quality_route_conflicts(route_conflict_alerts)
    snapshot_core_conflicts = _alert_snapshot_core_conflicts(route_conflict_alerts, core_rows)
    fresh_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=False)
    legacy_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=True)
    missing_final_route = _missing_final_route_rows(route_conflict_alerts)
    fresh_missing_final_route = _missing_final_route_rows(route_conflict_alerts, legacy=False)
    watchlist_conflicts = _watchlist_quality_state_conflicts(watchlist)
    incident_linkage = _incident_linkage_summary(hypotheses=hypotheses, watchlist=watchlist, alerts=alerts, incidents=incidents)
    _merge_context(ctx, locals())
    doctor_outcome_checks.apply_checks(SimpleNamespace(**vars(ctx)), ctx.blockers, ctx.warnings)
    if ctx.schema_result.schema_validation_errors:
        ctx.warnings.append(
            check_registry.format_check_message(
                "schema.validation_errors",
                f"schema_validation_errors={ctx.schema_result.schema_validation_errors}",
            )
        )
    if incident_linkage["invalid_canonical_incident_rows"]:
        message = f"invalid_canonical_incident_rows={incident_linkage['invalid_canonical_incident_rows']}"
        (ctx.blockers if ctx.strict else ctx.warnings).append(message)
    consistency_phase = consistency_doctor.ConsistencyDoctorResult()
    ctx.blockers.extend(consistency_phase.blockers)
    ctx.warnings.extend(consistency_phase.warnings)
    ctx.consistency_phase = consistency_phase


def _load_and_filter_doctor_artifacts(options: Mapping[str, Any]) -> SimpleNamespace:
    raw = _load_raw_doctor_artifacts(options)
    filtered = _filter_doctor_artifacts(raw, options)
    filtered.raw_api = sum(
        1
        for row in (*raw.raw_runs, *raw.raw_alerts, *raw.raw_feedback, *raw.raw_outcomes)
        if event_alpha_artifacts.is_api_row(row)
    )
    filtered.integrated_manifest_path = raw.integrated_manifest_path
    filtered.integrated_source_coverage_json_path = raw.integrated_source_coverage_json_path
    filtered.integrated_delivery_path = raw.integrated_delivery_path
    filtered.integrated_outcomes_path = raw.integrated_outcomes_path
    filtered.outcome_evidence_jsonl_diagnostics = raw.outcome_evidence_jsonl_diagnostics
    return filtered


def _default_doctor_artifact_dir(options: Mapping[str, Any]) -> Path | None:
    if options["inspected_alert_store_path"] is not None:
        return Path(options["inspected_alert_store_path"]).parent
    if options["source_coverage_report_path"] is not None:
        return Path(options["source_coverage_report_path"]).parent
    return None


def _load_raw_doctor_artifacts(options: Mapping[str, Any]) -> SimpleNamespace:
    default_dir = _default_doctor_artifact_dir(options)
    raw_fade_review_candidates = _load_raw_fade_review_candidates(options, default_dir)
    integrated_path = (
        default_dir / "event_integrated_radar_candidates.jsonl"
        if default_dir is not None
        else None
    )
    integrated_dir = integrated_path.parent if integrated_path is not None else None
    integrated_candidate_read = artifact_json_lines.read_jsonl(integrated_path)
    outcome_evidence_jsonl_diagnostics = _outcome_evidence_jsonl_diagnostics(
        default_dir,
        candidate_diagnostics=integrated_candidate_read.diagnostics,
    )
    return SimpleNamespace(
        raw_runs=[dict(row) for row in options["run_rows"] if isinstance(row, Mapping)],
        raw_alerts=[dict(row) for row in options["alert_rows"] if isinstance(row, Mapping)],
        raw_feedback=[dict(row) for row in options["feedback_rows"] if isinstance(row, Mapping)],
        raw_outcomes=[dict(row) for row in options["outcome_rows"] if isinstance(row, Mapping)],
        raw_hypotheses=[_row(row) for row in options["hypothesis_rows"]],
        raw_core_rows=[_row(row) for row in options["core_opportunity_rows"]],
        raw_watchlist=[_row(row) for row in options["watchlist_rows"]],
        raw_incidents=[_row(row) for row in options["incident_rows"]],
        raw_acquisition_rows=[
            dict(row) for row in options["evidence_acquisition_rows"] if isinstance(row, Mapping)
        ],
        raw_market_anomalies=_load_optional_rows(
            options["market_anomaly_rows"],
            lambda: event_market_anomaly_scanner.load_market_anomaly_rows(default_dir),
        ),
        raw_official_exchange_candidates=_load_optional_rows(
            options["official_exchange_candidate_rows"],
            lambda: event_official_exchange.load_official_listing_candidates(default_dir),
        ),
        raw_scheduled_catalysts=_load_optional_rows(
            options["scheduled_catalyst_rows"],
            lambda: event_scheduled_catalysts.load_scheduled_catalysts(default_dir),
        ),
        raw_unlock_candidates=_load_optional_rows(
            options["unlock_candidate_rows"],
            lambda: event_scheduled_catalysts.load_unlock_candidates(default_dir),
        ),
        raw_derivatives_state=_load_optional_rows(
            options["derivatives_state_rows"],
            lambda: event_derivatives_crowding.load_derivatives_state(default_dir),
        ),
        raw_fade_review_candidates=raw_fade_review_candidates,
        raw_dex_pool_state=list(event_dex_onchain_readiness.load_dex_pool_state(default_dir)),
        raw_dex_pool_anomalies=list(event_dex_onchain_readiness.load_dex_pool_anomalies(default_dir)),
        raw_protocol_fundamentals=list(event_dex_onchain_readiness.load_protocol_fundamentals(default_dir)),
        raw_integrated_candidates=list(integrated_candidate_read.rows),
        outcome_evidence_jsonl_diagnostics=outcome_evidence_jsonl_diagnostics,
        raw_burn_in_scorecard=_read_json(default_dir / "event_alpha_burn_in_scorecard.json" if default_dir is not None else None),
        raw_source_yield_report=_read_json(default_dir / "event_alpha_source_yield_report.json" if default_dir is not None else None),
        raw_daily_review_inbox=_read_json(default_dir / "event_alpha_daily_review_inbox.json" if default_dir is not None else None),
        raw_daily_burn_in_run=_read_json(default_dir / "event_alpha_daily_burn_in_run.json" if default_dir is not None else None),
        raw_candidate_mode_manifest=_read_json(default_dir / "event_alpha_candidate_mode_manifest.json" if default_dir is not None else None),
        raw_burn_in_namespace_policy=_read_json(default_dir / "event_alpha_burn_in_namespace_policy.json" if default_dir is not None else None),
        raw_burn_in_archive_manifest=_read_json(default_dir / "event_alpha_burn_in_archive_manifest.json" if default_dir is not None else None),
        integrated_manifest_path=(
            integrated_dir / "event_integrated_radar_input_manifest.json"
            if integrated_dir is not None
            else None
        ),
        integrated_source_coverage_json_path=(
            integrated_dir / "event_alpha_source_coverage.json"
            if integrated_dir is not None
            else None
        ),
        integrated_delivery_path=(
            integrated_dir / event_integrated_radar.INTEGRATED_DELIVERIES_FILENAME
            if integrated_dir is not None
            else None
        ),
        integrated_outcomes_path=(
            integrated_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
            if integrated_dir is not None
            else None
        ),
    )


def _load_optional_rows(rows: Iterable[Mapping[str, Any]] | None, loader: Callable[[], Iterable[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    if rows is None:
        return [dict(row) for row in loader() if isinstance(row, Mapping)]
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _outcome_evidence_jsonl_diagnostics(
    default_dir: Path | None,
    *,
    candidate_diagnostics: Any,
) -> dict[str, Any]:
    if default_dir is None:
        return {}
    return {
        "candidates": candidate_diagnostics,
        "core": artifact_json_lines.read_jsonl(
            default_dir / "event_core_opportunities.jsonl"
        ).diagnostics,
        "integrated_outcomes": artifact_json_lines.read_jsonl(
            default_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        ).diagnostics,
        "alpha_outcomes": artifact_json_lines.read_jsonl(
            default_dir / "event_alpha_outcomes.jsonl"
        ).diagnostics,
    }


def _attach_outcome_evidence_jsonl_diagnostics(ctx: SimpleNamespace) -> None:
    diagnostics = ctx.outcome_evidence_jsonl_diagnostics
    duplicate_counts = {
        name: len(item.duplicate_key_lines)
        for name, item in diagnostics.items()
        if item.duplicate_key_lines
    }
    malformed_counts = {
        name: len(item.invalid_json_lines) + len(item.non_object_lines)
        for name, item in diagnostics.items()
        if item.invalid_json_lines or item.non_object_lines
    }
    read_errors = tuple(sorted(name for name, item in diagnostics.items() if item.read_error))
    messages: list[str] = []
    if duplicate_counts:
        messages.append(
            "outcome_evidence_duplicate_json_keys="
            + ",".join(f"{name}:{duplicate_counts[name]}" for name in sorted(duplicate_counts))
        )
    if malformed_counts:
        messages.append(
            "outcome_evidence_invalid_jsonl="
            + ",".join(f"{name}:{malformed_counts[name]}" for name in sorted(malformed_counts))
        )
    if read_errors:
        messages.append("outcome_evidence_jsonl_read_errors=" + ",".join(read_errors))
    target = ctx.blockers if ctx.strict else ctx.warnings
    target.extend(
        check_registry.format_check_message("outcomes.eligibility_firewall", message)
        for message in messages
    )


def _load_raw_fade_review_candidates(options: Mapping[str, Any], default_dir: Path | None) -> list[dict[str, Any]]:
    rows = options["fade_review_candidate_rows"]
    if rows is not None:
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    candidates = list(event_derivatives_crowding.load_derivatives_candidates(default_dir))
    if not candidates:
        candidates = list(event_derivatives_crowding.load_fade_review_candidates(default_dir))
    return [dict(row) for row in candidates if isinstance(row, Mapping)]


def _filter_doctor_artifacts(raw: SimpleNamespace, options: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        runs=_filter_doctor_rows(raw.raw_runs, options),
        alerts=_filter_doctor_rows(raw.raw_alerts, options),
        feedback=_filter_doctor_rows(raw.raw_feedback, options),
        outcomes=_filter_doctor_rows(raw.raw_outcomes, options),
        hypotheses=_filter_doctor_rows(raw.raw_hypotheses, options),
        core_rows=_filter_doctor_rows(raw.raw_core_rows, options),
        watchlist=_filter_watchlist_rows_for_doctor(raw.raw_watchlist, **_doctor_filter_options(options)),
        incidents=_filter_doctor_rows(raw.raw_incidents, options),
        acquisition_rows=_filter_doctor_rows(raw.raw_acquisition_rows, options),
        market_anomalies=_filter_doctor_rows(raw.raw_market_anomalies, options),
        official_exchange_candidates=_filter_doctor_rows(raw.raw_official_exchange_candidates, options),
        scheduled_catalysts=_filter_doctor_rows(raw.raw_scheduled_catalysts, options),
        unlock_candidates=_filter_doctor_rows(raw.raw_unlock_candidates, options),
        derivatives_state=_filter_doctor_rows(raw.raw_derivatives_state, options),
        fade_review_candidates=_filter_doctor_rows(raw.raw_fade_review_candidates, options),
        dex_pool_state=_filter_doctor_rows(raw.raw_dex_pool_state, options),
        dex_pool_anomalies=_filter_doctor_rows(raw.raw_dex_pool_anomalies, options),
        protocol_fundamentals=_filter_doctor_rows(raw.raw_protocol_fundamentals, options),
        integrated_candidates=_filter_doctor_rows(raw.raw_integrated_candidates, options),
        burn_in_scorecard=raw.raw_burn_in_scorecard,
        source_yield_report=raw.raw_source_yield_report,
        daily_review_inbox=raw.raw_daily_review_inbox,
        daily_burn_in_run=raw.raw_daily_burn_in_run,
        candidate_mode_manifest=raw.raw_candidate_mode_manifest,
        burn_in_namespace_policy=raw.raw_burn_in_namespace_policy,
        burn_in_archive_manifest=raw.raw_burn_in_archive_manifest,
    )


def _filter_doctor_rows(rows: Iterable[Mapping[str, Any]], options: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(rows, **_doctor_filter_options(options))


def _doctor_filter_options(options: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "profile": options["profile"],
        "artifact_namespace": options["artifact_namespace"],
        "include_test_artifacts": options["include_test_artifacts"],
        "include_api_artifacts": options["include_api_artifacts"],
    }


def _inspect_run_snapshot_context(
    *,
    runs: list[Mapping[str, Any]],
    alerts: list[Mapping[str, Any]],
    feedback: list[Mapping[str, Any]],
    outcomes: list[Mapping[str, Any]],
    inspected_alert_store_path: str | Path | None,
    include_test_artifacts: bool,
    delivery_strict_scope: str | None,
    strict: bool,
) -> SimpleNamespace:
    blockers: list[str] = []
    warnings: list[str] = []
    matching_snapshot_runs = 0
    missing_snapshot_runs = 0
    external_snapshot_runs = 0
    if not runs:
        blockers.append("no matching operational/burn-in run rows found")
    latest_run_id = _latest_run_id(runs)
    latest_run = next((row for row in runs if str(row.get("run_id") or "") == str(latest_run_id or "")), None)
    effective_delivery_scope = _normalize_delivery_strict_scope(
        delivery_strict_scope,
        latest_run_id=latest_run_id,
        strict=strict,
    )
    run_ids = {str(row.get("run_id") or "") for row in runs if row.get("run_id")}
    alert_run_ids = {str(row.get("run_id") or "") for row in alerts if row.get("run_id")}
    alert_counts_by_run_id = _alert_counts_by_run_id(alerts)
    for row in runs:
        if event_alpha_artifacts.is_non_operational_row(row) and not include_test_artifacts:
            continue
        if int(row.get("alertable") or 0) <= 0:
            continue
        availability = event_alpha_artifacts.classify_snapshot_availability(
            row,
            inspected_alert_store_path,
            alert_counts_by_run_id.get(str(row.get("run_id") or "").strip(), 0),
        )
        matching_snapshot_runs += int(availability == event_alpha_artifacts.SNAPSHOT_AVAILABLE)
        external_snapshot_runs += int(availability in {
            event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH,
            event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL,
        })
        missing_snapshot_runs += int(availability not in {
            event_alpha_artifacts.SNAPSHOT_AVAILABLE,
            event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH,
            event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL,
        })
        _append_snapshot_availability_messages(
            row,
            availability,
            latest_run_id=latest_run_id,
            effective_delivery_scope=effective_delivery_scope,
            strict=strict,
            blockers=blockers,
            warnings=warnings,
        )
    _append_lineage_match_messages(
        alerts=alerts,
        feedback=feedback,
        outcomes=outcomes,
        run_ids=run_ids,
        alert_run_ids=alert_run_ids,
        strict=strict,
        blockers=blockers,
        warnings=warnings,
    )
    return SimpleNamespace(
        blockers=blockers,
        warnings=warnings,
        matching_snapshot_runs=matching_snapshot_runs,
        missing_snapshot_runs=missing_snapshot_runs,
        external_snapshot_runs=external_snapshot_runs,
        latest_run_id=latest_run_id,
        latest_run=latest_run,
        effective_delivery_scope=effective_delivery_scope,
    )


def _alert_counts_by_run_id(alerts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in alerts:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            counts[run_id] = counts.get(run_id, 0) + 1
    return counts


def _append_snapshot_availability_messages(
    row: Mapping[str, Any],
    availability: str,
    *,
    latest_run_id: str | None,
    effective_delivery_scope: str,
    strict: bool,
    blockers: list[str],
    warnings: list[str],
) -> None:
    run_id = str(row.get("run_id") or "").strip()
    stale_for_latest_scope = (
        effective_delivery_scope == "latest_run"
        and bool(latest_run_id)
        and bool(run_id)
        and run_id != latest_run_id
    )
    if not bool(row.get("snapshot_write_success")):
        if str(row.get("snapshot_write_block_reason") or "") == "test_or_fixture_run":
            warnings.append(f"run {row.get('run_id') or 'unknown'} is test/fixture and skipped snapshots")
            if availability == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL:
                _record_snapshot_availability_issue(
                    row,
                    availability,
                    blockers=blockers,
                    warnings=warnings,
                    strict=strict,
                )
        else:
            message = f"alertable run {row.get('run_id') or 'unknown'} has no successful snapshot write"
            (warnings if stale_for_latest_scope else blockers).append(message)
    elif int(row.get("alertable") or 0) > 0 and int(row.get("snapshot_rows_written") or 0) <= 0:
        message = f"alertable run {row.get('run_id') or 'unknown'} wrote zero alert snapshots"
        (warnings if stale_for_latest_scope else blockers).append(message)
    elif availability != event_alpha_artifacts.SNAPSHOT_AVAILABLE:
        if stale_for_latest_scope:
            warnings.append(f"stale alertable run {row.get('run_id') or 'unknown'} has snapshot availability={availability}")
        else:
            _record_snapshot_availability_issue(
                row,
                availability,
                blockers=blockers,
                warnings=warnings,
                strict=strict,
            )


def _append_lineage_match_messages(
    *,
    alerts: list[Mapping[str, Any]],
    feedback: list[Mapping[str, Any]],
    outcomes: list[Mapping[str, Any]],
    run_ids: set[str],
    alert_run_ids: set[str],
    strict: bool,
    blockers: list[str],
    warnings: list[str],
) -> None:
    orphan_alerts = sorted(alert_run_ids - run_ids)
    if orphan_alerts:
        warnings.append(f"alert snapshots reference unknown run_id(s): {', '.join(orphan_alerts[:5])}")
    if any(row.get("run_id") in (None, "") for row in alerts):
        warnings.append("legacy alert snapshots without run_id lineage are present")
    alert_keys = {str(row.get("alert_key") or "") for row in alerts if row.get("alert_key")}
    feedback_keys = {str(row.get("key") or row.get("alert_key") or "") for row in feedback}
    outcome_keys = {str(row.get("alert_key") or "") for row in outcomes}
    unknown_feedback = sorted(key for key in feedback_keys if key and key not in alert_keys)
    unknown_outcomes = sorted(key for key in outcome_keys if key and key not in alert_keys)
    if unknown_feedback:
        message = f"feedback without matching alert snapshot: {', '.join(unknown_feedback[:5])}"
        (blockers if strict else warnings).append(message)
    if unknown_outcomes:
        message = f"outcomes without matching alert snapshot: {', '.join(unknown_outcomes[:5])}"
        (blockers if strict else warnings).append(message)


def _phase_only_doctor_result(
    *,
    status: str,
    profile: str | None,
    artifact_namespace: str | None,
    runs: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    feedback: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    card_paths: Iterable[str | Path],
    namespace_phase: namespace_doctor.NamespaceDoctorResult,
    schema_result: schema_doctor.SchemaDoctorResult,
    strict: bool,
    strict_api: bool,
    schema_only: bool,
    legacy_checks_skipped: bool,
    blockers: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> EventAlphaArtifactDoctorResult:
    card_file_paths = [Path(path) for path in card_paths]
    research_card_paths = [path for path in card_file_paths if path.name != "index.md"]
    index_present = any(path.name == "index.md" for path in card_file_paths)
    return EventAlphaArtifactDoctorResult(
        status=status,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_rows=len(tuple(runs)),
        alert_rows=len(tuple(alerts)),
        feedback_rows=len(tuple(feedback)),
        outcome_rows=len(tuple(outcomes)),
        card_files=len(research_card_paths),
        research_card_files=len(research_card_paths),
        research_card_index_present=index_present,
        namespace_status=namespace_phase.namespace_status,
        namespace_stale_deprecated=namespace_phase.namespace_stale_deprecated,
        namespace_superseded_by=namespace_phase.namespace_superseded_by,
        strict=bool(strict),
        strict_api=bool(strict_api),
        schema_only=bool(schema_only),
        legacy_checks_skipped=bool(legacy_checks_skipped),
        schema_rows_validated=schema_result.schema_rows_validated,
        schema_validation_errors=schema_result.schema_validation_errors,
        missing_required_fields=schema_result.missing_required_fields,
        invalid_enum_fields=schema_result.invalid_enum_fields,
        invalid_path_fields=schema_result.invalid_path_fields,
        invalid_safety_fields=schema_result.invalid_safety_fields,
        deprecated_field_usage=schema_result.deprecated_field_usage,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )

def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})

def _read_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    return list(artifact_json_lines.read_jsonl(path).rows)


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}

__all__ = (
    'diagnose_artifacts',
    '_phase_only_doctor_result',
    '_row',
    '_read_json',
    '_read_jsonl',
)
