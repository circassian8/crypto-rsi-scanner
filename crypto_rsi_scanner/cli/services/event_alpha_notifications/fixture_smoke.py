"""Fixture-backed Event Alpha notification smoke command."""

from __future__ import annotations

from types import SimpleNamespace

from .bindings import *  # noqa: F403
from .fixture_smoke_data import (
    build_control_notification_fixtures,
    build_core_fixture_rows,
    build_primary_notification_fixtures,
)


def _prepare_fixture_context(verbose: bool, event_now: str | datetime | None) -> tuple[Any, datetime, bool, str]:
    _refresh_scanner_globals()
    _setup_event_discovery_logging(verbose)
    now = _event_research_now(event_now)
    fixture_profile = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE", "fixture") or "fixture")
    context = event_alpha_artifacts.context_from_profile(
        fixture_profile,
        run_mode="test",
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "fixture_notify_smoke",
    )
    if str(context.artifact_namespace or "").endswith("smoke"):
        shutil.rmtree(context.namespace_dir, ignore_errors=True)
    _apply_event_alpha_context_to_config(context)
    _normalize_profile_paths()
    no_send = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    run_id = event_alpha_run_ledger.run_id_for(now, context.profile)
    return context, now, no_send, run_id


def _write_fixture_core_and_cards(
    *,
    context: Any,
    now: datetime,
    run_id: str,
    entry: Any,
    decision: Any,
    aave_entry: Any,
    aave_decision: Any,
) -> tuple[Any, list[dict[str, Any]], Any]:
    core_write = event_core_opportunity_store.write_core_opportunities(
        build_core_fixture_rows(entry, aave_entry),
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(context.core_opportunity_store_path),
        now=now,
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    card_write = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=[entry, aave_entry],
        alert_rows=core_rows,
        route_decisions=[decision, aave_decision],
        now=now,
        lineage_context=_event_alpha_card_lineage_context(
            run_id=run_id,
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=context.artifact_namespace,
        ),
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_write.card_paths,
        run_id=run_id,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    return core_write, core_rows, card_write


def _write_fixture_snapshots(
    *,
    context: Any,
    now: datetime,
    run_id: str,
    primary: dict[str, Any],
    controls: dict[str, Any],
    core_by_id: dict[str, dict[str, Any]],
) -> Path:
    snapshot_path = _write_fixture_alert_snapshot(
        context,
        entry=primary["entry"],
        decision=primary["decision"],
        run_id=run_id,
        observed_at=now,
        core_row=core_by_id.get("agg:fixture-velvet-spacex") or {},
    )
    for entry_key, decision_key, core_id in (
        ("aave_entry", "aave_decision", "agg:fixture-aave-kraken"),
        ("btc_entry", "btc_decision", "agg:fixture-btc-rejected"),
        ("tao_entry", "tao_decision", "agg:fixture-tao-rejected"),
        ("doge_entry", "doge_decision", "agg:fixture-doge-near-miss"),
    ):
        source = primary if entry_key in primary else controls
        _write_fixture_alert_snapshot(
            context,
            entry=source[entry_key],
            decision=source[decision_key],
            run_id=run_id,
            observed_at=now,
            core_row=core_by_id.get(core_id) or {},
        )
    return snapshot_path


def _fixture_notification_config(context: Any, *, no_send: bool) -> Any:
    return event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=not no_send,
        mode="research_only",
        notification_scope=event_alpha_notifications.NOTIFICATION_SCOPE_NAMESPACE,
        profile_name=context.profile,
        artifact_namespace=context.artifact_namespace,
        daily_digest_cooldown_hours=0,
        instant_escalation_cooldown_hours=0,
        max_instant_per_day=10,
        health_heartbeat_enabled=False,
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_max_items=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MAX_ITEMS,
        research_review_digest_min_score=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE,
        research_review_digest_cooldown_hours=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_COOLDOWN_HOURS,
        research_review_digest_include_local_only=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_LOCAL_ONLY,
        research_review_digest_include_sector=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_SECTOR,
        research_review_digest_send_with_alerts=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS,
        allow_source_only_narrative_digest=config.EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST,
    )


def _fixture_sender(delivered_messages: list[str]):
    def _fake_sender(message: str) -> event_alpha_notification_sender.NotificationSendAttemptResult:
        delivered_messages.append(message)
        chunks = event_alpha_notification_sender.telegram_chunk_count(message)
        return event_alpha_notification_sender.NotificationSendAttemptResult(
            attempted=True,
            success=True,
            recipient_count=1,
            delivered_count=1,
            failed_count=0,
            chunk_count=chunks,
            delivered_chunks=chunks,
            failed_chunks=0,
            channel_summary={"channel": "fixture", "delivered_count": 1},
        )

    return _fake_sender


def _send_fixture_notifications(
    *,
    context: Any,
    now: datetime,
    run_id: str,
    primary: dict[str, Any],
    controls: dict[str, Any],
    core_rows: list[dict[str, Any]],
    card_write: Any,
    no_send: bool,
) -> tuple[Any, Any, list[str]]:
    delivered_messages: list[str] = []
    delivery_cfg = _event_alpha_notification_delivery_config_from_runtime(context)
    send_result = event_alpha_notifications.send_notifications(
        [primary["decision"], primary["aave_decision"], controls["doge_decision"]]
        if config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED
        else [primary["decision"], primary["aave_decision"]],
        storage=_FixtureNotificationStorage(),
        cfg=_fixture_notification_config(context, no_send=no_send),
        send_fn=_fixture_sender(delivered_messages),
        now=now,
        profile=context.profile,
        card_path_by_alert_id=_card_paths_by_alert_id([primary["decision"]], card_write.card_paths),
        core_opportunity_rows=core_rows,
        include_health_heartbeat=False,
        delivery_cfg=delivery_cfg,
        run_id=run_id,
        namespace=context.artifact_namespace,
    )
    return send_result, delivery_cfg, delivered_messages


def _fixture_pipeline_result(
    *,
    context: Any,
    run_id: str,
    event_now: str | datetime | None,
    decision: Any,
    send_result: Any,
    card_write: Any,
    core_write: Any,
) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
        router_result=event_alpha_router.EventAlphaRouterResult(
            state_path=context.watchlist_state_path,
            rows_read=1,
            decisions=[decision],
            enabled=True,
        ),
        alerts=(),
        warnings=(),
        clock_status=_event_clock_status(event_now),
        cycle_completed=True,
        partial_results=False,
        send_requested=True,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=send_result.lane_items_attempted,
        send_lane_items_delivered=send_result.lane_items_delivered,
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=send_result.cooldown_blocks,
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
        notification_burn_in=True,
        research_card_paths=card_write.card_paths,
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        core_opportunity_write_attempted=core_write.attempted,
        core_opportunity_write_success=core_write.success,
        core_opportunity_rows_written=core_write.rows_written,
        core_opportunity_write_block_reason=core_write.block_reason,
        run_ledger_path=str(context.run_ledger_path),
        alert_store_path=str(context.alert_store_path),
        watchlist_state_path=str(context.watchlist_state_path),
        research_cards_dir=str(context.research_cards_dir),
        snapshot_write_attempted=True,
        snapshot_write_success=True,
        snapshot_rows_written=5,
        snapshot_write_block_reason=None,
        notification_delivery_records_written=send_result.delivery_records_written,
        notification_deliveries_delivered=send_result.deliveries_delivered,
        notification_deliveries_partial_delivered=send_result.deliveries_partial_delivered,
        notification_deliveries_failed=send_result.deliveries_failed,
        notification_deliveries_skipped_duplicate=send_result.deliveries_skipped_duplicate,
        notification_deliveries_skipped_in_flight=send_result.deliveries_skipped_in_flight,
        notification_deliveries_blocked=send_result.deliveries_blocked,
    )


def _write_fixture_run_rows(context: Any, now: datetime, pipeline_result: Any) -> dict[str, Any]:
    event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(context.run_ledger_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        with_llm=False,
        send_requested=True,
        notification_burn_in=True,
    )
    return event_alpha_notification_runs.append_notification_run(
        pipeline_result,
        cfg=event_alpha_notification_runs.EventAlphaNotificationRunsConfig(context.notification_runs_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        telegram_ready=False,
        send_guard_enabled=False,
    )


def _print_fixture_summary(
    *,
    context: Any,
    run_id: str,
    no_send: bool,
    delivered_messages: list[str],
    delivery_cfg: Any,
    send_result: Any,
    notification_row: dict[str, Any],
    snapshot_path: Path,
    core_write: Any,
    card_write: Any,
    canonical_core: dict[str, Any],
) -> None:
    print(_event_alpha_context_block(context))
    print("\n".join([
        "=" * 76,
        "EVENT ALPHA NOTIFICATION FIXTURE SMOKE (fake sender)",
        "=" * 76,
        f"run_id: {run_id}",
        f"mode: {'no-send guarded preview' if no_send else 'fake sender'}",
        f"fake_sender_delivered: {len(delivered_messages)}",
        f"delivery_path: {event_artifact_paths.artifact_display_path(delivery_cfg.path)}",
        f"delivery_records_written: {send_result.delivery_records_written}",
        f"delivery_delivered: {send_result.deliveries_delivered}",
        f"delivery_partial_delivered: {send_result.deliveries_partial_delivered}",
        f"notification_run_path: {event_artifact_paths.artifact_display_path(context.notification_runs_path)}",
        f"notification_would_send: {notification_row.get('would_send_count')}",
        f"alert_snapshot_path: {event_artifact_paths.artifact_display_path(snapshot_path)}",
        f"core_opportunity_store_path: {event_artifact_paths.artifact_display_path(context.core_opportunity_store_path)}",
        f"core_opportunities_written: {core_write.rows_written}",
        f"research_card_count: {card_write.cards_written}",
        f"research_card_index: {event_artifact_paths.artifact_display_path(card_write.index_path)}",
        "feedback: make event-feedback-useful "
        f"FEEDBACK_TARGET='{canonical_core.get('core_opportunity_id') or primary_alert_id(canonical_core)}'",
        "No live providers, Telegram sends, normal RSI alerts, paper trades, live DB rows, or execution were used.",
    ]))


def primary_alert_id(canonical_core: dict[str, Any]) -> str:
    return str(canonical_core.get("alert_id") or canonical_core.get("core_opportunity_id") or "agg:fixture-velvet-spacex")


def event_alpha_notify_fixture_smoke(
    verbose: bool = False,
    *,
    event_now: str | datetime | None = None,
) -> None:
    """Run a local fake-sender Event Alpha notification smoke."""
    context, now, no_send, run_id = _prepare_fixture_context(verbose, event_now)
    primary = build_primary_notification_fixtures(now)
    controls = build_control_notification_fixtures(now)
    core_write, core_rows, card_write = _write_fixture_core_and_cards(
        context=context,
        now=now,
        run_id=run_id,
        entry=primary["entry"],
        decision=primary["decision"],
        aave_entry=primary["aave_entry"],
        aave_decision=primary["aave_decision"],
    )
    core_by_id = {str(row.get("core_opportunity_id") or ""): row for row in core_rows}
    canonical_core = core_by_id.get("agg:fixture-velvet-spacex") or (core_rows[0] if core_rows else {})
    snapshot_path = _write_fixture_snapshots(
        context=context,
        now=now,
        run_id=run_id,
        primary=primary,
        controls=controls,
        core_by_id=core_by_id,
    )
    send_result, delivery_cfg, delivered_messages = _send_fixture_notifications(
        context=context,
        now=now,
        run_id=run_id,
        primary=primary,
        controls=controls,
        core_rows=core_rows,
        card_write=card_write,
        no_send=no_send,
    )
    pipeline_result = _fixture_pipeline_result(
        context=context,
        run_id=run_id,
        event_now=event_now,
        decision=primary["decision"],
        send_result=send_result,
        card_write=card_write,
        core_write=core_write,
    )
    notification_row = _write_fixture_run_rows(context, now, pipeline_result)
    _print_fixture_summary(
        context=context,
        run_id=run_id,
        no_send=no_send,
        delivered_messages=delivered_messages,
        delivery_cfg=delivery_cfg,
        send_result=send_result,
        notification_row=notification_row,
        snapshot_path=snapshot_path,
        core_write=core_write,
        card_write=card_write,
        canonical_core=canonical_core,
    )
