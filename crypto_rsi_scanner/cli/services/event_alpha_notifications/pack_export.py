"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (pack_export)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping
from .bindings import *  # noqa: F403

def event_alpha_export_notification_pack(
    out: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Export a redacted zip of notification artifacts and operator reports."""
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    runs = event_alpha_notification_runs.load_notification_runs(context.notification_runs_path, limit=200)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=False)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    daily_brief = ""
    try:
        daily_brief = context.daily_brief_path.read_text(encoding="utf-8")
    except OSError:
        daily_brief = ""
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    lock_status = event_alpha_run_lock.inspect_run_lock(context, stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES)
    storage = Storage(config.DB_PATH)
    try:
        plan = event_alpha_notifications.build_notification_plan(
            [],
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(context.profile),
            now=_event_research_now(),
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    pause_state = _event_alpha_notification_pause_state(context)
    go_no_go = event_alpha_notification_go_no_go.build_go_no_go(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status="not_run",
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=_event_clock_status(),
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
    )
    doctor = event_alpha_environment_doctor.build_environment_doctor(
        profile=context.profile,
        context=context,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        lock_path=event_alpha_run_lock.lock_path_for_context(context),
        delivery_ledger_path=delivery_path,
        notification_runs_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        telegram_chat_ids_present=bool(config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        llm_provider=config.EVENT_LLM_PROVIDER,
        llm_enabled=config.EVENT_LLM_ENABLED,
        llm_extractor_provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        llm_extractor_enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        openai_key_present=bool(config.OPENAI_API_KEY),
        clock_status=_event_clock_status(),
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        python_executable=sys.executable,
        working_directory=str(config.DATA_DIR),
    )
    slo = event_alpha_notification_slo.build_slo_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        provider_health_rows=provider_rows,
        now=datetime.now(timezone.utc),
    )
    result = event_alpha_notification_pack.export_notification_pack(
        out_path=out,
        context=context,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        alert_rows=alerts.rows,
        provider_health_rows=provider_rows,
        go_no_go_text=event_alpha_notification_go_no_go.format_go_no_go(go_no_go),
        environment_doctor_text=event_alpha_environment_doctor.format_environment_doctor(doctor),
        slo_text=event_alpha_notification_slo.format_slo_report(slo),
        daily_brief_text=daily_brief,
        cards_dir=context.research_cards_dir,
    )
    print(event_alpha_notification_pack.format_notification_pack_result(result))
