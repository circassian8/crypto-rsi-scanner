"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (go_no_go)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping
from .bindings import *  # noqa: F403

def event_alpha_notify_go_no_go(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> None:
    """Print a concise day-1 notification go/no-go decision."""
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "notify_no_key",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or context.profile
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
        routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile_name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    artifacts = _event_alpha_local_artifacts(run_limit=250, latest_alerts=False)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=core_rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=card_paths,
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        daily_brief_path=context.daily_brief_path,
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
        delivery_strict_scope="latest_run",
    )
    readiness = event_alpha_send_readiness.build_send_readiness(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        run_rows=artifacts["runs"].rows,
        core_opportunity_rows=core_rows,
        alert_rows=artifacts["alerts"].rows,
        delivery_rows=delivery_rows,
        artifact_doctor=doctor,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    latest_delivery_rows = [
        row for row in event_alpha_notification_delivery.latest_rows_by_delivery(delivery_rows)
        if not readiness.latest_run_id or str(row.get("run_id") or "") == readiness.latest_run_id
    ]
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    result = event_alpha_notification_go_no_go.build_go_no_go(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status=doctor.status,
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=clock_status,
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
        send_readiness=readiness,
        delivery_rows=latest_delivery_rows,
        delivery_history_rows=delivery_rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_go_no_go.format_go_no_go(result))
