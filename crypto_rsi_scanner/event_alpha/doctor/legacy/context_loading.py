"""Context Loading for the legacy artifact doctor."""

from __future__ import annotations

from .runtime import *

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
    include_legacy_artifacts: bool = False,
    inspected_alert_store_path: str | Path | None = None,
    strict: bool = False,
    strict_legacy: bool = False,
    delivery_strict_scope: str | None = None,
    include_stale_artifacts: bool = False,
    schema_only: bool = False,
    skip_legacy_checks: bool = False,
) -> EventAlphaArtifactDoctorResult:
    """Diagnose cross-artifact lineage, mode, and profile/namespace cleanliness."""
    raw_runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    raw_alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    raw_feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    raw_outcomes = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    raw_hypotheses = [_row(row) for row in hypothesis_rows]
    raw_core_rows = [_row(row) for row in core_opportunity_rows]
    raw_watchlist = [_row(row) for row in watchlist_rows]
    raw_incidents = [_row(row) for row in incident_rows]
    raw_acquisition_rows = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    if market_anomaly_rows is None:
        default_market_anomaly_path = None
        if inspected_alert_store_path is not None:
            default_market_anomaly_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_market_anomaly_path = Path(source_coverage_report_path).parent
        raw_market_anomalies = list(event_market_anomaly_scanner.load_market_anomaly_rows(default_market_anomaly_path))
    else:
        raw_market_anomalies = [dict(row) for row in market_anomaly_rows if isinstance(row, Mapping)]
    if official_exchange_candidate_rows is None:
        default_official_exchange_path = None
        if inspected_alert_store_path is not None:
            default_official_exchange_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_official_exchange_path = Path(source_coverage_report_path).parent
        raw_official_exchange_candidates = list(event_official_exchange.load_official_listing_candidates(default_official_exchange_path))
    else:
        raw_official_exchange_candidates = [dict(row) for row in official_exchange_candidate_rows if isinstance(row, Mapping)]
    if scheduled_catalyst_rows is None:
        default_scheduled_path = None
        if inspected_alert_store_path is not None:
            default_scheduled_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_scheduled_path = Path(source_coverage_report_path).parent
        raw_scheduled_catalysts = list(event_scheduled_catalysts.load_scheduled_catalysts(default_scheduled_path))
    else:
        raw_scheduled_catalysts = [dict(row) for row in scheduled_catalyst_rows if isinstance(row, Mapping)]
    if unlock_candidate_rows is None:
        default_unlock_path = None
        if inspected_alert_store_path is not None:
            default_unlock_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_unlock_path = Path(source_coverage_report_path).parent
        raw_unlock_candidates = list(event_scheduled_catalysts.load_unlock_candidates(default_unlock_path))
    else:
        raw_unlock_candidates = [dict(row) for row in unlock_candidate_rows if isinstance(row, Mapping)]
    if derivatives_state_rows is None:
        default_derivatives_path = None
        if inspected_alert_store_path is not None:
            default_derivatives_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_derivatives_path = Path(source_coverage_report_path).parent
        raw_derivatives_state = list(event_derivatives_crowding.load_derivatives_state(default_derivatives_path))
    else:
        raw_derivatives_state = [dict(row) for row in derivatives_state_rows if isinstance(row, Mapping)]
    if fade_review_candidate_rows is None:
        default_fade_review_path = None
        if inspected_alert_store_path is not None:
            default_fade_review_path = Path(inspected_alert_store_path).parent
        elif source_coverage_report_path is not None:
            default_fade_review_path = Path(source_coverage_report_path).parent
        raw_fade_review_candidates = list(event_derivatives_crowding.load_derivatives_candidates(default_fade_review_path))
        if not raw_fade_review_candidates:
            raw_fade_review_candidates = list(event_derivatives_crowding.load_fade_review_candidates(default_fade_review_path))
    else:
        raw_fade_review_candidates = [dict(row) for row in fade_review_candidate_rows if isinstance(row, Mapping)]
    default_dex_onchain_path = None
    if inspected_alert_store_path is not None:
        default_dex_onchain_path = Path(inspected_alert_store_path).parent
    elif source_coverage_report_path is not None:
        default_dex_onchain_path = Path(source_coverage_report_path).parent
    raw_dex_pool_state = list(event_dex_onchain_readiness.load_dex_pool_state(default_dex_onchain_path))
    raw_dex_pool_anomalies = list(event_dex_onchain_readiness.load_dex_pool_anomalies(default_dex_onchain_path))
    raw_protocol_fundamentals = list(event_dex_onchain_readiness.load_protocol_fundamentals(default_dex_onchain_path))
    default_integrated_path = None
    if inspected_alert_store_path is not None:
        default_integrated_path = Path(inspected_alert_store_path).parent / "event_integrated_radar_candidates.jsonl"
    elif source_coverage_report_path is not None:
        default_integrated_path = Path(source_coverage_report_path).parent / "event_integrated_radar_candidates.jsonl"
    raw_integrated_candidates = _read_jsonl(default_integrated_path) if default_integrated_path is not None else []
    default_integrated_dir = default_integrated_path.parent if default_integrated_path is not None else None
    integrated_manifest_path = (
        default_integrated_dir / "event_integrated_radar_input_manifest.json"
        if default_integrated_dir is not None
        else None
    )
    integrated_source_coverage_json_path = (
        default_integrated_dir / "event_alpha_source_coverage.json"
        if default_integrated_dir is not None
        else None
    )
    integrated_delivery_path = (
        default_integrated_dir / event_integrated_radar.INTEGRATED_DELIVERIES_FILENAME
        if default_integrated_dir is not None
        else None
    )
    integrated_outcomes_path = (
        default_integrated_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        if default_integrated_dir is not None
        else None
    )
    raw_legacy = sum(
        1 for row in (*raw_runs, *raw_alerts, *raw_feedback, *raw_outcomes)
        if event_alpha_artifacts.is_legacy_row(row)
    )
    runs = event_alpha_artifacts.filter_artifact_rows(
        raw_runs,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        raw_alerts,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    feedback = event_alpha_artifacts.filter_artifact_rows(
        raw_feedback,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    outcomes = event_alpha_artifacts.filter_artifact_rows(
        raw_outcomes,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    hypotheses = event_alpha_artifacts.filter_artifact_rows(
        raw_hypotheses,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    core_rows = event_alpha_artifacts.filter_artifact_rows(
        raw_core_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    watchlist = _filter_watchlist_rows_for_doctor(
        raw_watchlist,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    incidents = event_alpha_artifacts.filter_artifact_rows(
        raw_incidents,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
        raw_acquisition_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    market_anomalies = event_alpha_artifacts.filter_artifact_rows(
        raw_market_anomalies,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    official_exchange_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_official_exchange_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    scheduled_catalysts = event_alpha_artifacts.filter_artifact_rows(
        raw_scheduled_catalysts,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    unlock_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_unlock_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    derivatives_state = event_alpha_artifacts.filter_artifact_rows(
        raw_derivatives_state,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    fade_review_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_fade_review_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    dex_pool_state = event_alpha_artifacts.filter_artifact_rows(
        raw_dex_pool_state,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    dex_pool_anomalies = event_alpha_artifacts.filter_artifact_rows(
        raw_dex_pool_anomalies,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    protocol_fundamentals = event_alpha_artifacts.filter_artifact_rows(
        raw_protocol_fundamentals,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    integrated_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_integrated_candidates,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    namespace_dir = _artifact_namespace_dir(
        inspected_alert_store_path,
        source_coverage_report_path,
        daily_brief_path,
        integrated_outcomes_path,
    )
    namespace_phase = namespace_doctor.inspect_namespace(
        namespace_dir,
        include_stale_artifacts=include_stale_artifacts,
    )
    if namespace_phase.short_circuit:
        phase_status = "BLOCKED" if namespace_phase.blockers else "STALE"
        return _phase_only_doctor_result(
            status=phase_status,
            profile=profile,
            artifact_namespace=artifact_namespace,
            runs=runs,
            alerts=alerts,
            feedback=feedback,
            outcomes=outcomes,
            card_paths=card_paths,
            namespace_phase=namespace_phase,
            schema_result=schema_doctor.SchemaDoctorResult(),
            strict=strict,
            strict_legacy=strict_legacy,
            schema_only=schema_only,
            legacy_checks_skipped=True,
            blockers=namespace_phase.blockers,
            warnings=namespace_phase.warnings,
        )
    schema_result = schema_doctor.validate_namespace_artifacts(namespace_phase.namespace_dir)
    safety_result = safety_doctor.validate_schema_safety(
        schema_result,
        strict=strict,
        schema_only=schema_only,
    )
    if schema_only or skip_legacy_checks:
        phase_blockers: list[str] = list(namespace_phase.blockers)
        phase_blockers.extend(safety_result.blockers)
        phase_warnings: list[str] = list(namespace_phase.warnings)
        phase_warnings.extend(safety_result.warnings)
        if schema_result.schema_validation_errors:
            message = check_registry.format_check_message(
                "schema.validation_errors",
                f"schema_validation_errors={schema_result.schema_validation_errors}",
            )
            (phase_blockers if schema_only or strict else phase_warnings).append(message)
        consistency_phase = consistency_doctor.skipped_result()
        phase_blockers.extend(consistency_phase.blockers)
        phase_warnings.extend(consistency_phase.warnings)
        status = "BLOCKED" if phase_blockers else ("WARN" if phase_warnings else "OK")
        return _phase_only_doctor_result(
            status=status,
            profile=profile,
            artifact_namespace=artifact_namespace,
            runs=runs,
            alerts=alerts,
            feedback=feedback,
            outcomes=outcomes,
            card_paths=card_paths,
            namespace_phase=namespace_phase,
            schema_result=schema_result,
            strict=strict,
            strict_legacy=strict_legacy,
            schema_only=schema_only,
            legacy_checks_skipped=True,
            blockers=phase_blockers,
            warnings=phase_warnings,
        )
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(namespace_phase.blockers)
    warnings.extend(namespace_phase.warnings)
    blockers.extend(safety_result.blockers)
    warnings.extend(safety_result.warnings)
    active_shim_logic_count, active_shim_logic_modules = event_alpha_shims.active_shim_violation_summary()
    if active_shim_logic_count:
        modules = ", ".join(active_shim_logic_modules[:5])
        warnings.append(
            check_registry.format_check_message(
                "paths.active_shim_contains_logic",
                "active_shim_modules_with_implementation_logic="
                f"{active_shim_logic_count}"
                + (f" modules={modules}" if modules else ""),
            )
        )
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
    alert_counts_by_run_id: dict[str, int] = {}
    for row in alerts:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            alert_counts_by_run_id[run_id] = alert_counts_by_run_id.get(run_id, 0) + 1
    for row in runs:
        if event_alpha_artifacts.is_non_operational_row(row) and not include_test_artifacts:
            continue
        alertable = int(row.get("alertable") or 0) > 0
        if not alertable:
            continue
        run_id = str(row.get("run_id") or "").strip()
        stale_for_latest_scope = (
            effective_delivery_scope == "latest_run"
            and bool(latest_run_id)
            and bool(run_id)
            and run_id != latest_run_id
        )
        matching = alert_counts_by_run_id.get(run_id, 0)
        availability = event_alpha_artifacts.classify_snapshot_availability(
            row,
            inspected_alert_store_path,
            matching,
        )
        if availability == event_alpha_artifacts.SNAPSHOT_AVAILABLE:
            matching_snapshot_runs += 1
        elif availability in {
            event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH,
            event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL,
        }:
            external_snapshot_runs += 1
        else:
            missing_snapshot_runs += 1
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
                warnings.append(
                    f"stale alertable run {row.get('run_id') or 'unknown'} has snapshot availability={availability}"
                )
            else:
                _record_snapshot_availability_issue(
                    row,
                    availability,
                    blockers=blockers,
                    warnings=warnings,
                    strict=strict,
                )
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
    namespaces = {
        event_alpha_artifacts.row_namespace(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    profiles = {
        event_alpha_artifacts.row_profile(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    if artifact_namespace and any(ns not in {artifact_namespace, "legacy"} for ns in namespaces):
        blockers.append("mixed artifact namespaces after filtering")
    elif len(namespaces - {"legacy"}) > 1:
        (blockers if strict else warnings).append("multiple artifact namespaces present")
    if profile and any(item not in {profile, "default"} for item in profiles):
        warnings.append("rows from multiple profiles are present")
    if provider_health_rows is not None and profile in {"no_key_live", "api_live", "full_llm_live", "research_send"}:
        if not provider_health_rows:
            message = "provider health rows missing for live/burn-in profile"
            (blockers if strict else warnings).append(message)
    if profile in {"full_llm_live", "no_key_llm"} and not list(llm_budget_rows):
        warnings.append("LLM budget rows missing for LLM profile")
    card_file_paths = [Path(path) for path in card_paths]
    research_card_paths = [path for path in card_file_paths if path.name != "index.md"]
    daily_brief_card_names = _daily_brief_card_names(daily_brief_path)
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
        if (
            bool(row.get("is_diagnostic_snapshot"))
            or event_core_opportunities.row_is_diagnostic(row)
        )
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
    card_acquisition_mismatches = _card_acquisition_count_mismatches(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    card_source_pack_mismatches = _card_source_pack_mismatches(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    card_support_blockers = _card_primary_section_contains_support_row_blockers(research_card_paths, normalized_core_rows_by_id)
    card_upgrade_inconsistent = _card_upgrade_text_inconsistent_with_final_level(research_card_paths, normalized_core_rows_by_id)
    card_market_missing = _card_market_confirmation_missing_but_core_has_market_confirmation(research_card_paths, normalized_core_rows_by_id)
    card_source_unknown = _card_latest_source_unknown_but_accepted_evidence_exists(
        research_card_paths,
        normalized_core_rows_by_id,
        acquisition_rows,
    )
    audit_impact_mismatch = 0
    audit_source_pack_mismatch = 0
    market_freshness_contradictions = sum(1 for row in core_rows if _core_row_has_market_freshness_contradiction(row))
    promoted_core_in_weak = _promoted_core_rows_that_are_weak(core_rows)
    core_route_conflicts = _core_route_conflicts_with_opportunity_level(core_rows)
    live_confirmation_conflicts = _live_confirmation_conflicts(core_rows, profile=profile, artifact_namespace=artifact_namespace)
    raw_core_conflicts = _raw_core_live_confirmation_conflicts(
        core_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    opportunity_lane_conflicts = _opportunity_lane_conflicts(core_rows)
    market_anomaly_conflicts = _market_anomaly_artifact_conflicts(market_anomalies)
    official_exchange_conflicts = _official_exchange_artifact_conflicts(official_exchange_candidates)
    scheduled_conflicts = _scheduled_catalyst_artifact_conflicts((*scheduled_catalysts, *unlock_candidates))
    derivatives_conflicts = _derivatives_crowding_artifact_conflicts((*derivatives_state, *fade_review_candidates))
    integrated_conflicts = _integrated_radar_artifact_conflicts(
        integrated_candidates,
        core_rows=core_rows,
        research_card_paths=research_card_paths,
        daily_brief_path=daily_brief_path,
        manifest_path=integrated_manifest_path,
        source_coverage_json_path=integrated_source_coverage_json_path,
        delivery_path=integrated_delivery_path,
        outcome_path=integrated_outcomes_path,
        preview_path=(
            Path(inspected_alert_store_path).parent / "event_alpha_notification_preview.md"
            if inspected_alert_store_path is not None
            else (
                Path(source_coverage_report_path).parent / "event_alpha_notification_preview.md"
                if source_coverage_report_path is not None
                else None
            )
        ),
    )
    namespace_status = event_alpha_namespace_status.load_namespace_status(namespace_dir)
    structured_path_conflicts = _structured_operator_path_conflicts(
        (
            *runs,
            *alerts,
            *feedback,
            *outcomes,
            *hypotheses,
            *core_rows,
            *watchlist,
            *incidents,
            *acquisition_rows,
            *market_anomalies,
            *official_exchange_candidates,
            *scheduled_catalysts,
            *unlock_candidates,
            *derivatives_state,
            *fade_review_candidates,
            *dex_pool_state,
            *dex_pool_anomalies,
            *protocol_fundamentals,
            *integrated_candidates,
            *delivery_rows,
        )
    )
    if namespace_dir is not None:
        structured_path_conflicts += _structured_operator_path_file_conflicts(namespace_dir)
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
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    upgrade_high_priority = 0
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
    diagnostic_snapshots_missing_feedback = sum(
        1 for row in alerts
        if _alert_snapshot_is_diagnostic(row) and not _alert_has_feedback_target(row)
    )
    review_cards_dir = card_file_paths[0].parent if card_file_paths else None
    review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        profile,
        artifact_namespace,
        include_diagnostics=True,
        notification_runs=runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    default_review_items = event_alpha_notification_inbox.build_event_alpha_review_items(
        profile,
        artifact_namespace,
        include_diagnostics=False,
        notification_runs=runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=review_cards_dir,
        notification_delivery_rows=delivery_rows,
        core_opportunity_rows=core_rows,
    )
    inbox_core_missing_card = sum(
        1 for item in review_items
        if not item.is_diagnostic and item.core_opportunity_id and not item.card_path
    )
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
    doctor_check_context = SimpleNamespace(**locals())
    doctor_integrated_radar_checks.apply_core_card_checks(doctor_check_context, blockers, warnings)
    doctor_provider_readiness_checks.apply_structured_artifact_checks(doctor_check_context, blockers, warnings)
    doctor_integrated_radar_checks.apply_integrated_artifact_checks(doctor_check_context, blockers, warnings)
    doctor_path_checks.apply_integrated_path_checks(doctor_check_context, blockers, warnings)
    doctor_source_coverage_checks.apply_checks(doctor_check_context, blockers, warnings)
    doctor_provider_readiness_checks.apply_preflight_checks(doctor_check_context, blockers, warnings)
    doctor_integrated_radar_checks.apply_identity_checks(doctor_check_context, blockers, warnings)
    research_review_enabled_but_lane_missing = 0
    research_review_candidates_without_delivery = 0
    if latest_run:
        rr_enabled = bool(latest_run.get("research_review_digest_enabled"))
        rr_candidates = _as_int(latest_run.get("research_review_digest_candidates"))
        rr_would_send = _as_int(latest_run.get("research_review_digest_would_send"))
        latest_lanes = {
            str(row.get("lane") or "")
            for row in delivery_rows
            if isinstance(row, Mapping)
            and latest_run_id
            and str(row.get("run_id") or "") == str(latest_run_id)
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
        strict_scope=effective_delivery_scope,
    )
    preview_conflicts = _notification_preview_consistency_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        latest_run=latest_run,
        core_rows=core_rows,
        latest_run_id=latest_run_id,
    )
    doctor_notification_checks.apply_checks(SimpleNamespace(**locals()), blockers, warnings)
    quality = _quality_missing_summary(
        hypotheses=hypotheses,
        watchlist=watchlist,
        alerts=alerts,
    )
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
    incident_linkage = _incident_linkage_summary(
        hypotheses=hypotheses,
        watchlist=watchlist,
        alerts=alerts,
        incidents=incidents,
    )
    doctor_outcome_checks.apply_checks(SimpleNamespace(**locals()), blockers, warnings)
    if schema_result.schema_validation_errors:
        warnings.append(
            check_registry.format_check_message(
                "schema.validation_errors",
                f"schema_validation_errors={schema_result.schema_validation_errors}",
            )
        )
    if incident_linkage["invalid_canonical_incident_rows"]:
        message = f"invalid_canonical_incident_rows={incident_linkage['invalid_canonical_incident_rows']}"
        (blockers if strict else warnings).append(message)
    consistency_phase = consistency_doctor.ConsistencyDoctorResult()
    blockers.extend(consistency_phase.blockers)
    warnings.extend(consistency_phase.warnings)
    status = "BLOCKED" if blockers else ("WARN" if warnings else "OK")
    return EventAlphaArtifactDoctorResult(
        status=status,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_rows=len(runs),
        alert_rows=len(alerts),
        feedback_rows=len(feedback),
        outcome_rows=len(outcomes),
        card_files=card_count,
        research_card_files=card_count,
        research_card_index_present=index_present,
        cards_missing_lineage=cards_missing_lineage,
        cards_missing_feedback_target=cards_missing_feedback_target,
        visible_core_opportunities=len(visible_core),
        core_opportunity_store_rows=len(core_rows),
        visible_core_opportunities_missing_store_rows=visible_missing_store_rows,
        duplicate_core_opportunity_store_rows=duplicate_store_rows,
        core_opportunity_store_rows_missing_card_path=store_rows_missing_card_path,
        visible_core_opportunities_missing_cards=visible_missing_cards,
        visible_core_opportunities_missing_feedback_targets=visible_missing_targets,
        alert_snapshots_missing_core_opportunity_id=snapshots_missing_core,
        alert_snapshots_missing_feedback_target=snapshots_missing_feedback,
        core_cards_missing_store_row=core_cards_missing_store,
        visible_core_cards_missing_store_row=visible_core_cards_missing_store,
        orphan_core_opportunity_cards=orphan_core_cards,
        diagnostic_snapshots_with_fake_core_id=diagnostic_fake_core,
        alert_snapshots_core_id_missing_from_store=snapshot_core_missing_store,
        evidence_acquisition_core_id_missing_from_store=acquisition_core_missing_store,
        card_primary_fields_mismatch_core_store=card_primary_mismatches,
        card_evidence_acquisition_count_mismatch=card_acquisition_mismatches,
        evidence_acquisition_stale_validated_digest=acquisition_final_conflicts["evidence_acquisition_stale_validated_digest"],
        card_source_pack_mismatch_core_acquisition=card_source_pack_mismatches,
        card_primary_section_contains_support_row_blockers=card_support_blockers,
        card_upgrade_text_inconsistent_with_final_level=card_upgrade_inconsistent,
        audit_primary_impact_path_mismatch_core=audit_impact_mismatch,
        audit_source_pack_mismatch_core=audit_source_pack_mismatch,
        card_market_confirmation_missing_but_core_has_market_confirmation=card_market_missing,
        card_latest_source_unknown_but_accepted_evidence_exists=card_source_unknown,
        quality_review_promoted_core_in_weak_section=promoted_core_in_weak,
        market_freshness_contradictory_summary=market_freshness_contradictions,
        quality_review_market_freshness_contradiction=market_freshness_contradictions,
        upgrade_candidates_include_high_priority=upgrade_high_priority,
        daily_brief_card_group_mismatch_with_index=card_group_mismatches,
        daily_brief_missing_selected_run=daily_brief_conflicts["daily_brief_missing_selected_run"],
        daily_brief_selected_run_mismatch=daily_brief_conflicts["daily_brief_selected_run_mismatch"],
        daily_brief_core_count_mismatch_store=daily_brief_conflicts["daily_brief_core_count_mismatch_store"],
        daily_brief_research_review_lane_missing=daily_brief_conflicts["daily_brief_research_review_lane_missing"],
        daily_brief_source_coverage_path_missing=daily_brief_conflicts["daily_brief_source_coverage_path_missing"],
        daily_brief_coinalyze_source_coverage_mismatch=daily_brief_conflicts[
            "daily_brief_coinalyze_source_coverage_mismatch"
        ],
        core_route_conflicts_with_opportunity_level=core_route_conflicts,
        live_validated_without_confirmation=live_confirmation_conflicts["live_validated_without_confirmation"],
        live_sector_digest_without_asset=live_confirmation_conflicts["live_sector_digest_without_asset"],
        live_rejected_results_promoted=live_confirmation_conflicts["live_rejected_results_promoted"],
        live_skipped_budget_promoted=live_confirmation_conflicts["live_skipped_budget_promoted"],
        raw_core_validated_without_confirmation=raw_core_conflicts["raw_core_validated_without_confirmation"],
        raw_core_source_only_narrative_validated=raw_core_conflicts["raw_core_source_only_narrative_validated"],
        raw_core_cryptopanic_tag_only_direct_path_confirmed=raw_core_conflicts["raw_core_cryptopanic_tag_only_direct_path_confirmed"],
        raw_core_suppressed_duplicate_validated_stale=raw_core_conflicts["raw_core_suppressed_duplicate_validated_stale"],
        confirmed_long_without_source_market=opportunity_lane_conflicts["confirmed_long_without_source_market"],
        fade_short_without_crowding_exhaustion=opportunity_lane_conflicts["fade_short_without_crowding_exhaustion"],
        early_long_without_fresh_strong_source=opportunity_lane_conflicts["early_long_without_fresh_strong_source"],
        risk_only_missing_evidence_only=opportunity_lane_conflicts["risk_only_missing_evidence_only"],
        cryptopanic_only_narrative_confirmed_lane=opportunity_lane_conflicts["cryptopanic_only_narrative_confirmed_lane"],
        diagnostic_visible_default_operator_lane=opportunity_lane_conflicts["diagnostic_visible_default_operator_lane"],
        core_missing_market_state_snapshot=opportunity_lane_conflicts["core_missing_market_state_snapshot"],
        market_state_return_unit_missing=opportunity_lane_conflicts["market_state_return_unit_missing"],
        market_state_possible_double_scaled=opportunity_lane_conflicts["market_state_possible_double_scaled"],
        market_state_lane_possible_double_scaled=opportunity_lane_conflicts["market_state_lane_possible_double_scaled"],
        market_anomaly_rows=len(market_anomalies),
        market_anomaly_missing_market_state_snapshot=market_anomaly_conflicts["market_anomaly_missing_market_state_snapshot"],
        market_anomaly_missing_market_state_class=market_anomaly_conflicts["market_anomaly_missing_market_state_class"],
        market_anomaly_confirmed_breakout_missing_evidence=market_anomaly_conflicts["market_anomaly_confirmed_breakout_missing_evidence"],
        market_anomaly_suspicious_illiquid_promoted_confirmed=market_anomaly_conflicts["market_anomaly_suspicious_illiquid_promoted_confirmed"],
        market_anomaly_created_alert_rows=market_anomaly_conflicts["market_anomaly_created_alert_rows"],
        market_anomaly_missing_freshness_status=market_anomaly_conflicts["market_anomaly_missing_freshness_status"],
        market_anomaly_needs_search_without_plan=market_anomaly_conflicts["market_anomaly_needs_search_without_plan"],
        official_exchange_candidate_rows=len(official_exchange_candidates),
        official_exchange_candidate_missing_source_fields=official_exchange_conflicts["official_exchange_candidate_missing_source_fields"],
        official_exchange_listing_without_official_source=official_exchange_conflicts["official_exchange_listing_without_official_source"],
        official_exchange_secret_leak=official_exchange_conflicts["official_exchange_secret_leak"],
        official_exchange_delisting_long_research=official_exchange_conflicts["official_exchange_delisting_long_research"],
        official_exchange_quote_asset_misclassified=official_exchange_conflicts["official_exchange_quote_asset_misclassified"],
        official_exchange_major_pair_noise_promoted_early_long=official_exchange_conflicts[
            "official_exchange_major_pair_noise_promoted_early_long"
        ],
        official_exchange_created_alert_rows=official_exchange_conflicts["official_exchange_created_alert_rows"],
        official_exchange_activation_missing_shared_schema=official_exchange_activation_conflicts[
            "official_exchange_activation_missing_shared_schema"
        ],
        official_exchange_activation_live_without_ledger=official_exchange_activation_conflicts[
            "official_exchange_activation_live_without_ledger"
        ],
        official_exchange_activation_signed_listener_secret_leak=official_exchange_activation_conflicts[
            "official_exchange_activation_signed_listener_secret_leak"
        ],
        official_exchange_activation_forbidden_side_effect_claim=official_exchange_activation_conflicts[
            "official_exchange_activation_forbidden_side_effect_claim"
        ],
        instrument_resolution_missing_canonical_id_when_fixture_has_it=instrument_resolution_conflicts[
            "instrument_resolution_missing_canonical_id_when_fixture_has_it"
        ],
        instrument_resolution_quote_asset_misclassified=instrument_resolution_conflicts[
            "instrument_resolution_quote_asset_misclassified"
        ],
        instrument_resolution_sector_visible_as_tradable=instrument_resolution_conflicts[
            "instrument_resolution_sector_visible_as_tradable"
        ],
        instrument_resolution_coinalyze_symbol_unlinked=instrument_resolution_conflicts[
            "instrument_resolution_coinalyze_symbol_unlinked"
        ],
        scheduled_catalyst_rows=len(scheduled_catalysts),
        unlock_candidate_rows=len(unlock_candidates),
        derivatives_state_rows=len(derivatives_state),
        fade_review_candidate_rows=len(fade_review_candidates),
        dex_pool_state_rows=len(dex_pool_state),
        dex_pool_anomaly_rows=len(dex_pool_anomalies),
        protocol_fundamental_rows=len(protocol_fundamentals),
        unlock_without_structured_evidence=scheduled_conflicts["unlock_without_structured_evidence"],
        unlock_missing_event_time=scheduled_conflicts["unlock_missing_event_time"],
        unlock_promoted_without_size_metrics=scheduled_conflicts["unlock_promoted_without_size_metrics"],
        media_unlock_promoted_structured=scheduled_conflicts["media_unlock_promoted_structured"],
        stale_completed_catalyst_upcoming=scheduled_conflicts["stale_completed_catalyst_upcoming"],
        calendar_event_missing_source_url=scheduled_conflicts["calendar_event_missing_source_url"],
        cryptopanic_unlock_proof=scheduled_conflicts["cryptopanic_unlock_proof"],
        scheduled_catalyst_created_alert_rows=scheduled_conflicts["scheduled_catalyst_created_alert_rows"],
        fade_review_without_completed_move=derivatives_conflicts["fade_review_without_completed_move"],
        fade_review_without_crowding_exhaustion=derivatives_conflicts["fade_review_without_crowding_exhaustion"],
        fade_review_created_triggered_fade=derivatives_conflicts["fade_review_created_triggered_fade"],
        fade_review_created_normal_rsi_signal=derivatives_conflicts["fade_review_created_normal_rsi_signal"],
        fade_review_notification_missing_disclaimer=derivatives_conflicts["fade_review_notification_missing_disclaimer"],
        derivatives_artifact_secret_leak=derivatives_conflicts["derivatives_artifact_secret_leak"],
        derivatives_state_missing_freshness_status=derivatives_conflicts["derivatives_state_missing_freshness_status"],
        derivatives_metric_claim_implemented_missing=derivatives_conflicts["derivatives_metric_claim_implemented_missing"],
        derivatives_unit_metadata_missing=derivatives_conflicts["derivatives_unit_metadata_missing"],
        stale_derivatives_snapshot_promoted_fade_review=derivatives_conflicts["stale_derivatives_snapshot_promoted_fade_review"],
        confirmed_long_crowded_without_warning=derivatives_conflicts["confirmed_long_crowded_without_warning"],
        integrated_radar_candidate_rows=len(integrated_candidates),
        integrated_candidate_missing_opportunity_type=integrated_conflicts["integrated_candidate_missing_opportunity_type"],
        integrated_candidate_missing_market_state_snapshot=integrated_conflicts["integrated_candidate_missing_market_state_snapshot"],
        integrated_confirmed_long_without_source_market=integrated_conflicts["integrated_confirmed_long_without_source_market"],
        integrated_early_long_without_fresh_strong_source=integrated_conflicts["integrated_early_long_without_fresh_strong_source"],
        integrated_fade_without_crowding_exhaustion=integrated_conflicts["integrated_fade_without_crowding_exhaustion"],
        integrated_risk_without_evidence=integrated_conflicts["integrated_risk_without_evidence"],
        integrated_market_anomaly_confirmed=integrated_conflicts["integrated_market_anomaly_confirmed"],
        integrated_cryptopanic_confirmed=integrated_conflicts["integrated_cryptopanic_confirmed"],
        integrated_major_pair_early_long=integrated_conflicts["integrated_major_pair_early_long"],
        integrated_input_manifest_missing=integrated_conflicts["integrated_input_manifest_missing"],
        integrated_source_coverage_json_missing=integrated_conflicts["integrated_source_coverage_json_missing"],
        integrated_candidate_core_missing=integrated_conflicts["integrated_candidate_core_missing"],
        integrated_candidate_core_opportunity_type_mismatch=integrated_conflicts["integrated_candidate_core_opportunity_type_mismatch"],
        integrated_candidate_core_market_state_mismatch=integrated_conflicts["integrated_candidate_core_market_state_mismatch"],
        integrated_candidate_core_route_level_mismatch=integrated_conflicts["integrated_candidate_core_route_level_mismatch"],
        integrated_candidate_core_reason_code_loss=integrated_conflicts["integrated_candidate_core_reason_code_loss"],
        integrated_candidate_core_source_url_loss=integrated_conflicts["integrated_candidate_core_source_url_loss"],
        integrated_candidate_core_official_event_loss=integrated_conflicts["integrated_candidate_core_official_event_loss"],
        integrated_candidate_core_scheduled_event_loss=integrated_conflicts["integrated_candidate_core_scheduled_event_loss"],
        integrated_candidate_core_unlock_event_loss=integrated_conflicts["integrated_candidate_core_unlock_event_loss"],
        integrated_candidate_core_derivatives_loss=integrated_conflicts["integrated_candidate_core_derivatives_loss"],
        integrated_candidate_card_opportunity_type_mismatch=integrated_conflicts["integrated_candidate_card_opportunity_type_mismatch"],
        integrated_candidate_card_why_now_mismatch=integrated_conflicts["integrated_candidate_card_why_now_mismatch"],
        integrated_major_pair_card_early_long=integrated_conflicts["integrated_major_pair_card_early_long"],
        integrated_card_generic_lane_override=integrated_conflicts["integrated_card_generic_lane_override"],
        card_opportunity_lane_core_mismatch=integrated_conflicts["card_opportunity_lane_core_mismatch"],
        integrated_candidate_card_official_event_missing=integrated_conflicts["integrated_candidate_card_official_event_missing"],
        integrated_candidate_card_source_url_missing=integrated_conflicts["integrated_candidate_card_source_url_missing"],
        integrated_candidate_core_crowding_metadata_loss=integrated_conflicts["integrated_candidate_core_crowding_metadata_loss"],
        derivatives_card_metric_claim_without_data=integrated_conflicts["derivatives_card_metric_claim_without_data"],
        integrated_coinalyze_crowding_card_missing=integrated_conflicts["integrated_coinalyze_crowding_card_missing"],
        integrated_coinalyze_loaded_no_rows_attached=integrated_conflicts["integrated_coinalyze_loaded_no_rows_attached"],
        integrated_coinalyze_missing_skip_reason=integrated_conflicts["integrated_coinalyze_missing_skip_reason"],
        integrated_coinalyze_stale_loaded_without_warning=integrated_conflicts["integrated_coinalyze_stale_loaded_without_warning"],
        integrated_coinalyze_loaded_from_stale_namespace=integrated_conflicts["integrated_coinalyze_loaded_from_stale_namespace"],
        integrated_fade_card_crowding_unknown=integrated_conflicts["integrated_fade_card_crowding_unknown"],
        integrated_fade_card_missing_disclaimer=integrated_conflicts["integrated_fade_card_missing_disclaimer"],
        integrated_confirmed_long_crowding_warning_hidden=integrated_conflicts["integrated_confirmed_long_crowding_warning_hidden"],
        integrated_dex_low_liquidity_promoted_confirmed=integrated_conflicts[
            "integrated_dex_low_liquidity_promoted_confirmed"
        ],
        integrated_market_confirmation_display_contradiction=integrated_conflicts["integrated_market_confirmation_display_contradiction"],
        integrated_derivatives_display_contradiction=integrated_conflicts["integrated_derivatives_display_contradiction"],
        integrated_manifest_mixed_timestamp_pair=integrated_conflicts["integrated_manifest_mixed_timestamp_pair"],
        integrated_core_silent_upgrade=integrated_conflicts["integrated_core_silent_upgrade"],
        integrated_diagnostic_visible_in_default_operator_section=integrated_conflicts["integrated_diagnostic_visible_in_default_operator_section"],
        integrated_preview_missing_disclaimer=integrated_conflicts["integrated_preview_missing_disclaimer"],
        integrated_delivery_ledger_missing=integrated_conflicts["integrated_delivery_ledger_missing"],
        integrated_preview_lane_mismatch=integrated_conflicts["integrated_preview_lane_mismatch"],
        integrated_delivery_missing_disclaimer=integrated_conflicts["integrated_delivery_missing_disclaimer"],
        integrated_delivery_sent_in_no_send=integrated_conflicts["integrated_delivery_sent_in_no_send"],
        integrated_delivery_side_effect_flag=integrated_conflicts["integrated_delivery_side_effect_flag"],
        integrated_delivery_missing_skip_reasons=integrated_conflicts["integrated_delivery_missing_skip_reasons"],
        integrated_delivery_card_path_absolute=integrated_conflicts["integrated_delivery_card_path_absolute"],
        integrated_delivery_card_path_not_rendered=integrated_conflicts["integrated_delivery_card_path_not_rendered"],
        integrated_operator_markdown_absolute_path=integrated_conflicts["integrated_operator_markdown_absolute_path"],
        operator_structured_path_absolute=integrated_conflicts["operator_structured_path_absolute"],
        integrated_legacy_preview_alerts_wording=integrated_conflicts["integrated_legacy_preview_alerts_wording"],
        integrated_manifest_daily_brief_unavailable=integrated_conflicts["integrated_manifest_daily_brief_unavailable"],
        integrated_outcome_missing_for_candidate=integrated_conflicts["integrated_outcome_missing_for_candidate"],
        integrated_outcome_side_effect_flag=integrated_conflicts["integrated_outcome_side_effect_flag"],
        integrated_outcome_schema_missing=integrated_conflicts["integrated_outcome_schema_missing"],
        integrated_outcome_missing_identity=integrated_conflicts["integrated_outcome_missing_identity"],
        integrated_outcome_returns_without_price=integrated_conflicts["integrated_outcome_returns_without_price"],
        integrated_outcome_diagnostic_in_performance=integrated_conflicts["integrated_outcome_diagnostic_in_performance"],
        integrated_calibration_diagnostic_in_main_priors=integrated_conflicts["integrated_calibration_diagnostic_in_main_priors"],
        integrated_calibration_prior_safety_missing=integrated_conflicts["integrated_calibration_prior_safety_missing"],
        integrated_calibration_legacy_alias_top_level=integrated_conflicts["integrated_calibration_legacy_alias_top_level"],
        integrated_outcome_return_double_scaled=integrated_conflicts["integrated_outcome_return_double_scaled"],
        integrated_outcome_missing_data_unlabeled=integrated_conflicts["integrated_outcome_missing_data_unlabeled"],
        integrated_outcome_thesis_move_missing=integrated_conflicts["integrated_outcome_thesis_move_missing"],
        integrated_outcome_card_thesis_interpretation_missing=integrated_conflicts[
            "integrated_outcome_card_thesis_interpretation_missing"
        ],
        integrated_outcome_card_trade_wording=integrated_conflicts["integrated_outcome_card_trade_wording"],
        integrated_performance_diagnostic_in_main_aggregate=integrated_conflicts[
            "integrated_performance_diagnostic_in_main_aggregate"
        ],
        integrated_performance_auto_apply_enabled=integrated_conflicts["integrated_performance_auto_apply_enabled"],
        integrated_performance_low_sample_missing_warning=integrated_conflicts[
            "integrated_performance_low_sample_missing_warning"
        ],
        integrated_performance_trade_pnl_wording=integrated_conflicts["integrated_performance_trade_pnl_wording"],
        integrated_created_normal_rsi_signal=integrated_conflicts["integrated_created_normal_rsi_signal"],
        integrated_created_triggered_fade=integrated_conflicts["integrated_created_triggered_fade"],
        source_coverage_report_missing=source_coverage_report_conflicts["source_coverage_report_missing"],
        source_coverage_provider_status_unknown=source_coverage_report_conflicts["source_coverage_provider_status_unknown"],
        source_coverage_provider_marked_healthy_without_observation=source_coverage_report_conflicts["source_coverage_provider_marked_healthy_without_observation"],
        source_coverage_category_priority_missing=source_coverage_report_conflicts[
            "source_coverage_category_priority_missing"
        ],
        source_coverage_readiness_link_missing=source_coverage_report_conflicts[
            "source_coverage_readiness_link_missing"
        ],
        source_coverage_context_provider_ranked_above_lane_critical=source_coverage_report_conflicts[
            "source_coverage_context_provider_ranked_above_lane_critical"
        ],
        source_coverage_coinalyze_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_coinalyze_missing_linked_artifact"
        ],
        source_coverage_bybit_announcements_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_bybit_announcements_missing_linked_artifact"
        ],
        source_coverage_unlock_calendar_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_unlock_calendar_missing_linked_artifact"
        ],
        source_coverage_dex_onchain_missing_linked_artifact=source_coverage_report_conflicts[
            "source_coverage_dex_onchain_missing_linked_artifact"
        ],
        live_provider_readiness_missing=live_provider_readiness_conflicts["live_provider_readiness_missing"],
        live_provider_readiness_secret_leak=live_provider_readiness_conflicts["live_provider_readiness_secret_leak"],
        live_provider_readiness_live_calls_allowed_in_smoke=live_provider_readiness_conflicts[
            "live_provider_readiness_live_calls_allowed_in_smoke"
        ],
        live_provider_readiness_configured_missing_env=live_provider_readiness_conflicts[
            "live_provider_readiness_configured_missing_env"
        ],
        coinalyze_preflight_secret_leak=coinalyze_preflight_conflicts["coinalyze_preflight_secret_leak"],
        coinalyze_preflight_live_call_allowed_in_smoke=coinalyze_preflight_conflicts[
            "coinalyze_preflight_live_call_allowed_in_smoke"
        ],
        coinalyze_preflight_configured_missing_env=coinalyze_preflight_conflicts[
            "coinalyze_preflight_configured_missing_env"
        ],
        coinalyze_preflight_ready_without_request_ledger=coinalyze_preflight_conflicts[
            "coinalyze_preflight_ready_without_request_ledger"
        ],
        coinalyze_preflight_missing_fixture_parser_status=coinalyze_preflight_conflicts[
            "coinalyze_preflight_missing_fixture_parser_status"
        ],
        coinalyze_preflight_forbidden_side_effect_claim=coinalyze_preflight_conflicts[
            "coinalyze_preflight_forbidden_side_effect_claim"
        ],
        coinalyze_rehearsal_secret_leak=coinalyze_preflight_conflicts["coinalyze_rehearsal_secret_leak"],
        coinalyze_rehearsal_live_without_ledger=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_without_ledger"
        ],
        coinalyze_rehearsal_live_call_allowed_in_smoke=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_call_allowed_in_smoke"
        ],
        coinalyze_rehearsal_live_without_explicit_allow=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_live_without_explicit_allow"
        ],
        coinalyze_rehearsal_request_budget_exceeded=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_request_budget_exceeded"
        ],
        coinalyze_rehearsal_success_without_derivatives_state=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_success_without_derivatives_state"
        ],
        coinalyze_rehearsal_success_without_crowding_candidates=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_success_without_crowding_candidates"
        ],
        coinalyze_provider_health_healthy_without_successful_ledger=coinalyze_preflight_conflicts[
            "coinalyze_provider_health_healthy_without_successful_ledger"
        ],
        coinalyze_rehearsal_forbidden_side_effect_claim=coinalyze_preflight_conflicts[
            "coinalyze_rehearsal_forbidden_side_effect_claim"
        ],
        coinalyze_supported_metric_implemented_missing_state=coinalyze_preflight_conflicts[
            "coinalyze_supported_metric_implemented_missing_state"
        ],
        bybit_announcements_preflight_secret_leak=bybit_announcements_conflicts[
            "bybit_announcements_preflight_secret_leak"
        ],
        bybit_announcements_preflight_live_call_allowed_in_smoke=bybit_announcements_conflicts[
            "bybit_announcements_preflight_live_call_allowed_in_smoke"
        ],
        bybit_announcements_preflight_missing_fixture_parser_status=bybit_announcements_conflicts[
            "bybit_announcements_preflight_missing_fixture_parser_status"
        ],
        bybit_announcements_rehearsal_secret_leak=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_secret_leak"
        ],
        bybit_announcements_rehearsal_live_without_ledger=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_live_without_ledger"
        ],
        bybit_announcements_rehearsal_live_without_explicit_allow=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_live_without_explicit_allow"
        ],
        bybit_announcements_rehearsal_unsupported_params=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_unsupported_params"
        ],
        bybit_announcements_rehearsal_forbidden_side_effect_claim=bybit_announcements_conflicts[
            "bybit_announcements_rehearsal_forbidden_side_effect_claim"
        ],
        unlock_calendar_preflight_secret_leak=unlock_calendar_conflicts[
            "unlock_calendar_preflight_secret_leak"
        ],
        unlock_calendar_preflight_live_without_ledger=unlock_calendar_conflicts[
            "unlock_calendar_preflight_live_without_ledger"
        ],
        unlock_calendar_preflight_live_call_allowed_in_smoke=unlock_calendar_conflicts[
            "unlock_calendar_preflight_live_call_allowed_in_smoke"
        ],
        unlock_calendar_preflight_missing_fixture_parser_status=unlock_calendar_conflicts[
            "unlock_calendar_preflight_missing_fixture_parser_status"
        ],
        unlock_calendar_preflight_forbidden_side_effect_claim=unlock_calendar_conflicts[
            "unlock_calendar_preflight_forbidden_side_effect_claim"
        ],
        dex_onchain_readiness_secret_leak=dex_onchain_conflicts["dex_onchain_readiness_secret_leak"],
        dex_onchain_live_without_ledger=dex_onchain_conflicts["dex_onchain_live_without_ledger"],
        dex_onchain_live_call_allowed_in_smoke=dex_onchain_conflicts["dex_onchain_live_call_allowed_in_smoke"],
        dex_onchain_missing_fixture_parser_status=dex_onchain_conflicts["dex_onchain_missing_fixture_parser_status"],
        dex_onchain_forbidden_side_effect_claim=dex_onchain_conflicts["dex_onchain_forbidden_side_effect_claim"],
        dex_low_liquidity_promoted_confirmed=dex_onchain_conflicts["dex_low_liquidity_promoted_confirmed"],
        protocol_metric_missing_source_time=dex_onchain_conflicts["protocol_metric_missing_source_time"],
        source_pack_provider_status_missing=source_coverage_conflicts["source_pack_provider_status_missing"],
        missing_provider_recommendations_missing=source_coverage_conflicts["missing_provider_recommendations_missing"],
        degraded_provider_absence_marked_meaningful=source_coverage_conflicts["degraded_provider_absence_marked_meaningful"],
        cryptopanic_configured_but_not_observed=cryptopanic_conflicts["cryptopanic_configured_but_not_observed"],
        cryptopanic_used_but_no_source_coverage_entry=cryptopanic_conflicts["cryptopanic_used_but_no_source_coverage_entry"],
        cryptopanic_accepted_evidence_missing_from_card=cryptopanic_conflicts["cryptopanic_accepted_evidence_missing_from_card"],
        cryptopanic_rejected_only_promoted=cryptopanic_conflicts["cryptopanic_rejected_only_promoted"],
        cryptopanic_token_printed_or_unredacted=cryptopanic_conflicts["cryptopanic_token_printed_or_unredacted"],
        cryptopanic_growth_unsupported_param_used=cryptopanic_conflicts["cryptopanic_growth_unsupported_param_used"],
        cryptopanic_duplicate_request_key=cryptopanic_conflicts["cryptopanic_duplicate_request_key"],
        cryptopanic_invalid_currency_code=cryptopanic_conflicts["cryptopanic_invalid_currency_code"],
        cryptopanic_empty_currency_request=cryptopanic_conflicts["cryptopanic_empty_currency_request"],
        cryptopanic_coin_id_sent_as_currency=cryptopanic_conflicts["cryptopanic_coin_id_sent_as_currency"],
        cryptopanic_all_requests_failed=cryptopanic_conflicts["cryptopanic_all_requests_failed"],
        cryptopanic_json_parse_errors=cryptopanic_conflicts["cryptopanic_json_parse_errors"],
        cryptopanic_configured_but_unusable=cryptopanic_conflicts["cryptopanic_configured_but_unusable"],
        cryptopanic_status_code_missing_on_http_failure=cryptopanic_conflicts["cryptopanic_status_code_missing_on_http_failure"],
        cryptopanic_body_excerpt_unredacted_token=cryptopanic_conflicts["cryptopanic_body_excerpt_unredacted_token"],
        cryptopanic_quota_exceeded=cryptopanic_conflicts["cryptopanic_quota_exceeded"],
        cryptopanic_request_ledger_missing_when_used=cryptopanic_conflicts["cryptopanic_request_ledger_missing_when_used"],
        cryptopanic_success_with_backoff_status=cryptopanic_conflicts["cryptopanic_success_with_backoff_status"],
        cryptopanic_restore_token_recommendation_when_configured=cryptopanic_conflicts[
            "cryptopanic_restore_token_recommendation_when_configured"
        ],
        evidence_count_mismatch=evidence_count_mismatches,
        unconfirmed_narrative_daily_digest=delivery_conflicts["unconfirmed_narrative_daily_digest"],
        single_source_no_market_fan_token_digest=delivery_conflicts["single_source_no_market_fan_token_digest"],
        visible_sector_core_without_config=visible_sector_cores,
        duplicate_proxy_core_rows=duplicate_proxy_cores,
        runs_with_matching_snapshots=matching_snapshot_runs,
        runs_with_missing_snapshots=missing_snapshot_runs,
        runs_with_external_snapshot_paths=external_snapshot_runs,
        legacy_rows_skipped=0 if include_legacy_artifacts else raw_legacy,
        legacy_rows_counted=sum(
            1 for row in (*runs, *alerts, *feedback, *outcomes)
            if event_alpha_artifacts.is_legacy_row(row)
        ),
        delivery_rows=delivery_summary.rows,
        latest_run_id=latest_run_id,
        latest_run_delivery_rows=delivery_conflicts["latest_run_delivery_rows"],
        legacy_delivery_rows=delivery_conflicts["legacy_delivery_rows"],
        stale_delivery_rows=delivery_conflicts["stale_delivery_rows"],
        delivery_strict_scope=effective_delivery_scope,
        deliveries_partial_delivered=delivery_summary.partial_delivered,
        deliveries_failed=delivery_summary.failed,
        delivery_status_missing=delivery_conflicts["delivery_status_missing"],
        delivery_status_detail_missing=delivery_conflicts["delivery_status_detail_missing"],
        delivery_mode_missing=delivery_conflicts["delivery_mode_missing"],
        delivery_state_inconsistent=delivery_conflicts["delivery_state_inconsistent"],
        delivery_would_send_sent_failed_inconsistent=delivery_conflicts["delivery_would_send_sent_failed_inconsistent"],
        delivery_identity_mismatch_core_store=delivery_conflicts["delivery_identity_mismatch_core_store"],
        delivery_core_id_missing=delivery_conflicts["delivery_core_id_missing"],
        legacy_pre_core_delivery_identity=delivery_conflicts["legacy_pre_core_delivery_identity"],
        stale_delivery_identity_missing_core=delivery_conflicts["stale_delivery_identity_missing_core"],
        delivery_feedback_target_missing=delivery_conflicts["delivery_feedback_target_missing"],
        delivery_card_path_missing=delivery_conflicts["delivery_card_path_missing"],
        delivery_alert_id_not_canonical=delivery_conflicts["delivery_alert_id_not_canonical"],
        telegram_message_contains_absolute_path=delivery_conflicts["telegram_message_contains_absolute_path"],
        telegram_message_contains_raw_debug_dump=delivery_conflicts["telegram_message_contains_raw_debug_dump"],
        research_review_digest_missing_confirmation_label=delivery_conflicts["research_review_digest_missing_confirmation_label"],
        research_review_digest_contains_strict_alertable=delivery_conflicts["research_review_digest_contains_strict_alertable"],
        research_review_digest_contains_hard_gated_candidate=delivery_conflicts["research_review_digest_contains_hard_gated_candidate"],
        research_review_digest_too_many_items=delivery_conflicts["research_review_digest_too_many_items"],
        research_review_digest_missing_feedback_target=delivery_conflicts["research_review_digest_missing_feedback_target"],
        research_review_digest_skipped_without_reason=delivery_conflicts["research_review_digest_skipped_without_reason"],
        research_review_digest_missing_family_summary=delivery_conflicts["research_review_digest_missing_family_summary"],
        research_review_digest_duplicate_visible_family_summary=delivery_conflicts[
            "research_review_digest_duplicate_visible_family_summary"
        ],
        research_review_digest_absolute_path=delivery_conflicts["research_review_digest_absolute_path"],
        notification_body_card_mismatch_canonical=delivery_conflicts["notification_body_card_mismatch_canonical"],
        notification_body_feedback_mismatch_canonical=delivery_conflicts["notification_body_feedback_mismatch_canonical"],
        research_review_body_uses_hypothesis_target_when_core_exists=delivery_conflicts["research_review_body_uses_hypothesis_target_when_core_exists"],
        research_review_digest_enabled_but_lane_missing=research_review_enabled_but_lane_missing,
        research_review_digest_candidates_without_delivery=research_review_candidates_without_delivery,
        digest_item_without_live_confirmation=delivery_conflicts["digest_item_without_live_confirmation"],
        digest_item_rejected_results_only=delivery_conflicts["digest_item_rejected_results_only"],
        strategic_broad_asset_digest_without_confirmation=delivery_conflicts["strategic_broad_asset_digest_without_confirmation"],
        notification_preview_missing=delivery_conflicts["notification_preview_missing"],
        notification_preview_relpath_missing=delivery_conflicts["notification_preview_relpath_missing"],
        notification_preview_path_unresolvable=delivery_conflicts["notification_preview_path_unresolvable"],
        notification_preview_run_summary_mismatch=preview_conflicts["notification_preview_run_summary_mismatch"],
        notification_preview_llm_summary_mismatch=preview_conflicts["notification_preview_llm_summary_mismatch"],
        notification_preview_lane_counts_mismatch=preview_conflicts["notification_preview_lane_counts_mismatch"],
        notification_preview_core_count_mismatch=preview_conflicts["notification_preview_core_count_mismatch"],
        notification_preview_alertable_count_mismatch=preview_conflicts["notification_preview_alertable_count_mismatch"],
        notification_preview_missing_send_guard_status=preview_conflicts["notification_preview_missing_send_guard_status"],
        notification_preview_send_guard_status_missing=preview_conflicts["notification_preview_send_guard_status_missing"],
        notification_preview_no_send_status_unclear=preview_conflicts["notification_preview_no_send_status_unclear"],
        notification_preview_legacy_alerts_wording=preview_conflicts["notification_preview_legacy_alerts_wording"],
        quality_fields_missing_count=quality["quality_fields_missing_count"],
        hypothesis_rows_missing_opportunity_verdict=quality["hypothesis_rows_missing_opportunity_verdict"],
        watchlist_rows_missing_quality_fields=quality["watchlist_rows_missing_quality_fields"],
        alert_rows_missing_quality_fields=quality["alert_rows_missing_quality_fields"],
        fresh_hypothesis_rows_missing_top_level_quality=quality["fresh_hypothesis_rows_missing_top_level_quality"],
        fresh_watchlist_rows_missing_top_level_quality=quality["fresh_watchlist_rows_missing_top_level_quality"],
        fresh_alert_rows_missing_top_level_quality=quality["fresh_alert_rows_missing_top_level_quality"],
        legacy_quality_missing_rows=quality["legacy_quality_missing_rows"],
        alertable_route_conflicts_with_opportunity_level=route_conflicts,
        alert_snapshot_route_mismatch_core_store=snapshot_core_conflicts["route_mismatch"],
        alert_snapshot_level_mismatch_core_store=snapshot_core_conflicts["level_mismatch"],
        alert_snapshot_live_confirmation_stale=snapshot_core_conflicts["live_confirmation_stale"],
        alert_snapshot_core_resolution_missing=snapshot_core_conflicts["core_resolution_missing"],
        alert_snapshot_pre_reconciliation_alertable=snapshot_core_conflicts["pre_reconciliation_alertable"],
        diagnostic_support_snapshot_alertable=snapshot_core_conflicts["diagnostic_support_alertable"],
        diagnostic_support_snapshot_inherits_core_route=snapshot_core_conflicts["diagnostic_support_inherits_core_route"],
        duplicate_alertable_snapshot_for_core=snapshot_core_conflicts["duplicate_alertable_snapshot_for_core"],
        canonical_snapshot_missing_for_visible_core=snapshot_core_conflicts["canonical_snapshot_missing_for_visible_core"],
        inbox_core_item_missing_card=inbox_core_missing_card,
        inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists=inbox_core_alert_target,
        inbox_diagnostic_snapshot_visible_by_default=inbox_diag_visible_default,
        audit_primary_snapshot_not_canonical_when_canonical_exists=audit_primary_not_canonical,
        feedback_readiness_counts_diagnostic_as_required=diagnostic_snapshots_missing_feedback,
        fresh_quality_route_conflict_rows=fresh_route_conflicts,
        legacy_quality_conflict_rows=legacy_route_conflicts,
        alert_rows_missing_final_route=missing_final_route,
        fresh_alert_rows_missing_final_route=fresh_missing_final_route,
        watchlist_state_conflicts_with_quality=watchlist_conflicts["watchlist_state_conflicts_with_quality"],
        universal_watchlist_state_conflicts=watchlist_conflicts["universal_watchlist_state_conflicts"],
        non_hypothesis_watchlist_quality_conflicts=watchlist_conflicts["non_hypothesis_watchlist_quality_conflicts"],
        hypothesis_watchlist_quality_conflicts=watchlist_conflicts["hypothesis_watchlist_quality_conflicts"],
        quality_capped_watchlist_rows=watchlist_conflicts["quality_capped_watchlist_rows"],
        active_watchlist_rows_quality_capped=watchlist_conflicts["active_watchlist_rows_quality_capped"],
        fresh_watchlist_state_conflict_rows=watchlist_conflicts["fresh_uncapped"],
        legacy_watchlist_conflicts=watchlist_conflicts["legacy"],
        hypothesis_rows_missing_incident_id=incident_linkage["hypothesis_rows_missing_incident_id"],
        watchlist_hypothesis_rows_missing_incident_id=incident_linkage["watchlist_hypothesis_rows_missing_incident_id"],
        alert_hypothesis_rows_missing_incident_id=incident_linkage["alert_hypothesis_rows_missing_incident_id"],
        incident_rows_without_linked_hypotheses=incident_linkage["incident_rows_without_linked_hypotheses"],
        incident_rows_without_linked_watchlist=incident_linkage["incident_rows_without_linked_watchlist"],
        canonical_unlinked_incidents=incident_linkage["canonical_unlinked_incidents"],
        active_incident_without_qualified_link=incident_linkage["active_incident_without_qualified_link"],
        linked_incident_without_qualified_link=incident_linkage["linked_incident_without_qualified_link"],
        weak_unqualified_incident_links=incident_linkage["weak_unqualified_incident_links"],
        quality_blocked_links_present=incident_linkage["quality_blocked_links_present"],
        quality_blocked_links_promoting_incident=incident_linkage["quality_blocked_links_promoting_incident"],
        diagnostic_incident_rows=incident_linkage["diagnostic_incident_rows"],
        raw_observation_incident_rows=incident_linkage["raw_observation_incident_rows"],
        external_context_incident_rows=incident_linkage["external_context_incident_rows"],
        rejected_incident_rows=incident_linkage["rejected_incident_rows"],
        incident_relevance_missing=incident_linkage["incident_relevance_missing"],
        invalid_canonical_incident_rows=incident_linkage["invalid_canonical_incident_rows"],
        garbage_primary_subject_incidents=incident_linkage["garbage_primary_subject_incidents"],
        fresh_incident_linkage_blockers=(
            incident_linkage["fresh_missing_hypotheses"]
            + incident_linkage["fresh_missing_watchlist"]
            + incident_linkage["fresh_missing_alerts"]
        ),
        legacy_incident_linkage_warnings=(
            incident_linkage["legacy_missing_hypotheses"]
            + incident_linkage["legacy_missing_watchlist"]
            + incident_linkage["legacy_missing_alerts"]
        ),
        namespace_status=namespace_status.status if namespace_status else event_alpha_namespace_status.STATUS_ACTIVE,
        namespace_stale_deprecated=1 if event_alpha_namespace_status.is_stale_deprecated(namespace_status) else 0,
        namespace_superseded_by=namespace_status.superseded_by if namespace_status else None,
        strict_legacy=bool(strict_legacy),
        strict=bool(strict),
        schema_only=False,
        legacy_checks_skipped=False,
        schema_rows_validated=schema_result.schema_rows_validated,
        schema_validation_errors=schema_result.schema_validation_errors,
        missing_required_fields=schema_result.missing_required_fields,
        invalid_enum_fields=schema_result.invalid_enum_fields,
        invalid_path_fields=schema_result.invalid_path_fields,
        invalid_safety_fields=schema_result.invalid_safety_fields,
        deprecated_field_usage=schema_result.deprecated_field_usage,
        active_shim_modules_with_implementation_logic=active_shim_logic_count,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )

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
    strict_legacy: bool,
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
        strict_legacy=bool(strict_legacy),
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
    if path is None:
        return []
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in source.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                rows.append(dict(item))
    except OSError:
        return []
    return rows

__all__ = (
    'diagnose_artifacts',
    '_phase_only_doctor_result',
    '_row',
    '_read_jsonl',
)
