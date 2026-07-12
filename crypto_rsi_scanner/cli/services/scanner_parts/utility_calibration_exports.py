"""Calibration, priors, and eval export utility commands."""

from __future__ import annotations

from .config_reports import (
    _event_alpha_alert_store_config_from_runtime,
    _event_alpha_context_block,
    _event_alpha_inputs_configured,
    _event_alpha_priors_config_from_runtime,
    _event_alert_config_from_runtime,
    _event_core_opportunity_store_config_from_runtime,
    _event_discovery_result_from_config,
    _event_feedback_config_from_runtime,
    _event_research_now,
    _setup_event_discovery_logging,
    resolve_event_alpha_artifact_context_for_report,
)
from .runtime import *

def _event_alpha_local_artifacts(
    *,
    context: Any,
    run_limit: int = 500,
    latest_alerts: bool = False,
) -> dict[str, Any]:
    """Load one resolved namespace without consulting legacy global paths.

    Alert snapshot return aliases remain diagnostics only. Exact observed
    outcome authority comes from the namespace's registered outcome artifacts,
    joined to the integrated candidate and Core opportunity stores.
    """
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=run_limit)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        context.alert_store_path,
        latest_only=latest_alerts,
        core_opportunity_store_path=context.core_opportunity_store_path,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    missed_rows = event_alpha_missed.load_missed_rows(context.missed_path)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(context.llm_budget_ledger_path)
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        latest_run=True,
        include_api=True,
    )
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=False,
        include_api=True,
    )
    incidents = event_incident_store.load_incidents(
        context.incident_store_path,
        limit=500,
        latest_run=True,
        include_api=True,
    )
    feedback_rows = [record.__dict__ for record in feedback.records]
    diagnostic_alert_outcome_rows = [row for row in alerts.rows if any(row.get(field) not in (None, "") for field in (
        "primary_horizon_return",
        "return_1h",
        "return_4h",
        "return_24h",
        "return_72h",
        "return_7d",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "mfe_mae_ratio",
        "direction_hit",
        "volatility_hit",
    ))]
    candidate_rows, integrated_core_rows = (
        event_integrated_radar_outcomes.load_integrated_radar_outcome_authority(
            context.namespace_dir
        )
    )
    integrated_outcome_rows = event_integrated_radar_outcomes.load_integrated_radar_outcomes(
        context.namespace_dir
    )
    event_alpha_outcome_rows = event_alpha_outcome_artifact_io.read_jsonl(
        context.outcomes_path
    )
    outcome_rows = [*event_alpha_outcome_rows, *integrated_outcome_rows]
    return {
        "runs": runs,
        "alerts": alerts,
        "feedback": feedback,
        "feedback_rows": feedback_rows,
        "missed_rows": missed_rows,
        "provider_rows": provider_rows,
        "budget_rows": budget_rows,
        "watchlist": watchlist,
        "hypotheses": hypotheses,
        "core_opportunities": core_opportunities,
        "candidate_rows": candidate_rows,
        "integrated_core_rows": integrated_core_rows,
        "incidents": incidents,
        "outcome_rows": outcome_rows,
        "event_alpha_outcome_rows": event_alpha_outcome_rows,
        "integrated_outcome_rows": integrated_outcome_rows,
        "diagnostic_alert_outcome_rows": diagnostic_alert_outcome_rows,
    }


def event_alpha_tuning_worksheet_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print weekly tuning recommendations without applying them."""
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
    artifacts = _event_alpha_local_artifacts(
        context=context,
        run_limit=500,
        latest_alerts=False,
    )
    worksheet = event_alpha_tuning.build_tuning_worksheet(
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        core_rows=artifacts["core_opportunities"].rows,
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
        now=_event_research_now(),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_tuning.format_tuning_worksheet(worksheet))

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_export_burn_in_pack(out_path, days, verbose, profile_name=profile_name, artifact_namespace=artifact_namespace, include_test_artifacts=include_test_artifacts, include_api_artifacts=include_api_artifacts)

def event_alpha_calibration_export_priors(out_path: str | None = None, verbose: bool = False) -> None:
    """Write reviewable calibration priors without applying them."""
    _setup_event_discovery_logging(verbose)
    alerts = event_alpha_alert_store.load_alert_snapshots(_event_alpha_alert_store_config_from_runtime().path)
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    cores = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=False,
    )
    path = Path(out_path).expanduser() if out_path else config.EVENT_ALPHA_PRIORS_PATH
    if not path.is_absolute():
        path = config.DATA_DIR / path
    payload = event_alpha_calibration.write_calibration_priors(
        path,
        alerts.rows,
        feedback_rows=feedback_rows,
        core_rows=cores.rows,
        generated_at=_event_research_now(),
    )
    print(event_alpha_calibration.format_priors_export(path, payload))

def event_alpha_priors_shadow_report(verbose: bool = False) -> None:
    """Print in-memory priors before/after comparison for current Event Alpha alerts."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha inputs ready for priors shadow report. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    alert_cfg = _event_alert_config_from_runtime()
    result = _event_discovery_result_from_config(now=_event_research_now())
    alerts = event_alerts.build_event_alert_candidates(result, cfg=alert_cfg, now=_event_research_now())
    priors_cfg = _event_alpha_priors_config_from_runtime()
    result_shadow = event_alpha_priors.compare_priors_shadow(alerts, cfg=priors_cfg, alert_cfg=alert_cfg)
    print(event_alpha_priors.format_priors_shadow_report(result_shadow))

def event_alpha_export_eval_cases_from_feedback(out_dir: str | None = None, verbose: bool = False) -> None:
    """Export proposed eval cases from feedback artifacts."""
    _setup_event_discovery_logging(verbose)
    alerts = event_alpha_alert_store.load_alert_snapshots(_event_alpha_alert_store_config_from_runtime().path)
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    cores = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=False,
    )
    result = event_alpha_eval_export.export_cases_from_feedback(
        alerts.rows,
        [record.__dict__ for record in feedback.records],
        out_dir or config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
        core_rows=cores.rows,
        now=_event_research_now(),
    )
    print(event_alpha_eval_export.format_eval_export_result(result))

def event_alpha_export_eval_cases_from_missed(out_dir: str | None = None, verbose: bool = False) -> None:
    """Export proposed eval cases from missed-opportunity artifacts."""
    _setup_event_discovery_logging(verbose)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    result = event_alpha_eval_export.export_cases_from_missed(
        missed_rows,
        out_dir or config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
    )
    print(event_alpha_eval_export.format_eval_export_result(result))
