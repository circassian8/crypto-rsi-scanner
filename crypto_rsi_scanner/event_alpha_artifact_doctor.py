"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_alert_store, event_alpha_artifacts, event_alpha_quality_fields, event_alpha_router, event_core_opportunities, event_research_cards, event_watchlist
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
    visible_core_opportunities_missing_cards: int = 0
    visible_core_opportunities_missing_feedback_targets: int = 0
    alert_snapshots_missing_core_opportunity_id: int = 0
    alert_snapshots_missing_feedback_target: int = 0
    runs_with_matching_snapshots: int = 0
    runs_with_missing_snapshots: int = 0
    runs_with_external_snapshot_paths: int = 0
    legacy_rows_skipped: int = 0
    legacy_rows_counted: int = 0
    delivery_rows: int = 0
    deliveries_partial_delivered: int = 0
    deliveries_failed: int = 0
    quality_fields_missing_count: int = 0
    hypothesis_rows_missing_opportunity_verdict: int = 0
    watchlist_rows_missing_quality_fields: int = 0
    alert_rows_missing_quality_fields: int = 0
    fresh_hypothesis_rows_missing_top_level_quality: int = 0
    fresh_watchlist_rows_missing_top_level_quality: int = 0
    fresh_alert_rows_missing_top_level_quality: int = 0
    legacy_quality_missing_rows: int = 0
    alertable_route_conflicts_with_opportunity_level: int = 0
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
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    incident_rows: Iterable[Mapping[str, Any] | object] = (),
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
    raw_watchlist = [_row(row) for row in watchlist_rows]
    raw_incidents = [_row(row) for row in incident_rows]
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
    card_core_ids = {value for path in research_card_paths for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_feedback_targets = {value for path in research_card_paths for value in (event_research_cards.card_feedback_target(path),) if value}
    visible_core = event_core_opportunities.visible_core_opportunities([*watchlist, *alerts, *hypotheses])
    visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids)
    visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
    )
    fresh_visible_missing_cards = sum(1 for item in visible_core if item.core_opportunity_id not in card_core_ids and _core_has_fresh_rows(item))
    fresh_visible_missing_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id not in card_feedback_targets
        and not any(str(row.get("core_opportunity_id") or "") == item.core_opportunity_id and _alert_has_feedback_target(row) for row in alerts)
        and _core_has_fresh_rows(item)
    )
    snapshots_missing_core = sum(1 for row in alerts if _alert_snapshot_should_have_core_id(row) and not str(row.get("core_opportunity_id") or "").strip())
    snapshots_missing_feedback = sum(1 for row in alerts if _alert_snapshot_should_have_core_id(row) and not _alert_has_feedback_target(row))
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
    if visible_missing_targets:
        message = f"visible_core_opportunities_missing_feedback_targets={visible_missing_targets}"
        (blockers if strict and fresh_visible_missing_targets else warnings).append(message)
    if snapshots_missing_core:
        warnings.append(f"alert_snapshots_missing_core_opportunity_id={snapshots_missing_core}")
    if snapshots_missing_feedback:
        message = f"alert_snapshots_missing_feedback_target={snapshots_missing_feedback}"
        (blockers if strict else warnings).append(message)
    if alerts and not card_count and any(str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} for row in alerts):
        warnings.append("high-priority/triggered snapshots exist but no research cards were found")
    delivery_summary = _delivery.summarize_delivery_rows([row for row in delivery_rows if isinstance(row, Mapping)])
    if delivery_summary.failed:
        warnings.append(
            f"notification deliveries failed: {delivery_summary.failed} failed delivery row(s) for this profile/namespace"
        )
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
    fresh_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=False)
    legacy_route_conflicts = _quality_route_conflicts(route_conflict_alerts, legacy=True)
    missing_final_route = _missing_final_route_rows(route_conflict_alerts)
    fresh_missing_final_route = _missing_final_route_rows(route_conflict_alerts, legacy=False)
    if route_conflicts:
        message = f"alertable_route_conflicts_with_opportunity_level={route_conflicts}"
        warnings.append(message)
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
        visible_core_opportunities_missing_cards=visible_missing_cards,
        visible_core_opportunities_missing_feedback_targets=visible_missing_targets,
        alert_snapshots_missing_core_opportunity_id=snapshots_missing_core,
        alert_snapshots_missing_feedback_target=snapshots_missing_feedback,
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
        quality_fields_missing_count=quality["quality_fields_missing_count"],
        hypothesis_rows_missing_opportunity_verdict=quality["hypothesis_rows_missing_opportunity_verdict"],
        watchlist_rows_missing_quality_fields=quality["watchlist_rows_missing_quality_fields"],
        alert_rows_missing_quality_fields=quality["alert_rows_missing_quality_fields"],
        fresh_hypothesis_rows_missing_top_level_quality=quality["fresh_hypothesis_rows_missing_top_level_quality"],
        fresh_watchlist_rows_missing_top_level_quality=quality["fresh_watchlist_rows_missing_top_level_quality"],
        fresh_alert_rows_missing_top_level_quality=quality["fresh_alert_rows_missing_top_level_quality"],
        legacy_quality_missing_rows=quality["legacy_quality_missing_rows"],
        alertable_route_conflicts_with_opportunity_level=route_conflicts,
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


def _core_has_fresh_rows(opportunity: event_core_opportunities.CoreOpportunity) -> bool:
    return any(
        not event_alpha_artifacts.is_legacy_row(row)
        for row in (opportunity.primary_row, *opportunity.supporting_rows)
    )


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
            f"visible_core_opportunities_missing_cards={result.visible_core_opportunities_missing_cards} "
            f"visible_core_opportunities_missing_feedback_targets={result.visible_core_opportunities_missing_feedback_targets} "
            f"alert_snapshots_missing_core_opportunity_id={result.alert_snapshots_missing_core_opportunity_id} "
            f"alert_snapshots_missing_feedback_target={result.alert_snapshots_missing_feedback_target}"
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
            f"rows={result.delivery_rows} partial={result.deliveries_partial_delivered} failed={result.deliveries_failed}"
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
