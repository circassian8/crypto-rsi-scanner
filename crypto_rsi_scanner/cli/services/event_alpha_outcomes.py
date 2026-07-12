"""Event Alpha Outcomes.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible through the public API bridge.
"""

from __future__ import annotations

import json
from types import ModuleType
from typing import Any, MutableMapping


_SERVICE_FUNCTION_NAMES = (
    'bind_scanner_globals',
    '_refresh_scanner_globals',
    '_scanner_call',
    'event_alpha_burn_in_readiness_report',
    'event_alpha_export_burn_in_pack',
    'event_alpha_integrated_radar_fill_outcomes_report',
    'event_alpha_integrated_radar_outcome_report',
    'event_alpha_integrated_radar_calibration_report',
    'event_alpha_calibration_report',
    'event_alpha_fill_outcomes',
    'event_alpha_feedback_readiness_report',
    'event_alpha_observed_outcome_build',
)


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module


def _refresh_scanner_globals() -> ModuleType:
    return bind_scanner_globals(globals())


def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from ... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)


def event_alpha_burn_in_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print live-style no-send burn-in readiness from profile-scoped artifacts."""
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    from crypto_rsi_scanner.event_alpha.operations import scorecard as event_alpha_contract_scorecard

    selected_profile = profile_name or "live_burn_in_no_send"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    evaluation_now = _event_research_now()
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        context.alert_store_path,
        latest_only=False,
        core_opportunity_store_path=context.core_opportunity_store_path,
    )
    current_alerts = event_alpha_alert_store.load_alert_snapshots(
        context.alert_store_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
    )
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=False,
        include_api=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        core_opportunity_rows=core_opportunities.rows,
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
        now=evaluation_now,
    )
    feedback_readiness = event_alpha_feedback_readiness.build_feedback_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        inbox_result=inbox,
        now=evaluation_now,
    )
    outcome_rows = [
        *event_alpha_outcome_artifact_io.read_jsonl(context.outcomes_path),
        *event_integrated_radar_outcomes.load_integrated_radar_outcomes(
            context.namespace_dir
        ),
    ]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(
            context.impact_hypothesis_store_path,
            limit=500,
            latest_run=True,
            include_api=True,
        ).rows,
        core_opportunity_rows=core_opportunities.rows,
        watchlist_rows=watchlist.entries,
        incident_rows=event_incident_store.load_incidents(
            context.incident_store_path,
            limit=500,
            latest_run=True,
            include_api=True,
        ).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(
            context.evidence_acquisition_path
        ),
        card_paths=[str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)],
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        llm_budget_rows=event_alpha_burn_in.load_llm_budget_rows(context.llm_budget_ledger_path),
        delivery_rows=delivery_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        include_test_artifacts=False,
        include_api_artifacts=False,
        artifact_namespace_dir=context.namespace_dir,
        inspected_alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        core_opportunity_store_path=context.core_opportunity_store_path,
        outcomes_path=context.outcomes_path,
        integrated_candidate_path=context.namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME,
        integrated_outcomes_path=context.namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        notification_preview_path=(
            event_alpha_notification_delivery.notification_preview_path_for_context(context)
        ),
        run_ledger_path=context.run_ledger_path,
        strict=True,
        evaluated_at=evaluation_now,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    acquisition_rows = event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path)
    contract_scorecard = event_alpha_contract_scorecard.build_authoritative_scorecard(
        base_dir=context.base_dir,
        now=evaluation_now,
    )
    readiness = event_alpha_burn_in_readiness.build_burn_in_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_rows=runs.rows,
        provider_status=provider_report,
        artifact_doctor=doctor,
        feedback_readiness=feedback_readiness,
        core_opportunity_rows=core_store.rows,
        evidence_acquisition_rows=acquisition_rows,
        daily_brief_path=context.daily_brief_path,
        burn_in_contract_scorecard=contract_scorecard,
    )
    print(_event_alpha_context_block(context))
    print(event_provider_status.format_event_discovery_provider_status(provider_report))
    print("")
    print(event_alpha_burn_in_readiness.format_burn_in_readiness(readiness))


def _burn_in_pack_artifact_doctor(
    *,
    artifacts: dict[str, Any],
    context: Any,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
    evaluated_at: Any,
) -> Any:
    cards_dir = context.research_cards_dir
    return event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=artifacts["core_opportunities"].rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        profile=context.profile,
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
        strict=bool(config.EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT),
        evaluated_at=evaluated_at,
    )


def _burn_in_pack_contract_sections(base_dir: Any, *, now: Any) -> tuple[Any, str, str]:
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist as checklist_api
    from crypto_rsi_scanner.event_alpha.operations import scorecard as scorecard_api

    scorecard = scorecard_api.build_authoritative_scorecard(base_dir=base_dir, now=now)
    checklist = checklist_api.build_burn_in_checklist(scorecard)
    return (
        scorecard,
        scorecard_api.format_scorecard(scorecard),
        checklist_api.format_burn_in_checklist(checklist),
    )


def event_alpha_export_burn_in_pack(
    out_path: str,
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Write a clean Event Alpha burn-in review zip."""
    _refresh_scanner_globals()
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
    artifacts = _event_alpha_local_artifacts(context=context, run_limit=500, latest_alerts=False)
    evaluation_now = _event_research_now()
    contract_scorecard, scorecard_text, checklist_text = _burn_in_pack_contract_sections(
        context.base_dir,
        now=evaluation_now,
    )
    readiness = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        candidate_rows=artifacts["candidate_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        days=days,
        now=evaluation_now,
        burn_in_contract_scorecard=contract_scorecard,
    )
    health = event_alpha_health_guard.evaluate_health_guard(
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
    doctor = _burn_in_pack_artifact_doctor(
        artifacts=artifacts,
        context=context,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        evaluated_at=evaluation_now,
    )
    router_result = event_alpha_router.route_watchlist(
        artifacts["watchlist"],
        cfg=_event_alpha_router_config_from_runtime(),
    )
    daily_brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        core_opportunity_rows=artifacts["core_opportunities"].rows,
        notification_runs=event_alpha_notification_runs.load_notification_runs(context.notification_runs_path).rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(context.impact_hypothesis_store_path, limit=100).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        watchlist_entries=artifacts["watchlist"].entries,
        router_result=router_result,
        provider_health_rows=artifacts["provider_rows"],
        artifact_namespace=artifact_namespace,
        run_mode=context.run_mode,
        run_ledger_path=context.run_ledger_path,
        alert_store_path=context.alert_store_path,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        clock_status=_event_clock_status(),
        generated_at=evaluation_now,
    )
    calibration = event_alpha_calibration.format_calibration_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        missed_rows=artifacts["missed_rows"],
        now=evaluation_now,
    )
    source_reliability = event_source_reliability.format_source_reliability_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
        now=evaluation_now,
    )
    tuning = event_alpha_tuning.format_tuning_worksheet(event_alpha_tuning.build_tuning_worksheet(
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
        now=evaluation_now,
    ))
    result = event_alpha_burn_in_pack.export_burn_in_pack(
        out_path,
        daily_brief=daily_brief,
        burn_in_scorecard=scorecard_text,
        burn_in_checklist=checklist_text,
        v1_readiness=event_alpha_v1_readiness.format_v1_readiness_report(readiness),
        health_guard=event_alpha_health_guard.format_health_guard_report(health),
        artifact_doctor=event_alpha_artifact_doctor.format_artifact_doctor_report(doctor),
        source_reliability=source_reliability,
        calibration=calibration,
        missed="Run --event-alpha-missed-report before exporting if fresh missed rows are required.\n",
        tuning=tuning,
        priors_shadow="Run --event-alpha-priors-shadow-report separately when current provider inputs are configured.\n",
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        outcome_rows=artifacts["outcome_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cards_dir=context.research_cards_dir,
        proposed_eval_dir=context.proposed_eval_cases_dir,
        profile=context.profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        date_range=f"{days}d",
    )
    print(event_alpha_burn_in_pack.format_burn_in_pack_result(result))


def event_alpha_integrated_radar_fill_outcomes_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_integrated_radar_fill_outcomes_report", *args, **kwargs)


def event_alpha_integrated_radar_outcome_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_integrated_radar_outcome_report", *args, **kwargs)


def event_alpha_integrated_radar_calibration_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_integrated_radar_calibration_report", *args, **kwargs)


def event_alpha_calibration_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_calibration_report", *args, **kwargs)


def event_alpha_fill_outcomes(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_fill_outcomes", *args, **kwargs)


def event_alpha_feedback_readiness_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_feedback_readiness_report", *args, **kwargs)


def event_alpha_observed_outcome_build(
    *,
    candidate_path: str | None,
    core_path: str | None,
    closes_path: str | None,
    candidate_id: str | None,
    core_id: str | None,
    evaluated_at: str | None,
    profile_assertion: str | None = None,
    artifact_namespace_assertion: str | None = None,
    out_path: str | None = None,
    confirm: bool = False,
    json_output: bool = False,
) -> Any:
    """Preview or explicitly stage one exact offline observed-market outcome."""

    from ...event_alpha.outcomes.observed_outcome_operator import (
        run_observed_outcome_operator,
    )

    result = run_observed_outcome_operator(
        candidate_path,
        core_path,
        closes_path,
        candidate_id,
        core_id,
        evaluated_at,
        profile_assertion=profile_assertion,
        artifact_namespace_assertion=artifact_namespace_assertion,
        out_path=out_path,
        confirm=confirm,
    )
    if json_output:
        print(result.to_json())
    else:
        print("Event Alpha exact observed-outcome operator")
        print("Research-only / unvalidated. Not a trade signal.")
        print(f"status: {'ok' if result.ok else 'blocked'}")
        print(f"mode: {result.mode}")
        print(f"written: {'yes' if result.written else 'no'}")
        print(
            "rows: "
            f"candidates={result.candidate_rows_supplied} "
            f"cores={result.core_rows_supplied} "
            f"observations={result.observations_accepted}/{result.observations_supplied}"
        )
        print("errors: " + (", ".join(result.errors) if result.errors else "none"))
        if result.outcome is not None:
            print(json.dumps(result.outcome, sort_keys=True, separators=(",", ":")))
    if not result.ok:
        raise SystemExit(2)
    return result


__all__ = tuple(name for name in _SERVICE_FUNCTION_NAMES if name != 'bind_scanner_globals')
