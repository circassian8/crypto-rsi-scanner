"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_alert_store, event_alpha_artifacts, event_alpha_notification_inbox, event_alpha_quality_fields, event_alpha_router, event_core_opportunities, event_core_opportunity_store, event_opportunity_verdict, event_research_cards, event_watchlist
from . import event_alpha_notification_delivery as _delivery


@dataclass(frozen=True)
class EventAlphaArtifactDoctorResult:
    status: str
    profile: str | None
    artifact_namespace: str | None
    run_rows: int
    alert_rows: int
    feedback_rows: int
    outcome_rows: int
    card_files: int
    research_card_files: int = 0
    research_card_index_present: bool = False
    cards_missing_lineage: int = 0
    cards_missing_feedback_target: int = 0
    visible_core_opportunities: int = 0
    core_opportunity_store_rows: int = 0
    visible_core_opportunities_missing_store_rows: int = 0
    duplicate_core_opportunity_store_rows: int = 0
    core_opportunity_store_rows_missing_card_path: int = 0
    visible_core_opportunities_missing_cards: int = 0
    visible_core_opportunities_missing_feedback_targets: int = 0
    alert_snapshots_missing_core_opportunity_id: int = 0
    alert_snapshots_missing_feedback_target: int = 0
    core_cards_missing_store_row: int = 0
    visible_core_cards_missing_store_row: int = 0
    orphan_core_opportunity_cards: int = 0
    diagnostic_snapshots_with_fake_core_id: int = 0
    alert_snapshots_core_id_missing_from_store: int = 0
    evidence_acquisition_core_id_missing_from_store: int = 0
    card_primary_fields_mismatch_core_store: int = 0
    card_evidence_acquisition_count_mismatch: int = 0
    card_source_pack_mismatch_core_acquisition: int = 0
    card_primary_section_contains_support_row_blockers: int = 0
    card_upgrade_text_inconsistent_with_final_level: int = 0
    audit_primary_impact_path_mismatch_core: int = 0
    audit_source_pack_mismatch_core: int = 0
    card_market_confirmation_missing_but_core_has_market_confirmation: int = 0
    card_latest_source_unknown_but_accepted_evidence_exists: int = 0
    quality_review_promoted_core_in_weak_section: int = 0
    market_freshness_contradictory_summary: int = 0
    quality_review_market_freshness_contradiction: int = 0
    upgrade_candidates_include_high_priority: int = 0
    daily_brief_card_group_mismatch_with_index: int = 0
    core_route_conflicts_with_opportunity_level: int = 0
    live_validated_without_confirmation: int = 0
    live_sector_digest_without_asset: int = 0
    live_rejected_results_promoted: int = 0
    live_skipped_budget_promoted: int = 0
    runs_with_matching_snapshots: int = 0
    runs_with_missing_snapshots: int = 0
    runs_with_external_snapshot_paths: int = 0
    legacy_rows_skipped: int = 0
    legacy_rows_counted: int = 0
    delivery_rows: int = 0
    deliveries_partial_delivered: int = 0
    deliveries_failed: int = 0
    delivery_identity_mismatch_core_store: int = 0
    delivery_alert_id_not_canonical: int = 0
    telegram_message_contains_absolute_path: int = 0
    telegram_message_contains_raw_debug_dump: int = 0
    digest_item_without_live_confirmation: int = 0
    digest_item_rejected_results_only: int = 0
    notification_preview_missing: int = 0
    quality_fields_missing_count: int = 0
    hypothesis_rows_missing_opportunity_verdict: int = 0
    watchlist_rows_missing_quality_fields: int = 0
    alert_rows_missing_quality_fields: int = 0
    fresh_hypothesis_rows_missing_top_level_quality: int = 0
    fresh_watchlist_rows_missing_top_level_quality: int = 0
    fresh_alert_rows_missing_top_level_quality: int = 0
    legacy_quality_missing_rows: int = 0
    alertable_route_conflicts_with_opportunity_level: int = 0
    alert_snapshot_route_mismatch_core_store: int = 0
    alert_snapshot_level_mismatch_core_store: int = 0
    alert_snapshot_live_confirmation_stale: int = 0
    alert_snapshot_core_resolution_missing: int = 0
    alert_snapshot_pre_reconciliation_alertable: int = 0
    diagnostic_support_snapshot_alertable: int = 0
    diagnostic_support_snapshot_inherits_core_route: int = 0
    duplicate_alertable_snapshot_for_core: int = 0
    canonical_snapshot_missing_for_visible_core: int = 0
    inbox_core_item_missing_card: int = 0
    inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists: int = 0
    inbox_diagnostic_snapshot_visible_by_default: int = 0
    audit_primary_snapshot_not_canonical_when_canonical_exists: int = 0
    feedback_readiness_counts_diagnostic_as_required: int = 0
    fresh_quality_route_conflict_rows: int = 0
    legacy_quality_conflict_rows: int = 0
    alert_rows_missing_final_route: int = 0
    fresh_alert_rows_missing_final_route: int = 0
    watchlist_state_conflicts_with_quality: int = 0
    universal_watchlist_state_conflicts: int = 0
    non_hypothesis_watchlist_quality_conflicts: int = 0
    hypothesis_watchlist_quality_conflicts: int = 0
    quality_capped_watchlist_rows: int = 0
    active_watchlist_rows_quality_capped: int = 0
    fresh_watchlist_state_conflict_rows: int = 0
    legacy_watchlist_conflicts: int = 0
    hypothesis_rows_missing_incident_id: int = 0
    watchlist_hypothesis_rows_missing_incident_id: int = 0
    alert_hypothesis_rows_missing_incident_id: int = 0
    incident_rows_without_linked_hypotheses: int = 0
    incident_rows_without_linked_watchlist: int = 0
    canonical_unlinked_incidents: int = 0
    active_incident_without_qualified_link: int = 0
    linked_incident_without_qualified_link: int = 0
    weak_unqualified_incident_links: int = 0
    quality_blocked_links_present: int = 0
    quality_blocked_links_promoting_incident: int = 0
    diagnostic_incident_rows: int = 0
    raw_observation_incident_rows: int = 0
    external_context_incident_rows: int = 0
    rejected_incident_rows: int = 0
    incident_relevance_missing: int = 0
    invalid_canonical_incident_rows: int = 0
    garbage_primary_subject_incidents: int = 0
    fresh_incident_linkage_blockers: int = 0
    legacy_incident_linkage_warnings: int = 0
    strict_legacy: bool = False
    strict: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


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
    card_paths: Iterable[str | Path] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    inspected_alert_store_path: str | Path | None = None,
    strict: bool = False,
    strict_legacy: bool = False,
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
    blockers: list[str] = []
    warnings: list[str] = []
    matching_snapshot_runs = 0
    missing_snapshot_runs = 0
    external_snapshot_runs = 0
    if not runs:
        blockers.append("no matching operational/burn-in run rows found")
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
                blockers.append(f"alertable run {row.get('run_id') or 'unknown'} has no successful snapshot write")
        elif int(row.get("alertable") or 0) > 0 and int(row.get("snapshot_rows_written") or 0) <= 0:
            blockers.append(f"alertable run {row.get('run_id') or 'unknown'} wrote zero alert snapshots")
        elif availability != event_alpha_artifacts.SNAPSHOT_AVAILABLE:
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
    card_count = len(research_card_paths)
    index_present = any(path.name == "index.md" for path in card_file_paths)
    cards_missing_lineage = sum(1 for path in research_card_paths if not event_research_cards.card_has_current_lineage(path))
    cards_missing_feedback_target = sum(1 for path in research_card_paths if not event_research_cards.card_feedback_target(path))
    card_group_map = event_research_cards.card_index_group_map(research_card_paths)
    card_core_ids = {value for path in research_card_paths for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_feedback_targets = {value for path in research_card_paths for value in (event_research_cards.card_feedback_target(path),) if value}
    visible_core = (
        event_core_opportunity_store.core_opportunities_from_rows(core_rows)
        if core_rows
        else event_core_opportunities.visible_core_opportunities([*watchlist, *alerts, *hypotheses])
    )
    visible_core_ids = {item.core_opportunity_id for item in visible_core}
    visible_core_by_id = {item.core_opportunity_id: item for item in visible_core}
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
    store_rows_missing_card_path = sum(1 for row in core_rows if not str(row.get("card_path") or row.get("research_card_path") or "").strip())
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
        if path in card_group_map
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
    card_primary_mismatches = _card_primary_mismatches(research_card_paths, core_rows_by_id)
    card_acquisition_mismatches = _card_acquisition_count_mismatches(
        research_card_paths,
        core_rows_by_id,
        acquisition_rows,
    )
    card_source_pack_mismatches = _card_source_pack_mismatches(
        research_card_paths,
        core_rows_by_id,
        acquisition_rows,
    )
    card_support_blockers = _card_primary_section_contains_support_row_blockers(research_card_paths, core_rows_by_id)
    card_upgrade_inconsistent = _card_upgrade_text_inconsistent_with_final_level(research_card_paths, core_rows_by_id)
    card_market_missing = _card_market_confirmation_missing_but_core_has_market_confirmation(research_card_paths, core_rows_by_id)
    card_source_unknown = _card_latest_source_unknown_but_accepted_evidence_exists(
        research_card_paths,
        core_rows_by_id,
        acquisition_rows,
    )
    audit_impact_mismatch = 0
    audit_source_pack_mismatch = 0
    market_freshness_contradictions = sum(1 for row in core_rows if _core_row_has_market_freshness_contradiction(row))
    promoted_core_in_weak = _promoted_core_rows_that_are_weak(core_rows)
    core_route_conflicts = _core_route_conflicts_with_opportunity_level(core_rows)
    live_confirmation_conflicts = _live_confirmation_conflicts(core_rows, profile=profile, artifact_namespace=artifact_namespace)
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
    if card_count and not index_present:
        message = "research cards exist but index.md was not found"
        (blockers if strict else warnings).append(message)
    if cards_missing_lineage:
        message = f"research cards missing current lineage: {cards_missing_lineage}"
        (blockers if strict else warnings).append(message)
    if cards_missing_feedback_target:
        message = f"research cards missing feedback target: {cards_missing_feedback_target}"
        (blockers if strict else warnings).append(message)
    if visible_missing_cards:
        message = f"visible_core_opportunities_missing_cards={visible_missing_cards}"
        (blockers if strict and fresh_visible_missing_cards else warnings).append(message)
    if visible_missing_store_rows:
        message = f"visible_core_opportunities_missing_store_rows={visible_missing_store_rows}"
        strict_core_store = strict and not include_test_artifacts and not include_legacy_artifacts
        (blockers if strict_core_store else warnings).append(message)
    if duplicate_store_rows:
        warnings.append(f"duplicate_core_opportunity_store_rows={duplicate_store_rows}")
    if store_rows_missing_card_path:
        message = f"core_opportunity_store_rows_missing_card_path={store_rows_missing_card_path}"
        (blockers if strict and card_count else warnings).append(message)
    if core_cards_missing_store:
        message = f"core_cards_missing_store_row={core_cards_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if orphan_core_cards:
        warnings.append(f"orphan_core_opportunity_cards={orphan_core_cards}")
    if diagnostic_fake_core:
        warnings.append(f"diagnostic_snapshots_with_fake_core_id={diagnostic_fake_core}")
    if snapshot_core_missing_store:
        message = f"alert_snapshots_core_id_missing_from_store={snapshot_core_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if acquisition_core_missing_store:
        message = f"evidence_acquisition_core_id_missing_from_store={acquisition_core_missing_store}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_primary_mismatches:
        message = f"card_primary_fields_mismatch_core_store={card_primary_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_acquisition_mismatches:
        message = f"card_evidence_acquisition_count_mismatch={card_acquisition_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_source_pack_mismatches:
        message = f"card_source_pack_mismatch_core_acquisition={card_source_pack_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_support_blockers:
        message = f"card_primary_section_contains_support_row_blockers={card_support_blockers}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_upgrade_inconsistent:
        message = f"card_upgrade_text_inconsistent_with_final_level={card_upgrade_inconsistent}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_market_missing:
        message = f"card_market_confirmation_missing_but_core_has_market_confirmation={card_market_missing}"
        (blockers if strict and core_store_available else warnings).append(message)
    if card_source_unknown:
        message = f"card_latest_source_unknown_but_accepted_evidence_exists={card_source_unknown}"
        (blockers if strict and core_store_available else warnings).append(message)
    if promoted_core_in_weak:
        message = f"quality_review_promoted_core_in_weak_section={promoted_core_in_weak}"
        (blockers if strict else warnings).append(message)
    if market_freshness_contradictions:
        message = f"market_freshness_contradictory_summary={market_freshness_contradictions}"
        (blockers if strict else warnings).append(message)
    if upgrade_high_priority:
        message = f"upgrade_candidates_include_high_priority={upgrade_high_priority}"
        (blockers if strict else warnings).append(message)
    if card_group_mismatches:
        message = f"daily_brief_card_group_mismatch_with_index={card_group_mismatches}"
        (blockers if strict and core_store_available else warnings).append(message)
    if core_route_conflicts:
        message = f"core_route_conflicts_with_opportunity_level={core_route_conflicts}"
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_validated_without_confirmation"]:
        message = (
            "live_validated_without_confirmation="
            f"{live_confirmation_conflicts['live_validated_without_confirmation']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_sector_digest_without_asset"]:
        message = (
            "live_sector_digest_without_asset="
            f"{live_confirmation_conflicts['live_sector_digest_without_asset']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_rejected_results_promoted"]:
        message = (
            "live_rejected_results_promoted="
            f"{live_confirmation_conflicts['live_rejected_results_promoted']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if live_confirmation_conflicts["live_skipped_budget_promoted"]:
        message = (
            "live_skipped_budget_promoted="
            f"{live_confirmation_conflicts['live_skipped_budget_promoted']}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if visible_missing_targets:
        message = f"visible_core_opportunities_missing_feedback_targets={visible_missing_targets}"
        (blockers if strict and fresh_visible_missing_targets else warnings).append(message)
    if snapshots_missing_core:
        warnings.append(f"alert_snapshots_missing_core_opportunity_id={snapshots_missing_core}")
    if snapshots_missing_feedback:
        message = f"alert_snapshots_missing_feedback_target={snapshots_missing_feedback}"
        (blockers if strict else warnings).append(message)
    if inbox_core_missing_card:
        message = f"inbox_core_item_missing_card={inbox_core_missing_card}"
        (blockers if strict and core_store_available else warnings).append(message)
    if inbox_core_alert_target:
        message = (
            "inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists="
            f"{inbox_core_alert_target}"
        )
        (blockers if strict and core_store_available else warnings).append(message)
    if inbox_diag_visible_default:
        message = f"inbox_diagnostic_snapshot_visible_by_default={inbox_diag_visible_default}"
        (blockers if strict else warnings).append(message)
    if audit_primary_not_canonical:
        message = f"audit_primary_snapshot_not_canonical_when_canonical_exists={audit_primary_not_canonical}"
        (blockers if strict and core_store_available else warnings).append(message)
    if diagnostic_snapshots_missing_feedback:
        warnings.append(
            "feedback_readiness_counts_diagnostic_as_required="
            f"{diagnostic_snapshots_missing_feedback}"
        )
    if alerts and not card_count and any(str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} for row in alerts):
        warnings.append("high-priority/triggered snapshots exist but no research cards were found")
    delivery_summary = _delivery.summarize_delivery_rows([row for row in delivery_rows if isinstance(row, Mapping)])
    if delivery_summary.failed:
        warnings.append(
            f"notification deliveries failed: {delivery_summary.failed} failed delivery row(s) for this profile/namespace"
        )
    delivery_conflicts = _notification_delivery_conflicts(
        delivery_rows=[row for row in delivery_rows if isinstance(row, Mapping)],
        core_rows_by_id=core_rows_by_id,
    )
    if delivery_conflicts["delivery_identity_mismatch_core_store"]:
        message = (
            "delivery_identity_mismatch_core_store="
            f"{delivery_conflicts['delivery_identity_mismatch_core_store']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["delivery_alert_id_not_canonical"]:
        message = (
            "delivery_alert_id_not_canonical="
            f"{delivery_conflicts['delivery_alert_id_not_canonical']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["digest_item_without_live_confirmation"]:
        message = (
            "digest_item_without_live_confirmation="
            f"{delivery_conflicts['digest_item_without_live_confirmation']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["digest_item_rejected_results_only"]:
        message = (
            "digest_item_rejected_results_only="
            f"{delivery_conflicts['digest_item_rejected_results_only']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["telegram_message_contains_absolute_path"]:
        message = (
            "telegram_message_contains_absolute_path="
            f"{delivery_conflicts['telegram_message_contains_absolute_path']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["telegram_message_contains_raw_debug_dump"]:
        message = (
            "telegram_message_contains_raw_debug_dump="
            f"{delivery_conflicts['telegram_message_contains_raw_debug_dump']}"
        )
        (blockers if strict else warnings).append(message)
    if delivery_conflicts["notification_preview_missing"]:
        warnings.append(f"notification_preview_missing={delivery_conflicts['notification_preview_missing']}")
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
    if quality["quality_fields_missing_count"]:
        message = (
            "quality fields missing: "
            f"total={quality['quality_fields_missing_count']} "
            f"hypotheses_missing_verdict={quality['hypothesis_rows_missing_opportunity_verdict']} "
            f"watchlist_missing={quality['watchlist_rows_missing_quality_fields']} "
            f"alerts_missing={quality['alert_rows_missing_quality_fields']}"
            f" fresh_hypotheses_missing_top_level={quality['fresh_hypothesis_rows_missing_top_level_quality']} "
            f"fresh_watchlist_missing_top_level={quality['fresh_watchlist_rows_missing_top_level_quality']} "
            f"fresh_alerts_missing_top_level={quality['fresh_alert_rows_missing_top_level_quality']} "
            f"legacy_quality_missing={quality['legacy_quality_missing_rows']}"
        )
        if fresh_missing:
            (blockers if strict else warnings).append(message)
        else:
            warnings.append(message)
    route_conflict_alerts = _latest_run_rows(alerts, runs)
    route_conflicts = _alertable_quality_route_conflicts(route_conflict_alerts)
    snapshot_core_conflicts = _alert_snapshot_core_conflicts(route_conflict_alerts, core_rows)
    fresh_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=False)
    legacy_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=True)
    missing_final_route = _missing_final_route_rows(route_conflict_alerts)
    fresh_missing_final_route = _missing_final_route_rows(route_conflict_alerts, legacy=False)
    if route_conflicts:
        message = f"alertable_route_conflicts_with_opportunity_level={route_conflicts}"
        warnings.append(message)
    if snapshot_core_conflicts["route_mismatch"]:
        message = f"alert_snapshot_route_mismatch_core_store={snapshot_core_conflicts['route_mismatch']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["level_mismatch"]:
        message = f"alert_snapshot_level_mismatch_core_store={snapshot_core_conflicts['level_mismatch']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["live_confirmation_stale"]:
        message = f"alert_snapshot_live_confirmation_stale={snapshot_core_conflicts['live_confirmation_stale']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["core_resolution_missing"]:
        message = f"alert_snapshot_core_resolution_missing={snapshot_core_conflicts['core_resolution_missing']}"
        (blockers if strict and core_store_available else warnings).append(message)
    if snapshot_core_conflicts["pre_reconciliation_alertable"]:
        warnings.append(
            "alert_snapshot_pre_reconciliation_alertable="
            f"{snapshot_core_conflicts['pre_reconciliation_alertable']}"
        )
    if snapshot_core_conflicts["diagnostic_support_alertable"]:
        message = f"diagnostic_support_snapshot_alertable={snapshot_core_conflicts['diagnostic_support_alertable']}"
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["diagnostic_support_inherits_core_route"]:
        message = (
            "diagnostic_support_snapshot_inherits_core_route="
            f"{snapshot_core_conflicts['diagnostic_support_inherits_core_route']}"
        )
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["duplicate_alertable_snapshot_for_core"]:
        message = (
            "duplicate_alertable_snapshot_for_core="
            f"{snapshot_core_conflicts['duplicate_alertable_snapshot_for_core']}"
        )
        (blockers if strict else warnings).append(message)
    if snapshot_core_conflicts["canonical_snapshot_missing_for_visible_core"]:
        warnings.append(
            "canonical_snapshot_missing_for_visible_core="
            f"{snapshot_core_conflicts['canonical_snapshot_missing_for_visible_core']}"
        )
    if fresh_route_conflicts and strict:
        blockers.append(f"fresh_quality_route_conflict_rows={fresh_route_conflicts}")
    if legacy_route_conflicts:
        message = f"legacy_quality_conflict_rows={legacy_route_conflicts}"
        (blockers if strict and strict_legacy else warnings).append(message)
    if fresh_missing_final_route and strict:
        blockers.append(f"fresh_alert_rows_missing_final_route={fresh_missing_final_route}")
    watchlist_conflicts = _watchlist_quality_state_conflicts(watchlist)
    if watchlist_conflicts["quality_capped_watchlist_rows"]:
        warnings.append(
            f"quality-capped rows present: {watchlist_conflicts['quality_capped_watchlist_rows']}"
        )
    if watchlist_conflicts["non_hypothesis_watchlist_quality_conflicts"]:
        warnings.append(
            "non_hypothesis_watchlist_quality_conflicts="
            f"{watchlist_conflicts['non_hypothesis_watchlist_quality_conflicts']}"
        )
    if watchlist_conflicts["hypothesis_watchlist_quality_conflicts"]:
        warnings.append(
            "hypothesis_watchlist_quality_conflicts="
            f"{watchlist_conflicts['hypothesis_watchlist_quality_conflicts']}"
        )
    if watchlist_conflicts["watchlist_state_conflicts_with_quality"]:
        warnings.append(
            f"watchlist_state_conflicts_with_quality={watchlist_conflicts['watchlist_state_conflicts_with_quality']}"
        )
    if watchlist_conflicts["fresh_uncapped"]:
        message = f"fresh_watchlist_state_conflict_rows={watchlist_conflicts['fresh_uncapped']}"
        (blockers if strict else warnings).append(message)
    if watchlist_conflicts["legacy"]:
        message = f"legacy_watchlist_conflicts={watchlist_conflicts['legacy']}"
        (blockers if strict and strict_legacy else warnings).append(message)
    incident_linkage = _incident_linkage_summary(
        hypotheses=hypotheses,
        watchlist=watchlist,
        alerts=alerts,
        incidents=incidents,
    )
    if incident_linkage["hypothesis_rows_missing_incident_id"]:
        message = f"hypothesis_rows_missing_incident_id={incident_linkage['hypothesis_rows_missing_incident_id']}"
        (blockers if strict and incident_linkage["fresh_missing_hypotheses"] else warnings).append(message)
    if incident_linkage["watchlist_hypothesis_rows_missing_incident_id"]:
        message = (
            "watchlist_hypothesis_rows_missing_incident_id="
            f"{incident_linkage['watchlist_hypothesis_rows_missing_incident_id']}"
        )
        (blockers if strict and incident_linkage["fresh_missing_watchlist"] else warnings).append(message)
    if incident_linkage["alert_hypothesis_rows_missing_incident_id"]:
        message = f"alert_hypothesis_rows_missing_incident_id={incident_linkage['alert_hypothesis_rows_missing_incident_id']}"
        (blockers if strict and incident_linkage["fresh_missing_alerts"] else warnings).append(message)
    if incident_linkage["incident_rows_without_linked_hypotheses"]:
        warnings.append(
            f"incident_rows_without_linked_hypotheses={incident_linkage['incident_rows_without_linked_hypotheses']}"
        )
    if incident_linkage["incident_rows_without_linked_watchlist"]:
        warnings.append(
            f"incident_rows_without_linked_watchlist={incident_linkage['incident_rows_without_linked_watchlist']}"
        )
    if incident_linkage["diagnostic_incident_rows"]:
        warnings.append(f"diagnostic_incident_rows={incident_linkage['diagnostic_incident_rows']}")
    if incident_linkage["raw_observation_incident_rows"]:
        warnings.append(f"raw_observation_incident_rows={incident_linkage['raw_observation_incident_rows']}")
    if incident_linkage["external_context_incident_rows"]:
        warnings.append(f"external_context_incident_rows={incident_linkage['external_context_incident_rows']}")
    if incident_linkage["rejected_incident_rows"]:
        warnings.append(f"rejected_incident_rows={incident_linkage['rejected_incident_rows']}")
    if incident_linkage["canonical_unlinked_incidents"]:
        warnings.append(f"canonical_unlinked_incidents={incident_linkage['canonical_unlinked_incidents']}")
    if incident_linkage["active_incident_without_qualified_link"]:
        message = f"active_incident_without_qualified_link={incident_linkage['active_incident_without_qualified_link']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["linked_incident_without_qualified_link"]:
        warnings.append(f"linked_incident_without_qualified_link={incident_linkage['linked_incident_without_qualified_link']}")
    if incident_linkage["weak_unqualified_incident_links"]:
        warnings.append(f"weak_unqualified_incident_links={incident_linkage['weak_unqualified_incident_links']}")
    if incident_linkage["quality_blocked_links_present"]:
        warnings.append(f"quality_blocked_links_present={incident_linkage['quality_blocked_links_present']}")
    if incident_linkage["quality_blocked_links_promoting_incident"]:
        message = f"quality_blocked_links_promoting_incident={incident_linkage['quality_blocked_links_promoting_incident']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["incident_relevance_missing"]:
        message = f"incident_relevance_missing={incident_linkage['incident_relevance_missing']}"
        (blockers if strict else warnings).append(message)
    if incident_linkage["garbage_primary_subject_incidents"]:
        warnings.append(f"garbage_primary_subject_incidents={incident_linkage['garbage_primary_subject_incidents']}")
    if incident_linkage["invalid_canonical_incident_rows"]:
        message = f"invalid_canonical_incident_rows={incident_linkage['invalid_canonical_incident_rows']}"
        (blockers if strict else warnings).append(message)
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
        core_route_conflicts_with_opportunity_level=core_route_conflicts,
        live_validated_without_confirmation=live_confirmation_conflicts["live_validated_without_confirmation"],
        live_sector_digest_without_asset=live_confirmation_conflicts["live_sector_digest_without_asset"],
        live_rejected_results_promoted=live_confirmation_conflicts["live_rejected_results_promoted"],
        live_skipped_budget_promoted=live_confirmation_conflicts["live_skipped_budget_promoted"],
        runs_with_matching_snapshots=matching_snapshot_runs,
        runs_with_missing_snapshots=missing_snapshot_runs,
        runs_with_external_snapshot_paths=external_snapshot_runs,
        legacy_rows_skipped=0 if include_legacy_artifacts else raw_legacy,
        legacy_rows_counted=sum(
            1 for row in (*runs, *alerts, *feedback, *outcomes)
            if event_alpha_artifacts.is_legacy_row(row)
        ),
        delivery_rows=delivery_summary.rows,
        deliveries_partial_delivered=delivery_summary.partial_delivered,
        deliveries_failed=delivery_summary.failed,
        delivery_identity_mismatch_core_store=delivery_conflicts["delivery_identity_mismatch_core_store"],
        delivery_alert_id_not_canonical=delivery_conflicts["delivery_alert_id_not_canonical"],
        telegram_message_contains_absolute_path=delivery_conflicts["telegram_message_contains_absolute_path"],
        telegram_message_contains_raw_debug_dump=delivery_conflicts["telegram_message_contains_raw_debug_dump"],
        digest_item_without_live_confirmation=delivery_conflicts["digest_item_without_live_confirmation"],
        digest_item_rejected_results_only=delivery_conflicts["digest_item_rejected_results_only"],
        notification_preview_missing=delivery_conflicts["notification_preview_missing"],
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
        strict_legacy=bool(strict_legacy),
        strict=bool(strict),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "feedback_target",
        "core_opportunity_id",
        "alert_id",
        "card_id",
        "alert_key",
        "snapshot_id",
    ))


def _alert_snapshot_should_have_core_id(row: Mapping[str, Any]) -> bool:
    if str(row.get("row_type") or "") not in {"", "event_alpha_alert_snapshot"}:
        return False
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    level = str(row.get("opportunity_level") or "").casefold()
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "")
    if event_alpha_router.route_value_is_alertable(route):
        return True
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
        return True
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    return state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }


def _alert_snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return event_alpha_notification_inbox.alert_snapshot_is_diagnostic(row)


def _audit_primary_snapshot_not_canonical_when_canonical_exists(
    alerts: Iterable[Mapping[str, Any]],
    store_core_ids: set[str],
) -> int:
    by_core: dict[str, list[dict[str, Any]]] = {}
    for row in alerts:
        core_id = str(row.get("core_opportunity_id") or row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
        if not core_id or core_id not in store_core_ids:
            continue
        by_core.setdefault(core_id, []).append(dict(row))
    conflicts = 0
    for rows in by_core.values():
        has_canonical = any(_snapshot_is_canonical(row) for row in rows)
        if not has_canonical:
            continue
        primary = _best_snapshot_for_doctor(rows)
        if not _snapshot_is_canonical(primary):
            conflicts += 1
    return conflicts


def _best_snapshot_for_doctor(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = [dict(row) for row in rows]
    if not items:
        return {}

    def rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
        diagnostic = _alert_snapshot_is_diagnostic(row)
        return (
            3 if _snapshot_is_canonical(row) else 0,
            1 if event_alpha_router.route_value_is_alertable(str(row.get("final_route_after_quality_gate") or row.get("route") or "")) and not diagnostic else 0,
            str(row.get("observed_at") or row.get("snapshot_id") or ""),
        )

    return max(items, key=rank)


def _snapshot_is_canonical(row: Mapping[str, Any]) -> bool:
    if _alert_snapshot_is_diagnostic(row):
        return False
    status = str(row.get("snapshot_core_resolution_status") or row.get("core_resolution_status") or "")
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
        or status in {"canonical", event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED}
        or bool(row.get("snapshot_core_reconciled"))
    )


def _expected_card_group_for_store_core(
    opportunity: event_core_opportunities.CoreOpportunity | None,
) -> str | None:
    if opportunity is None:
        return None
    if event_core_opportunities.core_opportunity_visibility_group(opportunity) is None:
        return "Diagnostic / Source-Noise / Control Cards"
    if opportunity.is_high_priority or opportunity.is_watchlist or opportunity.is_validated_digest or opportunity.alertable:
        return "Core Opportunity Cards"
    if (
        str(opportunity.final_state_after_quality_gate or "").strip()
        == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        or str(opportunity.primary_row.get("state_quality_capped") or "").strip().casefold()
        in {"1", "true", "yes", "y"}
        or opportunity.quality_capped_supporting_rows > 0
    ):
        return "Local-Only / Quality-Capped Cards"
    if str(opportunity.opportunity_level or "").casefold() == "exploratory" or opportunity.opportunity_score_final >= 50:
        return "Near-Miss Cards"
    return "Local-Only / Quality-Capped Cards"


def _core_has_fresh_rows(opportunity: event_core_opportunities.CoreOpportunity) -> bool:
    return any(
        not event_alpha_artifacts.is_legacy_row(row)
        for row in (opportunity.primary_row, *opportunity.supporting_rows)
    )


def _card_primary_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    mismatches = 0
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        route = str(core.get("final_route_after_quality_gate") or "").strip()
        state = str(core.get("final_state_after_quality_gate") or "").strip()
        level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        route_line = _card_line_value(text, "Final route")
        verdict_line = _card_line_value(text, "Opportunity verdict")
        summary_line = _card_line_value(text, "State / alert tier")
        mismatch = False
        if route_line and route and route_line != route:
            mismatch = True
        if verdict_line and level and not verdict_line.startswith(level):
            mismatch = True
        if summary_line and state and not summary_line.startswith(f"{state} /"):
            mismatch = True
        if summary_line and route and not summary_line.endswith(f"/ {route}"):
            mismatch = True
        mismatches += int(mismatch)
    return mismatches


def _card_acquisition_count_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if view.accepted_evidence_count <= 0:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_evidence_count(text, "accepted")
        if rendered is not None and rendered != view.accepted_evidence_count:
            mismatches += 1
    return mismatches


def _card_source_pack_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if not view.source_pack:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_line_value(text, "Source pack")
        if rendered and rendered != view.source_pack:
            mismatches += 1
    return mismatches


def _card_primary_section_contains_support_row_blockers(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    blockers = (
        "blocked by generic cooccurrence",
        "needs proof that this event directly affects the token",
        "no token value-capture mechanism is visible",
    )
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        count += int(any(blocker in text for blocker in blockers))
    return count


def _card_upgrade_text_inconsistent_with_final_level(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        if str(core.get("opportunity_level") or core.get("final_opportunity_level") or "").casefold() == "high_priority":
            count += int("already high priority" not in text)
    return count


def _card_market_confirmation_missing_but_core_has_market_confirmation(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        has_market = core.get("market_confirmation_level") not in (None, "", "none") or core.get("market_confirmation_score") not in (None, "")
        if not has_market:
            continue
        text = _read_card_text(path).casefold()
        count += int("no market snapshot stored" in text or "market data: not available" in text)
    return count


def _card_latest_source_unknown_but_accepted_evidence_exists(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    count = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        core_id = event_research_cards.card_core_opportunity_id(path) or ""
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        accepted = max(int(core.get("evidence_acquisition_accepted_count") or 0), view.accepted_evidence_count)
        if accepted <= 0:
            continue
        text = _read_card_text(path).casefold()
        count += int("- latest source: unknown" in text or "- latest source: not available" in text)
    return count


def _card_core_row(path: Path, core_rows_by_id: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    core_id = event_research_cards.card_core_opportunity_id(path)
    return core_rows_by_id.get(core_id or "")


def _read_card_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _core_row_is_promoted(row: Mapping[str, Any]) -> bool:
    level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").casefold()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)


def _card_evidence_count(text: str, label: str) -> int | None:
    match = re.search(rf"\b{re.escape(label)}=(\d+)\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _promoted_core_rows_that_are_weak(core_rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in core_rows:
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "")
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        impact = str(row.get("impact_path_type") or row.get("primary_impact_path") or "")
        if level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route):
            if impact in {"generic_cooccurrence_only", "insufficient_data"}:
                count += 1
    return count


def _card_line_value(text: str, label: str) -> str | None:
    match = re.search(rf"^-\s*{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _core_row_has_market_freshness_contradiction(row: Mapping[str, Any]) -> bool:
    status = str(row.get("market_context_freshness_status") or "").casefold()
    source = str(row.get("market_context_source") or "").casefold()
    age = row.get("market_context_age_hours")
    cap = row.get("market_context_freshness_cap_applied")
    if status not in {"fresh", "fixture_allowed_stale"}:
        return False
    if source not in {"", "missing", "unknown"}:
        return False
    return age in (None, "", "unknown") and bool(cap)


def _quality_missing_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    hypothesis_rows = [dict(row) for row in hypotheses if dict(row).get("row_type") in {"event_impact_hypothesis", ""}]
    watchlist_rows = [dict(row) for row in watchlist if dict(row).get("row_type") in {"event_watchlist_state", ""}]
    alert_rows = [dict(row) for row in alerts if dict(row).get("row_type") in {"event_alpha_alert_snapshot", ""}]
    hypothesis_missing_verdict = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_level"))
        or event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_score_final"))
    )
    watchlist_missing = sum(1 for row in watchlist_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    alert_missing = sum(1 for row in alert_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    all_rows = [*hypothesis_rows, *watchlist_rows, *alert_rows]
    missing_rows = [
        row
        for row in all_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
    ]
    legacy_missing = sum(1 for row in missing_rows if event_alpha_artifacts.is_legacy_row(row))
    fresh_hypothesis_missing = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_watchlist_missing = sum(
        1
        for row in watchlist_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_alert_missing = sum(
        1
        for row in alert_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    return {
        "quality_fields_missing_count": len(missing_rows),
        "hypothesis_rows_missing_opportunity_verdict": hypothesis_missing_verdict,
        "watchlist_rows_missing_quality_fields": watchlist_missing,
        "alert_rows_missing_quality_fields": alert_missing,
        "fresh_hypothesis_rows_missing_top_level_quality": fresh_hypothesis_missing,
        "fresh_watchlist_rows_missing_top_level_quality": fresh_watchlist_missing,
        "fresh_alert_rows_missing_top_level_quality": fresh_alert_missing,
        "legacy_quality_missing_rows": legacy_missing,
        "non_legacy_quality_missing": max(0, len(missing_rows) - legacy_missing),
    }


def _latest_run_rows(rows: Iterable[Mapping[str, Any]], run_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    run_ids = [str(row.get("run_id") or "") for row in run_rows if str(row.get("run_id") or "")]
    if not run_ids:
        return [row for row in rows]
    latest = sorted(run_ids)[-1]
    latest_rows = [row for row in rows if str(row.get("run_id") or "") == latest]
    return latest_rows


def _alertable_quality_route_conflicts(alerts: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in alerts if _row_has_alertable_quality_conflict(row))


def _alert_snapshot_core_conflicts(
    alerts: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "route_mismatch": 0,
        "level_mismatch": 0,
        "live_confirmation_stale": 0,
        "core_resolution_missing": 0,
        "pre_reconciliation_alertable": 0,
        "diagnostic_support_alertable": 0,
        "diagnostic_support_inherits_core_route": 0,
        "duplicate_alertable_snapshot_for_core": 0,
        "canonical_snapshot_missing_for_visible_core": 0,
    }
    core_rows_tuple = tuple(core_rows)
    core_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
    }
    alertable_canonical_by_core_route: dict[tuple[str, str], int] = {}
    canonical_alertable_core_ids: set[str] = set()
    for row in alerts:
        if event_alpha_artifacts.is_legacy_row(row):
            continue
        if _is_diagnostic_support_snapshot(row):
            route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
            alertable = bool(row.get("alertable_after_quality_gate", row.get("route_alertable")))
            if alertable or event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_alertable"] += 1
            if event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_inherits_core_route"] += 1
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if not core_id:
            continue
        core = core_by_id.get(core_id)
        if core is None:
            out["core_resolution_missing"] += 1
            continue
        snapshot_reconciled = bool(row.get("snapshot_core_reconciled"))
        snapshot_route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        core_route = str(core.get("final_route_after_quality_gate") or core.get("route") or "").strip()
        snapshot_level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        core_level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        if snapshot_route != core_route and not snapshot_reconciled:
            out["route_mismatch"] += 1
        if snapshot_level != core_level and not snapshot_reconciled:
            out["level_mismatch"] += 1
        snapshot_promoted = (
            snapshot_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(snapshot_route)
        )
        core_promoted = (
            core_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(core_route)
        )
        if (
            bool(core.get("live_confirmation_capped")) or str(core.get("live_confirmation_status") or "") in {"missing", "unresolved"}
        ) and snapshot_promoted and not core_promoted and not snapshot_reconciled:
            out["live_confirmation_stale"] += 1
        requested_route = str(row.get("requested_route_before_core_reconciliation") or "").strip()
        if (
            snapshot_reconciled
            and event_alpha_router.route_value_is_alertable(requested_route)
            and not event_alpha_router.route_value_is_alertable(snapshot_route)
        ):
            out["pre_reconciliation_alertable"] += 1
        if event_alpha_router.route_value_is_alertable(snapshot_route):
            canonical_alertable_core_ids.add(core_id)
            key = (core_id, snapshot_route)
            alertable_canonical_by_core_route[key] = alertable_canonical_by_core_route.get(key, 0) + 1
    out["duplicate_alertable_snapshot_for_core"] = sum(
        max(0, count - 1)
        for count in alertable_canonical_by_core_route.values()
        if count > 1
    )
    alertable_visible_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
        and event_alpha_router.route_value_is_alertable(
            row.get("final_route_after_quality_gate") or row.get("route")
        )
        and not event_core_opportunities.row_is_diagnostic(row)
    }
    out["canonical_snapshot_missing_for_visible_core"] = len(alertable_visible_core_ids - canonical_alertable_core_ids)
    return out


def _is_diagnostic_support_snapshot(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or bool(row.get("is_diagnostic_snapshot"))
    )


def _quality_route_conflicts(alerts: Iterable[Mapping[str, Any]], *, legacy: bool) -> int:
    count = 0
    for row in alerts:
        is_legacy = event_alpha_artifacts.is_legacy_row(row)
        if legacy != is_legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification == event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT or _row_has_alertable_quality_conflict(row):
            count += 1
    return count


def _missing_final_route_rows(alerts: Iterable[Mapping[str, Any]], *, legacy: bool | None = None) -> int:
    count = 0
    for row in alerts:
        if legacy is not None and event_alpha_artifacts.is_legacy_row(row) != legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification in {
            event_alpha_alert_store.SNAPSHOT_MISSING_FINAL_ROUTE,
            event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
        }:
            count += 1
    return count


def _core_route_conflicts_with_opportunity_level(rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        }:
            continue
        if bool(row.get("state_quality_capped")):
            continue
        components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
        _, block = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=True)
        if block:
            continue
        count += 1
    return count


def _live_confirmation_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, int]:
    out = {
        "live_validated_without_confirmation": 0,
        "live_sector_digest_without_asset": 0,
        "live_rejected_results_promoted": 0,
        "live_skipped_budget_promoted": 0,
    }
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route not in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }:
            continue
        if not event_opportunity_verdict.live_confirmation_required(
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        ):
            continue
        if bool(row.get("live_confirmation_passed")):
            continue
        if str(row.get("live_confirmation_status") or "") == "confirmed":
            continue
        out["live_validated_without_confirmation"] += 1
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip().casefold()
        if symbol == "SECTOR" or coin_id in {"sports_fan_proxy", "political_meme_proxy", "ai_ipo_proxy", "rwa_preipo_proxy", "sector"}:
            out["live_sector_digest_without_asset"] += 1
        status = str(row.get("evidence_acquisition_status") or "").strip()
        if status == "rejected_results_only":
            out["live_rejected_results_promoted"] += 1
        if status == "skipped_budget":
            out["live_skipped_budget_promoted"] += 1
    return out


def _notification_delivery_conflicts(
    *,
    delivery_rows: Iterable[Mapping[str, Any]],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "delivery_identity_mismatch_core_store": 0,
        "delivery_alert_id_not_canonical": 0,
        "telegram_message_contains_absolute_path": 0,
        "telegram_message_contains_raw_debug_dump": 0,
        "digest_item_without_live_confirmation": 0,
        "digest_item_rejected_results_only": 0,
        "notification_preview_missing": 0,
    }
    latest = _delivery.latest_rows_by_delivery(delivery_rows)
    for row in latest:
        lane = str(row.get("lane") or "")
        if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        alert_id = str(row.get("alert_id") or "").strip()
        core = core_rows_by_id.get(core_id) if core_id else None
        if core_id and not core:
            out["delivery_identity_mismatch_core_store"] += 1
        if core_id and alert_id and alert_id != core_id and lane != "triggered_fade":
            out["delivery_alert_id_not_canonical"] += 1
        if core and lane in {"daily_digest", "instant_escalation"}:
            if _delivery_core_lacks_live_confirmation(core):
                out["digest_item_without_live_confirmation"] += 1
            if str(core.get("evidence_acquisition_status") or "") == "rejected_results_only":
                out["digest_item_rejected_results_only"] += 1
        preview_path = str(row.get("notification_preview_path") or "").strip()
        if not preview_path:
            out["notification_preview_missing"] += 1
            continue
        path = Path(preview_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out["notification_preview_missing"] += 1
            continue
        telegram_body = text.split("## Telegram Body", 1)[-1]
        if re.search(r"/Users/|/tmp/|/private/tmp/", telegram_body):
            out["telegram_message_contains_absolute_path"] += 1
        if re.search(r"\b(alert_id|card_id|research_card|route|lane)=", telegram_body):
            out["telegram_message_contains_raw_debug_dump"] += 1
    return out


def _delivery_core_lacks_live_confirmation(core: Mapping[str, Any]) -> bool:
    if not event_alpha_router.route_value_is_alertable(core.get("final_route_after_quality_gate") or core.get("route")):
        return False
    status = str(core.get("evidence_acquisition_status") or "").strip()
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    accepted = _as_int(core.get("accepted_evidence_count"))
    source_class = str(core.get("source_class") or "").strip()
    market = str(core.get("market_confirmation_level") or "").casefold()
    freshness = str(core.get("market_context_freshness_status") or "").casefold()
    impact = str(core.get("impact_path_type") or "").casefold()
    strong_source = source_class in {
        "official_project",
        "official_exchange",
        "structured_event_calendar",
        "cryptopanic_tagged",
        "project_blog",
        "exchange_announcement",
    }
    direct_impact = impact in {
        "direct_token_event",
        "listing_liquidity_event",
        "unlock_supply_event",
        "exploit_security_event",
        "venue_value_capture",
        "fan_token_event",
    }
    fresh_market = market not in {"", "none", "missing", "unknown", "insufficient_data"} and freshness not in {"missing", "stale"}
    if accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate")):
        return False
    if strong_source or (fresh_market and direct_impact):
        return False
    return status in {
        "",
        "rejected_results_only",
        "no_results",
        "skipped_budget",
        "provider_unavailable",
        "skipped_config",
        "not_configured",
    } or confirmation in {"", "does_not_confirm", "unresolved", "coverage_gap"}


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _row_has_alertable_quality_conflict(row: Mapping[str, Any]) -> bool:
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    final_route, _ = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=False)
    route_alertable = bool(row.get("route_alertable"))
    route = str(row.get("route") or "")
    persisted_alertable = route_alertable or event_alpha_router.route_value_is_alertable(route)
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    if persisted_alertable and not final_alertable:
        return True
    if event_alpha_router.route_value_is_alertable(route) and route != final_route:
        return True
    if not final_alertable and not persisted_alertable:
        return False
    if final_route == "TRIGGERED_FADE_RESEARCH":
        return False
    level = str(data.get("opportunity_level") or "")
    if level in {"local_only", "exploratory", ""}:
        return True
    if str(data.get("impact_path_type") or "") == "insufficient_data":
        return True
    if str(data.get("candidate_role") or "") == "unknown_with_reason":
        return True
    if str(data.get("source_class") or "") == "insufficient_data":
        return True
    if str(data.get("evidence_specificity") or "") == "insufficient_data":
        return True
    try:
        score = float(data.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return score <= 0.0


def _watchlist_quality_state_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "watchlist_state_conflicts_with_quality": 0,
        "universal_watchlist_state_conflicts": 0,
        "non_hypothesis_watchlist_quality_conflicts": 0,
        "hypothesis_watchlist_quality_conflicts": 0,
        "quality_capped_watchlist_rows": 0,
        "active_watchlist_rows_quality_capped": 0,
        "fresh_uncapped": 0,
        "legacy": 0,
    }
    for row in rows:
        state = event_watchlist.final_state_value(row)
        requested = event_watchlist.requested_state_value(row)
        requested_active = requested in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        final_active = state in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        persisted_capped = row.get("state_quality_capped") is True
        capped = persisted_capped and not final_active
        has_conflict = _row_has_watchlist_quality_conflict(row)
        if capped and requested_active:
            out["quality_capped_watchlist_rows"] += 1
            out["active_watchlist_rows_quality_capped"] += 1
            continue
        if has_conflict:
            out["watchlist_state_conflicts_with_quality"] += 1
            out["universal_watchlist_state_conflicts"] += 1
            if _is_hypothesis_watchlist_row(row):
                out["hypothesis_watchlist_quality_conflicts"] += 1
            else:
                out["non_hypothesis_watchlist_quality_conflicts"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy"] += 1
            elif not capped or final_active:
                out["fresh_uncapped"] += 1
    return out


def _filter_watchlist_rows_for_doctor(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    """Filter watchlist rows while honoring path-scoped legacy metadata gaps.

    Older watchlist entries did not carry profile/run-mode fields even when
    they lived inside a profile namespace directory. Doctor callers pass rows
    from a resolved path, so missing metadata should not make those rows
    invisible to quality checks.
    """
    out: list[dict[str, Any]] = []
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        if not include_test_artifacts and event_alpha_artifacts.is_non_operational_row(data):
            continue
        row_profile = _clean_optional(data.get("profile"))
        if profile_key is not None and row_profile not in (None, profile_key):
            continue
        row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
        if namespace_key is not None and row_ns not in (None, namespace_key):
            continue
        if not include_legacy_artifacts and event_alpha_artifacts.is_legacy_row(data):
            if _row_has_watchlist_quality_conflict(data) or event_watchlist.state_is_quality_capped(data):
                if profile and not data.get("profile"):
                    data["profile"] = profile
                if artifact_namespace and not (data.get("artifact_namespace") or data.get("namespace")):
                    data["artifact_namespace"] = artifact_namespace
                if not data.get("run_mode"):
                    data["run_mode"] = "notification_burn_in" if str(profile or "").startswith("notify_") else "burn_in"
                data["_path_scoped_metadata_inferred"] = True
            else:
                continue
        out.append(data)
    return out


def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


def _row_has_watchlist_quality_conflict(row: Mapping[str, Any]) -> bool:
    if event_watchlist.final_state_value(row) == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return False
    requested = event_watchlist.requested_state_value(row)
    if requested not in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
        event_watchlist.EventWatchlistState.ARMED.value,
    }:
        return False
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    level = str(data.get("opportunity_level") or "")
    if level in {"local_only", "exploratory", ""}:
        return True
    if str(data.get("impact_path_type") or "") == "insufficient_data":
        return True
    if str(data.get("candidate_role") or "") == "unknown_with_reason":
        return True
    if str(data.get("source_class") or "") == "insufficient_data":
        return True
    if str(data.get("evidence_specificity") or "") == "insufficient_data":
        return True
    try:
        score = float(data.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return score <= 0.0


def _is_hypothesis_watchlist_row(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    return bool(row.get("hypothesis_id") or components.get("hypothesis_id") or str(row.get("relationship_type") or "") == "impact_hypothesis")


def _incident_linkage_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    incidents: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "hypothesis_rows_missing_incident_id": 0,
        "watchlist_hypothesis_rows_missing_incident_id": 0,
        "alert_hypothesis_rows_missing_incident_id": 0,
        "incident_rows_without_linked_hypotheses": 0,
        "incident_rows_without_linked_watchlist": 0,
        "canonical_unlinked_incidents": 0,
        "active_incident_without_qualified_link": 0,
        "linked_incident_without_qualified_link": 0,
        "weak_unqualified_incident_links": 0,
        "quality_blocked_links_present": 0,
        "quality_blocked_links_promoting_incident": 0,
        "fresh_missing_hypotheses": 0,
        "fresh_missing_watchlist": 0,
        "fresh_missing_alerts": 0,
        "legacy_missing_hypotheses": 0,
        "legacy_missing_watchlist": 0,
        "legacy_missing_alerts": 0,
        "diagnostic_incident_rows": 0,
        "raw_observation_incident_rows": 0,
        "external_context_incident_rows": 0,
        "rejected_incident_rows": 0,
        "incident_relevance_missing": 0,
        "invalid_canonical_incident_rows": 0,
        "garbage_primary_subject_incidents": 0,
    }
    for row in hypotheses:
        if dict(row).get("row_type") not in {"event_impact_hypothesis", ""}:
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_hypotheses"] += 1
            else:
                out["fresh_missing_hypotheses"] += 1
    for row in watchlist:
        if str(row.get("relationship_type") or "") != "impact_hypothesis":
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["watchlist_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_watchlist"] += 1
            else:
                out["fresh_missing_watchlist"] += 1
    for row in alerts:
        is_hypothesis = bool(row.get("hypothesis_id")) or str(row.get("relationship_type") or "") == "impact_hypothesis"
        if not is_hypothesis or _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["alert_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_legacy_row(row):
                out["legacy_missing_alerts"] += 1
            else:
                out["fresh_missing_alerts"] += 1
    for row in incidents:
        if dict(row).get("row_type") != "event_incident":
            continue
        subject_quality = str(row.get("incident_subject_quality") or "").strip()
        diagnostic = row.get("diagnostic_only") is True
        relevance = str(row.get("incident_relevance_status") or "").strip()
        if not relevance:
            out["incident_relevance_missing"] += 1
        if _is_garbage_incident_subject(row.get("primary_subject")):
            out["garbage_primary_subject_incidents"] += 1
        if relevance == "raw_observation":
            out["raw_observation_incident_rows"] += 1
        if relevance == "external_context_only":
            out["external_context_incident_rows"] += 1
        if relevance == "rejected_incident":
            out["rejected_incident_rows"] += 1
        relevance_is_hidden = (
            relevance in {"raw_observation", "external_context_only", "rejected_incident"}
            or (relevance == "diagnostic_only" and subject_quality != "invalid")
        )
        if diagnostic or (relevance_is_hidden and relevance in {"diagnostic_only", "rejected_incident"}):
            out["diagnostic_incident_rows"] += 1
            continue
        if relevance_is_hidden:
            continue
        elif subject_quality in {"invalid", "diagnostic_only"}:
            out["invalid_canonical_incident_rows"] += 1
        operational = relevance in {"canonical_incident", "linked_incident", "active_incident"} or (not relevance and not diagnostic)
        qualified_links = int(row.get("qualified_link_count") or 0)
        weak_links = int(row.get("weak_link_count") or 0)
        quality_blocked_links = int(row.get("quality_blocked_link_count") or 0)
        if relevance == "active_incident" and qualified_links <= 0:
            out["active_incident_without_qualified_link"] += 1
        if relevance == "linked_incident" and qualified_links <= 0:
            out["linked_incident_without_qualified_link"] += 1
        if weak_links > 0:
            out["weak_unqualified_incident_links"] += weak_links
        if quality_blocked_links > 0:
            out["quality_blocked_links_present"] += quality_blocked_links
        if relevance in {"linked_incident", "active_incident"} and quality_blocked_links > 0 and qualified_links <= 0:
            out["quality_blocked_links_promoting_incident"] += quality_blocked_links
        if operational and not row.get("linked_hypothesis_ids"):
            out["incident_rows_without_linked_hypotheses"] += 1
        if operational and not row.get("linked_watchlist_keys"):
            out["incident_rows_without_linked_watchlist"] += 1
        if operational and not row.get("linked_hypothesis_ids") and not row.get("linked_watchlist_keys"):
            out["canonical_unlinked_incidents"] += 1
    return out


_GARBAGE_INCIDENT_SUBJECTS = {
    "about",
    "actions",
    "all",
    "announcements",
    "any",
    "any us",
    "best prediction market apps",
    "bitcoin and mstr are",
    "during",
    "here",
    "however",
    "it",
    "llm",
    "need",
    "non",
    "not",
    "note",
    "only",
    "polymarket invite code sbwire",
    "polymarket referral code sbwire",
    "polymarket world cup volume",
    "when",
    "where",
    "will",
    "yes",
}


def _is_garbage_incident_subject(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    text = " ".join(text.replace("-", " ").replace("_", " ").split())
    if not text:
        return False
    if text in _GARBAGE_INCIDENT_SUBJECTS:
        return True
    if "invite code" in text or "referral code" in text:
        return True
    if text.startswith("best ") and text.endswith(" apps"):
        return True
    if text.endswith(" are") and " and " in text:
        return True
    return False


def _row_incident_id(row: Mapping[str, Any]) -> str:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    return str(row.get("incident_id") or components.get("incident_id") or score.get("incident_id") or "").strip()


def _row_has_no_incident(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    status = str(
        row.get("incident_link_status")
        or components.get("incident_link_status")
        or score.get("incident_link_status")
        or ""
    ).strip()
    reason = str(
        row.get("incident_link_reason")
        or components.get("incident_link_reason")
        or score.get("incident_link_reason")
        or ""
    ).strip()
    if status == "no_incident" and reason:
        return True
    warnings = " ".join(str(value) for value in row.get("warnings") or ())
    return "no_incident" in warnings


def _record_snapshot_availability_issue(
    row: Mapping[str, Any],
    availability: str,
    *,
    blockers: list[str],
    warnings: list[str],
    strict: bool,
) -> None:
    run_id = str(row.get("run_id") or "unknown")
    path = event_alpha_artifacts.safe_path_label(row.get("alert_store_path"))
    run_mode = str(row.get("run_mode") or "legacy")
    if availability == event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH:
        blockers.append(
            f"alertable_run_missing_matching_snapshot_rows: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL:
        warnings.append(
            f"fixture_snapshot_external_allowed: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY:
        message = (
            f"legacy_run_missing_snapshot_rows: {run_id}; "
            f"snapshot availability unknown for legacy/default row"
        )
        (blockers if strict else warnings).append(message)
    else:
        target = blockers if run_mode in {"burn_in", "operational"} else warnings
        target.append(f"alertable_run_missing_matching_snapshot_rows: {run_id}")


def format_artifact_doctor_report(result: EventAlphaArtifactDoctorResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA ARTIFACT DOCTOR (research artifact only)",
        "=" * 76,
        f"status: {result.status}",
        f"profile: {result.profile or 'any'}",
        f"namespace: {result.artifact_namespace or 'any'}",
        f"strict: {str(result.strict).lower()}",
        f"strict_legacy: {str(result.strict_legacy).lower()}",
        (
            "rows: "
            f"runs={result.run_rows} alerts={result.alert_rows} "
            f"feedback={result.feedback_rows} outcomes={result.outcome_rows} cards={result.card_files}"
        ),
        (
            "research cards: "
            f"research_card_files={result.research_card_files} "
            f"research_card_index_present={str(result.research_card_index_present).lower()} "
            f"cards_missing_lineage={result.cards_missing_lineage} "
            f"cards_missing_feedback_target={result.cards_missing_feedback_target}"
        ),
        (
            "core opportunity coverage: "
            f"visible_core_opportunities={result.visible_core_opportunities} "
            f"core_opportunity_store_rows={result.core_opportunity_store_rows} "
            f"visible_core_opportunities_missing_store_rows={result.visible_core_opportunities_missing_store_rows} "
            f"duplicate_core_opportunity_store_rows={result.duplicate_core_opportunity_store_rows} "
            f"core_opportunity_store_rows_missing_card_path={result.core_opportunity_store_rows_missing_card_path} "
            f"visible_core_opportunities_missing_cards={result.visible_core_opportunities_missing_cards} "
            f"visible_core_opportunities_missing_feedback_targets={result.visible_core_opportunities_missing_feedback_targets} "
            f"alert_snapshots_missing_core_opportunity_id={result.alert_snapshots_missing_core_opportunity_id} "
            f"alert_snapshots_missing_feedback_target={result.alert_snapshots_missing_feedback_target} "
            f"core_cards_missing_store_row={result.core_cards_missing_store_row} "
            f"visible_core_cards_missing_store_row={result.visible_core_cards_missing_store_row} "
            f"orphan_core_opportunity_cards={result.orphan_core_opportunity_cards} "
            f"diagnostic_snapshots_with_fake_core_id={result.diagnostic_snapshots_with_fake_core_id} "
            f"alert_snapshots_core_id_missing_from_store={result.alert_snapshots_core_id_missing_from_store} "
            f"evidence_acquisition_core_id_missing_from_store={result.evidence_acquisition_core_id_missing_from_store} "
            f"card_primary_fields_mismatch_core_store={result.card_primary_fields_mismatch_core_store} "
            f"card_evidence_acquisition_count_mismatch={result.card_evidence_acquisition_count_mismatch} "
            f"card_source_pack_mismatch_core_acquisition={result.card_source_pack_mismatch_core_acquisition} "
            f"card_primary_section_contains_support_row_blockers={result.card_primary_section_contains_support_row_blockers} "
            f"card_upgrade_text_inconsistent_with_final_level={result.card_upgrade_text_inconsistent_with_final_level} "
            f"audit_primary_impact_path_mismatch_core={result.audit_primary_impact_path_mismatch_core} "
            f"audit_source_pack_mismatch_core={result.audit_source_pack_mismatch_core} "
            f"card_market_confirmation_missing_but_core_has_market_confirmation={result.card_market_confirmation_missing_but_core_has_market_confirmation} "
            f"card_latest_source_unknown_but_accepted_evidence_exists={result.card_latest_source_unknown_but_accepted_evidence_exists} "
            f"quality_review_promoted_core_in_weak_section={result.quality_review_promoted_core_in_weak_section} "
            f"market_freshness_contradictory_summary={result.market_freshness_contradictory_summary} "
            f"quality_review_market_freshness_contradiction={result.quality_review_market_freshness_contradiction} "
            f"upgrade_candidates_include_high_priority={result.upgrade_candidates_include_high_priority} "
            f"daily_brief_card_group_mismatch_with_index={result.daily_brief_card_group_mismatch_with_index} "
            f"core_route_conflicts_with_opportunity_level={result.core_route_conflicts_with_opportunity_level} "
            f"alert_snapshot_route_mismatch_core_store={result.alert_snapshot_route_mismatch_core_store} "
            f"alert_snapshot_level_mismatch_core_store={result.alert_snapshot_level_mismatch_core_store} "
            f"alert_snapshot_live_confirmation_stale={result.alert_snapshot_live_confirmation_stale} "
            f"alert_snapshot_core_resolution_missing={result.alert_snapshot_core_resolution_missing} "
            f"alert_snapshot_pre_reconciliation_alertable={result.alert_snapshot_pre_reconciliation_alertable} "
            f"diagnostic_support_snapshot_alertable={result.diagnostic_support_snapshot_alertable} "
            f"diagnostic_support_snapshot_inherits_core_route={result.diagnostic_support_snapshot_inherits_core_route} "
            f"duplicate_alertable_snapshot_for_core={result.duplicate_alertable_snapshot_for_core} "
            f"canonical_snapshot_missing_for_visible_core={result.canonical_snapshot_missing_for_visible_core} "
            f"inbox_core_item_missing_card={result.inbox_core_item_missing_card} "
            f"inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists={result.inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists} "
            f"inbox_diagnostic_snapshot_visible_by_default={result.inbox_diagnostic_snapshot_visible_by_default} "
            f"audit_primary_snapshot_not_canonical_when_canonical_exists={result.audit_primary_snapshot_not_canonical_when_canonical_exists} "
            f"feedback_readiness_counts_diagnostic_as_required={result.feedback_readiness_counts_diagnostic_as_required} "
            f"live_validated_without_confirmation={result.live_validated_without_confirmation} "
            f"live_sector_digest_without_asset={result.live_sector_digest_without_asset} "
            f"live_rejected_results_promoted={result.live_rejected_results_promoted} "
            f"live_skipped_budget_promoted={result.live_skipped_budget_promoted}"
        ),
        (
            "snapshot lineage: "
            f"matching={result.runs_with_matching_snapshots} "
            f"missing={result.runs_with_missing_snapshots} "
            f"external={result.runs_with_external_snapshot_paths}"
        ),
        (
            "legacy rows: "
            f"skipped={result.legacy_rows_skipped} counted={result.legacy_rows_counted}"
        ),
        (
            "notification deliveries: "
            f"rows={result.delivery_rows} partial={result.deliveries_partial_delivered} failed={result.deliveries_failed} "
            f"identity_mismatch={result.delivery_identity_mismatch_core_store} "
            f"alert_id_not_canonical={result.delivery_alert_id_not_canonical} "
            f"digest_without_confirmation={result.digest_item_without_live_confirmation} "
            f"digest_rejected_only={result.digest_item_rejected_results_only} "
            f"preview_missing={result.notification_preview_missing} "
            f"raw_debug_dump={result.telegram_message_contains_raw_debug_dump} "
            f"absolute_path={result.telegram_message_contains_absolute_path}"
        ),
        (
            "quality fields: "
            f"missing_total={result.quality_fields_missing_count} "
            f"hypotheses_missing_verdict={result.hypothesis_rows_missing_opportunity_verdict} "
            f"watchlist_missing={result.watchlist_rows_missing_quality_fields} "
            f"alerts_missing={result.alert_rows_missing_quality_fields} "
            f"fresh_hypotheses_missing_top_level={result.fresh_hypothesis_rows_missing_top_level_quality} "
            f"fresh_watchlist_missing_top_level={result.fresh_watchlist_rows_missing_top_level_quality} "
            f"fresh_alerts_missing_top_level={result.fresh_alert_rows_missing_top_level_quality} "
            f"legacy_quality_missing={result.legacy_quality_missing_rows}"
        ),
        (
            "quality gate conflicts: "
            f"alertable_route_conflicts_with_opportunity_level={result.alertable_route_conflicts_with_opportunity_level} "
            f"fresh_quality_route_conflict_rows={result.fresh_quality_route_conflict_rows} "
            f"legacy_quality_conflict_rows={result.legacy_quality_conflict_rows} "
            f"alert_rows_missing_final_route={result.alert_rows_missing_final_route} "
            f"fresh_alert_rows_missing_final_route={result.fresh_alert_rows_missing_final_route}"
        ),
        (
            "watchlist quality state: "
            f"watchlist_state_conflicts_with_quality={result.watchlist_state_conflicts_with_quality} "
            f"universal={result.universal_watchlist_state_conflicts} "
            f"non_hypothesis={result.non_hypothesis_watchlist_quality_conflicts} "
            f"hypothesis={result.hypothesis_watchlist_quality_conflicts} "
            f"quality_capped={result.quality_capped_watchlist_rows} "
            f"active_watchlist_rows_quality_capped={result.active_watchlist_rows_quality_capped} "
            f"fresh_watchlist_state_conflict_rows={result.fresh_watchlist_state_conflict_rows} "
            f"legacy_watchlist_conflicts={result.legacy_watchlist_conflicts}"
        ),
        (
            "incident linkage: "
            f"hypothesis_rows_missing_incident_id={result.hypothesis_rows_missing_incident_id} "
            f"watchlist_hypothesis_rows_missing_incident_id={result.watchlist_hypothesis_rows_missing_incident_id} "
            f"alert_hypothesis_rows_missing_incident_id={result.alert_hypothesis_rows_missing_incident_id} "
            f"incident_rows_without_linked_hypotheses={result.incident_rows_without_linked_hypotheses} "
            f"incident_rows_without_linked_watchlist={result.incident_rows_without_linked_watchlist} "
            f"canonical_unlinked_incidents={result.canonical_unlinked_incidents} "
            f"active_incident_without_qualified_link={result.active_incident_without_qualified_link} "
            f"linked_incident_without_qualified_link={result.linked_incident_without_qualified_link} "
            f"weak_unqualified_incident_links={result.weak_unqualified_incident_links} "
            f"quality_blocked_links_present={result.quality_blocked_links_present} "
            f"quality_blocked_links_promoting_incident={result.quality_blocked_links_promoting_incident} "
            f"diagnostic_incident_rows={result.diagnostic_incident_rows} "
            f"raw_observation_incident_rows={result.raw_observation_incident_rows} "
            f"external_context_incident_rows={result.external_context_incident_rows} "
            f"rejected_incident_rows={result.rejected_incident_rows} "
            f"incident_relevance_missing={result.incident_relevance_missing} "
            f"invalid_canonical_incident_rows={result.invalid_canonical_incident_rows} "
            f"garbage_primary_subject_incidents={result.garbage_primary_subject_incidents} "
            f"fresh_blockers={result.fresh_incident_linkage_blockers} "
            f"legacy_warnings={result.legacy_incident_linkage_warnings}"
        ),
        "",
        "blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("Doctor reports artifact hygiene only; it does not send, trade, paper trade, or alter tiers.")
    return "\n".join(lines).rstrip()
