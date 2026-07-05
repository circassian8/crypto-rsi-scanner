"""Split implementation for `crypto_rsi_scanner/cli/event_alpha_command_registry.py` (dispatch)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from .._scanner_bindings import bind_scanner_globals
from ..services import (
    event_alpha_integrated as _service_integrated,
    event_alpha_namespace as _service_namespace,
    event_alpha_notifications as _service_notifications,
    event_alpha_outcomes as _service_outcomes,
    event_alpha_provider_preflights as _service_provider_preflights,
    event_alpha_reports as _service_reports,
    event_alpha_research as _service_research,
)
from .models import *  # noqa: F403
from .metadata import *  # noqa: F403


_FEEDBACK_SHORTCUT_ATTRS = (
    ("event_feedback_useful", "useful"),
    ("event_feedback_junk", "junk"),
    ("event_feedback_watch", "watch"),
    ("event_feedback_false_positive", "false_positive"),
    ("event_feedback_late", "late"),
    ("event_feedback_source_noise", "source_noise"),
    ("event_feedback_needs_confirmation", "needs_confirmation"),
    ("event_feedback_duplicate", "duplicate"),
    ("event_feedback_promising_source_type", "promising_source_type"),
    ("event_feedback_traded", "traded_elsewhere"),
    ("event_feedback_ignore", "ignored"),
    ("event_feedback_missed", "missed"),
)


def _include_legacy_api_artifacts(args) -> bool:
    return bool(
        getattr(args, "include_api", False)
        or getattr(args, "include_legacy", False)
        or getattr(args, "all_history", False)
    )

def _dispatch_event_alpha_command_section_1(args) -> bool:
    if args.event_fade_report:
        event_fade_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_discovery_report:
        event_discovery_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_alert_report:
        event_alert_report(
            verbose=args.verbose,
            send=args.event_alert_send,
            with_llm=args.with_llm,
            event_now=args.event_now,
        )
        return True
    if args.event_alpha_radar_report:
        event_alpha_radar_report(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return True
    if args.event_alpha_cycle:
        _service_research.event_alpha_cycle(
            verbose=args.verbose,
            with_llm=args.with_llm,
            send=args.event_alert_send,
            event_now=args.event_now,
            profile_name=args.event_alpha_profile,
        )
        return True
    if args.event_alpha_notify_cycle:
        event_alpha_notify_cycle(
            verbose=args.verbose,
            with_llm=args.with_llm,
            send=args.event_alert_send,
            event_now=args.event_now,
            profile_name=args.event_alpha_profile,
            ignore_provider_backoff=args.ignore_provider_backoff,
        )
        return True
    if args.event_alpha_notify_preview:
        _service_notifications.event_alpha_notify_preview(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return True
    if args.event_alpha_notify_go_no_go:
        _service_notifications.event_alpha_notify_go_no_go(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=getattr(args, "event_alpha_include_api_artifacts", False),
        )
        return True
    if args.event_alpha_environment_doctor:
        _service_reports.event_alpha_environment_doctor_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
        )
        return True
    if args.event_alpha_pause_notifications:
        event_alpha_pause_notifications(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            reason=args.reason,
        )
        return True
    if args.event_alpha_resume_notifications:
        event_alpha_resume_notifications(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            confirm=args.confirm,
        )
        return True
    if args.event_alpha_scheduler_status:
        event_alpha_scheduler_status_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return True
    if args.event_alpha_generate_launchd:
        event_alpha_generate_launchd(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            out=args.out,
        )
        return True
    if args.event_alpha_notification_slo_report:
        event_alpha_notification_slo_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_diagnostics=args.event_opportunity_audit_include_diagnostics,
        )
        return True
    if args.event_alpha_export_notification_pack:
        if not args.out:
            print("--event-alpha-export-notification-pack requires --out OUT.zip")
            return True
        _service_notifications.event_alpha_export_notification_pack(
            args.out,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_notification_checklist:
        event_alpha_notification_checklist_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return True
    if args.event_alpha_notify_preview_from_artifacts:
        _service_notifications.event_alpha_notify_preview_from_artifacts(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_send_readiness:
        event_alpha_send_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_telegram_final_check:
        event_alpha_telegram_final_check_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_send_test:
        event_alpha_send_test(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            ignore_notification_pause=args.ignore_notification_pause,
        )
        return True
    if args.event_alpha_telegram_recipient_check:
        event_alpha_telegram_recipient_check_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
        )
        return True
    return False

def _dispatch_event_alpha_command_section_2(args) -> bool:
    if args.event_alpha_notification_runs_report:
        event_alpha_notification_runs_report(
            path=args.event_alpha_notification_runs_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_notification_inbox:
        event_alpha_notification_inbox_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_diagnostics=args.event_opportunity_audit_include_diagnostics,
            burn_in_review=args.event_alpha_burn_in_review,
        )
        return True
    if args.event_alpha_notification_deliveries_report:
        event_alpha_notification_deliveries_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_notification_retry_failed:
        event_alpha_notification_retry_failed(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            confirm=args.confirm,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_mark_namespace_stale:
        _service_namespace.event_alpha_mark_namespace_stale(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            reason=args.reason,
            superseded_by=args.event_alpha_stale_superseded_by,
        )
        return True
    if args.event_alpha_mark_known_stale_namespaces:
        _service_namespace.event_alpha_mark_known_stale_namespaces(verbose=args.verbose)
        return True
    if args.event_alpha_prune_or_archive_stale_namespace:
        _service_namespace.event_alpha_prune_or_archive_stale_namespace(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            archive=args.event_alpha_stale_archive,
        )
        return True
    if args.event_alpha_namespace_lifecycle_report:
        _service_namespace.event_alpha_namespace_lifecycle_report(verbose=args.verbose)
        return True
    if args.event_alpha_list_active_namespaces:
        _service_namespace.event_alpha_list_active_namespaces(verbose=args.verbose)
        return True
    if args.event_alpha_archive_stale_namespaces:
        _service_namespace.event_alpha_archive_stale_namespaces(verbose=args.verbose)
        return True
    if args.event_alpha_provider_health_reset:
        _service_provider_preflights.event_alpha_provider_health_reset(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            provider_key=args.provider_key,
            service=args.service,
            role=args.role,
            reset_all=args.all,
            confirm=args.confirm,
        )
        return True
    if args.event_alpha_notify_fixture_smoke:
        _service_notifications.event_alpha_notify_fixture_smoke(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_alpha_runs_report:
        _service_reports.event_alpha_runs_report(
            path=args.event_alpha_run_ledger_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_impact_hypotheses_report:
        latest_hypothesis_run = args.latest_run or not (args.all_history or args.run_id or args.since)
        event_impact_hypotheses_report(
            path=args.event_impact_hypothesis_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            latest_run=latest_hypothesis_run,
            run_id=args.run_id,
            since=args.since,
            include_api=_include_legacy_api_artifacts(args),
        )
        return True
    if args.event_impact_hypotheses_inbox:
        event_impact_hypotheses_inbox(
            path=args.event_impact_hypothesis_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_incidents_report:
        latest_incident_run = args.latest_run or not (args.all_history or args.run_id)
        event_incidents_report(
            path=args.event_incident_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            latest_run=latest_incident_run,
            run_id=args.run_id,
            include_api=_include_legacy_api_artifacts(args),
            include_diagnostic=args.include_diagnostic_incidents,
            include_raw=args.include_raw_incidents,
            include_external_context=args.include_external_context_incidents,
        )
        return True
    if args.event_impact_hypothesis_smoke:
        event_impact_hypothesis_smoke(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_alpha_status:
        _service_reports.event_alpha_status(profile_name=args.event_alpha_profile, verbose=args.verbose)
        return True
    if args.event_alpha_preflight:
        _service_reports.event_alpha_preflight_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            send_requested=args.event_alert_send,
            verbose=args.verbose,
        )
        return True
    return False

def _dispatch_event_alpha_command_section_3(args) -> bool:
    if args.event_alpha_feedback_readiness:
        event_alpha_feedback_readiness_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_profile_report:
        event_alpha_profile_report(args.event_alpha_profile_report, verbose=args.verbose)
        return True
    if args.event_catalyst_search_report:
        event_catalyst_search_report(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return True
    if args.event_watchlist_refresh:
        event_watchlist_refresh(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return True
    if args.event_watchlist_report:
        event_watchlist_report(verbose=args.verbose)
        return True
    if args.event_watchlist_monitor:
        event_watchlist_monitor_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_alpha_router_report:
        event_alpha_router_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return True
    if args.event_alpha_signal_quality_eval:
        event_alpha_signal_quality_eval(
            path=args.event_alpha_signal_quality_cases_path,
            verbose=args.verbose,
        )
        return True
    if args.event_opportunity_audit:
        event_opportunity_audit_report(
            args.event_opportunity_audit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_quality_review:
        event_alpha_quality_review_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_quality_coverage_report:
        event_alpha_quality_coverage_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_policy_simulate:
        event_alpha_policy_simulate_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_export_signal_quality_cases:
        event_alpha_export_signal_quality_cases(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            out_path=args.event_alpha_signal_quality_export_path,
        )
        return True
    if args.event_alpha_missed_report:
        event_alpha_missed_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_near_miss_report:
        event_alpha_near_miss_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            event_now=args.event_now,
        )
        return True
    if args.event_alpha_calibration_report:
        event_alpha_calibration_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_source_reliability_report:
        event_source_reliability_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_burn_in_scorecard:
        event_alpha_burn_in_scorecard(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_burn_in_checklist:
        event_alpha_burn_in_checklist(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_burn_in_readiness:
        _service_outcomes.event_alpha_burn_in_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
        )
        return True
    if args.event_alpha_v1_readiness:
        _service_reports.event_alpha_v1_readiness_report(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    return False

def _dispatch_event_alpha_command_section_4(args) -> bool:
    if args.event_alpha_health_guard:
        _service_reports.event_alpha_health_guard_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_artifact_doctor:
        _service_reports.event_alpha_artifact_doctor_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
            strict=args.event_alpha_artifact_doctor_strict,
            strict_api=getattr(args, "event_alpha_artifact_doctor_strict_api", False),
            delivery_strict_scope=args.event_alpha_artifact_doctor_delivery_scope,
            include_stale_artifacts=args.event_alpha_include_stale_artifacts,
            schema_only=args.event_alpha_doctor_schema_only,
            skip_api_checks=getattr(args, "event_alpha_doctor_skip_api_checks", False),
        )
        return True
    if args.event_alpha_tuning_worksheet:
        event_alpha_tuning_worksheet_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_export_burn_in_pack:
        _service_outcomes.event_alpha_export_burn_in_pack(
            args.event_alpha_export_burn_in_pack,
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_calibration_export_priors is not None:
        event_alpha_calibration_export_priors(
            args.event_alpha_calibration_export_priors or None,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_priors_shadow_report:
        event_alpha_priors_shadow_report(verbose=args.verbose)
        return True
    if args.event_alpha_export_eval_cases_from_feedback is not None:
        event_alpha_export_eval_cases_from_feedback(
            args.event_alpha_export_eval_cases_from_feedback or None,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_export_eval_cases_from_missed is not None:
        event_alpha_export_eval_cases_from_missed(
            args.event_alpha_export_eval_cases_from_missed or None,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_explain_last_run:
        event_alpha_explain_last_run(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_daily_brief:
        _service_reports.event_alpha_daily_brief_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_api_artifacts=args.event_alpha_include_api_artifacts,
        )
        return True
    if args.event_alpha_integrated_radar_cycle:
        integrated_input_mode = event_integrated_radar.INPUT_MODE_AUTO
        if args.event_alpha_integrated_radar_run_sidecars:
            integrated_input_mode = event_integrated_radar.INPUT_MODE_RUN_SIDECARS
        if args.event_alpha_integrated_radar_load_existing:
            integrated_input_mode = event_integrated_radar.INPUT_MODE_LOAD_EXISTING
        if args.event_alpha_integrated_radar_auto:
            integrated_input_mode = event_integrated_radar.INPUT_MODE_AUTO
        _service_integrated.event_alpha_integrated_radar_cycle_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            fixture=args.event_alpha_integrated_radar_fixture,
            input_mode=integrated_input_mode,
            coinalyze_namespace=args.event_alpha_integrated_radar_coinalyze_namespace,
        )
        return True
    if args.event_alpha_integrated_radar_fill_outcomes:
        event_alpha_integrated_radar_fill_outcomes_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_integrated_radar_outcome_report:
        event_alpha_integrated_radar_outcome_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_integrated_radar_calibration_report:
        event_alpha_integrated_radar_calibration_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_integrated_radar_calibration_export_priors:
        event_alpha_integrated_radar_calibration_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            export_priors=True,
        )
        return True
    if args.event_alpha_market_anomaly_scan:
        _service_integrated.event_alpha_market_anomaly_scan_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            market_rows_path=args.event_alpha_market_anomaly_rows,
            asset_registry_path=args.event_alpha_market_anomaly_asset_registry,
            coingecko_universe_path=args.event_alpha_market_anomaly_universe,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    return False

def _dispatch_event_alpha_command_section_5(args) -> bool:
    if args.event_alpha_official_exchange_report:
        _service_integrated.event_alpha_official_exchange_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            binance_path=args.event_alpha_official_exchange_binance,
            bybit_path=args.event_alpha_official_exchange_bybit,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_scheduled_catalyst_report:
        _service_integrated.event_alpha_scheduled_catalyst_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            tokenomist_path=args.event_alpha_scheduled_catalyst_tokenomist,
            messari_path=args.event_alpha_scheduled_catalyst_messari,
            coinmarketcal_path=args.event_alpha_scheduled_catalyst_coinmarketcal,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_derivatives_report:
        _service_integrated.event_alpha_derivatives_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            derivatives_path=args.event_alpha_derivatives_crowding_path,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_replay:
        _service_integrated.event_alpha_replay_report(
            priors=args.event_alpha_replay_priors,
            llm_advisory=args.event_alpha_replay_llm_advisory,
            raw_events_path=args.event_alpha_replay_raw_events,
            market_rows_path=args.event_alpha_replay_market_rows,
            compare=args.event_alpha_replay_compare,
            replay_profile=args.event_alpha_replay_profile,
            replay_profile_alt=args.event_alpha_replay_profile_alt,
            verbose=args.verbose,
        )
        return True
    if args.event_alpha_prune_artifacts:
        event_alpha_prune_artifacts(confirm=args.confirm, verbose=args.verbose)
        return True
    if args.event_research_card is not None:
        event_research_card_report(args.event_research_card, verbose=args.verbose)
        return True
    if args.event_research_cards_write:
        event_research_cards_write(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_alerts_report:
        event_alpha_alerts_report(
            path=args.event_alpha_alert_store_path,
            feedback_path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_fill_outcomes:
        event_alpha_fill_outcomes(
            args.event_alpha_fill_outcomes[0],
            args.event_alpha_fill_outcomes[1],
            path=args.event_alpha_alert_store_path,
            verbose=args.verbose,
        )
        return True
    if args.event_feedback_mark:
        event_feedback_mark(
            args.event_feedback_mark,
            args.event_feedback_label,
            notes=args.event_feedback_notes,
            marked_by=args.event_feedback_by,
            path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    for attr, label in _FEEDBACK_SHORTCUT_ATTRS:
        target = getattr(args, attr)
        if target is not None:
            event_feedback_shortcut(
                target,
                label,
                notes=args.event_feedback_notes,
                verbose=args.verbose,
                profile_name=args.event_alpha_profile,
                artifact_namespace=args.event_alpha_artifact_namespace or None,
            )
            return True
    if args.event_feedback_report:
        event_feedback_report(
            path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_llm_shadow_report:
        event_llm_shadow_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_llm_extract_report:
        event_llm_extract_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_discovery_refresh:
        event_discovery_refresh(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_discovery_status:
        event_discovery_status(json_output=args.json)
        return True
    if args.event_discovery_runs:
        event_discovery_runs(limit=args.event_discovery_run_limit, json_output=args.json)
        return True
    if args.event_discovery_binance_listen:
        event_discovery_binance_listen(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_fade_auto_report:
        event_fade_auto_report(verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_fade_export_sample:
        event_fade_export_sample(args.event_fade_export_sample, verbose=args.verbose, event_now=args.event_now)
        return True
    if args.event_fade_export_cache_sample:
        event_fade_export_cache_sample(
            args.event_fade_export_cache_sample,
            verbose=args.verbose,
            event_now=args.event_now,
        )
        return True
    if args.event_fade_review_sample:
        event_fade_review_sample(args.event_fade_review_sample, verbose=args.verbose)
        return True
    return False

def _dispatch_event_alpha_command_section_6(args) -> bool:
    if args.event_fade_labeling_queue:
        event_fade_labeling_queue(
            args.event_fade_labeling_queue,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_review_packet:
        sample_path, out_path = args.event_fade_review_packet
        event_fade_review_packet(
            sample_path,
            out_path,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_export_review_template:
        sample_path, out_path = args.event_fade_export_review_template
        event_fade_export_review_template(
            sample_path,
            out_path,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_apply_review_template:
        sample_path, template_path, out_path = args.event_fade_apply_review_template
        event_fade_apply_review_template(
            sample_path,
            template_path,
            out_path,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_check_review_template:
        sample_path, template_path = args.event_fade_check_review_template
        event_fade_check_review_template(
            sample_path,
            template_path,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_review_bundle:
        sample_path, out_dir = args.event_fade_review_bundle
        event_fade_review_bundle(
            sample_path,
            out_dir,
            limit=args.event_fade_queue_limit,
            prices_path=args.event_fade_review_bundle_prices,
            auto_export_prices=args.event_fade_review_bundle_export_prices,
            price_days=args.event_fade_price_days,
            price_fixture_dir=args.event_fade_price_fixture_dir,
            price_interval=args.event_fade_price_interval,
            refresh_price_cache=args.event_fade_refresh_price_cache,
            reviewed_path=args.event_fade_review_bundle_reviewed,
            overwrite_outcomes=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
            event_now=args.event_now,
        )
        return True
    if args.event_fade_cache_review_bundle:
        event_fade_cache_review_bundle(
            args.event_fade_cache_review_bundle,
            limit=args.event_fade_queue_limit,
            prices_path=args.event_fade_review_bundle_prices,
            auto_export_prices=args.event_fade_review_bundle_export_prices,
            price_days=args.event_fade_price_days,
            price_fixture_dir=args.event_fade_price_fixture_dir,
            price_interval=args.event_fade_price_interval,
            refresh_price_cache=args.event_fade_refresh_price_cache,
            reviewed_path=args.event_fade_review_bundle_reviewed,
            overwrite_outcomes=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
            event_now=args.event_now,
        )
        return True
    if args.event_fade_merge_sample:
        fresh_path, reviewed_path, out_path = args.event_fade_merge_sample
        event_fade_merge_sample(fresh_path, reviewed_path, out_path, verbose=args.verbose)
        return True
    if args.event_fade_fill_outcomes:
        sample_path, prices_path, out_path = args.event_fade_fill_outcomes
        event_fade_fill_outcomes(
            sample_path,
            prices_path,
            out_path,
            overwrite=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
        )
        return True
    if args.event_fade_export_outcome_prices:
        sample_path, out_path = args.event_fade_export_outcome_prices
        event_fade_export_outcome_prices(
            sample_path,
            out_path,
            days=args.event_fade_price_days,
            fixture_dir=args.event_fade_price_fixture_dir,
            interval=args.event_fade_price_interval,
            refresh_cache=args.event_fade_refresh_price_cache,
            verbose=args.verbose,
        )
        return True
    return False

def dispatch_event_alpha_command(args) -> bool:
    """Dispatch one Event Alpha command using the preserved branch order."""
    _bind_api_scanner_globals()
    if _dispatch_event_alpha_command_section_1(args):
        return True
    if _dispatch_event_alpha_command_section_2(args):
        return True
    if _dispatch_event_alpha_command_section_3(args):
        return True
    if _dispatch_event_alpha_command_section_4(args):
        return True
    if _dispatch_event_alpha_command_section_5(args):
        return True
    if _dispatch_event_alpha_command_section_6(args):
        return True
    return False
