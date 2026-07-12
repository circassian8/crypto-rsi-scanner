"""Locked implementations for fixed-path Event Alpha report writers."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime import *
from .config_reports import (
    _event_alpha_alert_store_config_from_runtime,
    _event_alpha_context_block,
    _event_research_now,
    _research_card_markdown_paths,
)
from .utility_calibration_exports import _event_alpha_local_artifacts


@dataclass(frozen=True)
class ArtifactDoctorExecution:
    result: Any
    exact_revision_recorded: bool | None


def unlock_calendar_preflight(context: Any, *, provider: str | None, smoke_mode: bool) -> None:
    report = event_unlock_calendar_preflight.build_preflight_report(
        namespace_dir=context.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        provider_filter=provider,
        tokenomist_path=config.EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH,
        messari_path=config.EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH,
        coinmarketcal_path=config.EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH,
        smoke_mode=smoke_mode,
        now=_event_research_now(),
    )
    json_path, md_path = event_unlock_calendar_preflight.write_preflight_artifacts(report, context.namespace_dir)
    print(_event_alpha_context_block(context))
    print(f"unlock_calendar_preflight_json: {event_artifact_paths.artifact_display_path(json_path)}")
    print(f"unlock_calendar_preflight_report: {event_artifact_paths.artifact_display_path(md_path)}")
    print(event_unlock_calendar_preflight.format_preflight_report(report))


def artifact_doctor(
    context: Any,
    *,
    profile_name: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
    doctor_strict: bool,
    strict_api: bool,
    delivery_strict_scope: str | None,
    include_stale_artifacts: bool,
    schema_only: bool,
    skip_api_checks: bool,
) -> Any:
    from . import reports as report_service

    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=500,
        latest_alerts=False,
    )
    operator_run = report_service._ensure_operator_state_from_latest_run(context, artifacts["runs"].rows)
    operator_revision = report_service._operator_revision_for_run(context, operator_run)
    cards_dir = context.research_cards_dir
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    evaluation_now = _event_research_now()
    result = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=artifacts["core_opportunities"].rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        market_anomaly_rows=event_market_anomaly_scanner.load_market_anomaly_rows(context.namespace_dir),
        official_exchange_candidate_rows=event_official_exchange.load_official_listing_candidates(context.namespace_dir),
        scheduled_catalyst_rows=event_scheduled_catalysts.load_scheduled_catalysts(context.namespace_dir),
        unlock_candidate_rows=event_scheduled_catalysts.load_unlock_candidates(context.namespace_dir),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        daily_brief_path=context.daily_brief_path,
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        artifact_namespace_dir=context.namespace_dir,
        inspected_alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
        outcomes_path=context.outcomes_path,
        integrated_candidate_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME
        ),
        integrated_outcomes_path=(
            context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
        ),
        notification_preview_path=(
            event_alpha_notification_delivery.notification_preview_path_for_context(context)
        ),
        run_ledger_path=context.run_ledger_path,
        strict=doctor_strict,
        strict_api=strict_api,
        delivery_strict_scope=delivery_strict_scope,
        include_stale_artifacts=include_stale_artifacts,
        schema_only=schema_only,
        skip_api_checks=skip_api_checks,
        evaluated_at=evaluation_now,
    )
    exact_revision_recorded = report_service._record_operator_doctor_result(
        context,
        result,
        run_row=operator_run,
        expected_revision=operator_revision,
        strict=doctor_strict,
        schema_only=schema_only,
        skip_api_checks=skip_api_checks,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_artifact_doctor.format_artifact_doctor_report(result))
    return ArtifactDoctorExecution(result, exact_revision_recorded)


def integrated_radar_calibration(context: Any, *, export_priors: bool) -> None:
    rows = event_integrated_radar_outcomes.load_integrated_radar_outcomes(context.namespace_dir)
    candidates, core_rows = event_integrated_radar_outcomes.load_integrated_radar_outcome_authority(
        context.namespace_dir
    )
    evaluated_at = _event_research_now()
    if export_priors:
        priors = event_integrated_radar_outcomes.build_integrated_radar_calibration_priors(
            rows,
            candidate_rows=candidates,
            core_rows=core_rows,
            evaluated_at=evaluated_at,
        )
        path = context.namespace_dir / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME
        path.write_text(json.dumps(priors, sort_keys=True), encoding="utf-8")
        print(_event_alpha_context_block(context))
        print(f"integrated_radar_calibration_priors: {path}")
        return
    report = event_integrated_radar_outcomes.format_integrated_radar_calibration_report(
        rows,
        candidate_rows=candidates,
        core_rows=core_rows,
        evaluated_at=evaluated_at,
    )
    path = context.namespace_dir / event_integrated_radar.INTEGRATED_CALIBRATION_REPORT_FILENAME
    path.write_text(report, encoding="utf-8")
    event_integrated_radar_outcomes.write_radar_performance_dashboard(
        (context.namespace_dir,),
        output_namespace_dir=context.namespace_dir,
        generated_at=evaluated_at,
    )
    print(_event_alpha_context_block(context))
    print(report)
